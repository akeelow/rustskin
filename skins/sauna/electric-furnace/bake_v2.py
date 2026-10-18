"""Sauna Stove v2: build high-poly details over the original furnace and bake them
onto its UVs in Cycles.

Usage (from the repo root):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/electric-furnace/bake_v2.py -- [--size 2048] [--blend]

Writes into skins/sauna/electric-furnace/bake/:
  normal.png      tangent-space normal, OpenGL (Y+), like the Rust Normal slot
  ao.png          ambient occlusion of the high-poly
  curvature.png   0.5 = flat, brighter = convex edge, darker = crevice
  id.png          R = material id * 16 + 8 (see IDS), G = random value per part (board, stone)
  --blend also saves bake/highpoly.blend (the scene, for inspecting the details).

All geometry is built in the OBJ's own space (Y up, +Z = front, the same as texture_v1.py)
and given the low-poly's object matrix. A copy of the low-poly is part of the high-poly,
so every ray hits something (flat normal where there is no detail). A cage pushed out per
region sets where the rays start: flat cladding is projected straight along its axis (far
over the burners, close around the door), so planks and rock heaps land undistorted on the
low-poly's bevels and coils. Every flat field (side inset, back wall, raised box) gets its
own planks at its own depth, with trim over the steps between fields.

With --size 2048 it takes about a minute on an RTX 3060 Ti (OptiX).
"""
import math
import random
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

HERE = Path(__file__).resolve().parent
OBJ = HERE / "originals" / "electric.furnace.obj"
OUT = HERE / "bake"

# material ids baked into id.png (R channel)
IDS = {"base": 0, "board": 1, "nail": 2, "stone": 3, "plinth": 4, "mortar": 5, "bar": 6, "rivet": 7,
       "pallet": 8, "trim": 9}

BOARD_W, BOARD_GAP, BOARD_T, BOARD_BEVEL = 0.075, 0.004, 0.010, 0.0025
BURNERS = [(sx * 0.143, sz * 0.1435) for sx in (-1, 1) for sz in (-1, 1)]
PLATE_Y = 1.136


# ---------------------------------------------------------------- mesh helpers
def new_obj(name, bm, mat, low):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.matrix_world = low.matrix_world.copy()
    me.materials.append(mat)
    return ob


def add_box(bm, lo, hi, bevel=0.0, segs=2):
    """Axis-aligned box from corner lo to hi, edges rounded by `bevel`."""
    lo, hi = Vector(lo), Vector(hi)
    first = len(bm.verts)
    res = bmesh.ops.create_cube(bm, size=1.0)
    verts = res["verts"]
    for v in verts:
        v.co = Vector(((lo[i] + hi[i]) / 2 + v.co[i] * (hi[i] - lo[i]) for i in range(3)))
    if bevel > 0:
        edges = list({e for v in verts for e in v.link_edges})
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, offset_type="OFFSET", segments=segs,
                        profile=0.5, affect="EDGES", clamp_overlap=True)
        # bevel replaces the cube's corners; new verts are appended at the end
        verts = list(bm.verts)[first:]
    return verts


def add_rock(bm, center, radii, rng, subdiv=3, rough=0.22, seed=0):
    """Icosphere scaled to an ellipsoid, flattened faces and lumps from noise."""
    res = bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    off = Vector((rng.uniform(-50, 50), rng.uniform(-50, 50), rng.uniform(-50, 50)))
    rot = Matrix.Rotation(rng.uniform(0, math.tau), 3, "Y") @ Matrix.Rotation(rng.uniform(-0.3, 0.3), 3, "X")
    # a few planar cuts make basalt look split rather than river-rounded
    cuts = [Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))).normalized() for _ in range(3)]
    for v in res["verts"]:
        d = v.co.normalized()
        r = 1.0 + rough * (noise.fractal(d * 1.6 + off, 0.5, 2.0, 3) * 0.9)
        r += 0.04 * noise.noise(d * 7 + off)
        for c in cuts:
            k = d.dot(c)
            if k > 0.55:
                r = min(r, 0.55 / k * 1.08)
        p = d * r
        p = Vector((p.x * radii[0], p.y * radii[1], p.z * radii[2]))
        v.co = Vector(center) + rot @ p
    return res["verts"]


def noisy(verts, amp, freq, seed=0, axis=None):
    """Hammer marks / chisel: push vertices along `axis` (or their normal) by noise."""
    off = Vector((seed * 13.1, seed * 7.7, seed * 3.3))
    for v in verts:
        n = noise.noise(v.co * freq + off)
        d = Vector(axis) if axis is not None else v.normal
        v.co += d * amp * n


def subdivide(bm, cuts):
    bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=cuts, use_grid_fill=True)
    bm.normal_update()


# ---------------------------------------------------------------- materials
def id_material(name):
    m = bpy.data.materials.new(f"hp_{name}")
    m.use_nodes = True
    m["bake_id"] = IDS[name]
    return m


def set_pass(mats, kind):
    """Point every high-poly material at the shader the bake pass needs."""
    for m in mats:
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        if kind == "id":
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            comb = nt.nodes.new("ShaderNodeCombineColor")
            comb.inputs[0].default_value = (m["bake_id"] * 16 + 8) / 255.0
            comb.inputs[2].default_value = 0.0
            nt.links.new(geo.outputs["Random Per Island"], comb.inputs[1])
            nt.links.new(comb.outputs[0], em.inputs["Color"])
        elif kind == "curvature":
            # convex edges: rays shot *into* the solid hit the neighbouring face soon;
            # crevices: rays shot out hit the neighbouring face soon
            ao_in = nt.nodes.new("ShaderNodeAmbientOcclusion")
            ao_in.inside = True
            ao_in.samples = 16
            ao_in.inputs["Distance"].default_value = 0.004
            ao_out = nt.nodes.new("ShaderNodeAmbientOcclusion")
            ao_out.samples = 16
            ao_out.inputs["Distance"].default_value = 0.004
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
        else:  # normal / ao: any opaque surface; give it a diffuse look for the viewport
            bs = nt.nodes.new("ShaderNodeBsdfDiffuse")
            col = {"board": (0.6, 0.45, 0.3), "stone": (0.15, 0.15, 0.16), "plinth": (0.4, 0.38, 0.34),
                   "mortar": (0.6, 0.58, 0.54), "bar": (0.1, 0.09, 0.08), "rivet": (0.2, 0.18, 0.16),
                   "nail": (0.2, 0.2, 0.2), "pallet": (0.35, 0.25, 0.17), "trim": (0.5, 0.38, 0.26)}
            name = m.name[3:]
            bs.inputs["Color"].default_value = (*col.get(name, (0.5, 0.5, 0.5)), 1)
            nt.links.new(bs.outputs[0], out.inputs["Surface"])


# ---------------------------------------------------------------- high-poly parts
def build_burner_stones(low, mats, rng):
    """Heaps of split basalt on the four burners: a bottom layer on the plate, a smaller
    top layer towards the middle, so each burner reads as a mound of rocks."""
    bm = bmesh.new()
    for bi, (cx, cz) in enumerate(BURNERS):
        R = 0.112 if bi in (0, 3) else 0.098  # the big burners (+x+z, -x-z) and the small ones
        placed = []
        # (radius range, reach, tries, lift, allowed overlap): big rocks, small ones filling the
        # holes between them (so no coil shows through), then two shrinking layers on top
        layers = ((0.03, 0.042, R, 2500, 0.0, 0.7), (0.014, 0.022, R * 1.02, 3000, 0.0, 0.85),
                  (0.026, 0.036, R * 0.62, 1500, 0.024, 0.75), (0.022, 0.03, R * 0.3, 600, 0.045, 0.8))
        for layer, (rmin, rmax, reach, tries, lift, ov) in enumerate(layers):
            for _ in range(tries):
                r = rng.uniform(rmin, rmax)
                a = rng.uniform(0, math.tau)
                d = reach * math.sqrt(rng.uniform(0, 1))
                x, z = cx + d * math.cos(a), cz + d * math.sin(a)
                ok = True
                for (px, pz, pr, pl) in placed:
                    same = pl == layer or (layer <= 1 and pl <= 1)
                    if same and math.hypot(x - px, z - pz) < (r + pr) * ov:
                        ok = False
                        break
                if not ok:
                    continue
                ry = r * rng.uniform(0.5, 0.7)
                base = PLATE_Y + 0.004 + lift + (1 - d / R) * 0.008
                placed.append((x, z, r, layer))
                add_rock(bm, (x, base + ry * 0.75, z), (r, ry, r * rng.uniform(0.75, 1.0)), rng,
                         subdiv=3, seed=len(placed))
    return new_obj("hp_stones", bm, mats["stone"], low)


def board_strip(bm, axis_u, u0, u1, v0, v1, plane_axis, plane, out_sign, rng, along="v", nails=(), nail_bm=None):
    """Lay boards over a rectangle on an axis plane.

    axis_u/axis_v: the two in-plane axes (0=x, 1=y, 2=z); boards run along `along`.
    plane: coordinate of the surface they are nailed to; they stick out by BOARD_T * out_sign.
    """
    axes = [0, 1, 2]
    axes.remove(plane_axis)
    au = axis_u
    av = [a for a in axes if a != au][0]
    if along == "v":   # boards run along v, stacked across u
        span0, span1, len0, len1, a_span, a_len = u0, u1, v0, v1, au, av
    else:
        span0, span1, len0, len1, a_span, a_len = v0, v1, u0, u1, av, au
    n = max(1, round((span1 - span0) / BOARD_W))
    w = (span1 - span0) / n
    for i in range(n):
        s0 = span0 + i * w + BOARD_GAP / 2
        s1 = span0 + (i + 1) * w - BOARD_GAP / 2
        warp = rng.uniform(-0.0012, 0.0012)  # boards are not all equally proud
        t0 = plane
        t1 = plane + out_sign * (BOARD_T + warp)
        lo, hi = [0, 0, 0], [0, 0, 0]
        lo[a_span], hi[a_span] = s0, s1
        lo[a_len], hi[a_len] = len0, len1
        lo[plane_axis], hi[plane_axis] = min(t0, t1), max(t0, t1)
        verts = add_box(bm, lo, hi, BOARD_BEVEL, 2)
        # a slight cup across the board and chisel/adze waves along it
        mid = (s0 + s1) / 2
        seed = rng.uniform(0, 100)
        for v in verts:
            if (v.co[plane_axis] - plane) * out_sign > BOARD_T * 0.5:
                c = ((v.co[a_span] - mid) / (w / 2)) ** 2
                wave = noise.noise(Vector((v.co[a_len] * 9, mid * 40, seed)))
                v.co[plane_axis] += out_sign * (-0.0009 * c + 0.0005 * wave)
        if nail_bm is not None:
            top = plane + out_sign * (BOARD_T + warp)
            for pos_len in nails:
                if not (len0 + 0.02 < pos_len < len1 - 0.02):
                    continue
                for k in ((-0.24, 0.24) if w > 0.05 else (0.0,)):
                    c = [0, 0, 0]
                    c[a_span] = mid + k * w + rng.uniform(-0.002, 0.002)
                    c[a_len] = pos_len + rng.uniform(-0.004, 0.004)
                    c[plane_axis] = top
                    add_nail(nail_bm, c, plane_axis, out_sign, rng)
    return n


def add_nail(bm, c, axis, sign, rng):
    """Forged nail head: a low square-ish dome, 9-11 mm."""
    r = rng.uniform(0.0045, 0.0055)
    res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    for v in res["verts"]:
        p = v.co.copy()
        h = max(p[axis] * sign, -0.2)
        q = [p[0] * r, p[1] * r, p[2] * r]
        q[axis] = sign * h * 0.0018 - sign * 0.0006
        v.co = Vector(c) + Vector(q)


def trim_ring(bm, nails, plane_axis, plane, sign, u_axis, rect, w, rng):
    """Four trim planks around a rectangle (u0, u1, v0, v1) on an axis plane, nailed at the corners."""
    v_axis = [a for a in (0, 1, 2) if a not in (plane_axis, u_axis)][0]
    u0, u1, v0, v1 = rect
    t0, t1 = plane, plane + sign * (BOARD_T * 0.9)
    pieces = ((u0, u1, v0, v0 + w), (u0, u1, v1 - w, v1),
              (u0, u0 + w, v0 + w + 0.002, v1 - w - 0.002), (u1 - w, u1, v0 + w + 0.002, v1 - w - 0.002))
    for a0, a1, b0, b1 in pieces:
        lo, hi = [0, 0, 0], [0, 0, 0]
        lo[u_axis], hi[u_axis] = a0, a1
        lo[v_axis], hi[v_axis] = b0, b1
        lo[plane_axis], hi[plane_axis] = min(t0, t1), max(t0, t1)
        add_box(bm, lo, hi, BOARD_BEVEL, 2)
    for cu, cv in ((u0 + w / 2, v0 + w / 2), (u1 - w / 2, v0 + w / 2), (u0 + w / 2, v1 - w / 2), (u1 - w / 2, v1 - w / 2)):
        c = [0, 0, 0]
        c[u_axis], c[v_axis], c[plane_axis] = cu, cv, t1
        add_nail(nails, c, plane_axis, sign, rng)


def build_boards(low, mats, rng):
    """Plank cladding. Each flat field of the low-poly gets its own planks at its own depth
    and trim covers the steps between fields, so slat gaps never jog over a step when the
    stove is seen at an angle (the v1 "staircase")."""
    bm = bmesh.new()
    trim = bmesh.new()
    nails = bmesh.new()
    rows = (0.40, 0.72, 1.05)
    # left side: planks inside the inset panel (x = -0.311), trim over the raised frame (x = -0.325)
    board_strip(bm, 2, -0.29, 0.29, 0.35, 1.064, 0, -0.311, -1, rng, nails=(0.42, 0.72, 1.0), nail_bm=nails)
    trim_ring(trim, nails, 0, -0.325, -1, 2, (-0.336, 0.336, 0.306, 1.103), 0.052, rng)
    # back wall (z = -0.326), the raised box (z = -0.362) and trim around the box's rim
    board_strip(bm, 0, -0.338, 0.338, 0.306, 1.103, 2, -0.326, -1, rng, nails=rows, nail_bm=nails)
    board_strip(bm, 0, -0.226, 0.233, 0.62, 0.95, 2, -0.362, -1, rng, nails=(0.785,), nail_bm=nails)
    trim_ring(trim, nails, 2, -0.3705, -1, 0, (-0.238, 0.245, 0.612, 0.958), 0.034, rng)
    # right side: only a frame of planks around the louvre opening (z -0.285..0.285, y 0.35..1.05)
    board_strip(bm, 2, -0.336, -0.285, 0.306, 1.103, 0, 0.326, 1, rng, nails=rows, nail_bm=nails)
    board_strip(bm, 2, 0.285, 0.336, 0.306, 1.103, 0, 0.326, 1, rng, nails=rows, nail_bm=nails)
    board_strip(bm, 2, -0.281, 0.281, 0.306, 0.348, 0, 0.326, 1, rng, along="u", nails=(-0.2, 0.2), nail_bm=nails)
    board_strip(bm, 2, -0.281, 0.281, 1.052, 1.103, 0, 0.326, 1, rng, along="u", nails=(-0.2, 0.2), nail_bm=nails)
    return [new_obj("hp_boards", bm, mats["board"], low), new_obj("hp_trim", trim, mats["trim"], low),
            new_obj("hp_nails", nails, mats["nail"], low)]


def build_panel(low, mats, rng):
    """Control panel above the door: two horizontal planks with holes for the knobs."""
    bm = bmesh.new()
    nails = bmesh.new()
    board_strip(bm, 0, -0.338, 0.338, 0.935, 1.103, 2, 0.327, 1, rng, along="u", nails=(-0.3, 0.3), nail_bm=nails)
    ob = new_obj("hp_panel", bm, mats["board"], low)
    cut = bmesh.new()
    for kx in (-0.203, -0.05, 0.04, 0.129, 0.217):
        res = bmesh.ops.create_cone(cut, cap_ends=True, segments=32, radius1=0.036, radius2=0.036, depth=0.06)
        for v in res["verts"]:
            v.co = Vector((kx + v.co.x, 1.037 + v.co.y, 0.33 + v.co.z))
    cob = new_obj("hp_cut", cut, mats["board"], low)
    mod = ob.modifiers.new("holes", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = cob
    bpy.context.view_layer.objects.active = ob
    with bpy.context.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cob)
    nob = new_obj("hp_panel_nails", nails, mats["nail"], low)
    return [ob, nob]


def build_door(low, mats, rng):
    """Forged bars with hammer marks, rivets at the bar ends and around the door frame."""
    bm = bmesh.new()
    riv = bmesh.new()
    for x0, x1 in ((-0.213, -0.17), (-0.127, -0.084), (-0.041, 0.002), (0.045, 0.088), (0.131, 0.174)):
        v = add_box(bm, (x0 + 0.0005, 0.475, 0.30), (x1 - 0.0005, 0.931, 0.3505), 0.003, 2)
    subdivide(bm, 6)
    noisy([v for v in bm.verts if v.co.z > 0.345], 0.0006, 140, 3, axis=(0, 0, 1))
    for x0, x1 in ((-0.213, -0.17), (-0.127, -0.084), (-0.041, 0.002), (0.045, 0.088), (0.131, 0.174)):
        for y in (0.497, 0.703, 0.909):
            add_rivet(riv, ((x0 + x1) / 2, y, 0.3505), 0.0075)
    # door frame (front at z ~0.338): rivets every ~8 cm on the margin around the bars
    for x in [(-0.255 + i * 0.0855) for i in range(7)]:
        for y in (0.468 + 0.0, 0.94):
            add_rivet(riv, (x, y, 0.3375), 0.006)
    for y in [0.53 + i * 0.09 for i in range(5)]:
        add_rivet(riv, (-0.256, y, 0.3375), 0.006)
        add_rivet(riv, (0.198, y, 0.3375), 0.006)
    return [new_obj("hp_bars", bm, mats["bar"], low), new_obj("hp_rivets", riv, mats["rivet"], low)]


def add_rivet(bm, c, r):
    res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    for v in res["verts"]:
        p = v.co
        v.co = Vector((c[0] + p.x * r, c[1] + p.y * r, c[2] + max(p.z, -0.1) * r * 0.55))


def build_plinth(low, mats, rng):
    """Fieldstone plinth: courses of rough stones proud of a mortar bed, all four sides."""
    st = bmesh.new()
    mo = bmesh.new()
    y0, y1 = 0.040, 0.302
    face = 0.343           # mortar plane, just outside the lumpy original bricks
    for side in range(4):
        # local frame per side: u along the face, n outwards
        n = [Vector((0, 0, 1)), Vector((1, 0, 0)), Vector((0, 0, -1)), Vector((-1, 0, 0))][side]
        u = Vector((n.z, 0, -n.x)) * -1
        lo = n * face - u * 0.352
        add_slab = [lo + Vector((0, y0, 0)), lo + u * 0.704 + Vector((0, y0, 0)),
                    lo + u * 0.704 + Vector((0, y1, 0)), lo + Vector((0, y1, 0))]
        vs = [mo.verts.new(p) for p in add_slab]
        f = mo.faces.new(vs)
        f.normal_update()
        if f.normal.dot(n) < 0:
            f.normal_flip()
        y = y0
        course = 0
        while y < y1 - 0.02:
            h = rng.uniform(0.05, 0.085)
            h = min(h, y1 - y)
            if y1 - (y + h) < 0.03:
                h = y1 - y
            s = -0.352 + (0.0 if course % 2 == 0 else -rng.uniform(0.03, 0.06))
            while s < 0.352:
                L = rng.uniform(0.06, 0.17)
                s1 = min(s + L, 0.362)
                g = 0.005
                cu, cy = (max(s, -0.362) + s1) / 2, y + h / 2
                hl, hh = (s1 - max(s, -0.362)) / 2 - g, h / 2 - g
                shrink = hh * rng.uniform(0.0, 0.22)  # not every stone fills its course
                hh -= shrink
                cy += rng.uniform(-1, 1) * shrink
                if hl > 0.01:
                    depth = 0.012 + rng.uniform(0, 0.008)
                    c = n * (face + depth * 0.2) + u * cu + Vector((0, cy, 0))
                    first = len(st.verts)
                    res = bmesh.ops.create_cube(st, size=2.0)
                    seed = rng.uniform(0, 100)
                    # pull each corner around so stones are wedges and lumps, not bricks
                    m = min(hl, hh)
                    jit = {(sx, sy): (rng.uniform(-0.45, 0.25) * m, rng.uniform(-0.45, 0.25) * m)
                           for sx in (-1, 1) for sy in (-1, 1)}
                    for v in res["verts"]:
                        sx, sy = (1 if v.co.x > 0 else -1), (1 if v.co.y > 0 else -1)
                        ju, jy = jit[(sx, sy)]
                        v.co = (c + u * (v.co.x * hl + sx * ju) + Vector((0, v.co.y * hh + sy * jy, 0))
                                + n * (v.co.z * depth))
                    bmesh.ops.subdivide_edges(st, edges=list({e for v in res["verts"] for e in v.link_edges}),
                                              cuts=5, use_grid_fill=True)
                    verts = list(st.verts)[first:]  # grid fill replaces the cube's own verts
                    # round it: pull corners in towards an ellipsoid, then chisel with noise
                    for v in verts:
                        d = v.co - c
                        lu, ly, ln = d.dot(u) / hl, d.y / hh, d.dot(n) / depth
                        k = math.sqrt(lu * lu + ly * ly + ln * ln) or 1
                        e = 1.0 / max(k, 1e-6) ** 0.35
                        w = noise.fractal(v.co * 45 + Vector((seed, 0, 0)), 0.6, 2.0, 3)
                        v.co = c + u * (lu * hl * e) + Vector((0, ly * hh * e, 0)) + n * (ln * depth * e + 0.0018 * w)
                s = s + L
            y += h
            course += 1
    return [new_obj("hp_plinth", st, mats["plinth"], low), new_obj("hp_mortar", mo, mats["mortar"], low)]


def build_pallet(low, mats, rng):
    """Pallet: boards along x with gaps, nailed at both ends."""
    bm = bmesh.new()
    nails = bmesh.new()
    n = 8
    w = 0.778 / n
    for i in range(n):
        z0 = -0.389 + i * w + 0.003
        z1 = -0.389 + (i + 1) * w - 0.003
        verts = add_box(bm, (-0.392, -0.004, z0), (0.392, 0.0365 + rng.uniform(-0.001, 0.0015), z1), 0.003, 2)
        for x in (-0.355, 0.355):
            add_nail(nails, (x, max(v.co.y for v in verts), (z0 + z1) / 2), 1, 1, rng)
    return [new_obj("hp_pallet", bm, mats["pallet"], low), new_obj("hp_pallet_nails", nails, mats["nail"], low)]


def build_base_copy(low, mats):
    me = low.data.copy()
    ob = bpy.data.objects.new("hp_base", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.matrix_world = low.matrix_world.copy()
    me.materials.clear()
    me.materials.append(mats["base"])
    return ob


def cage_offset(p, n):
    """Where the bake rays start for a low-poly vertex (local OBJ space): returns the
    offset vector. Flat cladding is projected straight along its axis, so planks and
    stone heaps land on the low-poly undistorted even across its bumps and bevels."""
    x, y, z = p

    def axis(a, dist, guard=0.25):
        if n.dot(a) > guard:              # only surfaces that face that way (not the oven inside)
            return a * dist
        return n * 0.012

    if y > 1.139 and abs(x) < 0.30 and abs(z) < 0.30:
        return Vector((0, 0.075, 0))                     # burners: every face of the coils looks up at the heap
    if y > 1.12 and abs(x) < 0.34 and abs(z) < 0.34:
        return axis(Vector((0, 1, 0)), 0.075)            # rest of the top plate
    if y < 0.045:
        return n * 0.025                                 # pallet
    if y < 0.305:
        a = Vector((math.copysign(1, n.x), 0, 0)) if abs(n.x) > abs(n.z) else Vector((0, 0, math.copysign(1, n.z)))
        return axis(a, 0.065)                            # plinth stones, per side (back is set in)
    if z < -0.30 and abs(x) < 0.31:
        return axis(Vector((0, 0, -1)), 0.07)            # back wall and the raised box
    if x < -0.30 and abs(z) < 0.31:
        return axis(Vector((-1, 0, 0)), 0.04)
    if x > 0.30 and abs(z) < 0.31:
        return axis(Vector((1, 0, 0)), 0.03)
    if z > 0.30 and y > 0.93 and abs(x) < 0.31:
        return axis(Vector((0, 0, 1)), 0.025)            # control panel
    if abs(x) > 0.30 and abs(z) > 0.30 and y < 1.11:
        return n * 0.035                                 # box corners: reach the plank edges
    return n * 0.012                                    # door, corners, oven inside, everything else


def build_cage(low):
    me = low.data.copy()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.normal_update()
    for v in bm.verts:
        v.co = v.co + cage_offset(v.co, v.normal)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("cage", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.matrix_world = low.matrix_world.copy()
    ob.hide_render = True
    return ob


def build(low, seed=7):
    rng = random.Random(seed)
    mats = {k: id_material(k) for k in IDS}
    set_pass(mats.values(), "normal")
    hp = [build_base_copy(low, mats), build_burner_stones(low, mats, rng)]
    hp += build_boards(low, mats, rng)
    hp += build_panel(low, mats, rng)
    hp += build_door(low, mats, rng)
    hp += build_plinth(low, mats, rng)
    hp += build_pallet(low, mats, rng)
    return hp, mats


# ---------------------------------------------------------------- baking
def setup_cycles(scene):
    try:
        scene.render.engine = "CYCLES"
    except TypeError as e:
        raise SystemExit(f"no Cycles: {e}")
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
            print("bake device:", kind, [d.name for d in gpus])
            break
    else:
        scene.cycles.device = "CPU"
        print("bake device: CPU")
    scene.view_settings.view_transform = "Standard"


def bake(low, hp, cage, mats, size, out_dir):
    scene = bpy.context.scene
    setup_cycles(scene)
    # the low-poly must not shadow/occlude the high-poly copy that sits exactly on it
    for attr in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission",
                 "visible_volume_scatter", "visible_shadow"):
        setattr(low, attr, False)
    if scene.world is None:
        scene.world = bpy.data.worlds.new("bake")
    scene.world.light_settings.distance = 0.12

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
    passes = [("normal", "NORMAL", "normal", 1), ("ao", "AO", "normal", 64),
              ("curvature", "EMIT", "curvature", 16), ("id", "EMIT", "id", 1)]
    for name, kind, shader, samples in passes:
        set_pass(mats.values(), shader)
        img = bpy.data.images.new(f"bake_{name}", size, size, alpha=False, float_buffer=True)
        img.colorspace_settings.name = "Non-Color"
        tex.image = img
        scene.cycles.samples = samples
        print(f"baking {name} ...", flush=True)
        if name == "id":
            bk.margin_type = "ADJACENT_FACES"
        bpy.ops.object.bake(type=kind, use_clear=True, margin=16)
        img.filepath_raw = str(out_dir / f"{name}.png")
        img.file_format = "PNG"
        img.save()
        print("  ->", img.filepath_raw, flush=True)
    set_pass(mats.values(), "normal")


def load_low():
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="NEGATIVE_Z", up_axis="Y")
    low = bpy.context.selected_objects[0]
    low.name = "lowpoly"
    return low


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 2048
    bpy.ops.wm.read_factory_settings(use_empty=True)
    low = load_low()
    hp, mats = build(low)
    cage = build_cage(low)
    print("high-poly:", {o.name: len(o.data.polygons) for o in hp}, flush=True)
    bake(low, hp, cage, mats, size, OUT)
    if "--blend" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "highpoly.blend"))
    print("done")


if __name__ == "__main__":
    main()
