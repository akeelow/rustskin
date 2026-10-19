"""Sauna Towel Poncho v1 (Hide Poncho): variant C taken further - a bath towel thrown over the
shoulders, with a hole for the head.

Variants in game (screenshots/{A,B,C}_*): A (sheepskin) not sauna at all, B (felt) unclear, C reads
as a towel. But C's stripes followed every edge (the front flap's V, the neck, rings round the holes
in the back) like a printed design, and the faded brick went pink, like bacon. A real towel has
straight stripes across it near its ends. v1:
  - two straight bands across the body near the bottom (world height, so they run level round the
    body like a towel's end stripes) in a deep, slightly washed brick, plus a woven border line;
  - fringe only along the bottom edge; neck edge just hemmed;
  - terry: heavier loops in the normal, unevenly washed white, damp patches, a little yellowing at
    the neck; the worn holes in the back get frayed, darker rims;
  - the wooden toggles of the front flap become clothespins holding the towel shut.
Alpha: the fur tuft on the shoulder stays cut away (0); set the Diffuse Color slider to 255.

    .venv/Scripts/python skins/sauna/hide-poncho/texture_v1.py
Writes export/HidePoncho_v1_{diffuse,normal}.png and uv/v1_views.png.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "tools"))
import variants as v  # noqa: E402
from uv_zones import read_png, render_views  # noqa: E402

SIZE, ORIG, OUT = v.SIZE, v.ORIG, v.OUT
blur, smooth, hexc = v.blur, v.smooth, v.hexc
SEED = 31
TOWEL = hexc("#D3CBBC")
BRICK = hexc("#8A3A2E")
BRICK_FADED = hexc("#9C5446")
SWEAT = hexc("#B8A684")
GRIME = hexc("#7A6E5E")
PIN = hexc("#C7A77A")
PIN_DARK = hexc("#6E5236")


def main():
    g = v.geometry()
    V, T, F, N, cov = g["V"], g["T"], g["F"], g["N"], g["cov"]
    outer, inner, small = g["outer"], g["inner"], g["small"]
    x, y, z, d_hem, d_neck = g["x"], g["y"], g["z"], g["d_hem"], g["d_neck"]
    cloth = outer | inner
    rng = np.random.default_rng(SEED)
    noise = lambda r: blur(rng.random((SIZE, SIZE)), r)

    bc = np.asarray(Image.open(ORIG / "hide_poncho_bc.png").convert("RGBA"), np.float64) / 255.0
    lum = bc[..., :3] @ np.array([0.299, 0.587, 0.114])
    folds = np.clip(blur(lum, 4) / np.maximum(blur(lum, 26), 1e-3), 0.75, 1.3)
    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    fur = (xx > 0.78 * SIZE) & (yy > 0.76 * SIZE)

    # the bottom edge vs the other edges (neck, front opening, worn holes): bottom = edge texels low
    # on the body; holes = edge texels well inside the back panel
    run = np.arctan2(x, z) * 0.28                       # metres round the body
    bottom = y < 1.12
    holes = (d_hem < 0.03) & (y > 1.0) & (y < 1.3) & (z < -0.05) & (np.abs(x) < 0.2)

    # ---------------------------------------------------------------- terry
    loops = noise(0.6)
    clumps = noise(2.0)
    wash = noise(40)
    col = TOWEL * (0.88 + 0.14 * loops + 0.06 * clumps)[..., None] * (1 + 0.35 * (folds - 1))[..., None]
    col = col * (0.95 + 0.08 * wash)[..., None]
    damp = smooth(0.58, 0.68, noise(18)) * 0.25
    col = col * (1 - damp[..., None]) + GRIME * damp[..., None] * 0.9
    sweat = smooth(0.08, 0.0, d_neck) * 0.4 * (0.6 + 0.4 * noise(4))
    col = col * (1 - sweat[..., None]) + SWEAT * sweat[..., None]

    # ---------------------------------------------------------------- end stripes: straight, level
    wob = 0.004 * np.sin(run * 30)
    wide = np.abs(y + wob - 1.085) < 0.022
    narrow = np.abs(y + wob - 1.135) < 0.008
    border = np.abs(y + wob - 1.035) < 0.004                   # woven border line nearer the end
    fade = 0.75 + 0.2 * noise(6)
    sc = np.where(wide[..., None], BRICK, BRICK_FADED) * (0.85 + 0.2 * loops[..., None]) * (1 + 0.3 * (folds - 1))[..., None]
    stripe = (wide | narrow | border) & cloth
    col[stripe] = (col * (1 - fade[..., None]) + sc * fade[..., None])[stripe]

    # ---------------------------------------------------------------- edges: fringe at the bottom, hem elsewhere
    fringe = (d_hem < 0.02) & bottom & cloth
    threads = fringe & (np.sin(run * 2 * np.pi / 0.005 + 3 * noise(1)) > 0.1)
    col[fringe] = col[fringe] * 0.92
    col[threads] = TOWEL * 0.8
    hem = ((d_hem < 0.008) & ~bottom & ~holes | (d_neck < 0.01)) & cloth
    col[hem] = col[hem] * 0.9
    fray = holes & cloth
    col[fray] = (col * (1 - 0.3 * smooth(0.03, 0.0, d_hem))[..., None] + GRIME * 0.0)[fray]

    # ---------------------------------------------------------------- clothespins (the toggles)
    pins = small
    stripe_pin = pins & (np.mod(yy, 6) < 1)
    col[pins] = (PIN * (0.85 + 0.25 * noise(1.5))[..., None])[pins]
    col[stripe_pin] = PIN_DARK
    col[~cov & ~fur] = TOWEL * 0.9

    alpha = (bc[..., 3] * 255).round().astype(np.uint8)
    alpha = np.where(fur, 0, alpha).astype(np.uint8)

    # ---------------------------------------------------------------- normal: folds + heavy terry
    n0 = np.asarray(Image.open(ORIG / "hide_poncho_nrm.png").convert("RGB").resize((SIZE, SIZE), Image.BICUBIC), np.float64) / 255 * 2 - 1
    fx = blur(n0[..., 0] * 0.5 + 0.5, 2) * 2 - 1
    fy = blur(n0[..., 1] * 0.5 + 0.5, 2) * 2 - 1
    h = loops + 0.5 * clumps + 0.9 * threads - 0.4 * stripe * 0     # stripes woven flat into the terry
    hx, hy = v.grad_normal(h, 2.6)
    nx, ny = fx + hx, fy + hy
    nx = np.where(small, n0[..., 0], nx)
    ny = np.where(small, n0[..., 1], ny)
    nz = np.sqrt(np.clip(1 - nx ** 2 - ny ** 2, 0.05, 1))
    ln = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2)

    OUT.mkdir(exist_ok=True)
    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    full = np.full((SIZE, SIZE), 255, np.uint8)
    Image.fromarray(np.dstack([q(col), alpha]), "RGBA").save(OUT / "HidePoncho_v1_diffuse.png")
    Image.fromarray(np.dstack([q(nx / ln * 0.5 + 0.5), q(ny / ln * 0.5 + 0.5), full, full]), "RGBA").save(OUT / "HidePoncho_v1_normal.png")
    render_views(V, T, F, N, HERE / "uv" / "v1_views.png", tex=read_png(OUT / "HidePoncho_v1_diffuse.png"))
    print("done; stripe texels", int(stripe.sum()), "fringe", int(fringe.sum()), "holes", int(holes.sum()))


if __name__ == "__main__":
    main()
