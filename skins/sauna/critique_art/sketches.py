"""Critique-only overpaint sketches ("эскиз идеи, не финал"). Run from the repo root:
  .venv/Scripts/python skins/sauna/critique_art/sketches.py
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

HERE = Path(__file__).resolve().parent
S = HERE.parent
BRICK = (142, 58, 48)
LINEN = (207, 198, 180)
LEAF = (120, 132, 60)


def font(n):
    try:
        return ImageFont.truetype("arial.ttf", n)
    except OSError:
        return ImageFont.load_default()


def tint(base, draw_fn, opacity=0.85, blur=1.2):
    """Paint with draw_fn on a layer, multiply it by the base luminance a little so the shading survives."""
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    a = layer.getchannel("A").point(lambda v: int(v * opacity))
    out = base.copy()
    out.paste(layer.convert("RGB"), (0, 0), a)
    return out


def pair(before, after, out, title):
    h = 640
    b = before.resize((round(before.width * h / before.height), h), Image.LANCZOS)
    a = after.resize((round(after.width * h / after.height), h), Image.LANCZOS)
    sheet = Image.new("RGB", (b.width + a.width + 24, h + 64), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    d.text((8, 6), title, fill=(255, 255, 255), font=font(18))
    d.text((8, 36), "сейчас", fill=(255, 215, 120), font=font(15))
    d.text((b.width + 16, 36), "ЭСКИЗ ИДЕИ, НЕ ФИНАЛ (оверпейнт)", fill=(255, 140, 90), font=font(15))
    sheet.paste(b, (8, 58))
    sheet.paste(a, (b.width + 16, 58))
    sheet.save(out, quality=90)
    print("wrote", out.name)


def leaf(d, x, y, r, col=LEAF):
    d.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=(*col, 255))
    d.line((x - r * 1.5, y + r * 0.5, x + r * 0.8, y - r * 0.2), fill=(70, 70, 30, 255), width=max(1, int(r / 5)))


def locker():
    im = Image.open(HERE / "lineup_day.png").convert("RGB").crop((150, 90, 635, 690))
    im = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)

    def towel(d, x0, y0, w, h):
        d.ellipse((x0 + w / 2 - 7, y0 - 12, x0 + w / 2 + 7, y0 + 2), fill=(90, 62, 40, 255))          # peg
        d.polygon([(x0 + w * 0.42, y0 - 4), (x0 + w * 0.58, y0 - 4), (x0 + w, y0 + h * 0.16), (x0 + w, y0 + h),
                   (x0, y0 + h), (x0, y0 + h * 0.16)], fill=(*LINEN, 255))
        for k, t in ((0.74, 0.07), (0.84, 0.03)):
            d.rectangle((x0, y0 + h * k, x0 + w, y0 + h * (k + t)), fill=(*BRICK, 255))
        for fx in (0.3, 0.62):                                                                      # folds
            d.line((x0 + w * fx, y0 + h * 0.2, x0 + w * fx, y0 + h), fill=(150, 140, 122, 255), width=3)

    def paint(d):
        towel(d, 108, 520, 110, 270)                 # left niche, middle bay: the set's striped towel on a peg
        towel(d, 740, 205, 96, 215)                  # right niche, top bay: second towel, shorter
        leaf(d, 560, 1030, 13, (170, 150, 50))
    out = tint(im, paint, 0.9, 1.0)
    shade = Image.new("RGB", out.size, (255, 255, 255))
    sd = ImageDraw.Draw(shade)
    sd.rectangle((108, 520, 150, 790), fill=(170, 160, 150))      # the niche's own shadow falls on the towel too
    sd.rectangle((740, 205, 770, 420), fill=(185, 175, 165))
    out = ImageChops.multiply(out, shade.filter(ImageFilter.GaussianBlur(14)))
    pair(im, out, HERE / "sketch_locker_towels.jpg",
         "Шкафчик: вернуть полотенце сета в ниши (плоская вещь на плоской стенке — не наклейка)")


def robe_back():
    im = Image.open(S / "snow-jacket/workshop/back.jpg").convert("RGB").crop((480, 90, 1560, 1000))

    def paint(d):
        # wide + narrow brick stripe across the hem, as on every towel of the set
        d.line([(255, 700), (430, 735), (640, 742), (730, 722)], fill=(*BRICK, 255), width=26, joint="curve")
        d.line([(258, 668), (432, 702), (640, 709), (728, 690)], fill=(*BRICK, 255), width=9, joint="curve")
        # hanging loop at the collar
        d.arc((455, 118, 505, 178), 20, 160, fill=(*BRICK, 255), width=6)
        # the bath leaf stuck between the shoulder blades
        leaf(d, 560, 300, 20)
    out = tint(im, paint, 0.72, 1.6)
    pair(im, out, HERE / "sketch_robe_back.jpg",
         "Халат, спина: полоса полотенца по подолу, петля-вешалка, прилипший банный лист")


if __name__ == "__main__":
    locker()
    robe_back()
