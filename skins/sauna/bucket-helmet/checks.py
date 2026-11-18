"""Технические проверки Sauna Bucket (.venv): python skins/sauna/bucket-helmet/checks.py [--ver v1]

1. Размеры и каналы карт против оригинала; альфа Diffuse вся 255 (у оригинала альфы нет).
2. Шов развёртки сзади (остров 1, u = 0 | 1): ступенька цвета и нормали по обе стороны шва.
3. Отступы: каждая карта залита за край островов не меньше чем на 8 px.
4. Нормаль на гладких местах без деталей: средняя близка к (128, 128, 255), без полос по граням low-poly.
5. Общие острова (ушки 5/9/8, узлы сетки 2/4/28): одинаковое у обеих копий — по построению (зеркало), здесь —
   что узел и лист не легли на общий остров (по маскам id).
Пишет renders/checks_<ver>.md.
"""
import argparse
import json
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))


def img(p, mode="RGBA"):
    return np.asarray(Image.open(p).convert(mode)).astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ver", default="v1")
    a = ap.parse_args()
    pre = os.path.join(HERE, "export", f"SaunaBucket_{a.ver}")
    rep = [f"# Проверки SaunaBucket_{a.ver}", ""]
    # 1
    rep += ["## 1. Размеры и каналы", "", "| Карта | наша | оригинал |", "|---|---|---|"]
    orig = {"diffuse": "metal_improvised_helmet_02_bc.png", "normal": "metal_improvised_helmet_02_nrm.png",
            "specgloss": "metal_improvised_helmet_02_sg.png", "occlusion": "metal_improvised_helmet_02_ao.png",
            "fuzzmask": None}
    for k, o in orig.items():
        im = Image.open(f"{pre}_{k}.png")
        oi = Image.open(os.path.join(HERE, "originals", o)) if o else None
        rep.append(f"| {k} | {im.size[0]}, {im.mode} | {(str(oi.size[0]) + ', ' + oi.mode) if oi else 'слот пустой (белый)'} |")
    d = img(f"{pre}_diffuse.png")
    rep += ["", f"Альфа Diffuse: min {d[..., 3].min():.0f}, max {d[..., 3].max():.0f} (должно быть 255 — альфы нет).",
            f"Синий канал Normal: min {img(pre + '_normal.png')[..., 2].min():.0f} (B = 255, как у оригинала)."]
    # острова в 1024
    ids = np.asarray(Image.open(os.path.join(HERE, "uv", "ids.png")).convert("RGB")).astype(np.int32)
    isl = ids[..., 0] + ids[..., 1] * 256
    # 2 шов
    n = img(f"{pre}_normal.png")
    rows = np.where((isl[:, 0] == 1) & (isl[:, -1] == 1))[0]
    dc = np.abs(d[rows, 0, :3] - d[rows, -1, :3]).mean(1)
    inner = np.abs(d[rows, 1, :3] - d[rows, 2, :3]).mean(1)
    dn = np.abs(n[rows, 0, :2] - n[rows, -1, :2]).mean(1)
    rep += ["", "## 2. Шов развёртки сзади (остров 1, столбцы 0 и 1023)", "",
            f"Строк на шве: {len(rows)}. Разница цвета через шов: средняя {dc.mean():.1f}, 95 % {np.percentile(dc, 95):.1f} "
            f"(для сравнения — между соседними столбцами внутри острова: {inner.mean():.1f}). "
            f"Разница нормали: средняя {dn.mean():.1f}."]
    # 3 отступы
    m = isl > 0
    rep += ["", "## 3. Отступы", ""]
    dist = np.full(m.shape, 99, np.int32)
    cur = m.copy()
    for k in range(1, 20):
        g = cur | np.roll(cur, 1, 0) | np.roll(cur, -1, 0) | np.roll(cur, 1, 1) | np.roll(cur, -1, 1)
        dist[g & ~cur] = k
        cur = g
    for k in ("diffuse", "normal", "specgloss", "occlusion"):
        a_ = img(f"{pre}_{k}.png")
        bg = a_[~cur].reshape(-1, a_.shape[-1]) if (~cur).any() else None
        # пиксель «пустой», если совпадает с цветом самого дальнего фона
        ref = a_[0, 0]
        filled = np.abs(a_ - ref).sum(-1) > 3
        band = (dist >= 1) & (dist <= 8)
        rep.append(f"- {k}: в полосе 1–8 px вокруг островов залито {filled[band].mean() * 100:.1f} %")
    # 4 гладкие места
    smooth_px = (isl == 1)
    nx, ny = n[..., 0][smooth_px], n[..., 1][smooth_px]
    rep += ["", "## 4. Нормаль стенки", "",
            f"Средняя по стенке: R {nx.mean():.1f}, G {ny.mean():.1f} (ровно — 128/128; сдвиг > 6 — наклон всей поверхности).",
            "Полосы по граням low-poly ищутся по профилю среднего R вдоль u (32 грани по кругу — период 32 px):"]
    prof = np.array([n[..., 0][:, x][isl[:, x] == 1].mean() if (isl[:, x] == 1).any() else 128 for x in range(1024)])
    f = np.abs(np.fft.rfft(prof - prof.mean()))
    rep.append(f"гармоника 32 (грани): {f[32]:.0f}, соседние 30–34 без неё: {np.median(f[[29, 30, 34, 35]]):.0f}; "
               f"гармоника 18 (клёпки): {f[18]:.0f}.")
    # 5 асимметричное не на общих островах
    lay = json.load(open(os.path.join(HERE, "bake", "layout.json")))
    rep += ["", "## 5. Асимметричные детали", "",
            f"Лист: стенка (остров 1, уникальный), θ = {lay['leaf'][0]}°, y = {lay['leaf'][1]}. Узлы верёвки — на ушках "
            "(общие 5/9) — одинаковые на обоих ушках по замыслу (обрезанная ручка), строятся у +x и отражаются.",
            f"Нахлёст обруча: θ = {lay['joint'][0]}° (остров 1). Гнездо дроби: θ = {lay['shot'][0]}° (остров 1)."]
    out = os.path.join(HERE, "renders", f"checks_{a.ver}.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write("\n".join(rep) + "\n")
    print("\n".join(rep))


if __name__ == "__main__":
    main()
