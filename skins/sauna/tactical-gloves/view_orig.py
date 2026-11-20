"""Рендер оригинала Tactical Gloves: голая геометрия (без нормали) и с оригинальными картами, 6 видов.

blender -b -P skins/sauna/tactical-gloves/view_orig.py
Выход: renders/orig_geometry.png, renders/orig_textured.png
"""
import bpy, os, math
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
O = os.path.join(HERE, "originals")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=os.path.join(O, "tactical.gloves.obj"), forward_axis='NEGATIVE_Z', up_axis='Y')
ob = bpy.context.selected_objects[0]
me = ob.data
for p in me.polygons: p.use_smooth = True
# Blender: obj (x,y,z) -> (x,-z,y)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.samples = 32
sc.cycles.device = 'CPU'
sc.render.resolution_x = sc.render.resolution_y = 640
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.6, 0.65, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.6
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", 'SUN')); sc.collection.objects.link(sun)
sun.data.energy = 3.5; sun.rotation_euler = (math.radians(40), math.radians(10), math.radians(30))


def mat(textured):
    m = bpy.data.materials.new("m"); m.use_nodes = True
    nt = m.node_tree; b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    if not textured:
        b.inputs["Base Color"].default_value = (0.5, 0.5, 0.5, 1); b.inputs["Roughness"].default_value = 0.6
        return m
    def tex(name, cs):
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(name if os.path.isabs(name) else os.path.join(O, name))
        t.image.colorspace_settings.name = cs; return t
    bc = tex(textured if isinstance(textured, str) else "TacticalGloves_bc.png", "sRGB")
    nt.links.new(bc.outputs[0], b.inputs["Base Color"])
    if isinstance(textured, str):
        return m
    nm = tex("TacticalGloves_nrm.png", "Non-Color"); nn = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(nm.outputs[0], nn.inputs[1]); nt.links.new(nn.outputs[0], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 0.65
    return m


cen = Vector((0.477, -0.07, 0.30))  # правая (+x) перчатка в осях Blender
views = {
    "+x": Vector((1, 0, 0)), "-x": Vector((-1, 0, 0)), "-y(+z obj)": Vector((0, -1, 0)),
    "+y(-z obj)": Vector((0, 1, 0)), "низ": Vector((0.3, -0.3, -1)), "верх": Vector((0.3, -0.3, 1)),
}
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = 'ORTHO'; cam.data.ortho_scale = 0.26


def shoot(tag):
    files = []
    for k, (name, d) in enumerate(views.items()):
        cam.location = cen + d.normalized() * 0.6
        cam.rotation_euler = (cen - cam.location).to_track_quat('-Z', 'Y' if abs(d.z) < 0.9 else 'Z').to_euler()
        f = os.path.join(HERE, "renders", f"_tmp_{tag}_{k}.png"); sc.render.filepath = f
        bpy.ops.render.render(write_still=True); files.append(f)
    return files

import sys
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
RUNS = (("plan", ARGS[0]),) if ARGS else (("geometry", False), ("textured", True))
for tag, tx in RUNS:
    me.materials.clear(); me.materials.append(mat(tx))
    fs = shoot(tag)
    print("SHEET", tag, ";".join(fs))
