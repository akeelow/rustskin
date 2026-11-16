"""Sauna Door (Wooden Door): high-poly details modelled over the original door and baked onto its UVs.

The door of a steam room built from scrap: aspen boards nailed onto an old steel sheet.
  front (+z, towards the changing room)  9 boards of uneven width, a small window in a frame of four
                                         slats with a sill, a towel on a bent nail, forged nails, a leaf
  back  (-z, inside the steam room)      the same boards, the model's own three rails and two braces
                                         (rebuilt with rounded edges), the same window in the only field
                                         no brace crosses, two strap hinges, one tied with wire
The steel sheet shows in the gaps between the boards and as a strip along the door's edges.
References: references/ref_front.jpg, ref_back.jpg (layout and mood only; nothing is projected).

Usage (from the repo root):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/wooden-door/bake_door.py -- [--size 4096] [--blend] [--preview] [--nobake]

Writes bake/door_{normal,ao,curvature,id}.png. OBJ units are metres, Y up, the front faces +z; the
OBJ is imported without axis conversion, so Blender coordinates equal OBJ coordinates.
id.png: R = material id * 16 + 8 (see IDS), G = random value per part (per board, per nail).
The handle (two small islands shared by both sides) is not modelled: its texels keep the original maps.
"""
import json
import math
import random
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector, noise

HERE = Path(__file__).resolve().parent
OBJ = HERE / "originals" / "door.hinged.wood.obj"
OUT = HERE / "bake"

IDS = {"steel": 1, "board_f": 2, "board_b": 3, "rail": 4, "brace": 5, "nail": 6, "frame": 7, "sill": 8,
       "glass": 9, "towel": 10, "stripe": 11, "hook": 12, "leaf": 13, "hinge": 14, "wire": 15}
VIEW_COL = {"steel": (0.25, 0.1, 0.05), "board_f": (0.55, 0.45, 0.32), "board_b": (0.25, 0.16, 0.1),
            "rail": (0.3, 0.2, 0.12), "brace": (0.32, 0.22, 0.13), "nail": (0.12, 0.08, 0.06),
            "frame": (0.5, 0.42, 0.3), "sill": (0.5, 0.42, 0.3), "glass": (0.9, 0.5, 0.2),
            "towel": (0.75, 0.72, 0.65), "stripe": (0.5, 0.15, 0.12), "hook": (0.15, 0.08, 0.05),
            "leaf": (0.4, 0.42, 0.15), "hinge": (0.2, 0.1, 0.06), "wire": (0.25, 0.2, 0.18)}

# ---------------------------------------------------------------- the low-poly door (metres)
X0, X1 = -1.196, -0.015                  # plank faces; the edges are chamfered out to -1.21 / -0.002
Y0, Y1 = 0.013, 2.100
ZF = 0.054                               # front face
ZB = 0.0                                 # back plank face (fields between the rails)
ZR = -0.046                              # face of the rails and braces
RAILS = ((0.013, 0.225), (0.971, 1.197), (1.875, 2.100))        # y0, y1: bottom, middle, top
LOCK_BLOCK = (-1.196, -0.971, 0.746, 0.985)                      # under the middle rail, at the handle
BRACES = (  # outlines of the two braces on the back, as in the OBJ (x, y), counter-clockwise seen from -z
    ((-0.589, 1.214), (-0.822, 1.214), (-1.052, 1.619), (-1.052, 1.701), (-1.109, 1.721), (-1.188, 1.859), (-0.958, 1.859)),
    ((-0.025, 0.244), (-0.27, 0.244), (-0.543, 0.724), (-0.588, 0.864), (-0.668, 0.953), (-0.439, 0.953)),
)
# ---------------------------------------------------------------- the design
Z_STEEL_F, Z_STEEL_B = 0.041, 0.012      # the steel sheet between the two layers of boards
EDGE = 0.012                             # steel strip left bare along the door's edges
GAP = 0.007
N_BOARDS = 9
WINDOW = (-0.52, -0.12, 1.30, 1.78)      # frame outer: x0, x1, y0, y1 (front: upper right; back: upper left)
SLAT = 0.047
SILL_H = 0.036
HOOK = (-0.905, 1.865)                   # the bent nail the towel hangs on
TOWEL_W, TOWEL_L = 0.37, 0.60
NAIL_ROWS_F = (0.11, 0.58, 1.07, 1.56, 2.03)
LEAF = (-0.62, 0.135, 0.07, 38.0)        # x, y, length, angle
HINGES = (0.118, 1.99)                   # y of the two strap hinges (on the bottom and the top rail)


# ---------------------------------------------------------------- helpers
def new_obj(name, bm, mats):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    for m in (mats if isinstance(mats, (list, tuple)) else [mats]):
        me.materials.append(m)
    # big flat faces keep a flat normal next to their rounded edges (else the bake shows a gradient across them)
    me.set_sharp_from_angle(angle=math.radians(50))
    wn = ob.modifiers.new("weighted_normal", "WEIGHTED_NORMAL")
    wn.mode = "FACE_AREA"
    wn.weight = 100
    wn.keep_sharp = True
    return ob


def add_box(bm, lo, hi, bevel=0.0, segs=2):
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
        bm.verts.ensure_lookup_table()
        verts = list(bm.verts)[first:]
    return verts


def plank(bm, a0, a1, b0, b1, z_base, z_top, rng, axis="y", bevel=0.003, wave=0.0009, wobble=0.0012, step=0.04,
          shape=None):
    """A sawn board: runs along `axis` from a0 to a1, spans b0..b1 across, from z_base up (or down) to z_top.
    The face is a little wavy and cupped, the long edges wander, the long edges are rounded.
    shape = (seed, tilt, lift, b_ref0, b_ref1): pieces of one board cut around the window share it."""
    sgn = 1.0 if z_top > z_base else -1.0
    seed, tilt, lift, r0, r1 = shape or (rng.uniform(0, 100), rng.uniform(-0.0008, 0.0008),
                                         rng.uniform(-0.0008, 0.0008), b0, b1)
    n_len = max(2, int(abs(a1 - a0) / step))
    # cross-section: base corner, side, rounded shoulder, face, rounded shoulder, side, base corner
    prof = [(0.0, 0.0)]
    for k in range(4):
        t = k / 3 * math.pi / 2
        prof.append((bevel * (1 - math.cos(t)), -bevel * (1 - math.sin(t))))        # across offset, depth below face
    n_face = 6
    w = b1 - b0
    sect = [(0.0, None)] + [(p[0], p[1]) for p in prof[1:]]
    for k in range(1, n_face):
        sect.append((bevel + (w - 2 * bevel) * k / n_face, 0.0))
    sect += [(w - p[0], p[1]) for p in reversed(prof[1:])] + [(w, None)]
    rows = []
    for i in range(n_len + 1):
        a = a0 + (a1 - a0) * i / n_len
        wob0 = wobble * noise.noise(Vector((a * 2.2, seed, 1.0)))
        wob1 = wobble * noise.noise(Vector((a * 2.2, seed, 7.0)))
        row = []
        for (off, depth) in sect:
            b = b0 + off
            f = (b - r0) / (r1 - r0)                  # position across the whole board
            b += wob0 * (1 - f) * (b0 == r0) + wob1 * f * (b1 == r1)
            if depth is None:
                z = z_base
            else:
                cup = 0.0007 * (2 * f - 1) ** 2
                z = z_top + sgn * (depth + lift + tilt * (2 * f - 1) + cup
                                   + wave * noise.noise(Vector((b * 9.0, a * 2.5, seed))))
            row.append(bm.verts.new((b, a, z) if axis == "y" else (a, b, z)))
        rows.append(row)
    flip = (sgn > 0) == (axis == "y")
    for i in range(n_len):
        for k in range(len(sect) - 1):
            q = (rows[i][k], rows[i][k + 1], rows[i + 1][k + 1], rows[i + 1][k])
            bm.faces.new(q if flip else q[::-1])
    for row, rev in ((rows[0], False), (rows[-1], True)):
        f = bm.faces.new(row if (rev == flip) else row[::-1])
    return rows


NAILS = {"front": [], "back": []}       # (x, y) of every nail head, written to bake/layout.json


def forged_nail(bm, x, y, z, sgn, rng, r=0.006):
    """Square-ish domed forged nail head sitting on z, facing sgn*z."""
    NAILS["front" if sgn > 0 else "back"].append((round(x, 4), round(y, 4)))
    res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    rot = rng.uniform(0, math.pi / 2)
    c, s = math.cos(rot), math.sin(rot)
    k_r = rng.uniform(0.85, 1.15)
    for v in res["verts"]:
        p = v.co.copy()
        sq = max(abs(p.x), abs(p.y)) + 1e-6
        k = 0.75 + 0.25 * (math.hypot(p.x, p.y) / sq if sq > 1e-3 else 1)
        px, py = p.x * r * k * k_r, p.y * r * k * k_r
        v.co = Vector((x + c * px - s * py, y + s * px + c * py, z + sgn * (-0.0005 + max(p.z, -0.2) * r * 0.42)))
    if sgn < 0:
        bmesh.ops.reverse_faces(bm, faces=list({f for v in res["verts"] for f in v.link_faces}))


def prism(bm, outline, z0, z1, bevel=0.004):
    """Extrude a polygon (x, y) from z0 to z1 and round the edges of the z1 face."""
    first = len(bm.verts)
    bot = [bm.verts.new((x, y, z0)) for x, y in outline]
    top = [bm.verts.new((x, y, z1)) for x, y in outline]
    n = len(outline)
    ftop = bm.faces.new(top)
    bm.faces.new(bot[::-1])
    for i in range(n):
        bm.faces.new((bot[i], bot[(i + 1) % n], top[(i + 1) % n], top[i]))
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(ftop.edges), offset=bevel, offset_type="OFFSET", segments=3,
                        profile=0.5, affect="EDGES", clamp_overlap=True)
    bm.verts.ensure_lookup_table()
    new = list(bm.verts)[first:]
    bmesh.ops.recalc_face_normals(bm, faces=list({f for v in new for f in v.link_faces}))
    return new


def tube(bm, pts, r, segs=8):
    """A round wire through the points."""
    rings = []
    for i, p in enumerate(pts):
        p = Vector(p)
        d = (Vector(pts[min(i + 1, len(pts) - 1)]) - Vector(pts[max(i - 1, 0)])).normalized()
        u = d.cross(Vector((0, 0, 1)))
        if u.length < 1e-4:
            u = d.cross(Vector((1, 0, 0)))
        u.normalize()
        w = d.cross(u)
        rings.append([bm.verts.new(p + (u * math.cos(k / segs * math.tau) + w * math.sin(k / segs * math.tau)) * r)
                      for k in range(segs)])
    for a, b in zip(rings, rings[1:]):
        for k in range(segs):
            bm.faces.new((a[k], a[(k + 1) % segs], b[(k + 1) % segs], b[k]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    faces = list({f for ring in rings for v in ring for f in v.link_faces})
    bmesh.ops.recalc_face_normals(bm, faces=faces)


def board_edges(rng):
    """x-ranges of the boards: uneven widths, the same layout on both sides of the door."""
    w = [rng.uniform(0.8, 1.35) for _ in range(N_BOARDS)]
    span = (X1 - EDGE) - (X0 + EDGE)
    k = span / sum(w)
    xs, x = [], X0 + EDGE
    for wi in w:
        xs.append((x + GAP / 2, x + wi * k - GAP / 2))
        x += wi * k
    return xs


# ---------------------------------------------------------------- parts
def build_steel(mats):
    """The old steel sheet the boards are nailed to: seen in the gaps and on the door's edges."""
    bm = bmesh.new()
    add_box(bm, (-1.2095, 0.0005, Z_STEEL_B), (-0.0025, 2.112, Z_STEEL_F))
    # a little dented
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=24, use_grid_fill=True)
    for v in bm.verts:
        v.co.z += 0.0006 * noise.noise(Vector((v.co.x * 6, v.co.y * 6, 4.0)))
    return [new_obj("hp_steel", bm, mats["steel"])]


def build_boards(mats, rng, xs):
    wx0, wx1, wy0, wy1 = WINDOW
    out = []
    nails_f, nails_b = bmesh.new(), bmesh.new()
    for side, z_base, z_top, name in (("f", Z_STEEL_F - 0.001, ZF, "board_f"), ("b", Z_STEEL_B + 0.001, ZB, "board_b")):
        bm = bmesh.new()
        sgn = 1 if side == "f" else -1
        for (s0, s1) in xs:
            y_lo = Y0 + 0.006 + rng.uniform(0, 0.012)
            y_hi = Y1 - rng.uniform(0, 0.01) if side == "f" else Y1
            pieces = [(y_lo, y_hi, s0, s1)]          # whole boards: the pane is laid over them
            shape = (rng.uniform(0, 100), rng.uniform(-0.0008, 0.0008), rng.uniform(-0.0008, 0.0008), s0, s1)
            for (a0, a1, b0, b1) in pieces:
                plank(bm, a0, a1, b0, b1, z_base, z_top, rng, shape=shape)
            # nails
            w = s1 - s0
            if side == "f":
                for y in NAIL_ROWS_F:
                    for cx in ((s0 + w * 0.27, s0 + w * 0.73) if w > 0.115 else (s0 + w * 0.5,)):
                        px, py = cx + rng.uniform(-0.008, 0.008), y + rng.uniform(-0.012, 0.012)
                        if wx0 - 0.03 < px < wx1 + 0.03 and wy0 - SILL_H - 0.03 < py < wy1 + 0.03:
                            continue
                        forged_nail(nails_f, px, py, ZF, 1, rng)
            else:
                for y in (0.60, 1.52):                # between the rails: one nail per board
                    px, py = s0 + w * 0.5 + rng.uniform(-0.02, 0.02), y + rng.uniform(-0.03, 0.03)
                    if wx0 - 0.03 < px < wx1 + 0.03 and wy0 - SILL_H - 0.03 < py < wy1 + 0.03:
                        continue
                    if in_brace(px, py, 0.02) or in_lock_block(px, py, 0.02):
                        continue
                    forged_nail(nails_b, px, py, ZB, -1, rng, r=0.005)
        out.append(new_obj(f"hp_boards_{side}", bm, mats[name]))
    out += [new_obj("hp_nails_f", nails_f, mats["nail"]), new_obj("hp_nails_b", nails_b, mats["nail"])]
    return out


def in_poly(x, y, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        (xa, ya), (xb, yb) = poly[i], poly[(i + 1) % n]
        if (ya > y) != (yb > y) and x < xa + (y - ya) / (yb - ya) * (xb - xa):
            inside = not inside
    return inside


def in_brace(x, y, margin=0.0):
    return any(in_poly(x + dx, y + dy, b) for b in BRACES
               for dx in (-margin, 0, margin) for dy in (-margin, 0, margin))


def in_lock_block(x, y, margin=0.0):
    bx0, bx1, by0, by1 = LOCK_BLOCK
    return bx0 - margin < x < bx1 + margin and by0 - margin < y < by1 + margin


def build_rails(mats, rng, xs):
    """The model's own rails, lock block and braces, rebuilt with rounded edges, saw waves and nails."""
    rails, braces, nails = bmesh.new(), bmesh.new(), bmesh.new()
    for (y0, y1) in RAILS:
        plank(rails, X0 - 0.012, X1 + 0.012, y0 + 0.001, y1 - 0.001, ZB + 0.002, ZR, rng, axis="x",
              bevel=0.008, wave=0.0012, wobble=0.0)
        yc = (y0 + y1) / 2
        for i, (s0, s1) in enumerate(xs):             # one nail into every board, staggered
            px = (s0 + s1) / 2 + rng.uniform(-0.015, 0.015)
            py = yc + (0.055 if i % 2 else -0.055) + rng.uniform(-0.012, 0.012)
            if in_brace(px, py, 0.012):
                continue
            forged_nail(nails, px, py, ZR, -1, rng, r=0.0065)
    bx0, bx1, by0, by1 = LOCK_BLOCK
    plank(rails, by0 + 0.001, by1 + 0.02, bx0 - 0.012, bx1 - 0.001, ZB + 0.002, ZR, rng, axis="y",
          bevel=0.008, wave=0.001, wobble=0.0)
    for poly in BRACES:
        # keep clear of the rails' rounded edges: the outline's top and bottom sit on the rails
        prism(braces, poly, ZB + 0.002, ZR, bevel=0.007)
        (xa, ya), (xb, yb) = ((poly[0][0] + poly[1][0]) / 2, poly[0][1]), ((poly[-1][0] + poly[-2][0]) / 2, poly[-1][1])
        n = 5
        for k in range(n):
            t = (k + 0.5) / n
            off = 0.05 if k % 2 else -0.05
            px, py = xa + (xb - xa) * t + off + rng.uniform(-0.01, 0.01), ya + (yb - ya) * t + rng.uniform(-0.02, 0.02)
            if in_poly(px, py, poly) and in_poly(px - 0.02, py, poly) and in_poly(px + 0.02, py, poly):
                forged_nail(nails, px, py, ZR, -1, rng, r=0.0065)
    return [new_obj("hp_rails", rails, mats["rail"]), new_obj("hp_braces", braces, mats["brace"]),
            new_obj("hp_rail_nails", nails, mats["nail"])]


def build_window(mats, rng):
    """The same pane seen from both sides: on each a frame of four nailed slats and a sill."""
    x0, x1, y0, y1 = WINDOW
    frame, sill, nails, glass = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    for sgn, zs in ((1, ZF), (-1, ZB)):
        z_in, z_out = zs - sgn * 0.004, zs + sgn * 0.019
        # top and bottom slats run the full width, the side slats stand between them; none is square
        plank(frame, x0 - 0.006, x1 + 0.009, y1 - SLAT, y1 + 0.003, z_in, z_out, rng, axis="x", bevel=0.004, wobble=0.0015)
        plank(frame, x0 - 0.004, x1 + 0.004, y0, y0 + SLAT, z_in, z_out - sgn * 0.002, rng, axis="x", bevel=0.004, wobble=0.0015)
        plank(frame, y0 + SLAT, y1 - SLAT, x0 + 0.002, x0 + SLAT, z_in, z_out - sgn * 0.003, rng, axis="y", bevel=0.004, wobble=0.0015)
        plank(frame, y0 + SLAT, y1 - SLAT, x1 - SLAT - 0.003, x1, z_in, z_out - sgn * 0.001, rng, axis="y", bevel=0.004, wobble=0.0015)
        # glazing bead: a thin step around the pane
        xi0, xi1, yi0, yi1 = x0 + SLAT, x1 - SLAT, y0 + SLAT, y1 - SLAT
        bead = 0.012
        zb0, zb1 = zs - sgn * 0.002, zs + sgn * 0.009
        for a in ((xi0, yi0, xi1, yi0 + bead), (xi0, yi1 - bead, xi1, yi1),
                  (xi0, yi0 + bead, xi0 + bead, yi1 - bead), (xi1 - bead, yi0 + bead, xi1, yi1 - bead)):
            add_box(frame, (a[0], a[1], min(zb0, zb1)), (a[2], a[3], max(zb0, zb1)), 0.002, 2)
        for cx, cy in ((x0 + SLAT / 2, y0 + SLAT / 2), (x1 - SLAT / 2, y0 + SLAT / 2),
                       (x0 + SLAT / 2, y1 - SLAT / 2), (x1 - SLAT / 2, y1 - SLAT / 2),
                       (x0 + SLAT / 2, (y0 + y1) / 2), (x1 - SLAT / 2, (y0 + y1) / 2)):
            forged_nail(nails, cx + rng.uniform(-0.006, 0.006), cy + rng.uniform(-0.006, 0.006),
                        z_out - sgn * 0.003, sgn, rng, r=0.005)
        # the sill: a short thick board, its top sloped so water runs off
        verts = add_box(sill, (x0 - 0.022, y0 - SILL_H, min(z_in, zs + sgn * 0.032)),
                        (x1 + 0.026, y0 + 0.002, max(z_in, zs + sgn * 0.032)), 0.005, 3)
        for v in verts:
            if (v.co.z - zs) * sgn > 0.02 and v.co.y < y0 - SILL_H * 0.5:
                v.co.z -= sgn * 0.008
        # the pane, 16 mm back in the frame, a little wavy (old glass)
        zg = zs + sgn * 0.003
        res = bmesh.ops.create_grid(glass, x_segments=16, y_segments=24, size=0.5)
        for v in res["verts"]:
            x = xi0 + (v.co.x + 0.5) * (xi1 - xi0)
            y = yi0 + (v.co.y + 0.5) * (yi1 - yi0)
            v.co = Vector((x, y, zg + 0.0005 * noise.noise(Vector((x * 14, y * 14, 3.0)))))
        if sgn < 0:
            bmesh.ops.reverse_faces(glass, faces=list({f for v in res["verts"] for f in v.link_faces}))
    return [new_obj("hp_frame", frame, mats["frame"]), new_obj("hp_sill", sill, mats["sill"]),
            new_obj("hp_frame_nails", nails, mats["nail"]), new_obj("hp_glass", glass, mats["glass"])]


def towel_point(s, t, layer=0):
    """The towel is folded once over the bent nail and hangs in two layers: bunched at the nail, the
    left edge falling almost straight, the folds fanning out to the right, the hem at a slant with
    its low corner on the left. The under layer (1) is shorter and shows on the right.
    s across 0..1, t down 0..1."""
    hx, hy = HOOK
    length = TOWEL_L * (1.0 if layer == 0 else 0.80)
    width = TOWEL_W * (1.0 if layer == 0 else 0.93)
    spread = 0.03 + (width - 0.03) * (1 - (1 - t) ** 1.5)
    left = hx - 0.012 - 0.085 * t ** 1.3 + (0.045 * t if layer else 0.0)        # the left edge
    x = left + s * spread + 0.006 * math.sin(t * 5.0 + s * 2.0)
    hem = 1.0 - 0.34 * max(0.0, s - 0.22) ** 1.15 - 0.10 * max(0.0, 0.22 - s) / 0.22
    y = hy - 0.010 - length * t * hem
    # folds fan out from the nail: deep and narrow at the top, three soft ones at the hem
    amp = 0.003 + 0.022 * (1 - t) ** 0.7 * min(1.0, t * 8 + 0.2)
    ph = math.tau * (2.6 * s ** 0.85 + 0.10 * math.sin(t * 2.7 + 0.6) + 0.13 * layer)
    fold = (0.5 + 0.5 * math.cos(ph)) ** 0.65                                    # round ridges, sharp valleys
    z = ZF + (0.010 if layer == 0 else 0.003) + amp * fold
    z += 0.0020 * noise.noise(Vector((s * 6.0, t * 8.0, 2.0 + layer)))
    z += 0.004 * max(0.0, t - 0.88) / 0.12 * (0.5 + 0.5 * math.sin(s * 11.0))    # the hem lifts off the boards
    return Vector((x, y, z))


def build_towel(mats, rng):
    ns, nt = 96, 160
    bm = bmesh.new()
    for layer in (1, 0):
        g = [[bm.verts.new(towel_point(i / ns, j / nt, layer)) for i in range(ns + 1)] for j in range(nt + 1)]
        for j in range(nt):
            t = (j + 0.5) / nt
            stripe = 0.775 < t < 0.855 or 0.885 < t < 0.907
            for i in range(ns):
                f = bm.faces.new((g[j][i], g[j + 1][i], g[j + 1][i + 1], g[j][i + 1]))
                f.material_index = 1 if stripe else 0
        # the cloth has an edge: a skirt down to the boards all around
        border = [g[0][i] for i in range(ns + 1)] + [g[j][ns] for j in range(1, nt + 1)]             + [g[nt][i] for i in range(ns - 1, -1, -1)] + [g[j][0] for j in range(nt - 1, 0, -1)]
        low = [bm.verts.new((v.co.x, v.co.y, ZF - 0.001)) for v in border]
        n = len(border)
        for k in range(n):
            f = bm.faces.new((border[k], border[(k + 1) % n], low[(k + 1) % n], low[k]))
            f.material_index = border[k].link_faces[0].material_index
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # the bent nail: a shaft out of the board, bent upward, and the cloth's loop over it
    hook = bmesh.new()
    hx, hy = HOOK
    tube(hook, [(hx, hy - 0.006, ZF - 0.002), (hx, hy - 0.003, ZF + 0.026), (hx - 0.003, hy + 0.008, ZF + 0.036),
                (hx - 0.010, hy + 0.038, ZF + 0.039)], 0.0055, segs=10)
    forged_nail(hook, hx - 0.011, hy + 0.043, ZF + 0.038, 1, rng, r=0.010)
    return [new_obj("hp_towel", bm, [mats["towel"], mats["stripe"]]), new_obj("hp_hook", hook, mats["hook"])]


def build_leaf(mats):
    """A birch leaf stuck to the wet boards near the bottom: a toothed oval with a point, a midrib, a stalk."""
    cx, cy, L, ang = LEAF
    z = ZF
    bm = bmesh.new()
    a = math.radians(ang)
    ca, sa = math.cos(a), math.sin(a)
    nseg = 44
    centre = bm.verts.new((cx, cy, z + 0.0028))
    ring_v = []
    for i in range(nseg):
        t = i / nseg * math.tau
        u = math.cos(t)
        hw = 0.62 * math.sqrt(max(1 - u * u, 0)) * (1.15 - 0.45 * u)
        hw *= 1 + 0.07 * (1 if i % 2 else -1)
        v = hw * (1 if math.sin(t) >= 0 else -1)
        lx, ly = u * L / 2, v * L / 2
        ring_v.append(bm.verts.new((cx + ca * lx - sa * ly, cy + sa * lx + ca * ly, z + 0.0006 + 0.004 * v * v)))
    for i in range(nseg):
        bm.faces.new((centre, ring_v[i], ring_v[(i + 1) % nseg]))
    base = Vector((cx - ca * L / 2, cy - sa * L / 2, z + 0.002))
    tipv = Vector((cx + ca * L * 0.45, cy + sa * L * 0.45, z + 0.003))
    stalk_end = base - Vector((ca, sa, 0)) * (L * 0.32)
    tube(bm, [stalk_end, base, (base + tipv) / 2 + Vector((0, 0, 0.001)), tipv], 0.0016, segs=6)
    return [new_obj("hp_leaf", bm, mats["leaf"])]


def build_hinges(mats, rng):
    """Two hand-forged strap hinges on the rails at the hinge edge (x near 0); the top one is tied with wire."""
    hinge, nails, wire = bmesh.new(), bmesh.new(), bmesh.new()
    for y in HINGES:
        xe, L, h0, h1 = X1 + 0.004, 0.36, 0.062, 0.034
        outline = [(xe, y - h0 / 2), (xe, y + h0 / 2), (xe - 0.05, y + h0 / 2 - 0.004), (xe - L * 0.72, y + h1 / 2),
                   (xe - L * 0.78, y + h1 / 2 + 0.012), (xe - L, y + 0.002), (xe - L * 0.78, y - h1 / 2 - 0.012),
                   (xe - L * 0.72, y - h1 / 2), (xe - 0.05, y - h0 / 2 + 0.004)]
        verts = prism(hinge, outline, ZR + 0.001, ZR - 0.0055, bevel=0.0018)
        for v in verts:                                # hammered
            if v.co.z < ZR - 0.004:
                v.co.z += 0.0006 * noise.noise(Vector((v.co.x * 40, v.co.y * 40, 5.0)))
        # the knuckle: a barrel along the door's edge
        res = bmesh.ops.create_cone(hinge, cap_ends=True, segments=16, radius1=0.011, radius2=0.011, depth=h0 + 0.014)
        for v in res["verts"]:
            v.co = Vector((xe + 0.006 + v.co.x, y + v.co.z, ZR - 0.004 + v.co.y))
        for k, t in enumerate((0.12, 0.38, 0.64)):
            forged_nail(nails, xe - L * t + rng.uniform(-0.004, 0.004), y + rng.uniform(-0.004, 0.004), ZR - 0.0055, -1, rng, r=0.0062)
    # the wire: the top strap's last nail is gone, the end is lashed through two holes in the rail
    y = HINGES[1]
    xw = X1 + 0.004 - 0.36 * 0.80
    for k in range(3):
        x = xw + k * 0.011 + rng.uniform(-0.002, 0.002)
        tube(wire, [(x - 0.004, y - 0.05, ZR + 0.001), (x - 0.002, y - 0.036, ZR - 0.006), (x, y, ZR - 0.011),
                    (x + 0.002, y + 0.036, ZR - 0.006), (x + 0.004, y + 0.05, ZR + 0.001)], 0.0028, segs=8)
    twist = []
    for k in range(14):                                # the twisted ends sticking out below
        t = k / 13
        twist.append((xw + 0.011 + 0.006 * math.sin(t * 16), y - 0.05 - 0.035 * t, ZR - 0.004 - 0.003 * math.cos(t * 16)))
    tube(wire, twist, 0.0028, segs=8)
    return [new_obj("hp_hinges", hinge, mats["hinge"]), new_obj("hp_hinge_nails", nails, mats["nail"]),
            new_obj("hp_wire", wire, mats["wire"])]


LAYOUT = {}


def build(seed=5):
    rng = random.Random(seed)
    mats = {}
    for k in IDS:
        m = bpy.data.materials.new(f"hp_{k}")
        m.use_nodes = True
        m["bake_id"] = IDS[k]
        mats[k] = m
    set_pass(mats.values(), "view")
    xs = board_edges(rng)
    LAYOUT["boards"] = [(round(a, 4), round(b, 4)) for a, b in xs]
    print("boards:", [(round(a, 3), round(b, 3)) for a, b in xs], flush=True)
    hp = build_steel(mats)
    hp += build_boards(mats, rng, xs)
    hp += build_rails(mats, rng, xs)
    hp += build_window(mats, rng)
    hp += build_towel(mats, rng)
    hp += build_leaf(mats)
    hp += build_hinges(mats, rng)
    return hp, mats


# ---------------------------------------------------------------- baking
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
            nt.links.new(em.outputs[0], out.inputs["Surface"])
        else:
            bs = nt.nodes.new("ShaderNodeBsdfDiffuse")
            bs.inputs["Color"].default_value = (*VIEW_COL.get(m.name[3:], (0.5, 0.5, 0.5)), 1)
            nt.links.new(bs.outputs[0], out.inputs["Surface"])


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
    scene.view_settings.view_transform = "Standard"


def load_low():
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="Y", up_axis="Z")       # no axis conversion
    low = bpy.context.selected_objects[0]
    low.name = "lowpoly_door"
    bpy.context.view_layer.objects.active = low
    low.select_set(True)
    bpy.ops.mesh.customdata_custom_splitnormals_clear()
    # every face on its own vertices and flat: the cage can then move each face along its own normal
    bm = bmesh.new()
    bm.from_mesh(low.data)
    bmesh.ops.split_edges(bm, edges=bm.edges[:])
    bm.to_mesh(low.data)
    bm.free()
    for p in low.data.polygons:
        p.use_smooth = False
    low.data.update()
    return low


def cage_distance(n, c):
    """How far above a low-poly face the bake rays start: over everything modelled on that face."""
    if n.z > 0.9 and c.z > 0.05:
        return 0.050            # front: towel folds, sill
    if n.z < -0.9 and c.z > -0.01:
        return 0.040            # back fields: window frame, sill
    if n.z < -0.9:
        return 0.018            # rails and braces: nails, hinges, wire
    if abs(n.z) > 0.3:
        return 0.034            # chipped, sloped faces lie below the rebuilt boards: start above them
    return 0.004


def build_cage(low):
    me = low.data.copy()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.normal_update()
    for f in bm.faces:
        d = cage_distance(f.normal, f.calc_center_median())
        for v in f.verts:
            v.co += f.normal * d
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("cage", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.hide_render = True
    return ob


def bake(low, hp, cage, mats, size, out_dir):
    scene = bpy.context.scene
    setup_cycles(scene)
    for attr in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission",
                 "visible_volume_scatter", "visible_shadow"):
        setattr(low, attr, False)
    if scene.world is None:
        scene.world = bpy.data.worlds.new("bake")
    scene.world.light_settings.distance = 0.08

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
    bk.target = "IMAGE_TEXTURES"
    bk.normal_space = "TANGENT"
    bk.normal_r, bk.normal_g, bk.normal_b = "POS_X", "POS_Y", "POS_Z"  # OpenGL

    bpy.ops.object.select_all(action="DESELECT")
    for o in hp:
        o.select_set(True)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low

    out_dir.mkdir(exist_ok=True)
    passes = [("normal", "NORMAL", "view", 1), ("ao", "AO", "view", 96),
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


def preview(low, out_dir):
    """Clay renders of the high-poly, straight on from both sides: a check of the modelling, not of the skin."""
    scene = bpy.context.scene
    setup_cycles(scene)
    scene.cycles.samples = 48
    low.hide_render = True
    scene.render.resolution_x, scene.render.resolution_y = 800, 1400
    if scene.world is None:
        scene.world = bpy.data.worlds.new("w")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.5, 0.5, 0.5, 1)
    cam_d = bpy.data.cameras.new("cam")
    cam_d.type = "ORTHO"
    cam_d.ortho_scale = 2.2
    cam = bpy.data.objects.new("cam", cam_d)
    scene.collection.objects.link(cam)
    scene.camera = cam
    sun_d = bpy.data.lights.new("sun", "SUN")
    sun_d.energy = 3.0
    sun_d.angle = 0.1
    sun = bpy.data.objects.new("sun", sun_d)
    scene.collection.objects.link(sun)
    for name, z, rot, srot in (("front", 3.0, (0, 0, 0), (math.radians(-35), math.radians(-30), 0)),
                               ("back", -3.0, (0, math.pi, 0), (math.radians(35), math.radians(150), 0))):
        cam.location = (-0.605, 1.056, z)
        cam.rotation_euler = rot
        sun.rotation_euler = srot
        scene.render.filepath = str(out_dir / f"highpoly_{name}.png")
        bpy.ops.render.render(write_still=True)
    low.hide_render = False


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 4096
    bpy.ops.wm.read_factory_settings(use_empty=True)
    low = load_low()
    bb = [low.matrix_world @ Vector(c) for c in low.bound_box]
    print("low-poly bounds:", [round(min(v[i] for v in bb), 3) for i in range(3)],
          [round(max(v[i] for v in bb), 3) for i in range(3)], flush=True)
    hp, mats = build()
    cage = build_cage(low)
    print("high-poly:", {o.name: len(o.data.polygons) for o in hp}, flush=True)
    OUT.mkdir(exist_ok=True)
    LAYOUT.update(nails=NAILS, window=WINDOW, slat=SLAT, sill_h=SILL_H, hook=HOOK, hinges=HINGES)
    (OUT / "layout.json").write_text(json.dumps(LAYOUT, indent=1))
    if "--preview" in argv:
        preview(low, OUT)
    if "--nobake" not in argv:
        bake(low, hp, cage, mats, size, OUT)
    if "--blend" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "door_highpoly.blend"))
    print("done", flush=True)


if __name__ == "__main__":
    main()
