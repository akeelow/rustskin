"""Sauna Shotgun v1: из запечённых карт (bake_shotgun.py) — карты под слоты редактора, по вкладкам.

Запуск (.venv):  python texture_v1.py [--ver v1]
Вход:  bake/<part>_{normal,ao,color,id,poshi,poslo}.png, originals/<part>_{bc,nrm,sg,ao}.png,
       uv/<part>_ids.png (острова, islands.py)
Выход: export/DoubleBarrel_<ver>_<part>_{diffuse,normal,specgloss,occlusion}.png (+ _native — размер оригинала)

Что здесь (2D — только цвет и грязь поверх запечённого, как в правилах сета):
  железо     тёмное старое железо по оригинальным нормалям/AO: ржавчина в углублениях и снизу, светлые
             затёртые рёбра, копоть у дульного среза, белые минеральные потёки от пара (вертикальные,
             по положению точки в пространстве — не по развёртке)
  дерево     запечённый цвет + потемнение и засал в местах хвата (шейка, щека, цевьё), водяные пятна
  береста, полотенце, бечёвка, лист, смола, гвоздики — запечённый цвет, грязь в AO
Нормали: детали — запечённые; железо — оригинальная карта (Facepunch), на трубах стволов — оригинал +
раковины (whiteout). Spec/Gloss: Unity Specular — RGB блик, A глянец; металл светлый, остальное тёмное.
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(HERE, "bake")
O = os.path.join(HERE, "originals")
E = os.path.join(HERE, "export")
VER = sys.argv[sys.argv.index("--ver") + 1] if "--ver" in sys.argv else "v1"

IDS = {"metal": 1, "wood": 2, "bark": 3, "twine": 4, "towel": 5, "leaf": 6, "resin": 7, "nail": 8,
       "fore": 9, "burn": 10}
POS_LO = np.array([-0.35, -0.20, -0.50])
POS_HI = np.array([0.35, 0.10, 0.45])

# размеры: (diffuse, normal, specgloss, occlusion); None — слот не заменяем
OUT_SIZE = {
    "barrel": (1024, 1024, 1024, 512),
    "main": (1024, 1024, 512, 512),
    "stock": (1024, 1024, 1024, 512),   # оригинал Diffuse/SG 512 — мало для полотенца и орнамента
    "grip": (512, 512, 512, None),      # оригинал 256; AO-слота у GRIP нет (None) — AO в цвет
    "sights": (512, 512, 512, None),
}
NATIVE = {"stock": (512, 1024, 512, 512), "grip": (256, 256, 256, None)}


def hexc(h):
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255


def srgb2lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin2srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def load(path, size=None, mode="RGB", resample=Image.BILINEAR):
    im = Image.open(path).convert(mode)
    if size and im.size != (size, size):
        im = im.resize((size, size), resample)
    return np.asarray(im).astype(np.float32) / 255


def save(arr, path, size, mode="RGB"):
    a = (np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8)
    im = Image.fromarray(a, mode)
    if im.size != (size, size):
        im = im.resize((size, size), Image.LANCZOS)
    im.save(path)


def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


from noise_np import fbm, vnoise  # noqa: E402  (общий с bake_shotgun.py)


def curvature(nrm):
    """Выпуклость из карты нормалей: дивергенция (nx, ny); >0 — ребро, <0 — впадина."""
    nx = nrm[..., 0] * 2 - 1
    ny = nrm[..., 1] * 2 - 1
    d = np.gradient(nx, axis=1) - np.gradient(ny, axis=0)
    return d


def blur(a, r):
    """Простое размытие ящиком r px (дважды)."""
    if r < 1:
        return a
    for _ in range(2):
        k = 2 * r + 1
        c = np.cumsum(np.pad(a, ((r + 1, r), (0, 0)) + ((0, 0),) * (a.ndim - 2), mode="edge"), axis=0)
        a = (c[k:] - c[:-k]) / k
        c = np.cumsum(np.pad(a, ((0, 0), (r + 1, r)) + ((0, 0),) * (a.ndim - 2), mode="edge"), axis=1)
        a = (c[:, k:] - c[:, :-k]) / k
    return a


def whiteout(a, b):
    """Смешение двух карт нормалей (Unity/OpenGL, 0..1)."""
    x = a * 2 - 1
    y = b * 2 - 1
    n = np.stack([x[..., 0] + y[..., 0], x[..., 1] + y[..., 1], x[..., 2] * y[..., 2]], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-8
    return n * 0.5 + 0.5


def island_mask(part, ids_wanted, size):
    a = np.asarray(Image.open(os.path.join(HERE, "uv", f"{part}_ids.png")).convert("RGB")).astype(np.int32)
    isl = a[..., 0] + a[..., 1] * 256
    m = np.isin(isl, list(ids_wanted)).astype(np.float32)
    return np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize((size, size), Image.BILINEAR)) / 255


def islands_union(part, size):
    """Маска всех островов части (uv/<part>_ids.png), в рабочем размере."""
    a = np.asarray(Image.open(os.path.join(HERE, "uv", f"{part}_ids.png")).convert("RGB")).astype(np.int32)
    m = ((a[..., 0] + a[..., 1]) > 0).astype(np.uint8) * 255
    return np.asarray(Image.fromarray(m).resize((size, size), Image.NEAREST)) > 127


def dilate_fill(arr, mask, n):
    """Отступ: n раз растягиваем края островов наружу (среднее соседей), внутри острова не трогаем."""
    a = arr.copy()
    m = mask.copy()
    for _ in range(n):
        acc = np.zeros_like(a)
        cnt = np.zeros(m.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            sm = np.roll(np.roll(m, dy, 0), dx, 1)
            sa = np.roll(np.roll(a, dy, 0), dx, 1)
            acc += sa * sm[..., None] if a.ndim == 3 else sa * sm
            cnt += sm
        grow = (~m) & (cnt > 0)
        if a.ndim == 3:
            a[grow] = acc[grow] / cnt[grow][:, None]
        else:
            a[grow] = acc[grow] / cnt[grow]
        m = m | grow
    return a


def masked_blur(img, mask, r):
    """Размытие только внутри маски (гильзы: убрать надписи, сохранить цвет зон)."""
    w = blur(mask.astype(np.float32), r)
    b = blur(img * mask[..., None], r) / np.maximum(w[..., None], 1e-4)
    return np.where(mask[..., None], b, img)


def grade_to(col, mask, target, k=0.75):
    """Средний цвет участка — в target (sRGB 0..1), отклонения от среднего сжимаются в k раз."""
    if mask.sum() < 50:
        return col
    m = col[mask].mean(0)
    lm, lt = m.mean(), target.mean()
    l = col.mean(-1, keepdims=True)
    c = col - l
    new = l * (lt / lm) + (c - (m - lm)) * k + (target - lt)
    return np.where(mask[..., None], np.clip(new, 0, 1), col)


# Дерево сета (замер по export/Chair_v1.4_diffuse.png, 17.11.2026): sRGB (143, 128, 106), насыщенность 0.15.
# Первый вариант приклада был (160, 126, 93), 0.26 — желтее и ярче кресла в том же свете.
WOOD_SET = np.array([143, 128, 106], np.float32) / 255


# палитра железа и износа (sRGB)
IRON = hexc("45423E")
IRON_DARK = hexc("2B2A28")
EDGE = hexc("7A766E")
RUST = hexc("8C4A26")
RUST_DARK = hexc("5A2E18")
SOOT = hexc("191817")
MINERAL = hexc("D6D2C8")
WOOD_DARK = hexc("7A5A3C")
WOOD_OLD = hexc("45332A")


def iron_paint(size, pos, cav, edge, seed, part, tubes=None):
    """Цвет, блик, глянец старого железа по положению, впадинам и рёбрам."""
    P = pos
    n1 = fbm(P * 90, 4, seed)
    n2 = fbm(P * 400, 3, seed + 7)
    col = IRON[None, None] * (0.85 + 0.3 * n1[..., None])
    col = col * (1 - 0.35 * cav[..., None]) + IRON_DARK * 0.35 * cav[..., None]
    # ржавчина: во впадинах, у стыков, снизу; пятнами по шуму
    # «низ» по высоте точки — только где у острова одна копия: второй ствол — копия первого, повёрнутая
    # на ~99°, и его «низ» в общих UV лёг бы на бок. У колодки низа почти нет (она вся ниже стволов).
    low = smooth((-P[..., 1] - 0.0) / 0.04) * 0.6 if part == "barrel" else np.zeros(P.shape[:2], np.float32)
    if tubes is not None:
        low = low * (1 - tubes)
    # v1-рендер: рыжим было залито полствола — бриф: «рыжая ржавчина в углублениях». Теперь только
    # впадины, стыки и низ, пятна по шуму — лишь там, где уже есть впадина
    rust = smooth((cav * 1.8 + 0.25 * low + (n1 - 0.5) * 0.4 + (n2 - 0.5) * 0.3 - 0.70) * 2.6)
    if tubes is not None:   # впадина между стволами на повёрнутой копии ложится на бок — там слабее
        rust = rust * (1 - 0.65 * tubes)
    rust_col = RUST[None, None] * (1 - 0.4 * n2[..., None]) + RUST_DARK * 0.4 * n2[..., None]
    col = col * (1 - rust[..., None] * 0.85) + rust_col * rust[..., None] * 0.85
    # затёртые рёбра
    e = smooth(edge * 1.0) * (1 - rust * 0.7)
    col = col * (1 - e[..., None] * 0.6) + EDGE * e[..., None] * 0.6
    spec = 0.40 + 0.18 * e - 0.25 * rust
    gloss = 0.40 + 0.18 * e - 0.28 * rust + 0.06 * (n2 - 0.5)
    return col, spec, gloss, rust


def steam_and_soot(col, gloss, spec, P, part, seed, tubes=None):
    """Копоть у дула и белые минеральные потёки (вертикальные: не зависят от высоты y)."""
    if part in ("barrel", "sights"):
        z = P[..., 2]
        soot = smooth((z - 0.355) / 0.08) * (0.65 + 0.35 * fbm(P * 140, 3, seed + 3))
        col = col * (1 - soot[..., None] * 0.8) + SOOT * soot[..., None] * 0.8
        gloss = gloss * (1 - 0.6 * soot)
        spec = spec * (1 - 0.5 * soot)
    # потёки: полосы по x/z, обрываются по y шумом; гуще на стволах и колодке
    q = np.stack([P[..., 0] * 260, P[..., 2] * 260, np.zeros_like(P[..., 0])], -1)
    streak = smooth((vnoise(q, seed + 11) - 0.62) * 5)
    fade = smooth((fbm(P * np.array([30, 120, 30]), 3, seed + 12) - 0.42) * 3)
    blot = smooth((fbm(P * 160, 4, seed + 13) - 0.62) * 4)  # засохшие капли пятнами
    m = np.clip(streak * fade * 0.55 + blot * 0.45, 0, 1)
    if tubes is not None:   # на общих островах стволов потёки по x/y повернулись бы — только пятна
        m = m * (1 - tubes) + np.clip(blot * 0.45, 0, 1) * tubes
    col = col * (1 - m[..., None] * 0.55) + MINERAL * m[..., None] * 0.55
    gloss = gloss * (1 - 0.5 * m)
    return col, gloss, spec


def grip_zones(P, part):
    """Где держат руки (0..1): шейка приклада, щека (верх приклада слева), цевьё снизу и с боков."""
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    wrist = smooth(1 - np.abs(z + 0.205) / 0.06)
    cheek = smooth(1 - np.abs(z + 0.33) / 0.08) * smooth((y + 0.075) / 0.03) * smooth(-x / 0.01)
    fore = smooth(1 - np.abs(z - 0.31) / 0.11) * smooth((-y - 0.02) / 0.03)
    return np.clip(np.maximum(np.maximum(wrist, cheek * 0.8), fore), 0, 1)


def make(part):
    work = 2048 if part in ("barrel", "main", "stock") else 1024
    if part == "sights":
        return make_sights()
    S = work
    ids = (load(os.path.join(B, f"{part}_id.png"), S, resample=Image.NEAREST)[..., 0] * 255 - 8) / 16
    ids = np.round(ids).astype(np.int32)
    has = ids >= 1
    col_b = load(os.path.join(B, f"{part}_color.png"), S)
    nrm_b = load(os.path.join(B, f"{part}_normal.png"), S)
    ao_b = load(os.path.join(B, f"{part}_ao.png"), S)[..., 0]
    hi = load(os.path.join(B, f"{part}_poshi.png"), S, resample=Image.NEAREST)
    lo = load(os.path.join(B, f"{part}_poslo.png"), S, resample=Image.NEAREST)
    P = POS_LO + (np.round(hi * 255) * 256 + np.round(lo * 255)) / 65535 * (POS_HI - POS_LO)
    nrm_o = load(os.path.join(O, f"{part}_nrm.png"), S)
    ao_o_path = os.path.join(O, f"{part}_ao.png")
    ao_o = load(ao_o_path, S)[..., 0] if os.path.exists(ao_o_path) else np.ones((S, S), np.float32)
    seed = {"barrel": 1, "main": 2, "stock": 3, "grip": 3}[part]

    metal = (ids == IDS["metal"]) | ~has
    cav = np.clip((1 - ao_o) * 1.6 + (1 - ao_b) * 0.8, 0, 1)
    edge = np.clip(blur(curvature(nrm_o), 1) * 18, 0, 1)

    # --- железо
    tubes = island_mask("barrel", {1, 2, 17, 18}, S) if part == "barrel" else None
    col_i, spec_i, gloss_i, rust = iron_paint(S, P, cav, edge, seed, part, tubes)
    # --- детали: запечённый цвет + грязь
    col = col_b.copy()
    dirt = np.clip((1 - ao_b) * 1.4, 0, 1)
    col = col * (1 - 0.45 * dirt[..., None])
    col = grade_to(col, ids == IDS["wood"], WOOD_SET)
    col = grade_to(col, ids == IDS["fore"], WOOD_SET * 0.82)
    gz = grip_zones(P, part)
    n_w = fbm(P * 220, 3, seed + 5)
    wood = np.isin(ids, [IDS["wood"], IDS["fore"], IDS["burn"]])
    # дерево темнеет и засаливается в хвате; у цевья — от пара и рук
    wd = (gz * (0.55 + 0.35 * n_w))[..., None]
    col = np.where(wood[..., None], col * (1 - wd) + (WOOD_DARK * 0.85) * wd, col)
    # водяные пятна (кольца-разводы) на дереве
    ws = fbm(P * 45, 4, seed + 6)
    ring = smooth(1 - np.abs(ws - 0.55) / 0.012) * 0.12  # v1: разводы читались как горизонтали карты
    col = np.where(wood[..., None], col * (1 - ring[..., None]) + WOOD_DARK * ring[..., None], col)
    # береста и полотенце: серая грязь от рук там, где держат
    soft = np.isin(ids, [IDS["bark"], IDS["towel"], IDS["twine"]])
    sm = (gz * 0.35 * smooth((fbm(P * 300, 3, seed + 8) - 0.35) * 2))[..., None]
    col = np.where(soft[..., None], col * (1 - sm) + hexc("6E675C") * sm, col)
    # гвоздики — ржавые шляпки
    nail = (ids == IDS["nail"])[..., None]
    rn = smooth((fbm(P * 2500, 2, 9) - 0.4) * 3)[..., None]
    col = np.where(nail, col * (1 - 0.6 * rn) + RUST * 0.6 * rn, col)

    col = np.where(metal[..., None], col_i, col)
    spec = np.full((S, S), 0.17, np.float32)
    gloss = np.full((S, S), 0.2, np.float32)
    table = {"wood": (0.18, 0.20), "fore": (0.18, 0.26), "burn": (0.14, 0.10), "bark": (0.19, 0.15),
             "twine": (0.14, 0.07), "towel": (0.12, 0.04), "leaf": (0.21, 0.45), "resin": (0.25, 0.78),
             "nail": (0.30, 0.22)}
    for k, (s, g) in table.items():
        m = ids == IDS[k]
        spec[m], gloss[m] = s, g
    # засал: дерево в хвате блестит сильнее
    gloss = np.where(wood, gloss + 0.22 * gz, gloss)
    spec = np.where(metal, spec_i, spec)
    gloss = np.where(metal, gloss_i, gloss)
    col, gloss, spec = steam_and_soot(col, gloss, spec, P, part, seed + 20, tubes)

    # --- нормали
    n = nrm_b.copy()
    if part == "barrel":
        tubes = island_mask("barrel", {1, 2, 17, 18}, S)[..., None]
        n_metal = whiteout(nrm_o, nrm_b) * tubes + nrm_o * (1 - tubes)
    else:
        n_metal = nrm_o
    n = np.where(metal[..., None], n_metal, n)
    # --- AO
    ao = np.where(metal, ao_b * ao_o, ao_b * np.sqrt(ao_o))

    if part == "barrel":  # гильзы (вкладки у них нет, текстура — BARREL): оставляем оригинал
        sh = island_mask("shell", {1, 2, 3}, S) * (1 - island_mask("barrel", set(range(1, 100)), S))
        sh = (sh > 0.5)
        # на оригинальных гильзах есть надписи — правило сета «без текста»: размываем внутри гильз
        bc_o = masked_blur(load(os.path.join(O, "barrel_bc.png"), S), sh, 10)
        sg_o = load(os.path.join(O, "barrel_sg.png"), S, mode="RGBA")
        col[sh] = bc_o[sh]
        n[sh] = masked_blur(nrm_o, sh, 10)[sh]   # на нормалях гильз надписи выдавлены — тоже размываем
        spec[sh] = sg_o[..., :3].mean(-1)[sh]
        gloss[sh] = sg_o[..., 3][sh]
        ao[sh] = ao_o[sh]
    if part == "grip":  # нет слота AO — немного в цвет
        col = col * (0.55 + 0.45 * ao[..., None])

    # отступ: 8 px в итоговом размере (рабочий в 2–4 раза больше) за краем каждого острова
    pad = int(np.ceil(10 * S / OUT_SIZE[part][0]))
    um = islands_union(part, S)
    if part == "barrel":
        um = um | islands_union("shell", S)
    col = dilate_fill(col, um, pad)
    n = dilate_fill(n, um, pad)
    spec = dilate_fill(spec, um, pad)
    gloss = dilate_fill(gloss, um, pad)
    ao = dilate_fill(ao, um, pad)
    write(part, col, n, spec, gloss, ao, OUT_SIZE[part], "")
    if part in NATIVE:
        write(part, col, n, spec, gloss, ao, NATIVE[part], "_native")
    return col, ids


def write(part, col, n, spec, gloss, ao, sizes, suffix):
    os.makedirs(E, exist_ok=True)
    pre = os.path.join(E, f"DoubleBarrel_{VER}_{part}")
    sd, sn, ss, so = sizes
    rgba = np.concatenate([col, np.ones_like(col[..., :1])], -1)
    save(rgba, f"{pre}_diffuse{suffix}.png", sd, "RGBA")
    nn = np.concatenate([n[..., :2], np.ones_like(n[..., :1]), np.ones_like(n[..., :1])], -1)  # B = 255
    save(nn, f"{pre}_normal{suffix}.png", sn, "RGBA")
    sg = np.concatenate([np.repeat(spec[..., None], 3, -1), gloss[..., None]], -1)
    save(sg, f"{pre}_specgloss{suffix}.png", ss, "RGBA")
    if so:
        save(np.repeat(ao[..., None], 3, -1), f"{pre}_occlusion{suffix}.png", so, "RGB")


def make_sights():
    """SIGHTS: мелочь (мушка, целик, винты) без запекания — перекрас оригинала в железо сета."""
    S = 512
    bc = load(os.path.join(O, "sights_bc.png"), S)
    nrm = load(os.path.join(O, "sights_nrm.png"), S)
    sg = load(os.path.join(O, "sights_sg.png"), S, mode="RGBA")
    yy, xx = np.mgrid[0:S, 0:S] / S
    P = np.stack([xx * 0.1, yy * 0.1, np.zeros_like(xx)], -1)
    lum = bc.mean(-1)
    cav = np.clip(1 - lum / (lum.mean() + 1e-3), 0, 1) * 0.5
    edge = np.clip(blur(curvature(nrm), 1) * 18, 0, 1)
    col, spec, gloss, _ = iron_paint(S, P, cav, edge, 4, "sights")
    write("sights", col, nrm, spec, gloss, None, OUT_SIZE["sights"], "")


def main():
    parts = [a for a in sys.argv[1:] if a in OUT_SIZE] or list(OUT_SIZE)
    for p in parts:
        print("texture", p, flush=True)
        make(p)
    print("done")


if __name__ == "__main__":
    main()
