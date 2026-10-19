"""Sauna Changing Locker v4: the designer's board - rich joinery, built-in warm light, lime wood.

references/sauna/locker/designer_detailed_skin.html: an ordinary sauna locker in linden that looks
expensive through carpentry, not props: a cornice board, a frieze with a groove and a row of vent
holes, chamfered stiles with paired dowels, tongue-and-groove lining on the back, a lamp with a
wooden grille on the back wall, a hanger rail with three pegs, vertical vent slots, slatted shelves,
a framed drawer front, a slotted plinth on steel feet; outside, sides and back as frame-and-panel
with vents. Wear: water at the bottom, rubbed edges at hand height, board-to-board tone, shadow in
the corners. Light: a hidden LED slit under the frieze, strips on the shelf fronts, the lamp grille,
weak glow in the holes and slots.

Corrections for this model (see README): the three niches share one UV patch (identical niches, as
on the board); shelf top and underside share UVs, so the LED is on the shelf front edge; the bottom
niche's back wall is a sliver in the UV layout (no slots there); the glow of the light on the wood
goes into Emission (Diffuse is black at night), weaker than the strips.

Everything is placed in unit-local x: the carcass is three 60 cm units (centres -60, 0, 60), whose
parts mostly share UV patches. Doors are cut with alpha (texture_v2.open_doors).

    .venv/Scripts/python skins/sauna/locker/texture_v4.py
Writes export/Locker_v4_{diffuse,normal,specgloss,emission}.png and uv/v4_views.png.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
import importlib.util  # noqa: E402


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


v1 = load("locker_v1", "texture_v1.py")
v2 = load("locker_v2", "texture_v2.py")
blur, hexc, smooth, fbm, hash3 = v1.blur, v1.hexc, v1.smooth, v1.fbm, v1.hash3
SIZE, OUT, ORIG = v1.SIZE, v1.OUT, v1.ORIG
from uv_zones import load_obj, normal  # noqa: E402

SEED = 41
LIME_LIGHT = hexc("#D8AA70")    # shelves, pegs, grille
LIME_OLD = hexc("#A8743E")      # stiles, frame, drawer
LINING = hexc("#9A6534")        # back wall, sides (tongue-and-groove)
THERMO = hexc("#6A4426")        # plinth, cornice
GROOVE = hexc("#24160C")        # depth of grooves, slots, holes
STEEL = hexc("#4A4A4A")
LED = np.array([1.0, 0.80, 0.52])        # warm white, not orange
WARM = np.array([1.0, 0.86, 0.66])       # tint of the light on the wood

UNITS = np.array([-60.0, 0.0, 60.0])
SHELVES = (49.0, 84.0, 165.0)            # shelf tops (cm); floor 15, ceiling 217
LIGHTS = (217.0, 165.0, 84.0, 49.0)      # LED rows: the slit under the frieze and the shelf fronts


def boards(across, width, key, seed):
    """Board index, fraction across the board, groove (0..1) and tone for boards of `width`."""
    b = np.floor((across + 500) / width)
    fr = (across + 500) / width - b
    groove = 1 - smooth(0.0, 0.035, fr) * smooth(1.0, 0.965, fr)
    tone = hash3(b, np.full_like(b, key), np.zeros_like(b), seed)
    return b, fr, groove, tone


def circle(cx, cy, x, y, r, soft=0.15):
    return smooth(r + soft, r - soft, np.hypot(x - cx, y - cy))


def rect(x, y, x0, x1, y0, y1, soft=0.12):
    return (smooth(x0 - soft, x0 + soft, x) * smooth(x1 + soft, x1 - soft, x)
            * smooth(y0 - soft, y0 + soft, y) * smooth(y1 + soft, y1 - soft, y))


def main():
    V, T, F = load_obj(ORIG / "locker.obj")
    N = [normal(*(V[i] for i in vi)) for vi, _ in F]
    obj = v1.object_of_faces(ORIG / "locker.obj")
    pos, nrm, oid, dens, cov, ids = v1.raster(V, T, F, obj)
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    nx, ny, nz = nrm[..., 0], nrm[..., 1], nrm[..., 2]
    m = dict(V=V, T=T, F=F, N=N, obj=obj, pos=pos, nrm=nrm, oid=oid, dens=dens, cov=cov, ids=ids)
    alpha, body, back_in, cut = v2.open_doors(m)
    rng = np.random.default_rng(SEED)

    ao = np.asarray(Image.open(ORIG / "locker_ao.png").convert("L").resize((SIZE, SIZE), Image.BILINEAR), np.float64) / 255.0
    n0 = np.asarray(Image.open(ORIG / "locker_nrm.png").convert("RGB"), np.float64) / 255 * 2 - 1
    yy = np.arange(SIZE)[:, None].repeat(SIZE, 1)
    xx = np.arange(SIZE)[None, :].repeat(SIZE, 0)
    small = (yy < 205) & (xx < 1370)                       # hinges, latch, handles, bolts (geometry)

    xu = x - UNITS[np.argmin(np.abs(x[..., None] - UNITS), -1)]      # unit-local x, -30..30
    grain = fbm(x * 0.9, y * 0.04, z * 0.9, 4, SEED + 1)
    fine = fbm(x * 6, y * 0.3, z * 6, 3, SEED + 2)

    # ---------------------------------------------------------------- surface classes
    inside = body & (z < 21) & (z > -29) & (np.abs(x) < 89.5)
    front = body & (nz > 0.7) & (z > 25.5) & ~small
    drawer = body & (nz > 0.7) & (z > 23.5) & (z < 25.5) & (np.abs(x) < 23.5) & (y < 49)
    frieze = front & (y > 216.5)
    plinth = front & (y < 15.5) & (y > 5.5)
    feet = body & (y < 5.5)
    stile = front & ~frieze & ~plinth & ~feet
    top = body & (ny > 0.7) & (y > 223)
    sides_out = body & (np.abs(nx) > 0.7) & (np.abs(x) > 89.5)
    back_out = body & (nz < -0.7) & (z < -33)
    shelf = inside & (np.abs(ny) > 0.5) & ((np.abs(y - 165) < 2.5) | (np.abs(y - 82.5) < 2.5) | (np.abs(y - 47) < 3))
    shelf_edge = body & (nz > 0.7) & (np.abs(z - 20) < 1) & (y > 40) & (y < 170)
    floor = inside & (ny > 0.5) & (y < 17)
    ceiling = inside & (ny < -0.5) & (y > 214)
    niche_side = inside & (np.abs(nx) > 0.5) & ~back_in
    back = back_in
    iron = cov & (small | feet)

    # default for every surface no class claims (stile returns, edges, small faces): old linden
    col = LIME_OLD * (0.86 + 0.24 * grain[..., None]) * (0.95 + 0.08 * fine[..., None]) * np.ones(cov.shape + (1,))
    h = np.zeros(cov.shape)
    emit_k = np.zeros(cov.shape)         # LED / lamp emission (0..1), coloured LED
    wash = np.zeros(cov.shape)           # light falling on the wood (multiplies the wood colour)
    gloss = np.full(cov.shape, 0.18)
    spec = np.full(cov.shape, 0.06)

    def wood(mask, base, tone, extra=1.0):
        c = base * (0.9 + 0.14 * tone[..., None]) * (0.86 + 0.24 * grain[..., None]) * (0.95 + 0.08 * fine[..., None]) * extra
        col[mask] = c[mask]

    # ---------------------------------------------------------------- inside: back wall (lining)
    yb = y
    b, fr, groove, tone = boards(xu, 9.0, 1, SEED + 3)
    knots = smooth(0.82, 0.88, fbm(xu * 0.5, y * 0.2, b * 3, 2, SEED + 4))
    lining_c = LINING * (0.9 + 0.14 * tone[..., None]) * (0.86 + 0.24 * grain[..., None])
    lining_c = lining_c * (1 - 0.4 * knots[..., None])
    lining_c = lining_c * (1 - groove[..., None]) + GROOVE * groove[..., None]
    col[back] = lining_c[back]
    h[back] = (-0.35 * groove + 0.08 * smooth(0, 0.15, np.minimum(fr, 1 - fr)) + 0.03 * fine)[back]

    # lamp with a wooden grille, top section
    lx, ly, lw, lh = 0.0, 191.0, 10.0, 12.0
    frame_o = rect(xu, y, lx - lw, lx + lw, ly - lh, ly + lh)
    frame_i = rect(xu, y, lx - lw + 1.6, lx + lw - 1.6, ly - lh + 1.6, ly + lh - 1.6)
    slat = (np.mod(y - (ly - lh + 1.6), 2.0) < 1.2) * frame_i
    gapg = frame_i * (1 - slat)
    lamp = back & (frame_o > 0.5)
    lc = LIME_OLD * (0.95 + 0.1 * fine[..., None])
    col = np.where((lamp & (frame_i < 0.5))[..., None], lc, col)
    col = np.where((lamp & (slat > 0.5))[..., None], LIME_LIGHT * (0.95 + 0.1 * fine[..., None]), col)
    col = np.where((lamp & (gapg > 0.5))[..., None], np.array([0.98, 0.86, 0.62]), col)
    h = np.where(lamp, 1.2 * (frame_o - frame_i) + 0.7 * slat + 0.2 * gapg, h)
    emit_k = np.where(lamp, 0.75 * gapg, emit_k)
    gloss = np.where(lamp & (gapg > 0.5), 0.6, gloss)
    halo = np.exp(-((xu - lx) ** 2 + (y - ly) ** 2) / (2 * 17.0 ** 2)) * back * (y > 165) * (frame_o < 0.5)
    wash = np.maximum(wash, 0.85 * halo)

    # hanger rail with three pegs, middle section
    rail = back & (rect(xu, y, -24, 24, 146, 150) > 0.5)
    col = np.where(rail[..., None], LIME_OLD * (0.92 + 0.12 * fine[..., None]), col)
    h = np.where(rail, 0.9, h)
    shadow = back & ~rail & (rect(xu, y + 1.5, -24, 24, 146, 150, soft=1.2) > 0.05)
    for sx in (-21.0, 21.0):
        sc = back & (circle(sx, 148, xu, y, 0.5) > 0.5)
        col = np.where(sc[..., None], STEEL, col)
        h = np.where(sc, 1.1, h)
    for px in (-14.0, 0.0, 14.0):
        pg = back & (circle(px, 145.0, xu, y, 1.3) > 0.5)
        col = np.where(pg[..., None], LIME_LIGHT, col)
        h = np.where(pg, 2.4 * np.sqrt(np.clip(1 - (np.hypot(xu - px, y - 145) / 1.3) ** 2, 0, 1)), h)
        shadow |= back & ~pg & (circle(px + 0.8, 143.2, xu, y, 1.6, soft=0.8) > 0.2)
    col = np.where(shadow[..., None], col * 0.72, col)

    # vertical vent slots, middle section
    for sx in (-5.0, 0.0, 5.0):
        sl = back & (rect(xu, y, sx - 0.7, sx + 0.7, 100, 120, soft=0.2) > 0.5)
        col = np.where(sl[..., None], GROOVE, col)
        h = np.where(sl, -0.8, h)
        emit_k = np.where(sl, 0.2, emit_k)

    # corner shadow in the niches (towards shelves, ceiling and the side walls)
    d_shelf = np.min(np.abs(y[..., None] - np.array([15.0, 49.0, 84.0, 165.0, 217.0])), -1)
    d_side = 29.0 - np.abs(xu)
    corner = np.maximum(np.exp(-d_shelf / 4.0), np.exp(-np.maximum(d_side, 0) / 4.0)) * 0.35
    col = np.where(back[..., None], col * (1 - corner[..., None]), col)

    # ---------------------------------------------------------------- inside: niche sides, shelves, floor, ceiling
    b, fr, groove, tone = boards(z, 9.0, 2, SEED + 5)
    side_c = LINING * (0.92 + 0.12 * tone[..., None]) * (0.86 + 0.24 * grain[..., None])
    side_c = side_c * (1 - groove[..., None]) + GROOVE * groove[..., None]
    col = np.where(niche_side[..., None], side_c * (1 - 0.6 * corner[..., None]), col)
    h = np.where(niche_side, -0.3 * groove, h)
    # support battens under each shelf on the side walls, two screws each
    batt = niche_side & np.any([(y > s - 4.5) & (y < s - 1.5) for s in (49.0, 84.0, 165.0)], axis=0) & (z < 18)
    col = np.where(batt[..., None], LIME_OLD * (0.95 + 0.1 * fine[..., None]), col)
    h = np.where(batt, 0.8, h)

    b, fr, groove, tone = boards(z, 7.0, 3, SEED + 6)               # shelf slats run left-right
    sgap = 1 - smooth(0.0, 0.08, fr) * smooth(1.0, 0.92, fr)
    sc = LIME_LIGHT * (0.9 + 0.14 * tone[..., None]) * (0.86 + 0.24 * grain[..., None])
    rub = smooth(12, 19, z)                                          # front edge rubbed lighter
    sc = sc * (1 + 0.12 * rub[..., None])
    sc = sc * (1 - sgap[..., None]) + GROOVE * sgap[..., None]
    col = np.where(shelf[..., None], sc, col)
    h = np.where(shelf, -0.4 * sgap + 0.05 * fine, h)
    gloss = np.where(shelf, 0.22 + 0.1 * rub, gloss)
    col = np.where(shelf_edge[..., None], LIME_LIGHT * 1.05, col)

    lat = boards(xu, 6.0, 4, SEED + 7)[2] + boards(z, 6.0, 5, SEED + 8)[2]
    col = np.where(floor[..., None], (LIME_OLD * 0.9 * (0.9 + 0.2 * grain[..., None])) * (1 - np.clip(lat, 0, 1)[..., None]) + GROOVE * np.clip(lat, 0, 1)[..., None], col)
    h = np.where(floor, -0.5 * np.clip(lat, 0, 1), h)
    col = np.where(ceiling[..., None], LINING * 0.85, col)

    # ---------------------------------------------------------------- front: stiles, frieze, plinth, drawer
    b, fr, groove, tone = boards(xu, 7.0, 6, SEED + 9)
    sc = LIME_OLD * (0.9 + 0.14 * tone[..., None]) * (0.86 + 0.24 * grain[..., None])
    sd = np.abs(np.abs(xu) - 26.5)                                   # stile centre at |xu| = 26.5
    chamfer = smooth(2.6, 3.4, sd)
    sc = sc * (1 - 0.25 * chamfer[..., None])
    rubbed = smooth(85, 105, y) * smooth(145, 125, y) * smooth(1.5, 0.5, chamfer)
    sc = sc * (1 + 0.15 * rubbed[..., None])
    col = np.where(stile[..., None], sc, col)
    h = np.where(stile, -0.6 * chamfer, h)
    gloss = np.where(stile, 0.18 + 0.12 * rubbed, gloss)
    for jy in (49.0, 84.0, 165.0, 214.0):                            # paired dowels at every joint
        for dy in (-1.4, 1.4):
            dw = stile & (circle(np.sign(xu) * 26.5, jy + dy, xu, y, 0.5) > 0.5)
            col = np.where(dw[..., None], LIME_LIGHT * 1.05, col)
            h = np.where(dw, 0.25, h)

    fc = LIME_OLD * 0.95 * (0.86 + 0.24 * grain[..., None])
    col = np.where(frieze[..., None], fc, col)
    fg = frieze & (np.abs(y - 218.2) < 0.35)
    col = np.where(fg[..., None], GROOVE, col)
    h = np.where(fg, -0.5, h)
    holes = np.zeros(cov.shape)
    for hx in (-18, -12, -6, 0, 6, 12, 18):
        holes = np.maximum(holes, circle(hx, 220.8, xu, y, 0.7))
    hm = frieze & (holes > 0.5)
    col = np.where(hm[..., None], GROOVE, col)
    h = np.where(frieze, h - 0.8 * holes, h)
    emit_k = np.where(hm, 0.3, emit_k)

    pc = THERMO * (0.86 + 0.24 * grain[..., None])
    col = np.where(plinth[..., None], pc, col)
    slots = np.zeros(cov.shape)
    for sx in (-18, -6, 6, 18):
        slots = np.maximum(slots, rect(xu, y, sx - 3.5, sx + 3.5, 9.6, 11.4, soft=0.2))
    pm = plinth & (slots > 0.5)
    col = np.where(pm[..., None], GROOVE, col)
    h = np.where(plinth, -0.6 * slots, h)
    emit_k = np.where(pm, 0.3, emit_k)

    # drawer: frame + bevelled raised panel; the handle is steel geometry
    dfr = rect(x, y, -20.0, 20.0, 19.5, 44.5, soft=0.3)
    bevel = rect(x, y, -17.0, 17.0, 22.5, 41.5, soft=1.5)
    dc = LIME_OLD * (0.9 + 0.2 * grain[..., None]) * (1 - 0.15 * (dfr - bevel)[..., None])
    col = np.where(drawer[..., None], dc, col)
    h = np.where(drawer, -0.5 * dfr + 0.5 * bevel, h)

    # ---------------------------------------------------------------- top (cornice) and outside: frame + panels
    b, fr, groove, tone = boards(z, 12.0, 7, SEED + 10)
    tc = THERMO * (0.9 + 0.14 * tone[..., None]) * (0.86 + 0.24 * grain[..., None])
    tc = tc * (1 - groove[..., None]) + GROOVE * groove[..., None]
    col = np.where(top[..., None], tc * (1 + 0.15 * smooth(24, 28, z)[..., None]), col)
    h = np.where(top, -0.3 * groove, h)

    def frame_panel(mask, u, umin, umax, bays, vents):
        """Frame (stiles at bay edges, rails at 15, 118, 217) with recessed lining panels."""
        bw = (umax - umin) / bays
        ul = np.mod(u - umin, bw)
        st = (ul < 6.0) | (ul > bw - 6.0) | (u < umin + 6) | (u > umax - 6)
        rl = (np.abs(y - 21.0) < 6) | (np.abs(y - 120.0) < 4) | (y > 211)
        fr_m = (st | rl)
        bb, ff, gg, tt = boards(u, 6.0, 8, SEED + 11)
        panel = LINING * (0.9 + 0.14 * tt[..., None]) * (0.86 + 0.24 * grain[..., None])
        panel = panel * (1 - gg[..., None]) + GROOVE * gg[..., None]
        under = np.zeros(cov.shape)
        for ry in (211.0, 124.0, 27.0):                       # shadow under each rail
            under = np.maximum(under, smooth(ry - 4, ry, y) * (y < ry))
        panel = panel * (1 - 0.3 * under[..., None])
        frame_c = LIME_OLD * (0.86 + 0.24 * grain[..., None])
        c = np.where(fr_m[..., None], frame_c, panel)
        hh = np.where(fr_m, 0.0, -0.6 - 0.3 * gg)
        for vy0, vy1, kind in vents:
            for k in range(-2, 3):
                cx = umin + bw / 2 + k * 5.0
                if kind == "slot":
                    vm = (np.abs(np.mod(u - umin, bw) - bw / 2 - k * 5.0) < 0.7) & (y > vy0) & (y < vy1)
                else:
                    vm = np.zeros(cov.shape, bool)
                    for ry in np.arange(vy0, vy1, 4.0):
                        vm |= circle(bw / 2 + k * 5.0, ry, np.mod(u - umin, bw), y, 0.8) > 0.5
                c = np.where((vm & ~fr_m)[..., None], GROOVE, c)
                hh = np.where(vm & ~fr_m, -1.2, hh)
        # paired dowels at the frame joints
        for jy in (21.0, 120.0, 214.0):
            for e in (3.0, bw - 3.0):
                for dy in (-1.4, 1.4):
                    dw = circle(e, jy + dy, np.mod(u - umin, bw), y, 0.5) > 0.5
                    c = np.where(dw[..., None], LIME_LIGHT, c)
        col[mask] = c[mask]
        h[mask] = hh[mask]

    # (the outside of the side walls shares its UVs with the niches' outer walls: they get the
    #  niche lining with shelf battens, which outside reads as boards with rails)
    frame_panel(back_out, x, -90.0, 90.0, 3, ((198, 207, "hole"), (31, 40, "slot")))

    # ---------------------------------------------------------------- iron, wear
    iron_c = STEEL * (0.8 + 0.4 * blur(rng.random(cov.shape), 2)[..., None])
    col = np.where(iron[..., None], iron_c, col)
    spec = np.where(iron, 0.35, spec)
    gloss = np.where(iron, 0.45, gloss)
    water = smooth(34, 18, y + 6 * (fbm(x * 0.3, y * 0.1, z * 0.3, 3, SEED + 12) - 0.5)) * ~iron * cov
    col = col * (1 - 0.3 * water[..., None])
    gloss = gloss + 0.15 * water
    col = col * np.where((front | top | back_out)[..., None], 0.9 + 0.1 * ao[..., None], 0.72 + 0.28 * ao[..., None])
    col[~cov] = LINING * 0.8

    # ---------------------------------------------------------------- light
    # LED strips: shelf front edges and the slit under the frieze (front of the ceiling)
    strip = (shelf_edge | (shelf & (z > 17)) | (ceiling & (z > 15))) & ~small
    emit_k = np.where(strip, 0.9, emit_k)
    col = np.where(strip[..., None], np.array([0.96, 0.86, 0.68]), col)
    # light on the wood below every LED row, on the back wall and the niche sides
    below = np.zeros(cov.shape)
    for L in LIGHTS:
        below = np.maximum(below, (0.35 + 0.65 * smooth(L - 55, L - 1, y)) * (y < L - 1) * (y > L - 82))
    # the outer walls' inner faces share their UVs with the outside of the locker: no glow there
    divider = niche_side & (np.abs(x) < 85)
    wash = np.maximum(wash, 0.62 * below * back + 0.5 * below * divider)
    wash = np.maximum(wash, 0.45 * shelf * smooth(-25, 15, z) + 0.3 * floor + 0.25 * ceiling)
    emit = emit_k[..., None] * LED + (wash[..., None] * col * WARM)
    spec = np.where(emit_k > 0.5, 0.3, spec)
    gloss = np.where(emit_k > 0.5, 0.55, gloss)

    # ---------------------------------------------------------------- normal
    group = (oid.astype(np.int16) * 16 + 1 * back + 2 * shelf + 4 * stile + 8 * (sides_out | back_out)).astype(np.int16)
    nb = v1.height_to_normal(h, pos, dens, group, k=1.0)
    n0[..., 2] = np.sqrt(np.clip(1 - n0[..., 0] ** 2 - n0[..., 1] ** 2, 0, 1))
    nb = np.where(iron[..., None], n0, nb)

    out = dict(m, col=col, nb=nb, spec=spec, gloss=gloss, alpha=alpha)
    v1.save(out, "v4")
    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    em = Image.fromarray(q(emit)).resize((1024, 1024), Image.BOX)
    Image.fromarray(np.dstack([np.asarray(em), np.full((1024, 1024), 255, np.uint8)]), "RGBA").save(OUT / "Locker_v4_emission.png")
    print("done; back", int(back.sum()), "shelf", int(shelf.sum()), "stile", int(stile.sum()), "frieze", int(frieze.sum()),
          "sides", int(sides_out.sum()), "back_out", int(back_out.sum()), "top", int(top.sum()), "strip", int(strip.sum()),
          "drawer", int(drawer.sum()), "lamp", int(lamp.sum()))


if __name__ == "__main__":
    main()
