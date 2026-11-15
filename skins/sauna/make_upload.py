"""Sauna: one folder per item with exactly the Steam page pictures, numbered in upload order.

  .venv/Scripts/python skins/sauna/make_upload.py
Writes skins/sauna/upload/<NN item>/<NN>_<name>.jpg (copies; the folder is git-ignored, rebuild any time).
The order here is the one in PUBLISH.md: the first picture is the cover of the page's gallery.
"""
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "upload"

ITEMS = [
    ("1 Sauna Stove", "electric-furnace", [
        "ingame/front_night", "studio", "ingame/three_quarter_night", "ingame/three_quarter_day", "ingame/top_day",
        "ingame/top_night", "hero", "night", "firebox", "burners", "back"]),
    ("2 Sauna Bench", "bed", [
        "hero", "ingame/three_quarter_day", "ingame/headrest_day", "ingame/foot_day", "towel", "side", "foot", "dusk"]),
    ("3 Sauna Chair", "chair", [
        "hero", "ingame/three_quarter_day", "ingame/side_day", "ingame/back_day", "towel", "seat", "back", "dusk", "set"]),
    ("4 Sauna Stone Box", "wood-storage-box", [
        "ingame/top_night", "studio", "ingame/top_day", "ingame/three_quarter_day", "hero", "night", "top", "row", "set"]),
    ("5 Sauna Changing Locker", "locker", [
        "ingame/front_night", "studio", "ingame/front_day", "ingame/three_quarter_day", "ingame/three_quarter_night",
        "door", "hero", "night", "set"]),
    ("6 Sauna Towel Wrap", "burlap-headwrap", [
        "ingame/front_day", "hero", "ingame/side_day", "ingame/three_quarter_night", "front", "side", "set"]),
    ("7 Sauna Robe", "snow-jacket", [
        "ingame/three_quarter_day", "hero", "ingame/back_day", "back", "belt", "set"]),
]


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    for title, folder, pics in ITEMS:
        dst = OUT / title
        dst.mkdir(parents=True)
        for i, p in enumerate(pics, 1):
            src = HERE / folder / "workshop" / f"{p}.jpg"
            name = ("game_" if p.startswith("ingame/") else "render_") + p.split("/")[-1]
            shutil.copy2(src, dst / f"{i:02d}_{name}.jpg")
        print(f"{title}: {len(pics)} pictures")
    shutil.copy2(HERE / "workshop" / "collection.jpg", OUT / "collection.jpg")
    print("->", OUT)


if __name__ == "__main__":
    main()
