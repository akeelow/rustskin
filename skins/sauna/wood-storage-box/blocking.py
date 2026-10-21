"""Colour blocking v0 for the Sauna Stone Box (Wood Storage Box), concept D, open top (lid cut with alpha).

Story: by the stove the survivor keeps spare stones and the embers for lighting it in an old crate. So the
crate wouldn't dry out and split in the heat, he bound it with two hoops off a barrel; so it wouldn't catch
fire, he laid a sheet of steel on the bottom. The side towards the stove is smoked from the floor up.
The stones on the steel are still hot: at night the embers smoulder between them.

Glow only where the story puts heat: the embers between the stones on the floor (hot in the middle,
dying out towards the tray's edge). Optionally (LOW_GAP_GLOW) a faint warm leak through the lowest plank
gap, just above the stones. The handle slots don't glow: they sit 40 cm above the embers.

What the client draws (in-game test, README "Открытый верх"): the lid goes with alpha, every inner wall
wears its own outer side at the same spot, the inner floor has its own texels (shared only with the
outer bottom). So the walls are painted once, from outside; the floor is painted in its own coordinates.

    .venv/Scripts/python skins/sauna/wood-storage-box/blocking.py
Writes export/Box_blocking_v0_{diffuse (1024, alpha 0 on the lid), specgloss (512), emission (1024)}.png.
Normal and Occlusion stay original for now.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from concepts import (ASPEN, EMBER_CORE, EMBER_EDGE, IRON, PLANK_Y, RUST, SIZE, SLOT, SOOT, Box,  # noqa: E402
                      band, blur, char, hash1, hexc, is_lid, mix, smooth)

HERE = Path(__file__).resolve().parent
OUT = HERE / "export"
VERSION = "blocking_v0"
BASALT = hexc("#3D3E41")
ASH = hexc("#8C8680")
CINDER = hexc("#2A2624")
LOW_GAP_GLOW = 0.18          # warm leak through the lowest plank gap (y 0.135); 0 = off
TRAY = 0.025                 # the steel sheet stops 2.5 cm short of the walls


def walls(b):
    """Outer walls (and so the inner ones): aspen, two barrel hoops, smoke on the stove side (+x)."""
    col = b.wood(ASPEN * 0.95, grey_share=0.25)
    spec = np.full((SIZE, SIZE), 0.06)
    gloss = np.full((SIZE, SIZE), 0.14)
    side = np.clip((b.x - 0.05) / 0.3, 0, 1) * b.walls + b.right * 0.5
    col = char(col, np.clip(side * smooth(0.35, 0.03, b.y + 0.036 * b.blotch) * (0.45 + 0.1 * b.blotch), 0, 0.7))
    for y0, y1 in ((0.045, 0.09), (0.31, 0.355)):
        inside, rivet, rust, drip = band(b, y0, y1)
        col = mix(col, RUST * 0.8, drip * 0.35)
        iron = IRON * (1 - 0.45 * rust[..., None]) + RUST * 0.75 * 0.45 * rust[..., None]
        col = np.where(inside[..., None], iron * (0.9 + 0.2 * b.noise[..., None]), col)
        col = np.where(rivet[..., None], IRON * 1.4, col)
        spec = np.where(inside, 0.2, spec)
        gloss = np.where(inside, 0.25, gloss)
    # handle slots: dark and greasy round the edge where hands grab
    ends = b.front | b.back
    edge_y = np.where(np.abs(b.x) < 0.09, 0.45, 0.45 - (np.abs(b.x) - 0.09) / 0.07 * 0.045)
    d = np.where(np.abs(b.x) < SLOT[1], np.minimum(np.abs(b.y - edge_y), np.abs(b.y - 0.40)), 9)
    grip = (ends & (np.abs(b.x) < SLOT[1] + 0.02) & (b.y > 0.385) & (b.y < 0.48)) * smooth(0.025, 0.004, d)
    col = col * (1 - 0.3 * grip[..., None])
    gloss = gloss + 0.12 * grip
    return col, spec, gloss


def floor(b, col, spec, gloss):
    """Inner floor: a rusty steel sheet, basalt stones on it, ash and embers between them."""
    m, fx, fz = b.inner_floor()
    ys, xs = np.nonzero(m)
    x, z = fx[ys, xs], fz[ys, xs]
    # tray: steel sheet with a turned-up rim; outside it the wooden floor, dark with ash
    edge = np.minimum.reduce([x + 0.335, 0.325 - x, z + 0.44, 0.445 - z])        # to the nearest wall
    tray = edge > TRAY
    rim = smooth(0.006, 0.0, np.abs(edge - TRAY))
    rng = np.random.default_rng(5)
    n = 60
    c = np.column_stack([rng.uniform(-0.30, 0.29, n), rng.uniform(-0.40, 0.41, n)])
    size = rng.uniform(0.8, 1.3, n)
    dist = np.linalg.norm(np.column_stack([x, z])[:, None, :] - c[None], axis=2) / size[None]
    o = np.argsort(dist, axis=1)[:, :2]
    d1 = dist[np.arange(len(x)), o[:, 0]]
    d2 = dist[np.arange(len(x)), o[:, 1]]
    gap = np.clip(1 - (d2 - d1) / 0.014, 0, 1) ** 1.5                           # 1 on the seam between stones
    stone_in = (d1 < 0.065) & (edge > TRAY + 0.01)                                # stones stay on the tray
    tone = hash1(o[:, 0], 21)
    dome = np.clip(1 - d1 / 0.065, 0, 1)
    stone = BASALT * (0.75 + 0.35 * tone[:, None]) * (0.75 + 0.5 * dome[:, None] ** 0.7)
    steel = (IRON * 0.7 + RUST * 0.3) * (0.85 + 0.3 * b.noise[ys, xs][:, None])
    steel = steel * (1 + 0.5 * rim[:, None])
    wood_floor = CINDER * 1.4 * (0.9 + 0.2 * b.noise[ys, xs][:, None])
    base = np.where(tray[:, None], steel, wood_floor)
    ash = np.clip(gap * 0.8 + (~stone_in) * 0.4, 0, 1) * smooth(0.0, 0.08, edge)
    base = base * (1 - 0.6 * ash[:, None]) + ASH * 0.6 * ash[:, None]
    stone = stone * (1 - 0.85 * gap[:, None]) + CINDER * 0.85 * gap[:, None]
    out = np.where(stone_in[:, None], stone, base)
    col[ys, xs] = out
    spec[ys, xs] = np.where(stone_in, 0.05, np.where(tray, 0.15, 0.04))
    gloss[ys, xs] = np.where(stone_in, 0.2 + 0.1 * dome, np.where(tray, 0.3, 0.08))
    # embers: on some seams between stones, hot in the middle of the pile, dying out towards the tray edge
    pair = np.minimum(o[:, 0], o[:, 1]) * 97 + np.maximum(o[:, 0], o[:, 1])
    lit = hash1(pair, 23) > 0.35
    centre = np.clip(1 - np.hypot(x / 0.30, z / 0.40), 0, 1)
    heat = gap * stone_in * lit * (0.25 + 0.75 * centre) * (0.6 + 0.4 * hash1(pair, 24))
    h = np.zeros((SIZE, SIZE))
    h[ys, xs] = heat
    return col, spec, gloss, h


def low_gap(b):
    """A faint warm leak through the lowest plank gap, strongest mid-wall, gone at the corners."""
    near = np.abs(b.y - PLANK_Y[1]) < 0.006
    lip = near & (b.walls | (np.abs(b.nrm[..., 1]) > 0.7)) & ~b.lid
    t = np.where(b.front | b.back, 1 - np.abs(b.x) / 0.33, 1 - np.abs(b.z) / 0.45)
    return lip * smooth(0.0, 0.5, t) * smooth(0.006, 0.002, np.abs(b.y - PLANK_Y[1])) * LOW_GAP_GLOW


def main():
    b = Box()
    col, spec, gloss = walls(b)
    col, spec, gloss, heat = floor(b, col, spec, gloss)
    heat = np.maximum(blur(heat, 0.7), blur(low_gap(b), 0.6))
    core = smooth(0.35, 0.9, heat)
    emis = (EMBER_EDGE * (1 - core[..., None]) + EMBER_CORE * core[..., None]) * heat[..., None]
    alpha = ~b.face_mask(is_lid)
    OUT.mkdir(exist_ok=True)
    rgba = np.dstack([(np.clip(col, 0, 1) * 255).astype(np.uint8), (alpha * 255).astype(np.uint8)])
    Image.fromarray(rgba, "RGBA").save(OUT / f"Box_{VERSION}_diffuse.png")
    sg = np.dstack([np.repeat((np.clip(spec, 0, 1) * 255).astype(np.uint8)[..., None], 3, 2),
                    (np.clip(gloss, 0, 1) * 255).astype(np.uint8)])
    Image.fromarray(sg, "RGBA").resize((512, 512), Image.LANCZOS).save(OUT / f"Box_{VERSION}_specgloss.png")
    Image.fromarray((np.clip(emis, 0, 1) * 255).astype(np.uint8)).save(OUT / f"Box_{VERSION}_emission.png")
    print("wrote", OUT / f"Box_{VERSION}_*.png")


if __name__ == "__main__":
    main()
