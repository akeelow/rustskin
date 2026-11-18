"""Тест: какой размер карт редактор Rust держит у Bucket Helmet (2048 или 1024; AO — 1024 или 256).

Запуск (.venv):  python skins/sauna/bucket-helmet/test_slotsize.py
Пишет export/test_slotsize_diffuse.png (2048) и export/test_slotsize_occlusion.png (1024).

Что видно на ведре (стенка, по кругу): три пояса полос, сверху вниз — полосы по 1, 2 и 4 пикселя.
  Diffuse держится в 2048 → видны все три пояса;   ужат до 1024 → верхний пояс ровно серый.
Occlusion (тёмные полосы на светлом, низ стенки): пояса по 1, 2, 4, 8 пикселей.
  держится в 1024 → видны все четыре;   ужат до 512 → верхний серый;   до 256 → два верхних серые.
Без букв и цифр — число поясов читается и так.
"""
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "export")


def bands(size, top_frac, widths, band_h, lo, hi):
    a = np.full((size, size), hi, np.uint8)
    y0 = int(top_frac * size)
    for k, w in enumerate(widths):
        ys = np.arange(y0 + k * band_h, y0 + (k + 1) * band_h - band_h // 6)
        for y in ys:
            if ((y - y0) // w) % 2 == 0:
                a[y, :] = lo
    return a


def main():
    os.makedirs(OUT, exist_ok=True)
    # стенка снаружи — нижняя половина атласа (v 0.02…0.52, строки 490…1000 при 1024)
    d = bands(2048, 0.50, (1, 2, 4), 2048 // 9, 40, 215)
    rgba = np.dstack([d, d, d, np.full_like(d, 255)])
    Image.fromarray(rgba, "RGBA").save(os.path.join(OUT, "test_slotsize_diffuse.png"))
    o = bands(1024, 0.50, (1, 2, 4, 8), 1024 // 9, 60, 255)
    Image.fromarray(o, "L").save(os.path.join(OUT, "test_slotsize_occlusion.png"))
    print("ok")


if __name__ == "__main__":
    main()
