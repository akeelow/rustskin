"""Sauna Stove v1: procedural textures generated in the model's 3D space.

Every texel is mapped back to its 3D point on the furnace, so slats, stones and
masonry are continuous across UV seams. Needs numpy + Pillow:
    python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
    .venv/Scripts/python skins/sauna/electric-furnace/texture_v1.py

Writes export/ElectricFurnace_v1_{diffuse,normal,metalgloss,occlusion,emission}.png
and uv/v1_views.png (diffuse preview) + uv/v1_views_emission.png.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image as PILImage

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
from uv_zones import classify, load_obj, normal, read_png, render_views  # noqa: E402

SIZE = 2048
SEED = 7
ORIG = HERE / "originals"
OUT = HERE / "export"

# material ids
PALLET, PLINTH, IRON, PANEL, KNOB, SIDE, BACK, RIM, STONES, EMBERS = range(10)
EMBER_RGB = np.array([0.90, 0.26, 0.04])  # deep red-orange, close to the original emission
ZONE_IDS = {"front": 0, "back": 1, "right": 2, "left": 3, "top": 4, "hidden": 5}


def hexc(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255.0


# ---------------------------------------------------------------- noise helpers
def hash3(a, b, c, seed=0):
    a = a.astype(np.int64).astype(np.uint32)
    b = b.astype(np.int64).astype(np.uint32)
    c = c.astype(np.int64).astype(np.uint32)
    h = a * np.uint32(73856093) ^ b * np.uint32(19349663) ^ c * np.uint32(83492791) ^ np.uint32(seed * 2654435761 % 2**32)
    h ^= h >> np.uint32(13)
    h *= np.uint32(1274126177)
    h ^= h >> np.uint32(16)
    return h.astype(np.float64) / 2**32


def value_noise(x, y, z, seed=0):
    xi, yi, zi = np.floor(x), np.floor(y), np.floor(z)
    xf, yf, zf = x - xi, y - yi, z - zi
    u, v, w = (t * t * (3 - 2 * t) for t in (xf, yf, zf))
    out = 0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                wgt = (u if dx else 1 - u) * (v if dy else 1 - v) * (w if dz else 1 - w)
                out = out + wgt * hash3(xi + dx, yi + dy, zi + dz, seed)
    return out


def fbm(x, y, z, octaves=4, seed=0):
    total, amp, norm = 0, 1.0, 0
    for o in range(octaves):
        total = total + amp * value_noise(x * 2**o, y * 2**o, z * 2**o, seed + o * 17)
        norm += amp
        amp *= 0.5
    return total / norm


def voronoi(u, v, seed=0):
    """F1, F2 distances and nearest-cell id for 2D points (cell size 1)."""
    ui, vi = np.floor(u), np.floor(v)
    f1 = np.full(u.shape, 9.0)
    f2 = np.full(u.shape, 9.0)
    cid = np.zeros(u.shape)
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            cu, cv = ui + di, vi + dj
            px = cu + 0.15 + 0.7 * hash3(cu, cv, np.zeros_like(cu), seed)
            py = cv + 0.15 + 0.7 * hash3(cu, cv, np.ones_like(cu), seed)
            d = np.sqrt((u - px) ** 2 + (v - py) ** 2)
            closer = d < f1
            f2 = np.where(closer, f1, np.minimum(f2, d))
            cid = np.where(closer, hash3(cu, cv, np.full_like(cu, 2), seed), cid)
            f1 = np.where(closer, d, f1)
    return f1, f2, cid


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- geometry -> texel maps
def position_maps(V, T, F, N, zone):
    pos = np.zeros((SIZE, SIZE, 3), np.float32)
    nrm = np.zeros((SIZE, SIZE, 3), np.float32)
    zid = np.full((SIZE, SIZE), -1, np.int8)
    dens = np.zeros((SIZE, SIZE), np.float32)  # texels per metre
    Va, Ta = np.array(V, np.float64), np.array(T, np.float64)
    def uv_area(f):
        a, b, c = Ta[list(F[f][1])]
        return abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1]))
    order = sorted(range(len(F)), key=lambda f: -uv_area(f))
    for f in order:
        vi, ti = F[f]
        P = Va[list(vi)]
        uv = Ta[list(ti)] * SIZE
        uv[:, 1] = SIZE - uv[:, 1]
        x0, y0 = np.floor(uv.min(0)).astype(int) - 1
        x1, y1 = np.ceil(uv.max(0)).astype(int) + 1
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, SIZE - 1), min(y1, SIZE - 1)
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
        world_area = np.linalg.norm(np.cross(P[1] - P[0], P[2] - P[0])) / 2
        d = np.sqrt(abs(area) / 2 / max(world_area, 1e-12))
        ys, xs = np.nonzero(m)
        ys, xs = ys + y0, xs + x0
        pos[ys, xs] = p3[m]
        nrm[ys, xs] = N[f]
        zid[ys, xs] = ZONE_IDS[zone[f].split("-")[0]]
        dens[ys, xs] = d
    # gutter: grow islands a few texels so mips/bilinear don't pull in black
    filled = zid >= 0
    for _ in range(6):
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            src = np.roll(np.roll(filled, dy, 0), dx, 1)
            take = ~filled & src
            if not take.any():
                continue
            for arr in (pos, nrm, zid, dens):
                arr[take] = np.roll(np.roll(arr, dy, 0), dx, 1)[take]
            filled = filled | take
    return pos, nrm, zid, dens, filled


def material_map(pos, nrm, zid, glow):
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    # oven interior (behind the door, where the coils are); the bars sit in front of it at z >= 0.32
    inside = (np.abs(x) < 0.325) & (z > -0.30) & (z < 0.28) & (y > 0.33) & (y < 1.0)
    # thin parts (bars, edges) miss the visibility raster and come out "hidden":
    # outside the oven, give them the side their normal faces instead
    hidden_out = (zid == 5) & ~inside
    nx, ny, nz = nrm[..., 0], nrm[..., 1], nrm[..., 2]
    by_normal = np.where(ny > 0.7, 4, np.where(np.abs(nz) >= np.abs(nx), np.where(nz > 0, 0, 1), np.where(nx > 0, 2, 3)))
    zid = np.where(hidden_out, by_normal, zid).astype(np.int8)
    mat = np.full(zid.shape, SIDE, np.int8)
    mat[zid == 1] = BACK
    front = zid == 0
    mat[front & (y >= 0.93)] = PANEL
    mat[front & (y >= 0.95) & (y < 1.08) & (z > 0.334)] = KNOB
    mat[front & (y < 0.93)] = IRON
    mat[(y >= 0.27) & (y < 0.33) & (zid != 4)] = IRON
    mat[(y < 0.27) & (zid != 4)] = PLINTH
    # right-side vent: the louver fins are the tilted faces (nx < 0.95) of the vent -> cast-iron grille
    mat[(zid == 2) & (nrm[..., 0] < 0.95) & (np.abs(z) < 0.31) & (y > 0.42) & (y < 0.97)] = IRON
    mat[(glow | (zid == 5)) & inside & (zid != 4)] = EMBERS
    mat[zid == 4] = RIM
    mat[(zid == 4) & (y >= 1.155)] = STONES
    mat[y < 0.045] = PALLET
    return mat, zid


# ---------------------------------------------------------------- materials
def build(pos, nrm, mat, zid, glow0):
    x, y, z = (pos[..., i].astype(np.float64) for i in range(3))
    vertical = np.abs(nrm[..., 1]) < 0.7
    along_x = np.abs(nrm[..., 2]) >= np.abs(nrm[..., 0])
    h = np.where(along_x, x, z)  # horizontal coordinate along a vertical face
    col = np.zeros(pos.shape, np.float64)
    height = np.zeros(mat.shape)            # metres
    metal = np.zeros(mat.shape)
    gloss = np.zeros(mat.shape)
    emit = np.zeros(pos.shape, np.float64)
    cavity = np.zeros(mat.shape)            # 0..1 extra occlusion
    orig_w = np.zeros(mat.shape)            # how much of the original normal to keep

    def put(m, c, hgt=None, me=None, gl=None, cav=None, ow=None):
        col[m] = c[m] if np.ndim(c) == 3 else c
        if hgt is not None:
            height[m] = hgt[m]
        if me is not None:
            metal[m] = me[m] if np.ndim(me) else me
        if gl is not None:
            gloss[m] = gl[m] if np.ndim(gl) else gl
        if cav is not None:
            cavity[m] = cav[m]
        if ow is not None:
            orig_w[m] = ow

    # --- wooden slats (sides, back, control panel)
    W = 0.075
    hb = (h + 10) / W
    board = np.floor(hb)
    fr = hb - board
    gap = 1 - smooth(0.0, 0.06, fr) * smooth(1.0, 0.94, fr)
    tone = hash3(board, np.where(along_x, 1, 2) + zid, np.zeros_like(board), SEED)
    grain = fbm(h * 260, y * 9, board * 3.1, 4, SEED + 1)
    knots = smooth(0.82, 0.9, fbm(h * 40, y * 18, board, 2, SEED + 2))
    stain = smooth(0.55, 0.75, fbm(h * 6, y * 3, 0 * h, 4, SEED + 3)) * smooth(0.55, 0.35, y)
    drips = smooth(0.62, 0.72, fbm(h * 90, y * 2.5, board, 3, SEED + 4)) * smooth(0.5, 1.1, y)
    steam = smooth(0.95, 1.14, y)
    rows = (0.40, 1.04)
    nail = np.zeros(mat.shape)
    for r in rows:
        d = np.sqrt(((fr - 0.5) * W) ** 2 + (y - r) ** 2)
        nail = np.maximum(nail, 1 - smooth(0.0035, 0.0055, d))
        rust_halo = (1 - smooth(0.005, 0.012, d)) * 0.5
        stain = np.maximum(stain, rust_halo)

    # bevels and recess frames (tilted faces): plain trim, no gaps or nails
    trim = vertical & (np.maximum(np.abs(nrm[..., 0]), np.abs(nrm[..., 2])) < 0.95)
    gap = gap * ~trim
    nail = nail * ~trim
    # worn slat edges and box corners: lighter, rounded
    e = np.minimum(fr, 1 - fr)
    chips = fbm(h * 120, y * 60, board, 3, SEED + 5)
    wear = smooth(0.14, 0.065, e) * (1 - gap) * smooth(0.35, 0.65, chips)
    corner = smooth(0.025, 0.0, 0.389 - np.abs(h)) * smooth(0.3, 0.6, chips)
    wear = np.maximum(wear, corner)
    # scorch around the firebox door (heat rises: stronger above it)
    dx = np.maximum(np.abs(x) - 0.30, 0)
    dy = np.maximum(np.maximum(0.33 - y, y - 0.93), 0)
    dz = np.maximum(0.33 - z, 0)
    dd = np.sqrt(dx ** 2 + dy ** 2 + dz ** 2)
    scorch_n = fbm(x * 30, y * 30, z * 30, 4, SEED + 6)
    scorch = np.clip((1 - smooth(0.0, 0.16, dd + 0.04 * (scorch_n - 0.5))) * (0.5 + 0.8 * smooth(0.55, 0.95, y)), 0, 1)
    scorch = scorch * (z > 0.20)  # only the front half of the box

    def wood(base, darker):
        c = base[None, None, :] * (0.88 + 0.22 * tone[..., None])
        c = c * (0.86 + 0.24 * grain[..., None])
        c = c * (1 - 0.35 * knots[..., None])
        c = c * (1 - darker * steam[..., None]) * (1 - 0.28 * stain[..., None]) * (1 - 0.2 * drips[..., None])
        c = c * (1 - gap[..., None]) + hexc("#2A2018") * gap[..., None]
        c = c * (1 + 0.22 * wear[..., None])
        char = hexc("#1C120B") * (0.7 + 0.6 * scorch_n[..., None])
        c = c * (1 - 0.88 * scorch[..., None]) + char * 0.88 * scorch[..., None]
        c = c * (1 - nail[..., None]) + hexc("#3A3430") * nail[..., None]
        return c

    wood_h = -0.003 * gap + 0.0003 * grain + 0.0008 * nail - 0.0004 * knots - 0.0007 * wear         + 0.0003 * scorch * fbm(x * 400, y * 400, z * 400, 2, SEED + 7)
    wood_gloss = (30 + 45 * stain + 30 * drips) * (1 - 0.6 * scorch)
    wood_metal = 120 * nail
    for m, base, dk in ((SIDE, hexc("#C2A77E"), 0.25), (BACK, hexc("#7A5A3C"), 0.15), (PANEL, hexc("#C2A77E"), 0.3)):
        sel = mat == m
        put(sel, wood(base, dk), wood_h, wood_metal, wood_gloss, gap * 0.8, 0.0 if m != PANEL else 0.4)
    knob = mat == KNOB
    put(knob, hexc("#D8C3A0")[None, None, :] * (0.85 + 0.25 * grain[..., None]), 0.0002 * grain, 0, 55, None, 1.0)

    # --- stones on the burners (top view, x/z plane)
    cs = 0.038
    f1, f2, cid = voronoi(x / cs, z / cs, SEED + 10)
    edge = f2 - f1
    crack = 1 - smooth(0.03, 0.1, edge)
    speck = fbm(x * 900, z * 900, y * 900, 2, SEED + 11)
    t = cid[..., None]
    stone_c = hexc("#2B2C2E") * (1 - t) + hexc("#4A4846") * t  # basalt
    stone_c = stone_c * (0.88 + 0.22 * speck[..., None])
    mineral = smooth(0.76, 0.82, fbm(x * 70, z * 70, cid * 9, 3, SEED + 12))
    stone_c = stone_c * (1 - 0.35 * mineral[..., None]) + hexc("#BDB7AC") * 0.35 * mineral[..., None]
    stone_c = stone_c * (1 - crack[..., None]) + hexc("#1E1A18") * crack[..., None]
    dome = np.sqrt(np.clip(1 - (f1 / 0.75) ** 2, 0, 1))
    sel = mat == STONES
    put(sel, stone_c, 0.009 * dome - 0.004 * crack, 0, 50 + 30 * mineral, crack, 0.0)
    flicker = 0.55 + 0.45 * fbm(x * 30, z * 30, y, 3, SEED + 13)
    # thin coil strips get a low even warmth (cracks would blur into solid rings at 512 px);
    # the rest of the burner glows only in the cracks
    glow_top = np.where(glow0, 0.05 * flicker, 0.6 * crack * flicker)
    emit[sel] = (glow_top[..., None] * EMBER_RGB)[sel]

    # --- embers: stones inside the oven, seen through the bars (triplanar on dominant axis)
    an = np.abs(nrm)
    pu = np.where(an[..., 1] >= np.maximum(an[..., 0], an[..., 2]), x, np.where(along_x, x, z))
    pv = np.where(an[..., 1] >= np.maximum(an[..., 0], an[..., 2]), z, y)
    g1, g2, gid = voronoi(pu / 0.028, pv / 0.028, SEED + 20)
    gcrack = 1 - smooth(0.025, 0.08, g2 - g1)
    gt = gid[..., None]
    ember_c = hexc("#2F2F31") * (1 - gt) + hexc("#5A5653") * gt
    ember_c = ember_c * (1 - gcrack[..., None]) + hexc("#160F0C") * gcrack[..., None]
    sel = mat == EMBERS
    put(sel, ember_c, 0.007 * np.sqrt(np.clip(1 - (g1 / 0.75) ** 2, 0, 1)), 0, 45, gcrack, 0.3)
    low = np.clip(1.25 - (y - 0.33) / 0.55, 0.35, 1.0)
    hot_stone = smooth(0.7, 0.9, gid) * 0.18
    heat = (1.3 * gcrack + hot_stone) * low * (0.7 + 0.5 * fbm(x * 25, y * 25, z * 25, 3, SEED + 21))
    emit[sel] = (np.clip(heat * 0.55, 0, 1)[..., None] * EMBER_RGB)[sel]

    # --- forged iron (door, bars, kick band)
    mott = fbm(x * 40, y * 40, z * 40, 4, SEED + 30)
    rust = smooth(0.68, 0.78, fbm(x * 22, y * 22, z * 22, 4, SEED + 31)) * 0.85
    iron_c = hexc("#2E2A27") * (0.8 + 0.4 * mott[..., None])
    iron_c = iron_c * (1 - rust[..., None]) + hexc("#5A3A26") * (0.8 + 0.4 * mott[..., None]) * rust[..., None]
    sel = mat == IRON
    put(sel, iron_c, 0.0004 * fbm(x * 120, y * 120, z * 120, 3, SEED + 32), 150 - 110 * rust, 75 - 45 * rust, None, 1.0)

    # --- sooty rim of the top plate
    soot = fbm(x * 18, z * 18, y, 4, SEED + 40)
    rim_c = hexc("#45403B") * (0.75 + 0.45 * soot[..., None])
    # burner centres from the stone texels, one per quadrant
    st = mat == STONES
    bdist = np.full(mat.shape, 9.0)
    for sx in (-1, 1):
        for sz in (-1, 1):
            q = st & (np.sign(x) == sx) & (np.sign(z) == sz)
            if q.sum() < 50:
                continue
            cx, cz = x[q].mean(), z[q].mean()
            r = np.percentile(np.hypot(x[q] - cx, z[q] - cz), 98)
            bdist = np.minimum(bdist, np.hypot(x - cx, z - cz) - r)
    bdist = bdist + 0.012 * (fbm(x * 25, z * 25, y, 3, SEED + 42) - 0.5)
    # temper (heat-tint) bands: straw -> bronze -> purple -> blue -> plate
    stops = [(0.0, "#B8975A"), (0.012, "#9C6236"), (0.026, "#64386C"), (0.04, "#3B4F84"), (0.065, None)]
    temper_c = np.zeros(pos.shape)
    temper_a = np.zeros(mat.shape)
    for (d0, c0), (d1, c1) in zip(stops, stops[1:]):
        m = (bdist >= d0) & (bdist < d1)
        t = ((bdist - d0) / (d1 - d0))[..., None]
        a0 = 1.0
        a1 = 0.0 if c1 is None else 1.0
        cc1 = hexc(c0) if c1 is None else hexc(c1)
        temper_c[m] = (hexc(c0) * (1 - t) + cc1 * t)[m]
        temper_a[m] = (a0 * (1 - t[..., 0]) + a1 * t[..., 0])[m]
    temper_a *= 0.4 * (bdist >= 0)
    rim_c = rim_c * (1 - temper_a[..., None]) + temper_c * temper_a[..., None]
    # evaporated water: pale tide lines and duller patches
    tide = np.zeros(mat.shape)
    patch = np.zeros(mat.shape)
    for k, (sc, lvl) in enumerate(((9, 0.56), (14, 0.6))):
        b = fbm(x * sc, z * sc, y + k, 4, SEED + 43 + k)
        tide = np.maximum(tide, 1 - smooth(0.0, 0.01, np.abs(b - lvl)))
        patch = np.maximum(patch, smooth(lvl, lvl + 0.02, b))
    rim_c = rim_c * (1 + 0.1 * patch[..., None])
    rim_c = rim_c * (1 - 0.35 * tide[..., None]) + hexc("#A9A398") * 0.35 * tide[..., None]
    sel = mat == RIM
    put(sel, rim_c, 0.0003 * soot + 0.0002 * tide, 90 + 40 * temper_a - 50 * tide, 55 + 20 * temper_a - 25 * patch, None, 1.0)

    # --- fieldstone plinth (anisotropic voronoi on the face)
    p1, p2, pid = voronoi(h / 0.085, y / 0.055, SEED + 50)
    mortar = 1 - smooth(0.06, 0.16, p2 - p1)
    pt = pid[..., None]
    plinth_c = hexc("#5E574F") * (1 - pt) + hexc("#837A6E") * pt
    plinth_c = plinth_c * (0.85 + 0.3 * fbm(x * 500, y * 500, z * 500, 2, SEED + 51)[..., None])
    plinth_c = plinth_c * (1 - mortar[..., None]) + hexc("#8C857A") * mortar[..., None]
    wet = smooth(0.11, 0.05, y)
    plinth_c = plinth_c * (1 - 0.3 * wet[..., None])
    sel = mat == PLINTH
    put(sel, plinth_c, 0.006 * np.sqrt(np.clip(1 - (p1 / 0.8) ** 2, 0, 1)) - 0.004 * mortar, 0, 40 + 60 * wet, mortar * 0.7, 0.0)

    # --- wet pallet boards
    pw = np.where(vertical, h, z) / 0.09
    pb = np.floor(pw)
    pf = pw - pb
    pgap = 1 - smooth(0.0, 0.05, pf) * smooth(1.0, 0.95, pf)
    pgrain = fbm(np.where(vertical, y, x) * 30, pw * 40, pb, 4, SEED + 60)
    pal_c = hexc("#6B4F36")[None, None, :] * (0.8 + 0.3 * hash3(pb, pb, pb, SEED + 61)[..., None]) * (0.85 + 0.25 * pgrain[..., None])
    pal_c = pal_c * (1 - pgap[..., None]) + hexc("#24190F") * pgap[..., None]
    sel = mat == PALLET
    put(sel, pal_c, -0.002 * pgap + 0.0003 * pgrain, 0, 115, pgap * 0.6, 0.5)

    return col, height, metal, gloss, emit, cavity, orig_w


def height_to_normal(height, pos, dens, mat, strength=1.0):
    """Tangent-space normal (OpenGL, Y+) from a texture-space height map, seam-aware."""
    def diff(axis):
        hp, hm = np.roll(height, -1, axis), np.roll(height, 1, axis)
        pp, pm = np.roll(pos, -1, axis), np.roll(pos, 1, axis)
        mp, mm = np.roll(mat, -1, axis), np.roll(mat, 1, axis)
        texel = 1.0 / np.maximum(dens, 1.0)
        ok_p = (np.linalg.norm(pp - pos, axis=-1) < 3 * texel) & (mp == mat)
        ok_m = (np.linalg.norm(pm - pos, axis=-1) < 3 * texel) & (mm == mat)
        g = np.where(ok_p & ok_m, (hp - hm) / 2, np.where(ok_p, hp - height, np.where(ok_m, height - hm, 0)))
        return g * dens * strength  # metres of height per metre of surface
    du = diff(1)          # +x in image = +U
    dv = -diff(0)         # +y in image = -V
    n = np.stack([-du, -dv, np.ones_like(du)], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def main():
    V, T, F = load_obj(ORIG / "electric.furnace.obj")
    N = [normal(*(V[i] for i in vi)) for vi, _ in F]
    print("classifying zones ...")
    zone = classify(V, F, N)
    print("rasterising position maps ...")
    pos, nrm, zid, dens, filled = position_maps(V, T, F, N, zone)
    em0 = np.asarray(PILImage.open(ORIG / "ElectricFurnace_em.png").convert("RGB").resize((SIZE, SIZE), PILImage.NEAREST))
    glow0 = em0[..., 0] > 60
    mat, zid = material_map(pos, nrm, zid, glow0)
    print("building materials ...")
    col, height, metal, gloss, emit, cavity, orig_w = build(pos, nrm, mat, zid, glow0)

    n_new = height_to_normal(height, pos, dens, mat, strength=3.0)
    n0 = np.asarray(PILImage.open(ORIG / "ElectricFurnace_nrm.png").convert("RGB"), np.float64) / 255 * 2 - 1
    n0[..., 2] = np.sqrt(np.clip(1 - n0[..., 0] ** 2 - n0[..., 1] ** 2, 0, 1))
    w = orig_w[..., None]
    n0 = n0 * w + np.array([0.0, 0.0, 1.0]) * (1 - w)
    n0 /= np.maximum(np.linalg.norm(n0, axis=-1, keepdims=True), 1e-6)
    blend = np.stack([n_new[..., 0] + n0[..., 0], n_new[..., 1] + n0[..., 1], n_new[..., 2] * n0[..., 2]], -1)  # whiteout
    blend /= np.linalg.norm(blend, axis=-1, keepdims=True)

    OUT.mkdir(exist_ok=True)
    srgb = np.clip(col, 0, 1)
    rgba = lambda rgb, a=None: np.dstack([rgb, np.full(rgb.shape[:2], 255, np.uint8) if a is None else a]).astype(np.uint8)
    PILImage.fromarray(rgba((srgb * 255).round())).save(OUT / "ElectricFurnace_v1_diffuse.png")
    nr = np.dstack([(blend[..., 0] * 0.5 + 0.5) * 255, (blend[..., 1] * 0.5 + 0.5) * 255, np.full(mat.shape, 255)]).round()
    PILImage.fromarray(rgba(nr)).save(OUT / "ElectricFurnace_v1_normal.png")
    mrgb = np.repeat(np.clip(metal, 0, 255)[..., None], 3, -1).round()
    PILImage.fromarray(rgba(mrgb, np.clip(gloss, 0, 255).round())).save(OUT / "ElectricFurnace_v1_metalgloss.png")
    ao0 = np.asarray(PILImage.open(ORIG / "ElectricFurnace_AO.png").convert("L").resize((SIZE, SIZE), PILImage.BILINEAR), np.float64) / 255
    ao = np.clip(ao0 * (1 - 0.5 * cavity), 0, 1)
    ao_small = PILImage.fromarray((ao * 255).round().astype(np.uint8)).resize((512, 512), PILImage.BOX)
    PILImage.fromarray(rgba(np.repeat(np.asarray(ao_small)[..., None], 3, -1))).save(OUT / "ElectricFurnace_v1_occlusion.png")
    em_small = PILImage.fromarray((np.clip(emit, 0, 1) * 255).round().astype(np.uint8)).resize((512, 512), PILImage.BOX)
    em_arr = np.clip(np.asarray(em_small, np.float64) * 1.2, 0, 255)  # box filter dims thin cracks; compensate a little
    PILImage.fromarray(rgba(em_arr.round())).save(OUT / "ElectricFurnace_v1_emission.png")

    print("rendering previews ...")
    render_views(V, T, F, N, HERE / "uv" / "v1_views.png", tex=read_png(OUT / "ElectricFurnace_v1_diffuse.png"))
    render_views(V, T, F, N, HERE / "uv" / "v1_views_emission.png", tex=read_png(OUT / "ElectricFurnace_v1_emission.png"))
    share = {k: f"{(mat == i).mean():.1%}" for i, k in enumerate(
        ["pallet", "plinth", "iron", "panel", "knob", "side", "back", "rim", "stones", "embers"])}
    print("done; texture share:", share)


if __name__ == "__main__":
    main()
