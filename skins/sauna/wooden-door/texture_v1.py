"""Sauna Door v1: texture maps from the bake (bake_door.py) + palette and wear by the door's story.

Story: the door of a steam room built from scrap. Aspen boards nailed onto an old steel sheet.
  front (changing room)  pale, dry, grey-honey aspen; the lowest part and the boards round the handle
                         dark from steam and hands; rust runs under every nail; water and white mineral
                         streaks at the bottom and under the sill; a washed-out towel with a brick stripe
  back  (steam room)     the same boards steamed brown, darker towards the top, soot under the top rail;
                         rails and braces worn lighter on the edges; mineral streaks under the window
  window                 fogged glass with runs, a warm glow behind it, brighter at the bottom (emission)

Geometry (boards, gaps, rails, frame, sill, towel folds, nails, hinges, wire, leaf) comes from the
bake: normal, AO, curvature and ID. Drawn here in 2D, per texel from its 3D point: wood grain and
knots, the towel's weave, stains, streaks, soot, the fog and runs on the glass.
The handle (two small islands shared by both sides) keeps the original maps, re-tinted.

Inputs: bake/door_{normal,ao,curvature,id}.png, bake/layout.json, originals/*.
Outputs: export/Door_v1_{diffuse,normal,specgloss}.png (2048), _occlusion.png, _emission.png (1024).

    .venv/Scripts/python skins/sauna/wooden-door/texture_v1.py
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "uv"))
import analyze_uv as A  # noqa: E402

BAKE, ORIG, OUT = HERE / "bake", HERE / "originals", HERE / "export"
N, OUT_N = 4096, 2048
VERSION = "v1"
SEED = 21
IDS = {"steel": 1, "board_f": 2, "board_b": 3, "rail": 4, "brace": 5, "nail": 6, "frame": 7, "sill": 8,
       "glass": 9, "towel": 10, "stripe": 11, "hook": 12, "leaf": 13, "hinge": 14, "wire": 15}
HANDLE_ISLANDS = (8, 9)
FRONT_ISLAND = 2


def hexc(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255.0


# set palette (skins/sauna/README.md); ASPEN / ASPEN_GREY are the set's wood as tuned on the bench and chair
ASPEN = hexc("#A39176")
ASPEN_GREY = hexc("#958B7E")
ASPEN_FRESH = hexc("#C2A77E")
STEAMED = hexc("#7A5A3C")
SMOKED = hexc("#45332A")
SOOT = hexc("#241D1A")
LINEN = hexc("#CFC6B4")
BRICK = hexc("#8E3A30")
RUST = hexc("#8C4A26")
IRON = hexc("#2E2A27")
MINERAL = hexc("#D9D4C8")
GLOW_CORE = hexc("#FF6A1F")
GLOW_EDGE = hexc("#FFB347")
LEAF = hexc("#5C6A39")
LEAF_DRY = hexc("#8F7B34")
HANDLE = hexc("#5E4A38")


# ---------------------------------------------------------------- noise
def hash1(a, seed):
    a = a.astype(np.int64).astype(np.uint32) * np.uint32(2654435761) ^ np.uint32(seed * 97531)
    a ^= a >> np.uint32(15)
    a *= np.uint32(2246822519)
    a ^= a >> np.uint32(13)
    return (a.astype(np.float64) / 2 ** 32).astype(np.float32)


def vnoise(u, v, seed):
    iu, iv = np.floor(u), np.floor(v)
    fu, fv = (u - iu).astype(np.float32), (v - iv).astype(np.float32)
    fu, fv = fu * fu * (3 - 2 * fu), fv * fv * (3 - 2 * fv)
    iu, iv = iu.astype(np.int64), iv.astype(np.int64)

    def h(a, b):
        return hash1((a * 92837111 + b * 689287499) & 0x7FFFFFFF, seed)

    return ((h(iu, iv) * (1 - fu) + h(iu + 1, iv) * fu) * (1 - fv)
            + (h(iu, iv + 1) * (1 - fu) + h(iu + 1, iv + 1) * fu) * fv)


def fbm(u, v, seed, octaves=3):
    out, amp, tot = 0.0, 1.0, 0.0
    for o in range(octaves):
        out = out + amp * vnoise(u * 2 ** o, v * 2 ** o, seed + o * 13)
        tot += amp
        amp *= 0.5
    return out / tot


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def mix(a, b, t):
    t = np.asarray(t, np.float32)[..., None]
    return a * (1 - t) + b * t


# ---------------------------------------------------------------- texel -> 3D point
def texel_points():
    """Per texel: island id (-1 outside), 3D point, and the face normal's z."""
    P, T, VI = A.load()
    isl_of = A.islands(VI)
    isl = np.full((N, N), -1, np.int16)
    pos = np.zeros((N, N, 3), np.float32)
    nz = np.zeros((N, N), np.float32)
    fn = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    fn /= np.linalg.norm(fn, axis=1)[:, None] + 1e-12
    for k in range(len(T)):
        p = T[k] * N
        x0, x1 = int(np.floor(p[:, 0].min())), int(np.ceil(p[:, 0].max()))
        y0, y1 = int(np.floor(p[:, 1].min())), int(np.ceil(p[:, 1].max()))
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        d = (p[1, 1] - p[2, 1]) * (p[0, 0] - p[2, 0]) + (p[2, 0] - p[1, 0]) * (p[0, 1] - p[2, 1])
        if abs(d) < 1e-9:
            continue
        a = ((p[1, 1] - p[2, 1]) * (xs - p[2, 0]) + (p[2, 0] - p[1, 0]) * (ys - p[2, 1])) / d
        b = ((p[2, 1] - p[0, 1]) * (xs - p[2, 0]) + (p[0, 0] - p[2, 0]) * (ys - p[2, 1])) / d
        m = (a >= -1e-4) & (b >= -1e-4) & (a + b <= 1 + 1e-4)
        yy, xx = (ys[m] - 0.5).astype(int), (xs[m] - 0.5).astype(int)
        ok = (yy >= 0) & (yy < N) & (xx >= 0) & (xx < N)
        yy, xx, aa, bb = yy[ok], xx[ok], a[m][ok], b[m][ok]
        rows = N - 1 - yy                                    # image row 0 is v = 1
        pos[rows, xx] = (aa[:, None] * P[k, 0] + bb[:, None] * P[k, 1] + (1 - aa - bb)[:, None] * P[k, 2])
        isl[rows, xx] = isl_of[k]
        nz[rows, xx] = fn[k, 2]
    return isl, pos, nz


def load(name):
    return np.asarray(Image.open(BAKE / f"door_{name}.png").convert("RGB"), np.float32) / 255.0


def dilate(img, mask, steps):
    """Fill texels outside the islands from their neighbours (padding against seams)."""
    img, mask = img.copy(), mask.copy()
    for _ in range(steps):
        acc = np.zeros_like(img)
        cnt = np.zeros(mask.shape, np.float32)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            sm = np.roll(mask, (dy, dx), (0, 1))
            acc += np.roll(img, (dy, dx), (0, 1)) * sm[..., None]
            cnt += sm
        new = (~mask) & (cnt > 0)
        img[new] = acc[new] / cnt[new][:, None]
        mask |= new
    return img


def sample(canvas, x, y, x0, y0, scale):
    """Bilinear lookup of a door-space canvas (row 0 at y0, y up)."""
    u = np.clip((x - x0) * scale, 0, canvas.shape[1] - 1.001)
    v = np.clip((y - y0) * scale, 0, canvas.shape[0] - 1.001)
    iu, iv = u.astype(int), v.astype(int)
    fu, fv = u - iu, v - iv
    return (canvas[iv, iu] * (1 - fu) * (1 - fv) + canvas[iv, iu + 1] * fu * (1 - fv)
            + canvas[iv + 1, iu] * (1 - fu) * fv + canvas[iv + 1, iu + 1] * fu * fv)


def nail_runs(nails, length, rng):
    """Door-space canvas (1 px = 1 mm): a halo round every nail and a run of rusty water below it."""
    x0, y0, sc = -1.215, -0.005, 1000.0
    c = np.zeros((2125, 1220), np.float32)
    for (nx, ny) in nails:
        L = length * rng.uniform(0.5, 1.5)
        cx, cy = (nx - x0) * sc, (ny - y0) * sc
        w = rng.uniform(2.2, 3.6)
        ys = np.arange(int(cy - L * sc), int(cy + 14))
        xs = np.arange(int(cx - 14), int(cx + 15))
        ys, xs = ys[(ys >= 0) & (ys < c.shape[0])], xs[(xs >= 0) & (xs < c.shape[1])]
        gx, gy = np.meshgrid(xs, ys)
        below = np.clip((cy - gy) / (L * sc), 0, 1)
        run = np.exp(-((gx - cx - 1.5 * np.sin(gy * 0.07 + nx * 50)) / w) ** 2) * (1 - below) ** 1.4 * (gy <= cy)
        halo = np.exp(-(((gx - cx) ** 2 + (gy - cy) ** 2) / 9.0 ** 2))
        c[np.ix_(ys, xs)] = np.maximum(c[np.ix_(ys, xs)], np.maximum(run * 0.9, halo))
    return c, x0, y0, sc


def knots(xs_boards, rng, per_board=(0, 3)):
    out = []
    for (s0, s1) in xs_boards:
        for _ in range(rng.integers(per_board[0], per_board[1] + 1)):
            out.append((rng.uniform(s0 + 0.02, s1 - 0.02), rng.uniform(0.08, 2.05), rng.uniform(0.007, 0.016)))
    return out


# ---------------------------------------------------------------- main
def build():
    rng = np.random.default_rng(SEED)
    lay = json.loads((BAKE / "layout.json").read_text())
    isl_img, pos_img, nz_img = texel_points()
    M = isl_img >= 0
    nrm_b, ao_b, cur_b, id_b = load("normal"), load("ao")[..., 0], load("curvature")[..., 0], load("id")

    x, y, z = (pos_img[M][:, i] for i in range(3))
    isl = isl_img[M]
    mid = np.rint((id_b[M][:, 0] * 255 - 8) / 16).astype(int)
    rnd = id_b[M][:, 1]
    ao, cur = ao_b[M], cur_b[M]
    front = isl == FRONT_ISLAND
    handle = np.isin(isl, HANDLE_ISLANDS)
    is_ = {k: mid == v for k, v in IDS.items()}
    wood_f = is_["board_f"] | ((is_["frame"] | is_["sill"]) & front)
    wood_b = is_["board_b"] | is_["rail"] | is_["brace"] | ((is_["frame"] | is_["sill"]) & ~front)
    wood = wood_f | wood_b

    wx0, wx1, wy0, wy1 = lay["window"]
    slat = lay["slat"]
    px0, px1, py0, py1 = wx0 + slat, wx1 - slat, wy0 + slat, wy1 - slat          # the pane

    # ---- grain: along the board. boards and side slats run in y, rails / sill / top and bottom slats in x,
    # braces along their own slope
    along, across = y.copy(), x.copy()
    horiz = is_["rail"] & ~((x < -0.97) & (y < 0.97)) | is_["sill"] | (is_["frame"] & ((y < py0) | (y > py1)))
    along[horiz], across[horiz] = x[horiz], y[horiz]
    d = np.array([-0.369, 0.645]) / np.hypot(0.369, 0.645)
    br = is_["brace"]
    along[br], across[br] = x[br] * d[0] + y[br] * d[1], x[br] * d[1] - y[br] * d[0]
    off = rnd * 37.0
    warp = 0.004 * (vnoise(along * 3.0 + off, across * 14.0, 5) - 0.5)
    g1 = vnoise(along * 4.0 + off, (across + warp) * 150.0, 1)
    g2 = vnoise(along * 11.0 + off, (across + warp) * 420.0, 2)
    g3 = vnoise(along * 1.3 + off, (across + warp) * 38.0, 3)                    # broad bands of early / late wood
    grain = 0.45 * g1 + 0.25 * g2 + 0.30 * g3                                     # 0..1
    blotch = fbm(x * 7.0 + off, y * 3.0, 9)

    col = np.zeros((len(x), 3), np.float32)
    gloss = np.full(len(x), 0.16, np.float32)
    spec = np.full(len(x), 0.05, np.float32)
    height = np.zeros(len(x), np.float32)          # micro relief for the normal map (grain, weave)

    # ---------------- front wood
    tone = mix(mix(ASPEN_GREY, ASPEN, np.clip(rnd * 1.4, 0, 1)), ASPEN_FRESH, np.clip(rnd - 0.6, 0, 1) * 0.9)
    cf = tone * (0.80 + 0.36 * grain)[:, None] * (0.93 + 0.14 * blotch)[:, None]
    # steam and water: the lowest part of the door is dark, with a ragged upper edge on every board
    level = 0.36 + 0.16 * (vnoise(x * 9.0, x * 0 + 1.0, 31) - 0.5) + (rnd - 0.5) * 0.16
    yy = y + 0.07 * (vnoise(x * 160.0, y * 5.0, 32) - 0.5)
    wet = smooth(level + 0.09, level - 0.06, yy)
    damp = smooth(1.05, 0.25, y) * 0.22
    WET = STEAMED * 0.6 + SMOKED * 0.25 + ASPEN_GREY * 0.15            # wet aspen: brown-grey, not orange
    cf = mix(cf, WET * (0.82 + 0.3 * grain)[:, None], np.clip(wet * 0.9 + damp, 0, 1))
    cf = mix(cf, SMOKED * 1.05, smooth(0.16, 0.0, y) * 0.55)
    # hands: the boards round the handle and a smear below it
    hx, hy = -1.075, 1.065
    hand = np.exp(-(((x - hx) / 0.085) ** 2 + ((y - hy) / 0.13) ** 2))
    smear = np.exp(-((x - hx - 0.01) / 0.05) ** 2) * smooth(0.55, 1.0, y) * (y < hy) * 0.7
    grime = np.clip(np.maximum(hand, smear) * (0.75 + 0.5 * blotch), 0, 1) * 0.62
    cf = mix(cf, STEAMED * 0.80, grime)
    # water runs from the sill
    under = smooth(wx0 - 0.03, wx0 + 0.02, x) * smooth(wx1 + 0.04, wx1 - 0.01, x) * (y < wy0 - lay["sill_h"])
    runs = (vnoise(x * 230.0, y * 2.0, 41) > 0.62) * under * smooth(0.55, wy0, y) ** 1.5
    cf = mix(cf, STEAMED * 0.9, np.clip(under * smooth(0.95, wy0, y) * 0.25 + runs * 0.3, 0, 1))
    # white mineral streaks in the wet zone and under the sill
    sx = vnoise(x * 330.0, y * 1.5, 43)
    streak = smooth(0.74, 0.86, sx) * vnoise(x * 500.0, y * 30.0, 44)
    env = smooth(0.02, 0.10, y) * smooth(level + 0.12, level - 0.12, y) * (0.4 + 0.6 * vnoise(x * 14.0, y * 0, 45))
    env = np.maximum(env, under * smooth(0.75, wy0 - 0.03, y) * 0.7 * (vnoise(x * 120.0, y * 0, 46) > 0.5))
    mineral_f = np.clip(streak * env * 1.6, 0, 1)
    cf = mix(cf, MINERAL, mineral_f * 0.62)
    # frame and sill: the same aspen, greyer and more weathered
    fr = (is_["frame"] | is_["sill"]) & front
    cf[fr] = mix(cf[fr], ASPEN_GREY * (0.85 + 0.3 * grain[fr])[:, None], 0.55)
    # rust runs under the nails
    canvas, cx0, cy0, sc = nail_runs(lay["nails"]["front"], 0.055, rng)
    run = sample(canvas, x, y, cx0, cy0, sc)
    cf = mix(cf, RUST * 0.85, np.clip(run, 0, 1) * 0.6)
    col[wood_f] = cf[wood_f]
    gloss[wood_f] = (0.17 + 0.07 * grain + 0.30 * wet + 0.25 * grime)[wood_f]

    # ---------------- back wood: steamed, darker towards the top, soot under the top rail
    up = smooth(0.15, 2.05, y)
    tone = mix(STEAMED * 1.02, SMOKED * 1.12, up ** 0.85) * (0.86 + 0.28 * rnd)[:, None]
    planks = is_["rail"] | is_["brace"]
    tone[planks] *= 1.13
    fb = (is_["frame"] | is_["sill"]) & ~front
    tone[fb] = mix(STEAMED * 1.15, SMOKED * 1.3, up[fb] * 0.6)
    cb = tone * (0.74 + 0.5 * grain)[:, None] * (0.9 + 0.2 * blotch)[:, None]
    soot = np.clip(smooth(1.45, 2.08, y) * (0.45 + 0.6 * fbm(x * 5.0, y * 5.0, 51)), 0, 1)
    cb = mix(cb, SOOT, soot * 0.7)
    # worn edges of rails, braces, frame (convex in the curvature bake)
    edge = np.clip((cur - 0.56) * 3.2, 0, 1) * (planks | fb | is_["board_b"])
    cb = mix(cb, hexc("#9A8062"), edge * (0.55 - 0.3 * soot))
    # wet patches along the bottom rail and at the foot of the boards
    wetb = smooth(0.5, 0.0, y + 0.25 * (fbm(x * 6.0, y * 4.0, 52) - 0.5)) * 0.8
    cb = mix(cb, cb * 0.62, wetb)
    # mineral streaks: under the window all the way down, and thinner ones elsewhere
    underb = smooth(wx0 - 0.04, wx0 + 0.03, x) * smooth(wx1 + 0.05, wx1 - 0.02, x) * (y < wy0 - lay["sill_h"])
    sxb = vnoise(x * 300.0, y * 1.2, 53)
    streakb = smooth(0.70, 0.84, sxb) * (0.35 + 0.65 * vnoise(x * 480.0, y * 26.0, 54))
    envb = underb * smooth(0.05, 0.5, y) * 0.9 + (1 - underb) * smooth(1.2, 0.2, y) * 0.35 * (vnoise(x * 11.0, y * 0, 55) > 0.45)
    mineral_b = np.clip(streakb * envb * 1.5, 0, 1) * ~planks + np.clip(streakb * envb, 0, 1) * planks * 0.5
    cb = mix(cb, MINERAL * 0.92, mineral_b * 0.62)
    canvas_b, cx0, cy0, sc = nail_runs(lay["nails"]["back"], 0.03, rng)
    runb = sample(canvas_b, x, y, cx0, cy0, sc)
    cb = mix(cb, SOOT * 1.2, np.clip(runb, 0, 1) * 0.5)
    col[wood_b] = cb[wood_b]
    gloss[wood_b] = (0.22 + 0.10 * grain + 0.35 * wetb + 0.12 * (1 - soot))[wood_b]

    # ---------------- knots: dark resin, both sides share the boards' layout
    for side, mask, klist in (("f", is_["board_f"], knots(lay["boards"], rng)),
                              ("b", is_["board_b"], knots(lay["boards"], rng, (0, 2)))):
        for (kx, ky, kr) in klist:
            sel = mask & (np.abs(x - kx) < kr * 3) & (np.abs(y - ky) < kr * 4)
            if not sel.any():
                continue
            dd = np.hypot((x[sel] - kx) / kr, (y[sel] - ky) / (kr * 1.5))
            k = np.exp(-dd ** 2.2)
            ring = 0.25 * np.exp(-((dd - 1.5) / 0.35) ** 2)
            col[sel] = mix(col[sel], SMOKED * (0.9 if side == "f" else 0.6), np.clip(k * 0.85 + ring, 0, 1))
            gloss[sel] += 0.25 * k
            height[sel] -= 0.5 * k
    height[wood] += (grain[wood] - 0.5) * 1.0
    spec[wood] = 0.05

    # ---------------- steel sheet in the gaps and on the door's edges
    st = is_["steel"]
    rn = fbm(x * 40.0, y * 40.0, 61)
    col[st] = mix(mix(hexc("#5E3A28"), IRON, smooth(0.3, 0.7, rn)), RUST * 0.9, smooth(0.6, 0.9, fbm(x * 90.0, y * 90.0, 62)) * 0.55)[st]
    gloss[st], spec[st] = 0.22, 0.12

    # ---------------- iron: nails, hinges, wire, the bent nail
    for name, base, sp in (("nail", IRON, 0.22), ("hinge", IRON * 1.1, 0.2), ("wire", hexc("#4A4038"), 0.25), ("hook", IRON, 0.22)):
        m = is_[name]
        rr = fbm(x * 160.0, y * 160.0, 63)
        c = mix(base, RUST * 0.9, smooth(0.3, 0.75, rr + (0.25 if name != "wire" else 0.0)) * 0.75)
        c = mix(c, hexc("#6E655C"), np.clip((cur - 0.6) * 3, 0, 1) * 0.5)       # rubbed bright on the edges
        col[m] = c[m]
        gloss[m], spec[m] = 0.34, sp
    nb = is_["nail"] & ~front                  # in the steam room iron is black with soot
    col[nb] = mix(col[nb], SOOT * 1.3, 0.5)

    # ---------------- towel
    tw = is_["towel"] | is_["stripe"]
    weave = (np.sin(x * 2 * np.pi / 0.0035) * np.sin(y * 2 * np.pi / 0.0035)) * 0.5 + 0.5
    cloth = LINEN * (0.90 + 0.06 * weave + 0.08 * fbm(x * 30.0, y * 30.0, 71))[:, None]
    cloth = mix(cloth, hexc("#A89C86"), fbm(x * 9.0, y * 9.0, 72) * 0.35)        # washed-out, not clean
    stripe = mix(BRICK, LINEN, 0.22 + 0.25 * fbm(x * 60.0, y * 60.0, 73)) * (0.92 + 0.1 * weave)[:, None]
    ct = np.where(is_["stripe"][:, None], stripe, cloth)
    ct = ct * (0.80 + 0.20 * ao)[:, None]                                         # grime sits in the folds
    hem_damp = smooth(1.42, 1.25, y) * 0.18
    ct = mix(ct, ct * 0.8, hem_damp)
    col[tw] = ct[tw]
    gloss[tw], spec[tw] = 0.08, 0.03
    height[tw] += (weave[tw] - 0.5) * 0.5

    # ---------------- leaf
    lf = is_["leaf"]
    lcol = mix(LEAF, LEAF_DRY, fbm(x * 70.0, y * 70.0, 81)) * (0.8 + 0.3 * np.clip((cur - 0.4) * 2, 0, 1))[:, None]
    col[lf] = lcol[lf]
    gloss[lf], spec[lf] = 0.45, 0.06

    # ---------------- glass: fogged, with runs; warm glow behind, brighter at the bottom
    gl = is_["glass"]
    u = np.clip((x - px0) / (px1 - px0), 0, 1)
    v = np.clip((y - py0) / (py1 - py0), 0, 1)                                    # 0 bottom .. 1 top
    heat = np.clip((1 - v) ** 1.25 * (0.55 + 0.45 * np.exp(-((u - 0.45) / 0.33) ** 2)) + 0.14, 0, 1)
    fog = 0.75 + 0.25 * fbm(x * 45.0, y * 45.0, 91)
    track = np.zeros(len(x), np.float32)
    trng = np.random.default_rng(SEED + 5)
    for _ in range(6):
        tx, top, wdt = trng.uniform(0.08, 0.92), trng.uniform(0.35, 0.95), trng.uniform(0.008, 0.016)
        wob = 0.012 * (vnoise(v * 9.0, v * 0 + tx * 40, 92) - 0.5)
        tr = np.exp(-((u - tx - wob) / wdt) ** 2) * smooth(top, top - 0.06, v) * (0.5 + 0.5 * smooth(0.0, 0.5, top - v + 0.2))
        head = np.exp(-(((u - tx) / (wdt * 1.6)) ** 2 + ((v - top) / 0.02) ** 2))  # the drop at the top of a run
        track = np.maximum(track, np.maximum(tr, head))
    cells = 70.0
    du, dv = u * cells * (px1 - px0) / (py1 - py0), v * cells
    drop_h = hash1((np.floor(du).astype(np.int64) * 7919 + np.floor(dv).astype(np.int64) * 104729) & 0x7FFFFFFF, 93)
    drops = (np.hypot(du % 1 - 0.5, dv % 1 - 0.5) < 0.2) * (drop_h > 0.80)
    clear = np.clip(track + drops * 0.8, 0, 1)
    border = np.minimum(np.minimum(u, 1 - u) * (px1 - px0), np.minimum(v, 1 - v) * (py1 - py0))
    edge_dirt = smooth(0.03, 0.0, border)
    g_day = mix(hexc("#8F7458"), hexc("#BC966C"), heat) * fog[:, None]            # fog lit from behind
    g_day = mix(g_day, hexc("#7A4A2A"), clear * 0.6)                               # runs show the dark room and the glow
    g_day = mix(g_day, hexc("#5A4636"), edge_dirt * 0.6)
    col[gl] = g_day[gl]
    gloss[gl] = (0.42 + 0.35 * clear - 0.15 * edge_dirt)[gl]
    spec[gl] = 0.16
    emis = np.zeros((len(x), 3), np.float32)
    e_col = mix(GLOW_CORE, GLOW_EDGE, np.clip(heat * 1.25 - 0.1, 0, 1) ** 1.2)
    e_int = (0.13 + 0.54 * heat ** 1.4) * fog * (1 - 0.35 * clear) * (1 - 0.7 * edge_dirt)
    emis[gl] = (e_col * e_int[:, None])[gl]
    # the glow spills on the inner edges of the frame and on the sill's top
    near = (is_["frame"] | is_["sill"]) & (x > px0 - 0.016) & (x < px1 + 0.016) & (y > py0 - 0.02) & (y < py1 + 0.016)
    spill = 0.10 * (0.4 + 0.6 * np.clip(1 - (y - py0) / (py1 - py0), 0, 1))
    emis[near] = (GLOW_CORE * spill[:, None] * col.mean(1, keepdims=True) * 2.2)[near]

    # ---------------- dirt in the crevices (not lighting: the AO map carries the shading)
    crev = np.clip(1 - ao, 0, 1) ** 1.3
    dirt_amt = np.where(gl | tw, 0.0, 0.55)
    col = mix(col, col * hexc("#3A2C22") * 1.4, crev * dirt_amt)

    # ---------------- the handle: original maps, wood darkened by hands
    bc = np.asarray(Image.open(ORIG / "logwood_window_doors_bc.png").convert("RGB").resize((N, N), Image.LANCZOS), np.float32) / 255
    lum = bc[M].mean(1)
    col[handle] = (HANDLE * (0.55 + 1.3 * lum)[:, None])[handle]
    gloss[handle], spec[handle] = 0.42, 0.07
    emis[handle] = 0

    col = np.clip(col, 0.02, 0.92)

    # ================= assemble images
    def to_img(vals, ch):
        img = np.zeros((N, N, ch), np.float32)
        img[M] = vals.reshape(len(x), ch)
        return img

    diffuse = dilate(to_img(col, 3), M, 20)
    sg = dilate(to_img(np.concatenate([np.repeat(spec[:, None], 3, 1), gloss[:, None]], 1), 4), M, 20)
    emission = to_img(emis, 3)

    # normal: the bake + micro relief (grain, weave) from the height field in texture space
    Hm = np.zeros((N, N), np.float32)
    Hm[M] = height
    idm = np.full((N, N), -1, np.int16)
    idm[M] = mid
    same_x = (np.roll(idm, -1, 1) == idm) & (np.roll(idm, 1, 1) == idm)
    same_y = (np.roll(idm, -1, 0) == idm) & (np.roll(idm, 1, 0) == idm)
    dhx = (np.roll(Hm, -1, 1) - np.roll(Hm, 1, 1)) * same_x
    dhy = (np.roll(Hm, 1, 0) - np.roll(Hm, -1, 0)) * same_y                      # +v is up
    nb_ = nrm_b * 2 - 1
    k = 0.55
    nx_, ny_ = nb_[..., 0] - k * dhx, nb_[..., 1] - k * dhy
    nz_ = np.clip(nb_[..., 2], 0.2, 1)
    ln = np.sqrt(nx_ ** 2 + ny_ ** 2 + nz_ ** 2)
    normal = np.stack([nx_ / ln * 0.5 + 0.5, ny_ / ln * 0.5 + 0.5, np.ones_like(nx_)], -1)
    on = np.asarray(Image.open(ORIG / "logwood_window_doors_nrm.png").convert("RGB").resize((N, N), Image.LANCZOS), np.float32) / 255
    hm = np.zeros((N, N), bool)
    hm[M] = handle
    normal[hm] = on[hm]
    normal[..., 2] = 1.0
    normal = dilate(normal * M[..., None], M, 20)
    normal[~(M | (normal.sum(-1) > 1.01))] = (0.5, 0.5, 1.0)

    occ = ao_b.copy()
    oa = np.asarray(Image.open(ORIG / "logwood_window_doors_ao.png").convert("L").resize((N, N), Image.LANCZOS), np.float32) / 255
    occ[hm] = oa[hm]
    occ = dilate((occ * M)[..., None], M, 20)[..., 0]
    occ[occ == 0] = 1.0

    def save(arr, name, size, mode):
        im = Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), mode)
        im = im.resize((size, size), Image.BOX)
        path = OUT / f"Door_{VERSION}_{name}.png"
        im.save(path)
        print("->", path.name, im.size, im.mode)

    OUT.mkdir(exist_ok=True)
    save(np.concatenate([diffuse, np.ones((N, N, 1), np.float32)], -1), "diffuse", OUT_N, "RGBA")
    save(np.concatenate([normal, np.ones((N, N, 1), np.float32)], -1), "normal", OUT_N, "RGBA")
    save(sg, "specgloss", OUT_N, "RGBA")
    save(np.repeat(occ[..., None], 3, -1), "occlusion", 1024, "RGB")
    save(emission, "emission", 1024, "RGB")

    # numbers for the README
    def med(m):
        c = (np.median(col[m], 0) * 255).astype(int)
        return "#%02X%02X%02X" % tuple(c)
    print("median diffuse: front boards", med(is_["board_f"]), "| back boards", med(is_["board_b"]),
          "| rails", med(is_["rail"]), "| towel", med(is_["towel"]), "| stripe", med(is_["stripe"]),
          "| glass", med(gl))
    e = emis[gl]
    print("emission on glass: mean %.2f, max %.2f; lit texels %.2f%% of the islands" %
          (e.max(1).mean(), e.max(), 100 * (emis.max(1) > 0.02).mean()))


if __name__ == "__main__":
    build()
