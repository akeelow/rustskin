"""Sauna Bench v1: texture maps from the bake (bake_bench.py) + wear by the bench's story.

Story: a roadside bed frame of steel channel, the mattress thrown out, a deck of aspen slats from
a pallet on top, the headboard two boards from an old door; used every evening for three years:
the deck polished light where people lie, the bottom dark from water running down, the foot end
(toward the stove, -x) smoked and dried out, rust bleeding from the nails along the grain.

Inputs: bake/{normal,ao,curvature,id}.png, originals/bed_{bc,nrm}.png.
Outputs (v1.1; v1 in git history): export/Bed_v1.1_{diffuse,normal,specgloss,occlusion}.png

    .venv/Scripts/python skins/sauna/bed/texture_v1.py
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
sys.path.insert(0, str(HERE))
import blocking as B  # noqa: E402
from parts import pieces  # noqa: E402
from uv_zones import load_obj  # noqa: E402

BAKE = HERE / "bake"
OUT = HERE / "export"
SIZE = B.SIZE
SEED = 12
IDS = {"base": 0, "slat": 1, "pallet": 2, "apron": 3, "nail": 4, "leaf": 5, "cavity": 6,
       "headboard": 7, "post": 8, "towel": 9}

hexc, blur, smooth, hash1 = B.hexc, B.blur, B.smooth, B.hash1
# v1.1: in game (sun) the deck came out (242, 225, 176) from diffuse (161, 141, 111) - lighter and
# yellower than the game's own wooden platform; aspen darker and greyer
ASPEN = hexc("#A39176")          # aspen, steam-aged
ASPEN_GREY = hexc("#958B7E")     # weathered silver-grey
STEAMED = hexc("#7A5A3C")
SMOKED = hexc("#45332A")
LINEN = hexc("#CFC6B4")
BRICK = hexc("#8E3A30")
GAP = hexc("#2A2018")
IRON = hexc("#2E2A27")
RUST = hexc("#8C4A26")
MINERAL = hexc("#D9D4C8")
LEAF_GREEN, LEAF_DRY = hexc("#5C6A39"), hexc("#8A7440")


# ---------------------------------------------------------------- noise
def vnoise(u, v, seed):
    """2D value noise, smooth, about unit frequency."""
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
    """Tangent-space (OpenGL) normal xy from a height map h (cm) sampled per texel."""
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    return -gx * k, gy * k


# ---------------------------------------------------------------- main
def load(name, mode="RGB"):
    return np.asarray(Image.open(name).convert(mode), np.float64) / 255.0


def build():
    V, T, F = load_obj(B.ORIG / "bed.obj")
    P = pieces(V, F)
    piece_of = np.empty(len(F), int)
    for n, fs in enumerate(P):
        piece_of[fs] = n
    # shared UV: the copy baked in bake_bench.py (not in its DUPLICATES) is drawn last
    dup = [6, 21, 18, 22, 24, 25, 26, 28, 7, 8, 9, 10, 12, 13, 14, 15, 16]
    order = [B.BLANKET, *dup, 17, 19, 23, 27, 11, 20, 5, *B.HEADBOARD, B.MATTRESS, B.PILLOW]
    pos, nrm, pid = B.position_map(V, T, F, piece_of, order)
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    rng = np.random.default_rng(SEED)

    nb = load(BAKE / "normal.png") * 2 - 1
    ao = load(BAKE / "ao.png", "L")
    curv = load(BAKE / "curvature.png", "L")
    idm = np.asarray(Image.open(BAKE / "id.png").convert("RGB"), np.int32)
    mid = np.clip((idm[..., 0] - 8 + 8) // 16, 0, 15)
    rnd = idm[..., 1] / 255.0
    bc = load(B.ORIG / "bed_bc.png")
    on = load(B.ORIG / "bed_nrm.png") * 2 - 1
    lum = bc @ np.array([0.299, 0.587, 0.114])

    isin = lambda ids: np.isin(pid, ids)
    blanket = isin([B.BLANKET])
    pillow = isin([B.PILLOW])
    mattress = isin([B.MATTRESS])
    head = isin(B.HEADBOARD)
    posts = isin(B.HEAD_POSTS + B.FOOT_POSTS)
    foot_posts = isin(B.FOOT_POSTS)
    cross = isin(B.CROSS_SLATS)
    iron = isin(B.IRON_PARTS)
    baked = pillow | mattress | head | posts          # texels the high-poly stands in for

    M = {k: baked & (mid == v) for k, v in IDS.items()}
    top_low = nrm[..., 2] > 0.6
    # every mattress texel is deck (top) or apron (sides) unless it is a gap, nail or leaf; texels the
    # bake saw as towel (deck under the towel's edge) or joist ends (under the apron) included
    deck = mattress & top_low & ~(M["cavity"] | M["nail"] | M["leaf"])
    apron = mattress & ~top_low & ~M["nail"]
    wood_mat = deck | apron | M["headboard"] | M["post"]

    # along / across coordinates for the grain, per part
    top = nrm[..., 2] > 0.6
    along = np.where(deck, x, np.where(apron & (np.abs(nrm[..., 1]) > np.abs(nrm[..., 0])), x,
                     np.where(apron, y, np.where(M["headboard"], y, np.where(M["post"], z, x)))))
    across = np.where(deck, y, np.where(apron | M["headboard"], z, np.where(M["post"], x + y, y + z)))
    across = across + 37.0 * rnd                       # each board its own grain
    g = grain(along, across, SEED)
    big = fbm(x * 0.02 + 3, y * 0.02 + z * 0.02, SEED + 3, 3) - 0.5

    col = np.zeros((SIZE, SIZE, 3)) + STEAMED
    spec = np.full((SIZE, SIZE), 0.06)
    gloss = np.full((SIZE, SIZE), 0.22)
    hgt = np.zeros((SIZE, SIZE))

    # ---------------- wood base: per-board tone, grey/warm mix, grain
    tone = rnd
    greyness = np.clip(0.3 + 0.55 * hash1((rnd * 1000).astype(int), SEED + 1) + 0.3 * big, 0, 1)
    base = ASPEN * (1 - greyness[..., None] * 0.6) + ASPEN_GREY * (greyness[..., None] * 0.6)
    base = base * (0.9 + 0.16 * tone[..., None])
    wood = base * (0.86 + 0.2 * g[..., None]) * (1 + 0.08 * big[..., None])
    hgt += np.where(wood_mat, 0.035 * g, 0)

    # pallet slat: darker, browner, rougher, old nail holes in groups of three at stringer pitch
    pal = M["pallet"]
    wood = np.where(pal[..., None], wood * np.array([0.8, 0.74, 0.68]), wood)
    holes = np.zeros((SIZE, SIZE))
    if pal.any():
        yc = np.median(y[pal & top])
        for hx in (-92.0, -31.0, 30.0, 88.0):
            for k, dy in enumerate((-2.6, 0.0, 2.6)):
                hx2 = hx + 0.7 * (k - 1) + float(rng.uniform(-0.5, 0.5))
                d = np.hypot(x - hx2, y - (yc + dy))
                holes = np.maximum(holes, smooth(0.32, 0.18, d) * pal)
        ring_h = np.zeros_like(holes)
        for hx in (-92.0, -31.0, 30.0, 88.0):
            ring_h = np.maximum(ring_h, smooth(3.5, 0.5, np.hypot((x - hx) * 0.6, y - yc)) * pal)
        wood = wood * (1 - 0.15 * ring_h[..., None]) + RUST * 0.6 * (0.15 * ring_h[..., None])
    hgt -= 0.25 * holes
    wood = wood * (1 - 0.75 * holes[..., None])

    # ---------------- deck: polished lie zone, worn edges, gaps, foot end smoked, the tub ring
    lie = smooth(0, 1, (1 - np.abs((x + 5) / 70) ** 2.5) * (1 - np.abs(y / 36) ** 3)) * deck
    lie = lie * (0.8 + 0.4 * fbm(x * 0.05, y * 0.05, SEED + 21, 2))
    wood = wood * (1 + 0.05 * lie[..., None])
    wood = wood * (1 - 0.4 * lie[..., None] * (g[..., None] - 0.5) * 0.3)      # grain softer where polished
    convex = smooth(0.52, 0.7, curv)
    concave = smooth(0.48, 0.3, curv)
    wood = wood * (1 + 0.12 * convex[..., None]) * (1 - 0.25 * concave[..., None])
    smoke_foot = smooth(-88, -113, x) * (deck | apron)
    smoke_foot = smoke_foot * (0.75 + 0.5 * fbm(y * 0.06, z * 0.1 + x * 0.03, SEED + 31, 3))
    wood = wood * (1 - 0.5 * smoke_foot[..., None]) + SMOKED * (0.5 * smoke_foot[..., None]) * 0.6
    # dried-out cracks at the foot: thin dark lines along the grain
    crack = smooth(0.965, 0.995, vnoise(along * 0.05, across * 1.3, SEED + 41)) * smooth(-80, -108, x) * (deck | apron)
    wood = wood * (1 - 0.55 * crack[..., None])
    hgt -= 0.12 * crack
    # faint mineral ring from the wash tub near the foot end: broken, uneven, a damp disc inside
    ang = np.arctan2(y + 27, x + 86)
    rc = np.hypot(x + 86.0, y + 27.0) * (1 + 0.04 * np.sin(ang * 3 + 1.0))
    brk = smooth(0.3, 0.6, vnoise(ang * 2.2 + 7, 0.5, SEED + 51))
    ring = np.exp(-((rc - 12.5) / 0.6) ** 2) * brk * (0.6 + 0.4 * g) * deck
    disc = smooth(12.5, 10.0, rc) * deck * 0.5
    wood = wood * (1 - 0.06 * disc[..., None])
    wood = wood * (1 - 0.24 * ring[..., None]) + MINERAL * (0.24 * ring[..., None])

    # ---------------- apron: wet bottom with mineral streaks, a shade darker than the deck
    ap = apron
    wet = smooth(47, 38, z) * ap
    streak = (fbm(along * 0.25, 1.0, SEED + 61, 3) - 0.45) * 2
    minr = np.clip(streak, 0, 1) * smooth(52, 40, z) * ap * 0.6
    wood = np.where(ap[..., None], wood * 0.88, wood)
    wood = wood * (1 - 0.32 * wet[..., None]) * (1 - 0.15 * np.clip(-streak, 0, 1)[..., None] * wet[..., None])
    wood = wood * (1 - 0.3 * minr[..., None]) + MINERAL * (0.3 * minr[..., None])

    # ---------------- posts: darker toward the floor, mineral streaks; foot posts smoked
    po = M["post"]
    wood = np.where(po[..., None], wood * 0.92, wood)
    pfloor = smooth(30, -2, z) * po
    wood = wood * (1 - 0.45 * pfloor[..., None])
    pstreak = np.clip((fbm(across * 0.5, 2.0, SEED + 71, 3) - 0.5) * 2.5, 0, 1) * smooth(45, 5, z) * po
    wood = wood * (1 - 0.25 * pstreak[..., None]) + MINERAL * (0.25 * pstreak[..., None]) * smooth(20, 35, z)[..., None]
    psm = foot_posts & po
    psmoke = smooth(15, 62, z) * psm * (0.85 + 0.15 * fbm(z * 0.05, x * 0.1, SEED + 73, 2))
    wood = wood * (1 - 0.45 * psmoke[..., None]) + SMOKED * (0.3 * psmoke[..., None])
    endgrain = po & top
    wood = np.where(endgrain[..., None], wood * 0.82, wood)

    # ---------------- headboard: door boards, steam-darkened, paint islands (green / red)
    hb = M["headboard"]
    # weathered door wood: grey-brown, not fresh pine
    door_wood = STEAMED * 0.75 + ASPEN_GREY * 0.35
    door = door_wood * (0.84 + 0.26 * g[..., None]) * (1 + 0.1 * big[..., None])
    # paint chips: faded green on the upper board, faded brick red on the lower; ~25% left,
    # mostly away from the edges and in a few big islands, crisp chipped borders
    upper = z > 64.2
    # the lower board was red in the original; faded blue instead: red chips next to the towel
    # read as blood
    pcol = np.where(upper[..., None], hexc("#5F7350"), hexc("#566A78"))
    # v1.1: in game the islands read as stickers -> smaller broken chips, paint muted toward the wood
    pn = fbm(y * 0.045 + 11 * upper, z * 0.11, SEED + 81, 5) + 0.12 * (g - 0.5)
    pn = pn + 0.09 * (vnoise(y * 0.5, z * 0.9, SEED + 83) - 0.5)
    keep = smooth(0.57, 0.585, pn) * hb
    chip = smooth(0.55, 0.57, pn) * hb * (1 - keep)                     # bare grey wood ring at the chip edge
    pcol = pcol * 0.7 + door_wood * 0.3
    door = door * (1 - keep[..., None]) + pcol * (0.82 + 0.25 * g[..., None]) * keep[..., None]
    door = door * (1 - 0.35 * chip[..., None]) + ASPEN_GREY * (0.35 * chip[..., None])
    hgt += np.where(hb, 0.06 * keep, 0)
    # ghost of a removed hinge on the lower board, inner face: lighter wood, three screw holes
    inner = hb & (nrm[..., 0] < -0.6) & (z < 64)
    gh = smooth(0.4, 0.0, np.maximum(np.abs(y - 28.0) - 4.0, np.abs(z - 56.0) - 1.6)) * inner
    door = door * (1 - 0.35 * gh[..., None]) + ASPEN * (0.35 * gh[..., None])
    for sy in (25.3, 28.0, 30.7):
        sh = smooth(0.3, 0.15, np.hypot(y - sy, z - 56.0)) * inner
        door = door * (1 - 0.8 * sh[..., None])
        hgt -= 0.2 * sh
    door = door * (1 + 0.1 * convex[..., None]) * (1 - 0.2 * concave[..., None])
    wood = np.where(hb[..., None], door, wood)

    col = np.where(wood_mat[..., None], wood, col)
    spec = np.where(wood_mat, 0.06, spec)
    gloss = np.where(wood_mat, 0.2 + 0.16 * lie + 0.1 * wet - 0.08 * smoke_foot + 0.06 * keep, gloss)

    # ---------------- gaps and cavities
    cav = baked & M["cavity"] & ~apron
    col = np.where(cav[..., None], GAP * (0.8 + 0.3 * rnd[..., None]), col)

    # ---------------- nails: dark iron heads, rust bleeding into the wood
    nail = baked & M["nail"]
    nm = nail.astype(np.float64)
    halo = np.clip(blur(nm, 3) * 3.0, 0, 1) * (1 - nm)
    halo2 = np.clip(blur(nm, 7) * 2.5, 0, 1) * (1 - nm)
    nrust = smooth(0.45, 0.8, vnoise(x * 2 + y, z * 2, SEED + 91))
    ncol = IRON * (1 - 0.6 * nrust[..., None]) + RUST * 0.7 * (0.6 * nrust[..., None])
    ncol = ncol * (0.85 + 0.4 * convex[..., None])
    col = np.where(nail[..., None], ncol, col)
    HALO = hexc("#4E3424")                                              # wet dark iron stain, a hint of rust
    col = col * (1 - 0.45 * halo[..., None]) + HALO * (0.45 * halo[..., None])
    col = col * (1 - 0.14 * halo2[..., None])
    spec = np.where(nail, 0.25 - 0.12 * nrust, spec)
    gloss = np.where(nail, 0.35 - 0.15 * nrust, gloss)

    # ---------------- birch leaves
    lf = baked & M["leaf"]
    lcol = LEAF_GREEN * (1 - rnd[..., None]) + LEAF_DRY * rnd[..., None]
    lcol = lcol * (0.85 + 0.25 * vnoise(x * 1.5, y * 1.5, SEED + 95)[..., None]) * (1 - 0.3 * concave[..., None])
    col = np.where(lf[..., None], lcol, col)
    gloss = np.where(lf, 0.3, gloss)

    # ---------------- towel: washed linen, brick stripes near both ends, damp underneath
    tw = pillow & ((mid == IDS["towel"]) | (mid == IDS["base"]))
    ay = np.abs(y)
    stripes = (smooth(0.0, 0.25, 1.25 - np.abs(ay - 38.6)) + smooth(0.0, 0.2, 0.45 - np.abs(ay - 35.9)))
    stripes = np.clip(stripes, 0, 1) * (0.75 + 0.25 * vnoise(x * 0.6, z * 0.6, SEED + 101))
    weave = 0.5 + 0.25 * np.sin(x * 9.0) * np.sin(z * 9.0 + y * 9.0)
    tcol = LINEN * (0.95 + 0.06 * weave[..., None]) * (1 + 0.04 * big[..., None])
    tcol = tcol * (1 - 0.85 * stripes[..., None]) + BRICK * (0.85 * stripes[..., None])
    damp = smooth(57.5, 54.0, z) * tw
    tcol = tcol * (1 - 0.18 * damp[..., None])
    tcol = tcol * (1 - 0.25 * concave[..., None])
    col = np.where(tw[..., None], tcol, col)
    spec = np.where(tw, 0.04, spec)
    gloss = np.where(tw, 0.1 + 0.08 * damp, gloss)
    hgt += np.where(tw, 0.02 * weave, 0)

    # ---------------- cross slats (joists under the deck): wet dark wood, original detail kept
    detail = 1 + 0.45 * (np.clip(lum / np.maximum(blur(lum, 12), 1e-3), 0.6, 1.3) - 1)
    # v1.1: in game they came out orange -> dark grey-brown, wet
    jc = hexc("#4E4034") * (0.88 + 0.22 * grain(x, y + z, SEED + 111)[..., None]) * detail[..., None]
    col = np.where(cross[..., None], jc, col)
    gloss = np.where(cross, 0.3, gloss)

    # ---------------- iron: dark steel, rust in joints (AO) and at the bottom, drips
    # v1.1: AO-driven rust drew an orange line where the joists sit on the rail -> weaker, deeper AO only
    rmask = smooth(0.6, 0.25, ao) * 0.5 + smooth(0.0, -0.6, nrm[..., 2]) * 0.5
    rmask = rmask + 0.35 * (fbm(x * 0.08, y * 0.08 + z * 0.08, SEED + 121, 4) - 0.5) * 2
    drips = np.clip((vnoise(x * 0.35 + y * 0.35, z * 0.03, SEED + 125) - 0.7) * 3, 0, 1) * (np.abs(nrm[..., 2]) < 0.5)
    rmask = np.clip(rmask + 0.4 * drips, 0, 1)
    rmask = smooth(0.35, 0.8, rmask)
    ic = IRON * (1 - rmask[..., None]) + (RUST * 0.8 + IRON * 0.2) * rmask[..., None]
    ic = ic * (0.75 + 0.5 * lum[..., None]) * (0.9 + 0.2 * vnoise(x * 0.5, y * 0.5 + z, SEED + 127)[..., None])
    col = np.where(iron[..., None], ic, col)
    spec = np.where(iron, 0.32 - 0.22 * rmask, spec)
    gloss = np.where(iron, 0.4 - 0.25 * rmask, gloss)

    # ---------------- AO into colour (the game's AO only darkens ambient light)
    col = col * (0.55 + 0.45 * ao[..., None]) ** 0.8

    # ---------------- alpha: the blanket is gone
    alpha = np.where(blanket, 0.0, 1.0)
    col[blanket] = ASPEN * 0.8
    col[pid < 0] = STEAMED * 0.8

    # ---------------- normal: baked + detail where modelled, original elsewhere
    dx, dy = height_normal(hgt, 6.0)
    n = np.where(baked[..., None], nb, on)
    n[..., 0] += dx
    n[..., 1] += dy
    n[blanket] = (0, 0, 1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9

    occ = np.where(blanket, 1.0, 0.35 + 0.65 * ao)
    return col, alpha, n, spec, gloss, occ


def main():
    col, alpha, n, spec, gloss, occ = build()
    OUT.mkdir(exist_ok=True)
    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    Image.fromarray(np.dstack([q(col), q(alpha)]), "RGBA").save(OUT / "Bed_v1.1_diffuse.png")
    Image.fromarray(q(n * 0.5 + 0.5), "RGB").save(OUT / "Bed_v1.1_normal.png")
    Image.fromarray(np.dstack([q(spec), q(spec), q(spec), q(gloss)]), "RGBA").save(OUT / "Bed_v1.1_specgloss.png")
    Image.fromarray(q(occ), "L").save(OUT / "Bed_v1.1_occlusion.png")
    print("done")


if __name__ == "__main__":
    main()
