"""Colour blocking v0 for Sauna Changing Locker (Locker).

The three grey steel lockers become a wooden changing-room locker: everything metal turns into
vertical aspen slats 7.5 cm wide (continuous across UV seams: each texel is mapped to its 3D
point), the doors fresh light aspen, the carcass a shade darker from steam; the original's
wooden middle door and drawer stay wood, steam-darkened; small parts (hinges, latch, lever
handles) and the feet become rusty iron. The original's vents, rivets and grime are kept from
its luminance at low contrast. Normal and AO stay original for now.

Model units are centimetres (3ds Max export): x -90..90, y 0..224 up, +z front.

    .venv/Scripts/python skins/sauna/locker/blocking.py
Writes export/Locker_blocking_v0_{diffuse,specgloss}.png and uv/blocking_v0_views.png.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
from uv_zones import load_obj, normal, read_png, render_views  # noqa: E402

ORIG = HERE / "originals"
OUT = HERE / "export"
SIZE = 2048
SEED = 3
SLAT = 7.5          # cm


def hexc(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float64) / 255.0


ASPEN = hexc("#C2A77E")      # fresh aspen (set palette)
STEAMED = hexc("#9A7A55")    # carcass, a shade darker
OLD = hexc("#7A5A3C")        # steam-darkened (set palette): the original wooden door/drawer
GAP = hexc("#2A2018")
IRON = hexc("#2E2A27")
RUST = hexc("#8C4A26")


def blur(a, r):
    f = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
    return np.asarray(f, np.float64) / 255.0


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def position_map(V, T, F):
    """3D point and face normal per texel covered by the UV layout (+ a 4-texel gutter)."""
    pos = np.zeros((SIZE, SIZE, 3))
    nrm = np.zeros((SIZE, SIZE, 3))
    cov = np.zeros((SIZE, SIZE), bool)
    Va, Ta = np.array(V), np.array(T)
    for vi, ti in F:
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
        ys, xs = np.nonzero(m)
        pos[ys + y0, xs + x0] = p3[m]
        nrm[ys + y0, xs + x0] = normal(*P)
        cov[ys + y0, xs + x0] = True
    for _ in range(4):
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            take = ~cov & np.roll(np.roll(cov, dy, 0), dx, 1)
            pos[take] = np.roll(np.roll(pos, dy, 0), dx, 1)[take]
            nrm[take] = np.roll(np.roll(nrm, dy, 0), dx, 1)[take]
            cov |= take
    return pos, nrm, cov


def hash1(a, seed):
    a = a.astype(np.int64).astype(np.uint32) * np.uint32(2654435761) ^ np.uint32(seed * 97531)
    a ^= a >> np.uint32(15)
    a *= np.uint32(2246822519)
    a ^= a >> np.uint32(13)
    return a.astype(np.float64) / 2 ** 32


def main():
    V, T, F = load_obj(ORIG / "locker.obj")
    N = [normal(*(V[i] for i in vi)) for vi, _ in F]
    pos, nrm, cov = position_map(V, T, F)
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    rng = np.random.default_rng(SEED)

    bc = np.asarray(Image.open(ORIG / "locker_bc.png").convert("RGB"), np.float64) / 255.0
    lum = bc @ np.array([0.299, 0.587, 0.114])
    sg = np.asarray(Image.open(ORIG / "locker_sg.png").convert("RGBA"), np.float64) / 255.0
    detail = np.clip(lum / np.maximum(blur(lum, 12), 1e-3), 0.45, 1.4)
    detail = 1 + 0.6 * (detail - 1)

    # classes
    yy = np.arange(SIZE)[:, None].repeat(SIZE, 1)
    xx = np.arange(SIZE)[None, :].repeat(SIZE, 0)
    small = (yy < 205) & (xx < 1370)                          # hinges, latch, lever handles, bolts
    feet = cov & (y < 9)
    old_wood = cov & (blur(sg[..., 0], 4) < 0.3) & ~small     # the original's wooden door and drawer
    iron = cov & (small | feet)
    wood = cov & ~iron & ~old_wood
    door = (z > 22) & (np.abs(nrm[..., 2]) > 0.5)             # front faces of the three doors

    # vertical slats on walls and doors; along x on the top
    an = np.abs(nrm)
    h = np.where(an[..., 1] > 0.7, x, np.where(an[..., 2] >= an[..., 0], x, z))
    hb = (h + 300) / SLAT
    board = np.floor(hb)
    fr = hb - board
    gap = 1 - smooth(0.0, 0.07, fr) * smooth(1.0, 0.93, fr)
    tone = hash1(board + 1000 * (an[..., 2] < an[..., 0]), SEED)
    grain = blur(rng.random((SIZE, SIZE)), 0.8)
    streak = blur(rng.random((SIZE, SIZE)), 3)
    steam = smooth(150, 220, y) * 0.18 + smooth(40, 0, y) * 0.22   # top and bottom darker

    base = np.where(door[..., None], ASPEN, STEAMED)
    col = base * (0.86 + 0.24 * tone[..., None]) * (0.9 + 0.12 * grain[..., None] + 0.08 * streak[..., None])
    col = col * (1 - steam[..., None]) * detail[..., None]
    col = col * (1 - gap[..., None]) + GAP * gap[..., None]

    ow = OLD[None, None, :] * (0.85 + 0.3 * (lum / np.maximum(blur(lum, 30), 1e-3) - 1) + 0.15)[..., None]
    col = np.where(old_wood[..., None], ow * (1 - steam[..., None]), col)

    rust = smooth(0.55, 0.7, blur(rng.random((SIZE, SIZE)), 5))
    ic = (IRON * (1 - rust[..., None]) + RUST * rust[..., None]) * (0.7 + 0.6 * lum[..., None])
    col = np.where(iron[..., None], ic, col)
    col[~cov] = STEAMED * 0.8

    spec = np.where(iron, 0.35 - 0.2 * rust, 0.07)
    gloss = np.where(iron, 0.42 - 0.25 * rust, 0.22 + 0.08 * old_wood)

    OUT.mkdir(exist_ok=True)
    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    full = np.full((SIZE, SIZE), 255, np.uint8)
    out = OUT / "Locker_blocking_v0_diffuse.png"
    Image.fromarray(np.dstack([q(col), full]), "RGBA").save(out)
    Image.fromarray(np.dstack([q(spec), q(spec), q(spec), q(gloss)]), "RGBA").save(OUT / "Locker_blocking_v0_specgloss.png")
    render_views(V, T, F, N, HERE / "uv" / "blocking_v0_views.png", tex=read_png(out))
    print("done; wood", f"{wood.mean():.1%}", "old wood", f"{old_wood.mean():.1%}", "iron", f"{iron.mean():.1%}")


if __name__ == "__main__":
    main()
