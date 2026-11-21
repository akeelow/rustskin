"""Sauna Stove v3: рельеф плоских поверхностей как поля высот на numpy (bake_v3.py в Blender и превью в .venv).

Всё, что даёт форму, считается здесь функциями, и те же функции пишут маски цвета — рельеф и цвет совпадают пиксель в
пиксель (PLAN_v3.md §2). Сантиметры. Размеры деталей — под 5.5 px/см экспорта (1 px = 1.8 мм), §1 плана.

Маски (атрибуты вершин high-poly, запекаются Emit-проходами):
  m1 = (гребень волокна, полость, вмятина)   m2 = (гвоздь, сучок, обугливание)
  m3 = (ржавчина, накипь/корка, тон доски)    idc = (код материала / 32, номер доски / 32, кора)
"""
import numpy as np

import geom_v3 as G

# коды материалов (texture_v3.py)
MAT = {"slat": 1, "enamel": 2, "batten": 3, "nail": 4, "char": 5, "frame": 6, "bark": 7, "plaque": 8, "glass": 9,
       "iron": 10, "plate_enamel": 11, "plate_iron": 12, "scale": 13, "stone": 14, "wire": 15, "leaf": 16, "rim": 17,
       "rivet": 18, "rope": 19, "weld": 20, "rebar": 21, "soot_iron": 22, "cup": 23}
STEP = 0.1          # шаг сетки, см (запекание 4096 = 0.09 см/px)


# ------------------------------------------------------------------ шум
def vnoise(p, seed=0):
    p = np.asarray(p, np.float64)
    if p.shape[-1] == 2:
        p = np.concatenate([p, np.zeros(p.shape[:-1] + (1,))], -1)
    i = np.floor(p).astype(np.int64)
    f = p - i
    f = f * f * (3 - 2 * f)

    def h(dx, dy, dz):
        x = ((i[..., 0] + dx) * 73856093) ^ ((i[..., 1] + dy) * 19349663) ^ ((i[..., 2] + dz) * 83492791) ^ (seed * 2654435761)
        x = (x ^ (x >> 13)) * 1274126177
        return ((x ^ (x >> 16)) & 0xFFFF).astype(np.float64) / 65535

    out = 0.0
    for dx in (0, 1):
        wx = f[..., 0] if dx else 1 - f[..., 0]
        for dy in (0, 1):
            wy = f[..., 1] if dy else 1 - f[..., 1]
            for dz in (0, 1):
                wz = f[..., 2] if dz else 1 - f[..., 2]
                out = out + h(dx, dy, dz) * wx * wy * wz
    return out


def n2(x, y, seed=0):
    x, y = np.broadcast_arrays(np.asarray(x, np.float64), np.asarray(y, np.float64))
    return vnoise(np.stack([x, y], -1), seed)


def fbm2(x, y, seed=0, octaves=4):
    s, a, t = 0.0, 0.5, 0.0
    for k in range(octaves):
        s = s + a * n2(x * 2 ** k, y * 2 ** k, seed + 7 * k)
        t += a
        a *= 0.5
    return s / t


def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def round_drop(d, r):
    t = np.clip(r - d, 0, None)
    t = np.minimum(t, r)
    return r - np.sqrt(np.maximum(r * r - t * t, 0))


def voronoi(x, y, cell, seed):
    """F1, F2 (расстояния до двух ближайших центров) на сетке ячеек cell."""
    gx, gy = np.floor(x / cell).astype(np.int64), np.floor(y / cell).astype(np.int64)
    f1 = np.full(x.shape, 1e9)
    f2 = np.full(x.shape, 1e9)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            cx, cy = gx + dx, gy + dy
            hsh = (cx * 73856093) ^ (cy * 19349663) ^ (seed * 83492791)
            hsh = (hsh ^ (hsh >> 13)) * 1274126177
            rx = ((hsh & 0xFFFF) / 65535.0)
            ry = (((hsh >> 16) & 0xFFFF) / 65535.0)
            px, py = (cx + 0.15 + 0.7 * rx) * cell, (cy + 0.15 + 0.7 * ry) * cell
            d = np.hypot(x - px, y - py)
            f2 = np.where(d < f1, f1, np.minimum(f2, d))
            f1 = np.minimum(f1, d)
    return f1, f2


def grain_relief(along, across, depth0, tilt, c, s, seed, knots=(), quarter=False):
    """Гребни поздней древесины (0..1) по координатам доски; knots: [(along, across, r)] — волокна огибают."""
    warp = 0.45 * (fbm2(along * 0.025, across * 0.12, seed, 3) - 0.5) + 0.12 * (n2(along * 0.12, across * 0.5, seed + 3) - 0.5)
    if quarter:
        ph = (across - c) / (s * 0.8) + 2.5 * warp
    else:
        d = depth0 + tilt * along + 0.6 * warp
        ph = np.sqrt((across - c) ** 2 + d * d) / s + warp
    for (ka, kc, kr) in knots:
        dd = np.hypot((along - ka) / 1.5, across - kc)
        ph = ph + 1.6 * kr * np.exp(-(dd / (2.4 * kr)) ** 2) / s
    f = ph - np.floor(ph)
    return np.exp(-((f - 0.82) / 0.11) ** 2) + np.exp(-((f + 1 - 0.82) / 0.11) ** 2) + np.exp(-((f - 1.82) / 0.11) ** 2)


def nail_head(H, U, V, base, kind, r=0.55):
    """Кованая шляпка (скруглённый квадрат 11 мм) в локальных U, V. kind: 0 обычный, 1 утоплен с воронкой,
    2 торчит на 2 мм, 3 забит криво (наклон). Возвращает H и маску."""
    q = ((np.abs(U) / r) ** 4 + (np.abs(V) / r) ** 4) ** 0.25
    dome = np.sqrt(np.clip(1 - q ** 2, 0, 1))
    lift = {0: 0.05, 1: -0.05, 2: 0.22, 3: 0.08}[kind]
    hh = base + lift + 0.09 * dome - 0.025 * np.maximum(np.abs(U), np.abs(V)) / r
    if kind == 3:
        hh = hh + 0.09 * U / r
    # грани ковки на шляпке: четыре ската к углам
    hh = hh - 0.02 * (np.abs(U) + np.abs(V)) / r
    dd = np.hypot(U, V)
    H = H - 0.03 * np.clip(1 - ((dd - 0.8) / 0.35) ** 2, 0, 1)        # смятое дерево вокруг
    if kind == 1:
        H = H - 0.1 * np.clip(1 - (dd / 1.15) ** 2, 0, 1) ** 2
    H = np.where(q < 1, np.maximum(H, hh), H)
    return H, sstep(1.02, 0.92, q)


def char_field(X, Y, amount, cell, seed, along_y=True):
    """«Крокодилова кожа» обугленного дерева: блоки — продольные трещины вдоль волокна (шаг ~0.7 cell, волнистые)
    и поперечные со своим шагом в каждой колонке (~1.1 cell); блок — выпуклая подушка с бороздами волокон.
    along_y: волокно вдоль Y. -> dh, полость."""
    if not along_y:
        X, Y = Y, X
    cw = 0.8 * cell
    xa = X + 0.6 * cw * (fbm2(Y * 0.1, X * 0.04, seed, 3) - 0.5) * 2
    col = np.floor(xa / cw)
    fx = xa / cw - col
    dcol = np.minimum(fx, 1 - fx) * cw                       # до продольной трещины
    rh = cell * (0.55 + 1.1 * n2(col * 1.7, 0.5, seed + 1))
    off = n2(col * 3.1, 1.5, seed + 2) * rh
    yb = Y + off + 0.25 * rh * (n2(X * 0.6, Y * 0.15, seed + 3) - 0.5)
    fy = yb / rh - np.floor(yb / rh)
    drow = np.minimum(fy, 1 - fy) * rh                       # до поперечной трещины
    row = np.floor(yb / rh)
    has_col = n2(col * 2.3, row * 1.9, seed + 7) > 0.5           # продольная трещина есть не у каждого блока
    d = np.minimum(np.where(has_col, dcol, 9.0), drow)
    wcr = 0.09 * cell * (0.6 + 0.8 * n2(X * 0.9, Y * 0.9, seed + 4))
    crack = sstep(wcr, wcr * 0.3, d)
    pillow = np.clip(d / (0.35 * cell), 0, 1) ** 0.6
    fib = n2(X * 5.0, Y * 0.6, seed + 5)
    # мелкие вторичные трещинки внутри блоков (сетка вороного в 2.5 раза мельче, неглубокие)
    g1, g2 = voronoi(X, Y, 0.45 * cell, seed + 8)
    fine = sstep(0.05 * cell, 0.01 * cell, g2 - g1) * (n2(X * 0.7, Y * 0.7, seed + 9) > 0.45)
    dh = (-0.14 + 0.05 * pillow - 0.3 * crack - 0.07 * fine + 0.03 * (fib - 0.5)
          + 0.03 * (n2(X * 1.5, Y * 1.5, seed + 6) - 0.5)) * amount
    crack = np.maximum(crack, 0.5 * fine)
    return dh, crack * amount


# ------------------------------------------------------------------ левый бок
class LeftSide:
    """Левый бок (острова 2 — утопленная панель, 16 — рамка, 80 — её передний торец).

    Координаты поля: a = z модели (вперёд +, к дверце), b = y (вверх). Поле W(a, b) = расстояние наружу (−x),
    панель модели на W = 31.12, рамка — 32.5. По истории: колотые осиновые рейки на двух поперечинах, гвозди парами,
    крайняя рейка у дверцы обуглена, на второй от дверцы — банный термометр; снизу концы размочалены, вода и жар.
    """
    PANEL_W, FRAME_W = 31.12, 32.5
    A = (-33.0, 33.0)
    B = (30.4, 110.4)
    SLAT_TOP = 32.38            # верх реек (на 1.2 мм ниже рамки)
    BATTENS = ((38.6, 42.6), (98.8, 102.8))       # поперечины за рейками (видны в щелях), b
    N = 8
    THERMO = 6                  # рейка с термометром (вторая от дверцы)
    CHAR = 7                    # обугленная крайняя рейка у дверцы

    def __init__(self, seed=5):
        rng = np.random.default_rng(seed)
        self.rng = rng
        a0, a1 = -28.9, 28.9
        w = rng.uniform(6.0, 8.0, self.N)
        gaps = rng.uniform(0.35, 0.7, self.N - 1)
        w *= (a1 - a0 - gaps.sum()) / w.sum()
        self.edges = []
        a = a0
        for i in range(self.N):
            self.edges.append((a, a + w[i]))
            a += w[i] + (gaps[i] if i < self.N - 1 else 0)
        self.slats = []
        for i, (lo, hi) in enumerate(self.edges):
            self.slats.append(dict(
                lo=lo, hi=hi,
                b0=36.3 + rng.uniform(-0.3, 2.6),            # нижний конец (разной длины)
                b1=107.0,                                     # верх уходит под рамку
                top=rng.uniform(-0.08, 0.06),
                cup=rng.uniform(0.09, 0.16),                  # коробление желобом, см
                twist=rng.uniform(-0.12, 0.12),
                seed=int(rng.integers(1000)),
                quarter=rng.random() < 0.35,
                gc=(lo + hi) / 2 + rng.uniform(-3, 3),
                d0=rng.uniform(1.0, 3.0),
                tilt=rng.uniform(0.008, 0.02) * rng.choice((-1, 1)),
                s=rng.uniform(0.95, 1.4),
                amp=rng.uniform(0.07, 0.1),
                tone=rng.random(),
                ew=[(rng.uniform(0.15, 0.3), int(rng.integers(1000))) for _ in range(2)],   # волнистость кромок
            ))
        self._features(rng)

    def _features(self, rng):
        S = self.slats
        mid = lambda i: (S[i]["lo"] + S[i]["hi"]) / 2
        # гвозди парами в поперечины; (a, b, kind)
        nails = []
        for i in range(self.N):
            w = S[i]["hi"] - S[i]["lo"]
            for bc in (40.6, 100.8):
                for k, da in enumerate((-0.24 * w, 0.24 * w)):
                    kind = 0
                    r = rng.random()
                    if r < 0.15:
                        kind = 1
                    elif r < 0.25:
                        kind = 3
                    nails.append((mid(i) + da + rng.uniform(-0.3, 0.3), bc + rng.uniform(-0.6, 0.6), kind))
        nails[5] = (nails[5][0], nails[5][1], 2)                   # один торчит
        self.bent = (mid(3) + 0.25 * (S[3]["hi"] - S[3]["lo"]), 40.4)   # загнутый (вместо второго гвоздя рейки 3)
        nails = [n for n in nails if not (abs(n[0] - self.bent[0]) < 1.0 and abs(n[1] - self.bent[1]) < 1.5)]
        # термометр: 2 гвоздика
        self.thermo = (mid(self.THERMO), 59.0, 87.0, 3.3)          # a, b0, b1, полуширина
        ta, tb0, tb1, tw = self.thermo
        self.thermo_nails = [(ta, tb0 + 2.2), (ta, tb1 - 2.4)]
        self.nails = nails
        self.smiles = [(a, b, rng.uniform(0, 2 * np.pi)) for (a, b, k) in nails if rng.random() < 0.3]
        # сучки
        knots = []
        while len(knots) < 6:
            a, b = rng.uniform(-27, 20), rng.uniform(45, 98)
            i = self.slat_at(a)
            if i is None or i == self.CHAR or (i == self.THERMO and 57 < b < 89):
                continue
            if abs(b - 40.6) < 4 or abs(b - 100.8) < 4:
                continue
            if any(np.hypot(a - p, b - q) < 12 for p, q, *_ in knots):
                continue
            lo, hi = S[i]["lo"], S[i]["hi"]
            a = np.clip(a, lo + 1.6, hi - 1.6)
            knots.append((a, b, rng.uniform(0.5, 1.2), False))
        knots[2] = (knots[2][0], knots[2][1], 0.8, True)          # выпавший сучок — дыра
        self.knots = knots
        # трещины: (i, b0, b1, a, глубина, полуширина, seed): торцевые от верха и низа, продольные усушки
        cracks = []
        for i in range(self.N):
            if i == self.CHAR:
                continue
            lo, hi, b0 = S[i]["lo"], S[i]["hi"], S[i]["b0"]
            for _ in range(int(rng.integers(1, 3))):                 # от нижнего торца
                L = rng.uniform(3, 12)
                cracks.append((i, b0 - 0.5, b0 + L, rng.uniform(lo + 1.0, hi - 1.0), 0.35, 0.2, int(rng.integers(1000))))
            for _ in range(int(rng.integers(1, 3))):                 # продольные — больше в верхней трети (жар)
                b = rng.uniform(55, 100) if rng.random() < 0.7 else rng.uniform(44, 60)
                L = rng.uniform(6, 24)
                cracks.append((i, b, min(b + L, 106), rng.uniform(lo + 0.9, hi - 0.9), 0.25, 0.16, int(rng.integers(1000))))
        self.cracks = cracks
        # вмятины от ковша и полена: гнездом в передней половине на 50-80 см
        dents = []
        for _ in range(5):
            r = rng.pareto(2.0) * 0.6 + 0.9
            dents.append((rng.uniform(-5, 22), rng.uniform(55, 82), min(r, 2.2), 0.04 + 0.03 * min(r, 2.2)))
        for _ in range(4):
            dents.append((rng.uniform(-27, 27), rng.uniform(45, 100), rng.uniform(0.6, 1.2), 0.04))
        self.dents = dents
        # забоины на кромках реек
        nicks = []
        for _ in range(40):
            i = int(rng.integers(self.N))
            side = int(rng.integers(2))
            b = rng.uniform(S[i]["b0"] + 1, 105)
            nicks.append((i, side, b, rng.uniform(0.4, 1.0), rng.uniform(0.08, 0.18)))
        self.nicks = nicks
        # ржавчина на эмали в щелях: гнёзда раковин и пузырей (a, b, r, тип)
        rust = []
        for _ in range(140):
            cl = rng.random()
            a, b = rng.uniform(-29, 29), rng.uniform(34, 107) if cl < 0.6 else rng.uniform(34, 50)
            rust.append((a, b, rng.uniform(0.12, 0.35), int(rng.integers(2))))
        self.rust = rust

    def slat_at(self, a):
        for i, s in enumerate(self.slats):
            if s["lo"] - 0.3 <= a <= s["hi"] + 0.3:
                return i
        return None

    # -------------------------------------------------------------- поле
    def grid(self, step=STEP):
        a = np.arange(self.A[0], self.A[1] + 1e-6, step)
        b = np.arange(self.B[0], self.B[1] + 1e-6, step)
        return np.meshgrid(a, b)

    def field(self, A, B):
        base = G.raster_height(G.tris(islands=[2, 16]), A, B, 2, 1, 0, sign=-1, fill=self.FRAME_W)
        frame = base > (self.PANEL_W + self.FRAME_W) / 2
        S = self.slats
        W = np.full(A.shape, self.PANEL_W)
        z = np.zeros(A.shape)
        grain, cav, dent, nail, knot, char, rust, crust, tone = (z.copy() for _ in range(9))
        mat = np.full(A.shape, MAT["enamel"], float)
        sid = np.full(A.shape, -1.0)
        barkm = z.copy()

        # ---- эмаль под рейками: раковины и вздутия ржавчины
        en = self.PANEL_W + 0.01 * (n2(A * 0.3, B * 0.3, 3) - 0.5)
        for (a, b, r, kind) in self.rust:
            box = (np.abs(A - a) < r + 0.1) & (np.abs(B - b) < r + 0.1)
            if not box.any():
                continue
            d = np.hypot(A[box] - a, B[box] - b)
            u = np.clip(1 - (d / r) ** 2, 0, 1)
            en[box] += (-0.05 if kind == 0 else 0.04) * u
            rust[box] = np.maximum(rust[box], sstep(0, 0.4, u))
        rust = np.maximum(rust, 0.35 * sstep(0.55, 0.75, fbm2(A * 0.12, B * 0.12, 17, 3)))
        W = en

        # ---- поперечины за рейками (видны в щелях)
        for (b0, b1) in self.BATTENS:
            m = (B > b0) & (B < b1)
            hb = 31.75 - round_drop(np.minimum(B - b0, b1 - B), 0.3) + 0.02 * (n2(A * 0.2, B * 1.5, 9) - 0.5)
            W = np.where(m, np.maximum(W, hb), W)
            mat = np.where(m, MAT["batten"], mat)

        # ---- рейки
        for i, s in enumerate(S):
            wob_lo = s["ew"][0][0] * (fbm2(B * 0.035, s["ew"][0][1], 2) - 0.5) * 2 + 0.06 * (n2(B * 0.25, i, s["ew"][0][1]) - 0.5)
            wob_hi = s["ew"][1][0] * (fbm2(B * 0.035, s["ew"][1][1], 2) - 0.5) * 2 + 0.06 * (n2(B * 0.25, i + 9, s["ew"][1][1]) - 0.5)
            lo, hi = s["lo"] + wob_lo, s["hi"] + wob_hi
            # нижний торец: рваный, размочаленный (зубцы волокон)
            rag = 0.7 * (fbm2(A * 0.7, i * 3.1, s["seed"], 3) - 0.5) + 0.5 * np.clip(n2(A * 2.2, i * 7.7, s["seed"] + 4) - 0.55, 0, 1)
            b0 = s["b0"] + rag
            if i == self.CHAR:
                b0 = b0 - 0.4 * (n2(A * 0.6, 1.0, 7) - 0.5)
            inside = (A > lo) & (A < hi) & (B > b0) & (B < s["b1"])
            if not inside.any():
                continue
            dside = np.minimum(A - lo, hi - A)
            dend = B - b0
            u = (A - (lo + hi) / 2) / np.maximum((hi - lo) / 2, 0.5)
            hgt = self.SLAT_TOP + s["top"] + s["cup"] * (np.clip(u, -1, 1) ** 2 - 0.4) + s["twist"] * u * (B - 70) / 40
            hgt += 0.05 * (n2(B * 0.05, A * 0.3 + i * 11, 31) - 0.5)
            # ручные неровные фаски: радиус гуляет по длине
            rs = 0.28 + 0.12 * n2(B * 0.2, i * 5.0, 41)
            hgt -= np.maximum(round_drop(dside, rs), round_drop(dend, 0.35))
            # волокна (у торца — размочалены: гребни выше и с разрывами)
            kn = [(kb, ka, kr) for (ka, kb, kr, f) in self.knots if s["lo"] - 1 < ka < s["hi"] + 1]
            gr = grain_relief(B, A, s["d0"], s["tilt"], s["gc"], s["s"], s["seed"], kn, s["quarter"])
            wear = 1.0 + 0.6 * sstep(b0 + 8, b0 + 1, B) + 0.3 * sstep(85, 105, B)
            hgt += s["amp"] * wear * (gr - 0.35)
            fray = sstep(b0 + 3.5, b0 + 0.3, B)
            hgt -= fray * 0.1 * sstep(0.5, 0.65, n2(A * 3.0, B * 0.5, s["seed"] + 2))
            W = np.where(inside, hgt, W)
            grain = np.where(inside, gr, grain)
            streak = fbm2(A * 1.1 + i * 17.0, B * 0.025, s["seed"] + 21, 3)
            tone = np.where(inside, np.clip(0.45 * s["tone"] + 0.75 * (streak - 0.5) + 0.3, 0, 1), tone)
            sid = np.where(inside, i, sid)
            mat = np.where(inside, MAT["slat"], mat)

        inside = sid >= 0
        idx = sid.astype(int)

        # ---- сучки
        for (ka, kb, kr, fallen) in self.knots:
            d = np.hypot((B - kb) / 1.35, A - ka)
            core = sstep(kr, kr * 0.8, d)
            ring = np.exp(-((d - kr) / 0.12) ** 2)
            if fallen:
                hole = sstep(kr * 0.95, kr * 0.72, d)
                W = np.where(inside, W - 0.95 * hole, W)
                cav = np.maximum(cav, hole * inside)
                # край дыры: сломанные волокна
                W = W - inside * 0.06 * np.exp(-((d - kr * 1.05) / 0.15) ** 2)
            else:
                W = W + inside * (0.06 * core - 0.05 * ring)
                ang = np.arctan2(B - kb, A - ka)
                for a0 in (0.4 + ka, 2.5 + kb, 4.3 + ka * 0.3):
                    da = np.abs(np.angle(np.exp(1j * (ang - a0))))
                    tt = d * da
                    rad = (tt < 0.15) & (d < kr * 0.85)
                    W = W - inside * np.where(rad, 0.12 * (1 - tt / 0.15), 0)
            knot = np.maximum(knot, core * inside)

        # ---- трещины вдоль волокон (клин с мягкими концами, извилистые)
        for (i, ba, bb, ac, dep, hw, sd) in self.cracks:
            box = (B > ba - 1) & (B < bb + 1) & (np.abs(A - ac) < 1.5) & (idx == i)
            if not box.any():
                continue
            bs, as_ = B[box], A[box]
            t = np.clip((bs - ba) / (bb - ba), 0, 1)
            yc = ac + 0.3 * (n2(bs * 0.15, sd * 1.0, sd) - 0.5) + 0.08 * (n2(bs * 0.9, sd * 2.0, sd + 1) - 0.5)
            prof = (1 - t) ** 0.6 if ba < self.slats[i]["b0"] + 0.5 else np.sin(np.pi * t) ** 0.6
            w = hw * prof + 1e-3
            v = np.clip(1 - np.abs(as_ - yc) / w, 0, 1)
            W[box] -= dep * prof * v ** 0.8
            cav[box] = np.maximum(cav[box], v * prof)

        # ---- вмятины
        for (a, b, r, d) in self.dents:
            dd = np.hypot(A - a, B - b)
            u = np.clip(1 - (dd / r) ** 2, 0, 1) ** 2
            W = W - d * u * inside
            dent = np.maximum(dent, u * inside)
        # ---- забоины кромок
        for (i, side, b, r, d) in self.nicks:
            a = self.slats[i]["hi"] if side else self.slats[i]["lo"]
            box = (np.abs(A - a) < r + 0.3) & (np.abs(B - b) < r * 1.6 + 0.3) & (idx == i)
            if not box.any():
                continue
            dd = np.hypot(A[box] - a, (B[box] - b) / 1.5)
            u = np.clip(1 - (dd / r) ** 2, 0, 1)
            W[box] -= d * u * (0.7 + 0.6 * n2(A[box] * 3, B[box] * 3, 17))
            dent[box] = np.maximum(dent[box], u)

        # ---- обугленная рейка у дверцы (вся) и пятно снизу на соседней
        amt = (idx == self.CHAR) * (0.75 + 0.25 * sstep(40, 70, B))
        amt = amt + (idx == self.CHAR - 1) * sstep(0.55, 0.7, fbm2(A * 0.15, B * 0.05, 61, 3) + 0.25 * sstep(60, 40, B)) * 0.9
        amt = amt + (idx == self.CHAR - 1) * sstep(self.slats[self.CHAR - 1]["hi"] - 1.6, self.slats[self.CHAR - 1]["hi"], A) * 0.7
        amt = np.clip(amt, 0, 1)
        if (amt > 0).any():
            m = amt > 0
            dh, cr = char_field(A[m], B[m], amt[m], 1.8, 303)
            W[m] = W[m] * (1 - 0.15 * amt[m]) + 0.15 * amt[m] * (self.SLAT_TOP - 0.05) + dh
            cav[m] = np.maximum(cav[m], cr)
            char = np.maximum(char, amt)

        # ---- гвозди, «улыбки», загнутый гвоздь
        for (a, b, kind) in self.nails:
            box = (np.abs(A - a) < 1.6) & (np.abs(B - b) < 1.6)
            if not box.any():
                continue
            ang = (a * 7.3 + b * 3.1) % 1.57
            ca, sa = np.cos(ang), np.sin(ang)
            u, v = (A[box] - a) * ca + (B[box] - b) * sa, -(A[box] - a) * sa + (B[box] - b) * ca
            Wn, nm = nail_head(W[box], u, v, self.SLAT_TOP, kind)
            W[box] = np.where(inside[box], Wn, W[box])
            nail[box] = np.maximum(nail[box], nm * inside[box])
        for (a, b, ang) in self.smiles:
            cx, cy = a + 1.0 * np.cos(ang), b + 1.0 * np.sin(ang)
            dd = np.hypot(A - cx, B - cy)
            th = np.arctan2(B - cy, A - cx)
            win = np.clip(np.cos(th - ang) * 1.6 - 0.2, 0, 1)
            sm = np.exp(-((dd - 1.15) / 0.14) ** 2) * win * inside
            W = W - 0.05 * sm
            dent = np.maximum(dent, sm)
        ba, bb = self.bent
        u, v = B - bb, A - (ba - 0.2)
        dd = np.hypot(u, v)
        head = sstep(0.55, 0.45, dd)
        shank = np.clip(1 - (np.abs(v) / 0.2) ** 2, 0, 1) ** 0.5 * (u > 0) * (u < 3.0)
        W = np.maximum(W, np.where(dd < 0.55, self.SLAT_TOP + 0.08 + 0.2 * head, -1e9))
        W = np.maximum(W, np.where(shank > 0, self.SLAT_TOP + 0.04 + 0.18 * shank + 0.04 * u / 3, -1e9))
        nail = np.maximum(nail, np.maximum(head, (shank > 0.05) * 1.0))

        # ---- термометр: планка 6.6 × 28 × 1.2 см, паз с трубкой, риски 3 мм (без цифр), 2 гвоздика
        ta, tb0, tb1, tw = self.thermo
        ua, vb = A - ta, B - tb0
        L = tb1 - tb0
        top_round = np.where(vb > L - tw, np.hypot(ua, vb - (L - tw)) - tw, np.abs(ua) - tw)
        dpl = np.minimum(-top_round, vb)            # расстояние до края планки
        pl = dpl > 0
        hp = self.SLAT_TOP + 0.06 + 1.2 - round_drop(dpl, 0.35)
        hp += 0.03 * (grain_relief(B, A, 2.0, 0.01, ta + 1.0, 0.7, 55) - 0.35)
        # паз под трубку и трубка
        gx = np.abs(ua + 0.9)
        groove = (gx < 0.45) & (vb > 2.5) & (vb < L - 3.5)
        hp = np.where(groove, hp - 0.3 * np.clip(1 - (gx / 0.45) ** 4, 0, 1), hp)
        tube = (gx < 0.28) & (vb > 2.8) & (vb < L - 3.8)
        bulb = np.hypot(ua + 0.9, vb - 3.2)
        tub_h = self.SLAT_TOP + 0.06 + 1.2 - 0.3 + 0.32 * np.sqrt(np.clip(1 - (gx / 0.28) ** 2, 0, 1))
        bul_h = self.SLAT_TOP + 0.06 + 1.2 - 0.3 + 0.45 * np.sqrt(np.clip(1 - (bulb / 0.55) ** 2, 0, 1))
        glass = tube | (bulb < 0.55)
        hp = np.where(tube, np.maximum(hp, tub_h), hp)
        hp = np.where(bulb < 0.55, np.maximum(hp, bul_h), hp)
        # риски шкалы справа от паза: шаг 0.75 см, ширина 0.28, длина 1.1 / 2.0 (каждая 4-я)
        k = np.round((vb - 6.0) / 0.75)
        tick_c = 6.0 + k * 0.75
        long_t = (k % 4 == 0)
        tl = np.where(long_t, 2.0, 1.1)
        tick = (np.abs(vb - tick_c) < 0.14) & (ua > -0.2) & (ua < -0.2 + tl) & (k >= 0) & (vb < L - 5)
        hp = np.where(tick, hp - 0.1, hp)
        W = np.where(pl, np.maximum(W, hp), W)
        cav = np.where(pl, np.maximum(cav * 0, tick * 0.6 + groove * 0.3), cav)
        mat = np.where(pl, MAT["plaque"], mat)
        mat = np.where(pl & glass, MAT["glass"], mat)
        for (a, b) in self.thermo_nails:
            box = (np.abs(A - a) < 1.0) & (np.abs(B - b) < 1.0)
            Wn, nm = nail_head(W[box], A[box] - a, B[box] - b, self.SLAT_TOP + 1.26, 0, r=0.4)
            W[box] = Wn
            nail[box] = np.maximum(nail[box], nm)

        # ---- рамка: горбыль; на верхнем бруске и переднем — кора (обзол)
        if frame.any():
            Wf, fm = self.frame_field(A, B, frame)
            W = np.where(frame, Wf["h"], W)
            for k_, arr in (("grain", grain), ("cav", cav), ("nail", nail), ("char", char), ("tone", tone)):
                arr[frame] = Wf[k_][frame]
            barkm = np.where(frame, Wf["bark"], barkm)
            mat = np.where(frame, fm, mat)
            sid = np.where(frame, 9 + Wf["bar"], sid)

        mat = np.where(inside & (char > 0.5) & (mat == MAT["slat"]), MAT["char"], mat)
        mat = np.where((nail > 0.5), MAT["nail"], mat)
        cav = np.where(inside | frame | (mat == MAT["plaque"]) | (mat == MAT["glass"]), cav, np.maximum(cav, 0.6))
        return dict(h=W, grain=grain, cav=cav, dent=dent, nail=nail, knot=knot, char=char, rust=rust, crust=crust,
                    tone=tone, mat=mat, sid=sid, bark=barkm)

    def frame_field(self, A, B, frame):
        """Обвязка 16: верхний и нижний брусья во всю ширину, передний и задний — между ними. Горбыль: на верхнем
        и переднем — полоса коры (обзол); стыки, торцы с кольцами у краёв, гвозди."""
        F = self.FRAME_W
        z = np.zeros(A.shape)
        # какой брус: 0 верх, 1 низ, 2 перед (+a), 3 зад
        top, bot = B > 105.6, B < 35.8
        bar = np.where(top, 0, np.where(bot, 1, np.where(A > 0, 2, 3)))
        # координаты вдоль/поперёк бруса
        along = np.where(bar <= 1, A, B)
        across = np.where(bar == 0, B - 105.6, np.where(bar == 1, 35.8 - B, np.where(bar == 2, A - 28.3, -28.3 - A)))
        width = np.where(bar == 0, 110.2 - 105.6, np.where(bar == 1, 35.8 - 30.6, 32.6 - 28.3))
        h = np.full(A.shape, F)
        # стыки брусьев: щель 1.5 мм
        joint = ((bar >= 2) & ((np.abs(B - 105.6) < 0.08) | (np.abs(B - 35.8) < 0.08)))
        h = h - 0.12 * joint
        d_edge = np.minimum(across, width - across)
        h -= round_drop(np.clip(d_edge, 0, None), 0.3)
        gr = np.zeros(A.shape)
        for k in range(4):
            m = (bar == k) & frame
            if m.any():
                gr[m] = grain_relief(along[m], across[m], 1.5 + k, 0.01, width[m].mean() / 2 + 1.0, 1.2, 70 + k)
        h += 0.08 * (gr - 0.35)
        h += 0.08 * (fbm2(along * 0.06, across * 0.3 + bar * 5.0, 81, 3) - 0.5)     # горбыль — неровный, тёсаный
        # кора на верхнем и переднем брусьях: полоса 40-70 % ширины у внешней кромки, рваный край
        barkline = width * (0.45 + 0.25 * fbm2(along * 0.08, bar * 3.0, 91, 3))
        bark = ((bar == 0) | (bar == 2)) & (across > width - barkline) & frame
        # кора: пластины вдоль бруса, борозды, чечевички
        f1, f2 = voronoi(along * 0.22, across * 1.9, 0.9, 97)
        furrow = sstep(0.18, 0.04, f2 - f1)
        bh = 0.16 + 0.05 * np.clip(1 - f1, 0, 1) - 0.14 * furrow + 0.03 * (n2(along * 2.0, across * 2.0, 99) - 0.5)
        bh = bh * sstep(width - barkline, width - barkline + 0.25, across)          # ступенька у края коры
        h = np.where(bark, h + bh, h)
        cav = np.where(bark, furrow * 0.8, 0.0) + joint * 1.0
        # торцы с кольцами у концов верхнего/нижнего бруса (видны на передней кромке): только намёк — у края
        # гвозди: по 2 на углах + по вертикальным брусьям через ~22 см
        nail = z.copy()
        pts = []
        for bc in (108.0, 33.2):
            for ac in (-30.7, 30.7):
                pts += [(ac - 0.8 * np.sign(ac) * 0, bc - 0.9), (ac, bc + 0.9)]
        for ac in (-30.5, 30.5):
            for bc in (55.0, 78.0):
                pts.append((ac, bc))
        for (a, b) in pts:
            box = (np.abs(A - a) < 1.6) & (np.abs(B - b) < 1.6) & frame
            if not box.any():
                continue
            Hn, nm = nail_head(h[box], A[box] - a, B[box] - b, F, 0)
            h[box] = Hn
            nail[box] = np.maximum(nail[box], nm)
        # передний брус у дверцы обуглен у нижней половины (жар из топки)
        ch = (bar == 2) & frame
        amt = ch * sstep(0.45, 0.65, fbm2(A * 0.1, B * 0.04, 501, 3) + 0.25 * sstep(80, 45, B))
        char = z.copy()
        if (amt > 0).any():
            m = amt > 0
            dh, cr = char_field(A[m], B[m], amt[m], 1.7, 505)
            h[m] += dh
            cav[m] = np.maximum(cav[m], cr)
            char = amt
        mat = np.where(bark, MAT["bark"], MAT["frame"])
        mat = np.where(char > 0.5, MAT["char"], mat)
        return dict(h=h, grain=gr, cav=cav, nail=nail, char=char, tone=0.3 + 0.2 * bar, bark=bark * 1.0, bar=bar), mat
