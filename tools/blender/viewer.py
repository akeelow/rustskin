"""Skin viewer: look at a Rust skin in Blender the way the game shows it, before going in game.

Builds a scene with the item (one or more OBJ meshes sharing one material), its skin maps wired
like the Rust editor slots, a stand-in mannequin for clothing, day and night lighting, and renders
a contact sheet: front / 3-4 / side / back / top / close-up, by day and by night. Optionally saves
the scene (.blend) to open in Blender and orbit freely.

  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P tools/blender/viewer.py --
      --obj <a.obj> [--obj <b.obj> ...] --tex <prefix> [--cutoff 0.24] [--wear] [--units m|cm]
      [--focus x,y,z] [--sheet out.png] [--blend out.blend] [--size 512]

<prefix> + _diffuse.png (RGBA: alpha -> Alpha Cutoff), _normal.png (OpenGL), _specgloss.png
(clothing: RGB spec colour, A gloss) or _metalgloss.png (deployables: R metal, A gloss),
_emission.png, _occlusion.png - whatever exists. --wear adds the mannequin (clothing).
Like the game: back faces are culled, alpha is a hard cut at --cutoff, emission x 3.
--focus: point (OBJ space: Y up, +Z front) for the close-up, default the item's centre.
--up z: the OBJ is Z up (3ds Max export, e.g. the bed); --focus is then in that OBJ's x,y,z.
"""
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(name, default=None, many=False):
    vals = [args[i + 1] for i, a in enumerate(args) if a == name]
    return vals if many else (vals[-1] if vals else default)


OBJS = [Path(p).resolve() for p in opt("--obj", many=True)]
PREFIX = opt("--tex")
CUTOFF = float(opt("--cutoff", "0.0"))
WEAR = "--wear" in args
UNITS = 0.01 if opt("--units", "m") == "cm" else 1.0
SIZE = int(opt("--size", "512"))
SHEET = opt("--sheet")
BLEND = opt("--blend")
FOCUS = opt("--focus")
ZUP = opt("--up", "y").lower() == "z"   # OBJ exported Z up (3ds Max, e.g. the bed)


def tex_path(name):
    p = Path(f"{PREFIX}_{name}.png").resolve()
    return p if p.exists() else None


def material():
    m = bpy.data.materials.new("skin")
    m.use_nodes = True
    m.use_backface_culling = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    bs = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    bs.inputs["Roughness"].default_value = 0.7

    def tex(name, cs):
        p = tex_path(name)
        if not p:
            return None
        n = N.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(str(p))
        n.image.colorspace_settings.name = cs
        return n

    d = tex("diffuse", "sRGB")
    if d:
        L.new(d.outputs["Color"], bs.inputs["Base Color"])
        if CUTOFF > 0:
            c = N.new("ShaderNodeMath")
            c.operation = "GREATER_THAN"
            c.inputs[1].default_value = CUTOFF
            L.new(d.outputs["Alpha"], c.inputs[0])
            L.new(c.outputs[0], bs.inputs["Alpha"])
            try:
                m.surface_render_method = "DITHERED"
            except (AttributeError, TypeError):
                pass
    n = tex("normal", "Non-Color")
    if n:
        nm = N.new("ShaderNodeNormalMap")
        L.new(n.outputs["Color"], nm.inputs["Color"])
        L.new(nm.outputs["Normal"], bs.inputs["Normal"])
    for kind in ("specgloss", "metalgloss"):
        g = tex(kind, "Non-Color")
        if not g:
            continue
        inv = N.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        L.new(g.outputs["Alpha"], inv.inputs[1])
        L.new(inv.outputs[0], bs.inputs["Roughness"])
        sep = N.new("ShaderNodeSeparateColor")
        L.new(g.outputs["Color"], sep.inputs["Color"])
        if kind == "metalgloss":
            L.new(sep.outputs["Red"], bs.inputs["Metallic"])
        else:
            L.new(sep.outputs["Red"], bs.inputs["Specular IOR Level"])
        break
    e = tex("emission", "sRGB")
    if e:
        L.new(e.outputs["Color"], bs.inputs["Emission Color"])
        bs.inputs["Emission Strength"].default_value = 3.0
    o = tex("occlusion", "Non-Color")
    if o and d:
        mul = N.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs["Factor"].default_value = 1.0
        L.new(d.outputs["Color"], mul.inputs[6])
        L.new(o.outputs["Color"], mul.inputs[7])
        L.new(mul.outputs[2], bs.inputs["Base Color"])
    return m


def mannequin():
    """A plain stand-in body sized like the Rust player (shoulders ~1.45 m, head top ~1.8 m)."""
    skin = bpy.data.materials.new("skin_body")
    skin.use_nodes = True
    b = next(n for n in skin.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (0.36, 0.22, 0.15, 1)
    b.inputs["Roughness"].default_value = 0.6
    parts = []

    def blob(loc, scale, kind="sphere"):
        if kind == "sphere":
            bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, location=loc)
        else:
            bpy.ops.mesh.primitive_cylinder_add(vertices=32, location=loc)
        o = bpy.context.active_object
        o.scale = scale
        bpy.ops.object.shade_smooth()
        o.data.materials.append(skin)
        parts.append(o)

    # Blender axes: X = OBJ x, Y = -OBJ z (front is -Y), Z = OBJ y (up)
    blob((0, 0.0, 1.25), (0.17, 0.125, 0.22))           # chest
    blob((0, 0.0, 1.02), (0.15, 0.10, 0.16))            # belly / hips
    blob((0, 0.0, 1.41), (0.215, 0.115, 0.075))         # shoulders
    blob((0, 0.01, 1.53), (0.055, 0.055, 0.07), "cyl")  # neck
    blob((0, 0.0, 1.67), (0.095, 0.11, 0.12))           # head
    for sx in (-1, 1):
        blob((sx * 0.255, 0.0, 1.27), (0.05, 0.05, 0.15), "cyl")  # upper arm
        blob((sx * 0.27, 0.0, 1.0), (0.042, 0.042, 0.15), "cyl")   # forearm
        blob((sx * 0.09, 0.0, 0.55), (0.07, 0.07, 0.45), "cyl")    # leg
    return parts


def ground():
    bpy.ops.mesh.primitive_plane_add(size=6)
    g = bpy.context.active_object
    m = bpy.data.materials.new("ground")
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (0.42, 0.36, 0.27, 1)
    b.inputs["Roughness"].default_value = 0.9
    g.data.materials.append(m)


def lights(scene, mode):
    world = scene.world or bpy.data.worlds.new("w")
    scene.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    for o in [o for o in scene.objects if o.type == "LIGHT"]:
        bpy.data.objects.remove(o)
    if mode == "day":
        bg.inputs["Color"].default_value = (0.55, 0.62, 0.75, 1)
        bg.inputs["Strength"].default_value = 0.8
        rot, energy, colour = (math.radians(50), math.radians(10), math.radians(-35)), 3.5, (1.0, 0.96, 0.9)
    else:
        bg.inputs["Color"].default_value = (0.03, 0.04, 0.07, 1)
        bg.inputs["Strength"].default_value = 1.0
        rot, energy, colour = (math.radians(55), 0, math.radians(-25)), 0.35, (0.6, 0.7, 1.0)
    bpy.ops.object.light_add(type="SUN", rotation=rot)
    sun = bpy.context.active_object.data
    sun.energy = energy
    sun.color = colour
    sun.angle = math.radians(3)


def camera(scene, target, direction, dist, lens=50):
    cam = scene.camera
    if cam is None:
        bpy.ops.object.camera_add()
        cam = bpy.context.active_object
        scene.camera = cam
    eye = target + Vector(direction).normalized() * dist
    cam.location = eye
    cam.rotation_euler = (target - eye).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens


def to_blender(p):
    x, y, z = p
    return Vector((x, y, z)) if ZUP else Vector((x, -z, y))


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    mat = material()
    objs = []
    for p in OBJS:
        if ZUP:
            bpy.ops.wm.obj_import(filepath=str(p), forward_axis="Y", up_axis="Z")
        else:
            bpy.ops.wm.obj_import(filepath=str(p), forward_axis="NEGATIVE_Z", up_axis="Y")
        for o in bpy.context.selected_objects:
            o.scale = (UNITS, UNITS, UNITS)
            o.data.materials.clear()
            o.data.materials.append(mat)
            objs.append(o)
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    centre = (lo + hi) / 2
    radius = max((hi - lo).length / 2, 0.2)
    if WEAR:
        mannequin()
        centre = Vector((0, 0, max(centre.z, 1.0)))
        radius = max(radius, 0.45)
    ground()
    focus = to_blender([float(v) * UNITS for v in FOCUS.split(",")]) if FOCUS else (lo + hi) / 2

    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"
    vt = [v.identifier for v in scene.view_settings.bl_rna.properties["view_transform"].enum_items]
    scene.view_settings.view_transform = "AgX" if "AgX" in vt else "Filmic"
    scene.render.resolution_x = scene.render.resolution_y = SIZE

    # (name, direction from target, distance factor, target)
    shots = [("front", (0.0, -1, 0.15), 2.6, centre), ("three_quarter", (0.7, -1, 0.3), 2.6, centre),
             ("side", (1, 0.0, 0.1), 2.6, centre), ("back", (-0.2, 1, 0.25), 2.6, centre),
             ("top", (0.15, -0.35, 1), 2.6, centre), ("close", (0.35, -1, 0.35), 1.0, focus)]
    if SHEET:
        out = Path(SHEET).resolve()
        tiles = []
        for mode in ("day", "night"):
            lights(scene, mode)
            row = []
            for name, d, k, tgt in shots:
                camera(scene, tgt, d, radius * k)
                f = out.with_name(f"{out.stem}_{mode}_{name}.png")
                scene.render.filepath = str(f)
                bpy.ops.render.render(write_still=True)
                img = bpy.data.images.load(str(f))
                row.append(np.array(img.pixels[:]).reshape(SIZE, SIZE, 4))
                bpy.data.images.remove(img)
                f.unlink()
            tiles.append(np.concatenate(row, axis=1))
        sheet = np.concatenate(tiles[::-1], axis=0)              # pixel rows are bottom-up
        im = bpy.data.images.new(out.stem, sheet.shape[1], sheet.shape[0], alpha=True)
        im.pixels[:] = sheet.ravel()
        im.filepath_raw = str(out)
        im.file_format = "PNG"
        im.save()
        print("sheet", out, flush=True)
    if BLEND:
        lights(scene, "day")
        camera(scene, centre, (0.7, -1, 0.3), radius * 2.6)
        bpy.ops.wm.save_as_mainfile(filepath=str(Path(BLEND).resolve()))
        print("saved", BLEND, flush=True)


if __name__ == "__main__":
    main()
