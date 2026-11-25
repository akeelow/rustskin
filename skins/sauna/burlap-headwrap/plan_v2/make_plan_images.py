"""Картинки для PLAN_v2.md: сравнение с кэшем (вырезы Diffuse + Normal) и карта плотности текселей.
Запуск (.venv): python skins/sauna/burlap-headwrap/plan_v2/make_plan_images.py"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = 'C:/Program Files (x86)/Steam/steamapps/workshop/content/252490/'
F = ImageFont.truetype('arial.ttf', 18)
OUT = os.path.join(HERE, 'plan_v2')

srcs = [('Оригинал Facepunch', 'originals/burlapheadwraps_01_bc.png', 'originals/burlapheadwraps_01_nrm.png'),
        ('Наш v1.3 (опубликован, кэш 3840341829)', B + '3840341829/_MainTex0.png', B + '3840341829/_BumpMap0.png'),
        ('Чужой скин 3817263539 (в кэше, не из принятых)', B + '3817263539/_MainTex0.png', B + '3817263539/_BumpMap0.png')]
regs = [(300, 640, 700, 900), (150, 380, 550, 600)]   # лоб и прорезь; воротник (в пикселях 1024)
rows = []
for name, d, n in srcs:
    D = Image.open(d if d.startswith('C:') else os.path.join(HERE, d)).convert('RGB')
    N = Image.open(n if n.startswith('C:') else os.path.join(HERE, n)).convert('RGB')
    rows.append((name, [im.crop(r) for r in regs for im in (D, N)]))
W = sum(t.size[0] for t in rows[0][1]) + 30
H = sum(max(t.size[1] for t in r) + 28 for _, r in rows)
im = Image.new('RGB', (W, H), (20, 20, 24))
dr = ImageDraw.Draw(im)
y = 0
for name, row in rows:
    dr.text((6, y + 4), name + ' — слева лоб и прорезь (Diffuse, Normal), справа воротник', fill=(255, 255, 255), font=F)
    y += 28
    x = 0
    for t in row:
        im.paste(t, (x, y))
        x += t.size[0] + 10
    y += max(t.size[1] for t in row)
im.save(os.path.join(OUT, 'compare_cache.jpg'), quality=88)

# карта плотности: px/см при 1024 для каждой наружной грани
V, T, Fc = [], [], []
for line in open(os.path.join(HERE, 'originals', 'burlap.headwrap.obj')):
    p = line.split()
    if not p:
        continue
    if p[0] == 'v':
        V.append([float(x) for x in p[1:4]])
    elif p[0] == 'vt':
        T.append([float(x) for x in p[1:3]])
    elif p[0] == 'f':
        Fc.append([[int(i) - 1 for i in q.split('/')] for q in p[1:]])
V, T, Fc = np.array(V), np.array(T), np.array(Fc)
P = V[Fc[:, :, 0]]
t = T[Fc[:, :, 1]]
A3 = 0.5 * np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1)
A2 = 0.5 * np.abs((t[:, 1, 0] - t[:, 0, 0]) * (t[:, 2, 1] - t[:, 0, 1]) - (t[:, 2, 0] - t[:, 0, 0]) * (t[:, 1, 1] - t[:, 0, 1]))
dens = np.sqrt(A2 / np.maximum(A3, 1e-12)) * 1024 / 100
R = 1024
img = np.zeros((R, R, 3), np.uint8)
bc = np.asarray(Image.open(os.path.join(HERE, 'originals/burlapheadwraps_01_bc.png')).convert('RGB')).astype(float)
img[:] = (bc * 0.25).astype(np.uint8)
ys, xs = np.mgrid[0:R, 0:R]
Pt = np.stack([xs + 0.5, ys + 0.5], -1)


def col(v):  # 6 → красный, 12 → жёлтый, 18 → зелёный
    k = np.clip((v - 6) / 12, 0, 1)
    return np.array([255 * min(1, 2 - 2 * k), 255 * min(1, 2 * k), 40])


for i in range(len(Fc)):
    p = np.array([[u * R, (1 - v) * R] for u, v in t[i]])
    x0, y0 = np.floor(p.min(0)).astype(int)
    x1, y1 = np.ceil(p.max(0)).astype(int)
    sub = Pt[y0:y1 + 1, x0:x1 + 1]
    a, b, c = p
    e = lambda p0, p1: (p1[0] - p0[0]) * (sub[..., 1] - p0[1]) - (p1[1] - p0[1]) * (sub[..., 0] - p0[0])
    w0, w1, w2 = e(b, c), e(c, a), e(a, b)
    ins = ((w0 >= 0) & (w1 >= 0) & (w2 >= 0)) | ((w0 <= 0) & (w1 <= 0) & (w2 <= 0))
    img[y0:y1 + 1, x0:x1 + 1][ins] = (0.45 * col(dens[i]) + 0.55 * bc[y0:y1 + 1, x0:x1 + 1][ins]).astype(np.uint8)
im = Image.fromarray(img).crop((0, 360, 1024, 1024))
dr = ImageDraw.Draw(im)
dr.text((8, 8), 'px/см при 1024: красный 6, жёлтый 12, зелёный 18+', fill=(255, 255, 255), font=F)
im.save(os.path.join(OUT, 'density_atlas.jpg'), quality=88)
print('ok')
