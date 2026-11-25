"""Серые рендеры только с нормалью (проверка §9.2): модель Facepunch со своими нормалями OBJ (сглаженная, как в Unity),
серый материал, одна карта нормалей, скользящий свет. Ряды: без карты, оригинал, наш v1.2, принятые.
Это рендеры Blender, не кадры из игры.

blender -b -P skins/sauna/tactical-gloves/plan_v2/grey_normal.py
Выход: plan_v2/grey/<карта>_<вид>.png (лист собирает review.py --grey)
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

W = Path(__file__).resolve().parents[1]
OUT = W / "plan_v2" / "grey"
CACHE = Path("C:/Program Files (x86)/Steam/steamapps/workshop/content/252490")
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MAPS = {"none": None, "orig": W / "originals" / "TacticalGloves_nrm.png",
        "v1.2": W / "export" / "SaunaMitts_v1.2_normal.png",
        "3778719714": CACHE / "3778719714" / "_BumpMap0.png", "3816315503": CACHE / "3816315503" / "_BumpMap0.png",
        "3709631672": CACHE / "3709631672" / "_BumpMap0.png"}
if "--maps" in ARGS:
    MAPS = {k: v for k, v in MAPS.items() if k in ARGS[ARGS.index("--maps") + 1].split(",")}
C = Vector((0.472, 0.30, 0.068))
VIEWS = {"back": ((1, 0, 0.05), 0.23), "palm": ((-1, 0, 0.05), 0.23), "thumb": ((0.25, 0.1, -1), 0.23),
         "knuckle": ((1, 0.15, 0.25), 0.11)}


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    try:
        pr = bpy.context.preferences.addons["cycles"].preferences
        pr.compute_device_type = "OPTIX"
        pr.get_devices()
        for d in pr.devices:
            d.use = True
        sc.cycles.device = "GPU"
    except Exception as e:  # noqa: BLE001
        print("CPU:", e)
    sc.cycles.samples = 48
    sc.cycles.use_denoising = True
    sc.render.resolution_x = sc.render.resolution_y = 640
    sc.view_settings.view_transform = "Standard"
    bpy.ops.wm.obj_import(filepath=str(W / "originals" / "tactical.gloves.obj"), forward_axis="Y", up_axis="Z")
    g = bpy.context.selected_objects[0]
    for p in g.data.polygons:
        p.use_smooth = True
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    for p in g.data.polygons:
        p.select = p.center.x < 0
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.delete(type="FACE")
    bpy.ops.object.mode_set(mode="OBJECT")
    print("свои нормали:", g.data.has_custom_normals)

    m = bpy.data.materials.new("grey")
    m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (0.42, 0.42, 0.42, 1)
    b.inputs["Roughness"].default_value = 0.6
    tex = nt.nodes.new("ShaderNodeTexImage")
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tex.outputs["Color"], nm.inputs["Color"])
    g.data.materials.append(m)

    sc.world = bpy.data.worlds.new("w")
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.2, 0.2, 0.22, 1)
    bg.inputs["Strength"].default_value = 0.35
    ld = bpy.data.lights.new("sun", "SUN")
    ld.energy = 4.0
    sun = bpy.data.objects.new("sun", ld)
    sc.collection.objects.link(sun)
    cd = bpy.data.cameras.new("cam")
    cd.type = "ORTHO"
    cam = bpy.data.objects.new("cam", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    OUT.mkdir(parents=True, exist_ok=True)
    for k, p in MAPS.items():
        for lk in list(nm.outputs["Normal"].links):
            nt.links.remove(lk)
        if p is not None:
            img = bpy.data.images.load(str(p))
            img.colorspace_settings.name = "Non-Color"
            tex.image = img
            nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
        for vk, (d, ortho) in VIEWS.items():
            d = Vector(d).normalized()
            cc = C if vk != "knuckle" else Vector((0.495, 0.32, 0.07))
            cam.location = cc + d * 0.6
            cam.rotation_euler = (cc - cam.location).to_track_quat("-Z", "Y").to_euler()
            cd.ortho_scale = ortho
            cd.clip_end = 5
            # скользящий свет: от камеры, повёрнут на 65° вбок и 25° вверх
            q = (cc - cam.location).to_track_quat("-Z", "Y").to_euler()
            sun.rotation_euler = (q.x + math.radians(65), q.y, q.z + math.radians(25))
            sc.render.filepath = str(OUT / f"{k}_{vk}.png")
            bpy.ops.render.render(write_still=True)
            print("->", k, vk)


main()
