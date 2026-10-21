"""Sauna Stone Box v1: final maps from the bake (bake_box.py) and the v0 palette (blocking.py).

Walls: as blocking v0 (aspen, two hoops, smoke on the stove side, greasy handle slots), with the hoops and
rivets taken from the bake's id map so colour and relief match; original normal map elsewhere.
Floor (inner, its own texels): dark basalt stones (v0's were pale "eggs" in the sun), charcoal between
them with ash flecks, the steel tray's rim, the wooden floor's margin; baked normal and AO.
Glow: the embers - charcoal deep between the stones (low baked AO), hottest mid-pile, dying out
towards the tray. v1.1: the rim too - the survivor shovels the coals in over the rim on the stove side
(+x), the shovel knocks on it: that rim and the corners next to it are charred, smouldering in the
crackle; on the other rims only a few scorch spots where a coal fell. The handle slots don't glow.
The lid is cut with alpha (Alpha Cutoff 0.50).

    .venv/Scripts/python skins/sauna/wood-storage-box/texture_v1.py
Inputs: bake/{normal,ao,id}.png, originals/Wooden_Box_{nrm.png}, wooden_box_ao.png.
Outputs: export/Box_v1.1_{diffuse (RGBA), normal, specgloss (512), occlusion, emission}.png (1024).
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import blocking  # noqa: E402
from concepts import (EMBER_CORE, EMBER_EDGE, IRON, ORIG, RUST, SIZE, SOOT, Box, blur, hash1, hexc,  # noqa: E402
                      is_lid, smooth)

BAKE = HERE / "bake"
OUT = HERE / "export"
VERSION = "v1.1"
IDS = {"base": 0, "stone": 1, "coal": 2, "tray": 3, "hoop": 4, "rivet": 5}    # bake_box.IDS
BASALT = hexc("#2E2F32")
BASALT_WARM = hexc("#3A3430")
CHARCOAL = hexc("#141211")
ASH = hexc("#7E7872")
FLOOR_WOOD = hexc("#3B2E25")
CHAR = hexc("#1B1613")
SCORCH = hexc("#5A3A24")
RIM_Y = 0.533                 # wall tops
CRACKLE = 0.022               # charred-wood crackle cell, m (1.1 cm = 2-3 texels on the walls: blocky)


def load(path, mode="RGB", size=SIZE, resample=Image.LANCZOS):
    im = Image.open(path).convert(mode)
    if im.size != (size, size):
        im = im.resize((size, size), resample)
    return np.asarray(im, np.float64) / 255.0


def crackle(u, v, s, seed):
    """Charred-wood alligator crackle on 2D coordinates (m): 1 on the cracks, 0 in the cells' middle."""
    gu, gv = np.floor(u / s), np.floor(v / s)
    d1 = np.full(u.shape, 9.0)
    d2 = np.full(u.shape, 9.0)
    for du in (-1, 0, 1):
        for dv in (-1, 0, 1):
            cu, cv = gu + du, gv + dv
            k = cu * 7919 + cv * 104729
            px = (cu + 0.15 + 0.7 * hash1(k, seed)) * s
            py = (cv + 0.15 + 0.7 * hash1(k, seed + 1)) * s * 1.6        # cells stretched across the grain
            d = np.hypot(u - px, (v - py) / 1.6)
            d2 = np.where(d < d1, d1, np.minimum(d2, d))
            d1 = np.minimum(d1, d)
    return np.clip(1 - (d2 - d1) / (0.12 * s), 0, 1)


def rim(b, col, spec, gloss):
    """Charred, smouldering rim on the stove side (+x) and the corners next to it; scorch spots elsewhere.
    Outer faces near the top (the inner ones wear them in game) and the wall tops. Returns the heat too."""
    x, y, z = b.x, b.y, b.z
    top = (y > 0.525) & (b.nrm[..., 1] > 0.7) & ~b.lid
    # side of every texel by the nearest wall (the tops face up, so the normal can't tell)
    dist = np.stack([0.34 - x, z + 0.46, x + 0.36, 0.47 - z])               # right, back, left, front
    side = np.where(b.walls, np.select([b.right, b.back, b.left, b.front], [0, 1, 2, 3], 0), dist.argmin(0))
    run = np.select([side == 0, side == 1, side == 2, side == 3],
                    [0.48 - z, 0.34 - x, z + 0.47, x + 0.36], 0)          # along the wall, from its +x/front end
    from_stove = np.select([side == 0, side == 1, side == 2, side == 3],
                           [0 * x, 0.34 - x, 9 + 0 * x, 0.34 - x], 9)       # metres from the stove-side rim
    w = np.where(side == 0, 1.0, smooth(0.22, 0.0, from_stove))
    w = w * (0.75 + 0.25 * b.noise)
    seg = np.floor((run + side * 3.1) / 0.09)
    spot_c = (seg + 0.5) * 0.09 - side * 3.1
    spot = (hash1(seg, 31) > 0.82) * smooth(0.035, 0.01, np.abs(run - spot_c))
    w = np.maximum(w, spot * 0.7)
    h = RIM_Y - y                                                           # depth below the rim
    depth = 0.012 + 0.045 * w * (0.6 + 0.4 * b.blotch * 0.3 + 0.4 * b.noise)
    jag = 0.006 * b.blotch                                                  # wide waves, not texel noise (stair-steps)
    face = b.walls & (h < 0.1)
    a = np.where(top, smooth(0.05, 0.3, w), face * smooth(depth + 0.008, depth - 0.008, h + jag) * (w > 0.05))
    a = np.where(face | top, blur(a, 1.0), a)
    v = np.where(top, np.select([side == 0, side == 2], [x, x], z), y)
    cr = crackle(run, v, CRACKLE, 41)
    # colour: charred black, a little grey ash on the crackle cells, a brown scorch at the zone's edge
    char = CHAR * (0.85 + 0.25 * (1 - cr[..., None])) * (0.9 + 0.2 * b.noise[..., None])
    char = char * (1 - 0.6 * cr[..., None])
    scorch = smooth(0.05, 0.45, a) * (1 - smooth(0.45, 0.85, a))
    col = col * (1 - 0.65 * scorch[..., None]) + SCORCH * 0.65 * scorch[..., None]
    col = np.where((a > 0.45)[..., None], char, col * (1 - 0.6 * a[..., None]) + CHAR * 0.6 * a[..., None])
    spec = np.where(a > 0.45, 0.03, spec)
    gloss = np.where(a > 0.45, 0.07, gloss)
    # smoulder: in the cracks, deep in the charred zone, hottest at the very top on the stove side
    near_top = np.where(top, 1.0, smooth(depth, 0.0, h))
    heat = cr * smooth(0.5, 0.95, a) * near_top * (0.3 + 0.7 * w) * smooth(0.3, 0.7, b.noise + 0.2 * b.blotch * 0.3)
    return col, spec, gloss, np.clip(heat * 0.75, 0, 1)


def main():
    b = Box()
    col, spec, gloss = blocking.walls(b)
    nb = load(BAKE / "normal.png") * 2 - 1
    ao = load(BAKE / "ao.png", "L")
    idm = np.asarray(Image.open(BAKE / "id.png").convert("RGB").resize((SIZE, SIZE), Image.NEAREST), np.int32)
    mid = np.clip(idm[..., 0] // 16, 0, 15)
    rnd = idm[..., 1] / 255.0
    on = load(ORIG / "Wooden_Box_nrm.png") * 2 - 1
    occ_orig = load(ORIG / "wooden_box_ao.png", "L")
    M = {k: mid == v for k, v in IDS.items()}
    floor, fx, fz = b.inner_floor()

    # ---------------- walls: hoops and rivets from the bake
    hoop = b.walls & (M["hoop"] | M["rivet"])
    rust = smooth(0.3, 0.8, b.blotch * 0.25 + 0.5 + 0.3 * (b.noise - 0.5))
    iron = IRON * (1 - 0.45 * rust[..., None]) + RUST * 0.75 * 0.45 * rust[..., None]
    col = np.where(hoop[..., None], iron * (0.9 + 0.2 * b.noise[..., None]), col)
    riv = b.walls & M["rivet"]
    col = np.where(riv[..., None], IRON * 1.5 * (0.8 + 0.4 * ao[..., None]), col)
    spec = np.where(hoop, 0.2, spec)
    gloss = np.where(hoop, np.where(riv, 0.35, 0.25), gloss)

    col, spec, gloss, rim_heat = rim(b, col, spec, gloss)

    # ---------------- floor
    stone, coal, tray = floor & M["stone"], floor & M["coal"], floor & M["tray"]
    margin = floor & ~(stone | coal | tray)
    up = np.clip(nb[..., 2], 0, 1)
    warm = rnd > 0.7
    s = np.where(warm[..., None], BASALT_WARM, BASALT) * (0.8 + 0.4 * rnd[..., None])
    s = s * (0.9 + 0.2 * b.noise[..., None])
    dust = smooth(0.85, 1.0, up) * smooth(0.55, 0.9, ao) * 0.18          # a little ash settled on top
    s = s * (1 - dust[..., None]) + ASH * dust[..., None]
    fleck = smooth(0.66, 0.74, b.noise)                                  # grey ash flecks on the charcoal
    edge = np.minimum.reduce([fx + 0.335, 0.325 - fx, fz + 0.44, 0.445 - fz])
    fleck = np.clip(fleck * 0.6 + smooth(0.06, 0.035, edge) * 0.35, 0, 1) * smooth(0.3, 0.7, ao)
    c = CHARCOAL * (0.85 + 0.3 * b.noise[..., None])
    c = c * (1 - 0.6 * fleck[..., None]) + ASH * 0.6 * fleck[..., None]
    t = (IRON * 0.7 + RUST * 0.3) * (0.85 + 0.3 * b.noise[..., None])
    w = FLOOR_WOOD * (0.85 + 0.3 * b.noise[..., None])
    f = np.select([stone[..., None], coal[..., None], tray[..., None]], [s, c, t], w)
    f = f * (0.3 + 0.7 * ao[..., None])
    col = np.where(floor[..., None], f, col)
    spec = np.where(floor, np.select([stone, coal, tray], [0.05, 0.03, 0.15], 0.03), spec)
    gloss = np.where(floor, np.select([stone, coal, tray], [0.15 + 0.05 * up, 0.08, 0.28], 0.06), gloss)

    # ---------------- embers: charcoal deep between the stones, hottest mid-pile
    centre = np.clip(1 - np.hypot(fx / 0.28, fz / 0.38), 0, 1)
    deep = smooth(0.85, 0.5, ao)                                          # coal seams: AO 0.42..0.86
    flick = smooth(0.35, 0.75, b.noise + 0.25 * b.blotch * 0.3)
    heat = coal * deep * (0.15 + 0.85 * centre) * (0.4 + 0.6 * flick) * (1 - fleck)
    heat = blur(np.clip(1.2 * heat, 0, 1), 0.6)                           # a few hot cores, like v0 (1.4: too bright by day)
    heat = np.maximum(heat, blur(rim_heat, 0.5))
    core = smooth(0.35, 0.85, heat)
    emis = (EMBER_EDGE * (1 - core[..., None]) + EMBER_CORE * core[..., None]) * heat[..., None]
    col = np.where((heat > 0.15)[..., None], col * 0.5 + SOOT * 0.5, col)

    # ---------------- normal: baked on the floor and the hoops, original elsewhere
    n = np.where((floor | hoop)[..., None], nb, on)
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9
    occ = np.where(floor | hoop, 0.35 + 0.65 * ao, occ_orig)

    alpha = ~b.face_mask(is_lid)
    OUT.mkdir(exist_ok=True)
    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    Image.fromarray(np.dstack([q(col), q(alpha.astype(float))]), "RGBA").save(OUT / f"Box_{VERSION}_diffuse.png")
    Image.fromarray(q(n * 0.5 + 0.5), "RGB").save(OUT / f"Box_{VERSION}_normal.png")
    Image.fromarray(np.dstack([q(spec), q(spec), q(spec), q(gloss)]), "RGBA").resize(
        (512, 512), Image.LANCZOS).save(OUT / f"Box_{VERSION}_specgloss.png")
    Image.fromarray(q(occ), "L").save(OUT / f"Box_{VERSION}_occlusion.png")
    Image.fromarray(q(emis), "RGB").save(OUT / f"Box_{VERSION}_emission.png")
    print("wrote", OUT / f"Box_{VERSION}_*.png")


if __name__ == "__main__":
    main()
