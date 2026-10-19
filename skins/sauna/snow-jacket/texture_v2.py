"""Sauna Robe v2 (Snow Jacket): a short waffle bathrobe painted onto the parka.

The user's reference (references/sauna/robe/waffle_robe_kimono.png): beige waffle-cotton kimono
robe, wrap closure with a shawl collar running diagonally, a tie belt, patch pockets, wide
cuffs. The parka's geometry stays (short, stand collar, zip flap), so the robe is painted:
  - wrap: the top panel's collar band runs from the right side of the neck down across the
    chest to the belt, the under panel's band shows above the crossing (like a gi top);
  - belt: a band round the waist where the parka has its drawstring (y 0.46-0.54), a knot in
    front with two hanging tails;
  - wide turned-up cuffs, a hem seam, two patch pockets;
  - waffle weave in the normal (grid of recessed cells), the bands in plain smoother weave.
Regions are chosen per texel by its 3D point (OBJ space: Y up, +Z front, arms along X).

    .venv/Scripts/python skins/sauna/snow-jacket/texture_v2.py
Writes export/SnowJacket_v2_{diffuse,normal,specgloss,fuzz}.png and uv/v2_views.png.
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

SEED = 13
CLOTH = hexc("#C9B28C")      # beige waffle cotton (reference), a little washed out
BAND = hexc("#C2AA83")       # collar / belt / cuffs: same cloth, denser weave reads a touch darker
SEAM = hexc("#8C775A")
SHADOW = hexc("#5A4A38")
DAMP = hexc("#A8916C")
WAFFLE_PX = 9                # waffle cell, texels (~1.2 cm on the torso)

BELT_Y, BELT_W = 0.50, 0.024                 # belt centre and half width (m)
KNOT = (0.02, 0.50)                          # knot centre (x, y) on the front
NECK_R, NECK_L = (0.10, 0.83), (-0.10, 0.83)  # where the collar bands leave the neck
WAIST_A, WAIST_B = (-0.07, BELT_Y), (0.07, BELT_Y)
HEM_EDGE_X = -0.09                           # top panel's front edge at the hem
COLLAR_W = 0.025                             # collar band half width (m)


def seg_dist(px, py, a, b):
    """Distance from points to segment ab and signed side (+ = left of a->b)."""
    ax_, ay_ = a
    bx_, by_ = b
    dx, dy = bx_ - ax_, by_ - ay_
    t = np.clip(((px - ax_) * dx + (py - ay_) * dy) / (dx * dx + dy * dy), 0, 1)
    d = np.hypot(px - (ax_ + t * dx), py - (ay_ + t * dy))
    side = np.sign(dx * (py - ay_) - dy * (px - ax_))
    return d, side


def line_x(y, a, b):
    """x of the infinite line through a and b at height y."""
    return a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])


def grad_normal(h, k):
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
    front = cov & (z > 0.02) & (ax < 0.22)
    torso = cov & (ax < 0.24)

    bc = np.asarray(Image.open(ORIG / "jacket_snow_red_bc.png").convert("RGB").resize((SIZE, SIZE), Image.BICUBIC), np.float64) / 255.0
    r = bc[..., 0]
    folds = np.clip(blur(r, 2) / np.maximum(blur(r, 14), 1e-3), 0.75, 1.25)

    # ---------------------------------------------------------------- regions
    # top panel collar band: neck (right) -> belt (left), continuing as a narrow facing to the hem
    dA, sA = seg_dist(x, y, NECK_R, WAIST_A)
    dA2, _ = seg_dist(x, y, (WAIST_A[0], BELT_Y - BELT_W), (HEM_EDGE_X, 0.22))
    collar_a = front & (np.minimum(dA, dA2 * 1.4) < COLLAR_W)
    # the under panel shows only above the belt, on the far side of band A (left of it)
    edge_x = line_x(y, NECK_R, WAIST_A)
    under = front & (y > BELT_Y) & (x < edge_x - COLLAR_W)
    dB, _ = seg_dist(x, y, NECK_L, WAIST_B)
    collar_b = under & (dB < COLLAR_W)
    # the V between the two bands, above where they cross: the chest/undershirt in shadow
    vee = under & (x > line_x(y, NECK_L, WAIST_B) + COLLAR_W) & (y > 0.6)
    # stand collar of the parka = the back of the shawl collar
    neckband = cov & (y > 0.825) & (ax < 0.22)
    collar = collar_a | collar_b | neckband
    # top panel's front edge casts a soft shadow onto the under panel / lower front
    edge_shadow = (front & ~collar & (x < edge_x) & (y > BELT_Y)).astype(np.float64)
    edge_shadow = edge_shadow * smooth(COLLAR_W + 0.02, COLLAR_W, np.where(y > BELT_Y, dA, 1))
    lower_edge = front & (y < BELT_Y - BELT_W) & (np.abs(x - line_x(y, (WAIST_A[0], BELT_Y), (HEM_EDGE_X, 0.22)) + COLLAR_W) < 0.004)

    belt_band = torso & (np.abs(y - BELT_Y - 0.004 * np.sin(x * 40)) < BELT_W)
    kx, ky = KNOT
    knot = front & (((x - kx) / 0.032) ** 2 + ((y - ky) / 0.026) ** 2 < 1)
    tails = np.zeros_like(cov)
    for dx0, slope, end in ((-0.012, -0.12, 0.33), (0.014, 0.18, 0.36)):
        cx = kx + dx0 + (ky - y) * slope
        tails |= front & (y < ky) & (y > end) & (np.abs(x - cx) < 0.016)
    belt = belt_band | knot | tails

    cuff = cov & (ax > 0.405)
    cuff_seam = cov & (np.abs(ax - 0.405) < 0.004)
    hem_seam = cov & (np.abs(y - 0.24) < 0.003)
    pocket = np.zeros_like(cov)
    pocket_seam = np.zeros_like(cov)
    for px0 in (-0.12, 0.13):
        inside = front & (np.abs(x - px0) < 0.05) & (y > 0.27) & (y < 0.40)
        rim = front & (np.abs(x - px0) < 0.054) & (y > 0.266) & (y < 0.404) & ~inside
        pocket |= inside
        pocket_seam |= rim
    pocket_seam &= ~belt
    band = (collar | belt | cuff) & ~vee

    # ---------------------------------------------------------------- diffuse
    tone = 0.92 + 0.12 * blur(rng.random((SIZE, SIZE)), 30)
    fleck = 0.95 + 0.08 * blur(rng.random((SIZE, SIZE)), 0.7)
    shade = 1 + 0.35 * (folds - 1)
    col = CLOTH[None, None, :] * (tone * fleck * shade)[..., None]
    col = np.where(band[..., None], BAND[None, None, :] * (tone * fleck * shade)[..., None], col)
    damp = smooth(0.58, 0.68, blur(rng.random((SIZE, SIZE)), 22)) * 0.35
    col = col * (1 - damp[..., None]) + DAMP * damp[..., None]
    col = col * (1 - 0.35 * edge_shadow[..., None]) + SHADOW * 0.35 * edge_shadow[..., None]
    vee_depth = smooth(0.6, 0.78, y) * vee
    col = np.where(vee[..., None], SHADOW * (0.75 + 0.35 * (1 - vee_depth))[..., None], col)
    # seams and belt edges
    belt_edge = belt & ~(blur(belt.astype(np.float64), 1.2) > 0.97)
    band_edge = collar & ~(blur(collar.astype(np.float64), 1.2) > 0.97)
    for m, a in ((belt_edge, 0.55), (band_edge, 0.4), (cuff_seam, 0.6), (hem_seam, 0.5),
                 (pocket_seam, 0.55), (lower_edge, 0.6)):
        col[m] = col[m] * (1 - a) + SEAM * a
    col[~cov] = CLOTH * 0.9

    # ---------------------------------------------------------------- normal
    n0 = np.asarray(Image.open(ORIG / "jacket_snow_nrm.png").convert("RGB"), np.float64) / 255 * 2 - 1
    fx = (blur(n0[..., 0] * 0.5 + 0.5, 5) * 2 - 1) * 0.6        # big folds only: no quilting, no zip flap
    fy = (blur(n0[..., 1] * 0.5 + 0.5, 5) * 2 - 1) * 0.6
    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    u = (xx % WAFFLE_PX) / WAFFLE_PX
    v = (yy % WAFFLE_PX) / WAFFLE_PX
    ridge = np.maximum(smooth(0.3, 0.46, np.abs(u - 0.5)), smooth(0.3, 0.46, np.abs(v - 0.5)))
    weave = blur(rng.random((SIZE, SIZE)), 0.6)
    h = np.where(band, 0.35 * weave, ridge)
    # bands sit proud of the robe; seams sink
    relief = blur(band.astype(np.float64), 1.5) * 1.2 + blur(knot.astype(np.float64), 4) * 3.0
    grooves = (cuff_seam | hem_seam | pocket_seam | lower_edge).astype(np.float64)
    hx, hy = grad_normal(h, 0.9)
    rx, ry = grad_normal(relief - 0.8 * blur(grooves, 0.8), 1.4)
    nx, ny = fx + hx + rx, fy + hy + ry
    nx = np.where(vee, fx * 0.3, nx)
    ny = np.where(vee, fy * 0.3, ny)
    nz = np.sqrt(np.clip(1 - nx ** 2 - ny ** 2, 0.05, 1))
    ln = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2)
    nx, ny = nx / ln, ny / ln

    # ---------------------------------------------------------------- spec / gloss / fuzz
    spec = np.full((SIZE, SIZE), 0.04) + 0.04 * damp
    gloss = np.full((SIZE, SIZE), 0.1) + 0.25 * damp
    fuzz = np.where(band, 0.7, 1.0) * (1 - 0.5 * vee)

    OUT.mkdir(exist_ok=True)
    full = np.full((SIZE, SIZE), 255, np.uint8)
    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    Image.fromarray(np.dstack([q(col), full]), "RGBA").save(OUT / "SnowJacket_v2_diffuse.png")
    Image.fromarray(np.dstack([q(nx * 0.5 + 0.5), q(ny * 0.5 + 0.5), full, full]), "RGBA").save(OUT / "SnowJacket_v2_normal.png")
    Image.fromarray(np.dstack([q(spec), q(spec), q(spec), q(gloss)]), "RGBA").save(OUT / "SnowJacket_v2_specgloss.png")
    Image.fromarray(np.dstack([q(fuzz), q(fuzz), q(fuzz), full]), "RGBA").save(OUT / "SnowJacket_v2_fuzz.png")
    render_views(V, T, F, N, HERE / "uv" / "v2_views.png", tex=read_png(OUT / "SnowJacket_v2_diffuse.png"))
    print("done; collar", int(collar.sum()), "belt", int(belt.sum()), "vee", int(vee.sum()))


if __name__ == "__main__":
    main()
