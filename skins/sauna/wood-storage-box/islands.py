"""Wood Storage Box UV islands: which part of the model each island is, where it sits in 3D and in the atlas,
and which islands share texels (a painted detail would repeat there).

The OBJ is in metres, Y up (Blender 4.4 export): x = width, y = height, z = depth.

Usage: .venv/Scripts/python skins/sauna/wood-storage-box/islands.py
Writes uv/islands.png (original diffuse, islands outlined and numbered, shared texels in magenta)
and uv/islands.md.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from uv_zones import load_obj, normal, raster  # noqa: E402

HERE = Path(__file__).parent
OBJ = HERE / "originals" / "box.wooden.obj"
SIZE = 1024
GRID = 512   # texel grid for the overlap test


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


def owners(T, F, I):
    """texel -> set of island ids (u, v wrapped into 0..1)."""
    own = {}
    for n, fs in enumerate(I):
        for f in fs:
            ti = F[f][1]
            du = min(T[t][0] for t in ti) // 1
            dv = min(T[t][1] for t in ti) // 1
            pts = [((T[t][0] - du) * GRID, (1 - (T[t][1] - dv)) * GRID) for t in ti]
            for x, y, *_ in raster(pts, GRID, GRID):
                own.setdefault((x, y), set()).add(n)
    return own


def main():
    from PIL import Image, ImageDraw, ImageFont   # not in Blender's Python

    V, T, F = load_obj(OBJ)
    I = islands(F)
    own = owners(T, F, I)
    img = Image.open(HERE / "originals" / "Wooden_Box_bc.png").convert("RGB")
    img = Image.blend(img, Image.new("RGB", img.size, (0, 0, 0)), 0.35)
    over = Image.new("L", (GRID, GRID), 0)
    for (x, y), s in own.items():
        if len(s) > 1:
            over.putpixel((x, y), 255)
    over = over.resize(img.size, Image.NEAREST)
    img.paste((255, 0, 200), mask=over.point(lambda a: 150 if a else 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype("arial.ttf", 20)
    allu = [u for u, _ in T]
    allv = [v for _, v in T]
    md = ["# Острова развёртки ящика", "",
          f"{len(V)} вершин, {len(F)} треугольников. UV: u {min(allu):.3f}…{max(allu):.3f}, "
          f"v {min(allv):.3f}…{max(allv):.3f}.", "",
          "x — ширина, y — высота, z — глубина, м. UV — доли атласа, v сверху вниз. Площадь — м² в 3D и доля "
          "атласа; «плотн.» — атлас/м² (больше — чётче). «Общие» — острова, с которыми делит тексели "
          "(в пикселях сетки 512).", "",
          "| # | треуг. | x | y | z | u | v (сверху) | нормаль | м² | атлас | плотн. | общие |",
          "|---|---:|---|---|---|---|---|---|---:|---:|---:|---|"]
    for n, fs in enumerate(I):
        pts = [V[i] for f in fs for i in F[f][0]]
        uv = [T[t] for f in fs for t in F[f][1]]
        b = [(min(p[k] for p in pts), max(p[k] for p in pts)) for k in range(3)]
        acc = [0.0, 0.0, 0.0]
        area3 = areau = 0.0
        for f in fs:
            a, bb, c = (V[i] for i in F[f][0])
            nx = normal(a, bb, c)
            e1 = [bb[k] - a[k] for k in range(3)]
            e2 = [c[k] - a[k] for k in range(3)]
            cr = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]]
            ar = 0.5 * sum(x * x for x in cr) ** 0.5
            area3 += ar
            for k in range(3):
                acc[k] += nx[k] * ar
            ua, ub, uc = (T[t] for t in F[f][1])
            areau += 0.5 * abs((ub[0] - ua[0]) * (uc[1] - ua[1]) - (uc[0] - ua[0]) * (ub[1] - ua[1]))
            d.polygon([(T[t][0] % 1.0000001 * SIZE, (1 - T[t][1]) * SIZE) for t in F[f][1]], outline=(255, 255, 0))
        dirs = "+x -x +y -y +z -z".split()
        k = max(range(3), key=lambda k: abs(acc[k]))
        dom = dirs[2 * k + (acc[k] < 0)] if abs(acc[k]) > 0.4 * area3 else "смеш."
        shared = {}
        for s in own.values():
            if n in s and len(s) > 1:
                for m in s - {n}:
                    shared[m] = shared.get(m, 0) + 1
        cu = sum(u for u, _ in uv) / len(uv) * SIZE
        cv = (1 - sum(v for _, v in uv) / len(uv)) * SIZE
        d.text((cu, cv), str(n), fill=(255, 60, 60), font=font, anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0))
        fmt = lambda a: f"{a[0]:.2f}…{a[1]:.2f}"
        md.append(f"| {n} | {len(fs)} | {fmt(b[0])} | {fmt(b[1])} | {fmt(b[2])} | "
                  f"{min(u for u, _ in uv):.2f}…{max(u for u, _ in uv):.2f} | "
                  f"{1 - max(v for _, v in uv):.2f}…{1 - min(v for _, v in uv):.2f} | {dom} | {area3:.3f} | "
                  f"{areau:.3f} | {areau / max(area3, 1e-9):.2f} | "
                  f"{', '.join(f'#{m}: {c}' for m, c in sorted(shared.items(), key=lambda kv: -kv[1])[:6]) or '—'} |")
    (HERE / "uv").mkdir(exist_ok=True)
    img.save(HERE / "uv" / "islands.png")
    (HERE / "uv" / "islands.md").write_text("\n".join(md) + "\n\nМалиновым на `islands.png` — тексели, "
                                            "общие у разных островов.\n", encoding="utf8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
