"""In-game test: the lid cut out with alpha, every outer side in its own colour, to see in the Rust client
which inner walls survive (the inner faces and the lid share texels - uv/islands.md).

Outer sides: front (+z, handle slot) red, right (+x) yellow, back (-z) blue, left (-x) green; planks
darker at the bottom (plank 1) to lighter at the top (plank 4) and marked with 1-4 white bars near one
end, so a wall seen from inside tells whose texels it borrows. Inner floor: light grey with a black
arrow pointing to the front and a black dot on the right side. Plank edges and other faces: dark grey.

    .venv/Scripts/python skins/sauna/wood-storage-box/test_openlid.py
Writes export/Box_test_openlid_diffuse.png (1024, RGBA: alpha 0 on the lid). In the editor: Diffuse
Color 255/255/255, Alpha Cutoff 0.50; the other slots stay default.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from concepts import HERE, SIZE, Box, is_lid  # noqa: E402

SIDES = {"front": (205, 45, 45), "right": (225, 200, 40), "back": (50, 85, 215), "left": (45, 170, 65)}


def main():
    b = Box()
    col = np.full((SIZE, SIZE, 3), 60.0)
    shade = 0.55 + 0.15 * b.plank                         # plank 1 (bottom) .. plank 4 (top)
    for name, rgb in SIDES.items():
        m = getattr(b, name)
        col[m] = np.array(rgb) * shade[m][:, None]
        # 1-4 white bars near the plank's left end (seen from outside), 2 cm wide, 3 cm apart
        along = {"front": b.x + 0.34, "right": 0.48 - b.z, "back": 0.34 - b.x, "left": b.z + 0.47}[name]
        k = np.floor((along - 0.06) / 0.05)
        bar = m & (k >= 0) & (k <= b.plank) & (((along - 0.06) % 0.05) < 0.02) \
            & (np.abs(b.y - (np.array([0.067, 0.2, 0.334, 0.467])[b.plank])) < 0.04)
        col[bar] = 255
    floor, x, z = b.inner_floor()
    col[floor] = 200
    shaft = floor & (np.abs(x) < 0.03) & (z > -0.22) & (z < 0.05)
    head = floor & (z >= 0.05) & (z < 0.22) & (np.abs(x) < (0.22 - z) * 0.6)
    dot = floor & (np.hypot(x - 0.22, z) < 0.04)
    col[shaft | head | dot] = 15
    alpha = ~b.face_mask(is_lid)
    out = HERE / "export" / "Box_test_openlid_diffuse.png"
    out.parent.mkdir(exist_ok=True)
    Image.fromarray(np.dstack([col.astype(np.uint8), (alpha * 255).astype(np.uint8)]), "RGBA").save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
