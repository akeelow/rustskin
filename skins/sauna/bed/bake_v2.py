"""Sauna Bench v2.0: high-poly поверх кровати и запекание на её развёртку (4096, экспорт 2048 — texture_v2.py).

План: PLAN_v2.md. Каждая деталь — геометрия; маски цвета пишутся в атрибуты вершин той же геометрии.

Нормаль. Модель в игре сглажена целиком (нормали вершин OBJ отклонены от граней на 20-60°, даже у брусьев),
поэтому карта нормалей должна быть в касательном пространстве СГЛАЖЕННОЙ модели (так устроена оригинальная карта
Facepunch). v1 пёк на плоских гранях — в игре брусья и доски шейдились «мылом». Здесь в два шага:
  1) запекание в object space с копии low-poly с плоскими гранями (лучи идут по нормали грани, не косо на углах);
  2) перенос: сглаженная low-poly (нормали OBJ) с картой object space через узел Normal Map (Object) ->
     запекание NORMAL в касательном пространстве (MikkTSpace, как в Unity).

Запуск (из корня репозитория):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/bed/bake_v2.py -- \
      [--parts deck,apron,towel] [--size 4096] [--nobake] [--blend] [--gpu]

Пишет bake/v2/{normal,ao,m1,m2,m3,idc,cover}.png (размер --size), сцену bake/v2/highpoly.blend (--blend).
  m1 = (волокно, полость, вмятина), m2 = (гвоздь, сучок, обугл.), m3 = (царапина, скоба, тон доски),
  idc = (код материала / 16, номер рейки / 16, 0), cover = где запечено high-poly (белое).
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
ROOT = HERE.parents[2]
OBJ = HERE / "originals" / "bed.obj"
OUT = HERE / "bake" / "v2"
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))
import fields_v2 as FV  # noqa: E402
from parts import pieces  # noqa: E402
from uv_zones import load_obj  # noqa: E402

BLANKET, PILLOW, MATTRESS = 0, 1, 2
ATTRS = ("m1", "m2", "m3", "idc")


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


# ---------------------------------------------------------------- low-poly
def piece_per_polygon(me):
    V, T, F = load_obj(OBJ)
    at = {}
    for n, fs in enumerate(pieces(V, F)):
        for f in fs:
            for i in F[f][0]:
                at.setdefault(tuple(round(c, 2) for c in V[i]), set()).add(n)
    out = []
    for p in me.polygons:
        votes = {}
        for vi in p.vertices:
            for n in at.get(tuple(round(c, 2) for c in me.vertices[vi].co), ()):
                votes[n] = votes.get(n, 0) + 1
        out.append(max(votes, key=votes.get) if votes else -1)
    return out


def load_low():
    """Оригинал как есть: свои нормали OBJ (сглаженные, как в игре)."""
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="Y", up_axis="Z")
    low = bpy.context.selected_objects[0]
    low.name = "low_smooth"
    pp = piece_per_polygon(low.data)
    assert -1 not in pp, "polygons with no matching piece"
    low["pp"] = pp
    return low


def subset(low, keep, name, flat=False):
    """Копия low-poly только с гранями кусков keep. flat: нормали граней + разрез острых рёбер (для лучей)."""
    me = low.data.copy()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    pp = low["pp"]
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if pp[f.index] not in keep], context="FACES")
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
def grid_mesh(name, P, attrs):
    """P: (ny, nx, 3) точки сетки; attrs: {имя: (ny, nx, 3)} -> объект с квадами и цветами вершин."""
    ny, nx, _ = P.shape
    me = bpy.data.meshes.new(name)
    nv = nx * ny
    me.vertices.add(nv)
    me.vertices.foreach_set("co", P.reshape(-1).astype(np.float32))
    ii = np.arange(nv).reshape(ny, nx)
    q = np.stack([ii[:-1, :-1], ii[:-1, 1:], ii[1:, 1:], ii[1:, :-1]], -1).reshape(-1, 4)
    nf = len(q)
    me.loops.add(nf * 4)
    me.loops.foreach_set("vertex_index", q.reshape(-1).astype(np.int32))
    me.polygons.add(nf)
    me.polygons.foreach_set("loop_start", (np.arange(nf) * 4).astype(np.int32))
    me.update(calc_edges=True)
    me.validate(verbose=False)
    set_attrs(me, attrs, nv)
    me.polygons.foreach_set("use_smooth", np.ones(nf, bool))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def set_attrs(me, attrs, nv):
    for k in ATTRS:
        a = me.color_attributes.get(k) or me.color_attributes.new(k, "FLOAT_COLOR", "POINT")
        buf = np.zeros((nv, 4), np.float32)
        buf[:, 3] = 1
        if k in attrs:
            buf[:, :3] = np.asarray(attrs[k], np.float32).reshape(nv, 3)
        a.data.foreach_set("color", buf.ravel())


# ---------------------------------------------------------------- parts
def build_deck():
    X, Y = FV.deck_grid()
    log("deck field", X.shape)
    f = FV.Deck().field(X, Y)
    P = np.stack([X, Y, FV.DECK_Z + f["h"]], -1)
    return [grid_mesh("hp_deck", P, field_attrs(f))]


def field_attrs(f):
    z = np.zeros_like(f["h"])
    g = lambda k: f.get(k, z)
    return {
        "m1": np.stack([g("grain"), g("cavity"), g("dent")], -1),
        "m2": np.stack([g("nail"), g("knot"), g("char")], -1),
        "m3": np.stack([g("scratch"), g("strap"), g("tone")], -1),
        "idc": np.stack([g("mat") / 32.0, g("slat") / 16.0, z], -1),
    }


def bvh_of(low, keep):
    ob = subset(low, keep, "tmp_bvh")
    bvh = BVHTree.FromObject(ob, bpy.context.evaluated_depsgraph_get())
    bpy.data.objects.remove(ob)
    return bvh


def build_apron(low):
    """Фартук: по две доски на каждой стороне поверх выпуклого бока матраса + жестяные уголки на скруглениях."""
    bvh = bvh_of(low, {MATTRESS})
    ap = FV.Apron()
    out = []
    step = FV.STEP
    zs = np.arange(36.8, 55.4, step)
    for side in range(4):
        a0, a1 = FV.SIDE_A[side]
        As = np.arange(a0 - 0.5, a1 + 0.5 + 1e-6, step)
        ax = 1 if side < 2 else 0
        sgn = (-1, 1, -1, 1)[side]
        coarse = np.arange(a0 - 0.5, a1 + 2.5, 2.0)
        S = np.full((len(zs), len(coarse)), np.nan)
        for j, a in enumerate(coarse):
            for i, z in enumerate(zs):
                o = Vector((a, 0, z)) if ax == 1 else Vector((0, a, z))
                o[ax] = sgn * 160.0
                d = Vector((0, 0, 0))
                d[ax] = -sgn
                hit = bvh.ray_cast(o, d, 200.0)[0]
                if hit is not None:
                    S[i, j] = hit[ax]
        # выше плеча луч попадает в верх матраса (далеко внутри) или мимо: такие точки отбрасываем и тянем
        # профиль бока от ближайшего правильного ряда по высоте
        outer = np.nanmax(S * sgn, 0)
        S = np.where(S * sgn < outer[None, :] - 2.5, np.nan, S)
        for j in range(S.shape[1]):
            col = S[:, j]
            ok = ~np.isnan(col)
            if not ok.any():
                S[:, j] = sgn * outer[j] if not np.isnan(outer[j]) else np.nan
                continue
            idx = np.arange(len(col))
            S[:, j] = np.interp(idx, idx[ok], col[ok])      # концы — значением крайнего правильного ряда
        bad = np.isnan(S).all(0)
        if bad.any():
            good = np.where(~bad)[0]
            for j in np.where(bad)[0]:
                S[:, j] = S[:, good[np.argmin(np.abs(good - j))]]
        Sf = np.stack([np.interp(As, coarse, S[i]) for i in range(len(zs))])
        A, Z = np.meshgrid(As, zs)
        f = ap.field(side, A, Z)
        P = np.zeros(A.shape + (3,))
        P[..., 2] = Z
        P[..., 1 - ax] = A
        P[..., ax] = Sf + sgn * f["h"]
        # грани наружу: столбцы вдоль +a, строки вверх; у y+ и x- порядок столбцов переворачиваем
        fl = slice(None, None, -1) if (ax == 1 and sgn > 0) or (ax == 0 and sgn < 0) else slice(None)
        ob = grid_mesh(f"hp_apron_{side}", P[:, fl], {k: v[:, fl] for k, v in field_attrs(f).items()})
        out.append(ob)
        log("apron side", side, A.shape, "axis range %.1f..%.1f" % (P[..., ax].min(), P[..., ax].max()))
    for corner, (cx, cy) in FV.CORNERS.items():
        t0, t1 = (np.radians(t) for t in FV.TIN_TH[corner])
        ths = np.arange(t0, t1, step / FV.CORNER_R)
        zt = np.arange(37.6, 55.2, step)
        TH, Z = np.meshgrid(ths, zt)
        R = np.zeros_like(TH)
        for j, th in enumerate(ths):
            d = Vector((np.cos(th), np.sin(th), 0))
            for i, z in enumerate(zt):
                c = Vector((cx, cy, z))
                hit = bvh.ray_cast(c + d * 60, -d, 80)[0]
                R[i, j] = (hit - c).length if hit is not None else FV.CORNER_R
        f = FV.tin_field(corner, TH, Z)
        rr = R + f["h"]
        P = np.stack([cx + rr * np.cos(TH), cy + rr * np.sin(TH), Z], -1)
        out.append(grid_mesh(f"hp_tin_{corner[0]}{corner[1]}", P, field_attrs(f)))
        log("tin", corner, TH.shape)
    return out


def build_towel(low):
    """Подушка -> сложенное полотенце: гладкая копия (Catmull-Clark 6), сдвиг по нормали (fields_v2.towel_disp)."""
    ob = subset(low, {PILLOW}, "hp_towel")
    ob["group"] = "pillow"
    bvh = BVHTree.FromObject(ob, bpy.context.evaluated_depsgraph_get())
    m = ob.modifiers.new("cc", "SUBSURF")
    m.levels = m.render_levels = 6
    bpy.context.view_layer.objects.active = ob
    with bpy.context.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier="cc")
    me = ob.data
    with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), bool))
    me.update()
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    nr = np.empty(n * 3, np.float32)
    me.vertices.foreach_get("co", co)
    me.vertices.foreach_get("normal", nr)
    co, nr = co.reshape(n, 3).astype(np.float64), nr.reshape(n, 3).astype(np.float64)
    # |y| торца подушки на этой высоте и глубине: сетка 0.5 см + билинейная интерполяция
    gx = np.arange(55.0, 110.0, 0.5)
    gz = np.arange(50.0, 70.0, 0.5)
    YE = np.zeros((2, len(gz), len(gx)))
    for si, sg in enumerate((-1, 1)):
        for i, z in enumerate(gz):
            for j, x in enumerate(gx):
                hit = bvh.ray_cast(Vector((x, sg * 100.0, z)), Vector((0, -sg, 0)), 150.0)[0]
                YE[si, i, j] = abs(hit.y) if hit is not None else np.nan
    for si in range(2):
        a = YE[si]
        a[np.isnan(a)] = np.nanmax(a)
    fx = np.clip((co[:, 0] - gx[0]) / 0.5, 0, len(gx) - 1.001)
    fz = np.clip((co[:, 2] - gz[0]) / 0.5, 0, len(gz) - 1.001)
    ix, iz = fx.astype(int), fz.astype(int)
    tx, tz = fx - ix, fz - iz
    side = (co[:, 1] > 0).astype(int)
    A = YE[side]
    ye = (A[np.arange(n), iz, ix] * (1 - tx) * (1 - tz) + A[np.arange(n), iz, ix + 1] * tx * (1 - tz)
          + A[np.arange(n), iz + 1, ix] * (1 - tx) * tz + A[np.arange(n), iz + 1, ix + 1] * tx * tz)
    d, mk = FV.towel_disp(co, nr, ye)
    me.vertices.foreach_set("co", (co + nr * d[:, None]).astype(np.float32).ravel())
    me.update()
    z = np.zeros(n)
    set_attrs(me, {"m1": np.stack([z, mk["cavity"], mk["dent"]], -1), "m2": np.stack([z, z, z], -1),
                   "m3": np.stack([mk["stitch"], mk["stripe"], z + 0.5], -1),
                   "idc": np.stack([z + FV.MAT["towel"] / 32.0, z, z], -1)}, n)
    log("towel", n)
    # хвост с бахромой на настиле
    xs = np.arange(FV.FLAP_X[0], FV.FLAP_X[1], FV.STEP)
    ys = np.arange(FV.FLAP_Y[0] - 0.6, FV.FLAP_Y[1] + 0.6, FV.STEP)
    X, Y = np.meshgrid(xs, ys)
    dh = FV.Deck().field(X, Y)["h"]
    f = FV.flap_field(X, Y, dh)
    P = np.stack([X, Y, FV.DECK_Z + f["h"]], -1)
    z = np.zeros_like(X)
    flap = grid_mesh("hp_towel_flap", P, {
        "m1": np.stack([z, f["cavity"], f["dent"]], -1), "m2": np.stack([f["fringe"] * 1.0, z, z], -1),
        "m3": np.stack([f["stitch"], f["stripe"], z + 0.5], -1),
        "idc": np.stack([np.where(f["mask"], FV.MAT["towel"], FV.MAT["gap"]) / 32.0, z, z], -1)})
    return [ob, flap]


# ---------------------------------------------------------------- веник, листья, веточки (на настиле)
def mesh_np(name, V, Q, attrs):
    """Объект из массивов: V (n, 3), Q (m, 4) — квады; attrs {имя: (n, 3)}."""
    me = bpy.data.meshes.new(name)
    n, m = len(V), len(Q)
    me.vertices.add(n)
    me.vertices.foreach_set("co", np.asarray(V, np.float32).ravel())
    me.loops.add(m * 4)
    me.loops.foreach_set("vertex_index", np.asarray(Q, np.int32).ravel())
    me.polygons.add(m)
    me.polygons.foreach_set("loop_start", (np.arange(m) * 4).astype(np.int32))
    me.update(calc_edges=True)
    me.validate(verbose=False)
    set_attrs(me, attrs, n)
    me.polygons.foreach_set("use_smooth", np.ones(m, bool))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


class Acc:
    """Копилка вершин/квадов/атрибутов для одного объекта."""

    def __init__(self):
        self.V, self.Q, self.A = [], [], {k: [] for k in ATTRS}
        self.n = 0

    def add(self, V, Q, attrs):
        self.V.append(V)
        self.Q.append(Q + self.n)
        for k in ATTRS:
            self.A[k].append(attrs.get(k, np.zeros((len(V), 3))))
        self.n += len(V)

    def build(self, name):
        return mesh_np(name, np.concatenate(self.V), np.concatenate(self.Q),
                       {k: np.concatenate(v) for k, v in self.A.items()})


def grid_quads(nu, nv):
    ii = np.arange(nu * nv).reshape(nu, nv)
    return np.stack([ii[:-1, :-1], ii[1:, :-1], ii[1:, 1:], ii[:-1, 1:]], -1).reshape(-1, 4)


def attrs_const(n, mat, r=0.0, tone=0.5, cav=0.0):
    z = np.zeros(n)
    return {"m1": np.stack([z + r, z + cav, z], -1), "m2": np.stack([z, z, z], -1),
            "m3": np.stack([z, z, z + tone], -1), "idc": np.stack([z + FV.MAT[mat] / 32.0, z, z], -1)}


def tube(C, R, seg=10, twist=0.0, ridge=0.0):
    """Трубка по ломаной C (k, 3) с радиусами R (k,). twist — шаг свива (см), ridge — глубина свива (доля r)."""
    k = len(C)
    T = np.gradient(C, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-9
    up = np.where(np.abs(T[:, 2:3]) > 0.9, np.array([[1.0, 0, 0]]), np.array([[0, 0, 1.0]]))
    B1 = np.cross(T, up)
    B1 /= np.linalg.norm(B1, axis=1, keepdims=True)
    B2 = np.cross(T, B1)
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    ph = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    if twist:
        rid = np.sin(3 * ph[None, :] + (s[:, None] / twist) * 2 * np.pi) * 0.5 + 0.5
    else:
        rid = np.zeros((k, seg))
    rr = R[:, None] * (1 + ridge * (rid - 0.5) * 2)
    V = C[:, None, :] + rr[..., None] * (np.cos(ph)[None, :, None] * B1[:, None, :] + np.sin(ph)[None, :, None] * B2[:, None, :])
    ii = np.arange(k * seg).reshape(k, seg)
    # порядок обхода — нормали наружу (с обратным порядком бечёвка и прутья вышли чёрными)
    Q = np.stack([ii[:-1], np.roll(ii[:-1], -1, 1), np.roll(ii[1:], -1, 1), ii[1:]], -1).reshape(-1, 4)
    return V.reshape(-1, 3), Q, rid.reshape(-1)


def leaf(L, rng, nu=40, nv=15, curl_k=(0.08, 0.16)):
    """Берёзовый лист: u — вдоль жилки (0 черешок .. L кончик), v — поперёк. Возвращает (x, y, h, жилки)."""
    U, Vv = np.meshgrid(np.linspace(0, 1, nu), np.linspace(-1, 1, nv), indexing="ij")
    W = 0.36 * L * (U ** 0.45) * (1 - U) ** 0.75 / (0.45 ** 0.45 * 0.55 ** 0.75) * 0.95
    W = W * (1 + 0.05 * np.sin(U * 26 + rng.uniform(0, 6)))         # зубчики крупные, иначе не видно
    x = U * L
    y = Vv * W
    vein = np.exp(-(np.abs(y) / 0.07) ** 2) * (U < 0.97)
    for k in range(1, 8):
        u0 = 0.1 + 0.11 * k
        along = x - (u0 * L + np.abs(y) * 0.95)
        vein = np.maximum(vein, 0.7 * np.exp(-(along / 0.06) ** 2) * (np.abs(y) < W * 0.9) * (u0 < 0.95))
    curl = rng.uniform(*curl_k) * L
    h = 0.05 * vein + curl * np.abs(Vv) ** 2.2 + 0.25 * np.sin(U * np.pi) * rng.uniform(-0.6, 1.0) * curl_k[1] / 0.16
    h = h + 0.04 * np.sin(Vv * 9 + U * 5) * np.abs(Vv)
    return x, y, h, vein


def place_flat(x, y, h, pos, ang, base):
    ca, sa = np.cos(ang), np.sin(ang)
    X = pos[0] + x * ca - y * sa
    Y = pos[1] + x * sa + y * ca
    return np.stack([X, Y, base(X, Y) + h], -1)


def build_venik(low):
    """Плоский сушёный веник у изножья: прутья ручки, два пояса бечёвки, ~170 листьев кучей; опавшие листья и веточки."""
    deck = FV.Deck()
    rng = np.random.default_rng(55)

    def deck_top(X, Y, floor=-0.25):
        X2, Y2 = np.atleast_2d(np.asarray(X, float)), np.atleast_2d(np.asarray(Y, float))
        h = deck.field(X2, Y2)["h"].reshape(np.shape(X))
        return FV.DECK_Z + np.maximum(h, floor)

    acc = Acc()
    O = np.array([-31.0, 17.0])
    D = np.array([-0.96, 0.28])
    D = D / np.linalg.norm(D)
    Pp = np.array([-D[1], D[0]])
    deck_base = lambda X, Y: deck_top(X, Y, -0.2)

    def world(sv, pv, zv):
        XY = O[None, :] + sv[:, None] * D[None, :] + pv[:, None] * Pp[None, :]
        return np.column_stack([XY, deck_base(XY[:, 0], XY[:, 1]) + zv])

    for i in range(10):                                  # прутья ручки
        p0 = rng.uniform(-1.9, 1.9)
        r = rng.uniform(0.3, 0.45)
        zl = 0.35 + (i % 2) * 0.75 + rng.uniform(-0.1, 0.1)
        s_end = rng.uniform(26, 40)
        sv = np.linspace(-0.4 + rng.uniform(-0.6, 0.3), s_end, 90)
        pv = p0 * (0.75 + 0.25 * np.clip(sv / 12, 0, 1)) + 0.25 * np.sin(sv * 0.2 + i) + p0 * 0.35 * np.clip((sv - 14) / 20, 0, 1)
        Rv = r * (1 - 0.6 * np.clip((sv - 14) / (s_end - 14), 0, 1))
        C = world(sv, pv, zl + 0.0 * sv)
        V, Q, _ = tube(C, Rv, seg=10)
        acc.add(V, Q, attrs_const(len(V), "twig", tone=rng.random()))
    for s0 in (3.5, 9.5):                                # бечёвка: два пояса по 5 витков
        n = 5 * 40
        phi = np.linspace(0, 5 * 2 * np.pi, n)
        sv = s0 + 0.72 * phi / (2 * np.pi)
        C = world(sv, 2.45 * np.cos(phi), 0.95 + 1.05 * np.sin(phi))
        V, Q, rid = tube(C, np.full(n, 0.33), seg=8, twist=0.9, ridge=0.18)
        a = attrs_const(len(V), "twine", tone=0.5)
        a["m1"][:, 0] = rid
        acc.add(V, Q, a)
    order = []                                           # листья веером, куча выше к середине
    for _ in range(170):
        sv = rng.uniform(13, 46)
        Wd = 2.2 + 8.5 * ((sv - 13) / 33) ** 0.7
        pv = rng.uniform(-1, 1) * Wd
        pile = 1.5 * (1 - (pv / (Wd + 1)) ** 2) * (0.35 + 0.65 * np.clip((sv - 13) / 10, 0, 1)) * (1 - 0.5 * np.clip((sv - 38) / 8, 0, 1))
        order.append((rng.uniform(0, pile), sv, pv, Wd))
    order.sort()
    for zb, sv, pv, Wd in order:
        L = rng.uniform(4.2, 6.0)
        x, y, h, vein = leaf(L, rng, 34, 13, curl_k=(0.02, 0.05))     # веник прессованный: листья плоские
        ang_local = 0.5 * pv / Wd + rng.normal(0, 0.35)
        dirv = D * np.cos(ang_local) + Pp * np.sin(ang_local)
        ang = np.arctan2(dirv[1], dirv[0])
        base_xy = O + sv * D + pv * Pp - dirv * L * 0.35
        tilt = rng.uniform(-0.12, 0.12)
        P3 = place_flat(x, y, h + zb + 0.25 + tilt * (x - L / 2), base_xy, ang, deck_base)
        nu, nv = x.shape
        a = attrs_const(nu * nv, "leaf", tone=rng.random())
        a["m1"][:, 0] = vein.ravel()
        acc.add(P3.reshape(-1, 3), grid_quads(nu, nv), a)
    loose = ((-74.0, -31.2, 6.4, 0.2), (-61.0, 6.4, 6.0, -1.2), (-96.0, 27.0, 6.8, 2.8), (-35.0, 47.7, 5.8, 1.66),
             (-52.0, 30.5, 5.2, 2.2))
    for (lx, ly, L, a0) in loose:                        # опавшие листья
        x, y, h, vein = leaf(L, rng)
        P3 = place_flat(x, y, h + 0.08, np.array([lx, ly]), a0, lambda X, Y: deck_top(X, Y, -0.25))
        nu, nv = x.shape
        a = attrs_const(nu * nv, "leaf", tone=rng.random())
        a["m1"][:, 0] = vein.ravel()
        acc.add(P3.reshape(-1, 3), grid_quads(nu, nv), a)
    gy = deck.gc[9][0]                                   # лист наполовину в щели между рейками 9 и 10
    x, y, h, vein = leaf(6.2, rng)
    P3 = place_flat(x, y, h + 0.06, np.array([-88.0, gy - 2.2]), 1.35, lambda X, Y: deck_top(X, Y, -0.9))
    a = attrs_const(P3.shape[0] * P3.shape[1], "leaf", tone=0.8)
    a["m1"][:, 0] = vein.ravel()
    acc.add(P3.reshape(-1, 3), grid_quads(*x.shape), a)
    for (x0, y0, ang, L) in ((-45.0, 36.0, 2.6, 8.0), (-68.0, 20.0, -0.4, 6.0), (-24.0, 8.0, 0.9, 9.5)):   # веточки
        sv = np.linspace(0, L, 40)
        C2 = np.column_stack([x0 + sv * np.cos(ang) + 0.3 * np.sin(sv * 0.5), y0 + sv * np.sin(ang), np.zeros(40)])
        C2[:, 2] = deck_top(C2[:, 0], C2[:, 1], -0.2) + 0.2
        Rv = 0.2 * (1 - 0.4 * sv / L) * (1 + 0.25 * np.exp(-((sv % 2.6 - 1.3) / 0.15) ** 2))     # узелки
        V, Q, _ = tube(C2, Rv, seg=8)
        acc.add(V, Q, attrs_const(len(V), "twig", tone=0.3))
    return [acc.build("hp_venik")]


PARTS = {"deck": lambda low: build_deck(), "apron": build_apron, "towel": build_towel, "venik": build_venik}
PART_PIECES = {"deck": {MATTRESS}, "apron": {MATTRESS}, "towel": {PILLOW, MATTRESS}}


# ---------------------------------------------------------------- bake
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
    sc.world.light_settings.distance = 3.0      # AO: 3 см


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
    """Материал цели запекания: пустая картинка (активная); use_map — карта object space через Normal Map."""
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
    """Тексели граней цели (без отступа): эмиссия белым с самой low-poly."""
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
    t2 = {"ob": ob, "mat": m, "tex": tex}
    img = bake_pass(t2, None, "EMIT", size, f"{tag}_mask", 1.0, filt=0.01, margin=0)
    ob.data.materials.clear()
    for mm in old:
        ob.data.materials.append(mm)
    return img


def pixels(img):
    size = img.size[0]
    px = np.empty(size * size * 4, np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(size, size, 4)[..., :3]


def bake_group(low, keep, hp, size, extr, tag, mat):
    """Один набор кусков (keep) со своим high-poly: object-space нормаль -> касательная, AO, маски.
    Возвращает {карта: (size, size, 3)} и маску текселей группы."""
    for o in hp:
        o.data.materials.clear()
        o.data.materials.append(mat[0])
    flat = make_target(subset(low, keep, f"ray_{tag}", flat=True))
    res = {}
    set_pass(mat, "view")
    obj_n = bake_pass(flat, hp, "NORMAL", size, f"{tag}_nobj", extr, space="OBJECT", margin=4)
    res["ao"] = pixels(bake_pass(flat, hp, "AO", size, f"{tag}_ao", extr, samples=64, margin=4))
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


# группа запекания: имя, куски-цели, вытяжка лучей (см); high-poly помечен ob["group"]
# ---------------------------------------------------------------- брусковые куски: скруглённые коробки
import fields_box as FB  # noqa: E402

FACES = (("x-", 0, -1), ("x+", 0, 1), ("y-", 1, -1), ("y+", 1, 1), ("z-", 2, -1), ("z+", 2, 1))
FACE_UV = {0: (1, 2), 1: (0, 2), 2: (1, 0)}


def rbox(name, lo, hi, r, fn, step=FV.STEP, group="mattress"):
    """Скруглённая коробка (габариты lo..hi, радиус рёбер r): каждая грань — сетка в своих координатах (u, v),
    точки переносятся на скруглённую поверхность (смещение внутренней коробки на r), затем сдвиг по нормали h из
    fn(грань, U, V, P) -> {h, m1, m2, m3, mat}. Рёбра у соседних граней совпадают — без щелей."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    acc = Acc()
    for face, k, s in FACES:
        ua, va = FACE_UV[k]
        us = np.arange(lo[ua], hi[ua] + 1e-6, step)
        vs = np.arange(lo[va], hi[va] + 1e-6, step)
        if us[-1] < hi[ua] - 1e-4:
            us = np.append(us, hi[ua])
        if vs[-1] < hi[va] - 1e-4:
            vs = np.append(vs, hi[va])
        U, V = np.meshgrid(us, vs)
        P0 = np.zeros(U.shape + (3,))
        P0[..., k] = hi[k] if s > 0 else lo[k]
        P0[..., ua] = U
        P0[..., va] = V
        c = np.clip(P0, lo + r, hi - r)
        d = P0 - c
        L = np.linalg.norm(d, axis=-1, keepdims=True)
        nrm = d / np.maximum(L, 1e-9)
        q = c + r * nrm
        f = fn(face, U, V, q)
        Pf = q + nrm * f["h"][..., None]
        flip = (k == 0 and s < 0) or (k in (1, 2) and s > 0)
        sl = slice(None, None, -1) if flip else slice(None)
        nv, nu = U.shape
        z = np.zeros(U.shape)
        attrs = {"m1": f["m1"][:, sl], "m2": f["m2"][:, sl], "m3": f["m3"][:, sl],
                 "idc": np.stack([np.asarray(f["mat"], float) / 32.0, z, z], -1)[:, sl]}
        ii = np.arange(nv * nu).reshape(nv, nu)
        Q = np.stack([ii[:-1, :-1], ii[:-1, 1:], ii[1:, 1:], ii[1:, :-1]], -1).reshape(-1, 4)
        acc.add(Pf[:, sl].reshape(-1, 3), Q, {kk: v.reshape(-1, 3) for kk, v in attrs.items()})
    ob = acc.build(name)
    ob["group"] = group
    return ob


HB_BOX = {3: ((110.3, -62.8, 63.7), (112.8, 64.5, 82.2)), 4: ((110.3, -62.4, 47.4), (112.8, 64.7, 64.8))}
POST_BOX = {5: ((112.7, -60.4, -3.8), (117.3, -47.4, 89.1)), 20: ((-117.5, -60.4, -3.8), (-112.8, -47.6, 62.3))}
JOIST_BOX = ((12.8, -59.5, 35.5), (30.3, 65.0, 37.9))
IRON_BOX = {17: ((-112.7, -65.9, 24.4), (-109.2, 67.0, 36.7), 0.15), 19: ((117.4, -63.7, 3.7), (118.7, 65.8, 16.4), 0.12),
            23: ((113.4, -64.7, 26.1), (117.8, -44.0, 35.0), 0.1), 27: ((-113.5, 53.9, 24.6), (112.8, 58.1, 35.4), 0.15)}


def build_headboard(low):
    return [rbox(f"hp_board_{b}", *HB_BOX[b], 0.35, lambda f, U, V, P, b=b: FB.door_face(b, f, U, V, P), group="headboard")
            for b in (3, 4)]


def build_posts(low):
    return [rbox(f"hp_post_{p}", lo, hi, 0.5, lambda f, U, V, P, p=p, lo=lo, hi=hi: FB.post_face(p, f, U, V, P, lo, hi),
                 group="posts") for p, (lo, hi) in POST_BOX.items()]


def build_joist(low):
    lo, hi = JOIST_BOX
    return [rbox("hp_joist", lo, hi, 0.3, lambda f, U, V, P: FB.joist_face(f, U, V, P, lo, hi), group="joist")]


def build_iron(low):
    obs = [rbox(f"hp_iron_{p}", lo, hi, r, lambda f, U, V, P, p=p, lo=lo, hi=hi: FB.iron_face(p, f, U, V, P, lo, hi),
                group="iron") for p, (lo, hi, r) in IRON_BOX.items()]
    # проволока на распорке: 4 витка скрученной проволоки вокруг полосы (скрепили трещину)
    lo, hi, _ = IRON_BOX[19]
    xc, zc = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
    ax, az = (hi[0] - lo[0]) / 2 + 0.28, (hi[2] - lo[2]) / 2 + 0.28
    t = np.linspace(0, 4 * 2 * np.pi, 4 * 160)
    ct, st = np.cos(t), np.sin(t)
    px = xc + ax * np.sign(ct) * np.abs(ct) ** 0.15
    pz = zc + az * np.sign(st) * np.abs(st) ** 0.15
    py = 18.0 + 0.62 * t / (2 * np.pi) + 0.15 * np.sin(t * 2)
    V, Q, rid = tube(np.column_stack([px, py, pz]), np.full(len(t), 0.25), seg=8, twist=0.6, ridge=0.2)
    a = attrs_const(len(V), "twine", tone=0.5)
    a["idc"][:, 0] = FB.MATB["wire"] / 32.0
    a["m1"][:, 0] = rid
    acc = Acc()
    acc.add(V, Q, a)
    w = acc.build("hp_wire")
    w["group"] = "iron"
    return obs + [w]


# код материала в idc.R = код / 32 (с v2.3: кодов стало больше 16)
GROUPS = {"mattress": ({MATTRESS}, 4.0), "pillow": ({PILLOW}, 3.0), "headboard": ({3, 4}, 2.0),
          "posts": ({5, 20}, 2.0), "joist": ({11}, 1.5), "iron": ({17, 19, 23, 27}, 1.5)}
PARTS.update({"headboard": build_headboard, "posts": build_posts, "joist": build_joist, "iron": build_iron})
PART_GROUPS = {"deck": "mattress", "apron": "mattress", "towel": "pillow", "venik": "mattress",
               "headboard": "headboard", "posts": "posts", "joist": "joist", "iron": "iron"}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 4096
    parts = argv[argv.index("--parts") + 1].split(",") if "--parts" in argv else list(PARTS)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    setup_cycles("--gpu" in argv)
    low = load_low()
    low.hide_render = True          # иначе оригинал заслоняет лучи AO
    hp = []
    for p in parts:
        hp += PARTS[p](low)
    for o in hp:
        if "group" not in o:
            o["group"] = "mattress"
    log("high-poly:", {o.name: (len(o.data.vertices), o["group"]) for o in hp})
    if "--nobake" not in argv:
        OUT.mkdir(parents=True, exist_ok=True)
        mat = hp_material()
        result = {}
        if "--parts" in argv:     # пекутся только группы этих частей; остальное — из прошлого запекания
            for k in ("ao", *ATTRS, "cover", "normal", "mask"):
                path = OUT / f"{k}.png"
                if path.exists():
                    im = bpy.data.images.load(str(path))
                    im.colorspace_settings.name = "Non-Color"
                    result[k] = pixels(im).copy()
                    bpy.data.images.remove(im)
            log("merging into the previous bake:", sorted(result))
        for g, (keep, extr) in GROUPS.items():
            ghp = [o for o in hp if o["group"] == g]
            if not ghp:
                continue
            res, mask = bake_group(low, keep, ghp, size, extr, g, mat)
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
