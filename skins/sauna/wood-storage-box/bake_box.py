"""Sauna Stone Box v1: high-poly details modelled over the Wood Storage Box and baked onto its UVs.

Concept D, open top (the lid is cut with alpha in the textures). Modelled:
  stones   ~60 basalt stones on the floor: squashed, chipped icospheres, packed with gaps between them
  coals    a lumpy bed of charcoal between and under the stones (the embers glow there in texture_v1.py)
  tray     the steel sheet on the floor (2.5 cm short of the walls) with a turned-up rim
  hoops    two iron hoops round the outer walls, 2.5 mm proud, domed rivets every 12 cm
The walls themselves keep the original normal map (texture_v1.py), only the hoops are taken from here.

Bake target: only the faces the client really shows with their own texels - the four outer walls and the
inner floor (the in-game test: inner walls wear the outer ones; the lid goes; the outer bottom shares the
floor's texels and is never seen). Their UVs are shifted into 0..1 per face first (the floor sits at
v 1.84..2.0 in the OBJ; the client samples it there as a repeat).

Usage (from the repo root):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/wood-storage-box/bake_box.py -- [--size 2048] [--blend] [--nobake]

Writes bake/{normal,ao,id}.png. id.png: R = id * 16 + 8 (see IDS), G = random per part.
Model: the OBJ (metres, Y up) scaled to centimetres, axes kept: y up, +z front (the handle-slot end).
"""
import importlib.util
import math
import random
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector, noise
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
OBJ = HERE / "originals" / "box.wooden.obj"
OUT = HERE / "bake"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_locker = _load("locker_door_v5", HERE.parent / "locker" / "door_v5_bake.py")
setup_cycles, new_obj = _locker.setup_cycles, _locker.new_obj
IDS = {"base": 0, "stone": 1, "coal": 2, "tray": 3, "hoop": 4, "rivet": 5}
_locker.IDS = IDS
_locker.VIEW_COL.update({"base": (0.55, 0.5, 0.42), "stone": (0.18, 0.18, 0.19), "coal": (0.05, 0.045, 0.04),
                         "tray": (0.25, 0.18, 0.14), "hoop": (0.15, 0.13, 0.12), "rivet": (0.2, 0.18, 0.16)})
id_material, set_pass = _locker.id_material, _locker.set_pass

# cm, OBJ axes (y up, +z front)
FLOOR_Y = 2.4                         # inner floor 2.38..3.34 (slightly warped)
INNER = (-33.6, 31.6, -43.8, 45.1)    # inner floor x0, x1, z0, z1
TRAY_IN = 2.5                         # tray stops this short of the walls
COAL_IN = 4.0                         # the coal bed stops this short of the walls
HOOPS = ((4.5, 9.0), (31.0, 35.5))    # y0, y1 (same as blocking.py)
HOOP_T = 0.25
RIVET_STEP, RIVET_R = 12.0, 0.55
SEED = 17


# ---------------------------------------------------------------- low-poly
def load_low():
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="Y", up_axis="Z")   # keep the OBJ's axes
    low = bpy.context.selected_objects[0]
    low.name = "lowpoly_box"
    for v in low.data.vertices:
        v.co *= 100.0
    bpy.context.view_layer.objects.active = low
    low.select_set(True)
    bpy.ops.mesh.customdata_custom_splitnormals_clear()
    for p in low.data.polygons:
        p.use_smooth = False
    low.data.update()
    return low


def face_kind(p, me):
    """'floor', 'front', 'back', 'left', 'right' (outer walls) or None for everything else."""
    n, c = p.normal, p.center
    ys = [me.vertices[i].co.y for i in p.vertices]
    if max(ys) < 3.5 and n.y > 0.7 and c.y < 3.5:
        return "floor"
    if c.y > 53.3 or max(ys) > 53.6:
        return None
    for name, ax, sgn in (("right", 0, 1), ("left", 0, -1), ("front", 2, 1), ("back", 2, -1)):
        if abs(n[ax]) > 0.7 and n[ax] * sgn > 0 and c[ax] * sgn > 30:
            return name
    return None


def bake_target(low):
    """A copy of the low-poly with only the outer walls and the inner floor, UVs shifted into 0..1."""
    me = low.data.copy()
    ob = bpy.data.objects.new("bake_target", me)
    bpy.context.scene.collection.objects.link(ob)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    kinds = {f.index: face_kind(me.polygons[f.index], me) for f in bm.faces}
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if kinds[f.index] is None], context="FACES")
    uv = bm.loops.layers.uv.active
    for f in bm.faces:
        du = math.floor(min(l[uv].uv.x for l in f.loops) + 1e-6)
        dv = math.floor(min(l[uv].uv.y for l in f.loops) + 1e-6)
        for l in f.loops:
            l[uv].uv.x -= du
            l[uv].uv.y -= dv
    bm.to_mesh(me)
    bm.free()
    return ob


def build_cage(target):
    me = target.data.copy()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bm.normal_update()
    # every face its own verts, pushed along its own normal: 15 cm up from the floor (over the stones),
    # 1 cm out from the walls (over the hoops)
    bmesh.ops.split_edges(bm, edges=list(bm.edges))
    bm.faces.ensure_lookup_table()
    for f in bm.faces:
        d = 15.0 if f.normal.y > 0.7 else 1.0
        for v in f.verts:
            v.co = v.co + f.normal * d
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("cage", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.hide_render = True
    return ob


# ---------------------------------------------------------------- high-poly
def base_copy(low, mat):
    """The whole low-poly as it is (walls, floor, inner walls as occluders), id 'base'."""
    me = low.data.copy()
    me.materials.clear()
    me.materials.append(mat)
    ob = bpy.data.objects.new("hp_base", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def build_hoops(low, mat_hoop, mat_rivet, rng):
    """Outer wall faces cut to the hoop's height, pushed out by HOOP_T with sides; rivets on top."""
    hoops = []
    for k, (y0, y1) in enumerate(HOOPS):
        bm = bmesh.new()
        bm.from_mesh(low.data)
        bm.faces.ensure_lookup_table()
        me = low.data
        keep = {f.index for f in bm.faces if face_kind(me.polygons[f.index], me) not in (None, "floor")}
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in keep], context="FACES")
        for yc, sgn in ((y0, 1), (y1, -1)):
            geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
            bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, yc, 0), plane_no=(0, sgn, 0), clear_inner=True)
        bm.normal_update()
        ext = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
        for v in [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]:
            n = Vector((0, 0, 0))
            for f in v.link_faces:
                n += f.normal
            v.co += n.normalized() * HOOP_T if n.length else Vector()
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        ob = new_obj(f"hp_hoop{k}", bm, mat_hoop, low)
        for p in ob.data.polygons:        # flat: smoothing into the sides tilted the hoop's face
            p.use_smooth = False
        hoops.append(ob)
    # rivets: cast from outside onto the hoops along each wall
    bpy.context.view_layer.update()
    rivets = bmesh.new()
    for ob in hoops:
        bvh = BVHTree.FromObject(ob, bpy.context.evaluated_depsgraph_get())
        ys = [v.co.y for v in ob.data.vertices]
        yc = (min(ys) + max(ys)) / 2
        lines = [((t, yc, 80.0), (0, 0, -1)) for t in _steps(-31.0, 30.0)] + \
                [((t, yc, -80.0), (0, 0, 1)) for t in _steps(-31.0, 30.0)] + \
                [((80.0, yc, t), (-1, 0, 0)) for t in _steps(-43.0, 44.0)] + \
                [((-80.0, yc, t), (1, 0, 0)) for t in _steps(-43.0, 44.0)]
        for o, d in lines:
            hit = bvh.ray_cast(Vector(o), Vector(d))
            if hit[0] is None:
                continue
            p, n = hit[0], hit[1]
            if n.dot(Vector(d)) > 0:
                n = -n
            res = bmesh.ops.create_uvsphere(rivets, u_segments=12, v_segments=8, radius=RIVET_R)
            for v in res["verts"]:
                local = v.co.copy()
                # flatten into a dome: squash along the normal, keep the outer half
                along = local.dot(n)
                v.co = p + (local - n * along) + n * max(along, -0.05) * 0.55
    rv = new_obj("hp_rivets", rivets, mat_rivet, low)
    return hoops + [rv]


def _steps(a, b):
    t = a + RIVET_STEP / 2
    while t < b:
        yield t
        t += RIVET_STEP


def build_tray(low, mat):
    """Steel sheet 2 mm thick on the floor, 2.5 cm short of the walls, with a turned-up rim 1.2 cm."""
    x0, x1, z0, z1 = INNER[0] + TRAY_IN, INNER[1] - TRAY_IN, INNER[2] + TRAY_IN, INNER[3] - TRAY_IN
    bm = bmesh.new()
    y = FLOOR_Y + 1.0
    _box(bm, x0, x1, FLOOR_Y - 0.5, y, z0, z1)
    for a in ((x0, x0 + 0.25, z0, z1), (x1 - 0.25, x1, z0, z1), (x0, x1, z0, z0 + 0.25), (x0, x1, z1 - 0.25, z1)):
        _box(bm, a[0], a[1], y, y + 1.2, a[2], a[3])
    return new_obj("hp_tray", bm, mat, low)


def _box(bm, x0, x1, y0, y1, z0, z1):
    vs = [bm.verts.new((x, y, z)) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
        bm.faces.new([vs[i] for i in f])


def stone_layout(rng):
    """Dart throwing in the tray: centres at least 7 cm apart; radius from the nearest neighbour, a touch
    over half of it, so the stones lie packed against each other with narrow deep seams (v1 first try:
    8.5 cm apart and 0.46 of it - sparse dark blobs on the coal, the seams too open to glow)."""
    x0, x1 = INNER[0] + TRAY_IN + 3.5, INNER[1] - TRAY_IN - 3.5
    z0, z1 = INNER[2] + TRAY_IN + 3.5, INNER[3] - TRAY_IN - 3.5
    pts = []
    for _ in range(30000):
        p = (rng.uniform(x0, x1), rng.uniform(z0, z1))
        if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 > 7.0 ** 2 for q in pts):
            pts.append(p)
    out = []
    for p in pts:
        d = min(math.dist(p, q) for q in pts if q is not p)
        out.append((p[0], p[1], min(max(0.5 * d * 1.08, 3.4), 6.2)))
    return out


def build_stones(low, mat, rng):
    bm_all = []
    for k, (cx, cz, r) in enumerate(stone_layout(rng)):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=4, radius=1.0)
        sx, sz = r * rng.uniform(0.85, 1.1), r * rng.uniform(0.85, 1.1)
        h = r * rng.uniform(0.6, 0.85)
        rot = rng.uniform(0, math.tau)
        off = Vector((k * 7.3, k * 3.1, k * 5.7))
        for v in bm.verts:
            p = v.co.copy()
            # chipped basalt: a few flat facets (clamped planes) + fine noise
            d = 1.0 + 0.18 * noise.noise(p * 1.4 + off) + 0.05 * noise.noise(p * 5.0 + off)
            p *= d
            for j in range(4):
                a = Vector((math.cos(j * 1.7 + k), 0.35 * math.sin(j * 2.3 + k), math.sin(j * 1.7 + k))).normalized()
                lim = 0.82 + 0.1 * math.sin(j * 3.1 + k * 1.3)
                t = p.dot(a)
                if t > lim:
                    p -= a * (t - lim)
            if p.y < -0.35:                       # sits on the coals: flattened underside
                p.y = -0.35 + (p.y + 0.35) * 0.3
            x, z = p.x * math.cos(rot) - p.z * math.sin(rot), p.x * math.sin(rot) + p.z * math.cos(rot)
            v.co = Vector((cx + x * sx, FLOOR_Y + 1.4 + (p.y + 0.35) * h, cz + z * sz))
        bm_all.append(new_obj(f"hp_stone{k}", bm, mat, low))
    return bm_all


def build_coals(low, mat):
    """A lumpy bed of charcoal under and between the stones: a displaced grid, 4 mm cells."""
    x0, x1, z0, z1 = INNER[0] + COAL_IN, INNER[1] - COAL_IN, INNER[2] + COAL_IN, INNER[3] - COAL_IN
    bm = bmesh.new()
    nx, nz = int((x1 - x0) / 0.4), int((z1 - z0) / 0.4)
    rows = []
    for i in range(nz + 1):
        z = z0 + (z1 - z0) * i / nz
        row = []
        for j in range(nx + 1):
            x = x0 + (x1 - x0) * j / nx
            edge = min(x - x0, x1 - x, z - z0, z1 - z)
            lump = 0.9 * abs(noise.noise(Vector((x * 0.45, z * 0.45, 0.3)))) + 0.4 * noise.noise(Vector((x * 1.3, z * 1.3, 2.1)))
            y = FLOOR_Y + 1.0 + (1.3 + lump) * min(1.0, edge / 2.5)
            row.append(bm.verts.new((x, y, z)))
        rows.append(row)
    for i in range(nz):
        for j in range(nx):
            bm.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        if f.normal.y < 0:
            f.normal_flip()
    return new_obj("hp_coals", bm, mat, low)


def build(low):
    rng = random.Random(SEED)
    mats = {k: id_material(k) for k in IDS}
    hp = [base_copy(low, mats["base"])]
    hp += build_hoops(low, mats["hoop"], mats["rivet"], rng)
    hp.append(build_tray(low, mats["tray"]))
    hp.append(build_coals(low, mats["coal"]))
    hp += build_stones(low, mats["stone"], rng)
    return hp, mats


# ---------------------------------------------------------------- bake
def bake(target, hp, cage, mats, size):
    scene = bpy.context.scene
    setup_cycles(scene)
    if scene.world is None:
        scene.world = bpy.data.worlds.new("bake")
    scene.world.light_settings.distance = 8.0
    lm = bpy.data.materials.new("bake_target")
    lm.use_nodes = True
    target.data.materials.clear()
    target.data.materials.append(lm)
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
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    OUT.mkdir(exist_ok=True)
    for name, kind, shader, samples in (("normal", "NORMAL", "view", 1), ("ao", "AO", "view", 64),
                                        ("id", "EMIT", "id", 1)):
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
    target = bake_target(low)
    hp, mats = build(low)
    low.hide_render = True
    cage = build_cage(target)
    print("high-poly:", len(hp), "objects,", sum(len(o.data.polygons) for o in hp), "polygons", flush=True)
    if "--nobake" not in argv:
        bake(target, hp, cage, mats, size)
    if "--blend" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "highpoly.blend"))
    print("done")


if __name__ == "__main__":
    main()
