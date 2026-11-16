"""Wooden Door: UV islands, what part of the door each one is, texel density, overlaps.

  .venv/Scripts/python skins/sauna/wooden-door/uv/analyze_uv.py

Writes uv/islands.png (islands numbered, overlapping texels in red) and prints a table.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
OBJ = HERE.parent / "originals" / "door.hinged.wood.obj"
N = 2048


def load(path=OBJ):
    v, vt, tris = [], [], []
    for line in open(path):
        p = line.split()
        if not p:
            continue
        if p[0] == "v":
            v.append([float(x) for x in p[1:4]])
        elif p[0] == "vt":
            vt.append([float(x) for x in p[1:3]])
        elif p[0] == "f":
            idx = [tuple(int(a) if a else 0 for a in s.split("/")) for s in p[1:]]
            for k in range(1, len(idx) - 1):
                tris.append((idx[0], idx[k], idx[k + 1]))
    v, vt = np.array(v), np.array(vt)
    P = np.array([[v[c[0] - 1] for c in t] for t in tris])
    T = np.array([[vt[c[1] - 1] for c in t] for t in tris])
    VI = np.array([[c[1] - 1 for c in t] for t in tris])
    return P, T, VI


def islands(VI):
    parent = list(range(VI.max() + 1))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for t in VI:
        a, b, c = (find(int(x)) for x in t)
        parent[b] = a
        parent[c] = a
    roots = np.array([find(int(t[0])) for t in VI])
    _, ids = np.unique(roots, return_inverse=True)
    return ids


def raster(T, ids):
    """Per-texel island id (-1 empty) and how many triangles cover each texel."""
    owner = np.full((N, N), -1, np.int32)
    count = np.zeros((N, N), np.int32)
    for t, isl in zip(T, ids):
        p = t * N
        x0, x1 = int(np.floor(p[:, 0].min())), int(np.ceil(p[:, 0].max()))
        y0, y1 = int(np.floor(p[:, 1].min())), int(np.ceil(p[:, 1].max()))
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        d = (p[1, 1] - p[2, 1]) * (p[0, 0] - p[2, 0]) + (p[2, 0] - p[1, 0]) * (p[0, 1] - p[2, 1])
        if abs(d) < 1e-9:
            continue
        a = ((p[1, 1] - p[2, 1]) * (xs - p[2, 0]) + (p[2, 0] - p[1, 0]) * (ys - p[2, 1])) / d
        b = ((p[2, 1] - p[0, 1]) * (xs - p[2, 0]) + (p[0, 0] - p[2, 0]) * (ys - p[2, 1])) / d
        m = (a >= 0) & (b >= 0) & (a + b <= 1)
        yy, xx = (ys[m] - 0.5).astype(int), (xs[m] - 0.5).astype(int)
        ok = (yy >= 0) & (yy < N) & (xx >= 0) & (xx < N)
        yy, xx = yy[ok], xx[ok]
        count[yy, xx] += 1
        owner[yy, xx] = isl
    return owner, count


def main():
    P, T, VI = load()
    ids = islands(VI)
    owner, count = raster(T, ids)
    nrm = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    area3 = np.linalg.norm(nrm, axis=1) / 2
    e1, e2 = T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
    signed = (e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) / 2
    print("isl tris  u0    u1    v0    v1   | x0    x1    y0    y1    z0    z1   | normal        px/m  flip overlap%")
    rng = np.random.default_rng(3)
    img = np.zeros((N, N, 3), np.uint8)
    labels = []
    for i in range(ids.max() + 1):
        m = ids == i
        t, p = T[m].reshape(-1, 2), P[m].reshape(-1, 3)
        n = (nrm[m]).sum(0)
        n = n / (np.linalg.norm(n) + 1e-12)
        dens = np.sqrt(abs(signed[m]).sum() / max(area3[m].sum(), 1e-12)) * N
        tex = owner == i
        ov = (count[tex] > 1).mean() * 100 if tex.any() else 0
        flip = "mirr" if signed[m].sum() < 0 else ""
        print(f"{i:3d} {m.sum():4d} {t[:,0].min():.3f} {t[:,0].max():.3f} {t[:,1].min():.3f} {t[:,1].max():.3f} | "
              f"{p[:,0].min():5.2f} {p[:,0].max():5.2f} {p[:,1].min():5.2f} {p[:,1].max():5.2f} {p[:,2].min():5.2f} {p[:,2].max():5.2f} | "
              f"{n[0]:+.1f} {n[1]:+.1f} {n[2]:+.1f} {dens:6.0f} {flip:4s} {ov:5.1f}")
        img[tex] = rng.integers(60, 230, 3)
        labels.append((t[:, 0].mean() * N, (1 - t[:, 1].mean()) * N, str(i)))
    img[count > 1] = (255, 0, 0)
    out = Image.fromarray(img[::-1].copy())
    d = ImageDraw.Draw(out)
    for x, y, s in labels:
        d.text((x, y), s, fill=(255, 255, 255))
    out.save(HERE / "islands.png")
    print("overlapping texels:", int((count > 1).sum()), "of", int((count > 0).sum()))


if __name__ == "__main__":
    main()
