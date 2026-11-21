"""Sauna Stove v3: геометрия модели для полей высот — только numpy (работает и в .venv, и в Python Blender'а).

OBJ: x вправо (+X — правый бок), y вверх, z вперёд (+Z — дверца). Здесь всё в сантиметрах.
Острова UV нумеруются как в uv/islands_v3.md (по убыванию площади в атласе).
"""
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OBJ = HERE / "originals" / "electric.furnace.obj"


@lru_cache(None)
def load():
    """V (см), T, N, F (nf, 3 угла, (v, vt, vn)) — все грани OBJ — треугольники (21399)."""
    V, T, N, F = [], [], [], []
    for line in open(OBJ, encoding="utf8"):
        if line.startswith("v "):
            V.append([float(c) for c in line.split()[1:4]])
        elif line.startswith("vt "):
            T.append([float(c) for c in line.split()[1:3]])
        elif line.startswith("vn "):
            N.append([float(c) for c in line.split()[1:4]])
        elif line.startswith("f "):
            idx = [[int(x) - 1 for x in p.split("/")] for p in line.split()[1:]]
            for k in range(1, len(idx) - 1):
                F.append((idx[0], idx[k], idx[k + 1]))
    return np.array(V) * 100.0, np.array(T), np.array(N), np.array(F)


def _union(pairs_iter, n_hint=None):
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b in pairs_iter:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    return find


@lru_cache(None)
def island_of_face():
    """Номер острова UV для каждой грани (как в uv/islands_v3.md)."""
    V, T, N, F = load()
    ft = F[:, :, 1]
    find = _union((int(f[0]), int(a)) for f in ft for a in f[1:])
    g = defaultdict(list)
    for fi, f in enumerate(ft):
        g[find(int(f[0]))].append(fi)
    UV = T[ft]
    uvw = UV - np.floor(UV.min(1, keepdims=True))
    d1, d2 = uvw[:, 1] - uvw[:, 0], uvw[:, 2] - uvw[:, 0]
    a2 = np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / 2
    isl = sorted(g.values(), key=lambda fs: -a2[fs].sum())
    out = np.zeros(len(F), np.int32)
    for i, fs in enumerate(isl):
        out[fs] = i
    return out


@lru_cache(None)
def piece_of_face():
    """Номер связного куска (сварка по положению 0.1 мм) — как в uv/parts_v3.md."""
    V, T, N, F = load()
    fv = F[:, :, 0]
    key = {}
    pairs = []
    for i, p in enumerate(np.round(V / 100.0, 4)):
        k = tuple(p)
        if k in key:
            pairs.append((i, key[k]))
        else:
            key[k] = i
    pairs += [(int(f[0]), int(a)) for f in fv for a in f[1:]]
    find = _union(pairs)
    g = defaultdict(list)
    for fi, f in enumerate(fv):
        g[find(int(f[0]))].append(fi)
    pcs = sorted(g.values(), key=lambda fs: -len(fs))
    out = np.zeros(len(F), np.int32)
    for i, fs in enumerate(pcs):
        out[fs] = i
    return out


def tris(islands=None, pieces=None):
    """Треугольники (n, 3, 3) см выбранных островов/кусков."""
    V, T, N, F = load()
    m = np.ones(len(F), bool)
    if islands is not None:
        m &= np.isin(island_of_face(), list(islands))
    if pieces is not None:
        m &= np.isin(piece_of_face(), list(pieces))
    return V[F[m][:, :, 0]]


def copy_transform(piece_a, piece_b):
    """B ≈ R·A + t для двух кусков на общих UV (наименьшие квадраты по вершинам с одинаковыми UV, с отражением)."""
    V, T, N, F = load()
    pc = piece_of_face()
    d = []
    for p in (piece_a, piece_b):
        m = {}
        for f in F[pc == p]:
            for c in f:
                m[tuple(np.round(T[c[1]], 5))] = V[c[0]]
        d.append(m)
    ks = [k for k in d[0] if k in d[1]]
    A = np.array([d[0][k] for k in ks])
    B = np.array([d[1][k] for k in ks])
    ca, cb = A.mean(0), B.mean(0)
    U, S, Vt = np.linalg.svd((A - ca).T @ (B - cb))
    R = Vt.T @ U.T
    return R, cb - R @ ca


def raster_height(T3, U, Vg, ax_u, ax_v, ax_w, sign=1.0, fill=np.nan, ids=None):
    """Поле «высоты» по сетке U, Vg (2D, регулярная): для каждой точки — координата ax_w (×sign) треугольников T3,
    взятая по максимуму (наружная поверхность). Точки вне треугольников — fill. ids (n,) — метки треугольников:
    тогда возвращает (H, ID) — метка треугольника, давшего максимум (−1 вне)."""
    us, vs = U[0, :], Vg[:, 0]
    du, dv = us[1] - us[0], vs[1] - vs[0]
    H = np.full(U.shape, -np.inf)
    ID = np.full(U.shape, -1, np.int32)
    for ti, t in enumerate(T3):
        pu, pv, pw = t[:, ax_u], t[:, ax_v], t[:, ax_w] * sign
        i0 = max(int(np.floor((pu.min() - us[0]) / du)), 0)
        i1 = min(int(np.ceil((pu.max() - us[0]) / du)), len(us) - 1)
        j0 = max(int(np.floor((pv.min() - vs[0]) / dv)), 0)
        j1 = min(int(np.ceil((pv.max() - vs[0]) / dv)), len(vs) - 1)
        if i1 < i0 or j1 < j0:
            continue
        uu, vv = np.meshgrid(us[i0:i1 + 1], vs[j0:j1 + 1])
        det = (pv[1] - pv[2]) * (pu[0] - pu[2]) + (pu[2] - pu[1]) * (pv[0] - pv[2])
        if abs(det) < 1e-12:
            continue
        l0 = ((pv[1] - pv[2]) * (uu - pu[2]) + (pu[2] - pu[1]) * (vv - pv[2])) / det
        l1 = ((pv[2] - pv[0]) * (uu - pu[2]) + (pu[0] - pu[2]) * (vv - pv[2])) / det
        l2 = 1 - l0 - l1
        e = -1e-6
        ins = (l0 >= e) & (l1 >= e) & (l2 >= e)
        w = l0 * pw[0] + l1 * pw[1] + l2 * pw[2]
        sub = H[j0:j1 + 1, i0:i1 + 1]
        win = ins & (w > sub)
        H[j0:j1 + 1, i0:i1 + 1] = np.where(win, w, sub)
        if ids is not None:
            sid = ID[j0:j1 + 1, i0:i1 + 1]
            ID[j0:j1 + 1, i0:i1 + 1] = np.where(win, ids[ti], sid)
    H[~np.isfinite(H)] = fill
    return (H, ID) if ids is not None else H


def tris_ids(islands=None, pieces=None):
    """Треугольники (n, 3, 3) и номера их островов."""
    V, T, N, F = load()
    m = np.ones(len(F), bool)
    if islands is not None:
        m &= np.isin(island_of_face(), list(islands))
    if pieces is not None:
        m &= np.isin(piece_of_face(), list(pieces))
    return V[F[m][:, :, 0]], island_of_face()[m]
