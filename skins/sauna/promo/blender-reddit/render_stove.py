"""Кадры процесса для поста в r/blender: high-poly каменки и итог на оригинальной low-poly, один ракурс и свет.

Режимы (--what):
  hp    high-poly из bake_v3.py (все группы PARTS) + серая low-poly под ним (у неё только то, что не перепекалось);
        серая глина, без карт — то, что реально смоделировано
  grey  оригинальная low-poly Rust + только запечённая карта нормалей v3.1, серая глина
  full  оригинальная low-poly + все пять карт v3.1 (как в редакторе)

  blender -b -P skins/sauna/promo/blender-reddit/render_stove.py -- --what hp --shots 34_left,firebox [--size 1600]
Пишет src/stove_<what>_<кадр>.png рядом со скриптом. Ничего не меняет в папке каменки.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
STOVE = HERE.parents[1] / "electric-furnace"
sys.path.insert(0, str(STOVE))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


import view_v3 as V  # noqa: E402  (свои SHOTS и материал «как в редакторе»)

TAG = "v3.1"
MAPS = {k: f"export/ElectricFurnace_{TAG}_{k}.png" for k in ("normal", "metalgloss", "occlusion", "emission")}
MAPS["diffuse"] = f"export/ElectricFurnace_{TAG}_diffuse_cutout.png"
SHOTS = dict(V.SHOTS)
SHOTS["hero"] = ((-1.75, -2.05, 1.55), (0.02, 0, 0.62), 50, -150, 35)


def clay(name, rgb=(0.30, 0.30, 0.30)):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bs.inputs["Base Color"].default_value = (*rgb, 1)
    bs.inputs["Roughness"].default_value = 0.7
    return m


def gpu():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type == "OPTIX"
        sc.cycles.device = "GPU"
    except Exception:  # noqa: BLE001
        pass


def main():
    what = opt("--what", "hp")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    gpu()
    sc.cycles.samples = int(opt("--samples", "128"))
    sc.cycles.use_denoising = True
    size = int(opt("--size", "1600"))
    sc.render.resolution_x, sc.render.resolution_y = size, int(size * 0.75)
    sc.view_settings.view_transform = "Standard"

    if what == "hp":
        import bake_v3 as B
        low = B.load_low()
        low.data.materials.clear()
        low.data.materials.append(clay("low_under", (0.29, 0.29, 0.29)))
        hm = clay("hp")
        n = 0
        for p in B.PARTS:
            for o in B.PARTS[p](low):
                o.data.materials.clear()
                o.data.materials.append(hm)
                o.hide_render = False
                n += len(o.data.polygons)
        print("high-poly faces:", n, flush=True)
    else:
        V.args[:] = ["--mode", "full" if what == "full" else "grey", "--cutoff", "0.99", "--emit", opt("--emit", "4.0")]
        for k, p in MAPS.items():
            if what == "full" or k in ("normal", "diffuse"):
                V.args += ["--" + k, p]
        bpy.ops.wm.obj_import(filepath=str(V.OBJ), forward_axis="NEGATIVE_Z", up_axis="Y")
        ob = bpy.context.selected_objects[0]
        ob.data.materials.clear()
        ob.data.materials.append(V.material("full" if what == "full" else "grey"))

    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, -0.002))
    fl = bpy.context.object
    fl.data.materials.append(clay("floor", (0.30, 0.28, 0.25)))
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.55, 0.62, 0.75, 1)
    bg.inputs["Strength"].default_value = 0.35
    sc.world = w
    sun_d = bpy.data.lights.new("sun", "SUN")
    sun_d.energy = 4.0
    sun_d.angle = math.radians(1.5)
    sun = bpy.data.objects.new("sun", sun_d)
    sc.collection.objects.link(sun)
    cam_d = bpy.data.cameras.new("cam")
    cam_d.clip_start, cam_d.clip_end = 0.01, 100
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    for name in opt("--shots", "34_left").split(","):
        pos, tgt, lens, az, el = SHOTS[name]
        cam.location = pos
        cam.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
        cam_d.lens = lens
        a, e = math.radians(az), math.radians(el)
        d = Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))
        sun.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        path = HERE / "src" / f"stove_{what}_{name}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        sc.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        print("->", path, flush=True)
    if "--blend" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE / "src" / f"stove_{what}.blend"))


if __name__ == "__main__":
    main()
