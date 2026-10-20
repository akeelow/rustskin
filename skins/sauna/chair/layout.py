"""Sauna Chair: where the details are. Shared by bake_chair.py (Blender) and texture_v1.py (.venv),
so the modelled slats, boards, towel and nails and the painted wear line up.

Centimetres, the OBJ's axes scaled by 100: x = width (+x right, seen from the front), y = height,
z = depth (+z front). Functions take floats or numpy arrays.
"""
import random

import numpy as np

SEED = 21

# ---------------------------------------------------------------- seat: 6 aspen slats across (along x)
SEAT_Z = (-23.0, 31.6)           # seat top z -22.4..31.0, a little over so the slats reach the rim
SEAT_X = (-31.0, 26.0)           # wider than the seat (x -29.3..24.0); rays that miss leave no slat
SEAT_GAP = 0.45
FRONT = 5                        # slat index of the front slat (slats go from the back, -z)


def _edges(lo, hi, n, wmin, wmax, seed):
    rng = random.Random(seed)
    w = [rng.uniform(wmin, wmax) for _ in range(n)]
    k = (hi - lo) / sum(w)
    out, a = [], lo
    for wi in w:
        out.append((a, a + wi * k))
        a += wi * k
    return out


SLATS = _edges(*SEAT_Z, 6, 8.2, 9.6, SEED)

# ---------------------------------------------------------------- backrest: narrow vertical lining boards
PANEL_X = (-20.6, 20.6)          # panel front |x| < 20.5; outside it the curved side wings (bent frame)
PANEL_Y = (52.0, 113.0)
PANEL_GAP = 0.18                 # V-groove: chamfers 0.3 + a hairline gap
BOARDS = _edges(*PANEL_X, 6, 6.2, 7.2, SEED + 1)
BATTENS = ((60.0, 65.5), (84.0, 89.5))      # two cross battens on the back, y bands (the upper one
                                            # below the towel's back hem: at 96.5 it poked through)
BATTEN_X = (-22.0, 22.0)

# ---------------------------------------------------------------- towel over the top rail
TOWEL_X = (-19.0, 12.0)          # 31 cm wide (folded in half lengthwise), a little left of centre
TOWEL_FRONT = 79.0               # hem height on the front at the left edge; the right edge hangs 4 cm lower
TOWEL_BACK = 94.0
RAIL_AXIS = (109.0, -32.8)       # (y, z) of a line through the top rail: the towel wraps round it
FOLD_L = 7.6                     # drape folds across the front hang


def folds(x):
    """Drape folds across the hanging front, 0..1 (1 = the fold bulges out)."""
    t = (x - TOWEL_X[0]) / FOLD_L
    return 0.5 + 0.5 * np.sin(2 * np.pi * (t + 0.18 * np.sin(t * 1.7 + 0.6)) + 0.9)


def hem_front(x):
    """y of the front hem: slanted, a little lower under each fold."""
    t = (x - TOWEL_X[0]) / (TOWEL_X[1] - TOWEL_X[0])
    return TOWEL_FRONT - 4.0 * t - 0.7 * folds(x)


def hem_back(x):
    return TOWEL_BACK - 0.4 * folds(x * 1.3 + 3.0)


def towel_stripes(d):
    """Brick stripes on the front end by distance d (cm) above the hem: wide 3.4 cm + narrow 1.2 cm."""
    wide = np.clip((1.7 - np.abs(d - 5.4)) / 0.25, 0, 1)
    narrow = np.clip((0.6 - np.abs(d - 9.2)) / 0.2, 0, 1)
    return np.clip(wide + narrow, 0, 1)


# ---------------------------------------------------------------- seat details
RING_C, RING_R = (9.0, 7.0), 12.5            # wet ring from the wash basin (x, z), radius
CRACK_X = (-29.5, -14.5)                     # crack in the front slat from its left end
STAPLE_X = -21.5                             # staple across the crack


def crack_z(x):
    z0, z1 = SLATS[FRONT]
    return (z0 + z1) / 2 + 0.6 + 0.25 * np.sin(x * 0.9) + 0.1 * np.sin(x * 3.1)


def seat_nails():
    """Forged nails into the side rails: two per slat near each end (x -25.5 / +21.0), a few missing."""
    rng = random.Random(SEED + 5)
    out = []
    for i, (z0, z1) in enumerate(SLATS):
        for xs in (-25.5, 21.0):
            for j in (-1, 1):
                if rng.random() < 0.15:
                    continue
                out.append((xs + rng.uniform(-0.6, 0.6), (z0 + z1) / 2 + j * (z1 - z0) * 0.24 + rng.uniform(-0.4, 0.4)))
    return out


def batten_nails():
    """One nail per lining board in each batten, on the back."""
    rng = random.Random(SEED + 6)
    return [((x0 + x1) / 2 + rng.uniform(-0.8, 0.8), (y0 + y1) / 2 + rng.uniform(-0.6, 0.6))
            for (y0, y1) in BATTENS for (x0, x1) in BOARDS]


# ---------------------------------------------------------------- shovel-handle leg and its wire
POLE_BOTTOM = (-28.5, 3.6, 28.4)             # axis point (x, y, z) at the bottom of the round leg
POLE_TOP = (-26.25, 42.0, 26.4)
WIRE_Y = (1.2, 10.5)                         # wrapped over the split end, down onto the old rubber tip
WIRE_R, WIRE_PITCH = 0.12, 0.34


def pole_axis(y):
    t = (y - POLE_BOTTOM[1]) / (POLE_TOP[1] - POLE_BOTTOM[1])
    return tuple(a + (b - a) * t for a, b in zip(POLE_BOTTOM, POLE_TOP))
