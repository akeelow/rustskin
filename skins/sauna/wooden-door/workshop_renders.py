"""Sauna Door: showcase renders for the Steam Workshop page (Blender, Cycles). Renders, not game shots.

Usage (from the repo root):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/wooden-door/workshop_renders.py -- [shot ...] [--samples 160]
  .venv/Scripts/python skins/sauna/wooden-door/workshop_renders.py --jpg        (PNG -> JPG for upload)

Writes skins/sauna/wooden-door/workshop/<shot>.png (1920x1080) with the final v1.2 maps, wired like the
editor slots by ../showcase.py (Occlusion Scale 0.70, Emission x3 as in tools/blender/viewer.py).
The OBJ is metres, Y up, the front faces +Z; imported Z up, the front then faces -Y, x runs -1.21..0.
Shots: studio (first image), hero, night, back, back_night, window, set (in a wall, with stove and locker).
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "workshop"
CX = -0.605                                   # the door's centre line

# camera: look-at point, direction from target to eye, distance, lens mm, light preset
SHOTS = {
    "studio": ((CX, 0.0, 1.06), (0.55, -1.0, 0.10), 7.4, 50, "studio"),
    "hero": ((CX, 0.0, 1.06), (-0.50, -1.0, 0.16), 7.4, 50, "day"),
    "night": ((CX, 0.0, 1.06), (0.35, -1.0, 0.08), 7.4, 50, "night"),
    "back": ((CX, 0.0, 1.06), (0.55, 1.0, 0.16), 7.4, 50, "day_back"),
    "back_night": ((CX, 0.0, 1.06), (-0.40, 1.0, 0.08), 7.4, 50, "night"),
    "window": ((-0.60, 0.0, 1.50), (0.30, -1.0, 0.05), 1.75, 50, "day"),
    "set": ((-0.55, -0.3, 1.05), (0.25, -1.0, 0.14), 6.2, 35, "dusk"),
}


def render(name, samples):
    import bpy
    sys.path.insert(0, str(HERE.parent))
    import showcase as S
    S.ITEMS["door"] = dict(obj=HERE / "originals/door.hinged.wood.obj", up="y", scale=1.0, lift=0.0,
                           prefix=HERE / "export/Door_v1.2", cutoff=0.0, gloss="specgloss",
                           ao=(HERE / "export/Door_v1.2_occlusion.png", 0.70))
    target, direction, dist, lens, preset = SHOTS[name]
    scene = S.fresh()
    S.add("door")
    S.floor()
    if preset == "studio":
        S.studio(scene, target, scale=1.6, key=85.0, rim=420.0)
    elif preset == "day_back":                 # the same day, the sun brought round to the back
        S.lights(scene, "day")
        sun = next(o for o in bpy.data.objects if o.type == "LIGHT")
        sun.rotation_euler = (math.radians(45), math.radians(8), math.radians(215))
    else:
        S.lights(scene, preset)
    if preset == "night":                      # the window alone lights too little: its glow on the floor
        y = -0.5 if direction[1] < 0 else 0.5
        S.lamp((-0.32, y, 1.35), 1.2, color=(1.0, 0.6, 0.3), size=0.25)
    if name == "set":
        # the door in a lining-board wall of the changing room, the locker and the stove beside it
        # (the wall overlaps the door's edges by 2 cm: no daylight in the gaps)
        S.wall(0.03, width=4.0, height=3.0, x=-3.19)
        S.wall(0.03, width=4.0, height=3.0, x=1.98)
        bpy.ops.mesh.primitive_plane_add(size=1, location=(CX, 0.03, 2.545), rotation=(math.radians(90), 0, 0))
        lintel = bpy.context.active_object
        lintel.scale = (1.26, 0.91, 1)
        lintel.data.materials.append(bpy.data.materials["wall"])
        S.add("locker", (-2.45, -0.38, 0))
        S.add("stove", (0.95, -0.75, 0), rot_z=-18)
        S.stove_glow((0.95, -0.75), energy=60)
        S.lamp((-0.32, -0.5, 1.35), 5.0, color=(1.0, 0.6, 0.3), size=0.25)
    S.camera(scene, target, direction, dist, lens, fstop=8.0)
    S.render(scene, OUT / f"{name}.png", samples)


def to_jpg():
    from PIL import Image
    for name in SHOTS:
        p = OUT / f"{name}.png"
        if p.exists():
            Image.open(p).convert("RGB").save(OUT / f"{name}.jpg", quality=93)
            print("->", name + ".jpg")


def main():
    if "--jpg" in sys.argv:
        return to_jpg()
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    samples = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else 160
    for name in [a for a in argv if a in SHOTS] or list(SHOTS):
        render(name, samples)


if __name__ == "__main__":
    main()
