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
    # Bench moved slightly forward and angled so the slats, leaves and rolled towel are fully visible
    sc.add("bench", (0.18, WALL - 0.92, 0), rot_z=174)
    stove = (1.9, WALL - 0.4)
    sc.add("stove", (*stove, 0))
    sc.add("box", (1.35, -1.5, 0), rot_z=55)          # solid 3D box, glowing embers towards stove/center
    # Chair shifted to the left changing area in 3/4 view, unblocking the bench
    sc.add("chair", (-0.72, -1.75, 0), rot_z=-18)
    sc.figure(robe=True, wrap=True, location=(-1.52, -1.28, 0), rot_z=24)
    sc.wall(WALL, width=16.0, height=4.0)
    sc.floor()
    sc.lights(scene, "night")
    sc.stove_glow(stove, 115)
    # Dim warm lamp over the left changing area
    sc.lamp((-0.9, -1.8, 2.6), 65, color=(1.0, 0.8, 0.6), size=1.0)
    # Warm spotlight over the bench deck (eliminates central dark void, brings out wood grain and towel)
    sc.lamp((0.2, -0.2, 2.5), 85, color=(1.0, 0.88, 0.72), size=1.1)
    # Camera: slightly elevated perspective to show bench slats and bucket imprint
    sc.camera(scene, (-0.05, -0.48, 0.88), (0.05, -1.0, 0.35), 4.5, 32, fstop=11)
    sc.render(scene, OUT / "collection.png", samples, (size, size))


if __name__ == "__main__":
    main()
