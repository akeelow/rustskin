"""Colour blocking for Sauna Stove: flat palette colours per material, painted over the UV layout.

Run from the repo root:  python skins/sauna/electric-furnace/blocking.py
Writes:
  export/ElectricFurnace_blocking_v0_diffuse.png     -> editor slot DIFFUSE (Import)
  export/ElectricFurnace_blocking_v0_metalgloss.png  -> editor slot METAL/GLOSS (Import)
  uv/blocking_v0_views.png                           -> preview of the result from 5 sides
Emission stays the default (coil spirals now read as glowing cracks under the stones).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
from uv_zones import Image, classify, load_obj, normal, raster, read_png, render_views  # noqa: E402

SIZE = 2048
# name: (diffuse RGB, metalness 0-255, gloss 0-255) - colours from skins/sauna/README.md
MATERIALS = {
    "pallet":   ((0x6B, 0x4F, 0x36), 0, 115),   # wet dark boards under the stove
    "plinth":   ((0x6E, 0x66, 0x5C), 0, 40),    # fieldstone instead of bricks
    "iron":     ((0x2E, 0x2A, 0x27), 140, 70),  # kick band, door frame and bars
    "panel":    ((0xC2, 0xA7, 0x7E), 0, 35),    # light aspen boards on the control panel
    "knob":     ((0xD8, 0xC3, 0xA0), 0, 60),    # birch knobs
    "side":     ((0xC2, 0xA7, 0x7E), 0, 35),    # aspen slats, left and right
    "back":     ((0x7A, 0x5A, 0x3C), 0, 35),    # steam-darkened slats at the back
    "rim":      ((0x45, 0x40, 0x3B), 90, 60),   # sooty metal edge of the top plate
    "stones":   ((0x6A, 0x6B, 0x6E), 0, 55),    # sauna stones on the burners
    "embers":   ((0x3D, 0x3E, 0x41), 0, 45),    # stones inside / over the glowing coils
}


def material(cy, cz, zone, glowing):
    """Sauna material for a point at height cy / depth cz (m) on a triangle in `zone`."""
    base = zone.split("-")[0]
    if cy < 0.045:
        return "pallet"
    if base == "top":
        return "stones" if cy >= 1.155 else "rim"
    if glowing or base == "hidden":
        return "embers"
    if cy < 0.27:
        return "plinth"
    if cy < 0.33:
        return "iron"
    if base == "front":
        if cy < 0.93:
            return "iron"
        return "knob" if cz > 0.365 else "panel"
    return "back" if base == "back" else "side"


def grow(pts, px=1.5):
    """Push triangle corners away from the centroid so islands get a small gutter."""
    cx, cy = sum(p[0] for p in pts) / 3, sum(p[1] for p in pts) / 3
    out = []
    for x, y in pts:
        dx, dy = x - cx, y - cy
        d = (dx * dx + dy * dy) ** 0.5 or 1.0
        out.append((x + dx / d * px, y + dy / d * px))
    return out


def main():
    orig = HERE / "originals"
    V, T, F = load_obj(orig / "electric.furnace.obj")
    N = [normal(*(V[i] for i in vi)) for vi, _ in F]
    zone = classify(V, F, N)
    ew, eh, ech, epx = read_png(orig / "ElectricFurnace_em.png")

    fill_c, fill_m, fill_g = MATERIALS["side"]
    diffuse = Image(SIZE, SIZE, (*fill_c, 255))
    metalgloss = Image(SIZE, SIZE, (fill_m, fill_m, fill_m, fill_g))

    def uv_area(f):
        a, b, c = (T[i] for i in F[f][1])
        return abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1]))

    # Material is decided per pixel from the interpolated 3D position, so big panels
    # split cleanly at the height thresholds. Big triangles first: thin details win shared gutters.
    counts = {}
    for f in sorted(range(len(F)), key=lambda f: -uv_area(f)):
        vi, ti = F[f]
        p3 = [V[i] for i in vi]
        pts = [(T[i][0] * SIZE, (1 - T[i][1]) * SIZE) for i in ti]
        g = grow(pts)
        # barycentrics of the grown triangle are not those of the original; map back via the original
        (x0, y0), (x1, y1), (x2, y2) = pts
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0) or 1e-12
        for x, y, *_ in raster(g, SIZE, SIZE):
            px, py = x + 0.5, y + 0.5
            b0 = ((x1 - px) * (y2 - py) - (x2 - px) * (y1 - py)) / area
            b1 = ((x2 - px) * (y0 - py) - (x0 - px) * (y2 - py)) / area
            b0, b1 = min(max(b0, 0.0), 1.0), min(max(b1, 0.0), 1.0 - min(max(b0, 0.0), 1.0))
            b2 = 1 - b0 - b1
            cy = b0 * p3[0][1] + b1 * p3[1][1] + b2 * p3[2][1]
            cz = b0 * p3[0][2] + b1 * p3[1][2] + b2 * p3[2][2]
            e = epx[(min(int(py / SIZE * eh), eh - 1) * ew + min(int(px / SIZE * ew), ew - 1)) * ech]
            m = material(cy, cz, zone[f], e > 60)
            colour, metal, gloss = MATERIALS[m]
            diffuse.set(x, y, (*colour, 255))
            metalgloss.set(x, y, (metal, metal, metal, gloss))
            counts[m] = counts.get(m, 0) + 1

    export = HERE / "export"
    export.mkdir(exist_ok=True)
    diffuse.save(export / "ElectricFurnace_blocking_v0_diffuse.png")
    metalgloss.save(export / "ElectricFurnace_blocking_v0_metalgloss.png")
    render_views(V, T, F, N, HERE / "uv" / "blocking_v0_views.png",
                 tex=read_png(export / "ElectricFurnace_blocking_v0_diffuse.png"))
    total = sum(counts.values())
    print("texture share per material:", {m: f"{c / total:.1%}" for m, c in sorted(counts.items(), key=lambda kv: -kv[1])})


if __name__ == "__main__":
    main()
