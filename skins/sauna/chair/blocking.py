"""Colour blocking v0 for Sauna Chair (Chair), concept C "changing-room chair", no alpha.

Story: the survivor brought an old armchair frame of steel channel from the same roadside house as
the bench and set it in the changing room, where people cool off after the steam room. The backrest
is clad in narrow vertical lining boards (off-cuts from the sauna walls), the seat in aspen slats
across, the missing front leg replaced by a shovel handle with wire wrapped round the split end.
A linen towel with a brick stripe is thrown over the top of the backrest, the striped end hanging
down the front; a wet ring on the seat where the wash basin stood; a cracked front slat pulled
together with a staple.

Model: metres, Y up: x = width (+x right, seen from the front), y = height, z = depth (+z front).
Islands (see uv/islands.md): 0 shell (seat top + front lip, backrest front, side wings),
5 backrest back + seat underside, 2 top rail, 7/12 and 9/20 right/left arm (top+sides / underside),
13 arm bracket, 1 right arm post + strip under the seat front, 11 left arm post, 6/8 rear legs
(channel, run up behind the backrest), 4 front-left leg (round), 3/15/16 its tip and ends,
10 front-right leg (block), 14/17-19/21 bolts and brackets.

    .venv/Scripts/python skins/sauna/chair/blocking.py
Writes export/Chair_blocking_v0_{diffuse,specgloss}.png (1024, like the originals).
Normal and Occlusion stay original for now.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
sys.path.insert(0, str(HERE))
from islands import islands  # noqa: E402
from uv_zones import load_obj, normal  # noqa: E402

ORIG = HERE / "originals"
OUT = HERE / "export"
SIZE = 2048          # work size; maps are saved at OUT_SIZE
OUT_SIZE = 1024
SEED = 7


def hexc(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float64) / 255.0


# palette as the finished bench (bed/texture_v1.py, v1.2): one house, one survivor
ASPEN = hexc("#A39176")          # aspen, steam-aged
ASPEN_GREY = hexc("#958B7E")     # weathered silver-grey
STEAMED = hexc("#7A5A3C")
LINEN = hexc("#CFC6B4")
BRICK = hexc("#8E3A30")
GAP = hexc("#2A2018")
IRON = hexc("#2E2A27")
RUST = hexc("#8C4A26")
MINERAL = hexc("#D9D4C8")
HANDLE = hexc("#8A6B4C")         # shovel handle: denser, browner wood, polished by hands

SHELL, POST_R, RAIL, TIP, POLE, BACK, REAR_L, ARM_R, REAR_R, ARM_L, BLOCK, POST_L = range(12)
ARM_R_UNDER, BRACKET, BOLT, POLE_TOP, TIP_END = 12, 13, 14, 15, 16
TABS, ARM_L_UNDER, MISC = (17, 18, 19), 20, 21
SEAT_Y = 0.535       # shell above this is the backrest
PANEL_X = 0.205      # backrest panel half-width; outside it the curved side wings

# towel over the top rail: 31 cm wide, a little off-centre; the striped end hangs down the front
TOWEL_X = (-0.19, 0.12)
TOWEL_FRONT_Y = 0.79     # hem on the front, left corner (hangs a bit lower on the right)
TOWEL_BACK_Y = 0.94      # hem on the back

RING_C, RING_R = (0.09, 0.07), 0.125     # wet ring from the wash basin, seat (x, z), m


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


def position_map(V, T, F, island_of):
    """3D point, face normal and island id per texel (+ 4-texel gutter)."""
    pos = np.zeros((SIZE, SIZE, 3))
    nrm = np.zeros((SIZE, SIZE, 3))
    iid = np.full((SIZE, SIZE), -1)
    Va, Ta = np.array(V), np.array(T)
    for f, (vi, ti) in enumerate(F):
        P = Va[list(vi)]
        uv = Ta[list(ti)][:, :2] * SIZE
        uv[:, 1] = SIZE - uv[:, 1]
        x0, y0 = np.maximum(np.floor(uv.min(0)).astype(int) - 1, 0)
        x1, y1 = np.minimum(np.ceil(uv.max(0)).astype(int) + 1, SIZE - 1)
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
        iid[ys + y0, xs + x0] = island_of[f]
    for _ in range(4):
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            src = np.roll(np.roll(iid, dy, 0), dx, 1)
            take = (iid < 0) & (src >= 0)
            pos[take] = np.roll(np.roll(pos, dy, 0), dx, 1)[take]
            nrm[take] = np.roll(np.roll(nrm, dy, 0), dx, 1)[take]
            iid[take] = src[take]
    return pos, nrm, iid


def boards(h, width, jitter, seed, gap_cm=0.35):
    """Boards across coordinate h (cm): (board index, fraction 0..1 across the board, gap 0..1)."""
    k = np.floor(h / width)
    edge = (k + (hash1(k, seed) - 0.5) * jitter) * width
    k = np.where(h < edge, k - 1, k)
    e0 = (k + (hash1(k, seed) - 0.5) * jitter) * width
    e1 = (k + 1 + (hash1(k + 1, seed) - 0.5) * jitter) * width
    fr = np.clip((h - e0) / np.maximum(e1 - e0, 1e-3), 0, 1)
    g = gap_cm / np.maximum(e1 - e0, 1e-3)
    gap = 1 - smooth(0, g, fr) * smooth(1, 1 - g, fr)
    return k, fr, gap


def main():
    V, T, F = load_obj(ORIG / "chair.obj")
    island_of = np.empty(len(F), int)
    for n, fs in enumerate(islands(F)):
        island_of[fs] = n
    pos, nrm, iid = position_map(V, T, F, island_of)
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    xc, yc, zc = x * 100, y * 100, z * 100
    rng = np.random.default_rng(SEED)
    isin = lambda ids: np.isin(iid, ids)

    bc = np.asarray(Image.open(ORIG / "chair_bc.png").convert("RGB").resize((SIZE, SIZE), Image.BICUBIC),
                    np.float64) / 255.0
    lum = bc @ np.array([0.299, 0.587, 0.114])
    detail = np.clip(lum / np.maximum(blur(lum, 12), 1e-3), 0.6, 1.3)
    grain_f = blur(rng.random((SIZE, SIZE)), 0.8)
    streak = blur(rng.random((SIZE, SIZE)), 3)
    blotch = blur(rng.random((SIZE, SIZE)), 18)
    blotch = (blotch - blotch.mean()) / max(blotch.std(), 1e-6)

    col = np.zeros((SIZE, SIZE, 3)) + STEAMED
    spec = np.full((SIZE, SIZE), 0.06)
    gloss = np.full((SIZE, SIZE), 0.22)
    wood = np.zeros((SIZE, SIZE), bool)

    shell, back = isin([SHELL]), isin([BACK])
    seat = shell & (y < SEAT_Y)
    seat_top = seat & (nrm[..., 1] > 0.5)
    seat_edge = seat & ~seat_top
    panel = shell & (y >= SEAT_Y) & (np.abs(x) < PANEL_X)
    wings = shell & (y >= SEAT_Y) & ~panel
    under = back & (nrm[..., 1] < -0.5) & (y < 0.52)
    back_side = back & ~under

    # --- seat: aspen slats across (along x), stacked front to back --------------------------------
    k, fr, gap = boards(zc + 30, 9.0, 0.2, SEED)
    tone = hash1(k, SEED + 1)
    grey = hash1(k, SEED + 2) > 0.65
    base = np.where(grey[..., None], ASPEN_GREY, ASPEN)
    s = base * (0.92 + 0.14 * tone[..., None]) * (0.92 + 0.1 * grain_f[..., None] + 0.05 * streak[..., None])
    polished = smooth(0.2, 0.08, np.hypot(x / 1.2, z - 0.06))          # where people sit
    s = s * (1 + 0.07 * polished[..., None])
    s = s * (1 + 0.05 * smooth(0.26, 0.31, z)[..., None])              # front edge: rubbed by legs
    # wet ring from the wash basin: dark, broken in places, a faint damp disc inside
    r = np.hypot(x - RING_C[0], z - RING_C[1])
    # (v0 first try: a thin 9 mm ring read as a drawn circle - wider, softer inside, broken)
    ring = np.exp(-((r - RING_R) / 0.016) ** 2) * smooth(0.3, 0.6, blur(rng.random((SIZE, SIZE)), 20) + 0.25)
    ring = np.maximum(ring, 0.35 * smooth(RING_R + 0.005, RING_R - 0.04, r))
    s = s * (1 - 0.22 * ring[..., None])
    # cracked front slat at the left end, pulled together with a staple
    crack_z = 0.268 + 0.002 * np.sin(x * 90)
    crack = smooth(0.0025, 0.0005, np.abs(z - crack_z)) * smooth(-0.13, -0.17, x) * (x > -0.31)
    s = s * (1 - 0.75 * crack[..., None]) + GAP * 0.75 * crack[..., None]
    staple = (np.abs(x + 0.215) < 0.003) & (np.abs(z - crack_z) < 0.016)
    s = s * (1 - gap[..., None]) + GAP * gap[..., None]
    col[seat_top] = s[seat_top]
    gloss[seat_top] = (0.24 + 0.12 * polished + 0.25 * ring)[seat_top]
    # nails into the side rails: two per slat near each end
    kn, frn, _ = boards(zc + 30, 9.0, 0.2, SEED)
    nail = seat_top & (np.abs(np.abs(x) - 0.255) < 0.006) & (np.abs(frn - 0.5) > 0.12) & (np.abs(frn - 0.5) < 0.3)
    col[nail] = IRON * 1.2
    col[staple & seat_top] = IRON * 1.4
    spec[staple & seat_top] = 0.35

    # seat edges: front = slat face, sides = end grain (darker), underside of the lip wet
    e = ASPEN * 0.85 * (0.92 + 0.12 * grain_f[..., None])
    e = np.where((np.abs(nrm[..., 0]) > 0.5)[..., None], e * 0.78, e)
    e = e * (1 - 0.25 * smooth(0.47, 0.43, y)[..., None])
    col[seat_edge] = e[seat_edge]
    wood |= seat_top | seat_edge

    # --- backrest: narrow vertical lining boards (6.5 cm), V-groove between them ------------------
    kp, fp, gp = boards(xc + 30, 6.5, 0.08, SEED + 3, gap_cm=0.3)
    tp = hash1(kp, SEED + 4)
    p = ASPEN * (0.95 + 0.1 * tp[..., None]) * (0.92 + 0.1 * grain_f[..., None] + 0.06 * streak[..., None])
    lean = smooth(0.16, 0.06, np.hypot(x / 1.6, (y - 0.72) / 1.3))     # darker where sweaty backs lean
    p = p * (1 - 0.1 * lean[..., None])
    p = p * (1 - gp[..., None]) + GAP * gp[..., None]
    col[panel] = p[panel]
    gloss[panel] = (0.24 + 0.08 * lean)[panel]
    # back side: the same boards from behind, rougher and greyer, two battens across
    b = ASPEN_GREY * (0.88 + 0.1 * tp[..., None]) * (0.92 + 0.1 * grain_f[..., None])
    b = b * (1 - gp[..., None]) + GAP * gp[..., None]
    batten = (np.abs(y - 0.63) < 0.03) | (np.abs(y - 0.99) < 0.03)
    b = np.where(batten[..., None], STEAMED * 1.05 * (0.92 + 0.1 * grain_f[..., None]), b)
    col[back_side] = b[back_side]
    gloss[back_side] = 0.18
    # side wings: bent aspen frame, a shade darker, polished where hands grab the top corners
    w = ASPEN * 0.86 * (0.92 + 0.12 * grain_f[..., None] + 0.05 * streak[..., None])
    w = w * (1 + 0.06 * smooth(0.95, 1.08, y)[..., None])
    col[wings] = w[wings]
    # top rail: aspen crossbar (mostly under the towel)
    rl = isin([RAIL])
    col[rl] = (ASPEN * 0.9 * (0.92 + 0.12 * grain_f[..., None]))[rl]
    wood |= panel | back_side | wings | rl

    # --- seat underside: dark wet joists ------------------------------------------------------------
    col[under] = (STEAMED * 0.8 * (0.9 + 0.14 * grain_f[..., None]))[under]
    wood |= under

    # --- arms: aspen bars, front ends polished by hands -----------------------------------------
    arms = isin([ARM_R, ARM_L])
    a = ASPEN * 0.9 * (0.92 + 0.12 * grain_f[..., None] + 0.05 * streak[..., None])
    hand = smooth(0.05, 0.2, z) * (nrm[..., 1] > 0.5)
    a = a * (1 + 0.1 * hand[..., None])
    col[arms] = a[arms]
    gloss[arms] = (0.22 + 0.15 * hand)[arms]
    au = isin([ARM_R_UNDER, ARM_L_UNDER])
    col[au] = (ASPEN * 0.7 * (0.92 + 0.1 * grain_f[..., None]))[au]
    pl = isin([POST_L])
    col[pl] = (ASPEN * 0.8 * (0.92 + 0.12 * grain_f[..., None]))[pl]
    wood |= arms | au | pl

    # --- front legs: aspen block (right), shovel handle with wire at the foot (left) ---------------
    bl = isin([BLOCK])
    blk = ASPEN * 0.88 * (0.9 + 0.12 * grain_f[..., None] + 0.06 * streak[..., None])
    col[bl] = blk[bl]
    po = isin([POLE, POLE_TOP])
    h = HANDLE * (0.92 + 0.1 * grain_f[..., None]) * (1 + 0.08 * smooth(0.2, 0.4, y)[..., None])
    col[po] = h[po]
    gloss[po] = 0.34
    wire_zone = isin([POLE]) & (y < 0.11) | isin([TIP])
    turns = 0.5 + 0.5 * np.sin((y * 100 + np.arctan2(z - 0.28, x + 0.27) * 0.25) * 2 * np.pi / 0.45)
    wcol = IRON * (0.9 + 0.9 * turns[..., None]) * (1 - 0.3 * smooth(0.5, 0.75, blur(rng.random((SIZE, SIZE)), 4)))[..., None] \
        + RUST * 0.25 * smooth(0.5, 0.75, blur(rng.random((SIZE, SIZE)), 4))[..., None]
    col[wire_zone] = wcol[wire_zone]
    spec[wire_zone] = 0.3
    gloss[wire_zone] = 0.35
    te = isin([TIP_END])
    col[te] = GAP * 1.2
    wood |= bl | (po & ~wire_zone)

    # --- iron: rear legs (channel), right arm post, strip under the seat, brackets, bolts ------------
    ir = isin([REAR_L, REAR_R, POST_R, BRACKET, BOLT, MISC, *TABS])
    rust_n = blur(rng.random((SIZE, SIZE)), 6) + 0.05 * blotch
    rust_bias = 0.18 * smooth(0.12, 0.0, y) + 0.12 * np.exp(-((y - 0.45) / 0.05) ** 2)   # bottoms, seat joint
    rust = smooth(0.52, 0.68, rust_n + rust_bias)
    rust_c = RUST * 0.75 + IRON * 0.25                                      # pure RUST read as orange spots
    ic = (IRON * (1 - 0.8 * rust[..., None]) + rust_c * 0.8 * rust[..., None]) * (0.75 + 0.5 * lum[..., None])
    col[ir] = ic[ir]
    spec[ir] = (0.35 - 0.22 * rust)[ir]
    gloss[ir] = (0.42 - 0.25 * rust)[ir]

    # --- all legs: darkest at the floor, mineral streaks where water stands ----------------------
    legs = isin([REAR_L, REAR_R, BLOCK, POLE])
    wet = smooth(0.16, 0.0, y) * legs
    col *= (1 - 0.35 * wet)[..., None]
    mineral = wet * smooth(0.6, 0.8, blur(np.repeat(rng.random((1, SIZE)), SIZE, 0), 1.5)) * smooth(0.0, 0.03, y)
    col = col * (1 - 0.35 * mineral[..., None]) + MINERAL * 0.35 * mineral[..., None]

    # --- towel over the top rail -------------------------------------------------------------------
    inx = smooth(TOWEL_X[0] - 0.003, TOWEL_X[0] + 0.003, x) * smooth(TOWEL_X[1] + 0.003, TOWEL_X[1] - 0.003, x)
    hem_f = TOWEL_FRONT_Y - 0.04 * (x - TOWEL_X[0]) / (TOWEL_X[1] - TOWEL_X[0])
    front = (panel | wings) & (y > hem_f - 0.003)
    behind = back_side & (y > TOWEL_BACK_Y - 0.003)
    tw = (front | behind | rl) & (inx > 0.5)
    d = np.where(front, y - hem_f, np.where(behind, y - TOWEL_BACK_Y, 1.0)) * 100     # cm above the hem
    hem = smooth(1.2, 0.6, d)
    stripe = smooth(0.4, 0.0, np.abs(d - 5.2) - 1.7) + smooth(0.4, 0.0, np.abs(d - 9.0) - 0.6)
    stripe = stripe * front                                    # the striped end hangs at the front
    t = LINEN * (0.95 + 0.06 * grain_f[..., None]) * (1 - 0.08 * hem[..., None])
    t = t * (1 - stripe[..., None] * 0.9) + BRICK * stripe[..., None] * 0.9    # 0.7 mix read pink
    col[tw] = t[tw]
    spec[tw] = 0.05
    gloss[tw] = 0.12
    wood &= ~tw
    # soft shadow under the front hem
    sh = (panel | wings) & ~tw & (inx > 0.5) & (y < hem_f) & (y > hem_f - 0.03)
    col[sh] *= (1 - 0.3 * smooth(hem_f - 0.03, hem_f, y))[sh][:, None]

    col[wood] *= (1 + 0.035 * blotch[wood])[:, None]
    col[iid < 0] = STEAMED * 0.8

    OUT.mkdir(exist_ok=True)
    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    down = lambda im: im.resize((OUT_SIZE, OUT_SIZE), Image.LANCZOS)
    down(Image.fromarray(np.dstack([q(col), np.full((SIZE, SIZE), 255, np.uint8)]), "RGBA")).save(
        OUT / "Chair_blocking_v0_diffuse.png")
    down(Image.fromarray(np.dstack([q(spec), q(spec), q(spec), q(gloss)]), "RGBA")).save(
        OUT / "Chair_blocking_v0_specgloss.png")
    print("done; covered", f"{(iid >= 0).mean():.1%}")


if __name__ == "__main__":
    main()
