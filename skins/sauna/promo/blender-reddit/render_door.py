"""Кадры процесса для поста в r/blender: high-poly двери (bake_v2.py) и итог v2.9 на оригинальной low-poly.

Одна сцена, одна камера: сначала рендер high-poly (серая глина, low-poly под ним тоже глина), потом high-poly
скрывается, на low-poly — все карты v2.9 (материал view_v2.py, «как в редакторе»).

  blender -b -P skins/sauna/promo/blender-reddit/render_door.py -- --shots front_34,window [--size 1600] [--night]
Пишет src/door_{hp,full}_<кадр>.png рядом со скриптом. Ничего не меняет в папке двери.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
DOOR = HERE.parents[1] / "wooden-door"
sys.path.insert(0, str(DOOR))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


import view_v2 as V  # noqa: E402

SHOTS = dict(V.SHOTS)


def clay(name, rgb=(0.30, 0.30, 0.30)):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bs.inputs["Base Color"].default_value = (*rgb, 1)
    bs.inputs["Roughness"].default_value = 0.7
    return m


def main():
    import bake_v2 as B
    bpy.ops.wm.read_factory_settings(use_empty=True)
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
    sc.cycles.samples = int(opt("--samples", "128"))
    sc.cycles.use_denoising = True
    sc.cycles.transparent_max_bounces = 16
    size = int(opt("--size", "1600"))
    sc.render.resolution_x, sc.render.resolution_y = size, int(size * 0.75)
    sc.view_settings.view_transform = "Standard"

    low = B.load_low()                                  # см, OBJ-оси (Y вверх)
    hp = []
    for p in B.PARTS:
        hp += B.PARTS[p](low)
    root = bpy.data.objects.new("root", None)           # OBJ (x, y, z) -> мир view_v2 (x, -z, y)
    sc.collection.objects.link(root)
    root.rotation_euler = (math.radians(90), 0, 0)
    hm = clay("hp")
    n = 0
    for o in [low, *hp]:
        o.parent = root
        if o is not low:
            o.data.materials.clear()
            o.data.materials.append(hm)
            o.hide_render = False
            n += len(o.data.polygons)
    print("high-poly faces:", n, flush=True)
    low.hide_render = False
    skin = low.data.materials
    skin.clear()
    skin.append(clay("low_under", (0.29, 0.29, 0.29)))

    bpy.ops.mesh.primitive_plane_add(size=3000, location=(0, 0, 0))
    bpy.context.object.data.materials.append(clay("floor", (0.32, 0.30, 0.27)))
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
    cam_d.clip_start, cam_d.clip_end = 1, 8000
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam

    def shoot(what):
        for name in opt("--shots", "front_34").split(","):
            pos, tgt, lens, az, el = SHOTS[name]
            cam.location = pos
            cam.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
            cam_d.lens = lens
            a, e = math.radians(az), math.radians(el)
            d = Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))
            sun.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
            path = HERE / "src" / f"door_{what}_{name}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            sc.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            print("->", path, flush=True)

    if "--nohp" not in argv:
        shoot("hp")
    for o in hp:
        o.hide_render = True
    V.args[:] = ["--tex", "export/Door_v2.9", "--emit", opt("--emit", "4.0")]
    skin.clear()
    skin.append(V.material("full", 0.5))
    shoot("full")


if __name__ == "__main__":
    main()
