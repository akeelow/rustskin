"""Sauna Chair v1: texture maps from the bake (bake_chair.py) + wear by the chair's story.

Story: an old armchair on a steel-channel frame from the same roadside house as the bench, set in the
changing room where people cool off after the steam room. Backrest clad in lining off-cuts, seat in
aspen slats across, a shovel handle for the missing front leg with wire round its split end, a staple
across the cracked front slat. The seat is polished where people sit and the front edge where legs
rub; a wet patch where the wash basin stood; the lining a touch darker where sweaty backs lean; the
arms' front ends polished by hands; every leg darkest at the floor with mineral streaks; the channel
rusty at the joints and at the bottom. A linen towel with a brick stripe over the top of the backrest.

Inputs: bake/{normal,ao,curvature,id}.png, originals/chair_{bc,nrm}.png.
Outputs: export/Chair_v1.4_{diffuse,normal,specgloss,occlusion}.png (1024, like the originals;
earlier versions in git history).

    .venv/Scripts/python skins/sauna/chair/texture_v1.py
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
sys.path.insert(0, str(HERE))
import blocking as B  # noqa: E402
import layout as L  # noqa: E402
from islands import islands  # noqa: E402
from uv_zones import load_obj  # noqa: E402

BAKE = HERE / "bake"
OUT = HERE / "export"
SIZE, OUT_SIZE = B.SIZE, B.OUT_SIZE
SEED = 12
VERSION = "v1.4"
IDS = {"base": 0, "slat": 1, "cavity": 2, "lining": 3, "back": 4, "batten": 5, "frame": 6, "nail": 7,
       "towel": 8, "wire": 9, "staple": 10, "handle": 11, "joist": 12, "leaf": 13}

hexc, blur, smooth, hash1 = B.hexc, B.blur, B.smooth, B.hash1
ASPEN, ASPEN_GREY, STEAMED = B.ASPEN, B.ASPEN_GREY, B.STEAMED
LINEN, BRICK, GAP, IRON, RUST, MINERAL = B.LINEN, B.BRICK, B.GAP, B.IRON, B.RUST, B.MINERAL
# v0 in game: the handle read orange -> greyer, browner
HANDLE = hexc("#76634F")
HALO = hexc("#4E3424")           # wet dark iron stain round nails (as the bench)
IRON_PARTS = (1, 6, 8, 13, 14, 17, 18, 19, 21)      # keep the original normal map
LEGS = (4, 6, 8, 10)


# ---------------------------------------------------------------- noise (as the bench)
def vnoise(u, v, seed):
    iu, iv = np.floor(u), np.floor(v)
    fu, fv = u - iu, v - iv
    fu, fv = fu * fu * (3 - 2 * fu), fv * fv * (3 - 2 * fv)
    iu, iv = iu.astype(np.int64), iv.astype(np.int64)

    def h(a, b):
        return hash1((a * 92837111 + b * 689287499) & 0x7FFFFFFF, seed)

    return ((h(iu, iv) * (1 - fu) + h(iu + 1, iv) * fu) * (1 - fv)
            + (h(iu, iv + 1) * (1 - fu) + h(iu + 1, iv + 1) * fu) * fv)


def fbm(u, v, seed, octaves=4):
    s, a, tot = 0.0, 1.0, 0.0
    for o in range(octaves):
        s = s + a * vnoise(u * 2 ** o, v * 2 ** o, seed + o * 17)
        tot += a
        a *= 0.5
    return s / tot


def grain(along, across, seed):
    """Wood fibres: thin streaks along `along` (cm), warped; 0..1."""
    warp = 1.6 * fbm(along * 0.015, across * 0.12, seed + 5, 3)
    fib = vnoise(along * 0.04, across * 2.2 + warp * 3.0, seed)
    fine = vnoise(along * 0.12, across * 6.0 + warp * 5.0, seed + 9)
    rings = 0.5 + 0.5 * np.sin((across + 3.0 * warp) * 2.6)
    return np.clip(0.45 * fib + 0.25 * fine + 0.3 * rings, 0, 1)


def height_normal(h, k):
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    return -gx * k, gy * k


def load(name, mode="RGB"):
    im = Image.open(name).convert(mode)
    if im.size != (SIZE, SIZE):
        im = im.resize((SIZE, SIZE), Image.BICUBIC)
    return np.asarray(im, np.float64) / 255.0


def index_of(v, edges):
    """Board index for coordinate v (cm) by (lo, hi) edges; -1 outside."""
    k = np.full(v.shape, -1)
    for i, (a, b) in enumerate(edges):
        k = np.where((v >= a) & (v < b), i, k)
    return k


# ---------------------------------------------------------------- main
def build():
    V, T, F = load_obj(B.ORIG / "chair.obj")
    island_of = np.empty(len(F), int)
    for n, fs in enumerate(islands(F)):
        island_of[fs] = n
    pos, nrm, iid = B.position_map(V, T, F, island_of)
    x, y, z = pos[..., 0] * 100, pos[..., 1] * 100, pos[..., 2] * 100
    rng = np.random.default_rng(SEED)
    isin = lambda ids: np.isin(iid, ids)

    nb = load(BAKE / "normal.png") * 2 - 1
    ao = load(BAKE / "ao.png", "L")
    curv = load(BAKE / "curvature.png", "L")
    idm = np.asarray(Image.open(BAKE / "id.png").convert("RGB"), np.int32)
    mid = np.clip(idm[..., 0] // 16, 0, 15)
    rnd = idm[..., 1] / 255.0
    bc = load(B.ORIG / "chair_bc.png")
    on = load(B.ORIG / "chair_nrm.png") * 2 - 1
    lum = bc @ np.array([0.299, 0.587, 0.114])

    iron = isin(IRON_PARTS)
    baked = (iid >= 0) & ~iron
    M = {k: baked & (mid == v) for k, v in IDS.items()}
    slat, lining, back, frame = M["slat"], M["lining"], M["back"], M["frame"] | M["batten"]
    wood_mat = slat | lining | back | frame | M["handle"] | M["joist"]

    # board coordinates: seat slats by z (along x), lining boards by x (along y)
    k_seat = index_of(z, L.SLATS)
    k_board = index_of(x, L.BOARDS)
    # grain along each part: arms run front to back (z), rail and seat front edge across (x), the rest
    # (wings, posts, legs) up (y). (first v1 sheet: arms had their grain across, like printed stripes)
    arm_i = isin([7, 9, 12, 20])
    across_x = isin([2]) | (isin([0]) & (y < 53.5))
    along = np.where(slat, x, np.where(lining | back, y, np.where(arm_i, z, np.where(across_x, x, y))))
    across = np.where(slat, z, np.where(lining | back, x, np.where(arm_i, x + y, np.where(across_x, y + z, x))))
    # v1.1: wings are three off-cuts per side (layout.WING_JOINTS), arms one bar each: own tone per piece
    wings = isin([0]) & frame & (y >= 53.5)
    seg = L.wing_segment(y)
    board = np.where(slat, k_seat, np.where(lining | back, k_board + 10, -1))
    board = np.where(wings, 20 + seg + 3 * (x > 0), np.where(arm_i, 30 + (x > 0), board))
    brnd = np.where(board >= 0, hash1(board + 50, SEED), rnd)
    across = across + 37.0 * brnd
    g = grain(along, across, SEED)
    big = fbm(x * 0.02 + 3, y * 0.02 + z * 0.02, SEED + 3, 3) - 0.5
    convex = smooth(0.52, 0.7, curv)
    concave = smooth(0.48, 0.3, curv)

    col = np.zeros((SIZE, SIZE, 3)) + STEAMED
    spec = np.full((SIZE, SIZE), 0.06)
    gloss = np.full((SIZE, SIZE), 0.22)
    hgt = np.zeros((SIZE, SIZE))

    # ---------------- wood base: per-board tone, grey/warm mix, grain (as the bench)
    greyness = np.clip(0.3 + 0.55 * hash1((brnd * 1000).astype(int), SEED + 1) + 0.3 * big, 0, 1)
    # 0.45 (bench: 0.6): next to the bench on the sheet the chair came out paler and greyer
    base = ASPEN * (1 - greyness[..., None] * 0.45) + ASPEN_GREY * (greyness[..., None] * 0.45)
    base = base * (0.9 + 0.16 * brnd[..., None])
    wood = base * (0.86 + 0.2 * g[..., None]) * (1 + 0.08 * big[..., None])
    hgt += np.where(wood_mat, 0.035 * g, 0)

    # ---------------- seat: polished where people sit, front edge rubbed by legs, the basin's wet patch
    sit = smooth(0, 1, (1 - np.abs((x + 2) / 24) ** 2.5) * (1 - np.abs((z - 6) / 22) ** 3)) * slat
    sit = sit * (0.8 + 0.4 * fbm(x * 0.05, z * 0.05, SEED + 21, 2))
    wood = wood * (1 + 0.06 * sit[..., None])
    wood = wood * (1 - 0.4 * sit[..., None] * (g[..., None] - 0.5) * 0.3)      # grain softer where polished
    # v1.3: the front edge darker and greasy where legs and hands rub (was lighter, "polished")
    front = smooth(26.0, 31.0, z) * (slat | (frame & (iid == 0) & (y < 53)))
    wood = wood * (1 - 0.1 * front[..., None])
    # v1.3: water stands along the slats' edges by the gaps: damp darker borders
    za = np.zeros_like(z) + 1e3
    for (a, b) in L.SLATS:
        a2, b2 = a + L.SEAT_GAP / 2, b - L.SEAT_GAP / 2
        za = np.where((z >= a) & (z < b), np.minimum(z - a2, b2 - z), za)
    damp_gap = smooth(1.4, 0.2, za) * slat * (0.55 + 0.45 * fbm(x * 0.12, z * 0.3, SEED + 59, 3))
    wood = wood * (1 - 0.2 * damp_gap[..., None])
    # wet patch from the wash basin - darker and glossier than the bench's dry mineral ring
    # (v0 in game: a 22 % ring did not read at all)
    cx, cz = L.RING_C
    ang = np.arctan2(z - cz, x - cx)
    rc = np.hypot(x - cx, z - cz) * (1 + 0.035 * np.sin(ang * 3 + 1.0))
    # v1.1: no rim line at all - in game (v1) any ring read as a drawn circle. A wet patch where the
    # basin stood: soft broken edge, wetter on the side it was dragged off (toward -x), water in the gaps
    edge = L.RING_R + 2.5 * (fbm(ang * 1.2 + 3, 0.5, SEED + 57, 3) - 0.5) * 2
    disc = smooth(edge + 1.5, edge - 3.5, rc) * slat
    drag = smooth(4.0, -10.0, x - cx)
    disc = disc * (0.55 + 0.3 * drag + 0.15 * fbm(x * 0.2, z * 0.2, SEED + 53, 2))
    # (v1.2: 0.3 -> 0.4, in game v1.1 the patch hardly showed)
    wood = wood * (1 - 0.4 * disc[..., None]) + STEAMED * (0.1 * disc[..., None])
    # the crack: dark in the groove
    crack = np.exp(-((z - L.crack_z(x)) / 0.12) ** 2) * (x > L.CRACK_X[0]) * smooth(L.CRACK_X[1], L.CRACK_X[1] - 3, x)
    wood = wood * (1 - 0.6 * (crack * slat)[..., None])
    wood = wood * (1 + 0.12 * convex[..., None]) * (1 - 0.25 * concave[..., None])

    # ---------------- lining: a touch darker and smoother where backs lean; back side greyer, rougher
    # v1.1: the lean zone softer (v1 in game: with the wings' AO it read as a dirty smear)
    lean = smooth(0.0, 1.0, 1 - np.hypot(x / 15.0, (y - 72.0) / 11.0)) * lining
    wood = wood * (1 - 0.05 * lean[..., None])
    wood = np.where(back[..., None], wood * 0.9 * np.array([0.96, 0.98, 1.0]), wood)
    # the frame's seat front edge, wings, arms, rail, block leg, left arm post
    wood = np.where(frame[..., None], wood * 0.9, wood)
    # v1.1: joints between the wing off-cuts: a dark hairline, a shade under the proud piece
    joint = sum(np.exp(-((y - jy) / 0.16) ** 2) for jy in L.WING_JOINTS) * wings
    under = sum(smooth(jy - 1.2, jy, y) * (y < jy) for jy in L.WING_JOINTS) * wings
    wood = wood * (1 - 0.6 * joint[..., None]) * (1 - 0.1 * under[..., None])
    # arms' front ends: end grain, darker, rings round the bar's middle
    endg = isin([7, 9]) & (nrm[..., 2] > 0.6) & (z > 15)
    # (v1.2: in game v1.1 the rings read as a target - off-centre pith, fewer and fainter rings)
    rings = 0.5 + 0.5 * np.sin(np.hypot(y - 69.0, (np.abs(x) - 31.0) * 1.3) * 2.2 + 1.2 * vnoise(x * 0.6, y * 0.6, SEED + 55))
    wood = np.where(endg[..., None], wood * (0.76 + 0.05 * rings[..., None]), wood)
    bat = M["batten"]
    wood = np.where(bat[..., None], (STEAMED * 0.55 + ASPEN_GREY * 0.45) * (0.86 + 0.22 * g[..., None]), wood)
    arms = np.isin(iid, (7, 9)) & frame & (nrm[..., 1] > 0.5)
    hand = smooth(8.0, 22.0, z) * arms
    # v1.3: hands darken and grease the arms' front ends (was lighter)
    wood = wood * (1 - 0.13 * hand[..., None]) + STEAMED * (0.05 * hand[..., None])

    # ---------------- shovel handle: denser brown wood, polished, a little darker toward the floor
    hd = M["handle"]
    hcol = HANDLE * (0.86 + 0.2 * grain(y, x + z, SEED + 61)[..., None]) * (1 + 0.06 * convex[..., None])
    wood = np.where(hd[..., None], hcol, wood)
    # ---------------- seat underside: dark wet joists
    jo = M["joist"]
    wood = np.where(jo[..., None], hexc("#4E4034") * (0.88 + 0.22 * g[..., None]), wood)

    # ---------------- all legs: darkest at the floor, mineral streaks where water stands
    legs = isin(LEGS)
    wet = smooth(16.0, 0.0, y) * legs
    streak = np.clip((fbm(np.arctan2(z - 28, x + 27) * 6 + x * 0.3, 2.0, SEED + 71, 3) - 0.5) * 2.5, 0, 1) * wet
    wood = wood * (1 - 0.4 * wet[..., None])
    wood = wood * (1 - 0.25 * streak[..., None]) + MINERAL * (0.25 * streak[..., None]) * smooth(2.0, 8.0, y)[..., None]
    # v1.3: water running down the legs: thin darker streaks from the seat down, wettest at the floor
    run = smooth(0.62, 0.78, vnoise((x + z) * 1.4, y * 0.035, SEED + 73)) * smooth(42.0, 6.0, y) * legs
    wood = wood * (1 - 0.22 * run[..., None])

    # v1.1: board edges worn lighter on the frame and lining too (the wings read moulded without them)
    fl = frame | lining | back
    wood = wood * (1 + 0.14 * (convex * fl)[..., None])
    # v1.1: in game v1 was lighter than the bench and caught the sky (blue sheen): a shade darker,
    # warmer, and matter outside the polished seat and arm ends
    wood = wood * np.array([0.95, 0.93, 0.89])
    col = np.where(wood_mat[..., None], wood, col)
    gloss = np.where(wood_mat, 0.15 + 0.13 * sit + 0.22 * disc + 0.04 * lean + 0.18 * hand
                     + 0.12 * hd + 0.08 * wet + 0.12 * front + 0.12 * damp_gap + 0.1 * run, gloss)

    # ---------------- gaps and cavities
    cav = baked & M["cavity"]
    # v1.2: cavity where it is not a gap between boards (in game v1.1): the step at y 81 on the back
    # (top of the old back plate under the lining) and its sides; the wings' back edges outside the
    # lining (dashed dark outlines); the seat's front lip round the slats' ends (a black-outlined block)
    ledge = isin([5]) & (((nrm[..., 1] > 0.9) & (np.abs(y - 81.0) < 1.5)) | ((np.abs(nrm[..., 0]) > 0.9) & (y > 50)))
    stray = cav & ((np.abs(x) > L.PANEL_X[1]) & isin([0, 5]) & (y > 53.5) | isin([0]) & (y < 53.5) & (z > 30.0))
    edge_wood = ASPEN * np.array([0.95, 0.93, 0.89]) * 0.8 * (0.86 + 0.2 * g[..., None])
    col = np.where(cav[..., None], GAP * (0.8 + 0.3 * rnd[..., None]), col)
    col = np.where((stray | ledge)[..., None], edge_wood, col)
    ao = np.where(stray | ledge, np.maximum(ao, 0.85), ao)          # the ledge sits in the overhang's AO
    # the seat's front lip in the front slat's tone (v1.1: a lighter separate-looking block)
    lip = frame & isin([0]) & (y < 53.5)
    col = np.where(lip[..., None], col * 0.9, col)

    # ---------------- nails, staple, wire: dark iron, rust bleeding into the wood round the nails
    nail = M["nail"] | M["staple"]
    nm = nail.astype(np.float64)
    halo = np.clip(blur(nm, 3) * 3.0, 0, 1) * (1 - nm)
    halo2 = np.clip(blur(nm, 7) * 2.5, 0, 1) * (1 - nm)
    nrust = smooth(0.45, 0.8, vnoise(x * 2 + y, z * 2, SEED + 91))
    ncol = IRON * (1 - 0.6 * nrust[..., None]) + RUST * 0.7 * (0.6 * nrust[..., None])
    ncol = ncol * (0.85 + 0.4 * convex[..., None])
    col = np.where(nail[..., None], ncol, col)
    col = col * (1 - 0.45 * halo[..., None]) + HALO * (0.45 * halo[..., None])
    col = col * (1 - 0.14 * halo2[..., None])
    spec = np.where(nail, 0.25 - 0.12 * nrust, spec)
    gloss = np.where(nail, 0.35 - 0.15 * nrust, gloss)
    wi = M["wire"]
    wrust = smooth(0.4, 0.75, vnoise(y * 1.5, x + z, SEED + 93))
    wcol = IRON * 1.15 * (1 - 0.5 * wrust[..., None]) + RUST * 0.75 * (0.5 * wrust[..., None])
    wcol = wcol * (0.7 + 0.6 * convex[..., None]) * (1 - 0.3 * concave[..., None])
    col = np.where(wi[..., None], wcol, col)
    spec = np.where(wi, 0.35 - 0.15 * wrust, spec)
    gloss = np.where(wi, 0.42 - 0.2 * wrust, gloss)

    # ---------------- towel: washed linen, brick stripes on the front end, shade in the folds
    # the towel by position too: under the rail's front edge a few texels saw the rail / the cavity
    # (a dark notch and dashes along the towel's top on the first v1 sheet)
    in_x = (x > L.TOWEL_X[0] + 0.4) & (x < L.TOWEL_X[1] - 0.4)
    forced = baked & in_x & ~M["towel"] & ~M["leaf"] & (((iid == 0) & (y > L.hem_front(x) + 1.0) & (nrm[..., 2] > 0.2))
                                          | (iid == 2) | ((iid == 5) & (y > L.hem_back(x) + 1.0) & (y > 52)))
    tw = M["towel"] | forced
    ao = np.where(forced, np.maximum(ao, 0.85), ao)
    on_front = tw & (nrm[..., 2] > 0.2) & (y < L.RAIL_AXIS[0])
    d = np.where(on_front, y - L.hem_front(x), 99.0)
    stripes = L.towel_stripes(d) * (0.8 + 0.2 * vnoise(x * 0.6, y * 0.6, SEED + 101))
    # v1.3: coarse linen: warp and weft threads 0.7 cm (4 texels at 1024 - finer moirés), slubs
    tv = y + z
    slub = fbm(x * 0.4, tv * 3.0, SEED + 103, 2) - 0.5
    weave = 0.5 + 0.22 * np.sin(x * 2 * np.pi / 0.7 + 1.5 * slub) + 0.22 * np.sin(tv * 2 * np.pi / 0.7)
    tcol = LINEN * (0.94 + 0.08 * weave[..., None]) * (1 + 0.04 * big[..., None])
    tcol = tcol * (1 - 0.88 * stripes[..., None]) + BRICK * (0.88 * stripes[..., None])
    hem_line = np.exp(-((d - 2.0) / 0.25) ** 2) + np.where(tw & ~on_front & (y < L.RAIL_AXIS[0]),
                                                            np.exp(-((y - L.hem_back(x) - 2.0) / 0.25) ** 2), 0)
    tcol = tcol * (1 - 0.12 * hem_line[..., None])
    tcol = tcol * (1 - 0.3 * concave[..., None]) * (1 + 0.05 * convex[..., None])
    # v1.3: one damp patch where the towel lies on the rail (wet hands hung it there)
    tdamp = smooth(8.0, 2.0, np.hypot(x + 5.0, (y - 109.0) * 0.9) * (1 + 0.25 * vnoise(x * 0.5, y * 0.5, SEED + 105))) * tw
    # (13 % on the first v1.3 sheet read as a grey stain - half, wider)
    tcol = tcol * (1 - 0.065 * tdamp[..., None]) * (1 - 0.03 * tdamp[..., None] * np.array([0, 0.3, 1.0]))
    col = np.where(tw[..., None], tcol, col)
    spec = np.where(tw, 0.04, spec)
    gloss = np.where(tw, 0.1 + 0.1 * tdamp, gloss)
    hgt += np.where(tw, 0.05 * weave, 0)

    # ---------------- v1.3: leaves off the bath broom, each in a wet halo (darker, glossier)
    lf = M["leaf"]
    on_seat, on_towel = lf & (y < 56), lf & (y > 85) & isin([0])
    # v1.4: in game (v1.3, sun) the oak and the yellowed birch were bright yellow blobs (182,151,71 and
    # 213,191,92) - the bench had the same in v1.1: its darker leaf colours, and veins so the shape reads
    lcol = np.where(on_seat[..., None], hexc("#5E4A2C"),                            # steamed oak, brown
                    np.where(on_towel[..., None], B.hexc("#4F5C30"), hexc("#6E5A30")))  # green / dry birch
    lcol = lcol * (0.88 + 0.2 * vnoise(x * 1.2, y * 1.2 + z, SEED + 95)[..., None]) * (1 - 0.3 * concave[..., None])
    vein = np.zeros((SIZE, SIZE))
    for where, a, b, length, ang, kind, _ in L.LEAVES:
        # the leaf's own frame as bake_chair.place() lays it: seat / arm (up): x, -z; towel (front): y, -x
        lx, ly = (y - b, -(x - a)) if where == "towel" else (x - a, -(z - b))
        ca, sa = np.cos(np.radians(ang)), np.sin(np.radians(ang))
        u, v = ca * lx + sa * ly, -sa * lx + ca * ly
        near = lf & (np.hypot(u, v) < length * 0.75)
        mid = np.exp(-(v / 0.07) ** 2) * (np.abs(u) < length * 0.48)
        side = np.exp(-((np.mod(u - 0.8 * np.abs(v), length / 7.0) - length / 14.0) / 0.05) ** 2) * (np.abs(v) > 0.12)
        vein = np.maximum(vein, near * np.maximum(mid, 0.6 * side))
    lcol = lcol * (1 - 0.3 * vein[..., None])
    col = np.where(lf[..., None], lcol, col)
    spec = np.where(lf, 0.06, spec)
    gloss = np.where(lf, 0.38, gloss)
    lm = lf.astype(np.float64)
    lhalo = np.clip(blur(lm, 9) * 2.5, 0, 1) * (1 - lm)
    col = col * (1 - np.where(tw, 0.14, 0.28)[..., None] * lhalo[..., None])
    gloss = np.where(lf, gloss, gloss + 0.22 * lhalo)

    # ---------------- CRITIQUE.md (3.6): soft drop shadow under birch leaf on towel
    # The towel front hangs vertically (nrm_z > 0.2, Y is height).
    # Overhead light (daylight/room lamp) casts a soft shadow downwards (-y, +rows) onto the towel cloth.
    tm = on_towel.astype(np.float64)
    contact_t = blur(np.roll(tm, 2, axis=0), 2.5) * (1 - tm)
    soft_t = blur(np.roll(np.roll(tm, 7, axis=0), 2, axis=1), 6.0) * (1 - tm)
    towel_shadow = np.clip(contact_t * 0.75 + soft_t * 0.55, 0, 1) * tw
    col = col * (1 - 0.48 * towel_shadow[..., None])
    ao = np.maximum(0.0, ao - 0.28 * towel_shadow)

    # ---------------- iron: dark steel, rust in joints (AO), at the bottom and at the seat joint
    # v0 in game: orange patches -> rust a mix toward iron, weaker
    rmask = smooth(0.6, 0.25, ao) * 0.4 + 0.5 * smooth(10.0, 0.0, y) + 0.35 * np.exp(-((y - 45.0) / 5.0) ** 2)
    rmask = rmask + 0.35 * (fbm(x * 0.08, y * 0.08 + z * 0.08, SEED + 121, 4) - 0.5) * 2
    drips = np.clip((vnoise(x * 0.35 + z * 0.35, y * 0.03, SEED + 125) - 0.7) * 3, 0, 1) * (np.abs(nrm[..., 1]) < 0.5)
    rmask = smooth(0.4, 0.85, np.clip(rmask + 0.35 * drips, 0, 1))
    ic = IRON * (1 - 0.85 * rmask[..., None]) + (RUST * 0.7 + IRON * 0.3) * (0.85 * rmask[..., None])
    ic = ic * (0.75 + 0.5 * lum[..., None]) * (0.9 + 0.2 * vnoise(x * 0.5, y * 0.5 + z, SEED + 127)[..., None])
    ironm = iron | M["base"]
    col = np.where(ironm[..., None], ic, col)
    col = np.where((iron & isin([6, 8]))[..., None], col * (1 - 0.3 * smooth(16.0, 0.0, y))[..., None], col)
    spec = np.where(ironm, 0.32 - 0.22 * rmask, spec)
    gloss = np.where(ironm, 0.4 - 0.25 * rmask, gloss)

    # ---------------- v1.3: rust running down the wings from their nails
    rdrip = np.zeros((SIZE, SIZE))
    face = wings & (nrm[..., 2] > 0.2)
    for nx, ny in L.wing_nails():
        t = np.clip((ny - y) / 7.0, 0, 1)
        w = 0.22 + 0.15 * t
        rdrip = np.maximum(rdrip, face * (np.abs(x - nx) < w) * (y < ny - 0.3) * (1 - t) ** 1.5)
    rdrip = blur(rdrip, 1.2)
    col = col * (1 - 0.35 * rdrip[..., None]) + RUST * 0.75 * (0.35 * rdrip[..., None])

    # ---------------- AO into colour (the game's AO only darkens ambient light)
    # (v1.1: softer on the lining - the wings' AO darkened its sides into smears)
    col = col * np.where(lining[..., None], 0.7 + 0.3 * ao[..., None], (0.55 + 0.45 * ao[..., None]) ** 0.8)
    col[iid < 0] = STEAMED * 0.8

    # ---------------- normal: baked + grain where modelled, original on the iron
    dx, dy = height_normal(hgt, 6.0)
    n = np.where(baked[..., None], nb, on)
    n[..., 0] += dx
    n[..., 1] += dy
    # the handle's end caps (under the seat, on the floor): the cage rays met the seat / nothing there
    n[isin([15, 16])] = (0, 0, 1)
    n[forced] = (0, 0, 1)
    n[stray | ledge] = (0, 0, 1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9
    occ = 0.35 + 0.65 * ao
    return col, n, spec, gloss, occ


def main():
    col, n, spec, gloss, occ = build()
    OUT.mkdir(exist_ok=True)
    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    down = lambda im: im.resize((OUT_SIZE, OUT_SIZE), Image.LANCZOS)
    a255 = np.full(col.shape[:2], 255, np.uint8)
    down(Image.fromarray(np.dstack([q(col), a255]), "RGBA")).save(OUT / f"Chair_{VERSION}_diffuse.png")
    nd = np.asarray(down(Image.fromarray(q(n * 0.5 + 0.5), "RGB")), np.float64) / 255 * 2 - 1
    nd /= np.linalg.norm(nd, axis=-1, keepdims=True) + 1e-9
    Image.fromarray(q(nd * 0.5 + 0.5), "RGB").save(OUT / f"Chair_{VERSION}_normal.png")
    down(Image.fromarray(np.dstack([q(spec), q(spec), q(spec), q(gloss)]), "RGBA")).save(OUT / f"Chair_{VERSION}_specgloss.png")
    Image.fromarray(q(occ), "L").resize((512, 512), Image.LANCZOS).save(OUT / f"Chair_{VERSION}_occlusion.png")
    print("done")


if __name__ == "__main__":
    main()
