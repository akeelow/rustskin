"""Colour blocking v0 for Sauna Sheepskin (Snow Jacket).

The red nylon parka becomes a sheepskin coat thrown on to run out of the steam room into the
snow: tan leather outside, cream wool showing at the collar, the cuffs, the hem and along the
front opening; the grey yoke and elbow panels become darker suede patches; the original's
grime stays as worn, darkened leather. Regions are chosen per texel by its 3D point on the
model (OBJ space: Y up, +Z front, arms out along X), so trims run continuously across seams.

    .venv/Scripts/python skins/sauna/snow-jacket/blocking.py
Writes export/SnowJacket_blocking_v0_{diffuse,specgloss}.png and uv/blocking_v0_views.png.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
from uv_zones import load_obj, normal, read_png, render_views  # noqa: E402

ORIG = HERE / "originals"
OUT = HERE / "export"
SIZE = 1024
SEED = 5


def hexc(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float64) / 255.0


LEATHER = hexc("#8A6646")   # set palette: sheepskin, leather side
SUEDE = hexc("#5E4430")     # darker patches (yoke, elbows)
WOOL = hexc("#D6C8AC")      # set palette: sheepskin, wool side
GRIME = hexc("#3E3024")


def blur(a, r):
    f = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
    return np.asarray(f, np.float64) / 255.0


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def position_map(V, T, F):
    """3D point (OBJ space) and face normal for every texel covered by the UV layout."""
    pos = np.zeros((SIZE, SIZE, 3))
    nrm = np.zeros((SIZE, SIZE, 3))
    cov = np.zeros((SIZE, SIZE), bool)
    Va, Ta = np.array(V), np.array(T)
    for vi, ti in F:
        P = Va[list(vi)]
        uv = Ta[list(ti)] * SIZE
        uv[:, 1] = SIZE - uv[:, 1]
        x0, y0 = np.maximum(np.floor(uv.min(0)).astype(int) - 1, 0)
        x1, y1 = np.minimum(np.ceil(uv.max(0)).astype(int) + 1, SIZE - 1)
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = uv
        area = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)
        if abs(area) < 1e-9:
            continue
        w0 = ((bx - gx) * (cy - gy) - (cx - gx) * (by - gy)) / area
        w1 = ((cx - gx) * (ay - gy) - (ax - gx) * (cy - gy)) / area
        w2 = 1 - w0 - w1
        m = (w0 >= -0.02) & (w1 >= -0.02) & (w2 >= -0.02)
        if not m.any():
            continue
        p3 = w0[..., None] * P[0] + w1[..., None] * P[1] + w2[..., None] * P[2]
        ys, xs = np.nonzero(m)
        pos[ys + y0, xs + x0] = p3[m]
        nrm[ys + y0, xs + x0] = normal(*P)
        cov[ys + y0, xs + x0] = True
    # grow islands a few texels (gutter) so mips don't pull in the padding colour
    for _ in range(4):
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            src = np.roll(np.roll(cov, dy, 0), dx, 1)
            take = ~cov & src
            pos[take] = np.roll(np.roll(pos, dy, 0), dx, 1)[take]
            nrm[take] = np.roll(np.roll(nrm, dy, 0), dx, 1)[take]
            cov |= take
    return pos, nrm, cov


def main():
    V, T, F = load_obj(ORIG / "jacket.snow.obj")
    N = [normal(*(V[i] for i in vi)) for vi, _ in F]
    pos, nrm, cov = position_map(V, T, F)
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    rng = np.random.default_rng(SEED)

    bc = np.asarray(Image.open(ORIG / "jacket_snow_red_bc.png").convert("RGB").resize((SIZE, SIZE), Image.BICUBIC), np.float64) / 255.0
    r, g, b = bc[..., 0], bc[..., 1], bc[..., 2]
    lum = bc @ np.array([0.299, 0.587, 0.114])
    sat = bc.max(-1) - bc.min(-1)

    # original panels: grey nylon (yoke, elbows, hem binding) = low saturation and dark;
    # grime = dark, low-red smudges on the red cloth
    grey = (sat < 0.12) & (lum < 0.35)
    grey = blur(grey.astype(np.float64), 1.5) > 0.5
    redness = np.clip((r - np.maximum(g, b)) / np.maximum(r, 1e-3), 0, 1)
    grime = np.clip(1 - redness / 0.75, 0, 1) * ~grey
    grime = smooth(0.25, 0.7, blur(grime, 1.2))
    # folds: the red channel's local contrast (lit creases of the original)
    folds = np.clip(r / np.maximum(blur(r, 10), 1e-3), 0.7, 1.3)
    folds = 1 + 0.6 * (folds - 1)

    # wool trims, by 3D position (hem at y ~0.2-0.24, cuffs at |x| > 0.44, collar above ~0.83,
    # front opening along x ~ 0 on the chest)
    jag = 0.012 * (blur(rng.random((SIZE, SIZE)), 3) - 0.5) * 2      # shaggy trim edges
    hem = smooth(0.265, 0.245, y + jag)
    cuff = smooth(0.425, 0.445, np.abs(x) + jag)
    collar = smooth(0.84, 0.855, y + jag) * (np.abs(x) < 0.16)
    front = smooth(0.03, 0.018, np.abs(x) + jag * 0.5) * (z > 0.05) * (y > 0.23)
    wool = np.clip(np.maximum.reduce([hem, cuff, collar, front]), 0, 1) * cov

    # leather: tone, folds, scuffs lighter on raised creases, grime darker
    tone = 0.88 + 0.24 * blur(rng.random((SIZE, SIZE)), 25)
    grain = 0.94 + 0.12 * blur(rng.random((SIZE, SIZE)), 0.8)
    leather = LEATHER[None, None, :] * (tone * grain * folds)[..., None]
    scuff = smooth(1.08, 1.25, folds) * 0.25
    leather = leather * (1 + scuff[..., None])
    leather = leather * (1 - 0.55 * grime[..., None]) + GRIME * 0.55 * grime[..., None]
    patch = SUEDE[None, None, :] * (tone * folds)[..., None] * (0.9 + 0.2 * blur(rng.random((SIZE, SIZE)), 1.2))[..., None]
    col = np.where(grey[..., None], patch, leather)

    # wool: cream curls (clumpy noise), a bit greyed with wear
    curls = blur(rng.random((SIZE, SIZE)), 1.2)
    clumps = blur(rng.random((SIZE, SIZE)), 4)
    wc = WOOL[None, None, :] * (0.78 + 0.22 * curls + 0.12 * clumps)[..., None]
    wc = wc * (1 - 0.25 * grime[..., None])
    col = col * (1 - wool[..., None]) + wc * wool[..., None]
    col[~cov] = LEATHER * 0.9

    # specular/gloss (editor slot: RGB spec colour, A gloss): leather a little sheen where worn,
    # suede and wool matte
    spec = np.where(grey, 0.12, 0.2 + 0.1 * scuff) * (1 - wool) + 0.06 * wool
    gloss = np.where(grey, 0.2, 0.42 + 0.3 * scuff - 0.15 * grime) * (1 - wool) + 0.08 * wool

    OUT.mkdir(exist_ok=True)
    rgba = np.dstack([(np.clip(col, 0, 1) * 255).round().astype(np.uint8), np.full((SIZE, SIZE), 255, np.uint8)])
    out = OUT / "SnowJacket_blocking_v0_diffuse.png"
    Image.fromarray(rgba, "RGBA").save(out)
    sg = np.dstack([np.repeat((np.clip(spec, 0, 1) * 255).round()[..., None], 3, -1),
                    (np.clip(gloss, 0, 1) * 255).round()]).astype(np.uint8)
    Image.fromarray(sg, "RGBA").save(OUT / "SnowJacket_blocking_v0_specgloss.png")
    render_views(V, T, F, N, HERE / "uv" / "blocking_v0_views.png", tex=read_png(out))
    print("done; wool share", f"{wool[cov].mean():.1%}", "patch share", f"{grey[cov].mean():.1%}")


if __name__ == "__main__":
    main()
