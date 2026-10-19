"""Sauna Changing Locker v3: open locker filled with modelled sauna props, warm glow.

v2 in game (screenshots/v2_*): the alpha-cut doors work (no holes, the inside shows), but it was
boring - flat painted props - and nothing glowed: this item's Emission Color slider starts at
0/0/0 and has to be set to 255/255/255. v3 keeps v2's open doors and shelf lamp and replaces the
painted props with ones modelled and rendered head-on in Blender (props_v3.py -> bake/props_*):
a wooden bucket with a ladle, a candle lantern and a felt hat up top; a striped towel and a birch
whisk in the middle; birch logs, amber oil bottles and soap below. Each back-wall texel (shared by
all three compartments) takes the render's colour, shading and normal at its local position;
the lantern glows.

    "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/locker/props_v3.py
    .venv/Scripts/python skins/sauna/locker/texture_v3.py
Writes export/Locker_v3_{diffuse,normal,specgloss,emission}.png and uv/v3_views.png.
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
BAKE = HERE / "bake"
X0, X1, Y0, Y1 = -28.0, 28.0, 15.0, 217.0     # must match props_v3.py
OUT, SIZE = v1.OUT, v1.SIZE


def sample(img, px, py):
    """Bilinear lookup of img (H, W, C) at float pixel coords."""
    H, W = img.shape[:2]
    px = np.clip(px - 0.5, 0, W - 1.001)
    py = np.clip(py - 0.5, 0, H - 1.001)
    x0, y0 = np.floor(px).astype(int), np.floor(py).astype(int)
    fx, fy = (px - x0)[..., None], (py - y0)[..., None]
    a, b = img[y0, x0], img[y0, x0 + 1]
    c, d = img[y0 + 1, x0], img[y0 + 1, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def main():
    m = v1.build()
    pos, nrm, cov = m["pos"], m["nrm"], m["cov"]
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    col, spec, gloss = m["col"].copy(), m["spec"].copy(), m["gloss"].copy()
    alpha, body, back_in, cut = v2.open_doors(m)

    rd = lambda k: np.asarray(Image.open(BAKE / f"props_{k}.png").convert("RGBA"), np.float64) / 255.0
    albedo, nmap, shade, emit_r = rd("albedo"), rd("normal"), rd("shade"), rd("emit")
    H, W = albedo.shape[:2]

    cxs = np.array(v2.COMPARTMENTS)
    xl = x - cxs[np.argmin(np.abs(x[..., None] - cxs), -1)]
    px = (xl - X0) / (X1 - X0) * W
    py = (Y1 - y) / (Y1 - Y0) * H
    sel = back_in & (xl > X0) & (xl < X1) & (y > Y0) & (y < Y1)

    a = np.zeros(cov.shape + (4,))
    a[sel] = sample(albedo, px[sel], py[sel])
    cov_p = a[..., 3]
    s = np.zeros(cov.shape + (4,))
    s[sel] = sample(shade, px[sel], py[sel])
    lum = s[..., :3].mean(-1)
    wall_ref = np.median(lum[sel & (cov_p < 0.01)])
    light = np.clip(lum / max(wall_ref, 1e-3), 0.0, 1.4)

    # back wall: props' cast shadows; props: their colour with soft modelled shading
    col = np.where(sel[..., None], col * np.clip(light, 0.45, 1.0)[..., None], col)
    pc = a[..., :3] * (0.62 + 0.38 * np.clip(light, 0, 1.3))[..., None]
    col = col * (1 - cov_p[..., None]) + pc * cov_p[..., None]

    # normal: world normal of the render -> tangent space of the back-wall patch
    nw = np.zeros(cov.shape + (4,))
    nw[sel] = sample(nmap, px[sel], py[sel])
    n_world = nw[..., :3] * 2 - 1
    n_obj = np.stack([n_world[..., 0], n_world[..., 2], -n_world[..., 1]], -1)   # Blender -> OBJ axes
    dcol = np.roll(pos, -1, 1) - pos
    drow = np.roll(pos, -1, 0) - pos
    ok = sel & np.roll(sel, -1, 1) & np.roll(sel, -1, 0)
    tu = np.median(dcol[ok], 0)
    tv = -np.median(drow[ok], 0)                               # v runs up the image
    tu, tv = tu / np.linalg.norm(tu), tv / np.linalg.norm(tv)
    nt = np.stack([n_obj @ tu, n_obj @ tv, n_obj[..., 2]], -1)
    nt /= np.maximum(np.linalg.norm(nt, axis=-1, keepdims=True), 1e-6)
    nb = m["nb"].copy()
    w = (cov_p > 0.5)[..., None]
    nb = np.where(w, nt, nb)

    spec = np.where(cov_p > 0.5, 0.05, spec)
    gloss = np.where(cov_p > 0.5, 0.12, gloss)

    # glow: v2's shelf lamp + the candle lantern
    emit, col, strip, fall = v2.lamp(m, body, back_in, col)
    e = np.zeros(cov.shape + (4,))
    e[sel] = sample(emit_r, px[sel], py[sel])
    glow = e[..., :3] * e[..., 3:4] * 3.0
    emit = emit + glow
    spec = np.where(glow.max(-1) > 0.05, 0.4, spec)
    gloss = np.where(glow.max(-1) > 0.05, 0.6, gloss)

    out = dict(m, col=col, nb=nb, spec=spec, gloss=gloss, alpha=alpha)
    v1.save(out, "v3")
    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    em = Image.fromarray(q(emit)).resize((1024, 1024), Image.BOX)
    Image.fromarray(np.dstack([np.asarray(em), np.full((1024, 1024), 255, np.uint8)]), "RGBA").save(OUT / "Locker_v3_emission.png")
    print("done; back-wall texels", int(sel.sum()), "prop texels", int((cov_p > 0.5).sum()), "tangent u", tu.round(2), "v", tv.round(2))


if __name__ == "__main__":
    main()
