"""Sauna Sheepskin v1 (Snow Jacket): diffuse, normal, specular/gloss and fuzz mask.

Blocking v0 in game (screenshots/blocking_v0_*): the cut reads, but the leather was pale and
peachy like a suede windbreaker, the original's quilted nylon still showed in the normal with
a plastic sheen, and the wool strip down the front read as a white T-shirt under an open
jacket. v1:
  diffuse   darker, browner, uneven leather; dark seams and creases, lighter only on worn edges
            (elbows, cuffs, pocket flaps); the front placket stays leather, closed by wooden
            toggles on leather loops; wool only on the collar, cuffs and hem, greyed with wear
            and with a shaggy edge;
  normal    the original's big folds (blurred, quilting and stitches gone) + leather grain;
            curly wool on the trims; toggles raised; OpenGL, B = 255;
  specgloss leather low and soft (spec ~0.1, gloss ~0.3, worn spots a bit glossier), wool and
            suede matte;
  fuzz      fuzz mask: wool white, suede grey, leather black.

    .venv/Scripts/python skins/sauna/snow-jacket/texture_v1.py
Writes export/SnowJacket_v1_{diffuse,normal,specgloss,fuzz}.png and uv/v1_views.png.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "tools"))
from blocking import ORIG, OUT, SIZE, blur, hexc, position_map, smooth  # noqa: E402
from uv_zones import load_obj, normal, read_png, render_views  # noqa: E402

SEED = 9
LEATHER = hexc("#654D3B")     # aged sheepskin leather, darker and browner than the v0 palette tone
LEATHER_WORN = hexc("#8E7458")
SEAM = hexc("#3A2A1E")
SUEDE = hexc("#4E3A2A")
WOOL = hexc("#CDBE9E")        # set palette #D6C8AC, greyed with wear
WOOL_DARK = hexc("#8F826B")
WOOD = hexc("#5A3B22")
GRIME = hexc("#2E241B")
TOGGLES_Y = (0.36, 0.49, 0.62, 0.75)


def noise(rng, r):
    return blur(rng.random((SIZE, SIZE)), r)


def grad_normal(h, k):
    """Tangent-space x/y from an image-space height field (OpenGL: image +y is -V)."""
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    return -gx * k, gy * k


def main():
    V, T, F = load_obj(ORIG / "jacket.snow.obj")
    N = [normal(*(V[i] for i in vi)) for vi, _ in F]
    pos, nrm, cov = position_map(V, T, F)
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    ax = np.abs(x)
    rng = np.random.default_rng(SEED)

    bc = np.asarray(Image.open(ORIG / "jacket_snow_red_bc.png").convert("RGB").resize((SIZE, SIZE), Image.BICUBIC), np.float64) / 255.0
    r, g, b = bc[..., 0], bc[..., 1], bc[..., 2]
    lum = bc @ np.array([0.299, 0.587, 0.114])
    sat = bc.max(-1) - bc.min(-1)
    grey = blur(((sat < 0.12) & (lum < 0.35)).astype(np.float64), 1.5) > 0.5
    redness = np.clip((r - np.maximum(g, b)) / np.maximum(r, 1e-3), 0, 1)
    grime = smooth(0.25, 0.7, blur(np.clip(1 - redness / 0.75, 0, 1) * ~grey, 1.2))
    folds = np.clip(blur(r, 1.5) / np.maximum(blur(r, 12), 1e-3), 0.7, 1.3)
    ridge = smooth(1.06, 1.2, folds)                 # raised creases: where leather wears light
    crease = smooth(0.95, 0.82, folds)               # folds' valleys: dirt and dark

    # ---------------------------------------------------------------- regions (3D)
    shag = 0.018 * (noise(rng, 2.5) - 0.5) * 2
    hem = smooth(0.258, 0.24, y + shag)
    cuff = smooth(0.432, 0.448, ax + shag)
    collar = smooth(0.835, 0.85, y + shag) * (ax < 0.17)
    wool = np.clip(np.maximum.reduce([hem, cuff, collar]), 0, 1) * cov
    placket = cov & (ax < 0.032) & (z > 0.06) & (y > 0.26) & (y < 0.83)
    toggle = np.zeros((SIZE, SIZE))
    loop = np.zeros((SIZE, SIZE))
    for ty in TOGGLES_Y:
        dy = np.abs(y - ty)
        toggle = np.maximum(toggle, smooth(0.009, 0.006, dy) * smooth(0.045, 0.04, ax))     # 9 cm peg
        loop = np.maximum(loop, smooth(0.016, 0.012, dy) * smooth(0.06, 0.05, ax) * smooth(0.035, 0.045, ax))
    front = (z > 0.06)
    toggle *= front * cov
    loop *= front * cov * (1 - toggle)
    worn_zone = np.maximum(smooth(0.3, 0.38, ax) * smooth(0.46, 0.4, ax) * grey, 0)   # elbows

    # ---------------------------------------------------------------- diffuse
    tone = 0.86 + 0.26 * noise(rng, 30)
    blotch = 0.92 + 0.12 * noise(rng, 6)
    grain = noise(rng, 0.7)
    lc = LEATHER[None, None, :] * (tone * blotch * (0.95 + 0.1 * grain))[..., None]
    lc = lc * (1 + 0.25 * (folds - 1))[..., None]
    wear = np.clip(0.55 * ridge + 0.5 * cuff * 0 + 0.6 * worn_zone, 0, 1) * (0.6 + 0.4 * noise(rng, 2))
    lc = lc * (1 - 0.5 * wear[..., None]) + LEATHER_WORN * 0.5 * wear[..., None]
    dirt = np.clip(0.7 * crease + 0.8 * grime, 0, 1)
    lc = lc * (1 - 0.45 * dirt[..., None]) + GRIME * 0.45 * dirt[..., None]
    sc = SUEDE[None, None, :] * (tone * (0.88 + 0.24 * noise(rng, 1.2)))[..., None]
    sc = sc * (1 - 0.3 * dirt[..., None]) + GRIME * 0.3 * dirt[..., None]
    col = np.where(grey[..., None], sc, lc)
    # placket edges: dark seam lines along both sides
    seam = cov & front & (np.abs(ax - 0.032) < 0.003) & (y > 0.26) & (y < 0.83)
    col[seam] = SEAM
    col = np.where((loop > 0.3)[..., None], SEAM * 1.3, col)
    wood = WOOD[None, None, :] * (0.8 + 0.4 * blur(rng.random((SIZE, SIZE)), 0.6))[..., None]
    col = col * (1 - toggle[..., None]) + wood * toggle[..., None]

    curls = noise(rng, 1.0)
    clumps = noise(rng, 3.5)
    wc = WOOL[None, None, :] * (0.72 + 0.28 * curls + 0.1 * clumps)[..., None]
    wc = wc * (1 - 0.4 * smooth(0.45, 0.25, clumps)[..., None]) + WOOL_DARK * 0.4 * smooth(0.45, 0.25, clumps)[..., None]
    wc = wc * (1 - 0.35 * grime[..., None])
    col = col * (1 - wool[..., None]) + wc * wool[..., None]
    col[~cov] = LEATHER * 0.8

    # ---------------------------------------------------------------- normal
    n0 = np.asarray(Image.open(ORIG / "jacket_snow_nrm.png").convert("RGB"), np.float64) / 255 * 2 - 1
    fx = blur(n0[..., 0] * 0.5 + 0.5, 3.5) * 2 - 1           # big folds only: quilting/stitches gone
    fy = blur(n0[..., 1] * 0.5 + 0.5, 3.5) * 2 - 1
    lx, ly = grad_normal(noise(rng, 0.8) + 0.5 * noise(rng, 2.0), 1.2)       # leather grain
    wx, wy = grad_normal(curls + 0.6 * clumps, 3.0)                           # wool curls
    tx, ty = grad_normal(blur(toggle, 1.0) * 2.5 + blur(loop, 0.8), 2.0)      # toggles and loops
    nx = fx * (1 - 0.6 * wool) + lx * (1 - wool) + wx * wool + tx
    ny = fy * (1 - 0.6 * wool) + ly * (1 - wool) + wy * wool + ty
    nz = np.sqrt(np.clip(1 - nx ** 2 - ny ** 2, 0.05, 1))
    ln = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2)
    nx, ny = nx / ln, ny / ln

    # ---------------------------------------------------------------- specular / gloss / fuzz
    spec = np.where(grey, 0.05, 0.1 + 0.06 * wear) * (1 - wool) * (1 - toggle) + 0.04 * wool + 0.08 * toggle
    gloss = np.where(grey, 0.15, 0.3 + 0.2 * wear - 0.12 * dirt) * (1 - wool) * (1 - toggle) + 0.06 * wool + 0.35 * toggle
    fuzz = np.clip(wool + 0.45 * grey * (1 - wool), 0, 1)

    OUT.mkdir(exist_ok=True)
    full = np.full((SIZE, SIZE), 255, np.uint8)
    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    Image.fromarray(np.dstack([q(col), full]), "RGBA").save(OUT / "SnowJacket_v1_diffuse.png")
    Image.fromarray(np.dstack([q(nx * 0.5 + 0.5), q(ny * 0.5 + 0.5), full, full]), "RGBA").save(OUT / "SnowJacket_v1_normal.png")
    Image.fromarray(np.dstack([q(spec), q(spec), q(spec), q(gloss)]), "RGBA").save(OUT / "SnowJacket_v1_specgloss.png")
    Image.fromarray(np.dstack([q(fuzz), q(fuzz), q(fuzz), full]), "RGBA").save(OUT / "SnowJacket_v1_fuzz.png")
    render_views(V, T, F, N, HERE / "uv" / "v1_views.png", tex=read_png(OUT / "SnowJacket_v1_diffuse.png"))
    print("done; wool", f"{wool[cov].mean():.1%}", "toggle texels", int((toggle > 0.5).sum()))


if __name__ == "__main__":
    main()
