"""Sauna: bring the user's F12 editor screenshots from Steam into the repo (see SHOOTING.md).

  .venv/Scripts/python skins/sauna/ingame_import.py list --since 2026-11-15T12:00
      copies every Steam screenshot of Rust taken since then into skins/sauna/_inbox/ (raw, Steam names)
      and writes _inbox/contact.jpg (numbered thumbnails) to sort them by eye
  .venv/Scripts/python skins/sauna/ingame_import.py place <inbox file> <item folder> <shot name>
      e.g. place 20261115123001_1.jpg electric-furnace front_night
      raw   -> <item>/screenshots/editor_16x9/<shot>.jpg   (as shot, editor bars included)
      clean -> <item>/workshop/ingame/<shot>.jpg           (16:9 crop clear of the editor bars, 1920x1080)
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
INBOX = HERE / "_inbox"
STEAM = Path("C:/Program Files (x86)/Steam/userdata/48390285/760/remote/252490/screenshots")  # 252490 = Rust
# the editor's bottom toolbar and sky/time sliders start at y ~985 and its panel tab sits at x < 40 (1920x1080):
# keep the largest 16:9 window above the toolbar, centred
CROP = (93, 0, 1826, 975)


def stamp(p):
    try:
        return datetime.strptime(p.stem.split("_")[0], "%Y%m%d%H%M%S")
    except ValueError:
        return datetime.fromtimestamp(p.stat().st_mtime)


def cmd_list(since):
    INBOX.mkdir(exist_ok=True)
    shots = sorted((p for p in STEAM.glob("*.jpg") if stamp(p) >= since), key=stamp)
    for p in shots:
        shutil.copy2(p, INBOX / p.name)
    print(len(shots), "screenshots ->", INBOX)
    if not shots:
        return
    cols, w, h = 4, 480, 270
    rows = (len(shots) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * (h + 22)), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    try:
        f = ImageFont.truetype("arial.ttf", 15)
    except OSError:
        f = ImageFont.load_default()
    for i, p in enumerate(shots):
        im = Image.open(p).convert("RGB").resize((w, h))
        x, y = (i % cols) * w, (i // cols) * (h + 22)
        sheet.paste(im, (x, y + 22))
        d.text((x + 4, y + 3), f"{i + 1}. {p.name}", fill=(255, 220, 120), font=f)
    sheet.save(INBOX / "contact.jpg", quality=85)
    print("contact sheet:", INBOX / "contact.jpg")


def cmd_place(name, item, shot):
    src = INBOX / name if (INBOX / name).exists() else STEAM / name
    raw = HERE / item / "screenshots" / "editor_16x9" / f"{shot}.jpg"
    clean = HERE / item / "workshop" / "ingame" / f"{shot}.jpg"
    raw.parent.mkdir(parents=True, exist_ok=True)
    clean.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, raw)
    im = Image.open(src).convert("RGB")
    if im.size == (1920, 1080):
        im = im.crop(CROP).resize((1920, 1080), Image.LANCZOS)
    im.save(clean, quality=92)
    print(src.name, "->", raw.relative_to(HERE), "+", clean.relative_to(HERE))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "list":
        cmd_list(datetime.fromisoformat(a[a.index("--since") + 1]) if "--since" in a else datetime.min)
    elif a and a[0] == "place" and len(a) == 4:
        cmd_place(*a[1:])
    else:
        print(__doc__)
