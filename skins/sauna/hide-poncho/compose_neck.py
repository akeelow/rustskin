"""Sauna Towel v3.4 (neck): compose the export textures from the Blender bake (towel_neck_bake.py).

v3 in game (screenshots/v3_neck_front.webp) read as a white vest: flat bright white, wide bands,
and stray white flecks by the toggles. v3.1:
  - the towel is wider (13 cm, user wish) and rolled thicker (3 cm) (towel_neck_bake.py);
  - shading: the baked normal's tilt darkens the towel's rolled sides (it reads as a roll, not a
    slab) on top of the baked AO;
  - clean mask: the toggles and the fur cards are never towel; thin slivers and specks (rays that
    caught the towel from the hide's rim or the second layer of the flap) are removed by an
    opening (erode, then grow back) in texture space.

    .venv/Scripts/python skins/sauna/hide-poncho/compose_neck.py
Writes export/HidePoncho_v3_neck_{diffuse,normal,specgloss}.png (2048) and uv/v3_neck_views.png.
v3.3: 2048 bake, front-most layer only on the chest, a matte spec/gloss map.
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

SIZE, OUT = 2048, v.OUT
v.SIZE = SIZE                      # rasterise the hide at the bake's resolution
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
    # front z-buffer: on the chest the hide is two layers by the toggles (the flap over the panel);
    # the towel baked onto both, giving a double edge and grey under-panel patches (v3.2). Keep only
    # the front-most hide surface there.
    x, y, z = g["x"], g["y"], g["z"]
    chest = cov & (z > 0.05) & (y < 1.40)
    bx = np.floor(x / 0.006).astype(np.int64)
    by = np.floor(y / 0.006).astype(np.int64)
    key = (bx + 1000) * 100000 + (by + 1000)
    kc, zc = key[chest], z[chest]
    order = np.argsort(kc)
    ks, zs = kc[order], zc[order]
    starts = np.r_[0, np.nonzero(np.diff(ks))[0] + 1]
    zmax = np.maximum.reduceat(zs, starts)
    idx = np.searchsorted(ks[starts], key[chest])
    front = np.zeros_like(cov)
    front[chest] = zc >= zmax[np.clip(idx, 0, len(zmax) - 1)] - 0.006
    m = m & (~chest | front)
    filt = lambda a, f: np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(f)) > 127
    # closing fills pinholes in the hit mask (v3.1: grey specks), opening drops specks and slivers
    # thinner than ~4 texels; the strip's outline stays
    m = filt(filt(m, ImageFilter.MaxFilter(13)), ImageFilter.MinFilter(13)) & ~small & ~fur & cov
    m = filt(filt(m, ImageFilter.MinFilter(9)), ImageFilter.MaxFilter(9)) & m
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
        if comp.sum() > 24000:
            keep |= comp
    m = keep
    soft = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)), np.float64) / 255.0

    nz = np.clip(nrm[..., 2] * 2 - 1, 0, 1)
    # terry pile (v3.4: v3.3 read as a plain white strip): loops of 2-3 texels in tufts, strong
    # in the normal and visible in the colour
    rng0 = np.random.default_rng(7)
    loops = v.blur(rng0.random((SIZE, SIZE)), 1.0)
    loops = (loops - loops.mean()) / (loops.std() + 1e-6)
    tufts = v.blur(rng0.random((SIZE, SIZE)), 3.0)
    tufts = (tufts - tufts.mean()) / (tufts.std() + 1e-6)
    pile = np.clip(0.5 + 0.18 * loops + 0.12 * tufts, 0, 1)
    side = 0.6 + 0.4 * nz ** 1.5                     # rolled sides turn away from the light
    # dirtier (v3.2): a used towel - greyed and yellowed, blotchy stains, grime in the folds,
    # sweat at the neck, darker lower ends
    rng = np.random.default_rng(43)
    nse = lambda r: v.blur(rng.random((SIZE, SIZE)), r)
    stain = v.smooth(0.52, 0.62, nse(14)) * 0.22 + v.smooth(0.55, 0.65, nse(5)) * 0.12
    neck = v.smooth(0.07, 0.0, g["d_neck"]) * 0.35
    low = v.smooth(1.25, 1.1, g["y"]) * 0.12
    used = np.array([0.86, 0.82, 0.74])
    diffuse = albedo * used * (0.5 + 0.5 * ao[..., None]) * side[..., None] * (0.85 + 0.3 * pile)[..., None]
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
    hx, hy = v.grad_normal(pile, 2.2)
    nb = nrm * 2 - 1
    nb = np.stack([nb[..., 0] + hx, nb[..., 1] + hy, nb[..., 2]], -1)
    nb /= np.linalg.norm(nb, axis=-1, keepdims=True)
    normal = np.where(m[..., None], nb * 0.5 + 0.5, np.array([0.5, 0.5, 1.0]))
    spec = np.where(m, 0.04, 0.0)
    gloss = np.where(m, 0.08, 0.0)

    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    full = np.full((SIZE, SIZE), 255, np.uint8)
    OUT.mkdir(exist_ok=True)
    Image.fromarray(np.dstack([q(diffuse), alpha.round().astype(np.uint8)]), "RGBA").save(OUT / "HidePoncho_v3_neck_diffuse.png")
    Image.fromarray(np.dstack([q(normal[..., 0]), q(normal[..., 1]), full, full]), "RGBA").save(OUT / "HidePoncho_v3_neck_normal.png")
    Image.fromarray(np.dstack([q(spec), q(spec), q(spec), q(gloss)]), "RGBA").save(OUT / "HidePoncho_v3_neck_specgloss.png")
    render_views(g["V"], g["T"], g["F"], g["N"], HERE / "uv" / "v3_neck_views.png", tex=read_png(OUT / "HidePoncho_v3_neck_diffuse.png"))
    print("done; towel texels", int(m.sum()))


if __name__ == "__main__":
    main()
