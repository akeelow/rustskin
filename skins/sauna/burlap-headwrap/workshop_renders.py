"""Sauna Towel Wrap: showcase renders for the Steam Workshop page (Blender, Cycles).

Usage (from the repo root):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/burlap-headwrap/workshop_renders.py -- [shot ...] [--samples 128]

Writes skins/sauna/burlap-headwrap/workshop/<shot>.png (1920x1080). Final v1 maps (the original's frayed
edges cut with alpha, Alpha Cutoff 0.79) via ../showcase.py, on a wooden head form and stand.
Shots: hero (3/4, day), front, side, set (with the Sauna Robe by the Sauna Stove, dusk).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import showcase as sc  # noqa: E402

OUT = Path(__file__).resolve().parent / "workshop"
HEAD = 1.58

# camera: (look-at point m, direction from target to eye, distance, lens mm, light preset)
SHOTS = {
    "hero": ((0.0, 0.0, HEAD), (0.75, -1.0, 0.2), 1.05, 50, "day"),
    "front": ((0.0, 0.0, HEAD), (0.0, -1.0, 0.05), 1.0, 50, "day"),
    "side": ((0.0, 0.0, HEAD), (1.0, -0.05, 0.1), 1.0, 50, "day"),
    "set": ((0.3, 0.0, 1.25), (0.35, -1.0, 0.12), 2.6, 45, "dusk"),
}


def render(name, samples):
    target, direction, dist, lens, preset = SHOTS[name]
    scene = sc.fresh()
    if name == "set":
        sc.figure(robe=True, wrap=True, rot_z=-20)
        sc.add("stove", (0.95, 0.35, 0), rot_z=-10)
        sc.stove_glow((0.95, 0.35))
    else:
        sc.figure(robe=False, wrap=True)
    if name == "side":
        sc.wall(-0.9, side=True)
    else:
        sc.wall(0.9)
    sc.floor()
    sc.lights(scene, preset)
    sc.camera(scene, target, direction, dist, lens)
    sc.render(scene, OUT / f"{name}.png", samples)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    samples = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else 128
    names = [a for a in argv if a in SHOTS] or list(SHOTS)
    for name in names:
        render(name, samples)


if __name__ == "__main__":
    main()
