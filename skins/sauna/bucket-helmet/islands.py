"""Разбор развёртки Bucket Helmet: острова, где они на модели, плотность, копии, перекрытия.

Запуск (.venv):  python skins/sauna/bucket-helmet/islands.py
Вход:  originals/bucket.helmet.obj, originals/metal_improvised_helmet_02_bc.png
Выход: uv/islands.png (атлас: острова цветом и номером поверх оригинала),
       uv/ids.png     (служебная: id острова в R+G, 0 = пусто),
       uv/faces.json  (остров для каждой грани OBJ),
       uv/islands.md  (таблица).
Основа — skins/sauna/double-barrel/islands.py (одна часть вместо пяти, плюс «наружу/внутрь» по оси ведра).
"""
import json
import math
import os
from collections import defaultdict

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OBJ = os.path.join(HERE, "originals", "bucket.helmet.obj")
BC = os.path.join(HERE, "originals", "metal_improvised_helmet_02_bc.png")
RES = 1024


def load_obj(path):
    load_obj.nf = 0
    V, T, F = [], [], []
    FL = []  # номер строки f (грани OBJ) для каждого треугольника
    for line in open(path):
        p = line.split()
        if not p:
            continue
        if p[0] == "v":
            V.append([float(x) for x in p[1:4]])
        elif p[0] == "vt":
            T.append([float(x) for x in p[1:3]])
        elif p[0] == "f":
            c = [[int(i) - 1 if i else -1 for i in (q.split("/") + ["", ""])[:3]] for q in p[1:]]
            for k in range(1, len(c) - 1):  # триангуляция веером
                F.append([c[0], c[k], c[k + 1]])
                FL.append(load_obj.nf)
            load_obj.nf += 1
    load_obj.fl = FL
    return np.array(V), np.array(T), F


def uf_groups(items, links):
    par = {}

    def fd(a):
        while par.setdefault(a, a) != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    for a, b in links:
        ra, rb = fd(a), fd(b)
        if ra != rb:
            par[ra] = rb
    g = defaultdict(list)
    for key, it in items:
        g[fd(key)].append(it)
    return list(g.values())


def raster_tri(buf, uv, val, res):
    p = np.array([[u * res, (1 - v) * res] for u, v in uv])
    x0, y0 = np.floor(p.min(0)).astype(int)
    x1, y1 = np.ceil(p.max(0)).astype(int)
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, res - 1), min(y1, res - 1)
    if x1 < x0 or y1 < y0:
        return set()
    ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
    P = np.stack([xs + 0.5, ys + 0.5], -1)
    a, b, c = p

    def edge(p0, p1):
        return (p1[0] - p0[0]) * (P[..., 1] - p0[1]) - (p1[1] - p0[1]) * (P[..., 0] - p0[0])
    w0, w1, w2 = edge(b, c), edge(c, a), edge(a, b)
    inside = ((w0 >= 0) & (w1 >= 0) & (w2 >= 0)) | ((w0 <= 0) & (w1 <= 0) & (w2 <= 0))
    sub = buf[y0:y1 + 1, x0:x1 + 1]
    hits = set(np.unique(sub[inside & (sub != 0) & (sub != val)]).tolist())
    sub[inside] = val
    return hits


def main():
    V, T, F = load_obj(OBJ)
    bc = Image.open(BC).convert("RGB")
    texres = bc.size[0]
    lo, hi = V.min(0), V.max(0)
    cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
    # острова по общим vt
    links = [(f[0][1], c[1]) for f in F for c in f[1:]]
    isl = uf_groups([(f[0][1], i) for i, f in enumerate(F)], links)
    isl.sort(key=lambda fs: -len(fs))
    per_face = [0] * len(F)
    for k, fs in enumerate(isl, 1):
        for fi in fs:
            per_face[fi] = k
    os.makedirs(os.path.join(HERE, "uv"), exist_ok=True)
    json.dump(per_face, open(os.path.join(HERE, "uv", "faces.json"), "w"))
    per_obj = [0] * load_obj.nf   # остров для каждой грани OBJ (строки f) — читает bake_bucket.py
    for t, fl in enumerate(load_obj.fl):
        per_obj[fl] = per_face[t]
    json.dump(per_obj, open(os.path.join(HERE, "uv", "faces_obj.json"), "w"))
    buf = np.zeros((RES, RES), np.int32)
    overlaps = defaultdict(set)
    rows = []
    for k, faces in enumerate(isl, 1):
        a3 = a2 = 0.0
        out = up = 0.0
        for fi in faces:
            vi = [c[0] for c in F[fi]]
            ti = [c[1] for c in F[fi]]
            for h in raster_tri(buf, T[ti], k, RES):
                overlaps[k].add(h)
                overlaps[h].add(k)
            P = V[vi]
            n = np.cross(P[1] - P[0], P[2] - P[0])
            A = 0.5 * np.linalg.norm(n)
            a3 += A
            t = T[ti]
            a2 += 0.5 * abs((t[1][0] - t[0][0]) * (t[2][1] - t[0][1]) - (t[2][0] - t[0][0]) * (t[1][1] - t[0][1]))
            c = P.mean(0)
            r = np.array([c[0] - cx, 0, c[2] - cz])
            rl = np.linalg.norm(r) + 1e-9
            nn = n / (np.linalg.norm(n) + 1e-12)
            out += A * float(nn @ r / rl)
            up += A * nn[1]
        vs = V[[c[0] for fi in faces for c in F[fi]]]
        dens = math.sqrt(a2 / a3) * texres / 100 if a3 > 0 else 0
        comps = uf_groups([(F[fi][0][0], fi) for fi in faces],
                          [(F[fi][0][0], c[0]) for fi in faces for c in F[fi][1:]])
        ang = np.degrees(np.arctan2(vs[:, 0] - cx, vs[:, 2] - cz))
        rows.append(dict(k=k, nf=len(faces), lo=vs.min(0), hi=vs.max(0), dens=dens, uv=a2,
                         out=out / a3 if a3 else 0, up=up / a3 if a3 else 0, comps=len(comps),
                         area=a3, ang=(ang.min(), ang.max())))
    # атлас
    rng = np.random.default_rng(3)
    h = rng.random((len(isl) + 1, 3)) * 0.7 + 0.3
    col = (h[buf] * 255).astype(np.uint8)
    base = np.asarray(bc.resize((RES, RES))).astype(float)
    mask = buf[..., None] > 0
    im = Image.fromarray(np.where(mask, base * 0.4 + col * 0.6, base * 0.2).astype(np.uint8))
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    for r in rows:
        ys, xs = np.nonzero(buf == r["k"])
        if len(xs):
            d.text((int(np.median(xs)) - 8, int(np.median(ys)) - 8), str(r["k"]), fill=(255, 255, 255),
                   font=font, stroke_width=2, stroke_fill=(0, 0, 0))
    im.save(os.path.join(HERE, "uv", "islands.png"))
    ids = np.zeros((RES, RES, 3), np.uint8)
    ids[..., 0] = buf % 256
    ids[..., 1] = buf // 256
    Image.fromarray(ids).save(os.path.join(HERE, "uv", "ids.png"))
    # то же в 4096 (маски групп запекания без «ступенек» на краях островов)
    big = np.zeros((4096, 4096), np.int32)
    for k, faces in enumerate(isl, 1):
        for fi in faces:
            raster_tri(big, T[[c[1] for c in F[fi]]], k, 4096)
    ids4 = np.zeros((4096, 4096, 3), np.uint8)
    ids4[..., 0] = big % 256
    ids4[..., 1] = big // 256
    Image.fromarray(ids4).save(os.path.join(HERE, "uv", "ids_4096.png"))
    md = ["# Острова развёртки Bucket Helmet (islands.py)", "",
          f"OBJ: {len(V)} вершин, {len(F)} треугольников. Метры, y вверх. Габарит x {lo[0]:+.3f}…{hi[0]:+.3f}, "
          f"y {lo[1]:+.3f}…{hi[1]:+.3f}, z {lo[2]:+.3f}…{hi[2]:+.3f}. Ось ведра x={cx:+.3f}, z={cz:+.3f}.",
          "Плотность — px на 1 см при Diffuse 1024. «Наружу» — средняя проекция нормали на радиус (+1 наружу, "
          "−1 внутрь), «вверх» — на y. Угол — азимут atan2(x, z), 0° = +z.", "",
          "| # | граней | площадь см² | y | азимут | наружу | вверх | px/см | UV % | кусков геометрии | перекрытие с |",
          "|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---|"]
    for r in rows:
        ov = ", ".join(str(x) for x in sorted(overlaps.get(r["k"], ()))) or "—"
        md.append(f"| {r['k']} | {r['nf']} | {r['area'] * 1e4:.0f} | {r['lo'][1]:+.3f}…{r['hi'][1]:+.3f} | "
                  f"{r['ang'][0]:+.0f}…{r['ang'][1]:+.0f}° | {r['out']:+.2f} | {r['up']:+.2f} | {r['dens']:.1f} | "
                  f"{r['uv'] * 100:.1f} | {r['comps']} | {ov} |")
    cover = (buf > 0).mean()
    md += ["", f"Занято пикселей атласа: {cover * 100:.1f} %."]
    open(os.path.join(HERE, "uv", "islands.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
