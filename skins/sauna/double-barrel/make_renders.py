"""Все проверочные рендеры Sauna Shotgun (.venv; Blender вызывается сам, без окна).

Запуск:  python make_renders.py [--ver v1]
Выход (renders/):
  <ver>_sheet.png      6 видов × день/ночь (+ <ver>_view.blend — открыть и покрутить)
  <ver>_fp.png         от первого лица, глаз с обеих сторон × день/ночь (сторона: README «Сторона»)
  <ver>_fp_grey.png    то же в ч/б — читается ли без цвета
  <ver>_icon.png       вид сбоку и он же 128 и 64 px (как иконка инвентаря)
  <ver>_grip.png       вариант с короткой рукоятью GRIP вместо приклада STOCK
  <ver>_with_chair.png двустволка на сиденье Sauna Chair (v1.4) в одном свете — сверка с сетом
Это рендеры Blender, не игровые кадры.
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BL = r"C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe"
VER = sys.argv[sys.argv.index("--ver") + 1] if "--ver" in sys.argv else "v1"
R = os.path.join(HERE, "renders")
P = os.path.join(HERE, "source", "parts")
X = os.path.join(HERE, "export", f"DoubleBarrel_{VER}")


def parts(stock="stock", off=None):
    o = "" if off is None else "@" + ",".join(str(v) for v in off)
    names = [("barrel", "barrel"), ("main", "main"), ("sights", "sights"), (stock, stock)]
    out = []
    for obj, tex in names:
        out += ["--part", f"{P}/{obj}.obj={X}_{tex}{o}"]
    return out


def run(args):
    r = subprocess.run([BL, "-b", "-P", os.path.join(HERE, "gun_view.py"), "--"] + args,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    bad = [l for l in (r.stdout + r.stderr).splitlines() if "Traceback" in l or "Error:" in l]
    if bad:
        print("\n".join(bad))


def main():
    os.makedirs(R, exist_ok=True)
    run(parts() + ["--sheet", f"{R}/{VER}_sheet.png", "--blend", f"{R}/{VER}_view.blend", "--light", "both",
                   "--size", "400", "--aspect", "2.0", "--zoom", "0.75"])
    run(parts() + ["--views", "fp", "--sheet", f"{R}/{VER}_fp.png", "--light", "both", "--size", "720", "--aspect", "1.78"])
    run(parts() + ["--views", "fp", "--sheet", f"{R}/{VER}_fp_grey.png", "--light", "day", "--grey",
                   "--size", "720", "--aspect", "1.78"])
    # иконка: строго сбоку (+x — левый бок стрелка), студийный свет
    run(parts() + ["--views", "none", "--cam", "1.5,-0.07,-0.02:0,-0.07,-0.02:50", "--sheet", f"{R}/_icon.png",
                   "--light", "studio", "--size", "512"])
    run(parts("grip") + ["--sheet", f"{R}/{VER}_grip.png", "--light", "day", "--size", "400", "--aspect", "2.0",
                         "--zoom", "0.75"])
    chair = os.path.join(HERE, "..", "chair")
    # рядом с креслом на высоте сиденья, левым боком (+x) к камере
    run(parts(off=(0.62, 0.62, 0.0)) + ["--part", f"{chair}/originals/chair.obj={chair}/export/Chair_v1.4",
                                       "--views", "none", "--cam", "1.9,1.0,1.1:0.35,0.55,0:50",
                                       "--cam", "1.7,0.75,-0.9:0.35,0.55,0:50",
                                       "--sheet", f"{R}/{VER}_with_chair.png", "--light", "both",
                                       "--size", "640", "--aspect", "1.25"])
    # иконка 128/64
    im = Image.open(f"{R}/_icon.png").convert("RGB")
    a = np.asarray(im).astype(int)
    fg = np.abs(a - a[2, 2]).sum(-1) > 12
    ys, xs = np.nonzero(fg)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    side_len = int(max(x1 - x0, y1 - y0) * 1.08)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    side = im.crop((cx - side_len // 2, cy - side_len // 2, cx + side_len // 2, cy + side_len // 2)).resize((512, 512), Image.LANCZOS)
    W = Image.new("RGB", (512 + 128 + 64 + 40, 512), (40, 40, 44))
    W.paste(side, (0, 0))
    W.paste(side.resize((128, 128), Image.LANCZOS), (532, 0))
    W.paste(side.resize((64, 64), Image.LANCZOS), (680, 0))
    W.save(f"{R}/{VER}_icon.png")
    os.remove(f"{R}/_icon.png")
    print("renders done")


if __name__ == "__main__":
    main()
