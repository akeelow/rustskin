"""Sauna Bench v1: high-poly details modelled over the Bed and baked onto its UVs.

Concept A "bare bench" (the blanket is cut by alpha in the texture). Modelled:
  deck        13 aspen slats 7-9 cm along the bench over the mattress top: bevels, gaps, plane waves,
              one slat slightly twisted, one slat a thinner pallet board; a dark cavity under the gaps
  apron       two 9 cm boards on the mattress sides and ends
  nails       forged heads over the 10 cross slats (joists), some proud and tilted, one bent over
  leaves      a few dry birch leaves stuck in the foot half
  towel       the pillow: a folded linen towel, its front edge rolled into a bolster with a spiral
              on the ends, fold layers on the sides (displaced copy of the low-poly pillow)
  headboard   the two door boards: bevels, worn top edge, nails into the posts
  posts       aspen bars with bevels and a hewn top
Iron (rails, stretchers, plates) and the cross slats under the deck stay the low-poly's own shape
(their texels keep the original normal map in texture_v1.py).

Usage (from the repo root):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/bed/bake_bench.py -- [--size 2048] [--blend] [--nobake]

Writes bake/{normal,ao,curvature,id}.png. id.png: R = id * 16 + 8 (see IDS), G = random per part.
Model: centimetres, Z up (3ds Max export), +x head; piece numbers as in uv/parts.md.
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
ROOT = HERE.parents[2]
OBJ = HERE / "originals" / "bed.obj"
OUT = HERE / "bake"
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))
from parts import pieces  # noqa: E402
from uv_zones import load_obj  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_locker = _load("locker_door_v5", HERE.parent / "locker" / "door_v5_bake.py")
add_box, setup_cycles = _locker.add_box, _locker.setup_cycles
forged_nail, new_obj = _locker.forged_nail, _locker.new_obj

IDS = {"base": 0, "slat": 1, "pallet": 2, "apron": 3, "nail": 4, "leaf": 5, "cavity": 6,
       "headboard": 7, "post": 8, "towel": 9}
_locker.IDS = IDS                    # id_material/set_pass read the module's IDS
_locker.VIEW_COL.update({"slat": (0.72, 0.6, 0.42), "pallet": (0.55, 0.42, 0.28), "apron": (0.62, 0.5, 0.34),
                         "headboard": (0.42, 0.3, 0.2), "post": (0.66, 0.54, 0.36), "towel": (0.8, 0.77, 0.7)})
id_material, set_pass = _locker.id_material, _locker.set_pass

BLANKET, PILLOW, MATTRESS = 0, 1, 2
REPLACED = {BLANKET, PILLOW, MATTRESS, 3, 4, 5, 6, 20, 21}   # pieces the high-poly stands in for
# pieces whose UV duplicates another piece's: dropped from the bake target, so each shared texel
# is baked from one copy only (kept: head post 5, foot post 20, end rail 17, stretcher 19,
# bracket 23, side rail 27, cross slat 11)
DUPLICATES = {6, 21, 18, 22, 24, 25, 26, 28, 7, 8, 9, 10, 12, 13, 14, 15, 16}

# deck (mattress top z 54.6..55.4, flat part y -53..55)
DECK_X = (-111.0, 110.2)
DECK_Y = (-53.6, 55.6)
DECK_Z0, DECK_Z1 = 52.4, 55.05
N_SLATS, GAP = 13, 0.4
PALLET, TWISTED = 4, 9               # slat indices (from -y)
JOISTS = (-100.0, -82.0, -56.0, -27.5, -9.5, 21.5, 40.5, 67.0, 84.0, 100.5)   # cross slat centres, x
# apron (mattress sides bulge to y -54.2 / +56.3 at z 46; ends x -112.3 / +111.6)
APRON_Z = ((37.6, 46.25), (46.45, 54.7))
LEAVES = (  # x, y, length, angle (deg), surface z
    (-74.0, -31.2, 6.6, 12.0, DECK_Z1),            # v1.2: a third larger (in game they were dots)
    (-61.0, 6.4, 6.0, -70.0, DECK_Z1),
    (-96.0, 27.0, 7.0, 160.0, DECK_Z1),
    (-35.0, 47.7, 5.8, 95.0, DECK_Z1),
)
BENT_NAIL = (-56.0, -22.0)           # x, y: on the joist at x -56, bent over toward -x


# ---------------------------------------------------------------- low-poly
def piece_per_polygon(me):
    """Piece number for each Blender polygon, matched by vertex positions (the importer drops
    duplicate faces of the two-sided blanket, so polygon order differs from the OBJ)."""
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
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="Y", up_axis="Z")
    low = bpy.context.selected_objects[0]
    low.name = "lowpoly_bed"
    bpy.context.view_layer.objects.active = low
    low.select_set(True)
    bpy.ops.mesh.customdata_custom_splitnormals_clear()   # flat face normals for a sane tangent frame
    for p in low.data.polygons:
        p.use_smooth = False
    pp = piece_per_polygon(low.data)
    assert -1 not in pp, "polygons with no matching piece"
    return low, pp


def copy_pieces(low, pp, keep, name, mat):
    """A copy of the low-poly with only the polygons of pieces in `keep`."""
    me = low.data.copy()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.matrix_world = low.matrix_world.copy()
    me.materials.clear()
    me.materials.append(mat)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    kill = [f for f in bm.faces if pp[f.index] not in keep]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bm.to_mesh(me)
    bm.free()
    return ob


# ---------------------------------------------------------------- parts
def waves(verts, top_z, amp, freq, seed, along="x"):
    """Plane waves on the top face of a board-like box, stretched along the board."""
    for v in verts:
        if v.co.z > top_z - 0.05:
            p = Vector((v.co.x * freq * 0.12, v.co.y * freq, seed)) if along == "x" else \
                Vector((v.co.x * freq, v.co.y * freq * 0.12, seed))
            v.co.z += amp * noise.noise(p)


def build_deck(low, mats, rng):
    deck, pallet, nails, cav = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    widths = [rng.uniform(7.4, 9.0) for _ in range(N_SLATS)]
    k = (DECK_Y[1] - DECK_Y[0]) / sum(widths)
    y = DECK_Y[0]
    slats = []
    for i, w in enumerate(widths):
        w *= k
        slats.append((y + GAP / 2, y + w - GAP / 2))
        y += w
    for i, (y0, y1) in enumerate(slats):
        bm = pallet if i == PALLET else deck
        x0 = DECK_X[0] + rng.uniform(-0.4, 0.6)
        x1 = DECK_X[1] + rng.uniform(-0.6, 0.4)
        top = DECK_Z1 + rng.uniform(-0.12, 0.1) - (0.25 if i == PALLET else 0)
        edge = 1.4 if i in (0, N_SLATS - 1) else 0.45                  # outer slats follow the mattress round
        verts = add_box(bm, (x0, y0, DECK_Z0), (x1, y1, top), 0.35, 2)
        if i in (0, N_SLATS - 1):
            for v in verts:                                             # round the outer long edge down
                d = (v.co.y - y0) if i == 0 else (y1 - v.co.y)
                if d < edge and v.co.z > top - edge:
                    v.co.z -= (edge - d) ** 2 / edge * 0.55
        waves(verts, top - 0.1, 0.12 if i == PALLET else 0.06, 0.9, rng.uniform(0, 100))
        if i == TWISTED:                                                # a slight twist along the slat
            for v in verts:
                v.co.z += 0.22 * (v.co.x / 110.0) * ((v.co.y - (y0 + y1) / 2) / ((y1 - y0) / 2))
        # cup: the middle of the board a touch lower
        for v in verts:
            if v.co.z > top - 0.1:
                c = (v.co.y - (y0 + y1) / 2) / ((y1 - y0) / 2)
                v.co.z -= 0.05 * (1 - c * c)
        # nails over the joists: one or two per crossing, a few proud and tilted
        for jx in JOISTS:
            if (jx, i) == (BENT_NAIL[0], next(n for n, s in enumerate(slats) if s[0] <= BENT_NAIL[1] <= s[1])):
                continue
            if rng.random() < 0.22:
                continue
            n = 2 if rng.random() < 0.3 else 1
            for j in range(n):
                cy = (y0 + y1) / 2 + ((j - 0.5) * 3.4 if n == 2 else rng.uniform(-1.4, 1.4))
                proud = rng.random() < 0.1
                r = rng.uniform(0.34, 0.46)
                forged_nail(nails, jx + rng.uniform(-0.9, 0.9), cy, top + (0.18 if proud else 0.0), rng, r=r)
    # the bent nail: head plus shank lying on the board
    bx, by = BENT_NAIL
    forged_nail(nails, bx - 2.6, by, DECK_Z1 + 0.15, rng, r=0.42)
    shank = add_box(nails, (bx - 2.6, by - 0.17, DECK_Z1 - 0.05), (bx + 0.3, by + 0.17, DECK_Z1 + 0.28), 0.12, 1)
    for v in shank:
        v.co.z += 0.12 * max(0.0, (v.co.x - bx) / 3.0)
    # dark cavity under the gaps
    add_box(cav, (DECK_X[0] - 1, DECK_Y[0] - 1, DECK_Z0 - 0.6), (DECK_X[1] + 1, DECK_Y[1] + 1, DECK_Z0 - 0.2))
    return [new_obj("hp_deck", deck, mats["slat"], low), new_obj("hp_pallet", pallet, mats["pallet"], low),
            new_obj("hp_deck_nails", nails, mats["nail"], low), new_obj("hp_deck_cavity", cav, mats["cavity"], low)], slats


def mattress_bvh(low, pp, mats):
    ob = copy_pieces(low, pp, {MATTRESS}, "tmp_mattress", mats["base"])
    bvh = BVHTree.FromObject(ob, bpy.context.evaluated_depsgraph_get())
    bpy.data.objects.remove(ob)
    return bvh


def hug(bvh, p, axis, sign, off=0.3):
    """Coordinate on `axis` of the mattress surface seen from outside at p (+ off outward), or None."""
    o = p.copy()
    o[axis] += sign * 30.0
    d = Vector((0, 0, 0))
    d[axis] = -sign
    hit, *_ = bvh.ray_cast(o, d, 40.0)
    return None if hit is None else hit[axis] + sign * off


def build_apron(low, mats, rng, bvh):
    bm, nails, cav = bmesh.new(), bmesh.new(), bmesh.new()
    sides = (  # (axis, outer, inner, along range)
        ("y", -55.3, -52.6, (-111.6, 110.9)),
        ("y", 56.2, 53.2, (-111.6, 110.9)),
        ("x", -112.6, -109.6, (-52.8, 55.2)),
        ("x", 111.9, 108.9, (-52.8, 55.2)),
    )
    for axis, outer, inner, (a0, a1) in sides:
        lo_o, hi_o = min(outer, inner), max(outer, inner)
        for (z0, z1) in APRON_Z:
            if axis == "y":
                verts = add_box(bm, (a0, lo_o, z0), (a1, hi_o, z1), 0.35, 2)
            else:
                verts = add_box(bm, (lo_o, a0, z0), (hi_o, a1, z1), 0.35, 2)
            seed = rng.uniform(0, 100)
            ax = 1 if axis == "y" else 0
            s = 1 if outer > 0 else -1
            for v in verts:                 # outer face follows the bulging mattress side, 3 mm proud
                if abs(v.co[ax] - outer) < 0.6:
                    depth = outer - v.co[ax]                            # keep the bevel profile
                    q = v.co.copy()
                    q.z = min(max(q.z, 38.6), 54.4)
                    if ax == 1:
                        q.x = min(max(q.x, -108.0), 107.0)
                    else:
                        q.y = min(max(q.y, -50.0), 52.0)
                    h = hug(bvh, q, ax, s)
                    if h is not None:
                        along = v.co.x if axis == "y" else v.co.y
                        v.co[ax] = h - depth + s * 0.07 * noise.noise(Vector((along * 0.1, v.co.z * 0.9, seed)))
            # nails: near both ends and every ~50 cm
            n = max(2, int((a1 - a0) / 50) + 1)
            for j in range(n):
                t = (j + 0.5) / n if n > 2 else (0.06 if j == 0 else 0.94)
                a = a0 + (a1 - a0) * t + rng.uniform(-2, 2)
                zc = (z0 + z1) / 2 + rng.uniform(-1.2, 1.2)
                nb = bmesh.new()
                forged_nail(nb, 0, 0, 0, rng, r=rng.uniform(0.36, 0.45))
                q = Vector((a, 0, zc)) if axis == "y" else Vector((0, a, zc))
                q[ax] = outer
                if ax == 1:
                    q.x = min(max(q.x, -108.0), 107.0)
                else:
                    q.y = min(max(q.y, -50.0), 52.0)
                face = hug(bvh, q, ax, s) or outer
                for v in nb.verts:                                       # lay the nail head on the side face
                    lx, ly, lz = v.co
                    if axis == "y":
                        v.co = Vector((a + lx, face + s * lz, zc + ly))
                    else:
                        v.co = Vector((face + s * lz, a + lx, zc + ly))
                tmp = bpy.data.meshes.new("tmp")
                nb.to_mesh(tmp)
                nb.free()
                nails.from_mesh(tmp)
                bpy.data.meshes.remove(tmp)
    # cavity behind the apron gap
    add_box(cav, (-110.0, -52.0, 39.0), (109.0, 52.6, 53.0))
    return [new_obj("hp_apron", bm, mats["apron"], low), new_obj("hp_apron_nails", nails, mats["nail"], low),
            new_obj("hp_apron_cavity", cav, mats["cavity"], low)]


def build_headboard(low, mats, rng):
    bm, nails = bmesh.new(), bmesh.new()
    for (z0, z1, y0, y1) in ((47.4, 64.6, -62.4, 64.7), (63.9, 82.2, -62.8, 64.5)):
        verts = add_box(bm, (110.3, y0, z0), (112.8, y1, z1), 0.3, 2)
        seed = rng.uniform(0, 100)
        for v in verts:
            if v.co.x < 110.4 or v.co.x > 112.7:                       # waves on both faces
                v.co.x += 0.06 * noise.noise(Vector((v.co.y * 0.1, v.co.z * 0.8, seed)))
            if z1 > 80 and v.co.z > z1 - 1.0:                          # worn round top edge
                c = abs(v.co.x - 111.55) / 1.25
                v.co.z -= 0.5 * c * c
        for yc in (-54.0, 56.5):                                        # nails into the posts, inner face
            for dz in (-3.5, 3.5):
                nb = bmesh.new()
                forged_nail(nb, 0, 0, 0, rng, r=rng.uniform(0.4, 0.5))
                for v in nb.verts:
                    lx, ly, lz = v.co
                    v.co = Vector((110.3 - lz, yc + lx + rng.uniform(-0.05, 0.05), (z0 + z1) / 2 + dz + ly))
                tmp = bpy.data.meshes.new("tmp")
                nb.to_mesh(tmp)
                nb.free()
                nails.from_mesh(tmp)
                bpy.data.meshes.remove(tmp)
    return [new_obj("hp_headboard", bm, mats["headboard"], low), new_obj("hp_headboard_nails", nails, mats["nail"], low)]


def build_posts(low, mats, rng):
    bm = bmesh.new()
    for (x0, x1, y0, y1, z1) in ((112.7, 117.3, -60.4, -47.4, 89.1), (112.7, 117.3, 50.0, 63.0, 89.1),
                                 (-117.5, -112.8, -60.4, -47.6, 62.3), (-117.5, -112.8, 50.0, 62.8, 62.3)):
        verts = add_box(bm, (x0, y0, -3.8), (x1, y1, z1), 0.4, 2)
        seed = rng.uniform(0, 100)
        for v in verts:
            if v.co.z > z1 - 0.5:                                       # hewn top: sloped toward the outside
                out = (v.co.x - x0) / (x1 - x0) if x0 > 0 else (x1 - v.co.x) / (x1 - x0)
                v.co.z -= 1.6 * out + 0.3 * noise.noise(Vector((v.co.x, v.co.y, seed)))
            else:
                for ax in (0, 1):
                    v.co[ax] += 0.05 * noise.noise(Vector((v.co.z * 0.08, ax * 5.0, seed)))
    return [new_obj("hp_posts", bm, mats["post"], low)]


def build_leaves(low, mats, rng):
    _locker.LEAVES = LEAVES
    return _locker.build_leaves(low, mats, rng)


def build_towel(low, pp, mats):
    """The pillow as a folded towel: subdivided copy displaced along its normals.
    Front (x < 72): a rolled bolster, spiral grooves on its ends; behind: fold layers 3.2 cm."""
    ob = copy_pieces(low, pp, {PILLOW}, "hp_towel", mats["towel"])
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    for _ in range(4):
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    # smooth the low-poly facets a little (keeps the volume)
    for _ in range(6):
        bmesh.ops.smooth_vert(bm, verts=bm.verts[:], factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.normal_update()
    ROLL_X, ROLL_Z, FOLD_X = 65.0, 60.3, 72.0
    moves = []
    for v in bm.verts:
        n = v.normal
        x, y, z = v.co
        d = 0.18 * noise.noise(Vector((x * 0.12, y * 0.05, z * 0.12))) + 0.06 * noise.noise(Vector((x * 0.6, y * 0.6, z * 0.6)))
        if abs(n.y) > 0.55:                                            # ends of the towel
            if x < FOLD_X + 1.0:
                r = math.hypot(x - ROLL_X, (z - ROLL_Z) * 1.15)
                th = math.atan2(z - ROLL_Z, x - ROLL_X) / math.tau
                f = ((r - 0.4 - 1.8 * th) / 1.8) % 1.0
                d -= 0.9 * math.exp(-((min(f, 1 - f) / 0.17) ** 2)) * min(1.0, r / 1.5)
            else:
                f = ((z - 54.0) / 3.2) % 1.0
                d -= 0.8 * math.exp(-((min(f, 1 - f) / 0.14) ** 2))
        elif n.x > 0.55:                                               # back face toward the headboard: layers
            f = ((z - 54.0) / 3.2) % 1.0
            d -= 0.7 * math.exp(-((min(f, 1 - f) / 0.12) ** 2))
        if n.z > 0.4:
            d -= 3.0 * math.exp(-(((x - FOLD_X) / 1.9) ** 2))           # the fold between bolster and stack (v1.2 deeper)
            d += 0.7 * math.exp(-(((x - ROLL_X) / 4.5) ** 2))           # the bolster rounder
            d += 0.25 * math.exp(-(((abs(y) - 41.0) / 0.6) ** 2))      # hems near the towel's ends
            d -= 0.5 * math.exp(-(((x - 90.0) / 2.2) ** 2)) * (0.6 + 0.4 * noise.noise(Vector((y * 0.08, 3.0, 0.0))))
        moves.append((v, n.copy() * d))
    for v, m in moves:
        v.co += m
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return [ob]


def build_cage(low, pp):
    me = low.data.copy()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bm.normal_update()
    push = {}
    for f in bm.faces:
        d = 3.5 if pp[f.index] == PILLOW else 2.0
        for v in f.verts:
            push[v.index] = max(push.get(v.index, 0), d)
    for v in bm.verts:
        v.co = v.co + v.normal * push.get(v.index, 2.0)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("cage", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.matrix_world = low.matrix_world.copy()
    ob.hide_render = True
    return ob


def build(low, pp, seed=6):
    rng = random.Random(seed)
    mats = {k: id_material(k) for k in IDS}
    set_pass(mats.values(), "view")
    keep = {n for n in set(pp) if n not in REPLACED}
    hp = [copy_pieces(low, pp, keep, "hp_base", mats["base"])]
    deck, _ = build_deck(low, mats, rng)
    hp += deck
    hp += build_apron(low, mats, rng, mattress_bvh(low, pp, mats))
    hp += build_headboard(low, mats, rng)
    hp += build_posts(low, mats, rng)
    hp += build_leaves(low, mats, rng)
    hp += build_towel(low, pp, mats)
    return hp, mats


def bake(low, hp, cage, mats, size):
    scene = bpy.context.scene
    setup_cycles(scene)
    for attr in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission",
                 "visible_volume_scatter", "visible_shadow"):
        setattr(low, attr, False)
    if scene.world is None:
        scene.world = bpy.data.worlds.new("bake")
    scene.world.light_settings.distance = 8.0

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
    low, pp = load_low()
    hp, mats = build(low, pp)
    bm = bmesh.new()
    bm.from_mesh(low.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if pp[f.index] in DUPLICATES], context="FACES")
    # split hard edges (> 40 deg): the cage then pushes each flat side along its own normal; with
    # shared corner vertices it moved diagonally and rays from a post's side ran through the
    # headboard boards next to it
    sharp = [e for e in bm.edges if len(e.link_faces) == 2
             and e.link_faces[0].normal.angle(e.link_faces[1].normal, 0) > 0.7]
    bmesh.ops.split_edges(bm, edges=sharp)
    bm.to_mesh(low.data)
    bm.free()
    pp = piece_per_polygon(low.data)
    cage = build_cage(low, pp)
    print("high-poly:", {o.name: len(o.data.polygons) for o in hp}, flush=True)
    if "--nobake" not in argv:
        bake(low, hp, cage, mats, size)
    if "--blend" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "highpoly.blend"))
    print("done")


if __name__ == "__main__":
    main()
