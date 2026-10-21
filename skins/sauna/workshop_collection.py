"""Sauna set: the picture for the Steam collection (Blender, Cycles), all seven skins in one room.

Usage (from the repo root):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/workshop_collection.py -- [--samples 192] [--size 1024]

Writes skins/sauna/workshop/collection.png (square). Evening in the scrap-built sauna: the Changing Locker
against the lining wall, the Robe and the Towel Wrap on a tailor's stand, the Chair, the Bench along the
wall with its foot end to the Stove, the Stone Box by the stove with its burnt rim towards it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import showcase as sc  # noqa: E402

OUT = Path(__file__).resolve().parent / "workshop"
WALL = 1.12


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    samples = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else 192
    size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 1024
    scene = sc.fresh()
    sc.add("locker", (-2.0, WALL - 0.37, 0))
    sc.add("bench", (0.2, WALL - 0.75, 0), rot_z=180)  # headrest to the left, foot end to the stove
    stove = (1.9, WALL - 0.4)
    sc.add("stove", (*stove, 0))
    sc.add("box", (1.3, -1.5, 0), rot_z=60)          # burnt rim (+x) turned to the stove
    sc.add("chair", (0.05, -1.95, 0), rot_z=10)
    sc.figure(robe=True, wrap=True, location=(-1.35, -1.4, 0), rot_z=20)
    sc.wall(WALL, width=16.0, height=4.0)
    sc.floor()
    sc.lights(scene, "night")
    sc.stove_glow(stove, 110)
    sc.lamp((-0.6, -1.9, 2.6), 70, color=(1.0, 0.8, 0.6), size=1.0)   # a dim warm bulb over the changing area
    sc.camera(scene, (-0.05, -0.55, 0.98), (0.08, -1.0, 0.3), 4.6, 32, fstop=11)
    sc.render(scene, OUT / "collection.png", samples, (size, size))


if __name__ == "__main__":
    main()
