"""Sauna Boiler v4.4: кадры из редактора (режим предпросмотра, F12) -> workshop/upload_v4/ для страницы Workshop.

Поверх сцены редактор рисует заголовок «SAUNA BOILER / AKEELOW» и кнопки ✔ ✖ Steam (x > 1195, y < 292), слева —
язычок панели (x < 40), внизу — панель (y > 992). Котёл высокий и стоит левее заголовка, поэтому общие кадры режутся
4:5 (x 390–1190) по всей высоте до панели; топка крупно — полосой ниже заголовка (16:9).

  .venv/Scripts/python skins/sauna/furnace/workshop_upload_v4.py
"""
import shutil
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
STEAM = Path("C:/Program Files (x86)/Steam/userdata/48390285/760/remote/252490/screenshots")
OUT = HERE / "workshop" / "upload_v4"
UPLOAD = HERE.parent / "upload" / "9 Sauna Boiler" / "v4.4"     # папка загрузки (в git не попадает)
SRC = HERE / "screenshots" / "v4.4"

# номер на странице, исходник Steam, имя, обрезка (x0, y0, x1, y1)
TALL = (390, 0, 1190, 990)                 # 4:5, котёл ближе к центру, заголовок (x > 1195) не попадает
SHOTS = (
    (1, "20261122230126_1.jpg", "front_day", TALL),
    (2, "20261122230212_1.jpg", "back_day", TALL),
    (3, "20261122230151_1.jpg", "front_night", TALL),
    (4, "20261122225432_1.jpg", "firebox_cold", (330, 296, 1550, 982)),
    (5, "20261122230331_1.jpg", "top", TALL),
)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    SRC.mkdir(parents=True, exist_ok=True)
    UPLOAD.mkdir(parents=True, exist_ok=True)
    for num, src, name, box in SHOTS:
        raw = SRC / f"{num:02d}_{src}"
        if not raw.exists():
            shutil.copy2(STEAM / src, raw)
        im = Image.open(raw).convert("RGB").crop(box)
        if box != TALL:                                   # полоса 16:9 -> 1920×1080
            im = im.resize((1920, 1080), Image.LANCZOS)
        dst = OUT / f"{num:02d}_{name}.jpg"
        im.save(dst, quality=93)
        shutil.copy2(dst, UPLOAD / dst.name)
        print(dst.name, im.size)


if __name__ == "__main__":
    main()
