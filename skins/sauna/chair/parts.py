"""Chair model analysis: connected mesh pieces, their 3D bounds, UV bounds and shared UV texels.

The OBJ is in metres, Y up (Blender export): x = width, y = height, z = depth.

Usage: .venv/Scripts/python skins/sauna/chair/parts.py
Writes uv/parts.png (UV islands coloured by piece, numbered list in uv/parts.md).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from uv_zones import Image, load_obj, normal, raster  # noqa: E402

HERE = Path(__file__).parent
OBJ = HERE / "originals" / "chair.obj"
SIZE = 512


def pieces(V, F):
    parent = list(range(len(V)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    # weld by position too: the exporter splits vertices on UV seams
    key = {}
    for i, p in enumerate(V):
        k = tuple(round(c, 2) for c in p)
        if k in key:
            parent[find(i)] = find(key[k])
        else:
            key[k] = i
    for vi, _ in F:
        for a in vi[1:]:
            parent[find(a)] = find(vi[0])
    groups = {}
    for f, (vi, _) in enumerate(F):
        groups.setdefault(find(vi[0]), []).append(f)
    return sorted(groups.values(), key=lambda fs: -len(fs))


def main():
    V, T, F = load_obj(OBJ)
    P = pieces(V, F)
    owner = {}  # texel -> set of piece ids
    for n, fs in enumerate(P):
        for f in fs:
            ti = F[f][1]
            if None in ti:
                continue
            # u > 1 is the same texture tile (wrap): shift the triangle back into 0..1
            du = int(min(T[t][0] for t in ti) // 1)
            dv = int(min(T[t][1] for t in ti) // 1)
            pts = [((T[t][0] - du) * SIZE, (1 - (T[t][1] - dv)) * SIZE) for t in ti]
            for x, y, *_ in raster(pts, SIZE, SIZE):
                owner.setdefault((x, y), set()).add(n)
    img = Image(SIZE, SIZE)
    md = ["# Куски модели стула", "", "x — ширина, y — высота, z — глубина, м. "
          "UV — доли атласа, v сверху вниз.", "",
          "| # | треуг. | x | y | z | u | v (сверху) | вверх | общих текселей с |", "|---|---:|---|---|---|---|---|---:|---|"]
    for n, fs in enumerate(P):
        pts = [V[i] for f in fs for i in F[f][0]]
        uv = [(T[t][0] % 1 if T[t][0] > 1 else T[t][0], T[t][1]) for f in fs for t in F[f][1] if t is not None]
        b = [(min(p[k] for p in pts), max(p[k] for p in pts)) for k in range(3)]
        up = sum(1 for f in fs if normal(*(V[i] for i in F[f][0]))[1] > 0.7)
        shared = {}
        for xy, s in owner.items():
            if n in s and len(s) > 1:
                for m in s - {n}:
                    shared[m] = shared.get(m, 0) + 1
        col = ((n * 97) % 200 + 55, (n * 57) % 200 + 55, (n * 31) % 200 + 55)
        for xy, s in owner.items():
            if n in s:
                img.set(*xy, (255, 255, 255) if len(s) > 1 else col)
        fmt = lambda a: f"{a[0]:.2f}…{a[1]:.2f}"
        md.append(f"| {n} | {len(fs)} | {fmt(b[0])} | {fmt(b[1])} | {fmt(b[2])} | "
                  f"{min(u for u, _ in uv):.2f}…{max(u for u, _ in uv):.2f} | "
                  f"{1 - max(v for _, v in uv):.2f}…{1 - min(v for _, v in uv):.2f} | {up} | "
                  f"{', '.join(f'#{m}: {c}' for m, c in sorted(shared.items())) or '—'} |")
    img.save(HERE / "uv" / "parts.png")
    (HERE / "uv" / "parts.md").write_text("\n".join(md) + "\n\nБелым на `parts.png` — тексели, общие у разных кусков.\n",
                                          encoding="utf8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
