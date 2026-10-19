"""Sauna Changing Locker v3: model the sauna props of one compartment and render them head-on.

The locker's three compartments share one UV patch for their back wall, so whatever stands or
hangs in them is the same in all three. Rather than baking through a cage, the props are
rendered with an orthographic camera looking straight at the back wall; texture_v3.py then maps
each back-wall texel (local x, height) to a pixel of these renders.

Compartment-local space, centimetres, Blender axes: X = OBJ x (-28..28), Z = OBJ y (up, 15..217),
Y = -OBJ z (the back wall is at Y = +28, the open front at Y = -20).

  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/locker/props_v3.py

Writes bake/props_{albedo,normal,shade,emit}.png (RGBA, alpha = prop coverage for albedo).
Sections: top 165-217 (bucket with ladle, candle lantern, felt hat on a peg), middle 84-163 (towel
and birch whisk on pegs), lower 49-81 (birch logs, ends out; two amber bottles; a soap bar).
"""
import math
import random
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector, noise

HERE = Path(__file__).resolve().parent
OUT = HERE / "bake"
X0, X1, Y0, Y1 = -28.0, 28.0, 15.0, 217.0
WALL_Y = 28.0
RES_X, RES_Y = 560, 2020
rng = random.Random(5)


def hexc(h):
    """sRGB hex -> linear RGB (the passes are rendered with the Standard view transform)."""
    return tuple((int(h[i:i + 2], 16) / 255) ** 2.2 for i in (1, 3, 5))


MATS = {}


def mat(name, color, **flags):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m["color"] = color
    for k, v in flags.items():
        m[k] = v
    MATS[name] = m
    return m


def obj_from_bm(name, bm, m, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(m)
    return ob


def cyl(bm, c, r1, r2, h, segs=32, axis="Z"):
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r1, radius2=r2, depth=h)
    for v in res["verts"]:
        p = v.co.copy()
        if axis == "Y":
            p = Vector((p.x, p.z, p.y))
        elif axis == "X":
            p = Vector((p.z, p.y, p.x))
        v.co = Vector(c) + p
    return res["verts"]


def box(bm, c, s, bevel=0.0):
    res = bmesh.ops.create_cube(bm, size=1.0)
    first = len(bm.verts) - len(res["verts"])
    for v in res["verts"]:
        v.co = Vector((c[0] + v.co.x * s[0], c[1] + v.co.y * s[1], c[2] + v.co.z * s[2]))
    if bevel:
        bmesh.ops.bevel(bm, geom=list({e for v in res["verts"] for e in v.link_edges}), offset=bevel,
                        segments=3, affect="EDGES", clamp_overlap=True)
    return list(bm.verts)[first:]


def torus(bm, c, R, r, segs=40, ring=8):
    """Torus lying flat (axis Z) at c: ring radius R, tube radius r."""
    verts = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        row = []
        for j in range(ring):
            b = 2 * math.pi * j / ring
            p = Vector(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a), r * math.sin(b)))
            row.append(bm.verts.new(Vector(c) + p))
        verts.append(row)
    for i in range(segs):
        for j in range(ring):
            bm.faces.new((verts[i][j], verts[(i + 1) % segs][j], verts[(i + 1) % segs][(j + 1) % ring], verts[i][(j + 1) % ring]))


# ---------------------------------------------------------------- props
def peg(x, z):
    bm = bmesh.new()
    cyl(bm, (x, WALL_Y - 3, z), 1.1, 1.3, 6, 16, axis="Y")
    return obj_from_bm("peg", bm, mat("peg", hexc("#6B4D33")))


def bucket():
    """Wooden sauna bucket (shaika) on the top shelf, two iron hoops, a ladle leaning in it."""
    cx, cy, base = -13.0, 12.0, 165.0
    bm = bmesh.new()
    staves = 22
    for i in range(staves):
        a0, a1 = 2 * math.pi * i / staves, 2 * math.pi * (i + 0.94) / staves
        r0, r1, h = 10.0, 11.5, 14.0
        quad = []
        for (a, r, z) in ((a0, r0, 0), (a1, r0, 0), (a1, r1, h), (a0, r1, h)):
            quad.append(bm.verts.new(Vector((cx + r * math.cos(a), cy + r * math.sin(a), base + z))))
        bm.faces.new(quad)
        inner = [bm.verts.new(Vector((v.co.x - (v.co.x - cx) * 0.1, v.co.y - (v.co.y - cy) * 0.1, v.co.z))) for v in quad]
        bm.faces.new(inner[::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    b = obj_from_bm("bucket", bm, mat("bucket", hexc("#A27D52"), staves=1), smooth=False)
    hb = bmesh.new()
    torus(hb, (cx, cy, base + 3), 10.4, 0.45)
    torus(hb, (cx, cy, base + 11), 11.3, 0.45)
    h = obj_from_bm("hoops", hb, mat("hoops", hexc("#3A322C")))
    lb = bmesh.new()
    cyl(lb, (0, 0, 0), 4.0, 3.2, 3.0, 24)
    cyl(lb, (0, 0, 13), 0.8, 0.7, 24, 12)
    lad = obj_from_bm("ladle", lb, mat("ladle", hexc("#8E6A44")))
    lad.location = (cx + 4, cy - 2, base + 10)
    lad.rotation_euler = (math.radians(-25), math.radians(20), 0)
    return [b, h, lad]


def lantern():
    """Glass jar lantern with a burning candle: the warm glow of the set."""
    cx, cy, base = 5.0, 4.0, 165.0
    bm = bmesh.new()
    cyl(bm, (cx, cy, base + 0.8), 5.6, 5.6, 1.6, 24)
    cyl(bm, (cx, cy, base + 17.2), 5.8, 4.6, 1.6, 24)
    torus(bm, (cx, cy, base + 21.0), 2.8, 0.35, 24, 6)
    frame = obj_from_bm("lantern_frame", bm, mat("iron", hexc("#2E2A27")))
    for k in range(4):                                      # four wire bars
        a = math.pi / 4 + k * math.pi / 2
        wb = bmesh.new()
        cyl(wb, (cx + 5.3 * math.cos(a), cy + 5.3 * math.sin(a), base + 9.0), 0.35, 0.35, 15.0, 8)
        obj_from_bm(f"lantern_bar{k}", wb, mat("iron", hexc("#2E2A27")))
    gb = bmesh.new()
    cyl(gb, (cx, cy, base + 9.0), 5.0, 5.0, 14.5, 24)
    glass = obj_from_bm("lantern_glass", gb, mat("glass", hexc("#F0B868"), glow=0.55))
    cb = bmesh.new()
    cyl(cb, (cx, cy, base + 5.0), 2.0, 2.0, 8.0, 16)
    candle = obj_from_bm("candle", cb, mat("candle", hexc("#E6DCC4"), glow=0.3))
    fb = bmesh.new()
    res = bmesh.ops.create_uvsphere(fb, u_segments=12, v_segments=8, radius=1.0)
    for v in res["verts"]:
        v.co = Vector((cx + v.co.x * 0.9, cy + v.co.y * 0.9, base + 10.8 + v.co.z * 2.0 + max(v.co.z, 0) * 0.8))
    flame = obj_from_bm("flame", fb, mat("flame", hexc("#FFC060"), glow=1.0))
    return [frame, glass, candle, flame]


def felt_hat():
    """Felt sauna hat on a peg, brim down, tip up (seen from the front: a soft cone)."""
    x, z = 17.0, 196.0
    bm = bmesh.new()
    verts = cyl(bm, (x, WALL_Y - 7, z), 9.0, 2.5, 15.0, 32)
    for v in verts:
        n = noise.noise(v.co * 0.25)
        v.co.x += 0.6 * n
        v.co.y += 0.4 * n
    brim = bmesh.new()
    torus(brim, (x, WALL_Y - 7, z - 7.2), 9.4, 1.4, 40, 10)
    a = obj_from_bm("hat", bm, mat("felt", hexc("#B3A48A"), felt=1))
    b = obj_from_bm("hat_brim", brim, mat("felt", hexc("#B3A48A"), felt=1))
    return [a, b, peg(x, z + 8)]


def towel():
    """Washed linen towel with brick stripes hanging from a peg: a draped grid with folds."""
    x0, top, w, h = -8.0, 152.0, 22.0, 50.0
    bm = bmesh.new()
    nu, nv = 40, 60
    grid = []
    for j in range(nv + 1):
        v = j / nv
        row = []
        width = w * (0.22 + 0.78 * min(1.0, v / 0.35) ** 0.8)
        for i in range(nu + 1):
            u = i / nu - 0.5
            fold = math.sin(u * math.pi * 2 * (1.5 + 2.0 * min(v / 0.5, 1))) * (0.6 + 1.6 * v)
            hem = 1.2 * math.sin(u * 9 + 1.3) * (v > 0.95)
            row.append(bm.verts.new(Vector((x0 + u * width, WALL_Y - 2.2 - fold - 1.5 * (1 - v) ** 3,
                                            top - v * h + hem))))
        grid.append(row)
    for j in range(nv):
        for i in range(nu):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    t = obj_from_bm("towel", bm, mat("towel", hexc("#C2B9A5"), stripes=top - 0.83 * h, terry=1))
    return [t, peg(x0, top + 3)]


def venik():
    """Birch whisk: a handle bound with twine, a fan of small leaves below it."""
    x, top = 15.0, 156.0
    parts = []
    hb = bmesh.new()
    cyl(hb, (x, WALL_Y - 5, top - 6), 1.6, 1.9, 12, 16)
    parts.append(obj_from_bm("venik_handle", hb, mat("twig", hexc("#6E5A44"))))
    lb = bmesh.new()
    for k in range(260):
        v = rng.random()
        z = top - 12 - v * 34
        spread = 2.5 + 9.5 * math.sin(min(v * 1.25, 1) * math.pi * 0.62)
        a = rng.uniform(-1, 1)
        res = bmesh.ops.create_icosphere(lb, subdivisions=1, radius=1.0)
        cx, cy = x + a * spread, WALL_Y - 5 + rng.uniform(-3.5, 3.5) * (0.4 + v)
        rot = rng.uniform(0, math.pi)
        for vv in res["verts"]:
            p = vv.co
            px, pz = p.x * 1.4, p.z * 2.2
            vv.co = Vector((cx + px * math.cos(rot) - pz * math.sin(rot), cy + p.y * 0.35, z + px * math.sin(rot) + pz * math.cos(rot)))
    parts.append(obj_from_bm("venik_leaves", lb, mat("leaves", hexc("#5C6A39"), leaves=1)))
    parts.append(peg(x, top + 2))
    return parts


def logs():
    """Birch logs on the lower shelf, ends facing out: white bark, light end grain."""
    base = 49.0
    out = []
    spots = [(-18, 0), (-9, 0), (0, 0), (-13.5, 1), (-4.5, 1), (-9, 2)]
    for i, (lx, row) in enumerate(spots):
        r = rng.uniform(3.9, 4.6)
        bm = bmesh.new()
        cyl(bm, (lx + rng.uniform(-0.5, 0.5), 2.0, base + r + row * 7.6), r, r, 30, 28, axis="Y")
        out.append(obj_from_bm(f"log{i}", bm, mat("birch", hexc("#DCD6C8"), bark=1)))
    return out


def bottles():
    out = []
    for i, (x, h) in enumerate(((10.0, 15.0), (17.5, 12.0))):
        bm = bmesh.new()
        base = 49.0
        cyl(bm, (x, 10.0, base + h * 0.35), 3.2, 3.2, h * 0.7, 24)
        cyl(bm, (x, 10.0, base + h * 0.78), 3.2, 1.0, h * 0.18, 24)
        cyl(bm, (x, 10.0, base + h * 0.95), 1.0, 1.0, h * 0.16, 16)
        out.append(obj_from_bm(f"bottle{i}", bm, mat("amber", hexc("#7A3E12"), glass=1)))
        cb = bmesh.new()
        cyl(cb, (x, 10.0, base + h * 1.05), 1.05, 0.9, 1.6, 12)
        out.append(obj_from_bm(f"cork{i}", cb, mat("cork", hexc("#A88454"))))
    sb = bmesh.new()
    box(sb, (23.0, 6.0, 49.0 + 1.6), (5.0, 3.2, 3.2), bevel=0.6)
    out.append(obj_from_bm("soap", sb, mat("soap", hexc("#C9B98A"))))
    return out


def wall():
    bm = bmesh.new()
    for p in ((X0 - 5, WALL_Y, Y0 - 5), (X1 + 5, WALL_Y, Y0 - 5), (X1 + 5, WALL_Y, Y1 + 5), (X0 - 5, WALL_Y, Y1 + 5)):
        bm.verts.new(Vector(p))
    bm.faces.new(bm.verts)
    ob = obj_from_bm("wall", bm, mat("wall", (0.8, 0.8, 0.8)), smooth=False)
    ob.is_shadow_catcher = True
    sb = bmesh.new()
    for zz in (49.0, 84.0, 165.0):                          # shelves: shadow catchers too
        box(sb, (0, 4, zz - 1.5), (56, 48, 3))
    sh = obj_from_bm("shelves", sb, mat("wall", (0.8, 0.8, 0.8)), smooth=False)
    sh.is_shadow_catcher = True
    return [ob, sh]


# ---------------------------------------------------------------- passes
def set_pass(kind):
    for m in MATS.values():
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        col = tuple(m["color"]) + (1.0,)
        if m.name == "wall":
            bsdf = nt.nodes.new("ShaderNodeBsdfDiffuse")
            bsdf.inputs["Color"].default_value = (0.8, 0.8, 0.8, 1)
            nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
            continue
        em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        if kind == "albedo":
            src = color_tree(nt, m, col)
            nt.links.new(src, em.inputs["Color"])
        elif kind == "normal":
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            vm = nt.nodes.new("ShaderNodeVectorMath")
            vm.operation = "MULTIPLY_ADD"
            vm.inputs[1].default_value = (0.5, 0.5, 0.5)
            vm.inputs[2].default_value = (0.5, 0.5, 0.5)
            nt.links.new(geo.outputs["Normal"], vm.inputs[0])
            nt.links.new(vm.outputs[0], em.inputs["Color"])
        elif kind == "shade":
            nt.nodes.remove(em)
            bsdf = nt.nodes.new("ShaderNodeBsdfDiffuse")
            bsdf.inputs["Color"].default_value = (0.8, 0.8, 0.8, 1)
            nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
        elif kind == "emit":
            g = m.get("glow", 0.0)
            em.inputs["Color"].default_value = (col[0] * g, col[1] * g, col[2] * g, 1)


def color_tree(nt, m, col):
    """Albedo with simple procedural detail per material (stripes, bark, staves, felt, leaves)."""
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    rgb = nt.nodes.new("ShaderNodeRGB")
    rgb.outputs[0].default_value = col
    noisen = nt.nodes.new("ShaderNodeTexNoise")
    noisen.inputs["Scale"].default_value = 0.6
    noisen.inputs["Detail"].default_value = 6
    nt.links.new(geo.outputs["Position"], noisen.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 0.35
    nt.links.new(rgb.outputs[0], mix.inputs[6])
    nt.links.new(noisen.outputs["Color"], mix.inputs[7])
    last = mix.outputs[2]
    if "stripes" in m:
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(geo.outputs["Position"], sep.inputs[0])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.interpolation = "CONSTANT"
        z0 = m["stripes"]
        els = ramp.color_ramp.elements
        els[0].position, els[0].color = 0.0, (1, 1, 1, 1)
        stops = [(z0 - 3.0, (0.27, 0.04, 0.03, 1)), (z0 - 1.0, (1, 1, 1, 1)), (z0 + 0.5, (0.27, 0.04, 0.03, 1)), (z0 + 1.6, (1, 1, 1, 1))]
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = z0 - 10
        mr.inputs["From Max"].default_value = z0 + 10
        nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
        for zz, c in stops:
            e = els.new((zz - (z0 - 10)) / 20)
            e.color = c
        nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
        stripe = nt.nodes.new("ShaderNodeMix")
        stripe.data_type = "RGBA"
        stripe.blend_type = "MULTIPLY"
        stripe.inputs["Factor"].default_value = 1.0
        nt.links.new(last, stripe.inputs[6])
        nt.links.new(ramp.outputs["Color"], stripe.inputs[7])
        last = stripe.outputs[2]
    if "bark" in m:
        # black lenticels on white bark; ends (normal along Y) light brown end grain
        wave = nt.nodes.new("ShaderNodeTexNoise")
        wave.inputs["Scale"].default_value = 0.35
        mapping = nt.nodes.new("ShaderNodeMapping")
        mapping.inputs["Scale"].default_value = (0.3, 4.0, 3.0)
        nt.links.new(geo.outputs["Position"], mapping.inputs["Vector"])
        nt.links.new(mapping.outputs[0], wave.inputs["Vector"])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.62
        ramp.color_ramp.elements[0].color = (1, 1, 1, 1)
        ramp.color_ramp.elements[1].position = 0.66
        ramp.color_ramp.elements[1].color = (0.12, 0.11, 0.1, 1)
        nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
        dark = nt.nodes.new("ShaderNodeMix")
        dark.data_type = "RGBA"
        dark.blend_type = "MULTIPLY"
        dark.inputs["Factor"].default_value = 1.0
        nt.links.new(last, dark.inputs[6])
        nt.links.new(ramp.outputs["Color"], dark.inputs[7])
        sepn = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(geo.outputs["Normal"], sepn.inputs[0])
        absn = nt.nodes.new("ShaderNodeMath")
        absn.operation = "ABSOLUTE"
        nt.links.new(sepn.outputs["Y"], absn.inputs[0])
        endc = nt.nodes.new("ShaderNodeMix")
        endc.data_type = "RGBA"
        nt.links.new(absn.outputs[0], endc.inputs["Factor"])
        nt.links.new(dark.outputs[2], endc.inputs[6])
        endc.inputs[7].default_value = (0.40, 0.22, 0.09, 1)
        last = endc.outputs[2]
    return last


def render(path, kind, transparent=True):
    set_pass(kind)
    scene = bpy.context.scene
    scene.render.film_transparent = transparent
    scene.cycles.samples = {"shade": 128}.get(kind, 8)
    for o in bpy.data.objects:
        if o.name in ("wall", "shelves"):
            o.hide_render = kind != "shade"
    scene.render.filepath = str(path)
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    bpy.ops.render.render(write_still=True)
    print("rendered", path, flush=True)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
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
    scene.render.resolution_x, scene.render.resolution_y = RES_X, RES_Y
    scene.cycles.use_denoising = True

    bucket()
    lantern()
    felt_hat()
    towel()
    venik()
    logs()
    bottles()
    wall()

    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = Y1 - Y0
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = ((X0 + X1) / 2, -200.0, (Y0 + Y1) / 2)
    cam.rotation_euler = (math.radians(90), 0, 0)
    cam_data.clip_end = 1000
    scene.camera = cam

    world = bpy.data.worlds.new("w")
    scene.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Strength"].default_value = 0.45
    bg.inputs["Color"].default_value = (1, 1, 1, 1)
    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = 2.2
    sun.angle = math.radians(12)
    so = bpy.data.objects.new("sun", sun)
    scene.collection.objects.link(so)
    so.rotation_euler = (math.radians(55), math.radians(-18), math.radians(-12))   # from front, above, a bit left

    OUT.mkdir(exist_ok=True)
    render(OUT / "props_albedo.png", "albedo")
    render(OUT / "props_normal.png", "normal")
    render(OUT / "props_emit.png", "emit")
    render(OUT / "props_shade.png", "shade", transparent=False)
    print("done")


if __name__ == "__main__":
    main()
