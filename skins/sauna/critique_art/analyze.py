"""Critique-only analysis pictures for CRITIQUE_ART.md (Pillow + numpy). Run from the repo root:
  .venv/Scripts/python skins/sauna/critique_art/analyze.py
Needs lineup_day.png / lineup_night.png (lineup.py) next to this file.
"""
from pathlib import Path
import colorsys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

HERE = Path(__file__).resolve().parent
S = HERE.parent
REF = S.parent.parent / "references/sauna/workshop-electric-furnace"


def font(n):
    try:
        return ImageFont.truetype("arial.ttf", n)
    except OSError:
        return ImageFont.load_default()


def fit(im, h):
    return im.resize((max(1, round(im.width * h / im.height)), h), Image.LANCZOS)


def row(images, labels, out, h=420, title=None):
    ims = [fit(i.convert("RGB"), h) for i in images]
    top = 30 if title else 0
    W = sum(i.width for i in ims) + 8 * (len(ims) + 1)
    sheet = Image.new("RGB", (W, h + 26 + top + 8), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    if title:
        d.text((8, 5), title, fill=(255, 255, 255), font=font(18))
    x = 8
    for im, lab in zip(ims, labels):
        sheet.paste(im, (x, top + 26))
        d.text((x, top + 5), lab, fill=(255, 215, 120), font=font(14))
        x += im.width + 8
    sheet.save(out, quality=90)
    print("wrote", out.name)


def squint(name, src, box, note):
    im = Image.open(src).convert("RGB")
    if box:
        im = im.crop(box)
    grey = ImageOps.grayscale(im)
    blur = im.filter(ImageFilter.GaussianBlur(max(im.size) / 28))
    sq = ImageOps.pad(im, (max(im.size), max(im.size)), color=(60, 60, 60))
    i128 = sq.resize((128, 128), Image.LANCZOS)
    i64 = sq.resize((64, 64), Image.LANCZOS)
    icons = Image.new("RGB", (220, 420), (24, 24, 24))
    icons.paste(i128, (10, 30))
    icons.paste(i64, (10, 200))
    icons.paste(ImageOps.grayscale(i64).convert("RGB"), (90, 200))
    d = ImageDraw.Draw(icons)
    d.text((10, 8), "128 px", fill=(200, 200, 200), font=font(13))
    d.text((10, 180), "64 px / ч/б", fill=(200, 200, 200), font=font(13))
    row([im, grey, blur, icons], ["как есть", "ч/б: тональные массы", "прищур (размытие)", "иконка"],
        HERE / f"squint_{name}.jpg", title=f"{name} — {note}")


def kmeans(px, k=6, it=25, seed=0):
    rng = np.random.default_rng(seed)
    c = px[rng.choice(len(px), k, replace=False)].astype(float)
    for _ in range(it):
        lab = np.argmin(((px[:, None, :] - c[None]) ** 2).sum(-1), 1)
        for j in range(k):
            if (lab == j).any():
                c[j] = px[lab == j].mean(0)
    n = np.bincount(lab, minlength=k)
    o = np.argsort(-n)
    return c[o], n[o] / n.sum()


DIFF = {
    "Stove": "electric-furnace/export/ElectricFurnace_v2.8_diffuse.png",
    "Towel Wrap": "burlap-headwrap/export/BurlapHeadwrap_v1_diffuse.png",
    "Robe": "snow-jacket/export/SnowJacket_v2.3_diffuse.png",
    "Locker": "locker/export/Locker_v5.3_diffuse.png",
    "Bench": "bed/export/Bed_v1.2_diffuse.png",
    "Chair": "chair/export/Chair_v1.4_diffuse.png",
    "Stone Box": "wood-storage-box/export/Box_v1.5_diffuse.png",
}
PALETTE = [("свежее дерево", "#C2A77E"), ("дерево от пара", "#7A5A3C"), ("у огня", "#45332A"), ("базальт", "#3D3E41"),
           ("войлок", "#B3A48A"), ("лён", "#CFC6B4"), ("полоса", "#8E3A30"), ("ржавчина", "#8C4A26")]


def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def palette():
    rowh, sw = 74, 110
    W = 190 + sw * 8 + 20
    sheet = Image.new("RGB", (W, rowh * (len(DIFF) + 1) + 50), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    d.text((8, 6), "Палитра: k-means по diffuse (6 главных цветов, фон атласа убран) + «дерево» (медиана тёплых пикселей)",
           fill=(255, 255, 255), font=font(15))
    y = 34
    d.text((8, y + 24), "README сета", fill=(255, 215, 120), font=font(15))
    for i, (n, h) in enumerate(PALETTE):
        d.rectangle((190 + i * sw, y, 190 + (i + 1) * sw - 4, y + rowh - 22), fill=hexrgb(h))
        d.text((190 + i * sw, y + rowh - 20), f"{n} {h}", fill=(200, 200, 200), font=font(10))
    stats = {}
    for r, (name, rel) in enumerate(DIFF.items(), 1):
        im = Image.open(S / rel).convert("RGBA").resize((512, 512), Image.BOX)
        a = np.asarray(im).reshape(-1, 4)
        px = a[a[:, 3] > 128][:, :3].astype(int)
        q = px // 8
        key = q[:, 0] * 1024 + q[:, 1] * 32 + q[:, 2]
        mode = np.bincount(key).argmax()
        if (key == mode).mean() > 0.06:          # flat atlas background
            px = px[key != mode]
        px = px[px.sum(1) > 40]                   # unused black
        rng = np.random.default_rng(1)
        smp = px[rng.choice(len(px), min(20000, len(px)), replace=False)]
        c, w = kmeans(smp)
        hsv = np.array([colorsys.rgb_to_hsv(*(p / 255)) for p in smp])
        wood = smp[(hsv[:, 0] > 0.04) & (hsv[:, 0] < 0.14) & (hsv[:, 1] > 0.18) & (hsv[:, 2] > 0.3) & (hsv[:, 2] < 0.9)]
        med = np.median(wood, 0) if len(wood) > 200 else np.array([0, 0, 0])
        mh = colorsys.rgb_to_hsv(*(med / 255))
        stats[name] = (med, mh, len(wood) / len(smp))
        y = 34 + r * rowh
        d.text((8, y + 24), name, fill=(255, 215, 120), font=font(15))
        for i in range(6):
            col = tuple(int(v) for v in c[i])
            d.rectangle((190 + i * sw, y, 190 + (i + 1) * sw - 4, y + rowh - 22), fill=col)
            d.text((190 + i * sw, y + rowh - 20), "#%02X%02X%02X %d%%" % (*col, round(w[i] * 100)),
                   fill=(200, 200, 200), font=font(10))
        col = tuple(int(v) for v in med)
        d.rectangle((190 + 6 * sw + 20, y, 190 + 8 * sw - 4, y + rowh - 22), fill=col, outline=(255, 255, 255))
        d.text((190 + 6 * sw + 20, y + rowh - 20), "дерево #%02X%02X%02X  S=%d%% V=%d%%" % (*col, mh[1] * 100, mh[2] * 100),
               fill=(255, 255, 255), font=font(10))
    sheet.save(HERE / "palette.png")
    print("wrote palette.png")
    for k, (med, mh, share) in stats.items():
        print("%-11s wood #%02X%02X%02X  H=%.0f S=%.0f%% V=%.0f%% share=%.0f%%"
              % (k, *(int(v) for v in med), mh[0] * 360, mh[1] * 100, mh[2] * 100, share * 100))


def main():
    L = HERE / "lineup_day.png"
    squint("stove", L, (1360, 340, 1600, 705), "рендер lineup, карты v2.8")
    squint("locker", L, (150, 90, 635, 690), "рендер lineup, карты v5.2")
    squint("bench", L, (640, 325, 1045, 805), "рендер lineup, карты v1.2")
    squint("chair", L, (1105, 345, 1315, 705), "рендер lineup, карты v1.4")
    squint("box", L, (1635, 495, 1935, 785), "рендер lineup, карты v1.5")
    squint("robe_ingame", S / "snow-jacket/workshop/ingame/three_quarter_day.jpg", (1450, 60, 1820, 1080),
           "игра, v2.1 (старая карта)")
    squint("robe_render", S / "snow-jacket/workshop/hero.jpg", (480, 130, 1500, 1000), "рендер, v2.3")
    squint("wrap_ingame", S / "burlap-headwrap/workshop/ingame/front_day.jpg", (640, 330, 1220, 1080), "игра, v1")
    lin = Image.open(L)
    row([ImageOps.grayscale(lin)], ["день, ч/б"], HERE / "lineup_day_grey.jpg", h=560)
    row([lin.filter(ImageFilter.GaussianBlur(16))], ["день, прищур"], HERE / "lineup_day_squint.jpg", h=560)
    refs = [REF / "temple-1.jpg", REF / "tomb-of-the-octopus-1.jpg", REF / "bears-for-a-better-world-1.jpg",
            REF / "gear-mechanism-1.jpg"]
    crops = [Image.open(S / "electric-furnace/workshop/studio.jpg").crop((560, 60, 1320, 1050)),
             Image.open(S / "electric-furnace/workshop/ingame/front_night.jpg").crop((700, 60, 1300, 1080))]
    labels = ["НАШ studio.jpg (рендер, первый кадр)", "НАШ ingame front_night (v2.6)", "Temple", "Tomb of the Octopus",
              "Bears for a Better World", "Gear Mechanism"]
    row(crops + [Image.open(r) for r in refs], labels, HERE / "stove_vs_refs.jpg", h=520,
        title="Каменка рядом с принятыми печами (первые кадры страниц)")
    row([c.filter(ImageFilter.GaussianBlur(14)) for c in crops] + [Image.open(r).filter(ImageFilter.GaussianBlur(7)) for r in refs],
        labels, HERE / "stove_vs_refs_squint.jpg", h=360,
        title="То же, прищур: сколько крупных пятен и есть ли главный акцент")
    palette()


if __name__ == "__main__":
    main()
