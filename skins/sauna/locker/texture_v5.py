"""Sauna Changing Locker v5: v4 with a solid, storytelling middle door (the lock sits on it).

A key lock or code lock is mounted on the middle door (centre about x +2, y 102 cm); v4 cut that
door away, so the lock floated in front of the open niche. v5 keeps the middle door and dresses it
from the Blender bake (door_v5_bake.py -> bake/door_{normal,ao,curvature,id}.png):

  boards, battens  tongue-and-groove linden on darker thermo-linden battens, forged nails
  dials            sauna thermometer and hygrometer: cream faces, ticks and a coloured zone, no digits
  window           frosted, steamed pane with a heart drawn by a finger, drops and runs; glows at night
  map              an island burned into the boards beside the window: coast, river, monuments, a
                   dotted path to an X, a compass star, a rough frame
  lock plate       iron under the lock, key scratches, the wood around it rubbed by hands
  boot print       dried mud from a kick, left of the lock
  broken board     kicked in, splinters; warm light leaks out of the hole at night
  tally            notches carved into the middle batten (days counted)
  leaves, water    birch leaves from a whisk stuck to the wet wood, runs under the sill, damp bottom

    .venv/Scripts/python skins/sauna/locker/texture_v5.py
Writes export/Locker_v5_{diffuse,normal,specgloss,emission}.png and uv/v5_views.png.
"""
import importlib.util
import math
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


v4 = load("locker_v4", "texture_v4.py")
v1, smooth, fbm, hexc, blur = v4.v1, v4.smooth, v4.fbm, v4.hexc, v4.blur
SIZE, BAKE = v4.SIZE, HERE / "bake"
# material ids of door_v5_bake.py (kept literal here: that script needs bpy)
IDS = {"base": 0, "board": 1, "batten": 2, "nail": 3, "frame": 4, "glass": 5, "sill": 6, "plate": 7,
       "screw": 8, "dial_wood": 9, "bezel": 10, "face": 11, "needle": 12, "leaf": 13, "cavity": 14}

SEED = 53
BOARD = 0.5 * (v4.LIME_OLD + v4.LINING) * 1.05
BATTEN = v4.THERMO * 1.12
TRIM = v4.LIME_LIGHT * 0.9
BURN = hexc("#26140A")
MUD = hexc("#4E3B2A")
FROST = np.array([0.86, 0.80, 0.70])
INSIDE = np.array([0.42, 0.27, 0.13])          # what the clear glass shows by day: the warm niche
CREAM = hexc("#E2D6BC")
BRASS = hexc("#9C7A3C")
IRON = hexc("#3B3028")
RUST = hexc("#7A4024")
LEAF_Y, LEAF_G = hexc("#C9A23A"), hexc("#8E9A3A")
LED = v4.LED

# from door_v5_bake.py (cm, OBJ space)
WINDOW = (-24.5, -3.5, 140.0, 187.5)
GLASS = (-21.1, -6.9, 143.4, 184.1)
PLATE = (-8.0, 12.0, 89.0, 115.0)
DIALS = ((-13.3, 208.8), (11.6, 208.8))
DIAL_FACE_R = 5.4
MAP = (1.5, 24.2, 140.5, 188.0)
BOOT = (-18.2, 93.0, 8.0)                      # centre x, y, tilt (deg; toe up, leaning right)
MID_BATTEN = (127.81, 135.91)


def seg_dist(x, y, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = np.clip(((x - ax) * dx + (y - ay) * dy) / max(dx * dx + dy * dy, 1e-9), 0, 1)
    return np.hypot(x - ax - t * dx, y - ay - t * dy)


def line(d, w, soft=0.06):
    return smooth(w + soft, w - soft, d)


def load_bake(name):
    a = np.asarray(Image.open(BAKE / f"door_{name}.png").convert("RGB"), np.float64) / 255.0
    return a


def down2(a):
    """4096 bake -> 2048 texels (box)."""
    if a.shape[0] == SIZE:
        return a
    return a.reshape(SIZE, 2, SIZE, 2, -1).mean((1, 3)).squeeze()


def main():
    m = v4.build()
    pos, nrm, oid, ids, cov, dens = m["pos"], m["nrm"], m["oid"], m["ids"], m["cov"], m["dens"]
    col, nb, spec, gloss, alpha, emit = m["col"], m["nb"], m["spec"], m["gloss"], m["alpha"].copy(), m["emit"]
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    rng = np.random.default_rng(SEED)

    door = (oid == ids["locker_door_b_LOD0"])
    alpha = np.where(door, 1.0, alpha)                       # the middle door stays
    front = door & (nrm[..., 2] > 0.7) & ~m["small"] & (x < 25.8)

    nb_bake = load_bake("normal")
    id_raw = np.asarray(Image.open(BAKE / "door_id.png").convert("RGB"))
    if id_raw.shape[0] != SIZE:
        k = id_raw.shape[0] // SIZE
        id_raw = id_raw[k // 2::k, k // 2::k]
    pid = id_raw[..., 0].astype(int) // 16
    prand = id_raw[..., 1] / 255.0
    ao = down2(load_bake("ao"))[..., 0]
    curv = down2(load_bake("curvature"))[..., 0]
    nbk = down2(nb_bake) * 2 - 1
    nbk /= np.maximum(np.linalg.norm(nbk, axis=-1, keepdims=True), 1e-6)

    def is_(name):
        return front & (pid == IDS[name])

    board, batten, nail, frame, glass, sill = is_("board"), is_("batten"), is_("nail"), is_("frame"), is_("glass"), is_("sill")
    plate, screw, dwood, bezel, face, needle = is_("plate"), is_("screw"), is_("dial_wood"), is_("bezel"), is_("face"), is_("needle")
    # bake rays stop near the low-poly, so most of the hole in the broken board is a miss (id 0)
    leaf = is_("leaf")
    cavity = is_("cavity") | (front & (id_raw[..., 0] < 16) & (x > 16.5) & (y > 60) & (y < 120))
    base = is_("base") & ~cavity
    wood = board | batten | frame | sill | dwood | base

    grain_v = fbm(x * 0.9, y * 0.04, prand * 37, 4, SEED + 1)         # boards, frame stiles: along y
    grain_h = fbm(x * 0.04, y * 0.9, prand * 37, 4, SEED + 2)         # battens: along x
    fine = fbm(x * 6, y * 0.3, z * 6, 3, SEED + 3)
    knots = smooth(0.8, 0.86, fbm(x * 0.5, y * 0.12, prand * 11, 2, SEED + 4))
    h = np.zeros(cov.shape)                                          # decal relief (cm)
    em_k = np.zeros(cov.shape)                                       # door light (0..1, LED colour)

    # ---------------------------------------------------------------- wood
    c = np.zeros(cov.shape + (3,))
    tone = (0.86 + 0.26 * prand)[..., None]
    c = np.where(board[..., None], BOARD * tone * (0.84 + 0.26 * grain_v[..., None]), c)
    c = np.where((batten | dwood)[..., None], BATTEN * tone * (0.84 + 0.26 * grain_h[..., None]), c)
    stile = frame & (np.minimum(np.abs(x - WINDOW[0]), np.abs(x - WINDOW[1])) < 2.7)   # upright frame pieces
    c = np.where((frame | sill)[..., None], TRIM * tone * (0.86 + 0.24 * np.where(stile, grain_v, grain_h)[..., None]), c)
    c = np.where(base[..., None], BATTEN * 0.9, c)
    c = c * (0.95 + 0.08 * fine[..., None])
    c = c * (1 - 0.35 * (knots * board)[..., None])
    # worn edges lighter, crevices darker (curvature), contact shadow (AO)
    edge = np.clip((curv - 0.5) * 4, -1, 1)
    c = c * (1 + 0.22 * np.clip(edge, 0, 1)[..., None] - 0.25 * np.clip(-edge, 0, 1)[..., None])

    # ---------------------------------------------------------------- iron, brass, dials, leaves
    rust = smooth(0.45, 0.7, fbm(x * 0.6, y * 0.6, z, 3, SEED + 5))
    ic = IRON * (0.85 + 0.3 * fine[..., None])
    nrust = np.clip(0.35 + 0.65 * rust, 0, 1)
    ic = ic * (1 - nrust[..., None] * 0.6) + RUST * nrust[..., None] * 0.6
    c = np.where((nail | screw)[..., None], ic, c)
    # the plate: dark iron, rust creeping in from the edges, bright key scratches around the centre
    px0, px1, py0, py1 = PLATE
    dedge = np.minimum.reduce([x - px0, px1 - x, y - py0, py1 - y])
    prust = np.clip(smooth(3.0, 0.0, dedge) * 0.8 + 0.6 * rust + 0.15, 0, 1)
    pc = IRON * 0.9 * (0.9 + 0.2 * fine[..., None])
    pc = pc * (1 - 0.7 * prust[..., None]) + RUST * 0.7 * prust[..., None]
    scratch = np.zeros(cov.shape)
    pcx, pcy = 2.0, 102.0
    for _ in range(24):
        a = rng.uniform(0, math.tau)
        r0 = abs(rng.normal(0, 2.6))
        L = rng.uniform(0.4, 1.6)
        sx, sy = pcx + r0 * math.cos(a), pcy + r0 * math.sin(a) * 1.3
        da = rng.uniform(0, math.tau)
        ex, ey = sx + L * math.cos(da), sy + L * math.sin(da)
        scratch = np.maximum(scratch, line(seg_dist(x, y, sx, sy, ex, ey), 0.04, 0.04) * rng.uniform(0.4, 1.0))
    pc = pc * (1 - 0.6 * scratch[..., None]) + hexc("#B8B4AC") * 0.6 * scratch[..., None]
    c = np.where(plate[..., None], pc, c)
    c = np.where(bezel[..., None], BRASS * (0.8 + 0.4 * fine[..., None]) * (1 - 0.4 * rust[..., None] * 0.5), c)

    # dial faces: ticks over 270 degrees, a coloured zone, no digits
    fc = CREAM * (0.92 + 0.08 * fine[..., None])
    for k, (dx, dy) in enumerate(DIALS):
        rx, ry = x - dx, y - dy
        r = np.hypot(rx, ry)
        ang = np.degrees(np.arctan2(rx, ry))                      # 0 = up, clockwise positive
        on = np.abs(ang) <= 135
        t = (ang + 135) / 270                                     # 0..1 along the scale
        n_t = 40
        tt = t * n_t
        tick = np.abs(tt - np.round(tt)) * (270 / n_t) * np.pi / 180 * r < 0.07
        major = (np.round(tt) % 5 == 0)
        tick_m = on & tick & (((r > 3.75) & (r < 4.9) & major) | ((r > 4.25) & (r < 4.9)))
        zone = on & (r > 3.3) & (r < 3.75) & ((t > 0.68) if k == 0 else ((t > 0.35) & (t < 0.62)))
        ring = np.abs(r - 4.95) < 0.07
        mask = (face & (r < DIAL_FACE_R + 0.3))
        zc = hexc("#A8322A") if k == 0 else hexc("#3C6E8C")
        fc_k = np.where(zone[..., None], zc, fc)
        fc_k = np.where((tick_m | ring)[..., None], hexc("#2A2420"), fc_k)
        fc_k = fc_k * (1 - 0.25 * smooth(4.2, 5.4, r)[..., None])  # aged rim
        c = np.where(mask[..., None], fc_k, c)
    c = np.where(needle[..., None], hexc("#7A1E14"), c)
    lc = np.where((prand > 0.5)[..., None], LEAF_Y, LEAF_G) * (0.85 + 0.3 * fine[..., None])
    c = np.where(leaf[..., None], lc, c)

    # ---------------------------------------------------------------- window: frost, finger heart, drops
    gx0, gx1, gy0, gy1 = GLASS
    hx, hy, hs = -14.0, 167.5, 4.9
    X = (x - hx) / hs
    Y = (y - hy) / hs
    F = (X * X + Y * Y - 1) ** 3 - X * X * Y ** 3
    # distance to the heart curve ~ F / |grad F|
    dFx = 6 * X * (X * X + Y * Y - 1) ** 2 - 2 * X * Y ** 3
    dFy = 6 * Y * (X * X + Y * Y - 1) ** 2 - 3 * X * X * Y * Y
    dh = np.abs(F) / np.maximum(np.hypot(dFx, dFy), 1e-3) * hs
    wobble = 0.08 * fbm(x * 0.8, y * 0.8, 0, 2, SEED + 6)
    stroke = line(dh + wobble, 0.3, 0.1) * glass
    runs = np.zeros(cov.shape)
    for sx, sy0, L in ((hx - 2.9, hy - 2.3, 5.5), (hx + 0.0, hy - 4.8, 8.0), (hx + 3.6, hy - 1.0, 3.2)):
        wv = 0.05 * np.sin(y * 1.7 + sx)
        d = np.abs(x - sx - wv)
        tl = np.clip((sy0 - y) / L, 0, 1)
        runs = np.maximum(runs, line(d, 0.16 * (1 - 0.5 * tl), 0.05) * (y < sy0) * (y > sy0 - L))
        runs = np.maximum(runs, line(np.hypot(x - sx - wv, y - (sy0 - L)), 0.24, 0.06))
    # condensation runs down the lower part of the pane, and beads everywhere
    for _ in range(5):
        sx = rng.uniform(gx0 + 0.8, gx1 - 0.8)
        top = rng.uniform(gy0 + 3, gy0 + 11)
        d = np.abs(x - sx - 0.25 * fbm(y * 0.4 + sx, 0, 0, 2, SEED + 13))
        runs = np.maximum(runs, line(d, 0.09, 0.05) * smooth(gy0, top, y) * smooth(top, top - 2, y) * 0.6)
    beads = np.zeros(cov.shape)
    for _ in range(260):
        bx, by = rng.uniform(gx0, gx1), rng.uniform(gy0, gy1)
        br = rng.uniform(0.06, 0.22)
        beads = np.maximum(beads, line(np.hypot(x - bx, y - by), br, 0.05))
    clear = np.clip(np.maximum(stroke, runs * glass), 0, 1)
    frost_tone = FROST * (0.94 + 0.08 * fbm(x * 0.5, y * 0.5, 1, 3, SEED + 7)[..., None])
    frost_tone = frost_tone * (1 - 0.12 * smooth(gy1 - 6, gy1, y)[..., None])   # steam thicker on top
    gcol = frost_tone * (1 - clear[..., None]) + INSIDE * clear[..., None]
    gcol = gcol * (1 - 0.18 * beads[..., None] * glass[..., None]) + 0.18 * beads[..., None] * np.array([1.0, 0.97, 0.9])
    c = np.where(glass[..., None], gcol, c)
    em_k = np.where(glass, 0.16 + 0.22 * clear + 0.05 * beads, em_k)
    spec = np.where(glass, 0.45, spec)
    gloss = np.where(glass, 0.55 + 0.4 * np.maximum(clear, beads), gloss)
    # window light falling on the sill and the frame's inner edge at night
    near_w = np.exp(-np.maximum.reduce([gx0 - x, x - gx1, gy0 - y, y - gy1, np.zeros_like(x)]) / 1.8)
    sill_glow = (sill | frame) * near_w * 0.08

    # ---------------------------------------------------------------- burned map (right of the window)
    mx0, mx1, my0, my1 = MAP
    cx, cy, Rx, Ry = 12.6, 164.5, 7.6, 15.0
    th = np.arctan2((y - cy) / Ry, (x - cx) / Rx)
    rho = np.hypot((x - cx) / Rx, (y - cy) / Ry)
    rr = 1 + 0.16 * np.sin(3 * th + 1.0) + 0.09 * np.sin(5 * th + 2.2) + 0.05 * np.sin(11 * th + 0.4)
    reff = np.hypot(x - cx, y - cy) / np.maximum(rho, 1e-3)
    dc = (rho - rr) * reff                                           # cm, <0 inside the island
    burn = line(np.abs(dc), 0.17, 0.07)
    # inland hatching along the coast and a second faint contour (hills)
    burn = np.maximum(burn, 0.45 * line(np.abs(dc + 2.2 + 0.4 * np.sin(th * 4)), 0.09, 0.05) * (dc < 0))
    shore = (dc < 0) & (dc > -1.3) & (np.mod(x * 0.9 + y * 0.9, 0.7) < 0.18)
    burn = np.maximum(burn, 0.6 * shore)
    # river from the hills to the west coast
    pts = [(cx + 1.0, cy + 3.0), (cx - 0.8, cy + 1.2), (cx - 1.2, cy - 1.0), (cx - 3.8, cy - 2.4), (cx - 7.6, cy - 3.0)]
    for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
        burn = np.maximum(burn, 0.85 * line(seg_dist(x, y, ax, ay, bx, by), 0.1, 0.05) * (dc < 0.2))
    # monuments: little squares and a ring
    for (qx, qy, s) in ((cx + 2.6, cy + 9.0, 0.55), (cx - 3.0, cy - 8.0, 0.5), (cx + 3.4, cy - 3.5, 0.45)):
        dq = np.maximum(np.abs(x - qx), np.abs(y - qy))
        burn = np.maximum(burn, line(np.abs(dq - s), 0.09, 0.05))
    burn = np.maximum(burn, line(np.abs(np.hypot(x - (cx - 2.2), y - (cy + 6.5)) - 0.6), 0.09, 0.05))
    # a dotted path from the south shore to the X
    ex, ey = cx + 2.4, cy + 2.2
    path = [(cx + 1.2, cy - 14.6), (cx + 2.8, cy - 10.0), (cx + 0.6, cy - 6.0), (cx + 3.6, cy - 1.0), (ex, ey)]
    dots = np.zeros(cov.shape)
    for (ax, ay), (bx, by) in zip(path[:-1], path[1:]):
        L = math.hypot(bx - ax, by - ay)
        for k in range(int(L / 0.85)):
            t = (k + 0.5) * 0.85 / L
            dots = np.maximum(dots, line(np.hypot(x - ax - t * (bx - ax), y - ay - t * (by - ay)), 0.16, 0.05))
    burn = np.maximum(burn, dots)
    xm = np.maximum(line(seg_dist(x, y, ex - 1.1, ey - 1.1, ex + 1.1, ey + 1.1), 0.22, 0.06),
                    line(seg_dist(x, y, ex - 1.1, ey + 1.1, ex + 1.1, ey - 1.1), 0.22, 0.06))
    burn = np.maximum(burn, xm)
    # sea waves
    for (wx, wy) in ((4.0, 150.0), (20.5, 153.5), (5.0, 176.0), (21.5, 170.0), (19.0, 145.0)):
        dw = np.abs(y - wy - 0.3 * np.sin((x - wx) * 2.6))
        burn = np.maximum(burn, 0.8 * line(dw, 0.07, 0.04) * (np.abs(x - wx) < 1.2))
    # compass star top right
    sx, sy = 21.4, 184.0
    for (ax, ay, bx, by, w) in ((sx, sy - 1.8, sx, sy + 2.2, 0.09), (sx - 1.4, sy, sx + 1.4, sy, 0.08)):
        burn = np.maximum(burn, line(seg_dist(x, y, ax, ay, bx, by), w, 0.04))
    arrow = (y > sy + 1.0) & (y < sy + 2.4) & (np.abs(x - sx) < (sy + 2.4 - y) * 0.45)
    burn = np.maximum(burn, arrow.astype(float))
    # rough double frame
    fw = 0.1 + 0.04 * fbm(x * 0.7, y * 0.7, 3, 2, SEED + 8)
    dfr = np.minimum.reduce([np.abs(x - mx0), np.abs(x - mx1), np.abs(y - my0), np.abs(y - my1)])
    inside_r = (x > mx0 - 0.2) & (x < mx1 + 0.2) & (y > my0 - 0.2) & (y < my1 + 0.2)
    dfr2 = np.minimum.reduce([np.abs(x - mx0 - 0.55), np.abs(x - mx1 + 0.55), np.abs(y - my0 - 0.55), np.abs(y - my1 + 0.55)])
    inner_r = (x > mx0 + 0.35) & (x < mx1 - 0.35) & (y > my0 + 0.35) & (y < my1 - 0.35)
    burn = np.maximum(burn, line(dfr, fw, 0.05) * inside_r)
    burn = np.maximum(burn, 0.6 * line(dfr2, 0.06, 0.04) * inner_r)
    in_map = (x > mx0 - 1) & (x < mx1 + 1) & (y > my0 - 1) & (y < my1 + 1)
    burn = burn * (board | batten) * in_map * (0.82 + 0.18 * fbm(x * 2, y * 2, 5, 2, SEED + 9))
    scorch = np.clip(blur(burn, 2.5) * 1.6, 0, 1) * (board | batten)
    c = c * (1 - 0.22 * scorch[..., None])
    c = c * (1 - burn[..., None]) + BURN * burn[..., None]
    h = h - 0.12 * burn

    # ---------------------------------------------------------------- around the lock: rubbed wood, grime
    pr = np.hypot((x - 2.0) / 15.0, (y - 102.0) / 19.0)
    rub = smooth(1.15, 0.7, pr) * board
    c = c * (1 + 0.1 * rub[..., None])
    grime = smooth(1.0, 0.75, pr) * smooth(0.55, 0.8, pr) * board * (0.5 + 0.5 * fbm(x * 0.4, y * 0.4, 7, 3, SEED + 10))
    c = c * (1 - 0.18 * grime[..., None])
    gloss = np.where(front, gloss + 0.1 * rub, gloss)

    # ---------------------------------------------------------------- boot print (dried mud, left of the lock)
    bx, by, tilt = BOOT
    ca, sa = math.cos(math.radians(tilt)), math.sin(math.radians(tilt))
    u = (x - bx) * ca - (y - by) * sa                            # across the sole
    v = (x - bx) * sa + (y - by) * ca                            # heel -14 .. toe +14
    fore = ((u / 5.1) ** 2 + ((v - 6.0) / 8.2) ** 2) < 1
    waist = (np.abs(u + 0.6) < 3.4 + 0.25 * (v + 3)) & (v > -5.0) & (v < 0.5)
    heel = ((u / 4.2) ** 2 + ((v + 10.2) / 4.4) ** 2 < 1) & (v < -6.2)
    sole = fore | waist | heel
    chevron = np.mod(v + 0.55 * np.abs(u) + 0.3 * np.sin(u * 1.3), 1.9) < 0.95
    heel_bars = np.mod(v, 1.4) < 0.75
    rim_f = ((u / 5.1) ** 2 + ((v - 6.0) / 8.2) ** 2) > 0.82
    rim_h = ((u / 4.2) ** 2 + ((v + 10.2) / 4.4) ** 2) > 0.78
    tread = (fore & (chevron | rim_f)) | (heel & (heel_bars | rim_h)) | (waist & (np.mod(v, 2.2) < 0.5))
    erode = fbm(x * 0.9, y * 0.9, 2, 3, SEED + 11) + 0.25 * smooth(-14, 10, v)          # more mud at the toe
    mud = (sole & tread).astype(float) * smooth(0.36, 0.56, erode) * (0.55 + 0.45 * fbm(x * 3, y * 3, 4, 2, SEED + 14))
    for _ in range(40):                                                                 # flecks thrown off
        fx, fy = bx + rng.normal(0, 4.5), by + rng.normal(4, 7)
        mud = np.maximum(mud, line(np.hypot(x - fx, y - fy), rng.uniform(0.05, 0.25), 0.05) * 0.8)
    mud = blur(mud, 0.9) * (board | batten | base)
    c = c * (1 - 0.75 * mud[..., None]) + MUD * 0.75 * mud[..., None] * (0.9 + 0.2 * fine[..., None])
    h = h + 0.05 * mud
    gloss = np.where(front, gloss - 0.08 * mud, gloss)

    # ---------------------------------------------------------------- tally notches on the middle batten
    b0, b1 = MID_BATTEN
    notch = np.zeros(cov.shape)
    nx0 = 5.0
    marks = []
    for g in range(3):
        gx = nx0 + g * 5.2
        for k in range(4):
            xx = gx + k * 0.85 + rng.uniform(-0.1, 0.1)
            marks.append((xx, b0 + 1.6, xx + rng.uniform(-0.2, 0.2), b1 - 1.6))
        marks.append((gx - 0.4, b0 + 2.0, gx + 3.0, b1 - 2.2))
    for k in range(2):
        xx = nx0 + 3 * 5.2 + k * 0.85
        marks.append((xx, b0 + 1.6, xx + 0.1, b1 - 1.6))
    for (ax, ay, bx2, by2) in marks:
        d = seg_dist(x, y, ax, ay, bx2, by2)
        notch = np.maximum(notch, line(d, 0.16, 0.05))
    notch = notch * batten
    c = c * (1 - 0.6 * notch[..., None]) + hexc("#3A2412") * 0.6 * notch[..., None]
    h = h - 0.25 * notch

    # ---------------------------------------------------------------- water: runs under the sill, damp bottom
    wx0, wx1, wy0, _ = WINDOW
    runs_w = np.zeros(cov.shape)
    for _ in range(9):
        sx = rng.uniform(wx0, wx1)
        L = rng.uniform(5, 14)
        d = np.abs(x - sx - 0.15 * np.sin(y * 0.7 + sx))
        runs_w = np.maximum(runs_w, line(d, rng.uniform(0.25, 0.6), 0.25) * smooth(wy0 - 2.4 - L, wy0 - 3.0, y) * (y < wy0 - 2.4))
    damp = smooth(64, 49, y + 5 * fbm(x * 0.3, y * 0.1, 1, 3, SEED + 12))
    wet = np.clip(np.maximum(runs_w * 0.7, damp * 0.8), 0, 1) * (board | batten | base)
    c = c * (1 - 0.3 * wet[..., None])
    gloss = np.where(front, gloss + 0.15 * wet, gloss)

    # ---------------------------------------------------------------- broken board: the dark inside, and its light
    cav_light = np.exp(-((x - 21.3) ** 2 / (2 * 3.0 ** 2) + (y - 92.0) ** 2 / (2 * 12.0 ** 2)))
    c = np.where(cavity[..., None], hexc("#120A05") * (1 + 1.2 * cav_light[..., None]), c)
    em_k = np.where(cavity, 0.03 + 0.20 * cav_light ** 2, em_k)
    # splinter ends near the hole: fresh, lighter wood
    fresh = board & (x > 16.8) & (((y > 66) & (y < 83)) | ((y > 98) & (y < 116))) & (np.clip(edge, 0, 1) > 0.1)
    c = np.where(fresh[..., None], c * 1.25, c)

    # ---------------------------------------------------------------- AO, spec/gloss per material
    c = c * np.where(cavity, 1.0, 0.55 + 0.45 * ao)[..., None]
    sp = np.where(wood, 0.06, 0.06)
    gl = np.where(wood, 0.2, 0.2)
    sp = np.where(nail | screw, 0.22 - 0.12 * rust, sp)
    gl = np.where(nail | screw, 0.35 - 0.2 * rust, gl)
    sp = np.where(plate, 0.2 - 0.12 * prust + 0.25 * scratch, sp)
    gl = np.where(plate, 0.32 - 0.2 * prust + 0.2 * scratch, gl)
    sp = np.where(bezel, 0.6, sp)
    gl = np.where(bezel, 0.62, gl)
    sp = np.where(face | needle, 0.35, sp)
    gl = np.where(face | needle, 0.78, gl)                         # under the dial glass
    sp = np.where(leaf, 0.05, sp)
    gl = np.where(leaf, 0.4, gl)
    sp = np.where(cavity, 0.02, sp)
    gl = np.where(cavity, 0.05, gl)
    door_front_nonglass = front & ~glass
    spec = np.where(door_front_nonglass, sp, spec)
    gloss = np.where(door_front_nonglass, gl + np.where(wood, gloss - m["gloss"], 0), gloss)
    gloss = np.clip(gloss, 0, 1)

    col = np.where(front[..., None], c, col)

    # ---------------------------------------------------------------- normal: bake + decal relief
    group = (door * 2 + front).astype(np.int16)
    nh = v1.height_to_normal(h, pos, dens, group, k=1.0)
    nd = np.stack([nbk[..., 0] + nh[..., 0], nbk[..., 1] + nh[..., 1], nbk[..., 2] * nh[..., 2]], -1)
    nd /= np.linalg.norm(nd, axis=-1, keepdims=True)
    nd = np.where(cavity[..., None], np.array([0, 0, 1.0]), nd)
    nb = np.where(front[..., None], nd, nb)

    # ---------------------------------------------------------------- emission: the door's own light
    door_emit = em_k[..., None] * LED + (sill_glow[..., None] * c * v4.WARM)
    emit = np.where(front[..., None], door_emit, emit)

    out = dict(m, col=col, nb=nb, spec=spec, gloss=gloss, alpha=alpha)
    v1.save(out, "v5")
    v4.save_emission(emit, "v5")

    # Solid fallback for curators (no alpha cuts on left/right doors)
    m1 = v1.build()
    left_right = (oid == ids["locker_door_a_LOD0"]) | (oid == ids["locker_door_c_LOD0"])
    col_solid = np.where(left_right[..., None], m1["col"], col)
    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    full = np.full((SIZE, SIZE), 255, np.uint8)
    Image.fromarray(np.dstack([q(col_solid), full]), "RGBA").save(v1.OUT / "Locker_v5_diffuse_solid.png")
    print("saved Locker_v5_diffuse_solid.png")
    print("done; door front", int(front.sum()), {k: int(is_(k).sum()) for k in IDS})


if __name__ == "__main__":
    main()
