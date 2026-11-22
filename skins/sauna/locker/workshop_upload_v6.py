"""Sauna Changing Locker v6.2: кадры из редактора (режим предпросмотра, F12) -> workshop/upload_v6/ (1920×1080).

Поверх сцены редактор рисует заголовок «SAUNA CHANGING LOCKER / AKEELOW», кнопки ✔ ✖ Steam (x 1040–1290, y 225–290 —
прямо над шкафом) и нижнюю панель (y > 984). Шкаф высокий, поэтому кадр режется по полосе y 292–984 (16:9, ширина 1230),
по центру шкафа, и увеличивается до 1920×1080 (Lanczos).

  .venv/Scripts/python skins/sauna/locker/workshop_upload_v6.py
"""
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
SRC = HERE / "screenshots" / "v6.2"
OUT = HERE / "workshop" / "upload_v6"
Y0, Y1 = 292, 984
W = round((Y1 - Y0) * 16 / 9)

# номер на странице, исходник, имя, центр шкафа по x
SHOTS = (
    (1, "03_20261122143035_1.jpg", "three_quarter_day", 950),
    (2, "05_20261122143107_1.jpg", "front_day", 960),
    (3, "02_20261122143025_1.jpg", "three_quarter_night", 980),
    (4, "06_20261122143114_1.jpg", "drawer_and_shelves", 1300),
    (5, "04_20261122143042_1.jpg", "back_day", 1270),
)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for n, src, name, cx in SHOTS:
        im = Image.open(SRC / src).convert("RGB")
        x0 = max(0, min(im.width - W, cx - W // 2))
        im.crop((x0, Y0, x0 + W, Y1)).resize((1920, 1080), Image.LANCZOS).save(OUT / f"{n:02d}_{name}.jpg", quality=92)
        print(f"{n:02d}_{name}.jpg  <- {src}  x {x0}..{x0 + W}, y {Y0}..{Y1}")


if __name__ == "__main__":
    main()
