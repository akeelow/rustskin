"""Подготовка к запеканию Sauna Mitts (.venv): одна перчатка (+x), острова, карта «тексель → 3D».

python skins/sauna/tactical-gloves/prep_gloves.py
Выход:
  source/glove_r.npz   V (вершины +x), T (UV), F/FT (грани, тройки), isl (остров грани 1…7)
  source/pos_cache.npz pos (R,R,3) 3D-точка на каждый тексель (NaN — пусто), nrm, isl (R,R) — R = 1024
  uv/ids_2048.png      R = номер острова (служебная, для групп запекания)
Острова пронумерованы как в uv/model.md (по убыванию числа граней).
"""
import os
from collections import defaultdict
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))


def load():
    V, T, N, F, FT, FN = [], [], [], [], [], []
    for line in open(os.path.join(HERE, "originals", "tactical.gloves.obj")):
        p = line.split()
        if not p: continue
        if p[0] == "v": V.append([float(x) for x in p[1:4]])
        elif p[0] == "vt": T.append([float(x) for x in p[1:3]])
        elif p[0] == "vn": N.append([float(x) for x in p[1:4]])
        elif p[0] == "f":
            c = [q.split("/") for q in p[1:]]
            for j in range(1, len(c) - 1):  # в треугольники
                tri = (c[0], c[j], c[j + 1])
                F.append([int(a[0]) - 1 for a in tri]); FT.append([int(a[1]) - 1 for a in tri])
                FN.append([int(a[2]) - 1 for a in tri])
    return np.array(V), np.array(T), np.array(N), np.array(F), np.array(FT), np.array(FN)


def islands(FT, nT):
    par = list(range(nT))
    def f(a):
        while par[a] != a:
            par[a] = par[par[a]]; a = par[a]
        return a
    for t in FT:
        for a in t[1:]: par[f(a)] = f(t[0])
    roots = [f(t[0]) for t in FT]
    cnt = defaultdict(int)
    for r in roots: cnt[r] += 1
    order = {r: i + 1 for i, (r, _) in enumerate(sorted(cnt.items(), key=lambda x: -x[1]))}
    return np.array([order[r] for r in roots])


def raster(T, FT, vals, R):
    """Барицентрическая растеризация: vals (nF,3,k) -> (R,R,k), NaN вне островов. Строки сверху вниз (v=1 сверху)."""
    out = np.full((R, R, vals.shape[2]), np.nan, np.float32)
    for fi, ft in enumerate(FT):
        p = np.array([[T[t][0] * R, (1 - T[t][1]) * R] for t in ft])
        x0, y0 = np.maximum(np.floor(p.min(0)).astype(int), 0)
        x1, y1 = np.minimum(np.ceil(p.max(0)).astype(int), R - 1)
        if x1 < x0 or y1 < y0: continue
        ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        P = np.stack([xs + 0.5, ys + 0.5], -1)
        a, b, c = p
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12: continue
        w0 = ((b[1] - c[1]) * (P[..., 0] - c[0]) + (c[0] - b[0]) * (P[..., 1] - c[1])) / den
        w1 = ((c[1] - a[1]) * (P[..., 0] - c[0]) + (a[0] - c[0]) * (P[..., 1] - c[1])) / den
        w2 = 1 - w0 - w1
        m = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
        v = vals[fi]
        out[ys[m], xs[m]] = w0[m, None] * v[0] + w1[m, None] * v[1] + w2[m, None] * v[2]
    return out


def main():
    V, T, N, F, FT, FN = load()
    isl = islands(FT, len(T))
    keep = V[F].mean(1)[:, 0] > 0
    F, FT, FN, isl = F[keep], FT[keep], FN[keep], isl[keep]
    np.savez(os.path.join(HERE, "source", "glove_r.npz"), V=V, T=T, N=N, F=F, FT=FT, FN=FN, isl=isl)
    R = 1024
    # плотность грани: px атласа 1024 на мм
    P = V[F] * 1000.0
    a3 = np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1) / 2
    Q = T[FT] * R
    e1, e2 = Q[:, 1] - Q[:, 0], Q[:, 2] - Q[:, 0]
    a2 = np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) / 2
    dens = np.sqrt(a2 / np.maximum(a3, 1e-12))
    vals = np.concatenate([V[F], N[FN], np.repeat(isl[:, None, None], 3, 1).astype(float),
                           np.repeat(dens[:, None, None], 3, 1)], 2)
    r = raster(T, FT, vals, R)
    dm = r[..., 7].copy()
    for _ in range(24):   # плотность — наружу от островов, чтобы точки на самом шве не попадали в пустоту
        nanm = np.isnan(dm)
        if not nanm.any(): break
        acc = np.zeros_like(dm); cnt = np.zeros_like(dm)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sh = np.roll(dm, (dy, dx), (0, 1)); ok = ~np.isnan(sh)
            acc[ok] += sh[ok]; cnt[ok] += 1
        fill = nanm & (cnt > 0)
        dm[fill] = acc[fill] / cnt[fill]
    np.savez_compressed(os.path.join(HERE, "source", "pos_cache.npz"), pos=r[..., :3], nrm=r[..., 3:6],
                        isl=np.nan_to_num(r[..., 6]).round().astype(np.int16), dens=dm.astype(np.float32))
    for k in range(1, 8):
        print("island", k, "px/mm @1024: median %.2f" % np.median(dens[isl == k]))
    r2 = raster(T, FT, np.repeat(isl[:, None, None], 3, 1).astype(float), 2048)
    ids = np.nan_to_num(r2[..., 0]).round().astype(np.uint8)
    Image.fromarray(ids, "L").save(os.path.join(HERE, "uv", "ids_2048.png"))
    print("faces", len(F), "islands", np.bincount(isl))


if __name__ == "__main__":
    main()
