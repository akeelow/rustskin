"""Sauna Robe v3: рельеф халата как поле высот в пространстве атласа (PLAN_v3.md, §4–5).

Всё, что имеет форму, считается здесь функциями numpy на растре атласа 2048 (1 тексель ≈ 0.7 мм при плотности
~14.6 px/см): вафля по долевой нити каждого куска, швы, складки, полоса воротника и запах (вариант B), пояс со
сборкой и шлёвками, узел, концы с бахромой, накладные карманы, рулон полотенца, веточка с листьями, подпалины.
Те же функции пишут маски цвета — цвет и рельеф совпадают пиксель в пиксель. bake_v3.py (Blender) смещает плотную
копию low-poly на H по нормали (H в мм, выборка по UV вершины) и пишет маски в атрибуты вершин.

Оси OBJ: x — поперёк (+x = левая сторона персонажа), y — вверх, z — вперёд. Острова — по islands_v3.py:
0 перёд, 1 рукав +x, 2 рукав −x, 3 спина, 4 воротник, 5/6 клапаны нижних карманов −x/+x, 7 подол изнутри,
8/9 клапаны нагрудных +x/−x, 10 обтачка горловины, 11/12 торцы манжет +x/−x.

    .venv/Scripts/python skins/sauna/snow-jacket/fields_v3.py [--only-preview]
Пишет bake/v3/fields.npz и bake/v3/preview_{relief,code,masks}.png (рельеф — теневая отмывка, 1024).
"""
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))
from uv_zones import load_obj  # noqa: E402
from islands_v3 import islands, load_vn  # noqa: E402

OBJ = HERE / "originals" / "jacket.snow.obj"
OUT = HERE / "bake" / "v3"
R = 2048
T0 = time.time()

# коды материалов (CODE): цвет и Spec/Gloss выбирает texture_v3.py
BODY, BAND, BELT, POCKET, HEM, KNOT, FRINGE, LINEN, TWIG, LEAF, INNER, LOOP, CUFF = range(1, 14)

CELL = 11.0          # ячейка вафли, мм (8 px при 1024)
DEPTH = 1.1          # глубина ячейки, мм
BAND_W = 0.070       # ширина полосы воротника, м
BELT_Y, BELT_H = 0.500, 0.025   # центр и полувысота пояса, м
Y_CROSS = 0.68       # перекрестье запаха (вариант B)
BELT_TOP = 6.5       # верх пояса над телом нижней полы, мм
PLACKET = 0.035      # полуширина планки парки, м: кромка верхней полы идёт по её −x краю


def log(*a):
    print("[%5.1fs]" % (time.time() - T0), *a, flush=True)


# ------------------------------------------------------------------ шум
def vnoise2(x, y, seed=0):
    xi, yi = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = x - xi, y - yi
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)

    def h(dx, dy):
        k = ((xi + dx) * 73856093) ^ ((yi + dy) * 19349663) ^ (seed * 83492791 + 12345)
        k = (k ^ (k >> 13)) * 1274126177
        return ((k ^ (k >> 16)) & 0xFFFF).astype(np.float32) / 65535

    return (h(0, 0) * (1 - fx) * (1 - fy) + h(1, 0) * fx * (1 - fy) + h(0, 1) * (1 - fx) * fy + h(1, 1) * fx * fy)


def fbm(x, y, seed=0, octaves=3):
    s, a, t = 0.0, 0.5, 0.0
    for k in range(octaves):
        s = s + a * vnoise2(x * 2 ** k, y * 2 ** k, seed + 7 * k)
        t += a
        a *= 0.5
    return s / t


def hash2(i, j, seed=0):
    k = (i.astype(np.int64) * 73856093) ^ (j.astype(np.int64) * 19349663) ^ (seed * 83492791 + 777)
    k = (k ^ (k >> 13)) * 1274126177
    return ((k ^ (k >> 16)) & 0xFFFF).astype(np.float32) / 65535


def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def gauss(x, w):
    return np.exp(-(x / w) ** 2)


def prof(d, r):
    """Скруглённая кромка: 0 на краю (d = 0), 1 при d ≥ r (четверть окружности)."""
    q = np.clip(d / r, 0, 1)
    return np.sqrt(1 - (1 - q) ** 2)


def tube(d, r):
    """Сечение трубки радиуса r на расстоянии d от оси: 0…1."""
    return np.sqrt(np.clip(1 - (d / r) ** 2, 0, 1))


# ------------------------------------------------------------------ развёртка → растр
def rasterize(V, T, F, VN, FN, fi):
    pos = np.full((R, R, 3), np.nan, np.float32)
    nrm = np.zeros((R, R, 3), np.float32)
    isl = np.full((R, R), -1, np.int16)
    Va, Ta, VNa = np.array(V), np.array(T), np.array(VN)
    for f, (vi, ti) in enumerate(F):
        P = np.array([[Ta[t][0] * R, (1 - Ta[t][1]) * R] for t in ti])
        x0, y0 = np.floor(P.min(0)).astype(int)
        x1, y1 = np.ceil(P.max(0)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, R - 1), min(y1, R - 1)
        ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        cx, cy = xs + 0.5, ys + 0.5
        (ax, ay), (bx, by), (qx, qy) = P
        den = (by - qy) * (ax - qx) + (qx - bx) * (ay - qy)
        if abs(den) < 1e-12:
            continue
        b0 = ((by - qy) * (cx - qx) + (qx - bx) * (cy - qy)) / den
        b1 = ((qy - ay) * (cx - qx) + (ax - qx) * (cy - qy)) / den
        b2 = 1 - b0 - b1
        ok = (b0 >= -1e-4) & (b1 >= -1e-4) & (b2 >= -1e-4)
        if not ok.any():
            continue
        B = np.stack([b0[ok], b1[ok], b2[ok]], 1)
        pos[ys[ok], xs[ok]] = B @ Va[list(vi)]
        nn = B @ VNa[list(FN[f])]
        nrm[ys[ok], xs[ok]] = nn / np.linalg.norm(nn, axis=1, keepdims=True)
        isl[ys[ok], xs[ok]] = fi[f]
    return pos, nrm, isl


def seam_segments(V, T, F, fi):
    """UV-отрезки границ островов по классам: seam (шов), side (боковой шов 0–3), hem, cuff, neck, open."""
    edges = {}
    for f, (vi, ti) in enumerate(F):
        for k in range(3):
            a, b = vi[k], vi[(k + 1) % 3]
            ta, tb = ti[k], ti[(k + 1) % 3]
            key = (min(a, b), max(a, b))
            uv = (ta, tb) if a < b else (tb, ta)
            edges.setdefault(key, []).append((f, uv))
    segs = {c: [] for c in ("seam", "side", "hem", "cuff", "neck", "open")}
    for key, lst in edges.items():
        if len(lst) == 1:
            f, (ta, tb) = lst[0]
            segs["open"].append((fi[f], T[ta], T[tb]))
            continue
        (f1, uv1), (f2, uv2) = lst[0], lst[1]
        if uv1 == uv2:
            continue
        pair = {fi[f1], fi[f2]}
        if pair & {7}:
            c = "hem"
        elif pair & {11, 12}:
            c = "cuff"
        elif pair & {4, 10}:
            c = "neck"
        elif pair == {0, 3}:
            c = "side"
        else:
            c = "seam"
        for f, (ta, tb) in lst:
            segs[c].append((fi[f], T[ta], T[tb]))
    return segs


def seg_distance(segs, isl, pxmm, reach_mm=120.0):
    """Расстояние (мм) от текселя до ближайшего отрезка своего острова; дальше reach_mm — reach_mm."""
    D = np.full((R, R), reach_mm, np.float32)
    for n, ta, tb in segs:
        a = np.array([ta[0] * R, (1 - ta[1]) * R])
        b = np.array([tb[0] * R, (1 - tb[1]) * R])
        rp = reach_mm * pxmm[n]
        x0, y0 = np.floor(np.minimum(a, b) - rp).astype(int)
        x1, y1 = np.ceil(np.maximum(a, b) + rp).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, R - 1), min(y1, R - 1)
        ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        m = isl[y0:y1 + 1, x0:x1 + 1] == n
        if not m.any():
            continue
        p = np.stack([xs[m] + 0.5, ys[m] + 0.5], 1)
        ab = b - a
        t = np.clip(((p - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
        d = np.linalg.norm(p - (a + t[:, None] * ab), axis=1) / pxmm[n]
        sub = D[y0:y1 + 1, x0:x1 + 1]
        sub[m] = np.minimum(sub[m], d)
    return D


# ------------------------------------------------------------------ полилинии в плоскости (x, y), м
def polyline(P, path):
    """Для точек P (..., 2): расстояние до ломаной, сторона (+ слева от хода), длина вдоль, № отрезка."""
    path = np.asarray(path, float)
    best = np.full(P.shape[:-1], np.inf)
    side = np.zeros(P.shape[:-1])
    along = np.zeros(P.shape[:-1])
    acc = 0.0
    for k in range(len(path) - 1):
        a, b = path[k], path[k + 1]
        ab = b - a
        L = np.linalg.norm(ab)
        t = np.clip(((P - a) @ ab) / (L * L), 0, 1)
        q = a + t[..., None] * ab
        d = np.linalg.norm(P - q, axis=-1)
        s = np.sign(ab[0] * (P[..., 1] - a[1]) - ab[1] * (P[..., 0] - a[0]))
        m = d < best
        best = np.where(m, d, best)
        side = np.where(m, s, side)
        along = np.where(m, acc + t * L, along)
        acc += L
    return best, side, along


# ------------------------------------------------------------------ вафля
def waffle(S, T, seed, depth=DEPTH, cell=CELL):
    """Вафельное плетение в координатах ткани (мм). -> (h мм, полость 0…1)."""
    ws = S + 0.7 * (fbm(S / 45, T / 45, seed) - 0.5) * 2
    wt = T + 0.7 * (fbm(S / 45 + 9.1, T / 45 + 3.3, seed + 1) - 0.5) * 2
    cs = cell * (1 + 0.05 * (fbm(S / 300, T / 300, seed + 2) - 0.5))
    fx, fy = ws / cs, wt / cs
    ix, iy = np.floor(fx), np.floor(fy)
    ex = np.abs(fx - ix - 0.5) * 2
    ey = np.abs(fy - iy - 0.5) * 2
    ridge, wall = 1.5 / cell * 2, 1.7 / cell * 2   # полуширина гребня и ширина стенки в долях полуячейки
    inside = (1 - sstep(1 - ridge - wall, 1 - ridge, ex)) * (1 - sstep(1 - ridge - wall, 1 - ridge, ey))
    dvar = 1 + 0.18 * (hash2(ix, iy, seed) - 0.5) * 2
    pillow = 0.22 * (1 - np.maximum(ex, ey) ** 2)
    h = -depth * dvar * inside + pillow * inside
    return h.astype(np.float32), inside.astype(np.float32)


# ------------------------------------------------------------------ складки парки → складки халата
def stock_folds(cov1024):
    """Интегрирует родную нормаль парки (Франкот–Челлаппа), оставляет крупные складки (> 1.5 см), мм."""
    from PIL import Image
    n = np.asarray(Image.open(HERE / "originals" / "jacket_snow_nrm.png").convert("RGB"), np.float32) / 127.5 - 1
    nz = np.clip(n[..., 2], 0.35, 1)
    gx = -n[..., 0] / nz             # dh/dcol
    gy = n[..., 1] / nz              # dh/drow (строки вниз, зелёный вверх)
    gx[~cov1024] = 0
    gy[~cov1024] = 0
    N = gx.shape[0]
    wx = np.fft.fftfreq(N) * 2 * np.pi
    WX, WY = np.meshgrid(wx, wx)
    den = WX ** 2 + WY ** 2
    den[0, 0] = 1
    H = (-1j * WX * np.fft.fft2(gx) - 1j * WY * np.fft.fft2(gy)) / den
    H[0, 0] = 0
    s_lo, s_hi = 11.0, 90.0          # px при 1024: ~1.5 см и ~12 см
    filt = np.exp(-0.5 * den * s_lo ** 2) * (1 - np.exp(-0.5 * den * s_hi ** 2))
    h = np.real(np.fft.ifft2(H * filt)) * 1.37      # px -> мм (1 px 1024 ≈ 1.37 мм)
    h = np.clip(h * 0.7, -6, 6).astype(np.float32)
    return np.kron(h, np.ones((2, 2), np.float32))  # 1024 -> 2048 (сглажено фильтром)


# ------------------------------------------------------------------ сборка
def model():
    """OBJ, острова, растр атласа (pos, nrm, isl) и плотность px (2048) на мм по островам."""
    V, T, F = load_obj(OBJ)
    VN, FN = load_vn(OBJ)
    I = islands(F)
    fi = np.zeros(len(F), np.int32)
    for n, fs in enumerate(I):
        fi[fs] = n
    pos, nrm, isl = rasterize(V, T, F, VN, FN, fi)
    Va, Ta = np.array(V), np.array(T)
    pxmm = {}
    for n, fs in enumerate(I):
        a3 = au = 0.0
        for f in fs:
            a, b, c = (Va[i] for i in F[f][0])
            a3 += 0.5 * np.linalg.norm(np.cross(b - a, c - a))
            ua, ub, uc = (Ta[t] for t in F[f][1])
            au += 0.5 * abs((ub[0] - ua[0]) * (uc[1] - ua[1]) - (uc[0] - ua[0]) * (ub[1] - ua[1]))
        pxmm[n] = (au * R * R / (a3 * 1e6)) ** 0.5
    return V, T, F, I, fi, pos, nrm, isl, pxmm


def build():
    V, T, F, I, fi, pos, nrm, isl, pxmm = model()
    cov = isl >= 0
    log("растр:", cov.sum(), "текселей")
    log("px/мм:", {k: round(v, 2) for k, v in pxmm.items()})

    segs = seam_segments(V, T, F, fi)
    D = {c: seg_distance(s, isl, pxmm, 120.0 if c in ("hem", "cuff") else 30.0) for c, s in segs.items()}
    log("расстояния до швов готовы:", {c: len(s) for c, s in segs.items()})

    ys, xs = np.mgrid[0:R, 0:R]
    PX = np.zeros((R, R), np.float32)
    for n in range(len(I)):
        PX[isl == n] = pxmm[n]
    PX[~cov] = 1.46
    S0 = (xs + 0.5) / PX
    T0_ = (R - ys - 0.5) / PX        # вверх по атласу
    X, Y, Z = pos[..., 0], pos[..., 1], pos[..., 2]
    X, Y, Z = np.nan_to_num(X), np.nan_to_num(Y), np.nan_to_num(Z)
    P2 = np.stack([X, Y], -1)

    H = np.zeros((R, R), np.float32)
    CODE = np.zeros((R, R), np.uint8)
    CAV = np.zeros((R, R), np.float32)
    STRIPE = np.zeros((R, R), np.float32)
    GROOVE = np.zeros((R, R), np.float32)
    SCORCH = np.zeros((R, R), np.float32)
    THREAD = np.zeros((R, R), np.float32)

    # --- крупные складки: родные (сглаженные) + сборка у пояса + складки запаха
    cov1024 = cov.reshape(1024, 2, 1024, 2).any((1, 3))
    FOLD = stock_folds(cov1024)
    torso = (isl == 0) | (isl == 3)
    arc = np.arctan2(X, Z + 0.02) * 0.168 * 1000                 # мм по окружности талии
    dy = np.abs(Y - BELT_Y) - BELT_H
    gather_w = np.exp(-np.clip(dy, 0, None) / 0.035) * torso
    g = (0.55 * np.sin(2 * np.pi * arc / 23 + 6 * fbm(arc / 60, Y * 20, 3))
         + 0.35 * np.sin(2 * np.pi * arc / 37 + 4 * fbm(arc / 90, Y * 15, 4))
         + 0.25 * np.sin(2 * np.pi * arc / 61 + 2.0))
    gather = (np.clip(g, -1, 1) * 0.5 + 0.5) ** 1.4 * 3.2 * gather_w * (0.6 + 0.8 * fbm(arc / 40, Y * 30, 5))
    FOLD = FOLD * (1 - 0.6 * gather_w) + gather
    # складки запаха: от перекрестья к узлу (+x), поперёк направления
    dvec = np.array([0.15, -0.155]) / np.hypot(0.15, 0.155)
    across = (X + 0.035) * -dvec[1] + (Y - Y_CROSS) * dvec[0]
    alongw = (X + 0.035) * dvec[0] + (Y - Y_CROSS) * dvec[1]
    wrapw = (isl == 0) * sstep(0.0, 0.03, alongw) * (1 - sstep(0.13, 0.2, alongw)) * gauss(across, 0.06)
    FOLD += 2.2 * wrapw * np.sin(2 * np.pi * across / 0.027 + 1.3) * (0.7 + 0.6 * fbm(alongw * 30, across * 30, 6))
    log("складки готовы")

    # --- ткань всех кусков: своя вафля у каждого острова (фаза своя, на шве сбой)
    hw, cav = waffle(S0 + 31.7 * isl, T0_ + 17.3 * isl, seed=11)
    H[:] = FOLD + hw
    CAV[:] = cav
    CODE[cov] = BODY
    CODE[(isl == 4) | (isl == 10)] = BAND
    CODE[np.isin(isl, (5, 6, 8, 9))] = HEM

    # --- швы: канавка + валики припуска, вафля у шва глохнет
    dseam = np.minimum(np.minimum(D["seam"], D["side"]), D["neck"])
    groove = gauss(dseam, 1.1)
    ridge = gauss(dseam - 4.5, 2.4)
    H += -0.8 * groove + 0.6 * ridge
    H -= hw * (1 - sstep(1.5, 4.0, dseam))
    GROOVE = np.maximum(GROOVE, groove)
    # подол: строчка подгиба в 25 мм от сгиба, ступенька края подгиба изнутри на 40 мм
    dh = D["hem"]
    hemz = np.isin(isl, (0, 3)) & (dh < 60)
    H += hemz * (-0.45 * gauss(dh - 25, 1.0) + 0.9 * (1 - sstep(38, 42, dh)))
    GROOVE = np.maximum(GROOVE, hemz * gauss(dh - 25, 1.0))
    # кайма полотенца на спине: полосы 9 + 4 + 9 мм (тканые — только цвет)
    back = isl == 3
    for a, b in ((32, 41), (45, 49), (53, 62)):
        STRIPE = np.maximum(STRIPE, back * sstep(a - 0.6, a + 0.6, dh) * (1 - sstep(b - 0.6, b + 0.6, dh)))
    # отвороты манжет: отвёрнутый слой 90 мм, верхний край со строчкой, полоса 4 мм
    dc = D["cuff"]
    sleeve = np.isin(isl, (1, 2))
    cuffm = sleeve & (dc < 90)
    H += sleeve * (2.5 * prof(90 - dc, 3.5) * (dc < 90) - 0.4 * gauss(dc - 84, 0.9))
    CODE[cuffm] = CUFF
    STRIPE = np.maximum(STRIPE, sleeve * sstep(69.4, 70.6, dc) * (1 - sstep(73.4, 74.6, dc)))
    GROOVE = np.maximum(GROOVE, sleeve * gauss(dc - 84, 0.9))

    # --- воротник-стойка: кант у верхнего сгиба по наружной стороне
    col = isl == 4
    if col.any():
        # стойка = полоса, перегнутая по верху: в развёртке это вертикальная лента, сгиб идёт по её середине.
        # Расстояние до краёв острова 4 (шов втачивания снаружи и изнутри) максимально на сгибе; по строкам
        # атласа берём это максимум (полувысоту стойки) и кладём кант в 5–14 и 18–22 мм от сгиба (с обеих сторон).
        segs4 = [s_ for c in ("neck", "open", "seam") for s_ in segs[c] if s_[0] == 4]
        d4 = seg_distance(segs4, isl, pxmm, 80.0)
        rows = np.where(col, d4, 0).max(1)
        rows = np.convolve(rows, np.ones(9) / 9, mode="same")
        from_fold = rows[:, None] - d4
        for a_, b_ in ((5, 14), (18, 22)):
            STRIPE = np.maximum(STRIPE, col * sstep(a_ - 0.6, a_ + 0.6, from_fold) * (1 - sstep(b_ - 0.6, b_ + 0.6, from_fold)))

    # ================================================================== перёд (остров 0): запах B
    # Дизайн задан точками в плоскости (x, y) модели, а считается в мм развёртки острова 0: она почти
    # изометрична поверхности, поэтому полосы, карманы и узел не перекашиваются на наклонной груди.
    front = isl == 0
    fy_, fx_ = np.nonzero(front & (Z > -0.03))
    fX, fY = X[fy_, fx_], Y[fy_, fx_]
    fU, fW = S0[fy_, fx_], T0_[fy_, fx_]

    def uv(p):
        k = np.argmin((fX - p[0]) ** 2 + (fY - p[1]) ** 2)
        return np.array([fU[k], fW[k]])

    def path_uv(pts):
        return [tuple(uv(p)) for p in pts]

    P2 = np.stack([S0, T0_], -1)                          # мм развёртки
    def extend(path, mm=150.0):
        """Продлить ломаную за оба конца по направлению крайних отрезков (без «шапок» у концов)."""
        p = [np.array(q) for q in path]
        a = p[0] + (p[0] - p[1]) / np.linalg.norm(p[0] - p[1]) * mm
        b = p[-1] + (p[-1] - p[-2]) / np.linalg.norm(p[-1] - p[-2]) * mm
        return [tuple(a)] + [tuple(q) for q in p] + [tuple(b)]

    F_TOP = extend(path_uv([(0.075, 0.855), (-PLACKET, Y_CROSS), (-PLACKET, 0.22)]))
    F_UND = extend(path_uv([(-0.075, 0.855), (PLACKET, Y_CROSS), (PLACKET, 0.22)]))
    BW = BAND_W * 1000
    dT, sT, aT = polyline(P2, F_TOP)
    dU, sU, aU = polyline(P2, F_UND)
    ref_t = polyline(uv((0.10, 0.50))[None], F_TOP)[1][0]
    ref_u = polyline(uv((-0.10, 0.50))[None], F_UND)[1][0]
    top = front & (sT * ref_t > 0)
    under = front & ~top
    band_t = top & (dT < BW)
    band_u = under & (sU * ref_u > 0) & (dU < BW)
    vgap = under & (sU * ref_u < 0)                       # V над перекрестьем: вырез, в тени
    base = FOLD.copy()

    def band_surface(dm, al, lvl, seed):
        hb, cb = waffle(al, dm, seed)
        fold = prof(dm, 3.8)                               # сгиб у края полы
        seam_in = BW - dm                                  # шов притачивания с другой стороны
        h = base + lvl - 2.5 + 2.5 * fold + hb * sstep(2, 5, dm) * sstep(2, 5, seam_in)
        h += -0.7 * gauss(seam_in, 1.1) - 0.45 * gauss(seam_in - 4.5, 0.9) + 0.4 * gauss(seam_in - 9, 2.5)
        st = sstep(4.4, 5.6, dm) * (1 - sstep(13.4, 14.6, dm)) + sstep(17.4, 18.6, dm) * (1 - sstep(21.4, 22.6, dm))
        return h, cb, st, gauss(seam_in, 1.1) + gauss(seam_in - 4.5, 0.9)

    hU, cU, stU, grU = band_surface(dU, aU, 2.5, 21)      # нижняя пола: тело 0, полоса +2.5
    H = np.where(band_u, hU, H)
    CAV = np.where(band_u, cU, CAV)
    STRIPE = np.where(band_u, stU, STRIPE)
    GROOVE = np.where(band_u, np.maximum(GROOVE, grU), GROOVE)
    CODE[band_u] = BAND
    vdepth = sstep(0, 20, np.minimum(dU, dT))
    H = np.where(vgap, base - 2.5 * vdepth + hw * 0.6, H)
    CODE[vgap] = INNER
    H = np.where(top & ~band_t, base + 1.5 + hw, H)       # верхняя пола лежит поверх: +1.5, полоса +4
    hT, cT, stT, grT = band_surface(dT, aT, 4.0, 22)
    H = np.where(band_t, hT, H)
    CAV = np.where(band_t, cT, CAV)
    STRIPE = np.where(band_t, stT, STRIPE)
    GROOVE = np.where(band_t, np.maximum(GROOVE, grT), GROOVE)
    CODE[band_t] = BAND
    level = np.where(top, np.where(band_t, 4.0, 1.5), np.where(band_u, 2.5, 0.0))
    log("запах готов")

    # --- накладные карманы (тело кармана; верх — клапаны-подгибы, острова 5, 6, 8, 9)
    def patch(x0, x1, y0, y1, seed):
        nonlocal H, CAV
        a, b = uv(((x0 + x1) / 2, y0)), uv(((x0 + x1) / 2, y1))
        l, r = uv((x0, (y0 + y1) / 2)), uv((x1, (y0 + y1) / 2))
        u0, u1, w0, w1 = l[0], r[0], a[1], b[1]
        d = np.minimum(np.minimum(S0 - u0, u1 - S0), np.minimum(T0_ - w0, w1 - T0_))
        m = front & (d > 0)
        hp, cp = waffle(S0 + 3.7 + seed, T0_ + 5.1, seed)
        h = base + level + 1.5 * prof(d, 1.8) + hp * sstep(1.5, 4, d) - 0.45 * gauss(d - 5, 0.9)
        for cu in (u0 + 4, u1 - 4):                         # закрепки в верхних углах
            h += 0.6 * np.exp(-((S0 - cu) / 1.6) ** 2 - ((T0_ - (w1 - 6)) / 5) ** 2)
        H = np.where(m, h, H)
        CAV = np.where(m, cp, CAV)
        CODE[m] = POCKET
        GROOVE[m] = np.maximum(GROOVE[m], gauss(d - 5, 0.9)[m])

    patch(0.085, 0.195, 0.245, 0.428, 41)
    patch(-0.185, -0.055, 0.245, 0.428, 42)
    patch(0.055, 0.155, 0.548, 0.655, 43)
    patch(-0.158, -0.058, 0.548, 0.655, 44)

    # --- подпалины от искр (перёд, у подола и на кармане)
    for (cx, cy, r) in ((-0.100, 0.236, 4.5), (0.160, 0.268, 3.6), (-0.020, 0.300, 3.0)):
        c = uv((cx, cy))
        rr = np.hypot(S0 - c[0], T0_ - c[1])
        m = front & (rr < r * 4)
        H = np.where(m, H - 0.6 * gauss(rr, r * 0.8) + 0.35 * gauss(rr - r * 1.1, 0.9), H)
        SCORCH = np.maximum(SCORCH, m * np.clip(1.25 - rr / (r * 3.2), 0, 1))

    # ================================================================== пояс, шлёвки (0 и 3)
    belt_d = (BELT_H - np.abs(Y - BELT_Y)) * 1000          # мм от края пояса внутрь
    beltm = torso & (belt_d > 0)
    hb, cb = waffle(arc, Y * 1000, 51)
    h_belt = H + (base + BELT_TOP + hb * sstep(2, 5, belt_d) - H) * prof(belt_d, 3.5)
    h_belt += -0.45 * gauss(belt_d - 4.5, 0.9)
    H = np.where(beltm, h_belt, H)
    CAV = np.where(beltm, cb, CAV)
    CODE[beltm] = BELT
    GROOVE = np.where(beltm, np.maximum(GROOVE, gauss(belt_d - 4.5, 0.9)), GROOVE)
    ld = (6.0 - D["side"])                                  # шлёвки на боковых швах, ширина 12 мм
    lv = (0.036 - np.abs(Y - BELT_Y)) * 1000
    loopm = torso & (ld > 0) & (lv > 0)
    dl = np.minimum(ld, lv)
    hl, cl = waffle(Y * 1000, arc + 2.2, 52)
    h_loop = H + (base + BELT_TOP + 3.0 + 0.5 * hl * sstep(1.5, 3, dl) - H) * prof(dl, 2.0)
    h_loop += 0.7 * gauss(lv - 4, 1.6) * (ld > 0)          # закрепки на концах
    H = np.where(loopm, h_loop, H)
    CODE[loopm] = LOOP
    log("пояс и шлёвки готовы")

    # ================================================================== рулон полотенца в кармане −x (до узла: он справа)
    A_, B_ = uv((-0.108, 0.468)), uv((-0.130, 0.530))
    ax = B_ - A_
    Lr = np.linalg.norm(ax)
    ax /= Lr
    pr = np.array([-ax[1], ax[0]])
    ta = (S0 - A_[0]) * ax[0] + (T0_ - A_[1]) * ax[1]
    tp = (S0 - A_[0]) * pr[0] + (T0_ - A_[1]) * pr[1]
    RR = 19.0
    side = front & (ta > 0) & (ta < Lr) & (np.abs(tp) < RR)
    cap_a = (ta - Lr) / (RR * 0.5)
    capr = np.hypot(cap_a, tp / RR)
    cap = front & (capr < 1)
    hs = base + BELT_TOP + 1 + 9.0 * tube(tp, RR) ** 0.7
    edge_line = ta - (0.35 * Lr + tp * 0.45)               # край наружного слоя рулона по спирали
    hs += 0.8 * sstep(-0.6, 0.6, edge_line) - 0.5 * gauss(edge_line, 0.8)
    hs = H + (hs - H) * prof(RR - np.abs(tp), 2.5)
    H = np.where(side & ~cap, hs, H)
    STRIPE = np.where(side & ~cap, ((ta > 0.60 * Lr) & (ta < 0.74 * Lr)).astype(np.float32), STRIPE)
    th = np.arctan2(tp / RR, cap_a)
    rho = capr * RR
    spiral = (rho + th / (2 * np.pi) * 3.2) / 3.2
    sp = np.abs(spiral - np.round(spiral))
    hc = base + BELT_TOP + 1 + 9.0 * np.sqrt(np.clip(1 - capr ** 2, 0, 1)) ** 0.4 - 0.7 * gauss(sp, 0.12) * (capr < 0.92)
    hc = H + (hc - H) * prof((1 - capr) * RR, 2.0)
    H = np.where(cap, hc, H)
    CODE[side | cap] = LINEN
    CAV = np.where(cap, gauss(sp, 0.12), np.where(side, 0.0, CAV))

    # ================================================================== концы пояса, бахрома, узел (перёд, +x)
    def ribbon(pts, width, top_lvl, seed, twist_at=0.45):
        nonlocal H, CAV
        path = path_uv(pts)
        wmm = width * 1000
        d, s, al = polyline(P2, path)
        L = sum(np.hypot(*(np.array(path[k + 1]) - path[k])) for k in range(len(path) - 1))
        t = al / L
        w = wmm * (1 - 0.22 * gauss(t - twist_at, 0.12))
        e = w / 2 - d
        endd = L - al                                       # мм до конца
        m = front & (e > 0) & (t < 0.999)
        hr, cr = waffle(al, d * s + 50, seed)
        h = H + (base + top_lvl + hr * sstep(1.5, 4, e) * sstep(1.5, 4, endd) - H) * prof(np.minimum(e, endd + 0.5), 2.4)
        h += 0.9 * (endd < 15) * prof(endd, 1.5) - 0.45 * gauss(endd - 11, 0.9)       # подгиб конца
        h += -1.0 * gauss((t - twist_at) * L - d * s * 0.6, 2.0) * (e > 3)            # залом перекрута
        H = np.where(m, h, H)
        CAV = np.where(m, cr, CAV)
        CODE[m] = KNOT
        GROOVE[m] = np.maximum(GROOVE[m], gauss(endd - 11, 0.9)[m])
        end = np.array(path[-1])
        dirv = end - np.array(path[-2])
        dirv /= np.linalg.norm(dirv)
        perp = np.array([-dirv[1], dirv[0]])
        rng = np.random.default_rng(seed)
        for k in range(9):                                  # бахрома: пучки нитей 2.5–3 мм
            o = (k + 0.5) / 9 - 0.5
            p0 = end + perp * o * wmm * 0.92
            ang = rng.uniform(-0.25, 0.25)
            dv = np.array([dirv[0] * np.cos(ang) - dirv[1] * np.sin(ang), dirv[0] * np.sin(ang) + dirv[1] * np.cos(ang)])
            Lf = rng.uniform(14, 24)
            df, _, af = polyline(P2, [tuple(p0 - dv * 2), tuple(p0 + dv * Lf)])
            rf = rng.uniform(1.25, 1.5)
            mf = front & (df < rf) & (af > 0.5)
            hf = H + (2.2 * tube(df, rf) + 0.3 * np.sin(af * 2.2)) * (1 - 0.4 * af / Lf)
            H = np.where(mf, np.maximum(H, hf), H)
            CODE[mf] = FRINGE
            THREAD[mf] = 1

    ribbon([(0.064, 0.486), (0.076, 0.41), (0.085, 0.34), (0.088, 0.300)], 0.042, BELT_TOP + 2.0, 61, 0.5)
    ribbon([(0.040, 0.484), (0.031, 0.40), (0.023, 0.31), (0.019, 0.250)], 0.045, BELT_TOP + 2.5, 62, 0.42)
    K = uv((0.050, 0.500))
    kx, ky = (S0 - K[0]) / 38.0, (T0_ - K[1]) / 32.0
    kr = np.hypot(kx, ky)
    km = front & (kr < 1)
    dome = np.sqrt(np.clip(1 - kr ** 2, 0, 1)) ** 0.7
    hk, ck = waffle(((S0 - K[0]) * 0.8 - (T0_ - K[1]) * 0.6), ((S0 - K[0]) * 0.6 + (T0_ - K[1]) * 0.8), 63)
    lw = np.abs((S0 - K[0]) * 0.55 + (T0_ - K[1]) * 0.83)              # поперёк петли (наискосок)
    loop = prof(21 - lw, 2.6) * (lw < 21)
    hkn = base + BELT_TOP + 6.5 * dome + 3.0 * loop + 0.8 * hk * sstep(0.1, 0.3, dome)
    hkn += -1.2 * gauss(lw - 21, 1.4) * (kr < 0.95)                    # тень под краем петли
    for a in (0.6, 1.9, 3.4, 4.6):                                      # заломы от центра
        rx, ry = np.cos(a), np.sin(a)
        hkn += -0.9 * gauss((kx * ry - ky * rx) * 30, 1.2) * (kx * rx + ky * ry > 0.3) * dome
    H = np.where(km, H + (hkn - H) * prof((1 - kr) * 34, 2.5), H)
    CAV = np.where(km, ck, CAV)
    CODE[km] = KNOT
    log("рулон, узел и концы готовы")

    # ================================================================== веточка и листья в нагрудном +x
    twig = path_uv([(0.104, 0.664), (0.101, 0.700), (0.094, 0.735), (0.086, 0.760)])
    s0 = np.array(uv((0.100, 0.712)))
    s1 = s0 + 22.0 * np.array([np.cos(np.radians(150)), np.sin(np.radians(150))])
    shoot = [tuple(s0), tuple(s1)]
    for path, r in ((twig, 2.3), (shoot, 1.6)):
        d, _, al = polyline(P2, path)
        m = front & (d < r)
        bud = 0.25 * gauss(np.sin(al / 9.0), 0.25)
        H = np.where(m, np.maximum(H, H + 2 * r * tube(d, r) + bud), H)
        CODE[m] = TWIG

    def leaf(b0, ang, L, W, seed):
        """Лист: черешок в точке b0 (мм развёртки), направление ang (град., 0 = +u), длина L, ширина W, мм."""
        nonlocal H
        b0 = np.asarray(b0, float)
        ca, sa = np.cos(np.radians(ang)), np.sin(np.radians(ang))
        a = ((S0 - b0[0]) * ca + (T0_ - b0[1]) * sa) / L
        b = -(S0 - b0[0]) * sa + (T0_ - b0[1]) * ca
        half = W / 2 * np.sin(np.pi * np.clip(a, 0, 1)) ** 0.75 * (1 - 0.3 * np.clip(a, 0, 1))
        e = half - np.abs(b)
        m = front & (a > 0) & (a < 1) & (e > 0)
        bm = np.abs(b)
        vein = 0.0
        for k in range(1, 7):
            vein = vein + 0.45 * gauss((a - k / 7.0) * L - bm * 0.9, 0.9) * (bm < half * 0.9)
        serr = 0.25 * (np.sin(a * L / 2.6) > 0.3)
        h = H + 0.6 + 0.7 * gauss(bm, 0.9) + vein + 1.0 * (1 - sstep(0, 3.5, e)) + serr * (e < 1.2)
        H = np.where(m, np.maximum(H, h), H)
        CODE[m] = LEAF
        log("лист", seed, "текселей", int(m.sum()), "L", round(float(L), 1))

    leaf(twig[-1], 105, 38, 24, 71)
    leaf(shoot[-1], 165, 32, 20, 72)
    log("веточка и листья готовы")

    # нить-бахрома по сгибу отворота (редкие петли)
    rng = np.random.default_rng(9)
    for n in (1, 2):
        m = (isl == n) & (dc < 3.5)
        if m.any():
            ph = fbm(S0 / 6, T0_ / 6, 80 + n)
            loops = m & (ph > 0.62)
            H = np.where(loops, H + 1.2 * sstep(0.62, 0.72, ph), H)
            THREAD = np.maximum(THREAD, loops * 1.0)

    # клапаны: две стороны лежат в 2–3 мм друг от друга — рельеф вдвое мельче, иначе слои протыкают друг друга
    # только наружу, без крупных складок: иначе изнанка проходит сквозь лицо и лучи ловят её с обратной стороны
    flap = np.isin(isl, (5, 6, 8, 9))
    H = np.where(flap, np.clip(H - FOLD + 1.4, 0, 3.0) * 0.6, H)
    H[~cov] = 0
    return dict(H=H.astype(np.float32), CODE=CODE, CAV=CAV, STRIPE=STRIPE, GROOVE=np.clip(GROOVE, 0, 1),
                SCORCH=SCORCH, THREAD=THREAD, ISL=isl, POS=pos, NRM=nrm)


def dilate(a, cov, steps=6):
    """Заполнить поля за краем островов ближайшим (несколько шагов), чтобы выборка по UV у шва не брала пустоту."""
    a = a.copy()
    m = cov.copy()
    for _ in range(steps):
        acc = np.zeros_like(a, dtype=np.float32)
        cnt = np.zeros(m.shape, np.float32)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            mm = np.roll(m, (dy, dx), (0, 1))
            mk = mm[..., None] if a.ndim == 3 else mm
            acc += np.where(mk, np.roll(a, (dy, dx), (0, 1)), 0)
            cnt += mm
        new = ~m & (cnt > 0)
        c = cnt[new][:, None] if a.ndim == 3 else cnt[new]
        a[new] = (acc[new] / c).astype(a.dtype)
        m |= new
    return a


def previews(d):
    from PIL import Image
    H, cov = d["H"], d["ISL"] >= 0
    gy, gx = np.gradient(H / 0.68)          # мм на мм (тексель 2048 ≈ 0.68 мм)
    nx, ny = -gx, gy
    l = np.array([-0.5, 0.6, 0.62])
    l /= np.linalg.norm(l)
    shade = (nx * l[0] + ny * l[1] + l[2]) / np.sqrt(nx ** 2 + ny ** 2 + 1)
    img = np.clip(shade * 210 + 20, 0, 255).astype(np.uint8)
    img[~cov] = 30
    Image.fromarray(img).resize((1024, 1024), Image.LANCZOS).save(OUT / "preview_relief.png")
    Image.fromarray(img[700:1800, 0:1000]).save(OUT / "preview_relief_front_crop.png")
    pal = np.array([[30, 30, 30], [187, 168, 137], [160, 140, 110], [140, 125, 100], [200, 180, 150],
                    [170, 150, 120], [120, 100, 80], [230, 220, 200], [207, 198, 180], [90, 70, 50],
                    [92, 106, 57], [60, 50, 40], [150, 130, 100], [180, 160, 130]], np.uint8)
    c = pal[np.clip(d["CODE"], 0, 13)]
    c[d["STRIPE"] > 0.5] = (142, 58, 48)
    Image.fromarray(c).resize((1024, 1024), Image.NEAREST).save(OUT / "preview_code.png")
    m = np.dstack([d["CAV"], d["GROOVE"], np.maximum(d["SCORCH"], d["THREAD"])])
    Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8)).resize((1024, 1024), Image.LANCZOS).save(OUT / "preview_masks.png")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = build()
    cov = d["ISL"] >= 0
    log("поле: H от", float(d["H"][cov].min()), "до", float(d["H"][cov].max()), "мм")
    previews(d)
    out = {}
    for k in ("H", "CAV", "STRIPE", "GROOVE", "SCORCH", "THREAD"):
        out[k] = dilate(d[k].astype(np.float32), cov).astype(np.float16)
    out["CODE"] = dilate(d["CODE"].astype(np.float32), cov).round().astype(np.uint8)
    out["ISL"] = d["ISL"]
    np.savez_compressed(OUT / "fields.npz", **out)
    log("записано", OUT / "fields.npz")


if __name__ == "__main__":
    main()
