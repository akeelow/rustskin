"""Concept previews for the Sauna box (Wood Storage Box): quick colour paints on the real model, not v0.

Model: metres, Y up: x = width (+x right, seen from the front), y = height, z = depth (+z front:
the short end with the handle slot). Body x -0.36..0.34, z -0.46..0.48, walls of 4 horizontal planks
(y 0-0.13-0.27-0.40-0.53, gaps 1-3 mm), lid of 7 planks along z (y ~0.55, gaps 0-5 mm). Both ends
have a handle slot cut up into the bottom of the top plank (x -0.16..0.16, up to y 0.45).
UV tiles: the inner faces and the lid underside reuse the outer planks' texels (uv/islands.md),
so every outer face is painted last and wins.

    .venv/Scripts/python skins/sauna/wood-storage-box/concepts.py
Writes renders/concepts/<A|B|C|C_slots|C_corner|C_grate|D|D_open|D_slot|D_three>_{diffuse,specgloss,normal,occlusion[,emission]}.png
for viewer.py and renders/concepts/row6.obj (six boxes side by side, for the row test).
"""
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
from uv_zones import load_obj, normal  # noqa: E402

ORIG = HERE / "originals"
OUT = HERE / "renders" / "concepts"
SIZE = 1024
SEED = 11
CENTRE = np.array([-0.008, 0.27, 0.008])
PLANK_Y = (0.0, 0.135, 0.2675, 0.4005, 0.535)
SLOT = (-0.163, 0.161, 0.453)        # handle slot: x from, x to, top y


def hexc(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float64) / 255.0


# set palette (../README.md) and the finished bench / chair
ASPEN = hexc("#A39176")
ASPEN_LIGHT = hexc("#C2A77E")
ASPEN_GREY = hexc("#958B7E")
STEAMED = hexc("#7A5A3C")
OLD = hexc("#45332A")
LINEN = hexc("#CFC6B4")
BRICK = hexc("#8E3A30")
IRON = hexc("#2E2A27")
RUST = hexc("#8C4A26")
MINERAL = hexc("#D9D4C8")
FELT = hexc("#B3A48A")
LEAF_OAK = hexc("#5E4A2C")
LEAF_BIRCH = hexc("#4F5C30")
TWINE = hexc("#9C8762")
SOOT = hexc("#1E1A18")
EMBER_CORE = hexc("#FF6A1F")
EMBER_EDGE = hexc("#8E1E08")


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


def position_map(V, T, F):
    """3D point and face normal per texel; faces pointing out of the box are drawn last (they win
    the shared texels), with a 3-texel gutter."""
    Va, Ta = np.array(V), np.array(T)
    order = []
    for f, (vi, ti) in enumerate(F):
        P = Va[list(vi)]
        n = np.array(normal(*P))
        order.append((float(n @ (P.mean(0) - CENTRE)), f))
    pos = np.zeros((SIZE, SIZE, 3))
    nrm = np.zeros((SIZE, SIZE, 3))
    hit = np.zeros((SIZE, SIZE), bool)
    for _, f in sorted(order):
        vi, ti = F[f]
        P = Va[list(vi)]
        uv = Ta[list(ti)][:, :2].copy()
        uv -= np.floor(uv.min(0))                   # tiles wrap: shift back into 0..1
        uv *= SIZE
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
        hit[ys + y0, xs + x0] = True
    for _ in range(3):
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            take = ~hit & np.roll(np.roll(hit, dy, 0), dx, 1)
            pos[take] = np.roll(np.roll(pos, dy, 0), dx, 1)[take]
            nrm[take] = np.roll(np.roll(nrm, dy, 0), dx, 1)[take]
            hit |= take
    return pos, nrm


def is_lid(P):
    """A lid face (corners P, 3 x 3): reaches above the wall tops (y 0.533), or lies wholly above y 0.515
    and is not a wall's top edge (those face up) - the lid's sides and underside."""
    return P[:, 1].max() > 0.538 or (P[:, 1].min() > 0.515 and normal(*P)[1] < 0.9)


class Box:
    """Texel geometry and the shared wood base all concepts start from."""

    def __init__(self):
        V, T, F = load_obj(ORIG / "box.wooden.obj")
        self.V, self.T, self.F = V, T, F
        self.pos, self.nrm = position_map(V, T, F)
        x, y, z = self.pos[..., 0], self.pos[..., 1], self.pos[..., 2]
        self.x, self.y, self.z = x, y, z
        n = self.nrm
        self.lid = y > 0.538
        self.lid_top = self.lid & (n[..., 1] > 0.7)
        self.front = ~self.lid & (z > 0.43) & (n[..., 2] > 0.7)
        self.back = ~self.lid & (z < -0.43) & (n[..., 2] < -0.7)
        self.right = ~self.lid & (x > 0.32) & (n[..., 0] > 0.7)
        self.left = ~self.lid & (x < -0.33) & (n[..., 0] < -0.7)
        self.walls = self.front | self.back | self.right | self.left
        self.plank = np.digitize(y, PLANK_Y[1:-1])                   # 0 bottom .. 3 top
        self.lid_plank = np.digitize(x, (-0.267, -0.164, -0.0615, 0.040, 0.145, 0.252))
        # running coordinate along the wall (m), continuous round the corners: front, right, back, left
        self.run = np.select([self.front, self.right, self.back, self.left],
                             [x, 0.34 + (0.48 - z), 0.34 + 0.95 + (0.34 - x), 0.34 + 0.95 + 0.68 + (z + 0.47)], 0)
        rng = np.random.default_rng(SEED)
        bc = np.asarray(Image.open(ORIG / "Wooden_Box_bc.png").convert("RGB"), np.float64) / 255.0
        lum = bc @ np.array([0.299, 0.587, 0.114])
        self.detail = np.clip(lum / np.maximum(blur(lum, 10), 1e-3), 0.65, 1.3)    # vanilla grain & cracks
        self.blotch = blur(rng.random((SIZE, SIZE)), 14)
        self.blotch = (self.blotch - self.blotch.mean()) / max(self.blotch.std(), 1e-6)
        self.noise = blur(rng.random((SIZE, SIZE)), 2.5)

    def inner_floor(self):
        """(mask, x, z) of the inner floor in its own coordinates: it shares texels with the outer bottom,
        mirrored front to back, so the position map (outer faces win) can't be used to place things on it."""
        Va = np.array(self.V)
        fl = [f for f in self.F if Va[list(f[0])][:, 1].max() < 0.035 and normal(*Va[list(f[0])])[1] > 0.7]
        pos, _ = position_map(self.V, self.T, fl)
        m = self.face_mask(lambda P: P[:, 1].max() < 0.035 and normal(*P)[1] > 0.7, grow=0)
        return m, pos[..., 0], pos[..., 2]

    def face_mask(self, pred, grow=1):
        """Texels of every face whose corners P (3 x 3) pass pred(P) - all of them, shared or not (an alpha
        cut must take the lid's thin edge faces too), grown by a texel."""
        Va, Ta = np.array(self.V), np.array(self.T)
        m = Image.new("L", (SIZE, SIZE), 0)
        from PIL import ImageDraw
        d = ImageDraw.Draw(m)
        for vi, ti in self.F:
            if not pred(Va[list(vi)]):
                continue
            uv = Ta[list(ti)][:, :2].copy()
            uv -= np.floor(uv.min(0))
            d.polygon([(u * SIZE, (1 - v) * SIZE) for u, v in uv], fill=255)
        if grow:
            m = m.filter(ImageFilter.MaxFilter(2 * grow + 1))
        return np.asarray(m) > 127

    def wood(self, base, grey_share=0.3, spread=0.12, grain=0.7):
        face = np.select([self.front, self.right, self.back, self.left], [0, 1, 2, 3], 4)
        k = np.where(self.lid, 30 + self.lid_plank, self.plank + 4 * face)
        tone = hash1(k, SEED)
        grey = hash1(k, SEED + 1) < grey_share
        col = np.where(grey[..., None], ASPEN_GREY * base / ASPEN, base)
        col = col * (1 - spread / 2 + spread * tone[..., None])
        col = col * (1 + grain * (self.detail[..., None] - 1)) * (1 + 0.03 * self.blotch[..., None])
        # plank edges a touch lighter (rubbed), the vanilla AO darkens the gaps in game
        return col


def mix(col, c, a):
    a = np.clip(a, 0, 1)[..., None]
    return col * (1 - a) + c * a


def band(b, y0, y1, rivet_step=0.12):
    """A flat iron band round the walls between y0 and y1, rivets, rust running down under it."""
    y, run = b.y, b.run
    inside = b.walls & (y > y0) & (y < y1)
    rust_mask = smooth(0.3, 0.75, b.blotch * 0.25 + 0.5 + 0.3 * (b.noise - 0.5))
    rivet = inside & (np.hypot((run % rivet_step) - rivet_step / 2, y - (y0 + y1) / 2) < 0.006)
    drip_k = np.floor(run / 0.023)
    drip_len = 0.02 + 0.07 * hash1(drip_k, 5) ** 2
    drip = b.walls & (y < y0) & (y > y0 - drip_len) & (np.abs(run % 0.023 - 0.0115) < 0.0025) & (hash1(drip_k, 6) > 0.55)
    return inside, rivet, rust_mask, drip


def wet_bottom(b, col, h=0.16, k=0.32):
    wet = smooth(h, 0.0, b.y) * b.walls
    return col * (1 - k * wet[..., None]), wet


def mineral_streaks(b, col, from_y, amount=0.35):
    k = np.floor(b.run / 0.031)
    length = 0.03 + 0.12 * hash1(k, 8)
    s = b.walls & (b.y < from_y) & (b.y > from_y - length) & (hash1(k, 9) > 0.6)
    s = s * smooth(0.006, 0.0, np.abs(b.run % 0.031 - 0.015)) * smooth(from_y - length, from_y, b.y)
    return mix(col, MINERAL, amount * blur(s.astype(float), 1.2))


def towel(b, col, gloss, x0, x1, z0, z1):
    """Folded linen towel lying flat on the lid, brick stripe near one short edge."""
    x, z = b.x, b.z
    t = b.lid_top & (x > x0) & (x < x1) & (z > z0) & (z < z1)
    shadow = b.lid_top & ~t & (x > x0 - 0.012) & (x < x1 + 0.006) & (z > z0 - 0.012) & (z < z1 + 0.004)
    col = mix(col, col * 0.65, shadow * 1.0)
    weave = 0.95 + 0.05 * np.sin(x * 900) * np.sin(z * 900)
    lin = LINEN * weave[..., None] * (0.97 + 0.06 * b.noise[..., None])
    fold = smooth(0.012, 0.0, np.abs(x - (x0 + x1) / 2)) * 0.12                # centre fold line
    lin = lin * (1 - fold[..., None])
    stripe = ((z > z1 - 0.07) & (z < z1 - 0.04)) | ((z > z1 - 0.032) & (z < z1 - 0.022))
    lin = np.where(stripe[..., None], BRICK * weave[..., None], lin)
    col = np.where(t[..., None], lin, col)
    gloss = np.where(t, 0.08, gloss)
    return col, gloss


def leaf(b, col, cx, cz, ang, size, colour, dry=0.0):
    """One flat birch/oak leaf on the lid with a midrib and side veins."""
    x, z = b.x - cx, b.z - cz
    ca, sa = np.cos(ang), np.sin(ang)
    u = (x * ca + z * sa) / size
    v = (-x * sa + z * ca) / size
    shape = (np.abs(v) < 0.45 * np.sqrt(np.clip(1 - u ** 2, 0, 1)) * (1.1 - 0.4 * u)) & (np.abs(u) < 1)
    m = b.lid_top & shape
    vein = (np.abs(v) < 0.03) | (np.abs((np.abs(v) * 2.2 - u * 0.9) % 0.35 - 0.17) < 0.025)
    c = colour * (1 + 0.25 * dry) * (1 - 0.25 * vein)[..., None]
    halo = b.lid_top & ~m & (u ** 2 + (v / 0.6) ** 2 < 1.5)
    col = mix(col, col * 0.85, halo * 0.6)
    return np.where(m[..., None], c, col)


def venik(b, col, cx, z0, z1, width):
    """A pressed dry venik lying on the lid along z: handle wrapped in twine, leaf mass widening."""
    rng = np.random.default_rng(3)
    for i in range(160):
        t = np.sqrt(rng.random())
        lz = z0 + (z1 - z0) * (0.25 + 0.75 * t)
        lx = cx + (rng.random() - 0.5) * width * (0.3 + 0.7 * t)
        colour = LEAF_OAK if rng.random() < 0.35 else LEAF_BIRCH * (0.9 + 0.3 * rng.random())
        col = leaf(b, col, lx, lz, rng.random() * np.pi, 0.028 + 0.012 * rng.random(), colour, rng.random() * 0.5)
    handle = b.lid_top & (np.abs(b.x - cx) < 0.018) & (b.z > z0) & (b.z < z0 + (z1 - z0) * 0.3)
    col = np.where(handle[..., None], STEAMED * (0.9 + 0.2 * (np.sin(b.z * 700) > 0))[..., None], col)
    wrap = handle & (np.sin(b.z * 1100) > 0.2) & (b.z > z0 + 0.03) & (b.z < z0 + 0.07)
    return np.where(wrap[..., None], TWINE, col)


def save(name, col, spec, gloss, emis=None, alpha=None):
    OUT.mkdir(parents=True, exist_ok=True)
    rgb = (np.clip(col, 0, 1) * 255).astype(np.uint8)
    if alpha is not None:
        rgb = np.dstack([rgb, (np.clip(alpha, 0, 1) * 255).astype(np.uint8)])
    Image.fromarray(rgb).save(OUT / f"{name}_diffuse.png")
    sg = np.dstack([np.repeat((np.clip(spec, 0, 1) * 255).astype(np.uint8)[..., None], 3, 2),
                    (np.clip(gloss, 0, 1) * 255).astype(np.uint8)])
    Image.fromarray(sg, "RGBA").resize((512, 512), Image.LANCZOS).save(OUT / f"{name}_specgloss.png")
    shutil.copy(ORIG / "Wooden_Box_nrm.png", OUT / f"{name}_normal.png")
    shutil.copy(ORIG / "wooden_box_ao.png", OUT / f"{name}_occlusion.png")
    if emis is not None:
        Image.fromarray((np.clip(emis, 0, 1) * 255).astype(np.uint8)).save(OUT / f"{name}_emission.png")
    print("wrote", name)


def concept_a(b):
    """A. Sauna Tub: a wet rectangular tub-box bound with two rusty iron bands, towel on the lid."""
    col = b.wood(ASPEN * 0.94, grey_share=0.25)
    col, wet = wet_bottom(b, col)
    gloss = np.full((SIZE, SIZE), 0.18) + 0.12 * wet
    spec = np.full((SIZE, SIZE), 0.07)
    for y0, y1 in ((0.045, 0.09), (0.31, 0.355)):
        inside, rivet, rust, drip = band(b, y0, y1)
        col = mix(col, RUST * 0.8, drip * 0.55)
        col = mix(col, MINERAL, (b.walls & (b.y < y0) & (b.y > y0 - 0.015)) * 0.15)
        iron = IRON * (1 - 0.45 * rust[..., None]) + RUST * 0.75 * 0.45 * rust[..., None]
        col = np.where(inside[..., None], iron * (0.9 + 0.2 * b.noise[..., None]), col)
        col = np.where(rivet[..., None], IRON * 1.4, col)
        gloss = np.where(inside, 0.25, gloss)
        spec = np.where(inside, 0.2, spec)
    # two flat iron straps across the lid, near the ends, nailed to every plank
    for zc in (-0.36, 0.36):
        s = b.lid_top & (np.abs(b.z - zc) < 0.022)
        col = np.where(s[..., None], (IRON * 0.6 + RUST * 0.4) * (0.9 + 0.2 * b.noise[..., None]), col)
        nail = s & (np.abs(((b.x + 0.37) % 0.103) - 0.05) < 0.005) & (np.abs(b.z - zc) < 0.006)
        col = np.where(nail[..., None], IRON * 1.5, col)
    col = mineral_streaks(b, col, 0.045)
    col = mineral_streaks(b, col, 0.31, 0.25)
    col, gloss = towel(b, col, gloss, 0.03, 0.30, 0.02, 0.27)
    save("A", col, spec, gloss)


def concept_b(b):
    """B. Sauna Chest: dry, light lining-board chest for veniks; two pressed veniks tied on the lid."""
    col = b.wood(ASPEN_LIGHT * 0.98, grey_share=0.15, spread=0.1)
    col = col * (1 - 0.15 * smooth(0.08, 0.0, b.y)[..., None] * b.walls[..., None])
    gloss = np.full((SIZE, SIZE), 0.15)
    spec = np.full((SIZE, SIZE), 0.06)
    col = venik(b, col, -0.12, -0.40, 0.30, 0.20)
    col = venik(b, col, 0.15, -0.30, 0.40, 0.19)
    # twine round the lid, across both veniks
    tw = b.lid_top & (np.abs(b.z + 0.02) < 0.006)
    col = np.where(tw[..., None], TWINE * (0.9 + 0.2 * (np.sin(b.x * 1400) > 0))[..., None], col)
    for cx, cz, a, c in ((-0.30, 0.42, 0.7, LEAF_OAK), (0.26, -0.43, 2.1, LEAF_BIRCH)):
        col = leaf(b, col, cx, cz, a, 0.035, c)
    save("B", col, spec, gloss)


def char(col, amount):
    return col * (1 - amount[..., None]) + SOOT * amount[..., None]


def concept_c(b, glow):
    """C. Sauna Ember Box by the stove: iron corner plates, the right side (towards the stove)
    smoked from the floor up, lid scorched where hot stones are set down. glow: None, "slots" (embers
    inside seen through the handle slots and plank gaps), "corner" (the front-right corner charred and
    smouldering), "grate" (a cast-iron draught grate on the front, embers behind it)."""
    col = b.wood(ASPEN * 0.95, grey_share=0.3)
    gloss = np.full((SIZE, SIZE), 0.14)
    spec = np.full((SIZE, SIZE), 0.06)
    # soot: the right side towards the stove, rising from the floor; plank edges heavier
    side = np.clip((b.x - 0.05) / 0.3, 0, 1) * b.walls + b.right * 0.6
    up = smooth(0.45, 0.05, b.y + 0.036 * b.blotch)
    soot = np.clip(side * up * (0.55 + 0.1 * b.blotch), 0, 0.85)
    edge = smooth(0.012, 0.0, np.abs(b.y[..., None] - np.array(PLANK_Y)[None, None, :]).min(-1))
    soot = np.clip(soot + edge * side * 0.4, 0, 0.9)
    col = char(col, soot)
    # iron corner plates (a bent strip over each vertical corner), top and bottom
    ends = b.front | b.back
    dist = np.where(ends, np.minimum(0.325 - b.x, b.x + 0.34), np.minimum(0.478 - b.z, b.z + 0.466))
    plate = b.walls & (dist < 0.055) & (((b.y > 0.02) & (b.y < 0.12)) | ((b.y > 0.41) & (b.y < 0.52)))
    rust = smooth(0.3, 0.8, b.blotch * 0.3 + 0.5)
    col = np.where(plate[..., None], (IRON * (1 - rust[..., None] * 0.5) + RUST * rust[..., None] * 0.5)
                   * (0.9 + 0.2 * b.noise[..., None]), col)
    gloss = np.where(plate, 0.28, gloss)
    # lid: scorched where hot stones are set down (soft, no rings); two iron straps at the ends
    sc = np.clip(b.lid_top * smooth(0.16, 0.02, np.hypot((b.x + 0.08) / 1.2, b.z - 0.05)) * (0.6 + 0.1 * b.blotch), 0, 1)
    col = char(col, 0.55 * sc)
    for zc in (-0.40, 0.40):
        s = b.lid_top & (np.abs(b.z - zc) < 0.02)
        col = np.where(s[..., None], (IRON * 0.7 + RUST * 0.3) * (0.9 + 0.2 * b.noise[..., None]), col)
    heat = np.zeros((SIZE, SIZE))
    if glow == "slots":
        # handle slots: the cut faces of the slot, and a faint warm wash on the lip round it
        slot = (np.abs(b.z) > 0.43) & (b.x > SLOT[0] - 0.005) & (b.x < SLOT[1] + 0.005) & (b.y > 0.395) & (b.y < SLOT[2] + 0.004)
        mid = 1 - np.clip(np.abs(b.x) / 0.17, 0, 1)
        heat = (slot & (np.abs(b.nrm[..., 2]) < 0.5)) * (0.45 + 0.55 * mid)
        lip = (b.front | b.back) & (b.x > SLOT[0] - 0.02) & (b.x < SLOT[1] + 0.02) & (b.y > 0.39) & (b.y < 0.47)
        slot_edge_y = np.where(np.abs(b.x) < 0.09, 0.45, 0.45 - (np.abs(b.x) - 0.09) / 0.07 * 0.045)
        d = np.minimum(np.abs(b.y - slot_edge_y), np.abs(b.y - 0.40))
        heat = np.maximum(heat, lip * smooth(0.02, 0.0, d) * 0.35 * (0.4 + 0.6 * mid))
        # plank gaps on the stove side: thin ember lines along the gap lips, dying out at the ends
        gap_d = np.abs(b.y[..., None] - np.array(PLANK_Y[1:-1])[None, None, :]).min(-1)
        t = np.where(b.right, 0.478 - b.z, 0.325 - b.x)                  # from the front-right corner
        along = smooth(0.45, 0.05, t)
        heat = np.maximum(heat, (b.right | b.front) * smooth(0.006, 0.0015, gap_d)
                          * (0.25 + 0.75 * b.noise) * along * 0.7)
    elif glow == "corner":
        # the front-right corner charred into the wood and still smouldering in its cracks
        dist = np.where(b.front, 0.325 - b.x, np.where(b.right, 0.478 - b.z, 9))
        reach = 0.05 + 0.05 * smooth(0.4, 0.0, b.y) + 0.02 * b.blotch
        burnt = smooth(reach, reach * 0.4, dist) * (b.front | b.right)
        col = char(col, 0.85 * burnt)
        crack = smooth(0.85, 0.7, b.detail) + 0.6 * smooth(0.04, 0.0, np.abs(b.noise - 0.5)) * smooth(0.48, 0.52, b.noise + 0.02)
        heat = burnt * smooth(0.3, 0.9, burnt) * np.clip(crack, 0, 1) * (0.5 + 0.5 * smooth(0.35, 0.05, b.y))
    elif glow == "grate":
        # a cast-iron draught grate on the front bottom plank; embers behind its slots
        g = b.front & (np.abs(b.x + 0.005) < 0.11) & (b.y > 0.025) & (b.y < 0.11)
        col = np.where(g[..., None], IRON * (0.85 + 0.2 * b.noise[..., None]), col)
        col = np.where((b.front & (np.abs(b.x + 0.005) < 0.118) & (b.y > 0.018) & (b.y < 0.117) & ~g)[..., None], IRON * 0.6, col)
        u = (b.x + 0.005 + 0.11) / 0.22 * 6
        slot = g & (np.abs(u % 1 - 0.5) < 0.22) & (u > 0.5) & (u < 5.5) & (b.y > 0.04) & (b.y < 0.095)
        heat = slot * (0.55 + 0.45 * smooth(0.095, 0.045, b.y)) * (0.7 + 0.3 * b.noise)
        gloss = np.where(g, 0.3, gloss)
    emis = None
    if glow:
        heat = blur(heat, 0.8)
        core = smooth(0.3, 0.9, heat)
        emis = (EMBER_EDGE * (1 - core[..., None]) + EMBER_CORE * core[..., None]) * heat[..., None]
        col = np.where((heat > 0.2)[..., None], col * 0.6 + SOOT * 0.4, col)
    save(f"C_{glow}" if glow else "C", col, spec, gloss, emis)


def felt_pad(b, col, gloss, x0, x1, z0, z1):
    """A felt sitting pad lying flat on the lid: soft rounded corners, a running stitch round the edge."""
    x, z = b.x, b.z
    r = 0.025
    dx = np.maximum(np.maximum(x0 + r - x, x - (x1 - r)), 0)
    dz = np.maximum(np.maximum(z0 + r - z, z - (z1 - r)), 0)
    inside_d = r - np.hypot(dx, dz)                        # > 0 inside the rounded rectangle
    pad = b.lid_top & (inside_d > 0)
    shadow = b.lid_top & ~pad & (inside_d > -0.012)
    col = mix(col, col * 0.7, shadow * smooth(-0.012, 0.0, inside_d))
    f = FELT * (0.93 + 0.1 * b.noise[..., None] + 0.03 * b.blotch[..., None])
    f = f * (1 - 0.18 * smooth(0.04, 0.0, inside_d))[..., None] * (1 + 0.04 * smooth(0.02, 0.06, inside_d))[..., None]
    run = np.where(np.minimum(np.abs(x - x0), np.abs(x - x1)) < np.minimum(np.abs(z - z0), np.abs(z - z1)), z, x)
    stitch = pad & (np.abs(inside_d - 0.012) < 0.0018) & (np.sin(run * 420) > 0)
    f = np.where(stitch[..., None], LINEN * 0.9, f)
    sit = smooth(0.12, 0.0, np.hypot(x - (x0 + x1) / 2, (z - (z0 + z1) / 2) * 0.8))   # pressed where people sit
    f = f * (1 - 0.1 * sit)[..., None]
    col = np.where(pad[..., None], f, col)
    gloss = np.where(pad, 0.04, gloss)
    return col, gloss


def stones_inside(b, col, emis):
    """Open top: basalt stones on the floor inside, embers glowing in the gaps between them.
    The inner floor shares texels only with the outer bottom, which nobody sees."""
    floor, fx, fz = b.inner_floor()
    rng = np.random.default_rng(5)
    c = np.column_stack([rng.uniform(-0.34, 0.34, 90), rng.uniform(-0.45, 0.45, 90)])
    size = rng.uniform(0.8, 1.25, 90)
    ys, xs = np.nonzero(floor)
    px = np.column_stack([fx[ys, xs], fz[ys, xs]])
    d = np.linalg.norm(px[:, None, :] - c[None, :, :], axis=2) / size[None, :]
    o = np.argsort(d, axis=1)
    d1 = d[np.arange(len(d)), o[:, 0]]
    d2 = d[np.arange(len(d)), o[:, 1]]
    edge = d2 - d1                                          # 0 on the gap between two stones
    tone = hash1(o[:, 0], 21)
    dome = np.clip(1 - d1 / 0.06, 0, 1)                     # lighter towards the top of each stone
    stone = hexc("#3D3E41") * (0.75 + 0.35 * tone[:, None]) * (0.8 + 0.45 * dome[:, None])
    gap = np.clip(1 - edge / 0.012, 0, 1) ** 2
    stone = stone * (1 - 0.8 * gap[:, None])
    col[ys, xs] = stone
    # embers: in the gaps, hotter in the middle and towards the stove side (+x)
    hot = gap * np.clip(0.35 + 0.65 * (1 - np.hypot(px[:, 0] - 0.08, px[:, 1] * 0.7) / 0.4), 0, 1)
    hot = hot * (0.5 + 0.5 * hash1(o[:, 0] * 7 + o[:, 1], 22))
    heat = np.zeros(b.x.shape)
    heat[ys, xs] = hot
    heat = blur(heat, 0.7)
    core = smooth(0.3, 0.9, heat)
    emis = np.maximum(emis, (EMBER_EDGE * (1 - core[..., None]) + EMBER_CORE * core[..., None]) * heat[..., None])
    return col, emis


def concept_d(b, lid_cut=None):
    """D (mine). Sauna Stone Box: the box by the stove where spare stones and embers are kept hot,
    bound with two iron bands; a felt pad on the lid (it doubles as a seat); the stones glow through
    the handle slots and the gaps on the stove side."""
    col = b.wood(ASPEN * 0.95, grey_share=0.25)
    gloss = np.full((SIZE, SIZE), 0.14)
    spec = np.full((SIZE, SIZE), 0.06)
    side = np.clip((b.x - 0.05) / 0.3, 0, 1) * b.walls + b.right * 0.5
    soot = np.clip(side * smooth(0.35, 0.03, b.y + 0.036 * b.blotch) * (0.45 + 0.1 * b.blotch), 0, 0.7)
    col = char(col, soot)
    for y0, y1 in ((0.045, 0.09), (0.31, 0.355)):
        inside, rivet, rust, drip = band(b, y0, y1)
        col = mix(col, RUST * 0.8, drip * 0.35)
        iron = IRON * (1 - 0.45 * rust[..., None]) + RUST * 0.75 * 0.45 * rust[..., None]
        col = np.where(inside[..., None], iron * (0.9 + 0.2 * b.noise[..., None]), col)
        col = np.where(rivet[..., None], IRON * 1.4, col)
        gloss = np.where(inside, 0.25, gloss)
        spec = np.where(inside, 0.2, spec)
    sc = np.clip(b.lid_top * smooth(0.12, 0.02, np.hypot(b.x - 0.2, (b.z + 0.25) * 0.9)) * (0.5 + 0.1 * b.blotch), 0, 1)
    col = char(col, 0.5 * sc)
    col, gloss = felt_pad(b, col, gloss, -0.27, 0.13, -0.05, 0.36)
    col = leaf(b, col, 0.22, 0.30, 2.2, 0.03, LEAF_BIRCH)
    # glow: as C "slots"
    slot = (np.abs(b.z) > 0.43) & (b.x > SLOT[0] - 0.005) & (b.x < SLOT[1] + 0.005) & (b.y > 0.395) & (b.y < SLOT[2] + 0.004)
    mid = 1 - np.clip(np.abs(b.x) / 0.17, 0, 1)
    heat = (slot & (np.abs(b.nrm[..., 2]) < 0.5)) * (0.45 + 0.55 * mid)
    lip = (b.front | b.back) & (b.x > SLOT[0] - 0.02) & (b.x < SLOT[1] + 0.02) & (b.y > 0.39) & (b.y < 0.47)
    slot_edge_y = np.where(np.abs(b.x) < 0.09, 0.45, 0.45 - (np.abs(b.x) - 0.09) / 0.07 * 0.045)
    d = np.minimum(np.abs(b.y - slot_edge_y), np.abs(b.y - 0.40))
    heat = np.maximum(heat, lip * smooth(0.02, 0.0, d) * 0.35 * (0.4 + 0.6 * mid))
    gap_d = np.abs(b.y[..., None] - np.array(PLANK_Y[1:-1])[None, None, :]).min(-1)
    t = np.where(b.right, 0.478 - b.z, 0.325 - b.x)
    heat = np.maximum(heat, (b.right | b.front) * smooth(0.006, 0.0015, gap_d) * (0.25 + 0.75 * b.noise)
                      * smooth(0.45, 0.05, t) * 0.7)
    heat = blur(heat, 0.8)
    core = smooth(0.3, 0.9, heat)
    emis = (EMBER_EDGE * (1 - core[..., None]) + EMBER_CORE * core[..., None]) * heat[..., None]
    col = np.where((heat > 0.2)[..., None], col * 0.6 + SOOT * 0.4, col)
    if lid_cut is None:
        save("D", col, spec, gloss, emis)
        return
    # lid_cut "all": the whole lid cut out with alpha. Its texels are also the inner left wall and half of
    # the inner back wall (uv/islands.md), so those vanish with it - the preview shows exactly that.
    # lid_cut "plank": only the outermost right plank (island 3, x 0.252..0.371) is gone: it shares
    # texels with nothing but its own underside, so every inner wall stays; embers show through the slot.
    # lid_cut "three": planks 3, 9 and 19 are gone (the lid half taken apart for kindling): the inner left
    # wall stays whole, only the middle of the inner back wall (planks 9 and 19's texels) goes.
    col, emis = stones_inside(b, col, emis)
    keep = {"all": lambda x: False, "plank": lambda x: x < 0.2535,
            "three": lambda x: not (x > 0.2535 or -0.0615 < x < 0.0405 or -0.2665 < x < -0.164)}[lid_cut]
    cut = b.face_mask(lambda P: is_lid(P) and not keep(P[:, 0].mean()))
    name = {"all": "D_open", "plank": "D_slot", "three": "D_three"}[lid_cut]
    save(name, col, spec, gloss, emis, alpha=~cut)


def row_obj(n=6, step=0.715):
    """n boxes side by side along x (long sides touching), the way they stand in a base."""
    lines = (ORIG / "box.wooden.obj").read_text(encoding="utf8").splitlines()
    V = [l for l in lines if l.startswith("v ")]
    VT = [l for l in lines if l.startswith("vt ")]
    VN = [l for l in lines if l.startswith("vn ")]
    Fs = [l for l in lines if l.startswith("f ")]
    out = ["o row"]
    for k in range(n):
        dx = (k - (n - 1) / 2) * step
        out += [f"v {float(a) + dx:.6f} {b_} {c}" for a, b_, c in (l.split()[1:4] for l in V)]
    out += VT + VN
    for k in range(n):
        off = k * len(V)
        for l in Fs:
            parts = []
            for c in l.split()[1:]:
                i = c.split("/")
                i[0] = str(int(i[0]) + off)
                parts.append("/".join(i))
            out.append("f " + " ".join(parts))
    (OUT / "row6.obj").write_text("\n".join(out) + "\n", encoding="utf8")


def main():
    b = Box()
    concept_a(b)
    concept_b(b)
    for glow in (None, "slots", "corner", "grate"):
        concept_c(b, glow)
    concept_d(b)
    concept_d(b, lid_cut="all")
    concept_d(b, lid_cut="plank")
    concept_d(b, lid_cut="three")
    row_obj()


if __name__ == "__main__":
    main()
