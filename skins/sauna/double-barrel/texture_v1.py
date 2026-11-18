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
    # v1.2: размеры как у оригинальных слотов. Редактор ужимает картинку до размера слота по умолчанию
    # (кадр screenshots/ingame_v1.1_editor_grip_256.webp: файл 512 показан как 256), больший файл не даёт ничего.
    "stock": (512, 1024, 512, 512),
    "grip": (256, 256, 256, None),      # AO-слота у GRIP нет (None) — AO в цвет
    "sights": (512, 512, 512, None),
}
NATIVE = {}   # v1.1 — отдельные _native; с v1.2 основные карты сами в размере оригинала


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
# v1.1 (17.11.2026, по кадрам из игры): в v1 стволы читались хромом. В Unity Specular металл берёт цвет из
# блика, Diffuse у металла должен быть почти чёрным; у v1 был средне-серый #45423E + блик 0.40 — «полировка».
IRON = hexc("2A2826")
IRON_DARK = hexc("181716")
EDGE = hexc("4E4B46")
RUST = hexc("8C4A26")
RUST_DARK = hexc("5A2E18")
SOOT = hexc("191817")
MINERAL = hexc("C9C4B8")
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
    spec = 0.30 + 0.14 * e - 0.22 * rust
    gloss = 0.30 + 0.15 * e - 0.22 * rust + 0.06 * (n2 - 0.5)
    return col, spec, gloss, rust


def steam_and_soot(col, gloss, spec, P, part, seed, tubes=None, metal=None):
    """Копоть у дула и белые минеральные потёки (вертикальные: не зависят от высоты y)."""
    if part in ("barrel", "sights"):
        z = P[..., 2]
        soot = smooth((z - 0.32) / 0.10) * (0.7 + 0.3 * fbm(P * 140, 3, seed + 3))
        if metal is not None:   # v1.5: на дереве и коре копоть вдвое слабее (торец цевья был серым)
            soot = soot * (0.5 + 0.5 * metal)
        col = col * (1 - soot[..., None] * 0.8) + SOOT * soot[..., None] * 0.8
        gloss = gloss * (1 - 0.6 * soot)
        spec = spec * (1 - 0.5 * soot)
    # потёки: полосы по x/z, обрываются по y шумом; гуще на стволах и колодке
    q = np.stack([P[..., 0] * 260, P[..., 2] * 260, np.zeros_like(P[..., 0])], -1)
    streak = smooth((vnoise(q, seed + 11) - 0.62) * 5)
    fade = smooth((fbm(P * np.array([30, 120, 30]), 3, seed + 12) - 0.42) * 3)
    blot = smooth((fbm(P * 160, 4, seed + 13) - 0.62) * 4)  # засохшие капли пятнами
    m = np.clip(streak * fade * 0.45 + blot * 0.30, 0, 1) * 0.8
    if metal is not None:   # v1.5: минеральные потёки — только на железе (на торце цевья выходила белая плашка)
        m = m * metal
    if tubes is not None:   # на общих островах стволов потёки по x/y повернулись бы — только пятна
        m = m * (1 - tubes)   # v1.7: на трубах ни потёков, ни пятен — их облик даёт смоделированный рельеф
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
    nb_path = os.path.join(B, f"{part}_normal_base.png")
    if os.path.exists(nb_path):
        # v1.10: вычесть нормаль гранёной копии без рельефа — гранёность уходит, остаётся смоделированный рельеф
        nbase = load(nb_path, S)
        tub = (island_mask(part, {1, 2, 17, 18}, S) > 0.5) & (ids == IDS["metal"])
        nd = nrm_b.copy()
        nd[..., :2] = np.clip(nrm_b[..., :2] - nbase[..., :2] + 0.5, 0, 1)
        nrm_b = np.where(tub[..., None], nd, nrm_b)
    ao_o_path = os.path.join(O, f"{part}_ao.png")
    ao_o = load(ao_o_path, S)[..., 0] if os.path.exists(ao_o_path) else np.ones((S, S), np.float32)
    seed = {"barrel": 1, "main": 2, "stock": 3, "grip": 3}[part]

    metal = (ids == IDS["metal"]) | ~has
    if part == "barrel":
        # v1.2: трубы стволов — общий остров двух копий, вторая повёрнута на ~99°. Затенение из впадины между
        # стволами (оригинальный и запечённый AO) на второй копии ложилось на бок длинной чёрной полосой
        # (screenshots/ingame_v1.1_fp_inspect.webp). На трубах AO — только мягкий общий, без направленных полос.
        tb = island_mask("barrel", {1, 2, 17, 18}, S)
        ao_o = ao_o * (1 - tb) + np.maximum(ao_o, 0.92) * tb
        # v1.7: мелкое (ямки, вмятины, шов) оставляем — оно одинаково у обеих копий; крупное — мягкое
        ao_lo = blur(ao_b, 4)   # v1.10: затенение только от мелкого (ямки, царапины, шов); вмятины давали тёмные кляксы
        ao_hp = np.clip(ao_b / np.maximum(ao_lo, 1e-3), 0, 1)
        ao_b = ao_b * (1 - tb) + np.maximum(ao_lo, 0.9) * ao_hp * tb
    cav = np.clip((1 - ao_o) * 1.6 + (1 - ao_b) * 0.8, 0, 1)
    edge = np.clip(blur(curvature(nrm_o), 1) * 18, 0, 1)

    # --- железо
    tubes = island_mask("barrel", {1, 2, 17, 18}, S) if part == "barrel" else None
    col_i, spec_i, gloss_i, rust = iron_paint(S, P, cav, edge, seed, part, tubes)
    # --- детали: запечённый цвет + грязь
    col = col_b.copy()
    dirt = np.clip((1 - ao_b) * 1.4, 0, 1)
    col = col * (1 - 0.45 * dirt[..., None])
    col = grade_to(col, ids == IDS["wood"], WOOD_SET, k=1.0)   # v1.8: рисунок волокон не сжимать
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

    # v1.8: смоделированный рельеф деталей виден в цвете — тень во впадинах, светлее на гребнях (из запечённой
    # нормали, то есть из той же геометрии). В игре v1.7 береста, бечёвка, листья и кольца читались нарисованными
    # Только мелкий рельеф (высокие частоты нормали: кольца, бороздки, свив, жилки) — крупные перепады между
    # гладкой копией и гранями оригинала первый вариант v1.8 превращал в «складки ткани» на прикладе
    detail = ~metal
    nrm_hp = nrm_b - blur(nrm_b, 5) + 0.5
    cvb = blur(curvature(nrm_hp), 1) * 14
    cav_d = np.clip(-cvb, 0, 1)[..., None]
    rid_d = np.clip(cvb, 0, 1)[..., None]
    ao_hp = np.clip(ao_b / np.maximum(blur(ao_b, 8), 1e-3), 0, 1)[..., None]
    col = np.where(detail[..., None], col * (1 - 0.30 * cav_d) * (0.85 + 0.15 * ao_hp) + 0.08 * rid_d, col)
    col = np.where(metal[..., None], col_i, col)
    if part == "barrel":
        # v1.7: трубы стволов — цвет из геометрии (маски в цвете вершин high-poly: R ржавчина в ямках и вмятинах,
        # G светлый металл на царапинах и гребне шва). Положение второго ствола переводится в систему первого
        # (bake/barrel_copy.json), чтобы тон и копоть совпали. В v1-v1.6 здесь были нарисованные шумом пятна.
        import json
        bt = json.load(open(os.path.join(B, "barrel_copy.json")))
        Mi = np.linalg.inv(np.array(bt["M"]))
        Pc = np.where((P[..., 0] < bt["mx"])[..., None], (P - np.array(bt["T"])) @ Mi.T, P)
        tt = (island_mask("barrel", {1, 17, 18}, S) * (ids == IDS["metal"]))[..., None]   # не по коре и бечёвке манжет
        mk = np.clip(col_b, 0, 1) ** 2.2
        rm, bm = mk[..., 0:1], mk[..., 1:2]
        dm = mk[..., 2:3]
        # v1.10: дно вмятин в маске было ржавчиной (0.35·вмятина) — в рендере тёмные пятна-кляксы. Вмятина —
        # только рельеф; ржавчина остаётся в ямках
        rm = np.where(rm <= 0.36 * dm + 0.03, rm * 0.15, rm)
        tone = (0.9 + 0.2 * fbm(Pc * 25, 3, 81))[..., None]
        tcol = IRON * tone
        rv = fbm(Pc * 500, 2, 82)[..., None]
        rcol = hexc("4E2814") * (1 - rv * 0.6) + RUST * rv * 0.6   # v1.10: светлее — почти чёрные крупные раковины читались кляксами
        rw = np.clip(rm, 0, 1) ** 1.6 * 0.75   # темнее в глубине чаши, к кромке сходит на нет
        tcol = tcol * (1 - rw) + rcol * rw
        tcol = tcol * (1 - bm * 0.6) + (EDGE * 1.35) * bm * 0.6
        col = col * (1 - tt) + tcol * tt
        tube_sg = (tt[..., 0], 0.30 + 0.18 * bm[..., 0] - 0.2 * rm[..., 0], 0.30 + 0.15 * bm[..., 0] - 0.22 * rm[..., 0])
    else:
        tube_sg = None
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
    if tube_sg is not None:
        tw, tsp, tgl = tube_sg
        spec = spec * (1 - tw) + tsp * tw
        gloss = gloss * (1 - tw) + tgl * tw
    col, gloss, spec = steam_and_soot(col, gloss, spec, P, part, seed + 20, tubes, metal.astype(np.float32))

    # --- v1.3: в прицеле всё было одного тёмного железа (screenshots/ingame_v1.2_aim_*). Разные металлы
    # самоделки: задние муфты стволов — старая медь (фитинг), внутренние кольца — светлее и глаже,
    # гайки — воронёная сталь со светлыми рёбрами. Блик у меди цветной (Unity Specular: цвет металла — в блике).
    spec = np.repeat(spec[..., None], 3, -1)
    nw = fbm(P * 300, 3, seed + 40)
    if part == "barrel":
        cu = island_mask("barrel", {2, 3, 15, 30}, S)[..., None]
        ox = smooth((nw - 0.35) * 2.5)[..., None]
        # v1.4: в игре медь v1.3 блестела как новая труба — темнее, коричневее, блик и глянец ниже
        cu_col = hexc("3A2618") * (1 - ox * 0.6) + hexc("22170F") * ox * 0.6
        e3 = smooth(edge * 1.3)[..., None]
        cu_col = cu_col * (1 - e3 * 0.55) + hexc("7E5638") * e3 * 0.55
        pat = smooth((cav * 1.5 + (fbm(P * 700, 2, seed + 41) - 0.5) * 0.9 - 0.35) * 3)[..., None]  # ярь-медянка во впадинах
        cu_col = cu_col * (1 - pat * 0.7) + hexc("48604F") * pat * 0.7
        # v1.5: от третьего лица на солнце медь v1.4 всё ещё блестела как новая — блик и глянец ещё ниже
        cu_spec = np.array([0.21, 0.15, 0.11]) * (1 - pat) * (0.8 + 0.3 * (1 - ox)) + np.array([0.20, 0.14, 0.10]) * e3 + 0.05 * pat
        col = col * (1 - cu) + cu_col * cu
        spec = spec * (1 - cu) + np.clip(cu_spec, 0, 1) * cu
        gloss = gloss * (1 - cu[..., 0]) + (0.19 + 0.12 * e3[..., 0] - 0.10 * pat[..., 0] - 0.05 * ox[..., 0]) * cu[..., 0]
        st = island_mask("barrel", {13, 21, 22, 33}, S)[..., None]
        col = col * (1 - st) + (col * 0.75 + hexc("5A5853") * 0.25 * smooth(edge * 1.5)[..., None]) * st
        spec = spec * (1 - st) + 0.36 * st
        gloss = gloss * (1 - st[..., 0]) + (0.40 + 0.12 * smooth(edge)) * st[..., 0]
    if part == "main":
        nu = island_mask("main", {9, 10, 11, 12, 13}, S)[..., None]
        e3 = smooth(edge * 1.4)[..., None]
        nut_col = hexc("151618") * (0.9 + 0.2 * nw[..., None])
        nut_col = nut_col * (1 - e3 * 0.75) + hexc("6A6A6C") * e3 * 0.75
        rs = smooth((cav * 2.0 - 0.75) * 3)[..., None]
        nut_col = nut_col * (1 - rs * 0.7) + RUST_DARK * rs * 0.7
        col = col * (1 - nu) + nut_col * nu
        spec = spec * (1 - nu) + (np.array([0.30, 0.31, 0.34]) + 0.2 * e3 - 0.15 * rs) * nu
        gloss = gloss * (1 - nu[..., 0]) + (0.42 + 0.15 * e3[..., 0] - 0.2 * rs[..., 0]) * nu[..., 0]

    # --- нормали
    n = nrm_b.copy()
    if part == "barrel":
        tubes = island_mask("barrel", {1, 2, 17, 18}, S)[..., None]
        flat = np.zeros_like(nrm_o)
        flat[..., :] = (0.5, 0.5, 1.0)
        nrm_o_soft = flat * 0.65 + nrm_o * 0.35   # v1.7: точки и пятна оригинала на трубах ослаблены
        n_metal = whiteout(nrm_o_soft, nrm_b) * tubes + nrm_o * (1 - tubes)
    else:
        n_metal = nrm_o
    # v1.8: у деталей (не железо) рельеф в карте нормалей в 1.5 раза сильнее — тонкое в игре терялось
    nb = n.copy()
    xy = (nb[..., :2] - 0.5) + 0.5 * (nb[..., :2] - blur(nb, 4)[..., :2])   # усиливается только мелкое
    zz = np.sqrt(np.clip(0.25 - (xy ** 2).sum(-1), 0.02, 0.25))
    nb = np.concatenate([xy + 0.5, (zz + 0.5)[..., None]], -1)
    n = np.where(metal[..., None], n_metal, nb)
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
        spec[sh] = sg_o[..., :3][sh]
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
    sp = spec if spec.ndim == 3 else np.repeat(spec[..., None], 3, -1)
    sg = np.concatenate([sp, gloss[..., None]], -1)
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
