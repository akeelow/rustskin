"""Sauna Boiler v4: текстуры по запечённым картам (bake/v4, 4096) -> export/Furnace_<tag>_*.png (1024).

Цвет и материал — по маскам той же геометрии (fields_v4.py): рельеф и цвет совпадают пиксель в пиксель. 2D здесь
только то, у чего нет формы: тон листов и досок, копоть, побежалость, вода и мокрые следы, дымка минеральных
разводов, ржавые ореолы, полоса на тряпке. Тексели, которые в срезе ещё не переделаны (нутро топки, угли, дно),
берутся из v3.

Слоты Furnace (все 1024, как у 12 принятых скинов в кэше Steam — PLAN_v4.md §0.2):
  Diffuse (RGBA, альфа 255), Normal, Specular/Gloss (RGB — блик, A — глянец), Occlusion (1024, у v3 было 512),
  Emission (серая; цвет даёт ползунок, как в v3).

  .venv/Scripts/python skins/sauna/furnace/texture_v4.py [--tag v4.0]
"""
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fields_v4 as FV  # noqa: E402
import geom_v4 as G  # noqa: E402

BAKE = HERE / "bake" / "v4"
EXP = HERE / "export"
PREV = "v3"
OUT = 1024
WORK = 2048
M = FV.MAT
POS_LO, POS_SPAN = np.array([-55.0, 0.0, -55.0]), np.array([110.0, 165.0, 110.0])
Image.MAX_IMAGE_PIXELS = None


def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255


# палитра: сет (skins/sauna/README.md) + железо по референсу (PLAN_v4 §8 «Тон»): серое, чуть холодное
IRON, IRON_DK, STEEL = hexc("4A4644"), hexc("2B2827"), hexc("8E8983")
RUST, RUST_DK, RUST_LT = hexc("8C4A26"), hexc("5A2E1B"), hexc("A85F33")
SCALE, SCALE_DK = hexc("A8A397"), hexc("7C7870")
SOOT = hexc("15110F")
ASPEN, STEAMED, CHARWOOD = hexc("C2A77E"), hexc("7A5A3C"), hexc("45332A")
GREYWOOD = hexc("9C8B74")
LINEN, STRIPE = hexc("CFC6B4"), hexc("8E3A30")
BIRCH_LT = hexc("B89468")


def load(name, mode="RGB"):
    return np.asarray(Image.open(BAKE / f"{name}.png").convert(mode), np.float32) / 255


def down(a, k):
    s = a.shape
    return a.reshape(s[0] // k, k, s[1] // k, k, *s[2:]).mean((1, 3))


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


def fbm3(P, scale, seed, octaves=3):
    s, a, t = 0.0, 0.5, 0.0
    for k in range(octaves):
        s = s + a * FV.vnoise(P * scale * 2 ** k, seed + 7 * k)
        t += a
        a *= 0.5
    return (s / t).astype(np.float32)


def sstep(a, b, x):
    return FV.sstep(a, b, x).astype(np.float32)


def dilate(img, valid, n=16):
    """Отступы: заливка пустых текселей соседними (n шагов по 1 px)."""
    img = img.astype(np.float32).copy()
    v = valid.copy()
    for _ in range(n):
        acc = np.zeros_like(img)
        cnt = np.zeros(v.shape, np.float32)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            sv = np.roll(v, (dy, dx), (0, 1))
            si = np.roll(img, (dy, dx), (0, 1))
            acc += si * sv[..., None] if img.ndim == 3 else si * sv
            cnt += sv
        new = ~v & (cnt > 0)
        if not new.any():
            break
        if img.ndim == 3:
            img[new] = acc[new] / cnt[new][:, None]
        else:
            img[new] = acc[new] / cnt[new]
        v = v | new
    return img


def lanczos(a, size):
    """Уменьшение массива (H, W[, C]) float 0..1 по каналам Lanczos через PIL (режим F)."""
    if a.ndim == 2:
        return np.asarray(Image.fromarray(a.astype(np.float32), "F").resize((size, size), Image.LANCZOS), np.float32)
    return np.stack([lanczos(a[..., c], size) for c in range(a.shape[-1])], -1)


def build(tag):
    t0 = time.time()
    k = 4096 // WORK
    mask4 = load("mask", "L")
    mask = down(mask4, k) > 0.5
    ao = down(load("ao", "L"), k)
    m1, m2, m3, idc, pos = (load(n) for n in ("m1", "m2", "m3", "idc", "pos"))
    idc_full = idc
    m1, m2, m3, pos = (down(a, k) for a in (m1, m2, m3, pos))
    # код материала и номер листа — без усреднения (ближайший тексель)
    mat = np.rint(idc_full[::k, ::k, 0] * 32).astype(np.int32)
    sid = np.rint(idc_full[::k, ::k, 1] * 64).astype(np.int32) - 1
    heat = down(idc_full[..., 2], k)
    haze = np.clip(fblur(m3[..., 1], 5) * 2.5, 0, 1)
    print(f"load {time.time() - t0:.0f} s", flush=True)

    sel = mask
    P = pos[sel] * POS_SPAN + POS_LO                     # см, OBJ
    x, y, z = P.T
    th = G.theta(P)
    rr = G.radius(P)
    MT = mat[sel]
    SID = sid[sel]
    wear, cav, dent = m1[sel].T
    rivet, knot, char = m2[sel].T
    rust, crust, tone = m3[sel].T
    HT = heat[sel]
    AO = ao[sel]
    n = len(x)
    is_ = lambda *names: np.isin(MT, [M[q] for q in names])  # noqa: E731

    blot = fbm3(P, 0.06, 1)                              # пятна 15–30 см
    fine = fbm3(P, 0.5, 2)                               # мелкие пятна 2–4 см (цвет, без формы)
    streak = fbm3(P * np.array([1.0, 0.08, 1.0]), 0.6, 3)   # вертикальные потёки
    col = np.zeros((n, 3), np.float32)
    spec = np.full(n, 45, np.float32)
    gloss = np.full(n, 30, np.float32)

    # ---------------- копоть, побежалость, вода (2D: формы нет)
    up = np.clip(y - 84.0, 0, None)
    fan = sstep(22 + up * 0.55, 8, np.abs(np.radians(FV.wrapdeg(th - G.OPEN_TH)) * rr)) * np.exp(-up / 26) * (y > 60)
    soot = np.clip(np.maximum(fan * (0.45 + 0.4 * streak), HT * 0.3) * (0.75 + 0.5 * blot), 0, 0.85)
    soot = np.maximum(soot, sstep(14, 7, rr) * (y > 150))                 # вокруг отверстия в крышке
    plug_dx = np.abs(np.radians(FV.wrapdeg(th - FV.PLUG[0])) * rr)
    wet = (y < FV.PLUG[1] - 2) * sstep(3.5 + (FV.PLUG[1] - y) * 0.05, 1.0, plug_dx) * sstep(50, 60, y)

    # ---------------- железо: листы, крышка, откосы
    iron = is_("sheet", "lid", "reveal", "behind")
    t_ = (tone - 0.5)
    c = IRON * (0.9 + 0.55 * t_[:, None]) * (0.78 + 0.38 * blot[:, None])
    barrel = is_("sheet") & (SID == 5)
    c = mix(c, hexc("4E4038"), barrel * 0.6)                              # лист бочки — коричневее
    c = mix(c, IRON_DK, sstep(0.6, 0.25, AO) * 0.6 + dent * 0.15)
    c = mix(c, STEEL, wear * 0.35)
    r_ = np.clip(rust * (0.45 + 0.5 * fine), 0, 1) * 0.8
    c = mix(c, hexc("4A3026"), r_ * 0.7)
    c = mix(c, RUST, sstep(0.5, 0.9, cav) * sstep(0.4, 0.8, r_) * 0.35)
    c = mix(c, hexc("1C1210"), cav * 0.8)
    col[iron] = c[iron]
    spec[iron] = (56 - 26 * r_ + 22 * wear)[iron]
    gloss[iron] = (100 - 70 * r_ - 20 * (1 - blot) + 25 * wear - 40 * cav)[iron]
    rev = is_("reveal")
    col[rev] = mix(col, SOOT * 1.4, 0.75)[rev]
    spec[rev], gloss[rev] = 30, 18

    # ---------------- обручи, заклёпки, болты, рамка, петли, крюк, порог
    hoop = is_("hoop", "bolt")
    c = IRON_DK * (0.95 + 0.5 * t_[:, None]) * (0.8 + 0.4 * blot[:, None])
    hr = np.clip(rust + 0.4 * sstep(0.62, 0.85, fine) * (1 - wear), 0, 1)
    c = mix(c, RUST_DK, hr * 0.75)
    c = mix(c, RUST, hr * sstep(0.5, 0.8, fine) * 0.55)
    c = mix(c, STEEL, wear * 0.55)
    col[hoop] = c[hoop]
    spec[hoop] = (60 - 28 * hr + 30 * wear)[hoop]
    gloss[hoop] = (100 - 65 * hr + 30 * wear)[hoop]

    riv = is_("rivet", "nail")
    c = mix(IRON * 0.9 * np.ones((n, 1), np.float32), STEEL, wear * (0.45 + 0.4 * tone))
    c = mix(c, RUST, sstep(0.55, 0.9, 1 - AO) * 0.7)
    c = mix(c, RUST_DK, sstep(0.7, 0.9, fine) * 0.4)
    col[riv] = c[riv]
    spec[riv], gloss[riv] = (70 + 20 * wear)[riv], (90 + 30 * wear)[riv]

    frame = is_("frame", "hinge", "hook", "sill")
    c = IRON_DK * (0.85 + 0.3 * blot[:, None])
    c = mix(c, RUST_DK, (rust + 0.25 * sstep(0.55, 0.8, fine)) * 0.6)
    c = mix(c, hexc("10100F"), cav * 0.7)
    tint = HT * sstep(0.3, 0.7, blot)                                     # побежалость, приглушённо
    c = mix(c, hexc("4A4060"), tint * 0.25)
    c = mix(c, hexc("6A5A3A"), HT * sstep(0.5, 0.8, fine) * 0.2)
    c = mix(c, STEEL, wear * 0.55)
    col[frame] = c[frame]
    spec[frame] = (55 + 30 * wear)[frame]
    gloss[frame] = (50 + 50 * wear - 25 * cav)[frame]

    chk = is_("checker")
    c = hexc("3E3935") * (0.85 + 0.3 * blot[:, None])
    c = mix(c, RUST_DK, sstep(0.45, 0.75, fine) * 0.55 * (1 - knot))
    c = mix(c, STEEL, wear * knot * 0.6)
    col[chk] = c[chk]
    spec[chk], gloss[chk] = (55 + 30 * wear * knot)[chk], (60 + 50 * wear * knot)[chk]

    # ---------------- накипь (корка смоделирована) и дымка разводов вокруг (2D)
    cr = np.clip(crust, 0, 1)
    sc = mix(np.broadcast_to(SCALE_DK, (n, 3)), SCALE, sstep(0.4, 1.0, cr * (0.75 + 0.4 * fine)))
    metal = iron | hoop | riv | frame | chk
    a_cr = np.where(metal, np.clip(0.1 + 0.45 * cr, 0, 0.55) * (cr > 0.02), 0)
    hz = np.where(metal, haze[sel], 0) * (1 - a_cr)                       # дымка минеральных разводов вокруг корки
    col = mix(col, SCALE_DK, np.clip(hz * 0.35, 0, 0.12))
    col = mix(col, sc, a_cr)
    spec = spec * (1 - a_cr) + 45 * a_cr
    gloss = gloss * (1 - a_cr) + 14 * a_cr

    # ---------------- дерево: доски, ковш, затычка; тряпка, бечёвка, проволока
    slat = is_("slat", "char")
    bt = tone
    # тон доски + продольные полосы вдоль волокна (цвет, без формы): шум растянут по окружности
    along = fbm3(np.stack([np.radians(th) * 47 * 0.04, y * 0.9, bt * 13], -1), 1.0, 9)
    c = mix(ASPEN * (0.4 + 0.3 * bt[:, None]), GREYWOOD * 0.6, 0.3 + 0.3 * sstep(0.35, 0.75, along))
    c = mix(c, STEAMED * 0.9, 0.25 * sstep(0.45, 0.8, blot))
    c = c * (0.86 + 0.24 * along[:, None]) * (0.96 + 0.06 * wear[:, None])
    c = mix(c, STEAMED, sstep(14, 2, y) * 0.75 + 0.25 * sstep(0.5, 0.9, streak) * (y < 30))   # мокрый низ
    c = mix(c, CHARWOOD, knot * 0.6)
    c = mix(c, hexc("2A1E15"), cav * 0.8)
    c = mix(c, RUST_DK, rust * 0.4)                                        # ореолы от гвоздей и проволоки
    c = mix(c, hexc("D8D2C2"), sstep(0.72, 0.9, streak) * sstep(53.5, 40, y) * (1 - cav) * 0.18)   # минеральные потёки
    # обугливание: чёрные блоки, трещины чернее, на гранях серая зола, по краю зоны — опалённое коричневое
    scorch = sstep(0.0, 0.35, char)
    c = mix(c, hexc("3A2A1E"), scorch * 0.7)
    blk = sstep(0.3, 0.6, char)
    c = mix(c, hexc("2E2620"), blk)
    c = mix(c, hexc("5E5952"), blk * sstep(0.45, 0.8, fine) * (1 - cav) * 0.5)
    c = mix(c, hexc("120E0B"), blk * cav * 0.8)
    col[slat] = c[slat]
    spec[slat] = (36 - 8 * blk)[slat]
    gloss[slat] = (22 + 30 * sstep(14, 2, y) - 10 * blk)[slat]

    lad = is_("ladle")
    c = mix(hexc("6E5238") * (0.85 + 0.25 * knot[:, None]), hexc("3A2A1C"), cav * 0.8 + 0.2 * sstep(0.5, 0.9, blot))
    c = mix(c, hexc("A07E58"), wear * 0.6)
    col[lad] = c[lad]
    spec[lad], gloss[lad] = 40, (45 + 20 * wear)[lad]
    plg = is_("plug")
    c = hexc("6A4E36") * (0.88 + 0.16 * knot[:, None])
    c = mix(c, hexc("2A1E14"), cav * 0.9)
    col[plg] = c[plg]
    spec[plg], gloss[plg] = 40, 55
    rag = is_("rag")
    c = LINEN * (0.72 + 0.25 * wear[:, None]) * (0.9 + 0.15 * fine[:, None])
    band = sstep(0.6, 0.3, np.abs(((y - FV.PLUG[1]) + 0.8 * np.sin(x * 0.7)) - (-6.0)) / 1.2)   # выцветшая полоса
    c = mix(c, STRIPE * 1.1, band * 0.55)
    c = mix(c, hexc("6E665A"), sstep(FV.PLUG[1] - 6, FV.PLUG[1] - 12, y) * 0.6 + cav * 0.3)    # мокрый низ хвоста
    col[rag] = c[rag]
    spec[rag], gloss[rag] = 28, (12 + 30 * sstep(FV.PLUG[1] - 6, FV.PLUG[1] - 12, y))[rag]
    tw = is_("twine")
    col[tw] = (hexc("9A8462") * (0.8 + 0.3 * fine[:, None]))[tw]
    spec[tw], gloss[tw] = 30, 12
    wire = is_("wire")
    c = mix(RUST_DK * 1.05 * np.ones((n, 1), np.float32), RUST, sstep(0.45, 0.8, fine) * 0.6)
    c = mix(c, STEEL * 0.8, wear * 0.3)
    col[wire] = c[wire]
    spec[wire], gloss[wire] = 70, 45

    # ---------------- камни на крышке: базальт, сбитые рёбра светлее, белая корка на верхах (плещут водой)
    stn = is_("stone")
    c = hexc("54565A") * (0.75 + 0.5 * tone[:, None]) * (0.9 + 0.2 * fine[:, None])
    c = mix(c, hexc("6E6C6A"), wear * 0.5)
    c = mix(c, hexc("B8B2A4"), sstep(0.62, 0.85, fine) * sstep(0.4, 0.8, tone) * 0.35)
    col[stn] = c[stn]
    spec[stn], gloss[stn] = 45, (40 + 30 * wear)[stn]

    # ---------------- нутро топки: шамот в саже, раствор, зола, береста, колотое дерево, угли
    em = np.zeros(n, np.float32)                                     # свечение 0..1 (цвет — шкала ниже)
    brk = is_("brick")
    lowy = sstep(80, 58, y)
    c = hexc("8A6648") * (0.75 + 0.5 * tone[:, None])
    c = mix(c, hexc("A07A52"), wear * 0.4)
    c = mix(c, SOOT * 1.5, np.clip(0.55 + 0.4 * sstep(60, 90, y) - 0.3 * lowy, 0, 0.9) * (0.8 + 0.3 * blot))
    c = mix(c, hexc("6A2A14"), HT * lowy * 0.6)                             # отсвет углей внизу стенок
    c = mix(c, hexc("120E0C"), cav * 0.7)
    col[brk] = c[brk]
    spec[brk], gloss[brk] = 30, 12
    mor = is_("mortar")
    col[mor] = (hexc("2A2420") * (0.8 + 0.4 * fine[:, None]))[mor]
    spec[mor], gloss[mor] = 25, 8
    ash_ = is_("ash")
    c = mix(hexc("4A4642") * np.ones((n, 1), np.float32), hexc("9A948A"), sstep(0.35, 0.75, fine) * 0.7) * (0.85 + 0.25 * tone[:, None])
    c = mix(c, hexc("3A1A0E"), HT * 0.7)
    col[ash_] = c[ash_]
    spec[ash_], gloss[ash_] = 25, 6
    em[ash_] = (HT * 0.6)[ash_]
    emb = is_("ember")
    c = mix(hexc("1A1412") * (0.8 + 0.5 * tone[:, None]), hexc("5A2410"), np.clip(HT, 0, 1) * 0.8)
    c = mix(c, hexc("6A6460"), sstep(0.6, 0.9, fine) * (1 - HT) * 0.4)       # серая зола на остывших
    col[emb] = c[emb]
    spec[emb], gloss[emb] = 35, 20
    em[emb] = HT[emb]
    brk_ = is_("bark")
    c = hexc("DDD6C6") * (0.8 + 0.2 * fine[:, None])
    c = mix(c, hexc("2A2420"), knot * 0.85)                                  # чечевички
    c = mix(c, hexc("8A7A62"), sstep(0.55, 0.85, blot) * 0.35)
    c = mix(c, hexc("120E0C"), char * 0.9)
    col[brk_] = c[brk_]
    spec[brk_], gloss[brk_] = 38, 30
    em[brk_] = (HT * char)[brk_]
    lw = is_("logwood")
    c = mix(hexc("C9A878") * np.ones((n, 1), np.float32), hexc("9A7A50"), knot * 0.6) * (0.85 + 0.25 * fine[:, None])
    c = mix(c, hexc("120E0C"), char * 0.9)
    col[lw] = c[lw]
    spec[lw], gloss[lw] = 35, 20
    em[lw] = (HT * char)[lw]

    # ---------------- копоть и вода поверх всего
    st = np.where(metal | slat, soot, 0) * (1 - 0.6 * a_cr)
    col = mix(col, SOOT, np.clip(st * 0.85, 0, 0.8))
    spec = spec * (1 - st) + 28 * st
    gloss = gloss * (1 - st) + 10 * st
    wt = np.where(metal | slat | rag, wet, 0)
    col = col * (1 - 0.35 * wt[:, None])
    gloss = gloss + 45 * wt
    col = col * (0.55 + 0.45 * AO[:, None]) ** 0.5            # лёгкое затемнение полостей в цвете (AO — отдельный слот)
    print(f"colour {time.time() - t0:.0f} s", flush=True)

    # ---------------- сборка 2048 -> 1024
    D = np.zeros((WORK, WORK, 3), np.float32)
    D[sel] = np.clip(col, 0, 1)
    S = np.zeros((WORK, WORK, 2), np.float32)
    S[sel] = np.stack([np.clip(spec, 0, 255), np.clip(gloss, 0, 255)], -1) / 255
    # свечение: чёрный -> тёмно-красный -> #FF6A1F -> #FFB347 (выше не поднимается, как v3)
    ramp = np.stack([np.zeros(3, np.float32), hexc("6A1604"), hexc("FF6A1F"), hexc("FFB347")])
    e3 = np.clip(em, 0, 1) * 3
    i0 = np.clip(np.floor(e3).astype(int), 0, 2)
    fr = (e3 - i0)[:, None]
    ecol = ramp[i0] * (1 - fr) + ramp[i0 + 1] * fr
    E = np.zeros((WORK, WORK, 3), np.float32)
    E[sel] = ecol
    D = dilate(D, mask, 8)
    S = dilate(S, mask, 8)
    E = dilate(E, mask, 8)
    D1, S1, E1 = lanczos(D, OUT), lanczos(S, OUT), lanczos(E, OUT)
    body1 = down(mask4, 4096 // OUT) > 0.5

    # нормаль: усиление мелкого рельефа по материалу, 4096 -> 1024
    nrm = load("normal") * 2 - 1
    matf = np.rint(idc_full[..., 0] * 32)
    kboost = np.where(np.isin(matf, [M["slat"], M["char"], M["ladle"], M["plug"], M["bark"], M["logwood"]]), 0.5, 0.3)
    det = nrm - np.stack([fblur(nrm[..., c], 3) for c in range(3)], -1)
    nb = nrm + kboost[..., None] * det * (mask4[..., None] > 0.5)
    nb /= np.linalg.norm(nb, axis=-1, keepdims=True) + 1e-6
    N1 = lanczos(nb * 0.5 + 0.5, OUT)
    N1 = N1 * 2 - 1
    N1 /= np.linalg.norm(N1, axis=-1, keepdims=True) + 1e-6
    N1 = N1 * 0.5 + 0.5
    A1 = lanczos(load("ao", "L"), OUT)
    print(f"normal {time.time() - t0:.0f} s", flush=True)

    # ---------------- остальное (кубики углей — острова 8–10, вне запекания) — из v3
    def prev(slot, mode="RGB"):
        im = Image.open(EXP / f"Furnace_{PREV}_{slot}.png").convert(mode)
        if im.size[0] != OUT:
            im = im.resize((OUT, OUT), Image.LANCZOS)
        return np.asarray(im, np.float32) / 255

    pd, pn, psg = prev("diffuse"), prev("normal"), prev("specgloss", "RGBA")
    pao, pem = prev("occlusion", "L"), prev("emission")
    used1 = down(load("used", "L"), 4096 // OUT) > 0.5
    keep_prev = ~body1
    Df = np.where(keep_prev[..., None], pd, D1)
    Nf = np.where(keep_prev[..., None], pn, N1)
    SGf = np.where(keep_prev[..., None], np.stack([psg[..., 0], psg[..., 3]], -1), S1)
    Af = np.where(keep_prev, pao, A1)
    Ef = np.where(keep_prev[..., None], pem, E1)
    # кубики углей (острова 8–10, своя геометрия модели, ~10 кубиков на пятно): тлеющий / чёрный уголь / серый
    import measure_v4 as MS
    V_, T_, N_, F_ = G.load()
    isl_ = G.island_of_face()
    UV_ = T_[F_[:, :, 1]]
    for ci, (dc, ec) in zip((8, 9, 10), ((hexc("2A0E06"), hexc("6A1604") * 1.4), (hexc("161210"), hexc("6A1604") * 0.35),
                                         (hexc("3A3634"), np.zeros(3, np.float32)))):
        msk = np.zeros((OUT, OUT), bool)
        for f in np.flatnonzero(isl_ == ci):
            for yx in MS.raster(None, UV_[f], 0, OUT):
                msk[yx] = True
        msk = fblur(msk.astype(np.float32), 1) > 0.05
        Df[msk] = dc
        Ef[msk] = ec
    Df = dilate(Df, used1 | ~keep_prev, 6)

    EXP.mkdir(exist_ok=True)
    name = EXP / f"Furnace_{tag}"
    u8 = lambda a: (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)  # noqa: E731
    Image.fromarray(np.dstack([u8(Df), np.full((OUT, OUT), 255, np.uint8)]), "RGBA").save(f"{name}_diffuse.png")
    Image.fromarray(u8(Nf), "RGB").save(f"{name}_normal.png")
    sgc = u8(SGf)
    Image.fromarray(np.dstack([sgc[..., 0], sgc[..., 0], sgc[..., 0], sgc[..., 1]]), "RGBA").save(f"{name}_specgloss.png")
    Image.fromarray(u8(Af), "L").convert("RGB").save(f"{name}_occlusion.png")
    Image.fromarray(u8(Ef), "RGB").save(f"{name}_emission.png")
    print("->", name, f"{time.time() - t0:.0f} s")


if __name__ == "__main__":
    a = sys.argv
    build(a[a.index("--tag") + 1] if "--tag" in a else "v4.0")
