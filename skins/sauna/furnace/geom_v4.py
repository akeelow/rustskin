"""Sauna Boiler v4: геометрия модели Furnace для полей — только numpy (работает и в .venv, и в Python Blender'а).

OBJ: x вправо, y вверх, z вперёд (+Z — проём топки). Здесь всё в сантиметрах. Угол th = atan2(x − CX, z − CZ),
градусы, 0 — топка, +90 — +X. Острова UV нумеруются как в uv/islands_v4.md (по убыванию площади в атласе):
0 бак, 1 основание +X, 2 основание −X, 3 свод топки, 4 дно, 5 пол топки, 6 стенка топки, 7 ямка крышки, 8–10 угли.
"""
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OBJ = HERE / "originals" / "furnace.obj"
CX, CZ = 1.07, 4.93          # ось печи, см
TANK, BASE_R, BASE_L, VAULT, BOTTOM, FLOOR, WALL, HOLE = 0, 1, 2, 3, 4, 5, 6, 7


@lru_cache(None)
def load():
    """V (см), T, N, F (nf, 3 угла, (v, vt, vn))."""
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


def _union(pairs):
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    return find


@lru_cache(None)
def island_of_face():
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


def theta(P):
    return np.degrees(np.arctan2(P[..., 0] - CX, P[..., 2] - CZ))


def radius(P):
    return np.hypot(P[..., 0] - CX, P[..., 2] - CZ)


@lru_cache(None)
def opening_loop():
    """Кромка проёма топки: граничные рёбра острова 0 у топки -> упорядоченная ломаная (k, 3), см."""
    V, T, N, F = load()
    isl = island_of_face()
    cnt = defaultdict(int)
    for f in F[isl == TANK][:, :, 0]:
        for a, b in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
            cnt[(min(a, b), max(a, b))] += 1
    bnd = [e for e, c in cnt.items() if c == 1]
    fire = set(np.unique(F[np.isin(isl, (VAULT, FLOOR, WALL))][:, :, 0]).tolist())
    sel = [e for e in bnd if e[0] in fire and e[1] in fire]
    adj = defaultdict(list)
    for a, b in sel:
        adj[a].append(b)
        adj[b].append(a)
    ends = [v for v, n in adj.items() if len(n) == 1]
    start = ends[0] if ends else sel[0][0]
    path, prev = [start], None
    while True:
        nxt = [n for n in adj[path[-1]] if n != prev and n not in path]
        if not nxt:
            break
        prev = path[-1]
        path.append(nxt[0])
    return V[path]


@lru_cache(None)
def profile():
    """Радиус бака по высоте: (y, r_mean) с шагом 1 см по вершинам острова 0 (для развёртки рисунка)."""
    V, T, N, F = load()
    vs = np.unique(F[island_of_face() == TANK][:, :, 0])
    P = V[vs]
    ys = np.arange(50, 162, 1.0)
    r = np.array([np.median(radius(P[np.abs(P[:, 1] - y) < 4])) if (np.abs(P[:, 1] - y) < 4).sum() else np.nan for y in ys])
    ok = np.isfinite(r)
    r = np.interp(ys, ys[ok], r[ok])
    return ys, r


def seg_dist(P, L):
    """Расстояние от точек P (n, 3) до ломаной L (k, 3) и параметр вдоль неё (см) — по кускам, без огромных массивов."""
    best = np.full(len(P), 1e9)
    along = np.zeros(len(P))
    s0 = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(L, axis=0), axis=1))])
    for i in range(len(L) - 1):
        a, b = L[i], L[i + 1]
        ab = b - a
        t = np.clip(((P - a) @ ab) / max(ab @ ab, 1e-9), 0, 1)
        d = np.linalg.norm(P - (a + t[:, None] * ab), axis=1)
        m = d < best
        best = np.where(m, d, best)
        along = np.where(m, s0[i] + t * np.linalg.norm(ab), along)
    return best, along


OPEN_TH, OPEN_HW, OPEN_SPRING, OPEN_TOP = 1.0, 36.0, 67.0, 87.0   # проём: центр и полуширина (град.), пята и верх арки (см)


@lru_cache(None)
def outline():
    """Наружный контур проёма топки в (th, y): стойки до пяты арки, полуэллипс до верха; внизу замкнут по y = 56
    (низ проёма; ниже — порог).
    Подобран по верхним вершинам откосов (r > 30 см): стойки th −35…+37, верх y 86.8. -> (k, 2) [град., см]."""
    a = np.linspace(np.pi, 0, 61)
    th = OPEN_TH + OPEN_HW * np.cos(a)
    y = OPEN_SPRING + (OPEN_TOP - OPEN_SPRING) * np.sin(a)
    pts = [(OPEN_TH - OPEN_HW, 56.0)] + list(zip(th, y)) + [(OPEN_TH + OPEN_HW, 56.0)]
    return np.array(pts)
