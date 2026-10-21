"""Sauna Robe: showcase renders for the Steam Workshop page (Blender, Cycles).

Usage (from the repo root):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/snow-jacket/workshop_renders.py -- [shot ...] [--samples 128]

Writes skins/sauna/snow-jacket/workshop/<shot>.png (1920x1080). Final v2.1 maps via ../showcase.py, on a
wooden tailor's stand (no body: the set has no nudity; the inside of the robe shows through the collar).
Shots: hero (3/4, day), front, back, belt (the knot and the waffle up close), set (with the Sauna Towel Wrap
by the Sauna Stove, dusk).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import showcase as sc  # noqa: E402

OUT = Path(__file__).resolve().parent / "workshop"

# camera: (look-at point m, direction from target to eye, distance, lens mm, light preset)
SHOTS = {
    "hero": ((0.0, 0.0, 1.15), (0.75, -1.0, 0.25), 2.3, 50, "day"),
    "front": ((0.0, 0.0, 1.15), (0.0, -1.0, 0.08), 2.2, 50, "day"),
    "back": ((0.0, 0.0, 1.15), (-0.45, 1.0, 0.2), 2.3, 50, "day"),
    "belt": ((0.0, -0.12, 1.1), (0.3, -1.0, 0.15), 0.85, 50, "day"),
    "set": ((0.45, 0.0, 1.0), (0.35, -1.0, 0.2), 3.3, 40, "dusk"),
}


def render(name, samples):
    target, direction, dist, lens, preset = SHOTS[name]
    scene = sc.fresh()
    if name == "set":
        sc.figure(robe=True, wrap=True, rot_z=-20)
        sc.add("stove", (0.95, 0.35, 0), rot_z=-10)
        sc.stove_glow((0.95, 0.35))
    else:
        sc.figure(robe=True, wrap=False)
    sc.wall(-1.2 if name == "back" else 0.9)
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
