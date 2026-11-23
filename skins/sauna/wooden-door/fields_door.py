"""Sauna Door v2: рельеф двери полями высот на numpy (общий для bake_v2.py в Blender и texture_v2.py / превью в .venv).

План: PLAN_v2.md. Всё, что даёт форму, считается здесь функциями, и те же функции пишут маски цвета — рельеф и цвет
совпадают пиксель в пиксель. Единицы — сантиметры; оси модели (OBJ × 100, без поворота): x — ширина (−121 … 0,
ручка у −x), y — вверх, z — толщина (перед смотрит в +z, его плоскость z = ZF).

Плотность текселей двери в игре — 2.3 px/см (1 px ≈ 4.4 мм при 1024): форма не меньше 1.3–1.7 см, повторяющийся
рисунок не мельче 2.2–2.6 см (PLAN_v2.md, раздел 1).

Части:
  Front.field(X, Y)   перед: 9 досок вагонки (как v1.2), швы до стального листа, фаски, коробление, волокна,
                      сучки, трещины, вмятины, скол, затёртость у ручки, разбухший рваный низ, заплата, кованые
                      шляпки, загнутые концы гвоздей брусьев и раскосов, «улыбки» молотка, окно (рамка, замазка,
                      стекло, подоконник). Чистое место под замки.
  edge_field(Y, Z)    боковые кромки: стальной лист с загибом, бока досок, торцы брусьев с кольцами.
  towel_grid()        полотенце на гнутом гвозде (форма v1.2) + подгибы со строчкой и жатость.
  leaf_grid()         берёзовый лист.
  drip_cut(x, y)      прозрачные потёки на стекле (1 — насквозь), одни и те же x, y с обеих сторон двери.
"""
import numpy as np

# ------------------------------------------------------------------ noise (как bed/fields_v2.py)
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
    """Скругление кромки радиусом r: насколько поверхность ниже на расстоянии d от края."""
    t = np.clip(r - d, 0, None)
    t = np.minimum(t, r)
    return r - np.sqrt(np.maximum(r * r - t * t, 0))


# ------------------------------------------------------------------ модель (см)
ZF = 5.37                      # плоскость переда
ZB, ZR = 0.0, -4.6             # поле досок сзади, лицо брусьев и раскосов
FACE_X = (-119.6, -1.5)        # плоская часть переда; дальше фаска к кромке (x −121 и −0.2, z 4.0)
FACE_Y = (1.3, 211.2)
EDGE_X = (-121.0, -0.2)
STEEL_H = -1.3                 # стальной лист под досками переда (z 4.07)
STEP = 0.15                    # шаг сетки high-poly, см (запекание 4096: 1 px ≈ 1.1 мм)

# доски — раскладка v1.2 (bake/layout.json), одна и та же с двух сторон двери
BOARDS = ((-118.05, -106.29), (-105.59, -93.12), (-92.42, -79.63), (-78.93, -65.25), (-64.55, -52.10),
          (-51.40, -37.84), (-37.14, -28.94), (-28.24, -17.43), (-16.73, -3.05))
RAILS = ((1.3, 22.5), (97.1, 119.7), (187.5, 210.0))           # брусья сзади (y0, y1)
BRACES = (  # контуры раскосов сзади, как в OBJ (x, y)
    ((-58.9, 121.4), (-82.2, 121.4), (-105.2, 161.9), (-105.2, 170.1), (-110.9, 172.1), (-118.8, 185.9), (-95.8, 185.9)),
    ((-2.5, 24.4), (-27.0, 24.4), (-54.3, 72.4), (-58.8, 86.4), (-66.8, 95.3), (-43.9, 95.3)),
)
WINDOW = (-52.0, -12.0, 130.0, 178.0)      # рамка снаружи: x0, x1, y0, y1 (перед — справа вверху)
SLAT = 4.7
PANE = (WINDOW[0] + SLAT, WINDOW[1] - SLAT, WINDOW[2] + SLAT, WINDOW[3] - SLAT)   # −47.3 … −16.7, 134.7 … 173.3
SILL = (WINDOW[0] - 2.2, WINDOW[1] + 2.6, WINDOW[2] - 3.6, WINDOW[2] + 0.2)
HOOK = (-90.5, 186.5)
TOWEL_W, TOWEL_L = 37.0, 60.0
HANDLE = (-108.0, 106.5)
LOCK_ZONE = (-119.0, -93.0, 57.0, 95.0)    # кодовый и навесной замок (рамки с игровых кадров, v1.2) — чистые доски
HEAD_ROWS = (55.0, 156.0)                  # шляпки: доски на листе
PATCH = (6, 26.5)                          # доска 6 у низа заменена обрезком: стык на y 26.5
TWISTED = 3                                # доска «пропеллером»

MAT = {"board": 1, "patch": 2, "steel": 3, "nail": 4, "frame": 5, "sill": 6, "putty": 7, "glass": 8,
       "towel": 9, "hook": 10, "leaf": 11, "gap": 12, "rail_end": 13}


def in_poly(x, y, poly):
    x, y = np.asarray(x, float), np.asarray(y, float)
    inside = np.zeros(np.broadcast(x, y).shape, bool)
    n = len(poly)
    for i in range(n):
        (xa, ya), (xb, yb) = poly[i], poly[(i + 1) % n]
        cond = ((ya > y) != (yb > y)) & (x < xa + (y - ya) / (yb - ya + 1e-12) * (xb - xa))
        inside ^= cond
    return inside


def in_rect(x, y, r, m=0.0):
    return (x > r[0] - m) & (x < r[1] + m) & (y > r[2] - m) & (y < r[3] + m)


def towel_cover(x, y):
    """Грубо: где перед закрыт полотенцем (детали там не видны — не ставим)."""
    hx, hy = HOOK
    t = np.clip((hy - y) / TOWEL_L, -1, 2)
    tc = np.clip(t, 0, 1)
    return (t > 0.02) & (t < 1.0) & (x > hx - 9.5 - 4 * tc) & (x < hx - 1.5 + TOWEL_W * (1 - (1 - tc) ** 1.5) * 0.9)


def busy(x, y, m=0.0):
    """Места, где мелким деталям (сучки, трещины, вмятины) не место: окно, полотенце, замки."""
    return (in_rect(x, y, (SILL[0], SILL[1], SILL[2], WINDOW[3]), m) | towel_cover(x, y)
            | in_rect(x, y, LOCK_ZONE, m))


# ------------------------------------------------------------------ перед
class Front:
    def __init__(self, seed=31):
        rng = np.random.default_rng(seed)
        self.rng = rng
        nb = len(BOARDS)
        self.y_lo = FACE_Y[0] + 0.5 + rng.uniform(0, 1.0, nb)
        self.y_hi = FACE_Y[1] - rng.uniform(0.1, 0.8, nb)
        self.grain = []
        for i in range(nb):
            a, b = BOARDS[i]
            quarter = rng.random() < 0.3
            self.grain.append(dict(
                quarter=quarter, c=(a + b) / 2 + rng.uniform(-3, 3),
                d0=rng.uniform(1.0, 6.0) if not quarter else 0.0,
                tilt=rng.uniform(0.015, 0.035) * rng.choice((-1, 1)),
                s=rng.uniform(2.4, 3.4), seed=int(rng.integers(1000)),
                tone=rng.random(), cup=rng.uniform(0.1, 0.3) * (1 if rng.random() < 0.8 else -1),
                top=rng.uniform(-0.06, 0.06)))
        self.grain[PATCH[0]]["tone"] = 0.9
        self._features(rng)

    # -------------------------------------------------------------- раскладка деталей по истории
    def _features(self, rng):
        B = BOARDS
        mid = lambda i: (B[i][0] + B[i][1]) / 2
        # кованые шляпки: два ряда, доски прибиты к листу; kind 0 — обычная, 1 — утоплена с воронкой,
        # 2 — торчит на 4 мм, 3 — загнута (лежит на доске)
        heads = []
        for i, (a, b) in enumerate(B):
            w = b - a
            for y in HEAD_ROWS:
                xs = (a + w * 0.28, a + w * 0.72) if w > 11.5 else (a + w * 0.5,)
                for x in xs:
                    px, py = x + rng.uniform(-0.6, 0.6), y + rng.uniform(-1.0, 1.0)
                    if in_rect(px, py, (SILL[0], SILL[1], SILL[2], WINDOW[3]), 2.0) or towel_cover(px, py):
                        continue
                    kind = 1 if rng.random() < 0.15 else 0
                    heads.append([px, py, kind])
        heads[3][2] = 2
        heads[11][2] = 3
        # на заплате — по два гвоздя с каждой стороны стыка
        a, b = B[PATCH[0]]
        for py in (PATCH[1] - 3.0, PATCH[1] + 3.2):
            for x in (a + 2.4, b - 2.4):
                heads.append([x + rng.uniform(-0.3, 0.3), py + rng.uniform(-0.4, 0.4), 0])
        self.heads = [tuple(h) for h in heads]
        # загнутые концы: гвозди брусьев и раскосов пробивают дверь насквозь, на переде загнуты поперёк волокон
        clinch = []
        for (y0, y1) in RAILS:
            yc = (y0 + y1) / 2
            for i in range(len(B)):
                px = mid(i) + rng.uniform(-1.5, 1.5)
                py = yc + (5.5 if i % 2 else -5.5) + rng.uniform(-1.2, 1.2)
                if any(in_poly(px, py, br) for br in BRACES):
                    continue
                clinch.append((px, py))
        for poly in BRACES:
            (xa, ya) = ((poly[0][0] + poly[1][0]) / 2, poly[0][1])
            (xb, yb) = ((poly[-1][0] + poly[-2][0]) / 2, poly[-1][1])
            for k in range(5):
                t = (k + 0.5) / 5
                px = xa + (xb - xa) * t + (5.0 if k % 2 else -5.0) + rng.uniform(-1, 1)
                py = ya + (yb - ya) * t + rng.uniform(-2, 2)
                if in_poly(px, py, poly):
                    clinch.append((px, py))
        out = []
        for (px, py) in clinch:
            if towel_cover(px, py) or in_rect(px, py, LOCK_ZONE, 1.0) or in_rect(px, py, (SILL[0], SILL[1], SILL[2], WINDOW[3]), 1.5):
                continue
            ang = rng.choice((0.0, np.pi)) + rng.uniform(-0.45, 0.45)      # поперёк волокон, вбок
            out.append((px, py, ang, rng.uniform(3.0, 4.0)))
        self.clinch = out
        # «улыбки» молотка у части шляпок и загнутых концов
        self.smiles = []
        for (x, y, k) in self.heads:
            if k != 3 and rng.random() < 0.3:
                self.smiles.append((x, y, rng.uniform(0, 2 * np.pi), 1.6))
        for (x, y, a, L) in self.clinch:
            if rng.random() < 0.25:
                self.smiles.append((x + L * 0.6 * np.cos(a), y + L * 0.6 * np.sin(a), a + np.pi / 2 * rng.choice((-1, 1)), 1.8))
        # сучки (x, y, r, выпал)
        knots = []
        tries = 0
        while len(knots) < 10 and tries < 5000:
            tries += 1
            i = int(rng.integers(len(B)))
            a, b = B[i]
            x, y = rng.uniform(a + 2.5, b - 2.5), rng.uniform(10, 205)
            if busy(x, y, 4.0) or (i == PATCH[0] and y < PATCH[1] + 4):
                continue
            if any(np.hypot(x - kx, y - ky) < 25 for kx, ky, *_ in knots):
                continue
            if any(np.hypot(x - hx, y - hy) < 5 for hx, hy, _ in self.heads):
                continue
            knots.append((x, y, rng.uniform(1.3, 2.7), False))
        knots[4] = (knots[4][0], knots[4][1], 1.5, True)
        self.knots = knots
        # трещины (x, y0, y1, раскрытие (полуширина), глубина, seed): продольные и торцевые сверху (тепло из
        # парной идёт поверх двери) — у верхних концов гуще
        cracks = []
        for _ in range(5):
            i = int(rng.integers(len(B)))
            a, b = B[i]
            for _t in range(50):
                x, y = rng.uniform(a + 2, b - 2), rng.uniform(30, 190)
                L = rng.uniform(10, 40)
                if not (busy(x, y, 3) or busy(x, y + L, 3) or busy(x, y + L / 2, 3)):
                    cracks.append((x, y, y + L, 0.28, 0.35, int(rng.integers(1000))))
                    break
        for i in rng.choice(len(B), 5, replace=False):
            a, b = B[i]
            x = rng.uniform(a + 2.5, b - 2.5)
            L = rng.uniform(6, 16)
            cracks.append((x, self.y_hi[i] - L, self.y_hi[i] + 1, 0.3, 0.4, int(rng.integers(1000))))
        for i in rng.choice(len(B), 3, replace=False):                       # и у разбухшего низа
            a, b = B[i]
            x = rng.uniform(a + 2.5, b - 2.5)
            cracks.append((x, self.y_lo[i] - 1, self.y_lo[i] + rng.uniform(5, 12), 0.25, 0.35, int(rng.integers(1000))))
        self.cracks = cracks
        # вмятины: у низа гнездом (пинали, ставили шайку), редкие выше
        dents = []
        for _ in range(7):
            x, y = rng.uniform(-115, -6), rng.uniform(4, 38)
            if not busy(x, y, 2):
                r = rng.uniform(1.5, 4.0)
                dents.append((x, y, r, 0.04 + 0.03 * r))
        for _ in range(8):
            x, y = rng.uniform(-115, -6), rng.uniform(40, 200)
            r = rng.pareto(2.2) * 0.8 + 1.3
            if not busy(x, y, r + 2):
                dents.append((x, y, min(r, 3.0), 0.035 + 0.025 * min(r, 3.0)))
        self.dents = dents
        # забоины кромок досок у низа
        nicks = []
        for _ in range(24):
            i = int(rng.integers(len(B)))
            side = int(rng.integers(2))
            y = rng.uniform(3, 60) if rng.random() < 0.7 else rng.uniform(60, 205)
            x = B[i][side]
            if not busy(x, y, 1):
                nicks.append((x, y, rng.uniform(0.8, 1.8), rng.uniform(0.12, 0.25)))
        self.nicks = nicks
        self.chip = (4, -1)            # скол нижнего левого угла доски 4

    # -------------------------------------------------------------- поле
    def field(self, X, Y):
        """X, Y — сетка (см). h — смещение от плоскости переда (см), маски 0..1, коды."""
        H = np.zeros_like(X, dtype=np.float64)
        B = BOARDS
        nb = len(B)
        idx = np.full(X.shape, -1, np.int64)
        for i, (a, b) in enumerate(B):
            idx = np.where((X >= a - 0.35) & (X < b + 0.35), i, idx)
        ii = np.clip(idx, 0, nb - 1)
        a = np.asarray([b[0] for b in B])[ii]
        b = np.asarray([b[1] for b in B])[ii]
        wdt = b - a
        # рваный разбухший низ: торцы досок неровные (зубцы 1–2 см)
        ylo = np.asarray(self.y_lo)[ii] + 1.4 * (fbm2(X * 0.7, ii * 3.1, 7, 2) - 0.35)
        yhi = np.asarray(self.y_hi)[ii] + 0.3 * (n2(X * 0.9, ii * 2.3, 8) - 0.5)
        # заплата: доска 6 ниже стыка — отдельный обрезок
        pi_, py_ = PATCH
        patch = (idx == pi_) & (Y < py_)
        joint_lo = np.where((idx == pi_) & (Y >= py_), Y - (py_ + 0.25), 1e9)
        joint_hi = np.where(patch, (py_ - 0.25) - Y, 1e9)
        dside = np.minimum(X - a, b - X)
        dend = np.minimum(np.minimum(Y - ylo, yhi - Y), np.minimum(joint_lo, joint_hi))
        inside = (idx >= 0) & (dside > 0) & (dend > 0) & (X > FACE_X[0] - 0.5) & (X < FACE_X[1] + 0.5)

        # ---- зоны по истории
        hand = np.exp(-(((X - HANDLE[0]) / 11.0) ** 2 + ((Y - HANDLE[1]) / 17.0) ** 2))
        hand = np.clip(hand * 1.3 * (0.85 + 0.3 * n2(X * 0.2, Y * 0.2, 11)), 0, 1)
        wet = sstep(40.0, 12.0, Y + 6 * (n2(X * 0.15, 0.5, 12) - 0.5))

        # ---- фаски: у ручки затёрто сильнее, внизу кромки размочалены
        r_side = 0.55 + 0.6 * hand + 0.2 * wet
        r_end = 0.6 + 0.4 * wet
        drop = np.maximum(round_drop(dside, r_side), round_drop(dend, r_end))
        H -= drop

        # ---- доска: уровень, коробление, перекос, следы рубанка
        top = np.asarray([g["top"] for g in self.grain])[ii]
        cup = np.asarray([g["cup"] for g in self.grain])[ii]
        cu = np.clip((X - (a + b) / 2) / (wdt / 2), -1, 1)
        H += top + cup * (1 - cu ** 2) - np.where(patch, 0.12, 0.0)
        H += np.where(idx == TWISTED, 0.35 * ((Y - 106) / 106) * cu, 0)
        H += 0.06 * (n2(X * 0.05 + ii * 5, Y * 0.02, 31) - 0.5)
        H += 0.03 * (n2(X * 0.08 + ii * 3, Y * 0.18, 37) - 0.5) * (1 - hand)

        # ---- волокна: гребни поздней древесины (у переда сухо — невысокие; у низа размочалены; у ручки затёрты)
        g_ridge = np.zeros_like(X, dtype=np.float64)
        knots = [(kx, ky, kr) for kx, ky, kr, _ in self.knots]
        for i, g in enumerate(self.grain):
            m = (idx == i)
            if not m.any():
                continue
            xs, ys = X[m], Y[m]
            if i == pi_:
                ys = np.where(ys < py_, ys + 300.0, ys)        # у обрезка своё бревно
            warp = 0.9 * (fbm2(ys * 0.012, xs * 0.08, g["seed"], 3) - 0.5) + 0.2 * (n2(ys * 0.06, xs * 0.3, g["seed"] + 3) - 0.5)
            if g["quarter"]:
                ph = (xs - g["c"]) / (g["s"] * 0.9) + 1.6 * warp
            else:
                d = g["d0"] + g["tilt"] * (ys - 106.0) + 1.2 * warp
                ph = np.sqrt((xs - g["c"]) ** 2 + d * d) / g["s"] + warp
            for (kx, ky, kr) in knots:
                dd = np.hypot(xs - kx, (ys - ky) / 1.6)
                ph = ph + 1.4 * kr * np.exp(-(dd / (2.2 * kr)) ** 2) / g["s"]
            f = ph - np.floor(ph)
            g_ridge[m] = sstep(0.42, 0.72, f) * sstep(1.0, 0.86, f)     # гребень ~1/3 шага (8–11 мм), склон к поздней
        amp = 0.075 * (1 - 0.75 * hand) + 0.07 * wet
        amp = np.where(patch, 0.05, amp)
        H += amp * (g_ridge - 0.4)
        # размочаленные волокна у низа: мелкие продольные гребни
        H += 0.06 * wet * (n2(X * 1.6, Y * 0.08, 41) - 0.5)

        cav = np.zeros_like(X, dtype=np.float64)
        dent_m = np.zeros_like(X, dtype=np.float64)

        # ---- сучки
        knot_m = np.zeros_like(X, dtype=np.float64)
        for (kx, ky, kr, fallen) in self.knots:
            box = (np.abs(X - kx) < kr * 2) & (np.abs(Y - ky) < kr * 2.6)
            if not box.any():
                continue
            xs, ys = X[box], Y[box]
            dd = np.hypot(xs - kx, (ys - ky) / 1.3)
            core = sstep(kr, kr * 0.8, dd)
            ring = np.exp(-((dd - kr) / 0.3) ** 2)
            hb = H[box]
            if fallen:
                hole = sstep(kr * 0.95, kr * 0.7, dd)
                hb = hb * (1 - hole) + hole * (STEEL_H + 0.1)
                cav[box] = np.maximum(cav[box], sstep(kr * 0.95, kr * 0.7, dd))
                hb -= 0.08 * ring
            else:
                hb = hb + 0.09 * core - 0.07 * ring
                ang = np.arctan2(ys - ky, xs - kx)
                for a0 in (0.4 + kx, 2.5 + ky, 4.3 + kx * 0.3):
                    da = np.abs(np.angle(np.exp(1j * (ang - a0))))
                    tt = dd * da
                    rad = (tt < 0.3) & (dd < kr * 0.9) & (dd > kr * 0.2)
                    hb = hb - np.where(rad, 0.14 * (1 - tt / 0.3), 0)
                    cav[box] = np.maximum(cav[box], np.where(rad, 0.6 * (1 - tt / 0.3), 0))
            H[box] = hb
            knot_m[box] = np.maximum(knot_m[box], core)

        # ---- трещины (вдоль волокон, клин с мягкими концами, извилистые)
        for (xc, ya, yb, hw, dep, sd) in self.cracks:
            box = (Y > ya - 1) & (Y < yb + 1) & (np.abs(X - xc) < 2.5)
            if not box.any():
                continue
            xs, ys = X[box], Y[box]
            t = np.clip((ys - ya) / (yb - ya), 0, 1)
            cx = xc + 0.7 * (n2(ys * 0.08, sd * 1.0, sd) - 0.5) + 0.2 * (n2(ys * 0.4, sd * 2.0, sd + 1) - 0.5)
            prof = np.sin(np.pi * t) ** 0.6
            if yb > 200:
                prof = t ** 0.5          # торцевая сверху: шире у торца
            elif ya < 6:
                prof = (1 - t) ** 0.5    # снизу
            w = hw * prof + 1e-3
            core = np.clip(1 - np.abs(xs - cx) / w, 0, 1)
            shoulder = np.clip(1 - np.abs(xs - cx) / (w + 0.5), 0, 1) * prof        # скаты 5 мм с каждой стороны
            H[box] -= dep * prof * core ** 0.7 + 0.05 * shoulder
            cav[box] = np.maximum(cav[box], core * prof)

        # ---- вмятины (чаша без ободка)
        for (x, y, r, d) in self.dents:
            box = (np.abs(X - x) < r) & (np.abs(Y - y) < r)
            if not box.any():
                continue
            dd = np.hypot(X[box] - x, Y[box] - y)
            u = np.clip(1 - (dd / r) ** 2, 0, 1) ** 2
            H[box] -= d * u
            dent_m[box] = np.maximum(dent_m[box], u)
        # ---- забоины кромок
        for (x, y, r, d) in self.nicks:
            box = (np.abs(X - x) < r + 0.3) & (np.abs(Y - y) < r * 1.6 + 0.3)
            if not box.any():
                continue
            dd = np.hypot(X[box] - x, (Y[box] - y) / 1.5)
            u = np.clip(1 - (dd / r) ** 2, 0, 1)
            H[box] -= d * u * (0.7 + 0.6 * n2(X[box] * 2, Y[box] * 2, 17))
            dent_m[box] = np.maximum(dent_m[box], u)
        # ---- скол нижнего угла доски (клин, излом волокнами)
        ci, side = self.chip
        cx, cy = B[ci][0] if side < 0 else B[ci][1], self.y_lo[ci]
        u_, v_ = (X - cx) * (-side), Y - cy
        wedge = (idx == ci) & (u_ > -0.5) & (v_ > -0.5) & (u_ / 3.0 + v_ / 4.5 < 1)
        H = np.where(wedge, np.minimum(H, -0.45 - 0.3 * (1 - (u_ / 3.0 + v_ / 4.5)) + 0.08 * (n2(X * 2, Y * 0.5, 5) - 0.5)), H)
        dent_m = np.maximum(dent_m, wedge * 1.0)

        # ---- кованые шляпки Ø 1.8 см: четырёхгранная пирамидка со скруглением
        nail_m = np.zeros_like(X, dtype=np.float64)
        for (x, y, kind) in self.heads:
            box = (np.abs(X - x) < 2.6) & (np.abs(Y - y) < 2.6)
            if not box.any():
                continue
            xs, ys = X[box] - x, Y[box] - y
            if kind == 3:          # загнутый: шляпка набок и стержень лежит на доске
                u, v = xs + 2.6, ys
                dd = np.hypot(u, v)
                head = sstep(0.95, 0.8, dd)
                shank = np.clip(1 - (np.abs(v) / 0.33) ** 2, 0, 1) ** 0.5 * (xs > -2.6) * (xs < 0.4)
                hh = np.maximum(0.1 + 0.3 * head, np.where(shank > 0, 0.05 + 0.25 * shank, -9))
                H[box] = np.maximum(H[box], np.where((head > 0) | (shank > 0), hh, -9))
                nail_m[box] = np.maximum(nail_m[box], np.maximum(head, (shank > 0.05) * 1.0))
                continue
            aa = (x * 7.3 + y * 3.1) % 1.57
            ca, sa = np.cos(aa), np.sin(aa)
            u, v = xs * ca + ys * sa, -xs * sa + ys * ca
            r = 0.9
            q = ((np.abs(u) / r) ** 4 + (np.abs(v) / r) ** 4) ** 0.25
            pyr = 1 - np.maximum(np.abs(u), np.abs(v)) / r
            dome = np.sqrt(np.clip(1 - q ** 2, 0, 1))
            lift = {0: 0.05, 1: -0.1, 2: 0.4}[kind]
            hh = lift + 0.12 * dome + 0.08 * np.clip(pyr, 0, 1) + 0.03 * (n2(u * 3, v * 3, int(x)) - 0.5)
            dd = np.hypot(xs, ys)
            hb = H[box] - 0.04 * np.clip(1 - ((dd - 1.15) / 0.45) ** 2, 0, 1)      # смятое дерево вокруг
            if kind == 1:
                hb = hb - 0.14 * np.clip(1 - (dd / 1.7) ** 2, 0, 1) ** 2              # воронка от добойника
            H[box] = np.where(q < 1, np.maximum(hb, hh), hb)
            nail_m[box] = np.maximum(nail_m[box], sstep(1.03, 0.92, q))
        # ---- загнутые концы: стержень 6–7 мм, загнут вбок и вбит в дерево, на выходе бугорок
        for (x, y, ang, L) in self.clinch:
            box = (np.abs(X - x) < L + 1.5) & (np.abs(Y - y) < L + 1.5)
            if not box.any():
                continue
            ca, sa = np.cos(ang), np.sin(ang)
            xs, ys = X[box] - x, Y[box] - y
            u, v = xs * ca + ys * sa, -xs * sa + ys * ca
            t = np.clip(u / L, 0, 1)
            half = 0.38 * (1 - 0.55 * t) + 0.05
            on = (u > -0.3) & (u < L) & (np.abs(v) < half)
            prof = np.sqrt(np.clip(1 - (v / half) ** 2, 0, 1))
            hh = 0.22 * (1 - 0.6 * t) * prof + 0.03
            groove = np.clip(1 - np.abs(v) / (half + 0.45), 0, 1) * (u > -0.5) * (u < L + 0.4)
            hb = H[box] - 0.05 * groove                                   # дерево промято молотком вдоль стержня
            bump = np.exp(-(np.hypot(u + 0.1, v) / 0.45) ** 2) * 0.12      # выход стержня
            hn = np.where(on, np.maximum(hb, hh + bump), hb)
            H[box] = hn
            nail_m[box] = np.maximum(nail_m[box], on * sstep(0.0, 0.3, prof) + 0 * bump)
            dent_m[box] = np.maximum(dent_m[box], groove * 0.5)
        # ---- «улыбки» молотка: дуга, промах краем бойка
        for (x, y, a0, rr) in self.smiles:
            cx, cy = x + 1.2 * np.cos(a0), y + 1.2 * np.sin(a0)
            box = (np.abs(X - cx) < rr + 1) & (np.abs(Y - cy) < rr + 1)
            if not box.any():
                continue
            dd = np.hypot(X[box] - cx, Y[box] - cy)
            ang = np.arctan2(Y[box] - cy, X[box] - cx)
            win = np.clip(np.cos(ang - a0) * 1.6 - 0.2, 0, 1)
            sm = np.exp(-((dd - rr) / 0.22) ** 2) * win
            H[box] -= 0.08 * sm
            dent_m[box] = np.maximum(dent_m[box], sm)

        # ---- щели и стальной лист (под досками и полосой вдоль кромок)
        steel = STEEL_H + 0.06 * (fbm2(X * 0.25, Y * 0.25, 51, 3) - 0.5) - 0.08 * sstep(0.62, 0.8, fbm2(X * 0.6, Y * 0.6, 53, 2))
        H = np.where(inside, H, steel)
        cav = np.where(inside, cav, 1.0)
        mat = np.where(inside, np.where(patch, MAT["patch"], MAT["board"]), MAT["gap"])
        edge_strip = (X < B[0][0] - 0.35) | (X > B[-1][1] + 0.35)
        mat = np.where(edge_strip & ~inside, MAT["steel"], mat)
        cav = np.where(edge_strip & ~inside, 0.0, cav)
        nail_m = nail_m * inside
        mat = np.where(nail_m > 0.5, MAT["nail"], mat)
        grain_out = g_ridge * inside

        # ---- окно: рамка, замазка, стекло, подоконник (поверх досок)
        H, mat, cav, grain_out, nail_m, putty_m = self._window(X, Y, H, mat, cav, grain_out, nail_m)

        tone = np.asarray([g["tone"] for g in self.grain])[ii]
        tone = np.where(patch, 0.95, tone)
        return dict(h=H, grain=grain_out, cavity=cav, dent=dent_m * inside, nail=nail_m, knot=knot_m * inside,
                    wear=hand, putty=putty_m, tone=tone, mat=mat, board=np.where(inside, idx, nb))

    # -------------------------------------------------------------- окно
    def _window(self, X, Y, H, mat, cav, grain, nail_m):
        x0, x1, y0, y1 = WINDOW
        xi0, xi1, yi0, yi1 = PANE
        rng = np.random.default_rng(77)
        putty_m = np.zeros_like(X, dtype=np.float64)
        # подоконник: доска 3.6 × 44.8 см, верх 2.6 см над передом, кромки скруглены
        sx0, sx1, sy0, sy1 = SILL
        ds = np.minimum(np.minimum(X - sx0, sx1 - X), np.minimum(Y - sy0, sy1 - Y))
        sill = ds > 0
        hs = 2.6 - round_drop(np.minimum(np.minimum(X - sx0, sx1 - X), (Y - sy0) * 0.8), 0.8) - round_drop(sy1 - Y, 0.3)
        gs = sstep(0.42, 0.72, ((Y - sy0) * 0.45 + 0.5 * fbm2(X * 0.03, Y * 0.3, 61, 2)) % 1) * sstep(1.0, 0.86, ((Y - sy0) * 0.45 + 0.5 * fbm2(X * 0.03, Y * 0.3, 61, 2)) % 1)
        hs = hs + 0.05 * (gs - 0.4) + 0.04 * (n2(X * 0.1, Y * 0.5, 62) - 0.5)
        H = np.where(sill, np.maximum(H, hs), H)
        mat = np.where(sill, MAT["sill"], mat)
        grain = np.where(sill, gs, grain)
        cav = np.where(sill, 0.0, cav)
        # рейки рамки: верх и низ во всю ширину, бока между ними; разная высота, кромки скруглены
        slats = (("x", x0 - 0.6, x1 + 0.9, y1 - SLAT, y1 + 0.3, 1.9, 1),
                 ("x", x0 - 0.4, x1 + 0.4, y0, y0 + SLAT, 1.8, 2),
                 ("y", x0 + 0.2, x0 + SLAT, y0 + SLAT, y1 - SLAT, 1.6, 3),
                 ("y", x1 - SLAT - 0.3, x1, y0 + SLAT, y1 - SLAT, 1.75, 4))
        for (ax, a0, a1, b0, b1, ht, sd) in slats:
            d = np.minimum(np.minimum(X - a0, a1 - X), np.minimum(Y - b0, b1 - Y))
            m = d > 0
            if not m.any():
                continue
            along = X if ax == "x" else Y
            across = Y if ax == "x" else X
            ph = across * 0.5 + 0.6 * fbm2(along * 0.03, across * 0.2, 63 + sd, 2) + sd * 0.3
            f = ph % 1
            gr = sstep(0.42, 0.72, f) * sstep(1.0, 0.86, f)
            hh = ht - round_drop(d, 0.45) + 0.05 * (gr - 0.4) + 0.05 * (n2(along * 0.08, sd, 64) - 0.5) * 1.0
            H = np.where(m, np.maximum(H, hh), H)
            new = m & (hh >= H - 1e-9)
            mat = np.where(new, MAT["frame"], mat)
            grain = np.where(new, gr, grain)
            cav = np.where(new, 0.0, cav)
            nail_m = np.where(new, 0.0, nail_m)
        # гвозди рамки: по углам и посередине боковых реек, шляпки Ø 1.5
        for (cx, cy) in ((x0 + SLAT / 2, y0 + SLAT / 2), (x1 - SLAT / 2, y0 + SLAT / 2), (x0 + SLAT / 2, y1 - SLAT / 2),
                         (x1 - SLAT / 2, y1 - SLAT / 2), (x0 + SLAT / 2, (y0 + y1) / 2), (x1 - SLAT / 2, (y0 + y1) / 2)):
            cx += rng.uniform(-0.6, 0.6)
            cy += rng.uniform(-0.6, 0.6)
            dd = np.hypot(X - cx, Y - cy)
            m = dd < 0.75
            base = np.where(m, H, 0)
            H = np.where(m, base + 0.05 + 0.12 * np.sqrt(np.clip(1 - (dd / 0.75) ** 2, 0, 1)), H)
            nail_m = np.maximum(nail_m, sstep(0.78, 0.66, dd))
            mat = np.where(dd < 0.7, MAT["nail"], mat)
        # стекло и замазка: проём, по периметру — валик замазки 1.4 см с трещинами, местами выкрошилась
        inn = (X > xi0) & (X < xi1) & (Y > yi0) & (Y < yi1)
        d = np.minimum(np.minimum(X - xi0, xi1 - X), np.minimum(Y - yi0, yi1 - Y))
        gl_h = 0.3 + 0.03 * (n2(X * 0.15, Y * 0.15, 71) - 0.5)              # старое стекло чуть волнистое
        bead = 1.4 + 0.25 * (n2(X * 0.3 + Y * 0.3, 0.5, 72) - 0.5)
        pt = np.clip(1 - d / bead, 0, 1)
        ph_ = 0.3 + 0.55 * pt ** 1.1 + 0.04 * (n2(X * 1.2, Y * 1.2, 73) - 0.5)     # валик 5–6 мм, склон ~20°
        # выкрошившиеся куски: участки периметра без замазки
        gone = np.zeros_like(X, dtype=bool)
        for (cx, cy, L) in ((xi0, 160.0, 4.5), (xi1, 142.0, 3.5), (-28.0, yi1, 5.0)):
            gone |= (np.hypot(X - cx, Y - cy) < L) & (d < bead + 0.2)
        # трещины замазки: поперёк валика через 3–6 см (усохла кусками) и местами вдоль; борозды 3–4 мм
        horiz = (np.minimum(Y - yi0, yi1 - Y) < np.minimum(X - xi0, xi1 - X))
        per = np.where(horiz, X, Y)
        ph = per / 4.2 + 0.6 * n2(per * 0.3, horiz * 3.0, 74)
        cross = sstep(0.07, 0.02, np.abs((ph % 1) - 0.5) - 0.43) * (n2(np.floor(ph), horiz * 5.0 + 0.5, 75) > 0.25)
        longc = sstep(0.18, 0.05, np.abs(d - bead * 0.45)) * (n2(per * 0.15, horiz * 7.0, 76) > 0.55)
        crk = np.maximum(cross, longc)
        ph_ = ph_ - 0.3 * crk * pt
        has_p = (pt > 0) & ~gone
        hwin = np.where(has_p, np.maximum(gl_h, ph_), gl_h)
        H = np.where(inn, hwin, H)
        mat = np.where(inn, np.where(has_p & (ph_ > gl_h + 0.02), MAT["putty"], MAT["glass"]), mat)
        putty_m = np.where(inn, has_p * 1.0, putty_m)
        cav = np.where(inn, np.where(has_p, crk * 0.8 * pt, 0.0), cav)
        grain = np.where(inn, 0.0, grain)
        nail_m = np.where(inn, 0.0, nail_m)
        return H, mat, cav, grain, nail_m, putty_m


def _voronoi(x, y, cell, seed):
    """Расстояния до двух ближайших точек (F1, F2) на сетке ячеек cell, по одной точке на ячейку."""
    gx, gy = np.floor(x / cell), np.floor(y / cell)
    f1 = np.full(np.shape(x), 1e9)
    f2 = np.full(np.shape(x), 1e9)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            cx, cy = gx + dx, gy + dy
            px = (cx + n2(cx * 1.7, cy * 1.3, seed)) * cell
            py = (cy + n2(cx * 1.1, cy * 1.9, seed + 1)) * cell
            d = np.hypot(x - px, y - py)
            f2 = np.where(d < f1, f1, np.minimum(f2, d))
            f1 = np.minimum(f1, d)
    return f1, f2


def front_grid(step=STEP):
    xs = np.arange(EDGE_X[0] - 0.3, EDGE_X[1] + 0.3 + 1e-6, step)
    ys = np.arange(FACE_Y[0] - 1.2, FACE_Y[1] + 0.5 + 1e-6, step)
    return np.meshgrid(xs, ys)


# ------------------------------------------------------------------ боковые кромки
def edge_field(Y, Z, side):
    """Кромка двери в плоскости x = EDGE_X[side]: h — сдвиг наружу (см). Слои по z: доска переда, стальной лист с
    загибом, доска зада, ниже — торцы брусьев (кольца) и бока досок зада."""
    H = np.zeros_like(Y, dtype=np.float64)
    mat = np.full(Y.shape, MAT["board"])
    grain = np.zeros_like(Y, dtype=np.float64)
    cav = np.zeros_like(Y, dtype=np.float64)
    # стальной лист z 1.2 … 4.1, загнут на кромку (полукруг), с раковинами
    zs0, zs1 = 1.2, 4.1
    stl = (Z >= zs0) & (Z <= zs1)
    fold = 0.35 * np.sqrt(np.clip(1 - ((Z - (zs0 + zs1) / 2) / ((zs1 - zs0) / 2)) ** 2, 0, 1))
    f1, f2 = _voronoi(Y, Z + side * 50, 1.6, 81 + side)
    pits = np.clip(1 - f1 / 0.7, 0, 1) ** 2 * (n2(Y * 0.4, Z * 0.4 + side, 82) > 0.45)
    hs = fold - 0.08 * pits + 0.04 * (fbm2(Y * 0.2, Z * 0.5, 83, 3) - 0.5)
    H = np.where(stl, hs, H)
    mat = np.where(stl, MAT["steel"], mat)
    cav = np.where(stl, pits * 0.5, cav)
    # доски (бок крайней доски: волокна вдоль y), утоплены на 3 мм, кромки скруглены
    for (b0, b1) in ((4.15, 5.37), (0.0, 1.15)):
        m = (Z > b0) & (Z < b1)
        d = np.minimum(Z - b0, b1 - Z)
        gr = sstep(0.42, 0.72, (Z * 0.6 + 0.8 * fbm2(Y * 0.02, Z * 0.3 + b0, 84, 3)) % 1)
        H = np.where(m, -0.3 - round_drop(d, 0.35) + 0.04 * (gr - 0.4), H)
        grain = np.where(m, gr, grain)
    # ниже доски зада: торцы брусьев на их высоте (кольца), между брусьями — пусто (глубоко)
    below = Z < 0.0
    rails = np.zeros_like(Y, dtype=bool)
    for k, (y0, y1) in enumerate(RAILS):
        r = below & (Y > y0) & (Y < y1)
        cy, cz = (y0 + y1) / 2 + 9.0 * (1 if k % 2 else -1), -2.3 - 8.0
        rr = np.hypot(Y - cy, (Z - cz) * 1.1)
        ring = sstep(0.4, 0.7, (rr / 2.4 + 0.3 * n2(Y * 0.2, Z * 0.2, 85 + k)) % 1)
        d = np.minimum(np.minimum(Y - y0, y1 - Y), np.minimum(Z - ZR, 0.0 - Z))
        hr = -round_drop(d, 0.6) + 0.06 * (ring - 0.5)
        H = np.where(r, hr, H)
        grain = np.where(r, ring, grain)
        rails |= r
    H = np.where(below & ~rails, -6.0, H)
    mat = np.where(rails, MAT["rail_end"], mat)
    cav = np.where(below & ~rails, 1.0, cav)
    return dict(h=H, mat=mat, grain=grain, cavity=cav)


# ------------------------------------------------------------------ полотенце
def towel_point(S, T, layer):
    """Форма v1.2 (одобрена в игре): сложено пополам через гнутый гвоздь и висит в два слоя; складки веером от
    гвоздя, подол наискосок. S поперёк 0..1, T вниз 0..1 (массивы). Возвращает x, y, z (см)."""
    hx, hy = HOOK
    length = TOWEL_L * (1.0 if layer == 0 else 0.80)
    width = TOWEL_W * (1.0 if layer == 0 else 0.93)
    spread = 3.0 + (width - 3.0) * (1 - (1 - T) ** 1.5)
    left = hx - 1.2 - 8.5 * T ** 1.3 + (4.5 * T if layer else 0.0)
    x = left + S * spread + 0.6 * np.sin(T * 5.0 + S * 2.0)
    hem = 1.0 - 0.34 * np.maximum(0.0, S - 0.22) ** 1.15 - 0.10 * np.maximum(0.0, 0.22 - S) / 0.22
    y = hy - 1.0 - length * T * hem
    amp = 0.3 + 2.2 * (1 - T) ** 0.7 * np.minimum(1.0, T * 8 + 0.2)
    ph = 2 * np.pi * (2.6 * S ** 0.85 + 0.10 * np.sin(T * 2.7 + 0.6) + 0.13 * layer)
    fold = (0.5 + 0.5 * np.cos(ph)) ** 0.65
    z = ZF + (1.0 if layer == 0 else 0.3) + amp * fold
    z += 0.4 * (fbm2(S * 6.0 + layer * 9, T * 8.0, 91, 3) - 0.5)
    # жатый застиранный лён: мелкие заломы 3–5 см
    z += 0.18 * (fbm2(x * 0.25, y * 0.25 + layer * 30, 92, 2) - 0.5)
    z += 0.4 * np.maximum(0.0, T - 0.88) / 0.12 * (0.5 + 0.5 * np.sin(S * 11.0))
    return x, y, z


def towel_grid(layer, ns=260, nt=420):
    """Сетка слоя полотенца: точки (nt+1, ns+1, 3) и маски (подгиб, строчка, полоса)."""
    S, T = np.meshgrid(np.linspace(0, 1, ns + 1), np.linspace(0, 1, nt + 1))
    x, y, z = towel_point(S, T, layer)
    width = TOWEL_W * (1.0 if layer == 0 else 0.93)
    length = TOWEL_L * (1.0 if layer == 0 else 0.80)
    # подгибы: подол и боковые кромки — двойной слой 2 см (валик 2.5 мм), строчка по нему: стежки 1.5 см
    ds = np.minimum(S, 1 - S) * width
    dt = (1 - T) * length
    hem_w = 2.0
    hem = np.maximum(sstep(hem_w + 0.4, hem_w - 0.2, dt), sstep(hem_w + 0.4, hem_w - 0.2, ds) * (T > 0.03))
    z = z + 0.25 * hem
    along = np.where(dt < ds, S * width, T * length)
    near = np.where(dt < ds, dt, ds)
    stitch_line = np.exp(-((near - 1.4) / 0.18) ** 2)
    stitch = stitch_line * sstep(0.35, 0.2, np.abs(((along / 2.0) % 1) - 0.5) - 0.12)
    z = z - 0.06 * stitch_line + 0.05 * stitch
    # кирпичные полосы у подола (тканые — без рельефа, только маска)
    stripe = ((T > 0.775) & (T < 0.855)) | ((T > 0.885) & (T < 0.907))
    P = np.stack([x, y, z], -1)
    return P, dict(hem=hem, stitch=stitch, stripe=stripe * 1.0)


# ------------------------------------------------------------------ лист
LEAVES = ((-62.0, 13.5, 8.0, 38.0), (-24.5, 33.0, 7.0, -64.0))      # x, y, длина, угол


def leaf_grid(L, rng, nu=60, nv=24):
    """Берёзовый лист: u вдоль (0 черешок .. L кончик), v поперёк. Жилки боковые мельче 3 px — только средняя (4 мм)."""
    U, V = np.meshgrid(np.linspace(0, 1, nu), np.linspace(-1, 1, nv), indexing="ij")
    W = 0.36 * L * (U ** 0.45) * (1 - U) ** 0.75 / (0.45 ** 0.45 * 0.55 ** 0.75) * 0.95
    W = W * (1 + 0.06 * np.sin(U * 18 + rng.uniform(0, 6)))
    x = U * L
    y = V * W
    vein = np.exp(-(np.abs(y) / 0.2) ** 2) * (U < 0.95)
    h = 0.12 * vein + 0.3 * np.abs(V) ** 2.2 + 0.15 * np.sin(U * np.pi) * rng.uniform(0.2, 1.0)
    return x, y, h, vein


# ------------------------------------------------------------------ прозрачные потёки
# Дорожки, где вода стёрла конденсат. Капля бежит не прямо: стоит, набирает воду и срывается вбок — путь ломаный,
# ширина неровная. Уроки v1.1/v1.3: без капли-головки наверху («спички»), без круглых дырок («пули»), без ровных
# параллельных полос («когти»); v2 черновик: одинаковые прямые дорожки + сплошная полоса внизу — «гребёнка».
# (u старта — доля ширины стекла слева направо на переде, v старта, v конца (0 — до низа), полуширина см,
#  сливается с дорожкой №, seed излома)
DRIPS = ((0.17, 0.91, 0.0, 0.95, None, 11), (0.47, 0.76, 0.0, 0.85, None, 12), (0.30, 0.55, 0.24, 0.8, 1, 13),
         (0.70, 0.84, 0.47, 0.9, None, 14), (0.90, 0.42, 0.0, 0.85, None, 15))
DRIP_MIN_HALF = 0.85           # 1.7 см ≈ 4 px при 1024 — уже нельзя: мипы закроют дырку


def _drip_nodes(k):
    """Узлы ломаного пути: (v, x) — капля стоит и срывается вбок на 0.4–1.6 см каждые 3–6 см."""
    u0, v0, v1, hw, join, sd = DRIPS[k]
    xi0, xi1, yi0, yi1 = PANE
    rng = np.random.default_rng(300 + sd)
    hgt = yi1 - yi0
    vs, xs = [v0], [xi0 + u0 * (xi1 - xi0)]
    v = v0
    while v > -0.05:
        v -= rng.uniform(3.0, 6.0) / hgt
        xs.append(xs[-1] + rng.choice((-1, 1)) * rng.uniform(0.4, 1.6))
        vs.append(v)
    return np.array(vs[::-1]), np.array(xs[::-1])


def _drip_x(k, v):
    vs, xs = _drip_nodes(k)
    # между узлами — плавно (капля течёт), у узла — излом
    i = np.clip(np.searchsorted(vs, v) - 1, 0, len(vs) - 2)
    t = np.clip((v - vs[i]) / (vs[i + 1] - vs[i]), 0, 1)
    t = sstep(0.15, 0.85, t)
    x = xs[i] * (1 - t) + xs[i + 1] * t
    u0, v0, v1, hw, join, sd = DRIPS[k]
    if join is not None:          # ниже v1 сворачивает в дорожку join
        xj = _drip_x(join, v)
        tj = sstep(v1 + 0.2, v1 - 0.02, v)
        x = x * (1 - tj) + xj * tj
    return x


def drip_cut(x, y):
    """1 там, где стекло прозрачно насквозь (вырез альфой), 0 — запотевшее. x, y — см; одни и те же для обеих сторон."""
    xi0, xi1, yi0, yi1 = PANE
    hgt = yi1 - yi0
    v = (y - yi0) / hgt
    cut = np.zeros(np.shape(x))
    for k, (u0, v0, v1, hw, join, sd) in enumerate(DRIPS):
        cx = _drip_x(k, v)
        vend = v1 if join is None else v1 - 0.01
        along = np.clip((v0 - v) / max(v0 - vend, 1e-3), 0, 1)
        half = np.maximum(hw * (0.85 + 0.3 * along) * (1 + 0.22 * (n2(v * 7.0, k * 5.3, 303) - 0.5) * 2), DRIP_MIN_HALF)
        half = half * (0.55 + 0.45 * sstep(v0, v0 - 0.05, v)) + 0.0          # старт сужается (без головки)
        # внизу вода растекается лужицей у замазки
        pool = sstep(yi0 + 3.2, yi0 + 1.4, y) * (vend <= 0.0)
        half = half * (1 + 0.55 * pool)
        dy = 0.0
        if vend > 0 and join is None:     # застрявшая капля: конец скруглён, той же ширины (не шар)
            yend = yi0 + vend * hgt
            dy = np.maximum(yend - y, 0.0)
            cx = np.where(y < yend, _drip_x(k, np.full(np.shape(v), vend)), cx)
        body = sstep(1.12, 0.88, np.hypot(x - cx, dy) / half) * (v <= v0)
        if join is not None:
            body = body * (v >= vend - 0.05)
        cut = np.maximum(cut, body)
    inside = (x > xi0 + 1.1) & (x < xi1 - 1.1) & (y > yi0 + 1.0) & (y < yi1 - 1.2)   # не под замазкой
    return cut * inside
