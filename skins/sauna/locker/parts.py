"""Locker v6: разбор модели для плана — куски, острова развёртки, плотность текселей, нормали, общие развёртки.

Модель: originals/locker.obj (3ds Max, сантиметры; x вправо, y вверх, +z — перед).

Запуск (.venv):  python skins/sauna/locker/parts.py
Выход: uv/v6/islands.md   — таблица островов: кусок, где на модели, куда смотрит, размер, px/см, сглаженность, общие
       uv/v6/islands.png  — атлас 2048: острова цветом и номером поверх оригинального Diffuse
       uv/v6/ids.png      — служебная: номер острова в R+G*256 (0 = пусто)
       uv/v6/copies.md    — как связаны куски/острова на одних текселях (наименьшие квадраты)
"""
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OBJ = HERE / "originals" / "locker.obj"
OUT = HERE / "uv" / "v6"
RES = 2048  # размер слота Diffuse/Normal/SpecGloss


def load(path):
    V, T, N, F = [], [], [], []
    for line in open(path, encoding="utf8", errors="replace"):
        if line.startswith("v "):
            V.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("vt "):
            T.append([float(x) for x in line.split()[1:3]])
        elif line.startswith("vn "):
            N.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("f "):
            idx = [p.split("/") for p in line.split()[1:]]
            F.append(([int(p[0]) - 1 for p in idx], [int(p[1]) - 1 for p in idx], [int(p[2]) - 1 for p in idx]))
    return np.array(V), np.array(T), np.array(N), F


class DSU:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def join(self, a, b):
        self.p[self.find(a)] = self.find(b)


def poly_area_normal(P):
    n = np.zeros(3)
    for k in range(1, len(P) - 1):
        n += np.cross(P[k] - P[0], P[k + 1] - P[0])
    a = np.linalg.norm(n) / 2
    return a, n / (np.linalg.norm(n) or 1)


def uv_area(Q):
    a = 0.0
    for k in range(1, len(Q) - 1):
        u, v = Q[k] - Q[0], Q[k + 1] - Q[0]
        a += (u[0] * v[1] - u[1] * v[0]) / 2
    return a


def raster(buf, Q, val, res):
    """Заливает многоугольник (UV) значением val, возвращает множество значений, которые уже были под ним."""
    p = np.array([[u * res, (1 - v) * res] for u, v in Q])
    hits = set()
    for k in range(1, len(p) - 1):
        a, b, c = p[0], p[k], p[k + 1]
        x0, y0 = np.maximum(np.floor(np.min([a, b, c], 0)).astype(int), 0)
        x1, y1 = np.minimum(np.ceil(np.max([a, b, c], 0)).astype(int), res - 1)
        if x1 < x0 or y1 < y0:
            continue
        ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        X, Y = xs + 0.5, ys + 0.5

        def e(p0, p1):
            return (p1[0] - p0[0]) * (Y - p0[1]) - (p1[1] - p0[1]) * (X - p0[0])
        w0, w1, w2 = e(b, c), e(c, a), e(a, b)
        ins = ((w0 >= 0) & (w1 >= 0) & (w2 >= 0)) | ((w0 <= 0) & (w1 <= 0) & (w2 <= 0))
        sub = buf[y0:y1 + 1, x0:x1 + 1]
        hits |= set(np.unique(sub[ins & (sub != 0) & (sub != val)]).tolist())
        sub[ins & (sub == 0)] = val
    return hits


def facing(n):
    names = [("перед +z", (0, 0, 1)), ("зад −z", (0, 0, -1)), ("верх +y", (0, 1, 0)), ("низ −y", (0, -1, 0)),
             ("право +x", (1, 0, 0)), ("лево −x", (-1, 0, 0))]
    best = max(names, key=lambda kv: np.dot(n, kv[1]))
    return best[0] if np.dot(n, best[1]) > 0.7 else "наклон"


def rigid_fit(A, B):
    """B ≈ R A + t (Кабш, с отражением). Возвращает R, t, ошибку (см), det."""
    ca, cb = A.mean(0), B.mean(0)
    H = (A - ca).T @ (B - cb)
    U, S, Vt = np.linalg.svd(H)
    R = Vt.T @ U.T  # допускаем отражение: det = -1
    t = cb - R @ ca
    err = np.sqrt(((A @ R.T + t - B) ** 2).sum(1).mean())
    return R, t, err, np.linalg.det(R)


def describe_R(R):
    if np.linalg.det(R) < 0:
        # отражение: найдём ось (собственный вектор с −1)
        w, v = np.linalg.eig(R)
        ax = np.real(v[:, np.argmin(np.abs(w + 1))])
        return f"зеркало по оси {np.round(ax, 2).tolist()}"
    ang = np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1)))
    if ang < 1:
        return "сдвиг"
    w, v = np.linalg.eig(R)
    ax = np.real(v[:, np.argmin(np.abs(w - 1))])
    return f"поворот {ang:.0f}° вокруг {np.round(ax, 2).tolist()}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    V, T, N, F = load(OBJ)
    nf = len(F)

    # куски: сварка по положению (экспорт режет вершины на швах UV)
    d = DSU(len(V))
    key = {}
    for i, p in enumerate(V):
        k = tuple(np.round(p, 2))
        if k in key:
            d.join(i, key[k])
        else:
            key[k] = i
    for vi, _, _ in F:
        for a in vi[1:]:
            d.join(a, vi[0])
    roots = sorted({d.find(F[f][0][0]) for f in range(nf)})
    piece_faces = defaultdict(list)
    for f in range(nf):
        piece_faces[d.find(F[f][0][0])].append(f)
    order = sorted(piece_faces, key=lambda r: -sum(poly_area_normal(V[F[f][0]])[0] for f in piece_faces[r]))
    piece_of = np.zeros(nf, int)
    for n, r in enumerate(order):
        for f in piece_faces[r]:
            piece_of[f] = n

    # острова UV: связность по общим vt внутри куска
    du = DSU(len(T))
    for vi, ti, _ in F:
        for a in ti[1:]:
            du.join(a, ti[0])
    isl_key = {}
    island_of = np.zeros(nf, int)
    for f in range(nf):
        k = (piece_of[f], du.find(F[f][1][0]))
        island_of[f] = isl_key.setdefault(k, len(isl_key) + 1)
    nis = len(isl_key)

    # плотность, нормали
    A3 = np.zeros(nis + 1); AU = np.zeros(nis + 1); NS = np.zeros((nis + 1, 3))
    dev = defaultdict(list)
    lo = np.full((nis + 1, 3), 1e9); hi = np.full((nis + 1, 3), -1e9)
    ulo = np.full((nis + 1, 2), 1e9); uhi = np.full((nis + 1, 2), -1e9)
    for f, (vi, ti, ni) in enumerate(F):
        i = island_of[f]
        a, n = poly_area_normal(V[vi])
        A3[i] += a; NS[i] += a * n
        AU[i] += abs(uv_area(T[ti]))
        lo[i] = np.minimum(lo[i], V[vi].min(0)); hi[i] = np.maximum(hi[i], V[vi].max(0))
        Q = T[ti] % 1.0 if T[ti].max() > 1.0001 else T[ti]
        ulo[i] = np.minimum(ulo[i], Q.min(0)); uhi[i] = np.maximum(uhi[i], Q.max(0))
        for k in ni:
            vn = N[k] / (np.linalg.norm(N[k]) or 1)
            dev[i].append(np.degrees(np.arccos(np.clip(np.dot(vn, n), -1, 1))))

    # перекрытия в UV
    buf = np.zeros((RES, RES), np.int32)
    over = defaultdict(set)
    for f in sorted(range(nf), key=lambda f: island_of[f]):
        Q = T[F[f][1]]
        Q = Q - np.floor(Q.min(0))
        for h in raster(buf, Q, island_of[f], RES):
            over[island_of[f]].add(h); over[h].add(island_of[f])
    # перекрытия внутри одного острова (двусторонние дверцы и т.п.) — по треугольникам
    self_over = set()
    for i in range(1, nis + 1):
        b2 = np.zeros((RES // 4, RES // 4), np.int32)
        for f in np.where(island_of == i)[0]:
            Q = T[F[f][1]]; Q = Q - np.floor(Q.min(0))
            if raster(b2, Q, f + 1, RES // 4):
                self_over.add(i)

    # таблица островов
    rows = []
    for i in range(1, nis + 1):
        pxcm = np.sqrt(AU[i] * RES * RES / A3[i]) if A3[i] > 0 else 0
        n = NS[i] / (np.linalg.norm(NS[i]) or 1)
        dv = np.array(dev[i])
        p = piece_of[island_of == i][0]
        rows.append(dict(i=i, p=p, nf=int((island_of == i).sum()), lo=lo[i], hi=hi[i], ulo=ulo[i], uhi=uhi[i],
                         a=A3[i], px=pxcm, face=facing(n), dmed=np.median(dv), dmax=dv.max(),
                         over=sorted(over[i]), self=i in self_over))

    fmt = lambda a, b: f"{a:.0f}…{b:.0f}"
    md = ["# Locker: острова развёртки (v6)", "",
          "x вправо, y вверх, z к игроку (перед +z), см. UV — доли атласа (v снизу вверх). px/см — в 2048.",
          "Отклонение нормалей — угол между `vn` OBJ и нормалью грани (медиана / максимум): 0° — плоские грани, "
          "20–60° — сглажено.", "",
          "| # | кусок | граней | x | y | z | смотрит | площадь, см² | u | v | px/см | vn∡ мед/макс | общие тексели с |",
          "|---|---:|---:|---|---|---|---|---:|---|---|---:|---|---|"]
    for r in rows:
        ov = ", ".join(f"#{o}" for o in r["over"]) + (" · сам на себя" if r["self"] else "")
        md.append(f"| {r['i']} | {r['p']} | {r['nf']} | {fmt(r['lo'][0], r['hi'][0])} | {fmt(r['lo'][1], r['hi'][1])} | "
                  f"{fmt(r['lo'][2], r['hi'][2])} | {r['face']} | {r['a']:.0f} | {r['ulo'][0]:.3f}…{r['uhi'][0]:.3f} | "
                  f"{r['ulo'][1]:.3f}…{r['uhi'][1]:.3f} | {r['px']:.1f} | {r['dmed']:.0f}°/{r['dmax']:.0f}° | {ov or '—'} |")

    # куски
    md += ["", "## Куски (связные части модели)", "",
           "| кусок | граней | островов | x | y | z | площадь, см² | px/см (по площади) |", "|---:|---:|---:|---|---|---|---:|---:|"]
    for n in range(len(order)):
        fs = np.where(piece_of == n)[0]
        P = np.concatenate([V[F[f][0]] for f in fs])
        a3 = sum(A3[i] for i in set(island_of[fs]))
        au = sum(AU[i] for i in set(island_of[fs]))
        md.append(f"| {n} | {len(fs)} | {len(set(island_of[fs]))} | {fmt(P[:, 0].min(), P[:, 0].max())} | "
                  f"{fmt(P[:, 1].min(), P[:, 1].max())} | {fmt(P[:, 2].min(), P[:, 2].max())} | {a3:.0f} | "
                  f"{np.sqrt(au * RES * RES / a3):.1f} |")
    (OUT / "islands.md").write_text("\n".join(md) + "\n", encoding="utf8")

    # связь копий: острова с общими текселями — по вершинам с одинаковыми UV
    cp = ["# Locker: острова на одних текселях — как связаны копии", "",
          "Подбор B ≈ R·A + t по вершинам с одинаковыми UV (Кабш, допускаем отражение). Ошибка — СКО, см.", "",
          "| A | B | точек | связь | сдвиг t, см | ошибка, см |", "|---:|---:|---:|---|---|---:|"]
    uvpos = defaultdict(lambda: defaultdict(list))
    for f, (vi, ti, _) in enumerate(F):
        for v, t in zip(vi, ti):
            uvpos[island_of[f]][tuple(np.round(T[t] % 1.0, 4))].append(V[v])
    done = set()
    for i in range(1, nis + 1):
        for j in over[i]:
            if (j, i) in done or j == 0:
                continue
            done.add((i, j))
            common = set(uvpos[i]) & set(uvpos[j])
            if len(common) < 3:
                cp.append(f"| {i} | {j} | {len(common)} | перекрытие без общих вершин UV | — | — |")
                continue
            A = np.array([np.mean(uvpos[i][k], 0) for k in common])
            B = np.array([np.mean(uvpos[j][k], 0) for k in common])
            R, t, err, det = rigid_fit(A, B)
            cp.append(f"| {i} | {j} | {len(common)} | {describe_R(R)} | {np.round(t, 1).tolist()} | {err:.2f} |")
    (OUT / "copies.md").write_text("\n".join(cp) + "\n", encoding="utf8")

    # атлас номеров
    ids = np.zeros((RES, RES, 3), np.uint8)
    ids[..., 0] = buf % 256; ids[..., 1] = buf // 256
    Image.fromarray(ids).save(OUT / "ids.png")
    base = Image.open(HERE / "originals" / "locker_bc.png").convert("RGB").resize((RES, RES))
    rng = np.random.default_rng(3)
    pal = rng.integers(60, 255, (nis + 1, 3)).astype(np.uint8); pal[0] = 0
    col = pal[buf]
    mix = (np.asarray(base) * 0.45 + col * 0.55).astype(np.uint8)
    mix[buf == 0] = (np.asarray(base)[buf == 0] * 0.25).astype(np.uint8)
    img = Image.fromarray(mix)
    dr = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    for r in rows:
        ys, xs = np.where(buf == r["i"])
        if len(xs) == 0:
            continue
        k = len(xs) // 2
        cx, cy = int(np.median(xs)), int(np.median(ys))
        if buf[cy, cx] != r["i"]:
            cx, cy = xs[k], ys[k]
        dr.text((cx, cy), str(r["i"]), fill=(255, 255, 255), font=font, stroke_width=3, stroke_fill=(0, 0, 0), anchor="mm")
    img.save(OUT / "islands.png")
    # грани на одних текселях: куда в 3D идут +u и +v у каждой копии (что «вверх» и «вперёд» на общей развёртке)
    def uvkey(f):
        return tuple(sorted(tuple(np.round(T[t] % 1, 3)) for t in F[f][1]))
    same = defaultdict(list)
    for f in range(nf):
        same[uvkey(f)].append(f)
    sf = ["# Locker: грани на одних текселях — оси UV в 3D", "",
          "Для каждой группы граней с одинаковыми UV: центр грани, нормаль, куда в 3D смотрят +u и +v. Если у копий "
          "+v смотрит в разные стороны — рисунок на одной копии перевёрнут относительно другой.", "",
          "| площадь, см² | остров | центр (x, y, z) | нормаль | +u | +v |", "|---:|---:|---|---|---|---|"]
    vec = lambda a: "(" + ", ".join(f"{int(c):+d}" for c in np.round(a)) + ")"
    for k, fs in sorted(same.items(), key=lambda kv: -poly_area_normal(V[F[kv[1][0]][0]])[0]):
        a0 = poly_area_normal(V[F[fs[0]][0]])[0]
        if len(fs) < 2 or a0 < 100:
            continue
        for f in fs:
            Q = T[F[f][1]] % 1.0
            X = V[F[f][0]]
            sol = np.linalg.lstsq(Q - Q.mean(0), X - X.mean(0), rcond=None)[0]
            _, n = poly_area_normal(X)
            c = X.mean(0)
            sf.append(f"| {a0:.0f} | {island_of[f]} | ({c[0]:.0f}, {c[1]:.0f}, {c[2]:.0f}) | {vec(n)} | "
                      f"{vec(sol[0] / np.linalg.norm(sol[0]))} | {vec(sol[1] / np.linalg.norm(sol[1]))} |")
    (OUT / "shared_faces.md").write_text("\n".join(sf) + "\n", encoding="utf8")
    # служебная таблица для bake_v6.py (в Blender нет PIL): грань -> остров, кусок, центр, нормаль
    import json
    rec = []
    for f, (vi, ti, _) in enumerate(F):
        _, n = poly_area_normal(V[vi])
        rec.append(dict(island=int(island_of[f]), piece=int(piece_of[f]), c=np.round(V[vi].mean(0), 3).tolist(),
                        n=np.round(n, 4).tolist()))
    (OUT / "faces.json").write_text(json.dumps(rec), encoding="utf8")
    print("\n".join(md[:8 + nis]))
    print("\n".join(cp))


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    main()
