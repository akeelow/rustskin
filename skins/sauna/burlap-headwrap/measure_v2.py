"""Замеры модели Burlap Headwrap для плана v2.

Запуск (.venv):  python skins/sauna/burlap-headwrap/measure_v2.py
Вход:  originals/burlap.headwrap.obj, originals/burlapheadwraps_01_{bc,nrm,ao}.png, uv/faces.json (islands.py)
Выход: uv/measure_v2.md — плотность по граням (распределение), куски геометрии каждого острова (наружный /
       внутренний слой), как связаны копии на общих UV (наименьшие квадраты), отклонение нормалей OBJ от граней,
       доля альфы ≥ Alpha Cutoff по островам, толщина между слоями.
"""
import json
import math
import os
from collections import defaultdict

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OBJ = os.path.join(HERE, "originals", "burlap.headwrap.obj")
BC = os.path.join(HERE, "originals", "burlapheadwraps_01_bc.png")
CUT = 0.785


def load():
    V, T, N, F = [], [], [], []
    for line in open(OBJ):
        p = line.split()
        if not p:
            continue
        if p[0] == "v":
            V.append([float(x) for x in p[1:4]])
        elif p[0] == "vt":
            T.append([float(x) for x in p[1:3]])
        elif p[0] == "vn":
            N.append([float(x) for x in p[1:4]])
        elif p[0] == "f":
            F.append([[int(i) - 1 for i in q.split("/")] for q in p[1:]])
    return np.array(V), np.array(T), np.array(N), np.array(F)


def comps(fs, F):
    par = {}

    def fd(a):
        while par.setdefault(a, a) != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    for fi in fs:
        for c in F[fi][1:]:
            ra, rb = fd(F[fi][0][0]), fd(c[0])
            if ra != rb:
                par[ra] = rb
    g = defaultdict(list)
    for fi in fs:
        g[fd(F[fi][0][0])].append(fi)
    return sorted(g.values(), key=len, reverse=True)


def main():
    V, T, N, F = load()
    per = json.load(open(os.path.join(HERE, "uv", "faces.json")))
    bc = np.asarray(Image.open(BC).convert("RGBA")).astype(float) / 255
    res = bc.shape[0]
    out = ["# Замеры модели Burlap Headwrap (measure_v2.py)", ""]
    # центр головы — по наружному слою
    c0 = V.mean(0)
    for isl in sorted(set(per)):
        fs = [i for i, k in enumerate(per) if k == isl]
        name = {1: "капюшон", 2: "воротник"}.get(isl, str(isl))
        out += [f"## Остров {isl} ({name}): {len(fs)} треугольников", ""]
        cs = comps(fs, F)
        rows = []
        for ci, cf in enumerate(cs):
            P = V[F[cf][:, :, 0]]
            n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
            A = 0.5 * np.linalg.norm(n, axis=1)
            nn = n / (np.linalg.norm(n, axis=1, keepdims=True) + 1e-12)
            cen = P.mean(1)
            r = cen - c0
            r /= np.linalg.norm(r, axis=1, keepdims=True)
            outward = float((A * (nn * r).sum(1)).sum() / A.sum())
            t = T[F[cf][:, :, 1]]
            a2 = 0.5 * np.abs((t[:, 1, 0] - t[:, 0, 0]) * (t[:, 2, 1] - t[:, 0, 1])
                              - (t[:, 2, 0] - t[:, 0, 0]) * (t[:, 1, 1] - t[:, 0, 1]))
            d = np.sqrt(a2 / np.maximum(A, 1e-12)) * res / 100  # px/см при 1024
            w = A / A.sum()
            q = lambda pct: float(np.interp(pct, np.cumsum(w[np.argsort(d)]), np.sort(d)))
            # отклонение нормалей OBJ от нормали грани
            vn = N[F[cf][:, :, 2]]
            vn /= np.linalg.norm(vn, axis=2, keepdims=True)
            ang = np.degrees(np.arccos(np.clip((vn * nn[:, None]).sum(2), -1, 1)))
            # альфа под гранями (по центру грани)
            uc = t.mean(1)
            px = np.clip((uc[:, 0] * res).astype(int), 0, res - 1)
            py = np.clip(((1 - uc[:, 1]) * res).astype(int), 0, res - 1)
            alpha_ok = float((w * (bc[py, px, 3] >= CUT)).sum())
            rows.append((ci, len(cf), A.sum() * 1e4, outward, q(0.1), q(0.5), q(0.9), np.median(ang),
                         np.percentile(ang, 90), alpha_ok, P.reshape(-1, 3).min(0), P.reshape(-1, 3).max(0)))
        out += ["| кусок | граней | площадь см² | наружу | px/см 10 % | медиана | 90 % | угол vn↔грань, медиана | 90 % | "
                "непрозрачно (α ≥ 0.785) | y |", "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
        for r in rows:
            out.append(f"| {r[0]} | {r[1]} | {r[2]:.0f} | {r[3]:+.2f} | {r[4]:.1f} | {r[5]:.1f} | {r[6]:.1f} | "
                       f"{r[7]:.1f}° | {r[8]:.1f}° | {r[9] * 100:.0f} % | {r[10][1]:+.3f}…{r[11][1]:+.3f} |")
        # связь копий: пары вершин с одинаковым vt в разных кусках
        if len(cs) >= 2:
            vt2v = [defaultdict(set), defaultdict(set)]
            for k in (0, 1):
                for fi in cs[k]:
                    for c in F[fi]:
                        vt2v[k][c[1]].add(c[0])
            A_, B_ = [], []
            for vt, s0 in vt2v[0].items():
                s1 = vt2v[1].get(vt)
                if s1:
                    A_.append(V[sorted(s0)[0]])
                    B_.append(V[sorted(s1)[0]])
            A_, B_ = np.array(A_), np.array(B_)
            dist = np.linalg.norm(A_ - B_, axis=1) * 1000
            # наименьшие квадраты: B ≈ R A + t
            ca, cb = A_.mean(0), B_.mean(0)
            U, S, Wt = np.linalg.svd((A_ - ca).T @ (B_ - cb))
            R = (U @ Wt).T
            det = np.linalg.det(R)
            resid = np.linalg.norm((A_ - ca) @ R.T + cb - B_, axis=1) * 1000
            rot = math.degrees(math.acos(np.clip((np.trace(R) - 1) / 2, -1, 1)))
            out += ["", f"Общие UV у кусков 0 и 1: {len(A_)} пар вершин. Расстояние между парами (толщина «слоя»): "
                        f"медиана {np.median(dist):.1f} мм, 10 % {np.percentile(dist, 10):.1f}, 90 % "
                        f"{np.percentile(dist, 90):.1f}, макс {dist.max():.1f} мм. Лучшая жёсткая подгонка: поворот "
                        f"{rot:.1f}°, det {det:+.0f}, остаток медиана {np.median(resid):.1f} мм."]
        out.append("")
    # заполнение атласа оригиналом
    a = bc[..., 3]
    out += ["## Альфа оригинала", "",
            f"Пикселей с α ≥ {CUT}: {(a >= CUT).mean() * 100:.1f} % атласа; 0 < α < {CUT} (рвань, вырезается): "
            f"{((a > 0) & (a < CUT)).mean() * 100:.1f} %.", ""]
    open(os.path.join(HERE, "uv", "measure_v2.md"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    print("\n".join(out).encode("utf-8", "replace").decode("utf-8"))


if __name__ == "__main__":
    main()
