"""Colour blocking v0 for Sauna Bench (Bed), concept A "bare bench".

The blanket (with the sheet fold) is cut away by alpha; the mattress becomes the bench: deck of
aspen slats along the length on top, a two-board apron on the sides and ends; the pillow becomes
a rolled linen towel with a faded brick stripe; the headboard planks are old door boards with
paint remnants; posts are aspen bars, darker toward the floor, the foot end (toward the stove)
smoked; the cross slats under the deck are wet dark wood; steel rails, stretchers and brackets
stay old iron (set rule: boards on old iron). Normal and AO stay original for now.

Model: centimetres, Z up (3ds Max export): x = length (+x head), y = width, z = height.
Pieces (see uv/parts.md): 0 blanket, 1 pillow, 2 mattress, 3-4 headboard planks, 5-6 head posts,
7-16 cross slats (one shared UV), 17-18 end rails, 19/22 low stretchers, 20-21 foot posts,
23-26 brackets, 27-28 side rails.

    .venv/Scripts/python skins/sauna/bed/blocking.py
Writes export/Bed_blocking_v0_{diffuse,specgloss}.png.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
sys.path.insert(0, str(HERE))
from parts import pieces  # noqa: E402
from uv_zones import load_obj, normal  # noqa: E402

ORIG = HERE / "originals"
OUT = HERE / "export"
SIZE = 2048
SEED = 6


def hexc(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float64) / 255.0


ASPEN = hexc("#C2A77E")      # fresh aspen (set palette)
STEAMED = hexc("#7A5A3C")    # steam-darkened (set palette)
SMOKED = hexc("#45332A")     # old wood by the fire (set palette)
LINEN = hexc("#CFC6B4")
BRICK = hexc("#8E3A30")
GAP = hexc("#2A2018")
IRON = hexc("#2E2A27")
RUST = hexc("#8C4A26")

BLANKET, PILLOW, MATTRESS = 0, 1, 2
HEADBOARD = (3, 4)
HEAD_POSTS, FOOT_POSTS = (5, 6), (20, 21)
CROSS_SLATS = tuple(range(7, 17))
IRON_PARTS = (17, 18, 19, 22, 23, 24, 25, 26, 27, 28)


def blur(a, r):
    f = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
    return np.asarray(f, np.float64) / 255.0


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def hash1(a, seed):
    a = a.astype(np.int64).astype(np.uint32) * np.uint32(2654435761) ^ np.uint32(seed * 97531)
    a ^= a >> np.uint32(15)
    a *= np.uint32(2246822519)
    a ^= a >> np.uint32(13)
    return a.astype(np.float64) / 2 ** 32


def position_map(V, T, F, piece_of, order):
    """3D point, face normal and piece id per texel (+ 4-texel gutter). UV u > 1 wraps.
    Pieces in `order` are drawn last-wins, so shared UV areas take the last listed piece."""
    pos = np.zeros((SIZE, SIZE, 3))
    nrm = np.zeros((SIZE, SIZE, 3))
    pid = np.full((SIZE, SIZE), -1)
    Va, Ta = np.array(V), np.array(T)
    rank = {p: i for i, p in enumerate(order)}
    for f in sorted(range(len(F)), key=lambda f: rank.get(piece_of[f], -1)):
        vi, ti = F[f]
        if None in ti:
            continue
        P = Va[list(vi)]
        uv = Ta[list(ti)].copy()
        uv -= np.floor(uv.min(0))
        uv *= SIZE
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
        pid[ys + y0, xs + x0] = piece_of[f]
    for _ in range(4):
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            src = np.roll(np.roll(pid, dy, 0), dx, 1)
            take = (pid < 0) & (src >= 0)
            pos[take] = np.roll(np.roll(pos, dy, 0), dx, 1)[take]
            nrm[take] = np.roll(np.roll(nrm, dy, 0), dx, 1)[take]
            pid[take] = src[take]
    return pos, nrm, pid


def boards(h, width, jitter, seed):
    """Boards across coordinate h: (board index, fraction 0..1 across the board, gap 0..1)."""
    k = np.floor(h / width)
    # vary board widths: shift each edge by up to `jitter` of a width
    edge = (k + (hash1(k, seed) - 0.5) * jitter) * width
    k = np.where(h < edge, k - 1, k)
    e0 = (k + (hash1(k, seed) - 0.5) * jitter) * width
    e1 = (k + 1 + (hash1(k + 1, seed) - 0.5) * jitter) * width
    fr = np.clip((h - e0) / np.maximum(e1 - e0, 1e-3), 0, 1)
    w = e1 - e0
    g = 0.35 / np.maximum(w, 1e-3)                          # ~3.5 mm gap
    gap = 1 - smooth(0, g, fr) * smooth(1, 1 - g, fr)
    return k, fr, gap


def main():
    V, T, F = load_obj(ORIG / "bed.obj")
    P = pieces(V, F)
    piece_of = np.empty(len(F), int)
    for n, fs in enumerate(P):
        piece_of[fs] = n
    order = [BLANKET, *IRON_PARTS, *CROSS_SLATS, *FOOT_POSTS, *HEAD_POSTS, *HEADBOARD, MATTRESS, PILLOW]
    pos, nrm, pid = position_map(V, T, F, piece_of, order)
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    an = np.abs(nrm)
    rng = np.random.default_rng(SEED)
    cov = pid >= 0
    isin = lambda ids: np.isin(pid, ids)

    bc = np.asarray(Image.open(ORIG / "bed_bc.png").convert("RGB"), np.float64) / 255.0
    lum = bc @ np.array([0.299, 0.587, 0.114])
    detail = np.clip(lum / np.maximum(blur(lum, 12), 1e-3), 0.6, 1.3)
    detail = 1 + 0.45 * (detail - 1)
    grain_f = blur(rng.random((SIZE, SIZE)), 0.8)
    streak = blur(rng.random((SIZE, SIZE)), 3)
    blotch = blur(rng.random((SIZE, SIZE)), 18)
    blotch = (blotch - blotch.mean()) / max(blotch.std(), 1e-6)

    col = np.zeros((SIZE, SIZE, 3)) + STEAMED
    spec = np.full((SIZE, SIZE), 0.06)
    gloss = np.full((SIZE, SIZE), 0.22)
    alpha = np.ones((SIZE, SIZE))

    # --- bench deck (mattress top) and apron (mattress sides/ends) ---------------------------
    m = isin([MATTRESS])
    top = m & (nrm[..., 2] > 0.6)
    side = m & ~top
    k, fr, gap = boards(y + 200, 8.0, 0.22, SEED)               # slats along the length, 7-9 cm
    tone = hash1(k, SEED + 1)
    deck = ASPEN * (0.9 + 0.18 * tone[..., None]) * (0.92 + 0.1 * grain_f[..., None] + 0.06 * streak[..., None])
    worn = smooth(-60, 20, x) * smooth(48, 30, np.abs(y))       # polished where people lie (head half, middle)
    deck = deck * (1 + 0.06 * worn[..., None])
    deck = deck * (1 - 0.18 * smooth(-95, -112, x)[..., None])  # foot end toward the stove: smoked
    edge = smooth(48, 54, np.abs(y))                            # worn lighter long edges
    deck = deck * (1 + 0.05 * edge[..., None])
    deck = deck * (1 - gap[..., None]) + GAP * gap[..., None]
    col[top] = deck[top]
    gloss[top] = (0.26 + 0.12 * worn)[top]

    # apron: two horizontal boards 9 cm each on the sides and ends, a shade darker, wet at the bottom
    ka, fa, gapa = boards(z + 0.3, 9.0, 0.08, SEED + 2)
    tone_a = hash1(ka + 31 * (an[..., 0] > an[..., 1]), SEED + 3)
    apron = (ASPEN * 0.82) * (0.9 + 0.16 * tone_a[..., None]) * (0.92 + 0.1 * grain_f[..., None])
    apron = apron * (1 - 0.25 * smooth(46, 37, z)[..., None])   # water runs down
    apron = apron * (1 - 0.3 * smooth(-100, -112, x)[..., None])
    apron = apron * (1 - gapa[..., None]) + GAP * gapa[..., None]
    col[side] = apron[side]

    # --- towel roll (pillow) -------------------------------------------------------------------
    t = isin([PILLOW])
    stripe = smooth(0.0, 0.6, 1 - np.abs(((y + 60) % 70) - 9) / 4.0)   # faded brick stripes across the roll
    towel = LINEN * (0.95 + 0.06 * grain_f[..., None])
    towel = towel * (1 - stripe[..., None] * 0.65) + BRICK * 1.15 * stripe[..., None] * 0.65
    towel = towel * (1 - 0.12 * smooth(60, 54, z)[..., None])   # damp where it touches the wood
    col[t] = towel[t]
    gloss[t] = 0.12

    # --- headboard: old door boards with paint remnants ----------------------------------------
    hb = isin(HEADBOARD)
    sat = bc.max(-1) - bc.min(-1)
    paint = smooth(0.12, 0.3, sat) * smooth(0.55, 0.75, blur(rng.random((SIZE, SIZE)), 10))  # ~20% left
    hue = bc / np.maximum(bc.max(-1, keepdims=True), 1e-3)
    faded = 0.55 * hue * 0.62 + 0.45 * 0.5
    wood = STEAMED * 1.15 * (0.9 + 0.12 * grain_f[..., None]) * detail[..., None]
    hcol = wood * (1 - paint[..., None]) + faded * paint[..., None]
    col[hb] = hcol[hb]

    # --- posts ----------------------------------------------------------------------------------
    po = isin(HEAD_POSTS + FOOT_POSTS)
    post = ASPEN * 0.88 * (0.9 + 0.12 * grain_f[..., None] + 0.06 * streak[..., None]) * detail[..., None]
    post = post * (1 - 0.35 * smooth(30, 0, z)[..., None])                          # wet bottom
    post = post * (1 - 0.3 * (isin(FOOT_POSTS) * smooth(10, 62, z))[..., None])     # smoked, stove side
    col[po] = post[po]

    # --- cross slats under the deck: wet, dark -------------------------------------------------
    cs = isin(CROSS_SLATS)
    col[cs] = (STEAMED * 0.85 * (0.9 + 0.14 * grain_f[..., None]) * detail[..., None])[cs]

    # --- iron -------------------------------------------------------------------------------------
    ir = isin(IRON_PARTS)
    rust = smooth(0.5, 0.68, blur(rng.random((SIZE, SIZE)), 6) + 0.05 * blotch)
    ic = (IRON * (1 - rust[..., None]) + RUST * rust[..., None]) * (0.75 + 0.5 * lum[..., None])
    col[ir] = ic[ir]
    spec[ir] = (0.35 - 0.22 * rust)[ir]
    gloss[ir] = (0.42 - 0.25 * rust)[ir]

    # --- blanket: cut away ------------------------------------------------------------------------
    b = isin([BLANKET])
    alpha[b] = 0
    col[b] = ASPEN * 0.9          # colour behind the cut, in case of mip bleeding
    col[~cov] = STEAMED * 0.8

    # gentle large-scale variation everywhere wood
    woodm = top | side | po | hb | cs
    col[woodm] *= (1 + 0.035 * blotch[woodm])[:, None]

    OUT.mkdir(exist_ok=True)
    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    Image.fromarray(np.dstack([q(col), q(alpha)]), "RGBA").save(OUT / "Bed_blocking_v0_diffuse.png")
    Image.fromarray(np.dstack([q(spec), q(spec), q(spec), q(gloss)]), "RGBA").save(OUT / "Bed_blocking_v0_specgloss.png")
    print("done; covered", f"{cov.mean():.1%}", "cut", f"{b.mean():.1%}")


if __name__ == "__main__":
    main()
