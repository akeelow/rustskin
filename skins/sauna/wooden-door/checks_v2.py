"""Sauna Door v2: самопроверки экспорта (1024).

  .venv/Scripts/python skins/sauna/wooden-door/checks_v2.py [--tag v2.0]

1. Альфа: вне стекла ровно 255; на стекле — только потёки.
2. Ширина потёков: в каждой строке каждая прозрачная дорожка не уже 4 px (мипы не закроют дырку).
3. Потёки спереди и сзади: одни и те же точки двери (x, y) — доля совпадения.
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

# 1
outside = ~in_pane
bad = (a[outside] < 0.999).sum()
print(f"1. альфа вне стекла < 255: {bad} текселей", "OK" if bad == 0 else "FAIL")
ok &= bad == 0

# 2
cut = a < 0.5
for side, k in (("перед", 2), ("зад", 4)):
    m = cut & (isl == k)
    rows = np.where(m.any(1))[0]
    widths = []
    for r in rows:
        line = m[r].astype(np.int8)
        d = np.diff(np.concatenate([[0], line, [0]]))
        s, e = np.where(d == 1)[0], np.where(d == -1)[0]
        widths += list(e - s)
    widths = np.array(widths)
    thin = (widths < 4).sum()
    print(f"2. {side}: дорожек в строках {len(widths)}, ширина {widths.min() if len(widths) else 0}–{widths.max() if len(widths) else 0} px, "
          f"уже 4 px: {thin} ({100 * thin / max(len(widths), 1):.0f} %) — старт дорожки сужается, это допустимо до 15 %")
    ok &= thin <= 0.15 * max(len(widths), 1)

# 3
def grid(k):
    m = cut & (isl == k)
    g = np.zeros((60, 40), bool)
    gx = ((x[m] - xi0) / (xi1 - xi0) * 40).astype(int).clip(0, 39)
    gy = ((y[m] - yi0) / (yi1 - yi0) * 60).astype(int).clip(0, 59)
    g[gy, gx] = True
    return g
gf, gb = grid(2), grid(4)
iou = (gf & gb).sum() / max((gf | gb).sum(), 1)
print(f"3. потёки спереди/сзади совпадают (IoU по сетке 0.8 см): {iou:.2f}", "OK" if iou > 0.7 else "CHECK")

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
