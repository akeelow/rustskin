"""Plan v2: texel density (px/cm @1024) and model normal smoothing per island of the Wood Storage Box.
.venv/Scripts/python skins/sauna/wood-storage-box/plan_v2/measure.py"""
import sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from islands import islands  # noqa: E402

OBJ = HERE / "originals" / "box.wooden.obj"
v, vt, vn, F = [], [], [], []
for line in open(OBJ):
    p = line.split()
    if not p:
        continue
    if p[0] == "v": v.append([float(x) for x in p[1:4]])
    elif p[0] == "vt": vt.append([float(x) for x in p[1:3]])
    elif p[0] == "vn": vn.append([float(x) for x in p[1:4]])
    elif p[0] == "f":
        idx = [tuple(int(a) for a in s.split("/")) for s in p[1:]]
        for k in range(1, len(idx) - 1):
            F.append((idx[0], idx[k], idx[k + 1]))
v, vt, vn = map(np.array, (v, vt, vn))
P = np.array([[v[c[0] - 1] for c in t] for t in F])
T = np.array([[vt[c[1] - 1] for c in t] for t in F])
N = np.array([[vn[c[2] - 1] for c in t] for t in F])
I = islands([([c[0] - 1 for c in t], [c[1] - 1 for c in t]) for t in F])
fn = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); A3 = np.linalg.norm(fn, axis=1) / 2
fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-12
A2 = np.abs(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])) / 2
nn = N / (np.linalg.norm(N, axis=2, keepdims=True) + 1e-12)
ang = np.degrees(np.arccos(np.clip(np.einsum("tj,tkj->tk", fn, nn), -1, 1))).max(1)
print(f"{len(v)} v, {len(vn)} vn, {len(F)} tris")
print("isl tris  m2     px/cm  mm/px  nrm  dev med/max  x y z")
for n, fs in enumerate(I):
    fs = np.array(fs); a3 = A3[fs].sum(); a2 = A2[fs].sum()
    d = np.sqrt(a2 / a3) * 1024 / 100 if a3 > 0 else 0
    pp = P[fs].reshape(-1, 3)
    m = (fn[fs] * A3[fs, None]).sum(0); ax = "xyz"[np.abs(m).argmax()]; s = "+" if m[np.abs(m).argmax()] > 0 else "-"
    print(f"{n:2d} {len(fs):4d} {a3:6.3f} {d:6.2f} {10 / d if d else 0:5.2f}  {s}{ax}  {np.median(ang[fs]):5.1f}/{ang[fs].max():5.1f}  "
          f"x{pp[:,0].min():+.2f}..{pp[:,0].max():+.2f} y{pp[:,1].min():.2f}..{pp[:,1].max():.2f} z{pp[:,2].min():+.2f}..{pp[:,2].max():+.2f}")
# rim tops: up-facing faces at the top of the walls (not lid)
up = (fn[:, 1] > 0.9)
for lo, hi in ((0.52, 0.535), (0.535, 0.56)):
    m = up & (P[:, :, 1].mean(1) > lo) & (P[:, :, 1].mean(1) < hi)
    print(f"up-facing tris at y {lo}..{hi}: {m.sum()}, area {A3[m].sum():.4f} m2, px/cm {np.sqrt(A2[m].sum()/max(A3[m].sum(),1e-9))*10.24:.2f}")

# which islands hold the rim tops, the board ends at the corners, the slot cuts
isl = np.empty(len(F), int)
for n, fs in enumerate(I):
    isl[fs] = n
c = P.mean(1)
groups = {
    "rim top (up, y .52-.535)": up & (c[:, 1] > 0.52) & (c[:, 1] < 0.535),
    "corner ends (n along wall, at the corner)": ((np.abs(fn[:, 2]) > 0.9) & (np.abs(c[:, 0]) > 0.33)) | ((np.abs(fn[:, 0]) > 0.9) & (np.abs(c[:, 2]) > 0.44)),
    "slot cut faces (front/back, y .45-.53, |x|<.17)": (np.abs(c[:, 2]) > 0.43) & (c[:, 1] > 0.44) & (c[:, 1] < 0.53) & (np.abs(c[:, 0]) < 0.17) & (np.abs(fn[:, 2]) < 0.5),
}
for name, m in groups.items():
    ids, cnt = np.unique(isl[m], return_counts=True)
    w = np.sqrt(A2[m].sum() / max(A3[m].sum(), 1e-9)) * 10.24
    print(f"{name}: {m.sum()} tris, {A3[m].sum()*1e4:.0f} cm2, {w:.2f} px/cm, islands {dict(zip(ids.tolist(), cnt.tolist()))}")
