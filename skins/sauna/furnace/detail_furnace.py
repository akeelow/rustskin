"""Sauna Boiler: эксперимент с Detail-слоем (поверх карт v3, сами v3 не меняются).

Выход в export/:
  Furnace_detail_mask.png       1024, белое — железо (бак, обручи, клёпки, рамка, пояс) и камни; дерево, тряпка,
                                ковш, топка — чёрные. Значение продублировано во все каналы RGBA: какой канал читает
                                Rust, неизвестно (у Unity Standard — альфа).
  Furnace_detail_diffuse.png    512, бесшовная: следы молотка, оспины ржавчины, зерно металла. Среднее ≈ 190, как у
                                штатной plaster_b_detail: при Detail Color 179 это ≈ «без изменений»
                                (190/255 × 179/255 × 2 ≈ 1.04), видны только сами оспины и следы.
  Furnace_detail_normal.png     512, бесшовная, обычная RGB-нормаль (как наш основной Normal).
  Furnace_detail_occlusion.png  512, бесшовная, слабая грязь в оспинах.
  renders/detail_tile_preview.png — плитка 2×2 (проверка шва) и все три карты рядом.

  .venv/Scripts/python skins/sauna/furnace/detail_furnace.py
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import layout as L  # noqa: E402
from texture_furnace import dilate, down, load  # noqa: E402

OUT, REN = HERE / "export", HERE / "renders"
N = 512
rng = np.random.RandomState(7)
yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)


def pblur(a, sigma):
    """Периодическое гауссово размытие через FFT — плитка остаётся бесшовной."""
    f = np.fft.fftfreq(N)
    g = np.exp(-2 * (np.pi * sigma) ** 2 * (f[:, None] ** 2 + f[None, :] ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(a) * g)).astype(np.float32)


def pnoise(sigma, seed):
    r = np.random.RandomState(seed).randn(N, N).astype(np.float32)
    a = pblur(r, sigma)
    return (a - a.mean()) / (a.std() + 1e-9)


def wrapd(cx, cy):
    dx = (xx - cx + N / 2) % N - N / 2
    dy = (yy - cy + N / 2) % N - N / 2
    return dx, dy


def main():
    # ---------------- высота: следы молотка (мелкие пологие лунки), оспины ржавчины, зерно
    h = np.zeros((N, N), np.float32)
    for _ in range(170):                                 # следы молотка: круглые лунки 10–28 px
        cx, cy, r = rng.uniform(0, N), rng.uniform(0, N), rng.uniform(10, 28)
        dx, dy = wrapd(cx, cy)
        q = (dx * dx + dy * dy) / (r * r)
        h -= rng.uniform(0.5, 1.0) * np.clip(1 - q, 0, 1) ** 2
    h = (h - h.mean()) / (h.std() + 1e-9)
    pits = np.zeros((N, N), np.float32)
    cl = pnoise(40, 3) > 0.3                             # оспины кучками, не равномерно
    for _ in range(900):
        cx, cy = rng.uniform(0, N), rng.uniform(0, N)
        if not cl[int(cy), int(cx)] and rng.rand() < 0.7:
            continue
        r = rng.uniform(1.2, 3.5)
        dx, dy = wrapd(cx, cy)
        pits = np.maximum(pits, np.clip(1 - (dx * dx + dy * dy) / (r * r), 0, 1))
    grain = pnoise(0.8, 5) * 0.5 + pnoise(2.5, 6) * 0.5
    height = 0.55 * h - 1.6 * pits + 0.25 * grain

    # ---------------- diffuse: среднее 190, оспины темнее и рыжее, кромки лунок чуть светлее
    rustn = pnoise(18, 8)
    base = 190 + 9 * pnoise(6, 9) + 6 * grain + 5 * np.clip(pblur(h, 2) - pblur(h, 6), -2, 2)
    diff = np.stack([base, base, base], -1)
    tint = np.array([1.06, 0.88, 0.76], np.float32)        # ржавый оттенок в оспинах и пятнах
    rw = np.clip(pits * 1.2 + 0.25 * np.clip(rustn - 0.6, 0, None), 0, 1)
    diff = diff * (1 - 0.35 * rw[..., None]) * (1 + (tint - 1) * rw[..., None])
    diff += 190 - diff.mean()                               # держим общее среднее ≈ 190
    diff = np.clip(diff, 0, 255)

    # ---------------- нормаль (OpenGL, +Y вверх, как основной Normal)
    hs = pblur(height, 0.7)
    gx = (np.roll(hs, -1, 1) - np.roll(hs, 1, 1)) * 0.5
    gy = (np.roll(hs, -1, 0) - np.roll(hs, 1, 0)) * 0.5
    k = 0.9
    nrm = np.stack([-gx * k, gy * k, np.ones_like(gx)], -1)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    occ = np.clip(1 - 0.45 * pblur(pits, 1.0) - 0.08 * np.clip(-h, 0, None), 0.4, 1) * 255

    # ---------------- маска по развёртке
    idm = np.rint((load("id.png")[..., 0] * 255 - 6) / 12).astype(np.int32)
    on = np.isin(idm, [L.IDS[n] for n in ("tank", "hoop", "rivet", "frame", "drum", "stone")]).astype(np.float32)
    valid = idm > 0
    m1 = down(on)
    ok = down(valid.astype(np.float32)) > 0.4
    m1 = dilate(np.where(ok, m1, 0)[..., None], ok)[..., 0]
    q = lambda a: np.clip(a, 0, 255).round().astype(np.uint8)  # noqa: E731
    mk = q(m1 * 255)

    OUT.mkdir(exist_ok=True)
    Image.fromarray(np.dstack([mk, mk, mk, mk]), "RGBA").save(OUT / "Furnace_detail_mask.png")
    Image.fromarray(q(diff), "RGB").save(OUT / "Furnace_detail_diffuse.png")
    Image.fromarray(q((nrm * 0.5 + 0.5) * 255), "RGB").save(OUT / "Furnace_detail_normal.png")
    Image.fromarray(q(occ), "L").convert("RGB").save(OUT / "Furnace_detail_occlusion.png")

    # ---------------- превью: плитка 2×2 каждой карты (шов виден бы крестом по центру) + маска
    tiles = [np.tile(q(diff), (2, 2, 1)), np.tile(q((nrm * 0.5 + 0.5) * 255), (2, 2, 1)),
             np.tile(np.dstack([q(occ)] * 3), (2, 2, 1))]
    mprev = np.asarray(Image.fromarray(mk).resize((2 * N, 2 * N)).convert("RGB"))
    sheet = np.concatenate(tiles + [mprev], 1)
    Image.fromarray(sheet).resize((sheet.shape[1] // 2, sheet.shape[0] // 2), Image.LANCZOS).save(REN / "detail_tile_preview.png")
    print(f"diffuse mean {diff.mean():.1f} (штатная 189.8), mask on {mk.mean() / 2.55:.1f}% of texture")


if __name__ == "__main__":
    main()
