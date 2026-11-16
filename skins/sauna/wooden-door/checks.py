"""Sauna Door: self-checks before the game. Writes pictures to renders/ and prints numbers for the README.

    .venv/Scripts/python skins/sauna/wooden-door/checks.py <dir with orig_sheet.png, locker_sheet.png, stove_sheet.png>

The three extra sheets are tools/blender/viewer.py renders of the original door, the locker (v5.4) and
the stove (v2.9) in the viewer's standard light; renders/v1_sheet.png is the door's own.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "uv"))
import analyze_uv as A  # noqa: E402

R = HERE / "renders"
EXP = HERE / "export"
V = "v1"
CELL = 512                      # the viewer's sheet: 6 views x 2 rows (day, night)
VIEWS = {"front": 0, "three_quarter": 1, "side": 2, "back": 3, "top": 4, "close": 5}


def cell(sheet, view, night=False):
    c = VIEWS[view]
    return sheet.crop((c * CELL, CELL * night, (c + 1) * CELL, CELL * (night + 1)))


def row(images, pad=8, bg=(30, 30, 30)):
    h = max(i.height for i in images)
    out = Image.new("RGB", (sum(i.width for i in images) + pad * (len(images) + 1), h + 2 * pad), bg)
    x = pad
    for i in images:
        out.paste(i, (x, pad))
        x += i.width + pad
    return out


def padding():
    """Gap between UV islands and whether the exported maps are filled beyond the island edges."""
    P, T, VI = A.load()
    ids = A.islands(VI)
    owner, _ = A.raster(T, ids)                       # 2048, row 0 = v 0
    n = owner.shape[0]
    best = {}
    for d in range(1, 40):
        for dy, dx in ((0, d), (d, 0)):
            a, b = owner[:n - dy, :n - dx], owner[dy:, dx:]
            m = (a >= 0) & (b >= 0) & (a != b)
            for i, j in set(zip(a[m].tolist(), b[m].tolist())):
                best.setdefault((min(i, j), max(i, j)), d)
    print("closest island pairs (texels at 2048):", sorted(best.items(), key=lambda kv: kv[1])[:8])
    inside = owner[::-1] >= 0
    dif = np.asarray(Image.open(EXP / f"Door_{V}_diffuse.png").convert("RGB"), np.int32)
    ring = np.zeros_like(inside)
    for d in range(1, 9):
        for dy, dx in ((0, d), (0, -d), (d, 0), (-d, 0)):
            ring |= np.roll(inside, (dy, dx), (0, 1))
    ring &= ~inside
    print("texels within 8 px of an island: %d, of them filled: %.1f%%" % (ring.sum(), 100 * (dif[ring].sum(1) > 0).mean()))
    return owner, P, T, VI, ids


def seams(P, T, VI, ids):
    """3D edges shared by two UV islands: the diffuse just inside each side of the edge should match."""
    dif = np.asarray(Image.open(EXP / f"Door_{V}_diffuse.png").convert("RGB"), np.float32)
    n = dif.shape[0]
    edges = {}
    for k in range(len(P)):
        for a, b in ((0, 1), (1, 2), (2, 0)):
            key = tuple(sorted((tuple(np.round(P[k, a], 4)), tuple(np.round(P[k, b], 4)))))
            edges.setdefault(key, []).append((k, a, b))
    diffs = []
    for key, lst in edges.items():
        for i in range(len(lst)):
            for j in range(i + 1, len(lst)):
                (k1, a1, b1), (k2, a2, b2) = lst[i], lst[j]
                if ids[k1] == ids[k2] or min(ids[k1], ids[k2]) >= 8:
                    continue
                if np.linalg.norm(P[k1, a1] - P[k1, b1]) < 0.05:
                    continue
                n1 = np.cross(P[k1, 1] - P[k1, 0], P[k1, 2] - P[k1, 0])
                n2 = np.cross(P[k2, 1] - P[k2, 0], P[k2, 2] - P[k2, 0])
                cosang = n1 @ n2 / (np.linalg.norm(n1) * np.linalg.norm(n2) + 1e-12)
                for t in (0.2, 0.5, 0.8):
                    cols = []
                    for (k, a, b) in ((k1, a1, b1), (k2, a2, b2)):
                        pa, pb = (T[k, a], T[k, b]) if np.allclose(P[k, a], key[0], atol=1e-3) else (T[k, b], T[k, a])
                        c = T[k].mean(0)
                        uv = pa + (pb - pa) * t
                        uv = uv + (c - uv) / (np.linalg.norm(c - uv) * n + 1e-9) * 2.0      # 2 texels inside
                        cols.append(dif[int((1 - uv[1]) * n) % n, int(uv[0] * n) % n])
                    diffs.append((np.abs(cols[0] - cols[1]).mean(), cosang))
    d = np.array(diffs)
    flat = d[d[:, 1] > 0.9, 0]
    bent = d[d[:, 1] <= 0.9, 0]
    print("seams: %d samples on coplanar seams, median |dRGB| %.1f, 95%% %.1f (of 255); %d on corners (two different faces of the door), median %.1f"
          % (len(flat), np.median(flat) if len(flat) else 0, np.percentile(flat, 95) if len(flat) else 0, len(bent), np.median(bent)))


def icons(sheet):
    views = [cell(sheet, "front"), cell(sheet, "three_quarter"), cell(sheet, "back"), cell(sheet, "front", True)]
    tiles = []
    for v in views:
        for s in (128, 64):
            small = v.resize((s, s), Image.LANCZOS)
            for im in (small, small.convert("L").convert("RGB")):
                t = Image.new("RGB", (128, 128), (30, 30, 30))
                t.paste(im, ((128 - s) // 2, (128 - s) // 2))
                tiles.append(t)
    rows = [row(tiles[i * 4:(i + 1) * 4]) for i in range(4)]
    out = Image.new("RGB", (rows[0].width, sum(r.height for r in rows)))
    for i, r in enumerate(rows):
        out.paste(r, (0, i * r.height))
    out.save(R / f"{V}_icons.png")


def wood_stats(name, path, box):
    a = np.asarray(Image.open(path).convert("RGB"), np.float32) / 255
    h, w = a.shape[:2]
    c = a[int(box[1] * h):int(box[3] * h), int(box[0] * w):int(box[2] * w)].reshape(-1, 3)
    med = np.median(c, 0)
    mx, mn = med.max(), med.min()
    print("%-22s median #%02X%02X%02X  saturation %2.0f%%  value %2.0f%%" %
          (name, *(med * 255).astype(int), 100 * (mx - mn) / mx, 100 * mx))


def main():
    extra = Path(sys.argv[1])
    sheet = Image.open(R / f"{V}_sheet.png").convert("RGB")
    orig = Image.open(extra / "orig_sheet.png").convert("RGB")
    locker = Image.open(extra / "locker_sheet.png").convert("RGB")
    stove = Image.open(extra / "stove_sheet.png").convert("RGB")

    owner, P, T, VI, ids = padding()
    seams(P, T, VI, ids)
    icons(sheet)

    # silhouette and big shapes against the original
    row([cell(orig, "front"), cell(sheet, "front"), cell(orig, "back"), cell(sheet, "back"),
         cell(orig, "three_quarter"), cell(sheet, "three_quarter")]).save(R / f"{V}_vs_original.png")

    # with the set, same light
    for night in (False, True):
        row([cell(stove, "three_quarter", night), cell(locker, "three_quarter", night),
             cell(sheet, "three_quarter", night), cell(sheet, "back", night)]).save(
            R / f"{V}_set_{'night' if night else 'day'}.png")

    print("wood on the diffuse maps (set check):")
    S = HERE.parent
    wood_stats("door front, dry", EXP / f"Door_{V}_diffuse.png", (0.05, 0.60, 0.28, 0.80))
    wood_stats("door front, wet foot", EXP / f"Door_{V}_diffuse.png", (0.05, 0.95, 0.28, 0.99))
    wood_stats("door back", EXP / f"Door_{V}_diffuse.png", (0.34, 0.21, 0.58, 0.35))
    wood_stats("chair v1.4", S / "chair/export/Chair_v1.4_diffuse.png", (0.0, 0.0, 1.0, 1.0))
    wood_stats("bench v1.2", sorted((S / "bed/export").glob("*v1.2*diffuse*.png"))[0], (0.0, 0.0, 1.0, 1.0))
    wood_stats("locker v5.4", S / "locker/export/Locker_v5.4_diffuse.png", (0.0, 0.0, 1.0, 1.0))

    night = np.asarray(cell(sheet, "front", True), np.float32) / 255
    print("night front render: brightest pixel %.2f, pixels above 0.98: %d" % (night.max(), (night.max(-1) > 0.98).sum()))
    for n in ("diffuse", "normal", "specgloss", "occlusion", "emission"):
        im = Image.open(EXP / f"Door_{V}_{n}.png")
        print(n, im.size, im.mode)


if __name__ == "__main__":
    main()
