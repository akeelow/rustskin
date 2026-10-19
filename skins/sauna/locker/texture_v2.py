"""Sauna Changing Locker v2 (experiment): open-front locker with a warm lamp glow.

The user's reference (a sauna changing room: slatted wall, towels on wooden pegs, warm light
under the shelf) and wish: no doors, look into the compartments, something glowing.
  - the three doors get alpha 0 (Alpha Cutoff 0.5): they are separate objects, double-sided
    with shared UVs, so both sides go; texels shared with the carcass (hinges) are kept;
  - inside, on the back wall: a towel on a wooden peg (middle section) and a birch whisk
    (venik, upper section); the three compartments share one UV patch, so all look alike;
  - emission: a warm amber strip along the front of the shelves (top and middle shelves share
    UVs, so both glow), as if a lamp sits there, and a soft falloff of its light on the back and
    side walls below; nothing else glows.
Everything else is v1.

    .venv/Scripts/python skins/sauna/locker/texture_v2.py
Writes export/Locker_v2_{diffuse,normal,specgloss,emission}.png and uv/v2_views.png.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
sys.path.insert(0, str(HERE))
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("locker_v1", HERE / "texture_v1.py")
v1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v1)
blur, hexc, smooth, SIZE, OUT = v1.blur, v1.hexc, v1.smooth, v1.SIZE, v1.OUT

LINEN = hexc("#BDB4A0")
LINEN2 = hexc("#B3A58C")
STRIPE = hexc("#8E3A30")
PEG = hexc("#6B4D33")
BIRCH_LEAF = hexc("#5C6A39")
BIRCH_LEAF2 = hexc("#76803F")
TWIG = hexc("#6E5A44")
LADLE = hexc("#9A7650")
LAMP = np.array([1.0, 0.55, 0.18])      # warm amber, not neon

COMPARTMENTS = (-58.5, 0.0, 58.5)       # centres (cm); walls at x = +-30, outer walls at +-87
BACK_Z = -28.0                          # inner back wall, faces +z
TOP_SHELF, MID_SHELF = 163.0, 84.0      # undersides at 163 and 81


def coverage(V, T, F, obj, keep):
    sub = [(f, o) for f, o in zip(F, obj) if keep(o)]
    _, _, _, _, cov, _ = v1.raster(V, T, [f for f, _ in sub], [o for _, o in sub])
    return cov


def hanging_towel(x, y, cx, y_top, y_bot, halfw, seed):
    v = (y_top - y) / (y_top - y_bot)
    w = halfw * (0.2 + 0.8 * smooth(-0.05, 0.35, v)) * (1 + 0.05 * np.sin(v * 6 + seed))
    u = (x - cx) / np.maximum(w, 1e-3) * 0.5 + 0.5
    hem = 1 + 0.04 * np.sin(u * 8 + seed) + 0.02 * np.sin(u * 21 + 2 * seed)
    m = (u > 0) & (u < 1) & (v > 0) & (v < hem)
    folds = 0.5 + 0.5 * np.sin(u * 2 * np.pi * (1.4 + 1.8 * smooth(0, 0.5, v)) + seed)
    return m, u, v, folds


def open_doors(m):
    """Alpha 0 on the three doors (texels shared with the carcass, like hinges, kept).
    Returns alpha, carcass coverage, inner back wall mask, cut mask."""
    V, T, F, obj = m["V"], m["T"], m["F"], m["obj"]
    nrm, z = m["nrm"], m["pos"][..., 2]
    doors = coverage(V, T, F, obj, lambda o: "door" in o)
    body = coverage(V, T, F, obj, lambda o: "door" not in o)
    cut = doors & ~body
    back_in = (nrm[..., 2] > 0.5) & (np.abs(z - BACK_Z) < 1.5) & body
    return np.where(cut, 0.0, 1.0), body, back_in, cut


def lamp(m, body, back_in, col):
    """Warm amber strip along the shelf fronts and its light on the walls below."""
    pos, nrm, cov = m["pos"], m["nrm"], m["cov"]
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    # the shelf's top and underside share UVs (the underside alone can't be lit), so the strip is
    # the front 8 cm of the top shelf's faces plus its front edge
    # both shelves share UVs too, so both get the lamp strip and its light below
    on_shelf = (np.abs(y - TOP_SHELF - 1) < 2.5) | (np.abs(y - MID_SHELF + 1.5) < 2.5)
    shelf = body & (np.abs(nrm[..., 1]) > 0.5) & on_shelf & (np.abs(x) < 87)
    edge = body & (nrm[..., 2] > 0.5) & (np.abs(z - 20) < 2.5) & on_shelf
    strip = (shelf & (z > 12)) | edge
    below = np.maximum(smooth(TOP_SHELF - 45, TOP_SHELF, y) * (y < TOP_SHELF) * (y > MID_SHELF),
                       smooth(MID_SHELF - 30, MID_SHELF - 3, y) * (y < MID_SHELF - 3) * (y > 49))
    fall = below * back_in
    side_walls = body & (np.abs(nrm[..., 0]) > 0.5) & (z < 20) & (z > -27)
    fall_side = below * side_walls * 0.6
    emit = np.zeros(cov.shape + (3,))
    emit += (1.0 * strip)[..., None] * LAMP
    emit += (0.22 * fall + 0.18 * fall_side)[..., None] * LAMP * (col / np.maximum(col.max(-1, keepdims=True), 1e-3))
    col = np.where(strip[..., None], np.array([0.95, 0.8, 0.55]), col)

    return emit, col, strip, fall


def main():
    m = v1.build()
    V, T, F, obj = m["V"], m["T"], m["F"], m["obj"]
    pos, nrm, cov = m["pos"], m["nrm"], m["cov"]
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    col, h, spec, gloss = m["col"].copy(), m["h"].copy(), m["spec"].copy(), m["gloss"].copy()
    rng = np.random.default_rng(29)

    alpha, body, back_in, cut = open_doors(m)

    # ---------------------------------------------------------------- props on the back wall
    # the three compartments share one patch of the UV layout (as do the shelves), so the props
    # are drawn in compartment-local x and come out the same in all three
    cxs = np.array(COMPARTMENTS)
    xl = x - cxs[np.argmin(np.abs(x[..., None] - cxs), -1)]
    tm, u, v, folds = hanging_towel(xl, y, 0.0, 152.0, 98.0, 12.0, 0.7)
    tm &= back_in
    tc = LINEN * (0.66 + 0.34 * folds[..., None])
    st = (np.abs(v - 0.8) < 0.03) | (np.abs(v - 0.88) < 0.012)
    tc = np.where(st[..., None], tc * 0.4 + STRIPE * 0.6, tc)
    col = np.where(tm[..., None], tc, col)
    h = np.where(tm, 0.8 + 0.4 * folds, h)
    spec = np.where(tm, 0.03, spec)
    gloss = np.where(tm, 0.08, gloss)
    peg = back_in & (np.hypot(xl, y - 155.0) < 1.4)
    col = np.where(peg[..., None], PEG, col)
    h = np.where(peg, 1.5, h)
    sm, _, _, _ = hanging_towel(xl - 1.2, y + 2.0, 0.0, 152.0, 98.0, 12.0, 0.7)
    shade = blur((sm & back_in & ~tm).astype(np.float64), 4)

    # birch whisk (venik) on a peg in the upper section: handle up, leaves down
    yl = 200.0
    handle = back_in & (np.abs(xl) < 1.3) & (y > yl) & (y < 212)
    leaves_r = np.hypot(xl / 9.0, (y - (yl - 13)) / 15.0)
    leafy = 0.5 + 0.5 * np.sin(xl * 2.3 + np.sin(y * 1.7) * 2) * np.sin(y * 1.9 + xl)
    leaves = back_in & (leaves_r < 1 + 0.12 * (leafy - 0.5)) & (y < yl + 1)
    lc = BIRCH_LEAF * (1 - leafy[..., None]) + BIRCH_LEAF2 * leafy[..., None]
    col = np.where(leaves[..., None], lc * (0.75 + 0.3 * rng.random(cov.shape)[..., None]), col)
    col = np.where(handle[..., None], TWIG, col)
    h = np.where(leaves, 0.9 + 0.5 * leafy, h)
    h = np.where(handle, 0.8, h)
    peg2 = back_in & (np.hypot(xl, y - 213.0) < 1.4)
    col = np.where(peg2[..., None], PEG, col)
    shade = np.maximum(shade, blur(((back_in & (np.hypot((xl - 1.2) / 9.0, (y + 2 - (yl - 13)) / 15.0) < 1)) & ~leaves).astype(np.float64), 4))

    col = col * (1 - 0.35 * shade[..., None] * back_in[..., None])

    emit, col, strip, fall = lamp(m, body, back_in, col)

    # ---------------------------------------------------------------- normal
    nb_new = v1.height_to_normal(h, pos, m["dens"], m["group"], k=1.0)
    n0 = m["n0"]
    nb = np.stack([nb_new[..., 0] + n0[..., 0], nb_new[..., 1] + n0[..., 1], nb_new[..., 2] * n0[..., 2]], -1)
    nb /= np.linalg.norm(nb, axis=-1, keepdims=True)

    out = dict(m, col=col, nb=nb, spec=spec, gloss=gloss, alpha=alpha)
    v1.save(out, "v2")
    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    em = Image.fromarray(q(emit)).resize((1024, 1024), Image.BOX)
    Image.fromarray(np.dstack([np.asarray(em), np.full((1024, 1024), 255, np.uint8)]), "RGBA").save(OUT / "Locker_v2_emission.png")
    print("done; cut texels", int(cut.sum()), "strip", int(strip.sum()), "wall glow", int((fall > 0).sum()))


if __name__ == "__main__":
    main()
