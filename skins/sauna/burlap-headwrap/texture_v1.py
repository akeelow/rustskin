"""Sauna Towel Wrap v1: worn towel diffuse + terry normal (Burlap Headwrap).

After blocking v0 in game (screenshots/blocking_v0_*): it reads as a striped towel, but too clean
and white for Rust ("items should look dirty and worn"), and the normal still carried the coarse
burlap weave. v1:
  diffuse  washed grey-beige linen, unevenly washed; yellowed by sweat and breath around the eye
           slit and below it; grime along the hems; tea-coloured water rings; stripes and twine
           as in v0; original alpha (frayed edges, Alpha Cutoff 0.79) untouched;
  normal   the original's folds and ropes kept, the burlap weave blurred away and replaced by
           fine terry loops; frayed threads keep the original normal. OpenGL, B = 255.

    .venv/Scripts/python skins/sauna/burlap-headwrap/texture_v1.py
Writes export/BurlapHeadwrap_v1_{diffuse,normal}.png and uv/v1_views.png.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "tools"))
from blocking import (ORIG, OUT, SIZE, STRIPE, TWINE, blur, hexc, islands, rope_mask,  # noqa: E402
                      stripe_mask)
from uv_zones import load_obj, normal, read_png, render_views  # noqa: E402

SEED = 21
LINEN = hexc("#C2B7A2")       # the set's #CFC6B4 after many washes in the bathhouse
SWEAT = hexc("#A8946A")       # yellowing from sweat and breath
GRIME = hexc("#6E6250")       # dirt along the hems
TEA = hexc("#9C8461")         # water/tea ring stains


def noise(rng, r):
    return blur(rng.random((SIZE, SIZE)), r)


def norm01(a):
    return (a - a.min()) / max(a.max() - a.min(), 1e-6)


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def main():
    V, T, F = load_obj(ORIG / "burlap.headwrap.obj")
    N = [normal(*(V[i] for i in vi)) for vi, _ in F]
    isl = islands(V, T, F)
    cowl, hood = isl == 1, isl == 2
    fabric = cowl | hood
    rng = np.random.default_rng(SEED)

    bc = np.asarray(Image.open(ORIG / "burlapheadwraps_01_bc.png").convert("RGBA"), np.float64) / 255.0
    alpha = (bc[..., 3] * 255).round().astype(np.uint8)
    lum = bc[..., :3] @ np.array([0.299, 0.587, 0.114])
    ao = np.asarray(Image.open(ORIG / "burlapheadwraps_01_ao.png").convert("L").resize((SIZE, SIZE), Image.BILINEAR), np.float64) / 255.0

    # the original's dark ropes would bleed grey halos into the blurred folds: fill the
    # luminance under (and around) them from the neighbouring cloth first
    rope = rope_mask(hood, lum)
    wide = blur(rope.astype(np.float64), 3) > 0.02
    w = (~wide).astype(np.float64)
    fill = blur(lum * w, 10) / np.maximum(blur(w, 10), 1e-3)
    lum = np.where(wide, fill, lum)

    # folds from the original at low contrast; the weave itself is dropped (blurred out)
    folds =np.clip(blur(lum, 3) / np.maximum(blur(lum, 16), 1e-3), 0.6, 1.4)
    folds = 1 + 0.6 * (folds - 1)
    loops = blur(rng.random((SIZE, SIZE)), 0.6)                # terry loops, 1-2 texels
    wash = norm01(noise(rng, 60))                              # unevenly washed

    col = LINEN[None, None, :] * folds[..., None] * (0.84 + 0.16 * ao[..., None])
    col = col * (0.93 + 0.12 * loops[..., None]) * (0.94 + 0.1 * wash[..., None])

    # sweat and breath: around the eye slit (the alpha hole inside the hood) and below it
    slit = hood & (alpha < 100)
    near_slit = norm01(blur(slit.astype(np.float64), 22))
    below = np.zeros_like(near_slit)
    below[30:] = near_slit[:-30]                               # breath runs down (image +y = down the face)
    sweat = np.clip(0.75 * near_slit + 0.6 * below, 0, 1) * (0.6 + 0.4 * noise(rng, 8))
    sweat = smooth(0.15, 0.7, sweat) * hood
    col = col * (1 - 0.45 * sweat[..., None]) + SWEAT * folds[..., None] * 0.45 * sweat[..., None]

    # grime along the hems (where the towel touches the neck and the shoulders)
    ys = np.arange(SIZE)[:, None].astype(np.float64)
    grime = np.zeros((SIZE, SIZE))
    for part, reach in ((cowl, 70.0), (hood, 45.0)):
        solid = part & (alpha > 200)
        has = solid.any(0)
        hem = np.where(has, SIZE - 1 - np.argmax(solid[::-1], 0), 0)
        d = hem[None, :] - ys
        grime = np.maximum(grime, np.clip(1 - d / reach, 0, 1) * part * has[None, :])
    grime = grime * (0.5 + 0.5 * noise(rng, 5))
    col = col * (1 - 0.35 * grime[..., None]) + GRIME * 0.35 * grime[..., None] * folds[..., None]

    # tea-coloured water rings: darker rims round lighter blotches
    blot = noise(rng, 18)
    ring = np.exp(-((blot - 0.6) / 0.008) ** 2) * (blot.max() > 0.6)
    inside = smooth(0.6, 0.63, blot) * 0.25
    col = col * (1 - (0.4 * ring + inside)[..., None]) + TEA * (0.4 * ring + inside)[..., None]

    col[rope] = (TWINE[None, None, :] * folds[..., None] * (0.88 + 0.24 * loops[..., None]))[rope]
    stripes, fade = stripe_mask(cowl, hood, alpha, rng)
    sc = STRIPE[None, None, :] * folds[..., None] * (0.9 + 0.2 * wash[..., None])
    col[stripes] = (col * (1 - fade[..., None]) + sc * fade[..., None])[stripes]
    col[~fabric] = LINEN * 0.9

    # ---------------------------------------------------------------- normal
    n0 = np.asarray(Image.open(ORIG / "burlapheadwraps_01_nrm.png").convert("RGB"), np.float64) / 255 * 2 - 1
    fx = np.stack([blur(n0[..., i] * 0.5 + 0.5, 4) * 2 - 1 for i in range(2)], -1)   # folds only
    h = loops * 0.6 + 0.4 * blur(rng.random((SIZE, SIZE)), 1.4)
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    k = 1.6                                                    # terry depth
    tx, ty = -gx * k, gy * k                                   # image +y is -V: flip for OpenGL green
    nx, ny = fx[..., 0] + tx, fx[..., 1] + ty
    # ropes and frayed threads keep the original normal
    keep = rope | (fabric & (alpha < 250)) | (blur((alpha < 200).astype(np.float64), 2.5) > 0.05)
    nx = np.where(keep, n0[..., 0], nx)
    ny = np.where(keep, n0[..., 1], ny)
    nz = np.sqrt(np.clip(1 - nx ** 2 - ny ** 2, 0.05, 1))
    ln = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2)
    nx, ny = nx / ln, ny / ln

    OUT.mkdir(exist_ok=True)
    rgba = np.dstack([(np.clip(col, 0, 1) * 255).round().astype(np.uint8), alpha])
    Image.fromarray(rgba, "RGBA").save(OUT / "BurlapHeadwrap_v1_diffuse.png")
    nrm = np.dstack([(nx * 0.5 + 0.5) * 255, (ny * 0.5 + 0.5) * 255, np.full((SIZE, SIZE), 255), np.full((SIZE, SIZE), 255)])
    Image.fromarray(nrm.round().astype(np.uint8), "RGBA").save(OUT / "BurlapHeadwrap_v1_normal.png")
    render_views(V, T, F, N, HERE / "uv" / "v1_views.png", tex=read_png(OUT / "BurlapHeadwrap_v1_diffuse.png"))
    print("done")


if __name__ == "__main__":
    main()
