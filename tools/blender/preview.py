"""Render a Rust item with its skin textures in Blender (headless).

Usage (from the repo root):
  "<blender.exe>" -b -P tools/blender/preview.py -- <model.obj> <textures_prefix> <out.png> [day|night] [yaw_deg]

<textures_prefix> + _diffuse.png / _normal.png / _metalgloss.png / _occlusion.png / _emission.png
(Rust editor slots: Metal/Gloss = RGB metallic + A smoothness, Normal = OpenGL).
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
obj_path, prefix, out_path = argv[0], argv[1], argv[2]
mode = argv[3] if len(argv) > 3 else "day"
yaw = math.radians(float(argv[4])) if len(argv) > 4 else math.radians(35)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

bpy.ops.wm.obj_import(filepath=str(Path(obj_path).resolve()), forward_axis="NEGATIVE_Z", up_axis="Y")
obj = bpy.context.selected_objects[0]
bpy.ops.object.shade_smooth()


def tex(nodes, name, colorspace):
    p = Path(f"{prefix}_{name}.png").resolve()
    if not p.exists():
        return None
    n = nodes.new("ShaderNodeTexImage")
    n.image = bpy.data.images.load(str(p))
    n.image.colorspace_settings.name = colorspace
    return n


mat = bpy.data.materials.new("skin")
mat.use_nodes = True  # still needed for new materials in 5.x
nodes, links = mat.node_tree.nodes, mat.node_tree.links
bsdf = nodes["Principled BSDF"]
d = tex(nodes, "diffuse", "sRGB")
if d:
    links.new(d.outputs["Color"], bsdf.inputs["Base Color"])
mg = tex(nodes, "metalgloss", "Non-Color")
if mg:
    sep = nodes.new("ShaderNodeSeparateColor")
    links.new(mg.outputs["Color"], sep.inputs["Color"])
    links.new(sep.outputs["Red"], bsdf.inputs["Metallic"])
    inv = nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    links.new(mg.outputs["Alpha"], inv.inputs[1])
    links.new(inv.outputs[0], bsdf.inputs["Roughness"])
n = tex(nodes, "normal", "Non-Color")
if n:
    nm = nodes.new("ShaderNodeNormalMap")
    links.new(n.outputs["Color"], nm.inputs["Color"])
    links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
e = tex(nodes, "emission", "sRGB")
if e:
    links.new(e.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 4.0
obj.data.materials.clear()
obj.data.materials.append(mat)

# ground: weathered boards stand-in
bpy.ops.mesh.primitive_plane_add(size=6)
ground = bpy.context.active_object
gm = bpy.data.materials.new("ground")
gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.32, 0.27, 0.2, 1)
gm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.85
ground.data.materials.append(gm)

# camera: 3/4 view from slightly above
center = Vector((0, 0, 0.55))
dist = 2.4
cam_loc = center + Vector((math.sin(yaw) * dist, -math.cos(yaw) * dist, 1.25))
bpy.ops.object.camera_add(location=cam_loc)
cam = bpy.context.active_object
cam.rotation_euler = (center - cam_loc).to_track_quat("-Z", "Y").to_euler()
cam.data.lens = 50
scene.camera = cam

world = bpy.data.worlds.new("w")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
if mode == "night":
    bg.inputs["Color"].default_value = (0.04, 0.05, 0.08, 1)
    bg.inputs["Strength"].default_value = 1.0
    bpy.ops.object.light_add(type="SUN", rotation=(math.radians(60), 0, math.radians(30)))
    bpy.context.active_object.data.energy = 0.35
else:
    bg.inputs["Color"].default_value = (0.55, 0.62, 0.75, 1)
    bg.inputs["Strength"].default_value = 0.6
    bpy.ops.object.light_add(type="SUN", rotation=(math.radians(50), math.radians(10), math.radians(-40)))
    bpy.context.active_object.data.energy = 3.5

engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"
if mode == "night" and hasattr(scene.eevee, "use_bloom"):
    scene.eevee.use_bloom = True
scene.view_settings.view_transform = "AgX" if "AgX" in [v.identifier for v in scene.view_settings.bl_rna.properties["view_transform"].enum_items] else "Filmic"
scene.render.resolution_x = 1024
scene.render.resolution_y = 1024
scene.render.filepath = str(Path(out_path).resolve())
bpy.ops.render.render(write_still=True)
print("rendered", out_path)
