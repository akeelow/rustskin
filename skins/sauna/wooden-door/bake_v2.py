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


PARTS = {"front": build_front, "edges": build_edges, "towel": build_towel, "leaves": build_leaves}
# группа: куски-цели (острова), вытяжка лучей (см)
GROUPS = {"front": ({FRONT}, 4.5)}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 4096
    parts = argv[argv.index("--parts") + 1].split(",") if "--parts" in argv else list(PARTS)
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
        for g, (keep, extr) in GROUPS.items():
            ghp = [o for o in hp if o["group"] == g]
            if not ghp:
                continue
            res, mask = BB.bake_group(low, keep, ghp, size, extr, g, mat)
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
