"""Sauna Stone Box v2: проверки экспорта до отдачи в игру (PLAN_v2.md, раздел 4).

  .venv/Scripts/python skins/sauna/wood-storage-box/checks_v2.py [--tag v2.0]

1. «Diffuse против Normal»: мелкий рисунок яркости Diffuse без пары в нормали (нарисованное) — доля по участкам и карта
   plan_v2/check_dn_<tag>.png (красное — рисунок есть только в цвете).
2. Отступы: у каждого текселя наших участков в радиусе 8 px нет «чужих» (незаполненных) пикселей.
3. Альфа: только крышка; одиночные пиксели альфы на границе крышки («пыль», как у Starry Santa Sleigh).
4. Spec/Gloss и Emission: пределы по участкам.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from texture_v2 import fblur  # noqa: E402

EXP = HERE / "export"


def load(tag, name, mode):
    return np.asarray(Image.open(EXP / f"Box_{tag}_{name}.png").convert(mode), np.float32) / 255.0


def main():
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "v2.0"
    dif = load(tag, "diffuse", "RGBA")
    nrm = load(tag, "normal", "RGB") * 2 - 1
    sg = load(tag, "specgloss", "RGBA")
    em = load(tag, "emission", "RGB")
    mask = np.asarray(Image.open(HERE / "bake" / "v2" / "mask.png").convert("L").resize((1024, 1024), Image.BILINEAR)) > 127
    lum = dif[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32)
    hp_l = np.abs(lum - fblur(lum, 3)) / (fblur(lum, 6) + 0.05)
    hp_n = np.hypot(nrm[..., 0] - fblur(nrm[..., 0], 3), nrm[..., 1] - fblur(nrm[..., 1], 3))
    dl, dn = fblur(hp_l, 2), fblur(hp_n, 2)
    painted = (dl > 0.12) & (dn < 0.03) & mask
    regions = {"walls": mask & (np.arange(1024)[:, None] > 165), "floor": mask & (np.arange(1024)[:, None] <= 165)}
    print("1. Diffuse без пары в нормали (доля текселей с заметным рисунком цвета):")
    for k, m in regions.items():
        strong = (dl > 0.12) & m
        print(f"   {k}: рисунок цвета {strong.mean() / max(m.mean(), 1e-9):.1%} участка, из него без рельефа "
              f"{(painted & m).sum() / max(strong.sum(), 1):.1%}")
    vis = np.stack([lum] * 3, -1) * 0.6
    vis[painted] = (1, 0.15, 0.1)
    Image.fromarray((np.clip(vis, 0, 1) * 255).astype(np.uint8)).save(HERE / "plan_v2" / f"check_dn_{tag}.png")
    # 2. отступы: в радиусе 8 px от наших текселей альфа не нулевая там, где не крышка — проверяем, что цвет не чёрный
    grow = fblur(mask.astype(np.float32), 8) > 0.01
    ring = grow & ~mask
    dark = ring & (lum < 0.02) & (dif[..., 3] > 0.5)
    print(f"2. Отступ 8 px: тёмных (незаполненных) пикселей в кольце {dark.sum()} из {ring.sum()}")
    # 3. альфа
    a = dif[..., 3] > 0.5
    cut = ~a
    print(f"3. Альфа: вырезано {cut.mean():.1%} атласа; на наших участках {(cut & mask).sum()} px")
    nb = sum(np.roll(np.roll(a, dy, 0), dx, 1).astype(int) for dy in (-1, 0, 1) for dx in (-1, 0, 1)) - a
    specks = (a & (nb <= 2)) | (~a & (nb >= 7))
    print(f"   одиночные пиксели на границе выреза: {int(specks.sum())}")
    # 4. пределы
    for k, m in regions.items():
        print(f"4. {k}: spec {sg[..., 0][m].min():.2f}..{sg[..., 0][m].max():.2f}, gloss {sg[..., 3][m].min():.2f}..{sg[..., 3][m].max():.2f}, "
              f"emission max {em[m].max():.2f}, светится >0.1: {(em[m].max(-1) > 0.1).mean():.1%}")


if __name__ == "__main__":
    main()
