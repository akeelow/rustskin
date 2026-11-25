"""v2 разбор: что лежит в островах наружных досок (грани по направлениям, габариты), контуры прорезей."""
import sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from islands import islands  # noqa
OBJ = HERE / "originals" / "box.wooden.obj"
v, vt, F = [], [], []
for line in open(OBJ):
    p = line.split()
    if not p: continue
    if p[0] == "v": v.append([float(x) for x in p[1:4]])
    elif p[0] == "vt": vt.append([float(x) for x in p[1:3]])
    elif p[0] == "f":
        idx = [tuple(int(a) for a in s.split("/")) for s in p[1:]]
        for k in range(1, len(idx) - 1): F.append((idx[0], idx[k], idx[k + 1]))
v = np.array(v) * 100; vt = np.array(vt)
P = np.array([[v[c[0] - 1] for c in t] for t in F])
I = islands([([c[0] - 1 for c in t], [c[1] - 1 for c in t]) for t in F])
isl = np.empty(len(F), int)
for n, fs in enumerate(I): isl[fs] = n
fn = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); A = np.linalg.norm(fn, axis=1) / 2
fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-12
lab = np.array(["+x", "-x", "+y", "-y", "+z", "-z"])
dirs = np.array([[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]])
d = lab[(fn @ dirs.T).argmax(1)]
WALLS = {"left -x": [13, 7, 6, 8], "right +x": [15, 12, 2, 0], "front +z": [14, 27, 25, 16], "back -z": [22, 11, 4, 21]}
for w, ids in WALLS.items():
    print("==", w)
    for i in ids:
        m = isl == i
        pp = P[m].reshape(-1, 3)
        s = {k: round(A[m & (d == k)].sum(), 1) for k in lab if (m & (d == k)).any()}
        print(f"  #{i}: x {pp[:,0].min():.1f}..{pp[:,0].max():.1f} y {pp[:,1].min():.1f}..{pp[:,1].max():.1f} z {pp[:,2].min():.1f}..{pp[:,2].max():.1f}  area by dir cm2 {s}")
fl = isl == 35
pp = P[fl].reshape(-1, 3)
print("floor #35", pp.min(0).round(1), pp.max(0).round(1))
# slot: faces of front/back top boards facing +-y or along x inside |x|<17
for i in (14, 22):
    m = (isl == i) & (np.abs(P.mean(1)[:, 0]) < 17.5) & (np.abs(fn[:, 2]) < 0.5)
    pp = P[m].reshape(-1, 3)
    print(f"slot faces in #{i}: {m.sum()} x {pp[:,0].min():.1f}..{pp[:,0].max():.1f} y {pp[:,1].min():.1f}..{pp[:,1].max():.1f} z {pp[:,2].min():.1f}..{pp[:,2].max():.1f}")
for i in (10, 37):
    m = (isl == i) & (P.mean(1)[:, 1] < 52)
    if m.any():
        pp = P[m].reshape(-1, 3); print(f"low faces in lid island #{i}: {m.sum()}", pp.min(0).round(1), pp.max(0).round(1), d[m])
# vertices of the slot outline on the front outer face
m = (isl == 14) & (fn[:, 2] > 0.7)
pp = np.unique(P[m].reshape(-1, 3).round(2), axis=0)
sl = pp[(np.abs(pp[:, 0]) < 18) & (pp[:, 1] < 46)]
print("front slot outline verts (x,y):", sorted(map(tuple, sl[:, :2].round(1))))
print("== outer face flatness (coordinate along the wall normal): min..max, and +y cap height range")
ax = {"left -x": (0, "-x"), "right +x": (0, "+x"), "front +z": (2, "+z"), "back -z": (2, "-z")}
for w, ids in WALLS.items():
    k, dd = ax[w]
    for i in ids:
        m = (isl == i) & (d == dd)
        pp = P[m].reshape(-1, 3)
        cap = (isl == i) & (d == "+y")
        cp = P[cap].reshape(-1, 3)
        bot = (isl == i) & (d == "-y")
        bp = P[bot].reshape(-1, 3)
        print(f"  #{i}: outer {pp[:,k].min():.2f}..{pp[:,k].max():.2f}  top cap y {cp[:,1].min():.2f}..{cp[:,1].max():.2f}  bottom y {bp[:,1].min():.2f}..{bp[:,1].max():.2f}  "
              f"outer y {pp[:,1].min():.2f}..{pp[:,1].max():.2f}")
# OBJ polygon order check material
