"""Sauna Boiler: high-poly детали поверх Furnace и запекание на его развёртку.

Что смоделировано (всё — геометрия, ничего не нарисовано):
  shell    копия low-poly, сглаженная Catmull-Clark (4 уровня) и смещённая: листы бака внахлёст
           (ступенька на швах), вмятины, следы молота; рамка-накладка вокруг проёма топки
  hoops    пять плоских обручей по профилю бака, нижний разорван топкой; замки внахлёст
  rivets   клёпки: по обручам, вдоль вертикальных швов листов, по рамке топки, по краю крышки
  slats    ограждение: горизонтальные рейки рядами вокруг основания, облегают его бугры на
           постоянном отступе; стыки вразбежку, выпавшие рейки; кованые гвозди по концам;
           две нитки проволоки со скруткой
  logs     берёзовые поленья на полу топки (целые и колотое), торцы отдельным материалом
  embers   угли шестью гнёздами на золе; зола — бугристая подсыпка
  stones   куча базальта на крышке: камни уложены по высотной карте, второй ярус сверху
  ladle    резной ковш на гвозде, прижат к баку; plug/rag — деревянная затычка в тряпке

Запуск (из корня репозитория):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/furnace/bake_furnace.py -- [--size 2048] [--blend] [--nobake] [--preview]

Пишет bake/{normal,ao,id,tone}.png, bake/pos.npz, bake/layout.json; --blend → bake/highpoly.blend;
--preview → bake/hp_preview_*.png (рендер high-poly в условных цветах, не игровой кадр).
id.png: R = id * 12 + 6 (layout.IDS). tone.png: R — случайный тон детали, G/B — координаты детали.
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

HERE = Path(__file__).resolve().parent
OUT = HERE / "bake"
sys.path.insert(0, str(HERE))
import layout as L  # noqa: E402

OBJ = HERE / "originals" / "furnace.obj"
AXIS = Vector((L.CX, 0.0, L.CZ))
REG = ["tank", "drum", "wall", "floor", "under", "hole", "coal"]
VIEW_COL = {"tank": (0.16, 0.15, 0.14), "hoop": (0.1, 0.09, 0.09), "rivet": (0.22, 0.2, 0.19),
            "slat": (0.64, 0.55, 0.4), "nail": (0.1, 0.09, 0.08), "wire": (0.25, 0.14, 0.08),
            "drum": (0.2, 0.13, 0.09), "bark": (0.8, 0.78, 0.72), "logend": (0.7, 0.55, 0.35),
            "ember": (0.9, 0.3, 0.05), "ash": (0.3, 0.29, 0.28), "stone": (0.2, 0.2, 0.21),
            "ladle": (0.45, 0.33, 0.22), "plug": (0.5, 0.38, 0.26), "rag": (0.75, 0.72, 0.65),
            "frame": (0.09, 0.08, 0.08), "wall": (0.05, 0.045, 0.04), "under": (0.1, 0.1, 0.1)}


def er(th):
    return Vector((math.sin(th), 0.0, math.cos(th)))


def et(th):
    return Vector((math.cos(th), 0.0, -math.sin(th)))


def theta_of(p):
    return math.atan2(p.x - L.CX, p.z - L.CZ)


def radius_of(p):
    return math.hypot(p.x - L.CX, p.z - L.CZ)


def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def ang_diff(a, b):
    return (a - b + math.pi) % (2 * math.pi) - math.pi


# ---------------------------------------------------------------- low-poly
def load_low():
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="Y", up_axis="Z")   # оси как в OBJ
    low = bpy.context.selected_objects[0]
    low.name = "lowpoly"
    bpy.context.view_layer.objects.active = low
    bpy.ops.mesh.customdata_custom_splitnormals_clear()
    for p in low.data.polygons:
        p.use_smooth = True
    low.data.update()
    return low


def regions(me):
    """Область для каждого полигона: остров развёртки → tank / drum / wall / floor / under / hole / coal."""
    uv = me.uv_layers.active.data
    parent = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    keys = []
    for p in me.polygons:
        ks = [(me.loops[li].vertex_index, round(uv[li].uv.x, 5), round(uv[li].uv.y, 5)) for li in p.loop_indices]
        for k in ks[1:]:
            parent[find(k)] = find(ks[0])
        keys.append(ks[0])
    isl = {}
    for p, k in zip(me.polygons, keys):
        isl.setdefault(find(k), []).append(p.index)
    out = [None] * len(me.polygons)
    for ps in isl.values():
        ys = [me.vertices[v].co.y for i in ps for v in me.polygons[i].vertices]
        ny = sum(me.polygons[i].normal.y for i in ps) / len(ps)
        outward = sum(me.polygons[i].normal.dot((me.polygons[i].center - AXIS).normalized()) for i in ps) / len(ps)
        y0, y1 = min(ys), max(ys)
        if len(ps) > 700:
            r = "tank"
        elif y0 < 0.02 and y1 > 0.4:
            r = "drum"
        elif ny < -0.8 and y1 < 0.05:
            r = "under"
        elif y0 > 1.3:
            r = "hole"
        elif ny > 0.8 and y1 < 0.7:
            r = "floor"
        elif y1 < 0.62:
            r = "coal"
        else:
            assert outward < 0, (len(ps), y0, y1, outward)
            r = "wall"
        for i in ps:
            out[i] = r
    return out


def sub_mesh(low, reg, keep, name):
    """Копия low-poly только с полигонами областей keep; material_index = номер области."""
    bm = bmesh.new()
    bm.from_mesh(low.data)
    bm.faces.ensure_lookup_table()
    for f in bm.faces:
        f.material_index = REG.index(reg[f.index])
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if reg[f.index] not in keep], context="FACES")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


# ---------------------------------------------------------------- high-poly container
class HP:
    """Копит геометрию по материалам: mat -> bmesh со слоем цвета tone."""

    def __init__(self):
        self.bms = {}

    def bm(self, mat):
        if mat not in self.bms:
            b = bmesh.new()
            b.loops.layers.float_color.new("tone")
            self.bms[mat] = b
        return self.bms[mat]

    def add(self, mat, src, M=None, tone=0.5, tone_fn=None):
        """Перенести временный bmesh src в материал mat. tone — красный канал (тон детали),
        tone_fn(local_co) -> (g, b) — координаты детали."""
        dst = self.bm(mat)
        lay = dst.loops.layers.float_color["tone"]
        vm = {}
        for v in src.verts:
            vm[v] = dst.verts.new(M @ v.co if M else v.co)
        gb = {v: (tone_fn(v.co) if tone_fn else (0.0, 0.0)) for v in src.verts}
        for f in src.faces:
            try:
                nf = dst.faces.new([vm[v] for v in f.verts])
            except ValueError:
                continue
            nf.smooth = True
            for lp, v in zip(nf.loops, f.verts):
                lp[lay] = (tone, gb[v][0], gb[v][1], 1.0)
        src.free()

    def objects(self, mats):
        obs = []
        for mat, b in self.bms.items():
            me = bpy.data.meshes.new("hp_" + mat)
            b.normal_update()
            b.to_mesh(me)
            b.free()
            me.materials.append(mats[mat])
            if hasattr(me, "set_sharp_from_angle"):
                me.set_sharp_from_angle(angle=math.radians(42))
            ob = bpy.data.objects.new("hp_" + mat, me)
            bpy.context.scene.collection.objects.link(ob)
            obs.append(ob)
        return obs


# ---------------------------------------------------------------- primitives
def rounded_box(sx, sy, sz, bevel):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz))
    bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=2, profile=0.5, affect="EDGES")
    return bm


def dome(r, h, u=12, v=6):
    """Шляпка: приплюснутая сфера, сидит на z = 0, высота h."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=1.0)
    for vt in bm.verts:
        vt.co = Vector((vt.co.x * r, vt.co.y * r, vt.co.z * h))
    return bm


def stone(rng, sx, sy, sz, sub=3):
    """Колотый камень: шар с шумом, срезанный несколькими плоскостями."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    off = Vector((rng.uniform(0, 90), rng.uniform(0, 90), rng.uniform(0, 90)))
    planes = []
    for _ in range(rng.randint(4, 7)):
        n = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))).normalized()
        planes.append((n, rng.uniform(0.62, 0.9)))
    for v in bm.verts:
        d = v.co.normalized()
        p = d * (1 + 0.25 * noise.noise(d * 1.3 + off) + 0.08 * noise.noise(d * 3.4 + off))
        for n, k in planes:
            t = p.dot(n)
            if t > k:
                p -= n * (t - k) * 0.92
        v.co = Vector((p.x * sx, p.y * sy, p.z * sz))
    return bm


def tube(points, r, segs=6, closed=False):
    bm = bmesh.new()
    n = len(points)
    rings = []
    for i, p in enumerate(points):
        a = points[(i - 1) % n] if (closed or i > 0) else p
        b = points[(i + 1) % n] if (closed or i < n - 1) else p
        t = (b - a).normalized()
        side = t.cross(Vector((0, 1, 0)))
        side = side.normalized() if side.length > 1e-4 else Vector((1, 0, 0))
        up = side.cross(t).normalized()
        rings.append([bm.verts.new(p + (side * math.cos(2 * math.pi * k / segs) + up * math.sin(2 * math.pi * k / segs)) * r)
                      for k in range(segs)])
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for k in range(segs):
            bm.faces.new([b[k], b[(k + 1) % segs], a[(k + 1) % segs], a[k]])
    return bm


def log_mesh(rng, length, radius, half=False, rings=22, segs=28):
    """Полено вдоль локальной X. Возвращает (кора, торцы, скол). tone: G = вдоль, B = вокруг."""
    bark, ends = bmesh.new(), bmesh.new()
    off = Vector((rng.uniform(0, 50), rng.uniform(0, 50), rng.uniform(0, 50)))
    a0, a1 = (0.0, math.pi) if half else (0.0, 2 * math.pi)
    grid = []
    for i in range(rings + 1):
        x = (i / rings - 0.5) * length
        row = []
        for k in range(segs + (1 if half else 0)):
            a = a0 + (a1 - a0) * k / segs
            d = Vector((0, math.cos(a), math.sin(a)))
            rr = radius * (1 + 0.05 * noise.noise(Vector((x * 6, d.y * 2, d.z * 2)) + off)
                           + 0.025 * noise.noise(Vector((x * 30, d.y * 9, d.z * 9)) + off))
            row.append(bark.verts.new(Vector((x, d.y * rr, d.z * rr))))
        grid.append(row)
    m = len(grid[0])
    for i in range(rings):
        for k in range(m if not half else m - 1):
            bark.faces.new([grid[i + 1][k], grid[i + 1][(k + 1) % m], grid[i][(k + 1) % m], grid[i][k]])
    for i in (0, rings):                               # торцы: веер от центра
        x = (i / rings - 0.5) * length
        c = ends.verts.new(Vector((x + (0.004 if i else -0.004), 0, radius * (0.42 if half else 0))))
        rim = [ends.verts.new(v.co.copy()) for v in grid[i]]
        for k in range(len(rim) if not half else len(rim) - 1):
            f = [c, rim[k], rim[(k + 1) % len(rim)]]
            ends.faces.new(f[::-1] if i else f)
    split = None
    if half:                                           # плоскость скола: полоса между краями
        split = bmesh.new()
        prev = None
        for i in range(rings + 1):
            p0, p1 = grid[i][0].co, grid[i][-1].co
            row = []
            for s in range(7):
                p = p0.lerp(p1, s / 6)
                p.z += 0.004 * noise.noise(Vector((p.x * 14, p.y * 40, 0)) + off)
                row.append(split.verts.new(p))
            if prev:
                for s in range(6):
                    split.faces.new([prev[s + 1], row[s + 1], row[s], prev[s]])
            prev = row
    return bark, ends, split


# ---------------------------------------------------------------- shell (бак, основание, топка)
def build_shell(low, reg, mats, info):
    src = sub_mesh(low, reg, ("tank", "drum", "wall", "floor", "under"), "shell_src")
    mod = src.modifiers.new("ss", "SUBSURF")
    mod.subdivision_type = "CATMULL_CLARK"
    mod.levels = 4
    deps = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(src.evaluated_get(deps))
    bpy.data.objects.remove(src)
    me.name = "hp_shell"
    nv, npoly = len(me.vertices), len(me.polygons)
    co = np.empty(nv * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3).astype(np.float64)
    nrm = np.empty(nv * 3, np.float32)
    me.vertices.foreach_get("normal", nrm)
    nrm = nrm.reshape(-1, 3).astype(np.float64)
    pm = np.empty(npoly, np.int32)
    me.polygons.foreach_get("material_index", pm)
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lv)
    ls = np.empty(npoly, np.int32)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(npoly, np.int32)
    me.polygons.foreach_get("loop_total", lt)
    assert (lt == 4).all()
    quad = lv[ls[:, None] + np.arange(4)[None, :]]
    T = REG.index("tank")
    vtank = np.zeros(nv, bool)
    vtank[quad[pm == T].ravel()] = True
    vother = np.zeros(nv, bool)
    vother[quad[pm != T].ravel()] = True

    # гладкая поверхность до смещений — по ней садятся все детали
    bvh = BVHTree.FromPolygons([Vector(c) for c in co], [tuple(q) for q in quad[(pm == T) | (pm == REG.index("drum"))]])
    bvh_in = BVHTree.FromPolygons([Vector(c) for c in co], [tuple(q) for q in quad[(pm == REG.index("wall")) | (pm == REG.index("floor"))]])

    th = np.arctan2(co[:, 0] - L.CX, co[:, 2] - L.CZ)
    y = co[:, 1]
    erad = np.stack([np.sin(th), np.zeros(nv), np.cos(th)], 1)
    facing = (nrm * erad).sum(1)
    t0 = math.radians(L.OPENING[0])
    near = (np.abs((th - t0 + np.pi) % (2 * np.pi) - np.pi) < math.radians(55)) & (y > 0.5) & (y < 0.97)
    lip = vtank & near & (facing < 0.35) & (np.hypot(co[:, 0] - L.CX, co[:, 2] - L.CZ) < 0.46)
    lip_idx = np.nonzero(lip)[0]
    kd = kdtree.KDTree(len(lip_idx))
    for i in lip_idx:
        kd.insert(Vector(co[i]), int(i))
    kd.balance()
    # проём топки: границы по углу и высоте (для обруча, копоти и свечения в texture_furnace)
    edge = lip & (facing > 0.0)
    info["opening"] = {"th0": float(np.degrees(th[edge].min())), "th1": float(np.degrees(th[edge].max())),
                       "y0": float(y[edge].min()), "y1": float(y[edge].max()),
                       "center": [float(v) for v in co[edge].mean(0)]}
    print("opening", info["opening"], flush=True)

    # расстояние до кромки проёма, сглаженное по сетке: край накладки ровный, а не рваный
    dist = np.full(nv, 0.2)
    for i in np.nonzero(near & vtank)[0]:
        dist[i] = 0.0 if lip[i] else kd.find(Vector(co[i]))[2]
    e = np.concatenate([quad[:, [0, 1]], quad[:, [1, 2]], quad[:, [2, 3]], quad[:, [3, 0]]])
    e = e[(near & vtank)[e].all(1)]
    cnt = np.zeros(nv)
    np.add.at(cnt, e[:, 0], 1)
    np.add.at(cnt, e[:, 1], 1)
    movable = (near & vtank) & (cnt > 0)
    for _ in range(60):
        acc = np.zeros(nv)
        np.add.at(acc, e[:, 0], dist[e[:, 1]])
        np.add.at(acc, e[:, 1], dist[e[:, 0]])
        dist = np.where(movable, 0.5 * dist + 0.5 * acc / np.maximum(cnt, 1), dist)

    rng = random.Random(11)
    dents = []
    for _ in range(16):
        yy = rng.uniform(0.62, 1.45)
        dents.append((rng.uniform(-math.pi, math.pi), yy, rng.uniform(0.035, 0.085), rng.uniform(0.004, 0.009)))
    plate_rand = {}
    tone = np.zeros((nv, 4), np.float32)
    tone[:, 3] = 1.0
    frame_v = np.zeros(nv, bool)
    disp = np.zeros(nv)
    seams = [(c[0], c[1], [math.radians(a) for a in c[2]]) for c in L.COURSES]
    for i in np.nonzero(vtank)[0]:
        p = Vector(co[i])
        yi, ti = y[i], th[i]
        d = 0.0
        if facing[i] > 0.2 or yi > 1.4:
            # лист: пояс по высоте, сектор между вертикальными швами
            ci = next((k for k, c in enumerate(seams) if c[0] <= yi < c[1]), len(seams) - 1)
            sa = seams[ci][2]
            si = max(range(len(sa)), key=lambda k: -((ti - sa[k]) % (2 * math.pi)))
            key = (ci, si)
            if key not in plate_rand:
                plate_rand[key] = (rng.uniform(0.0, 0.006), rng.random())
            d += plate_rand[key][0]
            tone[i, 0] = plate_rand[key][1]
            for (dt, dy, dr, dd) in dents:
                rr = max(0.2, radius_of(p))
                q = (ang_diff(ti, dt) * rr) ** 2 + (yi - dy) ** 2
                if q < (2.2 * dr) ** 2:
                    d -= dd * math.exp(-q / (2 * (dr * 0.6) ** 2))
            d += 0.0016 * noise.noise(p * 7.0) + 0.0005 * noise.noise(p * 38.0)
        if near[i] and not lip[i]:
            if dist[i] < 0.06:
                h = smoothstep(0.006, 0.011, dist[i]) * (1 - smoothstep(0.050, 0.055, dist[i]))
                d = d * (1 - h) + 0.0065 * h
                frame_v[i] = h > 0.5
        disp[i] = d
    fade = np.where(vother, 0.0, 1.0)                 # стык с основанием и топкой не рвём
    co2 = co + nrm * (disp * fade)[:, None]
    # стенки топки: корка копоти
    W = REG.index("wall")
    vw = np.zeros(nv, bool)
    vw[quad[pm == W].ravel()] = True
    for i in np.nonzero(vw & ~vtank)[0]:
        p = Vector(co[i])
        co2[i] += nrm[i] * (0.004 * noise.noise(p * 16.0) + 0.0015 * noise.noise(p * 55.0))
    me.vertices.foreach_set("co", co2.astype(np.float32).ravel())

    names = ["tank", "drum", "wall", "ash", "under", "frame"]
    for n in names:
        me.materials.append(mats[n])
    fr = frame_v[quad].all(1) & (pm == T)
    pm2 = pm.copy()
    pm2[pm == REG.index("floor")] = 3
    pm2[fr] = 5
    me.polygons.foreach_set("material_index", pm2)
    att = me.color_attributes.new("tone", "FLOAT_COLOR", "POINT")
    att.data.foreach_set("color", tone.ravel())
    me.polygons.foreach_set("use_smooth", [True] * npoly)
    me.update()
    ob = bpy.data.objects.new("hp_shell", me)
    bpy.context.scene.collection.objects.link(ob)

    # точки рамки топки для клёпок: вершины на средней линии накладки
    fpts = []
    for i in np.nonzero(near & ~lip & vtank)[0]:
        p = Vector(co[i])
        if 0.029 < dist[i] < 0.033 and all((p - q).length > 0.05 for q, _ in fpts):
            fpts.append((p, Vector(nrm[i])))
    return ob, bvh, bvh_in, fpts


class Surf:
    def __init__(self, bvh):
        self.bvh = bvh

    def at(self, th, y):
        """Точка и нормаль наружной поверхности на угле th и высоте y (луч к оси)."""
        e = er(th)
        loc, n, _, _ = self.bvh.ray_cast(Vector((L.CX, y, L.CZ)) + e * 1.5, -e)
        if loc is None:
            return None, None
        return loc, n

    def top(self, x, z):
        loc, n, _, _ = self.bvh.ray_cast(Vector((x, 2.5, z)), Vector((0, -1, 0)))
        return loc, n

    def frame(self, th, y, lift=0.0):
        """Матрица: X — по окружности, Y — вверх вдоль поверхности, Z — нормаль."""
        p, n = self.at(th, y)
        x = (et(th) - n * et(th).dot(n)).normalized()
        yy = n.cross(x).normalized()
        if yy.y < 0:
            yy = -yy
            x = -x
        M = Matrix((x, yy, n)).transposed().to_4x4()
        M.translation = p + n * lift
        return M

    def conform(self, bm, th0, y0):
        """Локальные (x вдоль окружности, y вверх, z наружу) → на поверхность бака."""
        for v in bm.verts:
            p0, _ = self.at(th0, y0 + v.co.y)
            r = max(0.12, radius_of(p0))
            p, n = self.at(th0 + v.co.x / r, y0 + v.co.y)
            v.co = p + n * v.co.z
        return bm


# ---------------------------------------------------------------- бак: обручи и клёпки
def build_hoops(hp, S, info, rng):
    op = info["opening"]
    for hi, (hy, gap) in enumerate(L.HOOPS):
        if gap:
            gap = (math.radians(op["th0"]) - 0.16, math.radians(op["th1"]) + 0.16)
        N = 300
        bm = bmesh.new()
        prev = first = None
        ths = []
        for i in range(N):
            t = -math.pi + 2 * math.pi * i / N
            if gap and gap[0] < t < gap[1]:
                prev = None
                continue
            yy = hy + 0.004 * math.sin(t * 2 + hi * 1.7) + 0.002 * noise.noise(Vector((t * 3, hi * 5.0, 0)))
            p, n = S.at(t, yy)
            x = (et(t) - n * et(t).dot(n)).normalized()
            up = n.cross(x)
            if up.y < 0:
                up = -up
            w, tk = L.HOOP_W / 2, L.HOOP_T
            prof = [(-w, -0.006), (-w, tk * 0.55), (-w + 0.004, tk), (w - 0.004, tk), (w, tk * 0.55), (w, -0.006)]
            row = [bm.verts.new(p + up * s + n * h) for s, h in prof]
            if prev:
                for k in range(len(prof) - 1):
                    bm.faces.new([row[k], row[k + 1], prev[k + 1], prev[k]])
            elif first is None or gap:
                first = first or row
            prev = row
            ths.append(t)
        if not gap:
            for k in range(5):
                bm.faces.new([first[k], first[k + 1], prev[k + 1], prev[k]])
        hp.add("hoop", bm, tone=rng.random())
        # клёпки по обручу
        p0, _ = S.at(0.0 if not gap else math.pi, hy)
        step = 0.075 / max(0.15, radius_of(p0))
        t = ths[0] + step * 0.5
        while t < ths[-1]:
            hp.add("rivet", dome(0.0075, 0.0045), S.frame(t, hy, L.HOOP_T - 0.0005), tone=rng.random())
            t += step * rng.uniform(0.92, 1.08)
        # замок обруча: накладка внахлёст с двумя крупными клёпками
        tj = math.radians((150, 200, 260, 110, 300)[hi])
        r = max(0.15, radius_of(S.at(tj, hy)[0]))
        bm = rounded_box(0.10, L.HOOP_W + 0.004, 0.005, 0.0015)
        for v in bm.verts:
            v.co.z += L.HOOP_T + 0.0025
        hp.add("hoop", S.conform(bm, tj, hy), tone=rng.random())
        for s in (-0.03, 0.03):
            hp.add("rivet", dome(0.010, 0.006), S.frame(tj + s / r, hy, L.HOOP_T + 0.005), tone=rng.random())


def build_rivets(hp, S, fpts, rng):
    # вертикальные швы листов: ряд клёпок рядом со ступенькой
    for (y0, y1, seams) in L.COURSES:
        y1 = min(y1, 1.50)
        for a in seams:
            t = math.radians(a)
            yy = max(y0, 0.60) + 0.045
            while yy < y1 - 0.035:
                near_hoop = any(abs(yy - h[0]) < L.HOOP_W / 2 + 0.012 for h in L.HOOPS)
                p, _ = S.at(t, yy)
                if not near_hoop and p is not None:
                    r = max(0.15, radius_of(p))
                    hp.add("rivet", dome(0.0065, 0.004), S.frame(t + 0.016 / r, yy, 0.002), tone=rng.random())
                yy += 0.034 * rng.uniform(0.94, 1.06)
    # рамка топки
    for p, n in fpts:
        z = n.normalized()
        x = z.cross(Vector((0, 1, 0))).normalized()
        M = Matrix((x, z.cross(x), z)).transposed().to_4x4()
        M.translation = p + z * 0.006
        hp.add("rivet", dome(0.0075, 0.0045), M, tone=rng.random())
    # край крышки
    for k in range(22):
        a = 2 * math.pi * k / 22 + 0.1
        e = er(a)
        x, z = L.CX + e.x * 0.215, L.CZ + e.z * 0.215
        p, n = S.top(x, z)
        if p is None or n.y < 0.6:
            continue
        xx = n.cross(Vector((0, 0, 1))).normalized()
        M = Matrix((xx, n.cross(xx), n)).transposed().to_4x4()
        M.translation = p + n * 0.001
        hp.add("rivet", dome(0.007, 0.0042), M, tone=rng.random())


# ---------------------------------------------------------------- ограждение из реек
def build_slats(hp, S, info, rng):
    """Горизонтальные рейки рядами вокруг основания. Каждая облегает бугристую поверхность на
    постоянном отступе: вертикальные рейки на таких буграх при взгляде сбоку ломались зигзагом
    (параллакс проекции), горизонтальные ряды с геометрией не спорят."""
    rows = []
    y = 0.012
    while y < 0.43:
        w = rng.uniform(0.078, 0.108)
        rows.append((y, min(y + w, 0.468)))
        y += w + rng.uniform(0.006, 0.011)
    boards = []
    for ri, (y0, y1) in enumerate(rows):
        w = y1 - y0
        yc = (y0 + y1) / 2
        rad = max(0.3, radius_of(S.at(0.0, yc)[0]))
        t = math.radians(rng.uniform(150, 210))            # стык ряда — сзади, вразбежку
        end = t + 2 * math.pi
        while t < end - 0.05:
            length = rng.uniform(0.62, 1.15)                # длинные рейки: короткие читались кирпичной кладкой
            a1 = min(end, t + length / rad)
            if end - a1 < 0.35 / rad:
                a1 = end
            gap = rng.uniform(0.005, 0.010) / rad
            skip = ri == len(rows) - 1 and rng.random() < 0.22 and (a1 - t) * rad < 0.80   # выпавшая рейка
            if not skip:
                thick = rng.uniform(0.010, 0.013)
                lift = rng.uniform(0.0, 0.003)
                slope = rng.uniform(-0.006, 0.006)
                n_seg = max(8, int((a1 - t - gap) * rad / 0.008))
                prof = [(-w / 2, -0.002), (-w / 2 + 0.0005, thick * 0.55), (-w / 2 + 0.0035, thick),
                        (w / 2 - 0.0035, thick), (w / 2 - 0.0005, thick * 0.55), (w / 2, -0.002)]
                bm = bmesh.new()
                prev = None
                L_m = (a1 - t - gap) * rad
                for i in range(n_seg + 1):
                    k = i / n_seg
                    th = t + (a1 - t - gap) * k
                    edge = min(1.0, min(k, 1 - k) * L_m / 0.004)       # торцы скруглены
                    yy = yc + slope * (k - 0.5) * 2 + 0.002 * math.sin(k * 5 + ri)
                    row = []
                    for s_, h in prof:
                        ys = yy + s_ * (0.96 + 0.04 * edge)
                        p, nn = S.at(th, max(0.03, ys))               # у земли оболочка скруглена
                        p = Vector((p.x, ys, p.z))
                        row.append(bm.verts.new(p + nn * ((h + lift) * (edge if h > 0 else 1.0))))
                    if prev:
                        for j in range(len(prof) - 1):
                            bm.faces.new([row[j], row[j + 1], prev[j + 1], prev[j]])
                    prev = row
                # tone: G = вдоль рейки (0.6 м = 1), B = поперёк
                hp.add("slat", bm, tone=rng.random(),
                       tone_fn=lambda c, t=t, rad=rad, y0=y0, w=w: (((theta_of(c) - t) % (2 * math.pi)) * rad / 0.6,
                                                                    min(1.0, max(0.0, (c.y - y0) / w))))
                boards.append([t, a1 - gap, y0, y1, thick + lift, rad])
                for aa in (t + 0.022 / rad, a1 - gap - 0.022 / rad):
                    for yy in ((yc - w * 0.24, yc + w * 0.24) if w > 0.09 else (yc,)):
                        M = S.frame(aa, yy + rng.uniform(-0.006, 0.006), thick + lift - 0.0005)
                        b = dome(rng.uniform(0.0050, 0.0062), 0.0032, 8, 4)
                        for v in b.verts:
                            v.co.x *= 1.2
                        hp.add("nail", b, M, tone=rng.random())
            t = a1
    # проволока: две нитки поверх реек со скруткой
    for wi, wy in enumerate((L.WIRE_Y, L.WIRE_Y + 0.012)):
        pts = []
        for i in range(260):
            th = 2 * math.pi * i / 260
            yy = wy + 0.005 * math.sin(th * 3 + wi * 2.0) + 0.002 * noise.noise(Vector((th * 5, wi * 3.0, 0)))
            p, nn = S.at(th, yy)
            pts.append(p + nn * 0.0165)
        hp.add("wire", tube(pts, 0.0032, 6, closed=True), tone=0.3 + 0.4 * wi)
    th = math.radians(95)
    p, nn = S.at(th, L.WIRE_Y)
    pts = []
    for i in range(26):                                   # скрутка: спираль из двух концов
        a = i * 0.9
        pts.append(p + nn * (0.019 + 0.0035 * math.cos(a)) + et(th) * (0.0035 * math.sin(a)) + Vector((0, 0.005 - i * 0.0022, 0)))
    hp.add("wire", tube(pts, 0.0028, 6), tone=0.5)
    info["boards"] = boards


# ---------------------------------------------------------------- топка: зола, поленья, угли
def ash_y(x, z):
    p = Vector((x * 9.0, z * 9.0, 0.3))
    back = smoothstep(0.05, -0.28, z - L.CZ)
    return L.FLOOR_Y + 0.010 + 0.012 * noise.noise(p) + 0.005 * noise.noise(p * 3.1) + 0.035 * back


def build_firebox(hp, rng, info):
    # зола: бугристая подсыпка над полом
    bm = bmesh.new()
    N, R = 96, 0.335
    grid = {}
    for i in range(N + 1):
        for j in range(N + 1):
            x, z = L.CX - R + 2 * R * i / N, L.CZ - R + 2 * R * j / N
            if math.hypot(x - L.CX, z - L.CZ) <= R:
                grid[i, j] = bm.verts.new(Vector((x, ash_y(x, z), z)))
    for (i, j) in list(grid):
        q = [grid.get(k) for k in ((i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j))]
        if all(q):
            bm.faces.new(q)
    hp.add("ash", bm, tone=0.5)

    # поленья: (x0, z0) → (x1, z1) относительно оси, радиус, подъём, колотое
    logs = [((-0.115, 0.215), (-0.035, -0.105), 0.040, 0.000, False),
            ((0.135, 0.235), (0.075, -0.085), 0.036, 0.000, False),
            ((0.015, 0.265), (0.030, -0.005), 0.046, 0.000, True),
            ((-0.215, -0.045), (0.205, -0.135), 0.034, 0.052, False),
            ((0.215, 0.135), (0.255, -0.075), 0.028, 0.000, False),
            ((-0.235, 0.105), (-0.175, -0.125), 0.031, 0.000, True)]
    out = []
    for li, ((x0, z0), (x1, z1), r, lift, half) in enumerate(logs):
        a = Vector((L.CX + x0, 0, L.CZ + z0))
        b = Vector((L.CX + x1, 0, L.CZ + z1))
        mid = (a + b) / 2
        d = (b - a)
        length = d.length
        x = d.normalized()
        yv = Vector((0, 1, 0))
        z = x.cross(yv).normalized()
        roll = Matrix.Rotation(rng.uniform(0, 6.28) if not half else math.pi + rng.uniform(-0.25, 0.25), 4, "X")
        M = Matrix((x, z, yv)).transposed().to_4x4()      # локальная Z полена → вверх
        base = ash_y(mid.x, mid.z)
        M.translation = Vector((mid.x, base + (r * 0.72 if not half else r * 0.85) + lift, mid.z))
        bark, ends, split = log_mesh(rng, length, r, half)
        tone = rng.random()
        hp.add("bark", bark, M @ roll, tone=tone,
               tone_fn=lambda c, length=length: (c.x / length + 0.5, math.atan2(c.z, c.y) / (2 * math.pi) + 0.5))
        hp.add("logend", ends, M @ roll, tone=tone,
               tone_fn=lambda c, r=r, length=length: (min(1.0, math.hypot(c.y, c.z) / r), c.x / length + 0.5))
        if split:
            hp.add("logend", split, M @ roll, tone=tone,
                   tone_fn=lambda c, r=r, length=length: (0.5 + 0.5 * c.y / r, c.x / length + 0.5))
        out.append([a.x, a.z, b.x, b.z, r])
    info["logs"] = out

    # угли: шесть гнёзд, между ними зола
    nests = [(-0.035, 0.125), (0.095, 0.055), (-0.125, 0.005), (0.035, -0.085), (0.165, 0.175), (-0.165, 0.165)]
    info["nests"] = [[L.CX + x, L.CZ + z] for x, z in nests]
    for ni, (cx, cz) in enumerate(nests):
        for _ in range(rng.randint(11, 16)):
            dx, dz = rng.gauss(0, 0.028), rng.gauss(0, 0.028)
            x, z = L.CX + cx + dx, L.CZ + cz + dz
            s = rng.uniform(0.010, 0.022)
            heat = math.exp(-(dx * dx + dz * dz) / (2 * 0.03 ** 2)) * rng.uniform(0.65, 1.0)
            b = stone(rng, s * rng.uniform(0.8, 1.3), s * rng.uniform(0.8, 1.3), s * rng.uniform(0.6, 0.9), sub=2)
            M = Matrix.Rotation(rng.uniform(0, 6.28), 4, "Y")
            M.translation = Vector((x, ash_y(x, z) + s * 0.35, z))
            hp.add("ember", b, M, tone=rng.random(), tone_fn=lambda c, heat=heat, ni=ni: (heat, (ni + 0.5) / 8))


# ---------------------------------------------------------------- камни на крышке
def build_stones(hp, S, rng):
    G = 80
    R = 0.30
    hf = np.full((G, G), -1.0)

    def cell(v):
        return int((v + R) / (2 * R) * (G - 1))

    def surface(x, z):
        p, n = S.top(L.CX + x, L.CZ + z)
        return p.y if (p is not None and n.y > 0.5 and p.y > 1.45) else None

    placed = 0
    for layer, (count, rmin, rmax, smin, smax) in enumerate(((46, 0.085, 0.205, 0.026, 0.046), (16, 0.09, 0.16, 0.022, 0.036),
                                                             (30, 0.07, 0.225, 0.010, 0.018))):
        tries = 0
        done = 0
        pts = []
        while done < count and tries < 4000:
            tries += 1
            a, rr = rng.uniform(0, 6.283), math.sqrt(rng.uniform(rmin ** 2, rmax ** 2))
            x, z = rr * math.sin(a), rr * math.cos(a)
            sx, sz = rng.uniform(smin, smax), rng.uniform(smin, smax)
            sy = rng.uniform(0.55, 0.85) * min(sx, sz)
            if layer != 2 and any(math.hypot(x - px, z - pz) < 0.72 * (max(sx, sz) + ps) for px, pz, ps in pts):
                continue
            base = surface(x, z)
            if base is None:
                continue
            i0, i1, j0, j1 = cell(x - sx * 0.6), cell(x + sx * 0.6), cell(z - sz * 0.6), cell(z + sz * 0.6)
            under = hf[max(0, i0):i1 + 1, max(0, j0):j1 + 1]
            top = max(base, float(under.max())) if under.size else base
            if top + sy * 1.7 > base + 0.105:              # выше клетки запекания не кладём
                continue
            cy = top + sy * (0.62 if layer != 2 else 0.5)
            b = stone(rng, sx, sy, sz)
            M = Matrix.Rotation(rng.uniform(0, 6.28), 4, "Y") @ Matrix.Rotation(rng.uniform(-0.25, 0.25), 4, "X")
            M.translation = Vector((L.CX + x, cy, L.CZ + z))
            hp.add("stone", b, M, tone=rng.random(), tone_fn=lambda c, layer=layer: (layer / 2, 0.0))
            for i in range(max(0, i0), min(G, i1 + 1)):
                for j in range(max(0, j0), min(G, j1 + 1)):
                    hf[i, j] = max(hf[i, j], cy + sy * 0.55)
            pts.append((x, z, max(sx, sz)))
            done += 1
        placed += done
    print("stones placed", placed, flush=True)


# ---------------------------------------------------------------- ковш и затычка
def build_ladle(hp, S, rng):
    th, y = math.radians(L.LADLE[0]), L.LADLE[1]
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=28, v_segments=16, radius=1.0)
    for v in bm.verts:                                     # чаша: эллипсоид с выбранным нутром
        c = Vector((v.co.x * 0.056, v.co.y * 0.060, v.co.z * 0.030))
        rim = 0.019
        if c.z > rim:
            c.z = rim - (c.z - rim) * 1.7
            c.x *= 0.86
            c.y *= 0.86
        v.co = c
    hp.add("ladle", S.conform(bm, th, y), tone=0.35,
           tone_fn=lambda c: (0.0, 0.0))
    hl = 0.235
    bm = rounded_box(0.024, hl, 0.013, 0.004)
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if abs((e.verts[0].co - e.verts[1].co).y) > hl * 0.5], cuts=14)
    for v in bm.verts:                                     # ручка сужается к середине, расширяется к концу
        k = v.co.y / hl + 0.5
        v.co.x *= 0.85 + 0.45 * (k - 0.45) ** 2 * 4 * 0.5
        v.co.y += 0.05 + hl / 2
        v.co.z += 0.009
    hp.add("ladle", S.conform(bm, th, y), tone=0.55, tone_fn=lambda c: (1.0, 0.0))
    # гвоздь, на котором висит ковш
    p0, _ = S.at(th, y + 0.05 + hl - 0.022)
    hp.add("nail", dome(0.0075, 0.0045, 8, 4), S.frame(th, y + 0.05 + hl - 0.022, 0.0155), tone=rng.random())


def build_plug(hp, S, rng):
    th, y = math.radians(L.PLUG[0]), L.PLUG[1]
    M = S.frame(th, y)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=18, radius1=0.026, radius2=0.021, depth=0.05)
    bmesh.ops.bevel(bm, geom=[e for e in bm.edges if all(v.co.z > 0 for v in e.verts)], offset=0.004, segments=2, affect="EDGES")
    hp.add("plug", bm, M, tone=0.5, tone_fn=lambda c: (math.hypot(c.x, c.y) / 0.026, 0.0))
    # тряпка: скрученный жгут вокруг затычки и хвост вниз
    bm = bmesh.new()
    U, V = 40, 10
    ring = []
    for i in range(U):
        a = 2 * math.pi * i / U
        row = []
        for j in range(V):
            b = 2 * math.pi * j / V
            rr = 0.0125 * (1 + 0.3 * math.sin(a * 5 + b * 2) + 0.2 * noise.noise(Vector((a * 2, b, 1.0))))
            R = 0.036 + rr * math.cos(b)
            row.append(bm.verts.new(Vector((R * math.cos(a), R * math.sin(a) * 0.95, 0.008 + rr * 0.9 * math.sin(b) + 0.004))))
        ring.append(row)
    for i in range(U):
        for j in range(V):
            bm.faces.new([ring[i][j], ring[(i + 1) % U][j], ring[(i + 1) % U][(j + 1) % V], ring[i][(j + 1) % V]])
    hp.add("rag", S.conform(bm, th, y), tone=0.5, tone_fn=lambda c: (0.0, 0.0))
    bm = bmesh.new()
    NX, NY = 14, 30
    rows = []
    for j in range(NY + 1):
        v = j / NY
        row = []
        for i in range(NX + 1):
            u = i / NX - 0.5
            w = 0.050 * (1 - 0.35 * v)
            end = 0.135 + 0.018 * math.sin(i * 1.9) + 0.01 * noise.noise(Vector((i * 0.7, 3.0, 0)))
            x = u * w + 0.012 * math.sin(v * 5.0) * v
            yy = -0.030 - v * end
            z = 0.0035 + 0.0045 * (0.5 + 0.5 * math.sin(u * 15 + v * 4)) * (1 - 0.5 * v) + 0.006 * (1 - v) ** 3
            if abs(u) > 0.46:
                z = 0.0005
            row.append(bm.verts.new(Vector((x, yy, z))))
        rows.append(row)
    for j in range(NY):
        for i in range(NX):
            bm.faces.new([rows[j + 1][i], rows[j + 1][i + 1], rows[j][i + 1], rows[j][i]])
    hp.add("rag", S.conform(bm, th, y), tone=0.6, tone_fn=lambda c: (1.0, 0.0))


# ---------------------------------------------------------------- materials / passes
def make_materials():
    mats = {}
    for name in L.IDS:
        m = bpy.data.materials.new("hp_" + name)
        m.use_nodes = True
        m["bake_id"] = L.IDS[name]
        mats[name] = m
    return mats


def set_pass(mats, kind):
    for name, m in mats.items():
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        if kind == "view":
            bs = nt.nodes.new("ShaderNodeBsdfDiffuse")
            bs.inputs["Color"].default_value = (*VIEW_COL.get(name, (0.5, 0.5, 0.5)), 1)
            nt.links.new(bs.outputs[0], out.inputs["Surface"])
            continue
        em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        if kind == "id":
            v = (m["bake_id"] * 12 + 6) / 255.0
            em.inputs["Color"].default_value = (v, v, v, 1)
        elif kind == "tone":
            at = nt.nodes.new("ShaderNodeAttribute")
            at.attribute_name = "tone"
            nt.links.new(at.outputs["Color"], em.inputs["Color"])
        elif kind == "pos":
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            add = nt.nodes.new("ShaderNodeVectorMath")
            add.operation = "ADD"
            add.inputs[1].default_value = L.POS_OFF
            mul = nt.nodes.new("ShaderNodeVectorMath")
            mul.operation = "MULTIPLY"
            mul.inputs[1].default_value = tuple(1 / s for s in L.POS_SCALE)
            nt.links.new(geo.outputs["Position"], add.inputs[0])
            nt.links.new(add.outputs[0], mul.inputs[0])
            nt.links.new(mul.outputs[0], em.inputs["Color"])


def setup_cycles(scene):
    scene.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = kind
                prefs.get_devices()
                if any(d.type == kind for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = d.type == kind
                    scene.cycles.device = "GPU"
                    print("cycles:", kind, flush=True)
                    break
            except TypeError:
                continue
    except Exception as e:  # noqa: BLE001
        print("cycles: CPU", e, flush=True)


# ---------------------------------------------------------------- cage + bake
def build_target(low, reg):
    """Цель запекания: low-poly без островов, лежащих поверх чужих (дно, отверстие в крышке, кубики углей)."""
    tgt = sub_mesh(low, reg, ("tank", "drum", "wall", "floor"), "bake_target")
    for p in tgt.data.polygons:
        p.use_smooth = True
    me = tgt.data.copy()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.normal_update()
    for v in bm.verts:
        kinds = {REG[f.material_index] for f in v.link_faces}
        n = v.normal
        rad = Vector((v.co.x - L.CX, 0, v.co.z - L.CZ)).normalized()
        if "floor" in kinds:
            d = Vector((0, 1, 0)) * (0.17 if kinds == {"floor"} else 0.05)
        elif "wall" in kinds:
            d = n * (0.03 if kinds == {"wall"} else 0.012)
        elif kinds == {"drum"}:
            d = n * 0.04
        elif "drum" in kinds:
            d = n * 0.04
        elif v.co.y > 1.45 and n.y > 0.75:
            d = n * 0.125
        elif v.co.y > 1.45:
            d = n * 0.05
        else:
            d = n * 0.05
        v.co = v.co + d
    bm.to_mesh(me)
    bm.free()
    cage = bpy.data.objects.new("cage", me)
    bpy.context.scene.collection.objects.link(cage)
    cage.hide_render = True
    return tgt, cage


def bake(tgt, hp, cage, mats, size):
    scene = bpy.context.scene
    setup_cycles(scene)
    for attr in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission",
                 "visible_volume_scatter", "visible_shadow"):
        setattr(tgt, attr, False)
    if scene.world is None:
        scene.world = bpy.data.worlds.new("bake")
    scene.world.light_settings.distance = 0.35
    lm = bpy.data.materials.new("bake_target")
    lm.use_nodes = True
    tgt.data.materials.clear()
    tgt.data.materials.append(lm)
    for p in tgt.data.polygons:
        p.material_index = 0
    tex = lm.node_tree.nodes.new("ShaderNodeTexImage")
    lm.node_tree.nodes.active = tex
    bk = scene.render.bake
    bk.use_selected_to_active = True
    bk.use_cage = True
    bk.cage_object = cage
    bk.max_ray_distance = 0.0
    bk.target = "IMAGE_TEXTURES"
    bk.normal_space = "TANGENT"
    bk.normal_r, bk.normal_g, bk.normal_b = "POS_X", "POS_Y", "POS_Z"     # OpenGL
    bpy.ops.object.select_all(action="DESELECT")
    for o in hp:
        o.select_set(True)
    tgt.select_set(True)
    bpy.context.view_layer.objects.active = tgt
    OUT.mkdir(exist_ok=True)
    for name, kind, shader, samples in (("normal", "NORMAL", "view", 1), ("ao", "AO", "view", 96),
                                        ("id", "EMIT", "id", 1), ("tone", "EMIT", "tone", 1), ("pos", "EMIT", "pos", 1)):
        set_pass(mats, shader)
        img = bpy.data.images.new(f"bake_{name}", size, size, alpha=False, float_buffer=True)
        img.colorspace_settings.name = "Non-Color"
        tex.image = img
        scene.cycles.samples = samples
        print(f"baking {name} ...", flush=True)
        bk.margin_type = "EXTEND"
        bpy.ops.object.bake(type=kind, use_clear=True, margin=16 if name in ("normal", "ao") else 4)
        if name == "pos":
            a = np.empty(size * size * 4, np.float32)
            img.pixels.foreach_get(a)
            a = a.reshape(size, size, 4)[::-1, :, :3]
            np.savez_compressed(OUT / "pos.npz", pos=(np.clip(a, 0, 1) * 65535).round().astype(np.uint16))
        else:
            img.filepath_raw = str(OUT / f"{name}.png")
            img.file_format = "PNG"
            img.save()
        print("  ->", name, flush=True)
    set_pass(mats, "view")


def preview(hp, info):
    """Рендер high-poly в условных цветах (проверка геометрии, не игровой кадр)."""
    scene = bpy.context.scene
    setup_cycles(scene)
    scene.cycles.samples = 48
    scene.render.resolution_x = scene.render.resolution_y = 1100
    scene.render.film_transparent = False
    w = bpy.data.worlds.new("pv")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.57, 0.6, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.9
    scene.world = w
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.0
    scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(55), math.radians(-25), 0)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.lens = 50
    views = {"front": ((1.3, 1.25, 3.0), (0, 0.8, 0)), "back": ((-1.6, 1.3, -2.8), (0, 0.8, 0)),
             "top": ((0.35, 2.45, 0.75), (0, 1.5, 0)), "fire": ((0.25, 1.05, 1.25), (0.02, 0.66, 0.1)),
             "plug": ((-1.15, 0.95, 0.95), (-0.25, 0.62, 0.2)), "ladle": ((1.2, 1.3, 0.75), (0.25, 1.05, 0.15))}
    for name, (pos, look) in views.items():
        p, t = Vector(pos), Vector(look)
        fwd = (t - p).normalized()
        right = fwd.cross(Vector((0, 1, 0))).normalized()
        up = right.cross(fwd)
        M = Matrix((right, up, -fwd)).transposed().to_4x4()
        M.translation = p
        cam.matrix_world = M
        scene.render.filepath = str(OUT / f"hp_preview_{name}.png")
        bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 2048
    bpy.ops.wm.read_factory_settings(use_empty=True)
    low = load_low()
    reg = regions(low.data)
    print({r: reg.count(r) for r in REG}, flush=True)
    mats = make_materials()
    set_pass(mats, "view")
    info = {}
    rng = random.Random(5)
    shell, bvh, bvh_in, fpts = build_shell(low, reg, mats, info)
    S = Surf(bvh)
    hp = HP()
    build_hoops(hp, S, info, rng)
    build_rivets(hp, S, fpts, rng)
    build_slats(hp, S, info, rng)
    build_firebox(hp, rng, info)
    build_stones(hp, S, rng)
    build_ladle(hp, S, rng)
    build_plug(hp, S, rng)
    obs = [shell] + hp.objects(mats)
    print("high-poly:", {o.name: len(o.data.polygons) for o in obs}, flush=True)
    OUT.mkdir(exist_ok=True)
    (OUT / "layout.json").write_text(json.dumps(info, indent=1))
    tgt, cage = build_target(low, reg)
    low.hide_render = True
    if "--nobake" not in argv:
        bake(tgt, obs, cage, mats, size)
    if "--blend" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "highpoly.blend"))
    if "--preview" in argv:
        tgt.hide_render = True
        preview(obs, info)
    print("done")


if __name__ == "__main__":
    main()
