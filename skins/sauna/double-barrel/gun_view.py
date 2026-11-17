"""Просмотр двустволки: несколько частей, у каждой свой материал (как вкладки BARREL/GRIP/MAIN/STOCK/SIGHTS).

tools/blender/viewer.py вешает один материал на все OBJ — у оружия так нельзя, поэтому здесь своё.

  blender -b -P gun_view.py -- --part <obj>=<префикс> [--part ...] --sheet out.png [--blend out.blend]
         [--size 512] [--views default|fp|uvcheck] [--light day|night|both|studio] [--grey]

<префикс>: оригиналы (<p>_bc/_nrm/_sg/_ao.png) или экспорт (<p>_diffuse/_normal/_specgloss/_occlusion.png).
Spec/Gloss как в Rust (Unity Standard Specular): RGB — цвет блика, A — глянец. В Blender приближаем:
яркий цветной spec → металл с этим цветом, тёмный серый → диэлектрик.
--views fp: камера «от первого лица» — приклад у нижнего правого угла, стволы уходят вперёд.
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


PARTS = [p.split("=", 1) for p in opt("--part", many=True)]
SIZE = int(opt("--size", "512"))
SHEET = opt("--sheet")
BLEND = opt("--blend")
VIEWS = opt("--views", "default")
LIGHT = opt("--light", "both")
GREY = "--grey" in args
ASPECT = float(opt("--aspect", "1.0"))

NAMES = {"d": ("diffuse", "bc"), "n": ("normal", "nrm"), "s": ("specgloss", "sg"), "o": ("occlusion", "ao")}


def tex_path(prefix, key):
    for suf in NAMES[key]:
        p = Path(f"{prefix}_{suf}.png").resolve()
        if p.exists():
            return p
    return None


def material(name, prefix):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.use_backface_culling = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    bs = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    bs.inputs["Roughness"].default_value = 0.7
    if prefix in ("", "grey") or prefix.startswith("#"):
        h = prefix[1:] if prefix.startswith("#") else "808080"
        rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        bs.inputs["Base Color"].default_value = (*[x ** 2.2 for x in rgb], 1)
        return m

    def tex(key, cs):
        p = tex_path(prefix, key)
        if not p:
            return None
        n = N.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(str(p), check_existing=True)
        n.image.colorspace_settings.name = cs
        return n

    d = tex("d", "sRGB")
    base = d.outputs["Color"] if d else None
    o = tex("o", "Non-Color")
    if o and base is not None:
        mul = N.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs["Factor"].default_value = 1.0
        L.new(base, mul.inputs[6])
        L.new(o.outputs["Color"], mul.inputs[7])
        base = mul.outputs[2]
    n = tex("n", "Non-Color")
    if n:
        nm = N.new("ShaderNodeNormalMap")
        L.new(n.outputs["Color"], nm.inputs["Color"])
        L.new(nm.outputs["Normal"], bs.inputs["Normal"])
    g = tex("s", "sRGB")
    if g:
        inv = N.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        L.new(g.outputs["Alpha"], inv.inputs[1])
        L.new(inv.outputs[0], bs.inputs["Roughness"])
        # металличность ~ яркость spec: 0.04 (диэлектрик) → 0, ≥ 0.45 → 1
        bw = N.new("ShaderNodeRGBToBW")
        L.new(g.outputs["Color"], bw.inputs["Color"])
        mr = N.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = 0.06
        mr.inputs["From Max"].default_value = 0.45
        L.new(bw.outputs["Val"], mr.inputs["Value"])
        L.new(mr.outputs["Result"], bs.inputs["Metallic"])
        if base is not None:
            mix = N.new("ShaderNodeMix")
            mix.data_type = "RGBA"
            L.new(mr.outputs["Result"], mix.inputs["Factor"])
            L.new(base, mix.inputs[6])
            L.new(g.outputs["Color"], mix.inputs[7])
            base = mix.outputs[2]
    if base is not None:
        if GREY:
            bw2 = N.new("ShaderNodeRGBToBW")
            L.new(base, bw2.inputs["Color"])
            base = bw2.outputs["Val"]
        L.new(base, bs.inputs["Base Color"])
    return m


def lights(scene, mode):
    world = scene.world or bpy.data.worlds.new("w")
    scene.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    for ob in [ob for ob in scene.objects if ob.type == "LIGHT"]:
        bpy.data.objects.remove(ob)
    if mode == "day":
        bg.inputs["Color"].default_value = (0.55, 0.62, 0.75, 1)
        bg.inputs["Strength"].default_value = 0.8
        rot, energy, colour = (math.radians(50), math.radians(10), math.radians(-35)), 3.5, (1.0, 0.96, 0.9)
    elif mode == "studio":
        bg.inputs["Color"].default_value = (0.6, 0.6, 0.62, 1)
        bg.inputs["Strength"].default_value = 1.0
        rot, energy, colour = (math.radians(35), 0, math.radians(20)), 2.5, (1.0, 0.97, 0.93)
    else:
        bg.inputs["Color"].default_value = (0.03, 0.04, 0.07, 1)
        bg.inputs["Strength"].default_value = 1.0
        rot, energy, colour = (math.radians(55), 0, math.radians(-25)), 0.35, (0.6, 0.7, 1.0)
    bpy.ops.object.light_add(type="SUN", rotation=rot)
    sun = bpy.context.active_object.data
    sun.energy, sun.color, sun.angle = energy, colour, math.radians(3)
    if mode == "night":   # тёплый свет от каменки сбоку — как ночные кадры сета
        bpy.ops.object.light_add(type="POINT", location=(0.6, -0.4, 0.3))
        pl = bpy.context.active_object.data
        pl.energy, pl.color, pl.shadow_soft_size = 25, (1.0, 0.55, 0.25), 0.2


def camera(scene, target, eye, lens=50):
    cam = scene.camera
    if cam is None:
        bpy.ops.object.camera_add()
        cam = bpy.context.active_object
        scene.camera = cam
    cam.location = eye
    cam.rotation_euler = (target - eye).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    cam.data.clip_start = 0.005


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    objs = []
    for obj, prefix in PARTS:
        bpy.ops.wm.obj_import(filepath=str(Path(obj).resolve()), forward_axis="NEGATIVE_Z", up_axis="Y")
        mat = material(Path(obj).stem, prefix)
        for ob in bpy.context.selected_objects:
            ob.data.materials.clear()
            ob.data.materials.append(mat)
            bpy.context.view_layer.objects.active = ob
            bpy.ops.object.shade_smooth()
            objs.append(ob)
    bpy.context.view_layer.update()
    # патроны лежат сбоку (для анимации перезарядки) — в кадрирование не берём
    framed = [ob for ob in objs if "shell" not in ob.name.lower()] or objs
    pts = [ob.matrix_world @ Vector(c) for ob in framed for c in ob.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    c = (lo + hi) / 2
    r = (hi - lo).length / 2

    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"
    vt = [v.identifier for v in scene.view_settings.bl_rna.properties["view_transform"].enum_items]
    scene.view_settings.view_transform = "AgX" if "AgX" in vt else "Filmic"
    W, H = int(SIZE * ASPECT), SIZE
    scene.render.resolution_x, scene.render.resolution_y = W, H

    # Blender: X = OBJ x (вправо от стрелка), Y = -OBJ z (стволы смотрят в -Y), Z = вверх
    D = 2.9 * r * float(opt("--zoom", "1.0")) / min(ASPECT, 1.0)
    shots = {
        "default": [("left", c + Vector((-D, 0, 0.0)), c, 50),
                    ("right", c + Vector((D, 0, 0.0)), c, 50),
                    ("top", c + Vector((0.0, 0.0001, D)), c, 50),
                    ("bottom", c + Vector((0.0, 0.0001, -D)), c, 50),
                    ("left34", c + Vector((-0.7 * D, 0.6 * D, 0.35 * D)), c, 50),
                    ("front34", c + Vector((0.6 * D, -0.75 * D, 0.3 * D)), c, 50)],
        # от первого лица: глаз позади и выше приклада, чуть левее; оружие у правого края кадра
        "fp": [("fp", Vector((c.x - 0.09, hi.y + 0.16, hi.z + 0.10)),
                Vector((c.x - 0.03, lo.y - 0.15, c.z + 0.02)), 32),
               ("fp_close", Vector((c.x - 0.07, c.y + 0.12, hi.z + 0.07)),
                Vector((c.x + 0.01, lo.y, c.z)), 28)],
    }[VIEWS]

    modes = {"both": ("day", "night"), "day": ("day",), "night": ("night",), "studio": ("studio",)}[LIGHT]
    if SHEET:
        out = Path(SHEET).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        for mode in modes:
            lights(scene, mode)
            row = []
            for name, eye, tgt, lens in shots:
                camera(scene, tgt, eye, lens)
                f = out.with_name(f"_{out.stem}_{mode}_{name}.png")
                scene.render.filepath = str(f)
                bpy.ops.render.render(write_still=True)
                img = bpy.data.images.load(str(f))
                row.append(np.array(img.pixels[:]).reshape(H, W, 4))
                bpy.data.images.remove(img)
                f.unlink()
            rows.append(np.concatenate(row, axis=1))
        sheet = np.concatenate(rows[::-1], axis=0)
        im = bpy.data.images.new(out.stem, sheet.shape[1], sheet.shape[0], alpha=True)
        im.pixels[:] = sheet.ravel()
        im.filepath_raw = str(out)
        im.file_format = "PNG"
        im.save()
        print("sheet", out, flush=True)
    if BLEND:
        lights(scene, "day")
        name, eye, tgt, lens = shots[0]
        camera(scene, tgt, eye, lens)
        bpy.ops.wm.save_as_mainfile(filepath=str(Path(BLEND).resolve()))
        print("saved", BLEND, flush=True)


if __name__ == "__main__":
    main()
