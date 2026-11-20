"""Тест: какой размер карт редактор Rust держит у Tactical Gloves (2048 или ужимает до 1024).

Запуск (.venv):  python skins/sauna/tactical-gloves/test_slotsize.py
Пишет export/Test_slotsize_{diffuse,occlusion,fuzz}.png — все 2048.

Diffuse: тыл кисти и пальцы (остров тыла, правая половина атласа) — три пояса полос поперёк пальцев,
сверху (у запястья) вниз: полосы по 1, 2 и 4 пикселя.
  держится 2048 → видны все три пояса;  ужат до 1024 → верхний пояс (у запястья) ровно серый.
Ладонь (левая половина атласа) — те же пояса, но в Occlusion (тёмное на белом, Diffuse там светло-серый):
  держится 2048 → видны три пояса;  1024 → верхний серый;  512 → два верхних серые.
Fuzz Mask: белый на тыле, чёрный на ладони; ползунок Fuzz поставить 1.0 — тыл станет бархатным, ладонь нет.
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
    bands(d, int(0.455 * N), N, int(0.04 * N), (1, 2, 4), int(0.20 * N), 40)
    Image.fromarray(np.dstack([d, d, d, np.full_like(d, 255)]), "RGBA").save(os.path.join(OUT, "Test_slotsize_diffuse.png"))
    o = np.full((N, N), 255, np.uint8)
    bands(o, 0, int(0.452 * N), int(0.04 * N), (1, 2, 4), int(0.20 * N), 60)
    Image.fromarray(o, "L").save(os.path.join(OUT, "Test_slotsize_occlusion.png"))
    f = np.zeros((N, N), np.uint8)
    f[:, int(0.455 * N):] = 255
    Image.fromarray(f, "L").save(os.path.join(OUT, "Test_slotsize_fuzz.png"))
    print("ok")


if __name__ == "__main__":
    main()
