"""Sauna Robe v3: low-poly shape measurements for PLAN_v3.md (Blender -b, no GPU).

  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/snow-jacket/measure_v3.py

Prints:
  - how far the flaps (islands 5, 6, 8, 9) stand off the torso (distance from their vertices to island 0);
  - the front profile across the zip placket: torso surface depth z(x) at several heights (rays along -z);
  - the waist: circumference of the torso at several heights (rays from the y axis outwards);
  - triangle edge lengths (for the dense copy) per island.
"""
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
sys.path.insert(0, str(HERE))
from uv_zones import load_obj  # noqa: E402
from islands_v3 import islands  # noqa: E402

V, T, F = load_obj(HERE / "originals" / "jacket.snow.obj")
I = islands(F)
fi = {}
for n, fs in enumerate(I):
    for f in fs:
        fi[f] = n


def bvh(isls):
    tris = [list(F[f][0]) for f in range(len(F)) if fi[f] in isls]
    return BVHTree.FromPolygons([Vector(v) for v in V], tris)


torso = bvh({0, 3})
print("== flaps: stand-off from the torso (mm): median / max, and size (cm)")
for n in (5, 6, 8, 9, 10, 4, 7, 11, 12):
    vs = sorted({i for f in I[n] for i in F[f][0]})
    d = [torso.find_nearest(Vector(V[i]))[3] * 1000 for i in vs]
    P = np.array([V[i] for i in vs])
    ext = (P.max(0) - P.min(0)) * 100
    print(f"  #{n}: {np.median(d):.1f} / {max(d):.1f} mm; extent x {ext[0]:.1f} y {ext[1]:.1f} z {ext[2]:.1f} cm")

front = bvh({0})
print("== front profile: z of the torso front surface (mm) at x (cm) = -8..+8, rays along -z")
xs = [-8, -6, -4, -3, -2, -1, 0, 1, 2, 3, 4, 6, 8]
print("  y\\x " + " ".join(f"{x:+5d}" for x in xs))
for y in (0.30, 0.40, 0.50, 0.60, 0.70, 0.78):
    row = []
    for x in xs:
        hit = front.ray_cast(Vector((x / 100, y, 0.5)), Vector((0, 0, -1)))
        row.append(f"{hit[0].z * 1000:5.0f}" if hit[0] else "    -")
    print(f"  {y:.2f} " + " ".join(row))

body = bvh({0, 3})
print("== torso circumference (cm) at heights, rays from the axis outwards (36 rays)")
for y in (0.25, 0.35, 0.42, 0.46, 0.50, 0.54, 0.60, 0.70):
    pts = []
    for k in range(72):
        a = 2 * math.pi * k / 72
        d = Vector((math.sin(a), 0, math.cos(a)))
        hit = body.ray_cast(Vector((0, y, -0.02)) + d * 0.6, -d)
        if hit[0]:
            pts.append(hit[0])
    if len(pts) > 10:
        circ = sum((pts[i] - pts[i - 1]).length for i in range(len(pts)))
        print(f"  y {y:.2f}: {circ * 100:.1f} cm ({len(pts)} hits)")

print("== edge lengths per island (cm): median / max")
for n, fs in enumerate(I):
    L = []
    for f in fs:
        a, b, c = (np.array(V[i]) for i in F[f][0])
        L += [np.linalg.norm(b - a), np.linalg.norm(c - b), np.linalg.norm(a - c)]
    print(f"  #{n}: {np.median(L) * 100:.1f} / {max(L) * 100:.1f}")
