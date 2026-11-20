"""Sauna Mitts: high-poly детали поверх оригинальной Tactical Gloves и запекание на её развёртку.

Запуск (из корня репозитория, Blender без окна):
  blender -b -P skins/sauna/tactical-gloves/bake_gloves.py -- [--size 4096] [--nobake] [--preview] [--blend] [--cpu]

Что моделируется (подробно — PLAN_3D.md, номера деталей в скобках):
  hand   плотная копия оболочки кисти (рёбра ≤ 0.33 мм), смещение по нормали:
         подушки войлока между швами (2), валяная фактура (3), складки на суставах пальцев (6),
         валик бокового шва и канавки проколов (8, 9), кожаные заплаты ладони / большого пальца /
         подушечек / овалов на костяшках — толщина 1.2 мм, подогнутый край, мерея, заломы по линиям
         ладони, вытертые места, царапины (13–19); кожа-подложка, два куска бересты внахлёст, рваные
         края с отставшими слоями, чечевички, трещины (21–25); подпалины и прожоги до нижнего слоя (27–28)
  threads обмёточные стежки через край по боковым швам (9), стежки «вперёд иголку» по заплатам (10),
         через край по бересте (11), узелки и хвостики (12)
  felt   катышки (4), волоски (5), опалённые волоски у прожогов (29)
  cuff   плотная копия ремешка (рёбра ≤ 0.2 мм): полотняное плетение с утолщениями, тканая двойная полоса
         кольцом вокруг запястья (основа гуще), подгиб в два слоя, строчка, складки обмотки, бахрома и
         пришитый крестиками конец (31–37)
  closure узел бечёвки (остров 5), берёзовая палочка-пуговица (остров 6), петля из бечёвки от узла,
         накинутая на палочку, ворс джута (39–41)
Пишет source/bake/<map>.png (size×size): normal, normal_base (та же копия без рельефа — вычитается в
texture_v1.py), ao, color (цвет вершин, sRGB), id (R = код материала × 16 + 8), msk1 (R вытерто, G обуглено,
B тёмная деталь), msk2 (R сажа, G засаленность, B изнанка), poshi/poslo (положение, 16 бит).
"""
import math
import sys
import time
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector, kdtree
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gloves_layout as GL  # noqa: E402
import noise_np as NN  # noqa: E402

OBJ = HERE / "originals" / "tactical.gloves.obj"
OUT = HERE / "source" / "bake"
REN = HERE / "renders"
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SIZE = int(ARGS[ARGS.index("--size") + 1]) if "--size" in ARGS else 4096
T0 = time.time()

IDS = {"felt": 1, "leather": 2, "suede": 3, "bark": 4, "thread": 5, "linen": 6, "stripe": 7, "twine": 8,
       "wood": 9}
HEX = {"felt": "B3A48A", "felt_dark": "8E8170", "leather": "8A6646", "leather_dark": "6A4C33",
       "leather_worn": "A27C57", "suede": "9A7A58", "bark": "E3DDCF", "bark_edge": "C9B79A", "bark_in": "B88E6C",
       "lent": "3B342E", "thread": "D6CDBA", "thread_dark": "B0A68F", "linen": "CFC6B4", "stripe": "8E3A30",
       "twine": "B9A272", "twine_dark": "8C7850", "wood": "D9CDB4", "wood_end": "B9A27E", "char": "2E2018",
       "halo": "8F7048", "under": "4A3F33"}
POS_LO = np.array([0.40, 0.19, -0.01])
POS_HI = np.array([0.53, 0.43, 0.15])
MM = 0.001
CS = [0]


def log(*a):
    print("[%6.1fs]" % (time.time() - T0), *a, flush=True)


def lin(h):
    return np.array([(int(h[i:i + 2], 16) / 255) ** 2.2 for i in (0, 2, 4)], np.float32)


def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def gauss(x, w):
    return np.exp(-(x / w) ** 2)


# ----------------------------------------------------------------- данные подготовки
PC = np.load(HERE / "source" / "pos_cache.npz")
PC_POS, PC_NRM, PC_ISL, PC_DENS = PC["pos"], PC["nrm"], PC["isl"], PC["dens"]
G = np.load(HERE / "source" / "glove_r.npz")


def uv2pos(x, y):
    """Точка атласа 1024 (px) → 3D (OBJ, м) и нормаль по карте «тексель → 3D» (ближайший заполненный)."""
    xi, yi = int(round(x)), int(round(y))
    for r in range(0, 12):
        ys, xs = np.mgrid[max(yi - r, 0):min(yi + r, 1023) + 1, max(xi - r, 0):min(xi + r, 1023) + 1]
        ok = ~np.isnan(PC_POS[ys, xs, 0])
        if ok.any():
            k = np.argmin((ys[ok] - y) ** 2 + (xs[ok] - x) ** 2)
            yy, xx = ys[ok][k], xs[ok][k]
            return Vector(PC_POS[yy, xx]), Vector(PC_NRM[yy, xx]).normalized(), int(PC_ISL[yy, xx])
    raise ValueError(f"нет поверхности у ({x}, {y})")


def dens_at(x, y):
    return float(PC_DENS[int(np.clip(y, 0, 1023)), int(np.clip(x, 0, 1023))])


# ----------------------------------------------------------------- low-poly
def load_low():
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="Y", up_axis="Z")
    low = bpy.context.selected_objects[0]
    low.name = "low"
    bpy.context.view_layer.objects.active = low
    # вторая (левая, -x) перчатка делит ту же развёртку — запекаем одну правую; удаляем в режиме правки,
    # чтобы не потерять собственные нормали OBJ (по ним игра строит касательные)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    for p in low.data.polygons:
        p.select = p.center.x < 0
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.delete(type="FACE")
    bpy.ops.object.mode_set(mode="OBJECT")
    me = low.data
    V, F, isl = G["V"], G["F"], G["isl"]
    cen = V[F].mean(1)
    kd = kdtree.KDTree(len(cen))
    for i, c in enumerate(cen):
        kd.insert(c, i)
    kd.balance()
    att = me.attributes.new("isl", "INT", "FACE")
    att.data.foreach_set("value", [int(isl[kd.find(p.center)[1]]) for p in me.polygons])
    log("low:", len(me.polygons), "граней, свои нормали:", me.has_custom_normals)
    return low


def face_isl(ob):
    a = ob.data.attributes["isl"]
    v = np.empty(len(a.data), np.int32)
    a.data.foreach_get("value", v)
    return v


def dense_copy(low, isls, max_edge, name):
    ob = low.copy()
    ob.data = low.data.copy()
    ob.name = name
    bpy.context.scene.collection.objects.link(ob)
    fi = face_isl(ob)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if fi[f.index] not in isls], context="FACES")
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    prev = None
    for _ in range(14):
        long_e = [e for e in bm.edges if e.calc_length() > max_edge]
        # стоп, когда длинных рёбер больше не убывает: вытянутые треугольники пересоздают длинную диагональ,
        # и грани множатся впустую (первая сборка: 2 млн вершин и 15.6 млн граней)
        if not long_e or (prev is not None and abs(len(long_e) - prev) < 0.02 * prev):
            break
        prev = len(long_e)
        bmesh.ops.subdivide_edges(bm, edges=long_e, cuts=1, use_grid_fill=True)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    el = np.array([e.calc_length() for e in bm.edges])
    log(f"{name}: рёбра медиана {np.median(el) * 1000:.2f} мм, 99 % {np.percentile(el, 99) * 1000:.2f}, "
        f"макс {el.max() * 1000:.2f}, длиннее нормы {(el > max_edge).mean() * 100:.1f} %")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    for p in ob.data.polygons:
        p.use_smooth = True
    log(name, len(ob.data.vertices), "вершин", len(ob.data.polygons), "граней")
    return ob


def vdata(ob):
    """co (м), normal, uv в px атласа 1024, остров вершины (от последней её грани)."""
    me = ob.data
    n = len(me.vertices)
    co = np.empty(n * 3)
    nr = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    me.vertices.foreach_get("normal", nr)
    nl = len(me.loops)
    lv = np.empty(nl, np.int64)
    me.loops.foreach_get("vertex_index", lv)
    uvl = np.empty(nl * 2)
    me.uv_layers.active.data.foreach_get("uv", uvl)
    uvl = uvl.reshape(-1, 2)
    np_ = len(me.polygons)
    ls = np.empty(np_, np.int64)
    me.polygons.foreach_get("loop_start", ls)
    fi = face_isl(ob)
    lisl = np.repeat(fi, 3)                     # всё в треугольниках
    order = np.argsort(lisl, kind="stable")    # тыл раньше ладони: на шве побеждает больший номер
    UV = np.zeros((n, 2))
    ISL = np.zeros(n, np.int32)
    UV[lv[order]] = uvl[order]
    ISL[lv[order]] = lisl[order]
    px = np.stack([UV[:, 0] * 1024, (1 - UV[:, 1]) * 1024], 1)
    dens = PC_DENS[np.clip(px[:, 1].astype(int), 0, 1023), np.clip(px[:, 0].astype(int), 0, 1023)]
    dens = np.where(np.isnan(dens) | (dens <= 0), 3.0, dens)
    return co.reshape(n, 3), nr.reshape(n, 3), px, ISL, dens


def set_co(ob, co):
    ob.data.vertices.foreach_set("co", co.astype(np.float32).ravel())
    ob.data.update()


# ----------------------------------------------------------------- 2D-поля в px атласа
def sd_poly(P, poly):
    """Знаковое расстояние (px), + внутри многоугольника."""
    A = np.array(poly, float)
    B = np.roll(A, -1, 0)
    inside = np.zeros(len(P), bool)
    dmin = np.full(len(P), 1e9)
    for a, b in zip(A, B):
        ab = b - a
        L2 = ab @ ab
        if L2 < 1e-12:
            continue
        t = np.clip(((P - a) @ ab) / L2, 0, 1)
        d = np.linalg.norm(P - (a + t[:, None] * ab), axis=1)
        dmin = np.minimum(dmin, d)
        cond = ((a[1] > P[:, 1]) != (b[1] > P[:, 1])) & \
               (P[:, 0] < (b[0] - a[0]) * (P[:, 1] - a[1]) / (b[1] - a[1] + 1e-12) + a[0])
        inside ^= cond
    return np.where(inside, dmin, -dmin)


def d_polyline(P, line):
    A = np.array(line, float)
    dmin = np.full(len(P), 1e9)
    tpar = np.zeros(len(P))
    acc = 0.0
    for a, b in zip(A, A[1:]):
        ab = b - a
        L = math.sqrt(ab @ ab)
        t = np.clip(((P - a) @ ab) / (L * L), 0, 1)
        d = np.linalg.norm(P - (a + t[:, None] * ab), axis=1)
        better = d < dmin
        dmin = np.where(better, d, dmin)
        tpar = np.where(better, acc + t * L, tpar)
        acc += L
    return dmin, tpar


# ----------------------------------------------------------------- шум
def worley(p, cell, seed=0):
    """F1, F2 ячеистого шума (мм): p (N,3) в мм."""
    q = p / cell
    i = np.floor(q).astype(np.int64)
    f1 = np.full(len(p), 9.0)
    f2 = np.full(len(p), 9.0)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                c = i + np.array([dx, dy, dz])
                h = (c[:, 0] * 73856093) ^ (c[:, 1] * 19349663) ^ (c[:, 2] * 83492791) ^ (seed * 2654435761)
                jit = np.stack([((h >> s) & 1023) / 1023.0 for s in (0, 10, 20)], 1)
                d = np.linalg.norm(c + jit - q, axis=1)
                f2 = np.where(d < f1, f1, np.minimum(f2, d))
                f1 = np.minimum(f1, d)
    return f1, f2


def fbm_mm(co_mm, scale, oct=3, seed=0):
    return NN.fbm(co_mm / scale, oct, seed) * 2 - 1


_ROT = {}


def ridged(co_mm, scale, seed):
    """Гребни (1 − |2n − 1|)² по повёрнутым осям: сетка свалянных волокон без квадратов value noise."""
    if seed not in _ROT:
        q, _ = np.linalg.qr(np.random.default_rng(seed).normal(size=(3, 3)))
        _ROT[seed] = q
    p = (co_mm @ _ROT[seed]) / scale
    return (1 - np.abs(2 * NN.vnoise(p, seed) - 1)) ** 2


# ----------------------------------------------------------------- геометрия оболочки кисти
def seam_chains(low):
    """Боковые швы — рёбра low-poly между тылом (1) и ладонью (2); цепочки точек (м)."""
    me = low.data
    fi = face_isl(low)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.edges.ensure_lookup_table()
    seam = []
    for e in bm.edges:
        fs = [fi[f.index] for f in e.link_faces]
        if len(fs) == 2 and set(fs) == {1, 2}:
            seam.append((e.verts[0].index, e.verts[1].index))
    co = {v.index: v.co.copy() for v in bm.verts}
    nrm = {v.index: v.normal.copy() for v in bm.verts}
    bm.free()
    adj = {}
    for a, b in seam:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    used = set()
    chains = []
    starts = [v for v, n in adj.items() if len(n) == 1] + list(adj)
    for s in starts:
        if s in used:
            continue
        ch = [s]
        used.add(s)
        cur = s
        while True:
            nxt = [w for w in adj[cur] if w not in used]
            if not nxt:
                break
            cur = nxt[0]
            used.add(cur)
            ch.append(cur)
        if len(ch) > 2:
            chains.append([(co[i], nrm[i]) for i in ch])
    log("швы:", len(chains), "цепочек,", sum(len(c) for c in chains), "точек")
    return chains


def resample3d(chain, step):
    """Цепочка (точка, нормаль) → точки через step (м) с касательной и нормалью."""
    pts = [p for p, _ in chain]
    nrs = [n for _, n in chain]
    out = []
    carry = 0.0
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        L = (b - a).length
        if L < 1e-9:
            continue
        t = (b - a) / L
        s = carry
        while s < L:
            w = s / L
            out.append((a.lerp(b, w), t.copy(), nrs[i].lerp(nrs[i + 1], w).normalized()))
            s += step
        carry = s - L
    return out


def finger_axes():
    """Осевые линии пальцев (3D): середина между осями тыльной и ладонной полос; s — мм от кончика."""
    fingers = {}
    for f in GL.BACK_FINGERS:
        lines = []
        for isl, (x0, x1, yt, _) in ((1, GL.BACK_FINGERS[f]), (2, GL.PALM_FINGERS[f])):
            C = []
            for y in range(380, int(yt) + 8, 3):
                m = PC_ISL[y, x0:x1 + 1] == isl
                if m.sum() < 6:
                    continue
                C.append(PC_POS[y, x0:x1 + 1][m].mean(0))
            lines.append(np.array(C))
        back, palm = lines
        mid = []
        for p in back:
            q = palm[np.argmin(np.linalg.norm(palm - p, axis=1))]
            mid.append((p + q) / 2)
        mid = np.array(mid)[::-1]                       # от кончика к ладони
        tipdir = mid[0] - mid[3]
        tip = mid[0] + tipdir / np.linalg.norm(tipdir) * 0.004
        mid = np.vstack([tip, mid])
        s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(mid, axis=0), axis=1))]) * 1000
        kx, ky = GL.KNUCKLES[f]
        kp = np.array(uv2pos(kx, ky)[0])
        L = s[np.argmin(np.linalg.norm(mid - kp, axis=1))]
        fingers[f] = dict(pts=mid, s=s, L=L, tip=tip, joints=(0.24 * L, 0.52 * L))
        log(f"палец {f}: длина до костяшки {L:.1f} мм, DIP {0.24 * L:.1f}, PIP {0.52 * L:.1f}")
    return fingers


def finger_param(co, fingers):
    """Для каждой точки: палец (-1 нет), s (мм от кончика), расстояние до оси (мм)."""
    n = len(co)
    best = np.full(n, 1e9)
    fid = np.full(n, -1)
    sv = np.zeros(n)
    for k, (f, d) in enumerate(fingers.items()):
        P = d["pts"]
        sp = d["s"]
        for i in range(len(P) - 1):
            a, b = P[i], P[i + 1]
            ab = b - a
            t = np.clip(((co - a) @ ab) / (ab @ ab), 0, 1)
            dist = np.linalg.norm(co - (a + t[:, None] * ab), axis=1) * 1000
            better = dist < best
            best = np.where(better, dist, best)
            fid = np.where(better, k, fid)
            sv = np.where(better, sp[i] + t * (sp[i + 1] - sp[i]), sv)
    ok = best < 13
    names = list(fingers)
    Lk = np.array([fingers[f]["L"] for f in names])
    ok &= sv < Lk[np.maximum(fid, 0)] + 4
    return np.where(ok, fid, -1), sv, best


def in_island(x, y, isl):
    xi, yi = int(round(x)), int(round(y))
    return 0 <= xi < 1024 and 0 <= yi < 1024 and PC_ISL[yi, xi] == isl


def stitch_line_uv(poly, inset_mm, on_mm, off_mm, closed=True, ref_poly=None, jitter=0.4, rng=None):
    """Шов «вперёд иголку» по контуру (px атласа): отступ внутрь inset_mm; пары концов стежков (px).
    closed=False — только открытая полилиния (дуга края подушечки); сторону «внутрь» решает ref_poly."""
    ref = ref_poly or poly
    pts = GL.resample(poly, 1.0, closed)
    if not pts:
        return []
    x, y, tx, ty = pts[len(pts) // 2]
    side = 1.0 if sd_poly(np.array([[x - ty * 3, y + tx * 3]]), ref)[0] > 0 else -1.0
    path = []
    for x, y, tx, ty in pts:
        d = dens_at(x, y)
        path.append((x - ty * side * inset_mm * d, y + tx * side * inset_mm * d, d))
    stitches = []
    acc = 0.0
    state_on = True
    cur = None
    goal = on_mm
    for i in range(1, len(path)):
        (ax, ay, d), (bx, by, _) = path[i - 1], path[i]
        acc += math.hypot(bx - ax, by - ay) / d
        if state_on and cur is None:
            cur = (ax, ay)
        if acc >= goal:
            if state_on:
                stitches.append((cur, (bx, by)))
                cur = None
            state_on = not state_on
            acc = 0.0
            j = rng.uniform(-jitter, jitter) if rng is not None else 0
            goal = (on_mm if state_on else off_mm) + j
    return stitches


# ----------------------------------------------------------------- сетки деталей
def new_mesh(name, verts, faces, cols, ident, msk1=None, msk2=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    n = len(me.vertices)
    cols = np.broadcast_to(np.asarray(cols, np.float32), (n, 3))
    ids = np.broadcast_to(np.asarray([IDS[ident]] if isinstance(ident, str) else ident, np.float32), (n,))
    set_attrs(me, cols, ids, msk1, msk2)
    for p in me.polygons:
        p.use_smooth = True
    return ob


def set_attrs(me, cols, ids, msk1=None, msk2=None):
    n = len(me.vertices)
    for name, val in (("col", cols), ("idc", None), ("msk1", msk1), ("msk2", msk2)):
        a = me.color_attributes.get(name) or me.color_attributes.new(name, "FLOAT_COLOR", "POINT")
        buf = np.ones((n, 4), np.float32)
        if name == "idc":
            buf[:, 0] = (np.asarray(ids) * 16 + 8) / 255
            buf[:, 1:3] = 0
        elif val is None:
            buf[:, :3] = 0
        else:
            buf[:, :3] = val
        a.data.foreach_set("color", buf.ravel())


class Tubes:
    """Много трубок в одном объекте (нитки, бечёвка, волоски): кольца по seg вершин, свив прядей."""

    def __init__(self):
        self.V, self.F, self.C, self.I, self.M1 = [], [], [], [], []

    def add(self, pts, radius, col, ident, seg=8, plies=2, twist_mm=1.6, ply_depth=0.28, col_fn=None,
            rad_fn=None, m1=(0, 0, 0)):
        n = len(pts)
        if n < 2:
            return
        o = len(self.V)
        prev = None
        sacc = 0.0
        for i, p in enumerate(pts):
            p = Vector(p)
            if i:
                sacc += (p - Vector(pts[i - 1])).length * 1000
            tng = (Vector(pts[min(i + 1, n - 1)]) - Vector(pts[max(i - 1, 0)])).normalized()
            if prev is None:
                a = Vector((0, 0, 1)) if abs(tng.z) < 0.9 else Vector((1, 0, 0))
                prev = tng.cross(a).normalized()
            b1 = (prev - tng * prev.dot(tng)).normalized()
            b2 = tng.cross(b1)
            prev = b1
            r = radius * (rad_fn(i / (n - 1)) if rad_fn else 1.0)
            for k in range(seg):
                a = 2 * math.pi * k / seg
                g = 1.0
                if plies > 1:
                    g = 1.0 - ply_depth * max(0.0, math.cos(plies * a + 2 * math.pi * sacc / twist_mm)) ** 3
                self.V.append(p + (b1 * math.cos(a) + b2 * math.sin(a)) * r * g)
                self.C.append(col_fn(i, k, sacc) if col_fn else col)
                self.I.append(IDS[ident])
                self.M1.append(m1)
        for i in range(n - 1):
            for k in range(seg):
                k2 = (k + 1) % seg
                self.F.append((o + i * seg + k, o + (i + 1) * seg + k, o + (i + 1) * seg + k2, o + i * seg + k2))
        # крышки на концах (веером)
        for i, sgn in ((0, -1), (n - 1, 1)):
            c = len(self.V)
            self.V.append(Vector(pts[i]))
            self.C.append(col_fn(i, 0, sacc) if col_fn else col)
            self.I.append(IDS[ident])
            self.M1.append(m1)
            for k in range(seg):
                k2 = (k + 1) % seg
                f = (o + i * seg + k, o + i * seg + k2, c)
                self.F.append(f if sgn > 0 else f[::-1])

    def build(self, name):
        if not self.V:
            return None
        ob = new_mesh(name, self.V, self.F, np.array(self.C), np.array(self.I, np.float32),
                      msk1=np.array(self.M1, np.float32))
        me = ob.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        log(name, len(self.V), "вершин")
        return ob


class Surface:
    """Смещённая плотная поверхность: точка над ней по лучу вдоль нормали."""

    def __init__(self, ob):
        dg = bpy.context.evaluated_depsgraph_get()
        self.bvh = BVHTree.FromObject(ob, dg)

    def at(self, p, n, lift):
        p, n = Vector(p), Vector(n).normalized()
        hit = self.bvh.ray_cast(p + n * 0.006, -n, 0.012)
        if hit[0] is None:
            loc, nn, _, _ = self.bvh.find_nearest(p)
            return loc + nn * lift, nn
        return hit[0] + n * lift, hit[1]

    def nearest(self, p):
        loc, nn, _, _ = self.bvh.find_nearest(Vector(p))
        return loc, nn


def arc_on_surface(surf, a, b, na, nb, lift, sink, steps=10):
    """Нитка от a до b по поверхности: концы уходят внутрь на sink (м), середина — на lift над поверхностью."""
    pts = []
    for k in range(steps + 1):
        t = k / steps
        p = a.lerp(b, t)
        n = na.lerp(nb, t).normalized()
        e = min(t, 1 - t)
        h = lift * sstep(0.0, 0.18, e) - sink * (1 - sstep(0.0, 0.12, e))
        q, _ = surf.at(p, n, h)
        pts.append(q)
    return pts


# ----------------------------------------------------------------- оболочка кисти: смещение
def build_hand(low, rng):
    base = dense_copy(low, {1, 2}, 0.33 * MM, "hand_base")
    hp = base.copy()
    hp.data = base.data.copy()
    hp.name = "hand_hp"
    bpy.context.scene.collection.objects.link(hp)
    co, nr, px, ISL, dens = vdata(hp)
    n = len(co)
    mmpx = 1.0 / dens
    co_mm = co * 1000
    log("кисть: поля…")

    # швы и стежки (концы стежков нужны раньше смещения — ямки проколов)
    chains = seam_chains(low)
    seam_pts = [p for ch in chains for p, t, nn in resample3d(ch, 0.25 * MM)]
    kd = kdtree.KDTree(len(seam_pts))
    for k, p in enumerate(seam_pts):
        kd.insert(p, k)
    kd.balance()
    d_seam = np.array([kd.find(Vector(c))[2] for c in co]) * 1000
    log("расстояние до швов готово")

    # пальцы
    fingers = finger_axes()
    fid, s_f, rad_f = finger_param(co, fingers)
    names = list(fingers)

    # --- войлок
    # v1: подушка — вдавление у шва, а не подъём всей поверхности (иначе вся стопка деталей выше отступа луча)
    pillow = -0.7 * (1 - sstep(1.4, 6.0, d_seam))
    welt = 0.85 * gauss(d_seam, 1.05)
    clouds = 0.26 * fbm_mm(co_mm, 4.5, 3, 1)
    fib = 0.13 * ridged(co_mm, 1.7, 101) + 0.08 * ridged(co_mm, 0.85, 102) + 0.05 * ridged(co_mm * [1, 2.2, 1], 0.9, 103)
    clouds = clouds + fib - 0.12
    h = pillow + welt
    felt_amp = np.ones(n)

    # складки на суставах (поперёк пальца, волнистые)
    folds = np.zeros(n)
    wav = 0.9 * fbm_mm(co_mm, 6.0, 2, 7)
    for kf, f in enumerate(names):
        m = fid == kf
        if not m.any():
            continue
        for j, sj in enumerate(fingers[f]["joints"]):
            x = s_f[m] - sj + wav[m]
            palm = ISL[m] == 2
            g_p = 0.8 * gauss(x - 1.1, 0.6) + 0.65 * gauss(x + 1.1, 0.55) + 0.3 * gauss(x - 3.0, 0.7)
            g_b = sum(0.36 * gauss(x - o, 0.4) for o in (-2.8, -1.1, 0.6, 2.3)) * (1 - 0.35 * j)
            folds[m] -= np.where(palm, g_p, g_b)
    h += folds

    # --- кожа: заплаты (ладонь, большой палец, подушечки, напёрстки, овалы на костяшках)
    leather_sd = np.full(n, -99.0)        # мм, + внутри
    pads_palm, pads_back = GL.pad_polys()
    regions = [(2, GL.PALM_PATCH), (2, GL.THUMB_PATCH), (1, GL.THUMB_CAP)]
    regions += [(2, p) for p in pads_palm.values()] + [(1, p) for p in pads_back.values()]
    for isl, poly in regions:
        m = ISL == isl
        leather_sd[m] = np.maximum(leather_sd[m], sd_poly(px[m], poly) * mmpx[m])
    m1 = ISL == 1
    for f, (kx, ky) in GL.KNUCKLES.items():
        rx, ry = GL.KNUCKLE_MM
        d = dens_at(kx, ky)
        e = np.sqrt(((px[m1, 0] - kx) / (rx * d)) ** 2 + ((px[m1, 1] - ky) / (ry * d)) ** 2)
        leather_sd[m1] = np.maximum(leather_sd[m1], (1 - e) * rx)
    leather_sd += 0.25 * fbm_mm(co_mm, 3.0, 2, 11)      # край кроился ножом — не идеально ровно
    lm = sstep(-0.05, 0.55, leather_sd)
    worn = np.zeros(n)
    for cx, cy, rx, ry in GL.WORN:
        m = ISL == 2
        e = np.sqrt(((px[m, 0] - cx) / rx) ** 2 + ((px[m, 1] - cy) / ry) ** 2)
        worn[m] = np.maximum(worn[m], 1 - sstep(0.4, 1.0, e))
    # подушечки вытерты на самом кончике
    for kf, f in enumerate(names):
        m = fid == kf
        worn[m] = np.maximum(worn[m], (1 - sstep(4, 12, s_f[m])) * 0.8)
    worn *= sstep(0.35, 0.65, NN.fbm(co_mm / 3.5, 3, 77)) * (0.5 + 0.5 * sstep(-0.1, 0.25, clouds))
    worn *= lm
    f1, f2 = worley(co_mm, 1.1, 3)
    grain = -0.06 * (1 - sstep(0.0, 0.2, f2 - f1)) + 0.025 * fbm_mm(co_mm, 0.8, 2, 4)
    creases = np.zeros(n)
    mp = ISL == 2
    for line in GL.PALM_CREASES:
        d, _ = d_polyline(px[mp], line)
        creases[mp] -= 0.32 * gauss(d * mmpx[mp] + 0.4 * fbm_mm(co_mm[mp], 3, 2, 5), 0.6)
    # царапины на коже: короткие бороздки с мягкими концами, гуще на подушечках и ребре
    scratch = np.zeros(n)
    scr_list = []
    lidx = np.where(lm > 0.9)[0]
    for _ in range(46):
        i = rng.choice(lidx)
        Lmm = 3 + 12 * rng.random() ** 2
        ang = rng.uniform(0, math.pi)
        d = dens[i]
        a = px[i]
        b = a + np.array([math.cos(ang), math.sin(ang)]) * Lmm * d
        scr_list.append((a, b, ISL[i]))
    for a, b, isl in scr_list:
        m = (ISL == isl) & (lm > 0.5)
        ab = b - a
        t = np.clip(((px[m] - a) @ ab) / (ab @ ab), 0, 1)
        dd = np.linalg.norm(px[m] - (a + t[:, None] * ab), axis=1) * mmpx[m]
        taper = np.sin(np.pi * t) ** 0.6
        scratch[m] = np.minimum(scratch[m], -0.2 * gauss(dd, 0.22) * taper)
    leather_h = 0.9 * lm + 0.18 * gauss(leather_sd - 0.6, 0.4) * (leather_sd > -0.4)
    leather_h += (grain * (1 - 0.85 * worn) + creases + scratch) * lm
    # канавка строчки в 3 мм от края
    leather_h -= 0.14 * gauss(leather_sd - 3.0, 0.45) * lm
    felt_amp *= 1 - lm

    # --- тыл: подложка из грубой кожи и береста внахлёст
    mb = ISL == 1
    rag = 1.1 * fbm_mm(co_mm, 2.6, 2, 21)
    sd_s = np.full(n, -99.0)
    sd_b1 = np.full(n, -99.0)
    sd_b2 = np.full(n, -99.0)
    sd_s[mb] = sd_poly(px[mb], GL.SUEDE) * mmpx[mb] + rag[mb]
    rag2 = 0.8 * fbm_mm(co_mm, 2.4, 2, 22)
    sd_b1[mb] = sd_poly(px[mb], GL.BARK1) * mmpx[mb] + rag2[mb]
    sd_b2[mb] = sd_poly(px[mb], GL.BARK2) * mmpx[mb] + 0.8 * fbm_mm(co_mm[mb], 2.4, 2, 23)
    sm = sstep(-0.1, 0.6, sd_s)
    b1 = sstep(-0.1, 0.55, sd_b1)
    b2 = sstep(-0.1, 0.55, sd_b2)
    suede_h = 0.8 * sm + 0.06 * fbm_mm(co_mm, 0.5, 2, 24) * sm
    # отставшие слои у края бересты: полоски, где шум выше порога — край приподнят и закручен
    peel_n = NN.fbm(co_mm / 7.0, 2, 25)
    peel = sstep(0.55, 0.75, peel_n)
    bark_lift = lambda sd: 0.45 * gauss(sd - 0.6, 1.3) * peel   # noqa: E731
    # внахлёст: верхний кусок ложится на нижний, но стопка не больше ~2.3 мм над войлоком
    bark_h = 1.0 * np.maximum(b1, b2) + 0.35 * np.minimum(b1, b2) + np.maximum(bark_lift(sd_b1) * b1, bark_lift(sd_b2) * b2)
    bark_top = np.maximum(b1, b2)
    # чечевички — поперёк кисти (вдоль x атласа), ширина ~1 мм, утоплены
    lent = np.zeros(n)
    lent_mask = np.zeros(n)
    bi = np.where(mb & (bark_top > 0.5))[0]
    for _ in range(150):
        i = rng.choice(bi)
        Lmm = 3 + 8 * rng.random() ** 1.5
        d = dens[i]
        a = px[i]
        b = a + np.array([Lmm * d, rng.uniform(-0.6, 0.6)])
        m = mb & (np.abs(px[:, 1] - a[1]) < 6) & (px[:, 0] > a[0] - 6) & (px[:, 0] < b[0] + 6)
        ab = b - a
        t = np.clip(((px[m] - a) @ ab) / (ab @ ab), 0, 1)
        dd = np.linalg.norm(px[m] - (a + t[:, None] * ab), axis=1) * mmpx[m]
        g = gauss(dd, 0.45) * np.sin(np.pi * t) ** 0.4
        lent[m] = np.minimum(lent[m], -0.2 * g)
        lent_mask[m] = np.maximum(lent_mask[m], sstep(0.35, 0.75, g))
    # трещины вдоль пальцев (поперёк чечевичек)
    crack = np.zeros(n)
    crack_mask = np.zeros(n)
    for x0 in (585, 640, 735, 790):
        line = [(x0 + rng.uniform(-6, 6), y) for y in range(232, 444, 14)]
        line = [(x + rng.uniform(-3, 3), y) for x, y in line]
        y0, y1 = sorted(rng.uniform(240, 440, 2))
        line = [p for p in line if y0 <= p[1] <= y1]
        if len(line) < 2:
            continue
        d, _ = d_polyline(px[mb], line)
        g = gauss(d * mmpx[mb], 0.6)
        crack[mb] = np.minimum(crack[mb], -0.55 * g)
        crack_mask[mb] = np.maximum(crack_mask[mb], g)
    bark_h += (lent + crack) * bark_top
    felt_amp *= 1 - sm

    # --- подпалины и прожоги (только на войлоке)
    char = np.zeros(n)
    hole = np.zeros(n)
    burn_h = np.zeros(n)
    burn_list = []
    for bx, by, r, through in GL.BURNS:
        c, nn, _ = uv2pos(bx, by)
        burn_list.append((c, nn, r, through))
        dist = np.linalg.norm(co - np.array(c), axis=1) * 1000
        dist = dist * (1 + 0.25 * fbm_mm(co_mm, r * 0.7, 2, int(bx)))
        q = dist / r
        burn_h -= 0.45 * (1 - sstep(0.2, 1.0, q)) - 0.12 * gauss(q - 1.05, 0.12) * fbm_mm(co_mm, 1.2, 2, 3)
        char = np.maximum(char, 1 - sstep(0.5, 1.7, q))
        if through:
            rh = 0.42
            burn_h -= 1.25 * (1 - sstep(rh * 0.6, rh, q))
            burn_h += 0.25 * gauss(q - rh * 1.12, rh * 0.18)
            hole = np.maximum(hole, 1 - sstep(rh * 0.7, rh, q))
    free_felt = (1 - lm) * (1 - sm)
    burn_h *= free_felt
    char *= free_felt
    hole *= free_felt
    felt_amp *= 1 - 0.75 * sstep(0.3, 0.9, char)

    # --- ямки проколов: стежки на швах, по заплатам, по бересте
    surf_pts = []      # (3D, нормаль) концов стежков
    seam_st = []
    for ch in chains:
        L = sum((ch[i + 1][0] - ch[i][0]).length for i in range(len(ch) - 1))
        if L < 0.006:
            continue
        for p, t, nn in resample3d(ch, 5.6 * MM):
            j = rng.uniform(-0.5, 0.5) * MM
            side = nn.cross(t).normalized()
            a = p - side * 1.8 * MM - t * (1.3 * MM + j)
            b = p + side * 1.8 * MM + t * (1.3 * MM - j)
            seam_st.append((a, b, nn))
            surf_pts += [(a, nn), (b, nn)]
    patch_st = []
    lines = [(2, GL.PALM_PATCH, True, None), (2, GL.THUMB_PATCH, True, None), (1, GL.THUMB_CAP, True, None)]
    lines += [(2, p[:13], False, p) for p in pads_palm.values()] + [(1, p[:13], False, p) for p in pads_back.values()]
    for isl, poly, closed, ref in lines:
        for (pa, pb) in stitch_line_uv(poly, 3.0, 4.0, 2.2, closed=closed, ref_poly=ref, rng=rng):
            if not (in_island(*pa, isl) and in_island(*pb, isl)):
                continue
            a, na, ia = uv2pos(*pa)
            b, nb, ib = uv2pos(*pb)
            if (a - b).length > 0.007:
                continue
            patch_st.append((a, b, na, nb))
            surf_pts += [(a, na), (b, nb)]
    for f, (kx, ky) in GL.KNUCKLES.items():
        rx, ry = GL.KNUCKLE_MM
        d = dens_at(kx, ky)
        ring = [(kx + (rx - 2.3) * d * math.cos(t), ky + (ry - 2.3) * d * math.sin(t))
                for t in np.linspace(0, 2 * math.pi, 7)]
        for i in range(6):
            a, na, _ = uv2pos(*ring[i])
            b, nb, _ = uv2pos(*(np.array(ring[i]) * 0.35 + np.array(ring[i + 1]) * 0.65))
            patch_st.append((a, b, na, nb))
            surf_pts += [(a, na), (b, nb)]
    bark_st = []
    for poly, under in ((GL.BARK1, GL.BARK2), (GL.BARK2, None)):
        area = GL.poly_area(poly)
        for x, y, tx, ty in GL.resample(poly, 7.0 * 3.0):
            # край нижнего куска под верхним не виден — там не шьём (иначе строчка посреди накладки)
            if under is not None and sd_poly(np.array([[x, y]]), under)[0] > -1.5 * dens_at(x, y):
                continue
            d = dens_at(x, y)
            nx, ny = (-ty, tx) if area > 0 else (ty, -tx)
            pin = (x + nx * 2.6 * d - tx * 0.8 * d, y + ny * 2.6 * d - ty * 0.8 * d)
            pout = (x - nx * 2.4 * d + tx * 0.8 * d, y - ny * 2.4 * d + ty * 0.8 * d)
            if not (in_island(*pout, 1) and in_island(*pin, 1)):
                continue
            a, na, ia = uv2pos(*pout)
            b, nb, ib = uv2pos(*pin)
            bark_st.append((a, b, na, nb))
            surf_pts += [(a, na), (b, nb)]
    kdv = kdtree.KDTree(n)
    for i, c in enumerate(co):
        kdv.insert(c, i)
    kdv.balance()
    dimple = np.zeros(n)
    for p, nn in surf_pts:
        for (_, i, dist) in kdv.find_range(p, 2.2 * MM):
            dd = dist * 1000
            dimple[i] = min(dimple[i], -0.32 * gauss(dd, 0.55) + 0.06 * gauss(dd - 1.2, 0.5))
    log("проколов:", len(surf_pts))

    # --- сумма
    h += clouds * felt_amp + burn_h + leather_h + suede_h + bark_h + dimple * (1 - 0.5 * bark_top)
    set_co(hp, co + nr * (h * MM)[:, None])

    # --- цвета и маски
    cfelt = lin(HEX["felt"])
    cols = np.tile(cfelt, (n, 1)) * (1 + 0.12 * clouds[:, None])
    cols = cols * (1 - 0.25 * sstep(0.0, -0.4, folds))[:, None]
    leather_c = lin(HEX["leather"]) * (1 + 0.6 * grain[:, None]) + (lin(HEX["leather_worn"]) - lin(HEX["leather"])) * worn[:, None]
    leather_c = leather_c * (1 - 0.35 * sstep(0, -0.25, creases + scratch * 0))[:, None]
    leather_c += (lin(HEX["leather_worn"]) * 1.25 - leather_c) * sstep(0, -0.1, scratch)[:, None] * 0.6
    cols = cols * (1 - lm[:, None]) + leather_c * lm[:, None]
    cols = cols * (1 - sm[:, None]) + lin(HEX["suede"]) * (1 + 0.15 * fbm_mm(co_mm, 0.6, 2, 9))[:, None] * sm[:, None]
    bark_c = lin(HEX["bark"]) * (1 + 0.06 * fbm_mm(co_mm, 5, 2, 12))[:, None]
    edge = np.maximum(1 - sstep(0.0, 1.0, np.where(b2 > 0.5, sd_b2, sd_b1)), 0)
    bark_c = bark_c * (1 - edge[:, None] * 0.3) + lin(HEX["bark_in"]) * (edge * np.maximum(peel, 0.35))[:, None] * 0.5
    dark = np.maximum(lent_mask, crack_mask * 0.85) * bark_top
    bark_c = bark_c * (1 - dark[:, None]) + lin(HEX["lent"]) * dark[:, None]
    cols = cols * (1 - bark_top[:, None]) + bark_c * bark_top[:, None]
    cols = cols * (1 - char[:, None] * 0.85) + lin(HEX["char"]) * (sstep(0.35, 0.9, char))[:, None] * 0.85 \
        + lin(HEX["halo"]) * ((char > 0) * sstep(0.0, 0.35, char) * (1 - sstep(0.35, 0.9, char)))[:, None] * 0.6
    cols = cols * (1 - hole[:, None]) + lin(HEX["under"]) * hole[:, None] * 0.5
    ids = np.full(n, IDS["felt"], np.float32)
    ids = np.where(lm > 0.5, IDS["leather"], ids)
    ids = np.where(sm > 0.5, IDS["suede"], ids)
    ids = np.where(bark_top > 0.5, IDS["bark"], ids)
    # сажа: от кончиков пальцев и большого пальца
    tips = [fingers[f]["tip"] for f in names] + [np.array(uv2pos(18, 330)[0]), np.array(uv2pos(1005, 440)[0])]
    dtip = np.min([np.linalg.norm(co - t, axis=1) for t in tips], 0) * 1000
    soot = 1 - sstep(5, 24, dtip + 4 * fbm_mm(co_mm, 4, 2, 31))
    grease = np.zeros(n)
    grease[mp] = 1 - sstep(0.3, 1.0, np.sqrt(((px[mp, 0] - 280) / 170) ** 2 + ((px[mp, 1] - 380) / 170) ** 2))
    m1v = np.stack([np.clip(worn + 0.7 * sstep(0, -0.1, scratch), 0, 1), char, np.clip(np.maximum(dark, hole), 0, 1)], 1)
    m2v = np.stack([soot, grease, np.zeros(n)], 1)
    set_attrs(hp.data, cols, ids, m1v, m2v)
    set_attrs(base.data, np.tile(cfelt, (len(base.data.vertices), 1)), np.ones(len(base.data.vertices)))

    # ----- нитки
    surf = Surface(hp)
    th = Tubes()
    cth = lin(HEX["thread"])
    cth_d = lin(HEX["thread_dark"])
    tr = 0.55 * MM

    def thread_col(i, k, s):
        return cth * 0.85 + (cth_d - cth * 0.85) * (0.5 + 0.5 * math.sin(s * 3.1))

    for a, b, nn in seam_st:
        pts = arc_on_surface(surf, a, b, nn, nn, tr * 0.85, tr * 1.3, 12)
        th.add(pts, tr, cth, "thread", seg=8, plies=2, twist_mm=1.4, col_fn=thread_col)
    for a, b, na, nb in patch_st:
        pts = arc_on_surface(surf, a, b, na, nb, tr * 0.7, tr * 1.2, 10)
        th.add(pts, tr, cth, "thread", seg=8, plies=2, twist_mm=1.4, col_fn=thread_col)
    for a, b, na, nb in bark_st:
        pts = arc_on_surface(surf, a, b, na, nb, tr * 0.9, tr * 1.3, 12)
        th.add(pts, tr, cth, "thread", seg=8, plies=2, twist_mm=1.4, col_fn=thread_col)
    # узелки и хвостики у запястья (концы цепочек швов с наибольшим y)
    ends = sorted([ch[0] if ch[0][0].y > ch[-1][0].y else ch[-1] for ch in chains], key=lambda c: -c[0].y)[:5]
    for p, nn in ends:
        p = p + Vector((0, -0.004, 0))
        q, qn = surf.nearest(p)
        ring = [q + (Vector((math.cos(t), 0, math.sin(t))) * 1.1 * MM) for t in np.linspace(0, 2 * math.pi, 10)]
        ring = [surf.at(x, qn, tr * 0.9)[0] for x in ring]
        th.add(ring, tr * 1.05, cth, "thread", seg=8, plies=2, col_fn=thread_col)
        dirv = Vector((rng.uniform(-1, 1), -1, rng.uniform(-1, 1))).normalized()
        tail = [surf.at(q + dirv * (k * 1.2 * MM), qn, tr * 0.8)[0] for k in range(8)]
        th.add(tail, tr * 0.9, cth, "thread", seg=8, plies=2, col_fn=thread_col,
               rad_fn=lambda t: 1.0 - 0.5 * t)
    threads = th.build("hand_threads")

    # ----- катышки и волоски на войлоке
    felt_ok = (free_felt > 0.95) & (char < 0.05)
    pills = Tubes()
    pv, pf, pc = [], [], []
    for isl, zones in ((2, GL.PILL_ZONES_PALM), (1, GL.PILL_ZONES_BACK)):
        cand = np.where(felt_ok & (ISL == isl))[0]
        for cx, cy, rx, ry in zones:
            e = ((px[cand, 0] - cx) / rx) ** 2 + ((px[cand, 1] - cy) / ry) ** 2
            zc = cand[e < 1]
            if len(zc) == 0:
                continue
            for _ in range(int(8 + 0.2 * len(zc) ** 0.5)):
                i = rng.choice(zc)
                r = (0.55 + 0.6 * rng.random() ** 2) * MM
                c, nn = surf.at(co[i], nr[i], r * 0.35)
                o = len(pv)
                nn = Vector(nn)
                a1 = nn.orthogonal().normalized()
                a2 = nn.cross(a1)
                for ui in range(7):
                    th_ = math.pi * ui / 6
                    for vi in range(8):
                        ph = 2 * math.pi * vi / 8
                        rr = r * (1 + 0.18 * math.sin(3 * ph + i))
                        pv.append(c + (a1 * math.cos(ph) + a2 * math.sin(ph)) * rr * math.sin(th_)
                                  + nn * (r * 0.62 * math.cos(th_)))
                        pc.append(lin(HEX["felt"]) * (0.92 + 0.12 * rng.random()))
                for ui in range(6):
                    for vi in range(8):
                        v2 = (vi + 1) % 8
                        pf.append((o + ui * 8 + vi, o + ui * 8 + v2, o + (ui + 1) * 8 + v2, o + (ui + 1) * 8 + vi))
    pills_ob = new_mesh("hand_pills", pv, pf, np.array(pc), "felt")
    bm = bmesh.new()
    bm.from_mesh(pills_ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(pills_ob.data)
    bm.free()
    log("катышки:", len(pf) // 48)

    hairs = Tubes()
    cand = np.where(felt_ok)[0]
    w = 0.25 + 1.5 * gauss(d_seam[cand], 4.0)
    w /= w.sum()
    for i in rng.choice(cand, 120, p=w):
        Lmm = 2 + 3 * rng.random()
        nn = Vector(nr[i])
        dirv = (nn.orthogonal() * math.cos(rng.uniform(0, 6.3)) + nn.cross(nn.orthogonal()) * math.sin(rng.uniform(0, 6.3))).normalized()
        curl = rng.uniform(-0.25, 0.25)
        pts = []
        p = Vector(co[i])
        for k in range(7):
            t = k / 6
            lift = (0.12 + 0.06 * t) * MM
            q, qn = surf.at(p, nn, lift)
            pts.append(q)
            dirv = (dirv + Vector(qn).cross(dirv) * curl).normalized()
            p = p + dirv * (Lmm / 6 * MM)
        hairs.add(pts, 0.21 * MM, lin(HEX["felt"]) * 1.08, "felt", seg=5, plies=1, rad_fn=lambda t: 1 - 0.5 * t)
    # опалённые волоски у прожогов — короткие, закрученные, тёмные
    for c, nn, r, through in burn_list:
        for _ in range(int(6 + r * 2)):
            ang = rng.uniform(0, 6.3)
            nn_ = Vector(nn)
            t1 = nn_.orthogonal().normalized()
            t2 = nn_.cross(t1)
            start = Vector(c) + (t1 * math.cos(ang) + t2 * math.sin(ang)) * r * rng.uniform(0.5, 0.9) * MM
            pts = []
            for k in range(6):
                a2 = ang + k * 0.5
                q, _ = surf.at(start + (t1 * math.cos(a2) + t2 * math.sin(a2)) * k * 0.45 * MM, nn_, (0.3 + 0.1 * k) * MM)
                pts.append(q)
            hairs.add(pts, 0.24 * MM, lin(HEX["char"]) * 1.4, "felt", seg=5, plies=1, m1=(0, 0.8, 0),
                      rad_fn=lambda t: 1 - 0.5 * t)
    hairs_ob = hairs.build("hand_hairs")
    return base, hp, [hp, threads, pills_ob, hairs_ob], fingers


# ----------------------------------------------------------------- манжета-полотенце
class CuffFrame:
    def __init__(self, low):
        fi = face_isl(low)
        me = low.data
        vs = set()
        for p in me.polygons:
            if fi[p.index] in (3, 4, 7):
                vs.update(p.vertices)
        P = np.array([me.vertices[i].co[:] for i in vs])
        self.c = P.mean(0)
        w, v = np.linalg.eigh(np.cov((P - self.c).T))
        ax = v[:, 0]
        hand = np.array([0.477, 0.28, 0.07])
        if (hand - self.c) @ ax > 0:
            ax = -ax
        self.ax = ax / np.linalg.norm(ax)
        e1 = np.cross(self.ax, [0, 0, 1.0])
        self.e1 = e1 / np.linalg.norm(e1)
        self.e2 = np.cross(self.ax, self.e1)

    def coords(self, co):
        r = co - self.c
        a = r @ self.ax * 1000
        x, y = r @ self.e1, r @ self.e2
        return a, np.arctan2(y, x), np.hypot(x, y) * 1000

    def point(self, a_mm, th, R_mm):
        return Vector(self.c + self.ax * a_mm * MM + (self.e1 * math.cos(th) + self.e2 * math.sin(th)) * R_mm * MM)

    def radial(self, th):
        return Vector(self.e1 * math.cos(th) + self.e2 * math.sin(th))


def build_cuff(low, rng):
    base = dense_copy(low, {3, 4, 7}, 0.2 * MM, "cuff_base")
    hp = base.copy()
    hp.data = base.data.copy()
    hp.name = "cuff_hp"
    bpy.context.scene.collection.objects.link(hp)
    co, nr, px, ISL, dens = vdata(hp)
    n = len(co)
    CF = CuffFrame(low)
    a, th, R = CF.coords(co)
    radial = (co - CF.c) - np.outer((co - CF.c) @ CF.ax, CF.ax)
    radial /= np.linalg.norm(radial, axis=1, keepdims=True)
    outer = (np.sum(nr * radial, 1) > 0.2).astype(float)
    inner = (np.sum(nr * radial, 1) < -0.2).astype(float)
    co_mm = co * 1000
    along = th * R
    # конец ремешка внахлёст: по оригиналу — язычок острова 3 справа
    th_end = float(CF.coords(np.array(uv2pos(762, 843)[0])[None])[1][0])
    th_tab = float(CF.coords(np.array(uv2pos(700, 843)[0])[None])[1][0])
    sgn = 1 if ((th_end - th_tab + math.pi) % (2 * math.pi) - math.pi) > 0 else -1
    log(f"манжета: конец ремешка θ={math.degrees(th_end):.0f}°, направление {sgn}")

    # плетение: основа вдоль ленты (по along), уток поперёк (по a); полоса — основа гуще
    stripe = np.zeros(n)
    for a0, a1, s in GL.STRIPES:
        stripe = np.maximum(stripe, s * sstep(a0 - 0.25, a0 + 0.25, a) * (1 - sstep(a1 - 0.25, a1 + 0.25, a)))
    p_w = np.where(stripe > 0.5, GL.STRIPE_WEAVE_MM, GL.WEAVE_MM)
    p_f = GL.WEAVE_MM
    vj = a / p_w                      # номер нити основы (поперёк)
    ui = along / p_f                  # номер нити утка (вдоль)
    jw = np.round(vj)
    iw = np.round(ui)

    def hsh(k, seed):
        x = (k.astype(np.int64) * 2654435761 + seed * 97531) & 0xFFFFFFFF
        return ((x ^ (x >> 15)) & 1023) / 1023.0

    thick_w = 1 + 0.7 * (hsh(jw, 1) > 0.86) + 0.3 * hsh(jw, 2)
    thick_f = 1 + 0.8 * (hsh(iw, 3) > 0.88) + 0.3 * hsh(iw, 4)
    prof_w = np.clip(1 - ((vj - jw) * 2 / np.minimum(thick_w, 1.6)) ** 2, 0, 1) ** 0.6
    prof_f = np.clip(1 - ((ui - iw) * 2 / np.minimum(thick_f, 1.6)) ** 2, 0, 1) ** 0.6
    und_w = 0.5 + 0.5 * np.cos(np.pi * ui + np.pi * jw)
    und_f = 0.5 - 0.5 * np.cos(np.pi * vj + np.pi * iw)
    weave = np.maximum(prof_w * (0.55 + 0.45 * und_w) * thick_w, prof_f * (0.55 + 0.45 * und_f) * thick_f)
    weave = 0.11 * (weave - 0.5)
    # подгиб: снаружи — два слоя у кромок, изнутри — ступенька сырого края подгиба
    hem = np.abs(a) > GL.CUFF_HEM
    hem_out = 0.35 * sstep(GL.CUFF_HEM - 0.6, GL.CUFF_HEM + 0.6, np.abs(a))
    hem_in = 0.55 * sstep(GL.CUFF_HEM - 0.3, GL.CUFF_HEM + 0.3, np.abs(a))
    # строчка подгиба (снаружи) — канавка
    hem_groove = -0.18 * gauss(np.abs(a) - GL.CUFF_HEM_STITCH, 0.45)
    # складки обмотки: поперёк ленты (линии вдоль оси), неравномерно
    wr = 0.75 * NN.fbm(np.stack([along / 9.0, a / 40.0, np.zeros(n)], 1), 3, 41) * 2 - 0.75
    wr *= 1 - 0.55 * (a / 15) ** 2
    h = weave + outer * (hem_out + hem_groove) + inner * hem_in + wr * (0.6 + 0.4 * outer)
    h += 0.05 * fbm_mm(co_mm, 2.0, 2, 44)
    # конец ремешка: край чуть толще (подогнут), крестики потом трубками
    dth = ((th - th_end + math.pi) % (2 * math.pi) - math.pi) * sgn       # < 0 — на язычке
    on_tab = (dth < 0) & (dth > -0.6) & (outer > 0)
    h += 0.4 * gauss(dth * R + 1.0, 1.2) * on_tab
    set_co(hp, co + nr * (h * MM)[:, None])

    lc = lin(HEX["linen"])
    sc = lin(HEX["stripe"])
    tone = (1 + 0.5 * weave[:, None] * 6) * (1 + 0.04 * fbm_mm(co_mm, 3, 2, 45)[:, None])
    cols = (lc * (1 - stripe[:, None]) + sc * stripe[:, None]) * tone
    cols *= (1 - 0.18 * sstep(0, -0.4, wr))[:, None]
    ids = np.where(stripe > 0.5, IDS["stripe"], IDS["linen"]).astype(np.float32)
    m2v = np.stack([np.zeros(n), np.zeros(n), inner], 1)
    set_attrs(hp.data, cols, ids, None, m2v)
    set_attrs(base.data, np.tile(lc, (len(base.data.vertices), 1)), np.full(len(base.data.vertices), IDS["linen"]))

    surf = Surface(hp)
    tb = Tubes()
    cth = lin(HEX["thread"])
    tr = 0.45 * MM

    def on_cuff(a_mm, t, lift):
        p = CF.point(a_mm, t, 45)
        hit = surf.bvh.ray_cast(p, -CF.radial(t), 0.05)
        if hit[0] is None:
            return None, None
        return hit[0] + hit[1] * lift, hit[1]

    # строчка подгиба: «вперёд иголку» 4 мм, шаг 6 мм, по обеим кромкам
    for a_s in (-GL.CUFF_HEM_STITCH, GL.CUFF_HEM_STITCH):
        Rm = 33.0
        t = 0.0
        while t < 2 * math.pi:
            L1 = (4.0 + rng.uniform(-0.4, 0.4)) / Rm
            pts = []
            for k in range(9):
                tt = t + L1 * k / 8
                e = min(k, 8 - k) / 8
                q, nn = on_cuff(a_s + rng.uniform(-0.08, 0.08), tt, tr * (0.75 if e > 0.12 else -0.9))
                if q is not None:
                    pts.append(q)
            if len(pts) == 9:
                tb.add(pts, tr, cth, "thread", seg=8, plies=2, twist_mm=1.3)
            t += (6.0 + rng.uniform(-0.5, 0.5)) / Rm
    # крестики на конце ремешка (вместо липучки)
    for a_c in (-6.0, 5.0):
        tc = th_end - sgn * 5.0 / 33.0
        for d1, d2 in ((1, 1), (1, -1)):
            pts = []
            for k in range(11):
                u = k / 10
                aa = a_c + (-3.5 + 7 * u) * d1 * 0.5 * 2
                tt = tc + (-3.5 + 7 * u) * d2 / 33.0
                e = min(u, 1 - u)
                q, _ = on_cuff(aa, tt, tr * (1.0 if e > 0.1 else -0.9))
                if q is not None:
                    pts.append(q)
            if len(pts) > 6:
                tb.add(pts, tr * 1.1, cth, "thread", seg=8, plies=2, twist_mm=1.3)
    # бахрома: нитки на сыром конце ремешка, лежат на ткани под ним
    for k in range(10):
        aa = rng.uniform(-9.5, 9.5)
        Lm = rng.uniform(2.0, 5.0)
        pts = []
        for j in range(7):
            tt = th_end + sgn * (j / 6 * Lm - 0.3) / 33.0
            q, _ = on_cuff(aa + j * rng.uniform(-0.15, 0.15), tt, 0.3 * MM)
            if q is not None:
                pts.append(q)
        if len(pts) > 3:
            tb.add(pts, 0.28 * MM, lc * 0.95, "linen", seg=6, plies=1, rad_fn=lambda t: 1 - 0.4 * t)
    threads = tb.build("cuff_threads")
    return base, hp, [hp, threads], CF, surf


# ----------------------------------------------------------------- застёжка: узел, палочка, петля
def build_closure(low, CF, cuff_surf, rng):
    base = dense_copy(low, {5, 6}, 0.1 * MM, "small_base")
    hp = base.copy()
    hp.data = base.data.copy()
    hp.name = "small_hp"
    bpy.context.scene.collection.objects.link(hp)
    co, nr, px, ISL, dens = vdata(hp)
    n = len(co)
    h = np.zeros(n)
    cols = np.zeros((n, 3), np.float32)
    ids = np.zeros(n, np.float32)
    info = {}
    for isl in (5, 6):
        m = ISL == isl
        P = co[m]
        c = P.mean(0)
        w, v = np.linalg.eigh(np.cov((P - c).T))
        ax = v[:, 2]
        t = (P - c) @ ax * 1000
        r = (P - c) - np.outer((P - c) @ ax, ax)
        e1 = np.cross(ax, nr[m].mean(0))
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(ax, e1)
        phi = np.arctan2(r @ e2, r @ e1)
        rr = np.linalg.norm(r, axis=1) * 1000
        half = np.abs(t).max()
        info[isl] = (c, ax, half, rr.max())
        if isl == 5:   # узел бечёвки: три пряди по спирали, ворс
            g = np.cos(3 * phi - 2 * np.pi * t / 3.2)
            h[m] = -0.32 * np.clip(-g, 0, 1) ** 1.5 + 0.05 * fbm_mm(P * 1000, 0.5, 2, 51)
            cols[m] = lin(HEX["twine"]) * (0.85 + 0.25 * (g[:, None] * 0.5 + 0.5))
            ids[m] = IDS["twine"]
        else:          # берёзовая палочка: волокна вдоль, на торцах — кольца
            endm = (np.abs(t) > half - 0.6) & (np.abs(nr[m] @ ax) > 0.6)
            grain = 0.08 * np.sin(phi * 9 + 2.0 * fbm_mm(P * 1000, 1.5, 2, 52))
            rings = 0.07 * np.sin(rr * 2 * np.pi / 0.85)
            h[m] = np.where(endm, rings, grain) + 0.03 * fbm_mm(P * 1000, 0.6, 2, 53)
            cols[m] = np.where(endm[:, None], lin(HEX["wood_end"]) * (1 + 1.5 * rings[:, None]),
                               lin(HEX["wood"]) * (1 + 1.2 * grain[:, None]))
            ids[m] = IDS["wood"]
    set_co(hp, co + nr * (h * MM)[:, None])
    set_attrs(hp.data, cols, ids)
    set_attrs(base.data, np.tile(lin(HEX["twine"]), (len(base.data.vertices), 1)), np.full(len(base.data.vertices), IDS["twine"]))

    # петля: от узла (5) двумя прядями к палочке (6) и вокруг её основания, лежит на манжете
    c5, _, _, _ = info[5]
    c6, ax6, half6, r6 = info[6]
    a5, t5, _ = (float(x[0]) for x in CF.coords(np.array(c5)[None]))
    a6, t6, _ = (float(x[0]) for x in CF.coords(np.array(c6)[None]))
    tw = Tubes()
    rt = 1.25 * MM
    jute = lin(HEX["twine"])
    jute_d = lin(HEX["twine_dark"])
    surf = Surface(hp)

    def jcol(i, k, s):
        return jute * (0.9 + 0.15 * math.sin(s * 2.4 + k)) if k % 3 else jute_d

    loop = []
    Rr = 33.0
    # плоскость манжеты: a (мм вдоль оси) и s (мм по окружности); ось палочки в этой плоскости
    tang6 = np.cross(CF.ax, np.array(CF.radial(t6)))
    d6 = np.array([ax6 @ CF.ax, ax6 @ tang6])
    d6 /= np.linalg.norm(d6) + 1e-9
    p6 = np.array([-d6[1], d6[0]])
    g = np.array([a6, t6 * Rr])
    kn = np.array([a5, t5 * Rr])
    ea, eb = min(half6, 6.0) + 1.4, min(r6, 3.0) + 1.4
    log(f"палочка: ось в плоскости манжеты (a, s) = {d6.round(2)}, длина {2 * half6:.1f} мм, радиус {r6:.1f} мм")

    def E(ph):
        q = g + d6 * ea * math.cos(ph) + p6 * eb * math.sin(ph)
        q[0] = min(q[0], 14.0)
        return q
    phs = np.linspace(0, 2 * math.pi, 241)
    ph0 = phs[np.argmin([np.linalg.norm(E(ph) - kn) for ph in phs])]
    dl = 0.45
    to_kn = (kn - g) / np.linalg.norm(kn - g)
    side = np.array([-to_kn[1], to_kn[0]])
    path2d = []
    a_in = E(ph0 + dl)
    for w in np.linspace(0, 1, 12):          # прядь 1: от узла к палочке
        path2d.append(kn + side * 1.3 + (a_in - kn - side * 1.3) * w)
    for ph in np.linspace(ph0 + dl, ph0 + 2 * math.pi - dl, 40)[1:]:   # вокруг основания палочки
        path2d.append(E(ph))
    a_out = E(ph0 - dl)
    for w in np.linspace(0, 1, 12)[1:]:      # прядь 2: обратно к узлу
        path2d.append(a_out + (kn - side * 1.3 - a_out) * w)
    for aa, ss in path2d:
        tt = ss / Rr
        p = CF.point(aa, tt, 45)
        hit = cuff_surf.bvh.ray_cast(p, -CF.radial(tt), 0.05)
        if hit[0] is None:
            continue
        loop.append(hit[0] + hit[1] * rt * 0.95)
    for _ in range(4):   # пряди ровнее: на складках ткани лучи давали излом
        loop = [loop[0]] + [(loop[i - 1] + loop[i] * 2 + loop[i + 1]) / 4 for i in range(1, len(loop) - 1)] + [loop[-1]]
    tw.add(loop, rt, jute, "twine", seg=12, plies=3, twist_mm=3.4, ply_depth=0.32, col_fn=jcol)
    # ворс джута: короткие волокна от петли и узла
    for k in range(70):
        i = rng.integers(0, len(loop) - 1)
        p = loop[i].lerp(loop[i + 1], rng.random())
        d = Vector(rng.normal(size=3)).normalized()
        pts = [p + d * (rt * 0.9 + j * 0.35 * MM) for j in range(3)]
        tw.add(pts, 0.17 * MM, jute * 1.1, "twine", seg=4, plies=1, rad_fn=lambda t: 1 - 0.6 * t)
    twine = tw.build("closure_twine")
    log(f"застёжка: узел a={a5:.1f} мм, палочка a={a6:.1f} мм, петля {len(loop)} точек")
    return base, hp, [hp, twine], twine


# ----------------------------------------------------------------- запекание
def bake_material():
    m = bpy.data.materials.new("hp")
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL")
    bs = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    em = {}
    for name in ("col", "idc", "msk1", "msk2"):
        a = N.new("ShaderNodeVertexColor")
        a.layer_name = name
        e = N.new("ShaderNodeEmission")
        L.new(a.outputs["Color"], e.inputs["Color"])
        em[name] = e
    geo = N.new("ShaderNodeNewGeometry")
    mp = N.new("ShaderNodeMapRange")
    mp.data_type = "FLOAT_VECTOR"
    mp.inputs[7].default_value = POS_LO
    mp.inputs[8].default_value = POS_HI
    L.new(geo.outputs["Position"], mp.inputs["Vector"])
    e = N.new("ShaderNodeEmission")
    L.new(mp.outputs["Vector"], e.inputs["Color"])
    em["pos"] = e
    return m, out, bs, em


def set_pass(mat, which):
    m, out, bs, em = mat
    L = m.node_tree.links
    for l in list(out.inputs["Surface"].links):
        L.remove(l)
    L.new((bs if which == "view" else em[which]).outputs[0], out.inputs["Surface"])


def setup_cycles(scene, gpu=True):
    scene.render.engine = "CYCLES"
    scene.cycles.use_denoising = False
    scene.cycles.samples = 1
    scene.cycles.device = "CPU"
    if gpu:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for dt in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = dt
                prefs.get_devices()
                devs = [d for d in prefs.devices if d.type == dt]
                if devs:
                    for d in prefs.devices:
                        d.use = d.type == dt
                    scene.cycles.device = "GPU"
                    log("Cycles:", dt, [d.name for d in devs])
                    break
            except TypeError:
                continue


def low_subset(low, isls, name):
    ob = low.copy()
    ob.data = low.data.copy()
    ob.name = name
    ob.hide_render = False   # копия исходной low-poly наследует «не рендерить»
    bpy.context.scene.collection.objects.link(ob)
    fi = face_isl(ob)
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    for p in ob.data.polygons:
        p.select = fi[p.index] not in isls
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.delete(type="FACE")
    bpy.ops.object.mode_set(mode="OBJECT")
    ob.select_set(False)
    return ob


def save_png(name, arr):
    size = arr.shape[0]
    im = bpy.data.images.new(name, size, size, alpha=False)
    im.colorspace_settings.name = "Non-Color"
    buf = np.ones((size, size, 4), np.float32)
    buf[..., :3] = np.clip(arr, 0, 1)
    im.pixels[:] = buf.ravel()
    im.filepath_raw = str(OUT / f"{name}.png")
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)


def bake_all(low, groups, size):
    """groups: [(острова, high-poly, база для вычитания, extrusion мм)]. Каждая группа печётся своей копией
    low-poly без отступа (margin 0) в одну общую картинку — острова групп не пересекаются; отступ — в texture_v1."""
    scene = bpy.context.scene
    setup_cycles(scene, "--cpu" not in ARGS)
    mat = bake_material()
    if scene.world is None:
        scene.world = bpy.data.worlds.new("bake")
    scene.world.light_settings.distance = 0.005
    lm = bpy.data.materials.new("bake_target")
    lm.use_nodes = True
    tex = lm.node_tree.nodes.new("ShaderNodeTexImage")
    lm.node_tree.nodes.active = tex
    allhp = [o for g in groups for o in g[1] + [g[2]]]
    for o in allhp:
        o.data.materials.clear()
        o.data.materials.append(mat[0])
    lows = []
    for gi, (isls, hp, base, ext) in enumerate(groups):
        lg = low_subset(low, isls, f"low_g{gi}")
        lg.data.materials.clear()
        lg.data.materials.append(lm)
        for attr in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission",
                     "visible_volume_scatter", "visible_shadow"):
            setattr(lg, attr, False)
        lows.append(lg)
    bk = scene.render.bake
    bk.use_selected_to_active = True
    bk.use_cage = False
    bk.target = "IMAGE_TEXTURES"
    bk.normal_space = "TANGENT"
    bk.normal_r, bk.normal_g, bk.normal_b = "POS_X", "POS_Y", "POS_Z"   # OpenGL, как в Unity
    OUT.mkdir(parents=True, exist_ok=True)
    passes = (("normal", "NORMAL", "view", 4, False), ("normal_base", "NORMAL", "view", 4, True),
              ("ao", "AO", "view", 64, False), ("color", "EMIT", "col", 4, False),
              ("id", "EMIT", "idc", 1, False), ("msk1", "EMIT", "msk1", 4, False),
              ("msk2", "EMIT", "msk2", 4, False), ("pos", "EMIT", "pos", 1, False))
    only = ARGS[ARGS.index("--only") + 1].split(",") if "--only" in ARGS else None
    SHRINK = [1.5, 1.0, 0.5]   # мм: на время AO цель запекания утоплена внутрь — иначе она сама затеняет
    #                           рельеф, ушедший ниже исходной поверхности (v1, первая сборка: «камуфляж» на войлоке)
    for name, kind, shader, samples, use_base in passes:
        if only and name not in only:
            continue
        set_pass(mat, shader)
        scene.cycles.samples = samples
        scene.cycles.filter_width = 0.01 if name in ("id", "pos") else 1.5
        img = bpy.data.images.new(f"bake_{name}", size, size, alpha=True, float_buffer=True)
        img.colorspace_settings.name = "Non-Color"
        img.generated_color = (0, 0, 0, 0)
        tex.image = img
        for gi, ((isls, hp, base, ext), lg) in enumerate(zip(groups, lows)):
            srcs = [base] if use_base else hp
            for o in allhp:
                o.hide_render = o not in srcs
            # исходная low-poly и цели других групп не должны затенять AO (предпросмотр снимает «не рендерить»
            # со всех объектов — в полном прогоне v1 из-за этого вернулся «камуфляж»)
            low.hide_render = True
            for l2 in lows:
                l2.hide_render = l2 is not lg
            sh = SHRINK[gi] if name == "ao" else 0.0
            if sh:
                me = lg.data
                co0 = np.empty(len(me.vertices) * 3)
                nr0 = np.empty(len(me.vertices) * 3)
                me.vertices.foreach_get("co", co0)
                me.vertices.foreach_get("normal", nr0)
                me.vertices.foreach_set("co", (co0 - nr0 * sh * MM).astype(np.float32))
                me.update()
            bk.cage_extrusion = (ext + sh) * MM
            bk.max_ray_distance = (ext * 2.2 + sh) * MM
            bpy.ops.object.select_all(action="DESELECT")
            for o in srcs:
                o.select_set(True)
            lg.select_set(True)
            bpy.context.view_layer.objects.active = lg
            log(f"запекание {name}, группа {gi} ({sorted(isls)})…")
            bpy.ops.object.bake(type=kind, use_clear=(gi == 0), margin=0)
            if sh:
                me.vertices.foreach_set("co", co0.astype(np.float32))
                me.update()
        px = np.array(img.pixels[:], np.float32).reshape(size, size, 4)
        if name == "pos":
            q = np.clip(px[..., :3], 0, 1) * 65535
            save_png("poshi", np.floor(q / 256) / 255)
            save_png("poslo", (q % 256) / 255)
        else:
            arr = px[..., :3]
            if name == "color":
                arr = np.clip(arr, 0, 1) ** (1 / 2.2)
            save_png(name, arr)
        save_png("coverage", (px[..., 3:4] > 0.5).repeat(3, 2).astype(np.float32)) if name == "id" else None
        bpy.data.images.remove(img)
        log("  ->", name)
    for o in allhp:
        o.hide_render = False


# ----------------------------------------------------------------- предпросмотр high-poly
CLOSURE_VIEW = [(0.43, 0.375, 0.012), (0.1, 0.1, -1), 0.05]


def preview(objs, low, tag):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = "VERTEX"
    sh.show_cavity = False
    scene.render.resolution_x = scene.render.resolution_y = 1100
    cam = bpy.data.objects.new("pcam", bpy.data.cameras.new("pcam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.type = "ORTHO"
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = o not in objs
    views = {"back": ((0.477, 0.30, 0.07), (1, 0, 0), 0.20), "palm": ((0.477, 0.30, 0.07), (-1, 0, 0), 0.20),
             "fingers": ((0.48, 0.24, 0.07), (1, -0.2, 0.15), 0.08), "knuckle": ((0.49, 0.33, 0.07), (1, 0.15, 0.1), 0.07),
             "cuff": ((0.44, 0.39, 0.04), (0.6, 0.3, 0.75), 0.09), "closure": tuple(CLOSURE_VIEW) or None}
    for name, (c, d, sc) in views.items():
        if tag == "cuff" and name not in ("cuff", "closure"):
            continue
        if tag == "hand" and name in ("cuff", "closure"):
            continue
        c, d = Vector(c), Vector(d).normalized()
        cam.location = c + d * 0.5
        cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.data.ortho_scale = sc
        scene.render.filepath = str(REN / f"hp_{name}.png")
        bpy.ops.render.render(write_still=True)
        log("предпросмотр", name)
    for o in bpy.data.objects:
        o.hide_render = False
    bpy.data.objects.remove(cam)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rng = np.random.default_rng(20261120)
    low = load_low()
    low.hide_render = True
    hb, hhp, hand_objs, fingers = build_hand(low, rng)
    cb, chp, cuff_objs, CF, cuff_surf = build_cuff(low, rng)
    sb, shp, small_objs, twine = build_closure(low, CF, cuff_surf, rng)
    for o in (hb, cb, sb):
        o.hide_viewport = False
    if "--preview" in ARGS:
        preview([o for o in hand_objs if o], low, "hand")
        vv = np.empty(len(shp.data.vertices) * 3)
        shp.data.vertices.foreach_get("co", vv)
        cc = vv.reshape(-1, 3).mean(0)
        rd = cc - CF.c
        rd -= CF.ax * (rd @ CF.ax)
        rd /= np.linalg.norm(rd)
        CLOSURE_VIEW[:] = [tuple(cc), tuple(rd + CF.ax * 0.15), 0.045]
        preview([o for o in cuff_objs + small_objs if o], low, "cuff")
    if "--blend" in ARGS:
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE / "source" / "gloves_hp.blend"), compress=True)
    if "--nobake" not in ARGS:
        groups = [({1, 2}, [o for o in hand_objs if o], hb, 2.8),
                  ({3, 4, 7}, [o for o in cuff_objs if o] + [twine], cb, 2.6),
                  ({5, 6}, [o for o in small_objs if o], sb, 2.0)]
        bake_all(low, groups, SIZE)
    log("готово")


main()
