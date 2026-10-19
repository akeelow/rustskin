"""Sauna Towel v3.2 (neck): compose the export textures from the Blender bake (towel_neck_bake.py).

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
from PIL import Image, ImageDraw, ImageFilter

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
    filt = lambda a, f: np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(f)) > 127
    # closing fills pinholes in the hit mask (v3.1: grey specks), opening drops specks and slivers
    # thinner than ~4 texels; the strip's outline stays
    m = filt(filt(m, ImageFilter.MaxFilter(7)), ImageFilter.MinFilter(7)) & ~small & ~fur & cov
    m = filt(filt(m, ImageFilter.MinFilter(5)), ImageFilter.MaxFilter(5)) & m
    # drop small separate pieces (the flap's second layer by the toggles catches a sliver of towel)
    lab = Image.fromarray((m * 255).astype(np.uint8))
    keep = np.zeros_like(m)
    ys, xs = np.nonzero(m)
    seen = np.zeros_like(m)
    for yy0, xx0 in zip(ys[::97], xs[::97]):
        if seen[yy0, xx0] or not m[yy0, xx0]:
            continue
        tmp = lab.copy()
        ImageDraw.floodfill(tmp, (int(xx0), int(yy0)), 128)
        comp = np.asarray(tmp) == 128
        seen |= comp
        if comp.sum() > 6000:
            keep |= comp
    m = keep
    soft = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8)), np.float64) / 255.0

    nz = np.clip(nrm[..., 2] * 2 - 1, 0, 1)
    side = 0.6 + 0.4 * nz ** 1.5                     # rolled sides turn away from the light
    # dirtier (v3.2): a used towel - greyed and yellowed, blotchy stains, grime in the folds,
    # sweat at the neck, darker lower ends
    rng = np.random.default_rng(43)
    nse = lambda r: v.blur(rng.random((SIZE, SIZE)), r)
    stain = v.smooth(0.52, 0.62, nse(14)) * 0.22 + v.smooth(0.55, 0.65, nse(5)) * 0.12
    neck = v.smooth(0.07, 0.0, g["d_neck"]) * 0.35
    low = v.smooth(1.25, 1.1, g["y"]) * 0.12
    used = np.array([0.86, 0.82, 0.74])
    diffuse = albedo * used * (0.5 + 0.5 * ao[..., None]) * side[..., None]
    diffuse = diffuse * (1 - (stain + low)[..., None]) + np.array([0.42, 0.36, 0.28]) * (stain + low)[..., None]
    diffuse = diffuse * (1 - neck[..., None]) + np.array([0.62, 0.55, 0.40]) * neck[..., None]
    # pad the colour outwards from the strip, so the soft alpha edge shows towel, not grey
    w = m.astype(np.float64)
    for r in (1.5, 4, 10):
        acc = np.stack([v.blur(diffuse[..., i] * w, r) for i in range(3)], -1)
        cnt = v.blur(w, r)[..., None]
        fill = acc / np.maximum(cnt, 1e-3)
        diffuse = np.where((w < 0.5)[..., None] & (cnt > 0.01), fill, diffuse)
        w = np.maximum(w, (cnt[..., 0] > 0.01).astype(np.float64))
    diffuse = np.where(w[..., None] > 0.5, diffuse, np.array([0.7, 0.66, 0.58]))
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
