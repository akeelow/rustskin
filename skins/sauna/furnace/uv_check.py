"""Разбор развёртки Furnace: острова UV, их место на модели, перекрытия и отступы.
Запуск: .venv/Scripts/python skins/sauna/furnace/uv_check.py  -> uv/islands.png, uv/overlap.png, печать таблицы."""
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw
D = Path(__file__).parent
S = 1024
V, T, F = [], [], []
for l in open(D / "originals/furnace.obj"):
    if l.startswith("v "): V.append(list(map(float, l.split()[1:4])))
    elif l.startswith("vt "): T.append(list(map(float, l.split()[1:3])))
    elif l.startswith("f "):
        p = [x.split("/") for x in l.split()[1:]]
        for k in range(1, len(p) - 1):
            F.append([[int(p[0][0]) - 1, int(p[k][0]) - 1, int(p[k + 1][0]) - 1],
                      [int(p[0][1]) - 1, int(p[k][1]) - 1, int(p[k + 1][1]) - 1]])
V, T, F = np.array(V), np.array(T), np.array(F)
# острова = связные компоненты по индексам vt
par = list(range(len(T)))
def find(a):
    while par[a] != a:
        par[a] = par[par[a]]; a = par[a]
    return a
for f in F[:, 1]:
    a, b, c = map(find, f); par[b] = a; par[c] = a
root = np.array([find(f[0]) for f in F[:, 1]])
ids = {r: i for i, r in enumerate(sorted(set(root), key=lambda r: -np.sum(root == r)))}
isl = np.array([ids[r] for r in root])
cx, cz = V[:, 0].mean(), V[:, 2].mean()
print("axis", cx, cz, "islands", len(ids))
cover = np.zeros((S, S), np.int32); label = np.full((S, S), -1, np.int32)
pal = [(200, 80, 60), (70, 140, 220), (90, 190, 110), (230, 190, 60), (170, 90, 210), (80, 200, 200), (230, 130, 180), (150, 150, 150)]
img = Image.new("RGB", (S, S), (20, 20, 24)); dr = ImageDraw.Draw(img)
for i in range(len(ids)):
    m = isl == i
    tri = F[m]
    P = V[tri[:, 0]]; UV = T[tri[:, 1]]
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); n /= np.linalg.norm(n, axis=1)[:, None] + 1e-12
    c = P.mean(1); rad = np.stack([c[:, 0] - cx, 0 * c[:, 0], c[:, 2] - cz], 1); r = np.linalg.norm(rad, axis=1)
    outward = (n * rad).sum(1) / (r + 1e-9)
    a3 = 0.5 * np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1).sum()
    e1 = UV[:, 1] - UV[:, 0]; e2 = UV[:, 2] - UV[:, 0]
    auv = 0.5 * np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]).sum()
    one = Image.new("L", (S, S), 0); d1 = ImageDraw.Draw(one)
    for uv in UV:
        pts = [(u * S, (1 - v) * S) for u, v in uv]
        d1.polygon(pts, fill=1); dr.polygon(pts, fill=pal[i % len(pal)], outline=(0, 0, 0))
    a = np.asarray(one)
    cover += a; label[(a > 0) & (label < 0)] = i
    u0, v0 = UV.reshape(-1, 2).min(0); u1, v1 = UV.reshape(-1, 2).max(0)
    print(f"island {i}: tris {m.sum():4d} uv x {u0:.3f}-{u1:.3f} y(top) {1-v1:.3f}-{1-v0:.3f} | Y {P[...,1].min():.2f}-{P[...,1].max():.2f} r {r.min():.2f}-{r.max():.2f} outward {outward.mean():+.2f} ny {n[:,1].mean():+.2f} | texel density {np.sqrt(auv/a3)*S:.0f} px/m")
img.save(D / "uv/islands.png")
ov = cover > 1
print("overlap px", int(ov.sum()))
o = np.zeros((S, S, 3), np.uint8); o[cover == 1] = (60, 60, 70); o[ov] = (255, 40, 40)
Image.fromarray(o).save(D / "uv/overlap.png")
# отступ между островами: минимальное расстояние от острова до любого другого
for i in range(len(ids)):
    other = (label >= 0) & (label != i)
    mine = label == i; gap = None
    if not mine.any():
        print(f"island {i}: целиком лежит поверх другого острова"); continue
    for k in range(1, 40):  # расширяем остров на k px, пока не заденет чужой
        g = mine.copy()
        for _ in range(k):
            g2 = g.copy(); g2[1:] |= g[:-1]; g2[:-1] |= g[1:]; g2[:, 1:] |= g[:, :-1]; g2[:, :-1] |= g[:, 1:]; g = g2
        if (g & other).any(): gap = k; break
    print(f"island {i}: gap to nearest island ~{gap} px; to texture edge {min(np.argwhere(mine).min(), S-1-np.argwhere(mine).max())} px")
# профиль корпуса
print("profile (y: r min/mean/max over verts)")
r = np.hypot(V[:, 0] - cx, V[:, 2] - cz)
for y0 in np.arange(0, 1.6, 0.1):
    m = (V[:, 1] >= y0) & (V[:, 1] < y0 + 0.1)
    if m.any(): print(f" {y0:.1f}: {r[m].min():.2f} {r[m].mean():.2f} {r[m].max():.2f} n={m.sum()}")
