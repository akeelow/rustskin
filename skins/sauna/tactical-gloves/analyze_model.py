"""Разбор модели Tactical Gloves: компоненты, острова, общие UV (зеркальность), плотность px/см.

Запуск (.venv):  python skins/sauna/tactical-gloves/analyze_model.py
Выход: uv/model.md, uv/islands.png, uv/ids.npy
"""
import os, sys
from collections import defaultdict
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OBJ = os.path.join(HERE, "originals", "tactical.gloves.obj")
RES = 2048


def load(path):
    V, T, F, FT = [], [], [], []
    for line in open(path):
        p = line.split()
        if not p: continue
        if p[0] == "v": V.append([float(x) for x in p[1:4]])
        elif p[0] == "vt": T.append([float(x) for x in p[1:3]])
        elif p[0] == "f":
            vs = [c.split("/") for c in p[1:]]
            F.append([int(a[0]) - 1 for a in vs]); FT.append([int(a[1]) - 1 for a in vs])
    return np.array(V), np.array(T), F, FT


class DSU:
    def __init__(s, n): s.p = list(range(n))
    def f(s, a):
        while s.p[a] != a:
            s.p[a] = s.p[s.p[a]]; a = s.p[a]
        return a
    def u(s, a, b): s.p[s.f(a)] = s.f(b)


def main():
    V, T, F, FT = load(OBJ)
    out = []
    pr = lambda *a: out.append(" ".join(str(x) for x in a))
    pr("# Модель Tactical Gloves — разбор", "")
    pr(f"Вершин {len(V)}, UV {len(T)}, граней {len(F)}; bbox min {V.min(0).round(4)} max {V.max(0).round(4)}", "")
    # 3D components
    d = DSU(len(V))
    for f in F:
        for a in f[1:]: d.u(f[0], a)
    comp = defaultdict(list)
    for i, f in enumerate(F): comp[d.f(f[0])].append(i)
    pr("## Компоненты 3D", "")
    for k, fs in sorted(comp.items(), key=lambda x: -len(x[1])):
        vi = sorted({v for i in fs for v in F[i]})
        P = V[vi]
        pr(f"- {len(fs)} граней, центр {P.mean(0).round(3)}, min {P.min(0).round(3)} max {P.max(0).round(3)}")
    # UV islands
    du = DSU(len(T))
    for ft in FT:
        for a in ft[1:]: du.u(ft[0], a)
    isl = defaultdict(list)
    for i, ft in enumerate(FT): isl[du.f(ft[0])].append(i)
    order = sorted(isl.values(), key=lambda fs: -len(fs))
    ids = np.zeros((RES, RES), np.int32)
    img = Image.open(os.path.join(HERE, "originals", "TacticalGloves_bc.png")).convert("RGB")
    img = Image.fromarray(np.clip(np.asarray(img).astype(float) * 2.2, 0, 255).astype(np.uint8)).resize((RES, RES))
    dr = ImageDraw.Draw(img)
    rng = np.random.default_rng(3)
    pr("", "## Острова UV", "")
    pr("| № | граней | копий 3D | сторона x | UV bbox (u0 v0 u1 v1) | px/см @2048 | 3D центр |")
    pr("|---|---|---|---|---|---|---|")
    for n, fs in enumerate(order, 1):
        # copies: vertices sharing same vt -> group by 3D component
        comps = defaultdict(list)
        for i in fs: comps[d.f(F[i][0])].append(i)
        a3 = a2 = 0.0
        xs = []
        for i in fs:
            f, ft = F[i], FT[i]
            for j in range(1, len(f) - 1):
                p0, p1, p2 = V[f[0]], V[f[j]], V[f[j + 1]]
                t0, t1, t2 = T[ft[0]], T[ft[j]], T[ft[j + 1]]
                a3 += np.linalg.norm(np.cross(p1 - p0, p2 - p0)) / 2
                a2 += abs(np.cross(t1 - t0, t2 - t0)) / 2
            xs += [V[v][0] for v in f]
        dens = np.sqrt(a2 / max(a3, 1e-12)) * RES / 100.0
        uvs = np.array([T[t] for i in fs for t in FT[i]])
        col = tuple(int(c) for c in rng.integers(60, 255, 3))
        for i in fs:
            ft = FT[i]
            poly = [(T[t][0] * RES, (1 - T[t][1]) * RES) for t in ft]
            dr.polygon(poly, outline=col)
        c = uvs.mean(0)
        dr.text((c[0] * RES, (1 - c[1]) * RES), str(n), fill=(255, 255, 0))
        xs = np.array(xs)
        side = "оба" if xs.min() < 0 < xs.max() else ("+x" if xs.min() >= 0 else "-x")
        cen = np.array([V[v] for i in fs for v in F[i]]).mean(0)
        pr(f"| {n} | {len(fs)} | {len(comps)} | {side} | {uvs.min(0).round(3)} {uvs.max(0).round(3)} | {dens:.1f} | {cen.round(3)} |")
    # mirror check: for each vt, the set of 3D positions
    pos = defaultdict(set)
    for f, ft in zip(F, FT):
        for v, t in zip(f, ft): pos[t].add(v)
    multi = sum(1 for t in pos if len(pos[t]) > 1)
    pr("", f"UV-вершин с несколькими 3D-вершинами: {multi} из {len(pos)}")
    # sample pairs to test mirror x
    pairs = [(sorted(pos[t])) for t in pos if len(pos[t]) == 2]
    if pairs:
        A = np.array([V[p[0]] for p in pairs]); B = np.array([V[p[1]] for p in pairs])
        m = np.abs(A[:, 0] + B[:, 0]).mean(), np.abs(A[:, 1] - B[:, 1]).mean(), np.abs(A[:, 2] - B[:, 2]).mean()
        pr(f"Пары: {len(pairs)}; |xA+xB| {m[0]:.4f}, |yA-yB| {m[1]:.4f}, |zA-zB| {m[2]:.4f} (0 → зеркало по X)")
        sd = np.abs(A[:, 0] - B[:, 0])
        pr(f"|xA-xB| min {sd.min():.4f} median {np.median(sd):.4f} (0 → одна и та же точка, шов UV)")
    img.save(os.path.join(HERE, "uv", "islands.png"))
    open(os.path.join(HERE, "uv", "model.md"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
