"""Sauna Towel Poncho v2: only a towel is left - the rest of the hide is cut away with alpha.

The user's references (references/sauna/poncho/): a towel folded lengthwise, slung round the neck
with both ends hanging down the chest; or one thrown over a shoulder. The hide's geometry stays,
so the towel is a strip of it that keeps alpha 255, everything else alpha 0 (Alpha Cutoff 0.24):
  neck     - a band round the neck edge (7 cm) and two tails down the chest either side of it, ending
             at ~1.08 m with the towel's end stripes and a fringe;
  shoulder - a 20 cm strip over the left shoulder, hanging down the chest and the back, end stripes
             and fringe at both ends.
The strip is rounded in the normal (a folded towel, thicker in the middle), terry loops, darker fold
lines along its edges. The fur tuft and the wooden toggles are cut away too.

    .venv/Scripts/python skins/sauna/hide-poncho/texture_v2.py
Writes export/HidePoncho_v2_{neck,shoulder}_{diffuse,normal}.png and uv/v2_{neck,shoulder}_views.png.
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
SEED = 37
TOWEL = hexc("#D3CBBC")
BRICK = hexc("#8A3A2E")
BRICK_FADED = hexc("#9C5446")
FOLD = hexc("#9E9585")


def towel(g, mask, across, along_end, rng, tag):
    """Paint a folded terry towel on `mask`. across: 0..1 over the strip's width; along_end: metres
    from the strip's free end (for end stripes and fringe), large where there is no end."""
    x, y, z, cov = g["x"], g["y"], g["z"], g["cov"]
    noise = lambda r: blur(rng.random((SIZE, SIZE)), r)
    loops, clumps, wash = noise(0.6), noise(2.0), noise(40)
    round_ = np.sqrt(np.clip(1 - (2 * across - 1) ** 2, 0, 1))
    col = TOWEL * (0.86 + 0.14 * loops + 0.06 * clumps)[..., None] * (0.94 + 0.08 * wash)[..., None]
    col = col * (0.78 + 0.22 * round_)[..., None]                     # the fold sides turn away
    fold = smooth(0.1, 0.0, np.minimum(across, 1 - across))
    col = col * (1 - 0.35 * fold[..., None]) + FOLD * 0.35 * fold[..., None]
    # end stripes, level across the strip, and a fringe at the very end
    wide = np.abs(along_end - 0.075) < 0.018
    narrow = np.abs(along_end - 0.115) < 0.007
    line = np.abs(along_end - 0.035) < 0.004
    st = (wide | narrow | line) & mask
    fade = 0.75 + 0.2 * noise(6)
    sc = np.where(wide[..., None], BRICK, BRICK_FADED) * (0.85 + 0.2 * loops[..., None]) * (0.8 + 0.2 * round_[..., None])
    col[st] = (col * (1 - fade[..., None]) + sc * fade[..., None])[st]
    fringe = (along_end < 0.018) & mask
    run = (x + z) * 1.0
    threads = fringe & (np.sin(run * 2 * np.pi / 0.005 + 3 * noise(1)) > 0.1)
    col[fringe] = col[fringe] * 0.9
    col[threads] = TOWEL * 0.8
    col[~mask] = TOWEL * 0.85

    edge = smooth(0.0, 0.02, np.minimum(across, 1 - across))           # soft alpha at the strip's sides
    a = np.where(mask, 255 * np.where(along_end < 0.004, smooth(0.0, 0.004, along_end), 1.0) * np.maximum(edge, 0.0), 0)
    a = np.where(threads, 255, a)
    alpha = np.clip(a, 0, 255).round().astype(np.uint8)

    h = 22 * round_ + 0.9 * loops + 0.5 * clumps + 1.2 * threads
    hx, hy = v.grad_normal(np.where(mask, h, 0), 0.9)
    nz = np.sqrt(np.clip(1 - hx ** 2 - hy ** 2, 0.05, 1))
    ln = np.sqrt(hx ** 2 + hy ** 2 + nz ** 2)
    q = lambda c: (np.clip(c, 0, 1) * 255).round().astype(np.uint8)
    full = np.full((SIZE, SIZE), 255, np.uint8)
    OUT.mkdir(exist_ok=True)
    Image.fromarray(np.dstack([q(col), alpha]), "RGBA").save(OUT / f"HidePoncho_v2_{tag}_diffuse.png")
    Image.fromarray(np.dstack([q(hx / ln * 0.5 + 0.5), q(hy / ln * 0.5 + 0.5), full, full]), "RGBA").save(OUT / f"HidePoncho_v2_{tag}_normal.png")
    render_views(g["V"], g["T"], g["F"], g["N"], HERE / "uv" / f"v2_{tag}_views.png", tex=read_png(OUT / f"HidePoncho_v2_{tag}_diffuse.png"))
    print(tag, "visible texels", int((alpha > 61).sum()))


def main():
    g = v.geometry()
    x, y, z, cov, small, d_neck = g["x"], g["y"], g["z"], g["cov"], g["small"], g["d_neck"]
    cloth = cov & ~small
    rng = np.random.default_rng(SEED)
    ax = np.abs(x)

    # ---------------------------------------------------------------- round the neck, ends forward
    W = 0.07
    collar = cloth & (d_neck < W)
    tail = cloth & (z > 0.02) & (ax > 0.03) & (ax < 0.145) & (y > 1.08) & (y < 1.44)
    mask = collar | tail
    across = np.where(tail & (y < 1.40), (ax - 0.03) / 0.115, d_neck / W)
    along_end = np.where(tail, y - 1.08, 9.0)
    towel(g, mask, np.clip(across, 0, 1), along_end, rng, "neck")

    # ---------------------------------------------------------------- over the left shoulder
    xs, hw = 0.15, 0.10
    strip = cloth & (np.abs(x - xs) < hw) & (y > 1.04)
    across = (x - (xs - hw)) / (2 * hw)
    along_end = y - 1.04
    towel(g, strip, np.clip(across, 0, 1), along_end, rng, "shoulder")


if __name__ == "__main__":
    main()
