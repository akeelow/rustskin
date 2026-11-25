"""Тест: какой размер карт редактор Rust держит у Snow Jacket (2048 или ужимает до 1024). PLAN_v3.md, вопрос 1.

Запуск (.venv):  python skins/sauna/snow-jacket/test_slotsize.py
Пишет export/Test_slotsize_{diffuse,occlusion}.png — оба 2048 (образец — tactical-gloves/test_slotsize.py).

Diffuse: спина (остров 3, атлас u 0.51–0.86, v 0.44–1.0 сверху) — три пояса горизонтальных полос, сверху вниз
(от лопаток к подолу): полосы по 1, 2 и 4 пикселя 2048. Остальное светло-серое.
  держится 2048 → видны все три пояса;  ужат до 1024 → верхний пояс (у лопаток) ровно серый.
Перёд (остров 0, u 0.02–0.45) — те же пояса в Occlusion (тёмное на белом), если у Snow Jacket есть слот Occlusion.
Плюс подпись под слотом в редакторе («(1024…» / «(2048…») — на скриншот.
"""
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "export")
N = 2048


def bands(a, x0, x1, y0, widths, band_h, lo):
    for k, w in enumerate(widths):
        for y in range(y0 + k * band_h, y0 + (k + 1) * band_h - band_h // 6):
            if ((y - y0) // w) % 2 == 0:
                a[y, x0:x1] = lo


def main():
    os.makedirs(OUT, exist_ok=True)
    d = np.full((N, N), 200, np.uint8)
    bands(d, int(0.50 * N), int(0.87 * N), int(0.50 * N), (1, 2, 4), int(0.15 * N), 40)
    Image.fromarray(np.dstack([d, d, d, np.full_like(d, 255)]), "RGBA").save(
        os.path.join(OUT, "Test_slotsize_diffuse.png"))
    o = np.full((N, N), 255, np.uint8)
    bands(o, int(0.02 * N), int(0.46 * N), int(0.50 * N), (1, 2, 4), int(0.15 * N), 60)
    Image.fromarray(o, "L").save(os.path.join(OUT, "Test_slotsize_occlusion.png"))
    print("ok")


if __name__ == "__main__":
    main()
