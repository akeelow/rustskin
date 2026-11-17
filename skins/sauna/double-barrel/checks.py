"""Самопроверки Sauna Shotgun по экспортированным картам (.venv): швы, отступы, общие острова, spec/gloss.

Запуск:  python checks.py [--ver v1]
Выход:   renders/checks/report.md + картинки (seams_<part>.png, specgloss_zones.png)

1. Швы: для каждого ребра, где в 3D грани соседи, а в UV — разные места (шов развёртки), берём цвет
   Diffuse по обе стороны (1.5 px внутрь каждой грани) в 5 точках; печатаем медиану и 95-й перцентиль
   разницы и рисуем худшие швы на атласе.
2. Отступы: доля пикселей в полосе 1…8 px за краем островов, которые заполнены цветом острова
   (а не пустым фоном). Пустой фон экспорта — чёрный (0,0,0); у нас он должен отсутствовать рядом с краем.
3. Общие острова: какие детали (id из bake/<part>_id.png) лежат на островах с несколькими копиями
   геометрии (uv/islands.md) — там допустимо только симметричное.
4. Spec/Gloss: средние значения по деталям.
"""
import json
import os
import sys
from collections import defaultdict

import numpy as np
from PIL import Image, ImageDraw

from split_materials import load_obj, uv_islands

HERE = os.path.dirname(os.path.abspath(__file__))
VER = sys.argv[sys.argv.index("--ver") + 1] if "--ver" in sys.argv else "v1"
OUT = os.path.join(HERE, "renders", "checks")
IDN = {1: "metal", 2: "wood", 3: "bark", 4: "twine", 5: "towel", 6: "leaf", 7: "resin", 8: "nail", 9: "fore", 10: "burn"}
PARTS = ["barrel", "main", "stock", "grip", "sights"]


def img(path, mode="RGB"):
    return np.asarray(Image.open(path).convert(mode)).astype(np.float32)


def sample(a, uv):
    h, w = a.shape[:2]
    x = np.clip((uv[..., 0] * w - 0.5).round().astype(int), 0, w - 1)
    y = np.clip(((1 - uv[..., 1]) * h - 0.5).round().astype(int), 0, h - 1)
    return a[y, x]


def seams(part, diff):
    V, T, N, F = load_obj(os.path.join(HERE, "source", "parts", f"{part}.obj"))
    # вершины по положению (OBJ может дублировать вершины на швах)
    key = {}
    vid = [key.setdefault(tuple(np.round(v, 5)), len(key)) for v in V]
    edges = defaultdict(list)
    for fi, f in enumerate(F):
        for i in range(3):
            a, b = f[i], f[(i + 1) % 3]
            k = tuple(sorted((vid[a[0]], vid[b[0]])))
            # uv в порядке возрастания id вершины
            ua, ub = (T[a[1]], T[b[1]]) if vid[a[0]] < vid[b[0]] else (T[b[1]], T[a[1]])
            c = T[[x[1] for x in f]].mean(0)
            edges[k].append((ua, ub, c))
    h, w = diff.shape[:2]
    res = []
    for k, lst in edges.items():
        if len(lst) != 2:
            continue
        (a1, b1, c1), (a2, b2, c2) = lst
        if np.allclose(a1, a2, atol=1e-5) and np.allclose(b1, b2, atol=1e-5):
            continue  # не шов
        L1 = np.linalg.norm((b1 - a1) * [w, h])
        if L1 < 3:
            continue
        ts = np.linspace(0.15, 0.85, 5)[:, None]
        p1 = a1 + (b1 - a1) * ts
        p2 = a2 + (b2 - a2) * ts

        def inward(p, a, b, c):
            d = (b - a) * [w, h]
            nrm = np.array([-d[1], d[0]]) / (np.linalg.norm(d) + 1e-9)
            if np.dot((c - a) * [w, h], nrm) < 0:
                nrm = -nrm
            return p + nrm * 1.5 / np.array([w, h])
        s1 = sample(diff, inward(p1, a1, b1, c1))
        s2 = sample(diff, inward(p2, a2, b2, c2))
        dif = np.abs(s1 - s2).mean(-1).mean()
        res.append((dif, a1, b1, a2, b2))
    return res


def padding(part, diff):
    ids = img(os.path.join(HERE, "uv", f"{part}_ids.png"))
    m = (ids[..., 0] + ids[..., 1]) > 0
    if part == "barrel":
        s = img(os.path.join(HERE, "uv", "shell_ids.png"))
        m = m | ((s[..., 0] + s[..., 1]) > 0)
    S = diff.shape[0]
    m = np.asarray(Image.fromarray(m.astype(np.uint8) * 255).resize((S, S), Image.NEAREST)) > 127
    ring = m.copy()
    for _ in range(8):
        ring = ring | np.roll(ring, 1, 0) | np.roll(ring, -1, 0) | np.roll(ring, 1, 1) | np.roll(ring, -1, 1)
    band = ring & ~m
    empty = diff[..., :3].max(-1) < 2  # чистый чёрный фон
    return float(1 - (empty & band).sum() / max(band.sum(), 1)), int(band.sum())


def main():
    os.makedirs(OUT, exist_ok=True)
    rep = [f"# Самопроверки Sauna Shotgun {VER} (checks.py)", ""]
    rep += ["## 1. Швы развёртки (разница Diffuse по обе стороны шва, 0–255)", "",
            "| часть | швов | медиана | 95 % | худший | где худший (UV) |", "|---|---:|---:|---:|---:|---|"]
    for part in PARTS:
        p = os.path.join(HERE, "export", f"DoubleBarrel_{VER}_{part}_diffuse.png")
        diff = img(p)
        r = seams(part, diff)
        if not r:
            continue
        d = np.array([x[0] for x in r])
        worst = max(r, key=lambda x: x[0])
        rep.append(f"| {part} | {len(r)} | {np.median(d):.1f} | {np.percentile(d, 95):.1f} | {worst[0]:.1f} | "
                   f"({worst[1][0]:.3f},{worst[1][1]:.3f}) |")
        im = Image.fromarray(diff.astype(np.uint8)).convert("RGB")
        dr = ImageDraw.Draw(im)
        S = im.size[0]
        for dif, a1, b1, a2, b2 in sorted(r, key=lambda x: -x[0])[:40]:
            col = (255, 0, 255) if dif > 25 else (255, 200, 0)
            for a, b in ((a1, b1), (a2, b2)):
                dr.line([(a[0] * S, (1 - a[1]) * S), (b[0] * S, (1 - b[1]) * S)], fill=col, width=2)
        im.save(os.path.join(OUT, f"seams_{part}.png"))
    rep += ["", "Пурпурным на `seams_<часть>.png` — швы с разницей > 25, жёлтым — остальные из 40 худших.", ""]

    rep += ["## 2. Отступы (полоса 8 px за краем островов, в размере экспорта)", "",
            "| часть | размер | заполнено | пикселей в полосе |", "|---|---:|---:|---:|"]
    for part in PARTS:
        p = os.path.join(HERE, "export", f"DoubleBarrel_{VER}_{part}_diffuse.png")
        diff = img(p)
        f, nb = padding(part, diff)
        rep.append(f"| {part} | {diff.shape[0]} | {f * 100:.1f} % | {nb} |")
    rep.append("")

    rep += ["## 3. Детали на общих островах (несколько копий геометрии с одними UV)", ""]
    md = open(os.path.join(HERE, "uv", "islands.md"), encoding="utf-8").read()
    for part in ["barrel", "main", "stock", "grip"]:
        sec = md.split(f"## {part} ")[1].split("\n## ")[0]
        stacked = []
        for line in sec.splitlines():
            c = [x.strip() for x in line.split("|")]
            if len(c) > 8 and c[1].isdigit() and c[8].startswith("**"):
                stacked.append(int(c[1]))
        ids = img(os.path.join(HERE, "bake", f"{part}_id.png"))[..., 0]
        S = ids.shape[0]
        idv = np.round((ids - 8) / 16).astype(int)
        isl = img(os.path.join(HERE, "uv", f"{part}_ids.png"))
        isl = np.asarray(Image.fromarray(isl.astype(np.uint8)).resize((S, S), Image.NEAREST)).astype(int)
        isl = isl[..., 0] + isl[..., 1] * 256
        found = defaultdict(int)
        for k in stacked:
            m = isl == k
            for i in np.unique(idv[m]):
                if i in IDN and IDN[i] not in ("metal",):
                    found[(k, IDN[i])] += int((idv[m] == i).sum())
        rep.append(f"- **{part}**: общих островов {len(stacked)} ({', '.join(map(str, stacked)) or '—'}); "
                   + ("детали на них: " + ", ".join(f"остров {k} — {n} ({c} px)" for (k, n), c in sorted(found.items()))
                      if found else "деталей на них нет (только железо)"))
    rep.append("")

    rep += ["## 4. Spec/Gloss по деталям (0–255; RGB — блик, A — глянец)", "",
            "| часть | деталь | spec | gloss |", "|---|---|---:|---:|"]
    for part in ["barrel", "main", "stock", "grip"]:
        sg = img(os.path.join(HERE, "export", f"DoubleBarrel_{VER}_{part}_specgloss.png"), "RGBA")
        S = sg.shape[0]
        ids = np.asarray(Image.open(os.path.join(HERE, "bake", f"{part}_id.png")).convert("RGB").resize((S, S), Image.NEAREST))[..., 0].astype(int)
        idv = np.round((ids - 8) / 16).astype(int)
        for i, n in IDN.items():
            m = idv == i
            if m.sum() < 30:
                continue
            rep.append(f"| {part} | {n} | {sg[..., 0][m].mean():.0f} | {sg[..., 3][m].mean():.0f} |")
    rep.append("")
    open(os.path.join(OUT, "report.md"), "w", encoding="utf-8").write("\n".join(rep) + "\n")
    print("\n".join(rep))


if __name__ == "__main__":
    main()
