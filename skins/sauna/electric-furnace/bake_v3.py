"""Sauna Stove v3.0: high-poly поверх каменки и запекание на её развёртку (4096; экспорт 2048 — texture_v3.py).

План: PLAN_v3.md. Каждая деталь — геометрия; маски цвета пишутся в атрибуты вершин той же геометрии (fields_v3.py).

Нормаль (как Sauna Bench v2, гайд §9.2): модель частично сглажена (цоколь, железо — до 30–50°), поэтому
  1) запекание в object space с копии low-poly с плоскими гранями и разрезанными острыми рёбрами;
  2) перенос: сглаженная low-poly (нормали OBJ) + карта object space -> Normal Map (Object) -> запекание NORMAL в
     касательном пространстве (MikkTSpace, как в Unity).
Группы запекания — наборы ОСТРОВОВ UV (geom_v3.island_of_face, номера как в uv/islands_v3.md), у каждой свой
high-poly; результат сливается по маске текселей группы.

Запуск (из корня репозитория):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/electric-furnace/bake_v3.py -- \
      [--parts left,top,door] [--size 4096] [--nobake] [--blend] [--gpu]
Пишет bake/v3/{normal,ao,m1,m2,m3,idc,cover,mask,used}.png и highpoly.blend (--blend).
"""
import sys
import time
from pathlib import Path

import bmesh
import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
OBJ = HERE / "originals" / "electric.furnace.obj"
OUT = HERE / "bake" / "v3"
sys.path.insert(0, str(HERE))
import fields_v3 as FV  # noqa: E402
import geom_v3 as G  # noqa: E402

ATTRS = ("m1", "m2", "m3", "idc", "pos")
POS_LO, POS_SPAN = np.array([-40.0, 0.0, -40.0]), np.array([80.0, 120.0, 80.0])   # pos = (OBJ см - LO) / SPAN
CM = 0.01


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


# ---------------------------------------------------------------- low-poly
def load_low():
    """Оригинал как есть: свои нормали OBJ (сглаженные, как в игре). Меш — в координатах OBJ (м), объект повёрнут."""
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="NEGATIVE_Z", up_axis="Y")
    low = bpy.context.selected_objects[0]
    low.name = "low_smooth"
    isl = G.island_of_face()
    assert len(low.data.polygons) == len(isl), (len(low.data.polygons), len(isl))
    # порядок граней совпадает с OBJ: проверка по центру первой и последней грани
    V, T, N, F = G.load()
    for fi in (0, len(isl) - 1):
        c_obj = V[F[fi][:, 0]].mean(0) * CM
        c_bl = np.array(low.data.polygons[fi].center)
        assert np.abs(c_obj - c_bl).max() < 1e-4, (fi, c_obj, c_bl)
    return low


def subset(low, keep, name, flat=False, pieces=None):
    """Копия low-poly только с гранями островов keep (и кусков pieces — для общих развёрток: печётся одна копия).
    flat: нормали граней + разрез острых рёбер (для лучей)."""
    me = low.data.copy()
    ob = bpy.data.objects.new(name, me)
    ob.matrix_world = low.matrix_world
    bpy.context.scene.collection.objects.link(ob)
    isl = G.island_of_face()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    pc = G.piece_of_face() if pieces is not None else None
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if isl[f.index] not in keep
                               or (pc is not None and pc[f.index] not in pieces)], context="FACES")
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


def mesh_np(name, V, Q, attrs, low, group):
    """Объект из массивов (координаты OBJ в см): V (n, 3), Q (m, 4|3); attrs {имя: (n, 3)}."""
    me = bpy.data.meshes.new(name)
    n, m = len(V), len(Q)
    k = Q.shape[1]
    me.vertices.add(n)
    me.vertices.foreach_set("co", (np.asarray(V, np.float64) * CM).astype(np.float32).ravel())
    me.loops.add(m * k)
    me.loops.foreach_set("vertex_index", np.asarray(Q, np.int32).ravel())
    me.polygons.add(m)
    me.polygons.foreach_set("loop_start", (np.arange(m) * k).astype(np.int32))
    me.update(calc_edges=True)
    me.validate(verbose=False)
    set_attrs(me, attrs, n)
    me.polygons.foreach_set("use_smooth", np.ones(m, bool))
    ob = bpy.data.objects.new(name, me)
    ob.matrix_world = low.matrix_world
    bpy.context.scene.collection.objects.link(ob)
    ob["group"] = group
    return ob


def grid_quads(ny, nx):
    ii = np.arange(ny * nx).reshape(ny, nx)
    return np.stack([ii[:-1, :-1], ii[:-1, 1:], ii[1:, 1:], ii[1:, :-1]], -1).reshape(-1, 4)


def field_attrs(r):
    """Маски поля -> атрибуты (см. fields_v3.py)."""
    z = np.zeros_like(r["h"])
    g = lambda k: r.get(k, z)
    return {"m1": np.stack([np.clip(g("grain"), 0, 1), np.clip(g("cav"), 0, 1), np.clip(g("dent"), 0, 1)], -1),
            "m2": np.stack([np.clip(g("nail"), 0, 1), np.clip(g("knot"), 0, 1), np.clip(g("char"), 0, 1)], -1),
            "m3": np.stack([np.clip(g("rust"), 0, 1), np.clip(g("crust"), 0, 1), np.clip(g("tone"), 0, 1)], -1),
            "idc": np.stack([g("mat") / 32.0, (g("sid") + 1) / 32.0, np.clip(g("bark"), 0, 1)], -1)}


def grid_object(name, P, r, low, group, outward):
    """P (ny, nx, 3) — точки в см (OBJ); outward — вектор наружу: обход квадов разворачивается под него."""
    ny, nx, _ = P.shape
    Q = grid_quads(ny, nx)
    flatP = P.reshape(-1, 3)
    ok = np.isfinite(flatP).all(1)
    Q = Q[ok[Q].all(1)]                                   # NaN — вне островов: квады выбрасываются
    q0 = Q[len(Q) // 2]
    a, b, c = flatP[q0[0]], flatP[q0[1]], flatP[q0[3]]
    nrm = np.cross(b - a, c - a)
    if np.dot(nrm, outward) < 0:
        Q = Q[:, ::-1]
    flatP = np.where(ok[:, None], flatP, 0.0)
    rr = {k: (np.nan_to_num(v) if hasattr(v, "shape") else v) for k, v in r.items()}
    at = {k: v.reshape(-1, 3) for k, v in field_attrs(rr).items()}
    at["pos"] = np.clip((flatP - POS_LO) / POS_SPAN, 0, 1)
    return mesh_np(name, flatP, Q, at, low, group)


# ---------------------------------------------------------------- части
def build_left(low):
    f = FV.LeftSide()
    A, B = f.grid()
    t = time.time()
    r = f.field(A, B)
    log("left field", A.shape, f"{time.time() - t:.0f} s")
    P = np.stack([-r["h"], B, A], -1)
    return [grid_object("hp_left", P, r, low, "left", np.array([-1.0, 0, 0]))]


import fields_top_v3 as FT  # noqa: E402
import stones_v3 as ST  # noqa: E402


def pos_attr(V):
    return np.clip((np.asarray(V) - POS_LO) / POS_SPAN, 0, 1)


def const_attrs(n, mat, sid=0, tone=0.5):
    z = np.zeros(n)
    return {"m1": np.stack([z, z, z], -1), "m2": np.stack([z, z, z], -1), "m3": np.stack([z, z, z + tone], -1),
            "idc": np.stack([z + FV.MAT[mat] / 32.0, z + (sid + 1) / 32.0, z], -1)}


class Acc:
    """Копилка вершин/граней/атрибутов одного объекта (грани одного размера: все тройки или все четвёрки)."""

    def __init__(self):
        self.V, self.Q, self.A = [], [], {k: [] for k in ATTRS}
        self.n = 0

    def add(self, V, Q, attrs):
        V = np.asarray(V, float)
        self.V.append(V)
        self.Q.append(np.asarray(Q) + self.n)
        for k in ATTRS:
            if k == "pos":
                self.A[k].append(pos_attr(V))
            else:
                self.A[k].append(np.asarray(attrs.get(k, np.zeros((len(V), 3))), float))
        self.n += len(V)

    def build(self, name, low, group):
        return mesh_np(name, np.concatenate(self.V), np.concatenate(self.Q),
                       {k: np.concatenate(v) for k, v in self.A.items()}, low, group)


def tube(C, R, seg=10):
    """Трубка по ломаной C (k, 3) с радиусами R (k,); нормали наружу."""
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
    # обход: нормаль первой грани должна смотреть от оси наружу
    a, b, c = V.reshape(k, seg, 3)[0, 0], V.reshape(k, seg, 3)[0, 1], V.reshape(k, seg, 3)[1, 0]
    if np.dot(np.cross(b - a, c - a), a - C[0]) < 0:
        Q = Q[:, ::-1]
    return V.reshape(-1, 3), Q


def twisted_pair(C, r, pitch, seg=8):
    """Скрученная из двух прядей проволока по оси C: две трубки r, витки с шагом pitch (см)."""
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    T = np.gradient(C, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-9
    up = np.where(np.abs(T[:, 1:2]) > 0.9, np.array([[1.0, 0, 0]]), np.array([[0, 1.0, 0]]))
    B1 = np.cross(T, up)
    B1 /= np.linalg.norm(B1, axis=1, keepdims=True)
    B2 = np.cross(T, B1)
    Vs, Qs, n = [], [], 0
    for k in range(2):
        a = 2 * np.pi * s / pitch + k * np.pi
        Ck = C + 0.92 * r * (np.cos(a)[:, None] * B1 + np.sin(a)[:, None] * B2)
        V, Q = tube(Ck, np.full(len(C), r), seg)
        Vs.append(V)
        Qs.append(Q + n)
        n += len(V)
    return np.concatenate(Vs), np.concatenate(Qs)


def leaf(L, rng, nu=40, nv=15, curl_k=(0.08, 0.16)):
    """Берёзовый лист (из полока): u — вдоль жилки, v — поперёк. -> (x, y, h, жилки, v)."""
    U, Vv = np.meshgrid(np.linspace(0, 1, nu), np.linspace(-1, 1, nv), indexing="ij")
    W = 0.36 * L * (U ** 0.45) * (1 - U) ** 0.75 / (0.45 ** 0.45 * 0.55 ** 0.75) * 0.95
    W = W * (1 + 0.05 * np.sin(U * 26 + rng.uniform(0, 6)))
    x = U * L
    y = Vv * W
    vein = np.exp(-(np.abs(y) / 0.07) ** 2) * (U < 0.97)
    for k in range(1, 8):
        u0 = 0.1 + 0.11 * k
        along = x - (u0 * L + np.abs(y) * 0.95)
        vein = np.maximum(vein, 0.7 * np.exp(-(along / 0.06) ** 2) * (np.abs(y) < W * 0.9) * (u0 < 0.95))
    curl = rng.uniform(*curl_k) * L
    h = 0.06 * vein + curl * np.abs(Vv) ** 2.2 + 0.25 * np.sin(U * np.pi) * rng.uniform(-0.6, 1.0) * curl_k[1] / 0.16
    h = h + 0.04 * np.sin(Vv * 9 + U * 5) * np.abs(Vv)
    return x, y, h, vein, Vv


FACES = (("x-", 0, -1), ("x+", 0, 1), ("y-", 1, -1), ("y+", 1, 1), ("z-", 2, -1), ("z+", 2, 1))
FACE_UV = {0: (1, 2), 1: (0, 2), 2: (0, 1)}


def rbox(name, lo, hi, r, fn, low, group, step=FV.STEP, skip=()):
    """Скруглённая коробка (см): каждая грань — сетка (u, v), точки на скруглённой поверхности (смещение внутренней
    коробки на r), затем сдвиг по нормали h из fn(грань, U, V, P) -> dict поля. Рёбра соседних граней совпадают."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    acc = Acc()
    for face, k, sgn in FACES:
        if face in skip:
            continue
        ua, va = FACE_UV[k]
        us = np.arange(lo[ua], hi[ua] + 1e-6, step)
        vs = np.arange(lo[va], hi[va] + 1e-6, step)
        if us[-1] < hi[ua] - 1e-4:
            us = np.append(us, hi[ua])
        if vs[-1] < hi[va] - 1e-4:
            vs = np.append(vs, hi[va])
        U, Vv = np.meshgrid(us, vs)
        P0 = np.zeros(U.shape + (3,))
        P0[..., k] = hi[k] if sgn > 0 else lo[k]
        P0[..., ua] = U
        P0[..., va] = Vv
        c = np.clip(P0, lo + r, hi - r)
        d = P0 - c
        L = np.linalg.norm(d, axis=-1, keepdims=True)
        nrm = d / np.maximum(L, 1e-9)
        q = c + r * nrm
        f = fn(face, U, Vv, q)
        Pf = q + nrm * f["h"][..., None]
        nv_, nu_ = U.shape
        Q = grid_quads(nv_, nu_)
        a, b, cc = Pf[0, 0], Pf[0, 1], Pf[1, 0]
        out = np.zeros(3)
        out[k] = sgn
        if np.dot(np.cross(b - a, cc - a), out) < 0:
            Q = Q[:, ::-1]
        at = {kk: v.reshape(-1, 3) for kk, v in field_attrs(f).items()}
        acc.add(Pf.reshape(-1, 3), Q, at)
    return acc.build(name, low, group)


def build_top(low):
    f = FT.Top()
    X, Z = f.grid()
    t = time.time()
    r = f.field(X, Z)
    log("top field", X.shape, f"{time.time() - t:.0f} s")
    obs = [grid_object("hp_top", np.stack([X, r["h"], Z], -1), r, low, "top", np.array([0, 1.0, 0]))]
    # ---- кучи колотого базальта на чашах (PLAN §3.3)
    rng = np.random.default_rng(31)
    acc = Acc()
    for bi, (c, rc, rcut, big) in enumerate(FT.BURNERS):
        if big:
            hp = ST.heap(c, rc - 0.5, 114.15, rng, 8, (7.0, 9.0), 13, (3.0, 4.6), sub=5)
        else:
            hp = ST.heap(c, rc - 0.4, 114.15, rng, 6, (5.6, 7.2), 10, (2.4, 3.6), sub=5)
        for V, F, m in hp:
            n = len(V)
            at = {"m1": m["m1"], "m2": m["m2"], "m3": m["m3"],
                  "idc": np.stack([np.full(n, FV.MAT["stone"] / 32.0), np.full(n, (bi + 1) / 32.0), np.zeros(n)], -1)}
            acc.add(V, F, at)
    obs.append(acc.build("hp_stones", low, "top"))
    log("stones", acc.n)
    # ---- листья берёзы на плите спереди (сухие, один обожжён по краю)
    acc = Acc()
    for k, (lx, lz, L, ang) in enumerate(((-1.5, 25.0, 6.6, 0.35), (2.8, 23.4, 6.0, 2.5), (5.6, 26.4, 5.4, -0.6))):
        x, y, h, vein, vv = leaf(L, rng, curl_k=(0.02, 0.05))
        ca, sa = np.cos(ang), np.sin(ang)
        Xl = lx + x * ca - y * sa
        Zl = lz + x * sa + y * ca
        Yl = FT.Top.height_at(r["h"], X, Z, Xl, Zl) + h + 0.05 + 0.07 * k
        P = np.stack([Xl, Yl, Zl], -1)
        nu, nv = x.shape
        Q = grid_quads(nu, nv)
        a, b, cc = P[0, 0], P[0, 1], P[1, 0]
        if np.dot(np.cross(b - a, cc - a), [0, 1, 0]) < 0:
            Q = Q[:, ::-1]
        n = nu * nv
        at = const_attrs(n, "leaf", tone=rng.random())
        at["m1"][:, 0] = vein.ravel()
        if k == 1:
            at["m2"][:, 2] = np.clip((np.abs(vv.ravel()) - 0.7) / 0.3, 0, 1)
        acc.add(P.reshape(-1, 3), Q, at)
    obs.append(acc.build("hp_leaves", low, "top"))
    # ---- борт: 4 бруска
    for (nm, lo, hi, al) in FT.RIM_BOARDS:
        obs.append(rbox(f"hp_rim_{nm}", lo, hi, 0.35, lambda face, U, V, P, nm=nm, lo=lo, hi=hi, al=al:
                        FT.rim_face(nm, face, U, V, P, lo, hi, al), low, "top"))
    # ---- проволока на углах борта: 3 витка вокруг переднего/заднего бруска у каждого угла
    acc = Acc()
    for (nm, lo, hi, al) in FT.RIM_BOARDS[:2]:
        lo, hi = np.array(lo), np.array(hi)
        for xc in (lo[0] + 2.9, hi[0] - 2.9):
            n = 3 * 64
            t_ = np.linspace(0, 3 * 2 * np.pi, n)
            ry, rz = (hi[1] - lo[1]) / 2 + 0.28, (hi[2] - lo[2]) / 2 + 0.28
            yc, zc = (hi[1] + lo[1]) / 2, (hi[2] + lo[2]) / 2
            ct, st = np.cos(t_), np.sin(t_)
            C = np.column_stack([xc + 0.55 * t_ / (2 * np.pi) - 0.8, yc + ry * np.sign(st) * np.abs(st) ** 0.2,
                                 zc + rz * np.sign(ct) * np.abs(ct) ** 0.2])
            V, Q = twisted_pair(C, 0.14, 0.9)
            acc.add(V, Q, const_attrs(len(V), "wire", tone=0.4))
    obs.append(acc.build("hp_rimwire", low, "top"))
    return obs


def build_coil(low):
    """Обруч из двух скрученных прядей на внешнем витке спирали — на всех 4 спиралях (общая развёртка; малые —
    масштаб 0.766 больших)."""
    acc = Acc()
    for (c, rc, rcut, big) in FT.BURNERS:
        sc = 1.0 if big else 6.68 / 8.72
        R = 8.72 * sc
        ytop = 116.1 if big else 115.83
        t_ = np.linspace(0, 2 * np.pi, 720)
        C = np.column_stack([c[0] + R * np.cos(t_), np.full_like(t_, ytop + 0.17 * sc), c[1] + R * np.sin(t_)])
        V, Q = twisted_pair(C, 0.21 * sc, 1.0 * sc)
        acc.add(V, Q, const_attrs(len(V), "wire", tone=0.5))
    return [acc.build("hp_hoops", low, "coil")]


def build_caps(low):
    """Центры конфорок (общая развёртка ×4, куски 49–52): один и тот же камень, перенесённый преобразованием копии."""
    rng = np.random.default_rng(77)
    V, F, m = ST.stone(4.6, rng, sub=5, cracks=True)
    pcs = (49, 50, 51, 52)
    Vall, _, _, Fall = G.load()
    c0 = Vall[np.unique(Fall[G.piece_of_face() == pcs[0]][:, :, 0])].mean(0)
    V0 = V + np.array([c0[0], 116.0 - V[:, 1].min() - 0.4, c0[2]])
    acc = Acc()
    n = len(V)
    at = {"m1": m["m1"], "m2": m["m2"], "m3": m["m3"],
          "idc": np.stack([np.full(n, FV.MAT["stone"] / 32.0), np.zeros(n), np.zeros(n)], -1)}
    for p in pcs:
        if p == pcs[0]:
            Vk, Fk = V0, F
        else:
            R, t = G.copy_transform(pcs[0], p)
            Vk = V0 @ R.T + t
            Fk = F if np.linalg.det(R) > 0 else F[:, ::-1]
        acc.add(Vk, Fk, at)
    return [acc.build("hp_caps", low, "caps")]


import fields_door_v3 as FD  # noqa: E402


def strands(C, r, pitch, n=3, seg=8):
    """Свив из n прядей радиуса r по оси C с шагом pitch (верёвка — 3, проволока — 2)."""
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    T = np.gradient(C, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-9
    up = np.where(np.abs(T[:, 1:2]) > 0.9, np.array([[1.0, 0, 0]]), np.array([[0, 1.0, 0]]))
    B1 = np.cross(T, up)
    B1 /= np.linalg.norm(B1, axis=1, keepdims=True)
    B2 = np.cross(T, B1)
    Vs, Qs, m = [], [], 0
    off = r * (1.0 if n == 2 else 1.15)
    for k in range(n):
        a = 2 * np.pi * s / pitch + 2 * np.pi * k / n
        Ck = C + off * (np.cos(a)[:, None] * B1 + np.sin(a)[:, None] * B2)
        V, Q = tube(Ck, np.full(len(C), r), seg)
        Vs.append(V)
        Qs.append(Q + m)
        m += len(V)
    return np.concatenate(Vs), np.concatenate(Qs)


def build_door(low):
    obs = []
    f = FD.DoorFrame()
    X, Y = f.grid()
    r, win = f.field(X, Y)
    obs.append(grid_object("hp_doorframe", np.stack([X, Y, r["h"]], -1), r, low, "door", np.array([0, 0, 1.0])))
    for bar, (x0, x1) in FD.BARS.items():
        obs.append(rbox(f"hp_bar_{bar}", (x0, FD.BAR_Y[0], FD.BAR_Z[0]), (x1, FD.BAR_Y[1], FD.BAR_Z[1]), 0.3,
                        lambda face, U, V, P, bar=bar: FD.bar_face(bar, face, U, V, P), low, "door"))
    # ---- ручка: полоса 3.8 × 0.6 см по профилю модели
    ys = np.linspace(46.6, 93.1, 470)
    zc = FD.handle_z(ys) - 0.3
    C = np.column_stack([np.full_like(ys, sum(FD.HANDLE_X) / 2), ys, zc])
    T = np.gradient(C, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    Nn = np.column_stack([np.zeros(len(ys)), -T[:, 2], T[:, 1]])
    hw, ht, rr = 1.9, 0.3, 0.18
    th = np.linspace(0, 2 * np.pi, 40, endpoint=False)
    ca, sa = np.cos(th), np.sin(th)
    sx = np.sign(ca) * np.minimum(np.abs(ca) * 3, 1) * (hw - rr) + rr * ca
    sz = np.sign(sa) * np.minimum(np.abs(sa) * 3, 1) * (ht - rr * 0.6) + rr * 0.6 * sa
    V = C[:, None, :] + sx[None, :, None] * np.array([1.0, 0, 0])[None, None, :] + sz[None, :, None] * Nn[:, None, :]
    hm = 0.03 * (FV.n2(V[..., 0] * 2.0, V[..., 1] * 0.6, 71) - 0.5)
    V = V + hm[..., None] * np.stack([np.cos(th) * 0, np.zeros_like(th), np.sign(sa)], -1)[None]
    k, sg = V.shape[:2]
    ii = np.arange(k * sg).reshape(k, sg)
    Q = np.stack([ii[:-1], np.roll(ii[:-1], -1, 1), np.roll(ii[1:], -1, 1), ii[1:]], -1).reshape(-1, 4)
    a, b, c = V[1, 10], V[1, 11], V[2, 10]
    if np.dot(np.cross(b - a, c - a), V[1, 10] - C[1]) < 0:
        Q = Q[:, ::-1]
    acc = Acc()
    at = const_attrs(k * sg, "iron", sid=4)
    acc.add(V.reshape(-1, 3), Q, at)
    # ---- верёвка: 3 пряди, витки вокруг полосы от y 56 до 83, на концах — по 2 витка внахлёст (узел)
    turns = 28
    t_ = np.linspace(0, turns * 2 * np.pi, turns * 48)
    yy = 56.2 + (83.0 - 56.2) * t_ / t_[-1]
    zz = FD.handle_z(yy) - 0.3
    ex, ez = hw + 0.42, ht + 0.42
    cx, sx_ = np.cos(t_), np.sin(t_)
    px = sum(FD.HANDLE_X) / 2 + ex * np.sign(cx) * np.abs(cx) ** 0.35
    pz = zz + ez * np.sign(sx_) * np.abs(sx_) ** 0.35
    Cr = np.column_stack([px, yy, pz])
    Vr, Qr = strands(Cr, 0.2, 1.1, n=3, seg=7)
    ar = const_attrs(len(Vr), "rope", sid=5)
    acc.add(Vr, Qr, ar)
    for y0 in (56.0, 83.2):                     # обвязка концов: 2 тугих витка поперёк
        t2 = np.linspace(0, 2 * 2 * np.pi, 96)
        y2 = y0 + 0.5 * np.sin(t2 * 0.5)
        z2 = FD.handle_z(y2) - 0.3
        c2, s2 = np.cos(t2), np.sin(t2)
        C2 = np.column_stack([sum(FD.HANDLE_X) / 2 + (ex + 0.3) * np.sign(c2) * np.abs(c2) ** 0.35, y2,
                              z2 + (ez + 0.3) * np.sign(s2) * np.abs(s2) ** 0.35])
        V2, Q2 = strands(C2, 0.2, 1.1, n=3, seg=7)
        acc.add(V2, Q2, const_attrs(len(V2), "rope", sid=6))
    obs.append(acc.build("hp_handle", low, "door"))
    for cls, nm in ((FD.FrontFrame, "hp_front"), (FD.Strip80, "hp_strip80")):
        g = cls()
        Xg, Yg = g.grid()
        rg = g.field(Xg, Yg)
        obs.append(grid_object(nm, np.stack([Xg, Yg, rg["h"]], -1), rg, low, "door", np.array([0, 0, 1.0])))
    return obs


import fields_facades_v3 as FF  # noqa: E402


def build_facades(group):
    def f(low):
        obs = []
        for spec in FF.FACADES:
            if spec[1] != group:
                continue
            t = time.time()
            P, r = FF.facade_field(spec)
            out = np.zeros(3)
            out[spec[3]] = spec[4]
            obs.append(grid_object(f"hp_{spec[0]}", P, r, low, group, out))
            log("facade", spec[0], P.shape[:2], f"{time.time() - t:.0f} s")
        return obs
    return f


FACADE_GROUPS = {"right": 0.03, "rails85": 0.01, "rails86": 0.01, "post89": 0.01, "back": 0.03, "front2": 0.03,
                 "band": 0.015, "plinth": 0.03, "pallet": 0.02}


import fields_3d_v3 as F3  # noqa: E402


def displaced(low, name, group, islands, pieces, fn, edge=0.2):
    """Подразделённая копия граней модели (рёбра до edge см), смещённая fn(P, N) вдоль нормалей вершин; рядом — та же
    копия без смещения (plain_of = группа) для вычитания гранёности."""
    src = subset(low, islands, f"tmp_{name}", pieces=pieces)
    bm = bmesh.new()
    bm.from_mesh(src.data)
    for _ in range(8):
        long = [e for e in bm.edges if e.calc_length() > edge * CM]
        if not long:
            break
        bmesh.ops.subdivide_edges(bm, edges=long, cuts=1, use_grid_fill=True)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.normal_update()
    V = np.array([v.co for v in bm.verts]) / CM
    Nv = np.array([v.normal for v in bm.verts])
    Fi = np.array([[v.index for v in f.verts] for f in bm.faces])
    bm.free()
    bpy.data.objects.remove(src, do_unlink=True)
    r = fn(V, Nv)
    at = {"m1": np.stack([np.clip(r["grain"], 0, 1), np.clip(r["cav"], 0, 1), np.clip(r["dent"], 0, 1)], -1),
          "m2": np.stack([np.clip(r["nail"], 0, 1), np.clip(r["knot"], 0, 1), np.clip(r["char"], 0, 1)], -1),
          "m3": np.stack([np.clip(r["rust"], 0, 1), np.clip(r["crust"], 0, 1), np.clip(r["tone"], 0, 1)], -1),
          "idc": np.stack([r["mat"] / 32.0, (r["sid"] + 1) / 32.0, np.clip(r["bark"], 0, 1)], -1),
          "pos": pos_attr(V)}
    ob = mesh_np(name, V + Nv * r["h"][:, None], Fi, at, low, group)
    pl = mesh_np(name + "_plain", V, Fi, at, low, group + "_plain")
    pl["plain_of"] = group
    pl.hide_render = True
    log("displaced", name, len(V))
    return [ob]


def _fin_fn(p):
    if p in (15, 22):
        return F3.rebar3d(900 + p)
    if p == 20:
        return F3.charstick3d(900 + p)
    return F3.iron3d(900 + p, amp=0.06)


def build_fins(low):
    obs = []
    for p in range(13, 29):                                   # 16 пластин жалюзи (уникальные развёртки)
        isl = set(G.island_of_face()[G.piece_of_face() == p].tolist())
        obs += displaced(low, f"hp_fin_{p}", "fins", isl, {p}, _fin_fn(p))
    return obs


def _piece_islands(p):
    return set(G.island_of_face()[G.piece_of_face() == p].tolist())


def _center(p):
    V, T, N, F = G.load()
    pts = V[F[G.piece_of_face() == p][:, :, 0]].reshape(-1, 3)
    return ((pts[:, 0].min() + pts[:, 0].max()) / 2, (pts[:, 1].min() + pts[:, 1].max()) / 2)


def one(p, fn, group, edge=0.15):
    return lambda low: displaced(low, f"hp_{group}", group, _piece_islands(p), {p}, fn, edge)


def build_firebox(low):
    """Топка: куча колотого базальта на дне духовки (y 47.6), к задней стенке выше (до ~35 см), спереди — угли с
    трещинами-кубиками; печётся на стенки и дно лучами изнутри (PLAN §3.9)."""
    rng = np.random.default_rng(91)
    acc = Acc()
    heap = ST.heap((0.0, 3.0), 21.0, 47.6, rng, 34, (7.0, 11.0), 30, (3.5, 6.0), sub=4, crust=False, cell=0.4, lean=0.45)
    for V, F, m in heap:
        n = len(V)
        acc.add(V, F, {"m1": m["m1"], "m2": m["m2"], "m3": m["m3"],
                       "idc": np.stack([np.full(n, FV.MAT["stone"] / 32.0), np.full(n, 30 / 32.0), np.zeros(n)], -1)})
    for k in range(26):                                        # угли спереди, в нижней части кучи
        V, F, m = ST.charcoal(rng.uniform(3.5, 6.5), rng)
        R = ST.rot(rng)
        V = V @ R.T
        px, pz = rng.uniform(-19, 19), rng.uniform(8, 27)
        V = V + np.array([px, 47.6 - V[:, 1].min() + rng.uniform(0.0, 2.5), pz])
        n = len(V)
        acc.add(V, F, {"m1": m["m1"], "m2": m["m2"], "m3": m["m3"],
                       "idc": np.stack([np.full(n, FV.MAT["char"] / 32.0), np.full(n, 31 / 32.0), np.zeros(n)], -1)})
    log("firebox heap", acc.n)
    return [acc.build("hp_firebox", low, "firebox")]


PARTS = {"left": build_left, "top": build_top, "coil": build_coil, "caps": build_caps, "door": build_door}
# группа: (острова-цели, вытяжка лучей м, общие развёртки — AO только от своей геометрии)
GROUPS = {"left": ({2, 16}, 0.03, False),
          "top": (FT.TOP_ISLANDS | FT.RIM_ISLANDS, 0.085, False),
          "coil": (FT.COIL_ISLANDS, 0.012, True),
          "caps": (FT.CAP_ISLANDS, 0.06, True),
          "door": (FD.DOOR_ISLANDS | FD.BAR_ISLANDS | FD.HANDLE_ISLANDS | FD.FRONT_ISLANDS | FD.STRIP_ISLANDS, 0.045, False)}
PART_GROUPS = {"left": "left", "top": "top", "coil": "coil", "caps": "caps", "door": "door"}
# сложные детали: смещённые копии (группа: кусок, рельеф, вытяжка, общая ли развёртка)
DISPLACED = {
    "knob": (38, lambda: F3.knob3d(_center(38), 951), 0.008, True),
    "rosette": (44, lambda: F3.rosette3d(_center(44), 953), 0.008, True),
    "hinge": (65, lambda: F3.iron3d(955, amp=0.06), 0.008, True),
    "bolt": (32, lambda: F3.iron3d(957, amp=0.03), 0.008, True),
    "rack": (6, lambda: F3.iron3d(959, amp=0.04, soot=True, heavy=True), 0.008, True),
    "rackbar": (69, lambda: F3.iron3d(961, amp=0.03, soot=True, heavy=True), 0.006, True),
    "elem": (5, lambda: F3.iron3d(963, amp=0.04, soot=True, heavy=True), 0.008, True),
    "fanblade": (58, lambda: F3.iron3d(965, amp=0.03, soot=True), 0.006, True),
    "fan": (80, lambda: F3.iron3d(967, amp=0.03, soot=True), 0.006, True),
    "rbox": (61, lambda: F3.iron3d(969, amp=0.03, soot=True), 0.006, False),
}
for _g, (_p, _fn, _e, _sh) in DISPLACED.items():
    PARTS[_g] = (lambda p, fn, g: (lambda low: displaced(low, f"hp_{g}", g, _piece_islands(p), {p}, fn(), 0.15)))(_p, _fn, _g)
    PART_GROUPS[_g] = _g
    GROUPS[_g] = (_piece_islands(_p), _e, _sh, {_p})
# остальные видимые мелочи (аудит 22.11): откосы проёма, стенки лючка, кромки, боковины планок и стоек
DISPLACED2 = {
    "rest_soot": ({86, 87, 167, 168, 130, 133, 39}, None, lambda: F3.soot3d(971), 0.008, False),
    "rest_wood": ({118, 120, 76}, None, lambda: F3.wood3d(973), 0.008, False),
    "post_sides": ({81, 85}, {89}, lambda: F3.iron3d(975, amp=0.04), 0.006, True),
    "rail_sides": ({119, 121}, {85}, lambda: F3.iron3d(977, amp=0.04), 0.006, True),
    "rail86_sides": ({174, 175}, {86}, lambda: F3.iron3d(979, amp=0.04), 0.006, True),
    "rackbar2": ({78}, {68}, lambda: F3.iron3d(981, amp=0.03, soot=True, heavy=True), 0.006, True),
}
for _g, (_isl, _pcs, _fn, _e, _sh) in DISPLACED2.items():
    PARTS[_g] = (lambda isl, pcs, fn, g: (lambda low: displaced(low, f"hp_{g}", g, isl, pcs, fn(), 0.15)))(_isl, _pcs, _fn, _g)
    PART_GROUPS[_g] = _g
    GROUPS[_g] = (_isl, _e, _sh) + ((_pcs,) if _pcs else ())
PARTS["fins"] = build_fins
PARTS["firebox"] = build_firebox
PART_GROUPS["firebox"] = "firebox"
GROUPS["firebox"] = ({0, 1, 11, 23}, 0.35, False)
PART_GROUPS["fins"] = "fins"
GROUPS["fins"] = (set().union(*[_piece_islands(p) for p in range(13, 29)]), 0.01, False)
for _g, _e in FACADE_GROUPS.items():
    _specs = [sp for sp in FF.FACADES if sp[1] == _g]
    _isl = set().union(*[sp[2] for sp in _specs])
    _pcs = [sp[5] for sp in _specs if sp[5] is not None]
    PARTS[_g] = build_facades(_g)
    PART_GROUPS[_g] = _g
    GROUPS[_g] = (_isl, _e, bool(_pcs)) + ((set().union(*_pcs),) if _pcs else ())


# ---------------------------------------------------------------- запекание
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
    sc.world.light_settings.distance = 0.03      # AO: 3 см


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


def bake_pass(target, hp, kind, size, name, extr, samples=1, filt=1.5, margin=4, space="TANGENT"):
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
    bk.normal_r, bk.normal_g, bk.normal_b = "POS_X", "POS_Y", "POS_Z"   # OpenGL, как Unity
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


def white_mask(ob, size, tag):
    """Тексели граней объекта (без отступа): эмиссия белым."""
    m = bpy.data.materials.new(f"mask_{tag}")
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL")
    e = N.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (1, 1, 1, 1)
    L.new(e.outputs[0], out.inputs["Surface"])
    tex = N.new("ShaderNodeTexImage")
    old = list(ob.data.materials)
    ob.data.materials.clear()
    ob.data.materials.append(m)
    img = bake_pass({"ob": ob, "mat": m, "tex": tex}, None, "EMIT", size, f"{tag}_mask", 0.01, filt=0.01, margin=0)
    ob.data.materials.clear()
    for mm in old:
        ob.data.materials.append(mm)
    return img


def pixels(img):
    size = img.size[0]
    px = np.empty(size * size * 4, np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(size, size, 4)[..., :3]


def bake_group(low, keep, hp, size, extr, tag, mat, hide_for_ao=(), pieces=None):
    for o in hp:
        o.data.materials.clear()
        o.data.materials.append(mat[0])
    flat = make_target(subset(low, keep, f"ray_{tag}", flat=True, pieces=pieces))
    res = {}
    set_pass(mat, "view")
    obj_n = bake_pass(flat, hp, "NORMAL", size, f"{tag}_nobj", extr, space="OBJECT")
    plain = [o for o in bpy.data.objects if o.get("plain_of") == tag]
    if plain:
        # вычитание: n = норм(n_гладкой + (n_смещённой − n_копии без смещения)) — гранёность модели уходит целиком
        for o in plain:
            o.data.materials.clear()
            o.data.materials.append(mat[0])
            o.hide_render = False
        for o in hp:
            o.hide_render = True
        n0 = pixels(bake_pass(flat, plain, "NORMAL", size, f"{tag}_n0", extr, space="OBJECT")) * 2 - 1
        for o in plain:
            o.hide_render = True
        for o in hp:
            o.hide_render = False
        nd = pixels(obj_n) * 2 - 1
        sm0 = make_target(subset(low, keep, f"sm0_{tag}", pieces=pieces))
        ns = pixels(bake_pass(sm0, None, "NORMAL", size, f"{tag}_ns", extr, space="OBJECT")) * 2 - 1
        n = ns + (nd - n0)
        n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-6
        buf = np.ones((size, size, 4), np.float32)
        buf[..., :3] = n * 0.5 + 0.5
        obj_n.pixels.foreach_set(buf.ravel())
    for o in hide_for_ao:
        o.hide_render = True
    res["ao"] = pixels(bake_pass(flat, hp, "AO", size, f"{tag}_ao", extr, samples=64))
    for o in hide_for_ao:
        o.hide_render = False
    for k in (*ATTRS, "cover"):
        set_pass(mat, k)
        res[k] = pixels(bake_pass(flat, hp, "EMIT", size, f"{tag}_{k}", extr, filt=0.01 if k == "idc" else 1.5))
    set_pass(mat, "view")
    smooth = make_target(subset(low, keep, f"smooth_{tag}", pieces=pieces), use_map=obj_n)
    res["normal"] = pixels(bake_pass(smooth, None, "NORMAL", size, f"{tag}_ntan", extr))
    mask = pixels(white_mask(smooth["ob"], size, tag))[..., 0] > 0.5
    for im in list(bpy.data.images):
        if im.name.startswith(tag + "_"):
            bpy.data.images.remove(im)
    return res, mask


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 4096
    parts = argv[argv.index("--parts") + 1].split(",") if "--parts" in argv else list(PARTS)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    setup_cycles("--gpu" in argv)
    low = load_low()
    low.hide_render = True
    hp = []
    for p in parts:
        hp += PARTS[p](low)
    log("high-poly:", {o.name: (len(o.data.vertices), o["group"]) for o in hp})
    if "--nobake" not in argv:
        OUT.mkdir(parents=True, exist_ok=True)
        mat = hp_material()
        result = {}
        prev = {k: OUT / f"{k}.png" for k in ("ao", *ATTRS, "cover", "normal", "mask")}
        for k, path in prev.items():          # пекутся только группы этих частей; остальное — из прошлого запекания
            if path.exists():
                im = bpy.data.images.load(str(path))
                im.colorspace_settings.name = "Non-Color"
                if im.size[0] == size:
                    result[k] = pixels(im).copy()
                bpy.data.images.remove(im)
        log("merging into the previous bake:", sorted(result))
        used_path = OUT / "used.png"
        if not used_path.exists():           # все тексели модели (для отступов в texture_v3)
            holder = new_img("holder", size)
            low.hide_render = False
            save_png(holder, used_path, pixels(white_mask(low, size, "used")))
            low.hide_render = True
        groups = {PART_GROUPS[p] for p in parts}
        for g in groups:
            keep, extr, shared, *pcs = GROUPS[g]
            ghp = [o for o in hp if o["group"] == g]
            others = [o for o in hp if o["group"] != g] if shared else []
            res, mask = bake_group(low, keep, ghp, size, extr, g, mat, others, pieces=pcs[0] if pcs else None)
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
    if "--blend" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "highpoly.blend"))
    log("done")


if __name__ == "__main__":
    main()
