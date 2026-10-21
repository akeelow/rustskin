"""Concept board: the viewer.py sheets of the original and each concept side by side, with the 128 px
icon test (3/4 view at icon size) and the night row of six.

    .venv/Scripts/python skins/sauna/wood-storage-box/concept_board.py
Reads renders/{orig,concept_*}_sheet.png and concept_*_row6.png, writes renders/concept_board.png.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

R = Path(__file__).resolve().parent / "renders"
CELL = 512                      # viewer.py sheet: 6 columns x (day, night) of 512 px
ROWS = [("orig", "ванила"), ("concept_A", "A · ушат"), ("concept_B", "B · короб для веников"),
        ("concept_C", "C · ящик у каменки"), ("concept_C_slots", "C + свечение 1 · ручки и щели"),
        ("concept_C_corner", "C + свечение 2 · тлеющий угол"), ("concept_C_grate", "C + свечение 3 · поддувало"),
        ("concept_D", "D (мой) · ящик для камней"), ("concept_D_open", "D · вся крышка прозрачная"),
        ("concept_D_slot", "D · снята одна доска")]
SHOW = 300


def cell(sheet, col, night):
    return sheet.crop((col * CELL, night * CELL, (col + 1) * CELL, (night + 1) * CELL))


def main():
    font = ImageFont.truetype("arial.ttf", 22)
    heads = ["3/4 день", "3/4 ночь", "сверху", "спереди ночью", "иконка 128", "ряд из 6, ночь"]
    widths = [SHOW, SHOW, SHOW, SHOW, 150, SHOW * 2]
    board = Image.new("RGB", (220 + sum(widths), 40 + SHOW * len(ROWS)), (28, 28, 30))
    d = ImageDraw.Draw(board)
    x = 220
    for h, w in zip(heads, widths):
        d.text((x + 8, 10), h, fill=(230, 230, 230), font=font)
        x += w
    for r, (name, label) in enumerate(ROWS):
        y = 40 + r * SHOW
        d.text((10, y + SHOW // 2), label, fill=(240, 200, 120), font=font, anchor="lm") if len(label) < 18 else \
            d.multiline_text((10, y + SHOW // 2 - 30), label.replace(" · ", "\n"), fill=(240, 200, 120), font=font)
        sheet = Image.open(R / f"{name}_sheet.png").convert("RGB")
        tiles = [cell(sheet, 1, 0), cell(sheet, 1, 1), cell(sheet, 4, 0), cell(sheet, 0, 1)]
        x = 220
        for t in tiles:
            board.paste(t.resize((SHOW, SHOW), Image.LANCZOS), (x, y))
            x += SHOW
        icon = cell(sheet, 1, 0).crop((40, 60, 472, 492)).resize((128, 128), Image.LANCZOS)
        board.paste(icon, (x + 11, y + (SHOW - 128) // 2))
        x += 150
        row = R / f"{name}_row6.png"
        if row.exists():
            rs = Image.open(row).convert("RGB")
            board.paste(cell(rs, 1, 1).resize((SHOW, SHOW), Image.LANCZOS), (x, y))
            board.paste(cell(rs, 5, 1).resize((SHOW, SHOW), Image.LANCZOS), (x + SHOW, y))
    board.save(R / "concept_board.png")
    print("wrote", R / "concept_board.png")


if __name__ == "__main__":
    main()
