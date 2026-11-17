"""Классы граней приклада и рукояти по оригинальной текстуре (у Facepunch под ними своя рельефная деталь):
cloth — крестовая обмотка тканью (выпуклая полоса), metal — красные уголки затыльника, wood — остальное.
Запуск (.venv): python classify_stock.py → uv/faces_<part>_class.json (класс на грань OBJ, порядок граней OBJ)."""
import colorsys
import json
import os

import numpy as np
from PIL import Image

from split_materials import load_obj

HERE = os.path.dirname(os.path.abspath(__file__))


def classify(part):
    V, T, N, F = load_obj(os.path.join(HERE, "source", "parts", f"{part}.obj"))
    bc = np.asarray(Image.open(os.path.join(HERE, "originals", f"{part}_bc.png")).convert("RGB")).astype(float) / 255
    h, w = bc.shape[:2]
    out, cnt = [], {}
    for f in F:
        uv = T[[c[1] for c in f]]
        c = uv.mean(0)
        pts = [c] + [c + (p - c) * 0.6 for p in uv]
        cols = []
        for u, v in pts:
            x = int(np.clip(u * w, 0, w - 1))
            y = int(np.clip((1 - v) * h, 0, h - 1))
            cols.append(bc[y, x])
        r, g, b = np.median(cols, 0)
        hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
        if r > g + 0.12 and r > b + 0.12 and r > 0.25:
            k = "metal"           # красная краска по железу
        elif ss < 0.13 and ll > 0.27:   # ткань: серая, почти без насыщенности (дерево s > 0.18)
            k = "cloth"           # серо-розовая ткань
        else:
            k = "wood"
        out.append(k)
        cnt[k] = cnt.get(k, 0) + 1
    json.dump(out, open(os.path.join(HERE, "uv", f"faces_{part}_class.json"), "w"))
    print(part, cnt)


if __name__ == "__main__":
    for p in ("stock", "grip"):
        classify(p)
