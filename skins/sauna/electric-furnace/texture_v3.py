"""Sauna Stove v3.0: текстуры по запечённым картам (bake/v3, 4096) -> export/ElectricFurnace_<tag>_*.png (2048).

Цвет и материал — по маскам той же геометрии (fields_v3.py): рельеф и цвет совпадают пиксель в пиксель. 2D здесь
только то, у чего нет формы: тон, копоть, вода, ржавые ореолы, накипь цветом, свечение.
Тексели, которые ещё не переделаны (вертикальный срез), берутся из v2.9.

Слоты Electric Furnace (все 2048, как у принятых скинов в кэше Steam — PLAN_v3.md §0.2):
  Diffuse (+ _diffuse_cutout с альфой спиралей), Normal, Metal/Gloss (RGB — металличность, A — глянец),
  Occlusion, Emission.

  .venv/Scripts/python skins/sauna/electric-furnace/texture_v3.py [--tag v3.0]
"""
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fields_v3 as FV  # noqa: E402

BAKE = HERE / "bake" / "v3"
EXP = HERE / "export"
PREV = "v2.9"
EXPORT = 2048
M = FV.MAT
POS_LO, POS_SPAN = np.array([-40.0, 0.0, -40.0]), np.array([80.0, 120.0, 80.0])

Image.MAX_IMAGE_PIXELS = None


def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255


def load(name, mode="RGB"):
    return np.asarray(Image.open(BAKE / f"{name}.png").convert(mode), np.float32) / 255


def fblur(a, r, passes=3):
    a = a.astype(np.float32)
    for _ in range(passes):
        for ax in (0, 1):
            pad = [(0, 0)] * a.ndim
            pad[ax] = (r + 1, r)
            c = np.cumsum(np.pad(a, pad, mode="edge"), axis=ax, dtype=np.float64)
            hi = np.take(c, np.arange(2 * r + 1, c.shape[ax]), axis=ax)
            lo = np.take(c, np.arange(0, c.shape[ax] - 2 * r - 1), axis=ax)
            a = ((hi - lo) / (2 * r + 1)).astype(np.float32)
    return a


def mix(col, c, t):
    t = np.asarray(t, np.float32)
    if t.ndim == col.ndim - 1:
        t = t[..., None]
    return col * (1 - t) + np.asarray(c, np.float32) * t


def noise2(shape, cell, seed):
    """Плавный шум по текселям (для тона) — билинейная решётка."""
    rng = np.random.default_rng(seed)
    gy, gx = shape[0] // cell + 2, shape[1] // cell + 2
    g = rng.random((gy, gx)).astype(np.float32)
    im = Image.fromarray(g, "F").resize((gx * cell, gy * cell), Image.BICUBIC)
    return np.asarray(im, np.float32)[:shape[0], :shape[1]]


def build():
    t0 = time.time()
    mask = load("mask", "L") > 0.5
    ao = load("ao", "L")
    m1, m2, m3, idc, pos = (load(k) for k in ("m1", "m2", "m3", "idc", "pos"))
    nrm = load("normal")
    grain, cav, dent = m1[..., 0], m1[..., 1], m1[..., 2]
    nail, knot, char = m2[..., 0], m2[..., 1], m2[..., 2]
    rust, crust, tone = m3[..., 0], m3[..., 1], m3[..., 2]
    mat = np.round(idc[..., 0] * 32).astype(np.int32)
    sidm = np.round(idc[..., 1] * 32).astype(np.int32) - 1          # номер детали (камни топки = 6, угли = 7)
    bark = idc[..., 2]
    P = POS_LO + pos * POS_SPAN            # см, координаты OBJ
    X, Y, Z = P[..., 0], P[..., 1], P[..., 2]
    print(f"loaded {time.time() - t0:.0f} s")
    sh = mask.shape
    col = np.zeros(sh + (3,), np.float32)
    metal = np.zeros(sh, np.float32)
    gloss = np.full(sh, 0.15, np.float32)
    emit = np.zeros(sh + (3,), np.float32)
    big = noise2(sh, 256, 3)
    mid = noise2(sh, 48, 5)

    # ---------------- дерево реек (осина, состаренная паром: серо-бежевая, PLAN_v3 §8 «Тон по референсу»)
    wood = np.isin(mat, [M["slat"], M["frame"], M["batten"], M["plaque"], M["rim"]])
    light, dark = hexc("#9A8875"), hexc("#6A5A4B")
    c = mix(np.broadcast_to(dark, sh + (3,)).copy(), light, np.clip(0.1 + 0.85 * tone + 0.2 * (big - 0.5), 0, 1))
    c = c * (0.9 + 0.1 * grain[..., None])                           # вытертая ранняя древесина между гребнями — темнее
    c = mix(c, hexc("#9C958B"), 0.12 * grain * mid)                   # лёгкая седина на гребнях
    steam = np.clip((Y - 80) / 30, 0, 1) * (np.abs(X) > 28)          # пар сверху темнит бока
    wet = np.clip((48 - Y) / 14, 0, 1)                                # вода снизу
    c = c * (1 - 0.14 * steam[..., None]) * (1 - 0.22 * wet[..., None])
    c = mix(c, hexc("#5A4434"), 0.55 * knot)
    col = np.where(wood[..., None], c, col)
    gloss = np.where(wood, 0.13 + 0.08 * wet, gloss)
    # рамка (горбыль) темнее, кора — серо-бурая с тёмными бороздами
    fr = mat == M["frame"]
    col[fr] *= 0.86
    bk = mat == M["bark"]
    cb = mix(np.broadcast_to(hexc("#6E655B"), sh + (3,)).copy(), hexc("#8D857A"), np.clip(mid + 0.2 * (big - 0.5), 0, 1))
    cb = mix(cb, hexc("#3A332D"), np.clip(cav * 1.3, 0, 1))
    col = np.where(bk[..., None], cb, col)
    gloss = np.where(bk, 0.08, gloss)
    # поперечины за рейками — тёмные, сырые
    col[mat == M["batten"]] = hexc("#5E4F42") * (0.9 + 0.2 * mid[mat == M["batten"]][..., None])
    # термометр: свежая липа светлее, риски выжжены, трубка — стекло, красная жидкость до середины
    pl = mat == M["plaque"]
    col[pl] = mix(np.broadcast_to(hexc("#B49C7C"), (pl.sum(), 3)).copy(), hexc("#C9B596"), grain[pl] * 0.5)
    col[pl] = mix(col[pl], hexc("#3E2E22"), np.clip(cav[pl] * 1.4, 0, 1))
    gl = mat == M["glass"]
    col[gl] = hexc("#B9C2BC")
    liquid = gl & (Y < 74.0) & (np.abs(Z - 0) > -1)
    col[liquid] = hexc("#8E2E22")
    gloss[gl] = 0.85

    # ---------------- уголь (обугленное дерево)
    ch = mat == M["char"]
    cc = mix(np.broadcast_to(hexc("#1F1C1A"), sh + (3,)).copy(), hexc("#2E2A27"), np.clip(1 - cav * 1.5, 0, 1) * mid)
    cc = mix(cc, hexc("#0D0C0B"), np.clip(cav * 1.6, 0, 1))
    # переход: подпалённое дерево вокруг угля
    scorch = np.clip(fblur(char, 12) * 1.4, 0, 1) * wood
    col = mix(col, hexc("#3B2E25"), 0.65 * scorch)
    col = np.where(ch[..., None], cc, col)
    gloss = np.where(ch, 0.36 + 0.12 * (1 - cav), gloss)          # серебристый отблеск угля

    # ---------------- гвозди: кованое железо, ржавые; ореол ржавчины на дереве
    nl = (mat == M["nail"]) | (nail > 0.5)
    halo = np.clip(fblur(nail.astype(np.float32), 10) * 2.2, 0, 1) * (wood | ch) * (1 - nail)
    col = mix(col, hexc("#5A3A26"), 0.55 * halo)
    cn = mix(np.broadcast_to(hexc("#3A3430"), sh + (3,)).copy(), hexc("#6E4127"), 0.45 + 0.4 * (mid - 0.5))
    col = np.where(nl[..., None], cn, col)
    metal = np.where(nl, 0.55, metal)
    gloss = np.where(nl, 0.32, gloss)

    # ---------------- эмаль в щелях (кремовая, ржавые крапины)
    en = mat == M["enamel"]
    ce = mix(np.broadcast_to(hexc("#B8AE98"), sh + (3,)).copy(), hexc("#7C4424"), np.clip(rust * 1.2, 0, 1))
    col = np.where(en[..., None], ce, col)
    gloss = np.where(en, 0.5 - 0.35 * rust, gloss)

    # ================= верх плиты (PLAN_v3 §3.2–3.3)
    dark_cav = 1 - np.clip(cav, 0, 1)
    # ---- базальт: графит, сколы светлее, поры темнее, белая корка накипи на верхних гранях
    stn = mat == M["stone"]
    cs = mix(np.broadcast_to(hexc("#1D1E20"), sh + (3,)).copy(), hexc("#323336"), np.clip(tone + 0.3 * (mid - 0.5), 0, 1))     # v3.0 в игре сверху — светло-серые
    cs = mix(cs, hexc("#6E6B68"), 0.55 * grain)                       # свежий скол — светлее, с рыжинкой ниже
    cs = cs * (1 - 0.5 * np.clip(cav, 0, 1)[..., None])
    cs = mix(cs, hexc("#A9A398"), np.clip(crust * 0.9, 0, 0.55) * (0.5 + 0.5 * mid))   # корка — пятнами, не белые камни (в игре v3.0-slice — «серебро»)
    col = np.where(stn[..., None], cs, col)
    gloss = np.where(stn, 0.08 + 0.04 * grain, gloss)
    # ---- чаша между камнями: угли и жар
    cup = mat == M["cup"]
    col = np.where(cup[..., None], hexc("#16120F") * (0.7 + 0.6 * mid[..., None]), col)
    gloss = np.where(cup, 0.1, gloss)
    # ---- эмаль плиты: кремовая, кракелюр темнее, к выгоревшим зонам — копоть
    pe = mat == M["plate_enamel"]
    ce2 = mix(np.broadcast_to(hexc("#857C6A"), sh + (3,)).copy(), hexc("#766C5A"), mid)            # в игре #CDC3AA и #A99F89 — белые (солнце сверху)
    ce2 = mix(ce2, hexc("#9A907E"), np.clip(cav * 0.9, 0, 1))
    soot_t = np.clip(char * 1.3 + 0.35 * (big - 0.3), 0, 1) * (0.6 + 0.4 * big)          # копоть и пятнами по всей плите
    ce2 = mix(ce2, hexc("#3B332C"), 0.75 * soot_t)
    ce2 = mix(ce2, hexc("#9A8F78"), 0.25 * dent)
    col = np.where(pe[..., None], ce2, col)
    gloss = np.where(pe, 0.42 - 0.3 * soot_t - 0.2 * cav, gloss)
    # ---- выгоревшее железо: чёрно-бурое, ржавчина в раковинах, кольца старой конфорки чуть светлее
    pi_ = mat == M["plate_iron"]
    ci = mix(np.broadcast_to(hexc("#211D1B"), sh + (3,)).copy(), hexc("#2F2925"), mid)
    ci = mix(ci, hexc("#5E331E"), np.clip(rust * 0.9, 0, 1))
    ci = mix(ci, hexc("#4A4038"), 0.35 * grain)
    col = np.where(pi_[..., None], ci, col)
    metal = np.where(pi_, 0.35 * (1 - rust), metal)
    gloss = np.where(pi_, 0.28 - 0.15 * rust, gloss)
    # ---- накипь: бело-жёлтая бугристая корка
    scl = mat == M["scale"]
    cn2 = mix(np.broadcast_to(hexc("#A59D8B"), sh + (3,)).copy(), hexc("#9C8C68"), np.clip(mid * 1.2 - 0.2, 0, 1))
    cn2 = cn2 * (1 - 0.35 * np.clip(cav, 0, 1)[..., None])
    col = np.where(scl[..., None], cn2, col)
    gloss = np.where(scl, 0.12, gloss)
    # ---- борт: дерево темнее реек (у горячей плиты)
    rim = mat == M["rim"]
    col[rim] *= 0.82
    # ---- проволока: ржавая
    wi = mat == M["wire"]
    cw = mix(np.broadcast_to(hexc("#3E2D22"), sh + (3,)).copy(), hexc("#7A4526"), np.clip(mid + 0.3 * (big - 0.5), 0, 1))
    col = np.where(wi[..., None], cw, col)
    metal = np.where(wi, 0.45, metal)
    gloss = np.where(wi, 0.3, gloss)
    # ---- листья: сухие оливково-бурые, жилки светлее, один обожжён по краю
    lf = mat == M["leaf"]
    cl = mix(np.broadcast_to(hexc("#433F2A"), sh + (3,)).copy(), hexc("#5B5436"), np.clip(tone, 0, 1))       # жёлтые пятна в игре -> бурее
    cl = mix(cl, hexc("#A39A6C"), 0.35 * grain)
    cl = mix(cl, hexc("#2A221B"), np.clip(char * 1.2, 0, 1))
    col = np.where(lf[..., None], cl, col)
    gloss = np.where(lf, 0.2, gloss)

    # ================= дверца (PLAN_v3 §3.5)
    ir = np.isin(mat, [M["iron"], M["rivet"], M["weld"]])
    bare = 1 - np.clip(crust, 0, 1)                                    # где отслоилась окалина — голый металл
    rust = np.where(ir, np.clip((rust - 0.35) / 0.65, 0, 1), rust)            # ржавчина — только в раковинах, без «камуфляжа»
    cir = mix(np.broadcast_to(hexc("#29282A"), sh + (3,)).copy(), hexc("#46423F"), 0.35 * bare)
    cir = mix(cir, hexc("#6A3A21"), np.clip(rust * 0.95, 0, 1))
    cir = cir * (1 - 0.4 * np.clip(cav, 0, 1)[..., None])
    cir = mix(cir, hexc("#5A5550"), 0.25 * grain * bare)               # гребешки ударов — светлее
    col = np.where(ir[..., None], cir, col)
    metal = np.where(ir, (0.45 + 0.35 * bare) * (1 - rust), metal)
    gloss = np.where(ir, 0.3 + 0.15 * crust - 0.15 * rust, gloss)
    wd = mat == M["weld"]
    col[wd] = mix(col[wd], hexc("#3B3230"), 0.5)
    rb = mat == M["rebar"]
    crb = mix(np.broadcast_to(hexc("#3E2A20"), sh + (3,)).copy(), hexc("#5E3825"), np.clip(mid + 0.4 * grain - 0.2, 0, 1))
    col = np.where(rb[..., None], crb, col)
    metal = np.where(rb, 0.0, metal)
    gloss = np.where(rb, 0.12, gloss)
    so = mat == M["soot_iron"]
    col = np.where(so[..., None], mix(np.broadcast_to(hexc("#1C1918"), sh + (3,)).copy(), hexc("#4E2C1C"), rust), col)
    gloss = np.where(so, 0.15, gloss)
    rp = mat == M["rope"]
    crp = mix(np.broadcast_to(hexc("#6E5E42"), sh + (3,)).copy(), hexc("#8A7854"), mid)
    sootr = np.clip(1 - np.abs(Y - 69.0) / 9.0, 0, 1) * (0.5 + 0.5 * big)     # засаленная и закопчённая середина
    crp = mix(crp, hexc("#2C251E"), 0.7 * sootr)
    col = np.where(rp[..., None], crp, col)
    gloss = np.where(rp, 0.12, gloss)

    # ================= остальные поверхности (PLAN_v3 §3.6–3.12)
    def put(m, c, g=None, mt=None):
        nonlocal col, gloss, metal
        col = np.where(m[..., None], c, col)
        if g is not None:
            gloss = np.where(m, g, gloss)
        if mt is not None:
            metal = np.where(m, mt, metal)
    # краска забора на досках сзади: выцветшая зелёная, кракелюр
    fe = mat == M.get("fence", 24)
    cf = mix(np.broadcast_to(hexc("#4F6A4C"), sh + (3,)).copy(), hexc("#6F8467"), np.clip(mid + 0.3 * (big - 0.5), 0, 1))
    cf = cf * (1 - 0.35 * np.clip(cav * 1.5, 0, 1)[..., None])
    put(fe, cf, 0.22)
    # зад: доски темнее от пара
    back = (Z < -28.5) & wood
    col[back] *= 0.82
    # поддон: мокрые тёмные доски
    pa = mat == M.get("pallet", 30)
    cp = mix(np.broadcast_to(hexc("#4A3C30"), sh + (3,)).copy(), hexc("#665241"), np.clip(tone * 0.8 + 0.3 * (mid - 0.5), 0, 1))
    cp = cp * (0.9 + 0.1 * grain[..., None]) * (1 - 0.5 * np.clip(cav, 0, 1)[..., None])
    put(pa, cp, 0.26)
    # кирпич: приглушённый красно-бурый, у каждого свой тон; сколы светлее, соли снизу, копоть сверху
    bri = mat == M.get("brick", 25)
    cbr = mix(np.broadcast_to(hexc("#5E3F33"), sh + (3,)).copy(), hexc("#7D5141"), np.clip(tone + 0.25 * (mid - 0.5), 0, 1))
    cbr = mix(cbr, hexc("#94644F"), 0.55 * knot)                     # свежий скол
    cbr = mix(cbr, hexc("#3A2A24"), np.clip(cav * 0.8, 0, 1))
    cbr = mix(cbr, hexc("#2A2320"), np.clip((Y - 15.0) / 8.0, 0, 1)[..., None] * 0.45)   # копоть к поясу
    salt = np.clip((9.0 - Y) / 6.0, 0, 1) * np.clip(mid * 1.6 - 0.4, 0, 1)
    cbr = mix(cbr, hexc("#B9B2A4"), 0.5 * salt)
    put(bri, cbr, 0.12)
    mo = mat == M.get("mortar", 26)
    cmo = mix(np.broadcast_to(hexc("#8A8378"), sh + (3,)).copy(), hexc("#6C665D"), np.clip(grain + 0.3 * (mid - 0.5), 0, 1))
    cmo = mix(cmo, hexc("#3B3631"), np.clip((Y - 16.0) / 7.0, 0, 1)[..., None] * 0.4)
    put(mo, cmo, 0.08)
    # пояс: выцветшая оливковая краска, под ней железо
    ol = mat == M.get("olive", 27)
    col_ol = mix(np.broadcast_to(hexc("#4D5440"), sh + (3,)).copy(), hexc("#626A4F"), np.clip(mid, 0, 1))
    put(ol, col_ol, 0.3, 0.0)
    band_bare = (mat == M["iron"]) & (Y > 21.5) & (Y < 31.8) & (np.abs(X) < 32.5) & (np.abs(Z) < 32.5) & mask
    put(band_bare, mix(np.broadcast_to(hexc("#4A3528"), sh + (3,)).copy(), hexc("#6A4028"), np.clip(rust + 0.3 * mid, 0, 1)), 0.2, 0.15)
    # жесть латки
    tn = mat == M.get("tin", 28)
    ctn = mix(np.broadcast_to(hexc("#67635D"), sh + (3,)).copy(), hexc("#6A3B22"), np.clip(rust, 0, 1))
    put(tn, ctn * (1 - 0.15 * dent[..., None]), 0.35, 0.55)
    metal = np.where(tn, 0.55 * (1 - rust), metal)
    # зола
    ah = mat == M.get("ash", 29)
    put(ah, mix(np.broadcast_to(hexc("#7E7A73"), sh + (3,)).copy(), hexc("#A19C93"), mid), 0.05, 0.0)
    # копоть внутри проёмов (дерево)
    sw = mat == M.get("soot_wood", 31)
    put(sw, hexc("#1E1915") * (0.8 + 0.4 * mid[..., None]), 0.12, 0.0)
    so2 = mat == M["soot_iron"]

    # ---- топка: камни светлее (ловят свет самой печи, HANDOFF), угли — чёрные с серым отливом, голые стенки — копоть
    fb = stn & (sidm == 29)
    col = np.where(fb[..., None], col * 0.85, col)            # v3.0: светлые камни под светом печи — сплошной оранжевый
    coal = (mat == M["char"]) & (sidm == 30)
    put(coal, mix(np.broadcast_to(hexc("#1A1816"), sh + (3,)).copy(), hexc("#3A3633"), np.clip(1 - cav, 0, 1) * mid), 0.35)
    bare = mask & (mat == 0)
    put(bare, hexc("#15110F") * (0.8 + 0.4 * mid[..., None]), 0.1, 0.0)

    # ================= свечение: только глубоко между камнями и в трещинах (жар снизу), карта 2048
    deep = np.clip((0.42 - ao) / 0.32, 0, 1)
    heat = np.where(cup, deep ** 1.2, 0) + np.where(stn, np.clip(char, 0, 1) * deep ** 0.8, 0)
    heat = heat + np.where(coal, np.clip(char, 0, 1) * (0.5 + 0.5 * deep), 0)          # трещины углей
    heat = heat * (0.75 + 0.5 * big)
    heat = heat + np.where(so2, np.clip(char, 0, 1) * 0.6, 0)          # тление на дне отсека справа
    hot_c = mix(np.broadcast_to(hexc("#B8300C"), sh + (3,)).copy(), hexc("#FF6A1F"), np.clip(heat * 1.4, 0, 1))
    emit = hot_c * np.clip(heat * 0.75, 0, 0.7)[..., None]       # уровень v2.9 (тот же множитель в редакторе)

    # ---------------- полости и AO в цвет (игровой Occlusion приглушает только рассеянный свет)
    col = col * (1 - 0.45 * np.clip(cav, 0, 1)[..., None] * wood[..., None])
    col = col * (1 - 0.12 * dent[..., None])
    col = col * ((0.42 + 0.58 * ao[..., None]) ** 0.9)
    occ = 0.3 + 0.7 * ao
    return dict(col=col, metal=metal, gloss=gloss, occ=occ, nrm=nrm, emit=emit, mask=mask)


def extend(maps, own, steps):
    """Продлить значения own-текселей на соседние пустые на steps пикселей."""
    filled = own.copy()
    for _ in range(steps):
        new = np.zeros_like(filled)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            src = np.roll(np.roll(filled, dy, 0), dx, 1)
            take = ~filled & ~new & src
            for k, a in maps.items():
                sh = np.roll(np.roll(a, dy, 0), dx, 1)
                a[take] = sh[take]
            new |= take
        filled |= new
    return filled


def down(a):
    if a.ndim == 2:
        return np.asarray(Image.fromarray(a.astype(np.float32), "F").resize((EXPORT, EXPORT), Image.LANCZOS), np.float32)
    return np.stack([down(a[..., c]) for c in range(a.shape[-1])], -1)


def up(a, size=EXPORT):
    if a.ndim == 2:
        return np.asarray(Image.fromarray(a.astype(np.float32), "F").resize((size, size), Image.LANCZOS), np.float32)
    return np.stack([up(a[..., c], size) for c in range(a.shape[-1])], -1)


def main():
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "v3.0"
    r = build()
    mine = r["mask"]
    used = load("used", "L") > 0.5
    maps = {k: r[k] for k in ("col", "metal", "gloss", "occ", "nrm", "emit")}
    area = extend(maps, mine.copy(), 24) & (~used | mine)
    print("downscale")
    col, metal, gloss, occ, nrm, emit = (down(maps[k]) for k in ("col", "metal", "gloss", "occ", "nrm", "emit"))
    w = np.clip(down(area.astype(np.float32)), 0, 1)
    w = np.where(down(mine.astype(np.float32)) > 0.02, 1.0, w)       # свои тексели — целиком свои
    old = lambda n, mode: np.asarray(Image.open(EXP / f"ElectricFurnace_{PREV}_{n}.png").convert(mode), np.float32) / 255
    od, oc, on, omg = old("diffuse", "RGBA"), old("diffuse_cutout", "RGBA"), old("normal", "RGB"), old("metalgloss", "RGBA")
    oo = up(old("occlusion", "L"))
    oe = up(old("emission", "RGB"))
    W = w[..., None]
    dif = od.copy()
    dif[..., :3] = col * W + od[..., :3] * (1 - W)
    cut = oc.copy()
    cut[..., :3] = dif[..., :3]
    # альфа выреза спиралей — как в v2.9 (радиусы 8.3 / 6.0 см проверены в игре v2.2–v2.9)
    n = nrm * 2 - 1
    lowp = np.stack([fblur(n[..., c], 3) for c in range(3)], -1)
    n = n + 0.5 * (n - lowp) * np.array([1, 1, 0], np.float32)        # мелкий рельеф ×1.5 (гайд §9.2)
    n = n * W + (on * 2 - 1) * (1 - W)
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-6
    mg = omg.copy()
    for c in range(3):
        mg[..., c] = metal * w + omg[..., c] * (1 - w)
    mg[..., 3] = gloss * w + omg[..., 3] * (1 - w)
    occ_o = occ * w + oo * (1 - w)
    emit_o = emit * W + oe * (1 - W)
    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    EXP.mkdir(exist_ok=True)
    base = f"ElectricFurnace_{tag}"
    Image.fromarray(q(dif), "RGBA").save(EXP / f"{base}_diffuse.png")
    Image.fromarray(q(cut), "RGBA").save(EXP / f"{base}_diffuse_cutout.png")
    Image.fromarray(q(n * 0.5 + 0.5), "RGB").save(EXP / f"{base}_normal.png")
    Image.fromarray(q(mg), "RGBA").save(EXP / f"{base}_metalgloss.png")
    Image.fromarray(q(occ_o), "L").save(EXP / f"{base}_occlusion.png")
    Image.fromarray(q(emit_o), "RGB").save(EXP / f"{base}_emission.png")
    print("->", EXP / f"{base}_*.png")


if __name__ == "__main__":
    main()
