"""Sauna Changing Locker v5: the middle door modelled in Blender and baked onto its UVs.

v4 cut all three doors with alpha; a key lock or code lock is mounted on the middle door
(locker_door_b, lock centre at about x +2, y 102 cm; a code lock covers x -11..15, y 87..117),
so it floated in front of the open niche. v5 keeps the middle door solid and makes it the
centrepiece: tongue-and-groove boards on three battens (the battens are the low-poly's own),
and on it
  top field       a sauna thermometer and hygrometer (round dials in brass bezels)
  window field    a small window with a frosted pane and a sill (left), room for the burned map (right)
  lock field      an iron plate under the lock, a kicked-in board with splinters (right)
  everywhere      forged nails, birch leaves stuck to the wood
The decals with no real depth (burned map, boot print, finger heart in the steam, drops,
tally notches, scratches, grime) are drawn in texture_v5.py.

Usage (from the repo root):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/locker/door_v5_bake.py -- [--size 4096] [--blend]

Writes bake/door_{normal,ao,curvature,id}.png (OBJ units are cm; only the middle door's texels
are meaningful). id.png: R = material id * 16 + 8 (see IDS), G = random value per part.
"""
import importlib.util
import math
import random
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector, noise

HERE = Path(__file__).resolve().parent
OBJ = HERE / "originals" / "locker.obj"
OUT = HERE / "bake"

_spec = importlib.util.spec_from_file_location("stove_bake_v2", HERE.parent / "electric-furnace" / "bake_v2.py")
_stove = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_stove)
add_box, setup_cycles = _stove.add_box, _stove.setup_cycles

IDS = {"base": 0, "board": 1, "batten": 2, "nail": 3, "frame": 4, "glass": 5, "sill": 6, "plate": 7,
       "screw": 8, "dial_wood": 9, "bezel": 10, "face": 11, "needle": 12, "leaf": 13, "cavity": 14}

# the door (low-poly): x -26.68..25.58, y 48..219.6; plank faces z 26.2..27.35, battens 27.4..28.9
X0, X1, Y0, Y1 = -26.68, 25.58, 47.9, 219.7
BOARD_Z0, BOARD_Z1 = 25.6, 27.4
BATTEN_Z1 = 28.9
BATTENS = ((60.95, 69.06), (127.81, 135.91), (191.66, 199.77))
N_BOARDS, GAP = 6, 0.35
WINDOW = (-24.5, -3.5, 140.0, 187.5)            # frame outer: x0, x1, y0, y1
FRAME_W = 2.6
PLATE = (-8.0, 12.0, 89.0, 115.0)                # under the lock (hidden when locked)
BREAK = dict(board=5, lo=(70.5, 79.0), hi=(101.0, 112.0))   # kicked-in board: lower and upper fracture bands
DIALS = ((-13.3, 208.8), (11.6, 208.8))          # thermometer, hygrometer centres
DIAL_R = 7.0
LEAVES = (  # x, y, length, angle (deg), surface z
    (-13.0, 138.9, 5.2, 74.0, 29.6),            # on the sill
    (-19.5, 53.5, 5.6, -28.0, 27.4),
    (6.0, 51.0, 4.8, 37.0, 27.4),
    (17.5, 65.0, 5.0, 112.0, 28.9),             # on the bottom batten
    (22.0, 153.0, 4.4, -61.0, 27.4),
)


# ---------------------------------------------------------------- scene helpers
def new_obj(name, bm, mat, low):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.matrix_world = low.matrix_world.copy()
    me.materials.append(mat)
    return ob


def id_material(name):
    m = bpy.data.materials.new(f"hp_{name}")
    m.use_nodes = True
    m["bake_id"] = IDS[name]
    return m


VIEW_COL = {"board": (0.62, 0.42, 0.24), "batten": (0.36, 0.22, 0.12), "nail": (0.15, 0.15, 0.15),
            "frame": (0.55, 0.36, 0.2), "glass": (0.85, 0.8, 0.7), "sill": (0.55, 0.36, 0.2),
            "plate": (0.2, 0.2, 0.2), "screw": (0.3, 0.3, 0.3), "dial_wood": (0.36, 0.22, 0.12),
            "bezel": (0.6, 0.45, 0.2), "face": (0.9, 0.86, 0.75), "needle": (0.6, 0.1, 0.05),
            "leaf": (0.65, 0.55, 0.15), "cavity": (0.03, 0.02, 0.01)}


def set_pass(mats, kind):
    for m in mats:
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        if kind == "id":
            em = nt.nodes.new("ShaderNodeEmission")
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            comb = nt.nodes.new("ShaderNodeCombineColor")
            comb.inputs[0].default_value = (m["bake_id"] * 16 + 8) / 255.0
            comb.inputs[2].default_value = 0.0
            nt.links.new(geo.outputs["Random Per Island"], comb.inputs[1])
            nt.links.new(comb.outputs[0], em.inputs["Color"])
            nt.links.new(em.outputs[0], out.inputs["Surface"])
        elif kind == "curvature":
            em = nt.nodes.new("ShaderNodeEmission")
            ao_in = nt.nodes.new("ShaderNodeAmbientOcclusion")
            ao_in.inside = True
            ao_in.samples = 16
            ao_in.inputs["Distance"].default_value = 0.4
            ao_out = nt.nodes.new("ShaderNodeAmbientOcclusion")
            ao_out.samples = 16
            ao_out.inputs["Distance"].default_value = 0.4
            sub = nt.nodes.new("ShaderNodeMath")
            sub.operation = "SUBTRACT"
            nt.links.new(ao_out.outputs["AO"], sub.inputs[0])
            nt.links.new(ao_in.outputs["AO"], sub.inputs[1])
            ma = nt.nodes.new("ShaderNodeMath")
            ma.operation = "MULTIPLY_ADD"
            ma.inputs[1].default_value = 0.5
            ma.inputs[2].default_value = 0.5
            ma.use_clamp = True
            nt.links.new(sub.outputs[0], ma.inputs[0])
            nt.links.new(ma.outputs[0], em.inputs["Color"])
            nt.links.new(em.outputs[0], out.inputs["Surface"])
        else:
            bs = nt.nodes.new("ShaderNodeBsdfDiffuse")
            bs.inputs["Color"].default_value = (*VIEW_COL.get(m.name[3:], (0.5, 0.5, 0.5)), 1)
            nt.links.new(bs.outputs[0], out.inputs["Surface"])


def waves(verts, top_z, amp, freq, seed):
    """Adze/plane waves and a slight cup on the top face of a board-like box."""
    for v in verts:
        if v.co.z > top_z - 0.05:
            v.co.z += amp * noise.noise(Vector((v.co.x * freq, v.co.y * freq * 0.15, seed)))


def forged_nail(bm, x, y, z, rng, r=0.55):
    """Square-ish domed forged nail head sitting on z."""
    res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    rot = rng.uniform(0, math.pi / 2)
    c, s = math.cos(rot), math.sin(rot)
    for v in res["verts"]:
        p = v.co.copy()
        # squash a sphere toward a square dome
        sq = max(abs(p.x), abs(p.y)) + 1e-6
        k = 0.75 + 0.25 * (math.hypot(p.x, p.y) / sq if sq > 1e-3 else 1)
        px, py = p.x * r * k, p.y * r * k
        v.co = Vector((x + c * px - s * py, y + s * px + c * py, z - 0.05 + max(p.z, -0.2) * 0.22))


def screw(bm, x, y, z, rng, r=0.45):
    res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    ang = rng.uniform(0, math.pi)
    for v in res["verts"]:
        p = v.co.copy()
        h = max(p.z, -0.2) * 0.18
        # the slot
        d = abs(-math.sin(ang) * p.x + math.cos(ang) * p.y)
        if d < 0.16 and p.z > 0.3:
            h -= 0.1
        v.co = Vector((x + p.x * r, y + p.y * r, z - 0.03 + h))


# ---------------------------------------------------------------- parts
def board_box(bm, x0, x1, y0, y1, rng, seed):
    verts = add_box(bm, (x0, y0, BOARD_Z0), (x1, y1, BOARD_Z1 + rng.uniform(-0.08, 0.08)), 0.25, 2)
    waves(verts, BOARD_Z1 - 0.1, 0.07, 0.9, seed)
    return verts


def build_boards(low, mats, rng):
    bm = bmesh.new()
    nails = bmesh.new()
    w = (X1 - X0) / N_BOARDS
    wx0, wx1, wy0, wy1 = WINDOW
    hole_x0, hole_x1 = wx0 + FRAME_W * 0.5, wx1 - FRAME_W * 0.5      # boards end under the frame
    hole_y0, hole_y1 = wy0 + FRAME_W * 0.5, wy1 - FRAME_W * 0.5
    for i in range(N_BOARDS):
        s0 = X0 + i * w + GAP / 2
        s1 = X0 + (i + 1) * w - GAP / 2
        seed = rng.uniform(0, 100)
        if i == BREAK["board"]:
            build_broken_board(bm, s0, s1, rng, seed)
            continue
        if s1 <= hole_x0 or s0 >= hole_x1:
            board_box(bm, s0, s1, Y0, Y1, rng, seed)
            continue
        # the board passes the window: below it, above it, and the side strips beside the pane
        board_box(bm, s0, s1, Y0, hole_y0, rng, seed)
        board_box(bm, s0, s1, hole_y1, Y1, rng, seed)
        if s0 < hole_x0:
            board_box(bm, s0, hole_x0, hole_y0, hole_y1, rng, seed)
        if s1 > hole_x1:
            board_box(bm, hole_x1, s1, hole_y0, hole_y1, rng, seed)
    # forged nails: one per board at each batten (two on wide boards), and near the board ends
    for b0, b1 in BATTENS:
        for i in range(N_BOARDS):
            cx = X0 + (i + 0.5) * w + rng.uniform(-0.6, 0.6)
            forged_nail(nails, cx, (b0 + b1) / 2 + rng.uniform(-0.8, 0.8), BATTEN_Z1, rng)
    for i in range(N_BOARDS):
        for y in (51.0, 216.0):
            cx = X0 + (i + 0.5) * w + rng.uniform(-1, 1)
            forged_nail(nails, cx, y + rng.uniform(-0.6, 0.6), BOARD_Z1, rng, r=0.45)
    return [new_obj("hp_boards", bm, mats["board"], low), new_obj("hp_nails", nails, mats["nail"], low)]


def fracture(y_mid, spread, n, rng, seed):
    """Jagged fracture line across a board: fibre ends (y) for n fibres, long splinters here and there."""
    ys = []
    for k in range(n):
        t = k / max(n - 1, 1)
        y = y_mid + spread * (0.6 * noise.noise(Vector((t * 3.0, seed, 0.5))) + 0.5 * (rng.random() - 0.5))
        if rng.random() < 0.18:                     # a long splinter
            y += math.copysign(rng.uniform(1.5, 4.5), rng.random() - 0.5)
        ys.append(y)
    return ys


def build_broken_board(bm, s0, s1, rng, seed):
    """The kicked-in board: the lower and the upper piece end in fibres of different length; the
    fibres at the break are pushed into the locker (-z), the tips most, a few stick out."""
    n = 9
    lo_mid, lo_spread = (BREAK["lo"][0] + BREAK["lo"][1]) / 2, (BREAK["lo"][1] - BREAK["lo"][0])
    hi_mid, hi_spread = (BREAK["hi"][0] + BREAK["hi"][1]) / 2, (BREAK["hi"][1] - BREAK["hi"][0])
    lo_end = fracture(lo_mid, lo_spread, n, rng, seed)
    hi_end = fracture(hi_mid, hi_spread, n, rng, seed + 7)
    # the piece next to the lock side keeps a sliver along its edge (the board split lengthwise)
    lo_end[0] = max(lo_end[0], hi_end[0] - rng.uniform(5, 9))
    # whole board away from the break; fibres of uneven width only over the last few cm
    lo_solid = min(lo_end) - 3.0
    hi_solid = max(hi_end) + 3.0
    board_box(bm, s0, s1, Y0, lo_solid, rng, seed)
    board_box(bm, s0, s1, hi_solid, Y1, rng, seed)
    cuts = sorted(rng.uniform(0.08, 0.92) for _ in range(n - 1))
    edges = [s0] + [s0 + c * (s1 - s0) for c in cuts] + [s1]
    for k in range(n):
        f0, f1 = edges[k], edges[k + 1] - 0.04
        if f1 - f0 < 0.15:
            continue
        for (ya, yb, tip_at) in ((lo_solid - 0.6, lo_end[k], "top"), (hi_end[k], hi_solid + 0.6, "bottom")):
            if yb - ya < 0.5:
                continue
            push = rng.uniform(0.5, 1.7) * (1 if rng.random() < 0.8 else -0.6)   # into the locker, or out
            twist = rng.uniform(-0.3, 0.3)
            # a fibre: a thin box, (2 across) x (nv along) x (bottom, top); bends near the broken end
            nv = 12
            grid = {}
            for layer in (0, 1):
                for i in range(2):
                    for j in range(nv + 1):
                        t = j / nv
                        if tip_at == "top":
                            t = 1 - (1 - t) ** 2.5        # rows bunched at the broken end
                        else:
                            t = t ** 2.5
                        y = ya + (yb - ya) * t
                        d = (yb - y) if tip_at == "top" else (y - ya)   # distance from the broken end
                        bend = math.exp(-d / 3.0)
                        taper = 1 - 0.55 * bend * (0.5 + 0.5 * math.sin(k * 2.3))
                        x = f0 + (f1 - f0) * (0.5 + (i - 0.5) * taper)
                        z = (BOARD_Z1 if layer else BOARD_Z0) - push * bend + twist * bend * (i - 0.5)
                        if layer and bend < 0.2:
                            z += 0.05 * noise.noise(Vector((x * 0.9, y * 0.13, seed)))
                        grid[layer, i, j] = bm.verts.new((x, y, z))
            g = grid
            for j in range(nv):
                bm.faces.new((g[1, 0, j], g[1, 1, j], g[1, 1, j + 1], g[1, 0, j + 1]))      # top
                bm.faces.new((g[0, 0, j + 1], g[0, 1, j + 1], g[0, 1, j], g[0, 0, j]))      # bottom
                for i in (0, 1):
                    q = (g[0, i, j], g[0, i, j + 1], g[1, i, j + 1], g[1, i, j])
                    bm.faces.new(q if i == 0 else tuple(reversed(q)))
            for j in (0, nv):
                q = (g[0, 0, j], g[0, 1, j], g[1, 1, j], g[1, 0, j])
                bm.faces.new(q if j == 0 else tuple(reversed(q)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


def build_battens(low, mats, rng):
    bm = bmesh.new()
    for b0, b1 in BATTENS:
        x0 = X0 + 0.27
        x1 = 25.53
        verts = add_box(bm, (x0, b0, BOARD_Z1 - 0.2), (x1, b1, BATTEN_Z1), 0.4, 2)
        waves(verts, BATTEN_Z1 - 0.1, 0.1, 0.5, rng.uniform(0, 100))
    return [new_obj("hp_battens", bm, mats["batten"], low)]


def build_window(low, mats, rng):
    x0, x1, y0, y1 = WINDOW
    fw = FRAME_W
    frame = bmesh.new()
    zf0, zf1 = BOARD_Z1 - 0.3, BOARD_Z1 + 1.2
    for a in ((x0, y0, x1, y0 + fw), (x0, y1 - fw, x1, y1), (x0, y0 + fw, x0 + fw, y1 - fw), (x1 - fw, y0 + fw, x1, y1 - fw)):
        verts = add_box(frame, (a[0], a[1], zf0), (a[2], a[3], zf1), 0.35, 2)
        waves(verts, zf1 - 0.1, 0.06, 0.8, rng.uniform(0, 100))
    # glazing bead: a thin inner step around the pane
    bead = 0.8
    xi0, xi1, yi0, yi1 = x0 + fw, x1 - fw, y0 + fw, y1 - fw
    for a in ((xi0, yi0, xi1, yi0 + bead), (xi0, yi1 - bead, xi1, yi1), (xi0, yi0 + bead, xi0 + bead, yi1 - bead), (xi1 - bead, yi0 + bead, xi1, yi1 - bead)):
        add_box(frame, (a[0], a[1], BOARD_Z1 - 1.2), (a[2], a[3], BOARD_Z1 - 0.2), 0.15, 1)
    nails = bmesh.new()
    for cx, cy in ((x0 + fw / 2, y0 + fw / 2), (x1 - fw / 2, y0 + fw / 2), (x0 + fw / 2, y1 - fw / 2), (x1 - fw / 2, y1 - fw / 2)):
        forged_nail(nails, cx, cy, zf1, rng, r=0.4)
    # the pane, set back in the frame, a little wavy (old glass)
    glass = bmesh.new()
    res = bmesh.ops.create_grid(glass, x_segments=12, y_segments=24, size=0.5)
    for v in res["verts"]:
        x = xi0 + (v.co.x + 0.5) * (xi1 - xi0)
        y = yi0 + (v.co.y + 0.5) * (yi1 - yi0)
        v.co = Vector((x, y, BOARD_Z1 - 1.25 + 0.04 * noise.noise(Vector((x * 0.3, y * 0.3, 3.0)))))
    # the sill under the window
    sill = bmesh.new()
    verts = add_box(sill, (x0 - 1.2, y0 - 2.4, BOARD_Z1 - 0.3), (x1 + 1.2, y0 + 0.2, BOARD_Z1 + 2.2), 0.4, 2)
    for v in verts:                          # sloped top so water runs off
        if v.co.y > y0 - 1.0:
            pass
        elif v.co.z > BOARD_Z1 + 1.5:
            v.co.z -= 0.5
    return [new_obj("hp_frame", frame, mats["frame"], low), new_obj("hp_frame_nails", nails, mats["nail"], low),
            new_obj("hp_glass", glass, mats["glass"], low), new_obj("hp_sill", sill, mats["sill"], low)]


def build_plate(low, mats, rng):
    x0, x1, y0, y1 = PLATE
    bm = bmesh.new()
    verts = add_box(bm, (x0, y0, BOARD_Z1 - 0.2), (x1, y1, BOARD_Z1 + 0.35), 0.25, 2)
    # hammered: small dents on the face
    for v in verts:
        if v.co.z > BOARD_Z1 + 0.2:
            v.co.z -= 0.03 * abs(noise.noise(Vector((v.co.x * 0.8, v.co.y * 0.8, 9.0))))
    sc = bmesh.new()
    for cx, cy in ((x0 + 1.6, y0 + 1.6), (x1 - 1.6, y0 + 1.6), (x0 + 1.6, y1 - 1.6), (x1 - 1.6, y1 - 1.6)):
        screw(sc, cx, cy, BOARD_Z1 + 0.35, rng)
    return [new_obj("hp_plate", bm, mats["plate"], low), new_obj("hp_plate_screws", sc, mats["screw"], low)]


def disc(bm, cx, cy, r, z0, z1, segs=48, bevel=0.0):
    res = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs, radius1=r, radius2=r, depth=z1 - z0)
    for v in res["verts"]:
        v.co = Vector((v.co.x + cx, v.co.y + cy, v.co.z + (z0 + z1) / 2))
    if bevel > 0:
        edges = list({e for v in res["verts"] for e in v.link_edges})
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, offset_type="OFFSET", segments=2, profile=0.5,
                        affect="EDGES", clamp_overlap=True)


def ring(bm, cx, cy, r, tube, z, segs=48):
    res = bmesh.ops.create_circle(bm, cap_ends=False, segments=segs, radius=1.0)
    prof = []
    for k in range(12):
        a = k / 12 * math.tau
        prof.append((math.cos(a) * tube, math.sin(a) * tube * 0.8))
    bmesh.ops.delete(bm, geom=res["verts"], context="VERTS")
    rows = []
    for i in range(segs):
        th = i / segs * math.tau
        row = []
        for dr, dz in prof:
            row.append(bm.verts.new((cx + (r + dr) * math.cos(th), cy + (r + dr) * math.sin(th), z + dz)))
        rows.append(row)
    for i in range(segs):
        a, b = rows[i], rows[(i + 1) % segs]
        for k in range(12):
            bm.faces.new((a[k], a[(k + 1) % 12], b[(k + 1) % 12], b[k]))


def build_dials(low, mats, rng):
    wood, bez, face, needle, sc = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    zb = BOARD_Z1
    for k, (cx, cy) in enumerate(DIALS):
        disc(wood, cx, cy, DIAL_R, zb - 0.2, zb + 1.1, bevel=0.35)
        ring(bez, cx, cy, DIAL_R - 1.5, 0.55, zb + 1.35)
        disc(face, cx, cy, DIAL_R - 1.6, zb + 0.9, zb + 1.2)
        # needle: a thin tapered wedge from the hub
        ang = math.radians((35.0, -20.0)[k] + 90)
        L = DIAL_R - 2.6
        hub = bmesh.ops.create_cone(needle, cap_ends=True, segments=16, radius1=0.45, radius2=0.45, depth=0.3)
        for v in hub["verts"]:
            v.co += Vector((cx, cy, zb + 1.45))
        tri = [needle.verts.new((cx + math.cos(ang + s * 1.5708) * 0.22, cy + math.sin(ang + s * 1.5708) * 0.22, zb + 1.35)) for s in (1, -1)]
        tip = needle.verts.new((cx + math.cos(ang) * L, cy + math.sin(ang) * L, zb + 1.35))
        tail = needle.verts.new((cx - math.cos(ang) * 1.2, cy - math.sin(ang) * 1.2, zb + 1.35))
        top = [needle.verts.new((v.co.x, v.co.y, v.co.z + 0.12)) for v in (tri[0], tip, tri[1], tail)]
        bot = [tri[0], tip, tri[1], tail]
        needle.faces.new(top)
        needle.faces.new(list(reversed(bot)))
        for i in range(4):
            needle.faces.new((bot[i], bot[(i + 1) % 4], top[(i + 1) % 4], top[i]))
        for a in (90.0, 270.0):
            screw(sc, cx + math.cos(math.radians(a)) * (DIAL_R - 0.75), cy + math.sin(math.radians(a)) * (DIAL_R - 0.75), zb + 1.1, rng, r=0.35)
    return [new_obj("hp_dial_wood", wood, mats["dial_wood"], low), new_obj("hp_bezel", bez, mats["bezel"], low),
            new_obj("hp_face", face, mats["face"], low), new_obj("hp_needle", needle, mats["needle"], low),
            new_obj("hp_dial_screws", sc, mats["screw"], low)]


def build_leaves(low, mats, rng):
    """Birch leaves stuck to the wet wood: a toothed oval with a point, slightly curled, and a stalk."""
    bm = bmesh.new()
    for (cx, cy, L, ang, z) in LEAVES:
        a = math.radians(ang)
        ca, sa = math.cos(a), math.sin(a)
        nseg = 40
        outline = []
        for i in range(nseg):
            t = i / nseg * math.tau
            # leaf frame: u along the leaf (-1 base .. 1 tip), v across
            u = math.cos(t)
            hw = 0.62 * math.sqrt(max(1 - u * u, 0)) * (1.15 - 0.45 * u) ** 1.0
            hw *= 1 + 0.06 * (1 if i % 2 else -1)                  # teeth
            v = hw * (1 if math.sin(t) >= 0 else -1)
            outline.append((u, v))
        centre = bm.verts.new((cx, cy, z + 0.12))
        ring_v = []
        for (u, v) in outline:
            lx, ly = u * L / 2, v * L / 2
            curl = 0.25 * (v * L / 2) ** 2 / (L / 2) ** 2 * L * 0.25
            ring_v.append(bm.verts.new((cx + ca * lx - sa * ly, cy + sa * lx + ca * ly, z + 0.05 + curl)))
        for i in range(nseg):
            bm.faces.new((centre, ring_v[i], ring_v[(i + 1) % nseg]))
        # midrib ridge and stalk
        base = Vector((cx - ca * L / 2, cy - sa * L / 2, z + 0.1))
        tipv = Vector((cx + ca * L * 0.45, cy + sa * L * 0.45, z + 0.12))
        stalk_end = base - Vector((ca, sa, 0)) * (L * 0.3)
        for p0, p1, wdt in ((base, tipv, 0.07), (stalk_end, base, 0.09)):
            d = (p1 - p0)
            nrm = Vector((-d.y, d.x, 0)).normalized() * wdt
            q = [bm.verts.new(p0 + nrm), bm.verts.new(p1 + nrm * 0.4), bm.verts.new(p1 - nrm * 0.4), bm.verts.new(p0 - nrm)]
            qt = [bm.verts.new(v.co + Vector((0, 0, 0.08))) for v in q]
            bm.faces.new(qt)
            for i in range(4):
                bm.faces.new((q[i], q[(i + 1) % 4], qt[(i + 1) % 4], qt[i]))
    return [new_obj("hp_leaves", bm, mats["leaf"], low)]


def build_cavity(low, mats):
    """Inside the locker, behind the boards: what the bake sees through the broken board."""
    bm = bmesh.new()
    add_box(bm, (X0, Y0, 23.0), (X1, Y1, 24.0))
    return [new_obj("hp_cavity", bm, mats["cavity"], low)]


def build_base_copy(low, mats):
    """The low-poly door without its plank faces (the boards replace them): battens' sides, hinges."""
    me = low.data.copy()
    ob = bpy.data.objects.new("hp_base", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.matrix_world = low.matrix_world.copy()
    me.materials.clear()
    me.materials.append(mats["base"])
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.normal_update()
    kill = [f for f in bm.faces if f.normal.z > 0.7 and f.calc_center_median().x < 25.8]   # planks, battens
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bm.to_mesh(me)
    bm.free()
    return ob


def build_cage(low):
    """Front faces look straight down -z from 6 cm out (over sill, dials and leaves); the rest along the normal."""
    me = low.data.copy()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.normal_update()
    for v in bm.verts:
        n = v.normal
        if n.z > 0.5:
            v.co = Vector((v.co.x, v.co.y, 34.0))
        else:
            v.co = v.co + n * 1.0
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("cage", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.matrix_world = low.matrix_world.copy()
    ob.hide_render = True
    return ob


def build(low, seed=11):
    rng = random.Random(seed)
    mats = {k: id_material(k) for k in IDS}
    set_pass(mats.values(), "view")
    hp = [build_base_copy(low, mats)]
    hp += build_boards(low, mats, rng)
    hp += build_battens(low, mats, rng)
    hp += build_window(low, mats, rng)
    hp += build_plate(low, mats, rng)
    hp += build_dials(low, mats, rng)
    hp += build_leaves(low, mats, rng)
    hp += build_cavity(low, mats)
    return hp, mats


# ---------------------------------------------------------------- baking
def bake(low, hp, cage, mats, size, out_dir):
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
    bk.margin = 16
    bk.margin_type = "EXTEND"
    bk.target = "IMAGE_TEXTURES"
    bk.normal_space = "TANGENT"
    bk.normal_r, bk.normal_g, bk.normal_b = "POS_X", "POS_Y", "POS_Z"  # OpenGL

    bpy.ops.object.select_all(action="DESELECT")
    for o in hp:
        o.select_set(True)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low

    out_dir.mkdir(exist_ok=True)
    passes = [("normal", "NORMAL", "view", 1), ("ao", "AO", "view", 64),
              ("curvature", "EMIT", "curvature", 16), ("id", "EMIT", "id", 1)]
    for name, kind, shader, samples in passes:
        set_pass(mats.values(), shader)
        img = bpy.data.images.new(f"bake_{name}", size, size, alpha=False, float_buffer=True)
        img.colorspace_settings.name = "Non-Color"
        tex.image = img
        scene.cycles.samples = samples
        print(f"baking {name} ...", flush=True)
        bk.margin_type = "ADJACENT_FACES" if name == "id" else "EXTEND"
        bpy.ops.object.bake(type=kind, use_clear=True, margin=16)
        img.filepath_raw = str(out_dir / f"door_{name}.png")
        img.file_format = "PNG"
        img.save()
        print("  ->", img.filepath_raw, flush=True)
    set_pass(mats.values(), "view")


def load_door():
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="NEGATIVE_Z", up_axis="Y")
    door = None
    for ob in list(bpy.context.selected_objects):
        if "door_b" in ob.name:
            door = ob
        else:
            bpy.data.objects.remove(ob)
    door.name = "lowpoly_door_b"
    # the OBJ's vertex normals are garbage (they point along -y): bake against flat face normals,
    # or the tangent frame tilts and the whole normal map comes out green
    bpy.context.view_layer.objects.active = door
    door.select_set(True)
    bpy.ops.mesh.customdata_custom_splitnormals_clear()
    for p in door.data.polygons:
        p.use_smooth = False
    return door


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 4096
    bpy.ops.wm.read_factory_settings(use_empty=True)
    low = load_door()
    hp, mats = build(low)
    cage = build_cage(low)
    print("high-poly:", {o.name: len(o.data.polygons) for o in hp}, flush=True)
    if "--nobake" not in argv:
        bake(low, hp, cage, mats, size, OUT)
    if "--blend" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "door_v5_highpoly.blend"))
    print("done")


if __name__ == "__main__":
    main()
