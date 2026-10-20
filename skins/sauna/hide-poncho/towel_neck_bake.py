"""Sauna Towel v3 (neck): model a rolled terry towel slung round the neck in Blender and bake it
onto the hide poncho's UVs; whatever the towel doesn't cover becomes transparent.

v2's painted neck towel read as a life jacket (a flat white ring and two flat slabs). Here the
towel is real geometry: a folded towel (11 cm wide, 2.5 cm thick, lumpy terry) swept along a path
that lies on the poncho's surface - up the right side of the chest, over the shoulder, behind the
neck, over the left shoulder and down the chest. Its material carries what makes it a towel: hems
at both ends with a stitched seam, selvedge stitching along both long edges, brick end stripes and
a fringe. Baked onto the poncho (selected to active, rays from 4 cm outside):
  albedo (emission) x ambient occlusion -> diffuse, the hit mask -> alpha, tangent normal.

  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/hide-poncho/towel_neck_bake.py [-- --shape neck|shoulder --blend]

Writes bake/towel_<shape>_{albedo,mask,ao,shade,normal}.png + _path.npy (+ .blend with --blend);
then `.venv/Scripts/python skins/sauna/hide-poncho/compose_neck.py [shoulder]` makes the export textures.
"""
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector, noise
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
ORIG = HERE / "originals"
OUT = HERE / "export"
SIZE = 2048   # 2x the original diffuse: smoother alpha-cut edges (v3.2 had stair steps)

WIDTH, THICK = 0.11, 0.03
NECK_C = Vector((0.0, 0.0, -0.03))            # neck centre in x/z (OBJ space)
RING_RX, RING_RZ = 0.175, 0.155
TAIL_END_Y = 1.17
# the tails keep clear of the flap with the toggles (two hide sheets at x -0.06..0.09 below 1.3 m,
# whose torn edge cut the towel ragged in v3.3) and inside the hide's outer edge
TAIL_X_POS, TAIL_X_NEG = 0.148, 0.112


def lin(h):
    return tuple((int(h[i:i + 2], 16) / 255) ** 2.2 for i in (1, 3, 5))


TOWEL, BRICK, BRICK2, STITCH = lin("#D2CABB"), lin("#7E3127"), lin("#8E4639"), lin("#8C8272")


# ---------------------------------------------------------------- path on the poncho's surface
def surface_path(low):
    bvh = BVHTree.FromObject(low, bpy.context.evaluated_depsgraph_get(), deform=False)
    mw_inv = low.matrix_world.inverted()

    def cast(origin, direction):
        # BVH of the evaluated object is in local space already
        d = Vector(direction).normalized()
        loc, nrm, _, _ = bvh.ray_cast(Vector(origin), d)
        if nrm is not None and nrm.dot(d) > 0:      # back face hit: turn the normal towards the ray
            nrm = -nrm
        return loc, nrm

    pts = []
    # right tail, bottom -> top (front, rays from the front towards -z)
    ring_a = math.radians(42)
    top_r = Vector((NECK_C.x + RING_RX * math.sin(ring_a), 0, NECK_C.z + RING_RZ * math.cos(ring_a)))
    for k in range(40):
        t = k / 39
        y = TAIL_END_Y + t * 0.25
        x = TAIL_X_POS + (top_r.x - TAIL_X_POS) * smoothstep(0.6, 1.0, t)
        loc, n = cast((x, y, 1.0), (0, 0, -1))
        if loc is not None:
            pts.append((loc, n))
    # over the right shoulder, behind the neck, over the left shoulder (rays from above)
    for k in range(90):
        a = ring_a + (2 * math.pi - 2 * ring_a) * k / 89
        x = NECK_C.x + RING_RX * math.sin(a)
        z = NECK_C.z + RING_RZ * math.cos(a)
        loc, n = cast((x, 2.0, z), (0, -1, 0))
        # behind the neck the hide dips into a slit: such rays fall through to the back panel far
        # below - skip them, the towel bridges the gap (the bake only lands on the hide anyway)
        if loc is not None and loc.y > 1.38:
            pts.append((loc, n))
    # left tail, top -> bottom
    for k in range(40):
        t = 1 - k / 39
        y = TAIL_END_Y + t * 0.25
        x = -(TAIL_X_NEG + (top_r.x - TAIL_X_NEG) * smoothstep(0.6, 1.0, t))
        loc, n = cast((x, y, 1.0), (0, 0, -1))
        if loc is not None:
            pts.append((loc, n))
    del mw_inv
    return pts


def shoulder_path(low):
    """Towel over the left shoulder (+x), hanging down the chest and the back. Placed on outer hide
    only (mapped with ray casts, 20.10.2026): the front panel covers x <= 0.18 down to 1.20 m, the
    shoulder top x 0.12..0.26 (the neck opening comes to x 0.12), the back x <= 0.21 down to 1.04 m;
    clear of the toggle flap (x < 0.09 below 1.3 m) and of the small worn hole at the back (0.21, 1.34)."""
    bvh = BVHTree.FromObject(low, bpy.context.evaluated_depsgraph_get(), deform=False)

    def cast(origin, direction):
        d = Vector(direction).normalized()
        loc, nrm, _, _ = bvh.ray_cast(Vector(origin), d)
        if nrm is not None and nrm.dot(d) > 0:
            nrm = -nrm
        return loc, nrm

    pts = []
    for k in range(40):                                   # front, bottom -> top
        t = k / 39
        y = 1.21 + t * 0.21
        x = 0.14 + 0.035 * smoothstep(0.3, 1.0, t)
        loc, n = cast((x, y, 1.0), (0, 0, -1))
        if loc is not None and loc.z > 0:
            pts.append((loc, n))
    for k in range(40):                                   # over the shoulder, front -> back
        z = 0.09 - 0.24 * k / 39
        loc, n = cast((0.18, 2.0, z), (0, -1, 0))
        if loc is not None and loc.y > 1.38:
            pts.append((loc, n))
    for k in range(50):                                   # back, top -> bottom
        t = k / 49
        y = 1.42 - t * 0.37
        x = 0.175 - 0.03 * smoothstep(0.0, 0.7, t)
        loc, n = cast((x, y, -1.0), (0, 0, 1))
        if loc is not None and loc.z < 0:
            pts.append((loc, n))
    return pts


def smoothstep(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def resample(pts, step=0.004):
    P = np.array([p for p, _ in pts])
    Nn = np.array([n for _, n in pts])
    # light smoothing of the polyline (removes kinks between the three parts)
    for _ in range(6):
        P[1:-1] = 0.5 * P[1:-1] + 0.25 * (P[:-2] + P[2:])
        Nn[1:-1] = 0.5 * Nn[1:-1] + 0.25 * (Nn[:-2] + Nn[2:])
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    L = s[-1]
    ss = np.arange(0, L, step)
    Pr = np.stack([np.interp(ss, s, P[:, i]) for i in range(3)], 1)
    Nr = np.stack([np.interp(ss, s, Nn[:, i]) for i in range(3)], 1)
    Nr /= np.linalg.norm(Nr, axis=1, keepdims=True)
    return Pr, Nr, ss, L


def sweep(Pr, Nr, ss, L, K=36):
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")
    rings = []
    prev_b = None
    for i in range(len(Pr)):
        p, n = Vector(Pr[i]), Vector(Nr[i])
        t = Vector(Pr[min(i + 1, len(Pr) - 1)] - Pr[max(i - 1, 0)]).normalized()
        b = t.cross(n).normalized()
        if prev_b is not None and b.dot(prev_b) < 0:   # no flips along the strip (no twists)
            b = -b
        if prev_b is not None:
            b = (b + 2 * prev_b).normalized()           # and no sudden turns
        prev_b = b
        n = b.cross(t).normalized()
        dend = min(ss[i], L - ss[i])
        hem = 0.004 * smoothstep(0.035, 0.02, dend)              # doubled hem at the ends
        taper = 0.6 + 0.4 * smoothstep(0.0, 0.02, dend)
        ring = []
        for k in range(K):
            phi = 2 * math.pi * k / K
            # folded towel: flat-ish oval, a softer rounded fold on one side
            cx = math.cos(phi)
            cy = math.sin(phi)
            w = WIDTH / 2 * cx
            h = (THICK / 2) * (1 + cy) * (0.85 + 0.15 * (1 - abs(cx)) ** 0.5) + hem * (1 + cy) / 2
            lump = 0.0015 * noise.noise(Vector((ss[i] * 40, phi * 2, 0.0))) + 0.0007 * noise.noise(p * 300)
            q = p + b * w * taper + n * (h * taper + 0.0015 + lump)
            ring.append(bm.verts.new(q))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(K):
            a, b_, c, d = rings[i][k], rings[i][(k + 1) % K], rings[i + 1][(k + 1) % K], rings[i + 1][k]
            f = bm.faces.new((a, b_, c, d))
            for loop, (u, v) in zip(f.loops, ((ss[i] / L, k / K), (ss[i] / L, (k + 1) / K),
                                              (ss[i + 1] / L, (k + 1) / K), (ss[i + 1] / L, k / K))):
                loop[uv_layer].uv = (u, v)
    for ring in (rings[0], rings[-1]):                          # cap the ends
        bm.faces.new(ring)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("towel")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


# ---------------------------------------------------------------- materials
def towel_material(L, kind):
    m = bpy.data.materials.new("towel_" + kind)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N, Lk = nt.nodes, nt.links
    out = N.new("ShaderNodeOutputMaterial")
    if kind in ("normal", "ao"):
        bs = N.new("ShaderNodeBsdfDiffuse")
        bs.inputs["Color"].default_value = (0.8, 0.8, 0.8, 1)
        Lk.new(bs.outputs[0], out.inputs[0])
        return m
    em = N.new("ShaderNodeEmission")
    Lk.new(em.outputs[0], out.inputs[0])
    if kind == "mask":
        em.inputs["Color"].default_value = (1, 1, 1, 1)
        return m
    if kind == "shade":
        # the roll's own shading: 1 on top of the folded towel, darker on its rounded sides; from
        # the towel's UV (around), so it doesn't depend on how the hide under it is tilted
        tc = N.new("ShaderNodeTexCoord")
        sep = N.new("ShaderNodeSeparateXYZ")
        Lk.new(tc.outputs["UV"], sep.inputs[0])
        ang = N.new("ShaderNodeMath")
        ang.operation = "MULTIPLY"
        ang.inputs[1].default_value = 2 * math.pi
        Lk.new(sep.outputs["Y"], ang.inputs[0])
        sn = N.new("ShaderNodeMath")
        sn.operation = "SINE"
        Lk.new(ang.outputs[0], sn.inputs[0])
        mx = N.new("ShaderNodeMath")
        mx.operation = "MAXIMUM"
        mx.inputs[1].default_value = 0.0
        Lk.new(sn.outputs[0], mx.inputs[0])
        Lk.new(mx.outputs[0], em.inputs["Color"])
        return m
    tc = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(tc.outputs["UV"], sep.inputs[0])

    def math_(op, a, b=None, c=None):
        n = N.new("ShaderNodeMath")
        n.operation = op
        for i, val in enumerate((a, b, c)):
            if val is None:
                continue
            if isinstance(val, (int, float)):
                n.inputs[i].default_value = val
            else:
                Lk.new(val, n.inputs[i])
        return n.outputs[0]

    along = math_("MULTIPLY", sep.outputs["X"], L)
    dend = math_("MINIMUM", along, math_("SUBTRACT", L, along))
    around = sep.outputs["Y"]
    # bands (1 inside, 0 outside) built from |dend - c| < w
    band = lambda c, w: math_("LESS_THAN", math_("ABSOLUTE", math_("SUBTRACT", dend, c)), w)
    wide = band(0.085, 0.02)
    narrow = band(0.128, 0.007)
    hem = math_("LESS_THAN", dend, 0.03)
    dash_a = math_("LESS_THAN", math_("FRACT", math_("MULTIPLY", around, 0.24 / 0.006)), 0.55)
    hem_stitch = math_("MULTIPLY", band(0.028, 0.0012), dash_a)
    dash_l = math_("LESS_THAN", math_("FRACT", math_("DIVIDE", along, 0.006)), 0.55)
    # selvedge: the two long edges sit at around = 0 and 0.5 (the oval's sides)
    edge_d = math_("MINIMUM", math_("ABSOLUTE", math_("SUBTRACT", around, 0.0)),
                   math_("MINIMUM", math_("ABSOLUTE", math_("SUBTRACT", around, 0.5)), math_("ABSOLUTE", math_("SUBTRACT", around, 1.0))))
    selv = math_("MULTIPLY", math_("LESS_THAN", math_("ABSOLUTE", math_("SUBTRACT", edge_d, 0.03)), 0.004), dash_l)
    fringe = math_("LESS_THAN", dend, 0.006)

    nz = N.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 900.0
    nz.inputs["Detail"].default_value = 4.0
    Lk.new(tc.outputs["Object"], nz.inputs["Vector"])
    mott = N.new("ShaderNodeTexNoise")
    mott.inputs["Scale"].default_value = 25.0
    Lk.new(tc.outputs["Object"], mott.inputs["Vector"])

    def mix(fac, a, b):
        mx = N.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        if isinstance(fac, float):
            mx.inputs["Factor"].default_value = fac
        else:
            Lk.new(fac, mx.inputs["Factor"])
        for idx, val in ((6, a), (7, b)):
            if isinstance(val, tuple):
                mx.inputs[idx].default_value = val + (1.0,) if len(val) == 3 else val
            else:
                Lk.new(val, mx.inputs[idx])
        return mx.outputs[2]

    base = mix(0.25, TOWEL, nz.outputs["Color"])
    base = mix(math_("MULTIPLY", mott.outputs["Fac"], 0.25), base, (0.55, 0.5, 0.42))
    c = mix(wide, base, BRICK)
    c = mix(narrow, c, BRICK2)
    c = mix(math_("MULTIPLY", hem, 0.12), c, (0.3, 0.28, 0.24))
    c = mix(hem_stitch, c, STITCH)
    c = mix(selv, c, STITCH)
    c = mix(math_("MULTIPLY", fringe, 0.3), c, (0.4, 0.38, 0.33))
    Lk.new(c, em.inputs["Color"])
    return m


# ---------------------------------------------------------------- bake
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    bpy.ops.wm.obj_import(filepath=str(ORIG / "attire.hide.poncho_poncho.obj"), forward_axis="NEGATIVE_Z", up_axis="Y")
    low = bpy.context.selected_objects[0]
    low.name = "poncho"

    shape = argv[argv.index("--shape") + 1] if "--shape" in argv else "neck"
    Pr, Nr, ss, L = resample(shoulder_path(low) if shape == "shoulder" else surface_path(low))
    print(f"towel length {L:.2f} m, {len(Pr)} sections", flush=True)
    (HERE / "bake").mkdir(exist_ok=True)
    np.save(HERE / "bake" / f"towel_{shape}_path.npy", np.hstack([Pr, Nr]))   # centre line on the hide, OBJ space
    me = sweep(Pr, Nr, ss, L)
    towel = bpy.data.objects.new("towel", me)
    scene.collection.objects.link(towel)
    towel.matrix_world = low.matrix_world.copy()

    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = kind
        except TypeError:
            continue
        prefs.get_devices()
        if any(d.type == kind for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type == kind
            scene.cycles.device = "GPU"
            break
    scene.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.new("w")
    scene.world = world
    world.light_settings.distance = 0.05

    tm = bpy.data.materials.new("target")
    tm.use_nodes = True
    low.data.materials.clear()
    low.data.materials.append(tm)
    tex = tm.node_tree.nodes.new("ShaderNodeTexImage")
    tm.node_tree.nodes.active = tex
    for attr in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission", "visible_shadow"):
        setattr(low, attr, False)

    bk = scene.render.bake
    bk.use_selected_to_active = True
    bk.use_cage = False
    bk.cage_extrusion = 0.034
    bk.max_ray_distance = 0.05
    bk.margin = 2
    bk.normal_space = "TANGENT"
    bk.normal_r, bk.normal_g, bk.normal_b = "POS_X", "POS_Y", "POS_Z"
    bpy.ops.object.select_all(action="DESELECT")
    towel.select_set(True)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low

    res = {}
    for name, kind, btype, samples in (("albedo", "albedo", "EMIT", 4), ("mask", "mask", "EMIT", 1), ("shade", "shade", "EMIT", 1),
                                       ("normal", "normal", "NORMAL", 1), ("ao", "ao", "AO", 64)):
        towel.data.materials.clear()
        towel.data.materials.append(towel_material(L, kind))
        img = bpy.data.images.new("bake_" + name, SIZE, SIZE, alpha=False, float_buffer=True)
        img.colorspace_settings.name = "Non-Color"
        img.generated_color = (0, 0, 0, 1) if name != "normal" else (0.5, 0.5, 1, 1)
        tex.image = img
        scene.cycles.samples = samples
        bpy.ops.object.bake(type=btype, use_clear=False, margin=2)
        res[name] = np.array(img.pixels[:], dtype=np.float32).reshape(SIZE, SIZE, 4)[::-1, :, :3]
        print("baked", name, flush=True)

    # raw passes -> bake/towel_neck_*.png (rows top-down in numpy, saved as-is); compose_neck.py
    # (in .venv) turns them into the export textures
    (HERE / "bake").mkdir(exist_ok=True)

    def save_png(rgb, path):
        im = bpy.data.images.new(path.stem, SIZE, SIZE, alpha=True)
        im.colorspace_settings.name = "Non-Color"
        rgba = np.dstack([np.clip(rgb, 0, 1), np.ones((SIZE, SIZE))])
        im.pixels[:] = np.ascontiguousarray(rgba[::-1]).ravel()
        im.filepath_raw = str(path)
        im.file_format = "PNG"
        im.save()

    save_png(np.clip(res["albedo"], 0, 1) ** (1 / 2.2), HERE / "bake" / f"towel_{shape}_albedo.png")   # -> sRGB
    save_png(res["mask"], HERE / "bake" / f"towel_{shape}_mask.png")
    save_png(res["ao"], HERE / "bake" / f"towel_{shape}_ao.png")
    save_png(res["shade"], HERE / "bake" / f"towel_{shape}_shade.png")
    save_png(res["normal"], HERE / "bake" / f"towel_{shape}_normal.png")
    if "--blend" in argv:
        (HERE / "bake").mkdir(exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE / "bake" / f"towel_{shape}.blend"))
    print("done", flush=True)


if __name__ == "__main__":
    main()
