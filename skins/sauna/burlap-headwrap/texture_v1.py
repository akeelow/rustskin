"""Sauna Towel Wrap v1: worn towel diffuse + terry normal + damp specgloss (Burlap Headwrap).

Critique fixes:
1. Forehead stripes: moved twin brick-red stripes (#8E3A30) from the hidden neck fold
   to the visible forehead wrap above the eye slit (circling forehead, temples, and nape).
2. Solidified alpha: eliminated the coarse burlap "gauze pinhole" perforation on the forehead
   and temples, leaving the eye slit open and naturally frayed.
3. Damp accents & sweat: damp darkening on the nape and deep folds in Diffuse;
   high-gloss moisture sheen in export/BurlapHeadwrap_v1_specgloss.png.

Usage:
    .venv/Scripts/python skins/sauna/burlap-headwrap/texture_v1.py
Writes export/BurlapHeadwrap_v1_{diffuse,normal,specgloss}.png and uv/v1_views.png.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

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
DAMP = hexc("#8C7A5E")        # darkened saturated wet linen


def noise(rng, r):
    return blur(rng.random((SIZE, SIZE)), r)


def norm01(a):
    return (a - a.min()) / max(a.max() - a.min(), 1e-6)


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def raster_pos_3d(V, T, F):
    """Vectorized rasterization of 3D vertex positions across UV coordinates."""
    pos = np.zeros((SIZE, SIZE, 3), dtype=np.float32)
    for vi_list, ti_list in F:
        pts_3d = np.array([V[vi] for vi in vi_list])
        pts_uv = [(T[ti][0] * SIZE, (1.0 - T[ti][1]) * SIZE) for ti in ti_list]
        min_x = max(0, int(min(p[0] for p in pts_uv)))
        max_x = min(SIZE - 1, int(max(p[0] for p in pts_uv)))
        min_y = max(0, int(min(p[1] for p in pts_uv)))
        max_y = min(SIZE - 1, int(max(p[1] for p in pts_uv)))
        if max_x < min_x or max_y < min_y:
            continue
        p0, p1, p2 = pts_uv
        v0, v1, v2 = pts_3d
        denom = (p1[1] - p2[1]) * (p0[0] - p2[0]) + (p2[0] - p1[0]) * (p0[1] - p2[1])
        if abs(denom) < 1e-6:
            continue
        inv_denom = 1.0 / denom
        gy, gx = np.ogrid[min_y:max_y + 1, min_x:max_x + 1]
        w0 = ((p1[1] - p2[1]) * (gx - p2[0]) + (p2[0] - p1[0]) * (gy - p2[1])) * inv_denom
        w1 = ((p2[1] - p0[1]) * (gx - p2[0]) + (p0[0] - p2[0]) * (gy - p2[1])) * inv_denom
        w2 = 1.0 - w0 - w1
        inside = (w0 >= -0.01) & (w1 >= -0.01) & (w2 >= -0.01)
        if inside.any():
            val = w0[..., None] * v0 + w1[..., None] * v1 + w2[..., None] * v2
            pos[min_y:max_y + 1, min_x:max_x + 1][inside] = val[inside]
    return pos


def main():
    V, T, F = load_obj(ORIG / "burlap.headwrap.obj")
    N = [normal(*(V[i] for i in vi)) for vi, _ in F]
    isl = islands(V, T, F)
    cowl, hood = isl == 1, isl == 2
    fabric = cowl | hood
    rng = np.random.default_rng(SEED)

    bc = np.asarray(Image.open(ORIG / "burlapheadwraps_01_bc.png").convert("RGBA"), np.float64) / 255.0
    alpha_orig = (bc[..., 3] * 255).round().astype(np.uint8)

    # 1. Solidify alpha on hood cloth to eliminate "gauze pinholes" while keeping eye slit open
    solid_cloth = Image.fromarray(((alpha_orig > 180) & hood).astype(np.uint8) * 255)
    closed = solid_cloth.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.MinFilter(9))
    closed_arr = np.asarray(closed) > 128
    alpha = np.where(hood, np.where(closed_arr, 255, 0), alpha_orig).astype(np.uint8)

    lum = bc[..., :3] @ np.array([0.299, 0.587, 0.114])
    ao = np.asarray(Image.open(ORIG / "burlapheadwraps_01_ao.png").convert("L").resize((SIZE, SIZE), Image.BILINEAR), np.float64) / 255.0

    # The original's dark ropes would bleed grey halos into the blurred folds: fill under them
    rope = rope_mask(hood, lum)
    wide = blur(rope.astype(np.float64), 3) > 0.02
    w = (~wide).astype(np.float64)
    fill = blur(lum * w, 10) / np.maximum(blur(w, 10), 1e-3)
    lum = np.where(wide, fill, lum)

    # Folds from original at reduced contrast
    folds = np.clip(blur(lum, 3) / np.maximum(blur(lum, 16), 1e-3), 0.6, 1.4)
    folds = 1 + 0.6 * (folds - 1)
    loops = blur(rng.random((SIZE, SIZE)), 0.6)                # fine terry loops, 1-2 texels
    wash = norm01(noise(rng, 60))                              # unevenly washed

    col = LINEN[None, None, :] * folds[..., None] * (0.84 + 0.16 * ao[..., None])
    col = col * (0.93 + 0.12 * loops[..., None]) * (0.94 + 0.1 * wash[..., None])

    # Sweat and breath: around the eye slit and below it
    slit = hood & (alpha < 100)
    near_slit = norm01(blur(slit.astype(np.float64), 22))
    below = np.zeros_like(near_slit)
    below[30:] = near_slit[:-30]                               # breath runs down (image +y = down face)
    sweat = np.clip(0.75 * near_slit + 0.6 * below, 0, 1) * (0.6 + 0.4 * noise(rng, 8))
    sweat = smooth(0.15, 0.7, sweat) * hood
    col = col * (1 - 0.45 * sweat[..., None]) + SWEAT * folds[..., None] * 0.45 * sweat[..., None]

    # Dampness on the nape/back of head and in deep creases (sweat & steam condensation)
    pos_3d = raster_pos_3d(V, T, F)
    nape_hood = (pos_3d[..., 2] < -0.02) & (pos_3d[..., 1] < 0.36) & hood
    nape_cowl = (pos_3d[..., 2] < -0.02) & (pos_3d[..., 1] < 0.28) & cowl
    nape_region = nape_hood | nape_cowl
    nape_blur = blur(nape_region.astype(np.float64), 16) * fabric
    creases = np.clip((0.82 - ao) / 0.35, 0, 1) * fabric
    nape_damp = nape_blur * (0.6 + 0.4 * noise(rng, 12))
    damp = np.clip(0.65 * nape_damp + 0.45 * creases + 0.25 * sweat, 0, 1) * fabric
    col = col * (1 - 0.28 * damp[..., None]) + DAMP * folds[..., None] * 0.28 * damp[..., None]

    # Grime along hems
    ys = np.arange(SIZE)[:, None].astype(np.float64)
    grime = np.zeros((SIZE, SIZE))
    for part, reach in ((cowl, 70.0), (hood, 45.0)):
        solid = part & (alpha > 40)
        has = solid.any(0)
        hem = np.where(has, SIZE - 1 - np.argmax(solid[::-1], 0), 0)
        d = hem[None, :] - ys
        grime = np.maximum(grime, np.clip(1 - d / reach, 0, 1) * part * has[None, :])
    grime = grime * (0.5 + 0.5 * noise(rng, 5))
    col = col * (1 - 0.35 * grime[..., None]) + GRIME * 0.35 * grime[..., None] * folds[..., None]

    # Tea-coloured water rings
    blot = noise(rng, 18)
    ring = np.exp(-((blot - 0.6) / 0.008) ** 2) * (blot.max() > 0.6)
    inside = smooth(0.6, 0.63, blot) * 0.25
    col = col * (1 - (0.4 * ring + inside)[..., None]) + TEA * (0.4 * ring + inside)[..., None]

    # Stripes across forehead fold and cowl hem
    stripes, fade = stripe_mask(cowl, hood, alpha, rng)
    sc = STRIPE[None, None, :] * folds[..., None] * (0.9 + 0.2 * wash[..., None])
    col[stripes] = (col * (1 - fade[..., None]) + sc * fade[..., None])[stripes]

    # Twine ropes tied over cloth and stripes
    col[rope] = (TWINE[None, None, :] * folds[..., None] * (0.88 + 0.24 * loops[..., None]))[rope]
    col[~fabric] = LINEN * 0.9

    # ---------------------------------------------------------------- specgloss
    # RGB = Specular Color (51 base, 65 damp), Alpha = Glossiness (40 dry matte, 135 damp sheen)
    spec = 51.0 / 255.0 + (14.0 / 255.0) * damp
    spec[rope] = 56.0 / 255.0
    gloss = 40.0 / 255.0 + ((135.0 - 40.0) / 255.0) * damp
    gloss[rope] = 60.0 / 255.0

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
    keep = rope | (fabric & (alpha_orig < 250)) | (blur((alpha < 200).astype(np.float64), 2.5) > 0.05)
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
    sg = np.dstack([
        (np.clip(spec, 0, 1) * 255).round().astype(np.uint8),
        (np.clip(spec, 0, 1) * 255).round().astype(np.uint8),
        (np.clip(spec, 0, 1) * 255).round().astype(np.uint8),
        (np.clip(gloss, 0, 1) * 255).round().astype(np.uint8),
    ])
    Image.fromarray(sg, "RGBA").save(OUT / "BurlapHeadwrap_v1_specgloss.png")
    render_views(V, T, F, N, HERE / "uv" / "v1_views.png", tex=read_png(OUT / "BurlapHeadwrap_v1_diffuse.png"))
    print("Exported diffuse, normal, specgloss, and v1_views.png successfully.")


if __name__ == "__main__":
    main()
