"""Sauna Stove v3: быстрый предпросмотр полей высот (.venv, без Blender) — теневой рельеф и маски.

  .venv/Scripts/python skins/sauna/electric-furnace/preview_v3.py left [--step 0.1] [--crop a0,a1,b0,b1]
Пишет renders/v3/fields/<поле>_relief.png (скользящий свет), <поле>_masks.png (R полость, G волокно, B гвоздь/уголь).
Ориентация: как смотришь на поверхность снаружи.
"""
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fields_v3 as FV  # noqa: E402

OUT = HERE / "renders" / "v3" / "fields"


def shade(H, step, light=(-0.6, 0.55, 0.58), flip_x=False):
    gy, gx = np.gradient(H, step)
    n = np.stack([-gx, -gy, np.ones_like(H)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    l = np.asarray(light, float)
    l /= np.linalg.norm(l)
    s = np.clip((n * l).sum(-1), 0, 1)
    return s


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "left"
    step = float(sys.argv[sys.argv.index("--step") + 1]) if "--step" in sys.argv else FV.STEP
    OUT.mkdir(parents=True, exist_ok=True)
    t = time.time()
    if name == "left":
        f = FV.LeftSide()
        A, B = f.grid(step)
        r = f.field(A, B)
        # вид снаружи слева (камера в −x): вперёд (+a) — вправо, вверх (+b) — вверх
        H = r["h"][::-1, :]
        rr = {k: (v[::-1, :] if hasattr(v, "shape") and v.shape == A.shape else v) for k, v in r.items()}
    else:
        raise SystemExit("unknown field " + name)
    print(f"field {name}: {A.shape}, {time.time() - t:.1f} s, h {np.nanmin(H):.2f}..{np.nanmax(H):.2f}")
    s = shade(H, step)
    img = (np.clip(0.12 + 0.95 * s, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(img).save(OUT / f"{name}_relief.png")
    m = np.stack([rr["cav"], rr["grain"] * 0.5, np.maximum(rr["nail"], rr["char"])], -1)
    Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8)).save(OUT / f"{name}_masks.png")
    print("->", OUT / f"{name}_relief.png")


if __name__ == "__main__":
    main()
