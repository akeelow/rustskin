"""Проверка high-poly до запекания: серые рендеры сцены bake/v2/highpoly.blend (Cycles), скользящий свет.

  blender -b bake/v2/highpoly.blend -P skins/sauna/wood-storage-box/preview_hp.py -- --shots top,34,corner --out renders/v2/hp
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(name, default=None):
    return args[args.index(name) + 1] if name in args else default


# камера, цель, фокусное, азимут солнца (° от +x к +z), высота солнца — см, оси OBJ (y вверх)
SHOTS = {
    "top": ((0, 150, 0.5), (-1, 0, 0.5), 32, 40, 35),
    "34": ((120, 110, 140), (0, 15, 0), 38, 130, 30),
    "34b": ((-130, 100, -120), (0, 15, 0), 38, -60, 30),
    "corner": ((70, 40, 85), (34, 25, 47), 45, 110, 20),
    "floor": ((25, 75, 35), (0, 2, 0), 35, 60, 40),
    "slot": ((10, 55, 110), (0, 40, 46), 50, 80, 25),
    "rim": ((60, 70, 20), (34, 52, 0), 40, 150, 22),
    "sidex": ((200, 27, 0), (0, 27, 0), 50, 60, 25),
    "sidez": ((0, 27, 200), (0, 27, 0), 50, 30, 25),
}


def main():
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
    sc.cycles.samples = int(opt("--samples", "32"))
    sc.cycles.use_denoising = True
    size = int(opt("--size", "1000"))
    sc.render.resolution_x, sc.render.resolution_y = size, int(size * 0.7)
    sc.view_settings.view_transform = "Standard"
    m = bpy.data.materials.new("grey")
    m.use_nodes = True
    bs = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bs.inputs["Base Color"].default_value = (0.45, 0.45, 0.45, 1)
    bs.inputs["Roughness"].default_value = 0.8
    for o in list(sc.objects):
        if o.type != "MESH":
            continue
        o.rotation_euler = (math.radians(90), 0, 0)      # оси OBJ (y вверх) -> Blender (z вверх): (x, y, z) -> (x, -z, y)
        if not o.name.startswith("hp_"):
            o.hide_render = True
            continue
        o.data.materials.clear()
        o.data.materials.append(m)
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.55, 0.62, 0.75, 1)
    bg.inputs["Strength"].default_value = 0.3
    sc.world = w
    sun_d = bpy.data.lights.new("sun", "SUN")
    sun_d.energy = 4.0
    sun = bpy.data.objects.new("sun", sun_d)
    sc.collection.objects.link(sun)
    cam_d = bpy.data.cameras.new("cam")
    cam_d.clip_start, cam_d.clip_end = 1, 3000
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    out = opt("--out", "renders/v2/hp")
    for name in opt("--shots", "top,34").split(","):
        pos, tgt, lens, az, el = SHOTS[name]
        pos, tgt = (pos[0], -pos[2], pos[1]), (tgt[0], -tgt[2], tgt[1])
        cam.location = pos
        cam.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
        cam_d.lens = lens
        a, e = math.radians(az), math.radians(el)
        d = Vector((math.cos(e) * math.cos(a), -math.cos(e) * math.sin(a), math.sin(e)))
        sun.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        path = (HERE / f"{out}_{name}.png").resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        sc.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        print("->", path, flush=True)


if __name__ == "__main__":
    main()
