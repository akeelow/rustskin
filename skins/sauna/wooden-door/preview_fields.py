"""Sauna Door v2: теневой предпросмотр поля высот переда (.venv, секунды) — проверка формы до Blender.

    .venv/Scripts/python skins/sauna/wooden-door/preview_fields.py [--step 0.25] [--crop x0,x1,y0,y1]
Пишет renders/v2/fields_front.png (рельеф под скользящим светом слева сверху) и fields_front_masks.png.
"""
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fields_door as FD  # noqa: E402

args = sys.argv[1:]
step = float(args[args.index("--step") + 1]) if "--step" in args else 0.25
crop = [float(v) for v in args[args.index("--crop") + 1].split(",")] if "--crop" in args else None
tag = args[args.index("--tag") + 1] if "--tag" in args else "front"
t0 = time.time()
if crop:
    X, Y = np.meshgrid(np.arange(crop[0], crop[1], step), np.arange(crop[2], crop[3], step))
else:
    X, Y = FD.front_grid(step)
f = FD.Front().field(X, Y)
print("field %s in %.1fs" % (X.shape, time.time() - t0))
H = f["h"]
gy, gx = np.gradient(H, step)
n = np.stack([-gx, -gy, np.ones_like(H)], -1)
n /= np.linalg.norm(n, axis=-1, keepdims=True)
L = np.array([-0.55, 0.45, 0.70])
L /= np.linalg.norm(L)
sh = np.clip(n @ L, 0, 1)
img = (np.clip(0.15 + 0.85 * sh, 0, 1) * 255).astype(np.uint8)[::-1]
out = HERE / "renders" / "v2"
out.mkdir(parents=True, exist_ok=True)
Image.fromarray(img).save(out / f"fields_{tag}.png")
dc = DC = np.zeros(H.shape + (3,), np.float32)
dc[..., 0] = f["grain"]
dc[..., 1] = np.clip(f["cavity"] + f["nail"], 0, 1)
dc[..., 2] = np.clip(f["dent"] + f["knot"] + f["putty"] * 0.5, 0, 1)
Image.fromarray((dc[::-1] * 255).astype(np.uint8)).save(out / f"fields_{tag}_masks.png")
cut = FD.drip_cut(X, Y) * (f["mat"] == FD.MAT["glass"])
pane = (f["mat"] == FD.MAT["glass"]).sum()
print("glass texels", int(pane), "see-through %.1f%%" % (100 * (cut > 0.5).sum() / max(pane, 1)))
print("->", out / f"fields_{tag}.png")
