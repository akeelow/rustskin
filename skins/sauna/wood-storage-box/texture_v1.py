"""Sauna Stone Box v1: final maps from the bake (bake_box.py) and the v0 palette (blocking.py).

Walls: as blocking v0 (aspen, two hoops, smoke on the stove side, greasy handle slots), with the hoops and
rivets taken from the bake's id map so colour and relief match; original normal map elsewhere.
Floor (inner, its own texels): dark basalt stones (v0's were pale "eggs" in the sun), charcoal between
them with ash flecks, the steel tray's rim, the wooden floor's margin; baked normal and AO.
Glow: the embers - charcoal deep between the stones (low baked AO), hottest mid-pile, dying out
towards the tray. v1.1: the rim too - the survivor shovels the coals in over the rim on the stove side
(+x), the shovel knocks on it: that rim and the corners next to it are charred, smouldering in the
crackle (v1.2: nothing on the other rims); v1.3: that rim burnt away with alpha, the embers a line along
the burnt edge. The handle slots don't glow.
The lid is cut with alpha (Alpha Cutoff 0.50).

    .venv/Scripts/python skins/sauna/wood-storage-box/texture_v1.py
Inputs: bake/{normal,ao,id}.png, originals/Wooden_Box_{nrm.png}, wooden_box_ao.png.
Outputs: export/Box_v1.3_{diffuse (RGBA), normal, specgloss (512), occlusion, emission}.png (1024).
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
VERSION = "v1.4"
IDS = {"base": 0, "stone": 1, "coal": 2, "tray": 3, "hoop": 4, "rivet": 5}    # bake_box.IDS
BASALT = hexc("#26272A")              # v1: #2E2F32 - still pale in direct sun (v1.1 shots)
BASALT_WARM = hexc("#302B28")
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


def wave(t, seed, freqs=(9.0, 23.0, 57.0), amps=(0.5, 0.3, 0.2)):
    """Smooth 1D noise along t (m), 0..1."""
    rng = np.random.default_rng(seed)
    out = sum(a * np.sin(t * f * 2 * np.pi / 3 + rng.uniform(0, 2 * np.pi)) for f, a in zip(freqs, amps))
    return 0.5 + 0.5 * out / sum(amps)


def rim(b, col, spec, gloss):
    """The rim on the stove side (+x) and the corners next to it, where the coals are shovelled in: burnt away
    0-3 cm (alpha, smooth so the cut-off contour is smooth), embers smouldering deep inside charred alligator
    fissures in localized clusters (no continuous laser wire), charcoal under it fading into brown scorch.
    Outer and inner vertical wall faces and the wall tops.
    Returns colour, spec, gloss, heat and alpha (1 = keep)."""
    x, y, z = b.x, b.y, b.z
    top = (y > 0.525) & (b.nrm[..., 1] > 0.7) & ~b.lid
    dist = np.stack([0.34 - x, z + 0.46, x + 0.36, 0.47 - z])               # right, back, left, front
    side = np.where(b.walls, np.select([b.right, b.back, b.left, b.front], [0, 1, 2, 3], 0), dist.argmin(0))
    # continuous running coordinate: back corner (0) -> right wall (0..0.945) -> front corner (0.945)
    run = np.select([side == 0, side == 1, side == 2, side == 3],
                    [np.clip(z + 0.465, 0.0, 0.945), 0.34 - x, z + 0.47, x + 0.36], 0)
    from_stove = np.select([side == 0, side == 1, side == 2, side == 3],
                           [0 * x, np.maximum(0.34 - x, 0.0), 9 + 0 * x, np.maximum(0.34 - x, 0.0)], 9)
    w = np.where(side == 0, 1.0, smooth(0.2, 0.0, from_stove))            # how burnt: 1 on the stove side
    # continuous coordinate across back corner -> stove side -> front corner (no coordinate jumps!)
    s_ = np.select([side == 1, side == 0, side == 3], [-from_stove, run, 0.945 + from_stove], 0)
    h = RIM_Y - y                                                           # depth below the rim
    cut = w * (0.004 + 0.026 * wave(s_, 51) ** 1.5)                       # burnt away: 0.4..3 cm
    for c0, wid, dep in ((0.18, 0.05, 0.02), (0.55, 0.035, 0.015), (0.8, 0.06, 0.012)):   # tongues
        cut = cut + w * dep * np.exp(-((s_ - c0) / wid) ** 2)

    # all vertical & bevel faces in the burnt zone (outer, inner, and corners)
    face = ~b.lid & ~top & (h < 0.15) & (w > 0.001)
    keep = np.where(face, smooth(cut - 0.0025, cut + 0.0025, h), 1.0)
    keep = np.where(top, smooth(0.35, 0.15, w), keep)                       # the wall top is gone where burnt
    keep = blur(np.clip(keep, 0, 1), 0.8)                                   # smooth corner alpha steps

    below = h - cut                                                         # depth under the burnt edge
    char_d = w * (0.012 + 0.03 * wave(s_, 52))
    a = np.where(face, smooth(char_d + 0.02, char_d * 0.4, below), np.where(top, w, 0)) * (w > 0.03)
    a = blur(np.clip(a, 0, 1), 1.0)
    # colour: charcoal at the edge, brown scorch below it, no hard line
    ashy = smooth(0.45, 0.8, b.noise + 0.1 * b.blotch)
    char = CHAR * (0.85 + 0.2 * b.noise[..., None])
    char = char * (1 - 0.25 * ashy[..., None]) + ASH * 0.25 * ashy[..., None]
    scorch = smooth(0.0, 0.35, a) * (1 - smooth(0.35, 0.8, a))
    col = col * (1 - 0.7 * scorch[..., None]) + SCORCH * 0.7 * scorch[..., None]
    k = smooth(0.35, 0.8, a)
    col = col * (1 - k[..., None]) + char * k[..., None]
    spec = np.where(k > 0.5, 0.03, spec)
    gloss = np.where(k > 0.5, 0.07, gloss)

    # embers: natural smouldering wood coals in deep alligator crackle fissures (no continuous line!)
    cr = crackle(s_, y, CRACKLE, 41)
    fissures = smooth(0.55, 0.90, cr)                                      # isolated deep cracks
    clusters = smooth(0.45, 0.80, wave(s_, 53, (7.0, 17.0, 37.0), (0.6, 0.3, 0.1)))  # sparse hot pockets
    depth_fade = smooth(0.002, 0.008, below) * smooth(0.035, 0.015, below) * (below > 0)
    micro = 0.75 + 0.25 * wave(s_ * 5.0 + y * 7.0, 77, (13.0, 29.0), (0.6, 0.4))
    heat = 0.75 * fissures * clusters * micro * depth_fade * w * face
    heat = np.where(top, 0, heat)
    return col, spec, gloss, np.clip(heat, 0, 1), np.clip(keep, 0, 1)


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

    col, spec, gloss, rim_heat, rim_keep = rim(b, col, spec, gloss)

    # ---------------- floor
    stone, coal, tray = floor & M["stone"], floor & M["coal"], floor & M["tray"]
    margin = floor & ~(stone | coal | tray)
    up = np.clip(nb[..., 2], 0, 1)
    warm = rnd > 0.7
    s = np.where(warm[..., None], BASALT_WARM, BASALT) * (0.8 + 0.4 * rnd[..., None])
    s = s * (0.9 + 0.2 * b.noise[..., None])
    dust = smooth(0.85, 1.0, up) * smooth(0.55, 0.9, ao) * 0.08          # a little ash on top (0.18: snowballs in the sun)
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
    heat = blur(np.clip(0.85 * heat, 0, 1), 0.6)                           # v1.4: softened ~30% from v1.3 (1.2) to prevent daytime washout
    heat = np.maximum(heat, blur(rim_heat, 0.5))
    core = smooth(0.28, 0.78, heat)
    emis = (EMBER_EDGE * (1 - core[..., None]) + EMBER_CORE * core[..., None]) * heat[..., None]
    col = np.where((heat > 0.15)[..., None], col * 0.5 + SOOT * 0.5, col)

    # ---------------- normal: baked on the floor and the hoops, original elsewhere
    n = np.where((floor | hoop)[..., None], nb, on)
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9
    occ = np.where(floor | hoop, 0.35 + 0.65 * ao, occ_orig)

    alpha = np.minimum(~b.face_mask(is_lid), rim_keep)
    OUT.mkdir(exist_ok=True)
    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    diff_im = Image.fromarray(np.dstack([q(col), q(alpha)]), "RGBA")
    norm_im = Image.fromarray(q(n * 0.5 + 0.5), "RGB")
    spec_im = Image.fromarray(np.dstack([q(spec), q(spec), q(spec), q(gloss)]), "RGBA").resize(
        (512, 512), Image.LANCZOS)
    occ_im = Image.fromarray(q(occ), "L")
    emis_im = Image.fromarray(q(emis), "RGB")

    for ver in (VERSION, "v1.3"):
        diff_im.save(OUT / f"Box_{ver}_diffuse.png")
        norm_im.save(OUT / f"Box_{ver}_normal.png")
        spec_im.save(OUT / f"Box_{ver}_specgloss.png")
        occ_im.save(OUT / f"Box_{ver}_occlusion.png")
        emis_im.save(OUT / f"Box_{ver}_emission.png")
        print("wrote", OUT / f"Box_{ver}_*.png")


if __name__ == "__main__":
    main()
