"""Коллаж «все семь в игре» для постов: только кадры из редактора Rust, без рендеров.

Запуск: python skins/sauna/promo/make_collage.py  →  promo/collage_ingame.jpg (2400×1260)
Нужен Pillow (pip install --user pillow). Запускать без -I, иначе Python не увидит пользовательские пакеты.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]  # skins/sauna
OUT = Path(__file__).resolve().parent / "collage_ingame.jpg"

# (файл, подпись, рамка обрезки в пикселях 1920×1080 или None — центр 4:3)
TILES = [
    ("electric-furnace/workshop/upload_v3/02_three_quarter_night.jpg", "Sauna Stove · Electric Furnace", (140, 0, 1580, 1080)),
    ("wood-storage-box/workshop/ingame/top_night.jpg", "Sauna Stone Box · Wood Storage Box", None),
    ("locker/workshop/upload_v6/01_three_quarter_day.jpg", "Sauna Changing Locker · Locker", None),
    ("bed/workshop/upload_v2/07_dusk_v2.jpg", "Sauna Bench · Bed", (300, 300, 1340, 1080)),  # выше y=300 справа надпись редактора
    ("chair/workshop/ingame/three_quarter_day.jpg", "Sauna Chair · Chair", None),
    ("burlap-headwrap/workshop/ingame/front_day.jpg", "Sauna Towel Wrap · Burlap Headwrap", None),
    ("snow-jacket/workshop/ingame/three_quarter_day.jpg", "Sauna Robe · Snow Jacket", None),
    (None, None, None),  # плитка с названием
]
TW, TH, BAR = 600, 450, 80
COLS, ROWS = 4, 2
BG = (18, 14, 12)
FG = (235, 226, 210)
ACCENT = (255, 140, 50)


def font(size, bold=False):
    for name in (("segoeuib.ttf", "arialbd.ttf") if bold else ("segoeui.ttf", "arial.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def crop43(im, box):
    if box:
        im = im.crop(box)
    w, h = im.size
    if w / h > 4 / 3:
        nw = round(h * 4 / 3)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = round(w * 3 / 4)
        im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    return im.resize((TW, TH), Image.LANCZOS)


def fallback(path):
    """Если в ingame/ нет кадра — берём такой же из upload/ (имена там с номером и game_)."""
    p = ROOT / path
    if p.exists():
        return p
    hits = sorted(ROOT.glob(f"upload/*/*_game_{p.name}"))
    if not hits:
        raise FileNotFoundError(path)
    return hits[0]


def main():
    sheet = Image.new("RGB", (TW * COLS, (TH + BAR) * ROWS), BG)
    d = ImageDraw.Draw(sheet)
    f_label = font(26)
    for i, (path, label, box) in enumerate(TILES):
        x, y = (i % COLS) * TW, (i // COLS) * (TH + BAR)
        if path is None:
            d.text((x + TW // 2, y + 170), "SAUNA", font=font(110, True), fill=ACCENT, anchor="mm")
            d.text((x + TW // 2, y + 270), "7 skins for Rust", font=font(40), fill=FG, anchor="mm")
            d.text((x + TW // 2, y + 330), "a sauna scrap-built by a survivor", font=font(28), fill=FG, anchor="mm")
            d.text((x + TW // 2, y + TH + BAR // 2), "in-game editor shots", font=font(24), fill=(150, 140, 125), anchor="mm")
            continue
        im = Image.open(fallback(path)).convert("RGB")
        sheet.paste(crop43(im, box), (x, y))
        d.text((x + TW // 2, y + TH + BAR // 2), label, font=f_label, fill=FG, anchor="mm")
    sheet.save(OUT, quality=90)
    print(OUT, sheet.size)


if __name__ == "__main__":
    main()
