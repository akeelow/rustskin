"""Sauna Changing Locker v1: weathered aspen planks with real relief, a towel on a peg, a blank tag.

Blocking v0 in game (screenshots/blocking_v0_*): reads as a wooden locker, but the doors were
pale cream like painted cardboard, the slats were evenly drawn black lines with no relief (the
steel normal still showed), the front frame band got vertical ticks like a ruler, and the plank
middle door was flat orange. v1:
  diffuse   greyer weathered aspen, strong per-board tone, grain streaks along each board, knots,
            nails with rust halos, thin dark-brown gaps, steam darkening top and bottom, water
            stains low down, grime from the original AO; the carcass's front frame (top and bottom
            rails) runs horizontally; the plank door desaturated, grain from its own texture;
            levers turned wood; a washed towel with brick stripes on a wooden peg on the left door
            (set motif), a blank brass tag on the right door - no numbers;
  normal    texture-space height (gaps, bevels, grain, nails, knots, towel folds) -> tangent
            normal, whiteout-blended with the original at half strength (vents and door frames
            stay); OpenGL, B = 255;
  specgloss wood matte, wet bottom a bit glossy, iron and brass as metal.

    .venv/Scripts/python skins/sauna/locker/texture_v1.py
Writes export/Locker_v1_{diffuse,normal,specgloss}.png and uv/v1_views.png.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
sys.path.insert(0, str(HERE))
import importlib.util  # noqa: E402

from blocking import ORIG, OUT, SIZE, blur, hexc, smooth  # noqa: E402
from uv_zones import load_obj, normal, read_png, render_views  # noqa: E402

# the stove's noise helpers (fbm, hash3), loaded by path: both items have a texture_v1.py
_spec = importlib.util.spec_from_file_location("stove_texture_v1", HERE.parent / "electric-furnace" / "texture_v1.py")
_stove = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_stove)
fbm, hash3 = _stove.fbm, _stove.hash3

SEED = 17
SLAT = 7.5                     # cm
DOOR_FACE = hexc("#A8916E")    # weathered aspen, greyer than the v0 cream
CARCASS = hexc("#86694B")
PLANK_DOOR = hexc("#6E5842")
GAP = hexc("#33271D")
KNOT = hexc("#4A3626")
IRON = hexc("#2E2A27")
RUST = hexc("#7C4426")
WOOD_HANDLE = hexc("#5E4430")
LINEN = hexc("#BDB4A0")
STRIPE = hexc("#8E3A30")
BRASS = hexc("#8A7444")

# towel on the left door (object door_a): peg at (x, y), towel hangs below it
PEG = (-55.0, 170.0)
TOWEL = dict(x0=-71.0, x1=-39.0, y_top=168.0, y_bot=104.0)
TAG = (60.0, 166.0, 3.5, 1.8)  # right door: centre x, y, half width, half height (cm)


def object_of_faces(path):
    """Object name for every triangle, in load_obj's order (fans of each polygon)."""
    names, cur = [], None
    for line in open(path, encoding="utf8", errors="replace"):
        if line.startswith("o "):
            cur = line.split()[1]
        elif line.startswith("f "):
            names += [cur] * (len(line.split()) - 3)
    return names


def raster(V, T, F, obj):
    """Per texel: 3D point, face normal, object id, texels per cm, covered."""
    pos = np.zeros((SIZE, SIZE, 3))
    nrm = np.zeros((SIZE, SIZE, 3))
    oid = np.full((SIZE, SIZE), -1, np.int8)
    dens = np.zeros((SIZE, SIZE))
    ids = {n: i for i, n in enumerate(sorted(set(obj)))}
    Va, Ta = np.array(V), np.array(T)
    # the doors are double-sided slabs whose inner face reuses the outer face's UVs: raster the
    # faces looking backwards (-z) first so the outward ones win the shared texels
    order = sorted(range(len(F)), key=lambda f: normal(*Va[list(F[f][0])])[2])
    for f in order:
        vi, ti = F[f]
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
        world = np.linalg.norm(np.cross(P[1] - P[0], P[2] - P[0])) / 2
        ys, xs = np.nonzero(m)
        ys, xs = ys + y0, xs + x0
        pos[ys, xs] = p3[m]
        nrm[ys, xs] = normal(*P)
        oid[ys, xs] = ids[obj[f]]
        dens[ys, xs] = np.sqrt(abs(area) / 2 / max(world, 1e-9))
    cov = oid >= 0
    for _ in range(6):
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            take = ~cov & np.roll(np.roll(cov, dy, 0), dx, 1)
            for a in (pos, nrm, oid, dens):
                a[take] = np.roll(np.roll(a, dy, 0), dx, 1)[take]
            cov |= take
    return pos, nrm, oid, dens, cov, ids


def height_to_normal(h, pos, dens, group, k=1.0):
    """Tangent-space normal (OpenGL) from a texture-space height (cm); no differences across
    UV seams (neighbours far apart in 3D or in another group)."""
    def diff(axis):
        hp, hm = np.roll(h, -1, axis), np.roll(h, 1, axis)
        pp, pm = np.roll(pos, -1, axis), np.roll(pos, 1, axis)
        gp, gm = np.roll(group, -1, axis), np.roll(group, 1, axis)
        texel = 1.0 / np.maximum(dens, 1e-3)
        okp = (np.linalg.norm(pp - pos, axis=-1) < 3 * texel) & (gp == group)
        okm = (np.linalg.norm(pm - pos, axis=-1) < 3 * texel) & (gm == group)
        g = np.where(okp & okm, (hp - hm) / 2, np.where(okp, hp - h, np.where(okm, h - hm, 0)))
        return g * dens * k
    du, dv = diff(1), -diff(0)
    n = np.stack([-du, -dv, np.ones_like(du)], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def build():
    """All v1 maps plus the per-texel context, for v1 itself and for v2."""
    V, T, F = load_obj(ORIG / "locker.obj")
    N = [normal(*(V[i] for i in vi)) for vi, _ in F]
    obj = object_of_faces(ORIG / "locker.obj")
    assert len(obj) == len(F), (len(obj), len(F))
    pos, nrm, oid, dens, cov, ids = raster(V, T, F, obj)
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    an = np.abs(nrm)
    left, middle, right = (oid == ids["locker_door_a_LOD0"]), (oid == ids["locker_door_b_LOD0"]), (oid == ids["locker_door_c_LOD0"])
    body = oid == ids["locker_LOD0"]
    rng = np.random.default_rng(SEED)

    bc = np.asarray(Image.open(ORIG / "locker_bc.png").convert("RGB"), np.float64) / 255.0
    lum = bc @ np.array([0.299, 0.587, 0.114])
    sg0 = np.asarray(Image.open(ORIG / "locker_sg.png").convert("RGBA"), np.float64) / 255.0
    ao = np.asarray(Image.open(ORIG / "locker_ao.png").convert("L").resize((SIZE, SIZE), Image.BILINEAR), np.float64) / 255.0
    grime = np.clip(1 - lum / np.maximum(blur(lum, 12), 1e-3), 0, 0.6)      # dark smudges of the steel

    yy = np.arange(SIZE)[:, None].repeat(SIZE, 1)
    xx = np.arange(SIZE)[None, :].repeat(SIZE, 0)
    small = (yy < 205) & (xx < 1370)
    levers = small & (xx > 1040) & (yy < 185)
    feet = cov & (y < 9)
    plank_door = cov & (blur(sg0[..., 0], 4) < 0.3) & ~small
    iron = cov & (small | feet) & ~levers
    wood = cov & ~iron & ~plank_door & ~levers
    front_face = (nrm[..., 2] > 0.5)
    door = (left | right) & front_face
    rail = body & front_face & ((y > 214) | (y < 19))                # carcass front frame: horizontal

    # ---------------------------------------------------------------- boards
    top = an[..., 1] > 0.7
    across = np.where(top, x, np.where(an[..., 2] >= an[..., 0], x, z))
    along = np.where(top, z, y)
    across = np.where(rail, y, across)
    along = np.where(rail, x, along)
    hb = (across + 300) / SLAT
    board = np.floor(hb)
    fr = hb - board
    side_id = np.where(top, 3, np.where(an[..., 2] >= an[..., 0], 1, 2)) + 10 * rail
    tone = hash3(board, side_id, np.zeros_like(board), SEED)
    gapw = 0.035
    gap = 1 - smooth(0.0, gapw, fr) * smooth(1.0, 1 - gapw, fr)
    gap = np.where(rail, 1 - smooth(0.0, 0.03, np.abs(across - 217.0) / 3 % 1), gap)  # rails: one board
    bevel = smooth(0.0, 0.12, np.minimum(fr, 1 - fr))
    streak = fbm(across * 3.0, along * 0.12, board * 1.7, 4, SEED + 1)
    fine = fbm(across * 14, along * 0.6, board, 3, SEED + 2)
    knots = smooth(0.80, 0.86, fbm(across * 0.9, along * 0.25, board * 3.3, 2, SEED + 3))
    # nails: two per board near top and bottom, plus mid rows on the carcass
    rows = [24.0, 112.0, 200.0]
    nail = np.zeros(cov.shape)
    halo = np.zeros(cov.shape)
    for r in rows:
        for off in (-0.26, 0.26):
            d = np.hypot((fr - 0.5 - off) * SLAT, along - r - (hash3(board, np.full_like(board, r), side_id, SEED + 4) - 0.5) * 3)
            nail = np.maximum(nail, smooth(0.45, 0.3, d))
            halo = np.maximum(halo, smooth(1.4, 0.4, d) * 0.6)
    nail *= ~rail & ~top
    halo *= ~rail & ~top
    steam = smooth(150, 222, y) * 0.22 + smooth(45, 2, y) * 0.3
    water = smooth(0.58, 0.66, fbm(across * 0.15, y * 0.05, z * 0.1, 4, SEED + 5)) * smooth(70, 15, y)

    base = np.where(door[..., None], DOOR_FACE, CARCASS)
    col = base * (0.8 + 0.34 * tone[..., None])
    col = col * (0.82 + 0.3 * streak[..., None]) * (0.95 + 0.08 * fine[..., None])
    col = col * (1 - 0.45 * knots[..., None]) + KNOT * 0.45 * knots[..., None]
    col = col * (1 - steam[..., None]) * (1 - 0.18 * water[..., None])
    col = col * (1 - 0.5 * grime[..., None]) * (0.7 + 0.3 * ao[..., None])
    col = col * (1 - 0.35 * halo[..., None]) + RUST * 0.35 * halo[..., None]
    col = col * (1 - nail[..., None]) + IRON * nail[..., None]
    col = col * (1 - gap[..., None]) + GAP * gap[..., None]

    # plank middle door: its own texture, desaturated and darker
    pd = PLANK_DOOR[None, None, :] * (lum / np.maximum(blur(lum, 40), 1e-3))[..., None]
    pd = pd * (1 - steam[..., None]) * (0.75 + 0.25 * ao[..., None])
    col = np.where(plank_door[..., None], pd, col)

    rust = smooth(0.55, 0.7, blur(rng.random((SIZE, SIZE)), 5))
    ic = (IRON * (1 - rust[..., None]) + RUST * rust[..., None]) * (0.7 + 0.6 * lum[..., None])
    col = np.where(iron[..., None], ic, col)
    lever_grain = 0.85 + 0.3 * blur(rng.random((SIZE, SIZE)), 1.5)
    col = np.where(levers[..., None], WOOD_HANDLE * (lever_grain * (0.6 + 0.6 * lum))[..., None], col)

    # ---------------------------------------------------------------- towel on a peg (left door)
    t = TOWEL
    cx = (t["x0"] + t["x1"]) / 2
    halfw = (t["x1"] - t["x0"]) / 2
    v = (t["y_top"] - y) / (t["y_top"] - t["y_bot"])
    # gathered at the peg, falling open below it
    w = halfw * (0.18 + 0.82 * smooth(-0.05, 0.4, v)) * (1 + 0.04 * np.sin(v * 7))
    u = (x - cx) / np.maximum(w, 1e-3) * 0.5 + 0.5
    hem = 1 + 0.035 * np.sin(u * 9 + 1.3) + 0.02 * np.sin(u * 23)
    towel = left & front_face & (u > 0) & (u < 1) & (v > 0) & (v < hem)
    folds = 0.5 + 0.5 * np.sin(u * 2 * np.pi * (1.6 + 1.6 * smooth(0.0, 0.5, v)) + 0.8 * np.sin(v * 3))
    gather = smooth(0.25, 0.0, v)                                     # bunched at the peg
    tc = LINEN * (0.68 + 0.32 * folds[..., None]) * (0.95 + 0.08 * blur(rng.random((SIZE, SIZE)), 0.7)[..., None])
    stripes = ((np.abs(v - 0.80) < 0.025) | (np.abs(v - 0.87) < 0.012))
    tc = np.where(stripes[..., None], tc * 0.4 + STRIPE * 0.6 * (0.8 + 0.2 * folds[..., None]), tc)
    tc = tc * (1 - 0.18 * smooth(0.6, 1.0, v)[..., None])            # damp, greyer hem
    # soft cast shadow, offset down and to the right of the towel (computed in 3D, not in UV)
    sv = (t["y_top"] - (y + 2.5)) / (t["y_top"] - t["y_bot"])
    sw = halfw * (0.18 + 0.82 * smooth(-0.05, 0.4, sv))
    su = (x - 1.5 - cx) / np.maximum(sw, 1e-3) * 0.5 + 0.5
    sd = np.maximum.reduce([-su, su - 1, -sv, sv - 1.02])
    shade = smooth(0.12, -0.02, sd) * left * front_face * ~towel
    col = col * (1 - 0.38 * shade[..., None])
    col = np.where(towel[..., None], tc, col)
    peg = left & front_face & (np.hypot(x - PEG[0], y - PEG[1]) < 1.3)
    col = np.where(peg[..., None], WOOD_HANDLE * 1.2, col)

    # blank brass tag (no numbers) on the right door, two screws
    tag = right & front_face & (np.abs(x - TAG[0]) < TAG[2]) & (np.abs(y - TAG[1]) < TAG[3])
    screws = tag & ((np.hypot(x - TAG[0] + TAG[2] * 0.7, y - TAG[1]) < 0.35) | (np.hypot(x - TAG[0] - TAG[2] * 0.7, y - TAG[1]) < 0.35))
    col = np.where(tag[..., None], BRASS * (0.8 + 0.3 * blur(rng.random((SIZE, SIZE)), 3))[..., None], col)
    col = np.where(screws[..., None], IRON, col)
    col[~cov] = CARCASS * 0.8

    # ---------------------------------------------------------------- normal
    planks = wood | rail
    h = np.where(planks, -0.35 * gap + 0.12 * bevel + 0.05 * streak + 0.02 * fine - 0.06 * knots + 0.25 * nail, 0.0)
    h += np.where(towel, 0.6 + 0.35 * folds * (1 - gather) + 0.4 * gather * blur(rng.random((SIZE, SIZE)), 2), 0)
    h += np.where(peg, 1.2, 0) + np.where(tag, 0.15, 0) + np.where(screws, 0.1, 0)
    group = (oid.astype(np.int16) * 4 + 2 * towel + plank_door).astype(np.int16)
    n_new = height_to_normal(h, pos, dens, group, k=1.0)
    n0 = np.asarray(Image.open(ORIG / "locker_nrm.png").convert("RGB"), np.float64) / 255 * 2 - 1
    n0[..., 2] = np.sqrt(np.clip(1 - n0[..., 0] ** 2 - n0[..., 1] ** 2, 0, 1))
    keep = np.where(planks & ~towel, 0.45, np.where(towel | peg | tag, 0.0, 1.0))[..., None]
    n0 = n0 * keep + np.array([0, 0, 1.0]) * (1 - keep)
    n0 /= np.linalg.norm(n0, axis=-1, keepdims=True)
    nb = np.stack([n_new[..., 0] + n0[..., 0], n_new[..., 1] + n0[..., 1], n_new[..., 2] * n0[..., 2]], -1)
    nb /= np.linalg.norm(nb, axis=-1, keepdims=True)

    # ---------------------------------------------------------------- spec / gloss
    spec = np.where(iron, 0.35 - 0.2 * rust, 0.06)
    gloss = np.where(iron, 0.42 - 0.25 * rust, 0.2 + 0.25 * water + 0.05 * plank_door)
    spec = np.where(nail > 0.5, 0.3, spec)
    spec = np.where(tag & ~screws, 0.55, spec)
    gloss = np.where(tag & ~screws, 0.5, gloss)
    spec = np.where(towel, 0.03, spec)
    gloss = np.where(towel, 0.08, gloss)

    return dict(V=V, T=T, F=F, N=N, obj=obj, pos=pos, nrm=nrm, oid=oid, dens=dens, cov=cov, ids=ids,
                col=col, h=h, group=group, n0=n0, nb=nb, spec=spec, gloss=gloss, steam=steam,
                planks=planks, front_face=front_face, rng=rng)


def save(m, tag):
    OUT.mkdir(exist_ok=True)
    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    full = np.full((SIZE, SIZE), 255, np.uint8)
    alpha = q(m["alpha"]) if "alpha" in m else full
    nb = m["nb"]
    Image.fromarray(np.dstack([q(m["col"]), alpha]), "RGBA").save(OUT / f"Locker_{tag}_diffuse.png")
    Image.fromarray(np.dstack([q(nb[..., 0] * 0.5 + 0.5), q(nb[..., 1] * 0.5 + 0.5), full, full]), "RGBA").save(OUT / f"Locker_{tag}_normal.png")
    Image.fromarray(np.dstack([q(m["spec"])] * 3 + [q(m["gloss"])]), "RGBA").save(OUT / f"Locker_{tag}_specgloss.png")
    render_views(m["V"], m["T"], m["F"], m["N"], HERE / "uv" / f"{tag}_views.png", tex=read_png(OUT / f"Locker_{tag}_diffuse.png"))


def main():
    save(build(), "v1")
    print("done")


if __name__ == "__main__":
    main()
