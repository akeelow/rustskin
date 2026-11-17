"""Sauna Shotgun: high-poly детали поверх оригинальной двустволки, запекание на её развёртку.

Что моделируется (координаты OBJ: x — вправо от стрелка, y — вверх, z — к дулу, метры):
  bark     цевьё (BARREL, острова 4, 23, 31, 32): 7 колец бересты внахлёст, каждое чуть по спирали,
           стык кольца — внизу справа (от первого лица не виден); толщина коры 1 мм, кромка
           закручена, края рваные; чечевички — бороздки поперёк волокна (геометрия + цвет вершин)
  twine    две обмотки бечёвкой (5 витков, Ø 1.8 мм) по краям бересты, узел с хвостиками на левом боку
  leaf     берёзовый лист на левом боку цевья (видно от первого лица) — форма как у кресла и полока
  towel    полоса застиранного полотенца (кирпичная полоса вдоль) на шейке приклада, 3.5 витка внахлёст,
           складки, конец подогнут и прибит гвоздиком; вторая полоса — на рукояти рычага (MAIN, остров 8)
  wood     приклад и рукоять GRIP: копия оригинала, подразделена, волокна рельефом; сучок со
           смолой (капля — отдельная геометрия) и выжженный гвоздём орнамент (точки и зигзаг,
           углубления 0.5 мм) на левом боку приклада
  pits     раковины ржавчины на трубах стволов (оба ствола делят один остров — рисунок у них общий)
  nails    кованые гвоздики: конец полотенца, концы колец бересты
Железо (колодка, курки, гайки, пружины) остаётся оригинальной формы: texture_v1.py берёт для него
оригинальную карту нормалей.

Запуск (из папки скина):
  blender -b -P bake_shotgun.py -- [--part barrel|main|stock|grip|all] [--size 2048] [--nobake] [--blend]

Пишет bake/<part>_{normal,ao,color,id,poshi,poslo}.png:
  color — цвет деталей (цвета вершин high-poly), id — R = код детали (IDS) * 16 + 8,
  pos — положение точки в координатах OBJ (16 бит: hi/lo, диапазон POS_LO…POS_HI), для износа по месту.
"""
import json
import math
import random
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector, kdtree, noise
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import noise_np as NN  # noqa: E402

HERE = Path(__file__).resolve().parent
PARTS_DIR = HERE / "source" / "parts"
OUT = HERE / "bake"

IDS = {"metal": 1, "wood": 2, "bark": 3, "twine": 4, "towel": 5, "leaf": 6, "resin": 7, "nail": 8,
       "fore": 9, "burn": 10}
POS_LO = Vector((-0.35, -0.20, -0.50))
POS_HI = Vector((0.35, 0.10, 0.45))

# цвета сета (sRGB HEX) — детали; итоговая палитра и износ — texture_v1.py
HEX = {"wood": "C2A77E", "wood_dark": "A88B62", "bark": "E3DDCF", "lent": "3B342E", "bark_in": "B88E6C",
       "bark_grey": "BDB6A8", "twine": "A99B80", "twine_dark": "7E705A", "towel": "CFC6B4",
       "stripe": "8E3A30", "leaf": "5C6A39", "leaf_vein": "4A5630", "resin": "45332A", "resin_core": "7A4A1C",
       "nail": "3C3A37", "burn": "2E2018", "metal": "808080", "fore": "9C8460"}


def lin(h):
    return [(int(h[i:i + 2], 16) / 255) ** 2.2 for i in (0, 2, 4)]


def mix(a, b, t):
    return [x + (y - x) * t for x, y in zip(a, b)]


# ----------------------------------------------------------------- low-poly
def parse_obj(path):
    V, F = [], []
    for line in open(path):
        if line.startswith("v "):
            V.append(Vector([float(x) for x in line.split()[1:4]]))
        elif line.startswith("f "):
            F.append([int(c.split("/")[0]) - 1 for c in line.split()[1:]])
    return V, F


def load_low(part):
    """Часть как есть: оси OBJ сохраняются, свои нормали (vn) тоже — по ним считает касательные игра."""
    path = PARTS_DIR / f"{part}.obj"
    bpy.ops.wm.obj_import(filepath=str(path), forward_axis="Y", up_axis="Z")
    low = bpy.context.selected_objects[0]
    low.name = f"low_{part}"
    # остров каждой грани: сопоставляем по центру грани (импорт может переставить или выкинуть грани)
    V, F = parse_obj(path)
    isl = json.load(open(HERE / "uv" / f"faces_{part}.json"))
    kd = kdtree.KDTree(len(F))
    for i, f in enumerate(F):
        kd.insert(sum((V[j] for j in f), Vector()) / len(f), i)
    kd.balance()
    idx = [kd.find(p.center)[1] for p in low.data.polygons]
    low["isl"] = [isl[i] for i in idx]
    cpath = HERE / "uv" / f"faces_{part}_class.json"
    if cpath.exists():   # v1.8: класс грани по оригинальной текстуре (classify_stock.py): cloth / metal / wood
        cls = json.load(open(cpath))
        low["cls"] = [cls[i] for i in idx]
    return low


def polys_of(low, islands):
    isl = low["isl"]
    return [p for p in low.data.polygons if isl[p.index] in islands]


def bvh_of(low, islands=None):
    me = low.data
    verts = [v.co.copy() for v in me.vertices]
    ps = me.polygons if islands is None else polys_of(low, islands)
    return BVHTree.FromPolygons(verts, [list(p.vertices) for p in ps])


def copy_polys(low, islands, name):
    """Новый объект из граней указанных островов (копия формы, без UV-забот)."""
    me = low.data
    bm = bmesh.new()
    bm.from_mesh(me)
    isl = low["isl"]
    drop = [f for f in bm.faces if isl[f.index] not in islands]
    bmesh.ops.delete(bm, geom=drop, context="FACES")
    m2 = bpy.data.meshes.new(name)
    bm.to_mesh(m2)
    bm.free()
    ob = bpy.data.objects.new(name, m2)
    bpy.context.scene.collection.objects.link(ob)
    return ob


# ----------------------------------------------------------------- mesh helpers
def new_mesh(name, verts, faces, cols, ident, outward=None):
    """outward: точка «внутри» (нормали смотрят от неё) или вектор-направление наружу; None — пересчёт
    bmesh (для труб и замкнутых). Первое запекание бересты вышло с нормалями внутрь — AO чёрный."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    orient(me, outward)
    set_attrs(me, cols, ident)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    return ob


def orient(me, outward):
    if not me.polygons:
        return
    if outward is None:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        me.update()
        return
    score = 0.0
    for p in me.polygons:
        ref = outward(p.center) if callable(outward) else Vector(outward)
        score += p.normal.dot(ref) * p.area
    if score < 0:
        me.flip_normals()
        me.update()


def set_attrs(me, cols, ident):
    """cols: список RGB (линейный) на вершину или один цвет; ident: имя из IDS (одно на объект) или список."""
    n = len(me.vertices)
    ca = me.color_attributes.get("col") or me.color_attributes.new("col", "FLOAT_COLOR", "POINT")
    ia = me.color_attributes.get("idc") or me.color_attributes.new("idc", "FLOAT_COLOR", "POINT")
    if cols and isinstance(cols[0], (int, float)):
        cols = [cols] * n
    flat = np.ones((n, 4), np.float32)
    flat[:, :3] = np.array(cols, np.float32)
    ca.data.foreach_set("color", flat.ravel())
    if isinstance(ident, str):
        ident = [ident] * n
    ids = np.ones((n, 4), np.float32)
    ids[:, 0] = [(IDS[i] * 16 + 8) / 255 for i in ident]
    ids[:, 1:3] = 0
    ia.data.foreach_set("color", ids.ravel())


def grid_faces(nu, nv, closed_u=False):
    faces = []
    for i in range(nu - (0 if closed_u else 1)):
        i2 = (i + 1) % nu
        for j in range(nv - 1):
            faces.append((i * nv + j, i2 * nv + j, i2 * nv + j + 1, i * nv + j + 1))
    return faces


def smooth01(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


# ----------------------------------------------------------------- axis frames for wraps
class Axis:
    """Ось обмотки: направление A, базис e1/e2 поперёк, центр сечения по параметру s (из вершин)."""

    def __init__(self, verts, A, e1, step=0.003):
        self.A = Vector(A).normalized()
        self.e1 = Vector(e1).normalized()
        self.e2 = self.A.cross(self.e1).normalized()
        ss = [v.dot(self.A) for v in verts]
        lo, hi = min(ss), max(ss)
        self.s0, self.step = lo, step
        n = int((hi - lo) / step) + 1
        acc = [[Vector(), 0] for _ in range(n)]
        for v, s in zip(verts, ss):
            k = min(int((s - lo) / step), n - 1)
            acc[k][0] += v - self.A * s
            acc[k][1] += 1
        known = [(k, a / c) for k, (a, c) in enumerate(acc) if c]
        self.cent = []
        for k in range(n):  # дыры — ближайшим известным
            self.cent.append(min(known, key=lambda kc: abs(kc[0] - k))[1])

    def refine(self, bvh, far=0.15):
        """Центр сечения — середина между попаданиями лучей снаружи по ±e1 и ±e2 (вершины у моделей
        редкие: у цевья все вершины на 4 сечениях, центр по ним уходит в сторону)."""
        for _ in range(2):
            new = []
            for k, c0 in enumerate(self.cent):
                s = self.s0 + k * self.step
                c = c0 + self.A * s
                out = c0.copy()
                for e in (self.e1, self.e2):
                    a, _, _, _ = bvh.ray_cast(c + e * far, -e, far * 2)
                    b, _, _, _ = bvh.ray_cast(c - e * far, e, far * 2)
                    if a is not None and b is not None:
                        mid = (a + b) / 2 - self.A * s
                        out = out - e * out.dot(e) + e * mid.dot(e)
                new.append(out)
            self.cent = new
        return self

    def center(self, s):
        x = (s - self.s0) / self.step
        k = int(min(max(math.floor(x), 0), len(self.cent) - 2))
        t = min(max(x - k, 0.0), 1.0)
        return self.cent[k].lerp(self.cent[k + 1], t) + self.A * s

    def radial(self, th):
        return self.e1 * math.cos(th) + self.e2 * math.sin(th)


def surf(bvh, ax, s, th, far=0.12):
    """Точка поверхности по лучу снаружи к оси (самая внешняя), и радиальное направление."""
    d = ax.radial(th)
    c = ax.center(s)
    hit, n, _, _ = bvh.ray_cast(c + d * far, -d, far * 1.2)
    return hit, d, n


def wrap_strip(bvh, ax, s_a, s_b, th0, turns, width, offset_fn, du=0.0012, dv=0.0006, name="strip",
               color_fn=None, ident="towel", width_fn=None):
    """Лента по спирали вокруг оси: от s_a к s_b за `turns` оборотов, начиная с угла th0.
    offset_fn(t, v, u_m) — высота над поверхностью (м); v ∈ [-0.5, 0.5] поперёк, u_m — длина вдоль.
    color_fn(t, v, u_m) — линейный RGB. Лучи, не попавшие в поверхность, рвут ленту (там дыра)."""
    c = ax.center((s_a + s_b) / 2)
    hit0, d0, _ = surf(bvh, ax, (s_a + s_b) / 2, th0)
    r_est = (hit0 - c).length if hit0 else 0.02
    length = 2 * math.pi * r_est * abs(turns)
    nu = max(int(length / du), 8)
    nv = max(int(width / dv), 4)
    verts, cols, ok = [], [], []
    for i in range(nu):
        t = i / (nu - 1)
        th = th0 + 2 * math.pi * turns * t
        u_m = t * length
        w = width * (width_fn(t, u_m) if width_fn else 1.0)
        for j in range(nv):
            v = -0.5 + j / (nv - 1)
            s = s_a + (s_b - s_a) * t + v * w
            hit, d, _ = surf(bvh, ax, s, th)
            if hit is None:
                verts.append(ax.center(s))
                ok.append(False)
            else:
                verts.append(hit + d * offset_fn(t, v, u_m))
                ok.append(True)
            cols.append(color_fn(t, v, u_m) if color_fn else lin(HEX["towel"]))
    faces = [f for f in grid_faces(nu, nv) if all(ok[k] for k in f)]

    def out(p):
        s = p.dot(ax.A)
        r = p - ax.center(s)
        return r - ax.A * r.dot(ax.A)
    return new_mesh(name, verts, faces, cols, ident, outward=out)


def tube_mesh(points, radius, name, color, ident, seg=8, twist=0.0, col_fn=None):
    """Труба по ломаной (бечёвка): кольца по `seg` вершин; twist — скрутка волокон (для цвета)."""
    verts, cols = [], []
    n = len(points)
    prev = None
    for i, p in enumerate(points):
        tng = (points[min(i + 1, n - 1)] - points[max(i - 1, 0)]).normalized()
        if prev is None:
            a = Vector((0, 0, 1)) if abs(tng.z) < 0.9 else Vector((1, 0, 0))
            prev = tng.cross(a).normalized()
        b1 = (prev - tng * prev.dot(tng)).normalized()
        b2 = tng.cross(b1)
        prev = b1
        for k in range(seg):
            a = 2 * math.pi * k / seg
            # волокна: витая верёвка — канавки по спирали
            groove = 1.0 - 0.32 * max(0.0, math.cos(3 * a + twist * i)) ** 3   # v1.8: свив глубже
            verts.append(p + (b1 * math.cos(a) + b2 * math.sin(a)) * radius * groove)
            cols.append(col_fn(i, k, a) if col_fn else color)
    faces = []
    for i in range(n - 1):
        for k in range(seg):
            k2 = (k + 1) % seg
            faces.append((i * seg + k, (i + 1) * seg + k, (i + 1) * seg + k2, i * seg + k2))
    return new_mesh(name, verts, faces, cols, ident)


def forged_nail(center, normal, r, name):
    """Кованый гвоздик: четырёхгранная шляпка-пирамидка с притуплённой вершиной."""
    nrm = Vector(normal).normalized()
    a = Vector((1, 0, 0)) if abs(nrm.x) < 0.9 else Vector((0, 1, 0))
    t1 = nrm.cross(a).normalized()
    t2 = nrm.cross(t1)
    rot = random.uniform(0, math.pi / 2)
    base, top = [], []
    for k in range(4):
        ang = rot + k * math.pi / 2
        d = t1 * math.cos(ang) + t2 * math.sin(ang)
        base.append(center + d * r - nrm * 0.0003)
        top.append(center + d * r * 0.35 + nrm * r * 0.55)
    verts = base + top + [center + nrm * r * 0.62]
    faces = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 8), (5, 6, 8), (6, 7, 8), (7, 4, 8)]
    return new_mesh(name, verts, faces, lin(HEX["nail"]), "nail", outward=lambda p: p - center)


def leaf_mesh(center, normal, along, length, name, conform=None):
    """Берёзовый лист (как у кресла: зубчатый овал с остриём, загиб краёв, бороздка жилки, черешок).
    length в метрах; along — направление черешок→кончик (по поверхности)."""
    nrm = Vector(normal).normalized()
    ax = (Vector(along) - nrm * Vector(along).dot(nrm)).normalized()
    side = nrm.cross(ax)
    half = length / 2
    nu, nv = 60, 16
    verts, cols = [], []
    for i in range(nu + 1):
        u = -1 + 2 * i / nu
        w = 0.62 * math.sqrt(max(1 - u * u, 0)) * (1.15 - 0.45 * u)
        w = max(w * (1 + 0.05 * math.sin(u * 46.0)), 0.004)
        for j in range(nv + 1):
            v = (-1 + 2 * j / nv) * w
            h = 0.0005 + 0.05 * length * v * v + 0.0004 * math.exp(-(v / 0.04) ** 2) * (u < 0.92)   # загиб краёв ~0.6 мм, жилка — валиком
            # боковые жилки — неглубокие бороздки ёлочкой
            vein = 0.00030 * max(0.0, math.cos((u * 7 + abs(v) * 5) * math.pi)) ** 6
            p = center + ax * (u * half) + side * (v * half)
            if conform is not None:   # лист мокрый и прилип: ложится по ВНЕШНЕЙ поверхности (луч снаружи;
                # ближайшая точка в v1.8 нашла нижнее кольцо бересты — лист ушёл под соседнее и вышел «рваным»)
                loc, n2, _, _ = conform.ray_cast(p + nrm * 0.02, -nrm, 0.04)
                if loc is None:
                    loc, n2, _, _ = conform.find_nearest(p)
                if loc is not None:
                    verts.append(loc + n2.normalized() * (h - vein))
                else:
                    verts.append(p + nrm * (h - vein))
            else:
                verts.append(p + nrm * (h - vein))
            dark = math.exp(-(v / 0.04) ** 2) * 0.7 + (1 if vein > 0.00008 else 0) * 0.3
            yel = max(0.0, noise.noise(Vector((u * 2, v * 3, 7.1))) * 0.6)
            c = mix(lin(HEX["leaf"]), lin(HEX["leaf_vein"]), dark)
            cols.append(mix(c, lin("8A8A40"), yel * 0.5))
    faces = []
    for i in range(nu):
        for j in range(nv):
            a = i * (nv + 1) + j
            faces.append((a, a + nv + 1, a + nv + 2, a + 1))
    ob = new_mesh(name, verts, faces, cols, "leaf", outward=nrm)
    # черешок
    p0 = center - ax * (half * 1.0)
    pts = [p0 - ax * (half * 0.4 * k / 6) + nrm * 0.0007 for k in range(7)]
    st = tube_mesh(pts, 0.0006, name + "_stalk", lin(HEX["leaf_vein"]), "leaf", seg=6)
    return [ob, st]


# ----------------------------------------------------------------- parts
def copy_faces(low, pred, name):
    """Как copy_polys, но по условию на грань: pred(остров, центр, нормаль) -> bool."""
    bm = bmesh.new()
    bm.from_mesh(low.data)
    bm.faces.ensure_lookup_table()
    isl = low["isl"]
    drop = [f for f in bm.faces if not pred(isl[f.index], f.calc_center_median(), f.normal)]
    bmesh.ops.delete(bm, geom=drop, context="FACES")
    m2 = bpy.data.meshes.new(name)
    bm.to_mesh(m2)
    bm.free()
    ob = bpy.data.objects.new(name, m2)
    bpy.context.scene.collection.objects.link(ob)
    return ob


FORE_ISL = {4, 23, 31, 32}


def is_fore_cap(i, c, n):
    """Передний торец цевья: острова цевья, z > 0.405, нормаль смотрит вперёд (без скруглённой кромки)."""
    return i in FORE_ISL and c.z > 0.405 and n.z > 0.45


def end_grain(low, pred, name, center, ident="fore", seed=51, cracks=((0.6, 0.022), (2.9, 0.016)), level=5):
    """Дерево в торец по граням pred: годичные кольца бороздками (~3 мм: при 12-19 px/см это 4-6 px), поздняя
    древесина темнее, сердцевина `center` (не по центру, как у настоящего бруска), трещины-усушки, тёмная кромка
    там, где торец скругляется. Кольца считаются в плоскости, перпендикулярной средней нормали торца.
    v1.5 - передний торец цевья; v1.6 - все торцы: задние торцы цевья, затыльник приклада, торец рукояти GRIP
    (до этого на затыльник легли продольные волокна, остальные были заливкой)."""
    ob = copy_faces(low, pred, name)
    src = src_polys(low, pred)
    if not ob.data.polygons:
        print("end_grain: no faces for", name, flush=True)
        return ob
    nsum = Vector()
    for p in ob.data.polygons:
        nsum += p.normal * p.area
    N0 = nsum.normalized()
    a = Vector((1, 0, 0)) if abs(N0.x) < 0.9 else Vector((0, 1, 0))
    U = N0.cross(a).normalized()
    W = N0.cross(U)
    rounded(ob, low, 2, src)
    subdivided(ob, max(level - 2, 1))
    for p in ob.data.polygons:
        p.use_smooth = True
    C = np.array(center)
    Un, Wn, Nn = np.array(U), np.array(W), np.array(N0)
    early, late = np.array(lin("B9A07A")), np.array(lin("7A5E40"))

    def fn(co, nr):
        rel = co - C
        dx, dy = rel @ Un, (rel @ Wn) * 1.08
        r = np.hypot(dx, dy)
        ang = np.arctan2(dy, dx)
        wob = NN.fbm(np.stack([dx * 90, dy * 90, np.full_like(dx, 3.0)], -1), 3, seed) - 0.5
        ph = r / 0.0032 + wob * 1.3
        fr = ph - np.floor(ph)
        lw = NN.smooth((fr - 0.55) / 0.2) * (1 - NN.smooth((fr - 0.95) / 0.05))   # поздняя древесина
        d = -0.00035 * lw   # v1.8: кольца бороздками 0.35 мм (0.12 мм в игре не читались)
        cols = early + (late - early) * lw[:, None] * 0.85
        pith = np.exp(-(r / 0.0016) ** 2)
        cols = cols * (1 - pith[:, None] * 0.6) + np.array(lin("4E3A28")) * pith[:, None] * 0.6
        crack = np.zeros_like(r)
        for a0, ln in cracks:
            da = np.angle(np.exp(1j * (ang - a0)))
            dist = np.abs(np.sin(da)) * r
            crack = np.maximum(crack, np.exp(-(dist / (0.0005 + 0.00008 * r / 0.01)) ** 2) * (np.cos(da) > 0)
                               * NN.smooth((ln - r) / 0.004) * NN.smooth(r / 0.003))
        d -= 0.0014 * crack
        cols = cols * (1 - crack[:, None] * 0.8) + np.array(lin("33261A")) * crack[:, None] * 0.8
        rim = NN.smooth((0.85 - nr @ Nn) / 0.3)
        cols = cols * (1 - rim[:, None] * 0.45) + np.array(lin("6A5038")) * rim[:, None] * 0.45
        return d, cols.astype(np.float32), np.full(len(co), IDS[ident])
    cols, ids = displace(ob, fn)
    set_attrs_np(ob.data, cols, ids)
    return ob


FORE_PITH = (0.004, -0.044)   # сердцевина бруска цевья (одна для переднего и задних торцов)
FORE_REAR = {31, 32}          # задние торцы цевья (z 0.216...0.220)


def fore_cap(low):
    return end_grain(low, is_fore_cap, "hp_fore_cap", (FORE_PITH[0], FORE_PITH[1], 0.42), "fore", 51)


def grain_copy(low, pred, name, ident, seed=31):
    """Продольное дерево: копия граней, подразделена, волокна вдоль z рельефом и цветом."""
    ob = copy_faces(low, pred, name)
    rounded(ob, low, 2, src_polys(low, pred))
    subdivided(ob, 1)
    for p in ob.data.polygons:
        p.use_smooth = True
    cw, cd = np.array(lin(HEX["wood"])), np.array(lin(HEX["wood_dark"]))

    def fn(co, nr):
        x, y, z = co[:, 0], co[:, 1], co[:, 2]
        g = NN.fbm(np.stack([x * 120, y * 120, z * 9], -1), 3, seed) * 2 - 1
        fib = NN.vnoise(np.stack([x * 1200, y * 1200, z * 50], -1), seed + 1) * 2 - 1
        ring = np.sin((y * 260 + x * 140 + g * 3.0) * np.pi)
        d = 0.00018 * fib + 0.00012 * ring   # v1.8: волокна глубже
        t = 0.5 * NN.smooth(ring * 0.5 + 0.2) + 0.25 * (g * 0.5 + 0.5)
        return d, (cw + (cd - cw) * t[:, None]).astype(np.float32), np.full(len(co), IDS[ident])
    cols, ids = displace(ob, fn)
    set_attrs_np(ob.data, cols, ids)
    return ob


def metal_copy(low, islands, name):
    """Точная копия железа (нормали потом - оригинальные Facepunch, texture_v1.py)."""
    ob = copy_polys(low, islands, name)
    set_attrs(ob.data, lin(HEX["metal"]), "metal")
    return ob


def fore_end(low, rng):
    """BARREL: цевьё — береста кольцами, бечёвка, лист, гвоздики; трубы стволов с раковинами."""
    FORE = {4, 23, 31, 32}
    TUBES = {1, 18, 17, 2}
    hp = []
    # v1.6: цевьё отдельно от железа: бока и полоса между стволами - продольное дерево с волокнами (было заливкой),
    # передний и задние торцы - дерево в торец
    base = copy_faces(low, lambda i, c, n: i not in TUBES and i not in FORE, "hp_barrel_rest")
    set_attrs(base.data, lin(HEX["metal"]), "metal")
    hp.append(base)
    hp.append(grain_copy(low, lambda i, c, n: i in FORE and i not in FORE_REAR and not is_fore_cap(i, c, n),
                         "hp_fore_wood", "fore", 61))
    hp.append(end_grain(low, lambda i, c, n: i in FORE_REAR, "hp_fore_rear", (FORE_PITH[0], FORE_PITH[1], 0.218),
                        "fore", 52, cracks=((0.6, 0.022),)))

    hp += pitted_tubes(low, TUBES, rng)
    hp.append(fore_cap(low))
    hp += barrel_sleeves(low, rng)

    bvh = round_bvh(low, lambda i, c, n: i in FORE)
    isl = low["isl"]
    fore_v = {v for p in low.data.polygons if isl[p.index] in FORE for v in p.vertices}
    fv = [low.data.vertices[v].co.copy() for v in fore_v]
    ax = Axis(fv, (0, 0, 1), (1, 0, 0)).refine(bvh)
    # Угол θ: 0 — правый бок (+x), 90° — верх, 180° — левый бок, 270° — низ. Сверху на цевье лежат
    # стволы (сечение там вогнутое, r ≈ 20 мм против 31–44 по бокам и снизу), поэтому кора идёт дугой:
    # от правого верхнего края вниз, под цевьём, вверх по левому боку — концы заправлены под стволы.
    ARC0, ARC = math.radians(28), -math.radians(236)
    z0, z1 = 0.226, 0.416
    n_bands = 7
    band_w = 0.031
    step = (z1 - z0 - band_w) / (n_bands - 1)
    TH = 0.0014  # толщина коры (v1.8: 1.4 мм — при 1 мм в игре береста читалась нарисованной)

    def bark_color(seed):
        def fn(t, v, u_m):
            p = Vector((u_m * 90, v * 30, seed))
            c = lin(HEX["bark"])
            # серые пятна и розоватая луба по рваному краю
            g = noise.noise(p * 0.3) * 0.5 + 0.5
            c = mix(c, lin(HEX["bark_grey"]), smooth01((g - 0.45) * 2.5) * 0.6)
            edge = abs(v) * 2
            c = mix(c, lin(HEX["bark_in"]), smooth01((edge - 0.86) / 0.12) * 0.7)
            # чечевички: тёмные чёрточки ВДОЛЬ ленты (поперёк волокна берёзы)
            q = noise.noise(Vector((u_m * 140, v * band_w * 2600, seed + 3.3)))
            if q > 0.48:
                c = mix(c, lin(HEX["lent"]), min((q - 0.48) * 6, 1.0))
            # редкие чёрные крапинки
            if noise.noise(Vector((u_m * 900, v * band_w * 900, seed + 9))) > 0.62:
                c = mix(c, lin("1E1A17"), 0.8)
            return c
        return fn

    def bark_offset(k):
        layer = 0.0006 + (k % 2) * (TH * 1.1)  # чётные — внизу, нечётные лежат на соседях

        def fn(t, v, u_m):
            e = abs(v) * 2
            edge = 1.0 - 0.75 * smooth01((e - 0.82) / 0.18)  # кромка: толщина сходит на нет
            curl = 0.0012 * smooth01((v * 2 - 0.8) / 0.2)  # передняя рваная кромка отгибается
            q = noise.noise(Vector((u_m * 140, v * band_w * 2600, k + 3.3)))
            lent = -0.00035 * min((q - 0.48) * 8, 1.0) if q > 0.48 else 0.0  # чечевички — бороздки 0.35 мм
            wav = 0.00012 * noise.noise(Vector((u_m * 40, v * 6, k)))
            tuck = smooth01(min(t, 1 - t) / 0.04)  # концы заправлены под стволы — сходят к поверхности
            return (layer + TH * edge + curl + lent + wav) * (0.35 + 0.65 * tuck)
        return fn

    def rag(k):
        return lambda t, u_m: 1.0 + 0.06 * noise.noise(Vector((u_m * 60, k, 0.5)))

    bands = []
    for k in range(n_bands):
        zc = z0 + band_w / 2 + k * step
        pitch = 0.004 * (1 if k % 2 else -1)
        a0 = ARC0 + rng.uniform(-0.06, 0.06)
        ob = wrap_strip(bvh, ax, zc - pitch / 2, zc + pitch / 2, a0, (ARC + rng.uniform(-0.06, 0.06)) / (2 * math.pi),
                        band_w, bark_offset(k), name=f"hp_bark_{k}", color_fn=bark_color(k * 1.7),
                        ident="bark", width_fn=rag(k))
        bands.append(ob)
    hp += bands

    # бечёвка: по краям бересты, поверх колец
    dg = bpy.context.evaluated_depsgraph_get()
    bark_bvh = BVHTree.FromObject(bands[0], dg)
    all_bark = join_bvh(bands + [base])
    r = 0.0009
    # Сторона: на модели +x — левый бок стрелка (рычаг на +x; из-за приклада он слева) — его видно
    # от первого лица и со стороны щеки. Узел задней обмотки — на +x, передней — на -x (для вида сбоку).
    for zc, knot_th in ((z0 + 0.012, math.radians(-8)), (z1 - 0.012, math.radians(188))):
        turns = 5
        for coil in range(turns):  # каждый виток — дуга под цевьём; переход между витками скрыт стволами
            pts = []
            nn = 240
            for i in range(nn):
                t = i / (nn - 1)
                th = ARC0 + 0.05 + (ARC - 0.1) * t
                s = zc + (coil - (turns - 1) / 2) * 2.1 * r + 0.6 * r * t
                hit, d, _ = surf(all_bark, ax, s, th)
                if hit is not None:
                    pts.append(hit + d * (r * 0.9))
            hp.append(tube_mesh(pts, r, f"hp_twine_{zc:.3f}_{coil}", lin(HEX["twine"]), "twine", twist=0.9,
                                col_fn=twine_col))
        # узел: три петли и два хвостика вниз по боку
        down = -1 if math.cos(knot_th) > 0 else 1   # к низу (270°): на +x угол убывает, на -x растёт
        for kk in range(3):
            c_s = zc + (kk - 1) * 0.0016
            hit, d, _ = surf(all_bark, ax, c_s, knot_th + kk * 0.06)
            if hit is None:
                continue
            loop = []
            for i in range(25):
                a = 2 * math.pi * i / 24
                off = ax.A * (math.cos(a) * 0.0022) + ax.radial(knot_th + math.pi / 2) * (math.sin(a) * 0.0016)
                loop.append(hit + d * (2.2 * r + 0.0012 * (1 + math.sin(a))) + off)
            hp.append(tube_mesh(loop, r * 0.95, f"hp_knot_{zc:.3f}_{kk}", lin(HEX["twine"]), "twine", twist=0.9,
                                col_fn=twine_col))
        for side in (-1, 1):
            tail = []
            for i in range(30):
                t = i / 29
                th = knot_th + down * math.radians(18) * t + side * math.radians(3)  # вниз по боку
                s = zc + side * 0.002 + side * 0.006 * t
                hit, d, _ = surf(all_bark, ax, s, th)
                if hit is not None:
                    tail.append(hit + d * (r * (2.0 - 1.1 * t)))
            if len(tail) > 2:
                hp.append(tube_mesh(tail, r * 0.85, f"hp_tail_{zc:.3f}_{side}", lin(HEX["twine"]), "twine",
                                    twist=0.9, col_fn=twine_col))

    # лист: левый бок, ближе к середине цевья — там, где рука его не закроет целиком
    hit, d, n = surf(all_bark, ax, 0.33, math.radians(-14))   # +x — левый бок стрелка
    if hit is not None:
        along = Vector((0, -0.35, 1))
        hp += leaf_mesh(hit + d * 0.0004, d, along, 0.034, "hp_leaf", conform=all_bark)
    # гвоздики: прихватывают кольца снизу-слева (видно сбоку) и справа, не на листе
    for k, ob in enumerate(bands):
        zc = z0 + band_w / 2 + k * step
        for th in ((math.radians(225), math.radians(-35)) if k % 2 else (math.radians(-35),)):
            if abs(zc - 0.33) < 0.025 and th > 3:
                continue
            hit, d, _ = surf(all_bark, ax, zc + 0.008, th)
            if hit is not None:
                hp.append(forged_nail(hit + d * 0.0001, d, 0.0019, f"hp_nail_b{k}_{th:.1f}"))
    return hp


_BT = {}


def barrel_transform(low):
    """Второй ствол = M·первый + T (по вершинам с одинаковыми UV, метод наименьших квадратов). Кэш + bake/barrel_copy.json
    (texture_v1.py переводит положение точек второго ствола в систему первого, чтобы узоры совпали)."""
    if "M" in _BT:
        return _BT["M"], _BT["T"], _BT["ca"], _BT["cb"], _BT["A"]
    OUTER = {1}
    isl = low["isl"]
    vs = {v for p in low.data.polygons if isl[p.index] in OUTER for v in p.vertices}
    A = [low.data.vertices[v].co.copy() for v in vs if low.data.vertices[v].co.x > 0]
    Bv = [low.data.vertices[v].co.copy() for v in vs if low.data.vertices[v].co.x < 0]
    ca = sum(A, Vector()) / len(A)
    cb = sum(Bv, Vector()) / len(Bv)
    uvl = low.data.uv_layers.active.data
    byuv = {}
    for p in low.data.polygons:
        if isl[p.index] not in OUTER:
            continue
        for li, vi in zip(p.loop_indices, p.vertices):
            key = (round(uvl[li].uv.x, 5), round(uvl[li].uv.y, 5))
            byuv.setdefault(key, set()).add(vi)
    pairs = []
    for vset in byuv.values():
        pa_ = [low.data.vertices[i].co for i in vset if low.data.vertices[i].co.x > 0]
        pb_ = [low.data.vertices[i].co for i in vset if low.data.vertices[i].co.x < 0]
        if pa_ and pb_:
            pairs.append((pa_[0], pb_[0]))
    PA = np.array([list(p[0]) + [1.0] for p in pairs])
    PB = np.array([list(p[1]) for p in pairs])
    X, *_ = np.linalg.lstsq(PA, PB, rcond=None)
    err = float(np.abs(PA @ X - PB).max())
    M = X[:3].T
    T = X[3]
    print("barrel B = M A + t:", np.round(M, 3).tolist(), np.round(T, 4).tolist(), "max err", round(err, 5), flush=True)
    OUT.mkdir(exist_ok=True)
    json.dump({"M": M.tolist(), "T": T.tolist(), "mx": (ca.x + cb.x) / 2, "axisA": [ca.x, ca.y]},
              open(OUT / "barrel_copy.json", "w"), indent=1)
    _BT.update(M=M, T=T, ca=ca, cb=cb, A=A)
    return M, T, ca, cb, A


def barrel_sleeves(low, rng):
    """Манжеты бересты на стволах у казённика (z 0.142…0.206) + 4 витка бечёвки по переднему краю.
    Видно от первого лица — сверху на цевье всё закрывают стволы. Оба ствола делят один остров UV
    (общие vt), поэтому манжету строим на одном и копируем на второй тем же преобразованием, каким
    второй ствол получен из первого (зеркало или сдвиг — проверяем по вершинам): иначе два разных
    рисунка запеклись бы в одни и те же пиксели."""
    OUTER = {1}
    isl = low["isl"]
    M, T, ca, cb, A = barrel_transform(low)
    mx = (ca.x + cb.x) / 2

    # v1.9: манжеты ложатся на скруглённую трубу (на гранёной low-poly они выходили многоугольными)
    pr_ = lambda i, c, n: i in OUTER and c.x > 0
    proxy = copy_faces(low, pr_, "proxy_round_tube")
    even_mesh(proxy, 0.004)
    rounded(proxy, low, 1, src_polys(low, pr_))
    bvh = join_bvh([proxy])
    bpy.data.objects.remove(proxy)
    ax = Axis(A, (0, 0, 1), (1, 0, 0)).refine(bvh)
    TH = 0.0009
    # второй ствол — копия первого, повёрнутая ≈ на -99° вокруг оси z (не зеркало: см. лог). Стык коры
    # на первом при -60° уходит на втором к -159°: оба стыка снизу, где под стволами шарнирный блок.
    SEAM = math.radians(-60)
    objs = []
    for k, (za, zb) in enumerate(((0.142, 0.176), (0.170, 0.206))):
        def off(t, v, u_m, k=k):
            e = abs(v) * 2
            edge = 1.0 - 0.75 * smooth01((e - 0.82) / 0.18)
            curl = 0.0006 * smooth01((v * 2 - 0.85) / 0.15)
            q = noise.noise(Vector((u_m * 140, v * 34 * 2600 / 31, k + 13.3)))
            lent = -0.00016 if q > 0.48 else 0.0
            over = 0.0008 * smooth01((t - 0.94) / 0.06)   # конец кольца на его начале (стык внизу)
            return 0.0005 + k * TH * 1.05 + TH * edge + curl + lent + over

        def col(t, v, u_m, k=k):
            c = lin(HEX["bark"])
            g = noise.noise(Vector((u_m * 27, v * 9, k + 20))) * 0.5 + 0.5
            c = mix(c, lin(HEX["bark_grey"]), smooth01((g - 0.45) * 2.5) * 0.6)
            c = mix(c, lin(HEX["bark_in"]), smooth01((abs(v) * 2 - 0.86) / 0.12) * 0.7)
            q = noise.noise(Vector((u_m * 140, v * 34 * 2600 / 31, k + 13.3)))
            if q > 0.48:
                c = mix(c, lin(HEX["lent"]), min((q - 0.48) * 6, 1.0))
            if noise.noise(Vector((u_m * 900, v * 30, k + 29))) > 0.62:
                c = mix(c, lin("1E1A17"), 0.8)
            # копоть от выстрелов и пар — кора у ствола желтеет и сереет
            return mix(c, lin("A39882"), 0.25)
        zc = (za + zb) / 2
        objs.append(wrap_strip(bvh, ax, zc - 0.0015, zc + 0.0015, SEAM, 1.06, zb - za, off,
                               name=f"hp_sleeve_{k}", color_fn=col, ident="bark",
                               width_fn=lambda t, u_m, k=k: 1.0 + 0.05 * noise.noise(Vector((u_m * 60, k + 40, 0.5)))))
    sb = join_bvh(objs)
    r = 0.0008
    for coil in range(4):
        pts = []
        for i in range(181):
            t = i / 180
            th = SEAM + 2 * math.pi * t
            s = 0.199 + (coil - 1.5) * 2.1 * r + 0.5 * r * t
            hit, d, _ = surf(sb, ax, s, th)
            if hit is not None:
                pts.append(hit + d * (r * 0.9))
        objs.append(tube_mesh(pts, r, f"hp_sleeve_twine_{coil}", lin(HEX["twine"]), "twine", twist=0.9,
                              col_fn=twine_col))
    # второй ствол — тем же преобразованием
    out = list(objs)
    for ob in objs:
        o2 = ob.copy()
        o2.data = ob.data.copy()
        o2.name = ob.name + "_b"
        bpy.context.scene.collection.objects.link(o2)
        for v in o2.data.vertices:
            v.co = Vector(M @ np.array(v.co) + T)
        if np.linalg.det(M) < 0:   # зеркальное преобразование выворачивает грани
            o2.data.flip_normals()
        o2.data.update()
        out.append(o2)
    return out


def twine_col(i, k, a):
    c = lin(HEX["twine"])
    stripe = max(0.0, math.cos(3 * a + 0.9 * i)) ** 2
    c = mix(c, lin(HEX["twine_dark"]), 0.35 * stripe)
    return mix(c, lin("8C7E66"), 0.3 * (noise.noise(Vector((i * 0.05, k, 1.0))) * 0.5 + 0.5))


def join_bvh(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for ob in objs:
        me = ob.evaluated_get(dg).to_mesh()
        o = len(verts)
        verts += [ob.matrix_world @ v.co for v in me.vertices]
        polys += [[o + i for i in p.vertices] for p in me.polygons]
        ob.evaluated_get(dg).to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)


def subdivided(ob, levels):
    m = ob.modifiers.new("sub", "SUBSURF")
    m.subdivision_type = "SIMPLE"
    m.levels = m.render_levels = levels
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.modifier_apply(modifier="sub")
    ob.select_set(False)


def displace(ob, fn):
    """Сдвиг вершин вдоль нормали, векторно: fn(co (N,3), nrm (N,3)) -> (сдвиг (N,), цвет (N,3), id (N,) строки)."""
    me = ob.data
    me.update()
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    nr = np.empty(n * 3, np.float32)
    me.vertices.foreach_get("co", co)
    me.vertices.foreach_get("normal", nr)
    co, nr = co.reshape(n, 3), nr.reshape(n, 3)
    d, cols, ids = fn(co.astype(np.float64), nr)
    me.vertices.foreach_set("co", (co + nr * d[:, None]).astype(np.float32).ravel())
    me.update()
    return cols, ids


def set_attrs_np(me, cols, ids):
    n = len(me.vertices)
    ca = me.color_attributes.get("col") or me.color_attributes.new("col", "FLOAT_COLOR", "POINT")
    ia = me.color_attributes.get("idc") or me.color_attributes.new("idc", "FLOAT_COLOR", "POINT")
    flat = np.ones((n, 4), np.float32)
    flat[:, :3] = cols
    ca.data.foreach_set("color", flat.ravel())
    code = np.array([IDS[k] for k in IDS])
    idv = np.ones((n, 4), np.float32)
    idv[:, 0] = (ids * 16 + 8) / 255
    idv[:, 1:3] = 0
    ia.data.foreach_set("color", idv.ravel())


def refine_zone(ob, inside, cuts=3):
    """Мельче сетка там, где тонкий рельеф (орнамент, сучок): inside(центр грани) -> bool."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    faces = [f for f in bm.faces if inside(f.calc_center_median())]
    edges = list({e for f in faces for e in f.edges})
    if edges:
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=cuts, use_grid_fill=True)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bm.to_mesh(ob.data)
    bm.free()


def even_mesh(ob, max_edge):
    """Дробит рёбра длиннее max_edge (по одному разрезу за проход, пока не останется длинных), n-угольники —
    в треугольники. У трубы ствола одна грань идёт на 37 см вдоль: простое подразделение давало шаг 2.3 см
    вдоль ствола, и ямки вытягивались в полосы."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    for _ in range(12):
        long_e = [e for e in bm.edges if e.calc_length() > max_edge]
        if not long_e:
            break
        bmesh.ops.subdivide_edges(bm, edges=long_e, cuts=1, use_grid_fill=True)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bm.to_mesh(ob.data)
    bm.free()


_PH = {}


def src_polys(low, pred):
    """Индексы граней low-poly, из которых сделана копия (pred(остров, центр, нормаль))."""
    isl = low["isl"]
    return [p.index for p in low.data.polygons if pred(isl[p.index], p.center, p.normal)]


def phong_smooth(ob, low, src, alpha=1.0):
    """Скругление Phong: каждая точка копии переносится на гладкую поверхность, которую задают вершины low-poly
    и их собственные сглаженные нормали (vn из OBJ) — ту самую форму, которую игра показывает сглаживанием.
    Проходит через вершины оригинала и наружу не выпирает (Catmull-Clark уводил внутрь: углы граней торчали
    сквозь обмотку)."""
    # v1.9: ближайший треугольник ищется только среди граней, из которых сделана копия. Первая сборка v1.9 искала
    # по всей части — точки цевья липли к стволам, шейки к соседним деталям: дыры в бересте и полотенце
    key = (low.name, len(src), sum(src[:50]), sum(src[-50:]))
    if key not in _PH:
        me = low.data
        verts = [v.co.copy() for v in me.vertices]
        cn_all = [c.vector.copy() for c in me.corner_normals]
        polys, loops = [], []
        for k in src:
            p = me.polygons[k]
            polys.append(list(p.vertices))
            loops.append(list(p.loop_indices))
        _PH[key] = (BVHTree.FromPolygons(verts, polys), verts, polys, cn_all, loops)
    bvh, verts, polys, cn, loops = _PH[key]
    me = ob.data
    for v in me.vertices:
        loc, _, idx, _ = bvh.find_nearest(v.co)
        if loc is None or len(polys[idx]) != 3:
            continue
        a, b, c = (verts[k] for k in polys[idx])
        na, nb, nc = (cn[k] for k in loops[idx])
        v0, v1, v2 = b - a, c - a, loc - a
        d00, d01, d11 = v0.dot(v0), v0.dot(v1), v1.dot(v1)
        d20, d21 = v2.dot(v0), v2.dot(v1)
        den = d00 * d11 - d01 * d01
        if abs(den) < 1e-18:
            continue
        wb = (d11 * d20 - d01 * d21) / den
        wc = (d00 * d21 - d01 * d20) / den
        wa = 1 - wb - wc
        # Изгиб по рёбрам (как у PN-треугольников): выпуклость ребра i-j = -½·wᵢwⱼ·(Pⱼ−Pᵢ)·(Nᵢ−Nⱼ) вдоль нормали
        # грани. Длинные рёбра (> 6 см) не изгибаются — по длине труба прямая, а нормали её концов сглажены с
        # торцами (Phong по ним раздувал поверхность на 7–19 мм). Предел ±1.5 мм.
        fn_ = (b - a).cross(c - a)
        if fn_.length < 1e-12:
            continue
        fn_.normalize()
        if fn_.dot(na + nb + nc) < 0:
            fn_ = -fn_
        off = 0.0
        for (pi, ni, wi), (pj, nj, wj) in (((a, na, wa), (b, nb, wb)), ((b, nb, wb), (c, nc, wc)), ((c, nc, wc), (a, na, wa))):
            e = pj - pi
            if e.length > 0.06:
                continue
            off += -0.5 * wi * wj * e.dot(ni - nj) * 4.0 / 4.0
        off = max(-0.0015, min(0.0015, off))
        v.co = loc + fn_ * (off * alpha)
    me.update()


def rounded(ob, low, levels, src):
    """v1.9: копия без гранёности — подразделить и перенести на гладкую поверхность Phong. В v1.7–v1.8 копия
    трубы была с плоскими гранями, и гранёность ушла в запечённую нормаль — в игре стволы стали многоугольниками."""
    if levels > 0:
        subdivided(ob, levels)
    phong_smooth(ob, low, src)


def round_bvh(low, pred, name="proxy_round"):
    """BVH скруглённой копии граней (для обмоток и всего, что кладётся на поверхность лучами) — v1.9."""
    proxy = copy_faces(low, pred, name)
    rounded(proxy, low, 3, src_polys(low, pred))
    b = join_bvh([proxy])
    bpy.data.objects.remove(proxy)
    return b


def pitted_tubes(low, TUBES, rng):
    """v1.7: рельеф труб стволов геометрией, в размерах, которые держит текстура (19 px/см, пиксель ~0.5 мм):
    вмятины 4-9 мм шириной до 0.5 мм глубиной, гнёзда раковин Ø 1.5-2.5 мм (гуще у дула и снизу), сварной шов
    вдоль трубы (валик 2 мм с чешуйками — стволы из водопроводной трубы), глубокие продольные царапины.
    Узор считается в системе первого ствола: второй — его повёрнутая копия в тех же UV, и точки второго
    переводятся обратно (M⁻¹), поэтому рельеф у обоих одинаковый. В v1-v1.6 ямки были 0.25 мм (меньше пикселя)
    и у стволов разные — в одних пикселях смешивались два рисунка, трубы выглядели нарисованными.
    Цвет вершин — маски для texture_v1.py: R — ржавчина (ямки, дно вмятин), G — светлый металл (царапины,
    гребень шва), B — вмятины."""
    ob = copy_polys(low, TUBES, "hp_barrel_tubes")
    even_mesh(ob, 0.004)        # v1.9: мелкая сетка, потом на гладкую поверхность, потом ещё мельче
    rounded(ob, low, 0, src_polys(low, lambda i, c, n: i in TUBES))
    subdivided(ob, 1)
    for p in ob.data.polygons:
        p.use_smooth = True
    M, T, ca, cb, _ = barrel_transform(low)
    Minv = np.linalg.inv(M)
    mx = (ca.x + cb.x) / 2
    cx, cy = ca.x, ca.y
    R = 0.031
    rg = np.random.default_rng(7)
    dents = []
    for _ in range(6):   # v1.8: меньше и разного размера: 3–14 мм, глубина растёт с размером
        rr = 0.003 + 0.011 * rg.random() ** 2
        dents.append((rg.uniform(-np.pi, np.pi), rg.uniform(0.09, 0.42), rr, 0.00015 + rr * 0.04))
    scratches = [(rg.uniform(-np.pi, np.pi), rg.uniform(0.08, 0.36), rg.uniform(0.03, 0.08), rg.uniform(-0.08, 0.08))
                 for _ in range(7)]
    SEAM = np.radians(60)   # на первом стволе — сверху снаружи; на втором (поворот ≈ -99°) — сбоку снизу

    def fn(co, nr):
        pc = co.copy()
        b = co[:, 0] < mx
        pc[b] = (co[b] - T) @ Minv.T
        nc = nr.copy()
        nc[b] = nr[b] @ Minv.T
        dx, dy, z = pc[:, 0] - cx, pc[:, 1] - cy, pc[:, 2]
        r = np.hypot(dx, dy)
        th = np.arctan2(dy, dx)
        outer = (z > 0.075) & (r > 0.024) & (np.abs(nc[:, 2]) < 0.5)
        u = th * R
        d = np.zeros(len(co))
        rust = np.zeros(len(co))
        bright = np.zeros(len(co))
        dent = np.zeros(len(co))
        for t0, z0, rr, dp in dents:
            du = np.angle(np.exp(1j * (th - t0))) * R
            g = np.exp(-((du ** 2 + (z - z0) ** 2) / rr ** 2))
            d -= dp * g
            dent = np.maximum(dent, g)
            rim = np.exp(-((np.sqrt(du ** 2 + (z - z0) ** 2) - rr * 1.1) / (rr * 0.25)) ** 2)
            bright = np.maximum(bright, rim * 0.15)
        # раковины: ячейки ~2.2 мм, гуще у дула (z > 0.34), снизу (θ ≈ -90°) и в вмятинах
        bottom = np.exp(-(np.angle(np.exp(1j * (th + np.pi / 2))) / 0.9) ** 2)
        dens = 0.05 + 0.40 * NN.smooth((z - 0.36) / 0.06) + 0.20 * bottom + 0.35 * dent   # реже: россыпь читалась краской
        # круглые раковины: ячейки 2.2 мм, в каждой — чаша со случайным центром и радиусом 0.5-1.2 мм,
        # есть она или нет — по плотности (первый вариант на value noise давал квадратные пятна)
        # v1.8: раковины двух масштабов — мелкие (ячейка 2.6 мм, Ø 0.7–1.8 мм) и редкие крупные (ячейка 8 мм,
        # Ø 2.4–6 мм), размер по степенному закону (много мелких, мало крупных), гнёздами по низкочастотной маске.
        # В v1.7 все ямки были одного размера и ровной россыпью — «странно» (пользователь)
        nest = NN.smooth((NN.fbm(np.stack([u * 70, z * 70, np.full_like(z, 2.0)], -1), 3, 73) - 0.48) * 5)
        pit = np.zeros(len(co))

        def h(a, b, k):
            x = (a * 73856093) ^ (b * 19349663) ^ (k * 83492791)
            x = (x ^ (x >> 13)) * 1274126177
            return ((x ^ (x >> 16)) & 0xFFFF).astype(np.float64) / 65535

        for cell, rmin, rmax, prob, salt in ((0.0026, 0.00035, 0.0009, 0.85, 0), (0.008, 0.0012, 0.003, 0.35, 10)):
            gu, gz = np.floor(u / cell).astype(np.int64), np.floor(z / cell).astype(np.int64)
            for oa in (-1, 0, 1):
                for ob_ in (-1, 0, 1):
                    ca_, cb_ = gu + oa, gz + ob_
                    pu = (ca_ + h(ca_, cb_, 1 + salt)) * cell
                    pz = (cb_ + h(ca_, cb_, 2 + salt)) * cell
                    rad = rmin + (rmax - rmin) * h(ca_, cb_, 3 + salt) ** 2.5
                    on = h(ca_, cb_, 4 + salt) < dens * prob * (0.25 + 0.75 * nest)
                    dist = np.hypot((u - pu) * (1 + 0.25 * h(ca_, cb_, 6 + salt)), z - pz) / rad
                    bowl = np.clip(1 - dist ** 2, 0, 1) ** 0.7 * on
                    depth = (0.55 + 0.45 * h(ca_, cb_, 5 + salt)) * (0.6 + 0.8 * (rad - rmin) / (rmax - rmin + 1e-9))
                    pit = np.maximum(pit, bowl * np.clip(depth, 0, 1.3))
        d -= 0.00045 * pit
        rust = np.maximum(rust, np.clip(pit * 1.2, 0, 1))
        rust = np.maximum(rust, dent * 0.35)
        # сварной шов: валик Ø ~2 мм с чешуйками через 2.5 мм
        dus = np.angle(np.exp(1j * (th - SEAM))) * R
        zs = NN.smooth((z - 0.078) / 0.004) * NN.smooth((0.432 - z) / 0.004)
        ripple = 1 + 0.3 * np.sin(z * 2 * np.pi / 0.0025)
        bead = np.exp(-(dus / 0.0011) ** 2) * ripple * zs
        d += 0.00035 * bead
        bright = np.maximum(bright, np.exp(-(dus / 0.0005) ** 2) * zs * 0.8)
        rust = np.maximum(rust, np.exp(-((np.abs(dus) - 0.0016) / 0.0006) ** 2) * zs * 0.5)   # окалина у шва
        # продольные царапины
        for t0, z0, ln, sl in scratches:
            du = np.angle(np.exp(1j * (th - t0))) * R - sl * (z - z0)
            inz = NN.smooth((z - z0) / 0.006) * NN.smooth((z0 + ln - z) / 0.006)
            g = np.exp(-(du / 0.0006) ** 2) * inz
            d -= 0.00016 * g
            bright = np.maximum(bright, g)
        d *= outer
        rust *= outer
        bright *= outer
        dent *= outer
        cols = np.stack([rust, bright, dent], -1).astype(np.float32)
        return d, cols, np.full(len(co), IDS["metal"])
    cols, ids = displace(ob, fn)
    set_attrs_np(ob.data, cols, ids)
    return [ob]


KNOT = (-0.020, -0.118, -0.352)   # бок -x приклада (правый у стрелка; видно сбоку), ближе к шейке
ORN_Z = (-0.436, -0.404)
ORN_Y = (-0.150, -0.070)


def ornament_np(co):
    """Маска выжигания 0..1: два столбика точек и зигзаг между ними — бок +x (левый у стрелка, щека)."""
    x, y, z = co[:, 0], co[:, 1], co[:, 2]
    y0, y1 = ORN_Y
    zone = (x > 0.004) & (y > y0 - 0.003) & (y < y1 + 0.003) & (z > ORN_Z[0] - 0.004) & (z < ORN_Z[1] + 0.004)
    m = np.zeros(len(co))
    yy = np.round((y - y0) / 0.005) * 0.005 + y0
    okyy = (yy >= y0) & (yy <= y1)
    for zc in ORN_Z:  # точки Ø 2.4 мм через 5 мм
        d = np.hypot(z - zc, y - yy)
        m = np.maximum(m, NN.smooth((0.0012 - d) / 0.0004) * okyy)
    zm = (ORN_Z[0] + ORN_Z[1]) / 2
    ph = ((y - y0) / 0.008) % 2.0
    tri = np.where(ph < 1, ph, 2 - ph) - 0.5
    zz = zm + tri * 0.012
    m = np.maximum(m, NN.smooth((0.0007 - np.abs(z - zz)) / 0.0003) * ((y >= y0) & (y <= y1)))
    return m * zone


def copy_polys_idx(low, pred, name):
    """Копия граней по условию на полигон low (pred(p) -> bool)."""
    keep = {p.index for p in low.data.polygons if pred(p)}
    bm = bmesh.new()
    bm.from_mesh(low.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in keep], context="FACES")
    m2 = bpy.data.meshes.new(name)
    bm.to_mesh(m2)
    bm.free()
    ob = bpy.data.objects.new(name, m2)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def is_butt_end(i, c, n):
    """Затыльник приклада между железными пластинами: задняя грань острова 1 (v1.8; в v1.6 сюда попадали и
    пластины 5, 6 — у оригинала это красные железные уголки на пятке и носке)."""
    return i == 1 and n.z < -0.6 and c.z < -0.43


BUTT_PLATES = {5, 6}


def cloth_faces(low, isl_set):
    """Грани ткани (класс cloth) на островах isl_set, со сглаживанием класса по соседям (одиночные огрехи)."""
    cls = list(low["cls"])
    isl = low["isl"]
    me = low.data
    edge_f = {}
    for p in me.polygons:
        for ek in p.edge_keys:
            edge_f.setdefault(ek, []).append(p.index)
    for _ in range(2):
        new = list(cls)
        for p in me.polygons:
            nb = [q for ek in p.edge_keys for q in edge_f[ek] if q != p.index]
            if nb:
                c = sum(1 for q in nb if cls[q] == "cloth")
                if c >= 2 and cls[p.index] != "cloth":
                    new[p.index] = "cloth"
                elif c == 0 and cls[p.index] == "cloth":
                    new[p.index] = "wood"
        cls = new
    return {p.index for p in me.polygons if cls[p.index] == "cloth" and isl[p.index] in isl_set}


def cloth_band(low, faces, name, seed=5.0):
    """v1.8: крестовая обмотка на прикладе. У оригинала здесь выпуклая полоса ткани (своя геометрия), у v1-v1.7
    она была закрашена деревом — в игре читалась непонятной ступенькой («граница», пользователь). Теперь это
    полоса застиранного полотенца поверх выпуклости: плетение, поперечные складки, подшитые кромки со
    стежками, выцветшая кирпичная полоса посередине, бахрома на концах. Всё — рельефом."""
    bm = bmesh.new()
    bm.from_mesh(low.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in faces], context="FACES")
    # граница полосы — рёбра с одной гранью; расстояние до неё — «поперёк полосы»
    edge_pts = []
    for e in bm.edges:
        if len(e.link_faces) == 1:
            a, b = e.verts[0].co, e.verts[1].co
            for t in np.linspace(0, 1, 6):
                edge_pts.append(a.lerp(b, t))
    me2 = bpy.data.meshes.new(name)
    bm.to_mesh(me2)
    bm.free()
    ob = bpy.data.objects.new(name, me2)
    bpy.context.scene.collection.objects.link(ob)
    even_mesh(ob, 0.003)
    rounded(ob, low, 1, sorted(faces))
    for p in ob.data.polygons:
        p.use_smooth = True
    kd = kdtree.KDTree(len(edge_pts))
    for i, p in enumerate(edge_pts):
        kd.insert(p, i)
    kd.balance()
    n = len(ob.data.vertices)
    dist = np.array([kd.find(v.co)[2] for v in ob.data.vertices])
    half = max(np.percentile(dist, 97), 0.004)
    cw, cs, cd = np.array(lin(HEX["towel"])), np.array(lin(HEX["stripe"])), np.array(lin("9C927E"))

    def fn(co, nr):
        x, y, z = co[:, 0], co[:, 1], co[:, 2]
        e = dist / half   # 0 на кромке, 1 посередине
        weave = 0.00006 * np.sin(x * 9000 + z * 9000) * np.sin(y * 9000 - z * 9000)
        fold = 0.00045 * np.clip(NN.fbm(np.stack([x * 160, y * 160, z * 160], -1), 3, 91) - 0.45, 0, 1) * 3
        hem = 0.00035 * np.exp(-((dist - 0.0016) / 0.0007) ** 2)            # подшитая кромка — валик
        stitch = -0.00025 * np.exp(-((dist - 0.0016) / 0.00035) ** 2) * (np.sin(z * 2 * np.pi / 0.004 + y * 900) > 0.3)
        edge_drop = -0.0004 * NN.smooth((0.0008 - dist) / 0.0008)            # край ткани опускается к дереву
        d = 0.0006 + weave + fold + hem + stitch + edge_drop
        col = cw + (cd - cw) * (0.35 * NN.smooth((NN.fbm(co * 90, 3, 92) - 0.5) * 3))[:, None]
        stripe = NN.smooth((e - 0.62) / 0.06) * NN.smooth((0.88 - e) / 0.06)
        fade = 0.6 + 0.3 * NN.fbm(co * 60, 2, 93)
        col = col * (1 - (stripe * fade)[:, None]) + cs * (stripe * fade)[:, None]
        col = col * (1 - 0.35 * NN.smooth((0.0012 - dist) / 0.0012))[:, None]   # грязь по кромке
        return d, col.astype(np.float32), np.full(len(co), IDS["towel"])
    cols, ids = displace(ob, fn)
    set_attrs_np(ob.data, cols, ids)
    return ob


def plate_screws(low, plates, name):
    """v1.8: на железных уголках затыльника — по шурупу с прорезью (у оригинала там винты, у v1.6 — дерево)."""
    out = []
    bvh = bvh_of(low)
    for k in plates:
        ps = polys_of(low, {k})
        c = sum((p.center for p in ps), Vector()) / len(ps)
        for sx in (1, -1):
            hit, n, _, _ = bvh.ray_cast(Vector((sx * 0.2, c.y, c.z + 0.012)), Vector((-sx, 0, 0)), 0.4)
            if hit is None:
                continue
            n = n.normalized()
            a = Vector((0, 1, 0))
            t1 = n.cross(a).normalized()
            t2 = n.cross(t1)
            verts, faces = [], []
            nr_, nv_ = 10, 24
            for i in range(nr_ + 1):
                rr = 0.0024 * i / nr_
                for j in range(nv_):
                    ang = 2 * math.pi * j / nv_
                    dd = t1 * math.cos(ang) + t2 * math.sin(ang)
                    p = hit + dd * rr
                    hgt = 0.0008 * math.sqrt(max(1 - (rr / 0.0024) ** 2, 0))
                    slot = abs((p - hit).dot(t1)) < 0.00035 and rr < 0.0021
                    verts.append(p + n * (hgt - (0.0005 if slot else 0)))
            for i in range(nr_):
                for j in range(nv_):
                    j2 = (j + 1) % nv_
                    faces.append((i * nv_ + j, i * nv_ + j2, (i + 1) * nv_ + j2, (i + 1) * nv_ + j))
            out.append(new_mesh(f"{name}_{k}_{sx}", verts, faces, lin(HEX["nail"]), "nail",
                                outward=lambda p, h_=hit, n_=n: n_))
    return out


def wood_copy(low, name, butt=False, exclude=(), skip=frozenset()):
    """Дерево: копия, подразделена; волокна вдоль приклада, на прикладе — сучок и орнамент."""
    ob = copy_polys_idx(low, lambda p: low["isl"][p.index] not in exclude and p.index not in skip
                        and not (butt and is_butt_end(low["isl"][p.index], p.center, p.normal)), name)
    rounded(ob, low, 2, [p.index for p in low.data.polygons if low["isl"][p.index] not in exclude and p.index not in skip
                         and not (butt and is_butt_end(low["isl"][p.index], p.center, p.normal))])  # v1.9: без гранёности
    subdivided(ob, 1)
    knot = Vector(KNOT)
    if butt:
        def inside(c):
            orn = c.x > 0.002 and ORN_Y[0] - 0.008 < c.y < ORN_Y[1] + 0.008 and ORN_Z[0] - 0.012 < c.z < ORN_Z[1] + 0.012
            return orn or ((c - knot).length < 0.02 and c.x < 0)
        refine_zone(ob, inside, cuts=3)
    for p in ob.data.polygons:
        p.use_smooth = True

    def fn(co, nr):
        x, y, z = co[:, 0], co[:, 1], co[:, 2]
        g = NN.fbm(np.stack([x * 120, y * 120, z * 3], -1), 3, 31) * 2 - 1   # вдоль приклада медленнее — длинные волокна
        fib = NN.vnoise(np.stack([x * 1200, y * 1200, z * 50], -1), 32) * 2 - 1
        ring = np.sin((y * 260 + g * 3.0) * np.pi)
        d = 0.00018 * fib + 0.00012 * ring   # v1.8: волокна глубже
        # v1.8: волокна контрастнее — поздняя древесина заметно темнее (приклад читался «одного цвета»)
        late = NN.smooth((ring - 0.35) / 0.4)
        t = 0.55 * late + 0.2 * (g * 0.5 + 0.5) + 0.08 * (fib * 0.5 + 0.5)   # спокойнее: 0.85 давало «зебру»
        cw, cd = np.array(lin(HEX["wood"])), np.array(lin("7E6142"))
        cols = cw + (cd - cw) * t[:, None]
        ids = np.full(len(co), IDS["wood"])
        if butt:
            kd = np.linalg.norm(co - np.array(KNOT), axis=1)
            km = (kd < 0.016) & (x < -0.005)
            d += km * (0.0004 * np.exp(-(kd / 0.0045) ** 2) + 0.00012 * np.sin(kd * 2200) * np.exp(-(kd / 0.009) ** 2))
            # сучок: тёмное ядро Ø ~9 мм, светлое кольцо, тёмный ободок, свилеватость вокруг
            core = np.exp(-(kd / 0.0045) ** 2)
            rim = np.exp(-((kd - 0.0065) / 0.0012) ** 2)
            swirl = NN.smooth(np.sin(kd * 1600 + NN.vnoise(co * 400, 33) * 3) * 0.5 + 0.2) * np.exp(-(kd / 0.012) ** 2)
            w = (km * np.clip(core * 0.95 + rim * 0.7 + swirl * 0.35, 0, 1))[:, None]
            kc = np.array(lin("4E3624"))
            cols = cols * (1 - w) + kc * w
            b = ornament_np(co)
            d -= 0.0005 * b
            cb = np.array(lin(HEX["burn"]))
            # подпалина: тёмный ореол шире самой бороздки
            halo = NN.smooth(b * 3)[:, None] * 0.35
            cols = cols * (1 - halo) + cb * halo
            cols = cols * (1 - b[:, None]) + cb * b[:, None]
            ids = np.where(b > 0.5, IDS["burn"], ids)
        return d, cols.astype(np.float32), ids

    cols, ids = displace(ob, fn)
    set_attrs_np(ob.data, cols, ids)
    hp = [ob]
    if butt:
        hp.append(resin_drop(ob, knot))
    return hp


def resin_drop(wood, knot):
    """Капля смолы, стёкшая из сучка вниз: вытянутая полусфера на поверхности."""
    bvh = join_bvh([wood])
    hit, n, _, _ = bvh.ray_cast(knot + Vector((-0.05, -0.009, 0)), Vector((1, 0, 0)), 0.1)
    if hit is None:
        return None
    n = n.normalized()
    down = (Vector((0, -1, 0)) - n * n.dot(Vector((0, -1, 0)))).normalized()
    side = n.cross(down)
    verts, cols, faces = [], [], []
    nu, nv = 24, 12
    for i in range(nu + 1):
        a = math.pi * i / nu - math.pi / 2  # -90..90 по высоте
        for j in range(nv):
            b = 2 * math.pi * j / nv
            # вытянута вниз (капля), сплюснута по нормали
            x = math.cos(a) * math.cos(b) * 0.0024
            yv = math.sin(a) * (0.0060 if a > 0 else 0.0026)
            h = max(math.cos(a) * math.sin(b), -0.15) * 0.0013
            verts.append(hit + side * x + down * yv + n * h)
            core = math.cos(a) * max(math.sin(b), 0)
            cols.append(mix(lin(HEX["resin"]), lin(HEX["resin_core"]), core))
    for i in range(nu):
        for j in range(nv):
            j2 = (j + 1) % nv
            faces.append((i * nv + j, i * nv + j2, (i + 1) * nv + j2, (i + 1) * nv + j))
    ob = new_mesh("hp_resin", verts, faces, cols, "resin", outward=n)
    return ob


def towel_wrap(bvh, ax, s_a, s_b, th0, turns, width, name, seed):
    """Полоса полотенца: витки внахлёст, складки, вдоль — выцветшая кирпичная полоса, бахрома по краям."""
    TH = 0.0007   # застиранный лён: ~0.7 мм на слой; за 3.4 витка набирается ~2 мм

    def off(t, v, u_m):
        e = abs(v) * 2
        layer = 0.0004 + TH * (0.6 + 0.6 * t * turns)  # каждый следующий виток лежит на предыдущем
        edge = 1.0 - 0.7 * smooth01((e - 0.8) / 0.2)
        fold = 0.00045 * max(0.0, noise.noise(Vector((u_m * 70, v * 2, seed)))) ** 1.5
        weave = 0.00005 * math.sin(u_m * 9000) * math.sin(v * width * 9000)
        tuck = -0.0006 * smooth01((t - 0.96) / 0.04)  # конец подогнут под себя
        return layer * edge + fold + weave + tuck

    def col(t, v, u_m):
        c = lin(HEX["towel"])
        if 0.0 < v < 0.36:  # полоса вдоль ленты (~7 мм, как у полотенец сета), выцветшая неравномерно
            fade = 0.68 + 0.27 * (noise.noise(Vector((u_m * 30, v * 4, seed))) * 0.5 + 0.5)
            c = mix(c, lin(HEX["stripe"]), fade * smooth01((min(v - 0.0, 0.36 - v)) / 0.03))
        dirt = noise.noise(Vector((u_m * 25, v * 3, seed + 2))) * 0.5 + 0.5
        c = mix(c, lin("9C927E"), 0.35 * smooth01((dirt - 0.5) * 3))
        if abs(v) > 0.46:  # бахрома
            c = mix(c, lin("B8AE9A"), 0.5)
        return c

    def rag(t, u_m):
        return 1.0 + 0.05 * noise.noise(Vector((u_m * 90, seed, 0.2)))
    return wrap_strip(bvh, ax, s_a, s_b, th0, turns, width, off, name=name, color_fn=col, ident="towel",
                      width_fn=rag)


def stock_details(low, rng):
    """STOCK/GRIP: полотенце на шейке приклада (общая с GRIP форма) + гвоздик на конце."""
    W = {2}
    bvh = round_bvh(low, lambda i, c, n: i in (W | {3}))
    verts = [low.data.vertices[v].co.copy() for p in polys_of(low, W) for v in p.vertices]
    ax = Axis(verts, (0, 0, 1), (1, 0, 0)).refine(bvh)
    ob = towel_wrap(bvh, ax, -0.238, -0.196, math.radians(200), 3.4, 0.021, "hp_towel_wrist", 4.2)
    hp = [ob]
    end_th = math.radians(200) + 2 * math.pi * 3.4 - 0.25
    tbvh = join_bvh([ob])
    hit, d, _ = surf(tbvh, ax, -0.196, end_th)
    if hit is not None:
        hp.append(forged_nail(hit + d * 0.0003, d, 0.0021, "hp_nail_towel"))
    return hp


def crossbar_details(low):
    """v1.3: перемычка курков (MAIN, острова 5 и 27, одна копия) — главное, что видно в прицеле.
    Две обмотки бечёвкой по 4 витка между центральной стойкой (|x| < 0.013) и гайками (|x| > 0.023);
    под правую подсунут берёзовый лист — на задней грани (-z), обращённой к глазу; узел с хвостиками там же."""
    BAR = {5, 27}
    verts = [low.data.vertices[v].co.copy() for p in polys_of(low, BAR) for v in p.vertices]
    bar_bvh = round_bvh(low, lambda i, c, n: i in BAR)
    ax = Axis(verts, (1, 0, 0), (0, 1, 0), step=0.002).refine(bar_bvh)
    out = []
    # лист на задней грани у правой обмотки (x > 0 — левый бок стрелка; у правой руки лист не на виду)
    # v1.4: лист лежит вдоль перемычки — черешок под бечёвкой, кончик к центру. В v1.3 стоял поперёк под
    # бечёвкой: из-под неё торчал полукруг (screenshots/ingame_v1.3_aim_close.webp)
    p0 = ax.center(0.011)
    hit, n, _, _ = bar_bvh.ray_cast(Vector((0.011, p0.y + 0.0005, -0.2)), Vector((0, 0, 1)), 0.4)
    if hit is not None:
        out += leaf_mesh(hit + n * 0.0003, n, Vector((-1, -0.12, 0)), 0.019, "hp_leaf_bar", conform=bar_bvh)
    under = join_bvh([o for o in out if o.name == "hp_leaf_bar"]) if out else None
    r = 0.0008
    for side, xc in (("r", 0.0185), ("l", -0.0185)):
        for coil in range(4):
            pts = []
            for i in range(121):
                t = i / 120
                th = math.radians(-90) + 2 * math.pi * t
                s_ = xc + (coil - 1.5) * 2.1 * r + 0.4 * r * t
                hit, d, _ = surf(bar_bvh, ax, s_, th, far=0.05)
                if hit is None:
                    continue
                if under is not None:   # бечёвка поверх листа
                    h2, d2, _ = surf(under, ax, s_, th, far=0.05)
                    if h2 is not None and (h2 - ax.center(s_)).length > (hit - ax.center(s_)).length:
                        hit = h2
                pts.append(hit + d * (r * 0.9))
            if len(pts) > 3:
                out.append(tube_mesh(pts + pts[:2], r, f"hp_bar_twine_{side}{coil}", lin(HEX["twine"]), "twine",
                                     twist=0.9, col_fn=twine_col))
    # v1.4: узла на видимой грани нет — в игре тень между петлями читалась чёрной дырой. Узел — сверху (+y)
    th_k = 0.0   # e1 = +y
    hit, d, _ = surf(bar_bvh, ax, 0.0185, th_k, far=0.05)
    if hit is not None:
        for sgn in (-1, 1):
            tail = [hit + d * (r * (2.0 - 1.0 * t)) + Vector((sgn * 0.002 * t, 0, -0.004 * t)) for t in (i / 15 for i in range(16))]
            out.append(tube_mesh(tail, r * 0.85, f"hp_bar_tail_{sgn}", lin(HEX["twine"]), "twine", twist=0.9, col_fn=twine_col))
    return out


def lever_details(low, rng):
    """MAIN: колодка как есть + полоса полотенца на рукояти рычага (остров 8, торец 31)."""
    hp = []
    base = copy_polys(low, set(range(1, 100)), "hp_main")
    set_attrs(base.data, lin(HEX["metal"]), "metal")
    hp.append(base)
    H = {8, 31}
    verts = [low.data.vertices[v].co.copy() for p in polys_of(low, H) for v in p.vertices]
    ax = Axis(verts, (1, 0, 0), (0, 1, 0), step=0.002)
    bvh = round_bvh(low, lambda i, c, n: i in H)
    ob = towel_wrap(bvh, ax, 0.074, 0.122, math.radians(90), 3.2, 0.016, "hp_towel_lever", 9.1)
    hp.append(ob)
    # лист на верхней планке хвоста колодки (остров 16). v1.3: был шире планки (2.1 см на 2.4) и под углом —
    # свисал с краёв, свисающее не запекалось («порвался»). Теперь 2.2 см, строго вдоль планки.
    top = bvh_of(low, {16})
    hit, n, _, _ = top.ray_cast(Vector((0.0, 0.2, -0.108)), Vector((0, -1, 0)), 0.4)
    if hit is not None:
        hp += leaf_mesh(hit + n * 0.0003, n, Vector((0.0, 0, 1)), 0.022, "hp_leaf_top", conform=bvh_of(low))
    else:
        print("leaf_top missed", flush=True)
    hp += crossbar_details(low)
    return hp


# ----------------------------------------------------------------- bake
def bake_material():
    m = bpy.data.materials.new("hp")
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL")
    bs = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    ac = N.new("ShaderNodeVertexColor")
    ac.layer_name = "col"
    ai = N.new("ShaderNodeVertexColor")
    ai.layer_name = "idc"
    geo = N.new("ShaderNodeNewGeometry")
    mp = N.new("ShaderNodeMapRange")
    mp.data_type = "FLOAT_VECTOR"
    mp.inputs[7].default_value = POS_LO
    mp.inputs[8].default_value = POS_HI
    L.new(geo.outputs["Position"], mp.inputs["Vector"])
    em = {k: N.new("ShaderNodeEmission") for k in ("color", "id", "pos")}
    L.new(ac.outputs["Color"], em["color"].inputs["Color"])
    L.new(ai.outputs["Color"], em["id"].inputs["Color"])
    L.new(mp.outputs["Vector"], em["pos"].inputs["Color"])
    m["em"] = True
    return m, out, bs, em


def set_pass(mat, which):
    m, out, bs, em = mat
    L = m.node_tree.links
    for l in list(out.inputs["Surface"].links):
        L.remove(l)
    L.new((bs if which == "view" else em[which]).outputs[0], out.inputs["Surface"])


def setup_cycles(scene):
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.use_denoising = False
    scene.cycles.samples = 1


def low_subset(low, islands, name):
    """Копия low-poly только с гранями нужных островов (данные копируются целиком, нормали и UV свои)."""
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


def island_raster(part, size):
    """Номер острова на каждый пиксель (uv/<part>_ids.png, без PIL — через bpy)."""
    im = bpy.data.images.load(str(HERE / "uv" / f"{part}_ids.png"))
    im.colorspace_settings.name = "Non-Color"
    w = im.size[0]
    px = np.array(im.pixels[:], np.float32).reshape(w, w, 4)
    ids = np.round(px[..., 0] * 255).astype(np.int32) + np.round(px[..., 1] * 255).astype(np.int32) * 256
    k = size // w if size >= w else 1
    if size != w:
        ids = np.repeat(np.repeat(ids, k, 0), k, 1)
    return ids  # строки снизу вверх, как pixels Blender


def bake(low, hp, part, size, extr, groups=None):
    """groups: [(острова, [high-poly])] — каждая группа печётся отдельно и кладётся по своей маске островов;
    последняя группа без островов (None) — всё остальное. Нужно, когда острова делят копии геометрии
    (оба ствола в одном месте UV): иначе на трубу ствола попадает то, что лежит у его копии рядом."""
    scene = bpy.context.scene
    setup_cycles(scene)
    mat = bake_material()
    for o in hp:
        o.data.materials.clear()
        o.data.materials.append(mat[0])
    if scene.world is None:
        scene.world = bpy.data.worlds.new("bake")
    scene.world.light_settings.distance = 0.012   # AO: 1.2 см (с 3 см лист и узлы давали тёмный ореол)
    lm = bpy.data.materials.new("bake_target")
    lm.use_nodes = True
    tex = lm.node_tree.nodes.new("ShaderNodeTexImage")
    lm.node_tree.nodes.active = tex
    if not groups:
        groups = [(None, hp)]
    lows = []
    for gi, (isls, ghp) in enumerate(groups):
        lg = low if isls is None else low_subset(low, isls, f"low_{part}_g{gi}")
        lg.data.materials.clear()
        lg.data.materials.append(lm)
        for attr in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission",
                     "visible_volume_scatter", "visible_shadow"):
            setattr(lg, attr, False)
        lows.append(lg)
    raster = island_raster(part, size) if len(groups) > 1 else None
    bk = scene.render.bake
    bk.use_selected_to_active = True
    bk.use_cage = False
    bk.cage_extrusion = extr
    bk.max_ray_distance = extr * 2.5
    bk.target = "IMAGE_TEXTURES"
    bk.normal_space = "TANGENT"
    bk.normal_r, bk.normal_g, bk.normal_b = "POS_X", "POS_Y", "POS_Z"   # OpenGL, как в Unity
    OUT.mkdir(exist_ok=True)
    margin = max(16, size // 64)
    for name, kind, shader, samples in (("normal", "NORMAL", "view", 4), ("ao", "AO", "view", 48),
                                        ("color", "EMIT", "color", 4), ("id", "EMIT", "id", 1),
                                        ("pos", "EMIT", "pos", 1)):
        set_pass(mat, shader)
        scene.cycles.samples = samples
        # id и положение — без сглаживания пикселей (иначе на границе bark/metal выходит «wood»)
        scene.cycles.filter_width = 0.01 if name in ("id", "pos") else 1.5
        bk.margin_type = "ADJACENT_FACES" if name in ("id",) else "EXTEND"
        result = None
        for gi, ((isls, ghp), lg) in enumerate(zip(groups, lows)):
            img = bpy.data.images.new(f"bake_{part}_{name}_{gi}", size, size, alpha=False, float_buffer=True)
            img.colorspace_settings.name = "Non-Color"
            tex.image = img
            bpy.ops.object.select_all(action="DESELECT")
            for o in ghp:
                o.select_set(True)
            lg.select_set(True)
            bpy.context.view_layer.objects.active = lg
            print(f"baking {part} {name} group {gi} ...", flush=True)
            bpy.ops.object.bake(type=kind, use_clear=True, margin=margin)
            px = np.array(img.pixels[:], np.float32).reshape(size, size, 4)
            if result is None:
                result = px
            if isls is not None:
                # маска островов группы + 4 px наружу (не залезая на чужие острова): край без чужой каймы
                m = np.isin(raster, list(isls))
                g = m.copy()
                for _ in range(4):
                    g = g | np.roll(g, 1, 0) | np.roll(g, -1, 0) | np.roll(g, 1, 1) | np.roll(g, -1, 1)
                m = m | (g & (raster == 0))
                result[m] = px[m]
            else:
                keep = np.zeros((size, size), bool)
                for isls2, _ in groups:
                    if isls2 is not None:
                        k2 = np.isin(raster, list(isls2))
                        g = k2.copy()
                        for _ in range(4):
                            g = g | np.roll(g, 1, 0) | np.roll(g, -1, 0) | np.roll(g, 1, 1) | np.roll(g, -1, 1)
                        keep |= k2 | (g & (raster == 0))
                result[~keep] = px[~keep]
        if name == "pos":
            q = np.clip(result[..., :3], 0, 1) * 65535
            outs = (("poshi", np.floor(q / 256) / 255), ("poslo", (q % 256) / 255))
        else:
            arr = result[..., :3]
            if name == "color":   # цвета вершин линейные — в PNG пишем sRGB
                arr = np.clip(arr, 0, 1) ** (1 / 2.2)
            outs = ((name, arr),)
        for nm, arr in outs:
            im2 = bpy.data.images.new(f"{part}_{nm}", size, size, alpha=False)
            im2.colorspace_settings.name = "Non-Color"
            buf = np.ones((size, size, 4), np.float32)
            buf[..., :3] = arr
            im2.pixels[:] = buf.ravel()
            im2.filepath_raw = str(OUT / f"{part}_{nm}.png")
            im2.file_format = "PNG"
            im2.save()
        print("  ->", part, name, flush=True)
    set_pass(mat, "view")


def build(part, rng):
    low = load_low(part)
    if part == "barrel":
        hp = fore_end(low, rng)
    elif part == "main":
        hp = lever_details(low, rng)
    elif part == "stock":
        # v1.6: спусковая скоба (остров 4) - железо, как у оригинала (была деревом: весь приклад копировался
        # деревом целиком); затыльник (5, 6) - дерево в торец (на нём лежали продольные волокна)
        # v1.8: уголки затыльника (5, 6) — железо с шурупами; крестовая полоса ткани на острове 1 — обмотка
        band = cloth_faces(low, {1})
        hp = wood_copy(low, "hp_stock_wood", butt=True, exclude={4} | BUTT_PLATES, skip=band) + stock_details(low, rng)
        hp.append(metal_copy(low, {4} | BUTT_PLATES, "hp_stock_guard"))
        hp.append(cloth_band(low, band, "hp_stock_band"))
        hp += plate_screws(low, BUTT_PLATES, "hp_screw")
        cen = [p.center for p in low.data.polygons if is_butt_end(low["isl"][p.index], p.center, p.normal)]
        c0 = sum(cen, Vector()) / len(cen)
        hp.append(end_grain(low, is_butt_end, "hp_stock_butt", (c0.x + 0.003, c0.y - 0.012, c0.z),
                            "wood", 53, cracks=((1.2, 0.03), (3.6, 0.02))))
    elif part == "grip":
        # GRIP занимает то же место, что шейка STOCK: обмотку строим по прикладу, дерево — своё
        stock = load_low("stock")
        # v1.6: скоба GRIP (остров 3) - железо; торец рукояти (4) - дерево в торец
        hp = wood_copy(low, "hp_grip_wood", exclude={3, 4}) + stock_details(stock, rng)
        hp.append(metal_copy(low, {3}, "hp_grip_guard"))
        cen = [p.center for p in low.data.polygons if low["isl"][p.index] == 4]
        c0 = sum(cen, Vector()) / len(cen)
        hp.append(end_grain(low, lambda i, c, n: i == 4, "hp_grip_end", (c0.x, c0.y - 0.006, c0.z), "wood", 54,
                            cracks=((0.9, 0.018),), level=4))
        bpy.data.objects.remove(stock)
    return low, [o for o in hp if o is not None]


def look(low, hp, part, views):
    """Быстрый просмотр high-poly (цвета вершин, Eevee) — проверить форму до запекания."""
    scene = bpy.context.scene
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"
    mat = bake_material()
    L = mat[0].node_tree.links
    L.new(next(n for n in mat[0].node_tree.nodes if n.type == "VERTEX_COLOR" and n.layer_name == "col").outputs[0],
          mat[2].inputs["Base Color"])
    mat[2].inputs["Roughness"].default_value = 0.6
    set_pass(mat, "view")
    for o in hp:
        o.data.materials.clear()
        o.data.materials.append(mat[0])
    low.hide_render = True
    w = scene.world or bpy.data.worlds.new("w")
    scene.world = w
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.5, 0.52, 0.55, 1)
    bpy.ops.object.light_add(type="SUN", rotation=(math.radians(-40), math.radians(-30), 0))
    bpy.context.active_object.data.energy = 3.0
    bpy.ops.object.camera_add()
    cam = bpy.context.active_object
    scene.camera = cam
    cam.data.clip_start = 0.002
    scene.render.resolution_x, scene.render.resolution_y = 900, 600
    for name, eye, tgt, lens in views:
        cam.location = Vector(eye)
        cam.rotation_euler = (Vector(tgt) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = lens
        scene.render.filepath = str(OUT / f"look_{part}_{name}.png")
        bpy.ops.render.render(write_still=True)


# камеры просмотра: в координатах OBJ y — вверх; камера «вверх» = +y
LOOKS = {
    "barrel": [("left", (-0.35, -0.02, 0.32), (0, -0.035, 0.32), 50),
               ("under", (-0.12, -0.25, 0.30), (0, -0.04, 0.32), 50),
               ("knot", (0.12, -0.04, 0.24), (0.02, -0.04, 0.24), 50),
               ("sleeve", (0.10, 0.12, 0.05), (0.0, 0.0, 0.18), 50),
               ("cap", (0.0, -0.04, 0.60), (0.0, -0.04, 0.42), 50),
               ("tubes", (0.16, 0.06, 0.36), (0.0, 0.0, 0.30), 50)],
    "main": [("lever", (0.10, 0.10, 0.10), (0.09, -0.04, -0.054), 50),
             ("bar", (0.0, 0.03, -0.20), (0.0, 0.0, -0.05), 50),
             ("top", (0.0, 0.12, -0.12), (0.0, -0.02, -0.06), 50)],
    "stock": [("left", (-0.55, -0.09, -0.26), (0, -0.09, -0.26), 50),
              ("wrist", (-0.15, -0.05, -0.15), (0, -0.09, -0.22), 50),
              ("butt", (-0.18, -0.11, -0.40), (0, -0.11, -0.40), 50),
              ("buttend", (0.05, -0.10, -0.70), (0, -0.10, -0.45), 50),
              ("band", (0.30, -0.08, -0.33), (0, -0.09, -0.33), 50)],
    "grip": [("left", (-0.4, -0.09, -0.15), (0, -0.09, -0.15), 50),
             ("end", (-0.12, -0.25, -0.40), (0, -0.12, -0.25), 50)],
}


TUBE_ISLANDS = {1, 2, 17, 18}   # трубы стволов: обе копии в одних UV (uv/islands.md)
SIZES = {"barrel": 2048, "main": 2048, "stock": 2048, "grip": 1024}
EXTR = {"barrel": 0.0045, "main": 0.004, "stock": 0.004, "grip": 0.004}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    part = argv[argv.index("--part") + 1] if "--part" in argv else "all"
    parts = list(SIZES) if part == "all" else [part]
    for p in parts:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        rng = random.Random(11)
        random.seed(11)
        low, hp = build(p, rng)
        print(p, "high-poly:", {o.name: len(o.data.polygons) for o in hp}, flush=True)
        size = int(argv[argv.index("--size") + 1]) if "--size" in argv else SIZES[p]
        if "--blend" in argv:
            OUT.mkdir(exist_ok=True)
            bpy.ops.wm.save_as_mainfile(filepath=str(OUT / f"highpoly_{p}.blend"))
        if "--look" in argv:
            OUT.mkdir(exist_ok=True)
            look(low, hp, p, LOOKS[p])
        elif "--nobake" not in argv:
            groups = None
            if p == "barrel":   # трубы стволов (общие острова) — только со своими манжетами
                tub = [o for o in hp if o.name.startswith(("hp_barrel_tubes", "hp_sleeve"))]
                groups = [(TUBE_ISLANDS, tub), (None, [o for o in hp if o not in tub])]
            bake(low, hp, p, size, EXTR[p], groups)
    print("done", flush=True)


if __name__ == "__main__":
    main()
