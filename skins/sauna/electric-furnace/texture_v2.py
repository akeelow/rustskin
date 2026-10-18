"""Sauna Stove v2: textures driven by the high-poly bake (bake_v2.py).

Colour, wear, soot and glow come from the baked maps instead of noise alone:
  id.png        which part a texel shows (board, gap, nail, stone, mortar, bar, rivet ...)
                and a random value per board/stone for its tone;
  curvature.png worn, lighter edges on boards, stones and iron;
  ao.png        dirt in crevices, darker gaps, the Occlusion slot;
  normal.png    the Normal slot (plus fine wood grain / stone speckle from the v1 noise).
Texels the bake leaves flat (top-plate rim, knobs, oven interior, iron band) keep the v1 look.

    .venv/Scripts/python skins/sauna/electric-furnace/texture_v2.py
Writes export/ElectricFurnace_v2_{diffuse,normal,metalgloss,occlusion,emission}.png
and uv/v2_views.png, uv/v2_views_emission.png.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image as PILImage

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "tools"))
import texture_v1 as v1  # noqa: E402
from texture_v1 import (BACK, EMBER_RGB, EMBERS, IRON, KNOB, PALLET, PANEL, PLINTH, RIM, SEED,  # noqa: E402
                        SIDE, SIZE, STONES, fbm, hexc, smooth)
from uv_zones import classify, load_obj, normal, read_png, render_views  # noqa: E402

BAKE = HERE / "bake"
ORIG = HERE / "originals"
OUT = HERE / "export"
ID = {"base": 0, "board": 1, "nail": 2, "stone": 3, "plinth": 4, "mortar": 5, "bar": 6, "rivet": 7,
      "pallet": 8, "trim": 9}  # must match bake_v2.IDS


def load(name, mode):
    im = PILImage.open(BAKE / f"{name}.png").convert(mode)
    if im.size != (SIZE, SIZE):
        im = im.resize((SIZE, SIZE), PILImage.BILINEAR if mode != "RGB" or name != "id" else PILImage.NEAREST)
    return np.asarray(im, np.float64) / 255


def whiteout(a, b):
    n = np.stack([a[..., 0] + b[..., 0], a[..., 1] + b[..., 1], a[..., 2] * b[..., 2]], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def main():
    V, T, F = load_obj(ORIG / "electric.furnace.obj")
    N = [normal(*(V[i] for i in vi)) for vi, _ in F]
    print("classifying zones ...")
    zone = classify(V, F, N)
    print("rasterising position maps ...")
    pos, nrm, zid, dens, filled = v1.position_maps(V, T, F, N, zone)
    em0 = np.asarray(PILImage.open(ORIG / "ElectricFurnace_em.png").convert("RGB").resize((SIZE, SIZE), PILImage.NEAREST))
    glow0 = em0[..., 0] > 60
    mat, zid = v1.material_map(pos, nrm, zid, glow0)
    print("v1 base layer ...")
    col, height, metal, gloss, emit, cavity, orig_w = v1.build(pos, nrm, mat, zid, glow0)

    print("baked maps ...")
    idm = load("id", "RGB")
    pid = np.clip(np.round((idm[..., 0] * 255 - 8) / 16), 0, 15).astype(np.int8)
    rnd = idm[..., 1]
    ao_b = load("ao", "L")
    curv = load("curvature", "L")
    nb = load("normal", "RGB") * 2 - 1
    nb /= np.maximum(np.linalg.norm(nb, axis=-1, keepdims=True), 1e-6)

    x, y, z = (pos[..., i].astype(np.float64) for i in range(3))
    vertical = np.abs(nrm[..., 1]) < 0.7
    along_x = np.abs(nrm[..., 2]) >= np.abs(nrm[..., 0])
    h = np.where(along_x, x, z)
    edge = smooth(0.56, 0.75, curv)      # convex: worn edges
    crev = smooth(0.46, 0.3, curv)       # concave: dirt lines
    dirt = smooth(0.85, 0.35, ao_b)      # occluded: grime
    wood_zone = np.isin(mat, (SIDE, BACK, PANEL))
    micro = np.zeros(mat.shape)          # fine height on top of the baked normal (metres)

    def put(m, c, me=None, gl=None):
        col[m] = c[m] if np.ndim(c) == 3 else c
        if me is not None:
            metal[m] = me[m] if np.ndim(me) else me
        if gl is not None:
            gloss[m] = gl[m] if np.ndim(gl) else gl

    # ------------------------------------------------ planks (sides, back, panel, right-hand frame)
    board = pid == ID["board"]
    # gaps: bare texels right between planks; wood-zone texels far from any plank (the drum
    # in the right-hand opening, the plate edge) keep the painted v1 slats
    near = (board | (pid == ID["trim"])).copy()
    grown = near.copy()
    for _ in range(4):
        for dyy, dxx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            grown |= np.roll(np.roll(near, dyy, 0), dxx, 1)
        near = grown.copy()
    gap = wood_zone & (pid == ID["base"]) & grown
    horiz = (mat == PANEL) | ((x > 0.3) & ((y < 0.35) | (y > 1.05)))   # planks laid along the face
    lu = np.where(horiz, h, y)          # along the plank
    lv = np.where(horiz, y, h)          # across the plank
    grain = fbm(lv * 260, lu * 9, rnd * 37, 4, SEED + 1)
    rings = np.sin((lv * 900 + 6 * fbm(lv * 30, lu * 4, rnd * 11, 3, SEED + 2)) ) * 0.5 + 0.5
    knots = smooth(0.8, 0.88, fbm(lv * 40, lu * 18, rnd * 23, 2, SEED + 3))
    steam = smooth(0.95, 1.14, y)
    stain = smooth(0.55, 0.75, fbm(h * 6, y * 3, 0 * h, 4, SEED + 4)) * smooth(0.55, 0.35, y)
    drips = smooth(0.62, 0.72, fbm(h * 90, y * 2.5, rnd * 5, 3, SEED + 5)) * smooth(0.5, 1.1, y)
    # scorch around the firebox door (heat rises: stronger above it), as in v1.3
    dx = np.maximum(np.abs(x) - 0.30, 0)
    dy = np.maximum(np.maximum(0.33 - y, y - 0.93), 0)
    dz = np.maximum(0.33 - z, 0)
    sn = fbm(x * 30, y * 30, z * 30, 4, SEED + 6)
    scorch = np.clip((1 - smooth(0.0, 0.16, np.sqrt(dx ** 2 + dy ** 2 + dz ** 2) + 0.04 * (sn - 0.5)))
                     * (0.5 + 0.8 * smooth(0.55, 0.95, y)), 0, 1) * (z > 0.20)
    base = np.where((mat == BACK)[..., None], hexc("#7A5A3C"), hexc("#C2A77E"))
    darker = np.where(mat == BACK, 0.15, np.where(mat == PANEL, 0.3, 0.25))
    wc = base * (0.84 + 0.3 * rnd[..., None])
    wc = wc * (0.86 + 0.2 * grain[..., None]) * (0.95 + 0.07 * rings[..., None])
    wc = wc * (1 - 0.35 * knots[..., None])
    wc = wc * (1 - darker * steam)[..., None] * (1 - 0.28 * stain[..., None]) * (1 - 0.2 * drips[..., None])
    wc = wc * (1 + 0.28 * edge[..., None])                            # worn edges
    wc = wc * (1 - 0.35 * np.maximum(dirt, crev)[..., None])          # grime in corners and along nails
    char = hexc("#1C120B") * (0.7 + 0.6 * sn[..., None])
    wc = wc * (1 - 0.88 * scorch[..., None]) + char * 0.88 * scorch[..., None]
    wsel = board | (wood_zone & (pid == ID["trim"]))
    put(wsel, wc, 0, (30 + 45 * stain + 30 * drips) * (1 - 0.6 * scorch) * (1 - 0.4 * edge))
    micro[wsel] = (0.00025 * grain - 0.0003 * knots + 0.00015 * rings)[wsel]
    # gaps between planks: the sooty metal behind them
    put(gap, hexc("#231B15") * (0.8 + 0.4 * sn[..., None]), 40, 25)
    nail = pid == ID["nail"]
    nc = hexc("#3A3430") * (0.8 + 0.5 * edge[..., None]) + hexc("#5A3A26") * 0.3 * dirt[..., None]
    put(nail, nc, 150 - 60 * dirt, 70 + 40 * edge)
    # rust halo under nail heads leaks onto the wood around them
    halo = np.zeros(mat.shape, bool)
    for dyy, dxx in ((0, 3), (0, -3), (3, 0), (-3, 0), (2, 2), (-2, -2), (2, -2), (-2, 2)):
        halo |= np.roll(np.roll(nail, dyy, 0), dxx, 1)
    halo &= wsel & ~nail
    col[halo] = col[halo] * 0.75 + hexc("#5A3A26") * 0.25

    # ------------------------------------------------ burner heaps: basalt, white mineral, glowing bed
    stone = pid == ID["stone"]
    speck = fbm(x * 900, z * 900, y * 900, 2, SEED + 11)
    t = rnd[..., None]
    sc = hexc("#26272A") * (1 - t) + hexc("#47464A") * t
    sc = sc * (0.85 + 0.25 * speck[..., None])
    mineral = smooth(0.7, 0.78, fbm(x * 60, y * 60, z * 60, 3, SEED + 12)) * smooth(0.6, 0.9, ao_b)
    sc = sc * (1 - 0.4 * mineral[..., None]) + hexc("#BDB7AC") * 0.4 * mineral[..., None]
    sc = sc * (1 + 0.35 * edge[..., None]) * (0.55 + 0.45 * ao_b[..., None])
    put(stone, sc, 0, 45 + 35 * mineral + 30 * edge)
    micro[stone] = (0.0003 * speck)[stone]
    burner = (mat == STONES) | ((mat == RIM) & stone)
    bed = (mat == STONES) & ~stone
    # the glow lives in the deep gaps between rocks, never on their tops
    flicker = 0.55 + 0.45 * fbm(x * 30, z * 30, y, 3, SEED + 13)
    deep = smooth(0.75, 0.25, ao_b)
    put(bed, hexc("#1A1210") * (1 - deep[..., None]) + hexc("#3A1A0E") * deep[..., None], 0, 30)
    # only the dish floor between rocks glows; the dish's inner wall (exposed once the coils are
    # cut away) glowed as a bright ring in game (v2.1), so it stays dark soot
    floor = (nrm[..., 1] > 0.75) & (y < 1.145)  # dish floor, not the tops of the coil turns left in place
    glow = np.where(bed & floor, 0.85 * deep * flicker, 0)
    bcx = np.where(x > 0, 0.143, -0.143)
    bcz = np.where(z > 0, 0.1435, -0.1435)
    in_dish = (y > 1.13) & (np.hypot(x - bcx, z - bcz) < 0.1) & (np.abs(x) < 0.3) & (np.abs(z) < 0.3)
    wall = in_dish & ~stone & ~floor
    put(wall, hexc("#1E1714") * (0.8 + 0.4 * flicker[..., None]), 0, 25)
    emit[wall] = 0
    glow = glow + np.where(stone & (mat == STONES), 0.25 * smooth(0.45, 0.15, ao_b) * flicker, 0)  # rock undersides
    emit[burner | bed] = 0
    emit += glow[..., None] * EMBER_RGB

    # ------------------------------------------------ fieldstone plinth on mortar
    pst = pid == ID["plinth"]
    # upward faces of the lumpy original plinth come out as "top plate" (RIM) in the v1 map and
    # showed as rusty streaks along the stones in game (v2.1): they are mortar too
    plinth_tops = (mat == RIM) & (y > 0.04) & (y < 0.27)
    print(f"  plinth tops repainted: {(plinth_tops & (pid == ID['base'])).sum()} texels")
    mor = (pid == ID["mortar"]) | (((mat == PLINTH) | plinth_tops) & (pid == ID["base"]))
    pt = rnd[..., None]
    pc = hexc("#4E4943") * (1 - pt) + hexc("#8A7F72") * pt
    pc = pc * (0.85 + 0.3 * fbm(x * 500, y * 500, z * 500, 2, SEED + 51)[..., None])
    lichen = smooth(0.66, 0.74, fbm(x * 25, y * 25, z * 25, 3, SEED + 52)) * smooth(0.2, 0.06, y)
    pc = pc * (1 - 0.25 * lichen[..., None]) + hexc("#5C6A39") * 0.25 * lichen[..., None]
    pc = pc * (1 + 0.08 * edge[..., None]) * (0.8 + 0.2 * ao_b[..., None])
    wet = smooth(0.11, 0.05, y)
    pc = pc * (1 - 0.3 * wet[..., None])
    put(pst, pc, 0, 40 + 60 * wet)
    mc = hexc("#968E81") * (0.8 + 0.3 * fbm(x * 200, y * 200, z * 200, 3, SEED + 53)[..., None])
    mc = mc * (0.7 + 0.3 * ao_b[..., None]) * (1 - 0.3 * wet[..., None])
    put(mor, mc, 0, 30 + 50 * wet)
    micro[pst] = (0.0004 * fbm(x * 300, y * 300, z * 300, 3, SEED + 54))[pst]
    micro[mor] = (0.0003 * fbm(x * 400, y * 400, z * 400, 2, SEED + 55))[mor]

    # ------------------------------------------------ forged bars and rivets
    bar = (pid == ID["bar"]) | (pid == ID["rivet"])
    mott = fbm(x * 40, y * 40, z * 40, 4, SEED + 30)
    rust = smooth(0.66, 0.78, fbm(x * 22, y * 22, z * 22, 4, SEED + 31)) * (0.4 + 0.6 * dirt)
    ic = hexc("#2A2725") * (0.8 + 0.4 * mott[..., None])
    ic = ic * (1 - rust[..., None]) + hexc("#5A3A26") * (0.8 + 0.4 * mott[..., None]) * rust[..., None]
    ic = ic * (1 + 0.9 * edge[..., None] * (1 - rust[..., None]))       # polished by hands and pokers
    put(bar, ic, 150 - 110 * rust + 60 * edge, 70 - 45 * rust + 60 * edge)

    # ------------------------------------------------ pallet planks
    pal = pid == ID["pallet"]
    pg = fbm(z * 260, x * 9, rnd * 41, 4, SEED + 60)
    pc = hexc("#6B4F36") * (0.8 + 0.3 * rnd[..., None]) * (0.85 + 0.25 * pg[..., None])
    pc = pc * (1 + 0.2 * edge[..., None]) * (0.55 + 0.45 * ao_b[..., None])
    put(pal, pc, 0, 115 - 40 * edge)
    pgap = (mat == PALLET) & (pid == ID["base"])
    put(pgap, hexc("#24190F"), 0, 60)
    micro[pal] = (0.0003 * pg)[pal]

    # ------------------------------------------------ normal: baked + fine detail; flat leftovers keep v1
    detail = pid != ID["base"]
    keep_v1 = ~detail & ~gap & ~bed & ~pgap & ~mor
    height = np.where(keep_v1, height, micro)
    n_fine = v1.height_to_normal(height, pos, dens, mat, strength=3.0)
    n0 = np.asarray(PILImage.open(ORIG / "ElectricFurnace_nrm.png").convert("RGB"), np.float64) / 255 * 2 - 1
    n0[..., 2] = np.sqrt(np.clip(1 - n0[..., 0] ** 2 - n0[..., 1] ** 2, 0, 1))
    w = np.where(keep_v1, orig_w, 0)[..., None]
    n0 = n0 * w + np.array([0.0, 0.0, 1.0]) * (1 - w)
    n0 /= np.maximum(np.linalg.norm(n0, axis=-1, keepdims=True), 1e-6)
    # masonry: the low-poly is already lumpy, so full-strength stone edges read as pillows
    # with white rims in game (v2) -> soften them
    soft = (pst | mor)[..., None]
    nb = np.where(soft, nb * np.array([0.45, 0.45, 1.0]), nb)
    nb /= np.linalg.norm(nb, axis=-1, keepdims=True)
    nrm_out = whiteout(whiteout(nb, n_fine), n0)

    # ------------------------------------------------ occlusion: original x baked
    ao0 = np.asarray(PILImage.open(ORIG / "ElectricFurnace_AO.png").convert("L").resize((SIZE, SIZE), PILImage.BILINEAR), np.float64) / 255
    ao = np.clip(ao0 * (0.35 + 0.65 * ao_b), 0, 1)
    ao = np.where(burner | bed, ao_b, ao)   # the original AO still draws the coils; the heap has its own

    OUT.mkdir(exist_ok=True)
    rgba = lambda rgb, a=None: np.dstack([rgb, np.full(rgb.shape[:2], 255, np.uint8) if a is None else a]).astype(np.uint8)
    PILImage.fromarray(rgba((np.clip(col, 0, 1) * 255).round())).save(OUT / "ElectricFurnace_v2_diffuse.png")
    # experiment: alpha 0 on the coil spirals (texels above the burner dish), for Alpha Cutoff 0.5;
    # the dish under them carries the same baked heap, so the spirals' outline disappears
    cx = np.where(x > 0, 0.143, -0.143)
    cz = np.where(z > 0, 0.1435, -0.1435)
    # cut radius per burner: wider and the cut opens a slot between dish and ring through which
    # the stove's insides show (seen as glowing rings in game, v2.1); checked by ray casts in Blender
    big = (x > 0) == (z > 0)
    coil = (y > 1.145) & (np.hypot(x - cx, z - cz) < np.where(big, 0.083, 0.06)) & (np.abs(x) < 0.3) & (np.abs(z) < 0.3)
    alpha = np.where(coil, 0, 255)
    PILImage.fromarray(rgba((np.clip(col, 0, 1) * 255).round(), alpha)).save(OUT / "ElectricFurnace_v2_diffuse_cutout.png")
    nr = np.dstack([(nrm_out[..., 0] * 0.5 + 0.5) * 255, (nrm_out[..., 1] * 0.5 + 0.5) * 255, np.full(mat.shape, 255)]).round()
    PILImage.fromarray(rgba(nr)).save(OUT / "ElectricFurnace_v2_normal.png")
    mrgb = np.repeat(np.clip(metal, 0, 255)[..., None], 3, -1).round()
    PILImage.fromarray(rgba(mrgb, np.clip(gloss, 0, 215).round())).save(OUT / "ElectricFurnace_v2_metalgloss.png")
    ao_small = PILImage.fromarray((ao * 255).round().astype(np.uint8)).resize((512, 512), PILImage.BOX)
    PILImage.fromarray(rgba(np.repeat(np.asarray(ao_small)[..., None], 3, -1))).save(OUT / "ElectricFurnace_v2_occlusion.png")
    em_small = PILImage.fromarray((np.clip(emit, 0, 1) * 255).round().astype(np.uint8)).resize((512, 512), PILImage.BOX)
    em_arr = np.clip(np.asarray(em_small, np.float64) * 1.2, 0, 255)
    PILImage.fromarray(rgba(em_arr.round())).save(OUT / "ElectricFurnace_v2_emission.png")

    print("rendering previews ...")
    render_views(V, T, F, N, HERE / "uv" / "v2_views.png", tex=read_png(OUT / "ElectricFurnace_v2_diffuse.png"))
    render_views(V, T, F, N, HERE / "uv" / "v2_views_emission.png", tex=read_png(OUT / "ElectricFurnace_v2_emission.png"))
    share = {k: f"{(pid == i).mean():.1%}" for k, i in ID.items()}
    print("done; baked id share:", share)


if __name__ == "__main__":
    main()
