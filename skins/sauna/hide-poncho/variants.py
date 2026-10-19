"""Hide Poncho for the Sauna set: three look variants side by side, to choose from in game.

  A  sheepskin cape: tan leather outside, cream wool on the inside, turned out as a trim along the
     hem and round the neck; the fur tuft on the shoulder becomes cream wool; wooden toggles.
  B  felt sauna cape: grey-beige felt with a stitched zigzag band (brick and dark brown, no text)
     along the hem; the fur tuft is cut away (alpha 0).
  C  terry towel poncho: washed linen-white terry with two wide faded brick stripes along the hem
     and a fringed edge; the fur tuft is cut away.

The model is two meshes on one material: the hide (a closed shell: the outside and the inside are
two UV islands that meet at the hem and round the neck) and fur cards on the right shoulder (strand
textures with alpha in the bottom-right corner of the texture, Alpha Cutoff 0.24). Every texel is
mapped to its 3D point (OBJ space, metres: Y up, +Z front); the distance to the outside/inside seam
gives the hem and neck trims, continuous across UV seams.

    .venv/Scripts/python skins/sauna/hide-poncho/variants.py
Writes export/HidePoncho_{A,B,C}_{diffuse,normal}.png and uv/{A,B,C}_views.png.
"""
import collections
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
from uv_zones import classify, load_obj, normal, read_png, render_views  # noqa: E402

ORIG = HERE / "originals"
OUT = HERE / "export"
SIZE = 1024
SEED = 23


def hexc(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float64) / 255.0


def blur(a, r):
    f = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
    return np.asarray(f, np.float64) / 255.0


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


LEATHER = hexc("#8A6646")
LEATHER_DARK = hexc("#5E4430")
WOOL = hexc("#D6C8AC")
WOOL_DARK = hexc("#A39579")
FELT = hexc("#B3A48A")
FELT_IN = hexc("#C2B49A")
BRICK = hexc("#8E3A30")
DARK = hexc("#45332A")
TOWEL = hexc("#CFC6B4")
WOOD = hexc("#6B4D33")


def face_islands(F):
    """UV island id per face (faces sharing a texture vertex are one island)."""
    par = list(range(len(F)))

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i

    by_t = collections.defaultdict(list)
    for f, (_, ti) in enumerate(F):
        for t in ti:
            by_t[t].append(f)
    for fs in by_t.values():
        for f in fs[1:]:
            par[find(f)] = find(fs[0])
    return np.array([find(f) for f in range(len(F))])


def raster(V, T, F, label):
    """Per texel: 3D point and a label (per face) of the last face drawn there."""
    pos = np.zeros((SIZE, SIZE, 3))
    lab = np.full((SIZE, SIZE), -1, np.int64)
    Va, Ta = np.array(V), np.array(T)
    for f, (vi, ti) in enumerate(F):
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
        lab[ys + y0, xs + x0] = label[f]
    cov = lab >= 0
    for _ in range(6):                                  # gutter
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            take = ~cov & np.roll(np.roll(cov, dy, 0), dx, 1)
            pos[take] = np.roll(np.roll(pos, dy, 0), dx, 1)[take]
            lab[take] = np.roll(np.roll(lab, dy, 0), dx, 1)[take]
            cov |= take
    return pos, lab, cov


def nearest_dist(pts, samples, chunk=20000):
    out = np.full(len(pts), 9.0)
    if len(samples) == 0:
        return out
    for i in range(0, len(pts), chunk):
        d = np.linalg.norm(pts[i:i + chunk, None, :] - samples[None, :, :], axis=-1)
        out[i:i + chunk] = d.min(1)
    return out


def grad_normal(h, k):
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    return -gx * k, gy * k


def geometry():
    """Texel -> 3D point, outside/inside, toggles, distance to the hem and to the neck edge."""
    V, T, F = load_obj(ORIG / "attire.hide.poncho_poncho.obj")
    N = [normal(*(V[i] for i in vi)) for vi, _ in F]
    # Two layers: the UV islands follow the hide's two layers (left island = outer layer, right =
    # the overlapping front flap / inner layer); where they meet is a real edge (hem, neck, the front
    # opening with the toggles) -> trims. Which faces are seen from outside comes from visibility
    # (uv_zones.classify: faces seen in none of the 5 views are the inside -> wool / lining).
    isl = face_islands(F)
    big = [i for i, _ in collections.Counter(isl).most_common(2)]
    mean_u = {i: np.mean([T[t][0] for f in np.nonzero(isl == i)[0] for t in F[f][1]]) for i in big}
    outer_id, inner_id = sorted(big, key=lambda i: mean_u[i])
    side = np.where(isl == outer_id, 1, np.where(isl == inner_id, 2, 3))     # 3 = toggles etc.
    zone = classify(V, F, N)
    hidden_f = np.array([z_.startswith("hidden") for z_ in zone])
    vis_label = np.where(side == 3, 3, np.where(hidden_f, 2, 1))
    _, vis, _ = raster(V, T, F, vis_label)
    pos, lab, cov = raster(V, T, F, side)
    small = lab == 3
    outer, inner = (vis == 1) & ~small, (vis == 2) & ~small
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]

    # seam between outside and inside = the hem and the neck edge
    edge_faces = collections.defaultdict(list)
    for f, (vi, _) in enumerate(F):
        for a, b in ((vi[0], vi[1]), (vi[1], vi[2]), (vi[2], vi[0])):
            edge_faces[tuple(sorted((a, b)))].append(f)
    Va = np.array(V)
    samples = []
    for (a, b), fs in edge_faces.items():
        sides = {side[f] for f in fs}
        if 1 in sides and 2 in sides:
            for t in (0.0, 0.5):
                samples.append(Va[a] * (1 - t) + Va[b] * t)
    samples = np.array(samples)
    neck_c = np.array([0.0, 1.47, 0.0])
    is_neck = (samples[:, 1] > 1.36) & (np.hypot(samples[:, 0], samples[:, 2]) < 0.17)
    flat = pos[cov]
    d_hem = np.full(cov.shape, 9.0)
    d_neck = np.full(cov.shape, 9.0)
    d_hem[cov] = nearest_dist(flat, samples[~is_neck])
    d_neck[cov] = nearest_dist(flat, samples[is_neck])
    print("seam samples", len(samples), "neck", int(is_neck.sum()))

    return dict(V=V, T=T, F=F, N=N, pos=pos, cov=cov, outer=outer, inner=inner, small=small,
                x=x, y=y, z=z, d_hem=d_hem, d_neck=d_neck)


def main():
    g = geometry()
    V, T, F, N, pos, cov = g["V"], g["T"], g["F"], g["N"], g["pos"], g["cov"]
    outer, inner, small, x, y, z = g["outer"], g["inner"], g["small"], g["x"], g["y"], g["z"]
    d_hem, d_neck = g["d_hem"], g["d_neck"]

    bc = np.asarray(Image.open(ORIG / "hide_poncho_bc.png").convert("RGBA"), np.float64) / 255.0
    alpha0 = (bc[..., 3] * 255).round().astype(np.uint8)
    lum = bc[..., :3] @ np.array([0.299, 0.587, 0.114])
    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    fur = (xx > 0.78 * SIZE) & (yy > 0.76 * SIZE)          # fur strand cards
    folds = np.clip(blur(lum, 3) / np.maximum(blur(lum, 24), 1e-3), 0.7, 1.35)
    stains = np.clip(1 - lum / np.maximum(blur(lum, 10), 1e-3), 0, 0.6)
    rng = np.random.default_rng(SEED)
    noise = lambda r: blur(rng.random((SIZE, SIZE)), r)

    n0 = np.asarray(Image.open(ORIG / "hide_poncho_nrm.png").convert("RGB").resize((SIZE, SIZE), Image.BICUBIC), np.float64) / 255 * 2 - 1
    fx = (blur(n0[..., 0] * 0.5 + 0.5, 2) * 2 - 1)
    fy = (blur(n0[..., 1] * 0.5 + 0.5, 2) * 2 - 1)

    def save(tag, col, h, k, alpha, keep_orig=None):
        hx, hy = grad_normal(h, k)
        nx, ny = fx + hx, fy + hy
        if keep_orig is not None:
            nx = np.where(keep_orig, n0[..., 0], nx)
            ny = np.where(keep_orig, n0[..., 1], ny)
        nz = np.sqrt(np.clip(1 - nx ** 2 - ny ** 2, 0.05, 1))
        ln = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2)
        q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
        full = np.full((SIZE, SIZE), 255, np.uint8)
        col = np.where((~cov & ~fur)[..., None], col.mean((0, 1)), col)
        OUT.mkdir(exist_ok=True)
        Image.fromarray(np.dstack([q(col), alpha]), "RGBA").save(OUT / f"HidePoncho_{tag}_diffuse.png")
        Image.fromarray(np.dstack([q(nx / ln * 0.5 + 0.5), q(ny / ln * 0.5 + 0.5), full, full]), "RGBA").save(OUT / f"HidePoncho_{tag}_normal.png")
        render_views(V, T, F, N, HERE / "uv" / f"{tag}_views.png", tex=read_png(OUT / f"HidePoncho_{tag}_diffuse.png"))

    # ---------------------------------------------------------------- A: sheepskin
    jag = 0.006 * (noise(2) - 0.5) * 2
    trim = np.maximum(smooth(0.032, 0.026, d_hem + jag), smooth(0.04, 0.034, d_neck + jag)) * ~small
    wool = np.clip(trim + inner, 0, 1)
    curls = noise(1.0)
    clumps = noise(3.5)
    leather = LEATHER * (1 + 0.5 * (folds - 1))[..., None] * (0.92 + 0.12 * noise(20))[..., None]
    leather = leather * (1 - 0.5 * stains[..., None]) + LEATHER_DARK * 0.5 * stains[..., None]
    leather = leather * (0.94 + 0.1 * noise(0.7))[..., None]
    wc = WOOL * (0.74 + 0.26 * curls + 0.1 * clumps)[..., None]
    wc = wc * (1 - 0.35 * smooth(0.45, 0.25, clumps)[..., None]) + WOOL_DARK * 0.35 * smooth(0.45, 0.25, clumps)[..., None]
    col = leather * (1 - wool[..., None]) + wc * wool[..., None]
    col[small] = WOOD * (0.85 + 0.3 * noise(1.5)[small][..., None])
    col[fur] = (WOOL * (0.45 + 0.75 * lum[..., None]))[fur]       # cream wool tuft, strands from the original
    h = np.where(wool > 0.5, curls + 0.6 * clumps, 0.4 * noise(0.8) + 0.3 * stains)
    save("A", col, h, 3.0 * wool + 1.0 * (1 - wool), alpha0, keep_orig=fur | small)

    # ---------------------------------------------------------------- B: felt with a stitched zigzag band
    fib = noise(0.8)
    mott = noise(8)
    felt = np.where(inner[..., None], FELT_IN, FELT) * (0.88 + 0.12 * fib + 0.1 * mott)[..., None]
    felt = felt * (1 + 0.3 * (folds - 1))[..., None] * (1 - 0.15 * stains[..., None])
    # band 3..9 cm from the hem: two dark rules and a brick zigzag between them (along the hem: use the
    # angle round the body as the running coordinate)
    run = np.arctan2(x, z) * 0.28 + y * 0.0              # metres along the hem, roughly
    dz = d_hem
    rules = ((np.abs(dz - 0.035) < 0.0035) | (np.abs(dz - 0.085) < 0.0035)) & (outer | inner)
    zig_y = 0.06 + 0.017 * (2 * np.abs(np.mod(run / 0.04, 1) - 0.5) * 2 - 1)
    zig = (np.abs(dz - zig_y) < 0.005) & (outer | inner)
    dots = (np.hypot(np.mod(run, 0.04) - 0.02, dz - 0.06) < 0.004) & (outer | inner)
    col = felt.copy()
    col[rules] = DARK * (0.9 + 0.2 * fib[rules][..., None])
    col[zig] = BRICK * (0.85 + 0.25 * fib[zig][..., None])
    col[dots] = WOOL
    col[small] = WOOD * (0.85 + 0.3 * noise(1.5)[small][..., None])
    alphaB = np.where(fur, 0, alpha0).astype(np.uint8)
    h = 0.5 * fib + 0.6 * mott + 0.5 * (rules | zig | dots)
    save("B", col, h, 1.2, alphaB, keep_orig=small)

    # ---------------------------------------------------------------- C: terry towel poncho
    loops = noise(0.6)
    tw = TOWEL * (0.9 + 0.14 * loops)[..., None] * (1 + 0.35 * (folds - 1))[..., None] * (0.95 + 0.07 * noise(25))[..., None]
    wide = ((np.abs(d_hem - 0.075) < 0.018) | (np.abs(d_hem - 0.115) < 0.008)) & (outer | inner)
    fade = 0.5 + 0.25 * noise(6)
    col = tw.copy()
    col[wide] = (tw * (1 - fade[..., None]) + BRICK * fade[..., None] * (0.9 + 0.15 * loops[..., None]))[wide]
    fringe_zone = d_hem < 0.018
    threads = (np.sin(run * 2 * np.pi / 0.006) > 0.2) & fringe_zone
    col[fringe_zone] = col[fringe_zone] * 0.9
    col[threads] = TOWEL * 0.78
    col[small] = WOOD * (0.85 + 0.3 * noise(1.5)[small][..., None])
    alphaC = np.where(fur, 0, alpha0).astype(np.uint8)
    h = loops + 0.8 * threads
    save("C", col, h, 2.0, alphaC, keep_orig=small)
    print("done; outer", int(outer.sum()), "inner", int(inner.sum()), "trim", int((trim > 0.5).sum()))


if __name__ == "__main__":
    main()
