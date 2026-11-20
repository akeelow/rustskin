"""Схема раскладки деталей Sauna Mitts по развёртке — только для плана (не текстура скина).

.venv:  python skins/sauna/tactical-gloves/plan_layout.py
Выход: uv/plan_layout.png (2048), его же рендерит view_orig.py --tex uv/plan_layout.png
Координаты — в пикселях превью 1024 (x вправо, y вниз), как на uv/orig_bc_1k.png.
"""
import os
from collections import Counter
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
S = 2  # 1024 -> 2048
C = dict(felt="#B3A48A", leather="#8A6646", bark="#E3DDCF", barkdark="#3a3027", linen="#CFC6B4",
         stripe="#8E3A30", burn="#45332A", soot="#2b2622", thread="#EDE6D6", twine="#C9B27C", suede="#9A7A58")


def load():
    V, T, F, FT = [], [], [], []
    for line in open(os.path.join(HERE, "originals", "tactical.gloves.obj")):
        p = line.split()
        if not p: continue
        if p[0] == "vt": T.append([float(x) for x in p[1:3]])
        elif p[0] == "f":
            FT.append([int(c.split("/")[1]) - 1 for c in p[1:]])
    return np.array(T), FT


def P(pts):
    return [(x * S, y * S) for x, y in pts]


def main():
    T, FT = load()
    im = Image.new("RGB", (2048, 2048), "#202020")
    d = ImageDraw.Draw(im)
    # 1. всё — войлок (острова рук), полотенце (манжета)
    for ft in FT:
        uv = [(T[t][0] * 2048, (1 - T[t][1]) * 2048) for t in ft]
        cy = np.mean([q[1] for q in uv])
        d.polygon(uv, fill=C["linen"] if cy > 1560 else C["felt"])
    # 2. ладонь: кожаная заплата «короной» (как на референсе) + полоса на большой палец
    d.polygon(P([(150, 140), (390, 105), (420, 300), (440, 470), (405, 470), (395, 520), (360, 525), (350, 470),
                 (300, 470), (295, 530), (255, 535), (245, 470), (210, 470), (200, 520), (165, 525), (150, 470),
                 (135, 300)]), fill=C["leather"], outline=C["thread"], width=5)
    d.polygon(P([(20, 300), (130, 255), (150, 300), (140, 360), (30, 370)]), fill=C["leather"], outline=C["thread"], width=5)
    # подушечки пальцев (ладонная сторона)
    for cx, y0, y1 in ((172, 590, 700), (248, 600, 705), (322, 590, 695), (418, 570, 668)):
        d.rounded_rectangle(P([(cx - 30, y0), (cx + 30, y1)]), radius=40, fill=C["leather"], outline=C["thread"], width=5)
    # вытертые до блеска места хвата
    for b in ((230, 300, 330, 420), (40, 290, 110, 350), (160, 640, 190, 690)):
        d.ellipse(P([b[:2], b[2:]]), fill="#a07a55")
    # 3. тыльная сторона: береста внахлёст на кожаной подложке над костяшками
    d.polygon(P([(505, 225), (830, 215), (845, 330), (820, 445), (515, 450), (495, 330)]), fill=C["suede"])
    d.polygon(P([(520, 240), (690, 228), (700, 300), (690, 430), (530, 438), (512, 330)]), fill=C["bark"],
              outline=C["thread"], width=5)
    d.polygon(P([(670, 250), (820, 236), (832, 330), (812, 425), (680, 430), (660, 330)]), fill="#d8cdb6",
              outline=C["thread"], width=5)
    rng = np.random.default_rng(4)
    for _ in range(70):  # чечевички поперёк руки
        x, y = rng.uniform(530, 815), rng.uniform(245, 425)
        L = rng.uniform(6, 18)
        d.line(P([(x, y), (x + L, y + rng.uniform(-1, 1))]), fill=C["barkdark"], width=3)
    # кожаные овалы на костяшках пальцев (поверх выпуклостей оригинала)
    for cx, cy in ((522, 455), (606, 492), (705, 500), (795, 500)):
        d.ellipse(P([(cx - 24, cy - 30), (cx + 24, cy + 30)]), fill=C["leather"], outline=C["thread"], width=4)
    # 4. подпалины и прожоги (тыльная сторона, ближе к большому пальцу и запястью)
    for cx, cy, r, hole in ((610, 150, 22, True), (560, 175, 9, False), (760, 140, 13, True), (900, 330, 16, False),
                            (640, 560, 8, True), (790, 600, 10, False)):
        d.ellipse(P([(cx - r * 1.8, cy - r * 1.5), (cx + r * 1.8, cy + r * 1.5)]), fill="#7c6a52")
        d.ellipse(P([(cx - r, cy - r * 0.8), (cx + r, cy + r * 0.8)]), fill=C["burn"])
        if hole:
            d.ellipse(P([(cx - r * 0.45, cy - r * 0.35), (cx + r * 0.45, cy + r * 0.35)]), fill="#120d0a")
    # 5. сажа на кончиках пальцев (тыл и ладонь)
    for cx, cy in ((600, 715), (705, 730), (815, 712), (505, 610), (172, 690), (248, 695), (322, 685), (418, 655), (45, 330)):
        d.ellipse(P([(cx - 32, cy - 26), (cx + 32, cy + 26)]), fill=C["soot"])
    # 6. манжета-полотенце: подгиб у краёв, двойная кирпичная полоса поперёк запястья (вдоль острова)
    for x0, x1, y0, y1 in ((17, 357, 793, 885), (17, 357, 885, 975), (369, 748, 790, 885), (369, 748, 885, 968)):
        h = y1 - y0
        d.rectangle(P([(x0, y0 + h * 0.38), (x1, y0 + h * 0.50)]), fill=C["stripe"])
        d.rectangle(P([(x0, y0 + h * 0.56), (x1, y0 + h * 0.61)]), fill=C["stripe"])
        for yy in (y0 + 6, y1 - 6):
            for xx in range(int(x0) + 4, int(x1) - 8, 14):
                d.line(P([(xx, yy), (xx + 8, yy)]), fill=C["thread"], width=3)
    # петля из бечёвки, прижатая к манжете + узел на месте застёжки (острова 5, 6)
    d.arc(P([(560, 800), (660, 880)]), 0, 360, fill=C["twine"], width=10)
    d.rectangle(P([(800, 845), (930, 900)]), fill=C["twine"])
    d.rectangle(P([(800, 775), (920, 830)]), fill="#6b5236")
    # 7. стежки по швам: граница островов рук (бока пальцев и ладони)
    edges = Counter()
    for ft in FT:
        for a, b in zip(ft, ft[1:] + ft[:1]):
            edges[(min(a, b), max(a, b))] += 1
    for (a, b), n in edges.items():
        if n == 2 and T[a][1] > 0.25 and T[b][1] > 0.25:
            pa, pb = T[a] * [2048, -2048] + [0, 2048], T[b] * [2048, -2048] + [0, 2048]
            m = (pa + pb) / 2
            dv = (pb - pa); dv = dv / (np.linalg.norm(dv) + 1e-9)
            nv = np.array([-dv[1], dv[0]]) * 7
            d.line([tuple(m - nv), tuple(m + nv)], fill=C["thread"], width=3)
    im.save(os.path.join(HERE, "uv", "plan_layout.png"))


if __name__ == "__main__":
    main()
