"""Разбор развёртки двустволки по частям: острова, где они на модели, перекрытия в UV.

Запуск (.venv):  python islands.py
Вход:  source/parts/<part>.obj (split_materials.py), originals/<part>_bc.png
Выход: uv/<part>_islands.png  (атлас: острова цветом и номером поверх оригинала),
       uv/<part>_ids.png      (служебная: id острова в R+G, 0 = пусто; читает texture-скрипт),
       uv/islands.md          (таблица: номер, грани, где на модели, нормаль, плотность, перекрытия).
Оси OBJ: x — вправо от стрелка, y — вверх, z — вперёд (к дулу). Метры.
"""
import os
from collections import defaultdict

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from split_materials import load_obj, uv_islands

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = ["barrel", "main", "sights", "stock", "grip", "shell"]
TEX = {"shell": "main"}  # у патронов своей вкладки нет (сверено по атласу main: гильзы справа внизу)
RES = 1024


def raster_tri(buf, uv, val, res):
    """Растеризация треугольника в buf (H×W int) значением val; возвращает пиксели, уже занятые другим."""
    p = np.array([[u * res, (1 - v) * res] for u, v in uv])
    x0, y0 = np.floor(p.min(0)).astype(int)
    x1, y1 = np.ceil(p.max(0)).astype(int)
    x0, y0 = max(x0, 0), max(y0, 0)
    x1, y1 = min(x1, res - 1), min(y1, res - 1)
    if x1 < x0 or y1 < y0:
        return 0
    ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
    P = np.stack([xs + 0.5, ys + 0.5], -1)
    a, b, c = p
    def edge(p0, p1):
        return (p1[0] - p0[0]) * (P[..., 1] - p0[1]) - (p1[1] - p0[1]) * (P[..., 0] - p0[0])
    w0, w1, w2 = edge(b, c), edge(c, a), edge(a, b)
    inside = ((w0 >= 0) & (w1 >= 0) & (w2 >= 0)) | ((w0 <= 0) & (w1 <= 0) & (w2 <= 0))
    sub = buf[y0:y1 + 1, x0:x1 + 1]
    clash = inside & (sub != 0) & (sub != val)
    hits = set(np.unique(sub[clash]).tolist())
    sub[inside & (sub == 0)] = val
    return hits


def tri_area3(V):
    return 0.5 * np.linalg.norm(np.cross(V[1] - V[0], V[2] - V[0]))


def tri_area2(T):
    return 0.5 * abs((T[1][0] - T[0][0]) * (T[2][1] - T[0][1]) - (T[2][0] - T[0][0]) * (T[1][1] - T[0][1]))


def where(lo, hi, part):
    """Словесно, где кусок (для таблицы)."""
    cz, cy, cx = (lo[2] + hi[2]) / 2, (lo[1] + hi[1]) / 2, (lo[0] + hi[0]) / 2
    side = "лев" if hi[0] < 0.002 else ("прав" if lo[0] > -0.002 else "оба бока")
    return f"z {lo[2]:+.3f}…{hi[2]:+.3f}, y {lo[1]:+.3f}…{hi[1]:+.3f}, x {lo[0]:+.3f}…{hi[0]:+.3f} ({side})"


def main():
    os.makedirs(os.path.join(HERE, "uv"), exist_ok=True)
    md = ["# Острова развёртки по частям (islands.py)", "",
          "Оси OBJ: x — вправо от стрелка (+x правый бок), y — вверх, z — к дулу. Метры.",
          "Плотность — px текстуры на 1 см поверхности (по размеру оригинального Diffuse).",
          "Перекрытие — острова, делящие пиксели атласа (зеркало или повтор: асимметричное туда нельзя).", ""]
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    for part in PARTS:
        V, T, N, F = load_obj(os.path.join(HERE, "source", "parts", f"{part}.obj"))
        bc = Image.open(os.path.join(HERE, "originals", f"{TEX.get(part, part)}_bc.png")).convert("RGB")
        texres = bc.size[0]
        isl = sorted(uv_islands(F), key=lambda fs: -len(fs))
        buf = np.zeros((RES, RES), np.int32)
        overlaps = defaultdict(set)
        rows = []
        for k, faces in enumerate(isl, 1):
            a3 = a2 = 0.0
            nsum = np.zeros(3)
            for fi in faces:
                vi = [c[0] for c in F[fi]]
                ti = [c[1] for c in F[fi]]
                hits = raster_tri(buf, T[ti], k, RES)
                for h in hits:
                    overlaps[k].add(h)
                    overlaps[h].add(k)
                A = tri_area3(V[vi])
                a3 += A
                a2 += tri_area2(T[ti])
                nsum += np.cross(V[vi[1]] - V[vi[0]], V[vi[2]] - V[vi[0]])
            vs = V[[c[0] for fi in faces for c in F[fi]]]
            dens = np.sqrt(a2 / a3) * texres / 100 if a3 > 0 else 0
            n = nsum / (np.linalg.norm(nsum) + 1e-12)
            # сколько отдельных кусков геометрии делят этот остров (общие vt → одна текстура на копиях)
            par = {}
            def fd(a):
                while par.setdefault(a, a) != a:
                    par[a] = par[par[a]]
                    a = par[a]
                return a
            for fi in faces:
                vi = [c[0] for c in F[fi]]
                for b in vi[1:]:
                    par[fd(vi[0])] = fd(b)
            comps = defaultdict(list)
            for fi in faces:
                comps[fd(F[fi][0][0])].append(fi)
            cb = []
            for fs in comps.values():
                cv = V[[c[0] for fi in fs for c in F[fi]]]
                cb.append(((cv.min(0) + cv.max(0)) / 2).round(3))
            stacked = len(comps)
            # UV-площадь против реально закрашенных пикселей: > 1 — остров лежит сам на себе (зеркало)
            cover = (buf == k).sum() / RES / RES
            self_ov = a2 / cover if cover > 0 else 0
            rows.append((k, len(faces), vs.min(0), vs.max(0), n, dens, a2, stacked, self_ov, cb))
        # картинка
        h = np.random.default_rng(3).random((len(isl) + 1, 3)) * 0.7 + 0.3
        col = (h[buf] * 255).astype(np.uint8)
        base = np.asarray(bc.resize((RES, RES))).astype(float)
        mask = buf[..., None] > 0
        out = np.where(mask, base * 0.45 + col * 0.55, base * 0.25).astype(np.uint8)
        im = Image.fromarray(out)
        d = ImageDraw.Draw(im)
        for k in range(1, len(isl) + 1):
            ys, xs = np.nonzero(buf == k)
            if len(xs):
                d.text((int(np.median(xs)) - 8, int(np.median(ys)) - 9), str(k), fill=(255, 255, 255),
                       font=font, stroke_width=2, stroke_fill=(0, 0, 0))
        im.save(os.path.join(HERE, "uv", f"{part}_islands.png"))
        ids = np.zeros((RES, RES, 3), np.uint8)
        ids[..., 0] = buf % 256
        ids[..., 1] = buf // 256
        Image.fromarray(ids).save(os.path.join(HERE, "uv", f"{part}_ids.png"))

        md += [f"## {part} ({len(F)} треуг., {len(isl)} островов, Diffuse {texres} px)", "",
               "| # | граней | где | нормаль (x,y,z) | px/см | UV % | слоёв в UV | копий геометрии (центры) | перекрытие с |",
               "|---:|---:|---|---|---:|---:|---:|---|---|"]
        for k, nf, lo, hi, n, dens, a2, stacked, self_ov, cb in rows:
            ov = ", ".join(str(x) for x in sorted(overlaps.get(k, ()))) or "—"
            cps = "1" if stacked == 1 else f"**{stacked}**: " + "; ".join(str(tuple(c)) for c in cb[:4])
            md.append(f"| {k} | {nf} | {where(lo, hi, part)} | {n[0]:+.2f},{n[1]:+.2f},{n[2]:+.2f} | "
                      f"{dens:.1f} | {a2 * 100:.1f} | {self_ov:.2f} | {cps} | {ov} |")
        md.append("")
    with open(os.path.join(HERE, "uv", "islands.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
