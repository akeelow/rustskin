"""Sauna Door v2: самопроверки экспорта (1024).

  .venv/Scripts/python skins/sauna/wooden-door/checks_v2.py [--tag v2.0]

1. Альфа: везде ровно 255 (v2.8: стекло глухое; проверки ширины потёков v2.0–v2.7 — в истории git).
2. Отпечаток ладони: на переде и сзади темнее тумана вокруг (днём протёртое стекло видно).
3. Ладонь спереди и сзади — одна маска в x, y: площади почти равны.
4. Нормаль на гладком стекле — (128, 128, 255) ± 3.
5. Diffuse против Normal на переде: мелкий рисунок яркости Diffuse без пары в Normal (подсветка в картинке).
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "uv"))
import fields_door as FD  # noqa: E402
import texture_v1 as T1  # noqa: E402

tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "v2.0"
EXP = HERE / "export"
dif = np.asarray(Image.open(EXP / f"Door_{tag}_diffuse.png").convert("RGBA"), np.float32) / 255
nrm = np.asarray(Image.open(EXP / f"Door_{tag}_normal.png").convert("RGB"), np.float32) / 255
isl, pos, nz = T1.texel_points()
isl, pos = isl[2::4, 2::4], pos[2::4, 2::4] * 100.0
x, y = pos[..., 0], pos[..., 1]
a = dif[..., 3]
xi0, xi1, yi0, yi1 = FD.PANE
in_pane = (x > xi0) & (x < xi1) & (y > yi0) & (y < yi1) & np.isin(isl, (2, 4))
ok = True

# 1 (v2.8: стекло глухое — прозрачных потёков больше нет)
bad = (a < 0.999).sum()
print(f"1. альфа < 255 где угодно: {bad} текселей", "OK" if bad == 0 else "FAIL")
ok &= bad == 0
cut = a < 0.5

# 2–3: отпечаток ладони — на переде и сзади в одних и тех же x, y, темнее тумана вокруг (днём)
clear, rim = FD.palm_print(x, y)
lum = dif[..., :3].mean(-1)
for side, k in (("перед", 2), ("зад", 4)):
    g = in_pane & (isl == k)
    pin = g & (clear > 0.6)
    ring = g & (clear < 0.02) & (rim < 0.05) & (np.hypot(x - FD.PALM_C[0], y - FD.PALM_C[1]) < 13)
    d = np.median(lum[ring]) - np.median(lum[pin]) if pin.any() and ring.any() else 0
    print(f"2. {side}: ладонь {pin.sum()} px (1024), темнее тумана вокруг на {d:.3f}", "OK" if d > 0.06 else "CHECK")
    ok &= bool(d > 0.06)
both = [((isl == k) & in_pane & (clear > 0.6)).sum() for k in (2, 4)]
r = min(both) / max(max(both), 1)
print(f"3. ладонь спереди/сзади — одна маска (x, y); площадь {both[0]} / {both[1]} px, отношение {r:.2f}", "OK" if r > 0.8 else "CHECK")

# 4
glass_f = in_pane & (isl == 2) & ~cut
inner = glass_f & (x > xi0 + 2.5) & (x < xi1 - 2.5) & (y > yi0 + 2.5) & (y < yi1 - 2.5)
dn = np.abs(nrm[inner] - np.array([0.5, 0.5, 1.0])).max(1) * 255
print(f"4. нормаль на стекле: отклонение медиана {np.median(dn):.1f}, 95 % {np.percentile(dn, 95):.1f}")

# 5
from PIL import ImageFilter  # noqa: E402
lum = dif[..., :3].mean(-1)
hp_d = lum - np.asarray(Image.fromarray((lum * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)), np.float32) / 255
slope = np.hypot(nrm[..., 0] - 0.5, nrm[..., 1] - 0.5)
hp_n = slope - np.asarray(Image.fromarray((slope * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)), np.float32) / 255
front = (isl == 2) & ~in_pane
d_det = np.abs(hp_d) > 0.06
n_det = np.asarray(Image.fromarray((np.abs(hp_n) > 0.02).astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(5)), np.float32) > 0
lonely = d_det & ~n_det & front
print(f"5. детали Diffuse без пары в Normal на переде: {100 * lonely.sum() / max((d_det & front).sum(), 1):.1f} % деталей Diffuse")
vis = (dif[..., :3] * 0.6 * 255).astype(np.uint8)
vis[lonely] = (255, 0, 255)
out = HERE / "renders" / "v2" / f"check_{tag}_diffuse_vs_normal.png"
out.parent.mkdir(parents=True, exist_ok=True)
Image.fromarray(vis).save(out)
print("   ->", out.name)
print("ИТОГ:", "OK" if ok else "есть ошибки")
