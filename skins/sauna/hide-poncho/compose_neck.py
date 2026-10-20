"""Sauna Towel v3.4 (neck): compose the export textures from the Blender bake (towel_neck_bake.py).

v3 in game (screenshots/v3_neck_front.webp) read as a white vest: flat bright white, wide bands,
and stray white flecks by the toggles. v3.1:
  - the towel is wider (13 cm, user wish) and rolled thicker (3 cm) (towel_neck_bake.py);
  - shading: the baked normal's tilt darkens the towel's rolled sides (it reads as a roll, not a
    slab) on top of the baked AO;
  - clean mask: the toggles and the fur cards are never towel; thin slivers and specks (rays that
    caught the towel from the hide's rim or the second layer of the flap) are removed by an
    opening (erode, then grow back) in texture space.

    .venv/Scripts/python skins/sauna/hide-poncho/compose_neck.py
Writes export/HidePoncho_v3_neck_{diffuse,normal,specgloss}.png (2048) and uv/v3_neck_views.png.
v3.3: 2048 bake, front-most layer only on the chest, a matte spec/gloss map.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "tools"))
import variants as v  # noqa: E402
from uv_zones import read_png, render_views  # noqa: E402

SIZE, OUT = 2048, v.OUT
SHAPE = sys.argv[1] if len(sys.argv) > 1 else "neck"     # neck | shoulder
TAG = {"neck": "v3_neck", "shoulder": "v4_shoulder", "drape": "v5_shoulder"}[SHAPE]
v.SIZE = SIZE                      # rasterise the hide at the bake's resolution
BAKE = HERE / "bake"


def load(name):
    return np.asarray(Image.open(BAKE / f"towel_{SHAPE}_{name}.png").convert("RGB"), np.float64) / 255.0


def main():
    g = v.geometry()
    small, cov = g["toggles"], g["cov"]   # only the wooden toggles; "small" also holds a patch of hide
    albedo, mask, ao, nrm = load("albedo"), load("mask")[..., 0], load("ao")[..., 0], load("normal")

    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    fur = (xx > 0.78 * SIZE) & (yy > 0.76 * SIZE)
    m = (mask > 0.5) & ~small & ~fur & cov
    # front z-buffer: on the chest the hide is two layers by the toggles (the flap over the panel);
    # the towel baked onto both, giving a double edge and grey under-panel patches (v3.2). Keep only
    # the front-most hide surface there.
    x, y, z = g["x"], g["y"], g["z"]
    chest = cov & (z > 0.05) & (y < 1.40)
    bx = np.floor(x / 0.006).astype(np.int64)
    by = np.floor(y / 0.006).astype(np.int64)
    key = (bx + 1000) * 100000 + (by + 1000)
    kc, zc = key[chest], z[chest]
    order = np.argsort(kc)
    ks, zs = kc[order], zc[order]
    starts = np.r_[0, np.nonzero(np.diff(ks))[0] + 1]
    zmax = np.maximum.reduceat(zs, starts)
    idx = np.searchsorted(ks[starts], key[chest])
    front = np.zeros_like(cov)
    front[chest] = zc >= zmax[np.clip(idx, 0, len(zmax) - 1)] - 0.006
    m = m & (~chest | front)
    # only hide texels right under the towel: near its centre line sideways (half width + 6 mm) and
    # within 1.5 cm of the surface it was laid on. v3.4: a fold of the hide behind the neck lay within
    # the bake's ray reach and caught a floating scrap of towel.
    path = np.load(BAKE / f"towel_{SHAPE}_path.npy") if SHAPE != "drape" else None
    if path is None:                                    # v5 drape: the towel mesh itself is the limit
        path = np.zeros((1, 11))
    C, Nn = path[:, :3], path[:, 3:6]
    Bn = path[:, 6:9] if path.shape[1] >= 11 else None
    WL, WR = (path[:, 9], path[:, 10]) if path.shape[1] >= 11 else (None, None)
    pts = np.stack([g["x"], g["y"], g["z"]], -1)[m]
    keep_pt = np.zeros(len(pts), bool)
    for i in (range(0, len(pts), 20000) if SHAPE != "drape" else []):
        P = pts[i:i + 20000]
        d = np.linalg.norm(P[:, None, :] - C[None, :, :], axis=-1)
        j = d.argmin(1)
        rel = P - C[j]
        h = np.abs((rel * Nn[j]).sum(1))
        lat = np.sqrt(np.maximum((rel ** 2).sum(1) - h ** 2, 0))
        if Bn is None:
            keep_pt[i:i + 20000] = (h < 0.015) & (lat < 0.055 + 0.006)
        else:
            t = (rel * Bn[j]).sum(1)                    # signed: left -, right +
            keep_pt[i:i + 20000] = (h < 0.02) & (t > -WL[j] - 0.012) & (t < WR[j] + 0.012)
    if SHAPE != "drape":
        mm = np.zeros_like(m)
        mm[m] = keep_pt
        m = mm
    filt = lambda a, f: np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(f)) > 127
    # closing fills pinholes in the hit mask (v3.1: grey specks), opening drops specks and slivers
    # thinner than ~4 texels; the strip's outline stays
    m = filt(filt(m, ImageFilter.MaxFilter(13)), ImageFilter.MinFilter(13)) & ~small & ~fur & cov
    m = filt(filt(m, ImageFilter.MinFilter(9)), ImageFilter.MaxFilter(9)) & m
    # drop small separate pieces (the flap's second layer by the toggles catches a sliver of towel)
    lab = Image.fromarray((m * 255).astype(np.uint8))
    keep = np.zeros_like(m)
    ys, xs = np.nonzero(m)
    seen = np.zeros_like(m)
    for yy0, xx0 in zip(ys[::97], xs[::97]):
        if seen[yy0, xx0] or not m[yy0, xx0]:
            continue
        tmp = lab.copy()
        ImageDraw.floodfill(tmp, (int(xx0), int(yy0)), 128)
        comp = np.asarray(tmp) == 128
        seen |= comp
        if comp.sum() > 24000:
            keep |= comp
    m = keep
    soft = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)), np.float64) / 255.0

    nz = np.clip(nrm[..., 2] * 2 - 1, 0, 1)
    # terry pile (v3.4: v3.3 read as a plain white strip): loops of 2-3 texels in tufts, strong
    # in the normal and visible in the colour
    rng0 = np.random.default_rng(7)
    loops = v.blur(rng0.random((SIZE, SIZE)), 1.0)
    loops = (loops - loops.mean()) / (loops.std() + 1e-6)
    tufts = v.blur(rng0.random((SIZE, SIZE)), 3.0)
    tufts = (tufts - tufts.mean()) / (tufts.std() + 1e-6)
    pile = np.clip(0.5 + 0.18 * loops + 0.12 * tufts, 0, 1)
    # rolled sides darker, from the towel's own profile (baked "shade"). v3.4 used the baked
    # normal's tilt, which is also large where the hide under the towel is dented - those dents
    # came out as dark patches ("a hole") although the normal map already flattens them
    if SHAPE == "drape":
        side = np.ones((SIZE, SIZE))                    # the real folds and AO do the shading
    else:
        shade = load("shade")[..., 0]
        side = 0.68 + 0.32 * np.sqrt(np.clip(shade, 0, 1))
    # dirtier (v3.2): a used towel - greyed and yellowed, blotchy stains, grime in the folds,
    # sweat at the neck, darker lower ends
    rng = np.random.default_rng(43)
    nse = lambda r: v.blur(rng.random((SIZE, SIZE)), r)
    stain = v.smooth(0.52, 0.62, nse(14)) * 0.22 + v.smooth(0.55, 0.65, nse(5)) * 0.12
    neck = v.smooth(0.07, 0.0, g["d_neck"]) * (0.35 if SHAPE == "neck" else 0.15)
    low = v.smooth(1.25, 1.1, g["y"]) * 0.12
    used = np.array([0.86, 0.82, 0.74])
    diffuse = albedo * used * (0.5 + 0.5 * ao[..., None]) * side[..., None] * (0.85 + 0.3 * pile)[..., None]
    diffuse = diffuse * (1 - (stain + low)[..., None]) + np.array([0.42, 0.36, 0.28]) * (stain + low)[..., None]
    diffuse = diffuse * (1 - neck[..., None]) + np.array([0.62, 0.55, 0.40]) * neck[..., None]
    # the hide's worn holes are tunnels through its thickness; their walls catch the towel at a
    # grazing angle and came out as flat grey patches (v3.4). Repaint them from the towel around
    # them (colour and normal), so they read as dents in the towel instead of grey holes.
    lum = diffuse.mean(-1)
    sat = diffuse.max(-1) - diffuse.min(-1)
    ref = np.stack([v.blur(lum * m, 25)], -1)[..., 0] / np.maximum(v.blur(m.astype(np.float64), 25), 1e-3)
    bad = m & (lum < 0.72 * ref) & (sat < 0.12)
    bad = np.asarray(Image.fromarray((bad * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(7))) > 127
    bad &= m
    w = (m & ~bad).astype(np.float64)
    for r in (2, 6, 16):
        acc = np.stack([v.blur(diffuse[..., i] * w, r) for i in range(3)], -1)
        cnt = v.blur(w, r)[..., None]
        sel = (bad & (w < 0.5) & (cnt[..., 0] > 0.01))
        diffuse = np.where(sel[..., None], acc / np.maximum(cnt, 1e-3), diffuse)
        # (normals are NOT copied: in a dent the baked normal is what flattens it)
        w = np.maximum(w, sel.astype(np.float64))
    print("repainted hole texels", int(bad.sum()))
    # the hide's worn holes go through its outer layer: through them one sees the inside layer
    # (also towel), which faces the body and sits in shadow -> a dark "hole" (v3.4). Brighten the
    # inside layer under the towel so the holes read as soft dips in the terry.
    _, fid, _ = v.raster(g["V"], g["T"], g["F"], np.arange(len(g["F"])))
    fn = np.array(g["N"])[np.clip(fid, 0, None)]
    pos = np.stack([g["x"], g["y"], g["z"]], -1)
    inside = ((fn * (pos - np.array([0.0, 1.2, -0.02]))).sum(-1) < 0) & m     # faces turned to the body
    if SHAPE == "shoulder":
        # the inside of the hide is only ever seen through the neck opening or the open sides: no towel
        m = m & ~inside
        inside = inside & m
        soft = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)), np.float64) / 255.0
    if SHAPE == "drape":
        # v5.2: the inside face of the hide under the towel shows the towel's back (v5.1 was see-
        # through from inside): every body-facing texel within 1.2 cm of an outward towel texel
        # takes that texel's colour, a little darker (the towel's underside, in shadow)
        out_t = m & ~inside
        fac = (fn * (pos - np.array([0.0, 1.2, -0.02]))).sum(-1) < 0
        cand = cov & fac & ~g["toggles"]
        # nearest outward towel texel within ~1.2 cm: shifted voxel grids (fast; v5.2 brute force took 29 min)
        P_out, C_out = pos[out_t], diffuse[out_t]
        Pc = pos[cand]
        take = np.zeros(len(Pc), bool)
        col_in = np.zeros((len(Pc), 3))
        cell = 0.012
        for off in [np.array(o) * cell / 2 for o in np.ndindex(2, 2, 2)]:
            ko = np.floor((P_out + off) / cell).astype(np.int64)
            kc = np.floor((Pc + off) / cell).astype(np.int64)
            enc = lambda k: (k[:, 0] + 10000) * 10 ** 10 + (k[:, 1] + 10000) * 10 ** 5 + (k[:, 2] + 10000)
            eo, ec = enc(ko), enc(kc)
            uniq, inv = np.unique(eo, return_inverse=True)
            sums = np.zeros((len(uniq), 3))
            np.add.at(sums, inv, C_out)
            cnt = np.bincount(inv, minlength=len(uniq))[:, None]
            idx = np.clip(np.searchsorted(uniq, ec), 0, len(uniq) - 1)
            hit = (uniq[idx] == ec) & ~take
            col_in[hit] = (sums[idx[hit]] / cnt[idx[hit]])
            take |= hit
        inner_m = np.zeros_like(m)
        inner_m[cand] = take
        diffuse[cand] = np.where(take[:, None], col_in * 0.8, diffuse[cand])
        m = m | inner_m
        inside = np.zeros_like(m)
        soft = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)), np.float64) / 255.0
        print("towel back texels (inside face)", int(inner_m.sum()))
    diffuse = np.where(inside[..., None], np.clip(diffuse * 1.6, 0, 1), diffuse)
    print("brightened inside texels", int(inside.sum()))
    # pad the colour outwards from the strip, so the soft alpha edge shows towel, not grey
    w = m.astype(np.float64)
    for r in (1.5, 4, 10):
        acc = np.stack([v.blur(diffuse[..., i] * w, r) for i in range(3)], -1)
        cnt = v.blur(w, r)[..., None]
        fill = acc / np.maximum(cnt, 1e-3)
        diffuse = np.where((w < 0.5)[..., None] & (cnt > 0.01), fill, diffuse)
        w = np.maximum(w, (cnt[..., 0] > 0.01).astype(np.float64))
    diffuse = np.where(w[..., None] > 0.5, diffuse, np.array([0.7, 0.66, 0.58]))
    alpha = np.clip((soft - 0.35) / 0.3, 0, 1) * 255
    if SHAPE == "drape":
        # holes: where the hide has a hole under the middle of the towel (not at its own edges or
        # folds), the towel gets a worn hole - darker frayed rim, loose threads across the gap
        uvp = load("uv")
        interior = (uvp[..., 1] > 0.07) & (uvp[..., 1] < 0.93) & (uvp[..., 0] > 0.03) & (uvp[..., 0] < 0.97)
        inner_m = filt(m, ImageFilter.MinFilter(9))
        band = m & ~inner_m
        uv_int = filt(interior & m, ImageFilter.MaxFilter(9))
        rim = band & uv_int
        rng2 = np.random.default_rng(11)
        streak = v.blur(rng2.random((SIZE, SIZE)), 0.8)
        fray = rim & (streak > 0.45)
        diffuse = np.where(rim[..., None], diffuse * 0.72, diffuse)
        diffuse = np.where(fray[..., None], diffuse * 0.8 + np.array([0.75, 0.71, 0.63]) * 0.2, diffuse)
        near_gap = filt(rim, ImageFilter.MaxFilter(7)) & ~m
        threads = near_gap & (v.blur(rng2.random((SIZE, SIZE)), 0.6) > 0.62)
        alpha = np.where(threads, 255, alpha)
        diffuse = np.where(threads[..., None], np.array([0.7, 0.66, 0.58]), diffuse)
        print("hole rim texels", int(rim.sum()), "threads", int(threads.sum()))
    hx, hy = v.grad_normal(pile, 2.2)
    nb = nrm * 2 - 1
    nb = np.stack([nb[..., 0] + hx, nb[..., 1] + hy, nb[..., 2]], -1)
    nb /= np.linalg.norm(nb, axis=-1, keepdims=True)
    normal = np.where(m[..., None], nb * 0.5 + 0.5, np.array([0.5, 0.5, 1.0]))
    spec = np.where(m, 0.04, 0.0)
    gloss = np.where(m, 0.08, 0.0)

    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    full = np.full((SIZE, SIZE), 255, np.uint8)
    OUT.mkdir(exist_ok=True)
    Image.fromarray(np.dstack([q(diffuse), alpha.round().astype(np.uint8)]), "RGBA").save(OUT / f"HidePoncho_{TAG}_diffuse.png")
    Image.fromarray(np.dstack([q(normal[..., 0]), q(normal[..., 1]), full, full]), "RGBA").save(OUT / f"HidePoncho_{TAG}_normal.png")
    Image.fromarray(np.dstack([q(spec), q(spec), q(spec), q(gloss)]), "RGBA").save(OUT / f"HidePoncho_{TAG}_specgloss.png")
    render_views(g["V"], g["T"], g["F"], g["N"], HERE / "uv" / f"{TAG}_views.png", tex=read_png(OUT / f"HidePoncho_{TAG}_diffuse.png"))
    print("done; towel texels", int(m.sum()))


if __name__ == "__main__":
    main()
