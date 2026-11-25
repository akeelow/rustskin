"""Проверка Sauna Mitts v1.2 по урокам §9 (25.11.2026). .venv:
  .venv/Scripts/python skins/sauna/tactical-gloves/plan_v2/review.py
Выход (plan_v2/):
  review.md          замеры: плотность и сглаженность нормалей по островам; рельеф Normal по полосам частот
                     (форма / деталь / мелочь ≤ 3 px) у оригинала, у нашей v1.2 и у 5 принятых; прорези пальцев
  atlas_compare.jpg  весь атлас (Diffuse | Normal): наш, оригинал, 5 принятых
  region_compare.jpg одни и те же места атласа крупно: костяшки, пальцы тыла, ладонь, манжета, застёжка
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
FONT = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 14)

W = Path(__file__).resolve().parents[1]
OUT = W / "plan_v2"
CACHE = Path("C:/Program Files (x86)/Steam/steamapps/workshop/content/252490")
ACC = ["3613104700", "3709631672", "3778719714", "3793827397", "3816315503"]
R = 1024
NAMES = {1: "тыл", 2: "ладонь", 3: "манжета A", 4: "манжета B", 5: "узел", 6: "пуговица", 7: "конец ремешка"}
REG = {  # (x0, y0, x1, y1) в 1024, y сверху
    "костяшки (береста, овалы)": (486, 205, 870, 538),
    "пальцы тыла (подпалины, складки)": (538, 486, 922, 768),
    "ладонь (заплата, прорези)": (100, 300, 440, 717),
    "манжета (полоса, петля)": (230, 770, 620, 1000),
    "застёжка (узел, пуговица)": (806, 832, 960, 960),
}


def load_obj():
    V, T, N, F, FT, FN = [], [], [], [], [], []
    for line in open(W / "originals" / "tactical.gloves.obj"):
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
            c = [q.split("/") for q in p[1:]]
            for j in range(1, len(c) - 1):
                tri = (c[0], c[j], c[j + 1])
                F.append([int(a[0]) - 1 for a in tri])
                FT.append([int(a[1]) - 1 for a in tri])
                FN.append([int(a[2]) - 1 for a in tri])
    return [np.array(a) for a in (V, T, N, F, FT, FN)]


def islands(FT, nT):
    par = np.arange(nT)

    def f(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    for t in FT:
        for a in t[1:]:
            par[f(a)] = f(t[0])
    roots = np.array([f(t[0]) for t in FT])
    u, cnt = np.unique(roots, return_counts=True)
    order = {r: i + 1 for i, r in enumerate(u[np.argsort(-cnt)])}
    return np.array([order[r] for r in roots])


def gblur(a, s):
    """Гауссово размытие через FFT (без scipy), a (H,W[,k])."""
    h, w = a.shape[:2]
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.rfftfreq(w)[None, :]
    g = np.exp(-2 * (np.pi * s) ** 2 * (fx ** 2 + fy ** 2))
    if a.ndim == 2:
        return np.fft.irfft2(np.fft.rfft2(a) * g, s=(h, w))
    return np.stack([np.fft.irfft2(np.fft.rfft2(a[..., k]) * g, s=(h, w)) for k in range(a.shape[2])], -1)


def mblur(n, m, s):
    return gblur(n * m[..., None], s) / np.maximum(gblur(m.astype(float), s), 1e-3)[..., None]


def nload(p):
    a = np.asarray(Image.open(p).convert("RGB").resize((R, R), Image.LANCZOS)).astype(np.float32) / 127.5 - 1
    return a / np.maximum(np.linalg.norm(a, axis=-1, keepdims=True), 1e-6)


def ang(a, b):
    return np.degrees(np.arccos(np.clip((a * b).sum(-1), -1, 1)))


def unit(a):
    return a / np.maximum(np.linalg.norm(a, axis=-1, keepdims=True), 1e-6)


def main():
    V, T, N, F, FT, FN = load_obj()
    isl = islands(FT, len(T))
    right = V[F].mean(1)[:, 0] > 0
    P, UV, NN = V[F], T[FT], unit(N[FN])
    fn = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    A3 = np.linalg.norm(fn, axis=1) / 2
    fn = unit(fn)
    A2 = np.abs(np.cross(UV[:, 1] - UV[:, 0], UV[:, 2] - UV[:, 0])) / 2
    dev = np.degrees(np.arccos(np.clip(np.einsum("tj,tkj->tk", fn, NN), -1, 1)))
    L = ["# Проверка v1.2 по урокам §9 — замеры (plan_v2/review.py, 25.11.2026)", "",
         "## 1. Плотность и нормали модели (одна правая перчатка)", "",
         "| № | остров | граней | площадь см² | px/см @1024 | мм/px | откл. vn от грани, ° медиана / 95 % / макс | ребро low-poly мм, медиана |",
         "|---|---|---:|---:|---:|---:|---|---:|"]
    for i in range(1, 8):
        m = (isl == i) & right
        a3, a2 = A3[m].sum(), A2[m].sum()
        d = np.sqrt(a2 / a3) * R / 100
        e = np.linalg.norm(P[m][:, [1, 2, 0]] - P[m], axis=2).ravel() * 1000
        dv = dev[m].ravel()
        L.append(f"| {i} | {NAMES[i]} | {m.sum()} | {a3 * 1e4:.0f} | {d:.1f} | {10 / d:.2f} | "
                 f"{np.median(dv):.1f} / {np.percentile(dv, 95):.1f} / {dv.max():.1f} | {np.median(e):.1f} |")
    # копии: левая = зеркало правой (общие UV)
    L += ["", "Копии на общей развёртке: каждая UV-вершина у двух 3D-вершин — правая и левая перчатки, зеркало по X "
          "(`uv/model.md`). Других общих развёрток внутри одной перчатки нет.", ""]

    # --- карты
    ids = np.asarray(Image.open(W / "uv" / "ids_2048.png").resize((R, R), Image.NEAREST))
    maps = {"оригинал": W / "originals" / "TacticalGloves_nrm.png",
            "наш v1.2": W / "export" / "SaunaMitts_v1.2_normal.png"}
    for a in ACC:
        maps[a] = CACHE / a / "_BumpMap0.png"
    L += ["## 2. Рельеф Normal по частотам (средний наклон, °; 1024)", "",
          "Форма — размытие σ 12 px (≈ 4 мм и крупнее: складки, подушки, накладки); деталь — σ 1.5…12 px; "
          "мелочь — то, что тоньше σ 1.5 px (≤ 3 px ≈ 1 мм: в игре на расстоянии руки рассыпается в шум).", "",
          "| карта | остров | форма | деталь | мелочь | доля мелочи в рельефе |", "|---|---|---:|---:|---:|---:|"]
    z = np.array([0, 0, 1.0])
    stats = {}
    for k, p in maps.items():
        n = nload(p)
        for i in (1, 2, 3):
            m = ids == i
            mi = m & (gblur(m.astype(float), 3) > 0.98)   # без кромки острова
            b12 = unit(mblur(n, m, 12))
            b15 = unit(mblur(n, m, 1.5))
            f_ = ang(b12, z)[mi].mean()
            d_ = ang(b15, b12)[mi].mean()
            s_ = ang(n, b15)[mi].mean()
            stats[(k, i)] = (f_, d_, s_)
            L.append(f"| {k} | {NAMES[i]} | {f_:.1f} | {d_:.1f} | {s_:.1f} | {s_ / (d_ + s_) * 100:.0f} % |")
    L.append("")

    # --- прорези между пальцами (ладонь и тыл)
    hand = (ids == 1) | (ids == 2)
    bg = ~hand
    yy, xx = np.mgrid[0:R, 0:R]
    gap = []
    for dx in range(1, 9):   # фон, у которого слева и справа на расстоянии ≤ dx — ткань кисти
        l = np.roll(hand, dx, 1)
        r_ = np.roll(hand, -dx, 1)
        gap.append(bg & l & r_)
    gw = np.zeros((R, R), int)
    for k in range(8, 0, -1):
        gw[gap[k - 1]] = 2 * k
    sl = gw > 0
    L += ["## 3. Прорези между пальцами (1024)", "",
          f"Пикселей фона, зажатых между пальцами ближе 16 px: {sl.sum()}; из них уже 8 px: {(sl & (gw <= 8)).sum()}, "
          f"уже 4 px: {(sl & (gw <= 4)).sum()}.", ""]
    dif = np.asarray(Image.open(W / "export" / "SaunaMitts_v1.2_diffuse.png").convert("RGB")).astype(float)
    if sl.any():
        L.append(f"Цвет в прорезях (отступ, тянется мип-уровнями в край пальца): медиана {np.median(dif[sl], 0).round(0)}, "
                 f"цвет войлока рядом: {np.median(dif[(ids == 2) & (gblur(sl.astype(float), 4) > 0.05)], 0).round(0)}.")
    L.append("")
    (OUT / "review.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))

    # --- листы сравнения
    skins = [("наш v1.2 (3843000799)", W / "export/SaunaMitts_v1.2_diffuse.png", maps["наш v1.2"]),
             ("оригинал Facepunch", W / "originals/TacticalGloves_bc.png", maps["оригинал"])]
    skins += [(a, CACHE / a / "_MainTex0.png", maps[a]) for a in ACC]
    S = 300
    cols = 2
    rows = (len(skins) + cols - 1) // cols
    out = Image.new("RGB", (S * 2 * cols + 10, (S + 20) * rows), (40, 40, 40))
    d = ImageDraw.Draw(out)
    cache = {}
    for k, (name, dp, np_) in enumerate(skins):
        r, c = divmod(k, cols)
        for j, p in enumerate((dp, np_)):
            im = Image.open(p).convert("RGB").resize((R, R), Image.LANCZOS)
            cache[(k, j)] = im
            out.paste(im.resize((S, S), Image.LANCZOS), (c * (2 * S + 10) + j * S, r * (S + 20) + 20))
        d.text((c * (2 * S + 10) + 4, r * (S + 20) + 4), name, fill=(255, 255, 255), font=FONT)
    out.save(OUT / "atlas_compare.jpg", quality=88)

    for rn, box in REG.items():
        w, h = box[2] - box[0], box[3] - box[1]
        sc = 260 / h
        tw = int(w * sc)
        out = Image.new("RGB", (tw * 2 * 2 + 30, (260 + 18) * ((len(skins) + 1) // 2)), (30, 30, 30))
        d = ImageDraw.Draw(out)
        for k in range(len(skins)):
            r, c = divmod(k, 2)
            y = r * 278 + 18
            for j in (0, 1):
                out.paste(cache[(k, j)].crop(box).resize((tw, 260), Image.LANCZOS), (c * (2 * tw + 30) + j * tw, y))
            d.text((c * (2 * tw + 30) + 4, y - 15), f"{skins[k][0]} — {rn}: Diffuse | Normal", fill=(255, 255, 255), font=FONT)
        key = list(REG).index(rn) + 1
        out.save(OUT / f"region_{key}.jpg", quality=88)
    print("листы готовы")


def grey_sheet():
    """Лист серых рендеров grey_normal.py: ряды — карты, столбцы — виды."""
    G = OUT / "grey"
    rows = [("none", "без карты (только сглаженная модель)"), ("orig", "оригинал Facepunch"), ("v1.2", "наш v1.2"),
            ("3778719714", "принятый 3778719714"), ("3816315503", "принятый 3816315503"),
            ("3709631672", "принятый 3709631672")]
    rows = [r for r in rows if (G / f"{r[0]}_back.png").exists()]
    views = ["back", "palm", "thumb", "knuckle"]
    S = 300
    out = Image.new("RGB", (S * len(views), (S + 20) * len(rows)), (30, 30, 30))
    d = ImageDraw.Draw(out)
    for r, (k, name) in enumerate(rows):
        for c, v in enumerate(views):
            out.paste(Image.open(G / f"{k}_{v}.png").convert("RGB").resize((S, S), Image.LANCZOS), (c * S, r * (S + 20) + 20))
        d.text((4, r * (S + 20) + 3), name + " — серый материал, только Normal (рендер Blender)", fill=(255, 255, 255),
               font=FONT)
    out.save(OUT / "grey_sheet.jpg", quality=88)
    print("grey_sheet.jpg")


if __name__ == "__main__":
    import sys
    if "--grey" in sys.argv:
        grey_sheet()
    else:
        main()
