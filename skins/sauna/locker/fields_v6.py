"""Sauna Changing Locker v6: рельеф и маски поверхностей (numpy; общий для bake_v6.py в Blender и проверок в .venv).

План: PLAN_v6.md (разделы 3 и 8). Всё, что имеет форму, — здесь: поле высот h (см, сдвиг по нормали грани наружу) и
маски цвета из тех же функций (рельеф и цвет совпадают пиксель в пиксель).

Координаты — как в originals/locker.obj: x вправо, y вверх, z к игроку, сантиметры.
Плотность: 5.1 px/см в 2048 (1 px ≈ 2 мм), запекание 4096. Детали — не мельче 7–8 мм, глубины 0.2–1 мм (см. план, 1.3).

Каналы атрибутов вершин (bake_v6.py -> bake/v6/<имя>.png):
  m1  = (волокно | раковина, полость, вмятина)
  m2  = (шляпка гвоздя/болта, сучок, покрытие: эмаль/краска 0..1)
  m3  = (кромка: износ/скол/кайма, разное: царапина/полировка/шкала/полоса, тон доски 0..1)
  idc = (код материала / 32, номер доски / 16, свечение 0..1)
  pos = мировые координаты, нормированные (POS_LO..POS_HI)
"""
import numpy as np

STEP = 0.15                          # шаг сетки high-poly, см
POS_LO = np.array([-100.0, -10.0, -45.0])
POS_HI = np.array([100.0, 235.0, 45.0])

MAT = {"side": 1, "niche": 2, "board": 3, "ledge": 4, "gap": 5, "nail": 6, "steel": 7, "brass": 8, "glass": 9,
       "dial": 10, "plate": 11, "mud": 12, "leaf": 13, "towel": 14, "twig": 15, "twine": 16, "peg": 17, "lamp": 18,
       "glow": 19, "grate": 20, "shelf": 21, "frame": 22, "split": 23, "stub": 24}


# ------------------------------------------------------------------ шум (как в bed/fields_v2.py)
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


def voronoi(x, y, cell, seed):
    ix, iy = np.floor(x / cell).astype(np.int64), np.floor(y / cell).astype(np.int64)
    f1 = np.full(x.shape, 1e9)
    f2 = np.full(x.shape, 1e9)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            cx, cy = ix + dx, iy + dy
            h = (cx * 73856093) ^ (cy * 19349663) ^ (seed * 83492791)
            h = (h ^ (h >> 13)) * 1274126177
            jx = ((h & 0xFFFF) / 65535.0) * 0.8 + 0.1
            jy = (((h >> 16) & 0xFFFF) / 65535.0) * 0.8 + 0.1
            d = np.hypot(x - (cx + jx) * cell, y - (cy + jy) * cell)
            f2 = np.where(d < f1, f1, np.minimum(f2, d))
            f1 = np.minimum(f1, d)
    return f1, f2


def round_drop(d, r):
    """Скругление кромки радиусом r: насколько поверхность опущена на расстоянии d от кромки."""
    t = np.minimum(np.clip(r - d, 0, None), r)
    return r - np.sqrt(np.maximum(r * r - t * t, 0))


def grain_relief(along, across, depth0, tilt, c, s, seed, knots=()):
    """Гребни поздней древесины 0..1 (арки тангентальной доски); knots: [(along, across, r)] — волокна огибают."""
    warp = 0.45 * (fbm2(along * 0.025, across * 0.12, seed, 3) - 0.5) + 0.12 * (n2(along * 0.12, across * 0.5, seed + 3) - 0.5)
    d = depth0 + tilt * along + 0.6 * warp
    ph = np.sqrt((across - c) ** 2 + d * d) / s + warp
    for (ka, kc, kr) in knots:
        dd = np.hypot((along - ka) / 1.5, across - kc)
        ph = ph + 0.9 * kr * np.exp(-(dd / (2.2 * kr)) ** 2) / s
    f = ph - np.floor(ph)
    return np.exp(-((f - 0.82) / 0.11) ** 2) + np.exp(-((f + 1 - 0.82) / 0.11) ** 2) + np.exp(-((f - 1.82) / 0.11) ** 2)


# ------------------------------------------------------------------ поле: словарь каналов
class Field:
    KEYS = ("grain", "cav", "dent", "nail", "knot", "coat", "edge", "misc", "tone", "board", "glow")

    def __init__(self, shape, mat):
        self.h = np.zeros(shape)
        for k in self.KEYS:
            setattr(self, k, np.zeros(shape))
        self.mat = np.full(shape, MAT[mat], np.int32)

    def put(self, mask, **kw):
        """Записать значения каналов там, где mask (bool или 0..1 > 0.5)."""
        m = mask if mask.dtype == bool else mask > 0.5
        for k, v in kw.items():
            if k == "mat":
                self.mat = np.where(m, MAT[v], self.mat)
            else:
                cur = getattr(self, k)
                setattr(self, k, np.where(m, v, cur))

    def mx(self, **kw):
        for k, v in kw.items():
            setattr(self, k, np.maximum(getattr(self, k), v))

    def attrs(self, P):
        pos = (P - POS_LO) / (POS_HI - POS_LO)
        return {"m1": np.stack([self.grain, np.clip(self.cav, 0, 1), np.clip(self.dent, 0, 1)], -1),
                "m2": np.stack([np.clip(self.nail, 0, 1), np.clip(self.knot, 0, 1), np.clip(self.coat, 0, 1)], -1),
                "m3": np.stack([np.clip(self.edge, 0, 1), np.clip(self.misc, 0, 1), np.clip(self.tone, 0, 1)], -1),
                "idc": np.stack([self.mat / 32.0, self.board / 16.0, np.clip(self.glow, 0, 1)], -1),
                "pos": np.clip(pos, 0, 1)}


# ------------------------------------------------------------------ общие детали дерева
def boards_layout(a0, a1, widths, seed):
    """Раскладка досок поперёк [a0, a1]: список (лево, право, параметры)."""
    rng = np.random.default_rng(seed)
    w = np.asarray(widths, float)
    w = w * (a1 - a0) / w.sum()
    out, a = [], a0
    for i, wi in enumerate(w):
        out.append(dict(lo=a, hi=a + wi, seed=int(rng.integers(10000)), d0=rng.uniform(1.0, 3.2),
                        tilt=rng.uniform(0.008, 0.025) * rng.choice((-1, 1)), c=a + wi * rng.uniform(0.25, 0.75),
                        s=rng.uniform(0.8, 1.25), amp=rng.uniform(0.07, 0.11), tone=rng.random(), i=i))
        a += wi
    return out


def vagonka(fl, along, across, layout, chamfer=0.45, depth=0.28, gap=0.12, knots=(), amp_k=1.0):
    """Вертикальная (или любая) вагонка: доски вдоль along, раскладка по across. V-шпунт на стыках, волокна, сучки.
    knots: [(along, across, r)]. Пишет в fl.h, grain, cav, knot, tone, board; возвращает расстояние до стыка."""
    dj = np.full(along.shape, 1e9)
    for b in layout:
        inb = (across >= b["lo"]) & (across < b["hi"])
        if not inb.any():
            continue
        kk = [(ka, kc, kr) for (ka, kc, kr) in knots if b["lo"] < kc < b["hi"]]
        g = grain_relief(along[inb], across[inb], b["d0"], b["tilt"], b["c"], b["s"], b["seed"], kk)
        fl.h[inb] += b["amp"] * amp_k * (g - 0.35)
        fl.grain[inb] = g
        fl.tone[inb] = b["tone"]
        fl.board[inb] = b["i"] + 1
        d = np.minimum(across[inb] - b["lo"], b["hi"] - across[inb])
        dj[inb] = d
    # V-шпунт: фаски к стыку, в середине щель
    ch = np.clip(1 - dj / chamfer, 0, 1)
    fl.h -= depth * ch ** 1.4
    slot = dj < gap
    fl.h = np.where(slot, fl.h - 0.5, fl.h)
    fl.cav = np.maximum(fl.cav, np.clip(1 - dj / (gap * 2.2), 0, 1))
    for (ka, kc, kr) in knots:                            # сучок: твёрдое кольцо, тёмная середина
        dd = np.hypot((along - ka) / 1.25, across - kc)
        k = sstep(kr, kr * 0.75, dd)
        fl.h += 0.06 * k - 0.05 * np.exp(-((dd - kr) / 0.12) ** 2)
        fl.knot = np.maximum(fl.knot, k)
    return dj


def crack(fl, along, across, a0, a1, c0, depth, hw, seed):
    """Трещина вдоль волокна: V-борозда с мягкими концами (раскрытие 2·hw)."""
    box = (along > a0 - 1) & (along < a1 + 1) & (np.abs(across - c0) < 2.5)
    if not box.any():
        return
    t = np.clip((along[box] - a0) / (a1 - a0), 0, 1)
    cc = c0 + 0.35 * (n2(along[box] * 0.15, seed, seed) - 0.5)
    prof = np.sin(np.pi * t) ** 0.6
    g = np.clip(1 - np.abs(across[box] - cc) / (hw * prof + 1e-3), 0, 1)
    fl.h[box] -= depth * prof * g ** 0.8
    fl.cav[box] = np.maximum(fl.cav[box], g * prof)


def dent(fl, a, b, A, B, r, d):
    u = np.clip(1 - ((A - a) ** 2 + (B - b) ** 2) / r ** 2, 0, 1) ** 2
    fl.h -= d * u
    fl.dent = np.maximum(fl.dent, u)


def nail_round(fl, a, b, A, B, r=0.65, lift=0.12, smile=None, base=0.0):
    """Круглая кованая шляпка (купол), вокруг — смятое дерево; smile — угол дуги промаха молотком."""
    dd = np.hypot(A - a, B - b)
    m = dd < r * 3
    if not m.any():
        return
    dome = np.sqrt(np.clip(1 - (dd / r) ** 2, 0, 1))
    fl.h -= 0.03 * np.clip(1 - ((dd - r * 1.25) / (r * 0.6)) ** 2, 0, 1)
    fl.h = np.where(dd < r, np.maximum(fl.h, base + lift * 0.35 + lift * dome), fl.h)
    fl.nail = np.maximum(fl.nail, sstep(r * 1.03, r * 0.9, dd))
    fl.put(dd < r * 0.97, mat="nail")
    if smile is not None:
        cx, cy = a + 1.3 * np.cos(smile), b + 1.3 * np.sin(smile)
        ds = np.hypot(A - cx, B - cy)
        arc = np.exp(-((ds - 0.85) / 0.16) ** 2) * (np.cos(np.arctan2(B - cy, A - cx) - smile - np.pi) > 0.2)
        fl.h -= 0.05 * arc
        fl.dent = np.maximum(fl.dent, arc)


def edge_wear(fl, d, r, k=1.0):
    """Скругление кромки радиусом r на расстоянии d от неё + маска износа кромки."""
    fl.h -= round_drop(np.maximum(d, 0), r)
    fl.edge = np.maximum(fl.edge, k * sstep(r * 1.4, 0.0, d))


def steel_surface(fl, U, V, de, seed, chip=0.25, r_edge=0.6):
    """Старая эмаль на стали: слой 0.03, сколы у кромок (de — расстояние до кромки), раковины в голом металле."""
    # эмаль почти цела; сколы мелкие (2–6 см), гуще у кромок — крупные пятна в игре читаются «камуфляжем» (§9.6)
    en_n = fbm2(U * 0.24, V * 0.24, seed, 4) + 0.12 * (n2(U * 1.1, V * 1.1, seed + 1) - 0.5) - chip * sstep(1.3, 0.0, de)
    en = sstep(0.28, 0.287, en_n)
    fl.coat = en
    fl.edge = np.maximum(fl.edge, sstep(0.25, 0.28, en_n) * (1 - en))
    f1, _ = voronoi(U, V, 0.75, seed + 3)
    nest = sstep(0.42, 0.62, fbm2(U * 0.08, V * 0.08, seed + 5, 3)) * (1 - en)
    rr = 0.18 + 0.2 * n2(np.floor(U / 0.75), np.floor(V / 0.75), seed + 7)
    pit = np.clip(1 - (f1 / rr) ** 2, 0, 1) * nest
    b1, _ = voronoi(U, V, 3.5, seed + 9)
    blist = np.clip(1 - (b1 / 0.9) ** 2, 0, 1) * en * sstep(0.8, 0.86, n2(np.floor(U / 3.5) * 1.3, np.floor(V / 3.5) * 1.7, seed + 11))
    fl.h += 0.03 * en - 0.06 * pit + 0.05 * blist + 0.012 * (fbm2(U * 0.4, V * 0.4, seed + 13, 2) - 0.5)
    fl.grain = np.maximum(fl.grain, pit)
    fl.knot = np.maximum(fl.knot, blist)          # у стали: пузырь ржавчины под эмалью
    edge_wear(fl, de, r_edge, 0.0)


# ------------------------------------------------------------------ основа поля по граням low-poly
def faces_base(A, B, polys, k):
    """Высота поверхности low-poly вдоль оси k (наружу — max) в точках (A, B) других двух осей.
    polys: список (n, 3) вершин граней. NaN там, где граней нет."""
    ia, ib = [i for i in range(3) if i != k]
    out = np.full(A.shape, -1e9)
    for P in polys:
        P = np.asarray(P, float)
        n = np.cross(P[1] - P[0], P[2] - P[0])
        if abs(n[k]) < 1e-3 * np.linalg.norm(n):
            continue
        a, b = P[:, ia], P[:, ib]
        lo_a, hi_a, lo_b, hi_b = a.min(), a.max(), b.min(), b.max()
        m = (A >= lo_a - 1e-4) & (A <= hi_a + 1e-4) & (B >= lo_b - 1e-4) & (B <= hi_b + 1e-4)
        if not m.any():
            continue
        Am, Bm = A[m], B[m]
        inside = np.zeros(Am.shape, bool)
        for t in range(1, len(P) - 1):            # веер треугольников
            (xa, ya), (xb, yb), (xc, yc) = (a[0], b[0]), (a[t], b[t]), (a[t + 1], b[t + 1])
            det = (yb - yc) * (xa - xc) + (xc - xb) * (ya - yc)
            if abs(det) < 1e-9:
                continue
            l1 = ((yb - yc) * (Am - xc) + (xc - xb) * (Bm - yc)) / det
            l2 = ((yc - ya) * (Am - xc) + (xa - xc) * (Bm - yc)) / det
            l3 = 1 - l1 - l2
            inside |= (l1 >= -1e-4) & (l2 >= -1e-4) & (l3 >= -1e-4)
        val = P[0, k] - (n[ia] * (Am - P[0, ia]) + n[ib] * (Bm - P[0, ib])) / n[k]
        cur = out[m]
        out[m] = np.where(inside, np.maximum(cur, val), cur)
    return np.where(out < -1e8, np.nan, out)


# ================================================================== СРЕДНЯЯ ДВЕРЦА, ПЕРЕД (#67)
DOOR_X = (-26.7, 25.6)
DOOR_Y = (48.0, 219.6)
DOOR_BOARDS = ((-26.7, -9.2), (-9.2, 9.05), (9.05, 25.6))
DOOR_TOP = (218.8, 219.6, 217.6)
LEDGES = ((61.0, 69.1), (127.8, 135.9), (191.7, 199.8))
WINDOW = (-15.5, 15.5, 160.0, 191.4)           # рама снаружи: x0, x1, y0, y1
GAUGES = ((-8.6, 208.9, 1), (8.6, 208.9, 2))    # центр x, y; 1 — термометр, 2 — гигрометр
GAUGE_R = (6.6, 5.25)                           # ободок: внешний, внутренний радиус
LOCK = (2.0, 102.0)                             # центр игрового замка (проверено в v5)
PLATE = (6.4, 7.4)                              # полуразмеры стальной площадки
BOOTS = ((-17.5, 99.0, -0.18, 1.0), (-4.5, 75.5, 0.12, 0.55))     # x, y, поворот, полнота отпечатка
SPLIT = (18.6, 70.5, 101.0)                     # x, y0, y1 — трещина-пролом правой доски
DOOR_LEAF = (17.2, 113.0, 1.9)                  # лист: x, y, угол
TALLY = (6.0, 131.85)                           # зарубки 2 × 5 на средней поперечине


def door_front(X, Y, Z0):
    """X, Y — сетка; Z0 — поверхность low-poly (faces_base, ось z). Возвращает Field (h — вдоль +z)."""
    fl = Field(X.shape, "board")
    rng = np.random.default_rng(67)
    ledge = Z0 > 28.1
    bi = np.digitize(X, [DOOR_BOARDS[0][1], DOOR_BOARDS[1][1]])            # 0, 1, 2
    # ---- доски: волокна вдоль y, тон и сучки по доске
    for i, (x0, x1) in enumerate(DOOR_BOARDS):
        m = (bi == i) & ~ledge
        if not m.any():
            continue
        sd = 600 + i * 17
        r2 = np.random.default_rng(sd)
        kn = [(r2.uniform(80, 180), r2.uniform(x0 + 3, x1 - 3), r2.uniform(0.6, 1.3)) for _ in range(2)]
        g = grain_relief(Y[m], X[m], r2.uniform(1.2, 3.0), r2.uniform(0.008, 0.02), r2.uniform(x0 + 4, x1 - 4),
                         r2.uniform(0.9, 1.3), sd, kn)
        fl.h[m] += 0.065 * (g - 0.35)
        fl.grain[m] = g
        fl.tone[m] = (0.2, 0.75, 0.45)[i]
        fl.board[m] = i + 1
        for (ka, kc, kr) in kn:
            dd = np.hypot((Y[m] - ka) / 1.25, X[m] - kc)
            k = sstep(kr, kr * 0.75, dd)
            fl.h[m] += 0.06 * k - 0.05 * np.exp(-((dd - kr) / 0.12) ** 2)
            fl.knot[m] = np.maximum(fl.knot[m], k)
        # стыки досок: фаска + щель
        dj = np.minimum(X[m] - x0 if i > 0 else 99, x1 - X[m] if i < 2 else 99)
        fl.h[m] -= 0.3 * np.clip(1 - dj / 0.4, 0, 1) ** 1.4
        fl.cav[m] = np.maximum(fl.cav[m], np.clip(1 - dj / 0.25, 0, 1))
        fl.h[m] = np.where(dj < 0.1, fl.h[m] - 0.6, fl.h[m])
        # верхний торец и нижняя кромка скруглены, низ размочален
        top = DOOR_TOP[i]
        fl.h[m] -= round_drop(np.maximum(top - Y[m], 0), 0.5)
        fl.edge[m] = np.maximum(fl.edge[m], sstep(0.8, 0.0, top - Y[m]))
        low = sstep(6.0, 0.0, Y[m] - DOOR_Y[0])
        fl.h[m] -= low * 0.12 * sstep(0.45, 0.75, n2(X[m] * 2.2, Y[m] * 0.35, sd + 5))
        fl.h[m] -= round_drop(np.maximum(Y[m] - DOOR_Y[0], 0), 0.6)
        fl.h[m] -= round_drop(np.maximum(np.minimum(X[m] - DOOR_X[0], DOOR_X[1] - X[m]), 0), 0.45)
    # трещины усушки по доскам (крупные, видно с 3 м)
    for (x, y0, y1) in ((-20.5, 140.0, 158.0), (-3.0, 103.0, 121.0), (-13.0, 72.0, 86.0), (14.0, 141.0, 152.0),
                        (21.0, 203.0, 215.0)):
        crack(fl, Y, X, y0, y1, x, 0.6, 0.2, int(x * 10 + y0))
    # ---- поперечины: волокна вдоль x, кромки скруглены, по 3 шляпки
    for j, (y0, y1) in enumerate(LEDGES):
        m = ledge & (Y > y0 - 0.5) & (Y < y1 + 0.5)
        g = grain_relief(X[m], Y[m], 2.2 + j, 0.01, (y0 + y1) / 2 + 0.6, 1.0, 700 + j)
        fl.h[m] += 0.1 * (g - 0.35)
        fl.grain[m] = g
        fl.tone[m] = 0.55 + 0.15 * j
        fl.board[m] = 4 + j
        fl.put(m, mat="ledge")
        dy = np.minimum(Y[m] - y0, y1 - Y[m])
        dx = np.minimum(X[m] - DOOR_X[0], DOOR_X[1] - X[m])
        fl.h[m] -= round_drop(np.maximum(dy, 0), 0.45) + round_drop(np.maximum(dx, 0), 0.5)
        fl.edge[m] = np.maximum(fl.edge[m], sstep(0.9, 0.0, np.minimum(dy, dx)))
        for kx in (-20.5, -1.0, 19.5):
            if j == 1 and kx > 0:
                kx = 21.2
            nail_round(fl, kx + rng.uniform(-0.6, 0.6), (y0 + y1) / 2 + rng.uniform(-0.5, 0.5), X, Y, r=0.68, lift=0.14,
                       smile=rng.uniform(0, 6.3) if rng.random() < 0.5 else None)
        crack(fl, X, Y, DOOR_X[0] + 1, DOOR_X[0] + rng.uniform(5, 9), (y0 + y1) / 2 + rng.uniform(-1.5, 1.5), 0.4, 0.18, 710 + j)
    # зарубки на средней поперечине: 2 × (4 прямых + 1 косая)
    tx, ty = TALLY
    for grp in range(2):
        for k in range(5):
            cx = tx + grp * 6.2 + k * 0.95
            if k < 4:
                ax, ang, L = cx, 0.0, 3.6
            else:
                ax, ang, L = tx + grp * 6.2 + 1.45, 0.75, 5.2
            ca, sa = np.cos(ang), np.sin(ang)
            u = (X - ax) * ca - (Y - ty) * sa                      # поперёк зарубки
            v = (X - ax) * sa + (Y - ty) * ca                      # вдоль
            prof = np.clip(1 - np.abs(u) / 0.32, 0, 1) * sstep(L / 2, L / 2 - 0.6, np.abs(v))
            fl.h -= 0.32 * prof
            fl.cav = np.maximum(fl.cav, prof ** 1.5)
    # ---- окно: рама с фаской, штапик, стекло утоплено; капли и потёки воды — формой
    wx0, wx1, wy0, wy1 = WINDOW
    din = np.minimum(np.minimum(X - wx0, wx1 - X), np.minimum(Y - wy0, wy1 - Y))
    inwin = din > 0
    frame = inwin & (din < 3.0)
    bead = inwin & (din >= 3.0) & (din < 3.8)
    glass = inwin & (din >= 3.8)
    fr_h = 1.05 - round_drop(np.clip(din, 0, None), 0.35) - round_drop(np.clip(3.0 - din, 0, None), 0.3)
    gw = grain_relief(np.where(np.abs(X) > np.abs(Y - (wy0 + wy1) / 2), Y, X),
                      np.where(np.abs(X) > np.abs(Y - (wy0 + wy1) / 2), X, Y), 1.8, 0.01, 0.0, 0.9, 731)
    # рама в «ус»: диагональные стыки по углам
    cxw, cyw = (wx0 + wx1) / 2, (wy0 + wy1) / 2
    hx, hy = (wx1 - wx0) / 2, (wy1 - wy0) / 2
    diag = np.abs(np.abs(X - cxw) - hx - (np.abs(Y - cyw) - hy))
    fl.h = np.where(frame, fl.h * 0.2 + fr_h + 0.07 * (gw - 0.35) - 0.15 * np.clip(1 - diag / 0.12, 0, 1), fl.h)
    fl.cav = np.where(frame, np.clip(1 - diag / 0.1, 0, 1), fl.cav)
    fl.put(frame, mat="frame", tone=0.4, board=7, knot=0.0, nail=0.0)
    fl.grain = np.where(frame, gw, fl.grain)
    fl.edge = np.where(frame, np.maximum(sstep(0.5, 0.0, din), sstep(2.5, 3.0, din)), fl.edge)
    fl.h = np.where(bead, 0.45 - round_drop(np.clip(3.8 - din, 0, None), 0.35), fl.h)
    fl.put(bead, mat="frame", tone=0.5, board=7, edge=0.6)
    gxy = np.stack([X, Y], -1)
    gl_h = np.full(X.shape, -0.3)
    wet = np.zeros(X.shape)
    for (dx, dy, r) in [(rng.uniform(wx0 + 4, wx1 - 4), rng.uniform(wy0 + 4, wy1 - 4), rng.uniform(0.25, 0.45)) for _ in range(38)]:
        dd = np.hypot(X - dx, Y - dy)
        drop = np.sqrt(np.clip(1 - (dd / r) ** 2, 0, 1))
        gl_h = np.maximum(gl_h, -0.3 + 0.07 * drop)
        wet = np.maximum(wet, sstep(r, r * 0.6, dd))
    # сердечко (пальцем по запотевшему стеклу: формы нет — маска) и потёки из него (валики воды — форма)
    hx_, hy_ = (X - cxw) / 6.0, (Y - (cyw + 0.8)) / 6.0
    q = (hx_ ** 2 + hy_ ** 2 - 1) ** 3 - hx_ ** 2 * hy_ ** 3
    heart = sstep(0.06, 0.0, np.abs(q) * 3.0) * glass
    for (rx, ry, L) in ((-1.6, -5.1, 9.0), (0.4, -5.9, 12.5), (1.9, -4.6, 7.0), (-4.4, -2.6, 5.5)):
        x0r = cxw + rx
        y0r = cyw + 0.8 + ry
        t = np.clip((y0r - Y) / L, 0, 1)
        run = np.exp(-((X - x0r - 0.15 * np.sin(t * 6)) / (0.34 * (1 - 0.4 * t))) ** 2) * (Y < y0r) * (Y > y0r - L)
        bulb = np.sqrt(np.clip(1 - ((X - x0r) ** 2 + (Y - (y0r - L)) ** 2) / 0.45 ** 2, 0, 1))
        gl_h = np.maximum(gl_h, -0.3 + 0.05 * run + 0.08 * bulb)
        heart = np.maximum(heart, np.maximum(run, sstep(0.45, 0.3, np.hypot(X - x0r, Y - (y0r - L)))) * glass)
    fl.h = np.where(glass, gl_h, fl.h)
    fl.put(glass, mat="glass", grain=0.0, knot=0.0, nail=0.0, cav=0.0, edge=0.0, board=8)
    fl.misc = np.where(glass, np.maximum(heart, wet * 0.6), fl.misc)
    fl.glow = np.where(glass, 1.0, fl.glow)
    # ---- приборы: латунный ободок с тремя шурупами, купол стекла; шкала под стеклом — маска
    for (gx, gy, kind) in GAUGES:
        dd = np.hypot(X - gx, Y - gy)
        ro, ri = GAUGE_R
        ring = (dd < ro) & (dd >= ri)
        prof = np.sqrt(np.clip(1 - ((dd - (ro + ri) / 2) / ((ro - ri) / 2 + 0.08)) ** 2, 0, 1))
        base = fl.h.copy()
        fl.h = np.where(ring, np.maximum(base, 0.2 + 0.55 * prof), fl.h)
        ang = np.arctan2(Y - gy, X - gx)
        for a in (np.pi / 2, np.pi / 2 + 2.094, np.pi / 2 - 2.094):
            sx, sy = gx + (ro + ri) / 2 * np.cos(a), gy + (ro + ri) / 2 * np.sin(a)
            ds = np.hypot(X - sx, Y - sy)
            fl.h = np.where(ds < 0.42, np.maximum(fl.h, 0.75 + 0.12 * np.sqrt(np.clip(1 - (ds / 0.42) ** 2, 0, 1))), fl.h)
            fl.h -= 0.1 * (ds < 0.42) * (np.abs((X - sx) * np.cos(a + 0.4) + (Y - sy) * np.sin(a + 0.4)) < 0.09)
            fl.nail = np.maximum(fl.nail, sstep(0.45, 0.38, ds))
        fl.put(ring, mat="brass", board=8 + kind, grain=0.0, knot=0.0, cav=0.0)
        fl.edge = np.where(ring, prof, fl.edge)
        face = dd < ri
        dome = np.sqrt(np.clip(1 - (dd / ri) ** 2, 0, 1))
        fl.h = np.where(face, 0.25 + 0.3 * dome, fl.h)
        fl.put(face, mat="dial", board=8 + kind, grain=0.0, knot=0.0, cav=0.0, nail=0.0)
        # шкала: риски по дуге 270°, цветная зона, стрелка (маски; под стеклом формы не видно)
        a_rel = (np.pi * 1.25 - ang) % (2 * np.pi)                  # 0 .. 1.5π по часовой от левого низа
        on_arc = a_rel < 1.5 * np.pi
        tick_ph = (a_rel / (1.5 * np.pi) * 20) % 1.0
        ticks = on_arc & (np.minimum(tick_ph, 1 - tick_ph) < 0.09) & (dd > ri * 0.66) & (dd < ri * 0.86)
        zone = on_arc & (dd > ri * 0.86) & (dd < ri * 0.96) & ((a_rel > 1.05 * np.pi) if kind == 1 else (a_rel < 0.45 * np.pi))
        needle_a = 1.5 * np.pi * (0.78 if kind == 1 else 0.35)
        na = np.pi * 1.25 - needle_a
        u = (X - gx) * np.cos(na) + (Y - gy) * np.sin(na)
        v = -(X - gx) * np.sin(na) + (Y - gy) * np.cos(na)
        needle = (u > -0.8) & (u < ri * 0.82) & (np.abs(v) < 0.1 + 0.08 * (u < 0.3)) | (dd < 0.35)
        fl.misc = np.where(face, np.maximum(ticks * 0.6, needle * 1.0), fl.misc)
        fl.edge = np.where(face, zone * 1.0, fl.edge)
    # ---- стальная площадка под замок со скважиной старого врезного замка
    lx, ly = LOCK
    px, py = PLATE
    dpl = np.minimum(px - np.abs(X - lx), py - np.abs(Y - ly))
    cr = 0.9
    qx, qy = np.maximum(np.abs(X - lx) - (px - cr), 0), np.maximum(np.abs(Y - ly) - (py - cr), 0)
    dround = cr - np.hypot(qx, qy)
    dpl = np.where((qx > 0) & (qy > 0), dround, dpl)
    plate = dpl > 0
    # затёртое руками дерево вокруг: гребни волокон сглажены
    hand = sstep(16.0, 6.0, np.hypot((X - lx) * 1.1, Y - ly)) * ~ledge
    fl.h -= hand * 0.06 * (fl.grain - 0.35)
    fl.misc = np.where(~plate & ~glass, np.maximum(fl.misc, hand), fl.misc)
    pu, pv = X - lx, Y - ly
    fl.h = np.where(plate, 0.28 - round_drop(np.clip(dpl, 0, None), 0.25), fl.h)
    fl.put(plate, mat="plate", board=11, grain=0.0, knot=0.0, cav=0.0, edge=0.0, misc=0.0)
    sp = Field(X.shape, "plate")
    steel_surface(sp, pu, pv, np.clip(dpl, 0, None), 1101, chip=0.35, r_edge=0.25)
    fl.h = np.where(plate, fl.h + sp.h * 0.8, fl.h)
    fl.coat = np.where(plate, sp.coat, fl.coat)
    fl.grain = np.where(plate, sp.grain, fl.grain)
    fl.edge = np.where(plate, sp.edge, fl.edge)
    for (bx, by) in ((-px + 1.3, -py + 1.3), (px - 1.3, -py + 1.3), (-px + 1.3, py - 1.3), (px - 1.3, py - 1.3)):
        dd = np.hypot(pu - bx, pv - by)
        ang = np.arctan2(pv - by, pu - bx)
        hexr = 0.62 / np.cos(((ang + 0.2) % (np.pi / 3)) - np.pi / 6)
        head = dd < hexr
        fl.h = np.where(head, np.maximum(fl.h, 0.62 - 0.12 * sstep(0.2, 1.0, dd / hexr)), fl.h)
        fl.nail = np.maximum(fl.nail, head * 1.0)
    key = (np.hypot(pu, pv - 0.9) < 0.75) | ((np.abs(pu) < 0.33) & (pv > -1.6) & (pv < 0.9))
    fl.h = np.where(key & plate, -0.9, fl.h)
    fl.cav = np.where(plate, key * 1.0, fl.cav)
    # царапины ключом вокруг скважины: дуги 1.5–3.5 см, бороздки 0.35 см
    scr = np.zeros(X.shape)
    for _ in range(7):
        r0, a0, da = rng.uniform(1.2, 3.0), rng.uniform(0, 6.28), rng.uniform(0.3, 0.9)
        cxs, cys = rng.normal(0, 1.2), rng.normal(0.3, 1.2)
        dd = np.hypot(pu - cxs, pv - cys)
        an = (np.arctan2(pv - cys, pu - cxs) - a0) % (2 * np.pi)
        s = np.clip(1 - np.abs(dd - r0) / 0.17, 0, 1) * (an < da) * sstep(0.0, 0.15, an) * sstep(da, da - 0.15, an)
        scr = np.maximum(scr, s)
    fl.h -= 0.035 * scr * plate
    fl.misc = np.where(plate, scr, fl.misc)
    # ---- следы сапога: засохшая грязь 0.3–0.5 мм, грунтозацепы, под каблуком смятые волокна
    for (bx, by, ang, full) in BOOTS:
        ca, sa = np.cos(ang), np.sin(ang)
        u = (X - bx) * ca + (Y - by) * sa            # поперёк подошвы
        v = -(X - bx) * sa + (Y - by) * ca           # вдоль (носок вверху)
        fore = (u / 4.7) ** 2 + ((v - 4.6) / 8.0) ** 2 < 1
        heel = (u / 3.9) ** 2 + ((v + 8.9) / 3.8) ** 2 < 1
        waist = (np.abs(u - 0.6) < 3.0 - 0.25 * np.abs(v + 1.5)) & (v > -6.0) & (v < 0.0)
        sole = (fore | waist) & ~((v > -5.6) & (v < -4.4))                  # подъём: каблук отдельно
        sole = sole | heel
        # грунтозацепы: «ёлочка» на подошве, поперечные бруски на каблуке, канавка по оси
        row = np.floor((v + 20.0) / 1.7)
        blk = ((((u + 0.85 * (row % 2) + 20.0) % 1.7) < 1.05) & (((v + 20.0) % 1.7) < 1.05))
        rim = (np.abs(u) > 3.2) & (((v + 20.0) % 1.2) < 0.7)              # кант подошвы
        bars = ((v + 8.9) % 1.9) < 1.05
        lug = np.where(v < -4.4, bars, blk | rim)
        part = sstep(0.38, 0.62, fbm2(X * 0.22, Y * 0.22, int(bx * 7 + 3), 3) + 0.3 * (full - 0.6))
        mud = sole & lug & (part > 0.5) & ~plate & ~ledge
        film = sole & (part > 0.35) & ~plate & ~ledge                      # тонкая плёнка грязи между зацепами
        fl.h = np.where(mud, fl.h + 0.05, np.where(film, fl.h + 0.012, fl.h))
        fl.h -= 0.05 * (heel & ~ledge & ~plate)                            # каблук смял дерево
        fl.put(mud | film, mat="mud")
        fl.misc = np.where(mud | film, mud * 1.0 + film * 0.4, fl.misc)
        fl.dent = np.maximum(fl.dent, (sole & ~ledge & ~plate) * 0.5)
    # ---- пролом: продольная трещина правой доски с вырванной щепой; ночью изнутри свет
    sx, sy0, sy1 = SPLIT
    t = np.clip((Y - sy0) / (sy1 - sy0), 0, 1)
    open_w = 0.18 + 0.42 * np.sin(np.pi * t) ** 0.7
    cxs = sx + 0.6 * np.sin(t * 5.0) + 0.25 * (n2(Y * 0.5, 3.0, 81) - 0.5)
    ds = np.abs(X - cxs)
    inside = (ds < open_w) & (Y > sy0) & (Y < sy1)
    fl.h = np.where(inside, -1.3, fl.h - 0.25 * np.clip(1 - (ds - open_w) / 0.5, 0, 1) * ((Y > sy0) & (Y < sy1)))
    fl.put(inside, mat="split", glow=1.0, grain=0.0)
    fl.cav = np.maximum(fl.cav, np.clip(1 - (ds - open_w) / 0.4, 0, 1) * ((Y > sy0) & (Y < sy1)))
    for k in range(6):                               # щепа: тонкие пластинки по краю, приподняты
        y0 = rng.uniform(sy0 + 4, sy1 - 6)
        side = rng.choice((-1, 1))
        L = rng.uniform(1.8, 3.2)
        tt = np.clip((Y - y0) / L, 0, 1)
        xs = cxs + side * (open_w + 0.15 + 0.2 * tt)
        sp_m = (np.abs(X - xs) < 0.28) & (Y > y0) & (Y < y0 + L)
        fl.h = np.where(sp_m, fl.h + 0.12 + 0.12 * tt, fl.h)
        fl.edge = np.maximum(fl.edge, sp_m * 1.0)
    # ---- лист: пластина 0.8 мм, жилки валиком, края подвёрнуты
    lfx, lfy, la = DOOR_LEAF
    ca, sa = np.cos(la), np.sin(la)
    u = (X - lfx) * ca + (Y - lfy) * sa + 3.2
    v = -(X - lfx) * sa + (Y - lfy) * ca
    L = 6.6
    U = np.clip(u / L, 0, 1)
    W = 0.36 * L * (U ** 0.45) * (1 - U) ** 0.75 / (0.45 ** 0.45 * 0.55 ** 0.75) * 0.95
    W = W * (1 + 0.06 * np.sin(U * 26))
    leaf = (u > 0) & (u < L) & (np.abs(v) < W)
    vv = np.abs(v) / np.maximum(W, 1e-3)
    vein = np.exp(-(np.abs(v) / 0.11) ** 2)
    for k in range(1, 7):
        along = u - (0.14 * k * L + np.abs(v) * 0.95)
        vein = np.maximum(vein, 0.75 * np.exp(-(along / 0.1) ** 2) * (vv < 0.9))
    lh = 0.12 + 0.06 * vein + 0.18 * vv ** 2.2
    stem = (u < 0) & (u > -1.4) & (np.abs(v) < 0.12)
    fl.h = np.where(leaf, fl.h + lh, fl.h)
    fl.h = np.where(stem, fl.h + 0.12, fl.h)
    fl.put(leaf | stem, mat="leaf", board=0)
    fl.grain = np.where(leaf, vein, fl.grain)
    fl.tone = np.where(leaf, 0.8, fl.tone)
    # ---- вмятины и забоины по доскам (гуще внизу, где бьют ногой и ставят шайку)
    for _ in range(26):
        y = 50 + rng.pareto(1.6) * 25
        if y > 215:
            continue
        x = rng.uniform(-25, 24)
        r = min(0.6 + rng.pareto(2.0) * 0.6, 2.2)
        dent(fl, x, y, X, Y, r, 0.04 + 0.03 * r)
    return fl


# ================================================================== НИША (общие тексели трёх ниш)
NICHE_X = (-83.46, -36.74)        # видимая спинка
NICHE_Y = (15.45, 217.45)
NICHE_Z_BACK = -27.64
WALL_X = (-89.10, -30.82)         # стенки (большие грани)
WALL_Z = (-24.83, 21.42)
SHELF_Y = {"A": (81.42, 83.72), "B": (162.91, 165.22)}
SHELF_X = (-89.69, -30.23)
SHELF_Z = (-28.14, 20.22)
PEGS = ((-71.0, 151.0), (-49.5, 151.0))        # колышки: полотенце, веник
PEG_PROFILE = ((0.0, 1.9), (0.7, 1.9), (0.7, 1.15), (4.3, 1.15), (4.3, 1.65), (5.6, 1.65))   # (вылет, радиус)
LAMP = (-60.1, 193.0, 9.0, 6.0, 3.8)           # плафон: центр x, y, полуширина, полувысота, вылет


def peg_height(dd):
    """Высота точёного колышка над стеной (вид спереди) по расстоянию от оси."""
    h = np.where(dd < 1.9, 0.7 - round_drop(np.clip(1.9 - dd, 0, None), 0.3), -9.0)
    knob = np.where(dd < 1.65, 4.6 + 1.0 * np.sqrt(np.clip(1 - (dd / 1.65) ** 2, 0, 1)), -9.0)
    return np.maximum(h, knob)


def niche_back(X, Y):
    """Спинка ниши (z = −27.64, наружу +z): тёмная вагонка, колышки, плафон с решёткой."""
    fl = Field(X.shape, "niche")
    lay = boards_layout(*NICHE_X, [8.1, 7.4, 8.6, 7.8, 7.2, 7.6], 210)
    rng = np.random.default_rng(211)
    knots = [(rng.uniform(25, 140), rng.uniform(NICHE_X[0] + 3, NICHE_X[1] - 3), rng.uniform(0.6, 1.2)) for _ in range(4)]
    vagonka(fl, Y, X, lay, knots=knots, amp_k=1.3)
    for _ in range(3):
        x = rng.uniform(NICHE_X[0] + 2, NICHE_X[1] - 2)
        y0 = rng.uniform(20, 120)
        crack(fl, Y, X, y0, y0 + rng.uniform(10, 25), x, 0.5, 0.18, int(rng.integers(999)))
    for _ in range(10):
        dent(fl, rng.uniform(*NICHE_X), rng.uniform(40, 150), X, Y, rng.uniform(0.7, 1.8), rng.uniform(0.05, 0.1))
    # гвозди вагонки у пола и у потолка (по одному в доску; по высоте можно — копии не перевёрнуты)
    for b in lay:
        for yy in (20.5, 212.0):
            nail_round(fl, (b["lo"] + b["hi"]) / 2 + rng.uniform(-1, 1), yy + rng.uniform(-0.5, 0.5), X, Y, r=0.55, lift=0.08,
                       smile=rng.uniform(0, 6.3) if rng.random() < 0.3 else None)
    # колышки
    for (px, py) in PEGS:
        dd = np.hypot(X - px, Y - py)
        ph = peg_height(dd)
        on = ph > fl.h
        fl.h = np.where(on, ph, fl.h)
        fl.put(on, mat="peg", board=9, grain=0.0, knot=0.0, cav=0.0, nail=0.0)
        rings = np.exp(-(((dd / 0.33) % 1.0 - 0.7) / 0.15) ** 2) * (dd < 1.6)
        fl.grain = np.where(on, rings, fl.grain)
        fl.edge = np.where(on, sstep(1.2, 1.65, dd) * (dd < 1.65), fl.edge)
    # плафон: рамка 1.4 см, решётка из реек 0.9 см с зазорами 0.9 см, за ней светящееся матовое стекло
    lx, ly, hw, hh, dep = LAMP
    dl = np.minimum(hw - np.abs(X - lx), hh - np.abs(Y - ly))
    lamp = dl > 0
    rim = lamp & (dl < 1.4)
    inner = lamp & (dl >= 1.4)
    slat = inner & ((((X - lx) / 1.8) % 1.0) < 0.5)
    fl.h = np.where(rim, dep - round_drop(np.clip(dl, 0, None), 0.4) - round_drop(np.clip(1.4 - dl, 0, None), 0.2), fl.h)
    fl.h = np.where(slat, dep - 0.35 - round_drop(np.minimum(((X - lx) / 1.8) % 1.0, 0.5 - ((X - lx) / 1.8) % 1.0) * 1.8, 0.2), fl.h)
    gl = inner & ~slat
    fl.h = np.where(gl, dep - 1.6, fl.h)
    fl.put(rim | slat, mat="lamp", board=10, knot=0.0, nail=0.0, cav=0.0)
    fl.put(gl, mat="glow", glow=1.0, board=10, grain=0.0)
    fl.grain = np.where(rim | slat, 0.5 + 0.5 * np.sin(Y * 3.0 + X), fl.grain)
    for (sx, sy) in ((lx - hw + 0.7, ly - hh + 0.7), (lx + hw - 0.7, ly - hh + 0.7), (lx - hw + 0.7, ly + hh - 0.7),
                     (lx + hw - 0.7, ly + hh - 0.7)):
        dd = np.hypot(X - sx, Y - sy)
        fl.h = np.where(dd < 0.42, np.maximum(fl.h, dep + 0.12), fl.h)
        fl.nail = np.maximum(fl.nail, sstep(0.45, 0.38, dd))
    return fl


def niche_wall(Zc, Y, flip=False):
    """Стенка ниши (вид с x = −30.82 наружу −x; другая копия — та же развёртка вверх ногами).
    Только то, что не зависит от «верха»: вагонка по высоте, сучки, вмятины, без брусков под полки."""
    fl = Field(Zc.shape, "niche")
    lay = boards_layout(WALL_Z[0] - 6.0, WALL_Z[1] + 4.6, [8.0, 8.6, 7.4, 8.2, 7.8, 8.4, 7.9], 220)
    rng = np.random.default_rng(221)
    knots = [(rng.uniform(40, 190), rng.uniform(WALL_Z[0] + 3, WALL_Z[1] - 3), rng.uniform(0.6, 1.1)) for _ in range(4)]
    vagonka(fl, Y, Zc, lay, knots=knots, amp_k=1.3)
    for _ in range(3):
        zc = rng.uniform(*WALL_Z)
        y0 = rng.uniform(30, 170)
        crack(fl, Y, Zc, y0, y0 + rng.uniform(10, 25), zc, 0.5, 0.18, int(rng.integers(999)))
    for _ in range(8):
        dent(fl, rng.uniform(*WALL_Z), rng.uniform(30, 200), Zc, Y, rng.uniform(0.7, 1.6), rng.uniform(0.05, 0.09))
    return fl


def niche_floor(X, Zc):
    """Пол ниши: решётка-трап — 6 реек поперёк ниши на двух лагах; в щелях пол темнее."""
    fl = Field(X.shape, "grate")
    rng = np.random.default_rng(231)
    H = np.full(X.shape, 0.0)
    lags = (-75.5, -44.5)
    lag = np.zeros(X.shape, bool)
    for lx in lags:
        d = 2.0 - np.abs(X - lx)
        m = d > 0
        H = np.where(m, np.maximum(H, 1.4 - round_drop(np.clip(d, 0, None), 0.3)), H)
        lag |= m
    z0, z1 = WALL_Z[0] + 0.6, WALL_Z[1] - 0.4
    n = 6
    gap = 1.5
    w = (z1 - z0 - gap * (n - 1)) / n
    slat_m = np.zeros(X.shape, bool)
    for i in range(n):
        a = z0 + i * (w + gap)
        d = np.minimum(np.minimum(Zc - a, a + w - Zc), np.minimum(X - (NICHE_X[0] - 4.5), (NICHE_X[1] + 4.5) - X))
        m = d > 0
        g = grain_relief(X, Zc, 1.5 + i * 0.4, 0.015, a + w * 0.4, 1.0, 240 + i)
        hs = 2.6 - round_drop(np.clip(d, 0, None), 0.45) + 0.09 * (g - 0.35)
        H = np.where(m, hs, H)
        fl.grain = np.where(m, g, fl.grain)
        fl.tone = np.where(m, rng.random(), fl.tone)
        fl.board = np.where(m, i + 1, fl.board)
        fl.edge = np.where(m, sstep(0.8, 0.0, d), fl.edge)
        slat_m |= m
        for lx in lags:                                     # гвозди в лаги
            nail_round(fl, lx + rng.uniform(-0.3, 0.3), a + w / 2, X, Zc, r=0.5, lift=0.07)
    fl.h = H + np.where(slat_m, fl.h, 0)
    under = ~slat_m
    fl.put(under & ~lag, mat="gap", cav=1.0)
    fl.put(under & lag, mat="grate", cav=0.5)
    return fl


def niche_ceiling(X, Zc):
    """Потолок ниши (вид снизу): вагонка вдоль глубины, у передней кромки — паз-светильник."""
    fl = Field(X.shape, "niche")
    lay = boards_layout(NICHE_X[0] - 6, NICHE_X[1] + 6, [9.0, 8.0, 8.8, 7.6, 8.4, 8.2, 8.6], 250)
    vagonka(fl, Zc, X, lay, amp_k=1.1)
    slot = (Zc > 16.8) & (Zc < 19.6)
    fl.h = np.where(slot, -0.9 - round_drop(np.clip(np.minimum(Zc - 16.8, 19.6 - Zc), 0, None), 0.3) * 0, fl.h)
    fl.put(slot, mat="glow", glow=1.0, grain=0.0)
    fl.cav = np.maximum(fl.cav, sstep(0.6, 0.0, np.minimum(np.abs(Zc - 16.8), np.abs(Zc - 19.6))) * slot)
    return fl


def shelf_top(X, Zc, key):
    """Полка: 5 реек вдоль x с зазорами (верх = низ — одна развёртка), передняя кромка скруглена и вытерта."""
    fl = Field(X.shape, "shelf")
    rng = np.random.default_rng(260 + ord(key))
    z0, z1 = SHELF_Z
    n, gap = 5, 0.8
    w = (z1 - z0 - gap * (n - 1)) / n
    H = np.full(X.shape, -1.6)
    for i in range(n):
        a = z0 + i * (w + gap)
        d = np.minimum(Zc - a, a + w - Zc)
        m = d > 0
        r = 0.35 if i < n - 1 else 1.0                       # передняя рейка скруглена по износу
        g = grain_relief(X, Zc, 1.2 + i * 0.5, 0.012, a + w * rng.uniform(0.3, 0.7), 1.05, 270 + i + ord(key))
        hs = -round_drop(np.clip(d, 0, None), r) + 0.09 * (g - 0.35)
        H = np.where(m, hs, H)
        fl.grain = np.where(m, g, fl.grain)
        fl.tone = np.where(m, rng.random(), fl.tone)
        fl.board = np.where(m, i + 1, fl.board)
        fl.edge = np.where(m, sstep(r * 1.6, 0.0, d) * (1.0 if i == n - 1 else 0.6), fl.edge)
    slat = H > -1.5
    fl.h = H
    fl.put(~slat, mat="gap", cav=1.0)
    for _ in range(8):                                       # вмятинки от шайки у передней кромки
        dent(fl, rng.uniform(-86, -34), z1 - rng.uniform(0.5, 4.0), X, Zc, rng.uniform(0.6, 1.2), 0.06)
    return fl


def shelf_edge(X, Yc, y0, y1):
    """Передняя кромка полки (z = 20.22, 2.3 см): продольное волокно, внизу паз со светящейся планкой."""
    fl = Field(X.shape, "shelf")
    g = grain_relief(X, Yc, 2.0, 0.01, (y0 + y1) / 2, 0.9, 281)
    fl.h += 0.07 * (g - 0.35)
    fl.grain = g
    fl.tone += 0.5
    d = np.minimum(Yc - y0, y1 - Yc)
    edge_wear(fl, d, 0.4, 1.0)
    slot = Yc < y0 + 0.75
    fl.h = np.where(slot, -0.5, fl.h)
    fl.put(slot, mat="glow", glow=1.0, grain=0.0, edge=0.0)
    return fl


SHELF_C_BOARDS = ((-89.69, -70.77), (-70.77, -49.15), (-49.15, -30.23))


def shelf_c_top(X, Zc, base=None):
    """Нижняя полка из трёх досок вдоль глубины (верх = низ): волокна вдоль z, щели между досками,
    передние торцы скруглены, по два гвоздя на концах (в бруски)."""
    fl = Field(X.shape, "shelf")
    rng = np.random.default_rng(291)
    z0, z1 = SHELF_Z
    for i, (a, b) in enumerate(SHELF_C_BOARDS):
        m = (X >= a) & (X < b)
        g = grain_relief(Zc[m], X[m], 1.4 + i * 0.6, 0.012, a + (b - a) * rng.uniform(0.3, 0.7), 1.05, 292 + i)
        fl.h[m] += 0.085 * (g - 0.35)
        fl.grain[m] = g
        fl.tone[m] = rng.random()
        fl.board[m] = i + 1
        d = np.minimum(X[m] - a if i > 0 else 9, b - X[m] if i < 2 else 9)
        fl.h[m] -= 0.35 * np.clip(1 - d / 0.4, 0, 1) ** 1.4
        fl.cav[m] = np.maximum(fl.cav[m], np.clip(1 - d / 0.22, 0, 1))
        de = np.minimum(Zc[m] - z0, z1 - Zc[m])
        fl.h[m] -= round_drop(np.clip(de, 0, None), 0.7)
        fl.edge[m] = np.maximum(fl.edge[m], sstep(1.0, 0.0, z1 - Zc[m]))
        for zz in (z0 + 2.0, z1 - 2.0):
            for dx in (-0.25, 0.25):
                nail_round(fl, a + (b - a) * (0.5 + dx), zz + rng.uniform(-0.4, 0.4), X, Zc, r=0.55, lift=0.08)
    for _ in range(6):
        dent(fl, rng.uniform(-88, -32), rng.uniform(z0 + 2, z1 - 2), X, Zc, rng.uniform(0.7, 1.4), 0.06)
    return fl


def shelf_c_edge(X, Yc):
    """Передние торцы досок нижней полки: годичные кольца вокруг сердцевины ниже доски, трещина."""
    fl = Field(X.shape, "shelf")
    for i, (a, b) in enumerate(SHELF_C_BOARDS):
        m = (X >= a) & (X < b)
        pu, pv = a + (b - a) * (0.35 + 0.3 * i / 2), 40.0
        r = np.hypot(X[m] - pu, Yc[m] - pv) + 0.3 * (fbm2(X[m] * 0.3, Yc[m] * 0.3, 301 + i, 2) - 0.5)
        f = (r / 0.55) % 1.0
        ring = np.exp(-((f - 0.8) / 0.12) ** 2)
        fl.h[m] += 0.05 * ring
        fl.grain[m] = ring
        fl.board[m] = i + 1
        fl.tone[m] = 0.3 + 0.2 * i
        ang = np.arctan2(Yc[m] - pv, X[m] - pu)
        chk = (np.abs(np.angle(np.exp(1j * (ang - 1.4 - 0.3 * i)))) * r < 0.15)
        fl.h[m] -= 0.3 * chk
        fl.cav[m] = np.maximum(fl.cav[m], chk * 1.0)
        d = np.minimum(X[m] - a, b - X[m])
        fl.cav[m] = np.maximum(fl.cav[m], np.clip(1 - d / 0.25, 0, 1))
        fl.h[m] -= 0.3 * np.clip(1 - d / 0.3, 0, 1)
    fl.misc += 1.0                                          # торец: маска для цвета (темнее)
    return fl


# ================================================================== БОК СНАРУЖИ (#5, общий с перегородками, зеркально перед↔зад)
SIDE_Z = (-34.13, 25.83)
SIDE_Y = (0.0, 223.85)
SIDE_STEEL = 2.0                  # стальной уголок корпуса спереди и сзади (симметрично)
BATTENS = ((15.45, 21.0), (112.0, 117.5), (211.0, 216.5))


def side_panel(Zc, Y):
    """Бок (вид с x = −89.94 наружу −x): светлая вагонка на шпонках поверх старого стального корпуса.
    Сталь видна: уголки спереди/сзади 2 см, цоколь до 15.45 и карниз выше 217.45. По глубине — только симметричное."""
    fl = Field(Zc.shape, "side")
    zm = (SIDE_Z[0] + SIDE_Z[1]) / 2
    za = np.abs(Zc - zm)                          # симметрия перед↔зад
    half = (SIDE_Z[1] - SIDE_Z[0]) / 2
    wood_half = half - SIDE_STEEL
    lay = boards_layout(-wood_half, wood_half, [8.6, 8.2, 8.8, 8.4, 8.8, 8.2, 8.6], 310)
    rng = np.random.default_rng(311)
    zs = Zc - zm
    knots = [(rng.uniform(30, 200), rng.uniform(-wood_half + 3, wood_half - 3), rng.uniform(0.6, 1.3)) for _ in range(5)]
    vagonka(fl, Y, zs, lay, knots=knots, amp_k=1.2)
    wood = (za < wood_half) & (Y > 15.45) & (Y < 217.45)
    # концы досок: верх и низ скруглены, низ размочален
    dl = np.minimum(Y - 15.45, 217.45 - Y)
    fl.h -= round_drop(np.clip(dl, 0, None), 0.5)
    fl.h -= sstep(5.0, 0.0, Y - 15.45) * 0.12 * sstep(0.45, 0.75, n2(Zc * 2.0, Y * 0.4, 313)) * wood
    for _ in range(4):
        zc = rng.uniform(-wood_half + 2, wood_half - 2)
        y0 = rng.uniform(150, 195)
        crack(fl, Y, zs, y0, y0 + rng.uniform(10, 22), zc, 0.55, 0.2, int(rng.integers(999)))
    for _ in range(9):
        dent(fl, rng.uniform(-wood_half, wood_half), rng.uniform(60, 140), zs, Y, rng.uniform(0.8, 2.0), rng.uniform(0.05, 0.1))
    # шпонки 2 см поверх вагонки, по гвоздю в каждую доску
    for (b0, b1) in BATTENS:
        d = np.minimum(np.minimum(Y - b0, b1 - Y), wood_half - za)
        m = d > 0
        g = grain_relief(zs, Y, 2.0, 0.01, (b0 + b1) / 2, 1.0, 320 + int(b0))
        hb = 2.0 - round_drop(np.clip(d, 0, None), 0.5) + 0.09 * (g - 0.35)
        fl.h = np.where(m, np.maximum(fl.h, hb), fl.h)
        fl.grain = np.where(m, g, fl.grain)
        fl.board = np.where(m, 12, fl.board)
        fl.tone = np.where(m, 0.6, fl.tone)
        fl.cav = np.where(m, 0.0, fl.cav)
        fl.edge = np.where(m, sstep(0.8, 0.0, d), fl.edge)
        for b in lay:
            zc = (b["lo"] + b["hi"]) / 2 + rng.uniform(-1, 1)
            nail_round(fl, zc, (b0 + b1) / 2 + rng.uniform(-0.6, 0.6), zs, Y, r=0.65, lift=0.13, base=2.0,
                       smile=rng.uniform(0, 6.3) if rng.random() < 0.3 else None)
    # сталь: уголки, цоколь, карниз
    steel = ~wood
    st = Field(Zc.shape, "steel")
    de = np.minimum(np.minimum(half - za, np.abs(za - wood_half)), np.minimum(np.abs(Y - 15.45), np.abs(Y - 217.45)))
    de = np.minimum(de, np.minimum(Y - SIDE_Y[0], SIDE_Y[1] - Y))
    steel_surface(st, Zc, Y, de, 331, chip=0.3)
    fl.h = np.where(steel, -0.3 + st.h, fl.h)
    for k in ("coat", "grain", "knot", "edge"):
        setattr(fl, k, np.where(steel, getattr(st, k), getattr(fl, k)))
    fl.put(steel, mat="steel", board=13, cav=0.0, tone=0.5, nail=0.0)
    fl.cav = np.where(steel, sstep(0.4, 0.0, np.abs(za - wood_half)) * (Y > 15.45) * (Y < 217.45), fl.cav)
    return fl


# ================================================================== РАМА СПЕРЕДИ (#4, сталь; три блока — одни тексели)
FRAME_X = (-89.94, -29.98)
FRAME_OPEN = (-83.46, -36.74, 15.45, 217.45)     # проём ниши
HINGE_Y = ((26.0, 40.0), (106.0, 120.0), (187.0, 201.0))
HINGE_X = (-33.1, -30.2)                          # обломки петель снятых дверец на правой стойке


def frame_front(X, Y):
    """Рама блока (z = 25.83, наружу +z): стальные стойки, карниз и цоколь с облезлой эмалью;
    обломки петель сорванных крайних дверец на правой стойке (копии — правые стойки всех трёх блоков)."""
    fl = Field(X.shape, "steel")
    ox0, ox1, oy0, oy1 = FRAME_OPEN
    d_out = np.minimum(np.minimum(X - FRAME_X[0], FRAME_X[1] - X), np.minimum(Y - 0.0, 223.85 - Y))
    d_open = np.minimum(np.minimum(np.abs(X - ox0), np.abs(X - ox1)), np.minimum(np.abs(Y - oy0), np.abs(Y - oy1)))
    inopen = (X > ox0) & (X < ox1) & (Y > oy0) & (Y < oy1)
    d_open = np.where((X > ox0 - 0.01) & (X < ox1 + 0.01) & (Y > oy0 - 7) & (Y < oy1 + 7), d_open, 99)
    de = np.minimum(d_out, np.where(inopen, 0, d_open))
    steel_surface(fl, X, Y, np.clip(de, 0, None), 401, chip=0.35, r_edge=0.7)
    fl.h -= round_drop(np.clip(de, 0, None), 0.9) * 0.6
    # продух-прорези в цоколе: по 2 штампованные щели 1 × 9 см с отогнутой кромкой
    for sx in (-66.0, -54.0):
        q = np.hypot((X - sx) / 4.5, (Y - 10.7) / 0.55)
        fl.h -= 0.9 * sstep(1.0, 0.9, q) - 0.12 * np.exp(-((q - 1.15) / 0.12) ** 2)
        fl.cav = np.maximum(fl.cav, sstep(1.0, 0.9, q))
    # заклёпки по карнизу и на стойках у углов
    for (rx, ry) in ((-87.2, 220.6), (-32.7, 220.6), (-87.2, 3.6), (-32.7, 3.6), (-60.0, 220.6)):
        dd = np.hypot(X - rx, Y - ry)
        fl.h = np.where(dd < 0.6, np.maximum(fl.h, 0.12 + 0.22 * np.sqrt(np.clip(1 - (dd / 0.6) ** 2, 0, 1))), fl.h)
        fl.nail = np.maximum(fl.nail, sstep(0.62, 0.5, dd))
    # обломки петель: пластина 2.6 × 14 см, 0.2 см, три заклёпки, обломанный край
    for (y0, y1) in HINGE_Y:
        dx = np.minimum(X - HINGE_X[0], HINGE_X[1] - X)
        dy = np.minimum(Y - y0, y1 - Y)
        torn = 0.35 * (n2(Y * 1.3, 5.0, int(y0)) - 0.5)
        m = (dx + torn * (X > (HINGE_X[0] + HINGE_X[1]) / 2) > 0) & (dy > 0)
        fl.h = np.where(m, 0.24 + 0.02 * (fbm2(X * 2, Y * 2, int(y0), 2) - 0.5), fl.h)
        fl.put(m, mat="stub", coat=0.0, board=14)
        fl.edge = np.where(m, sstep(0.3, 0.0, np.minimum(dx, dy)), fl.edge)
        ring = np.exp(-((np.minimum(dx, dy) + 0.15) / 0.2) ** 2) * ~m * (np.abs(X - np.mean(HINGE_X)) < 2.5) * (Y > y0 - 1) * (Y < y1 + 1)
        fl.coat = np.where(ring > 0.5, 0.0, fl.coat)               # вокруг пластины эмаль сбита
        for ry in (y0 + 2.0, (y0 + y1) / 2, y1 - 2.0):
            dd = np.hypot(X - (HINGE_X[0] + 1.2), Y - ry)
            fl.h = np.where(dd < 0.5, np.maximum(fl.h, 0.32 + 0.12 * np.sqrt(np.clip(1 - (dd / 0.5) ** 2, 0, 1))), fl.h)
            fl.nail = np.maximum(fl.nail, sstep(0.52, 0.42, dd))
    fl.board = np.where(fl.board == 0, 13, fl.board)
    return fl


# ================================================================== ПОЛОТЕНЦЕ И ВЕНИК (сетки)
def _towel_panel(px, py, W, L, z_top, z_bot, xoff, skew, seed, nu_step=0.25):
    """Одно свисающее полотнище: собрано у колышка, вертикальные складки, косой подшитый низ."""
    nu, nv = int(W / nu_step) + 1, int(L / nu_step) + 1
    s = np.linspace(-0.5, 0.5, nu)
    t = np.linspace(0, 1, nv)
    S, Tt = np.meshgrid(s, t, indexing="ij")
    gather = np.clip(1 - Tt / 0.3, 0, 1) ** 1.5
    width = W * (1 - 0.66 * gather)
    x = px + xoff * (1 - gather) + S * width + 0.9 * np.sin(Tt * 2.4 + seed) * Tt
    hem = py + 1.2 - L + (S + 0.5) * skew
    y = py + 1.2 - Tt * (py + 1.2 - hem)
    ph = S * (5.5 + 4.0 * gather) * np.pi + 1.1 * np.sin(Tt * 3.3 + seed) + 0.6 * np.sin(S * 7 + seed)
    amp = 0.75 * gather + 0.45 + 0.35 * np.sin(Tt * 3.7 + 2 + seed) ** 2
    folds = amp * (0.65 * np.sin(ph) + 0.28 * np.sin(2.3 * ph + 0.7 + seed))
    z = z_top + (z_bot - z_top) * Tt + folds + 0.12 * (fbm2(S * 12, Tt * 22, int(seed * 10), 3) - 0.5)
    top = np.clip(1 - Tt / 0.06, 0, 1)
    z = z + top * 1.0
    y = y + top * 1.0
    d_side = (0.5 - np.abs(S)) * width
    d_bot = (1 - Tt) * L
    hemm = (d_side < 1.4) | (d_bot < 1.6)
    z = z + 0.18 * hemm
    on_side = np.abs(d_side - 1.0) < 0.13
    on_bot = np.abs(d_bot - 1.2) < 0.13
    along = np.where(on_side, Tt * L, S * W)
    stitch = (on_side | on_bot) & (((along / 1.15) % 1.0) < 0.7)
    z = z + 0.06 * stitch
    stripe = ((d_bot > 6.5) & (d_bot < 8.1)) | ((d_bot > 9.1) & (d_bot < 10.7))
    ii = np.arange(nu * nv).reshape(nu, nv)
    Q = np.stack([ii[:-1, :-1], ii[:-1, 1:], ii[1:, 1:], ii[1:, :-1]], -1).reshape(-1, 4)
    masks = dict(stitch=stitch.reshape(-1) * 1.0, stripe=stripe.reshape(-1) * 1.0,
                 fold=np.clip(0.5 + 0.5 * folds.reshape(-1) / 1.2, 0, 1), hem=hemm.reshape(-1) * 1.0)
    fringe = []
    rng = np.random.default_rng(int(seed * 100))
    for k in range(2, nu - 2, 7):
        Lf = rng.uniform(2.2, 3.2)
        C = np.column_stack([np.full(10, x[k, -1]) + np.linspace(0, rng.uniform(-0.4, 0.4), 10),
                             y[k, -1] - np.linspace(0, Lf, 10), np.full(10, z[k, -1]) - np.linspace(0, 0.25, 10)])
        fringe.append(C)
    return np.stack([x, y, z], -1).reshape(-1, 3), Q, masks, fringe


def towel_mesh(seed=501):
    """Полотенце, перекинутое через колышек (PEGS[0]): два конца разной длины — передний короче и правее,
    задний длиннее и выглядывает слева снизу; у обоих складки, подшитый низ со стежками, кирпичные полосы, бахрома.
    Возвращает список полотнищ (V, Q, маски, бахрома)."""
    px, py = PEGS[0]
    wall = NICHE_Z_BACK
    tip = wall + 5.6
    back = _towel_panel(px, py, 25.0, 50.0, wall + 2.2, wall + 0.9, -2.6, -6.0, 1.7)
    front = _towel_panel(px, py, 25.0, 41.0, tip - 0.9, wall + 3.0, 1.6, 4.5, 0.4)
    return [back, front]


def leaf_grid(L, rng, nu=30, nv=13):
    """Берёзовый лист (как в bed/bake_v2.leaf): x вдоль жилки, y поперёк, h — изгиб и жилки."""
    U, Vv = np.meshgrid(np.linspace(0, 1, nu), np.linspace(-1, 1, nv), indexing="ij")
    W = 0.36 * L * (U ** 0.45) * (1 - U) ** 0.75 / (0.45 ** 0.45 * 0.55 ** 0.75) * 0.95
    W = W * (1 + 0.05 * np.sin(U * 26 + rng.uniform(0, 6)))
    x = U * L
    y = Vv * W
    vein = np.exp(-(np.abs(y) / 0.09) ** 2) * (U < 0.97)
    for k in range(1, 7):
        u0 = 0.1 + 0.13 * k
        along = x - (u0 * L + np.abs(y) * 0.95)
        vein = np.maximum(vein, 0.7 * np.exp(-(along / 0.08) ** 2) * (np.abs(y) < W * 0.9) * (u0 < 0.95))
    curl = rng.uniform(0.04, 0.09) * L
    h = 0.07 * vein + curl * np.abs(Vv) ** 2.2 + 0.2 * np.sin(U * np.pi) * rng.uniform(-0.5, 1.0)
    return x, y, h, vein


def venik_parts(seed=551):
    """Сушёный берёзовый веник на петле из бечёвки (PEGS[1]): прутья ручки, 3 пояса бечёвки, ~110 листьев.
    Возвращает список (имя, C или сетка, радиусы/атрибуты) — геометрию собирает bake_v6.py."""
    rng = np.random.default_rng(seed)
    px, py = PEGS[1]
    wall = NICHE_Z_BACK
    out = {"tubes": [], "leaves": []}
    hy_top = py - 5.5                                      # верх ручки: под петлёй
    zc = wall + 2.6
    # петля: от верха ручки через колышек
    phi = np.linspace(0, np.pi, 40)
    loop = np.column_stack([px + 1.25 * np.cos(phi) * (1 - 0.0 * phi), py + 1.9 * np.sin(phi) - 0.3,
                            np.full(40, wall + 3.4)])
    pre = np.column_stack([np.linspace(px - 0.6, px + 1.25, 15), np.linspace(hy_top, py - 0.3, 15), np.linspace(zc, wall + 3.4, 15)])
    post = np.column_stack([np.linspace(px - 1.25, px + 0.6, 15), np.linspace(py - 0.3, hy_top, 15), np.linspace(wall + 3.4, zc, 15)])
    out["tubes"].append(("twine", np.vstack([pre, loop[::-1], post]), 0.28, 0.8))
    # прутья ручки: 11 шт., сходятся вверху
    for i in range(11):
        a = rng.uniform(0, 2 * np.pi)
        r0 = rng.uniform(0.2, 1.1)
        L = rng.uniform(14, 18)
        tt = np.linspace(0, 1, 40)
        spread = 1.0 + 2.6 * tt ** 1.5
        C = np.column_stack([px + r0 * np.cos(a) * spread + 0.3 * np.sin(tt * 4 + i),
                             hy_top - tt * L,
                             zc + 0.6 * r0 * np.sin(a) * spread])
        out["tubes"].append(("twig", C, 0.3 * (1 - 0.45 * tt) + 0.03, 0.0))
    # пояса бечёвки
    for yb in (hy_top - 1.2, hy_top - 4.0, hy_top - 6.6):
        n = 4 * 40
        ph = np.linspace(0, 4 * 2 * np.pi, n)
        R = 1.45 + 0.1 * (hy_top - yb)
        C = np.column_stack([px + R * np.cos(ph), yb - 0.62 * ph / (2 * np.pi), zc + 0.8 * R * np.sin(ph)])
        out["tubes"].append(("twine", C, 0.27, 0.7))
    # листья: веер вниз от ручки, гуще в середине, слоями к стене
    top_leaves = hy_top - 10.0
    for k in range(140):
        tt = rng.uniform(0, 1) ** 0.8
        yl = top_leaves - tt * 24.0
        wd = 3.0 + 8.0 * np.sin(np.pi * min(tt * 1.1, 1.0)) ** 0.8
        xl = px + rng.uniform(-1, 1) * wd
        depth = (1 - (abs(xl - px) / (wd + 1)) ** 2) * (1.0 - 0.6 * tt)
        L = rng.uniform(5.0, 7.0)
        ang = -np.pi / 2 + rng.normal(0, 0.5) + 0.35 * (xl - px) / wd
        out["leaves"].append((xl, yl, wall + 0.6 + depth * rng.uniform(0.6, 4.2), ang, L, rng.uniform(-0.35, 0.35)))
    out["leaves"].sort(key=lambda l: l[2])
    return out


# ================================================================== проверка в .venv: теневой рельеф
def relief(H, step, L=(-0.5, 0.45, 0.74)):
    gy, gx = np.gradient(H, step)
    L = np.asarray(L) / np.linalg.norm(L)
    nx, ny, nz = -gx, -gy, np.ones_like(H)
    nn = np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.clip((nx * L[0] + ny * L[1] + nz * L[2]) / nn, 0, 1)


if __name__ == "__main__":
    import sys
    from pathlib import Path
    from PIL import Image
    sys.path.insert(0, str(Path(__file__).parent))
    import parts as PT
    step = float(sys.argv[1]) if len(sys.argv) > 1 else 0.2
    out = Path(__file__).parent / "plan_v6"
    V, T, N, F = PT.load(PT.OBJ)
    import json
    rec = json.loads((Path(__file__).parent / "uv" / "v6" / "faces.json").read_text())
    polys = [V[F[f][0]] for f in range(len(F)) if rec[f]["island"] == 67 and rec[f]["n"][2] > 0.1]
    xs = np.arange(DOOR_X[0] - 0.3, DOOR_X[1] + 0.3, step)
    ys = np.arange(DOOR_Y[0] - 0.3, DOOR_Y[1] + 0.3, step)
    X, Y = np.meshgrid(xs, ys)
    Z0 = faces_base(X, Y, polys, 2)
    Z0 = np.where(np.isnan(Z0), 26.0, Z0)
    fl = door_front(X, Y, Z0)
    img = relief(Z0 + fl.h, step)[::-1]
    Image.fromarray((img ** 1.1 * 255).astype(np.uint8)).save(out / "relief_door.png")
    xs = np.arange(NICHE_X[0], NICHE_X[1], step)
    ys = np.arange(NICHE_Y[0], NICHE_Y[1], step)
    X, Y = np.meshgrid(xs, ys)
    fl = niche_back(X, Y)
    Image.fromarray((relief(fl.h, step)[::-1] ** 1.1 * 255).astype(np.uint8)).save(out / "relief_niche_back.png")
    zs = np.arange(SIDE_Z[0], SIDE_Z[1], step)
    ys = np.arange(SIDE_Y[0], SIDE_Y[1], step)
    Zg, Y = np.meshgrid(zs, ys)
    fl = side_panel(Zg, Y)
    Image.fromarray((relief(fl.h, step)[::-1] ** 1.1 * 255).astype(np.uint8)).save(out / "relief_side.png")
    xs = np.arange(FRAME_X[0], FRAME_X[1], step)
    ys = np.arange(0, 223.85, step)
    X, Y = np.meshgrid(xs, ys)
    fl = frame_front(X, Y)
    Image.fromarray((relief(fl.h, step)[::-1] ** 1.1 * 255).astype(np.uint8)).save(out / "relief_frame.png")
    print("ok")
