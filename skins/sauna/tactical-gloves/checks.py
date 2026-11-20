"""Проверки Sauna Mitts (.venv): атлас островов, отступы, швы, растяжение, Spec/Gloss по зонам, ч/б и иконки.

python skins/sauna/tactical-gloves/checks.py [--ver v1] [--atlas-only]
Выход: uv/islands_atlas.png, uv/white.png, uv/<ver>_checks.md, renders/<ver>_icons.png
"""
import os
import sys
from collections import defaultdict

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[1:]
VER = ARGS[ARGS.index("--ver") + 1] if "--ver" in ARGS else "v1"
EX = os.path.join(HERE, "export")
NAMES = {1: "тыл", 2: "ладонь", 3: "манжета A", 4: "манжета B", 5: "узел", 6: "палочка", 7: "конец ремешка"}
IDS = {1: "войлок", 2: "кожа", 3: "кожа-подложка", 4: "береста", 5: "нить", 6: "лён", 7: "полоса", 8: "джут",
       9: "дерево"}


def atlas():
    ids = np.asarray(Image.open(os.path.join(HERE, "uv", "ids_2048.png")))
    pal = {0: (40, 40, 40), 1: (214, 120, 90), 2: (90, 150, 214), 3: (120, 200, 110), 4: (220, 200, 90),
           5: (200, 110, 210), 6: (110, 210, 210), 7: (240, 150, 40)}
    im = np.zeros(ids.shape + (3,), np.uint8)
    for k, c in pal.items():
        im[ids == k] = c
    # сетка 1 см (по плотности ~6 px/мм в 2048): видно растяжение и направление
    yy, xx = np.mgrid[0:2048, 0:2048]
    grid = ((xx % 60) < 2) | ((yy % 60) < 2)
    im[grid & (ids > 0)] = (im[grid & (ids > 0)] * 0.55).astype(np.uint8)
    img = Image.fromarray(im)
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=90)
    except TypeError:
        font = ImageFont.load_default()
    for k in range(1, 8):
        ys, xs = np.where(ids == k)
        if len(xs):
            d.text((int(np.median(xs)) - 25, int(np.median(ys)) - 45), str(k), fill=(255, 255, 255), font=font,
                   stroke_width=5, stroke_fill=(0, 0, 0))
    img.save(os.path.join(HERE, "uv", "islands_atlas.png"))
    Image.new("RGB", (64, 64), (255, 255, 255)).save(os.path.join(HERE, "uv", "white.png"))


def dilate(m, r):
    m = m.copy()
    for _ in range(r):
        m = m | np.roll(m, 1, 0) | np.roll(m, -1, 0) | np.roll(m, 1, 1) | np.roll(m, -1, 1)
    return m


def main():
    atlas()
    if "--atlas-only" in ARGS:
        return
    out = [f"# Проверки {VER}", ""]
    pr = out.append
    ids = np.asarray(Image.open(os.path.join(HERE, "uv", "ids_2048.png")))
    isl = ids > 0
    dif = np.asarray(Image.open(os.path.join(EX, f"SaunaMitts_{VER}_diffuse.png")).convert("RGB"), np.float32)
    nrm = np.asarray(Image.open(os.path.join(EX, f"SaunaMitts_{VER}_normal.png")).convert("RGB"), np.float32)
    sg = np.asarray(Image.open(os.path.join(EX, f"SaunaMitts_{VER}_specgloss.png")).convert("RGBA"), np.float32)

    # 1. отступы: полоса 8 px вокруг островов не должна быть пустой (чёрной) и не должна резко отличаться
    band = dilate(isl, 8) & ~isl
    black = (dif[band].sum(1) < 6).mean() * 100
    flatn = (np.abs(nrm[band] - [128, 128, 255]).sum(1) < 3).mean() * 100
    pr("## Отступы (2048)")
    pr(f"- полоса 8 px вокруг островов: чёрных пикселей Diffuse {black:.2f} % (норма 0), плоской нормали {flatn:.1f} %")
    # минимальный зазор между островами (расстояние до чужого острова)
    gaps = []
    for k in range(1, 8):
        m = ids == k
        other = isl & ~m
        g = dilate(m, 8) & other
        gaps.append((k, int(g.sum())))
    pr("- острова, у которых в 8 px есть чужой остров (пиксели): " + ", ".join(f"{NAMES[k]} {v}" for k, v in gaps))
    pr("")

    # 1б. брак запекания: нормаль наклонена больше 60° (z < 0.5) — почти всегда промах луча, а не рельеф
    nz = nrm[..., 2] / 127.5 - 1
    pr("## Брак нормали (наклон > 60°, доля пикселей острова)")
    pr("| остров | > 60° | > 45° |")
    pr("|---|---:|---:|")
    for k in range(1, 8):
        m = ids == k
        pr(f"| {NAMES[k]} | {(nz[m] < 0.5).mean() * 100:.2f} % | {(nz[m] < 0.707).mean() * 100:.2f} % |")
    pr("")

    # 2. швы: цвет и нормаль по обе стороны UV-шва в одной 3D-точке
    G = np.load(os.path.join(HERE, "source", "glove_r.npz"))
    V, T, F, FT, fi = G["V"], G["T"], G["F"], G["FT"], G["isl"]
    edges = defaultdict(list)
    for f, (vv, tt) in enumerate(zip(F, FT)):
        for a in range(3):
            b = (a + 1) % 3
            key = (min(vv[a], vv[b]), max(vv[a], vv[b]))
            edges[key].append((f, tt[a] if vv[a] < vv[b] else tt[b], tt[b] if vv[a] < vv[b] else tt[a]))
    diffs = defaultdict(list)
    ndiffs = defaultdict(list)
    for key, fl in edges.items():
        if len(fl) != 2:
            continue
        (f1, a1, b1), (f2, a2, b2) = fl
        if a1 == a2 and b1 == b2:
            continue
        for w in (0.25, 0.5, 0.75):
            p1 = T[a1] * (1 - w) + T[b1] * w
            p2 = T[a2] * (1 - w) + T[b2] * w
            # чуть внутрь своей грани
            c1 = T[FT[f1]].mean(0)
            c2 = T[FT[f2]].mean(0)
            p1 = p1 + (c1 - p1) * 0.08
            p2 = p2 + (c2 - p2) * 0.08
            x1, y1 = int(p1[0] * 2048), int((1 - p1[1]) * 2048)
            x2, y2 = int(p2[0] * 2048), int((1 - p2[1]) * 2048)
            if not (0 <= x1 < 2048 and 0 <= y1 < 2048 and 0 <= x2 < 2048 and 0 <= y2 < 2048):
                continue
            pair = tuple(sorted((fi[f1], fi[f2])))
            diffs[pair].append(np.abs(dif[y1, x1] - dif[y2, x2]).mean())
            ndiffs[pair].append(np.abs(nrm[y1, x1, 2] - nrm[y2, x2, 2]))
    pr("## UV-швы: разница по обе стороны (Diffuse, 0–255; Normal.z)")
    pr("| пара островов | точек | Diffuse медиана | 90 % | Normal.z медиана |")
    pr("|---|---:|---:|---:|---:|")
    for pair, v in sorted(diffs.items()):
        v = np.array(v)
        pr(f"| {NAMES[pair[0]]} / {NAMES[pair[1]]} | {len(v)} | {np.median(v):.1f} | {np.percentile(v, 90):.1f} | "
           f"{np.median(ndiffs[pair]):.1f} |")
    pr("")

    # 3. растяжение текселя: отношение главных масштабов UV-якобиана на гранях пальцев
    pr("## Растяжение текселя (px/мм в 2048, по граням)")
    P = V[F] * 1000
    Q = T[FT] * 2048
    rows = []
    for k in (1, 2, 3, 4):
        m = fi == k
        an, dn = [], []
        for p, q in zip(P[m], Q[m]):
            e1, e2 = p[1] - p[0], p[2] - p[0]
            u1 = e1 / (np.linalg.norm(e1) + 1e-12)
            nn = np.cross(e1, e2)
            u2 = np.cross(nn, u1)
            u2 /= np.linalg.norm(u2) + 1e-12
            A = np.array([[e1 @ u1, e2 @ u1], [e1 @ u2, e2 @ u2]])
            B = np.array([q[1] - q[0], q[2] - q[0]]).T
            try:
                J = B @ np.linalg.inv(A)
            except np.linalg.LinAlgError:
                continue
            s = np.linalg.svd(J, compute_uv=False)
            an.append(s[0] / max(s[1], 1e-6))
            dn.append(np.sqrt(s[0] * s[1]))
        an, dn = np.array(an), np.array(dn)
        rows.append(f"| {NAMES[k]} | {np.median(dn):.1f} | {np.percentile(dn, 5):.1f}–{np.percentile(dn, 95):.1f} | "
                    f"{np.median(an):.2f} | {np.percentile(an, 95):.2f} |")
    pr("| остров | px/мм медиана | 5–95 % | анизотропия медиана | 95 % |")
    pr("|---|---:|---:|---:|---:|")
    out.extend(rows)
    pr("")

    # 4. Spec/Gloss по материалам
    idb = np.asarray(Image.open(os.path.join(HERE, "source", "bake", "id.png")).convert("RGB"))[..., 0]
    idb = np.round((idb.astype(np.float32) - 8) / 16).astype(int)
    idb = idb[::2, ::2]
    pr("## Spec/Gloss по материалам (0–255; ползунки Spec Color 255, Glossiness 1.00)")
    pr("| материал | доля | блик медиана | глянец медиана | глянец 95 % |")
    pr("|---|---:|---:|---:|---:|")
    for k, nm in IDS.items():
        m = (idb == k) & isl
        if m.sum() < 50:
            continue
        pr(f"| {nm} | {m.mean() * 100:.1f} % | {np.median(sg[m, 0]):.0f} | {np.median(sg[m, 3]):.0f} | "
           f"{np.percentile(sg[m, 3], 95):.0f} |")
    pr("")
    open(os.path.join(HERE, "uv", f"{VER}_checks.md"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    print("\n".join(out))

    # 5. ч/б и иконки из кадра «от первого лица»
    fp = os.path.join(HERE, "renders", f"{VER}_fp_day.png")
    if os.path.exists(fp):
        im = Image.open(fp).convert("RGB")
        w = im.width
        sheet = Image.new("RGB", (w + w // 2 + 20, w), (30, 30, 30))
        sheet.paste(ImageOps.grayscale(im).convert("RGB").resize((w // 2, w // 2)), (w + 20, 0))
        i128 = im.resize((128, 128), Image.LANCZOS)
        i64 = im.resize((64, 64), Image.LANCZOS)
        sheet.paste(im, (0, 0))
        sheet.paste(i128.resize((256, 256), Image.NEAREST), (w + 20, w // 2 + 20))
        sheet.paste(i64.resize((256, 256), Image.NEAREST), (w + 20 + 280, w // 2 + 20))
        sheet.save(os.path.join(HERE, "renders", f"{VER}_icons.png"))
        print("иконки: renders/%s_icons.png" % VER)


if __name__ == "__main__":
    main()
