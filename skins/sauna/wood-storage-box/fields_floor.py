"""Sauna Stone Box v2: дно — противень, слой углей, пепел, колотые камни, угли, обугленные поленья, совок, лист
(PLAN_v2.md, 3.5 и 8.2). Чистый numpy: сетки и меши, Blender (bake_v2.py) только собирает их в объекты.

Единицы — см, оси OBJ (y вверх, +x — к печи, +z — перед). Дно внутри: x -33.6..31.6, z -43.8..45.1, y 2.4..3.3.
Плотность дна 3.6 px/см при 1024 (1 px = 2.8 мм): формы от 1 см, трещины угля 3-4 мм, камни 4-11 см.

Маски (атрибуты вершин, те же каналы для всех кусков дна):
  m1 = (рябь/волокно, полость, вмятина), m2 = (жар: трещина угля / щель, свежий скол камня, пепел),
  m3 = (ржавая раковина, обугленность, тон куска);  mat — код материала (MAT).
"""
import numpy as np

from fields_walls import fbm2, load_obj, island_of_faces, n2, sstep, vnoise, voronoi

MAT = {"floor": 6, "tray": 7, "coalbed": 8, "ash": 9, "stone": 10, "stone_old": 11, "coal": 12, "log": 13,
       "scoop": 14, "leaf": 18}
INNER = (-33.6, 31.6, -43.8, 45.1)
TRAY_IN = 2.5
TRAY = (INNER[0] + TRAY_IN, INNER[1] - TRAY_IN, INNER[2] + TRAY_IN, INNER[3] - TRAY_IN)
TRAY_R = 3.5                    # скругление углов (глубокая тянутая противень-кювета)
RIM_H = 2.3                     # высота борта над дном противня
BEAD_R = 0.45                   # закатанная кромка
STEP = 0.2                      # шаг сетки поля, см
SCOOP = dict(c=(-19.5, 27.0), yaw=np.radians(-35.0), L=16.0, W=13.0)   # совок: центр, поворот, длина/ширина ковша
SEED = 23
LEAF = dict(c=(10.5, 22.0), r=5.2, ang=np.radians(28.0), L=8.0)   # v2.1: лист лежит на пепле, а не на камне


# ------------------------------------------------------------------ дно ящика (низ из OBJ)
def floor_tris():
    V, _, F = load_obj()
    isl = island_of_faces(F)
    return np.array([[V[c[0] - 1] for c in t] for t, i in zip(F, isl) if i == 35])


def floor_base(X, Z):
    """Высота дна ящика под точкой (барицентрика по треугольникам острова 35)."""
    T = floor_tris()
    Yb = np.full(X.shape, np.nan)
    for t in T:
        (x0, _, z0), (x1, _, z1), (x2, _, z2) = t
        d = (z1 - z2) * (x0 - x2) + (x2 - x1) * (z0 - z2)
        if abs(d) < 1e-9:
            continue
        a = ((z1 - z2) * (X - x2) + (x2 - x1) * (Z - z2)) / d
        b = ((z2 - z0) * (X - x2) + (x0 - x2) * (Z - z2)) / d
        c = 1 - a - b
        m = (a >= -1e-6) & (b >= -1e-6) & (c >= -1e-6)
        Yb = np.where(m & np.isnan(Yb), a * t[0, 1] + b * t[1, 1] + c * t[2, 1], Yb)
    return np.where(np.isnan(Yb), np.nanmean(Yb), Yb)


def tray_dist(X, Z):
    """Знаковое расстояние до края противня (внутри > 0), углы скруглены."""
    x0, x1, z0, z1 = TRAY
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    hx, hz = (x1 - x0) / 2 - TRAY_R, (z1 - z0) / 2 - TRAY_R
    qx, qz = np.abs(X - cx) - hx, np.abs(Z - cz) - hz
    out = np.hypot(np.maximum(qx, 0), np.maximum(qz, 0)) + np.minimum(np.maximum(qx, qz), 0) - TRAY_R
    return -out


def scoop_local(X, Z):
    cx, cz = SCOOP["c"]
    ca, sa = np.cos(SCOOP["yaw"]), np.sin(SCOOP["yaw"])
    dx, dz = X - cx, Z - cz
    return dx * ca + dz * sa, -dx * sa + dz * ca


def grid():
    xs = np.arange(INNER[0] - 0.4, INNER[1] + 0.4 + 1e-6, STEP)
    zs = np.arange(INNER[2] - 0.4, INNER[3] + 0.4 + 1e-6, STEP)
    return np.meshgrid(xs, zs)


def floor_field(X, Z):
    """Поле дна: высота y (абсолютная) и маски. Камни, угли-куски, поленья, совок, лист — отдельные меши сверху."""
    rng = np.random.default_rng(SEED)
    base = floor_base(X, Z)
    zero = np.zeros_like(X)
    # --- доски дна ящика (видны в зазоре у стенок): вдоль z, щели, волокна, подпалины
    bw = 10.8
    bx = (X - INNER[0]) / bw
    bi = np.floor(bx)
    gap = np.abs(bx - np.round(bx)) * bw
    g = 0.5 + 0.5 * np.sin((Z * 0.9 + 6 * fbm2(X * 0.2, Z * 0.03, 3, 3)) * 2.2 + bi * 1.7)
    Hf = base + 0.04 * g - 0.45 * sstep(0.22, 0.05, gap)
    cav = sstep(0.22, 0.05, gap)
    # --- противень
    e = tray_dist(X, Z)
    warp = 0.14 * (fbm2(X * 0.05, Z * 0.05, 5, 3) - 0.5) + 0.05 * np.sin(X * 0.21 + Z * 0.13)
    yb = base.mean() + 0.35 + warp
    wall = RIM_H * sstep(1.4, 0.35, e)
    bead = np.sqrt(np.clip(BEAD_R ** 2 - (e - 0.12) ** 2, 0, None))
    Ht = yb + np.maximum(wall, np.where(np.abs(e - 0.12) < BEAD_R, RIM_H - BEAD_R * 0.6 + bead, 0))
    in_tray = e > -0.33
    dent = zero.copy()
    for k in range(5):                                   # вмятины на борту
        ang = rng.uniform(0, 2 * np.pi)
        px = np.clip((TRAY[0] + TRAY[1]) / 2 + 40 * np.cos(ang), TRAY[0], TRAY[1])
        pz = np.clip((TRAY[2] + TRAY[3]) / 2 + 50 * np.sin(ang), TRAY[2], TRAY[3])
        u = np.clip(1 - ((X - px) ** 2 + (Z - pz) ** 2) / rng.uniform(2.0, 3.2) ** 2, 0, 1) ** 2 * sstep(2.0, 0.0, np.abs(e))
        Ht -= 0.35 * u
        dent = np.maximum(dent, u)
    # раковины ржавчины на борту и у кромки
    f1, f2, idn = voronoi(X * 1.0, Z * 1.0 + 0.3 * X, 0.7, 41)
    rr = 0.14 + 0.22 * ((idn % 991) / 991.0)
    nest = sstep(0.4, 0.65, fbm2(X * 0.08, Z * 0.08, 43, 3)) * sstep(3.0, 0.0, e) * in_tray
    pit = np.clip(1 - (f1 / rr) ** 2, 0, 1) * nest
    Ht -= 0.06 * pit
    # --- слой углей на противне: комья в клетках 1.6-2.4 см, глубокие щели между ними (там жар)
    s_u, s_v = scoop_local(X, Z)
    under_scoop = sstep(1.5, -0.5, np.maximum(np.abs(s_u) - (SCOOP["L"] / 2 + 0.8), np.abs(s_v) - (SCOOP["W"] / 2 + 0.8)))
    big = fbm2(X * 0.06, Z * 0.06, 45, 2)                # комья разного размера: 1.4-3 см
    csz = 1.5 + 1.6 * big
    c1, c2, cid = voronoi(X + 1.5 * fbm2(X * 0.1, Z * 0.1, 47, 2), Z, 2.1, 49)
    c1, c2 = c1 * 2.1 / csz, c2 * 2.1 / csz
    lump = np.sqrt(np.clip(1 - (c1 / 1.35) ** 2, 0, 1))
    taper = sstep(1.6, 4.5, e)
    lump_h = (0.75 + 0.55 * ((cid % 613) / 613.0)) * lump
    k1, k2, _ = voronoi(X, Z, 0.75, 51)                  # трещиноватость комьев
    crk = sstep(0.12, 0.03, k2 - k1) * lump
    Hb = yb + 0.25 + (0.9 + lump_h - 0.12 * crk) * taper * (1 - 0.75 * under_scoop)
    gapc = sstep(0.25, 0.05, c2 - c1) * taper
    ember = np.clip(gapc + 0.35 * crk * taper, 0, 1) * (1 - under_scoop)
    # --- пепел: у бортов внутри, пятнами на углях, горками в зазоре у стенок и в углах ящика
    an = fbm2(X * 0.09, Z * 0.09, 53, 4)
    leafbed = sstep(LEAF["r"] + 1.0, LEAF["r"] - 1.5, np.hypot(X - LEAF["c"][0], Z - LEAF["c"][1]))
    ash_t = np.clip(sstep(0.42, 0.56, an) * 0.95 + sstep(3.2, 1.6, e) * sstep(0.45, 0.65, fbm2(X * 0.2, Z * 0.2, 55, 2))
                    + leafbed, 0, 1) * (e > 1.2)
    ash_t = np.maximum(ash_t, under_scoop * 0.0)
    ash_lvl = yb + 0.3 + 1.6 * ash_t * taper + 0.6 * ash_t * (1 - taper)
    dw = np.minimum.reduce([X - INNER[0], INNER[1] - X, Z - INNER[2], INNER[3] - Z])
    corner = np.minimum(np.minimum(np.hypot(X - INNER[0], Z - INNER[2]), np.hypot(X - INNER[1], Z - INNER[2])),
                        np.minimum(np.hypot(X - INNER[0], Z - INNER[3]), np.hypot(X - INNER[1], Z - INNER[3])))
    ash_m = (sstep(2.2, 0.0, dw) * sstep(0.35, 0.65, fbm2(X * 0.12, Z * 0.12, 57, 3)) * 0.8 + sstep(9.0, 2.0, corner)) * (e < 0.0)
    ash_m_lvl = base + 1.2 * np.clip(ash_m, 0, 1) * (0.7 + 0.3 * fbm2(X * 0.5, Z * 0.5, 59, 2))
    # --- сборка: что выше, то и видно
    H = Hf.copy()
    mat = np.full(X.shape, MAT["floor"])
    H = np.where(in_tray, np.maximum(H, Ht), H)
    mat = np.where(in_tray, MAT["tray"], mat)
    bed = (e > 1.4) & (Hb > Ht + 0.02)
    H = np.where(bed, Hb, H)
    mat = np.where(bed, MAT["coalbed"], mat)
    ash_top = (e > 1.2) & (ash_lvl > H + 0.02)
    ash_mm = (e < 0.0) & (ash_m_lvl > H + 0.05)
    H = np.where(ash_top, ash_lvl + 0.04 * (fbm2(X * 0.8, Z * 0.8, 61, 2) - 0.5), H)
    H = np.where(ash_mm, ash_m_lvl, H)
    ash = (ash_top | ash_mm) * 1.0
    mat = np.where(ash > 0.5, MAT["ash"], mat)
    ember = ember * (1 - ash) * bed
    char = sstep(4.0, 0.0, dw) * (mat == MAT["floor"])          # доски дна у стенок подгорели
    tone = (cid % 997) / 997.0
    m1 = np.stack([np.where(mat == MAT["floor"], g, crk), np.clip(cav + gapc * bed, 0, 1), dent], -1)
    m2 = np.stack([ember, zero, ash], -1)
    m3 = np.stack([pit * in_tray, char, tone], -1)
    return dict(y=H, m1=m1, m2=m2, m3=m3, mat=mat, bed_top=Hb, yb=yb, e=e)


# ------------------------------------------------------------------ меши: икосфера и колотый камень
def icosphere(n):
    t = (1 + 5 ** 0.5) / 2
    V = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
         (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    Fc = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
          (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10),
          (8, 6, 7), (9, 8, 1)]
    V = [np.array(v, float) / np.linalg.norm(v) for v in V]
    for _ in range(n):
        cache = {}

        def mid(a, b):
            key = (min(a, b), max(a, b))
            if key not in cache:
                m = V[a] + V[b]
                V.append(m / np.linalg.norm(m))
                cache[key] = len(V) - 1
            return cache[key]

        nf = []
        for a, b, c in Fc:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        Fc = nf
    return np.array(V), np.array(Fc, np.int64)


_ICO = {}


def ico(n):
    if n not in _ICO:
        _ICO[n] = icosphere(n)
    return _ICO[n]


def rot_matrix(rng, tilt_deg=25.0):
    yaw = rng.uniform(0, 2 * np.pi)
    tx, tz = np.radians(rng.uniform(-tilt_deg, tilt_deg)), np.radians(rng.uniform(-tilt_deg, tilt_deg))
    Ry = np.array([[np.cos(yaw), 0, np.sin(yaw)], [0, 1, 0], [-np.sin(yaw), 0, np.cos(yaw)]])
    Rx = np.array([[1, 0, 0], [0, np.cos(tx), -np.sin(tx)], [0, np.sin(tx), np.cos(tx)]])
    Rz = np.array([[np.cos(tz), -np.sin(tz), 0], [np.sin(tz), np.cos(tz), 0], [0, 0, 1]])
    return Ry @ Rx @ Rz


def polytope_radius(D, c0, abc, planes, k):
    """Расстояние от внутренней точки c0 по направлениям D до поверхности: эллипсоид abc ∩ полупространства
    planes [(n, o, kind)] (n·p <= o), мягкий минимум с радиусом скругления k. Возвращает r и веса каждого члена."""
    inv = 1.0 / np.asarray(abc) ** 2
    a2 = (D * D * inv).sum(1)
    b2 = 2 * (D * c0 * inv).sum(1)
    c2 = (c0 * c0 * inv).sum() - 1
    te = (-b2 + np.sqrt(np.maximum(b2 * b2 - 4 * a2 * c2, 0))) / (2 * a2)
    T = [te]
    for (n, o, _) in planes:
        nd = D @ n
        T.append(np.where(nd > 1e-4, (o - n @ c0) / np.maximum(nd, 1e-4), 1e4))
    T = np.stack(T, 1)
    m = T.min(1, keepdims=True)
    w = np.exp(-(T - m) / k)
    r = m[:, 0] - k * np.log(w.sum(1))
    return r, w / w.sum(1, keepdims=True)


def stone_mesh(rng, size, kind="chipped", crack=False, half=None):
    """Камень размером size (полуось в плане, см). kind: 'chipped' — колотый (грани раскола, сколы на рёбрах),
    'old' — окатанный. half: None или (нормаль раскола, сдвиг) — половинка расколотого камня.
    Возвращает V (n,3) в своих осях (низ на y=0), F (m,3), маски (n,) рябь, полость, свежий скол."""
    D, F = ico(5)
    a, c = size * rng.uniform(0.8, 1.25), size * rng.uniform(0.6, 1.0)
    b = size * rng.uniform(0.5, 0.75)                    # плоские: лежат плашмя
    abc = (a, b, c)
    planes = []
    if kind == "chipped":
        for j in range(rng.integers(9, 14)):            # большие грани раскола; первые две — сверху (кусок лежит
            n = rng.normal(size=3)                       # на сколе, верх — тоже скол)
            if j < 2:
                n[1] = abs(n[1]) + 2.0
            n /= np.linalg.norm(n)
            o = rng.uniform(0.45, 0.78) * np.sqrt(((n * abc) ** 2).sum())
            planes.append((n, o, 1))
        for _ in range(rng.integers(4, 8)):             # сколы на рёбрах: маленькие, почти на поверхности
            n = rng.normal(size=3)
            n[1] = abs(n[1])
            n /= np.linalg.norm(n)
            o = rng.uniform(0.7, 0.85) * np.sqrt(((n * abc) ** 2).sum())
            planes.append((n, o, 2))
    c0 = np.zeros(3)
    if half is not None:
        hn, hs = half
        planes.append((hn, 0.0, 3))
        c0 = -hn * 0.3 * min(abc)
    kr = 0.09 if kind == "chipped" else 0.5
    r, w = polytope_radius(D, c0, abc, planes, kr)
    P = c0 + D * r[:, None]
    face_w = sum(w[:, i + 1] for i, p in enumerate(planes) if p[2] in (1, 3))
    chip_w = sum(w[:, i + 1] for i, p in enumerate(planes) if p[2] == 2) if planes else np.zeros(len(D))
    skin_w = w[:, 0]
    # корка: бугристая; грани раскола: раковистая рябь вокруг точки удара
    seed = int(rng.integers(1 << 20))
    sk = 0.07 * (vnoise(P * 0.55, seed) - 0.5) + 0.04 * (vnoise(P * 1.6, seed + 1) - 0.5) + 0.015 * (vnoise(P * 4.0, seed + 2) - 0.5)
    rip = np.zeros(len(D))
    for i, (n, o, kd) in enumerate(planes):
        if kd == 3:
            continue
        imp = n * o + rng.normal(size=3) * 0.5 * size
        dd = np.linalg.norm(P - imp, axis=1)
        lam = rng.uniform(0.9, 1.3)
        rip += w[:, i + 1] * np.sin(dd / lam * 2 * np.pi) * np.exp(-dd / (2.5 * size))
    disp = sk * (skin_w + 0.25) + 0.035 * rip
    cav = np.zeros(len(D))
    if crack:                                            # трещина от жара через тело
        m = rng.normal(size=3)
        m[1] *= 0.3
        m /= np.linalg.norm(m)
        dpl = P @ m + 0.25 * (vnoise(P * 0.4, seed + 5) - 0.5) * size * 0.3
        gr = np.clip(1 - np.abs(dpl) / 0.22, 0, 1)
        disp -= 0.35 * gr
        cav = gr
    Nr = P - c0
    Nr /= np.linalg.norm(Nr, axis=1, keepdims=True)
    P = P + Nr * disp[:, None]
    P[:, 1] -= P[:, 1].min()
    return P, F, dict(rip=np.clip(0.5 + 2 * rip, 0, 1), cav=cav, chip=np.clip(chip_w * 1.2, 0, 1),
                      face=np.clip(face_w, 0, 1))


def coal_mesh(rng, size):
    """Кусок древесного угля: брусок с гранями по волокну и «крокодиловой» трещиноватостью (щели — жар)."""
    D, F = ico(4)
    abc = (size * rng.uniform(1.0, 1.5), size * rng.uniform(0.6, 0.8), size * rng.uniform(0.7, 1.0))
    planes = []
    for ax in range(3):                                  # почти брусок: 6 граней
        for sg in (-1, 1):
            n = np.zeros(3)
            n[ax] = sg
            n += rng.normal(size=3) * 0.15
            n /= np.linalg.norm(n)
            planes.append((n, abc[ax] * rng.uniform(0.7, 0.85), 1))
    r, w = polytope_radius(D, np.zeros(3), abc, planes, 0.18)
    P = D * r[:, None]
    seed = int(rng.integers(1 << 20))
    # трещиноватость: 3D-ячейки ~1 см по поверхности
    cell = rng.uniform(0.8, 1.1)
    f1, f2, _ = voronoi(P[:, 0] + 0.6 * P[:, 1], P[:, 2] - 0.4 * P[:, 1], cell, seed % 9973)
    crk = sstep(0.14, 0.03, f2 - f1)
    lines = sstep(0.07, 0.0, np.abs(np.sin(P[:, 1] / 0.55 * np.pi + 2 * vnoise(P * 0.5, seed))) - 0.93) * 0.0
    disp = -0.14 * crk + 0.03 * (vnoise(P * 1.2, seed + 1) - 0.5)
    P = P + D * disp[:, None]
    P[:, 1] -= P[:, 1].min()
    return P, F, dict(rip=lines, cav=crk, ember=crk)


def log_mesh(rng, R, L, nu=None, nv=72):
    """Обугленное полено: цилиндр (ось x), «крокодиловая кожа» клетками 1.5-2.5 см, торцы — кольца и излом.
    Возвращает V, F (треугольники), маски."""
    nu = nu or int(L / 0.15)
    u = np.linspace(-L / 2, L / 2, nu)
    ph = np.linspace(0, 2 * np.pi, nv, endpoint=False)
    U, PH = np.meshgrid(u, ph, indexing="ij")
    seed = int(rng.integers(1 << 20))
    cell = rng.uniform(1.5, 2.2)
    f1, f2, cid = voronoi(U * 1.0, PH * R * 1.15, cell, seed % 9973)
    crk = sstep(0.22, 0.05, f2 - f1)
    dome = np.sqrt(np.clip(1 - (f1 / (cell * 0.75)) ** 2, 0, 1))
    Rr = R * (1 + 0.06 * (vnoise(np.stack([U * 0.2, np.cos(PH), np.sin(PH)], -1), seed) - 0.5)) \
        + 0.12 * dome - 0.32 * crk
    Y = Rr * np.sin(PH)
    Zc = Rr * np.cos(PH)
    # концы: обломаны неровно (сжать к оси)
    endw = np.minimum(U + L / 2, L / 2 - U)
    shrink = sstep(0.0, 1.2, endw + 0.6 * (vnoise(np.stack([PH, U * 0.0 + 1.0, U * 0.0], -1) * np.array([1.5, 1, 1]), seed + 3) - 0.5))
    Y, Zc = Y * (0.55 + 0.45 * shrink), Zc * (0.55 + 0.45 * shrink)
    V = np.stack([U, Y, Zc], -1).reshape(-1, 3)
    ii = np.arange(nu * nv).reshape(nu, nv)
    q = np.stack([ii[:-1], np.roll(ii[:-1], -1, 1), np.roll(ii[1:], -1, 1), ii[1:]], -1).reshape(-1, 4)
    Fq = np.concatenate([q[:, [0, 1, 2]], q[:, [0, 2, 3]]])
    # торцы: веер к центру (кольца — в маске)
    caps = []
    Vl = [V]
    n0 = len(V)
    for end, row in ((0, ii[0]), (1, ii[-1])):
        cidx = n0 + end
        Vl.append(np.array([[(-L / 2 if end == 0 else L / 2) * 0.97, 0.0, 0.0]]))
        for j in range(nv):
            a, b_ = row[j], row[(j + 1) % nv]
            caps.append((cidx, b_, a) if end == 0 else (cidx, a, b_))
    V = np.concatenate(Vl)
    F = np.concatenate([Fq, np.array(caps)])
    ember = np.concatenate([crk.ravel(), [0, 0]])
    cavm = np.concatenate([crk.ravel(), [0, 0]])
    V[:, 1] += R
    return V, F, dict(rip=np.concatenate([dome.ravel(), [0, 0]]), cav=cavm, ember=ember)


def place(V, R, pos):
    return V @ R.T + np.asarray(pos)


# ------------------------------------------------------------------ раскладка
def layout(rng=None):
    """Куски на противне: поленья, крупные/средние/мелкие камни, угли, второй слой. (тип, x, z, r, слой, параметры)."""
    rng = rng or np.random.default_rng(SEED + 1)
    x0, x1, z0, z1 = TRAY[0] + 2.0, TRAY[1] - 2.0, TRAY[2] + 2.0, TRAY[3] - 2.0
    occ = []                                             # (x, z, r)

    def free(x, z, r, k=0.86):
        if np.hypot(x - LEAF["c"][0], z - LEAF["c"][1]) < LEAF["r"] + r * 0.5:
            return False
        su, sv = scoop_local(np.array(x), np.array(z))
        if abs(su) < SCOOP["L"] / 2 + r * 0.6 + 0.5 and abs(sv) < SCOOP["W"] / 2 + r * 0.6 + 0.5:
            return False
        if su < -SCOOP["L"] / 2 and abs(sv) < 2.0 + r and su > -SCOOP["L"] / 2 - 15:     # ручка
            return False
        return all(np.hypot(x - a, z - b) > (r + c) * k for a, b, c in occ)

    out = []
    for _ in range(3):                                    # обугленные поленья
        R, L = rng.uniform(2.3, 3.0), rng.uniform(7.5, 10.0)
        for _ in range(3000):
            x, z, yaw = rng.uniform(x0 + 6, x1 - 6), rng.uniform(z0 + 6, z1 - 6), rng.uniform(0, np.pi)
            pts = [(x + t * np.cos(yaw), z + t * np.sin(yaw)) for t in np.linspace(-L / 2 + R, L / 2 - R, 3)]
            if all(free(px, pz, R) for px, pz in pts):
                occ += [(px, pz, R) for px, pz in pts]
                out.append(("log", x, z, R, 0, dict(L=L, yaw=yaw)))
                break
    sizes = ([("stone", rng.uniform(4.6, 5.8)) for _ in range(10)] + [("stone", rng.uniform(3.0, 4.2)) for _ in range(48)]
             + [("coal", rng.uniform(1.0, 2.0)) for _ in range(30)] + [("stone", rng.uniform(1.9, 2.6)) for _ in range(70)])
    for kind, r in sizes:
        for _ in range(3000):
            x, z = rng.uniform(x0 + r * 0.6, x1 - r * 0.6), rng.uniform(z0 + r * 0.6, z1 - r * 0.6)
            if free(x, z, r, 0.74 if kind == "stone" else 0.9):
                occ.append((x, z, r))
                out.append((kind, x, z, r, 0, {}))
                break
    for _ in range(26):                                   # второй слой над швами
        r = rng.uniform(2.6, 4.4)
        for _ in range(500):
            x, z = rng.uniform(x0 + 7, x1 - 7), rng.uniform(z0 + 7, z1 - 7)
            su, sv = scoop_local(np.array(x), np.array(z))
            if abs(su) < SCOOP["L"] / 2 + r + 2 and abs(sv) < SCOOP["W"] / 2 + r + 2:
                continue
            if np.hypot(x - LEAF["c"][0], z - LEAF["c"][1]) < LEAF["r"] + r:
                continue
            if all(np.hypot(x - a, z - b) > (r + c) * 0.9 for (k, a, b, c, ly, _) in out if ly == 1):
                out.append(("stone", x, z, r, 1, {}))
                break
    return out


def heap_lift(x, z):
    """Куча выше к середине: камни лежат друг на друге."""
    cx, cz = (TRAY[0] + TRAY[1]) / 2 + 2.0, (TRAY[2] + TRAY[3]) / 2 - 3.0
    q = np.hypot((x - cx) / 30.0, (z - cz) / 40.0)
    return 2.2 * np.clip(1 - q ** 2, 0, 1)


# ------------------------------------------------------------------ совок
def scoop_field(su, sv, ground):
    """Ковш совка поверх поля: su — вдоль (передняя кромка +L/2, задняя стенка -L/2), sv — поперёк.
    ground — высота слоя под ним. Возвращает (h, маски) или NaN вне ковша."""
    L, W = SCOOP["L"], SCOOP["W"]
    du = su + L / 2                                      # от задней стенки
    wv = W / 2 * (0.68 + 0.32 * np.clip(du / L, 0, 1))  # v2.1: трапеция — у задней стенки уже (сверху был «рамкой»)
    dv = wv - np.abs(sv)
    fr = L / 2 - su
    inside = (du > -0.35) & (dv > -0.35) & (fr > -0.2)
    tilt = 0.06 * (L / 2 - su)                           # задняя часть приподнята: ручка лежит на борту
    yb = ground + 0.35 + tilt
    Wh = 0.7 + 2.5 * np.clip((L / 2 - su) / L, 0, 1) ** 1.2   # борта: у задней стенки 3.2, к кромке сходят
    edge = np.minimum(np.minimum(du, dv), 99)
    wall = np.where(edge < 0.5, Wh * sstep(0.5, 0.15, edge), 0.0)
    back = np.where(du < 0.5, (3.2 + tilt * 0) * sstep(0.5, 0.15, du), 0.0)
    bead = np.where((edge < 0.25) & (edge > -0.35), 0.18 * np.sqrt(np.clip(1 - ((edge + 0.05) / 0.3) ** 2, 0, 1)), 0)
    H = yb + 0.15 + np.maximum(wall, back) + bead
    out_drop = sstep(0.0, -0.35, np.minimum(edge, fr))
    H = H - out_drop * 4.0
    lip = sstep(1.2, 0.0, fr) * 0.12                     # передняя кромка тоньше, чуть загнута
    H = H + lip
    # пепел и два уголька в ковше (задняя половина)
    ashh = np.clip(0.7 * sstep(1.0, -6.0, su) * sstep(0.4, 1.6, np.minimum(du, dv))
                   * sstep(0.35, 0.65, fbm2(su * 0.35, sv * 0.35, 71, 3)), 0, 1)       # пепел пятнами у задней стенки
    coal = np.zeros_like(su)
    ang = np.arctan2(sv, su)
    for j, (cu, cv, cr) in enumerate(((-4.8, 2.2, 1.6), (-2.2, -2.9, 1.2), (-5.6, -1.2, 0.9), (-1.0, 0.8, 0.8), (-3.6, 4.0, 0.7))):
        a = np.arctan2(sv - cv, su - cu)
        rr = cr * (0.75 + 0.35 * np.sin(3 * a + j) + 0.15 * np.sin(5 * a + 2 * j))   # угловатые комья, не диски
        dd = np.hypot(su - cu, sv - cv)
        lump = np.clip(1 - (dd / rr) ** 2, 0, 1) ** 0.6
        k1, k2, _ = voronoi(su * 1.0, sv * 1.0, 0.7, 77 + j)
        coal = np.maximum(coal, lump * (1 - 0.35 * sstep(0.12, 0.02, k2 - k1)))
    _ = ang
    inner = (du > 0.5) & (dv > 0.5)
    H = np.where(inner, np.maximum(H, yb + 0.15 + 0.6 * ashh + 1.1 * coal * (coal > 0.05)), H)
    # накладка ручки на дне у задней стенки с двумя заклёпками
    plate = (du > 0.5) & (du < 3.0) & (np.abs(sv) < 1.2)
    H = np.where(plate & inner & (ashh < 0.3), np.maximum(H, yb + 0.27), H)
    riv = np.zeros_like(su)
    for (ru, rv) in ((1.1, 0.0), (2.4, 0.0)):
        dd = np.hypot(du - ru, sv - rv)
        rv_ = np.sqrt(np.clip(1 - (dd / 0.38) ** 2, 0, 1))
        H = np.where(plate & inner & (dd < 0.38) & (ashh < 0.3), np.maximum(H, yb + 0.27 + 0.15 * rv_), H)
        riv = np.maximum(riv, (dd < 0.4) * plate * 1.0)
    mat = np.where(inner & (coal > 0.05), MAT["coal"], np.where(inner & (ashh > 0.12), MAT["ash"], MAT["scoop"]))
    return np.where(inside, H, np.nan), dict(mat=mat, coal=coal, ash=ashh * inner, rivet=riv, edge=sstep(0.6, 0.0, np.abs(edge)))


def leaf(L, rng, nu=44, nv=17, curl=(0.04, 0.08)):
    """Берёзовый лист (как bed/bake_v2.leaf), сухой и скрученный: x вдоль жилки, y поперёк, h подъём, жилки."""
    U, Vv = np.meshgrid(np.linspace(-0.18, 1, nu), np.linspace(-1, 1, nv), indexing="ij")
    Up = np.clip(U, 0, 1)
    W = 0.36 * L * (Up ** 0.5) * (1 - Up) ** 1.1 / (0.45 ** 0.5 * 0.55 ** 1.1) * 0.95
    W = np.where(U < 0.02, 0.09, np.maximum(W, 0.09 * (U < 0.08)))           # черешок 1.4 см
    W = W * (1 + 0.05 * np.sin(U * 26 + rng.uniform(0, 6)))
    x, y = U * L, Vv * W
    vein = np.exp(-(np.abs(y) / 0.1) ** 2) * (U < 0.97)
    U = Up
    for k in range(1, 8):
        u0 = 0.1 + 0.11 * k
        along = x - (u0 * L + np.abs(y) * 0.95)
        vein = np.maximum(vein, 0.75 * np.exp(-(along / 0.085) ** 2) * (np.abs(y) < W * 0.9) * (u0 < 0.95))
    c = rng.uniform(*curl) * L
    h = 0.07 * vein + c * np.abs(Vv) ** 2.0 + 0.5 * np.sin(U * np.pi) * rng.uniform(0.2, 0.8)
    h = h + 0.05 * np.sin(Vv * 9 + U * 5) * np.abs(Vv)
    burn = sstep(0.7, 1.0, U + 0.15 * (vnoise(np.stack([U * 4, Vv * 3], -1), 7) - 0.5))
    return x, y, h, vein, burn
