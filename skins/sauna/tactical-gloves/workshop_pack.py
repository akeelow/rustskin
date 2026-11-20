"""Sauna Mitts: картинки для страницы Workshop в одну папку (.venv).

python skins/sauna/tactical-gloves/workshop_pack.py
1. Кадры из редактора (F12, папка скриншотов Steam) → workshop/ingame/*.jpg: панель редактора снизу и язычок меню
   слева обрезаны по 16:9, 1920×1080. Исходники копируются в screenshots/editor_f12/.
2. Рендеры Blender v1.2 → workshop/*.jpg.
3. Всё вместе в порядке загрузки → skins/sauna/upload/12 Sauna Mitts/NN_*.jpg (+ textures/ — карты v1.2 для
   редактора). Папка upload в .gitignore — её можно пересобрать в любой момент.
"""
import shutil
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
STEAM = Path("C:/Program Files (x86)/Steam/userdata/48390285/760/remote/252490/screenshots")
VER = "v1.2"
UPLOAD = HERE.parent / "upload" / "12 Sauna Mitts"

# кадры F12 20.11.2026 (v1.2, день) — по времени съёмки
GAME = [("20261120213813_1.jpg", "back_day"), ("20261120213825_1.jpg", "side_day"),
        ("20261120213831_1.jpg", "palm_q34_day"), ("20261120213838_1.jpg", "palm_day")]
CROP = (90, 0, 1832, 980)   # без панели редактора (снизу с y ≈ 990) и язычка меню (слева x < 20); 16:9

# крупные планы бересты и застёжки на страницу не идут: под скользящим светом береста — серая графика, на застёжке
# видна плоская кромка нахлёста ремешка (остров 7)
RENDERS = [("fp_day", "fp_render"), ("view_back", "back"), ("view_palm", "palm"), ("robe_back", "set")]

# порядок на странице: кадры из игры первыми (главный — тыл), затем рендеры
ORDER = [("game", "back_day"), ("game", "palm_day"), ("game", "side_day"), ("game", "palm_q34_day"),
         ("render", "back"), ("render", "palm"), ("render", "set"), ("render", "fp_render")]


def main():
    ing = HERE / "workshop" / "ingame"
    ing.mkdir(parents=True, exist_ok=True)
    raw = HERE / "screenshots" / "editor_f12"
    raw.mkdir(parents=True, exist_ok=True)
    for src, name in GAME:
        shutil.copy2(STEAM / src, raw / f"{VER}_{name}.jpg")
        im = Image.open(STEAM / src).convert("RGB").crop(CROP).resize((1920, 1080), Image.LANCZOS)
        im.save(ing / f"{name}.jpg", quality=93)
    for src, name in RENDERS:
        im = Image.open(HERE / "renders" / f"{VER}_{src}.png").convert("RGB")
        im.save(HERE / "workshop" / f"{name}.jpg", quality=93)
    if UPLOAD.exists():
        shutil.rmtree(UPLOAD)
    (UPLOAD / "textures").mkdir(parents=True)
    for i, (kind, name) in enumerate(ORDER, 1):
        src = (ing if kind == "game" else HERE / "workshop") / f"{name}.jpg"
        shutil.copy2(src, UPLOAD / f"{i:02d}_{kind}_{name}.jpg")
    for k in ("diffuse", "normal", "specgloss", "occlusion", "fuzz"):
        shutil.copy2(HERE / "export" / f"SaunaMitts_{VER}_{k}.png", UPLOAD / "textures")
    for p in sorted(UPLOAD.rglob("*")):
        if p.is_file():
            print(p.relative_to(UPLOAD.parent))


if __name__ == "__main__":
    main()
