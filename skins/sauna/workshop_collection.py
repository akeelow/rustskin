"""Sauna set: the picture for the Steam collection (Blender, Cycles), all seven skins in one room.

Usage (from the repo root):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/workshop_collection.py -- [--samples 192] [--size 1024] [--out <png>]

Writes skins/sauna/workshop/collection.png (square). Evening in the scrap-built sauna, seen from above the
door so the floor, not the wall, fills the frame: the Stove glowing at the centre, the Bench along the wall
with its foot end to it, the Stone Box in front of the stove with its stones to the camera, the Changing
Locker on the left, the Chair in front, and the Robe and the Towel Wrap on a tailor's stand by the locker.
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
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else OUT / "collection.png"
    sc.EMISSION = 9.0                                   # brighter rocks and embers: the stove is the light of the picture
    scene = sc.fresh()
    sc.add("locker", (-2.05, WALL - 0.37, 0))
    sc.add("bench", (-0.25, WALL - 0.92, 0), rot_z=174)  # foot end towards the stove
    stove = (1.55, WALL - 0.4)
    sc.add("stove", (*stove, 0))
    sc.add("box", (1.0, -1.3, 0), rot_z=20)            # in front of the stove, open top to the camera
    sc.add("chair", (-0.85, -1.55, 0), rot_z=-30)
    sc.figure(robe=True, wrap=True, location=(-1.6, -0.8, 0), rot_z=35)
    sc.wall(WALL, width=16.0, height=4.0)
    sc.floor()
    sc.lights(scene, "night")
    sc.lamp((stove[0] - 0.25, stove[1] - 1.05, 0.22), 170)    # firebox glow on the floor, not on the stove front
    sc.lamp((1.0, -1.3, 0.9), 12, size=0.4)            # warmth of the embers in the box on its walls
    sc.lamp((-1.2, -1.2, 2.6), 55, color=(1.0, 0.8, 0.6), size=1.0)   # dim lamp over the changing area
    # From above the door: steep enough that the wall above the locker leaves the frame
    sc.camera(scene, (-0.12, -0.3, 0.72), (0.08, -1.0, 0.55), 4.3, 30, fstop=11)
    sc.render(scene, out, samples, (size, size))


if __name__ == "__main__":
    main()
