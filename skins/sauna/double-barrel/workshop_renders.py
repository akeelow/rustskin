"""Картинки для страницы Workshop (Blender-рендеры, 1920×1080, JPG) — через gun_view.py.

Запуск (.venv):  python workshop_renders.py [--ver v1]
Выход: workshop/hero.jpg, workshop/detail.jpg, workshop/set.jpg
Это рендеры Blender: подписывать как рендеры, не выдавать за игровые кадры (главный кадр — из игры).
"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_renders import HERE, parts, run  # noqa: E402

VER = sys.argv[sys.argv.index("--ver") + 1] if "--ver" in sys.argv else "v1"
W = os.path.join(HERE, "workshop")
SHOTS = {
    # +x — левый бок стрелка: лист, узел, орнамент
    "hero": (parts(), ["--cam", "1.05,0.32,0.42:0,-0.06,-0.01:50"], "studio"),
    "detail": (parts(), ["--cam", "0.36,0.05,0.40:0.0,-0.035,0.21:50"], "studio"),
    "set": (parts(off=(0.62, 0.62, 0.0)) + ["--part", os.path.join(HERE, "..", "chair", "originals", "chair.obj")
                                            + "=" + os.path.join(HERE, "..", "chair", "export", "Chair_v1.4")],
            ["--cam", "1.9,1.0,1.1:0.35,0.55,0:50"], "night"),
}


def main():
    os.makedirs(W, exist_ok=True)
    for name, (pp, cam, light) in SHOTS.items():
        tmp = os.path.join(W, f"_{name}.png")
        run(pp + ["--views", "none"] + cam + ["--sheet", tmp, "--light", light, "--size", "1080", "--aspect", "1.7778"])
        Image.open(tmp).convert("RGB").save(os.path.join(W, f"{name}.jpg"), quality=92)
        os.remove(tmp)
        print(name, flush=True)


if __name__ == "__main__":
    main()
