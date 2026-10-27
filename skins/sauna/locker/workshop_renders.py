"""Sauna Changing Locker: showcase renders for the Steam Workshop page (Blender, Cycles).

Usage (from the repo root):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/locker/workshop_renders.py -- [shot ...] [--samples 128]

Writes skins/sauna/locker/workshop/<shot>.png (1920x1080). Final v5.2 maps (side doors cut with alpha, Alpha
Cutoff 0.50; Emission Color 255; original occlusion at 0.75) via ../showcase.py. The OBJ is centimetres,
Y up, +Z front; imported Z up, the front faces -Y.
Shots: studio (dark studio, first on the page), hero (day), night (niche lights and the window), front (straight on, day), door (window, gauges and
map on the middle door, day), set (in the changing room with the Sauna Chair, dusk).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import showcase as sc  # noqa: E402

OUT = Path(__file__).resolve().parent / "workshop"

# camera: (look-at point m, direction from target to eye, distance, lens mm, light preset)
SHOTS = {
    "studio": ((0.0, 0.0, 1.05), (0.55, -1.0, 0.22), 6.2, 40, "studio"),   # first image: dark studio, niches lit
    "hero": ((0.0, 0.0, 1.1), (0.6, -1.0, 0.25), 5.2, 40, "day"),
    "night": ((0.0, 0.0, 1.1), (-0.45, -1.0, 0.2), 5.2, 40, "night"),
    "front": ((0.0, -0.34, 1.12), (0.2, -1.0, 0.08), 5.1, 40, "day"),
    "door": ((0.02, -0.34, 1.72), (0.3, -1.0, 0.05), 2.1, 50, "day"),
    "set": ((0.35, 0.0, 1.0), (0.45, -1.0, 0.2), 5.6, 40, "dusk"),
}


def render(name, samples):
    target, direction, dist, lens, preset = SHOTS[name]
    scene = sc.fresh()
    sc.add("locker")
    if name == "set":
        sc.wall(0.42)
        sc.add("chair", (1.35, -0.75, 0), rot_z=-35)
        sc.lamp((1.6, -1.6, 1.4), 60)              # the stove's glow from the steam room door
    if preset == "studio":
        sc.floor(2.6)
        sc.studio(scene, target, scale=2.0, key=240, rim=300)
    else:
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
