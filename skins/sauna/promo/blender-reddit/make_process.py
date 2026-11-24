"""Картинки поста о процессе (r/blender): пары «high-poly | итог на оригинальной low-poly» с подписями,
развёртка каменки и последний кадр из игры.

Сначала рендеры (Blender): render_stove.py (--what hp и full) и render_door.py -> src/*.png.
Запуск: python skins/sauna/promo/blender-reddit/make_process.py  ->  1_*.jpg … 7_*.jpg рядом со скриптом.
Нужен Pillow.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SRC = HERE / "src"
SAUNA = HERE.parents[1]
FONT = "C:/Windows/Fonts/segoeui.ttf"
FONT_B = "C:/Windows/Fonts/segoeuib.ttf"
BG = (24, 24, 26)
FG = (235, 235, 235)
DIM = (165, 165, 170)
FOOT = "High-poly detail baked onto the original item UVs  ·  Blender renders (Cycles), not in-game"
L_HP = "HIGH-POLY  ·  {n}"
L_LO = "ORIGINAL RUST MESH ({lo}) + BAKED MAPS"

PAIRS = [  # (файл, левый, правый, кол-во граней high-poly, low-poly, заголовок)
    ("1_stove_hp_vs_final.jpg", "stove_hp_hero", "stove_full_hero", "9.4M faces", "21k tris",
     "Sauna Stove (Rust: Electric Furnace)"),
    ("2_stove_side_closeup.jpg", "stove_hp_side_close", "stove_full_side_close", "9.4M faces", "21k tris",
     "Side panel: split aspen slats, nails, knots, thermometer"),
    ("3_stove_top_closeup.jpg", "stove_hp_top_close", "stove_full_top_close", "9.4M faces", "21k tris",
     "Cooktop: chipped enamel and scale; stones sit under the vanilla burner coils"),
    ("5_door_hp_vs_final.jpg", "door_hp_front_34", "door_full_front_34", "4.2M faces", "864 tris",
     "Sauna Door (Rust: Wooden Door)"),
    ("6_door_window.jpg", "door_hp_window", "door_full_window", "4.2M faces", "864 tris",
     "Window: the palm print is painted in the texture, not modelled"),
]


def font(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def label(img, text, xy, size=30):
    d = ImageDraw.Draw(img, "RGBA")
    f = font(size, True)
    x, y = xy
    w = d.textlength(text, font=f)
    d.rectangle((x - 12, y - 8, x + w + 12, y + size + 12), fill=(0, 0, 0, 150))
    d.text((x, y), text, font=f, fill=FG)


def frame(content, title, foot=FOOT):
    """Полоса заголовка сверху и подпись снизу вокруг картинки."""
    top, bot = 84, 64
    W, H = content.size
    out = Image.new("RGB", (W, H + top + bot), BG)
    out.paste(content, (0, top))
    d = ImageDraw.Draw(out)
    d.text((28, 20), title, font=font(40, True), fill=FG)
    d.text((28, H + top + 14), foot, font=font(28), fill=DIM)
    return out


def pair(name, left, right, hp_n, lo_n, title):
    a = Image.open(SRC / f"{left}.png").convert("RGB")
    b = Image.open(SRC / f"{right}.png").convert("RGB")
    w, h = 1200, int(1200 * a.height / a.width)
    a, b = a.resize((w, h), Image.LANCZOS), b.resize((w, h), Image.LANCZOS)
    c = Image.new("RGB", (w * 2 + 8, h), BG)
    c.paste(a, (0, 0))
    c.paste(b, (w + 8, 0))
    label(c, L_HP.format(n=hp_n), (24, 22))
    label(c, L_LO.format(lo=lo_n), (w + 8 + 24, 22))
    frame(c, title).save(HERE / name, quality=92)
    print("->", name)


def uv_sheet():
    """Развёртка каменки: исходные UV Rust поверх запечённой нормали и итогового диффуза."""
    obj = SAUNA / "electric-furnace" / "originals" / "electric.furnace.obj"
    vt, faces = [], []
    for line in obj.read_text().splitlines():
        if line.startswith("vt "):
            u, v = map(float, line.split()[1:3])
            vt.append((u, v))
        elif line.startswith("f "):
            faces.append([int(p.split("/")[1]) - 1 for p in line.split()[1:]])
    S = 1500
    im = Image.open(SAUNA / "electric-furnace" / "export" / "ElectricFurnace_v3.1_diffuse.png").convert("RGB")
    im = im.resize((S, S), Image.LANCZOS)
    d = ImageDraw.Draw(im, "RGBA")
    for f in faces:
        pts = [(vt[i][0] * S, (1 - vt[i][1]) * S) for i in f]
        d.line(pts + [pts[0]], fill=(255, 255, 255, 38), width=1)
    label(im, "FINAL DIFFUSE ON RUST'S ORIGINAL UV LAYOUT", (20, 18), 28)
    frame(im, "Skins can't change the mesh or the UVs",
          "Baked at 4096, shipped at 2048  ·  thin lines = the vanilla UV islands").save(HERE / "4_stove_uv_layout.jpg", quality=92)
    print("-> 4_stove_uv_layout.jpg")


def ingame():
    im = Image.open(HERE.parent / "reddit" / "1_stove_night.jpg").convert("RGB")
    label(im, "IN-GAME  ·  Rust skin editor, night", (28, 26), 34)
    im.save(HERE / "7_stove_ingame.jpg", quality=92)
    print("-> 7_stove_ingame.jpg")


if __name__ == "__main__":
    for p in PAIRS:
        if (SRC / f"{p[1]}.png").exists() and (SRC / f"{p[2]}.png").exists():
            pair(*p)
        else:
            print("skip", p[0])
    uv_sheet()
    ingame()
