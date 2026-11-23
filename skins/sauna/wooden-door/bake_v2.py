"""Sauna Door v2.0: high-poly поверх двери и запекание на её развёртку (4096, экспорт 1024 — texture_v2.py).

План: PLAN_v2.md. Каждая деталь — геометрия (fields_door.py); маски цвета пишутся в атрибуты вершин той же геометрии.
Механика запекания — как у полока v2 (функции берутся из ../bed/bake_v2.py): нормаль в два шага — object space
с гранёной копии low-poly, затем касательная сглаженной low-poly с нормалями OBJ (зад, брусья и кромки модели
сглажены до 45–55°, как в игре), AO и маски — по группам.

Единицы — сантиметры: OBJ (метры) при загрузке умножается на 100, оси без поворота (x — ширина, y — вверх,
z — толщина, перед в +z).

Запуск (из корня репозитория):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/wooden-door/bake_v2.py -- \
      [--parts front,edges,towel,leaves] [--size 4096] [--nobake] [--blend] [--gpu]

Пишет bake/v2/{normal,ao,m1,m2,m3,idc,cover,mask}.png:
  m1 = (волокно, полость, вмятина), m2 = (гвоздь, сучок, затёртость у ручки), m3 = (строчка / замазка, полоса / подгиб,
  тон доски), idc = (код материала / 32, номер доски / 16, 0), mask — тексели запечённых групп.
"""
import importlib.util
import sys
import time
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OBJ = HERE / "originals" / "door.hinged.wood.obj"
OUT = HERE / "bake" / "v2"
sys.path.insert(0, str(HERE))
import fields_door as FD  # noqa: E402

_spec = importlib.util.spec_from_file_location("bed_bake", HERE.parent / "bed" / "bake_v2.py")
BB = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(BB)
log, grid_mesh, Acc, tube = BB.log, BB.grid_mesh, BB.Acc, BB.tube
_bed_subset = BB.subset


def subset(low, keep, name, flat=False):
    """Как bed/bake_v2.subset, но сглаженная копия сохраняет нормали OBJ. Проверено 23.11.2026: копия через bmesh
    теряет собственные нормали — плоский перед двери получал наклон до 82° (медиана 12°) от фасок кромок, и
    касательная нормаль запекалась с ложным градиентом (на стекле (140, 143) вместо (128, 128))."""
    if flat:
        return _bed_subset(low, keep, name, flat=True)
    pp = low["pp"]
    me0 = low.data
    cn = np.array([c.vector[:] for c in me0.corner_normals])
    loops = [i for p in me0.polygons if pp[p.index] in keep for i in p.loop_indices]
    vco = np.array([me0.vertices[me0.loops[i].vertex_index].co[:] for i in loops])
    ob = _bed_subset(low, keep, name, flat=False)
    me = ob.data
    co = np.array([me.vertices[l.vertex_index].co[:] for l in me.loops])
    assert len(co) == len(vco) and np.abs(co - vco).max() < 1e-4, "loop order changed in subset"
    me.normals_split_custom_set([tuple(v) for v in cn[loops]])
    me.update()
    got = np.array([c.vector[:] for c in me.corner_normals])
    err = np.degrees(np.arccos(np.clip((got * cn[loops]).sum(1), -1, 1))).max()
    log(f"  subset {name}: OBJ normals restored, max error {err:.2f}°")
    return ob


BB.subset = subset             # bake_group берёт subset из модуля полока

FRONT = 2                      # остров развёртки: перед + боковые кромки
MAT = FD.MAT


# ---------------------------------------------------------------- low-poly
def obj_islands():
    """Острова развёртки по треугольникам OBJ (как uv/analyze_uv.py) и центры треугольников (см)."""
    v, vt, tris = [], [], []
    for line in open(OBJ):
        p = line.split()
        if not p:
            continue
        if p[0] == "v":
            v.append([float(x) for x in p[1:4]])
        elif p[0] == "vt":
            vt.append([float(x) for x in p[1:3]])
        elif p[0] == "f":
            idx = [tuple(int(a) for a in s.split("/")) for s in p[1:]]
            for k in range(1, len(idx) - 1):
                tris.append((idx[0], idx[k], idx[k + 1]))
    v = np.array(v) * 100.0
    VI = np.array([[c[1] - 1 for c in t] for t in tris])
    C = np.array([[v[c[0] - 1] for c in t] for t in tris]).mean(1)
    parent = list(range(VI.max() + 1))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for t in VI:
        a, b, c = (find(int(x)) for x in t)
        parent[b] = a
        parent[c] = a
    roots = np.array([find(int(t[0])) for t in VI])
    _, ids = np.unique(roots, return_inverse=True)
    return ids, C


def load_low():
    """Оригинал как есть: свои нормали OBJ (сглаженные, как в игре), × 100 (см). low["pp"] — остров каждой грани."""
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="Y", up_axis="Z")
    low = bpy.context.selected_objects[0]
    low.name = "low_smooth"
    low.data.transform(Matrix.Scale(100.0, 4))
    low.data.update()
    ids, C = obj_islands()
    kd = KDTree(len(C))
    for i, c in enumerate(C):
        kd.insert(Vector(c), i)
    kd.balance()
    pp = []
    for p in low.data.polygons:
        _, i, d = kd.find(p.center)
        assert d < 0.05, ("polygon without an OBJ triangle", p.index, d)
        pp.append(int(ids[i]))
    low["pp"] = pp
    log("low-poly", len(low.data.polygons), "polygons, islands", sorted(set(pp)))
    return low


def field_attrs(f, extra=None):
    z = np.zeros_like(f["h"])
    g = lambda k: np.asarray(f.get(k, z), float)
    a = {
        "m1": np.stack([g("grain"), g("cavity"), g("dent")], -1),
        "m2": np.stack([g("nail"), g("knot"), g("wear")], -1),
        "m3": np.stack([g("putty"), z, g("tone") if "tone" in f else z + 0.5], -1),
        "idc": np.stack([g("mat") / 32.0, g("board") / 16.0, z], -1),
    }
    if extra:
        a.update(extra)
    return a


# ---------------------------------------------------------------- части
def build_front(low):
    X, Y = FD.front_grid()
    log("front field", X.shape)
    t0 = time.time()
    f = FD.Front().field(X, Y)
    log("  %.1fs, h %.2f..%.2f" % (time.time() - t0, f["h"].min(), f["h"].max()))
    P = np.stack([X, Y, FD.ZF + f["h"]], -1)
    ob = grid_mesh("hp_front", P, field_attrs(f))
    ob["group"] = "front"
    return [ob]


def build_edges(low):
    """Боковые кромки: сетка (y, z) в плоскости x = EDGE_X, сдвиг наружу."""
    out = []
    ys = np.arange(0.0, 212.4, FD.STEP)
    zs = np.arange(-5.0, 5.8, FD.STEP)
    Y, Z = np.meshgrid(ys, zs)
    for side, sgn in ((0, -1), (1, 1)):
        f = FD.edge_field(Y, Z, side)
        P = np.stack([FD.EDGE_X[side] + sgn * f["h"], Y, Z], -1)
        sl = slice(None, None, -1) if sgn < 0 else slice(None)         # грани наружу (±x)
        z = np.zeros_like(Y)
        a = {"m1": np.stack([f["grain"], f["cavity"], z], -1), "m2": np.stack([z, z, z], -1),
             "m3": np.stack([z, z, z + 0.5], -1), "idc": np.stack([f["mat"] / 32.0, z, z], -1)}
        ob = grid_mesh(f"hp_edge_{side}", P[:, sl], {k: v[:, sl] for k, v in a.items()})
        ob["group"] = "front"
        out.append(ob)
        log("edge", side, P.shape)
    return out


def ring_skirt(acc, ring, z_low, attrs_of):
    """Кромка ткани: от края слоя вниз до досок. ring (n, 3) — замкнутый контур; грани наружу."""
    xy = ring[:, :2]
    area = 0.5 * np.sum(xy[:, 0] * np.roll(xy[:, 1], -1) - np.roll(xy[:, 0], -1) * xy[:, 1])
    if area < 0:
        ring = ring[::-1]
    n = len(ring)
    low = ring.copy()
    low[:, 2] = z_low
    V = np.concatenate([ring, low])
    k = np.arange(n)
    Q = np.stack([k, k + n, (k + 1) % n + n, (k + 1) % n], -1)
    acc.add(V, Q, attrs_of(len(V)))


def build_towel(low):
    """Полотенце в два слоя (форма v1.2) с подгибами, строчкой и жатостью; гнутый гвоздь."""
    acc = Acc()
    for layer in (1, 0):
        P, m = FD.towel_grid(layer)
        P = P[::-1]                                   # строки снизу вверх: грани смотрят в +z
        m = {k: v[::-1] for k, v in m.items()}
        nt, ns = P.shape[:2]
        z = np.zeros((nt, ns))
        attrs = {"m1": np.stack([z, z, z], -1), "m2": np.stack([z, z, z], -1),
                 "m3": np.stack([m["stitch"], m["stripe"], m["hem"]], -1),
                 "idc": np.stack([z + MAT["towel"] / 32.0, z, z], -1)}
        ii = np.arange(nt * ns).reshape(nt, ns)
        Q = np.stack([ii[:-1, :-1], ii[:-1, 1:], ii[1:, 1:], ii[1:, :-1]], -1).reshape(-1, 4)
        acc.add(P.reshape(-1, 3), Q, {k: v.reshape(-1, 3) for k, v in attrs.items()})
        ring = np.concatenate([P[0, :], P[1:, -1], P[-1, -2::-1], P[-2:0:-1, 0]])
        st = np.concatenate([m["stripe"][0, :], m["stripe"][1:, -1], m["stripe"][-1, -2::-1], m["stripe"][-2:0:-1, 0]])

        def attrs_of(n, st=st):
            zz = np.zeros(n)
            s2 = np.concatenate([st, st])
            return {"m1": np.stack([zz, zz, zz], -1), "m2": np.stack([zz, zz, zz], -1),
                    "m3": np.stack([zz, s2, zz + 1.0], -1), "idc": np.stack([zz + MAT["towel"] / 32.0, zz, zz], -1)}
        ring_skirt(acc, ring, FD.ZF - 0.1, attrs_of)
    tw = acc.build("hp_towel")
    tw["group"] = "front"
    # гнутый гвоздь: стержень из доски, загнут вверх, ткань перекинута через него; шляпка
    hk = Acc()
    hx, hy = FD.HOOK
    ZF = FD.ZF
    C = np.array([(hx, hy - 0.6, ZF - 0.2), (hx, hy - 0.3, ZF + 2.6), (hx - 0.3, hy + 0.8, ZF + 3.6), (hx - 1.0, hy + 3.8, ZF + 3.9)])
    t = np.linspace(0, 1, 40)
    Cs = np.stack([np.interp(t * 3, np.arange(4), C[:, i]) for i in range(3)], -1)
    V, Q, _ = tube(Cs, np.full(len(Cs), 0.6), seg=12)
    hk.add(V, Q, BB.attrs_const(len(V), "twig"))
    # шляпка: сплюснутая сфера Ø 2 см на конце
    th, ph = np.meshgrid(np.linspace(0, np.pi, 10), np.linspace(0, 2 * np.pi, 17)[:-1], indexing="ij")
    c = C[-1] + np.array([-0.1, 0.4, 0.0])
    S = np.stack([c[0] + 1.0 * np.sin(th) * np.cos(ph), c[1] + 0.45 * np.cos(th), c[2] + 1.0 * np.sin(th) * np.sin(ph)], -1)
    nu, nv = S.shape[:2]
    ii = np.arange(nu * nv).reshape(nu, nv)
    Qs = np.stack([ii[:-1], np.roll(ii[:-1], -1, 1), np.roll(ii[1:], -1, 1), ii[1:]], -1).reshape(-1, 4)[:, ::-1]
    hk.add(S.reshape(-1, 3), Qs, BB.attrs_const(nu * nv, "twig"))
    hook = hk.build("hp_hook")
    bm = bmesh.new()
    bm.from_mesh(hook.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])        # шляпка-сфера: грани наружу
    bm.to_mesh(hook.data)
    bm.free()
    for k in ("idc",):
        a = hook.data.color_attributes[k]
        buf = np.zeros(len(hook.data.vertices) * 4, np.float32)
        a.data.foreach_get("color", buf)
        buf = buf.reshape(-1, 4)
        buf[:, 0] = MAT["hook"] / 32.0
        a.data.foreach_set("color", buf.ravel())
    hook["group"] = "front"
    return [tw, hook]


def build_leaves(low):
    """Два берёзовых листа у мокрого низа: прилипли к доскам, края подвёрнуты."""
    rng = np.random.default_rng(8)
    front = FD.Front()
    acc = Acc()
    for (lx, ly, L, ang) in FD.LEAVES:
        x, y, h, vein = FD.leaf_grid(L, rng)
        a = np.radians(ang)
        ca, sa = np.cos(a), np.sin(a)
        X = lx + (x - L / 2) * ca - y * sa
        Y = ly + (x - L / 2) * sa + y * ca
        base = front.field(X, Y)["h"]
        # лист лежит на гребнях: опора — сглаженный максимум поля под ним
        base = np.maximum(base, np.percentile(base, 70) - 0.15)
        P = np.stack([X, Y, FD.ZF + base + 0.12 + h], -1)
        nu, nv = x.shape
        ii = np.arange(nu * nv).reshape(nu, nv)
        Q = np.stack([ii[:-1, :-1], ii[1:, :-1], ii[1:, 1:], ii[:-1, 1:]], -1).reshape(-1, 4)
        at = BB.attrs_const(nu * nv, "leaf", tone=rng.random())
        at["m1"][:, 0] = vein.ravel()
        at["idc"][:, 0] = MAT["leaf"] / 32.0
        acc.add(P.reshape(-1, 3), Q, at)
        # черешок
        t = np.linspace(0, 1, 16)
        Cs = np.stack([lx - L / 2 * ca - 2.2 * t * ca, ly - L / 2 * sa - 2.2 * t * sa, np.zeros(16)], -1)
        Cs[:, 2] = FD.ZF + front.field(Cs[:, 0:1], Cs[:, 1:2])["h"][:, 0] + 0.2
        V, Qt, _ = tube(Cs, np.full(16, 0.16), seg=8)
        at = BB.attrs_const(len(V), "leaf", tone=0.2)
        at["idc"][:, 0] = MAT["leaf"] / 32.0
        acc.add(V, Qt, at)
    ob = acc.build("hp_leaves")
    ob["group"] = "front"
    return [ob]


# ================================================================ зад (v2.4)
def flip_quads(ob):
    """Развернуть грани (нормали в −z / наружу)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def check_normals(ob, want, name):
    """Средняя нормаль граней объекта против ожидаемого направления — гранями внутрь AO и нормаль чёрные."""
    n = np.zeros(len(ob.data.polygons) * 3, np.float32)
    ob.data.polygons.foreach_get("normal", n)
    m = n.reshape(-1, 3).mean(0)
    log(f"  {name}: mean normal {np.round(m, 2)} (want {want})")
    assert np.dot(m, want) > 0.3, f"{name}: faces point the wrong way"


def field_mesh(name, P, f, group, want, flip):
    attrs = {k: f[k] for k in ("m1", "m2", "m3")}
    z = np.zeros(P.shape[:2])
    attrs["idc"] = np.stack([np.asarray(f["mat"], float) / 32.0, f.get("board", z) / 16.0, z], -1)
    ob = grid_mesh(name, P, attrs)
    if flip:
        flip_quads(ob)
    check_normals(ob, np.array(want), name)
    ob["group"] = group
    return ob


def build_back(low):
    X, Y = FD.back_grid()
    log("back field", X.shape)
    f = FD.Back().field(X, Y)
    fa = field_attrs(f)
    f2 = dict(m1=fa["m1"], m2=fa["m2"], m3=fa["m3"], mat=f["mat"], board=f["board"])
    P = np.stack([X, Y, FD.ZB - f["h"]], -1)
    return [field_mesh("hp_back", P, f2, "back", (0, 0, -1), flip=True)]


def build_rails(low):
    fr = FD.Front()
    out = []
    for k, (lo, hi) in enumerate(FD.RAIL_BOX):
        ob = BB.rbox(f"hp_rail_{k}", lo, hi, 0.7,
                     lambda face, U, V, P, k=k, lo=lo, hi=hi: FD.rail_face(k, face, U, V, P, np.asarray(lo), np.asarray(hi), fr.through_rails),
                     step=FD.STEP, group="rails")
        out.append(ob)
    x0, x1, y0, y1 = FD.LOCK_BLOCK
    lo, hi = np.array([x0, y0, FD.ZR]), np.array([x1, y1, 0.0])
    out.append(BB.rbox("hp_lock", lo, hi, 0.7, lambda face, U, V, P: FD.lock_face(face, U, V, P, lo, hi),
                       step=FD.STEP, group="rails"))
    # петли: кованая полоса по лицу бруса, шарнир по кромке двери
    hg = FD.HINGE
    for k, yh in enumerate(FD.HINGES_Y):
        xs = np.arange(hg["xe"] - hg["L"] - 1.0, hg["xe"] + 0.3, FD.STEP * 0.8)
        ys = np.arange(yh - hg["h0"] / 2 - 1.0, yh + hg["h0"] / 2 + 1.0, FD.STEP * 0.8)
        X, Y = np.meshgrid(xs, ys)
        f = FD.hinge_field(X, Y, yh, k)
        P = np.stack([X, Y, FD.ZR - f["h"]], -1)
        out.append(field_mesh(f"hp_hinge_{k}", P, f, "rails", (0, 0, -1), flip=True))
    acc = Acc()

    def add(V, Q, mat, rid=None):
        a = BB.attrs_const(len(V), "twig")
        a["idc"][:, 0] = FD.MAT[mat] / 32.0
        if rid is not None:
            a["m1"][:, 0] = rid
        acc.add(V, Q, a)
    for yh in FD.HINGES_Y:                    # шарнир: ствол по кромке двери
        t = np.linspace(-hg["h0"] / 2 - 0.7, hg["h0"] / 2 + 0.7, 40)
        C = np.stack([np.full_like(t, hg["xe"] + 0.6), yh + t, np.full_like(t, FD.ZR - 0.5)], -1)
        V, Q, _ = tube(C, np.full(len(t), 1.1), seg=16)
        add(V, Q, "hinge")
    # проволока: последнего гвоздя у верхней петли нет — конец прикручен через брус; жгут Ø ~0.9 см, скрутка вниз
    yh = FD.HINGES_Y[1]
    xw = hg["xe"] - hg["L"] * 0.9
    for k in range(3):
        x = xw + k * 1.1
        key = np.array([(x - 0.4, yh - 5.0, FD.ZR + 0.1), (x - 0.2, yh - 3.6, FD.ZR - 0.6), (x, yh, FD.ZR - 1.0),
                        (x + 0.2, yh + 3.6, FD.ZR - 0.6), (x + 0.4, yh + 5.0, FD.ZR + 0.1)])
        s = np.linspace(0, 4, 60)
        C = np.stack([np.interp(s, np.arange(5), key[:, i]) for i in range(3)], -1)
        V, Q, rid = tube(C, np.full(len(s), 0.42), seg=10, twist=0.9, ridge=0.25)
        add(V, Q, "wire", rid)
    t = np.linspace(0, 1, 50)
    C = np.stack([xw + 1.1 + 0.6 * np.sin(t * 16), yh - 5.0 - 3.5 * t, FD.ZR - 0.4 - 0.3 * np.cos(t * 16)], -1)
    V, Q, rid = tube(C, np.full(len(t), 0.33), seg=8, twist=0.8, ridge=0.25)
    add(V, Q, "wire", rid)
    iron = acc.build("hp_hinge_iron")
    iron["group"] = "rails"
    out.append(iron)
    # верхняя и нижняя кромки: торцы досок переда и зада, стальной лист
    xs = np.arange(FD.EDGE_X[0] - 0.3, FD.EDGE_X[1] + 0.3, FD.STEP)
    zs = np.arange(-0.3, 5.7, FD.STEP)
    X, Z = np.meshgrid(xs, zs)
    for top, ye, want in ((True, 211.3, (0, 1, 0)), (False, -0.1, (0, -1, 0))):
        f = FD.end_field(X, Z, top)
        P = np.stack([X, ye + (1 if top else -1) * f["h"], Z], -1)
        zz = np.zeros_like(X)
        f2 = dict(m1=np.stack([f["grain"], f["cavity"], zz], -1), m2=np.stack([zz, zz, zz], -1),
                  m3=np.stack([zz, zz, zz + 0.4], -1), mat=f["mat"])
        out.append(field_mesh(f"hp_end_{'top' if top else 'bottom'}", P, f2, "rails", want, flip=top))
    return out


def build_braces(low):
    fr = FD.Front()
    out = []
    for bi, poly in enumerate(FD.BRACES):
        pa = np.array(poly)
        xs = np.arange(pa[:, 0].min() - 0.3, pa[:, 0].max() + 0.3, FD.STEP)
        ys = np.arange(pa[:, 1].min() - 0.3, pa[:, 1].max() + 0.3, FD.STEP)
        X, Y = np.meshgrid(xs, ys)
        f = FD.brace_field(X, Y, bi, fr.through_braces)
        P = np.stack([X, Y, FD.ZB - f["h"]], -1)
        ny, nx = X.shape
        ii = np.arange(ny * nx).reshape(ny, nx)
        ins = f["inside"]
        qm = ins[:-1, :-1] & ins[:-1, 1:] & ins[1:, 1:] & ins[1:, :-1]
        Q = np.stack([ii[:-1, :-1], ii[1:, :-1], ii[1:, 1:], ii[:-1, 1:]], -1)[qm]       # обход для −z
        z = np.zeros((ny, nx))
        attrs = {"m1": f["m1"], "m2": f["m2"], "m3": f["m3"], "idc": np.stack([np.asarray(f["mat"], float) / 32.0, z, z], -1)}
        acc = Acc()
        acc.add(P.reshape(-1, 3), Q, {k: v.reshape(-1, 3) for k, v in attrs.items()})
        # стенки по контуру: от поля досок до скругления лица
        area = 0.5 * np.sum(pa[:, 0] * np.roll(pa[:, 1], -1) - np.roll(pa[:, 0], -1) * pa[:, 1])
        zl = np.linspace(FD.ZB, FD.ZB - 3.6, 25)
        cx, cy = pa.mean(0)
        for i in range(len(pa)):
            a, b = pa[i], pa[(i + 1) % len(pa)]
            L = np.hypot(*(b - a))
            s = np.linspace(0, 1, max(2, int(L / FD.STEP)))
            pts = a[None] + s[:, None] * (b - a)[None]
            n_out = np.array([b[1] - a[1], a[0] - b[0]]) / L * (1 if area > 0 else -1)
            Vw = np.stack([np.repeat(pts[:, 0:1], len(zl), 1), np.repeat(pts[:, 1:2], len(zl), 1),
                           np.repeat(zl[None], len(pts), 0)], -1)
            nu, nv = len(pts), len(zl)
            jj = np.arange(nu * nv).reshape(nu, nv)
            Qw = np.stack([jj[:-1, :-1], jj[1:, :-1], jj[1:, 1:], jj[:-1, 1:]], -1).reshape(-1, 4)
            # нормаль квада (вдоль × вниз по z) должна смотреть наружу
            e1 = np.append(b - a, 0.0)
            e2 = np.array([0, 0, zl[1] - zl[0]])
            if np.dot(np.cross(e1, e2)[:2], n_out) < 0:
                Qw = Qw[:, ::-1]
            zz = np.zeros(nu * nv)
            g = FD.grain_ridge(Vw[..., 2].ravel(), (pts[:, 0:1] * 0 + s[:, None] * L).repeat(nv, 1).ravel(), 2.2, 650 + i)
            aw = {"m1": np.stack([g, zz, zz], -1), "m2": np.stack([zz, zz, sstep_np(1.6, 0.0, -(Vw[..., 2].ravel()) - 2.0)], -1),
                  "m3": np.stack([zz, zz, zz + 0.45 + 0.1 * bi], -1), "idc": np.stack([zz + FD.MAT["brace"] / 32.0, zz, zz], -1)}
            acc.add(Vw.reshape(-1, 3), Qw, aw)
        ob = acc.build(f"hp_brace_{bi}")
        ob["group"] = "braces"
        check_normals(ob, np.array((0, 0, -1)), ob.name)
        out.append(ob)
    return out


# ================================================================ ручка (v2.7)
def check_outward(ob, zmid, name):
    """Доля граней, смотрящих от оси ручки (у замкнутого тела средняя нормаль ≈ 0 — check_normals не годится)."""
    nf = len(ob.data.polygons)
    n = np.zeros(nf * 3, np.float32)
    c = np.zeros(nf * 3, np.float32)
    ob.data.polygons.foreach_get("normal", n)
    ob.data.polygons.foreach_get("center", c)
    n, c = n.reshape(-1, 3), c.reshape(-1, 3)
    out = c - np.array([FD.HC[0], FD.HC[1], zmid])
    out[:, 0] *= 0.3
    frac = float(((n * out).sum(1) > 0).mean())
    log(f"  {name}: outward {frac:.3f}")
    assert frac > 0.8, f"{name}: faces point inward"


def build_handle(low):
    """Ручка: основание и перекладина — поля fields_door (дерево), бечёвка — трубки со свивом. Копия сзади — зеркало
    по z (обе копии на одних текселях островов 8 и 9)."""
    out = []
    U, TH = FD.bar_grid()
    Pb, _, ab = FD.bar_field(U, TH)
    PH, R, Z, T = FD.boss_grid()
    Po, _, ao_ = FD.boss_field(PH, R, Z, T)
    paths = FD.twine_paths()
    for side, mirror in (("front", False), ("back", True)):
        mz = (lambda P: np.concatenate([P[..., :2], (FD.HANDLE_MIRROR - P[..., 2])[..., None]], -1)) if mirror else (lambda P: P)
        zm = lambda z: FD.HANDLE_MIRROR - z if mirror else z
        bar = grid_mesh(f"hp_handle_bar_{side}", mz(Pb), ab)
        if not mirror:
            flip_quads(bar)                    # сетка перекладины обходит сечение внутрь; зеркало разворачивает само
        boss = grid_mesh(f"hp_handle_boss_{side}", mz(Po), ao_)
        if mirror:
            flip_quads(boss)
        acc = Acc()
        for k, C in enumerate(paths):
            Rr = np.full(len(C), FD.TWINE_R)
            if k % 3:                           # хвосты (после каждой обмотки по два) сужаются под виток
                Rr = FD.TWINE_R * np.linspace(1.0, 0.55, len(C))
            V, Q, rid = tube(mz(C), Rr, seg=12, twist=0.7, ridge=0.3)
            a = BB.attrs_const(len(V), "twig")
            a["idc"][:, 0] = FD.MAT["twine"] / 32.0
            a["m1"][:, 0] = rid
            acc.add(V, Q, a)
        tw = acc.build(f"hp_twine_{side}")     # трубка сама строит обход наружу — на зеркале не разворачивать
        check_outward(bar, zm(11.0), bar.name)
        check_outward(boss, zm(6.5), boss.name)
        boss["group"] = "handle_boss"          # основание: 4 сектора на одних текселях — AO только от себя
        bar["group"] = tw["group"] = "handle_bar"
        out += [bar, boss, tw]
    return out


def sstep_np(e0, e1, x):
    return FD.sstep(e0, e1, x)


PARTS = {"front": build_front, "edges": build_edges, "towel": build_towel, "leaves": build_leaves,
         "back": build_back, "rails": build_rails, "braces": build_braces, "handle": build_handle}
# группа: куски-цели (острова), вытяжка лучей (см)
GROUPS = {"front": ({FRONT}, 4.5), "back": ({0, 4}, 3.2), "rails": ({1, 3, 5}, 2.6), "braces": ({6, 7}, 1.8),
          "handle_boss": ({8}, 1.2), "handle_bar": ({9}, 1.4)}
GROUP_PARTS = {"front": ("front", "edges", "towel", "leaves"), "back": ("back",), "rails": ("rails",), "braces": ("braces",),
               "handle_boss": ("handle",), "handle_bar": ("handle",)}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 4096
    groups = argv[argv.index("--groups") + 1].split(",") if "--groups" in argv else list(GROUPS)
    # для AO нужны и соседи (брусья и раскосы бросают тень на поле досок)
    parts = sorted({p for g in groups for p in GROUP_PARTS[g]} | ({"back", "rails", "braces"} if set(groups) & {"back", "rails", "braces"} else set()))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    BB.setup_cycles("--gpu" in argv)
    bpy.context.scene.world.light_settings.distance = 3.0          # AO: 3 см
    low = load_low()
    low.hide_render = True
    hp = []
    for p in parts:
        hp += PARTS[p](low)
    log("high-poly:", {o.name: (len(o.data.vertices), o["group"]) for o in hp})
    if "--nobake" not in argv:
        OUT.mkdir(parents=True, exist_ok=True)
        mat = BB.hp_material()
        result = {}
        if "--groups" in argv:          # пекутся только эти группы; остальное — из прошлого запекания
            for k in ("ao", "m1", "m2", "m3", "idc", "cover", "normal", "mask"):
                path = OUT / f"{k}.png"
                if path.exists():
                    im = bpy.data.images.load(str(path))
                    im.colorspace_settings.name = "Non-Color"
                    result[k] = BB.pixels(im).copy()
                    bpy.data.images.remove(im)
            log("merging into the previous bake:", sorted(result))
        for g in groups:
            keep, extr = GROUPS[g]
            ghp = [o for o in hp if o["group"] == g]
            if not ghp:
                continue
            hide = [o for o in hp if o["group"] == "handle_bar"] if g == "handle_boss" else ()
            res, mask = BB.bake_group(low, keep, ghp, size, extr, g, mat, hide_for_ao=hide)
            for k, arr in res.items():
                if k not in result:
                    result[k] = np.zeros_like(arr) if k != "normal" else np.zeros_like(arr) + (0.5, 0.5, 1.0)
                result[k][mask] = arr[mask]
            if "mask" not in result:
                result["mask"] = np.zeros((size, size, 3), np.float32)
            result["mask"][mask] = 1.0
            log("group", g, "texels", int(mask.sum()))
        holder = BB.new_img("holder", size)
        for k, arr in result.items():
            BB.save_png(holder, OUT / f"{k}.png", arr)
    if "--blend" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "highpoly.blend"))
    log("done")


if __name__ == "__main__":
    main()
