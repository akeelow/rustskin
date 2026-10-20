"""Chair UV islands: which part of the model each island is, where it sits in 3D and in the atlas.

The OBJ is in metres, Y up (Blender export): x = width, y = height, z = depth (+z = front, seat edge).
Most of the chair is one welded mesh (parts.py finds one big piece), so islands are split by UV
connectivity instead.

Usage: .venv/Scripts/python skins/sauna/chair/islands.py
Writes uv/islands.png (original diffuse, islands outlined and numbered) and uv/islands.md.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from uv_zones import load_obj, normal  # noqa: E402

HERE = Path(__file__).parent
SIZE = 1024


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
    V, T, F = load_obj(HERE / "originals" / "chair.obj")
    I = islands(F)
    img = Image.open(HERE / "originals" / "chair_bc.png").convert("RGB")
    img = Image.blend(img, Image.new("RGB", img.size, (0, 0, 0)), 0.35)
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype("arial.ttf", 22)
    md = ["# Острова развёртки стула", "",
          "x — ширина (+x справа, если смотреть спереди), y — высота, z — глубина (+z — перед), м. "
          "UV — доли атласа, v сверху вниз. Площадь — м² в 3D и доля атласа.", "",
          "| # | треуг. | x | y | z | u | v (сверху) | нормаль | м² | атлас |",
          "|---|---:|---|---|---|---|---|---|---:|---:|"]
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
            d.polygon([(T[t][0] * SIZE, (1 - T[t][1]) * SIZE) for t in F[f][1]], outline=(255, 255, 0))
        dirs = "+x -x +y -y +z -z".split()
        k = max(range(3), key=lambda k: abs(acc[k]))
        dom = dirs[2 * k + (acc[k] < 0)] if abs(acc[k]) > 0.4 * area3 else "смеш."
        cu = sum(u for u, _ in uv) / len(uv) * SIZE
        cv = (1 - sum(v for _, v in uv) / len(uv)) * SIZE
        d.text((cu, cv), str(n), fill=(255, 60, 60), font=font, anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0))
        fmt = lambda a: f"{a[0]:.2f}…{a[1]:.2f}"
        md.append(f"| {n} | {len(fs)} | {fmt(b[0])} | {fmt(b[1])} | {fmt(b[2])} | "
                  f"{min(u for u, _ in uv):.2f}…{max(u for u, _ in uv):.2f} | "
                  f"{1 - max(v for _, v in uv):.2f}…{1 - min(v for _, v in uv):.2f} | {dom} | {area3:.3f} | {areau:.3f} |")
    img.save(HERE / "uv" / "islands.png")
    (HERE / "uv" / "islands.md").write_text("\n".join(md) + "\n", encoding="utf8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
