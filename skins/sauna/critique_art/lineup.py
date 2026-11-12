"""Critique-only: all seven Sauna skins in one row, same neutral light and scale (analysis, not a Workshop picture).

  blender -b -P skins/sauna/critique_art/lineup.py -- [day|night]
Writes skins/sauna/critique_art/lineup_<preset>.png
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import showcase as sc  # noqa: E402


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    preset = argv[0] if argv else "day"
    scene = sc.fresh()
    sc.add("locker", (-3.1, 0.2, 0), rot_z=10)
    sc.add("bench", (-1.2, 0.1, 0), rot_z=100)
    sc.add("chair", (0.35, -0.1, 0), rot_z=-20)
    sc.add("stove", (1.5, 0.1, 0), rot_z=-18)
    sc.add("box", (2.75, -0.35, 0), rot_z=25)
    sc.figure(robe=True, wrap=True, location=(4.0, 0.0, 0), rot_z=-15)
    sc.floor(size=24.0)
    sc.lights(scene, preset)
    sc.camera(scene, (0.3, 0, 0.9), (0.0, -1.0, 0.38), 21.0, 75, fstop=22)
    sc.render(scene, HERE / f"lineup_{preset}.png", 128, (2400, 900))


if __name__ == "__main__":
    main()
