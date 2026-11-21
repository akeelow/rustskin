"""Sauna Stove v3.0 — замеры модели перед планом (PLAN_v3.md, раздел 0).

Куски (связные части, сваренные по положению), их габариты, плотность текселей (px/см при 2048), сглаженность
нормалей OBJ (угол vn к нормали грани), общие тексели между кусками и преобразование копий (наименьшие квадраты
по вершинам с одинаковыми UV), перекрытия внутри куска.

Оси OBJ: x — вправо (+X правый бок), y — вверх, z — вперёд (+Z перед, дверца). Метры.
Запуск (.venv, из корня репозитория):  .venv/Scripts/python skins/sauna/electric-furnace/measure_v3.py
Пишет: uv/parts_v3.md, uv/parts_v3.png (атлас: куски цветом и номером, белое — общие тексели).
"""
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OBJ = HERE / "originals" / "electric.furnace.obj"
BC = HERE / "originals" / "ElectricFurnace_bc.png"
EXPORT = 2048
RES = 1024  # растр для перекрытий


def load():
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
    F = np.array(F)  # (nf, 3, 3): corner, (v, vt, vn)
    return np.array(V), np.array(T), np.array(N), F


def pieces(V, F):
    parent = np.arange(len(V))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    key = {}
    for i, p in enumerate(np.round(V, 4)):
        k = tuple(p)
        if k in key:
            parent[find(i)] = find(key[k])
        else:
            key[k] = i
    for f in F[:, :, 0]:
        for a in f[1:]:
            parent[find(a)] = find(f[0])
    g = defaultdict(list)
    for fi, f in enumerate(F[:, :, 0]):
        g[find(f[0])].append(fi)
    return sorted(g.values(), key=lambda fs: -len(fs))


def raster(buf_owner, uv, pid, res):
    p = np.c_[uv[:, 0] * res, (1 - uv[:, 1]) * res]
    x0, y0 = np.floor(p.min(0)).astype(int)
    x1, y1 = np.ceil(p.max(0)).astype(int)
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, res - 1), min(y1, res - 1)
    if x1 < x0 or y1 < y0:
        return []
    ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
    P = np.stack([xs + 0.5, ys + 0.5], -1)
    a, b, c = p

    def e(p0, p1):
        return (p1[0] - p0[0]) * (P[..., 1] - p0[1]) - (p1[1] - p0[1]) * (P[..., 0] - p0[0])

    w0, w1, w2 = e(b, c), e(c, a), e(a, b)
    ins = ((w0 >= 0) & (w1 >= 0) & (w2 >= 0)) | ((w0 <= 0) & (w1 <= 0) & (w2 <= 0))
    return list(zip(ys[ins].tolist(), xs[ins].tolist()))


def side_of(n):
    ax = int(np.argmax(np.abs(n)))
    return ["+X прав" if n[0] > 0 else "−X лев", "верх" if n[1] > 0 else "низ", "+Z перед" if n[2] > 0 else "−Z зад"][ax]


def kabsch(A, B):
    """B ≈ R A + t, R может быть с отражением."""
    ca, cb = A.mean(0), B.mean(0)
    H = (A - ca).T @ (B - cb)
    U, S, Vt = np.linalg.svd(H)
    R = Vt.T @ U.T
    t = cb - R @ ca
    err = np.abs((A @ R.T + t) - B).max()
    return R, t, err


def describe_R(R):
    det = np.linalg.det(R)
    Rr = R if det > 0 else R @ np.diag([-1, 1, 1])
    ang = math.degrees(math.acos(np.clip((np.trace(Rr) - 1) / 2, -1, 1)))
    w, v = np.linalg.eig(Rr)
    axis = np.real(v[:, np.argmin(np.abs(w - 1))])
    s = f"поворот {ang:.0f}° вокруг ({axis[0]:+.2f}, {axis[1]:+.2f}, {axis[2]:+.2f})"
    if det < 0:
        s = "зеркало по x, затем " + s
    return s


def main():
    V, T, N, F = load()
    fv, ft, fn = F[:, :, 0], F[:, :, 1], F[:, :, 2]
    P = V[fv]
    fnorm = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    area3 = np.linalg.norm(fnorm, axis=1) / 2  # м²
    fnorm = fnorm / np.maximum(np.linalg.norm(fnorm, axis=1, keepdims=True), 1e-12)
    UV = T[ft]
    uvw = UV - np.floor(UV.min(1, keepdims=True))  # тайлы > 1 → в 0..1
    d1, d2 = uvw[:, 1] - uvw[:, 0], uvw[:, 2] - uvw[:, 0]
    area2 = np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / 2
    # угол нормалей вершин к нормали грани
    cn = N[fn]
    cn = cn / np.maximum(np.linalg.norm(cn, axis=2, keepdims=True), 1e-12)
    ang = np.degrees(np.arccos(np.clip(np.einsum("fcj,fj->fc", cn, fnorm), -1, 1)))
    tri_ang = ang.max(1)

    PCS = pieces(V, F)
    owner = defaultdict(set)
    for n, fs in enumerate(PCS):
        for f in fs:
            for yx in raster(owner, uvw[f], n, RES):
                owner[yx].add(n)
    shared = defaultdict(lambda: defaultdict(int))
    for yx, s in owner.items():
        if len(s) > 1:
            for a in s:
                for b in s - {a}:
                    shared[a][b] += 1

    # перекрытие внутри куска (одна часть куска на текселях другой части того же куска)
    self_ov = defaultdict(int)
    cnt = defaultdict(lambda: defaultdict(int))
    for n, fs in enumerate(PCS):
        for f in fs:
            for yx in raster(None, uvw[f], n, RES):
                cnt[n][yx] += 1
    for n in cnt:
        self_ov[n] = sum(1 for v in cnt[n].values() if v > 1)

    rows = []
    md = ["# Sauna Stove: куски модели (замеры для v3)", "",
          "`measure_v3.py`. Оси OBJ: x вправо (+X — правый бок), y вверх, z вперёд (+Z — дверца). Размеры в см.",
          "px/см — при экспорте 2048 (медиана по площади); «угол vn» — насколько нормали вершин OBJ отклонены от "
          "нормали грани (медиана / 95 %): больше ~5° — кусок сглажен, нужен перенос нормали.", "",
          "| # | треуг. | x | y | z | площадь, см² | главная сторона | px/см | угол vn мед / 95% | своё перекр., px | общие тексели с (px при 1024) |",
          "|---|---:|---|---|---|---:|---|---:|---|---:|---|"]
    for n, fs in enumerate(PCS):
        fs = np.array(fs)
        pts = V[fv[fs]].reshape(-1, 3) * 100
        lo, hi = pts.min(0), pts.max(0)
        a3 = area3[fs].sum() * 1e4
        dens = np.sqrt(area2[fs] * EXPORT ** 2 / np.maximum(area3[fs] * 1e4, 1e-9))
        w = area3[fs]
        order = np.argsort(dens)
        cw = np.cumsum(w[order]) / w.sum()
        med = dens[order][np.searchsorted(cw, 0.5)]
        nsum = (fnorm[fs] * w[:, None]).sum(0)
        main_side = side_of(nsum) if np.linalg.norm(nsum) > 0.2 * w.sum() else "разные"
        am = np.median(tri_ang[fs]); a95 = np.percentile(tri_ang[fs], 95)
        sh = ", ".join(f"{m} ({c})" for m, c in sorted(shared[n].items(), key=lambda kv: -kv[1])[:6])
        md.append(f"| {n} | {len(fs)} | {lo[0]:.0f}…{hi[0]:.0f} | {lo[1]:.0f}…{hi[1]:.0f} | {lo[2]:.0f}…{hi[2]:.0f} | "
                  f"{a3:.0f} | {main_side} | {med:.1f} | {am:.0f}° / {a95:.0f}° | {self_ov[n]} | {sh} |")
        rows.append((n, fs, med))

    # копии: пары с общими текселями → преобразование по вершинам с одинаковым vt
    md += ["", "## Копии на общих текселях (наименьшие квадраты по вершинам с одинаковыми UV)", "",
           "| пара | общих UV-вершин | преобразование | ошибка, мм |", "|---|---:|---|---:|"]
    vt_pos = []
    for n, fs in enumerate(PCS):
        d = {}
        for f in fs:
            for c in range(3):
                d[tuple(np.round(uvw[f, c], 5))] = V[fv[f, c]]
        vt_pos.append(d)
    done = set()
    for a in shared:
        for b, c in shared[a].items():
            if (b, a) in done or c < 20:
                continue
            done.add((a, b))
            ks = [k for k in vt_pos[a] if k in vt_pos[b]]
            if len(ks) < 4:
                md.append(f"| {a}↔{b} | {len(ks)} | вершины UV не совпадают (перекрытие без общей сетки) | — |")
                continue
            A = np.array([vt_pos[a][k] for k in ks]); B = np.array([vt_pos[b][k] for k in ks])
            R, t, err = kabsch(A, B)
            md.append(f"| {a}↔{b} | {len(ks)} | {describe_R(R)}, сдвиг ({t[0]*100:+.1f}, {t[1]*100:+.1f}, {t[2]*100:+.1f}) см | {err*1000:.1f} |")

    # сводка сглаженности по сторонам главных кусков
    md += ["", "## Сглаженность по сторонам (все грани, медиана угла vn)", "", "| сторона | граней | медиана | 95 % |", "|---|---:|---:|---:|"]
    sides = np.array([side_of(n) for n in fnorm])
    for s in np.unique(sides):
        m = sides == s
        md.append(f"| {s} | {m.sum()} | {np.median(tri_ang[m]):.0f}° | {np.percentile(tri_ang[m], 95):.0f}° |")

    (HERE / "uv" / "parts_v3.md").write_text("\n".join(md) + "\n", encoding="utf8")

    # атлас
    img = Image.open(BC).convert("RGB").resize((RES, RES)).point(lambda v: v // 3)
    px = img.load()
    cent = {}
    for n, fs in enumerate(PCS):
        col = ((n * 97) % 200 + 55, (n * 57) % 200 + 55, (n * 31) % 200 + 55)
        acc = []
        for f in fs:
            for y, x in raster(None, uvw[f], n, RES):
                px[x, y] = (255, 255, 255) if len(owner[(y, x)]) > 1 else col
                acc.append((x, y))
        if acc:
            cent[n] = np.mean(acc, 0)
    dr = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = None
    for n, (x, y) in cent.items():
        if len(PCS[n]) >= 20 or n < 40:
            dr.text((x - 6, y - 7), str(n), fill=(255, 255, 0), font=font, stroke_width=2, stroke_fill=(0, 0, 0))
    img.save(HERE / "uv" / "parts_v3.png")
    print("\n".join(md[:12 + min(len(PCS), 80)]))
    print(f"... кусков: {len(PCS)}")


if __name__ == "__main__" and not ({"--islands", "--compare", "--numbered"} & set(__import__("sys").argv)):
    main()


# ---------------------------------------------------------------- острова UV (связность по общим vt)
def islands(F):
    ft = F[:, :, 1]
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for f in ft:
        for a in f[1:]:
            ra, rb = find(a), find(f[0])
            if ra != rb:
                parent[ra] = rb
    g = defaultdict(list)
    for fi, f in enumerate(ft):
        g[find(f[0])].append(fi)
    return list(g.values())


def main_islands():
    V, T, N, F = load()
    fv, ft, fn = F[:, :, 0], F[:, :, 1], F[:, :, 2]
    P = V[fv]
    fnorm = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    area3 = np.linalg.norm(fnorm, axis=1) / 2
    fnorm = fnorm / np.maximum(np.linalg.norm(fnorm, axis=1, keepdims=True), 1e-12)
    UV = T[ft]
    uvw = UV - np.floor(UV.min(1, keepdims=True))
    d1, d2 = uvw[:, 1] - uvw[:, 0], uvw[:, 2] - uvw[:, 0]
    area2 = np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / 2
    cn = N[fn]
    cn = cn / np.maximum(np.linalg.norm(cn, axis=2, keepdims=True), 1e-12)
    ang = np.degrees(np.arccos(np.clip(np.einsum("fcj,fj->fc", cn, fnorm), -1, 1))).max(1)
    PCS = pieces(V, F)
    piece_of = np.zeros(len(F), int)
    for n, fs in enumerate(PCS):
        piece_of[fs] = n
    ISL = islands(F)
    # перекрытия островов (растр 1024)
    owner = defaultdict(set)
    for k, fs in enumerate(ISL):
        for f in fs:
            for yx in raster(None, uvw[f], k, RES):
                owner[yx].add(k)
    ov = defaultdict(lambda: defaultdict(int))
    for yx, s in owner.items():
        if len(s) > 1:
            for a in s:
                for b in s - {a}:
                    ov[a][b] += 1
    rec = []
    for k, fs in enumerate(ISL):
        fs = np.array(fs)
        a2px = area2[fs].sum() * EXPORT ** 2
        a3 = area3[fs].sum() * 1e4
        pts = V[fv[fs]].reshape(-1, 3) * 100
        lo, hi = pts.min(0), pts.max(0)
        uv = uvw[fs].reshape(-1, 2)
        nsum = (fnorm[fs] * area3[fs][:, None]).sum(0)
        side = side_of(nsum) if np.linalg.norm(nsum) > 0.5 * area3[fs].sum() else "разные"
        rec.append(dict(k=k, n=len(fs), a2=a2px, a3=a3, dens=math.sqrt(a2px / max(a3, 1e-9)),
                        lo=lo, hi=hi, u=(uv[:, 0].min(), uv[:, 0].max()), v=(1 - uv[:, 1].max(), 1 - uv[:, 1].min()),
                        side=side, ang=np.median(ang[fs]), a95=np.percentile(ang[fs], 95),
                        piece=np.bincount(piece_of[fs]).argmax(), ov=dict(ov[k])))
    rec.sort(key=lambda r: -r["a2"])
    order = {r["k"]: i for i, r in enumerate(rec)}
    md = ["# Sauna Stove: острова UV (замеры для v3)", "",
          "`measure_v3.py --islands`. Острова — связные по общим `vt`. Номер острова — по убыванию площади в атласе. "
          "Оси: x вправо (+X — правый бок), y вверх, z вперёд (+Z — дверца), см. "
          "px/см — при 2048; «угол vn» — медиана / 95 % отклонения нормалей вершин от граней.", "",
          f"Всего островов: {len(rec)}; в таблице — занимающие ≥ 2000 px² при 2048 (остальные мелочь: винты, рёбра).", "",
          "| № | треуг. | px² (2048) | см² | px/см | сторона | x | y | z | u | v (сверху) | угол vn | кусок | перекрыт с № (px при 1024) |",
          "|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---:|---|"]
    for i, r in enumerate(rec):
        if r["a2"] < 2000:
            continue
        o = ", ".join(f"{order[m]} ({c})" for m, c in sorted(r["ov"].items(), key=lambda kv: -kv[1])[:5])
        lo, hi = r["lo"], r["hi"]
        md.append(f"| {i} | {r['n']} | {r['a2']:.0f} | {r['a3']:.0f} | {r['dens']:.1f} | {r['side']} | "
                  f"{lo[0]:.0f}…{hi[0]:.0f} | {lo[1]:.0f}…{hi[1]:.0f} | {lo[2]:.0f}…{hi[2]:.0f} | "
                  f"{r['u'][0]:.3f}–{r['u'][1]:.3f} | {r['v'][0]:.3f}–{r['v'][1]:.3f} | {r['ang']:.0f}°/{r['a95']:.0f}° | {r['piece']} | {o} |")
    used = sum(r["a2"] for r in rec) / EXPORT ** 2
    md += ["", f"Занято атласа (с перекрытиями): {used*100:.0f} %."]
    (HERE / "uv" / "islands_v3.md").write_text("\n".join(md) + "\n", encoding="utf8")
    img = Image.open(BC).convert("RGB").resize((RES, RES)).point(lambda v: v // 3)
    px = img.load()
    dr = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 13)
    except OSError:
        font = None
    for i, r in enumerate(rec):
        col = ((i * 97) % 200 + 55, (i * 57) % 200 + 55, (i * 31) % 200 + 55)
        for f in ISL[r["k"]]:
            for y, x in raster(None, uvw[f], 0, RES):
                px[x, y] = (255, 255, 255) if len(owner[(y, x)]) > 1 else col
    for i, r in enumerate(rec):
        if r["a2"] >= 2000:
            x = (r["u"][0] + r["u"][1]) / 2 * RES
            y = (r["v"][0] + r["v"][1]) / 2 * RES
            dr.text((x - 6, y - 7), str(i), fill=(255, 255, 0), font=font, stroke_width=2, stroke_fill=(0, 0, 0))
    img.save(HERE / "uv" / "islands_v3.png")
    print("islands", len(rec))


if __name__ == "__main__" and "--islands" in __import__("sys").argv:
    main_islands()


# ---------------------------------------------------------------- сравнение с принятыми скинами из кэша Steam
CACHE = Path(r"C:/Program Files (x86)/Steam/steamapps/workshop/content/252490")
CACHED = ["3752247893", "3752908734", "3767601686", "3785172146", "3793518390", "3797829067", "3805880543",
          "3840311723"]  # последний — наш v2.9
REGIONS = {"left_side": (0.524, 0.677, 0.791, 0.981), "top_plate": (0.695, 0.866, 0.823, 0.994),
           "plinth_front": (0.530, 0.707, 0.452, 0.506), "door": (0.541, 0.673, 0.612, 0.755),
           "back": (0.549, 0.765, 0.245, 0.404)}  # u0, u1, v0, v1 (v сверху)


def richness(path, region):
    """Насыщенность нормали: средний угол мелкого (σ 4 px) и среднего (σ 4–24 px) рельефа, градусы, в 2048."""
    from PIL import ImageFilter
    im = Image.open(path).convert("RGB")
    if im.size[0] != 2048:
        im = im.resize((2048, 2048), Image.LANCZOS)
    u0, u1, v0, v1 = region
    c = im.crop((int(u0 * 2048), int(v0 * 2048), int(u1 * 2048), int(v1 * 2048)))
    f = lambda img: np.asarray(img, float)[..., :2] / 255 * 2 - 1
    a, b4, b24 = f(c), f(c.filter(ImageFilter.GaussianBlur(4))), f(c.filter(ImageFilter.GaussianBlur(24)))
    deg = lambda d: np.degrees(np.arcsin(np.clip(np.linalg.norm(d, axis=-1), 0, 1))).mean()
    return deg(a - b4), deg(b4 - b24)


def main_compare(extra=()):
    """--compare [normal.png ...]: вырезы Diffuse+Normal одного места атласа у принятых и у нас (plan_v3/cmp_*.jpg),
    таблица насыщенности нормали; extra — свои карты нормалей для сравнения (например export v3)."""
    font = ImageFont.truetype("arial.ttf", 18)
    out = HERE / "plan_v3"
    out.mkdir(exist_ok=True)
    for name, (u0, u1, v0, v1) in REGIONS.items():
        W = 300
        H = int(W * (v1 - v0) / (u1 - u0))
        sheet = Image.new("RGB", (len(CACHED) * (2 * W + 12), H + 28), (30, 30, 34))
        d = ImageDraw.Draw(sheet)
        for i, s in enumerate(CACHED):
            x = i * (2 * W + 12)
            for j, t in enumerate(["_MainTex0", "_BumpMap0"]):
                im = Image.open(CACHE / s / f"{t}.png").convert("RGB")
                w, h = im.size
                sheet.paste(im.crop((int(u0 * w), int(v0 * h), int(u1 * w), int(v1 * h))).resize((W, H), Image.LANCZOS),
                            (x + j * W, 28))
            d.text((x + 4, 4), ("OUR v2.9 " if s == CACHED[-1] else "") + s, fill=(255, 255, 0), font=font)
        sheet.save(out / f"cmp_{name}.jpg", quality=88)
    print("| скин | " + " | ".join(REGIONS) + " |")
    for s in CACHED + list(extra):
        p = CACHE / s / "_BumpMap0.png" if s in CACHED else Path(s)
        print(f"| {s} | " + " | ".join("%.1f / %.1f" % richness(p, r) for r in REGIONS.values()) + " |")


if __name__ == "__main__" and "--compare" in __import__("sys").argv:
    import sys as _s
    main_compare(_s.argv[_s.argv.index("--compare") + 1:])


def main_numbered(size=2048):
    """--numbered: атлас 2048 — острова цветом и крупным номером в центре масс (для рендера на модели)."""
    V, T, N, F = load()
    UV = T[F[:, :, 1]]
    uvw = UV - np.floor(UV.min(1, keepdims=True))
    d1, d2 = uvw[:, 1] - uvw[:, 0], uvw[:, 2] - uvw[:, 0]
    area2 = np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / 2
    ISL = sorted(islands(F), key=lambda fs: -area2[fs].sum())
    img = Image.new("RGB", (size, size), (40, 40, 40))
    px = img.load()
    cents = []
    for i, fs in enumerate(ISL):
        col = ((i * 97) % 180 + 60, (i * 57) % 180 + 60, (i * 31) % 180 + 60)
        acc = []
        for f in fs:
            for y, x in raster(None, uvw[f], 0, size):
                px[x, y] = col
                acc.append((x, y))
        if acc:  # пиксель острова, ближайший к центру масс (у рамок центр масс лежит в чужом острове)
            A = np.array(acc, float)
            cents.append(A[np.argmin(((A - A.mean(0)) ** 2).sum(1))])
        else:
            cents.append(None)
    dr = ImageDraw.Draw(img)
    for i, c in enumerate(cents):
        if c is None or area2[ISL[i]].sum() * size * size < 1500:
            continue
        fs = 40 if area2[ISL[i]].sum() * size * size > 20000 else 22
        font = ImageFont.truetype("arialbd.ttf", fs)
        dr.text((c[0], c[1]), str(i), fill=(255, 255, 255), font=font, anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0))
    img.save(HERE / "uv" / "islands_v3_num.png")
    print("ok", len(ISL))


if __name__ == "__main__" and "--numbered" in __import__("sys").argv:
    main_numbered()
