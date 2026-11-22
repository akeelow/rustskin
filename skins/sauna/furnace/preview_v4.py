"""Sauna Boiler v4: быстрый предпросмотр поля (fields_v4) в атласе — до Blender (.venv).

Каждый тексель островов 0–2 получает точку модели (барицентрически по треугольнику UV) и нормаль OBJ; поле считается
в этих точках. Выход: plan_v4/preview_relief.png — теневой рельеф по атласу (свет сверху-слева в развёртке),
plan_v4/preview_masks.png — маски цветом. Не запекание и не игровой кадр: только проверка размеров и раскладки.

  .venv/Scripts/python skins/sauna/furnace/preview_v4.py [--size 2048]
"""
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fields_v4 as FV  # noqa: E402
import geom_v4 as G  # noqa: E402


def texel_points(size, islands=(0, 1, 2)):
    V, T, N, F = G.load()
    isl = G.island_of_face()
    P = np.full((size, size, 3), np.nan)
    Nn = np.zeros((size, size, 3))
    for f in F[np.isin(isl, islands)]:
        uv = T[f[:, 1]] * size
        uv[:, 1] = size - uv[:, 1]
        x0, y0 = np.floor(uv.min(0)).astype(int)
        x1, y1 = np.ceil(uv.max(0)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, size - 1), min(y1, size - 1)
        if x1 < x0 or y1 < y0:
            continue
        ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        px, py = xs + 0.5, ys + 0.5
        (ax, ay), (bx, by), (cx, cy) = uv
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        w0 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / den
        w1 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / den
        w2 = 1 - w0 - w1
        ins = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        W = np.stack([w0[ins], w1[ins], w2[ins]], -1)
        P[ys[ins], xs[ins]] = W @ V[f[:, 0]]
        nn = W @ N[f[:, 2]]
        Nn[ys[ins], xs[ins]] = nn / np.linalg.norm(nn, axis=1, keepdims=True)
    return P, Nn


def main():
    size = int(sys.argv[sys.argv.index("--size") + 1]) if "--size" in sys.argv else 2048
    t = time.time()
    P, N = texel_points(size)
    ok = np.isfinite(P[..., 0])
    print("texels", ok.sum(), f"{time.time() - t:.0f} s")
    r = FV.body(P[ok], N[ok])
    print(f"field {time.time() - t:.0f} s")
    H = np.zeros((size, size))
    H[ok] = r["h"]
    # теневой рельеф: градиент h по текселям (см на тексель), свет сверху-слева
    px_cm = 1.0 / (3.9 * size / 1024)
    gy, gx = np.gradient(H)
    nx, ny = -gx / px_cm, -gy / px_cm
    L = np.array([-0.5, -0.6, 0.62])
    sh = (nx * L[0] + ny * L[1] + L[2]) / np.sqrt(nx ** 2 + ny ** 2 + 1)
    img = np.clip(0.15 + 0.85 * sh, 0, 1)
    img[~ok] = 0.1
    out = HERE / "plan_v4"
    Image.fromarray((img * 255).astype(np.uint8)).save(out / "preview_relief.png")
    M = np.zeros((size, size, 3))
    M[ok] = np.stack([np.clip(r["rust"] + r["char"], 0, 1), np.clip(r["crust"] + r["wear"] * 0.5, 0, 1),
                      np.clip(r["cav"] + r["rivet"] + r["knot"] * 0.6, 0, 1)], -1)
    M[ok] = 0.25 * img[ok][:, None] + 0.75 * M[ok]
    Image.fromarray((M * 255).astype(np.uint8)).save(out / "preview_masks.png")
    np.save(out / "preview_h.npy", H.astype(np.float32))
    # нормаль деталей из высот (без гранёности — как после вычитания) — для замера measure_v4 --compare
    n3 = np.stack([nx, ny, np.ones_like(nx)], -1)
    n3 /= np.linalg.norm(n3, axis=-1, keepdims=True)
    n3[~ok] = (0, 0, 1)
    Image.fromarray(((n3 * 0.5 + 0.5) * 255).astype(np.uint8)).resize((1024, 1024), Image.LANCZOS).save(out / "preview_normal.png")
    print("h range", r["h"].min(), r["h"].max())


if __name__ == "__main__":
    main()
