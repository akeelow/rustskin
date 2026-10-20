"""Sauna Chair v1: high-poly details modelled over the Chair and baked onto its UVs.

Concept C "changing-room chair", no alpha. Modelled (positions from layout.py):
  seat      6 aspen slats across, conformed to the seat by rays from above: rounded long edges, real
            gaps over a dark cavity, waves, cup; the front slat cracked at its left end, a staple across
  lining    narrow vertical boards over the backrest front (V-grooves, chamfers), conformed by rays
  back      the same boards from behind + two cross battens with a nail per board
  towel     a linen towel over the top rail: front and back hangs conformed by rays, wrapped round the
            rail by rays toward its axis; drape folds growing toward the hem, a hem band, rounded edges
  nails     forged heads at both ends of every slat (into the side rails), on the battens
  wire      a helix of wire round the split end of the shovel-handle leg and its old rubber tip
Wings, arms, rail, the block leg and the handle are the low-poly's own shape, subdivided with slight
waves (hand-planed); iron parts (rear legs, posts, brackets) stay as they are and keep the original
normal map in texture_v1.py.

Usage (from the repo root):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/chair/bake_chair.py -- [--size 2048] [--blend] [--nobake]

Writes bake/{normal,ao,curvature,id}.png. id.png: R = id * 16 + 8 (see IDS), G = random per part.
Model: the OBJ (metres, Y up) scaled to centimetres, axes kept: y up, +z front.
"""
import importlib.util
import math
import random
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector, kdtree, noise
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OBJ = HERE / "originals" / "chair.obj"
OUT = HERE / "bake"
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))
import layout as L  # noqa: E402
from islands import islands  # noqa: E402
from uv_zones import load_obj  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_locker = _load("locker_door_v5", HERE.parent / "locker" / "door_v5_bake.py")
add_box, setup_cycles = _locker.add_box, _locker.setup_cycles
forged_nail, new_obj = _locker.forged_nail, _locker.new_obj

IDS = {"base": 0, "slat": 1, "cavity": 2, "lining": 3, "back": 4, "batten": 5, "frame": 6, "nail": 7,
       "towel": 8, "wire": 9, "staple": 10, "handle": 11, "joist": 12}
_locker.IDS = IDS                    # id_material/set_pass read the module's IDS
_locker.VIEW_COL.update({"slat": (0.64, 0.57, 0.46), "lining": (0.64, 0.57, 0.46), "back": (0.58, 0.55, 0.5),
                         "batten": (0.48, 0.35, 0.24), "frame": (0.6, 0.53, 0.42), "towel": (0.8, 0.77, 0.7),
                         "wire": (0.2, 0.2, 0.2), "staple": (0.2, 0.2, 0.2), "handle": (0.54, 0.42, 0.3),
                         "joist": (0.35, 0.27, 0.2)})
id_material, set_pass = _locker.id_material, _locker.set_pass

# islands (uv/islands.md)
SHELL, POST_R, RAIL, TIP, POLE, BACK = 0, 1, 2, 3, 4, 5
ARMS = (7, 9, 12, 20)
POST_L, BLOCK, POLE_TOP, TIP_END = 11, 10, 15, 16
IRON = (POST_R, 6, 8, 13, 14, 17, 18, 19, 21, TIP)
SEAT_Y = 53.5


# ---------------------------------------------------------------- low-poly
def island_per_polygon(me):
    """Island number for each Blender polygon, matched by UV centroid (UVs never overlap)."""
    V, T, F = load_obj(OBJ)
    kd = kdtree.KDTree(len(F))
    isl = {}
    for n, fs in enumerate(islands(F)):
        for f in fs:
            isl[f] = n
    for f, (_, ti) in enumerate(F):
        kd.insert((sum(T[t][0] for t in ti) / 3, sum(T[t][1] for t in ti) / 3, 0), f)
    kd.balance()
    uv = me.uv_layers.active.data
    out = []
    for p in me.polygons:
        c = Vector((0, 0, 0))
        for li in p.loop_indices:
            c += Vector((*uv[li].uv, 0))
        _, f, d = kd.find(c / p.loop_total)
        assert d < 1e-4, f"no island for polygon {p.index}"
        out.append(isl[f])
    return out


def regions(me):
    """Region per polygon: island number, or a name for the parts of the shell and back that the
    high-poly re-models (seat top/edge, panel, wings, back side, seat underside)."""
    out = []
    for p, n in zip(me.polygons, island_per_polygon(me)):
        c, nm = p.center, p.normal
        if n == SHELL:
            if c.y < SEAT_Y:
                out.append("seat_top" if nm.y > 0.5 else "seat_edge")
            elif abs(c.x) < 20.5 and nm.z > 0.3:
                out.append("panel")
            else:
                out.append("wing")
        elif n == BACK:
            out.append("back_side" if c.y > 52.0 and nm.z < -0.3 else "under")
        else:
            out.append(n)
    return out


def load_low():
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="Y", up_axis="Z")   # keep the OBJ's axes
    low = bpy.context.selected_objects[0]
    low.name = "lowpoly_chair"
    for v in low.data.vertices:
        v.co *= 100.0                                                       # metres -> cm
    bpy.context.view_layer.objects.active = low
    low.select_set(True)
    bpy.ops.mesh.customdata_custom_splitnormals_clear()
    for p in low.data.polygons:
        p.use_smooth = False
    low.data.update()
    return low


def copy_regions(low, reg, keep, name, mat, push=0.0, subdiv=0, wave=0.0, seed=0.0):
    """A copy of the low-poly with only the polygons whose region is in `keep`; optionally pushed
    along the normals (negative: inward), subdivided and waved (hand-planed wood)."""
    me = low.data.copy()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.clear()
    me.materials.append(mat)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if reg[f.index] not in keep], context="FACES")
    for _ in range(subdiv):
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True)
    bm.normal_update()
    if push or wave:
        moves = []
        for v in bm.verts:
            d = push + wave * noise.noise(Vector((v.co.x * 0.08, v.co.y * 0.08 + seed, v.co.z * 0.08)))
            moves.append((v, v.normal * d))
        for v, m in moves:
            v.co += m
    bm.to_mesh(me)
    bm.free()
    return ob


def region_bvh(low, reg, keep):
    bm = bmesh.new()
    bm.from_mesh(low.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if reg[f.index] not in keep], context="FACES")
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    return bvh


# ---------------------------------------------------------------- conformed grids
def refined(a, b, step, edge=(0.03, 0.08, 0.15, 0.25, 0.4)):
    """Samples from a to b, dense near both ends (for rounded / chamfered board edges)."""
    w = b - a
    near = [e for e in edge if e < w / 2]
    mid0, mid1 = a + (near[-1] if near else 0), b - (near[-1] if near else 0)
    n = max(1, int(math.ceil((mid1 - mid0) / step)))
    s = [a] + [a + e for e in near] + [mid0 + (mid1 - mid0) * k / n for k in range(1, n)] \
        + [b - e for e in reversed(near)] + [b]
    return sorted(set(round(v, 4) for v in s))


def conform(bm, bvh, rows, cols, origin, ray, offset, ok=lambda n: True):
    """Grid of vertices: for each (r, c) cast `ray` from origin(r, c) onto the low-poly, lift the hit by
    offset(r, c, hit) against the ray. Quads where all four corners hit. Returns the vertex grid."""
    ray = Vector(ray).normalized()
    g = []
    for r in rows:
        line = []
        for c in cols:
            o = origin(r, c)
            if o is None:
                line.append(None)
                continue
            hit, n, _, _ = bvh.ray_cast(Vector(o), ray, 500.0)
            if hit is None:
                line.append(None)
                continue
            if n.dot(ray) > 0:
                n = -n
            if not ok(n):
                line.append(None)
                continue
            line.append(bm.verts.new(hit - ray * offset(r, c, hit)))
        g.append(line)
    for i in range(len(rows) - 1):
        for j in range(len(cols) - 1):
            q = (g[i][j], g[i][j + 1], g[i + 1][j + 1], g[i + 1][j])
            if None not in q:
                face_against(bm.faces.new(q), ray)
    return g


def face_against(f, d):
    """Turn a new face to look against direction d (toward where the rays came from). v1 first bake:
    the grids built by rays from behind faced into the chair and the back baked inside out."""
    f.normal_update()
    if f.normal.dot(d) > 0:
        f.normal_flip()


def hang(bm, bvh, rows, cols, yfun, ray_z, offset, k=0.12, blur=6):
    """A hanging cloth: per column cast rays along z (ray_z -1: from the front, +1: from behind) at
    heights yfun(row, col); the cloth may not fall back into a step faster than k cm per cm of drop,
    so it hangs straight off the rail's front instead of following the ledge under it (v1 first try
    followed it: a ragged band). The outward coordinate is then smoothed across +-blur columns.
    Rows bottom-up. Quads."""
    ray = Vector((0, 0, ray_z))
    nr, nc = len(rows), len(cols)
    hits = [[None] * nc for _ in rows]
    out = [[None] * nc for _ in rows]                               # outward coordinate (-ray_z * z)
    for j, c in enumerate(cols):
        for i, r in enumerate(rows):
            y = yfun(r, c)
            if y is not None:
                hits[i][j] = bvh.ray_cast(Vector((c, y, -80.0 * ray_z)), ray, 200.0)[0]
        prev = None
        for i in reversed(range(nr)):
            hit = hits[i][j]
            if hit is None:
                prev = None
                continue
            o = -ray_z * hit.z
            if prev is not None:
                o = max(o, prev - k * abs(hits[i + 1][j].y - hit.y))
            out[i][j] = prev = o
    g = [[None] * nc for _ in rows]
    for i in range(nr):
        for j in range(nc):
            if out[i][j] is None:
                continue
            vals = [out[i][q] for q in range(max(0, j - blur), min(nc, j + blur + 1)) if out[i][q] is not None]
            hit = hits[i][j]
            o = max(-ray_z * hit.z, sum(vals) / len(vals))       # smoothed, never inside the chair
            p = Vector((hit.x, hit.y, -ray_z * o))
            g[i][j] = bm.verts.new(p - ray * offset(rows[i], cols[j], p))
    for i in range(nr - 1):
        for j in range(nc - 1):
            q = (g[i][j], g[i][j + 1], g[i + 1][j + 1], g[i + 1][j])
            if None not in q:
                face_against(bm.faces.new(q), ray)


def round_edge(d, r):
    """Height drop of a rounded edge at distance d from it (radius r)."""
    if d >= r:
        return 0.0
    return -(r - math.sqrt(max(0.0, r * r - (r - d) ** 2)))


def place(bm_target, build, origin, normal):
    """Build a part in a local frame (z = up from the surface) and place it at origin facing normal."""
    nb = bmesh.new()
    build(nb)
    n = Vector(normal).normalized()
    t1 = n.cross(Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((1, 0, 0))).normalized()
    t2 = n.cross(t1)
    for v in nb.verts:
        lx, ly, lz = v.co
        v.co = Vector(origin) + t1 * lx + t2 * ly + n * lz
    tmp = bpy.data.meshes.new("tmp")
    nb.to_mesh(tmp)
    nb.free()
    bm_target.from_mesh(tmp)
    bpy.data.meshes.remove(tmp)


# ---------------------------------------------------------------- parts
def build_seat(low, reg, mats, rng):
    bvh = region_bvh(low, reg, {"seat_top", "seat_edge"})
    slats, nails, staple = bmesh.new(), bmesh.new(), bmesh.new()
    xs = refined(L.SEAT_X[0], L.SEAT_X[1], 0.3, ())
    for i, (z0, z1) in enumerate(L.SLATS):
        a, b = z0 + L.SEAT_GAP / 2, z1 - L.SEAT_GAP / 2
        zs = refined(a, b, 0.3)
        if i == L.FRONT:                                    # dense around the crack
            zc = L.crack_z(-22.0)
            zs = sorted(set(zs + [round(zc + k * 0.04, 4) for k in range(-14, 15)]))
        lift = rng.uniform(-0.08, 0.08)
        seed = rng.uniform(0, 100)

        def off(x, z, hit, a=a, b=b, lift=lift, seed=seed, i=i):
            h = 0.15 + lift + round_edge(min(z - a, b - z), 0.35)
            h += 0.05 * noise.noise(Vector((x * 0.1, z * 0.9, seed)))                # plane waves
            c = (z - (a + b) / 2) / ((b - a) / 2)
            h -= 0.05 * (1 - c * c)                                                  # cupped a little
            if i == L.FRONT and L.CRACK_X[0] < x < L.CRACK_X[1]:
                taper = min(1.0, (L.CRACK_X[1] - x) / 4.0)
                h -= 0.35 * taper * math.exp(-((z - L.crack_z(x)) / (0.05 + 0.04 * taper)) ** 2)
            return h

        # stop where the rounded lip turns steep (v1 first bake: slats ran down the lip in ragged teeth)
        conform(slats, bvh, xs, zs, lambda x, z: (x, 90.0, z), (0, -1, 0), off, ok=lambda n: n.y > 0.6)
    ob = new_obj("hp_seat", slats, mats["slat"], low)
    sb = BVHTree.FromObject(ob, bpy.context.evaluated_depsgraph_get())
    for x, z in L.seat_nails():
        hit, n, _, _ = sb.ray_cast(Vector((x, 90.0, z)), Vector((0, -1, 0)), 100.0)
        if hit is not None:
            proud = rng.random() < 0.12
            place(nails, lambda nb: forged_nail(nb, 0, 0, 0.1 if proud else 0.0, rng, r=rng.uniform(0.34, 0.44)), hit, n)
    # staple across the crack: a flat iron bridge with rounded ends, 3 cm long
    x = L.STAPLE_X
    hit, n, _, _ = sb.ray_cast(Vector((x, 90.0, L.crack_z(x))), Vector((0, -1, 0)), 100.0)
    if hit is not None:
        place(staple, lambda nb: add_box(nb, (-0.17, -1.5, -0.05), (0.17, 1.5, 0.2), 0.08, 2), hit, n)
    # cavity under the gaps
    cav = copy_regions(low, reg, {"seat_top"}, "hp_seat_cavity", mats["cavity"], push=-0.9)
    return [ob, new_obj("hp_seat_nails", nails, mats["nail"], low),
            new_obj("hp_staple", staple, mats["staple"], low), cav]


def lining(bm, bvh, ray_z, rng, y_range, x_edges, chamfer=0.3):
    """Vertical lining boards conformed onto the backrest from the front (ray -z) or back (+z)."""
    ys = refined(y_range[0], y_range[1], 0.3, ())
    for (x0, x1) in x_edges:
        a, b = x0 + L.PANEL_GAP / 2, x1 - L.PANEL_GAP / 2
        xs = refined(a, b, 0.3, (0.04, 0.1, 0.2, 0.3, 0.45))
        lift = rng.uniform(-0.05, 0.05)
        seed = rng.uniform(0, 100)

        def off(y, x, hit, a=a, b=b, lift=lift, seed=seed):
            d = min(x - a, b - x)
            h = 0.15 + lift - max(0.0, chamfer - d)                                  # V-groove chamfer
            return h + 0.04 * noise.noise(Vector((x * 0.9, y * 0.1, seed)))

        conform(bm, bvh, ys, xs, lambda y, x: (x, y, -80.0 * ray_z), (0, 0, ray_z), off)


def build_backrest(low, reg, mats, rng):
    front, back, frame, battens, nails = (bmesh.new() for _ in range(5))
    pv = region_bvh(low, reg, {"panel"})
    lining(front, pv, -1.0, rng, L.PANEL_Y, L.BOARDS)
    bv = region_bvh(low, reg, {"back_side"})
    lining(back, bv, 1.0, rng, (50.0, 113.0), L.BOARDS, chamfer=0.25)
    # outside the lining on the back: the wings' back faces, plain frame
    ys = refined(50.0, 113.0, 0.4, ())
    for (a, b) in ((-33.0, L.PANEL_X[0]), (L.PANEL_X[1], 33.0)):
        conform(frame, bv, ys, refined(a, b, 0.4, ()), lambda y, x: (x, y, -80.0), (0, 0, 1), lambda *_: 0.1)
    # two cross battens, 1.4 cm proud, rounded edges and ends
    for (y0, y1) in L.BATTENS:
        seed = rng.uniform(0, 100)

        def off(y, x, hit, y0=y0, y1=y1, seed=seed):
            h = 1.55 + round_edge(min(y - y0, y1 - y), 0.4) + round_edge(min(x - L.BATTEN_X[0], L.BATTEN_X[1] - x), 0.4)
            return h + 0.05 * noise.noise(Vector((x * 0.1, y * 0.9, seed)))

        conform(battens, bv, refined(y0, y1, 0.25), refined(*L.BATTEN_X, 0.3), lambda y, x: (x, y, -80.0), (0, 0, 1), off)
    obb = new_obj("hp_battens", battens, mats["batten"], low)
    bb = BVHTree.FromObject(obb, bpy.context.evaluated_depsgraph_get())
    for x, y in L.batten_nails():
        hit, n, _, _ = bb.ray_cast(Vector((x, y, -80.0)), Vector((0, 0, 1)), 200.0)
        if hit is not None:
            place(nails, lambda nb: forged_nail(nb, 0, 0, 0, rng, r=rng.uniform(0.36, 0.46)), hit, n)
    cav = copy_regions(low, reg, {"panel", "back_side"}, "hp_lining_cavity", mats["cavity"], push=-0.7)
    return [new_obj("hp_lining", front, mats["lining"], low), new_obj("hp_back", back, mats["back"], low),
            new_obj("hp_back_frame", frame, mats["frame"], low), obb,
            new_obj("hp_batten_nails", nails, mats["nail"], low), cav]


def build_towel(low, reg, mats):
    """Linen towel over the top rail: front hang, rail top, back - three patches conformed by rays."""
    bm = bmesh.new()
    x0, x1 = L.TOWEL_X
    xs = refined(x0, x1, 0.25, (0.04, 0.1, 0.2, 0.32, 0.5))

    def edges(x, s):
        """Rounded side edges and hem: the towel thins to 0.2 cm at its borders."""
        k = min(1.0, (min(x - x0, x1 - x) / 0.5)) ** 0.5
        if s is not None:
            k = min(k, min(1.0, s / 0.35) ** 0.5)
        return k

    def front_off(s, x, hit):
        y = hit.y
        s = s if hit.y < L.RAIL_AXIS[0] - 0.01 else 99.0
        amp = min(1.0, max(0.0, (109.0 - y) / 24.0))
        h = 0.55 + 0.14 * L.folds(x) + 1.5 * amp * L.folds(x) + 0.08 * noise.noise(Vector((x * 0.3, y * 0.3, 1.0)))
        if 0.35 < s < 2.0:
            h += 0.14                                                                 # hem band
        return 0.2 + (h - 0.2) * edges(x, s)

    hem_s = [0.0, 0.05, 0.12, 0.22, 0.35, 0.5, 0.8, 1.2, 1.6, 1.85, 2.0, 2.15, 2.5]
    yc, zc = L.RAIL_AXIS
    ss = hem_s + [2.5 + 0.35 * k for k in range(1, 110)]
    # front hang: rows = distance above the hem, cols = x; rays -z, up to the rail axis height
    tv = region_bvh(low, reg, {"panel", "wing", RAIL})
    hang(bm, tv, ss, xs, lambda s, x: min(L.hem_front(x) + s, yc) if L.hem_front(x) + s < yc + 0.35 else None,
         -1.0, front_off)
    # over the rail: rays toward the rail axis from all round it (front -> top -> back), lifted
    # radially, so the wrap meets the front and back hangs without a seam (v1 first try: a separate
    # top patch lifted straight up left a ragged step at the rail's front edge)
    top = region_bvh(low, reg, {RAIL, "panel", "back_side", "wing"})
    ths = [math.radians(a) for a in range(0, 181, 2)]
    g = []
    for th in ths:
        d = Vector((0, math.sin(th), math.cos(th)))
        line = []
        for x in xs:
            hit, *_ = top.ray_cast(Vector((x, yc, zc)) + d * 30.0, -d, 40.0)
            if hit is None:
                line.append(None)
                continue
            k = th / math.pi                                     # 0 at the front, 1 at the back
            h = (0.55 + 0.14 * L.folds(x)) * (1 - k) + (0.55 + 0.05 * L.folds(x * 1.3 + 3.0)) * k
            h += 0.06 * noise.noise(Vector((x * 0.2, th * 3.0, 4.0)))
            line.append(bm.verts.new(hit + d * (0.2 + (h - 0.2) * edges(x, None))))
        g.append(line)
    for i in range(len(ths) - 1):
        for j in range(len(xs) - 1):
            q = (g[i][j], g[i][j + 1], g[i + 1][j + 1], g[i + 1][j])
            if None not in q:
                th = (ths[i] + ths[i + 1]) / 2
                face_against(bm.faces.new(q), -Vector((0, math.sin(th), math.cos(th))))

    # back hang
    def back_off(s, x, hit):
        h = 0.55 + 0.45 * L.folds(x * 1.3 + 3.0) * min(1.0, max(0.1, (yc - hit.y) / 12.0))
        if 0.35 < s < 2.0:
            h += 0.14
        return 0.2 + (h - 0.2) * edges(x, s)

    bk = region_bvh(low, reg, {RAIL, "back_side", "wing"})
    hang(bm, bk, ss, xs, lambda s, x: min(L.hem_back(x) + s, yc) if L.hem_back(x) + s < yc + 0.35 else None,
         1.0, back_off)
    ob = new_obj("hp_towel", bm, mats["towel"], low)
    return [ob]


def build_wire(low, reg, mats):
    """Wire wound round the split end of the round leg and down over its old rubber tip."""
    bvh = region_bvh(low, reg, {POLE, TIP})
    bm = bmesh.new()
    pts = []
    y = L.WIRE_Y[0]
    step = L.WIRE_PITCH / 24
    th = 0.0
    while y < L.WIRE_Y[1]:
        ax = Vector(L.pole_axis(y))
        d = Vector((math.cos(th), 0, math.sin(th)))
        hit, *_ = bvh.ray_cast(ax + d * 8.0, -d, 8.0)
        if hit is not None:
            pts.append(hit + d * (L.WIRE_R * 0.8))
        y += step
        th += math.tau / 24
    ring = 6
    rows = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        u = t.cross(Vector((0, 1, 0))).normalized()
        w = t.cross(u)
        rows.append([bm.verts.new(p + (u * math.cos(k * math.tau / ring) + w * math.sin(k * math.tau / ring)) * L.WIRE_R)
                     for k in range(ring)])
    for a, b in zip(rows, rows[1:]):
        if (a[0].co - b[0].co).length > 1.0:          # a missed ray: do not bridge
            continue
        for k in range(ring):
            bm.faces.new((a[k], a[(k + 1) % ring], b[(k + 1) % ring], b[k]))
    return [new_obj("hp_wire", bm, mats["wire"], low)]


def build(low, reg, seed=7):
    rng = random.Random(seed)
    mats = {k: id_material(k) for k in IDS}
    set_pass(mats.values(), "view")
    hp = [copy_regions(low, reg, set(IRON), "hp_iron", mats["base"]),
          copy_regions(low, reg, {"under"}, "hp_joists", mats["joist"]),
          copy_regions(low, reg, {"wing", "seat_edge", RAIL, *ARMS, POST_L, BLOCK}, "hp_frame", mats["frame"],
                       subdiv=3, wave=0.05, seed=1.0),
          copy_regions(low, reg, {POLE, POLE_TOP, TIP_END}, "hp_handle", mats["handle"], subdiv=2, wave=0.03, seed=2.0)]
    hp += build_seat(low, reg, mats, rng)
    hp += build_backrest(low, reg, mats, rng)
    hp += build_towel(low, reg, mats)
    hp += build_wire(low, reg, mats)
    return hp, mats


def build_cage(low, reg):
    me = low.data.copy()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bm.normal_update()
    push = {}
    for f in bm.faces:
        d = 3.0 if reg[f.index] in ("panel", "back_side", "wing", RAIL) else 1.2
        for v in f.verts:
            push[v.index] = max(push.get(v.index, 0), d)
    for v in bm.verts:
        v.co = v.co + v.normal * push.get(v.index, 1.2)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("cage", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.hide_render = True
    return ob


def bake(low, hp, cage, mats, size):
    scene = bpy.context.scene
    setup_cycles(scene)
    for attr in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission",
                 "visible_volume_scatter", "visible_shadow"):
        setattr(low, attr, False)
    if scene.world is None:
        scene.world = bpy.data.worlds.new("bake")
    scene.world.light_settings.distance = 6.0

    lm = bpy.data.materials.new("bake_target")
    lm.use_nodes = True
    low.data.materials.clear()
    low.data.materials.append(lm)
    tex = lm.node_tree.nodes.new("ShaderNodeTexImage")
    lm.node_tree.nodes.active = tex

    bk = scene.render.bake
    bk.use_selected_to_active = True
    bk.use_cage = True
    bk.cage_object = cage
    bk.max_ray_distance = 0.0
    bk.target = "IMAGE_TEXTURES"
    bk.normal_space = "TANGENT"
    bk.normal_r, bk.normal_g, bk.normal_b = "POS_X", "POS_Y", "POS_Z"  # OpenGL

    bpy.ops.object.select_all(action="DESELECT")
    for o in hp:
        o.select_set(True)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low

    OUT.mkdir(exist_ok=True)
    for name, kind, shader, samples in (("normal", "NORMAL", "view", 1), ("ao", "AO", "view", 64),
                                        ("curvature", "EMIT", "curvature", 16), ("id", "EMIT", "id", 1)):
        set_pass(mats.values(), shader)
        img = bpy.data.images.new(f"bake_{name}", size, size, alpha=False, float_buffer=True)
        img.colorspace_settings.name = "Non-Color"
        tex.image = img
        scene.cycles.samples = samples
        print(f"baking {name} ...", flush=True)
        bk.margin_type = "ADJACENT_FACES" if name == "id" else "EXTEND"
        bpy.ops.object.bake(type=kind, use_clear=True, margin=8)
        img.filepath_raw = str(OUT / f"{name}.png")
        img.file_format = "PNG"
        img.save()
        print("  ->", img.filepath_raw, flush=True)
    set_pass(mats.values(), "view")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 2048
    bpy.ops.wm.read_factory_settings(use_empty=True)
    low = load_low()
    reg = regions(low.data)
    hp, mats = build(low, reg)
    # split hard edges (> 40 deg) so the cage pushes each flat side along its own normal
    bm = bmesh.new()
    bm.from_mesh(low.data)
    sharp = [e for e in bm.edges if len(e.link_faces) == 2
             and e.link_faces[0].normal.angle(e.link_faces[1].normal, 0) > 0.7]
    bmesh.ops.split_edges(bm, edges=sharp)
    bm.to_mesh(low.data)
    bm.free()
    cage = build_cage(low, regions(low.data))
    print("high-poly:", {o.name: len(o.data.polygons) for o in hp}, flush=True)
    if "--nobake" not in argv:
        bake(low, hp, cage, mats, size)
    if "--blend" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "highpoly.blend"))
    print("done")


if __name__ == "__main__":
    main()
