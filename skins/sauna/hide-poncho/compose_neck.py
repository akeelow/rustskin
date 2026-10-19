"""Sauna Towel v3.1 (neck): compose the export textures from the Blender bake (towel_neck_bake.py).

v3 in game (screenshots/v3_neck_front.webp) read as a white vest: flat bright white, wide bands,
and stray white flecks by the toggles. v3.1:
  - the towel is wider (13 cm, user wish) and rolled thicker (3 cm) (towel_neck_bake.py);
  - shading: the baked normal's tilt darkens the towel's rolled sides (it reads as a roll, not a
    slab) on top of the baked AO;
  - clean mask: the toggles and the fur cards are never towel; thin slivers and specks (rays that
    caught the towel from the hide's rim or the second layer of the flap) are removed by an
    opening (erode, then grow back) in texture space.

    .venv/Scripts/python skins/sauna/hide-poncho/compose_neck.py
Writes export/HidePoncho_v3_neck_{diffuse,normal}.png and uv/v3_neck_views.png.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "tools"))
import variants as v  # noqa: E402
from uv_zones import read_png, render_views  # noqa: E402

SIZE, OUT = v.SIZE, v.OUT
BAKE = HERE / "bake"


def load(name):
    return np.asarray(Image.open(BAKE / f"towel_neck_{name}.png").convert("RGB"), np.float64) / 255.0


def main():
    g = v.geometry()
    small, cov = g["small"], g["cov"]
    albedo, mask, ao, nrm = load("albedo"), load("mask")[..., 0], load("ao")[..., 0], load("normal")

    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    fur = (xx > 0.78 * SIZE) & (yy > 0.76 * SIZE)
    m = (mask > 0.5) & ~small & ~fur & cov
    # opening: drop specks and slivers thinner than ~4 texels, keep the strip's outline
    im = Image.fromarray((m * 255).astype(np.uint8))
    opened = im.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5))
    m = (np.asarray(opened) > 127) & m
    soft = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8)), np.float64) / 255.0

    nz = np.clip(nrm[..., 2] * 2 - 1, 0, 1)
    side = 0.6 + 0.4 * nz ** 1.5                     # rolled sides turn away from the light
    diffuse = albedo * (0.6 + 0.4 * ao[..., None]) * side[..., None]
    diffuse = np.where(m[..., None], diffuse, np.array([0.8, 0.77, 0.71]))
    alpha = np.clip((soft - 0.35) / 0.3, 0, 1) * 255
    normal = np.where(m[..., None], nrm, np.array([0.5, 0.5, 1.0]))

    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    full = np.full((SIZE, SIZE), 255, np.uint8)
    OUT.mkdir(exist_ok=True)
    Image.fromarray(np.dstack([q(diffuse), alpha.round().astype(np.uint8)]), "RGBA").save(OUT / "HidePoncho_v3_neck_diffuse.png")
    Image.fromarray(np.dstack([q(normal[..., 0]), q(normal[..., 1]), full, full]), "RGBA").save(OUT / "HidePoncho_v3_neck_normal.png")
    render_views(g["V"], g["T"], g["F"], g["N"], HERE / "uv" / "v3_neck_views.png", tex=read_png(OUT / "HidePoncho_v3_neck_diffuse.png"))
    print("done; towel texels", int(m.sum()))


if __name__ == "__main__":
    main()
