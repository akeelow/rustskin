"""Colour blocking v0 for Sauna Towel Wrap (Burlap Headwrap).

The burlap hood + neck cowl becomes a washed-out terry towel wound round the head: off-white
linen with faded brick stripes along the cowl's frayed hem, the binding ropes kept as light flax
twine (set rule: rope instead of fasteners), a few damp patches. Folds and weave come from the
original diffuse (its luminance, contrast reduced), the original alpha (frayed edges, Alpha
Cutoff 0.79) is kept as is.

    .venv/Scripts/python skins/sauna/burlap-headwrap/blocking.py
Writes export/BurlapHeadwrap_blocking_v0_diffuse.png (DIFFUSE slot) and uv/blocking_v0_views.png.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
from uv_zones import load_obj, normal, read_png, render_views  # noqa: E402

ORIG = HERE / "originals"
OUT = HERE / "export"
SIZE = 1024
SEED = 11


def hexc(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float64) / 255.0


TOWEL = hexc("#CFC6B4")     # washed-out linen / terry (set palette)
STRIPE = hexc("#8E3A30")    # faded brick stripe (set palette)
TWINE = hexc("#B8A27A")     # flax twine, a shade darker than the towel so it still reads


def blur(a, r):
    """Gaussian blur of a 0..1 array (via 8-bit; plenty for masks and local means)."""
    f = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
    return np.asarray(f, np.float64) / 255.0


def islands(V, T, F):
    """Per-texel island id (0 = empty, 1 = cowl, 2 = hood) by flood-filling faces that share UVs."""
    parent = list(range(len(F)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    by_uv = {}
    for f, (_, ti) in enumerate(F):
        for t in ti:
            by_uv.setdefault(t, []).append(f)
    for fs in by_uv.values():
        for f in fs[1:]:
            parent[find(f)] = find(fs[0])
    groups = {}
    for f in range(len(F)):
        groups.setdefault(find(f), []).append(f)
    # the two big islands: the higher one on the texture (smaller image y) is the cowl strip
    big = sorted(groups.values(), key=len, reverse=True)[:2]
    mean_y = [np.mean([1 - T[t][1] for f in g for t in F[f][1]]) for g in big]
    order = np.argsort(mean_y)
    ids = Image.new("L", (SIZE, SIZE), 0)
    draw = ImageDraw.Draw(ids)
    for label, gi in ((1, order[0]), (2, order[1])):
        for f in big[gi]:
            pts = [(T[t][0] * SIZE, (1 - T[t][1]) * SIZE) for t in F[f][1]]
            draw.polygon(pts, fill=label)
    return np.asarray(ids)


def main():
    V, T, F = load_obj(ORIG / "burlap.headwrap.obj")
    N = [normal(*(V[i] for i in vi)) for vi, _ in F]
    isl = islands(V, T, F)
    cowl, hood = isl == 1, isl == 2

    bc = np.asarray(Image.open(ORIG / "burlapheadwraps_01_bc.png").convert("RGBA"), np.float64) / 255.0
    alpha = (bc[..., 3] * 255).round().astype(np.uint8)
    lum = bc[..., :3] @ np.array([0.299, 0.587, 0.114])
    ao = np.asarray(Image.open(ORIG / "burlapheadwraps_01_ao.png").convert("L").resize((SIZE, SIZE), Image.BILINEAR), np.float64) / 255.0

    # folds and weave from the original, at reduced contrast (no baked light in the diffuse)
    detail = np.clip(lum / np.maximum(blur(lum, 14), 1e-3), 0.55, 1.5)
    detail = 1 + 0.55 * (detail - 1)
    rng = np.random.default_rng(SEED)
    terry = np.asarray(Image.fromarray((rng.random((SIZE, SIZE)) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7)), np.float64) / 255.0
    damp = blur(rng.random((SIZE, SIZE)), 40)
    damp = np.clip((damp - 0.52) * 12, 0, 1)

    col = TOWEL[None, None, :] * detail[..., None] * (0.86 + 0.14 * ao[..., None])
    col = col * (0.95 + 0.1 * terry[..., None])

    # ropes on the hood: much darker than their surroundings in the original
    rope = hood & (lum < blur(lum, 8) * 0.8)
    rope = (blur(rope.astype(np.float64), 1.6) > 0.2) & hood    # take in the rope's grey edges too
    twine = TWINE[None, None, :] * detail[..., None] * (0.9 + 0.2 * terry[..., None])
    col[rope] = twine[rope]

    # faded stripes along the towel's hems: the cowl's frayed lower edge and the hood's lower edge
    ys = np.arange(SIZE)[:, None]
    fade = 0.55 + 0.25 * blur(rng.random((SIZE, SIZE)), 6)
    sc = STRIPE[None, None, :] * detail[..., None]
    stripes = np.zeros((SIZE, SIZE), bool)
    for part, offs in ((cowl, ((46, 6), (64, 3))), (hood, ((34, 5), (50, 3)))):
        solid = part & (alpha > 200)
        has = solid.any(0)
        hem = np.where(has, SIZE - 1 - np.argmax(solid[::-1], 0), np.nan)
        xs = np.arange(SIZE)
        hem = np.interp(xs, xs[has], hem[has])        # bridge empty columns with the nearest hem
        k = 51                                        # smooth the frayed edge into a hem line
        hem = np.convolve(np.pad(hem, k // 2, mode="edge"), np.ones(k) / k, mode="valid")
        d = hem[None, :] - ys + 3 * np.sin(xs / 37.0)[None, :]
        for off, w in offs:
            stripes |= (np.abs(d - off) < w) & part & has[None, :]
    col[stripes] = (col * (1 - fade[..., None]) + sc * fade[..., None])[stripes]

    col = col * (1 - 0.12 * damp[..., None] * (cowl | hood)[..., None])
    fabric = cowl | hood
    col[~fabric] = TOWEL * 0.9                      # padding colour for mips, nothing shows there

    OUT.mkdir(exist_ok=True)
    rgba = np.dstack([(np.clip(col, 0, 1) * 255).round().astype(np.uint8), alpha])
    out = OUT / "BurlapHeadwrap_blocking_v0_diffuse.png"
    Image.fromarray(rgba, "RGBA").save(out)
    render_views(V, T, F, N, HERE / "uv" / "blocking_v0_views.png", tex=read_png(out))
    print("done:", out, "rope texels", int(rope.sum()), "stripe texels", int(stripes.sum()))


if __name__ == "__main__":
    main()
