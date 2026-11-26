"""Sauna Shotgun v2: рельеф high-poly как функции numpy (PLAN_v2.md, раздел 3).

Каждая функция получает точки поверхности P (n, 3) и нормали N (n, 3) в координатах OBJ (метры; x — вправо от
стрелка, +x — левый бок, виден игроку; y — вверх; z — к дулу) и возвращает:
  h    сдвиг по нормали, м (рельеф);
  col  цвет вершины, линейный RGB (то, что потом уточняет texture_v2.py);
  ids  код материала (bake_shotgun.IDS);
  m1   маски (n, 3): R — ржавчина/полость (ямка, трещина, бороздка), G — светлое (царапина, гребень, зачистка),
       B — своя у каждой части (у дерева — поздняя древесина, у металла — окалина).
Цвет и рельеф считаются одними функциями — совпадают пиксель в пиксель. Работает и в Blender, и в .venv
(предпросмотр: `python fields_dbs.py`).

Размеры — под плотность текселей (PLAN_v2 §1.2): трубы 19 px/см (пиксель 0.53 мм), колодка 25.7, приклад 11.7.
Минимальная форма 3–4 px, склоны 10–30°.
"""
import numpy as np

try:
    import noise_np as NN
except ImportError:  # запуск из корня репозитория
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import noise_np as NN

MM = 0.001
IDS = {"metal": 1, "wood": 2, "bark": 3, "twine": 4, "towel": 5, "leaf": 6, "resin": 7, "nail": 8,
       "fore": 9, "burn": 10}


def lin(h):
    return np.array([(int(h[i:i + 2], 16) / 255) ** 2.2 for i in (0, 2, 4)])


def hash01(*ints, seed=0):
    """Псевдослучайное 0..1 по целым массивам (векторно)."""
    x = np.int64(seed * 2654435761 % 2 ** 31)
    for k, a in enumerate(ints):
        x = x ^ (np.asarray(a, np.int64) * (73856093, 19349663, 83492791, 2147483587)[k % 4])
    x = (x ^ (x >> 13)) * 1274126177
    return ((x ^ (x >> 16)) & 0xFFFF).astype(np.float64) / 65535


def bowl(d):
    """Профиль чаши без светлого ободка: 1 в центре, 0 на краю (d — расстояние / радиус)."""
    return np.where(d < 1, (1 - np.clip(d, 0, 1) ** 2) ** 2, 0.0)


# ====================================================================== трубы стволов
AXIS_A = (0.036623, 0.002627)   # ось первого ствола (x > 0), bake/barrel_copy.json
R_NOM = 0.029                   # радиус ствола (0.028 у дула, 0.031 у казённика)
C_NOM = 2 * np.pi * R_NOM
SEAM_TH = np.radians(60)        # шов на первом стволе — сверху снаружи (на втором уходит вбок)
THREAD = (0.4045, 0.4335, 2.3 * MM, 0.33 * MM)   # резьба у дула: от, до, шаг, глубина
WRENCH = ((np.radians(150), 0.262), (np.radians(-35), 0.262))   # следы трубного ключа: угол, z
WRENCH_W = 15 * MM


def wrap(d, period):
    return (d + period / 2) % period - period / 2


def tube_coords(P):
    x, y, z = P[:, 0] - AXIS_A[0], P[:, 1] - AXIS_A[1], P[:, 2]
    th = np.arctan2(y, x)
    return th, th * R_NOM, z, np.hypot(x, y)


def cell_pits(s, z, cell, rmin, rmax, depth_k, prob, seed, period=C_NOM):
    """Круглые раковины по ячейкам (своя чаша в каждой живой ячейке). Радиус — степенной закон (много мелких,
    мало крупных), глубина растёт с размером. prob(cs, cz) — доля живых ячеек по месту."""
    ns = max(int(round(period / cell)), 1)
    cs = period / ns
    i0 = np.floor(s / cs).astype(np.int64)
    j0 = np.floor(z / cell).astype(np.int64)
    h = np.zeros(len(s))
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            ii, jj = (i0 + di) % ns, j0 + dj
            cx = (ii + 0.15 + 0.7 * hash01(ii, jj, 1, seed=seed)) * cs
            cz = (jj + 0.15 + 0.7 * hash01(ii, jj, 2, seed=seed)) * cell
            rad = rmin + (rmax - rmin) * hash01(ii, jj, 3, seed=seed) ** 2.6
            alive = hash01(ii, jj, 4, seed=seed) < prob(cx, cz)
            d = np.hypot(wrap(s - cx, period), z - cz) / rad
            h = np.minimum(h, -depth_k * rad * 2 * bowl(d) * alive)
    return h


def tube_field(P, N):
    th, s, z, r = tube_coords(P)
    rad = np.stack([np.cos(th), np.sin(th), np.zeros_like(th)], -1)
    lat = NN.smooth((np.abs((N * rad).sum(-1)) - 0.75) / 0.2)      # только боковая поверхность трубы
    n = len(P)
    h = np.zeros(n)
    rust = np.zeros(n)
    bright = np.zeros(n)
    rg = np.random.default_rng(17)

    # общая фактура старой трубы: волна проката и мелкая шероховатость (формы 2–15 мм)
    Pn = np.stack([s, z, np.zeros(n)], -1)
    h += 0.09 * MM * (NN.fbm(Pn * 140, 3, 701) - 0.5) * 2
    h += 0.06 * MM * (NN.fbm(Pn * 420, 2, 702) - 0.5) * 2
    scale = NN.smooth((NN.fbm(Pn * 45, 3, 703) - 0.45) * 3)      # пятна окалины (цвет)

    # заводской шов трубы: широкий пологий валик (урок v1.11: узкий крутой читался трещиной)
    ds = wrap(s - SEAM_TH * R_NOM, C_NOM)
    sig = 1.2 * MM * (0.85 + 0.3 * NN.fbm(np.stack([z * 300, z * 0, z * 0 + 3], -1), 2, 704))
    g = np.exp(-(ds / sig) ** 2)
    rip = 0.5 + 0.5 * np.cos(2 * np.pi * (z - 0.8 * np.abs(ds)) / (3.0 * MM))
    seam_on = NN.smooth((z - 0.072) / 0.004) * NN.smooth((THREAD[0] - 0.002 - z) / 0.004)
    h += 0.30 * MM * g * (0.78 + 0.22 * rip) * seam_on
    bright = np.maximum(bright, 0.6 * NN.smooth((g - 0.55) / 0.35) * rip * seam_on)

    # резьба у дула (обрезок водопроводной трубы): винтовая нитка, к концу сбита, в канавках грязь
    z0, z1, pitch, dep = THREAD
    zone = NN.smooth((z - z0) / 0.003) * NN.smooth((z1 - z) / 0.0008)
    v = ((z - th / (2 * np.pi) * pitch) / pitch) % 1.0
    groove = (0.5 + 0.5 * np.cos(2 * np.pi * v)) ** 1.4
    worn = 0.55 + 0.45 * NN.smooth((NN.fbm(np.stack([s * 180, z * 180, s * 0 + 5], -1), 3, 705) - 0.35) * 2.5)
    h += -dep * groove * zone * worn
    rust = np.maximum(rust, 0.55 * groove * zone)
    bright = np.maximum(bright, 0.7 * NN.smooth((0.25 - groove) / 0.2) * zone * worn)

    # следы трубного ключа: насечки вдоль ствола через 2.4 мм, две губки напротив
    for thw, zw in WRENCH:
        dsw = wrap(s - thw * R_NOM, C_NOM)
        env = NN.smooth((9.0 * MM - np.abs(dsw)) / (1.5 * MM)) * NN.smooth((WRENCH_W / 2 - np.abs(z - zw)) / (2 * MM))
        k = np.floor(dsw / (2.4 * MM))
        vv = dsw / (2.4 * MM) - k
        keep = hash01(k.astype(np.int64) + 50, int(zw * 1000), seed=706) > 0.2
        tooth = np.exp(-((vv - 0.5) / 0.16) ** 2) * keep
        tooth *= 0.6 + 0.4 * np.cos(np.clip((z - zw) / (WRENCH_W / 2), -1, 1) * np.pi / 2)
        h += -0.24 * MM * tooth * env
        bright = np.maximum(bright, 0.8 * tooth * env)

    # вмятины: степенной закон 5–20 мм, глубина растёт с размером, вытянутые под разным углом
    for _ in range(8):
        rr = (2.5 + 7.5 * rg.random() ** 2.2) * MM
        t0, zc = rg.uniform(-np.pi, np.pi), rg.uniform(0.16, 0.40)
        asp, ang = rg.uniform(1.0, 1.8), rg.uniform(0, np.pi)
        du, dz = wrap(s - t0 * R_NOM, C_NOM), z - zc
        a = (du * np.cos(ang) + dz * np.sin(ang)) / rr
        b = (-du * np.sin(ang) + dz * np.cos(ang)) / (rr * asp)
        h += -(0.15 * MM + 0.09 * rr) * bowl(np.hypot(a, b))   # склон до ~10°

    # раковины: крупные Ø 2–6 мм гнёздами и к дулу гуще, мелкие Ø 1.6–2.4 мм только в гнёздах
    def nest(cs, cz):
        q = NN.fbm(np.stack([cs * 35, cz * 35, cs * 0 + 9], -1), 3, 707)
        return np.clip((q - 0.42) * 2.2, 0, 1) * (0.35 + 0.65 * NN.smooth((cz - 0.22) / 0.18))
    hp1 = cell_pits(s, z, 7.0 * MM, 1.0 * MM, 3.0 * MM, 0.09, lambda cs, cz: 0.3 + 0.6 * nest(cs, cz), 708)
    hp2 = cell_pits(s, z, 3.6 * MM, 0.8 * MM, 1.2 * MM, 0.085, lambda cs, cz: 0.25 + 0.6 * nest(cs, cz), 709)
    pits = np.minimum(hp1, hp2) * (1 - zone)
    h += pits
    # изъеденные места: в гнёздах раковины сливаются, поверхность съедена неровно (формы 1.5–4 мм)
    eat = np.clip((nest(s, z) - 0.25) * 2.5, 0, 1) * (1 - zone)
    rough = NN.fbm(np.stack([s * 330, z * 330, s * 0 + 4], -1), 3, 710)
    h += -0.14 * MM * eat * NN.smooth((rough - 0.38) * 2.5)
    rust = np.maximum(rust, 0.5 * eat * NN.smooth((rough - 0.45) * 3))
    rust = np.maximum(rust, np.clip(-pits / (0.15 * MM), 0, 1))

    # продольные царапины: бороздка 1 мм с мягкими концами и заусенцем по краям
    for k_ in range(25):   # 9 глубоких и 16 мелких
        t0, za = rg.uniform(-np.pi, np.pi), rg.uniform(0.15, 0.36)
        L, sl = rg.uniform(0.03, 0.12), rg.uniform(-0.06, 0.06)
        w, dp = (rg.uniform(0.35, 0.5) * MM, rg.uniform(0.12, 0.2) * MM) if k_ < 9 else (0.3 * MM, rg.uniform(0.06, 0.1) * MM)
        t = (z - za) / L
        env = NN.smooth(t / 0.15) * NN.smooth((1 - t) / 0.25)
        dsc = wrap(s - (t0 * R_NOM + sl * (z - za)), C_NOM)
        gq = np.exp(-(dsc / w) ** 2)
        burr = np.exp(-((np.abs(dsc) - 2.0 * w) / (0.6 * w)) ** 2)
        h += (-dp * gq + 0.25 * dp * burr) * env
        bright = np.maximum(bright, 0.9 * np.exp(-(dsc / (1.6 * w)) ** 2) * env)

    h *= lat
    col = np.tile(lin("808080"), (n, 1))
    m1 = np.stack([rust * lat, bright * lat, scale], -1)
    return h, col, np.full(n, IDS["metal"]), m1


# ====================================================================== колодка (MAIN, рамка-швеллер)
FRAME_WELDS = (-0.112, 0.088)   # поперечные швы: колодку сварили из двух обрезков швеллера; передний — к шарниру
FRAME_ISL = {1, 2, 7, 15, 16, 17, 20, 21, 22, 23, 32, 34, 37, 41}   # 15, 21-23: пластины шарнира (в v1.11 на 23 остался контур рисунка Facepunch)


def frame_field(P, N, isl):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    n = len(P)
    h = np.zeros(n)
    rust = np.zeros(n)
    bright = np.zeros(n)
    rg = np.random.default_rng(23)
    chan = isl == 1          # сам швеллер (бока и полки)
    rod = isl == 16          # труба поверх (верхняя планка) — ближе всего к глазу

    h += 0.08 * MM * (NN.fbm(P * 160, 3, 801) - 0.5) * 2 + 0.06 * MM * (NN.fbm(P * 480, 2, 802) - 0.5) * 2
    # риски напильника пятнами по всей рамке (её подгоняли вручную): бороздки 1.2 мм через 2 мм наискось
    fz = ((x + y) * 0.6 + z * 0.8) / (2.0 * MM)
    patch = NN.smooth((NN.fbm(P * 45, 3, 830) - 0.48) * 4)
    fl = np.exp(-(((fz % 1.0) - 0.5) / 0.18) ** 2) * patch
    plate = ~rod
    h += -0.07 * MM * fl * plate
    bright = np.maximum(bright, 0.25 * fl * plate)
    # раковины на швеллере (реже, чем на стволах)
    hp0 = cell_pits(x + y, z, 6.0 * MM, 0.8 * MM, 2.4 * MM, 0.08,
                    lambda cs, cz: 0.3 * NN.smooth((NN.fbm(np.stack([cs * 40, cz * 40, cs * 0 + 1], -1), 2, 831) - 0.35) * 3),
                    832, period=10.0)
    h += hp0 * plate
    rust = np.maximum(rust, 0.7 * np.clip(-hp0 / (0.12 * MM), 0, 1) * plate)
    scale = NN.smooth((NN.fbm(P * 50, 3, 803) - 0.45) * 3)

    # поперечные сварные швы по швеллеру: валик 4 мм, чешуйки через 2.2 мм, брызги вокруг
    for k, zw in enumerate(FRAME_WELDS):
        wob = 0.6 * MM * (NN.fbm(np.stack([x * 300, y * 300, x * 0 + k], -1), 2, 804 + k) - 0.5) * 2
        dz = z - zw - wob
        sig = 1.25 * MM
        g = np.exp(-(dz / sig) ** 2)
        along = x * 1.0 + y * 1.0
        rip = 0.5 + 0.5 * np.cos(2 * np.pi * (along - 0.9 * np.abs(dz)) / (2.2 * MM))
        top = NN.smooth((y + 0.006) / 0.004)              # на верхней полке шов зачищен болгаркой — ниже
        hb = 0.34 * MM * g * (0.8 + 0.2 * rip) * (1 - 0.6 * top)
        h += hb * chan
        bright = np.maximum(bright, chan * (0.5 * NN.smooth((g - 0.5) / 0.4) * rip + 0.6 * top * g))
        rust = np.maximum(rust, chan * 0.25 * np.exp(-((np.abs(dz) - 2.3 * MM) / (0.6 * MM)) ** 2))
        # брызги: капли Ø 1–2 мм в полосе 3–9 мм от шва
        cell = 2.6 * MM
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                a = np.floor(along / cell).astype(np.int64) + di
                b = np.floor(dz / cell).astype(np.int64) + dj
                ca = (a + 0.5 + 0.4 * (hash01(a, b, 1, seed=810 + k) - 0.5)) * cell
                cb = (b + 0.5 + 0.4 * (hash01(a, b, 2, seed=810 + k) - 0.5)) * cell
                live = (hash01(a, b, 3, seed=810 + k) < 0.22) & (np.abs(cb) > 3 * MM) & (np.abs(cb) < 9 * MM)
                rr = (0.5 + 0.5 * hash01(a, b, 4, seed=810 + k)) * MM
                d = np.hypot(along - ca, dz - cb) / rr
                h += chan * live * 0.2 * MM * bowl(d) ** 0.5
                bright = np.maximum(bright, chan * live * 0.5 * (d < 1))

    # следы болгарки: пятна дуговых рисок (диск ~11.5 см) у швов, на боках и верхних полках
    for _ in range(6):
        zc = rg.choice(FRAME_WELDS) + rg.uniform(-0.012, 0.012)
        side = rg.choice([-1, 1])
        cy = rg.uniform(-0.05, -0.02)
        cen = np.array([side * 0.018, cy, zc])
        dd = np.linalg.norm(P - cen, axis=1)
        dl = np.linalg.norm((P - cen) * [1.0, 1.0, 2.5], axis=1)   # пятно вытянуто поперёк шва, край рваный
        env = NN.smooth((rg.uniform(11, 15) * MM - dl + 4 * MM * (NN.fbm(P * 220, 2, 840) - 0.5)) / (3 * MM))
        ctr = cen + np.array([0, rg.uniform(-1, 1), rg.uniform(-1, 1)]) * 0.058
        rr = np.linalg.norm(P - ctr, axis=1)
        v = (rr / (2.0 * MM)) % 1.0
        line = np.exp(-((v - 0.5) / 0.18) ** 2)
        h += -0.08 * MM * line * env * chan - 0.06 * MM * env * chan   # пятно чуть сточено
        bright = np.maximum(bright, chan * env * (0.12 + 0.35 * line))

    # вмятины и забоины от молотка: на полках и боках, Ø 3–8 мм
    for _ in range(30):
        c = np.array([rg.uniform(-0.018, 0.018), rg.uniform(-0.064, -0.016), rg.uniform(-0.155, 0.12)])
        rr = (1.5 + 2.5 * rg.random() ** 1.8) * MM
        d = np.linalg.norm(P - c, axis=1) / rr
        h += -(0.15 * MM + 0.06 * rr) * bowl(d)

    # керны разметки у окна (ряд Ø 1.4 мм) и у отверстий под оси курков
    for zc in np.linspace(-0.07, -0.035, 5):
        for sx in (-1, 1):
            c = np.array([sx * 0.018, -0.024, zc])
            d = np.linalg.norm(P - c, axis=1) / (0.75 * MM)
            h += -0.22 * MM * bowl(d) * chan
            rust = np.maximum(rust, 0.6 * (d < 0.9) * chan)

    # труба-планка сверху: раковины и продольные царапины (её видно от первого лица)
    th = np.arctan2(y + 0.0145, x)
    s = th * 0.0105
    hp_ = cell_pits(s, z, 4.5 * MM, 0.8 * MM, 2.2 * MM, 0.07,
                    lambda cs, cz: 0.25 + 0.35 * NN.smooth((NN.fbm(np.stack([cs * 50, cz * 50, cs * 0], -1), 2, 820) - 0.4) * 3),
                    821, period=2 * np.pi * 0.0105)
    h += hp_ * rod
    rust = np.maximum(rust, np.clip(-hp_ / (0.12 * MM), 0, 1) * rod)
    for _ in range(5):
        za, L = rg.uniform(-0.12, 0.08), rg.uniform(0.02, 0.06)
        x0 = rg.uniform(-0.006, 0.006)
        t = (z - za) / L
        env = NN.smooth(t / 0.15) * NN.smooth((1 - t) / 0.25)
        gq = np.exp(-((x - x0 - 0.03 * (z - za)) / (0.4 * MM)) ** 2)
        h += -0.15 * MM * gq * env * rod
        bright = np.maximum(bright, 0.9 * gq * env * rod)

    col = np.tile(lin("808080"), (n, 1))
    return h, col, np.full(n, IDS["metal"]), np.stack([rust, bright, scale], -1)


# ====================================================================== приклад (STOCK, осина)
PITH = (np.array([-0.11, -0.095, -0.33]), np.array([0.16, 0.035, 1.0]))   # сердцевина сбоку и наклонно: на боках «арки»
KNOT = np.array([-0.020, -0.118, -0.352])    # сучок на боку −x (как в v1)
ORN_Z = (-0.436, -0.404)
ORN_Y = (-0.150, -0.070)
STOCK_AX = (np.array([0.0, -0.095, -0.46]), np.array([0.0, -0.065, -0.20]))   # ось ложи для тесания


def ornament(P):
    """Выжженный гвоздём орнамент на щеке (+x): два столбика точек Ø 3.2 мм и зигзаг 2.2 мм (в v1.11: 2.4 и 1.4 мм,
    в нормали не читались)."""
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    y0, y1 = ORN_Y
    zone = (x > 0.004) & (y > y0 - 0.004) & (y < y1 + 0.004) & (z > ORN_Z[0] - 0.005) & (z < ORN_Z[1] + 0.005)
    m = np.zeros(len(P))
    yy = np.round((y - y0) / 0.0065) * 0.0065 + y0
    ok = (yy >= y0) & (yy <= y1)
    for zc in ORN_Z:
        d = np.hypot(z - zc, y - yy)
        m = np.maximum(m, NN.smooth((1.6 * MM - d) / (0.6 * MM)) * ok)
    zm = (ORN_Z[0] + ORN_Z[1]) / 2
    ph = ((y - y0) / 0.009) % 2.0
    tri = np.where(ph < 1, ph, 2 - ph) - 0.5
    zz = zm + tri * 0.013
    m = np.maximum(m, NN.smooth((1.1 * MM - np.abs(z - zz)) / (0.45 * MM)) * ((y >= y0) & (y <= y1)))
    return m * zone


def stock_field(P, N, isl):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    n = len(P)
    rg = np.random.default_rng(31)
    # годичные кольца: расстояние до сердцевины (наклонная ось — на плоских боках выходят «арки»)
    o, d = PITH[0], PITH[1] / np.linalg.norm(PITH[1])
    q = P - o
    radial = q - np.outer(q @ d, d)
    r = np.linalg.norm(radial, axis=1)
    kd = np.linalg.norm(P - KNOT, axis=1)
    r = r + 2.0 * MM * np.exp(-(kd / (11 * MM)) ** 2) * np.sin(kd / (3 * MM))     # свиль вокруг сучка
    wob = NN.fbm(np.stack([x * 14, y * 14, z * 4], -1), 2, 901)
    ring_w = 3.4 * MM * (0.7 + 0.6 * NN.fbm(np.stack([r * 40, r * 0, r * 0 + 2], -1), 2, 902))
    ph = (r / ring_w + wob * 5.0) % 1.0
    # поздняя древесина — гребень с крутым внешним и пологим внутренним краем (ранняя выветрена)
    late = NN.smooth((ph - 0.55) / 0.3) * NN.smooth((1.0 - ph) / 0.06)
    # волокна вдоль ложи: вытянутые полосы, поперёк 3–4 мм
    along = q @ d
    fib = NN.fbm(np.stack([radial[:, 0] * 260, radial[:, 1] * 260, along * 14], -1), 3, 903) - 0.5
    # износ хвата: гребни сглажены (щека и шейка)
    grip = NN.smooth((0.012 - np.linalg.norm((P - np.array([0.02, -0.075, -0.30])) * [0.3, 1.2, 0.35], axis=1)) / 0.01)
    h = 0.45 * MM * late * (1 - 0.6 * grip) + 0.24 * MM * fib * 2
    # мелкие трещинки по волокну (дерево у печи пересыхает): 5–15 мм, раскрытие ~0.5 мм
    for _ in range(70):
        c = np.array([rg.choice([-1, 1]) * 0.022, rg.uniform(-0.165, -0.035), rg.uniform(-0.455, -0.24)])
        L = rg.uniform(0.005, 0.015)
        qd = P - c
        tt = (qd @ d) / L
        perp = np.linalg.norm(qd - np.outer(qd @ d, d) - np.outer(qd[:, 0], [1, 0, 0]), axis=1)
        env = NN.smooth((0.5 - np.abs(tt)) / 0.25) * (np.abs(qd[:, 0]) < 0.006)
        h += -0.3 * MM * np.exp(-(perp / (0.4 * MM)) ** 2) * env

    # тесание скобелем: длинные пологие ложбины 2.5–3.5 см вокруг ложи
    a0, a1 = STOCK_AX
    ax = (a1 - a0) / np.linalg.norm(a1 - a0)
    qq = P - a0
    rr = qq - np.outer(qq @ ax, ax)
    ang = np.arctan2(rr[:, 1], rr[:, 0]) + 0.6 * (qq @ ax)
    u = ang * 0.035
    k = np.floor(u / (30 * MM))
    t = u / (30 * MM) - k
    h += -0.38 * MM * (1 - (2 * t - 1) ** 2) * (0.7 + 0.3 * hash01(k.astype(np.int64), seed=904))

    # трещины усушки у затыльника (по волокну)
    crack = np.zeros(n)
    for _ in range(5):
        side = rg.choice([-1, 1])
        yc = rg.uniform(-0.16, -0.06)
        L = rg.uniform(0.025, 0.06)
        dz_ = z - (-0.462)
        tt = dz_ / L
        env = NN.smooth((1 - tt) / 0.35) * (tt > -0.02)
        dy = y - (yc + 0.08 * dz_ + 0.6 * MM * (NN.fbm(np.stack([z * 200, z * 0 + side, z * 0], -1), 2, 905) - 0.5))
        on = (x * side > 0.008)
        g = np.exp(-(dy / (0.55 * MM)) ** 2)
        sh = np.exp(-(dy / (2.2 * MM)) ** 2)
        crack = np.maximum(crack, g * env * on)
        h += (-0.9 * MM * g - 0.18 * MM * sh) * env * on

    # вмятины и забоины: гуще у пятки, носка и по рёбрам
    for _ in range(28):
        c = np.array([rg.uniform(-0.022, 0.022), rg.uniform(-0.17, -0.03), -0.46 + 0.26 * rg.random() ** 1.6])
        rr_ = (1.5 + 4.5 * rg.random() ** 2.2) * MM
        dd = np.linalg.norm((P - c) * [1, 1, 0.7], axis=1) / rr_
        h += -(0.15 * MM + 0.05 * rr_) * bowl(dd)
        crack = np.maximum(crack, 0.35 * bowl(dd))
    # поперечные задиры
    for _ in range(6):
        c = np.array([rg.choice([-0.021, 0.021]), rg.uniform(-0.16, -0.05), rg.uniform(-0.45, -0.25)])
        dirv = np.array([0, np.cos(a := rg.uniform(0.6, 1.4)), np.sin(a)])
        L = rg.uniform(0.01, 0.03)
        qd = P - c
        tt = (qd @ dirv) / L
        perp = np.linalg.norm(qd - np.outer(qd @ dirv, dirv) - np.outer(qd[:, 0], [1, 0, 0]), axis=1)
        env = NN.smooth(tt / 0.2) * NN.smooth((1 - tt) / 0.2) * (np.abs(qd[:, 0]) < 0.006)
        g = np.exp(-(perp / (0.45 * MM)) ** 2)
        h += -0.22 * MM * g * env

    # сучок: твёрдое тёмное ядро чуть выступает, вокруг — тёмный ободок и 3 радиальные трещинки
    core = np.exp(-(kd / (5.0 * MM)) ** 2) * (x < -0.006)
    rim = np.exp(-((kd - 7.0 * MM) / (1.2 * MM)) ** 2) * (x < -0.006)
    h += 0.25 * MM * core - 0.15 * MM * rim
    # выжженный орнамент
    orn = ornament(P)
    h += -0.55 * MM * orn

    cw, cd = lin("C2A77E"), lin("7E6142")
    tone = 0.3 * late + 0.25 * NN.fbm(np.stack([x * 120, y * 120, z * 3], -1), 3, 906) + 0.15 * (fib + 0.5)
    col = cw + (cd - cw) * np.clip(tone, 0, 1)[:, None]
    kc = lin("4E3624")
    wk = np.clip(core * 0.95 + rim * 0.7, 0, 1)[:, None]
    col = col * (1 - wk) + kc * wk
    cb = lin("2E2018")
    halo = (NN.smooth(orn * 3) * 0.35)[:, None]
    col = col * (1 - halo) + cb * halo
    col = col * (1 - orn[:, None]) + cb * orn[:, None]
    ids = np.where(orn > 0.5, IDS["burn"], IDS["wood"])
    m1 = np.stack([np.maximum(crack, orn), late, grip], -1)
    return h, col, ids, m1


def iron_field(P, N, seed=41):
    """Железо приклада (скоба, уголки затыльника): риски напильника поперёк, забоины."""
    n = len(P)
    rg = np.random.default_rng(seed)
    h = 0.04 * MM * (NN.fbm(P * 200, 3, seed) - 0.5) * 2
    v = ((P[:, 1] * 0.7 + P[:, 2] * 0.7) / (2.0 * MM)) % 1.0
    line = np.exp(-((v - 0.5) / 0.2) ** 2) * NN.smooth((NN.fbm(P * 90, 2, seed + 1) - 0.45) * 4)
    h += -0.07 * MM * line
    bright = 0.5 * line
    for _ in range(6):
        c = P[rg.integers(n)]
        rr = (1.0 + 1.5 * rg.random()) * MM
        d = np.linalg.norm(P - c, axis=1) / rr
        h += -0.2 * MM * bowl(d)
    col = np.tile(lin("808080"), (n, 1))
    return h, col, np.full(n, IDS["metal"]), np.stack([np.zeros(n), bright, np.zeros(n)], -1)


# ====================================================================== вафельное полотенце (как халат сета)
def waffle(u, v, cell=4.6 * MM):
    """Вафельное плетение: выпуклая решётка, ячейки утоплены. 0..1 (1 — гребень решётки)."""
    a = np.abs(((u / cell) % 1.0) - 0.5) * 2
    b = np.abs(((v / cell) % 1.0) - 0.5) * 2
    return np.clip(np.maximum(a, b) ** 3 * 1.4, 0, 1)


def towel_relief(u, v, dist, seed=0):
    """Рельеф полосы полотенца по её координатам: u — вдоль (м), v — поперёк (м), dist — до края (м).
    Возвращает (h, кирпичная полоса 0..1 для цвета, грязь у кромки)."""
    w = waffle(u, v)
    fold = 0.45 * MM * np.clip(NN.fbm(np.stack([u * 90, v * 90, u * 0 + seed], -1), 3, 950 + int(seed)) - 0.45, 0, 1) * 3
    hem = 0.4 * MM * np.exp(-((dist - 2.2 * MM) / (0.9 * MM)) ** 2)          # подшитая кромка — валик
    st = (np.sin(u * 2 * np.pi / (4.0 * MM)) > 0.2)
    stitch = -0.3 * MM * np.exp(-((dist - 2.2 * MM) / (0.45 * MM)) ** 2) * st
    drop = -0.4 * MM * NN.smooth((0.9 * MM - dist) / (0.9 * MM))
    h = 0.7 * MM + 0.28 * MM * w * NN.smooth((dist - 3.5 * MM) / (1 * MM)) + fold + hem + stitch + drop
    return h, w


if __name__ == "__main__":
    # предпросмотр: теневой рельеф полей на плоской развёртке (без Blender) -> plan_v2/fields_preview.png
    from pathlib import Path

    from PIL import Image
    HERE = Path(__file__).resolve().parent
    res = 0.13 * MM   # шаг ~ как пиксель запекания 4096 на трубе

    def shade(H, step):
        gy, gx = np.gradient(H, step)
        nrm = np.stack([-gx, -gy, np.ones_like(H)], -1)
        nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
        L = np.array([-0.6, 0.5, 0.62])
        L /= np.linalg.norm(L)
        return np.clip(nrm @ L, 0, 1)

    tiles = []
    # труба: развёртка θ × z (дуло справа), 0.15…0.44
    th = np.linspace(-np.pi, np.pi, int(C_NOM / res))
    zz = np.linspace(0.15, 0.44, int(0.29 / res))
    TH, ZZ = np.meshgrid(th, zz, indexing="ij")
    P = np.stack([AXIS_A[0] + R_NOM * np.cos(TH), AXIS_A[1] + R_NOM * np.sin(TH), ZZ], -1).reshape(-1, 3)
    Nn = np.stack([np.cos(TH), np.sin(TH), 0 * TH], -1).reshape(-1, 3)
    h, col, ids, m1 = tube_field(P, Nn)
    img = shade(h.reshape(TH.shape), res)
    rgb = np.stack([img] * 3, -1)
    rgb[..., 0] += 0.5 * m1[:, 0].reshape(TH.shape)
    rgb[..., 2] += 0.4 * m1[:, 1].reshape(TH.shape)
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).resize((1200, int(1200 * TH.shape[0] / TH.shape[1]))).save(HERE / "plan_v2" / "field_tube.png")
    print("tube relief range mm", h.min() / MM, h.max() / MM)


def preview_stock():
    from pathlib import Path
    from PIL import Image
    res = 0.25 * MM
    yy = np.arange(-0.17, -0.03, res)
    zz = np.arange(-0.46, -0.20, res)
    Y, Z = np.meshgrid(yy, zz, indexing="ij")
    out = []
    for sx in (1, -1):
        P = np.stack([np.full(Y.shape, 0.021 * sx), Y, Z], -1).reshape(-1, 3)
        Nn = np.tile([sx, 0.0, 0.0], (len(P), 1))
        h, col, ids, m1 = stock_field(P, Nn, None)
        H = h.reshape(Y.shape)[::-1]
        gy, gz = np.gradient(H, res)
        L = np.array([0.5, 0.6, 0.62]); L /= np.linalg.norm(L)
        nrm = np.stack([-gz, -gy, np.ones_like(H)], -1); nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
        sh = np.clip(nrm @ L, 0, 1)[..., None]
        c = col.reshape(Y.shape + (3,))[::-1] ** (1 / 2.2)
        out.append(np.clip(c * (0.35 + 0.9 * sh), 0, 1))
    img = np.concatenate(out, 0)
    Image.fromarray((img * 255).astype(np.uint8)).save(Path(__file__).resolve().parent / "plan_v2" / "field_stock.png")
