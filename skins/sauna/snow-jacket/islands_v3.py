"""Sauna Robe v3: measurements of the Snow Jacket model before modelling (PLAN_v3.md, section 1).

Per UV island: where it sits in 3D, which way it faces, 3D and atlas area, texel density in px/cm at the
export size (1024) and at the bake size (4096), how far the OBJ vertex normals deviate from the face
normals (is the model smoothed?), and which islands share texels (mirrored or copied geometry).
The stock relief of the parka (pocket flaps, zip placket, seams, quilting) is measured from the
original normal map: the deviation from flat (128, 128, 255) per island.

The OBJ is in metres, Y up: x = across the arms (+x = character's left? see PLAN_v3), y = height,
z = front (+z) / back (-z).

    .venv/Scripts/python skins/sauna/snow-jacket/islands_v3.py
Writes uv/islands_v3.md, uv/islands_v3.png (atlas over the original diffuse, numbered, shared texels
magenta), uv/islands_v3_views.png (model coloured by island, 5 views) and uv/stock_relief_v3.png.
"""
import colorsys
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from uv_zones import load_obj, normal, raster, render_views  # noqa: E402

OBJ = HERE / "originals" / "jacket.snow.obj"
GRID = 1024


def load_vn(path):
    """Per triangle corner: vertex-normal vectors (same fan triangulation as load_obj)."""
    VN, FN = [], []
    for line in open(path, encoding="utf8", errors="replace"):
        if line.startswith("vn "):
            VN.append(tuple(map(float, line.split()[1:4])))
        elif line.startswith("f "):
            idx = [p.split("/") for p in line.split()[1:]]
            ni = [int(p[2]) - 1 if len(p) > 2 and p[2] else None for p in idx]
            for k in range(1, len(ni) - 1):
                FN.append((ni[0], ni[k], ni[k + 1]))
    return np.array(VN), FN


def islands(F):
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for _, ti in F:
        for t in ti[1:]:
            parent[find(t)] = find(ti[0])
    groups = {}
    for f, (_, ti) in enumerate(F):
        groups.setdefault(find(ti[0]), []).append(f)
    return sorted(groups.values(), key=lambda fs: -len(fs))


def main():
    from PIL import Image, ImageDraw, ImageFont   # not in Blender's Python (measure_v3.py imports islands)

    V, T, F = load_obj(OBJ)
    VN, FN = load_vn(OBJ)
    N = [normal(*(V[i] for i in vi)) for vi, _ in F]
    I = islands(F)
    Va = np.array(V)

    # texel owners (island ids per texel, 1024 grid) and per-texel face for the stock-normal stats
    own = np.full((GRID, GRID), -1, np.int32)
    multi = np.zeros((GRID, GRID), bool)
    for n, fs in enumerate(I):
        for f in fs:
            pts = [(T[t][0] * GRID, (1 - T[t][1]) * GRID) for t in F[f][1]]
            for x, y, *_ in raster(pts, GRID, GRID):
                if 0 <= x < GRID and 0 <= y < GRID:
                    if own[y, x] >= 0 and own[y, x] != n:
                        multi[y, x] = True
                    own[y, x] = n

    # self-overlap inside an island (mirrored halves on one island): count texels hit twice by one island
    selfhit = np.zeros(len(I), int)
    for n, fs in enumerate(I):
        cnt = {}
        for f in fs:
            pts = [(T[t][0] * GRID, (1 - T[t][1]) * GRID) for t in F[f][1]]
            for x, y, *_ in raster(pts, GRID, GRID):
                cnt[(x, y)] = cnt.get((x, y), 0) + 1
        selfhit[n] = sum(1 for c in cnt.values() if c > 1)

    nrm = np.asarray(Image.open(HERE / "originals" / "jacket_snow_nrm.png").convert("RGB"), np.float32) / 127.5 - 1
    dev = np.hypot(nrm[..., 0], nrm[..., 1])            # 0 = flat
    dev_img = (np.clip(dev / 0.5, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(dev_img).save(HERE / "uv" / "stock_relief_v3.png")

    rows = []
    for n, fs in enumerate(I):
        pts = Va[[i for f in fs for i in F[f][0]]]
        area3 = areau = 0.0
        acc = np.zeros(3)
        angs = []
        for f in fs:
            a, b, c = (Va[i] for i in F[f][0])
            cr = np.cross(b - a, c - a)
            ar = 0.5 * np.linalg.norm(cr)
            area3 += ar
            fn = np.array(N[f])
            acc += fn * ar
            ua, ub, uc = (np.array(T[t]) for t in F[f][1])
            areau += 0.5 * abs((ub[0] - ua[0]) * (uc[1] - ua[1]) - (uc[0] - ua[0]) * (ub[1] - ua[1]))
            for ni in FN[f]:
                if ni is not None:
                    vn = VN[ni] / (np.linalg.norm(VN[ni]) or 1)
                    angs.append(np.degrees(np.arccos(np.clip(vn @ fn, -1, 1))))
        dirs = "+x -x +y -y +z -z".split()
        k = int(np.argmax(np.abs(acc)))
        dom = dirs[2 * k + (acc[k] < 0)] if abs(acc[k]) > 0.4 * area3 else "смеш."
        # px/cm: sqrt(atlas fraction * size^2 / area_cm2)
        dens = lambda size: (areau * size * size / max(area3 * 1e4, 1e-9)) ** 0.5
        mask = own == n
        shared = sorted({int(m) for m in np.unique(own[multi & mask]) if m != n}) if multi[mask].any() else []
        rel = float(np.percentile(dev[mask], 90)) if mask.any() else 0
        uv = np.array([T[t] for f in fs for t in F[f][1]])
        rows.append(dict(n=n, tris=len(fs), b=[(pts[:, j].min(), pts[:, j].max()) for j in range(3)], dom=dom,
                         a3=area3, au=areau, d1=dens(1024), d4=dens(4096), ang=np.median(angs) if angs else 0,
                         angmax=np.percentile(angs, 95) if angs else 0, shared=shared, selfhit=selfhit[n],
                         rel=rel, u=(uv[:, 0].min(), uv[:, 0].max()), v=(1 - uv[:, 1].max(), 1 - uv[:, 1].min()),
                         cu=uv[:, 0].mean(), cv=1 - uv[:, 1].mean()))

    # atlas image
    img = Image.open(HERE / "originals" / "jacket_snow_red_bc.png").convert("RGB").resize((GRID, GRID))
    img = Image.blend(img, Image.new("RGB", img.size, (0, 0, 0)), 0.35)
    over = Image.fromarray((multi * 150).astype(np.uint8))
    img.paste((255, 0, 200), mask=over)
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype("arial.ttf", 18)
    for n, fs in enumerate(I):
        for f in fs:
            d.polygon([(T[t][0] * GRID, (1 - T[t][1]) * GRID) for t in F[f][1]], outline=(255, 255, 0))
    for r in rows:
        d.text((r["cu"] * GRID, r["cv"] * GRID), str(r["n"]), fill=(255, 60, 60), font=font, anchor="mm",
               stroke_width=2, stroke_fill=(0, 0, 0))
    img.save(HERE / "uv" / "islands_v3.png")

    # model coloured by island
    face_isl = {}
    for n, fs in enumerate(I):
        for f in fs:
            face_isl[f] = n
    col = lambda f: tuple(int(255 * c) for c in colorsys.hsv_to_rgb((face_isl[f] * 0.137) % 1, 0.65, 0.95))
    render_views(V, T, F, N, HERE / "uv" / "islands_v3_views.png", colour_of=col, cell=400)

    allang = [r["ang"] for r in rows]
    tot3 = sum(r["a3"] for r in rows)
    totu = sum(r["au"] for r in rows)
    md = ["# Острова развёртки Snow Jacket (замеры v3, 25.11.2026)", "",
          f"`islands_v3.py`. {len(V)} вершин, {len(F)} треугольников, {len(VN)} нормалей `vn`, {len(I)} островов. "
          f"Площадь модели {tot3:.3f} м², занято атласа {totu:.3f}. Средняя плотность "
          f"{(totu * 1024 ** 2 / (tot3 * 1e4)) ** 0.5:.1f} px/см при 1024.", "",
          "x — поперёк (руки), y — высота, z — перёд (+) / спина (−), м. UV: v сверху вниз. «px/см» — при экспорте "
          "1024 и при запекании 4096. «∠vn» — медиана (95-й перцентиль) угла между нормалью вершины OBJ и нормалью "
          "грани: больше ~5° — модель сглажена. «Рельеф» — 90-й перцентиль отклонения оригинальной нормали от "
          "плоской (0 — ровно, 0.3 — сильные складки). «Самоналожение» — тексели острова, на которые ложатся две его "
          "же грани (зеркальные половины на одних UV).", "",
          "| # | треуг. | x | y | z | вид | м² | атлас | px/см 1024 | px/см 4096 | ∠vn | рельеф | самоналож. | общие с |",
          "|---|---:|---|---|---|---|---:|---:|---:|---:|---|---:|---:|---|"]
    f2 = lambda a: f"{a[0]:+.2f}…{a[1]:+.2f}"
    for r in rows:
        md.append(f"| {r['n']} | {r['tris']} | {f2(r['b'][0])} | {f2(r['b'][1])} | {f2(r['b'][2])} | {r['dom']} | "
                  f"{r['a3']:.4f} | {r['au']:.4f} | {r['d1']:.1f} | {r['d4']:.1f} | {r['ang']:.0f}° ({r['angmax']:.0f}°) | "
                  f"{r['rel']:.2f} | {r['selfhit']} | {', '.join('#%d' % m for m in r['shared']) or '—'} |")
    md += ["", f"Медиана ∠vn по островам: {np.median(allang):.0f}°.", ""]
    (HERE / "uv" / "islands_v3.md").write_text("\n".join(md) + "\n", encoding="utf8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
