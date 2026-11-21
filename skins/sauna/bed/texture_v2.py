"""Sauna Bench v2.0: карты из запекания bake_v2.py (4096) -> экспорт 2048 (Lanczos).

Форма и всё, у чего она есть, — уже в геометрии (bake/v2/normal, m1-m3, idc). Здесь только:
  - палитра по маскам той же геометрии (волокно, полость, вмятина, гвоздь, сучок, обугливание, царапина, скоба, тон);
  - то, у чего формы нет: копоть у изножья, вода и минералы, ржавые потёки от гвоздей, кольцо от шайки, засаленность,
    влажный низ полотенца;
  - Spec/Gloss по материалам (Unity Specular), Occlusion из AO.
Куски, которых v2 ещё не касался (спинка, стойки, ламели, железо), берутся из v1.2 до их очереди.

    .venv/Scripts/python skins/sauna/bed/texture_v2.py [--tag v2.0]
Выход: export/Bed_<tag>_{diffuse,normal,specgloss,occlusion}.png (2048).
Тон настила — по референсу пользователя: светлота как у v1.2 в игре, насыщенность вдвое ниже (PLAN_v2.md, раздел 8).
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
sys.path.insert(0, str(HERE))
import blocking as B  # noqa: E402
import fields_box as FB  # noqa: E402
import fields_v2 as FV  # noqa: E402
from parts import pieces  # noqa: E402
from uv_zones import load_obj  # noqa: E402

BAKE = HERE / "bake" / "v2"
OUT = HERE / "export"
S = 4096
EXPORT = 2048
MINE = (B.PILLOW, B.MATTRESS, 3, 4, 5, 20, 11, 17, 19, 23, 27)   # все куски (копии общих развёрток — по ним же)
MAT = FV.MAT
sstep = FV.sstep


def hexc(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255


# палитра (sRGB)
WOOD = hexc("#6D6862")          # осина, состаренная паром (v2.2: по кадрам v2.0-v2.1 на ~25 % темнее и серее v2.0)
WOOD_GREY = hexc("#686664")
WOOD_WARM = hexc("#72695D")
NEW_WOOD = hexc("#787166")      # недавно заменённая рейка (v2.1-v2.2: в игре была светлой полосой)
GAP = hexc("#1C1612")
KNOT = hexc("#4A3828")
SOOT = hexc("#2A221D")
CHAR = hexc("#1B1714")
ASH = hexc("#5E5952")
IRON = hexc("#2B2825")
RUST = hexc("#8C4A26")
RUST_DARK = hexc("#5A3424")
MINERAL = hexc("#D6D2C6")
LINEN = hexc("#CFC6B4")
BRICK = hexc("#8E3A30")
THREAD = hexc("#B6AC99")
LEAF_OLIVE = hexc("#47502F")    # v2.1: веник в игре — яркий «салат»
LEAF_DRY = hexc("#5E5232")
LEAF_YELLOW = hexc("#7A6634")
TWIG = hexc("#5B3E2E")
TWINE = hexc("#A99A7C")
TIN = hexc("#6C6963")
DOOR_WOOD = hexc("#6E6860")     # голое дерево двери, выветренное
GREEN = hexc("#56684A")         # выцветшая зелёная краска (верхняя доска)
BLUE = hexc("#4F6573")          # выцветшая синяя (нижняя доска и грунт под зелёной)
BRASS = hexc("#5C4E2E")         # потемневшая латунь
PLUG = hexc("#8A7A62")
POST_WOOD = hexc("#766E62")
JOIST = hexc("#5A5149")
ENAMEL = hexc("#23251F")        # эмаль старой кровати: почти чёрная с оливой (решение пользователя 20.11)
STEEL = hexc("#3B3732")
STEEL_BRIGHT = hexc("#6E6A64")


def load(name, mode="RGB"):
    return np.asarray(Image.open(BAKE / f"{name}.png").convert(mode), np.float32) / 255.0


def blur(a, r):
    im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
    return np.asarray(im, np.float32) / 255.0


def fbm(x, y, seed, octaves=3):
    return FV.fbm2(x, y, seed, octaves).astype(np.float32)


def mix(col, c, t):
    return col * (1 - t[..., None]) + np.asarray(c, np.float32) * t[..., None]


def build():
    B.SIZE = S
    V, T, F = load_obj(B.ORIG / "bed.obj")
    P = pieces(V, F)
    piece_of = np.empty(len(F), int)
    for n, fs in enumerate(P):
        piece_of[fs] = n
    dup = [6, 21, 18, 22, 24, 25, 26, 28, 7, 8, 9, 10, 12, 13, 14, 15, 16]
    order = [B.BLANKET, *dup, 17, 19, 23, 27, 11, 20, 5, *B.HEADBOARD, B.MATTRESS, B.PILLOW]
    print("position map", S)
    pos, nrm, pid = B.position_map(V, T, F, piece_of, order)
    pos, nrm = pos.astype(np.float32), nrm.astype(np.float32)
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]

    print("bake maps")
    nb = load("normal")
    ao = load("ao", "L")
    m1, m2, m3, idc = load("m1"), load("m2"), load("m3"), load("idc")
    mask = load("mask", "L") > 0.5
    cover = load("cover", "L") > 0.5     # куда попали лучи (пропуски — цвет куска по умолчанию, ровная нормаль)
    mat = np.rint(idc[..., 0] * 32).astype(np.int32)      # v2.3: код / 32
    grain, cav, dent = m1[..., 0], m1[..., 1], m1[..., 2]
    nail, knot, char = m2[..., 0], m2[..., 1], m2[..., 2]
    scr, strap, tone = m3[..., 0], m3[..., 1], m3[..., 2]
    slat = np.rint(idc[..., 1] * 16).astype(np.int32)

    mine = mask & np.isin(pid, MINE)
    top = nrm[..., 2] > 0.6
    wood = np.isin(mat, [MAT["slat"], MAT["pallet"], MAT["new"], MAT["apron"], MAT["patch"], MAT["char"]]) & mine
    deck = wood & top & (pid == B.MATTRESS)
    apron = wood & ~top & (pid == B.MATTRESS)

    col = np.zeros((S, S, 3), np.float32) + GAP
    spec = np.full((S, S), 0.05, np.float32)
    gloss = np.full((S, S), 0.2, np.float32)

    # ---------------- дерево: тон доски (серее/теплее), волокна по маске гребней геометрии
    big = fbm(x * 0.02 + 3, y * 0.02 + z * 0.02, 903) - 0.5
    greyness = np.clip(0.25 + 0.6 * ((tone * 7.31) % 1.0) + 0.4 * big, 0, 1)
    base = mix(np.zeros_like(col) + WOOD_WARM, WOOD_GREY, greyness)
    base = base * (0.84 + 0.3 * tone[..., None])
    base = np.where((mat == MAT["new"])[..., None], NEW_WOOD * (0.95 + 0.1 * tone[..., None]), base)
    base = np.where((mat == MAT["pallet"])[..., None], base * np.array([0.86, 0.83, 0.8], np.float32), base)
    base = np.where((mat == MAT["patch"])[..., None], base * np.array([1.06, 1.0, 0.92], np.float32), base)
    gr = np.clip(grain, 0, 1)
    wc = base * (1.08 - 0.32 * gr[..., None])                      # гребни поздней древесины темнее (v2.1 сильнее)
    fine = fbm(x * 0.6 + z * 0.3, y * 0.08 + z * 0.6, 905, 2) - 0.5
    wc = wc * (1 + 0.06 * fine[..., None])
    # отполированная зона (лежат) — светлее и теплее, засаленная середина
    lie = sstep(0, 1, (1 - np.abs((x + 5) / 72) ** 2.5)) * sstep(0, 1, 1 - np.abs(y / 38) ** 3) * deck
    wc = wc * (1 + 0.05 * lie[..., None]) + 0.02 * lie[..., None] * np.array([1, 0.6, 0.2], np.float32)
    # вмятины и забоины — чуть темнее (смятое волокно, грязь), царапины — светлее (свежее дерево)
    wc = wc * (1 - 0.1 * dent[..., None]) * (1 + 0.16 * scr[..., None])
    # сучки
    wc = mix(wc, KNOT, 0.75 * knot)
    # трещины и щели — темно, по маске полостей геометрии
    wc = mix(wc, GAP, np.clip(cav * 1.1, 0, 1))

    # ---------------- копоть изножья и обугливание (тон без формы + клетки из геометрии)
    smoke = sstep(-62, -114, x) * (deck | apron)
    smoke = np.clip(smoke * (0.7 + 0.5 * fbm(y * 0.06, z * 0.1 + x * 0.03, 911)), 0, 1)
    wc = mix(wc, SOOT, 0.6 * smoke)
    ch = np.clip(char, 0, 1) * wood
    cell_top = np.clip(1 - cav, 0, 1)
    char_col = mix(np.zeros_like(col) + CHAR, ASH, 0.35 * cell_top * (0.5 + 0.5 * fbm(x * 0.8, y * 0.8 + z, 913)))
    wc = mix(wc, char_col, ch)

    # ---------------- кольцо от шайки и минералы (на настиле), вода и потёки (на фартуке)
    tx, ty, tr = FV.TUB
    ang = np.arctan2(y - ty, x - tx)
    rc = np.hypot(x - tx, y - ty) * (1 + 0.04 * np.sin(ang * 3 + 1.0))
    brk = sstep(0.3, 0.6, fbm(ang * 2.2 + 7, ang * 0 + 0.5, 915, 2))
    ring = np.exp(-((rc - tr) / 0.7) ** 2) * brk * deck
    wc = wc * (1 - 0.06 * (sstep(tr, tr - 2.5, rc) * deck)[..., None])
    wc = mix(wc, MINERAL, 0.15 * ring)                 # v2.3: в игре «нарисованный круг» (было 0.28)
    wet = sstep(47, 37.5, z) * apron
    wc = wc * (1 - 0.3 * wet[..., None])
    along = np.where(np.abs(nrm[..., 1]) > np.abs(nrm[..., 0]), x, y)
    streak = np.clip((fbm(along * 0.22, along * 0 + 1.0, 917, 3) - 0.56) * 2.4, 0, 1) * sstep(52, 41, z) * apron
    wc = mix(wc, MINERAL, 0.12 * streak)            # v2.1: в игре 0.26 — белые полосы
    # ржавые потёки от гвоздей фартука: вниз по доске
    ap = FV.Apron()
    rust_st = np.zeros((S, S), np.float32)
    side_of = np.where(nrm[..., 1] < -0.6, 0, np.where(nrm[..., 1] > 0.6, 1, np.where(nrm[..., 0] < -0.6, 2, 3)))
    for (sd, a, zn, kind) in ap.nails:
        m = apron & (side_of == sd) & (z < zn) & (z > zn - 9)
        if not m.any():
            continue
        aa = x[m] if sd < 2 else y[m]
        dzz = zn - z[m]
        w = 0.25 + 0.06 * dzz
        rust_st[m] = np.maximum(rust_st[m], np.exp(-((aa - a) / w) ** 2) * np.exp(-dzz / 5.0) * (0.6 + 0.4 * np.sin(dzz * 1.3 + a) ** 2))
    wc = mix(wc, RUST_DARK, 0.45 * rust_st)

    col = np.where(wood[..., None], wc, col)
    spec = np.where(wood, 0.055, spec)
    gloss = np.where(wood, 0.2 + 0.18 * lie + 0.1 * wet - 0.1 * smoke - 0.12 * ch, gloss)

    # ---------------- гвозди, скоба: тёмное железо, ржавчина; ореол влаги и ржавчины в дерево
    iron = mine & (np.isin(mat, [MAT["nail"], MAT["strap"]]) | ((mat == FB.MATB["door"]) & (nail > 0.5)))
    nrust = sstep(0.45, 0.8, fbm(x * 2 + y, z * 2, 921, 2))
    ic = mix(np.zeros_like(col) + IRON, RUST * 0.75, 0.55 * nrust)
    col = np.where(iron[..., None], ic, col)
    halo_src = (iron | (nail > 0.5)).astype(np.float32)
    woodish = wood | (mine & np.isin(mat, [FB.MATB["door"], FB.MATB["post"]]))
    halo_src = halo_src * (mat != FB.MATB["bolt"]) * ~np.isin(mat, [FB.MATB["enamel"], FB.MATB["steel"]])
    halo = np.clip(blur(halo_src, 6) * 3.0, 0, 1) * (1 - halo_src) * woodish
    halo2 = np.clip(blur(halo_src, 14) * 2.5, 0, 1) * (1 - halo_src) * woodish
    col = mix(col, hexc("#4E3424"), 0.42 * halo)
    col = col * (1 - 0.12 * halo2[..., None])
    spec = np.where(iron, 0.28 - 0.14 * nrust, spec)
    gloss = np.where(iron, 0.36 - 0.16 * nrust, gloss)

    # ---------------- жесть уголков
    tin = mine & (mat == MAT["tin"])
    tr_m = np.clip(0.35 * dent + 0.5 * sstep(0.55, 0.8, fbm(x * 0.3 + y * 0.3, z * 0.3, 925, 3)) + 0.4 * sstep(43, 39, z), 0, 1)
    tc = mix(np.zeros_like(col) + TIN * (0.85 + 0.25 * fbm(x * 1.5 + y, z * 1.5, 927, 2)[..., None]), RUST, 0.8 * tr_m)
    tc = mix(tc, SOOT, 0.5 * sstep(-90, -112, x) * tin)            # уголки у изножья подкопчены
    col = np.where(tin[..., None], tc, col)
    spec = np.where(tin, 0.32 - 0.22 * tr_m, spec)
    gloss = np.where(tin, 0.34 - 0.18 * tr_m, gloss)

    # ---------------- полотенце (подушка и хвост на настиле)
    tw = mine & ((mat == MAT["towel"]) | ((pid == B.PILLOW) & (mat == 0)))     # v2.1: угол торца был чёрным
    stripe = np.clip(strap, 0, 1)                       # m3.G у полотенца — полосы
    stitch = np.clip(scr, 0, 1)                         # m3.R — строчка
    fringe = np.clip(nail, 0, 1)                        # m2.R у хвоста — бахрома
    tc = np.zeros_like(col) + LINEN * (0.96 + 0.05 * fbm(x * 0.3, y * 0.3 + z * 0.3, 931, 3)[..., None])
    tc = mix(tc, BRICK * (0.9 + 0.15 * fbm(x * 0.5, y * 0.5 + z, 933, 2)[..., None]), 0.86 * stripe)
    tc = mix(tc, THREAD, 0.6 * stitch)
    tc = tc * (1 - 0.06 * fringe[..., None])
    tc = tc * (1 - 0.3 * cav[..., None])                 # щели между слоями и складка
    damp = sstep(57.0, 54.0, z) * tw * (pid == B.PILLOW)
    tc = tc * (1 - 0.14 * damp[..., None])
    tc = tc * (1 - 0.05 * dent[..., None])
    col = np.where(tw[..., None], tc, col)
    spec = np.where(tw, 0.04, spec)
    gloss = np.where(tw, 0.1 + 0.05 * damp, gloss)

    # ---------------- веник, листья, веточки, бечёвка
    lf = mine & (mat == MAT["leaf"])
    t = tone
    lc = mix(mix(np.zeros_like(col) + LEAF_OLIVE, LEAF_DRY, np.clip(t * 1.6, 0, 1)), LEAF_YELLOW, np.clip(t * 2 - 1, 0, 1) * 0.35)
    lc = lc * (1 + 0.18 * grain[..., None])               # жилки светлее
    lc = lc * (0.88 + 0.2 * fbm(x * 1.2, y * 1.2, 941, 2)[..., None])
    col = np.where(lf[..., None], lc, col)
    spec = np.where(lf, 0.06, spec)
    gloss = np.where(lf, 0.26, gloss)
    tg = mine & (mat == MAT["twig"])
    col = np.where(tg[..., None], TWIG * (0.85 + 0.35 * tone[..., None]) * (0.9 + 0.2 * fbm(x * 2, y * 2 + z, 943, 2)[..., None]), col)
    gloss = np.where(tg, 0.3, gloss)
    tn = mine & (mat == MAT["twine"])
    col = np.where(tn[..., None], TWINE * (0.78 + 0.3 * grain[..., None]), col)
    spec = np.where(tn, 0.04, spec)
    gloss = np.where(tn, 0.12, gloss)

    # ---------------- спинка: доски от двери, краска слоями (грунт синий, сверху зелёная), латунь, пробка
    MB = FB.MATB
    door = mine & (mat == MB["door"])
    pnt = m2[..., 2]
    upper = pid == 3
    tn = fbm(y * 0.04, z * 0.2 + x, 951, 3)
    dw = DOOR_WOOD * (0.88 + 0.22 * tn[..., None]) * (1.08 - 0.32 * np.clip(grain, 0, 1)[..., None])
    top_c = np.where(upper[..., None], GREEN, BLUE)
    pc = np.where((pnt > 0.75)[..., None], top_c, BLUE * 1.05)
    fade = 0.15 + 0.25 * fbm(y * 0.1, z * 0.3, 953, 3) + 0.15 * (x > 112.0)          # снаружи выцвело сильнее
    pc = mix(pc, hexc("#8C8A80"), np.clip(fade, 0, 1))
    pa = sstep(0.25, 0.4, pnt)
    dc = mix(dw, pc * (0.9 + 0.15 * tn[..., None]), pa)
    dc = mix(dc, hexc("#8E877C"), 0.35 * np.clip(m3[..., 0], 0, 1) * (1 - pa))           # светлое дерево у краёв сколов
    dc = mix(dc, GAP, np.clip(cav * 1.1, 0, 1))
    dc = dc * (1 - 0.12 * dent[..., None])
    col = np.where(door[..., None], dc, col)
    spec = np.where(door, 0.05 + 0.03 * pa, spec)
    gloss = np.where(door, 0.2 + 0.12 * pa, gloss)
    br = mine & (mat == MB["brass"])
    key = cav * (cav > 0.9)                                         # только скважина (паз под накладкой не темнит)
    col = np.where(br[..., None], mix(np.zeros_like(col) + BRASS * (0.85 + 0.3 * fbm(y * 2, z * 2, 955, 2)[..., None]), GAP, key), col)
    spec = np.where(br, 0.38, spec)
    gloss = np.where(br, 0.42, gloss)
    pl = mine & (mat == MB["plug"])
    col = np.where(pl[..., None], PLUG * (1.04 - 0.25 * np.clip(grain, 0, 1)[..., None]), col)

    # ---------------- стойки: тёсаная осина, к полу темнее, у изножья копоть сверху (только по высоте — общие развёртки)
    post = mine & (mat == MB["post"])
    pcol = POST_WOOD * (1.08 - 0.3 * np.clip(grain, 0, 1)[..., None]) * (0.92 + 0.16 * fbm(z * 0.05, x + y, 957, 3)[..., None])
    pcol = mix(pcol, KNOT, 0.75 * knot)
    pcol = mix(pcol, GAP, np.clip(cav * 1.1, 0, 1))
    pcol = pcol * (1 - 0.1 * dent[..., None])
    pcol = pcol * (1 - 0.42 * sstep(25, -3, z)[..., None])
    foot_post = post & (x < 0)
    pcol = mix(pcol, SOOT, 0.55 * sstep(15, 62, z) * foot_post)
    endg = post & (nrm[..., 2] > 0.6)
    pcol = np.where(endg[..., None], pcol * 0.82, pcol)
    col = np.where(post[..., None], pcol, col)
    spec = np.where(post, 0.05, spec)
    gloss = np.where(post, 0.22 + 0.1 * sstep(80, 88, z) * (x > 0), gloss)

    # ---------------- ламели: мокрое серо-бурое дерево, торцы светлее со щепой и минеральной коркой
    jo = mine & (mat == MB["joist"])
    jcol = JOIST * (1.08 - 0.3 * np.clip(grain, 0, 1)[..., None]) * (0.9 + 0.2 * fbm(y * 0.05, x * 0.1, 959, 3)[..., None])
    jcol = mix(jcol, GAP, np.clip(cav * 1.1, 0, 1))
    jend = jo & (np.abs(nrm[..., 1]) > 0.6)
    jcol = np.where(jend[..., None], jcol * 1.12, jcol)
    jcol = mix(jcol, MINERAL, 0.18 * sstep(0.55, 0.75, fbm(x * 0.3, z * 0.6 + y, 961, 3)) * jend)
    col = np.where(jo[..., None], jcol, col)
    gloss = np.where(jo, 0.3, gloss)

    # ---------------- железо: эмаль (почти чёрная олива), голая сталь, ржавчина в раковинах, пузыри, шов, болты, проволока
    metal = mine & np.isin(mat, [MB["enamel"], MB["steel"], MB["bolt"], MB["wire"]])
    en = np.clip(m2[..., 2], 0, 1)
    pitm, blist, chip, weld, bolt = (np.clip(a, 0, 1) for a in (grain, m2[..., 1], m3[..., 0], m3[..., 1], nail))
    rn = fbm(x * 0.25 + y * 0.25, z * 0.4 + x * 0.1, 963, 4)
    bare = mix(np.zeros_like(col) + STEEL, RUST * 0.8, np.clip(0.35 + 0.6 * (rn - 0.5) * 2, 0, 1) * 0.6)
    bare = mix(bare, RUST, 0.85 * pitm)
    bare = mix(bare, STEEL_BRIGHT, 0.55 * chip)
    enc = ENAMEL * (0.9 + 0.2 * fbm(x * 0.1 + y * 0.1, z * 0.3, 965, 3)[..., None])
    enc = mix(enc, RUST_DARK, 0.7 * blist)
    mcol = mix(bare, enc, en)
    mcol = mix(mcol, hexc("#2A2420"), 0.6 * weld)                    # шов: тёмная окалина
    mcol = mix(mcol, hexc("#4C4A52"), 0.25 * sstep(0.2, 0.5, weld) * sstep(0.95, 0.6, weld))   # цвета побежалости у шва
    mcol = mix(mcol, IRON * 1.1, 0.8 * bolt)
    mcol = mix(mcol, GAP, np.clip(cav * 1.2, 0, 1))
    wire = mine & (mat == MB["wire"])
    mcol = np.where(wire[..., None], mix(np.zeros_like(col) + STEEL * 0.9, RUST * 0.7, 0.4 + 0.3 * grain)[...], mcol)
    col = np.where(metal[..., None], mcol, col)
    rust_amt = (1 - en) * np.clip(0.35 + 0.6 * (rn - 0.5) * 2, 0, 1) * 0.6 + pitm
    spec = np.where(metal, 0.14 * en + (1 - en) * (0.3 - 0.22 * np.clip(rust_amt, 0, 1)), spec)
    gloss = np.where(metal, 0.48 * en + (1 - en) * (0.34 - 0.18 * np.clip(rust_amt, 0, 1)), gloss)

    # ---------------- пропуски запекания (лучи не попали: ухо пластины внутри стойки и т. п.) — цвет куска, ровная нормаль
    nohit = mine & ~cover & ~np.isin(pid, (B.MATTRESS, B.PILLOW))
    iron_piece = np.isin(pid, (17, 19, 23, 27))
    col = np.where((nohit & iron_piece)[..., None], ENAMEL, col)
    col = np.where((nohit & ~iron_piece)[..., None], DOOR_WOOD * 0.8, col)
    nb = np.where(nohit[..., None], np.array([0.5, 0.5, 1.0], np.float32), nb)

    # ---------------- AO в цвет (игровой Occlusion только приглушает рассеянный свет)
    col = col * ((0.45 + 0.55 * ao[..., None]) ** 0.9)
    occ = 0.35 + 0.65 * ao
    return dict(col=col, spec=spec, gloss=gloss, occ=occ, nrm=nb, mine=mine, pid=pid)


def extend(maps, own, steps):
    """Продлить значения own-текселей на соседние пустые (без чужих кусков) на steps пикселей."""
    filled = own.copy()
    for _ in range(steps):
        grow = {}
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


def fblur(a, r, passes=3):
    """Размытие float-карты: три прохода скользящего среднего (близко к гауссу), края — повтор."""
    a = a.astype(np.float32)
    for _ in range(passes):
        for ax in (0, 1):
            pad = [(0, 0), (0, 0)]
            pad[ax] = (r + 1, r)
            c = np.cumsum(np.pad(a, pad, mode="edge"), axis=ax, dtype=np.float64)
            hi = np.take(c, np.arange(2 * r + 1, c.shape[ax]), axis=ax)
            lo = np.take(c, np.arange(0, c.shape[ax] - 2 * r - 1), axis=ax)
            a = ((hi - lo) / (2 * r + 1)).astype(np.float32)
    return a


def down(a):
    """4096 -> 2048 Lanczos по каналам (float)."""
    if a.ndim == 2:
        return np.asarray(Image.fromarray(a.astype(np.float32), "F").resize((EXPORT, EXPORT), Image.LANCZOS), np.float32)
    return np.stack([down(a[..., c]) for c in range(a.shape[-1])], -1)


def main():
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "v2.0"
    r = build()
    mine, pid = r["mine"], r["pid"]
    # продлеваем свои куски на 24 px (4096) в пустые тексели, ближние к ним, — без тёмной каймы после уменьшения
    owner = pid.copy()
    for _ in range(40):
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            src = np.roll(np.roll(owner, dy, 0), dx, 1)
            take = (owner < 0) & (src >= 0)
            owner[take] = src[take]
    own = mine.copy()
    maps = {k: r[k] for k in ("col", "spec", "gloss", "occ", "nrm")}
    area = extend(maps, own, 24) & np.isin(owner, MINE)
    print("downscale")
    col, spec, gloss, occ, nrm = (down(maps[k]) for k in ("col", "spec", "gloss", "occ", "nrm"))
    area2 = down(area.astype(np.float32)) > 0.5
    mine2 = down(mine.astype(np.float32)) > 0.5
    use = area2 | mine2
    # остальное — из v1.2
    old = lambda n, mode: np.asarray(Image.open(OUT / f"Bed_v1.2_{n}.png").convert(mode), np.float32) / 255
    od, on, osg, oo = old("diffuse", "RGBA"), old("normal", "RGB"), old("specgloss", "RGBA"), old("occlusion", "L")
    dif = od.copy()
    dif[..., :3] = np.where(use[..., None], col, od[..., :3])
    dif[..., 3] = np.where(use, 1.0, od[..., 3])
    # одеяло и его поля (ближайший кусок — одеяло) прозрачны: иначе по краю выреза тянутся чёрные щепки
    blanket = owner[::2, ::2] == B.BLANKET
    dif[..., 3] = np.where(blanket & ~mine2, 0.0, dif[..., 3])
    n = nrm * 2 - 1
    # v2.1: в игре днём рельеф слабее, чем в Blender — мелкую деталь x1.5 (промт: «карту нормалей деталей усиливай»);
    # крупная поправка на сглаженную модель (размытая нормаль) остаётся как есть
    lowp = np.stack([fblur(n[..., c], 4) for c in range(3)], -1)
    n = n + 0.5 * (n - lowp) * np.array([1, 1, 0], np.float32)
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-6
    nrm_o = np.where(use[..., None], n * 0.5 + 0.5, on)
    sg = osg.copy()
    sg[..., 0] = sg[..., 1] = sg[..., 2] = np.where(use, spec, osg[..., 0])
    sg[..., 3] = np.where(use, gloss, osg[..., 3])
    occ_o = np.where(use, occ, oo)
    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    OUT.mkdir(exist_ok=True)
    Image.fromarray(q(dif), "RGBA").save(OUT / f"Bed_{tag}_diffuse.png")
    Image.fromarray(q(nrm_o), "RGB").save(OUT / f"Bed_{tag}_normal.png")
    Image.fromarray(q(sg), "RGBA").save(OUT / f"Bed_{tag}_specgloss.png")
    Image.fromarray(q(occ_o), "L").save(OUT / f"Bed_{tag}_occlusion.png")
    print("->", OUT / f"Bed_{tag}_*.png")


if __name__ == "__main__":
    main()
