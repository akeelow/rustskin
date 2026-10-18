"""Map a Rust item's UV layout to the parts of the model you actually see.

Pure Python (no PIL/numpy). Each triangle gets the zone of the view it is most
visible from (front/back/left/right/top), split into body and plinth by height;
triangles not visible from any side are "hidden" (oven interior, undersides).

Usage:
  python tools/uv_zones.py <model.obj> <out_dir> [--diffuse tex.png] [--size 2048] [--plinth 0.27]

Writes into out_dir:
  uv_zones.png   UV layout filled with zone colours (paint guide)
  uv_wire.png    transparent UV wireframe, put it as the top layer in your editor
  views.png      the model from 5 sides in zone colours
  views_tex.png  the same views with the diffuse texture (only with --diffuse) - sanity check
  uv_zones.md    legend
"""
import argparse
import math
import struct
import zlib
from pathlib import Path

VIEWS = [  # name, label, projection (right, up, depth toward viewer), view direction
    ("front", "перед (+Z)", lambda p: (p[0], p[1], p[2]), (0, 0, 1)),
    ("back", "зад (-Z)", lambda p: (-p[0], p[1], -p[2]), (0, 0, -1)),
    ("right", "правый бок (+X)", lambda p: (-p[2], p[1], p[0]), (1, 0, 0)),
    ("left", "левый бок (-X)", lambda p: (p[2], p[1], -p[0]), (-1, 0, 0)),
    ("top", "верх", lambda p: (p[0], -p[2], p[1]), (0, 1, 0)),
]
COLOURS = {
    "front": (60, 150, 235), "back": (60, 200, 120), "right": (240, 190, 50),
    "left": (180, 90, 220), "top": (230, 60, 60), "hidden": (70, 70, 70),
}


def load_obj(path):
    V, T, F = [], [], []
    for line in open(path, encoding="utf8", errors="replace"):
        if line.startswith("v "):
            V.append(tuple(map(float, line.split()[1:4])))
        elif line.startswith("vt "):
            T.append(tuple(map(float, line.split()[1:3])))
        elif line.startswith("f "):
            idx = [p.split("/") for p in line.split()[1:]]
            vi = [int(p[0]) - 1 for p in idx]
            ti = [int(p[1]) - 1 if len(p) > 1 and p[1] else None for p in idx]
            for k in range(1, len(vi) - 1):
                F.append(((vi[0], vi[k], vi[k + 1]), (ti[0], ti[k], ti[k + 1])))
    return V, T, F


def normal(a, b, c):
    u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    l = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
    return (n[0] / l, n[1] / l, n[2] / l)


def raster(pts, w, h):
    """Yield (x, y, b0, b1, b2) for pixel centres inside a 2D triangle."""
    (x0, y0), (x1, y1), (x2, y2) = pts
    area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    if abs(area) < 1e-12:
        return
    for y in range(max(int(min(y0, y1, y2)), 0), min(int(max(y0, y1, y2)) + 1, h)):
        py = y + 0.5
        for x in range(max(int(min(x0, x1, x2)), 0), min(int(max(x0, x1, x2)) + 1, w)):
            px = x + 0.5
            b0 = ((x1 - px) * (y2 - py) - (x2 - px) * (y1 - py)) / area
            b1 = ((x2 - px) * (y0 - py) - (x0 - px) * (y2 - py)) / area
            b2 = 1 - b0 - b1
            if b0 >= -1e-6 and b1 >= -1e-6 and b2 >= -1e-6:
                yield x, y, b0, b1, b2


class Image:
    def __init__(self, w, h, fill=(24, 24, 28, 255)):
        self.w, self.h = w, h
        self.px = bytearray(bytes(fill) * (w * h))

    def set(self, x, y, c):
        i = (y * self.w + x) * 4
        self.px[i:i + 4] = bytes(c if len(c) == 4 else (*c, 255))

    def line(self, a, b, c):
        n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1]))) + 1
        for k in range(n + 1):
            x, y = int(a[0] + (b[0] - a[0]) * k / n), int(a[1] + (b[1] - a[1]) * k / n)
            if 0 <= x < self.w and 0 <= y < self.h:
                self.set(x, y, c)

    def save(self, path):
        stride = self.w * 4
        raw = b"".join(b"\x00" + bytes(self.px[y * stride:(y + 1) * stride]) for y in range(self.h))

        def chunk(tag, data):
            return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

        Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 6, 0, 0, 0))
                               + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def read_png(path):
    """Minimal 8-bit RGB/RGBA non-interlaced PNG reader -> (w, h, channels, bytearray)."""
    data = Path(path).read_bytes()
    pos, idat, w = 8, b"", None
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        tag, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        if tag == b"IHDR":
            w, h, depth, ctype, _, _, inter = struct.unpack(">IIBBBBB", body)
            assert depth == 8 and ctype in (2, 6) and inter == 0, "unsupported PNG"
            ch = 4 if ctype == 6 else 3
        elif tag == b"IDAT":
            idat += body
        pos += 12 + n
    raw, stride = zlib.decompress(idat), w * ch
    out, prev = bytearray(h * stride), bytearray(stride)
    for y in range(h):
        f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        if f == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                line[i] = (line[i] + ((line[i - ch] if i >= ch else 0) + prev[i]) // 2) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                b, c = prev[i], prev[i - ch] if i >= ch else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return w, h, ch, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("obj")
    ap.add_argument("out")
    ap.add_argument("--diffuse")
    ap.add_argument("--size", type=int, default=2048)
    ap.add_argument("--plinth", type=float, default=0.27, help="height (m) below which side faces count as plinth")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    V, T, F = load_obj(a.obj)
    N = [normal(*(V[i] for i in vi)) for vi, _ in F]
    ys = [p[1] for p in V]
    span = max(max(p[0] for p in V) - min(p[0] for p in V), max(ys) - min(ys)) * 1.1
    cy = (max(ys) + min(ys)) / 2
    cell = 512

    def to_screen(k, name, proj, p):
        q = proj(p)
        oy = 0 if name == "top" else cy
        return (k * cell + cell / 2 + q[0] / span * cell, cell / 2 - (q[1] - oy) / span * cell, q[2])

    # visibility: per view, z-buffer of triangle ids
    seen = [dict() for _ in F]
    for k, (name, _, proj, d) in enumerate(VIEWS):
        zbuf, ids = {}, {}
        for f, (vi, _) in enumerate(F):
            if N[f][0] * d[0] + N[f][1] * d[1] + N[f][2] * d[2] <= 0.05:
                continue
            s = [to_screen(0, name, proj, V[i]) for i in vi]
            for x, y, b0, b1, b2 in raster([(p[0], p[1]) for p in s], cell, cell):
                z = b0 * s[0][2] + b1 * s[1][2] + b2 * s[2][2]
                if z > zbuf.get((x, y), -1e9):
                    zbuf[(x, y)], ids[(x, y)] = z, f
        for f in ids.values():
            seen[f][name] = seen[f].get(name, 0) + 1
    zone = []
    for f, (vi, _) in enumerate(F):
        if not seen[f]:
            zone.append("hidden")
            continue
        z = max(seen[f], key=seen[f].get)
        low = sum(V[i][1] for i in vi) / 3 < a.plinth and z != "top"
        zone.append(z + ("-plinth" if low else ""))

    def colour(z):
        base = COLOURS[z.split("-")[0]]
        return tuple(int(c * 0.55) for c in base) if z.endswith("plinth") else base

    size = a.size
    uvz, wire = Image(size, size), Image(size, size, (0, 0, 0, 0))
    for f, (vi, ti) in enumerate(F):
        if None in ti:
            continue
        pts = [(T[i][0] * size, (1 - T[i][1]) * size) for i in ti]
        for x, y, *_ in raster(pts, size, size):
            uvz.set(x, y, colour(zone[f]))
    for f, (vi, ti) in enumerate(F):
        if None in ti:
            continue
        pts = [(T[i][0] * size, (1 - T[i][1]) * size) for i in ti]
        for s, e in ((0, 1), (1, 2), (2, 0)):
            uvz.line(pts[s], pts[e], (15, 15, 15))
            wire.line(pts[s], pts[e], (255, 255, 255, 160))
    uvz.save(out / "uv_zones.png")
    wire.save(out / "uv_wire.png")

    tex = read_png(a.diffuse) if a.diffuse else None
    sheets = [("views.png", False)] + ([("views_tex.png", True)] if tex else [])
    for fname, textured in sheets:
        img, zb = Image(cell * len(VIEWS), cell), {}
        for k, (name, _, proj, d) in enumerate(VIEWS):
            for f, (vi, ti) in enumerate(F):
                shade = N[f][0] * d[0] + N[f][1] * d[1] + N[f][2] * d[2]
                if shade <= 0.05:
                    continue
                s = [to_screen(k, name, proj, V[i]) for i in vi]
                for x, y, b0, b1, b2 in raster([(p[0], p[1]) for p in s], cell * len(VIEWS), cell):
                    z = b0 * s[0][2] + b1 * s[1][2] + b2 * s[2][2]
                    if z <= zb.get((x, y), -1e9):
                        continue
                    zb[(x, y)] = z
                    if textured and None not in ti:
                        u = b0 * T[ti[0]][0] + b1 * T[ti[1]][0] + b2 * T[ti[2]][0]
                        v = b0 * T[ti[0]][1] + b1 * T[ti[1]][1] + b2 * T[ti[2]][1]
                        tw, th, ch, px = tex
                        i = (min(int((1 - v) * th), th - 1) * tw + min(int(u * tw), tw - 1)) * ch
                        c = tuple(int(px[i + j] * (0.55 + 0.45 * shade)) for j in range(3))
                    else:
                        c = tuple(int(cc * (0.4 + 0.6 * shade)) for cc in colour(zone[f]))
                    img.set(x, y, c)
        img.save(out / fname)

    counts = {}
    for z in zone:
        counts[z] = counts.get(z, 0) + 1
    labels = {n: lbl for n, lbl, _, _ in VIEWS} | {"hidden": "скрыто (внутри духовки, днище, обратные стороны)"}
    md = ["# UV-зоны модели", "", f"Модель: `{Path(a.obj).name}`, треугольников: {len(F)}. "
          f"Цоколь — всё ниже {a.plinth} м (тот же цвет, темнее).", "",
          "| Цвет | Зона | Треугольников |", "|---|---|---:|"]
    for z in sorted(counts, key=lambda z: -counts[z]):
        base = z.split("-")[0]
        md.append(f"| rgb{colour(z)} | {labels[base]}{' — цоколь' if z.endswith('plinth') else ''} | {counts[z]} |")
    md += ["", "Файлы: `uv_zones.png` — развёртка по зонам; `uv_wire.png` — прозрачная сетка для слоя; "
           "`views.png` — виды по зонам; `views_tex.png` — виды с оригинальной текстурой (проверка)."]
    (out / "uv_zones.md").write_text("\n".join(md) + "\n", encoding="utf8")
    print("done:", ", ".join(f"{z}={c}" for z, c in counts.items()))


if __name__ == "__main__":
    main()
