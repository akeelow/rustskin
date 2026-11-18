"""Sauna Bucket: high-poly банной шайки поверх оригинального Bucket Helmet и запекание на его развёртку.

Всё, у чего есть форма, — геометрия (план: PLAN.md, номера деталей в скобках):
  wall    стенка снаружи (остров 1): 18 клёпок разной ширины (1, 2), V-щели (3), ступеньки (4), волокна (5),
          сучки (6), набухший низ (8), трещины (9), вмятины (10), гнездо дроби со свинцом (11), царапины (12),
          пропил окна: свежая фаска, сколы, запилы, щепки (26–28), молотковые промахи у гвоздей (14)
  hoops   два кованых обруча (16–25): нижний — на валике края, перепилен окном, концы прибиты; верхний — с
          нахлёстом; заклёпки, грани ковки, вмятины, раковины двух масштабов
  nails   кованые гвозди вкладыша (14), гвозди сетки (33), загнутые гвозди
  leaf    берёзовый лист (50), черешок под обручем
  resin   капля смолы у сучка (7)
  top     макушка (остров 3): утор — торцы тех же 18 клёпок с кольцами (34, 35), днище из трёх досок (36),
          шканты (37), жестяная латка на трещине (38), вмятина и скол (39)
  inner   изнанка (7, 37): жестяной вкладыш — шов внахлёст с гвоздями, вмятины-шишки, край у дна, зубчатый край
          у окна (30, 45–49)
  cut     торец окна (остров 6): дерево с бороздками пилы + полоска жести (29)
  ears    ушки (5, 9) и их гвозди (8): дощечка с волокнами, узел верёвки в дырке, распушённый обрывок (41–44)
  wires   сетка (10–36, 38–45): свив проволоки, бугры цинка, раковины (31); общие узлы (2, 4, 28) — гладкие

Координаты — как в OBJ: метры, y вверх, +z — лицо. Азимут θ = atan2(x, z − zc(y)), u = 0.5 + θ/360.

Запуск (из корня репозитория):
  blender -b -P skins/sauna/bucket-helmet/bake_bucket.py -- [--size 4096] [--look] [--nobake] [--blend] [--only wall,top,...]
Пишет bake/{normal,ao,aowide,color,id,msk,poshi,poslo}.png и bake/layout.json (положения деталей для texture_v1.py).
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector, kdtree
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import noise_np as NN  # noqa: E402

OBJ = HERE / "originals" / "bucket.helmet.obj"
OUT = HERE / "bake"
D2R = math.pi / 180

IDS = {"wood": 1, "endgrain": 2, "fresh": 3, "iron": 4, "rivet": 5, "nail": 6, "tin": 7, "rope": 8,
       "leaf": 9, "resin": 10, "wire": 11, "lead": 12, "paint": 13}
POS_LO = np.array([-0.17, 0.10, -0.17])
POS_HI = np.array([0.17, 0.42, 0.17])

# базовые цвета деталей (sRGB HEX); итоговая палитра, мокрое, разводы, ржавые потёки — texture_v1.py
HEX = {"wood": "C2A77E", "wood_late": "9C825C", "wood_end": "A88D66", "end_ring": "7E6546",
       "fresh": "DCC7A0", "knot": "6E4E30", "iron": "3A3632", "iron_edge": "6A6560", "rust": "8C4A26",
       "tin": "8A8C8E", "rope": "B8A27A", "rope_dark": "8A7656", "leaf": "5C6A39", "leaf_vein": "7E8A4E",
       "leaf_edge": "8A7A3A", "resin": "8A5A22", "lead": "5A5C60", "wire": "8E9290", "zinc": "B9BDB8"}


def lin(h):
    return np.array([(int(h[i:i + 2], 16) / 255) ** 2.2 for i in (0, 2, 4)])


def smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


# ================================================================ low-poly
def load_low():
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="Y", up_axis="Z")
    low = bpy.context.selected_objects[0]
    low.name = "low"
    V, Fc = [], []
    for line in open(OBJ):
        if line.startswith("v "):
            V.append(Vector([float(x) for x in line.split()[1:4]]))
        elif line.startswith("f "):
            idx = [int(c.split("/")[0]) - 1 for c in line.split()[1:]]
            Fc.append(sum((V[j] for j in idx), Vector()) / len(idx))
    isl = json.load(open(HERE / "uv" / "faces_obj.json"))
    kd = kdtree.KDTree(len(Fc))
    for i, c in enumerate(Fc):
        kd.insert(c, i)
    kd.balance()
    low["isl"] = [isl[kd.find(p.center)[1]] for p in low.data.polygons]
    return low


def bvh_of(low, islands):
    me = low.data
    isl = low["isl"]
    verts = [v.co.copy() for v in me.vertices]
    return BVHTree.FromPolygons(verts, [list(p.vertices) for p in me.polygons if isl[p.index] in islands])


def loops_of(low, islands):
    """Граничные петли островов (списки координат вершин)."""
    me = low.data
    isl = low["isl"]
    cnt = {}
    for p in me.polygons:
        if isl[p.index] not in islands:
            continue
        vs = list(p.vertices)
        for a, b in zip(vs, vs[1:] + vs[:1]):
            k = (min(a, b), max(a, b))
            cnt[k] = cnt.get(k, 0) + 1
    adj = {}
    for (a, b), c in cnt.items():
        if c == 1:
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
    seen, out = set(), []
    for s in adj:
        if s in seen:
            continue
        lp, cur = [s], s
        seen.add(s)
        while True:
            nx = [n for n in adj[cur] if n not in seen]
            if not nx:
                break
            cur = nx[0]
            seen.add(cur)
            lp.append(cur)
        out.append([me.vertices[i].co.copy() for i in lp])
    return out


# ================================================================ cone field
def axis_z(y):
    """Ось ведра чуть наклонена: центр колец z 0.0036 у края → 0.013 у макушки (разбор 18.11)."""
    return 0.0036 + (np.asarray(y) - 0.145) * (0.013 - 0.0036) / (0.395 - 0.145)


class Field:
    """Радиус гладкой поверхности r(θ, y) по лучам от оси к low-poly; по θ — ряд Фурье до 4-й гармоники (без
    граней low-poly, но с овалом и наклоном), по y — как есть (валик края и закатанная кромка — настоящая
    форма). sign=+1 — наружная стенка, луч от оси; inner — тот же луч, первая встреча (изнанка)."""

    def __init__(self, bvh, y0, y1, dy=0.001, dth=1.0):
        self.ys = np.arange(y0, y1 + 1e-9, dy)
        self.th = np.arange(-180, 180, dth)
        R = np.full((len(self.ys), len(self.th)), np.nan)
        for j, y in enumerate(self.ys):
            zc = float(axis_z(y))
            for i, t in enumerate(self.th):
                d = Vector((math.sin(t * D2R), 0, math.cos(t * D2R)))
                hit = bvh.ray_cast(Vector((0, y, zc)), d, 0.3)
                if hit[0] is not None:
                    R[j, i] = (hit[0] - Vector((0, y, zc))).length
        # гармоники по θ
        K = 4
        A = [np.ones_like(self.th)]
        for k in range(1, K + 1):
            A += [np.cos(k * self.th * D2R), np.sin(k * self.th * D2R)]
        A = np.stack(A, 1)
        self.coef = np.full((len(self.ys), A.shape[1]), np.nan)
        cnt = np.isfinite(R).sum(1)
        full = cnt >= 280          # ряды, где лучи попали почти по всему кругу: полный ряд Фурье
        for j in np.where(full)[0]:
            ok = np.isfinite(R[j])
            self.coef[j] = np.linalg.lstsq(A[ok], R[j, ok], rcond=None)[0]
        fj = np.where(full)[0]
        for j in np.where(~full)[0]:   # неполные ряды (край, кромка): гармоники ближайшего полного, свой средний
            jn = fj[np.argmin(np.abs(fj - j))]
            self.coef[j] = self.coef[jn]
            ok = np.isfinite(R[j])
            if ok.sum() > 10:
                self.coef[j, 0] += np.mean(R[j, ok] - A[ok] @ self.coef[jn])
        # остаток (вмятины оригинала) — сглаженный: грани low-poly (шаг 11.25°) уходят, вмятины остаются
        fit = self.coef @ A.T
        res = np.where(np.isfinite(R), R - fit, 0.0)
        wgt = np.isfinite(R).astype(float)

        def blur(a, sx, sy):
            kx = np.exp(-0.5 * (np.arange(-3 * sx, 3 * sx + 1) / sx) ** 2)
            ky = np.exp(-0.5 * (np.arange(-3 * sy, 3 * sy + 1) / sy) ** 2)
            a = np.concatenate([a[:, -3 * sx:], a, a[:, :3 * sx]], 1)
            a = np.apply_along_axis(lambda r: np.convolve(r, kx, "same"), 1, a)[:, 3 * sx:-3 * sx]
            return np.apply_along_axis(lambda c: np.convolve(c, ky, "same"), 0, a)
        sres = blur(res, int(5 / dth), max(1, int(0.003 / dy)))
        sw = blur(wgt, int(5 / dth), max(1, int(0.003 / dy)))
        self.res = np.clip(np.where(sw > 0.2, sres / np.maximum(sw, 1e-6), 0.0), -0.006, 0.006)
        self.dth = dth
        self.raw = R
        self.K = K

    def r(self, th, y):
        th = np.asarray(th, float)
        y = np.asarray(y, float)
        fy = np.clip((y - self.ys[0]) / (self.ys[1] - self.ys[0]), 0, len(self.ys) - 1.001)
        j = np.floor(fy).astype(int)
        w = fy - j
        c = self.coef[j] * (1 - w)[..., None] + self.coef[j + 1] * w[..., None]
        out = c[..., 0].copy()
        for k in range(1, self.K + 1):
            out += c[..., 2 * k - 1] * np.cos(k * th * D2R) + c[..., 2 * k] * np.sin(k * th * D2R)
        # + сглаженный остаток (билинейно по θ, y)
        ft = ((th + 180) % 360) / self.dth
        i = np.floor(ft).astype(int) % self.res.shape[1]
        i2 = (i + 1) % self.res.shape[1]
        wt = ft - np.floor(ft)
        rr = self.res
        a = rr[j, i] * (1 - wt) + rr[j, i2] * wt
        b = rr[j + 1, i] * (1 - wt) + rr[j + 1, i2] * wt
        return out + a * (1 - w) + b * w

    def point(self, th, y, h=0.0):
        th = np.asarray(th, float)
        y = np.asarray(y, float)
        r = self.r(th, y) + h
        return np.stack([r * np.sin(th * D2R), y, axis_z(y) + r * np.cos(th * D2R)], -1)


# ================================================================ mesh helpers
def mesh_np(name, verts, faces, cols=None, ids=None, msk=None, smooth_shade=True):
    me = bpy.data.meshes.new(name)
    fl = faces.tolist() if isinstance(faces, np.ndarray) else [list(f) for f in faces]
    me.from_pydata(np.asarray(verts, np.float32).tolist(), [], fl)
    me.update()
    n = len(me.vertices)
    for attr, arr, default in (("col", cols, (0.5, 0.5, 0.5)), ("msk", msk, (0, 0, 0))):
        a = me.color_attributes.new(attr, "FLOAT_COLOR", "POINT")
        flat = np.ones((n, 4), np.float32)
        flat[:, :3] = default if arr is None else arr
        a.data.foreach_set("color", flat.ravel())
    a = me.color_attributes.new("idc", "FLOAT_COLOR", "POINT")
    flat = np.ones((n, 4), np.float32)
    flat[:, 1:3] = 0
    iv = np.full(n, IDS["wood"]) if ids is None else (np.full(n, IDS[ids]) if isinstance(ids, str) else ids)
    flat[:, 0] = (iv * 16 + 8) / 255
    a.data.foreach_set("color", flat.ravel())
    if smooth_shade:
        me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), bool))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def grid_faces(nu, nv, closed_u=False, keep=None):
    i = np.arange(nu if closed_u else nu - 1)
    j = np.arange(nv - 1)
    I, J = np.meshgrid(i, j, indexing="ij")
    I, J = I.ravel(), J.ravel()
    I2 = (I + 1) % nu
    q = np.stack([I * nv + J, I2 * nv + J, I2 * nv + J + 1, I * nv + J + 1], 1)
    if keep is not None:
        q = q[keep.ravel()]
    return q


def flip_if_inward(ob, ref):
    """ref(центр грани) -> вектор «наружу»; переворачивает меш, если большинство граней смотрит внутрь."""
    me = ob.data
    s = 0.0
    for p in list(me.polygons)[:: max(1, len(me.polygons) // 400)]:
        s += p.normal.dot(ref(p.center)) * p.area
    if s < 0:
        me.flip_normals()
        me.update()


def dome(center, normal, r, hgt, name, tilt=None, seg=20, ring=8, ident="rivet", col=None, msk_top=0.8):
    """Купол заклёпки: шапка эллипсоида на поверхности."""
    n = Vector(normal).normalized()
    if tilt is not None:
        n = (n + Vector(tilt)).normalized()
    a = Vector((0, 1, 0)) if abs(n.y) < 0.9 else Vector((1, 0, 0))
    t1 = n.cross(a).normalized()
    t2 = n.cross(t1)
    verts, cols, msk = [], [], []
    for i in range(ring + 1):
        ph = (math.pi / 2) * i / ring
        rr = r * math.cos(ph) * (1.04 if i == 0 else 1.0)
        hh = hgt * math.sin(ph) - (0.0003 if i == 0 else 0)
        for k in range(seg):
            a_ = 2 * math.pi * k / seg
            verts.append(center + (t1 * math.cos(a_) + t2 * math.sin(a_)) * rr + n * hh)
            cols.append(lin(HEX["iron"]) if col is None else col)
            msk.append((msk_top * (math.sin(ph) ** 2), 0, 0.6))
    faces = []
    for i in range(ring):
        for k in range(seg):
            k2 = (k + 1) % seg
            faces.append((i * seg + k, i * seg + k2, (i + 1) * seg + k2, (i + 1) * seg + k))
    ob = mesh_np(name, verts, faces, np.array(cols), ident, np.array(msk))
    flip_if_inward(ob, lambda p: p - center)
    return ob


def forged_nail(center, normal, r, name, rng, flat=0.55):
    """Кованая шляпка: четырёхгранная пирамидка с притупленной вершиной и «лепестками» от ударов."""
    n = Vector(normal).normalized()
    a = Vector((0, 1, 0)) if abs(n.y) < 0.9 else Vector((1, 0, 0))
    t1 = n.cross(a).normalized()
    t2 = n.cross(t1)
    rot = rng.uniform(0, math.pi / 2)
    verts = []
    rings = [(1.0, -0.0003), (1.0, r * 0.18), (0.45, r * flat), (0.18, r * flat * 1.1)]
    for rr, hh in rings:
        for k in range(8):
            ang = rot + k * math.pi / 4
            sq = 1.0 / max(abs(math.cos(ang - rot)), abs(math.sin(ang - rot)))   # квадратная шляпка
            jag = 1 + rng.uniform(-0.08, 0.1)
            verts.append(center + (t1 * math.cos(ang) + t2 * math.sin(ang)) * (r * rr * sq * 0.78 * jag) + n * hh)
    verts.append(center + n * r * flat * 1.15)
    faces = []
    for i in range(len(rings) - 1):
        for k in range(8):
            k2 = (k + 1) % 8
            faces.append((i * 8 + k, i * 8 + k2, (i + 1) * 8 + k2, (i + 1) * 8 + k))
    top = len(verts) - 1
    for k in range(8):
        faces.append((24 + k, 24 + (k + 1) % 8, top))
    m = np.zeros((len(verts), 3))
    m[:, 0] = [0.0] * 8 + [0.3] * 8 + [0.7] * 17
    m[:, 2] = 0.8
    ob = mesh_np(name, verts, faces, np.tile(lin(HEX["iron"]), (len(verts), 1)), "nail", m)
    flip_if_inward(ob, lambda p: p - center)
    return ob


def tube(points, radius, name, ident, col, seg=10, strands=3, groove=0.32, twist=1.0, fray=None):
    """Труба по ломаной: верёвка (свив strands прядей) или проволока; fray(i) -> множитель радиуса."""
    pts = [Vector(p) for p in points]
    n = len(pts)
    verts, cols = [], []
    prev = None
    s = 0.0
    for i, p in enumerate(pts):
        if i:
            s += (p - pts[i - 1]).length
        tng = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        if prev is None:
            a = Vector((0, 1, 0)) if abs(tng.y) < 0.9 else Vector((1, 0, 0))
            prev = tng.cross(a).normalized()
        b1 = (prev - tng * prev.dot(tng)).normalized()
        b2 = tng.cross(b1)
        prev = b1
        rr = radius * (fray(i) if fray else 1.0)
        for k in range(seg):
            a = 2 * math.pi * k / seg
            # свив: канавки по спирали, шаг = 2π·r·strands·twist
            ph = strands * a - s / (radius * twist + 1e-9)
            g = 1.0 - groove * max(0.0, math.cos(ph)) ** 3
            verts.append(p + (b1 * math.cos(a) + b2 * math.sin(a)) * rr * g)
            cols.append(col * (0.75 + 0.25 * (1 - max(0.0, math.cos(ph)) ** 3)))
    faces = []
    for i in range(n - 1):
        for k in range(seg):
            k2 = (k + 1) % seg
            faces.append((i * seg + k, i * seg + k2, (i + 1) * seg + k2, (i + 1) * seg + k))
    ob = mesh_np(name, verts, faces, np.array(cols), ident)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


# ================================================================ hole outline
class Hole:
    """Контур смотровой дыры в (x = θ·R0, y), метры; дистанция и параметр вдоль контура для точек стенки."""
    R0 = 0.137

    def __init__(self, low):
        lps = loops_of(low, {1})
        lp = max(lps, key=len)   # нижний край + дыра одной петлёй
        P = np.array([[math.atan2(c.x, c.z - float(axis_z(c.y))) / D2R, c.y] for c in lp])
        front = (np.abs(P[:, 0]) < 70) & (P[:, 1] > 0.1402)
        # самая длинная непрерывная серия «спереди» (петля циклическая)
        n = len(P)
        best, cur, start = (0, 0), 0, 0
        for k in range(2 * n):
            if front[k % n]:
                if cur == 0:
                    start = k
                cur += 1
                if cur > best[1] and cur <= n:
                    best = (start, cur)
            else:
                cur = 0
        idx = [(best[0] + k) % n for k in range(best[1])]
        Q = P[idx]
        if Q[0, 0] > Q[-1, 0]:
            Q = Q[::-1]
        # замкнуть ниже края
        Q = np.vstack([[Q[0, 0], 0.120], Q, [Q[-1, 0], 0.120]])
        self.th = Q[:, 0]
        self.y = Q[:, 1]
        self.poly = np.stack([Q[:, 0] * D2R * self.R0, Q[:, 1]], 1)
        seg = np.diff(self.poly, axis=0)
        self.cum = np.r_[0, np.cumsum(np.linalg.norm(seg, axis=1))]

    def query(self, th, y, chunk=30000):
        """-> (расстояние до контура, м; внутри — отрицательное), параметр вдоль контура (м)."""
        X = np.stack([np.asarray(th, float).ravel() * D2R * self.R0, np.asarray(y, float).ravel()], 1)
        d = np.empty(len(X))
        s = np.empty(len(X))
        A, B = self.poly[:-1], self.poly[1:]
        AB = B - A
        L2 = (AB ** 2).sum(1) + 1e-18
        for c0 in range(0, len(X), chunk):
            x = X[c0:c0 + chunk]
            t = np.clip(((x[:, None, :] - A[None]) * AB[None]).sum(2) / L2[None], 0, 1)
            Pp = A[None] + t[..., None] * AB[None]
            dd = np.linalg.norm(x[:, None, :] - Pp, axis=2)
            k = dd.argmin(1)
            d[c0:c0 + chunk] = dd[np.arange(len(x)), k]
            s[c0:c0 + chunk] = self.cum[k] + t[np.arange(len(x)), k] * np.sqrt(L2[k])
            # внутри: число пересечений луча вправо
            yy, xx = x[:, 1][:, None], x[:, 0][:, None]
            P0, P1 = self.poly[:, :][None, :-1], self.poly[None, 1:]
            cond = ((P0[..., 1] > yy) != (P1[..., 1] > yy))
            xint = P0[..., 0] + (yy - P0[..., 1]) * (P1[..., 0] - P0[..., 0]) / (P1[..., 1] - P0[..., 1] + 1e-18)
            inside = (cond & (xx < xint)).sum(1) % 2 == 1
            d[c0:c0 + chunk][inside] *= -1
        sh = np.shape(th)
        return d.reshape(sh), s.reshape(sh)

    def th_range_at(self, y0, y1):
        """Крайние азимуты дыры в полосе высот (для обреза нижнего обруча)."""
        m = (self.y >= y0 - 0.002) & (self.y <= y1 + 0.002)
        return self.th[m].min(), self.th[m].max()


# ================================================================ layout
def stave_layout(rng):
    """18 клёпок разной ширины: щель на 0° и ±180° (шов развёртки), ушки (±90°) посередине клёпки."""
    b = []
    for lo, sgn in ((-180.0, 1), (0.0, 1)):
        w = rng.uniform(17.0, 23.0, 9)
        a, c = w[:4], w[5:]
        a = a * (90 - w[4] / 2) / a.sum()
        c = c * (90 - w[4] / 2) / c.sum()
        ws = np.r_[a, w[4], c]
        b += list(lo + np.r_[0, np.cumsum(ws)][:-1])
    b.append(180.0)
    return np.array(b)


class Layout:
    def __init__(self, rng, hole):
        self.b = stave_layout(rng)
        ns = len(self.b) - 1
        self.ns = ns
        self.off = rng.uniform(-0.0004, 0.0004, ns)        # ступенька между клёпками (4)
        self.tilt = rng.uniform(-0.0025, 0.0025, ns)       # наклон клёпки (м/м по высоте)
        self.tone = rng.uniform(-1, 1, ns)                 # тон клёпки
        self.pitch = rng.uniform(0.0032, 0.0048, ns)       # шаг годовых слоёв на лице клёпки
        self.cath = (rng.random(ns) < 0.5) * rng.uniform(0.6, 1.0, ns)   # «арки» тангентального распила
        self.ya = rng.uniform(0.18, 0.36, ns)
        self.phi = rng.uniform(0, 6.28, ns)
        self.hole = hole
        # верхний и нижний обруч (16, 17)
        self.hoop_up = (0.335, 0.357)
        self.hoop_lo = (0.1405, 0.1625)
        self.joint_th = -68.0      # нахлёст верхнего обруча (19)
        self.joint_len = 0.045
        lo_l, lo_r = hole.th_range_at(*self.hoop_lo)
        self.hoop_lo_cut = (lo_l - 3.0, lo_r + 3.0)        # концы нижнего обруча — у окна
        self.knots = [(-122.0, 0.245, 0.0055, True), (138.0, 0.300, 0.0042, False), (72.0, 0.215, 0.0065, False)]
        self.leaf = (52.0, 0.302)      # центр листа (θ, y)
        self.shot = (-21.0, 0.313)     # гнездо дроби
        self.data = {}

    def stave_of(self, th):
        k = np.clip(np.searchsorted(self.b, th, side="right") - 1, 0, self.ns - 1)
        s = (th - self.b[k]) / (self.b[k + 1] - self.b[k])
        return k, s


# ================================================================ wall (остров 1)
def wall_relief(L, F, TH, Y, rng):
    """Высота над гладкой поверхностью (м), цвет (лин.), маски (R свежее, G впадина, B источник ржавчины), id."""
    N = TH.shape
    r = F.r(TH, Y)
    k, s = L.stave_of(TH)
    wdt = (L.b[k + 1] - L.b[k]) * D2R * r
    de = np.minimum(s, 1 - s) * wdt
    arc = TH * D2R * r
    h = np.zeros(N)
    R = np.zeros(N)
    G = np.zeros(N)
    B = np.zeros(N)
    ids = np.full(N, IDS["wood"])
    # (3) щель: фаски 1.6 мм до −1.1 мм + зазор 0.8 мм до −1.9 мм
    h += -0.0011 * (1 - smooth(de / 0.0016)) - 0.0008 * (1 - smooth(de / 0.0004))
    G += 1 - smooth(de / 0.0012)
    # плоская клёпка (лёгкая грань) и ступенька (4)
    h += -0.0005 * 4 * s * (1 - s)
    h += L.off[k] + L.tilt[k] * (Y - 0.27)
    # (5) волокна: годовые слои бороздками; xs — поперёк клёпки
    xs = (s - 0.5) * wdt
    wav = 0.0011 * np.sin(2 * np.pi * Y / 0.17 + L.phi[k]) + 0.0009 * (NN.fbm(np.stack([Y * 25, k * 3.1 + 0 * Y, Y * 0], -1), 3, 5) - 0.5)
    cath = L.cath[k] * 0.010 * np.exp(-((Y - L.ya[k]) / 0.05) ** 2) * np.cos(np.clip(xs / (wdt * 0.5), -1, 1) * np.pi / 2)
    defl = np.zeros(N)
    knot_m = np.zeros(N)
    for (kt, ky, kr, _) in L.knots:          # (6) волокна обтекают сучок
        dx = (TH - kt) * D2R * r
        dy = Y - ky
        dd = np.sqrt(dx ** 2 + (dy / 2.2) ** 2)
        defl += 1.7 * kr * dx / (np.abs(dx) + 0.35 * kr + 1e-9) * np.exp(-(dd / (3.2 * kr)) ** 2)
        knot_m = np.maximum(knot_m, 1 - smooth(np.sqrt(dx ** 2 + dy ** 2) / kr))
    phase = (xs + wav + cath + defl) / L.pitch[k]
    g = (0.5 + 0.5 * np.cos(2 * np.pi * phase)) ** 4
    # слои разной силы: у каждого годового кольца своя глубина (0.3…1.25), иначе «вельвет»
    ring_n = np.floor(phase + 0.5)
    g = g * (0.3 + 0.95 * NN.vnoise(np.stack([ring_n * 1.37, k * 5.3 + 0 * ring_n, Y * 6.0], -1), 21))
    swell = smooth((0.205 - Y) / 0.04)        # (8) набухший низ над нижним обручем
    gamp = 0.00036 * (1 + 0.5 * swell) * (0.75 + 0.5 * NN.vnoise(np.stack([TH * 0.6, Y * 300, k * 7.0 + 0 * Y], -1), 3))
    h += -gamp * g
    h += 0.00045 * swell
    # вторичный рисунок: тонкие поры между слоями (2 px по высоте — только намёк)
    h += -0.00008 * (0.5 + 0.5 * np.cos(4 * np.pi * phase + 1.3))
    tone = L.tone[k]
    base = lin(HEX["wood"])
    late = lin(HEX["wood_late"])
    t = 0.55 * g + 0.15 * swell
    col = np.empty(N + (3,))
    for c in range(3):
        col[..., c] = (base[c] * (1 - t) + late[c] * t) * (1 + 0.07 * tone)
    # сучки: кольца и тёмная сердцевина
    for (kt, ky, kr, pit) in L.knots:
        dx = (TH - kt) * D2R * r
        dy = Y - ky
        dd = np.sqrt(dx ** 2 + (dy / 1.25) ** 2)
        inside = 1 - smooth((dd - kr) / 0.0008 + 0.5)
        ring = 0.5 + 0.5 * np.cos(2 * np.pi * dd / 0.0021)
        h += inside * (-0.0003 * ring - 0.0002)
        if pit:
            h += -0.0011 * (1 - smooth(dd / (kr * 0.38)))
            G += 1 - smooth(dd / (kr * 0.45))
        kc = lin(HEX["knot"])
        for c in range(3):
            col[..., c] = col[..., c] * (1 - inside * (0.55 + 0.25 * ring)) + kc[c] * inside * (0.55 + 0.25 * ring)
        # тёмный ореол
        halo = np.exp(-(dd / (1.8 * kr)) ** 2) * 0.25
        col *= (1 - halo)[..., None]
    # (9) трещины-усушки: от нижнего обруча вверх и от макушки вниз
    cracks = []
    for _ in range(5):
        while True:
            ct = rng.uniform(-175, 175)
            if abs(ct) > 48 and abs(abs(ct) - 90) > 8:
                break
        cracks.append((ct, L.hoop_lo[1] - 0.001, rng.uniform(0.016, 0.045), rng.uniform(0.0017, 0.0022)))
    for _ in range(2):
        ct = rng.uniform(-170, 170)
        if abs(ct) < 50:
            ct += 100
        cracks.append((ct, 0.386, -rng.uniform(0.014, 0.026), 0.0017))
    for (ct, y0, ln, w0) in cracks:
        kk, _ = L.stave_of(np.array([ct]))
        cc = ct
        tt = (Y - y0) / ln
        on = (tt >= 0) & (tt <= 1)
        wig = 0.0006 * np.sin(Y / 0.007 + ct) + 0.0003 * np.sin(Y / 0.0023 + 2 * ct)
        dx = (TH - cc) * D2R * r - wig
        w = (w0 * (1 - np.clip(tt, 0, 1)) ** 0.7 + 0.0003)
        prof = (1 - smooth(np.abs(dx) / (w / 2 + 1e-9))) * on * (1 - smooth((tt - 0.85) / 0.15))
        h += -0.0016 * prof
        G = np.maximum(G, prof)
    L.data["cracks"] = cracks
    # (10) вмятины: гуще на лбу и висках
    dents = [(-58, 0.298, 0.015, 0.0006), (40, 0.232, 0.011, 0.0005), (-95, 0.275, 0.007, 0.0004),
             (8, 0.318, 0.008, 0.00035), (118, 0.255, 0.009, 0.0004), (-150, 0.33 - 0.03, 0.006, 0.0003)]
    for (dt, dy0, dr, dp) in dents:
        rho = np.sqrt(((TH - dt) * D2R * r) ** 2 + (Y - dy0) ** 2)
        bowl = np.clip(1 - (rho / dr) ** 2, 0, 1) ** 2
        h += -dp * bowl + gamp * g * 0.5 * bowl      # волокна в вмятине смяты
        G = np.maximum(G, 0.35 * bowl)
    L.data["dents"] = dents
    # (11) гнездо дроби: 5 ямок, вокруг вырванные волокна, в двух — свинец
    st, sy = L.shot
    shots = [(st + 0.0, sy + 0.000), (st + 5.5, sy + 0.009), (st - 4.0, sy - 0.006), (st + 8.0, sy - 0.004),
             (st - 6.5, sy + 0.010)]
    for i, (pt, py) in enumerate(shots):
        dx = (TH - pt) * D2R * r
        dy = Y - py
        rho = np.sqrt(dx ** 2 + dy ** 2)
        pr = 0.0029
        pit = 1 - smooth((rho - pr * 0.75) / (pr * 0.4))
        h += -0.0009 * pit
        G = np.maximum(G, pit)
        ang = np.arctan2(dy, dx)
        petal = (0.5 + 0.5 * np.cos(5 * ang + i)) ** 3 * np.exp(-((rho - pr * 1.25) / (pr * 0.45)) ** 2)
        h += 0.00025 * petal
        R = np.maximum(R, np.clip(petal * 1.4, 0, 1) * (1 - pit) + 0.6 * np.exp(-((rho - pr) / (pr * 0.5)) ** 2))
        if i in (0, 2):     # свинцовая дробина в ямке
            ball = np.clip(1 - (rho / (pr * 0.55)) ** 2, 0, 1)
            h += 0.0007 * np.sqrt(ball)
            ids = np.where(ball > 0.05, IDS["lead"], ids)
    L.data["shots"] = shots
    # (12) царапины поперёк волокна
    scr = []
    for _ in range(8):
        while True:
            ct = rng.uniform(-170, 170)
            cy = rng.uniform(0.175, 0.33)
            if not (abs(ct) < 48 and cy < 0.30):
                break
        scr.append((ct, cy, rng.uniform(0.02, 0.06), rng.uniform(-25, 25) * D2R, rng.uniform(0.0015, 0.002)))
    for (ct, cy, ln, an, wd) in scr:
        dx = (TH - ct) * D2R * r
        dy = Y - cy
        along = dx * math.cos(an) + dy * math.sin(an)
        across = -dx * math.sin(an) + dy * math.cos(an) + 0.0006 * np.sin(along / 0.004)
        tt = np.abs(along) / (ln / 2)
        on = 1 - smooth((tt - 0.7) / 0.3)
        grv = (1 - smooth(np.abs(across) / (wd / 2))) * on
        lip = np.exp(-((np.abs(across) - wd * 0.75) / (wd * 0.25)) ** 2) * on
        h += -0.00038 * grv + 0.00008 * lip
        R = np.maximum(R, grv * 0.9)
    L.data["scratches"] = scr
    # (26–28) окно: свежая фаска, сколы, запилы, щепки
    hd, hs = L.hole.query(TH, Y)
    band = 0.0032 + 0.0045 * NN.vnoise(np.stack([hs * 90, hs * 0 + 1.7, hs * 0], -1), 9)
    near = (hd >= -0.002) & (hd < 0.02)
    seg_rand = NN.vnoise(np.stack([np.floor(hs / 0.006) * 3.7, hs * 0 + 4.2, hs * 0], -1), 11)
    fac = np.clip(1 - np.maximum(hd, 0) / band, 0, 1)
    h += near * (-(0.0004 + 0.0007 * seg_rand) * fac ** 1.3)
    fresh_w = near * smooth(fac * 1.6) ** 0.8          # свежее дерево плавно светлеет к кромке
    R = np.maximum(R, fresh_w)
    ids = np.where(near & (fac > 0.45), IDS["fresh"], ids)
    # сколы по кромке
    chips = []
    total = L.hole.cum[-1]
    for i in range(14):
        cs = rng.uniform(0.02 * total, 0.98 * total)
        chips.append((cs, rng.uniform(0.002, 0.005), rng.uniform(0.0005, 0.001)))
    for (cs, cr, cdp) in chips:
        rho = np.sqrt((hs - cs) ** 2 + (hd - cr * 0.3) ** 2)
        bowl = np.clip(1 - (rho / cr) ** 2, 0, 1) ** 1.5 * near
        h += -cdp * bowl
        R = np.maximum(R, smooth(bowl * 3))
        ids = np.where(bowl > 0.05, IDS["fresh"], ids)
    # запилы в трёх острых углах контура: бороздка дальше угла
    P = L.hole.poly
    ang = []
    for i in range(2, len(P) - 2):
        a = P[i] - P[i - 2]
        c = P[i + 2] - P[i]
        cosv = (a @ c) / (np.linalg.norm(a) * np.linalg.norm(c) + 1e-12)
        if P[i, 1] > 0.17:
            ang.append((cosv, i))
    ang.sort()
    kerfs = []
    for _, i in ang[:3]:
        d0 = P[i] - P[i - 2]
        d0 = d0 / (np.linalg.norm(d0) + 1e-12)
        kerfs.append((P[i].copy(), d0, rng.uniform(0.006, 0.015)))
    for (p0, d0, ln) in kerfs:
        X = TH * D2R * Hole.R0 - p0[0]
        Yy = Y - p0[1]
        along = X * d0[0] + Yy * d0[1]
        across = -X * d0[1] + Yy * d0[0]
        on = (along > -0.001) & (along < ln)
        tip = 1 - smooth((along - ln * 0.7) / (ln * 0.3))
        grv = (1 - smooth(np.abs(across) / 0.001)) * on * tip
        h += -0.001 * grv
        G = np.maximum(G, grv)
        R = np.maximum(R, 0.5 * grv)
    L.data["kerfs"] = [(float(p[0]), float(p[1]), float(d[0]), float(d[1]), ln) for p, d, ln in kerfs]
    # щепки: тонкие лучины вдоль волокна у боковых краёв окна
    spl = []
    for side in (-1, 1):
        for j in range(2):
            m = (L.hole.y > 0.17 + 0.05 * j) & (np.sign(L.hole.th) == side)
            if m.sum() == 0:
                continue
            i = np.where(m)[0][len(np.where(m)[0]) // 2]
            spl.append((L.hole.th[i] + side * 1.3, L.hole.y[i] + rng.uniform(-0.01, 0.01), rng.uniform(0.012, 0.018)))
    for (pt, py, ln) in spl:
        dx = (TH - pt) * D2R * r
        dy = Y - py
        tt = (dy + ln / 2) / ln
        on = (tt > 0) & (tt < 1)
        wdt_ = 0.001 * (1 - np.clip(tt, 0, 1) ** 2)
        prof = (1 - smooth(np.abs(dx) / (wdt_ + 1e-6))) * on
        h += 0.00055 * prof * (0.4 + 0.6 * np.clip(tt, 0, 1))
        R = np.maximum(R, prof)
        ids = np.where(prof > 0.3, IDS["fresh"], ids)
    L.data["splinters"] = spl
    # (14) молотковые промахи у гвоздей вкладыша — полумесяцы
    for (nt, ny, miss) in L.data["nails_liner"]:
        if not miss:
            continue
        dx = (TH - nt) * D2R * r
        dy = Y - ny
        rho = np.sqrt((dx - 0.0045) ** 2 + dy ** 2)
        moon = np.clip(1 - (rho / 0.0042) ** 2, 0, 1) * (np.sqrt(dx ** 2 + dy ** 2) > 0.0032)
        h += -0.0003 * moon
        G = np.maximum(G, 0.4 * moon)
    # источники ржавчины на дереве: под обручами, у гвоздей и заклёпок
    for (y0, y1) in (L.hoop_up, L.hoop_lo):
        B = np.maximum(B, np.exp(-((Y - y0) / 0.0018) ** 2) * 0.5)
        B = np.maximum(B, np.exp(-((Y - y1) / 0.0018) ** 2) * 0.35)
    for (nt, ny, _) in L.data["nails_liner"]:
        rho = np.sqrt(((TH - nt) * D2R * r) ** 2 + (Y - ny) ** 2)
        B = np.maximum(B, np.exp(-(rho / 0.004) ** 2))
    fc = lin(HEX["fresh"])[None] * (0.92 + 0.12 * (1 - g))[..., None]
    col = col * (1 - fresh_w[..., None]) + fc * fresh_w[..., None]
    col = np.where(ids[..., None] == IDS["fresh"], fc, col)
    col = np.where(ids[..., None] == IDS["lead"], lin(HEX["lead"])[None] + 0 * col, col)
    msk = np.stack([np.clip(R, 0, 1), np.clip(G, 0, 1), np.clip(B, 0, 1)], -1)
    return h, col, msk, ids, hd


def build_wall(L, F, rng, step=0.00055):
    y0, y1 = 0.1396, 0.4030
    nth = int(round(2 * math.pi * 0.142 / step))
    ny = int(round((y1 - y0) / step)) + 1
    th = np.linspace(-180, 180, nth, endpoint=False)
    ys = np.linspace(y0, y1, ny)
    TH, Y = np.meshgrid(th, ys, indexing="ij")
    h, col, msk, ids, hd = wall_relief(L, F, TH, Y, rng)
    P = F.point(TH, Y, h)
    keep_v = hd > -0.003
    keep = keep_v[:-0 or None]
    kq = keep_v & np.roll(keep_v, -1, 0)
    kq = kq[:, :-1] & kq[:, 1:]
    faces = grid_faces(nth, ny, closed_u=True, keep=kq)
    ob = mesh_np("hp_wall", P.reshape(-1, 3), faces, col.reshape(-1, 3), ids.ravel(), msk.reshape(-1, 3))
    print("wall:", nth, "x", ny, "verts, faces", len(faces), flush=True)
    return ob


# ================================================================ hoops
def build_hoop(L, F, rng, y0, y1, name, th_cut=None, joint=None, step=0.0005):
    """Кованый обруч поверх стенки: толщина 1.6 мм, скруглённые кромки, грани ковки, вмятины, раковины."""
    r_mid = float(F.r(0.0, (y0 + y1) / 2))
    if th_cut is None:
        th0, th1, closed = -180.0, 180.0, True
    else:   # обруч идёт от правого конца окна вокруг затылка к левому
        th0, th1, closed = th_cut[1], th_cut[0] + 360.0, False
    nth = int(round((th1 - th0) * D2R * r_mid / step))
    nv = int(round((y1 - y0) / 0.00035)) + 1
    th = np.linspace(th0, th1, nth, endpoint=not closed)
    vv = np.linspace(0, 1, nv)
    TH, V = np.meshgrid(th, vv, indexing="ij")
    Y = y0 + (y1 - y0) * V
    THw = (TH + 180) % 360 - 180
    W = (y1 - y0)
    de = np.minimum(V, 1 - V) * W
    T = 0.0016
    t = T * np.sqrt(smooth(de / 0.0009))
    arc = (TH - th0) * D2R * r_mid
    # нахлёст (19)
    R = np.zeros_like(t)
    G = np.zeros_like(t)
    if joint is not None:
        jt, jl = joint
        a = ((TH - jt) * D2R * r_mid)
        on = smooth(a / 0.0006 + 0.5) * (1 - smooth((a - jl) / 0.0005 + 0.5))
        t = t + 0.0014 * on * np.sqrt(smooth(de / 0.0009))
        R = np.maximum(R, np.exp(-((a - jl) / 0.0007) ** 2) * 0.8)   # торец верхнего слоя затёрт
    # грани ковки (21): гребни |sin| с шагом 9–14 мм
    face_ = 0.00012 * np.abs(np.sin(np.pi * arc / 0.0115 + 0.6 * np.sin(arc / 0.031) + 1.3 * V))
    t = t - face_
    # вмятины (22)
    for _ in range(4):
        a0 = rng.uniform(0.02, (th1 - th0) * D2R * r_mid - 0.02)
        vr = rng.uniform(0.003, 0.0075)
        dp = rng.uniform(0.0003, 0.0005)
        rho = np.sqrt((arc - a0) ** 2 + ((V - rng.uniform(0.3, 0.7)) * W) ** 2)
        t = t - dp * np.clip(1 - (rho / vr) ** 2, 0, 1) ** 2
    # раковины (23): два масштаба, гнёздами, гуще к нижней кромке
    nests = [(rng.uniform(0, arc.max()), rng.uniform(0.0, 0.6)) for _ in range(14)]
    pits = []
    for (na, nv_) in nests:
        for _ in range(int(rng.integers(6, 18))):
            u = rng.random()
            pr = 0.0008 * (1 - u) ** (-0.55)       # степенной закон: много мелких
            pr = min(pr, 0.003)
            pits.append((na + rng.normal(0, 0.006), np.clip(nv_ + rng.normal(0, 0.18), 0.05, 0.95), pr))
    for _ in range(60):
        pits.append((rng.uniform(0, arc.max()), rng.uniform(0.05, 0.95) ** 1.6, 0.0008 + rng.random() * 0.0006))
    da = arc[1, 0] - arc[0, 0]
    for (pa, pv, pr) in pits:
        i0 = int((pa - pr * 1.3) / da)
        i1 = int((pa + pr * 1.3) / da) + 2
        if i1 < 0 or i0 >= nth:
            continue
        sl = slice(max(i0, 0), min(i1, nth))
        rho = np.sqrt((arc[sl] - pa) ** 2 + ((V[sl] - pv) * W) ** 2)
        cup = np.clip(1 - (rho / pr) ** 2, 0, 1)
        dep = 0.00012 + 0.11 * pr
        t[sl] -= dep * cup ** 1.2
        G[sl] = np.maximum(G[sl], smooth(cup * 2))
    # затёртая верхняя кромка (24)
    R = np.maximum(R, smooth((V - 0.8) / 0.2) * 0.7 * (1 - G))
    R = np.maximum(R, smooth((0.12 - V) / 0.12) * 0.35 * (1 - G))
    # концы перепиленного обруча (18): стёсаны, светлые
    if th_cut is not None:
        e = np.minimum(arc, arc.max() - arc)
        t = t * smooth(e / 0.0012) ** 0.5
        R = np.maximum(R, 1 - smooth(e / 0.004))
    t = np.maximum(t, 0.00005)
    P = F.point(THw, Y, t + 0.0002)
    nb = np.stack([R, G, np.full_like(R, 0.3)], -1)
    col = np.tile(lin(HEX["iron"]), TH.shape + (1,)) * (1 - 0.25 * G)[..., None]
    faces = grid_faces(nth, nv, closed_u=closed)
    ob = mesh_np(name, P.reshape(-1, 3), faces, col.reshape(-1, 3), "iron", nb.reshape(-1, 3))
    # бока полосы (толщина) — короткие юбки к стенке, чтобы луч не уходил в щель под обручем
    return ob


def wall_frame(F, th, y):
    p = Vector(F.point(th, y, 0.0).tolist())
    n = Vector((math.sin(th * D2R), 0, math.cos(th * D2R)))
    return p, n


def hoop_parts(L, F, rng):
    obs = []
    obs.append(build_hoop(L, F, rng, *L.hoop_up, "hp_hoop_up", joint=(L.joint_th, L.joint_len)))
    obs.append(build_hoop(L, F, rng, *L.hoop_lo, "hp_hoop_lo", th_cut=L.hoop_lo_cut))
    rivets = []
    r_up = float(F.r(L.joint_th, sum(L.hoop_up) / 2))
    jl = L.joint_len / r_up / D2R
    ym = sum(L.hoop_up) / 2
    for th_, tilt in ((L.joint_th + jl * 0.25, None), (L.joint_th + jl * 0.75, None),
                      (-150.0, None), (-20.0, (0.25, 0.1, 0)), (40.0, None), (110.0, None)):
        rivets.append((th_, ym, 0.0030 + (0.0014 if L.joint_th < th_ < L.joint_th + jl else 0.0), tilt))
    ylm = sum(L.hoop_lo) / 2
    for th_ in (-140.0, 160.0, 75.0 + 30.0):
        rivets.append((th_, ylm, 0.0030, None))
    for i, (th_, y_, lift, tilt) in enumerate(rivets):
        p, n = wall_frame(F, th_, y_)
        obs.append(dome(p + n * (lift - 0.0003), n, 0.0035, 0.0018, f"hp_rivet{i}", tilt=tilt))
    # гвозди в концах нижнего обруча (18)
    r_lo = float(F.r(0.0, ylm))
    ends = [L.hoop_lo_cut[0] - 0.006 / r_lo / D2R, L.hoop_lo_cut[1] + 0.006 / r_lo / D2R]
    for i, th_ in enumerate(ends):
        p, n = wall_frame(F, th_, ylm)
        obs.append(forged_nail(p + n * 0.0017, n, 0.0034, f"hp_hoopnail{i}", rng))
    L.data["rivets"] = [(r[0], r[1]) for r in rivets] + [(e, ylm) for e in ends]
    return obs


# ================================================================ nails, leaf, resin
def nail_layout(L, rng):
    ny = 0.257
    nails = []
    for th_ in np.linspace(-160, 160, 13):
        th_ = th_ + rng.uniform(-4, 4)
        if abs(th_) < 55 or 38 < th_ < 72:
            continue
        k, s = L.stave_of(np.array([th_]))
        if min(s[0], 1 - s[0]) < 0.22:
            th_ += 4.0 * (1 if s[0] < 0.5 else -1)
        nails.append((float(th_), ny + rng.uniform(-0.004, 0.004), bool(rng.random() < 0.3)))
    L.data["nails_liner"] = nails


def nail_parts(L, F, rng):
    obs = []
    bent = set(rng.choice(len(L.data["nails_liner"]), 2, replace=False).tolist())
    for i, (th_, y_, _) in enumerate(L.data["nails_liner"]):
        p, n = wall_frame(F, th_, y_)
        if i in bent:   # загнутый гвоздь: стержень вбит набок, шляпка у дерева
            d = Vector((math.cos(th_ * D2R), 0.35, -math.sin(th_ * D2R))).normalized()
            pts = [p + n * 0.0007 + d * (0.0015 * j) for j in range(9)]
            obs.append(tube(pts, 0.0009, f"hp_bent{i}", "nail", lin(HEX["iron"]), seg=8, strands=4, groove=0.15, twist=3))
            obs.append(forged_nail(pts[-1] + n * 0.0003, n, 0.0030, f"hp_nail{i}", rng, flat=0.45))
        else:
            obs.append(forged_nail(p, n, 0.0034, f"hp_nail{i}", rng))
    # гвозди сетки (33) у четырёх углов окна, проволока вокруг них
    hole = L.hole
    pts_ = []
    for (side, yy) in ((-1, 0.283), (1, 0.283), (-1, 0.182), (1, 0.182)):
        th_ = 30.0 * side
        for _ in range(80):
            d, _s = hole.query(np.array([th_]), np.array([yy]))
            if d[0] > 0.007:
                break
            th_ += side * 0.5
        pts_.append((th_, yy))
        p, n = wall_frame(F, th_, yy)
        obs.append(forged_nail(p, n, 0.0030, f"hp_meshnail{len(pts_)}", rng))
        # 2.5 витка проволоки Ø 2 мм вокруг гвоздя, конец уходит к сетке
        t1 = Vector((math.cos(th_ * D2R), 0, -math.sin(th_ * D2R)))
        t2 = Vector((0, 1, 0))
        wp = []
        for j in range(46):
            a = j / 18 * 2 * math.pi
            rr = 0.0042 + 0.0006 * j / 46
            wp.append(p + n * (0.0011 + 0.00015 * math.sin(a * 3)) + (t1 * math.cos(a) + t2 * math.sin(a)) * rr)
        tail = (t1 * (-side)).normalized()
        for j in range(1, 8):
            wp.append(wp[-1] + tail * 0.0016 + n * 0.00005)
        obs.append(tube(wp, 0.001, f"hp_meshwire{len(pts_)}", "wire", lin(HEX["wire"]), seg=8, strands=2, groove=0.2, twist=1.5))
    L.data["mesh_nails"] = pts_
    return obs


def leaf_part(L, F, rng, length=0.056):
    """Берёзовый лист (50): двоякопильчатый край, средняя жилка валиком, 7 пар боковых бороздками, края загнуты;
    лежит по поверхности клёпок (перекрывает щель), черешок под нижней кромкой верхнего обруча."""
    ct, cy = L.leaf
    k, s = L.stave_of(np.array([ct]))
    nu, nv = 170, 70
    u = np.linspace(0, 1, nu)            # 0 — основание (у черешка, вверху), 1 — кончик (внизу)
    v = np.linspace(-1, 1, nv)
    U, Vv = np.meshgrid(u, v, indexing="ij")
    half_w = 0.5 * length * 0.70 * np.sin(np.pi * np.clip(U, 0, 1) ** 0.72) ** 0.85 * (1 - 0.18 * U)
    # двоякопильчатый край: зубцы 2.5 мм и 1.2 мм
    sarc = U * length
    teeth = 0.0011 * (0.5 + 0.5 * np.sin(2 * np.pi * sarc / 0.0045)) + 0.0005 * (0.5 + 0.5 * np.sin(2 * np.pi * sarc / 0.0019))
    hw = np.maximum(half_w - teeth * (U > 0.08) * (U < 0.96), 0.0002)
    a = -U * length + length * 0.5      # вдоль: вверх к черешку положительно
    b = Vv * hw                          # поперёк
    # жилки
    mid = np.exp(-(b / 0.0008) ** 2) * (U < 0.95)
    vein = np.zeros_like(U)
    for i in range(7):
        u0 = 0.12 + i * 0.11
        # линия из средней жилки к краю под ~40° к кончику
        bb = np.abs(b)
        aa_line = (u0 + bb / length * 1.1)
        d = np.abs(U - aa_line) * length * 0.75
        vein = np.maximum(vein, np.exp(-(d / 0.00045) ** 2) * (bb < hw * 0.92))
    curl = 0.0011 * np.abs(Vv) ** 3
    hgt = 0.00045 + curl + 0.0006 * mid - 0.00025 * vein + 0.0002 * (NN.vnoise(np.stack([U * 9, Vv * 4, U * 0 + 3], -1), 7) - 0.5)
    TH = ct + b / float(F.r(ct, cy)) / D2R
    Y = cy + a
    base = F.r(TH, Y) + L.off[k[0]] + L.tilt[k[0]] * (Y - 0.27) + 0.00015
    th_r = TH * D2R
    zc = axis_z(Y)
    rr = base + hgt
    P = np.stack([rr * np.sin(th_r), Y, zc + rr * np.cos(th_r)], -1)
    col = np.empty(U.shape + (3,))
    lc, vc, ec = lin(HEX["leaf"]), lin(HEX["leaf_vein"]), lin(HEX["leaf_edge"])
    tv = np.clip(0.8 * mid + 0.7 * vein, 0, 1)
    te = smooth((np.abs(Vv) - 0.82) / 0.18) * 0.6 + 0.25 * (NN.vnoise(np.stack([U * 6, Vv * 3, U * 0 + 9], -1), 3) > 0.7)
    for c in range(3):
        col[..., c] = lc[c] * (1 - tv) + vc[c] * tv
        col[..., c] = col[..., c] * (1 - te) + ec[c] * te
    faces = grid_faces(nu, nv)
    ob = mesh_np("hp_leaf", P.reshape(-1, 3), faces, col.reshape(-1, 3), "leaf",
                 np.stack([0 * U, 0.3 * vein, 0 * U], -1).reshape(-1, 3))
    flip_if_inward(ob, lambda p: Vector((p.x, 0, p.z - float(axis_z(p.y)))))
    # черешок к нижней кромке верхнего обруча
    p0, n0 = wall_frame(F, ct, cy + length * 0.5)
    pts = [p0 + n0 * 0.0009 + Vector((0, 0.0015 * j, 0)) for j in range(9)]
    st = tube(pts, 0.0007, "hp_leaf_stalk", "leaf", lin(HEX["leaf_vein"]), seg=8, strands=1, groove=0.05)
    L.data["leaf_len"] = length
    return [ob, st]


def resin_part(L, F):
    kt, ky, kr, _ = L.knots[0]
    p, n = wall_frame(F, kt + 0.6, ky - kr * 1.2)
    ob = dome(p, n, 0.0024, 0.0014, "hp_resin", ident="resin", col=lin(HEX["resin"]), msk_top=0.0)
    # вытянуть каплю вниз
    for v in ob.data.vertices:
        d = v.co - p
        if d.y < 0:
            v.co.y = p.y + d.y * 1.5
    ob.data.update()
    return ob


# ================================================================ top (остров 3)
def height_field(bvh, xs, zs, y_from, down=True):
    H = np.full((len(xs), len(zs)), np.nan)
    d = Vector((0, -1 if down else 1, 0))
    for i, x in enumerate(xs):
        for j, z in enumerate(zs):
            hit = bvh.ray_cast(Vector((x, y_from, z)), d, 0.3)
            if hit[0] is not None:
                H[i, j] = hit[0].y
    return H


def blur2(a, s):
    k = np.exp(-0.5 * (np.arange(-3 * s, 3 * s + 1) / s) ** 2)
    k /= k.sum()
    ok = np.isfinite(a)
    v = np.where(ok, a, 0.0)
    w = ok.astype(float)
    for ax in (0, 1):
        v = np.apply_along_axis(lambda r: np.convolve(r, k, "same"), ax, v)
        w = np.apply_along_axis(lambda r: np.convolve(r, k, "same"), ax, w)
    return np.where(ok, v / np.maximum(w, 1e-9), np.nan)


def build_top(L, low, rng, step=0.0005):
    """Макушка = дно шайки: утор из торцов клёпок (34, 35), паз, днище из трёх досок (36), шканты (37),
    жестяная латка на трещине (38), вмятина и скол (39)."""
    zc = 0.0128
    R = 0.1245
    xs = np.arange(-R, R + 1e-9, step)
    zs = np.arange(zc - R, zc + R + 1e-9, step)
    H = height_field(bvh_of(low, {3}), xs, zs, 0.46)
    Hs = blur2(H, 3)
    X, Z = np.meshgrid(xs, zs, indexing="ij")
    gx = np.gradient(np.nan_to_num(Hs, nan=0.39), step, axis=0)
    gz = np.gradient(np.nan_to_num(Hs, nan=0.39), step, axis=1)
    nrm = np.stack([-gx, np.ones_like(gx), -gz], -1)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    zr = Z - zc
    rho = np.sqrt(X ** 2 + zr ** 2)
    TH = np.degrees(np.arctan2(X, zr))
    h = np.zeros(X.shape)
    G = np.zeros(X.shape)
    Rm = np.zeros(X.shape)
    ids = np.full(X.shape, IDS["wood"])
    col = np.tile(lin(HEX["wood"]), X.shape + (1,))
    rin = 0.1005
    chime = rho > rin
    # (34) торцы клёпок: кольца вокруг сердцевины за пределами ведра
    k, s = L.stave_of(TH)
    de = np.minimum(s, 1 - s) * (L.b[k + 1] - L.b[k]) * D2R * rho
    pr = rng.uniform(0.02, 0.09, L.ns)
    pt = rng.uniform(-0.3, 0.3, L.ns)
    pitch = rng.uniform(0.0026, 0.0038, L.ns)
    cth = ((L.b[k] + L.b[k + 1]) / 2 + pt[k] * (L.b[k + 1] - L.b[k])) * D2R
    px_ = (0.124 + pr[k]) * np.sin(cth)
    pz_ = (0.124 + pr[k]) * np.cos(cth)
    dpith = np.sqrt((X - px_) ** 2 + (zr - pz_) ** 2)
    ph = dpith / pitch[k] + 0.25 * (NN.vnoise(np.stack([X * 300, zr * 300, k * 3.0 + 0 * X], -1), 4) - 0.5)
    ring = (0.5 + 0.5 * np.cos(2 * np.pi * ph)) ** 3
    h += chime * (-0.0004 * ring)
    ec, rc = lin(HEX["wood_end"]), lin(HEX["end_ring"])
    for c in range(3):
        col[..., c] = np.where(chime, ec[c] * (1 - 0.55 * ring) + rc[c] * 0.55 * ring, col[..., c])
    ids = np.where(chime, IDS["endgrain"], ids)
    # стыки торцов
    jt = 1 - smooth(de / 0.0011)
    h += chime * (-0.0010 * jt)
    G = np.maximum(G, chime * jt)
    # трещинки по торцам (3 клёпки)
    for kk in rng.choice(L.ns, 4, replace=False):
        tc = (L.b[kk] + L.b[kk + 1]) / 2 + rng.uniform(-4, 4)
        dx = np.abs((TH - tc) * D2R * rho) + 0.0006 * np.sin(rho / 0.002)
        cr = (1 - smooth(dx / 0.0007)) * chime * (rho < 0.121)
        h += -0.0013 * cr
        G = np.maximum(G, cr)
    # (35) фаска утора внутрь
    ch = smooth((rin + 0.003 - rho) / 0.003) * chime
    h += -0.0011 * ch
    # затёртая внешняя кромка
    Rm = np.maximum(Rm, smooth((rho - 0.118) / 0.004) * 0.6 * chime)
    # паз между утором и днищем
    groove = (1 - smooth(np.abs(rho - (rin - 0.0008)) / 0.0011))
    h += -0.0016 * groove
    G = np.maximum(G, groove)
    # (36) днище: три доски поперёк (стыки вдоль x)
    bot = rho < rin - 0.0008
    joints = (-0.033, 0.031)
    bidx = np.digitize(zr, joints)
    boff = np.array([0.0003, -0.0002, 0.00025])
    bph = rng.uniform(0, 6.28, 3)
    bpi = np.array([0.0052, 0.0046, 0.0058])
    dj = np.min(np.stack([np.abs(zr - j) for j in joints]), 0)
    jg = 1 - smooth(dj / 0.0012)
    phase = (zr + 0.0015 * np.sin(X / 0.025 + bph[bidx]) + 0.001 * (NN.fbm(np.stack([X * 30, bidx * 2.0 + 0 * X, X * 0], -1), 3, 9) - 0.5)) / bpi[bidx]
    g = (0.5 + 0.5 * np.cos(2 * np.pi * phase)) ** 4
    g = g * (0.3 + 0.95 * NN.vnoise(np.stack([np.floor(phase + 0.5) * 1.37, bidx * 5.3 + 0 * X, X * 6.0], -1), 22))
    h += bot * (boff[bidx] - 0.00034 * g - 0.0011 * jg)
    G = np.maximum(G, bot * jg)
    wc, lc = lin(HEX["wood"]), lin(HEX["wood_late"])
    for c in range(3):
        col[..., c] = np.where(bot, wc[c] * (1 - 0.55 * g) + lc[c] * 0.55 * g, col[..., c])
    # трещина средней доски под латкой
    crx = np.abs(zr - (0.004 + 0.0012 * np.sin(X / 0.009)))
    crk = (1 - smooth(crx / 0.0008)) * bot * (np.abs(X) < 0.075)
    h += -0.0014 * crk
    G = np.maximum(G, crk)
    # (37) шканты у края — на стыках досок
    dowels = [(-0.078, joints[0]), (0.081, joints[1])]
    for (dxx, dzz) in dowels:
        dd = np.sqrt((X - dxx) ** 2 + (zr - dzz) ** 2)
        inn = 1 - smooth((dd - 0.0028) / 0.0005)
        rr = (0.5 + 0.5 * np.cos(2 * np.pi * dd / 0.0011)) ** 2
        h = h * (1 - inn) + inn * (0.0002 - 0.00025 * rr + boff[1])
        for c in range(3):
            col[..., c] = col[..., c] * (1 - inn) + inn * (ec[c] * (1 - 0.5 * rr) + rc[c] * 0.5 * rr)
        ids = np.where(inn > 0.5, IDS["endgrain"], ids)
    # (39) вмятина и скол утора
    dd = np.sqrt((X + 0.05) ** 2 + (zr - 0.058) ** 2)
    h += -0.0005 * np.clip(1 - (dd / 0.012) ** 2, 0, 1) ** 2
    chip_t = 150.0
    da = np.abs(((TH - chip_t + 180) % 360) - 180) * D2R * rho
    chip = smooth((0.0075 - da) / 0.003) * smooth((rho - 0.112) / 0.004)
    h += -0.0018 * chip
    Rm = np.maximum(Rm, chip * 0.9)
    # (38) жестяная латка 50×35 мм на трещине
    an = 8 * D2R
    ux = (X - 0.012) * math.cos(an) + (zr - 0.004) * math.sin(an)
    uz = -(X - 0.012) * math.sin(an) + (zr - 0.004) * math.cos(an)
    ex = np.maximum(np.abs(ux) - 0.025, 0)
    ez = np.maximum(np.abs(uz) - 0.0175, 0)
    edge_d = np.sqrt(ex ** 2 + ez ** 2) - 0.0
    inside = np.minimum(0.025 - np.abs(ux), 0.0175 - np.abs(uz))
    patch = smooth(inside / 0.0006 + 0.5)
    dent = 0.00018 * (NN.fbm(np.stack([ux * 120, uz * 120, 0 * ux + 2], -1), 3, 31) - 0.5)
    h = h * (1 - patch) + patch * (0.0006 + boff[1] + dent + 0.0003 * smooth(inside / 0.003))
    ids = np.where(patch > 0.5, IDS["tin"], ids)
    tc_ = lin(HEX["tin"])
    for c in range(3):
        col[..., c] = col[..., c] * (1 - patch) + patch * tc_[c]
    Rm = np.maximum(Rm, patch * (1 - smooth(inside / 0.0015)) * 0.8)
    G = np.maximum(G, (1 - patch) * np.exp(-(np.maximum(-inside, 0) / 0.0008) ** 2) * 0.6 * (inside < 0))
    nails = []
    for sx in (-1, 1):
        for sz in (-1, 1):
            nx_ = 0.012 + (sx * 0.020) * math.cos(an) - (sz * 0.0125) * math.sin(an)
            nz_ = 0.004 + (sx * 0.020) * math.sin(an) + (sz * 0.0125) * math.cos(an)
            nails.append((nx_, nz_))
    for (nx_, nz_) in nails:
        dd = np.sqrt((X - nx_) ** 2 + (zr - nz_) ** 2)
        hd_ = np.clip(1 - (dd / 0.0017) ** 2, 0, 1)
        h += 0.0008 * np.sqrt(hd_)
        ids = np.where(hd_ > 0.05, IDS["nail"], ids)
        for c in range(3):
            col[..., c] = np.where(hd_ > 0.05, lin(HEX["iron"])[c], col[..., c])
        Rm = np.maximum(Rm, hd_ * 0.7)
    L.data["top_patch"] = [0.012, 0.004, 8.0]
    L.data["top_dowels"] = dowels
    ok = np.isfinite(Hs)
    P = np.stack([X, Hs, Z], -1) + nrm * h[..., None]
    nx_, nz_ = X.shape
    kq = ok[:-1, :-1] & ok[1:, :-1] & ok[1:, 1:] & ok[:-1, 1:]
    P = np.nan_to_num(P, nan=0.39)
    faces = grid_faces(nx_, nz_, keep=kq)
    msk = np.stack([Rm, G, np.zeros_like(G)], -1)
    ob = mesh_np("hp_top", P.reshape(-1, 3), faces, col.reshape(-1, 3), ids.ravel(), msk.reshape(-1, 3))
    flip_if_inward(ob, lambda p: Vector((0, 1, 0)))
    print("top faces", len(faces), flush=True)
    return ob


# ================================================================ inner (острова 7, 37)
def build_inner(L, low, Fin, rng, step=0.0008):
    """Жестяной вкладыш из синего ведра (45–49): шов внахлёст с гвоздями, шишки, загнутый нижний край,
    полоса мокрого дерева у края, зубчатый край у окна."""
    y0, y1 = 0.1396, 0.3850
    nth = int(round(2 * math.pi * 0.135 / step))
    ny = int(round((y1 - y0) / step)) + 1
    TH, Y = np.meshgrid(np.linspace(-180, 180, nth, endpoint=False), np.linspace(y0, y1, ny), indexing="ij")
    r = Fin.r(TH, Y)
    h = np.zeros(TH.shape)        # внутрь (к оси) положительно
    G = np.zeros(TH.shape)
    Rm = np.zeros(TH.shape)
    ids = np.full(TH.shape, IDS["tin"])
    col = np.tile(lin(HEX["tin"]), TH.shape + (1,))
    liner_lo = 0.152
    on = smooth((Y - liner_lo) / 0.0006)
    # нижний край вкладыша загнут валиком
    bead = np.exp(-((Y - (liner_lo + 0.0012)) / 0.0011) ** 2)
    h += on * 0.0005 + 0.0005 * bead
    Rm = np.maximum(Rm, 0.6 * bead)
    # (46) шов внахлёст сзади: второй слой от 166° до 180°
    tw = ((TH - 166.0 + 180) % 360) - 180
    lap = smooth(tw / 0.15 + 0.5) * smooth((180.0 - 166.0 - tw) / 0.15 + 0.5)
    h += 0.0005 * lap * on
    Rm = np.maximum(Rm, np.exp(-(tw * D2R * r / 0.0008) ** 2) * 0.7 * on)
    # (47) шишки от ударов и дроби (вмятины с той стороны)
    bumps = [(-21.0, 0.313, 0.018, 0.0011), (-58, 0.298, 0.016, 0.0008), (40, 0.232, 0.012, 0.0007),
             (120, 0.27, 0.02, 0.0006)] + [(t_, y_, 0.004, 0.0005) for (t_, y_) in L.data["shots"]]
    for (bt, by, br, bd) in bumps:
        rho = np.sqrt(((TH - bt) * D2R * r) ** 2 + (Y - by) ** 2)
        h += bd * np.clip(1 - (rho / br) ** 2, 0, 1) ** 2 * on
    # жесть мятая (крупно — 8 px/см)
    h += 0.00025 * (NN.fbm(np.stack([TH * 0.15, Y * 60, 0 * Y + 4], -1), 3, 41) - 0.5) * on
    # (48) ниже вкладыша — мокрое дерево изнутри, щели клёпок
    k, s = L.stave_of(TH)
    de = np.minimum(s, 1 - s) * (L.b[k + 1] - L.b[k]) * D2R * r
    wood = 1 - on
    jg = 1 - smooth(de / 0.0015)
    h += wood * (-0.0009 * jg)
    ids = np.where(on < 0.5, IDS["wood"], ids)
    wc = lin(HEX["wood_late"])
    for c in range(3):
        col[..., c] = col[..., c] * on + wood * wc[c]
    # (30) у окна: жесть обрезана зубцами, загнута, дальше — свежий срез дерева
    hd, hs = L.hole.query(TH, Y)
    tooth = 0.0045 + 0.0035 * np.abs(((hs / 0.008) % 1.0) * 2 - 1)
    tin_on = smooth((hd - tooth) / 0.0005)
    lip = np.exp(-((hd - tooth) / 0.0012) ** 2) * (hd > tooth - 0.001)
    h = h * tin_on + 0.0008 * lip * tin_on
    Rm = np.maximum(Rm, lip * 0.9)
    fresh = (1 - tin_on) * (hd > -0.003)
    ids = np.where((fresh > 0.5) & (on > 0.5), IDS["fresh"], ids)
    fc = lin(HEX["fresh"])
    for c in range(3):
        col[..., c] = col[..., c] * (1 - fresh) + fresh * fc[c] * 0.9
    G = np.maximum(G, jg * wood)
    P = Fin.point(TH, Y, -h)
    keep_v = hd > -0.003
    kq = keep_v & np.roll(keep_v, -1, 0)
    kq = kq[:, :-1] & kq[:, 1:]
    faces = grid_faces(nth, ny, closed_u=True, keep=kq)
    msk = np.stack([Rm, G, np.zeros_like(G)], -1)
    ob = mesh_np("hp_inner", P.reshape(-1, 3), faces, col.reshape(-1, 3), ids.ravel(), msk.reshape(-1, 3))
    flip_if_inward(ob, lambda p: Vector((-p.x, 0, -(p.z - float(axis_z(p.y))))))
    obs = [ob]
    # гвозди шва и нижнего края (шляпки внутрь)
    nl = [(173.0, y_) for y_ in np.linspace(0.19, 0.36, 6)]
    nl += [(t_, 0.162) for t_ in np.arange(-150, 151, 30) if abs(t_) > 45]
    nl += [(-42.0, 0.27), (40.0, 0.25)]
    for i, (t_, y_) in enumerate(nl):
        rr = float(Fin.r(t_, y_)) - 0.0005
        p = Vector((rr * math.sin(t_ * D2R), y_, float(axis_z(y_)) + rr * math.cos(t_ * D2R)))
        n = -Vector((math.sin(t_ * D2R), 0, math.cos(t_ * D2R)))
        obs.append(forged_nail(p, n, 0.0036, f"hp_innail{i}", rng))
    L.data["inner_nails"] = nl
    # (49) внутреннее дно — жестяной круг с вмятиной и гвоздями по краю (4 px/см — только крупное)
    zc = 0.0128
    xs = np.arange(-0.112, 0.1121, 0.001)
    zs = np.arange(zc - 0.112, zc + 0.1121, 0.001)
    Hb = height_field(bvh_of(low, {37}), xs, zs, 0.30, down=False)
    Hb = blur2(Hb, 2)
    X, Z = np.meshgrid(xs, zs, indexing="ij")
    hb = 0.0005 + 0.0016 * np.clip(1 - ((X + 0.02) ** 2 + (Z - zc - 0.01) ** 2) / 0.045 ** 2, 0, 1) ** 2
    rr = np.sqrt(X ** 2 + (Z - zc) ** 2)
    for a in np.arange(0, 360, 45):
        dd = np.sqrt((X - 0.09 * math.sin(a * D2R)) ** 2 + (Z - zc - 0.09 * math.cos(a * D2R)) ** 2)
        hb += 0.001 * np.sqrt(np.clip(1 - (dd / 0.0035) ** 2, 0, 1))
    ok = np.isfinite(Hb)
    Pb = np.stack([X, np.nan_to_num(Hb, nan=0.38) - hb, Z], -1)
    kq = ok[:-1, :-1] & ok[1:, :-1] & ok[1:, 1:] & ok[:-1, 1:]
    fb = grid_faces(*X.shape, keep=kq)
    ob2 = mesh_np("hp_inner_bottom", Pb.reshape(-1, 3), fb, np.tile(lin(HEX["tin"]), (X.size, 1)), "tin",
                  np.stack([0 * X, 0 * X, 0 * X], -1).reshape(-1, 3))
    flip_if_inward(ob2, lambda p: Vector((0, -1, 0)))
    obs.append(ob2)
    print("inner faces", len(faces), flush=True)
    return obs


# ================================================================ copies of low-poly faces
def copy_faces(low, islands, name, side=None):
    bm = bmesh.new()
    bm.from_mesh(low.data)
    bm.faces.ensure_lookup_table()
    isl = low["isl"]
    drop = [f for f in bm.faces if isl[f.index] not in islands or
            (side is not None and np.sign(f.calc_center_median().x) != side)]
    bmesh.ops.delete(bm, geom=drop, context="FACES")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def even_mesh(ob, max_edge):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    for _ in range(14):
        long_e = [e for e in bm.edges if e.calc_length() > max_edge]
        if not long_e:
            break
        bmesh.ops.subdivide_edges(bm, edges=long_e, cuts=1, use_grid_fill=False)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def displace_np(ob, fn):
    """fn(co (N,3), nrm (N,3)) -> (сдвиг вдоль нормали (N,), цвет (N,3), id (N,), msk (N,3))."""
    me = ob.data
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    nr = np.empty(n * 3, np.float32)
    me.vertices.foreach_get("co", co)
    me.vertices.foreach_get("normal", nr)
    co, nr = co.reshape(n, 3).astype(np.float64), nr.reshape(n, 3).astype(np.float64)
    d, cols, ids, msk = fn(co, nr)
    me.vertices.foreach_set("co", (co + nr * d[:, None]).astype(np.float32).ravel())
    me.update()
    for attr, arr in (("col", cols), ("msk", msk)):
        a = me.color_attributes.new(attr, "FLOAT_COLOR", "POINT")
        flat = np.ones((n, 4), np.float32)
        flat[:, :3] = arr
        a.data.foreach_set("color", flat.ravel())
    a = me.color_attributes.new("idc", "FLOAT_COLOR", "POINT")
    flat = np.ones((n, 4), np.float32)
    flat[:, 1:3] = 0
    flat[:, 0] = (ids * 16 + 8) / 255
    a.data.foreach_set("color", flat.ravel())
    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), bool))


def build_cut(L, low, F, Fin):
    """Торец окна (29): дерево поперёк волокна с бороздками пилы, щель, полоска жести вкладыша изнутри."""
    ob = copy_faces(low, {6}, "hp_cut")
    even_mesh(ob, 0.0006)

    def fn(co, nr):
        th = np.degrees(np.arctan2(co[:, 0], co[:, 2] - axis_z(co[:, 1])))
        rho = np.sqrt(co[:, 0] ** 2 + (co[:, 2] - axis_z(co[:, 1])) ** 2)
        ro, ri = F.r(th, co[:, 1]), Fin.r(th, co[:, 1])
        fr = np.clip((rho - ri) / np.maximum(ro - ri, 1e-4), 0, 1)
        _, s = L.hole.query(th, co[:, 1])
        tin = fr < 0.16
        gap = (fr >= 0.16) & (fr < 0.24)
        saw = 0.00022 * np.cos(2 * np.pi * s / 0.0024 + 0.6 * np.sin(s / 0.011))
        d = np.where(tin, 0.0001, np.where(gap, -0.0003, saw))
        col = np.where(tin[:, None], lin(HEX["tin"])[None], lin(HEX["fresh"])[None] * (0.9 + 0.15 * (saw[:, None] / 0.00022)))
        col = np.where(gap[:, None], lin(HEX["knot"])[None] * 0.5, col)
        ids = np.where(tin, IDS["tin"], IDS["fresh"])
        msk = np.stack([np.where(tin, 0.9, 0.6), gap * 1.0, 0 * fr], 1)
        return d, col, ids, msk
    displace_np(ob, fn)
    return ob


def build_ears(L, low, rng):
    """Ушки (41–44): дощечка с волокнами; в дырке — узел обрезанной верёвки, обрывок с распушённым концом.
    Обе копии в одних UV: строим у +x и отражаем в −x."""
    obs = []
    ear = copy_faces(low, {5, 9}, "hp_ear_p", side=1)
    even_mesh(ear, 0.0007)

    def fn(co, nr):
        ph = (co[:, 2] + 0.0007 * np.sin(co[:, 1] / 0.012)) / 0.0031
        g = (0.5 + 0.5 * np.cos(2 * np.pi * ph)) ** 4
        d = -0.00028 * g
        col = lin(HEX["wood"])[None] * (1 - 0.5 * g[:, None]) + lin(HEX["wood_late"])[None] * 0.5 * g[:, None]
        msk = np.stack([0 * g, 0.3 * g, 0 * g], 1)
        return d, col, np.full(len(g), IDS["wood"]), msk
    displace_np(ear, fn)
    obs.append(ear)
    riv = copy_faces(low, {8}, "hp_earnail_p", side=1)
    even_mesh(riv, 0.0007)

    def fr(co, nr):
        a = np.arctan2(co[:, 2] - 0.003, co[:, 1] - 0.1745)
        d = 0.00015 * np.abs(np.sin(2 * a))
        col = np.tile(lin(HEX["iron"]), (len(a), 1))
        return d, col, np.full(len(a), IDS["nail"]), np.stack([0.5 + 0 * a, 0 * a, 0.8 + 0 * a], 1)
    displace_np(riv, fr)
    obs.append(riv)
    # узел: петля вокруг дырки (центр 0.1508, 0.1325, 0.0009; нормаль +x), обрывок вверх по ушку
    c = Vector((0.1513, 0.1325, 0.0009))
    nx = Vector((1, 0, 0))
    up = Vector((0, 1, 0))
    fw = Vector((0, 0, 1))
    rr = 0.0025
    loop = []
    for j in range(40):
        a = 2 * math.pi * j / 39 * 1.15 - 0.3
        dip = 0.0026 * math.exp(-((a - 0.2) / 0.35) ** 2)     # уходит в дырку
        loop.append(c + nx * (rr + 0.0003 - dip) + (up * math.cos(a) + fw * math.sin(a)) * 0.0052)
    obs.append(tube(loop, rr, "hp_knot_p", "rope", lin(HEX["rope"]), seg=14, strands=3, groove=0.3, twist=1.0))
    tail = [c + nx * (rr + 0.0004) + up * (0.0048 + 0.0016 * j) + fw * (0.0012 * math.sin(j / 4)) for j in range(15)]
    obs.append(tube(tail, rr * 0.92, "hp_rope_p", "rope", lin(HEX["rope"]), seg=14, strands=3, groove=0.3, twist=1.0))
    # распушённый конец: 6 волокон Ø 1 мм веером
    end = tail[-1]
    for i in range(6):
        a = (i - 2.5) * 0.22
        dirv = (up * math.cos(a) + fw * math.sin(a)).normalized()
        pts = [end + dirv * (0.0013 * j) + nx * (rr * 0.6 - 0.0002 * j) + fw * (0.0004 * (i - 2.5)) for j in range(7)]
        obs.append(tube(pts, 0.0005, f"hp_fray_p{i}", "rope", lin(HEX["rope_dark"]), seg=6, strands=2, groove=0.2))
    # изнутри ушка верёвка проходит вниз от дырки
    inn = [c - nx * 0.0042 + up * (-0.001 * j) for j in range(8)]
    obs.append(tube(inn, rr * 0.9, "hp_rope_in_p", "rope", lin(HEX["rope"]), seg=12, strands=3, groove=0.3))
    # зеркальная копия для второго ушка
    mir = []
    for o in obs:
        o2 = o.copy()
        o2.data = o.data.copy()
        o2.name = o.name.replace("_p", "_m")
        bpy.context.scene.collection.objects.link(o2)
        me = o2.data
        n = len(me.vertices)
        co = np.empty(n * 3, np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(n, 3)
        co[:, 0] *= -1
        me.vertices.foreach_set("co", co.ravel())
        me.flip_normals()
        me.update()
        mir.append(o2)
    return obs + mir


def build_wires(L, low, rng, shared):
    """Сетка (31, 32): уникальные проволоки — свив двух жил, бугры цинка, раковины; общие узлы — гладкие."""
    obs = []
    uniq = [i for i in range(10, 46) if i not in shared and i != 37]
    ob = copy_faces(low, set(uniq), "hp_wires")
    even_mesh(ob, 0.0006)
    isl_of = {}
    # ось каждой проволоки — главная компонента её вершин (по острову)
    me = ob.data
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(n, 3).astype(np.float64)
    # куски — по связности
    bm = bmesh.new()
    bm.from_mesh(me)
    comp = np.full(n, -1)
    cid = 0
    bm.verts.ensure_lookup_table()
    for v in bm.verts:
        if comp[v.index] >= 0:
            continue
        stack = [v]
        comp[v.index] = cid
        while stack:
            u = stack.pop()
            for e in u.link_edges:
                w = e.other_vert(u)
                if comp[w.index] < 0:
                    comp[w.index] = cid
                    stack.append(w)
        cid += 1
    bm.free()
    axis = np.zeros((n, 3))
    cen = np.zeros((n, 3))
    for c_ in range(cid):
        m = comp == c_
        P = co[m]
        mu = P.mean(0)
        u, s_, vt = np.linalg.svd(P - mu, full_matrices=False)
        axis[m] = vt[0]
        cen[m] = mu

    def fn(co, nr):
        s = ((co - cen) * axis).sum(1)
        radial = (co - cen) - axis * s[:, None]
        b1 = np.cross(axis, np.array([0.0, 0.0, 1.0]))
        b1 /= np.linalg.norm(b1, axis=1, keepdims=True) + 1e-12
        b2 = np.cross(axis, b1)
        phi = np.arctan2((radial * b2).sum(1), (radial * b1).sum(1))
        tw = np.maximum(0, np.cos(2 * phi - 2 * np.pi * s / 0.0055)) ** 2
        zinc = NN.vnoise(co * 900, 51)
        pits = NN.vnoise(co * 1500, 52)
        pit = smooth((pits - 0.72) / 0.12)
        d = -0.00016 * tw + 0.0001 * smooth((zinc - 0.6) / 0.2) - 0.00012 * pit
        col = lin(HEX["wire"])[None] * (1 - 0.3 * tw[:, None]) * (1 - 0.0 * pit[:, None])
        col = col * (1 - smooth((zinc - 0.6) / 0.2)[:, None]) + lin(HEX["zinc"])[None] * smooth((zinc - 0.6) / 0.2)[:, None]
        msk = np.stack([0.3 * smooth((zinc - 0.6) / 0.2), np.maximum(pit, 0.5 * tw), 0 * s], 1)
        return d, col, np.full(len(s), IDS["wire"]), msk
    displace_np(ob, fn)
    obs.append(ob)
    sh = copy_faces(low, set(shared), "hp_wires_shared")
    even_mesh(sh, 0.0008)

    def fs(co, nr):
        n_ = len(co)
        return np.zeros(n_), np.tile(lin(HEX["wire"]) * 0.8, (n_, 1)), np.full(n_, IDS["wire"]), np.tile([0, 0.5, 0], (n_, 1))
    displace_np(sh, fs)
    obs.append(sh)
    return obs


# ================================================================ bake
def bake_material():
    m = bpy.data.materials.new("hp")
    m.use_nodes = True
    N, Ln = m.node_tree.nodes, m.node_tree.links
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL")
    bs = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    em = {}
    for key, layer in (("color", "col"), ("id", "idc"), ("msk", "msk")):
        vc = N.new("ShaderNodeVertexColor")
        vc.layer_name = layer
        e = N.new("ShaderNodeEmission")
        Ln.new(vc.outputs["Color"], e.inputs["Color"])
        em[key] = e
    geo = N.new("ShaderNodeNewGeometry")
    mp = N.new("ShaderNodeMapRange")
    mp.data_type = "FLOAT_VECTOR"
    mp.inputs[7].default_value = Vector(POS_LO.tolist())
    mp.inputs[8].default_value = Vector(POS_HI.tolist())
    Ln.new(geo.outputs["Position"], mp.inputs["Vector"])
    e = N.new("ShaderNodeEmission")
    Ln.new(mp.outputs["Vector"], e.inputs["Color"])
    em["pos"] = e
    return m, out, bs, em


def set_pass(mat, which):
    m, out, bs, em = mat
    Ln = m.node_tree.links
    for l in list(out.inputs["Surface"].links):
        Ln.remove(l)
    Ln.new((bs if which == "view" else em[which]).outputs[0], out.inputs["Surface"])


def setup_cycles(scene):
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            prefs.compute_device_type = kind
        except TypeError:
            continue
        prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type == kind]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == kind
            scene.cycles.device = "GPU"
            print("bake device:", kind, [d.name for d in gpus], flush=True)
            break
    else:
        scene.cycles.device = "CPU"
        print("bake device: CPU", flush=True)
    scene.cycles.use_denoising = False
    scene.view_settings.view_transform = "Standard"


def low_subset(low, islands, name):
    ob = low.copy()
    ob.data = low.data.copy()
    ob.name = name
    bpy.context.scene.collection.objects.link(ob)
    isl = low["isl"]
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if isl[f.index] not in islands], context="FACES")
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def island_raster(size):
    im = bpy.data.images.load(str(HERE / "uv" / "ids_4096.png"))
    im.colorspace_settings.name = "Non-Color"
    w = im.size[0]
    px = np.array(im.pixels[:], np.float32).reshape(w, w, 4)
    ids = np.round(px[..., 0] * 255).astype(np.int32) + np.round(px[..., 1] * 255).astype(np.int32) * 256
    bpy.data.images.remove(im)
    if size != w:
        k = w // size
        ids = ids[::k, ::k] if size < w else np.repeat(np.repeat(ids, size // w, 0), size // w, 1)
    return ids


def save_png(arr, name, size):
    im2 = bpy.data.images.new(name, size, size, alpha=False)
    im2.colorspace_settings.name = "Non-Color"
    buf = np.ones((size, size, 4), np.float32)
    buf[..., :3] = arr
    im2.pixels.foreach_set(buf.ravel())
    im2.filepath_raw = str(OUT / f"{name}.png")
    im2.file_format = "PNG"
    im2.save()
    bpy.data.images.remove(im2)


def merge_save(arr, name, size, filled, partial):
    """partial: заменить в уже запечённой карте только пиксели этих групп (допекание одной группы)."""
    p = OUT / f"{name}.png"
    if partial and p.exists():
        im = bpy.data.images.load(str(p))
        im.colorspace_settings.name = "Non-Color"
        old = np.empty(size * size * 4, np.float32)
        if tuple(im.size) == (size, size):
            im.pixels.foreach_get(old)
            old = old.reshape(size, size, 4)[..., :3]
            arr = np.where(filled[..., None], arr, old)
        bpy.data.images.remove(im)
    save_png(arr, name, size)


def bake(low, groups, size, passes, partial=False):
    """groups: [(имя, острова, [high-poly], extrusion)]. Каждая группа печётся отдельно (только свой high-poly)
    и кладётся по маске своих островов + 6 px наружу."""
    scene = bpy.context.scene
    setup_cycles(scene)
    mat = bake_material()
    allhp = [o for g in groups for o in g[2]]
    for o in allhp:
        o.data.materials.clear()
        o.data.materials.append(mat[0])
    if scene.world is None:
        scene.world = bpy.data.worlds.new("bake")
    lm = bpy.data.materials.new("bake_target")
    lm.use_nodes = True
    tex = lm.node_tree.nodes.new("ShaderNodeTexImage")
    lm.node_tree.nodes.active = tex
    lows = []
    for gname, isls, ghp, extr in groups:
        lg = low_subset(low, isls, f"low_{gname}")
        lg.hide_render = False
        lg.data.materials.clear()
        lg.data.materials.append(lm)
        for attr in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission",
                     "visible_volume_scatter", "visible_shadow"):
            setattr(lg, attr, False)
        lows.append(lg)
    low.hide_render = True
    bk = scene.render.bake
    bk.use_selected_to_active = True
    bk.use_cage = False
    bk.target = "IMAGE_TEXTURES"
    bk.normal_space = "TANGENT"
    bk.normal_r, bk.normal_g, bk.normal_b = "POS_X", "POS_Y", "POS_Z"   # OpenGL, как у оригинала
    OUT.mkdir(exist_ok=True)
    for name, kind, shader, samples, psize, aod in passes:
        rast = island_raster(psize)
        scene.cycles.samples = samples
        scene.cycles.filter_width = 0.01 if name in ("id", "pos", "msk") else 1.5
        if aod:
            scene.world.light_settings.distance = aod
        set_pass(mat, shader)
        result = np.zeros((psize, psize, 4), np.float32)
        if name == "normal":
            result[..., :3] = (0.5, 0.5, 1.0)
        elif name in ("ao", "aowide"):
            result[..., :3] = 1.0
        filled = np.zeros((psize, psize), bool)
        for (gname, isls, ghp, extr), lg in zip(groups, lows):
            bk.cage_extrusion = extr
            bk.max_ray_distance = extr * 2.2
            bk.margin_type = "ADJACENT_FACES" if name == "id" else "EXTEND"
            img = bpy.data.images.new(f"bk_{name}_{gname}", psize, psize, alpha=False, float_buffer=True)
            img.colorspace_settings.name = "Non-Color"
            tex.image = img
            bpy.ops.object.select_all(action="DESELECT")
            for o in ghp:
                o.select_set(True)
            lg.select_set(True)
            bpy.context.view_layer.objects.active = lg
            print(f"baking {name} {gname} ({psize}) ...", flush=True)
            bpy.ops.object.bake(type=kind, use_clear=True, margin=max(8, psize // 128))
            px = np.empty(psize * psize * 4, np.float32)
            img.pixels.foreach_get(px)
            px = px.reshape(psize, psize, 4)
            m = np.isin(rast, list(isls))
            g = m.copy()
            for _ in range(max(2, psize // 680)):
                g = g | np.roll(g, 1, 0) | np.roll(g, -1, 0) | np.roll(g, 1, 1) | np.roll(g, -1, 1)
            m = m | (g & (rast == 0) & ~filled)
            result[m] = px[m]
            filled |= m
            bpy.data.images.remove(img)
        if name == "pos":
            q = np.clip(result[..., :3], 0, 1) * 65535
            merge_save(np.floor(q / 256) / 255, "poshi", psize, filled, partial)
            merge_save((q % 256) / 255, "poslo", psize, filled, partial)
        else:
            arr = result[..., :3]
            if name == "color":
                arr = np.clip(arr, 0, 1) ** (1 / 2.2)
            merge_save(arr, name, psize, filled, partial)
        print("  ->", name, flush=True)


# ================================================================ view (high-poly check)
def look_at(eye, tgt, up=Vector((0, 1, 0))):
    """Матрица камеры (или солнца): смотрит из eye в tgt, верх кадра — мировой +y (y — вверх, как в OBJ)."""
    from mathutils import Matrix
    f = (tgt - eye).normalized()
    if abs(f.dot(up)) > 0.99:
        up = Vector((0, 0, -1))
    r = f.cross(up).normalized()
    u = r.cross(f)
    m = Matrix(((r.x, u.x, -f.x, eye.x), (r.y, u.y, -f.y, eye.y), (r.z, u.z, -f.z, eye.z), (0, 0, 0, 1)))
    return m


def look(hp, views, tag):
    scene = bpy.context.scene
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"
    m = bpy.data.materials.new("look")
    m.use_nodes = True
    N, Ln = m.node_tree.nodes, m.node_tree.links
    bs = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    vc = N.new("ShaderNodeVertexColor")
    vc.layer_name = "col"
    Ln.new(vc.outputs["Color"], bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = 0.55
    m.use_backface_culling = True
    for o in hp:
        o.data.materials.clear()
        o.data.materials.append(m)
    w = scene.world or bpy.data.worlds.new("w")
    scene.world = w
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.35, 0.37, 0.4, 1)
    bg.inputs["Strength"].default_value = 0.6
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.active_object
    sun.data.energy = 4.0
    sun.data.angle = 0.02
    sun.rotation_euler = (Vector((0.3, -0.6, -0.5))).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.object.camera_add()
    cam = bpy.context.active_object
    scene.camera = cam
    cam.data.clip_start = 0.002
    scene.render.resolution_x, scene.render.resolution_y = 1200, 900
    for name, eye, tgt, lens, sdir in views:
        cam.location = Vector(eye)
        cam.matrix_world = look_at(Vector(eye), Vector(tgt))
        cam.data.lens = lens
        sun.matrix_world = look_at(Vector((0, 0, 0)), Vector(sdir))
        scene.render.filepath = str(OUT / f"look_{tag}_{name}.png")
        bpy.ops.render.render(write_still=True)


LOOKS_WALL = [
    ("front", (0.0, 0.30, 0.75), (0, 0.27, 0), 50, (0.2, -0.5, -1.0)),
    ("q34", (0.50, 0.40, 0.50), (0, 0.27, 0), 50, (-0.6, -0.6, -0.8)),
    ("left", (-0.75, 0.30, 0.05), (0, 0.27, 0), 50, (0.8, -0.4, -0.4)),
    ("back", (0.0, 0.32, -0.75), (0, 0.27, 0), 50, (0.3, -0.4, 1.0)),
    ("hole", (0.05, 0.24, 0.40), (0.0, 0.22, 0.12), 60, (0.7, -0.3, -0.6)),
    ("leaf", (0.30, 0.30, 0.22), (0.11, 0.30, 0.08), 70, (-0.8, -0.2, -0.5)),
    ("joint", (-0.30, 0.34, 0.12), (-0.12, 0.34, 0.04), 70, (0.9, -0.2, -0.2)),
    ("shot", (-0.08, 0.32, 0.30), (-0.05, 0.31, 0.13), 85, (0.9, 0.1, -0.4)),
]


# ================================================================ main
LOOKS_REST = [
    ("top", (0.10, 0.75, 0.25), (0, 0.39, 0.012), 45, (0.3, -1.0, -0.4)),
    ("topclose", (0.04, 0.52, 0.10), (0.01, 0.39, 0.01), 60, (0.5, -1.0, -0.2)),
    ("inside", (0.0, -0.05, 0.25), (0.0, 0.30, -0.05), 40, (0.0, 1.0, -0.3)),
    ("ear", (0.30, 0.15, 0.05), (0.15, 0.15, 0.0), 80, (-0.9, -0.3, -0.3)),
    ("cut", (0.0, 0.23, 0.32), (0.0, 0.22, 0.13), 60, (0.4, -0.2, -0.9)),
]

SHARED_WIRES = (2, 4, 28)
WIRE_ISL = tuple(i for i in range(10, 46) if i != 37 and i not in (2, 4, 28))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else None
    size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 4096
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rng = np.random.default_rng(23)
    low = load_low()
    OUT.mkdir(exist_ok=True)
    hole = Hole(low)
    F = Field(bvh_of(low, {1}), 0.136, 0.405)
    Fin = Field(bvh_of(low, {7}), 0.136, 0.390)
    L = Layout(rng, hole)
    nail_layout(L, rng)
    groups = []

    def want(k):
        return only is None or k in only
    if want("wall"):
        hp = [build_wall(L, F, rng)] + hoop_parts(L, F, rng) + nail_parts(L, F, rng) + leaf_part(L, F, rng)
        hp.append(resin_part(L, F))
        groups.append(("wall", (1,), hp, 0.008))
    else:   # раскладка нужна изнанке и др.
        L.data.setdefault("shots", [(L.shot[0], L.shot[1])])
    if want("top"):
        groups.append(("top", (3,), [build_top(L, low, rng)], 0.006))
    if want("inner"):
        groups.append(("inner", (7, 37), build_inner(L, low, Fin, rng), 0.006))
    if want("cut"):
        groups.append(("cut", (6,), [build_cut(L, low, F, Fin)], 0.0025))
    if want("ears") or want("earnail"):
        eo = build_ears(L, low, rng)
        nails_ = [o for o in eo if "earnail" in o.name]
        if want("ears"):
            groups.append(("ears", (5, 9), [o for o in eo if o not in nails_], 0.010))
        # гвоздь ушка (остров 8) лежит под дощечкой ушка: своей группой, иначе луч упирается в дерево
        groups.append(("earnail", (8,), nails_, 0.003))
    if want("wires"):
        w = build_wires(L, low, rng, SHARED_WIRES)
        groups.append(("wires", WIRE_ISL, [w[0]], 0.0015))
        groups.append(("wires_shared", SHARED_WIRES, [w[1]], 0.0015))
    lay = {"staves": L.b.tolist(), "hoop_up": L.hoop_up, "hoop_lo": L.hoop_lo, "hoop_lo_cut": L.hoop_lo_cut,
           "joint": [L.joint_th, L.joint_len], "knots": L.knots, "leaf": L.leaf, "shot": L.shot,
           "hole_th": hole.th.tolist(), "hole_y": hole.y.tolist()}
    lay.update({k: v for k, v in L.data.items()})
    if want("wall"):   # раскладку пишем только при полной сборке стенки
        json.dump(lay, open(OUT / "layout.json", "w"), indent=1, default=float)
    allhp = [o for g in groups for o in g[2]]
    print("high-poly:", {o.name: len(o.data.polygons) for o in allhp if len(o.data.polygons) > 5000},
          "total", sum(len(o.data.polygons) for o in allhp), flush=True)
    low.hide_render = True
    if "--blend" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "highpoly.blend"))
    if "--look" in argv:
        look(allhp, LOOKS_WALL + LOOKS_REST, "hp")
    elif "--nobake" not in argv:
        passes = [("normal", "NORMAL", "view", 8, size, None),
                  ("color", "EMIT", "color", 4, size, None),
                  ("id", "EMIT", "id", 1, size, None),
                  ("msk", "EMIT", "msk", 2, size, None),
                  ("pos", "EMIT", "pos", 1, size, None),
                  ("ao", "AO", "view", 64, size, 0.012),
                  ("aowide", "AO", "view", 64, 1024, 0.06)]
        if "--passes" in argv:
            keep = set(argv[argv.index("--passes") + 1].split(","))
            passes = [p for p in passes if p[0] in keep]
        bake(low, groups, size, passes, partial=only is not None)
    print("done", flush=True)


if __name__ == "__main__":
    main()
