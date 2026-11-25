"""Sauna Stone Box v2.0: high-poly поверх ящика и запекание на его развёртку (4096; экспорт 1024 — texture_v2.py).

План: PLAN_v2.md. Каждая деталь — геометрия; маски цвета пишутся в атрибуты вершин той же геометрии.
Основа — Sauna Bench v2 (../bed/bake_v2.py): rbox, группы запекания, нормаль в два шага.

Нормаль. Стенки в игре сглажены целиком (vn отклонены от граней на 35-56°), поэтому карта — в касательном
пространстве СГЛАЖЕННОЙ модели: (1) object space с копии low-poly с плоскими гранями (лучи по нормали грани);
(2) сглаженная low-poly с картой object space через Normal Map (Object) -> NORMAL в tangent space.

Цели запекания — только то, что клиент показывает своими текселями: 16 наружных досок (остров на доску:
лицо, кромки, торцы) и дно внутри (остров 35). Изнанка стенок в игре показывает наружную сторону.

Группы: доски через одну (0 и 2 — с обручами; 1 и 3), чтобы лучи у щелей не ловили соседнюю доску; дно отдельно.
AO стенок — без камней и дна (иначе тень содержимого встанет и снаружи).

Запуск (из корня репозитория):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/wood-storage-box/bake_v2.py -- \
      [--groups wA,wB,floor] [--size 4096] [--nobake] [--blend] [--gpu]
Пишет bake/v2/{normal,ao,m1,m2,m3,idc,cover,mask}.png.
  idc = (код материала / 32, номер куска / 64, 0); смысл m1-m3 — в fields_walls.py и fields_floor.py.
"""
import sys
import time
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
OBJ = HERE / "originals" / "box.wooden.obj"
OUT = HERE / "bake" / "v2"
sys.path.insert(0, str(HERE))
import fields_floor as FF  # noqa: E402
import fields_walls as FW  # noqa: E402

ATTRS = ("m1", "m2", "m3", "idc")
STEP = 0.15


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


# ---------------------------------------------------------------- low-poly
def load_low():
    """Оригинал как есть (свои нормали OBJ — сглаженные, как в игре), метры -> см, оси OBJ (y вверх)."""
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="Y", up_axis="Z")
    low = bpy.context.selected_objects[0]
    low.name = "low_smooth"
    me = low.data
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get("co", co)
    me.vertices.foreach_set("co", co * 100.0)
    me.update()
    V, _, F = FW.load_obj()
    isl = FW.island_of_faces(F)
    assert len(me.polygons) == len(F), (len(me.polygons), len(F))
    # порядок граней как в файле: проверка по центрам
    cen = np.array([np.mean([V[c[0] - 1] for c in t], 0) for t in F])
    bc = np.array([tuple(p.center) for p in me.polygons])
    err = np.abs(cen - bc).max()
    log("low-poly", len(me.polygons), "faces, centre mismatch %.4f cm" % err)
    assert err < 0.01
    low["isl"] = isl.tolist()
    return low


def subset(low, keep, name, flat=False):
    """Копия low-poly только с гранями островов keep, UV сдвинуты в 0..1 (дно лежит в тайле v 1..2).
    flat: нормали граней + разрез острых рёбер (для лучей)."""
    me = low.data.copy()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    isl = low["isl"]
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if isl[f.index] not in keep], context="FACES")
    uv = bm.loops.layers.uv.active
    for f in bm.faces:
        du = np.floor(min(l[uv].uv.x for l in f.loops) + 1e-6)
        dv = np.floor(min(l[uv].uv.y for l in f.loops) + 1e-6)
        for l in f.loops:
            l[uv].uv.x -= du
            l[uv].uv.y -= dv
    if flat:
        sharp = [e for e in bm.edges if len(e.link_faces) == 2
                 and e.link_faces[0].normal.angle(e.link_faces[1].normal, 0) > 0.7]
        bmesh.ops.split_edges(bm, edges=sharp)
    bm.to_mesh(me)
    bm.free()
    if flat:
        bpy.context.view_layer.objects.active = ob
        with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
        for p in me.polygons:
            p.use_smooth = False
    return ob


# ---------------------------------------------------------------- mesh from numpy
def set_attrs(me, attrs, nv):
    for k in ATTRS:
        a = me.color_attributes.get(k) or me.color_attributes.new(k, "FLOAT_COLOR", "POINT")
        buf = np.zeros((nv, 4), np.float32)
        buf[:, 3] = 1
        if k in attrs:
            buf[:, :3] = np.asarray(attrs[k], np.float32).reshape(nv, 3)
        a.data.foreach_set("color", buf.ravel())


def mesh_np(name, V, Fp, attrs, group):
    """Объект из массивов: V (n, 3), Fp (m, k) — многоугольники по k вершин; attrs {имя: (n, 3)}."""
    me = bpy.data.meshes.new(name)
    V = np.asarray(V, np.float32)
    Fp = np.asarray(Fp, np.int32)
    n, (m, k) = len(V), Fp.shape
    me.vertices.add(n)
    me.vertices.foreach_set("co", V.ravel())
    me.loops.add(m * k)
    me.loops.foreach_set("vertex_index", Fp.ravel())
    me.polygons.add(m)
    me.polygons.foreach_set("loop_start", (np.arange(m) * k).astype(np.int32))
    me.update(calc_edges=True)
    me.validate(verbose=False)
    set_attrs(me, attrs, n)
    me.polygons.foreach_set("use_smooth", np.ones(m, bool))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob["group"] = group
    return ob


class Acc:
    def __init__(self, k):
        self.k = k
        self.V, self.F, self.A = [], [], {a: [] for a in ATTRS}
        self.n = 0

    def add(self, V, F, attrs):
        V = np.asarray(V, float).reshape(-1, 3)
        F = np.asarray(F)
        if F.shape[1] == 3 and attrs.get("closed", True):   # замкнутый кусок: обход наружу (иначе нормаль чёрная)
            c = V - V.mean(0)
            vol = np.einsum("ij,ij->i", c[F[:, 0]], np.cross(c[F[:, 1]], c[F[:, 2]])).sum()
            if vol < 0:
                F = F[:, ::-1]
        self.V.append(V)
        self.F.append(np.asarray(F) + self.n)
        for a in ATTRS:
            self.A[a].append(np.asarray(attrs.get(a, np.zeros((len(V), 3))), float).reshape(-1, 3))
        self.n += len(V)

    def build(self, name, group):
        if not self.V:
            return None
        return mesh_np(name, np.concatenate(self.V), np.concatenate(self.F),
                       {a: np.concatenate(v) for a, v in self.A.items()}, group)


def grid_quads(nr, nc, flip=False):
    ii = np.arange(nr * nc).reshape(nr, nc)
    q = np.stack([ii[:-1, :-1], ii[:-1, 1:], ii[1:, 1:], ii[1:, :-1]], -1).reshape(-1, 4)
    return q[:, ::-1] if flip else q


def consts(n, mat, tone=0.5, idx=0, **k):
    z = np.zeros(n)
    g = lambda key: np.asarray(k.get(key, z), float).reshape(n)
    return {"m1": np.stack([g("a1"), g("b1"), g("c1")], -1), "m2": np.stack([g("a2"), g("b2"), g("c2")], -1),
            "m3": np.stack([g("a3"), g("b3"), z + tone], -1),
            "idc": np.stack([np.broadcast_to(np.asarray(mat, float) / 32.0, (n,)), z + idx / 64.0, z], -1)}


# ---------------------------------------------------------------- доски: скруглённые коробки
FACES = (("x-", 0, -1), ("x+", 0, 1), ("y-", 1, -1), ("y+", 1, 1), ("z-", 2, -1), ("z+", 2, 1))
FACE_UV = {0: (1, 2), 1: (0, 2), 2: (1, 0)}


def rbox(name, b, r, group, idx):
    """Доска: скруглённая коробка по габаритам острова (lo..hi), грань — сетка (u, v), точка переносится на
    скруглённую поверхность, затем сдвиг по нормали h из FW.board_face. Изнанка — редкой сеткой и без рельефа.
    Верхняя торцевая доска: нижняя кромка поднята аркой прорези (slot_bottom), лицо и изнанка сжаты над ней."""
    lo, hi = np.asarray(b["lo"], float), np.asarray(b["hi"], float)
    k_in = b["k"]
    inner = "xyz"[k_in] + ("-" if b["s"] > 0 else "+")
    acc = Acc(4)
    for face, k, s in FACES:
        step = 1.0 if face == inner else STEP
        ua, va = FACE_UV[k]
        us = np.arange(lo[ua], hi[ua] + 1e-6, step)
        vs = np.arange(lo[va], hi[va] + 1e-6, step)
        if us[-1] < hi[ua] - 1e-4:
            us = np.append(us, hi[ua])
        if vs[-1] < hi[va] - 1e-4:
            vs = np.append(vs, hi[va])
        U, Vg = np.meshgrid(us, vs)
        P0 = np.zeros(U.shape + (3,))
        P0[..., k] = hi[k] if s > 0 else lo[k]
        P0[..., ua] = U
        P0[..., va] = Vg
        c = np.clip(P0, lo + r, hi - r)
        d = P0 - c
        L = np.linalg.norm(d, axis=-1, keepdims=True)
        nrm = d / np.maximum(L, 1e-9)
        q = c + r * nrm
        if b["slot"]:
            yb = FW.slot_bottom(q[..., 0], lo[1])
            q[..., 1] = yb + (q[..., 1] - lo[1]) * (hi[1] - yb) / (hi[1] - lo[1])
        f = FW.board_face(b, face, U, Vg, q)
        Pf = q + nrm * f["h"][..., None]
        flip = (k == 0 and s < 0) or (k in (1, 2) and s > 0)
        sl = slice(None, None, -1) if flip else slice(None)
        nv, nu = U.shape
        z = np.zeros(U.shape)
        attrs = {"m1": f["m1"][:, sl], "m2": f["m2"][:, sl], "m3": f["m3"][:, sl],
                 "idc": np.stack([np.broadcast_to(np.asarray(f["mat"], float), U.shape) / 32.0, z + idx / 64.0, z], -1)[:, sl]}
        acc.add(Pf[:, sl].reshape(-1, 3), grid_quads(nv, nu), {kk: v.reshape(-1, 3) for kk, v in attrs.items()})
    return acc.build(name, group)


def build_walls(groups):
    bs = FW.boards()
    out = []
    for i, b in enumerate(bs):
        g = "wA" if b["plank"] % 2 == 0 else "wB"
        if g not in groups:
            continue
        ob = rbox(f"hp_board_{b['wall']}{b['plank']}", b, 0.35, g, i)
        out.append(ob)
        log("board", b["wall"], b["plank"], "island", b["island"], len(ob.data.vertices))
    if "wA" in groups:
        out += build_hoops(bs)
    return out


def build_hoops(bs):
    obs = []
    for hi_, ((y0, y1), plank) in enumerate(zip(FW.HOOPS, (0, 2))):
        C, N, ss, corners, joint = FW.hoop_layout(bs, plank, STEP)
        length = ss[-1]
        ys = np.arange(y0 - 0.3, y1 + 0.3 + 1e-6, 0.1)
        S, Y = np.meshgrid(ss, ys, indexing="ij")
        f = FW.hoop_field(S, Y, y0, y1, length, 300 + hi_, corners, joint)
        Pp = np.zeros(S.shape + (3,))
        Pp[..., 0] = C[:, 0][:, None] + N[:, 0][:, None] * (f["h"] + 0.03)
        Pp[..., 2] = C[:, 1][:, None] + N[:, 1][:, None] * (f["h"] + 0.03)
        Pp[..., 1] = Y
        n = S.size
        z = np.zeros(S.shape)
        mat = np.where(f["m2"][..., 0] > 0.5, FW.MAT["rivet"], FW.MAT["hoop"])
        attrs = {"m1": f["m1"], "m2": f["m2"], "m3": f["m3"],
                 "idc": np.stack([mat / 32.0, z + (40 + hi_) / 64.0, z], -1)}
        # обход: строки — вдоль контура, столбцы — по высоте; нормаль наружу проверяется ниже
        Q = grid_quads(*S.shape)
        ob = mesh_np(f"hp_hoop{hi_}", Pp.reshape(-1, 3), Q, {k: v.reshape(n, 3) for k, v in attrs.items()}, "wA")
        fix_outward(ob, lambda c: np.column_stack([c[:, 0], np.zeros(len(c)), c[:, 2]]))
        obs.append(ob)
        log("hoop", hi_, S.shape, "corners", len(corners), "joint s %.1f" % joint)
    return obs


def fix_outward(ob, outward):
    """Перевернуть все грани, если нормали в среднем смотрят внутрь (outward(центры) -> направление наружу)."""
    me = ob.data
    m = len(me.polygons)
    cen = np.empty(m * 3, np.float32)
    nr = np.empty(m * 3, np.float32)
    me.polygons.foreach_get("center", cen)
    me.polygons.foreach_get("normal", nr)
    cen, nr = cen.reshape(m, 3), nr.reshape(m, 3)
    d = outward(cen)
    if np.mean(np.sum(d * nr, 1)) < 0:
        me.flip_normals()
        me.update()
        log("  flipped", ob.name)


# ---------------------------------------------------------------- дно
def tube(C, R, seg=12):
    k = len(C)
    T = np.gradient(C, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-9
    up = np.where(np.abs(T[:, 1:2]) > 0.9, np.array([[1.0, 0, 0]]), np.array([[0, 1.0, 0]]))
    B1 = np.cross(T, up)
    B1 /= np.linalg.norm(B1, axis=1, keepdims=True)
    B2 = np.cross(T, B1)
    ph = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    V = C[:, None, :] + R[:, None, None] * (np.cos(ph)[None, :, None] * B1[:, None, :] + np.sin(ph)[None, :, None] * B2[:, None, :])
    ii = np.arange(k * seg).reshape(k, seg)
    Q = np.stack([ii[:-1], np.roll(ii[:-1], -1, 1), np.roll(ii[1:], -1, 1), ii[1:]], -1).reshape(-1, 4)
    return V.reshape(-1, 3), Q


def build_floor():
    out = []
    X, Z = FF.grid()
    f = FF.floor_field(X, Z)
    P = np.stack([X, f["y"], Z], -1)
    n = X.size
    z = np.zeros(X.shape)
    attrs = {"m1": f["m1"], "m2": f["m2"], "m3": f["m3"], "idc": np.stack([f["mat"] / 32.0, z, z], -1)}
    ob = mesh_np("hp_floor", P.reshape(-1, 3), grid_quads(*X.shape), {k: v.reshape(n, 3) for k, v in attrs.items()}, "floor")
    fix_outward(ob, lambda c: np.tile([0.0, 1.0, 0.0], (len(c), 1)))
    out.append(ob)
    log("floor field", X.shape)
    bed = lambda x, z_: float(FF.floor_field(np.array([[x]]), np.array([[z_]]))["bed_top"][0, 0])
    rng = np.random.default_rng(FF.SEED + 7)
    stones, coals, logs = Acc(3), Acc(3), Acc(3)
    items = FF.layout()
    cracked = set(rng.choice([i for i, it in enumerate(items) if it[0] == "stone" and it[3] > 3.0], 4, replace=False).tolist())
    split = next(i for i, it in enumerate(items) if it[0] == "stone" and 3.0 < it[3] < 4.0 and i not in cracked)
    for i, (kind, x, z_, r, layer, prm) in enumerate(items):
        base_y = bed(x, z_) - 0.5 + FF.heap_lift(x, z_)
        if layer == 1:
            base_y += r * 0.55
        if kind == "stone":
            old = rng.random() < 0.1
            if i == split:                                 # расколотый камень: две половинки рядом
                hn = rng.normal(size=3)
                hn[1] = 0
                hn /= np.linalg.norm(hn)
                sub = np.random.default_rng(int(rng.integers(1 << 30)))
                for sg in (1, -1):
                    sub2 = np.random.default_rng(1234)    # одинаковая форма у половинок
                    V, F, m = FF.stone_mesh(sub2, r, "chipped", half=(hn * sg, 0.0))
                    R = FF.rot_matrix(sub, 8)
                    V = FF.place(V, R, (x + sg * hn[0] * 0.45, base_y, z_ + sg * hn[2] * 0.45))
                    stones.add(V, F, consts(len(V), FF.MAT["stone"], tone=rng.random(), idx=i % 64, a1=m["rip"], b1=m["cav"],
                                            b2=np.maximum(m["chip"], 0.8 * (m["face"] > 0.5) * 0)))
                continue
            V, F, m = FF.stone_mesh(rng, r, "old" if old else "chipped", crack=i in cracked)
            R = FF.rot_matrix(rng, 25)
            V = FF.place(V, R, (x, base_y, z_))
            stones.add(V, F, consts(len(V), FF.MAT["stone_old" if old else "stone"], tone=rng.random(), idx=i % 64,
                                    a1=m["rip"], b1=m["cav"], b2=m["chip"]))
        elif kind == "coal":
            V, F, m = FF.coal_mesh(rng, r)
            R = FF.rot_matrix(rng, 30)
            V = FF.place(V, R, (x, base_y - 0.3, z_))
            coals.add(V, F, consts(len(V), FF.MAT["coal"], tone=rng.random(), idx=i % 64, a1=m["rip"], b1=m["cav"], a2=m["ember"]))
        else:
            V, F, m = FF.log_mesh(rng, r, prm["L"])
            yaw = prm["yaw"]
            R = np.array([[np.cos(yaw), 0, -np.sin(yaw)], [0, 1, 0], [np.sin(yaw), 0, np.cos(yaw)]])
            V = FF.place(V, R, (x, base_y - 0.6 * r, z_))
            logs.add(V, F, consts(len(V), FF.MAT["log"], tone=rng.random(), idx=i % 64, a1=m["rip"], b1=m["cav"], a2=m["ember"]))
    for acc, name in ((stones, "hp_stones"), (coals, "hp_coals"), (logs, "hp_logs")):
        ob = acc.build(name, "floor")
        out.append(ob)
        log(name, len(ob.data.vertices))
    out += build_scoop(f)
    out.append(build_leaf(out, items))
    return out


def build_scoop(f):
    L, W = FF.SCOOP["L"], FF.SCOOP["W"]
    us = np.arange(-L / 2 - 0.5, L / 2 + 0.3 + 1e-6, STEP)
    vs = np.arange(-W / 2 - 0.5, W / 2 + 0.5 + 1e-6, STEP)
    SU, SV = np.meshgrid(us, vs, indexing="ij")
    cx, cz = FF.SCOOP["c"]
    ca, sa = np.cos(FF.SCOOP["yaw"]), np.sin(FF.SCOOP["yaw"])
    X = cx + SU * ca - SV * sa
    Z = cz + SU * sa + SV * ca
    g = FF.floor_field(X, Z)["y"]
    ground = float(np.percentile(g, 70))
    H, m = FF.scoop_field(SU, SV, ground)
    P = np.stack([X, H, Z], -1)
    Q = grid_quads(*SU.shape)
    ok = ~np.isnan(P.reshape(-1, 3)[:, 1])
    Q = Q[ok[Q].all(1)]
    P = np.nan_to_num(P)
    n = SU.size
    att = consts(n, m["mat"].ravel(), tone=0.4, idx=50, a1=m["edge"].ravel(), c2=m["ash"].ravel(), a2=m["rivet"].ravel() * 0)
    att["m2"][:, 1] = m["rivet"].ravel()
    pan = mesh_np("hp_scoop", P.reshape(-1, 3), Q, att, "floor")
    fix_outward(pan, lambda c: np.tile([0.0, 1.0, 0.0], (len(c), 1)))
    # ручка: пруток от задней стенки назад и вверх, на конце петля
    top = ground + 0.35 + 0.06 * L + 3.2
    t = np.linspace(0, 1, 60)
    hu = -L / 2 - 0.1 - 13.0 * t
    hy = top + 0.1 + 1.2 * t - 0.6 * t * (1 - t)
    C = np.column_stack([cx + hu * ca, hy, cz + hu * sa])
    V1, Q1 = tube(C, np.full(len(t), 0.5), 12)
    a = np.linspace(0, 2 * np.pi, 80)
    rc = -L / 2 - 13.1 - 1.9
    ring = np.column_stack([cx + (rc + 1.9 * np.cos(a)) * ca - 1.9 * np.sin(a) * sa, top + 1.3 + 0.1 * np.sin(a),
                            cz + (rc + 1.9 * np.cos(a)) * sa + 1.9 * np.sin(a) * ca])
    V2, Q2 = tube(ring, np.full(len(a), 0.38), 10)
    acc = Acc(4)
    acc.add(V1, Q1, consts(len(V1), FF.MAT["scoop"], tone=0.4, idx=51))
    acc.add(V2, Q2, consts(len(V2), FF.MAT["scoop"], tone=0.4, idx=51))
    h = acc.build("hp_scoop_handle", "floor")
    log("scoop", len(pan.data.vertices), "handle", len(h.data.vertices), "ground %.2f" % ground)
    return [pan, h]


def build_leaf(floor_obs, items):
    """Сухой бурый лист на большом камне ближе к середине; ложится лучами на то, что под ним."""
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = [BVHTree.FromObject(o, dg) for o in floor_obs if o.name in ("hp_stones", "hp_coals", "hp_logs", "hp_floor")]
    big = [it for it in items if it[0] == "stone" and it[3] > 4.4 and it[4] == 0]
    tgt = min(big, key=lambda it: np.hypot(it[1] - 6.0, it[2] + 4.0))
    rng = np.random.default_rng(91)
    x, y, h, vein, burn = FF.leaf(8.2, rng)
    ang = np.radians(35.0)
    X = tgt[1] - 3.0 + x * np.cos(ang) - y * np.sin(ang)
    Z = tgt[2] - 2.0 + x * np.sin(ang) + y * np.cos(ang)
    Hs = np.zeros_like(X)
    for i in range(X.shape[0]):
        for j in range(X.shape[1]):
            best = -1e9
            for b in bvh:
                hit = b.ray_cast(Vector((X[i, j], 60.0, Z[i, j])), Vector((0, -1, 0)), 100.0)[0]
                if hit is not None:
                    best = max(best, hit.y)
            Hs[i, j] = best
    # лист жёсткий: опора — сглаженный максимум под ним (не проваливается в щели между камнями)
    from numpy.lib.stride_tricks import sliding_window_view as sw
    pad = np.pad(Hs, 4, mode="edge")
    Hm = sw(pad, (9, 9)).max(axis=(-1, -2))
    P = np.stack([X, Hm + 0.1 + h, Z], -1)
    nu, nv = x.shape
    att = consts(nu * nv, FF.MAT["leaf"], tone=0.6, idx=52, a1=vein.ravel(), b3=burn.ravel())
    att["m3"][:, 1] = burn.ravel()
    ob = mesh_np("hp_leaf", P.reshape(-1, 3), grid_quads(nu, nv), att, "floor")
    fix_outward(ob, lambda c: np.tile([0.0, 1.0, 0.0], (len(c), 1)))
    log("leaf on stone at %.1f %.1f" % (tgt[1], tgt[2]))
    return ob


# ---------------------------------------------------------------- bake (как ../bed/bake_v2.py)
def hp_material():
    m = bpy.data.materials.new("hp")
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL")
    bs = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    em = {}
    for k in ATTRS:
        a = N.new("ShaderNodeVertexColor")
        a.layer_name = k
        e = N.new("ShaderNodeEmission")
        L.new(a.outputs["Color"], e.inputs["Color"])
        em[k] = e
    w = N.new("ShaderNodeEmission")
    w.inputs["Color"].default_value = (1, 1, 1, 1)
    em["cover"] = w
    return m, out, bs, em


def set_pass(mat, which):
    m, out, bs, em = mat
    L = m.node_tree.links
    for l in list(out.inputs["Surface"].links):
        L.remove(l)
    L.new((bs if which == "view" else em[which]).outputs[0], out.inputs["Surface"])


def setup_cycles(gpu):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    if gpu:
        try:
            prefs = bpy.context.preferences.addons["cycles"].preferences
            for kind in ("OPTIX", "CUDA"):
                try:
                    prefs.compute_device_type = kind
                    prefs.get_devices()
                    ok = [d for d in prefs.devices if d.type == kind]
                    if ok:
                        for d in prefs.devices:
                            d.use = d.type == kind
                        sc.cycles.device = "GPU"
                        log("GPU", kind)
                        break
                except TypeError:
                    continue
        except Exception as e:  # noqa: BLE001
            log("GPU off:", e)
    sc.cycles.use_denoising = False
    sc.cycles.samples = 1
    if sc.world is None:
        sc.world = bpy.data.worlds.new("bake")
    sc.world.light_settings.distance = 3.0


def new_img(name, size):
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    return img


def save_png(img, path, arr=None):
    size = img.size[0]
    if arr is not None:
        buf = np.ones((size, size, 4), np.float32)
        buf[..., :3] = arr
        img.pixels.foreach_set(buf.ravel())
    out = bpy.data.images.new(img.name + "_out", size, size, alpha=False)
    out.colorspace_settings.name = "Non-Color"
    px = np.empty(size * size * 4, np.float32)
    img.pixels.foreach_get(px)
    out.pixels.foreach_set(px)
    out.filepath_raw = str(path)
    out.file_format = "PNG"
    out.save()
    bpy.data.images.remove(out)
    log("  ->", path.name)


def bake_pass(target, hp, kind, size, name, extr, samples=1, filt=1.5, margin=32, space="TANGENT"):
    sc = bpy.context.scene
    bk = sc.render.bake
    img = new_img(name, size)
    target["tex"].image = img
    target["mat"].node_tree.nodes.active = target["tex"]
    bk.use_selected_to_active = hp is not None
    bk.use_cage = False
    bk.cage_extrusion = extr
    bk.max_ray_distance = extr * 2.0
    bk.target = "IMAGE_TEXTURES"
    bk.normal_space = space
    bk.normal_r, bk.normal_g, bk.normal_b = "POS_X", "POS_Y", "POS_Z"
    bk.margin = margin
    bk.margin_type = "EXTEND"
    sc.cycles.samples = samples
    sc.cycles.filter_width = filt
    bpy.ops.object.select_all(action="DESELECT")
    if hp:
        for o in hp:
            o.select_set(True)
    ob = target["ob"]
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    log("bake", name, kind, space if kind == "NORMAL" else "")
    bpy.ops.object.bake(type=kind, use_clear=True, margin=margin)
    return img


def make_target(ob, use_map=None):
    m = bpy.data.materials.new(ob.name + "_bake")
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    tex = N.new("ShaderNodeTexImage")
    if use_map is not None:
        src = N.new("ShaderNodeTexImage")
        src.image = use_map
        src.interpolation = "Closest"
        nm = N.new("ShaderNodeNormalMap")
        nm.space = "OBJECT"
        bs = next(n for n in N if n.type == "BSDF_PRINCIPLED")
        L.new(src.outputs["Color"], nm.inputs["Color"])
        L.new(nm.outputs["Normal"], bs.inputs["Normal"])
    ob.data.materials.clear()
    ob.data.materials.append(m)
    for attr in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission",
                 "visible_volume_scatter", "visible_shadow"):
        setattr(ob, attr, False)
    return {"ob": ob, "mat": m, "tex": tex}


def piece_mask(target, size, tag):
    m = bpy.data.materials.new(f"mask_{tag}")
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL")
    e = N.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (1, 1, 1, 1)
    L.new(e.outputs[0], out.inputs["Surface"])
    tex = N.new("ShaderNodeTexImage")
    ob = target["ob"]
    old = list(ob.data.materials)
    ob.data.materials.clear()
    ob.data.materials.append(m)
    img = bake_pass({"ob": ob, "mat": m, "tex": tex}, None, "EMIT", size, f"{tag}_mask", 1.0, filt=0.01, margin=0)
    ob.data.materials.clear()
    for mm in old:
        ob.data.materials.append(mm)
    return img


def pixels(img):
    size = img.size[0]
    px = np.empty(size * size * 4, np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(size, size, 4)[..., :3]


def bake_group(low, keep, hp, size, extr, tag, mat, hide_for_ao=(), ao_dist=3.0):
    for o in hp:
        o.data.materials.clear()
        o.data.materials.append(mat[0])
    flat = make_target(subset(low, keep, f"ray_{tag}", flat=True))
    res = {}
    set_pass(mat, "view")
    obj_n = bake_pass(flat, hp, "NORMAL", size, f"{tag}_nobj", extr, space="OBJECT", margin=4)
    for o in hide_for_ao:
        o.hide_render = True
    bpy.context.scene.world.light_settings.distance = ao_dist
    res["ao"] = pixels(bake_pass(flat, hp, "AO", size, f"{tag}_ao", extr, samples=64, margin=4))
    for o in hide_for_ao:
        o.hide_render = False
    for k in (*ATTRS, "cover"):
        set_pass(mat, k)
        res[k] = pixels(bake_pass(flat, hp, "EMIT", size, f"{tag}_{k}", extr, filt=0.01 if k == "idc" else 1.5, margin=4))
    set_pass(mat, "view")
    smooth = make_target(subset(low, keep, f"smooth_{tag}"), use_map=obj_n)
    res["normal"] = pixels(bake_pass(smooth, None, "NORMAL", size, f"{tag}_ntan", extr, margin=4))
    mask = pixels(piece_mask(smooth, size, tag))[..., 0] > 0.5
    for im in list(bpy.data.images):
        if im.name.startswith(tag + "_"):
            bpy.data.images.remove(im)
    return res, mask


ISL_A = [FW.WALL_ISL[w][p] for w in FW.WALL_ISL for p in (0, 2)]
ISL_B = [FW.WALL_ISL[w][p] for w in FW.WALL_ISL for p in (1, 3)]
GROUPS = {"wA": (set(ISL_A), 1.5, 3.0), "wB": (set(ISL_B), 1.5, 3.0), "floor": ({35}, 14.0, 4.0)}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 4096
    groups = argv[argv.index("--groups") + 1].split(",") if "--groups" in argv else list(GROUPS)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    setup_cycles("--gpu" in argv)
    low = load_low()
    low.hide_render = True
    hp = build_walls(groups)
    if "floor" in groups:
        hp += build_floor()
    hp = [o for o in hp if o is not None]
    log("high-poly:", sum(len(o.data.vertices) for o in hp), "verts in", len(hp), "objects")
    if "--blend" in argv:
        OUT.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "highpoly.blend"))
    if "--nobake" in argv:
        log("done (no bake)")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    mat = hp_material()
    result = {}
    partial = set(groups) != set(GROUPS)
    if partial:                     # пекутся только эти группы; остальное — из прошлого запекания
        for k in ("ao", *ATTRS, "cover", "normal", "mask"):
            path = OUT / f"{k}.png"
            if path.exists():
                im = bpy.data.images.load(str(path))
                im.colorspace_settings.name = "Non-Color"
                result[k] = pixels(im).copy()
                bpy.data.images.remove(im)
        log("merging into the previous bake:", sorted(result))
    floor_obs = [o for o in hp if o["group"] == "floor"]
    for g in groups:
        keep, extr, aod = GROUPS[g]
        ghp = [o for o in hp if o["group"] == g]
        res, mask = bake_group(low, keep, ghp, size, extr, g, mat, floor_obs if g != "floor" else (), aod)
        for k, arr in res.items():
            if k not in result:
                result[k] = np.zeros_like(arr) if k != "normal" else np.zeros_like(arr) + (0.5, 0.5, 1.0)
            result[k][mask] = arr[mask]
        if "mask" not in result:
            result["mask"] = np.zeros((size, size, 3), np.float32)
        result["mask"][mask] = 1.0
        log("group", g, "texels", int(mask.sum()))
    holder = new_img("holder", size)
    for k, arr in result.items():
        save_png(holder, OUT / f"{k}.png", arr)
    log("done")


if __name__ == "__main__":
    main()
