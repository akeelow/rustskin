"""Sauna Boiler v4: рельеф бака и пояса реек — поле смещения вдоль нормалей подразделённой копии модели (numpy, см).

Всё, что имеет форму, считается здесь функциями; те же функции пишут маски цвета (PLAN_v4.md §2). Рельеф и цвет
совпадают пиксель в пиксель. Размеры — под 3.9 px/см бака и 4.5 px/см реек при 1024 (1 px = 2.2–2.6 мм), PLAN §1.
Гранёность модели в нормаль не попадает: bake_v4 печёт копию без смещения и вычитает её.

body(P, N) -> dict: h (см, наружу) и маски
  m1 = (wear — светлый металл / гребень волокна, cav — полость, dent — вмятина)
  m2 = (rivet — заклёпка, гвоздь; knot — сучок / ромбик рифлёнки; char — обугливание)
  m3 = (rust, crust — корка накипи, tone — тон листа / доски)
  idc = (код материала / 32, номер листа / доски / 32, heat — жар у топки)
"""
import numpy as np

import geom_v4 as G

MAT = {"sheet": 1, "hoop": 2, "rivet": 3, "frame": 4, "checker": 5, "hinge": 6, "bolt": 7, "ladle": 8, "plug": 9,
       "rag": 10, "twine": 11, "hook": 12, "slat": 13, "nail": 14, "wire": 15, "char": 16, "behind": 17,
       "reveal": 18, "sill": 19, "lid": 20, "stone": 21, "brick": 22, "mortar": 23, "ash": 24, "bark": 25,
       "logwood": 26, "ember": 27}
KEYS = ("h", "wear", "cav", "dent", "rivet", "knot", "char", "rust", "crust", "tone", "mat", "sid", "heat")


# ------------------------------------------------------------------ шум (из electric-furnace/fields_v3.py)
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


def voronoi_c(x, y, cell, seed, period=None):
    """F1, F2, центр ближайшей ячейки и два её хеша (0..1). period — число ячеек по x на круг (бесшовно по углу)."""
    gx, gy = np.floor(x / cell).astype(np.int64), np.floor(y / cell).astype(np.int64)
    f1 = np.full(x.shape, 1e9)
    f2 = np.full(x.shape, 1e9)
    cxs, cys, h1, h2 = (np.zeros(x.shape) for _ in range(4))
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            cx, cy = gx + dx, gy + dy
            hx = cx % period if period else cx
            hsh = (hx * 73856093) ^ (cy * 19349663) ^ (seed * 83492791)
            hsh = (hsh ^ (hsh >> 13)) * 1274126177
            rx = (hsh & 0xFFFF) / 65535.0
            ry = ((hsh >> 16) & 0xFFFF) / 65535.0
            px, py = (cx + 0.12 + 0.76 * rx) * cell, (cy + 0.12 + 0.76 * ry) * cell
            d = np.hypot(x - px, y - py)
            closer = d < f1
            f2 = np.where(closer, f1, np.minimum(f2, d))
            f1 = np.where(closer, d, f1)
            cxs = np.where(closer, px, cxs)
            cys = np.where(closer, py, cys)
            h1 = np.where(closer, ((hsh >> 8) & 0xFFFF) / 65535.0, h1)
            h2 = np.where(closer, ((hsh >> 24) & 0xFF) / 255.0, h2)
    return f1, f2, cxs, cys, h1, h2


def grain_relief(along, across, depth0, tilt, c, s, seed, knots=()):
    """Гребни поздней древесины (0..1); knots: [(along, across, r)] — волокна огибают сучок."""
    warp = 0.45 * (fbm2(along * 0.025, across * 0.12, seed, 3) - 0.5) + 0.12 * (n2(along * 0.12, across * 0.5, seed + 3) - 0.5)
    d = depth0 + tilt * along + 0.6 * warp
    ph = np.sqrt((across - c) ** 2 + d * d) / s + warp
    for (ka, kc, kr) in knots:
        dd = np.hypot((along - ka) / 1.5, across - kc)
        ph = ph + 1.6 * kr * np.exp(-(dd / (2.4 * kr)) ** 2) / s
    f = ph - np.floor(ph)
    return np.exp(-((f - 0.82) / 0.13) ** 2) + np.exp(-((f + 1 - 0.82) / 0.13) ** 2) + np.exp(-((f - 1.82) / 0.13) ** 2)


def alligator(X, Y, cell, seed):
    """Обугленное дерево: неровные блоки (Вороной, вытянут вдоль волокна X в 1.7 раза), выпуклые, глубокие трещины между
    ними и мелкие трещинки внутри. -> dh, трещина."""
    f1, f2, cx, cy, h1, h2 = voronoi_c(X / 1.7, Y, cell, seed)
    gap = f2 - f1
    w = 0.09 * cell * (0.7 + 0.6 * h2)
    crack = sstep(w, w * 0.25, gap)
    pillow = np.clip(gap / (0.5 * cell), 0, 1) ** 0.5
    g1, g2, _, _, k1, _ = voronoi_c(X / 1.7, Y, cell * 0.4, seed + 1)
    fine = sstep(0.05 * cell, 0.01 * cell, g2 - g1) * (k1 < 0.45)
    dh = -0.1 + 0.08 * pillow - 0.35 * crack - 0.06 * fine + 0.025 * (n2(X * 1.3, Y * 1.3, seed + 2) - 0.5)
    return dh, np.maximum(crack, 0.5 * fine)


def char_field(X, Y, amount, cell, seed):
    """«Крокодилова кожа» обугленного дерева (волокно вдоль X): блоки-подушки, трещины. -> dh, трещина."""
    X, Y = Y, X
    cw = 0.8 * cell
    xa = X + 0.6 * cw * (fbm2(Y * 0.1, X * 0.04, seed, 3) - 0.5) * 2
    col = np.floor(xa / cw)
    fx = xa / cw - col
    dcol = np.minimum(fx, 1 - fx) * cw
    rh = cell * (0.55 + 1.1 * n2(col * 1.7, 0.5, seed + 1))
    off = n2(col * 3.1, 1.5, seed + 2) * rh
    yb = Y + off + 0.25 * rh * (n2(X * 0.6, Y * 0.15, seed + 3) - 0.5)
    fy = yb / rh - np.floor(yb / rh)
    drow = np.minimum(fy, 1 - fy) * rh
    row = np.floor(yb / rh)
    has_col = n2(col * 2.3, row * 1.9, seed + 7) > 0.5
    d = np.minimum(np.where(has_col, dcol, 9.0), drow)
    wcr = 0.1 * cell * (0.6 + 0.8 * n2(X * 0.9, Y * 0.9, seed + 4))
    crack = sstep(wcr, wcr * 0.3, d)
    pillow = np.clip(d / (0.35 * cell), 0, 1) ** 0.6
    dh = (-0.12 + 0.07 * pillow - 0.3 * crack + 0.03 * (n2(X * 1.5, Y * 1.5, seed + 6) - 0.5)) * amount
    return dh, crack * amount


def wrapdeg(a):
    return (a + 180.0) % 360.0 - 180.0


# ------------------------------------------------------------------ раскладка (PLAN_v4 §3, решения §7)
# пояса листов: y0, y1, швы (град.). Горизонтальные стыки — под обручами 91.5, 112.5, 131.5
COURSES = ((-1.0, 91.5, (72.0, 141.0, 214.0, 291.0)),
           (91.5, 112.5, (21.0, 96.0, 171.0, 249.0, 322.0)),
           (112.5, 131.5, (57.0, 152.0, 236.0, 331.0)),
           (131.5, 999.0, (12.0, 133.0, 251.0)))
# обручи: центр по y, пропуск по углу (у топки), замок: (угол, тип)
HOOPS = ((62.5, True, (180.0, "lap")), (91.5, False, (78.0, "bolt")), (112.5, False, (-75.0, "lap")),
         (131.5, False, (145.0, "bolt")), (148.5, False, (-150.0, "weld")))
HOOP_HW, HOOP_T = 3.2, 0.7
BOARD_TOP = 53.5                     # верх пояса реек
ROWS = (0.0, 15.5, 28.5, 41.0, BOARD_TOP)
PATCH = (22.0, 50.0, 93.5, 110.5)    # рифлёная заплата: th0, th1, y0, y1 (верх и низ — под обручами)
HINGES_Y = (64.0, 80.0)              # петли пропавшей дверцы на левом краю рамки
PLUG = (-52.0, 70.5)                 # затычка с тряпкой
HOOK = (60.0, 106.0)                 # крюк, на нём ковш (чаша — между обручами 62.5 и 91.5)
FRAME_W = 12.5                       # ширина рамки проёма от кромки горла (по скосу и 2–3 см на стенку), см
SILL = (48.5, 57.0)                  # железный порог под проёмом
WIRES = (34.5, 8.5)                  # проволока по поясу реек (y)
TWIST_TH = 78.0                      # скрутка верхней проволоки


def course_of(y):
    c = np.zeros(len(y), np.int32)
    for k, (y0, y1, _) in enumerate(COURSES):
        c[(y >= y0) & (y < y1)] = k
    return c


def sheet_layout():
    """Список листов: (курс, th0, th1, глобальный номер, тип). Тип: plain / barrel / roof."""
    out, gid = [], 0
    for k, (y0, y1, seams) in enumerate(COURSES):
        for j in range(len(seams)):
            a0, a1 = seams[j], seams[(j + 1) % len(seams)]
            if a1 <= a0:
                a1 += 360
            kind = "plain"
            if k == 1 and abs(a0 - 96) < 1:
                kind = "barrel"
            if k == 1 and abs(a0 - 249) < 1:
                kind = "roof"
            out.append((k, a0, a1, gid, kind))
            gid += 1
    return out


SHEETS = sheet_layout()


class Index:
    """Пространственный индекс точек по (th, y): ячейки cth град. × cy см, перенос через ±180."""

    def __init__(self, th, y, cth=3.0, cy=3.0):
        self.cth, self.cy = cth, cy
        self.nth = int(round(360 / cth))
        ci = np.floor((th + 180) / cth).astype(np.int64) % self.nth
        cj = np.floor(y / cy).astype(np.int64) + 20
        key = ci * 100000 + cj
        self.order = np.argsort(key, kind="stable")
        self.key = key[self.order]

    def q(self, thc, yc, rth, ry):
        i0 = int(np.floor((thc - rth + 180) / self.cth))
        i1 = int(np.floor((thc + rth + 180) / self.cth))
        j0 = int(np.floor((yc - ry) / self.cy)) + 20
        j1 = int(np.floor((yc + ry) / self.cy)) + 20
        out, seen = [], set()
        for i in range(i0, i1 + 1):
            ii = i % self.nth
            if ii in seen:
                continue
            seen.add(ii)
            lo = np.searchsorted(self.key, ii * 100000 + j0, "left")
            hi = np.searchsorted(self.key, ii * 100000 + j1, "right")
            out.append(self.order[lo:hi])
        return np.concatenate(out) if out else np.zeros(0, np.int64)


def poly_sdist(px, py, poly):
    """Знаковое расстояние до замкнутой ломаной (снаружи +) и признак «внутри»."""
    best = np.full(px.shape, 1e9)
    inside = np.zeros(px.shape, bool)
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        t = np.clip(((px - ax) * ex + (py - ay) * ey) / max(ex * ex + ey * ey, 1e-12), 0, 1)
        d = np.hypot(px - ax - t * ex, py - ay - t * ey)
        best = np.minimum(best, d)
        cond = ((ay > py) != (by > py)) & (px < ax + (py - ay) * ex / (ey + 1e-12))
        inside ^= cond
    return np.where(inside, -best, best), inside


# ------------------------------------------------------------------ детали
def dome(d, R, hgt, p=0.75):
    return hgt * np.clip(1 - (d / R) ** 2, 0, 1) ** p


class Body:
    """Поле бака (остров 0) и пояса реек (острова 1, 2) одной функцией по точкам модели."""

    def __init__(self, P, N, seed=4):
        self.P, self.N = P, N
        n = len(P)
        self.n = n
        self.th = G.theta(P)
        self.y = P[:, 1]
        self.r = G.radius(P)
        ys, rp = G.profile()
        self.Rp = np.interp(self.y, ys, rp)
        self.up = N[:, 1]
        self.o = {k: np.zeros(n) for k in KEYS}
        self.o["tone"][:] = 0.5
        self.o["sid"][:] = -1
        self.rng = np.random.default_rng(seed)
        self.ix = Index(self.th, self.y)
        # проём: контур горла топки (граница острова 0) в проекции на фронт (x, y); рамка — по скосу вокруг него
        L = G.opening_loop()
        self.polyI = np.stack([L[:, 0], L[:, 1]], -1)
        near = (np.abs(self.th) < 80) & (self.y < 108) & (P[:, 2] > G.CZ)
        self.front = near
        self.dopen = np.full(n, 99.0)
        dd, _ = poly_sdist(P[near, 0], self.y[near], self.polyI)
        self.dopen[near] = dd
        poly = G.outline().copy()
        s42 = np.radians(wrapdeg(self.th)) * 42.0
        _, ins = poly_sdist(s42[near], self.y[near], np.stack([np.radians(poly[:, 0]) * 42.0, poly[:, 1]], -1))
        # откосы проёма: точки внутри контура или заметно ближе к оси, чем стенка
        self.reveal = np.zeros(n, bool)
        self.reveal[near] = ins & (self.y[near] > 50)
        self.reveal |= near & (self.r < self.Rp - 4.0) & (self.y > 52) & (self.y < 92) & (np.abs(self.th) < 45)
        self.lid = (self.y > 149.0) & (self.up > 0.45)
        self.board = (self.y < BOARD_TOP) & ~self.reveal
        self.tank = ~self.board & ~self.lid & ~self.reveal
        self.heat = np.clip(sstep(40.0, 14.0, self.dopen) * (self.y < 114), 0, 1)
        self.o["heat"] = self.heat.copy()

    # ---------------------------------------------------------------- общие операции
    def loc(self, idx, thc, yc):
        dth = wrapdeg(self.th[idx] - thc)
        return np.radians(dth) * self.Rp[idx], self.y[idx] - yc

    def put(self, idx, hh, mat=None, **masks):
        """Наложить деталь: высота — максимум; где деталь выше прежнего, маски прежней поверхности сбрасываются и
        берутся из детали."""
        if len(idx) == 0:
            return np.zeros(0, bool)
        o = self.o
        H = o["h"]
        win = hh > H[idx] + 1e-4
        H[idx] = np.maximum(H[idx], hh)
        sel = idx[win]
        if mat is not None:
            o["mat"][sel] = mat
        for k in ("wear", "cav", "dent", "rivet", "knot", "rust", "crust"):
            o[k][sel] = 0
        for k, v in masks.items():
            vv = np.broadcast_to(np.asarray(v, float), hh.shape)
            o[k][sel] = vv[win]
        return win

    def rivet(self, thc, yc, base=None, R=0.95, hgt=0.55, kind=0, mat=MAT["rivet"], tone=None):
        """Полукруглая заклёпка Ø 2R. kind: 0 — обычная, 1 — смята на бок, 2 — выпала (дыра с ржавчиной)."""
        idx = self.ix.q(thc, yc, np.degrees((R + 1.2) / max(self.Rp_at(yc), 10)), R + 1.2)
        if len(idx) == 0:
            return
        ds, dy = self.loc(idx, thc, yc)
        d = np.hypot(ds, dy)
        H = self.o["h"]
        b = H[idx] if base is None else base
        if kind == 2:
            hole = d < 0.42
            H[idx] = np.where(hole, H[idx] - 0.25 * (1 - (d / 0.42) ** 2), H[idx])
            self.o["cav"][idx] = np.maximum(self.o["cav"][idx], hole * 1.0)
            ring = np.clip(1 - d / 1.4, 0, 1)
            self.o["rust"][idx] = np.maximum(self.o["rust"][idx], ring)
            return
        ddx = ds + (0.35 * dy if kind == 1 else 0)
        dd = np.hypot(ddx, dy * (0.85 if kind == 1 else 1))
        hh = b + dome(dd, R, hgt, 0.6) - (0.12 * np.clip(ds / R, 0, 1) if kind == 1 else 0)
        collar = b + 0.05 * np.exp(-((d - R * 1.04) / 0.12) ** 2)
        hh = np.where(dd < R, hh, collar)
        win = self.put(idx, hh, mat=mat, rivet=(dd < R) * 1.0, wear=np.clip(1 - dd / (0.55 * R), 0, 1) * 0.8,
                       tone=tone if tone is not None else self.rng.random())

    def Rp_at(self, y):
        ys, rp = G.profile()
        return float(np.interp(y, ys, rp))

    # ---------------------------------------------------------------- бак: листы
    def sheets(self):
        o, th, y = self.o, self.th, self.y
        m = self.tank | self.reveal
        crs = course_of(y)
        for (k, a0, a1, gid, kind) in SHEETS:
            a = (th - a0) % 360.0
            sel = np.where(m & (crs == k) & (a < (a1 - a0)))[0]
            if len(sel) == 0:
                continue
            ac = (a0 + a1) / 2
            ds = np.radians(wrapdeg(th[sel] - ac)) * self.Rp[sel]
            yy = y[sel]
            seed = 100 + gid
            cell = 7.0 if k < 2 else (5.5 if k == 2 else 4.5)
            f1, f2, cx, cy, h1, h2 = voronoi_c(ds * (1 + 0.15 * n2(ds * 0.05, yy * 0.05, seed)), yy, cell, seed)
            # ковка: в каждой ячейке своя пологая чаша с наклоном (удар молотка), гребешки на границах
            ang = 2 * np.pi * h1
            slope = 0.015 + 0.025 * h2
            plane = slope * ((ds - cx) * np.cos(ang) + (yy - cy) * np.sin(ang))
            depth = 0.3 + 0.15 * h2
            a_, b_ = (f1 / cell) ** 2, (f2 / cell) ** 2              # чаши ударов, рёбра между ними скруглены
            kk = 0.09
            hk = np.clip(kk - np.abs(a_ - b_), 0, None) / kk
            smin = np.minimum(a_, b_) - kk * hk * hk / 4
            hm = plane - depth * np.clip(smin / 0.33, 0, 1.3) + depth * 0.5
            edge = sstep(0.12 * cell, 0.02 * cell, f2 - f1)
            hm += 0.02 * (fbm2(ds * 0.3, yy * 0.3, seed + 1, 3) - 0.5)
            # мелкие следы бойка поверх крупных граней (рихтовка): лунки 2–3 см, не везде
            g1, g2, _, _, p1, p2 = voronoi_c(ds + 31.0 * gid, yy, 2.8, seed + 7)
            a2, b2 = (g1 / 2.8) ** 2, (g2 / 2.8) ** 2
            hk2 = np.clip(0.06 - np.abs(a2 - b2), 0, None) / 0.06
            sm2 = np.minimum(a2, b2) - 0.06 * hk2 * hk2 / 4
            peen = (0.05 + 0.04 * p2) * np.clip(sm2 / 0.33, 0, 1.3) * (p1 < 0.5)
            hm -= peen * (0.6 + 0.8 * n2(ds * 0.05, yy * 0.05, seed + 8))
            # особые листы (решение 4)
            if kind == "barrel":
                for yr in (97.6, 106.4):
                    hm += 0.38 * np.exp(-((yy - yr) / 1.0) ** 2)
            if kind == "roof":
                hm += 0.11 * np.sin(2 * np.pi * ds / 7.6) * (1 - 0.4 * n2(yy * 0.1, ds * 0.05, seed + 2))
            o["h"][sel] += hm
            o["wear"][sel] = np.maximum(o["wear"][sel], 0.3 * edge)
            o["sid"][sel] = gid
            o["mat"][sel] = MAT["sheet"]
            o["tone"][sel] = 0.5 + 0.35 * (self.rng.random() - 0.5) + 0.12 * (fbm2(ds * 0.04, yy * 0.04, seed + 3, 2) - 0.5)
        # нахлёст на вертикальных швах: кромка рубленая (волна + «укусы» зубила), ряд заклёпок
        for k, (y0, y1, seams) in enumerate(COURSES):
            for j, a in enumerate(seams):
                top_right = (j + k) % 2 == 0                 # какой лист сверху
                yc0, yc1 = max(y0, 50.0), min(y1, 151.0)
                idx = self.ix.q(a, (yc0 + yc1) / 2, 14.0, (yc1 - yc0) / 2 + 1)
                idx = idx[(self.tank | self.reveal)[idx] & (course_of(self.y[idx]) == k)]
                if len(idx) == 0:
                    continue
                ds, _ = self.loc(idx, a, 0)
                x = ds if top_right else -ds                  # + внутрь верхнего листа
                yy = self.y[idx]
                seed = 300 + 10 * k + j
                wob = 0.45 + 0.35 * (fbm2(yy * 0.3, seed, seed, 3) - 0.5) * 2
                ph = yy / 1.5 + 2 * n2(yy * 0.2, seed, seed + 1)
                bites = 0.22 * np.clip(np.sin(ph * np.pi) * 1.4 - 0.4, 0, 1)
                xe = -wob + bites
                lap = 0.3 * np.clip(1 - (x - xe) / 5.5, 0, 1) ** 0.6 + 0.04 * np.exp(-((x - xe - 0.25) / 0.2) ** 2)
                lap = lap * sstep(xe - 0.02, xe + 0.2, x)
                self.o["h"][idx] += lap * (x < 7)
                self.o["cav"][idx] = np.maximum(self.o["cav"][idx], 0.6 * np.exp(-((x - xe + 0.15) / 0.25) ** 2))
                self.o["wear"][idx] = np.maximum(self.o["wear"][idx], 0.7 * np.exp(-((x - xe - 0.3) / 0.25) ** 2))
                # заклёпки шва: 1.7 см от кромки, шаг 5 см; не под обручами и не на рамке
                Ra = self.Rp_at((yc0 + yc1) / 2)
                yr = yc0 + 2.5
                while yr < yc1 - 1.5:
                    if not self.hoop_at(yr, 1.8):
                        Rr = self.Rp_at(yr)
                        thr = a + np.degrees((1.7 - 0.45) / Rr) * (1 if top_right else -1)
                        if self.free(thr, yr, 3.0):
                            kind = 2 if self.rng.random() < 0.04 else (1 if self.rng.random() < 0.1 else 0)
                            self.rivet(thr, yr, kind=kind)
                    yr += 5.0 * self.rng.uniform(0.95, 1.05)

    def dI_wall(self, th, y):
        """Расстояние (фронтальная проекция) от точки стенки бака (th, y) до горла топки."""
        if abs(wrapdeg(th)) > 85:
            return 99.0
        R = self.Rp_at(y)
        x = G.CX + R * np.sin(np.radians(th))
        d, _ = poly_sdist(np.array([x]), np.array([y]), self.polyI)
        return float(d[0])

    def hoop_at(self, y, margin=0.0):
        return any(abs(y - yc) < HOOP_HW + margin for yc, _, _ in HOOPS)

    def free(self, th, y, R):
        """Свободно ли место для заклёпки: не рамка, не заплата, не затычка, не крюк/ковш, не петли."""
        if y < BOARD_TOP + 1.5:
            return False
        if self.dI_wall(th, y) < FRAME_W + R:
            return False
        if PATCH[0] - 3 < th < PATCH[1] + 3 and PATCH[2] < y < PATCH[3]:
            return False
        for (tc, yc, rr) in ((PLUG[0], PLUG[1], 6.0), (HOOK[0], 96.0, 13.0), (HOOK[0], 80.0, 9.0)):
            if abs(np.radians(wrapdeg(th - tc)) * 42) < rr + R and abs(y - yc) < rr + 4 + R:
                return False
        return True

    # ---------------------------------------------------------------- вмятины, жар, ржавчина
    def dents(self):
        rng = np.random.default_rng(21)
        spots = []
        for _ in range(40):
            u = rng.random()
            R = 3.0 + 9.0 * u ** 2.2                       # степенной: много мелких, мало крупных
            if rng.random() < 0.35:                        # гнездо у топки и на высоте колена
                th = rng.uniform(-75, 75)
                y = rng.uniform(58, 100)
            else:
                th = rng.uniform(-180, 180)
                y = rng.uniform(58, 145)
            spots.append((th, y, R, 0.08 + 0.06 * R * rng.uniform(0.6, 1.0)))
        for (thc, yc, R, dep) in spots:
            idx = self.ix.q(thc, yc, np.degrees((R + 1) / self.Rp_at(yc)), R + 1)
            idx = idx[self.tank[idx]]
            ds, dy = self.loc(idx, thc, yc)
            q = np.hypot(ds, dy * 1.15) / R
            bowl = dep * np.clip(1 - q ** 2, 0, 1) ** 1.6
            self.o["h"][idx] -= bowl
            self.o["dent"][idx] = np.maximum(self.o["dent"][idx], np.clip(1 - q, 0, 1))

    def pillows(self):
        """Жар у топки: лист вздут подушками между анкерами (сетка 10 × 9 см), анкеры — заклёпки в узлах."""
        m = np.where(self.tank & (self.heat > 0.02))[0]
        s = np.radians(wrapdeg(self.th[m] - G.OPEN_TH)) * self.Rp[m]
        yy = self.y[m]
        fx, fy = s / 10.0, yy / 9.0
        pil = np.abs(np.sin(np.pi * fx)) * np.abs(np.sin(np.pi * fy))
        w = self.heat[m] * sstep(FRAME_W, FRAME_W + 3, self.dopen[m])
        self.o["h"][m] += 0.22 * w * pil ** 0.8
        for i in range(-6, 7):
            for j in range(6, 13):
                sx, yj = i * 10.0, j * 9.0
                thn = G.OPEN_TH + np.degrees(sx / self.Rp_at(yj))
                hv = np.clip((40 - self.dI_wall(thn, yj)) / 26, 0, 1) * (yj < 114)
                if hv > 0.5 and not self.hoop_at(yj, 1.5) and self.free(thn, yj, 2.5):
                    self.rivet(thn, yj, R=0.85, hgt=0.5)

    def rust(self):
        rng = np.random.default_rng(33)
        o = self.o
        nests = []
        for (yc, gap, _) in HOOPS[:4]:                  # под обручами: вода стоит в щели
            for _ in range(4):
                th = rng.uniform(-180, 180)
                if abs(th) < 55:
                    th += 110 * np.sign(th + 1e-3)
                nests.append((th, yc - HOOP_HW - rng.uniform(1.5, 6), rng.uniform(2.5, 6)))
        for _ in range(7):                              # мокрый низ у реек
            nests.append((rng.uniform(-180, 180), rng.uniform(55.5, 60), rng.uniform(3, 7)))
        nests += [(PLUG[0] + 2, PLUG[1] - 7, 4.5), (PLUG[0] - 3, 58.5, 4.0)]
        for (thc, yc, R) in nests:
            idx = self.ix.q(thc, yc, np.degrees((R + 1) / self.Rp_at(yc)), R + 1)
            idx = idx[self.tank[idx]]
            ds, dy = self.loc(idx, thc, yc)
            fall = np.clip(1 - np.hypot(ds, dy) / R, 0, 1)
            f1, f2, cx, cy, h1, h2 = voronoi_c(ds + 37 * thc, dy, 1.25, int(abs(thc * 10 + yc)) + 5)
            rp = 0.3 + 0.28 * h1
            pit = (f1 < rp) & (h2 < 0.35 + 0.55 * fall)
            dep = (0.06 + 0.06 * h2) * np.clip(1 - (f1 / rp) ** 2, 0, 1)
            o["h"][idx] -= np.where(pit, dep, 0)
            o["cav"][idx] = np.maximum(o["cav"][idx], pit * np.clip(1 - f1 / rp, 0, 1))
            o["rust"][idx] = np.maximum(o["rust"][idx], np.clip(fall * 1.3, 0, 1) * (0.5 + 0.5 * pit))
        # пузыри ржавчины гнёздами: выпуклость, у части лопнувшая середина и чешуя по краю
        for _ in range(16):
            thc = rng.uniform(-180, 180)
            if abs(thc) < 50:
                thc += 120 * np.sign(thc + 1e-3)
            yc = rng.uniform(56, 140)
            for b in range(rng.integers(3, 7)):
                R = rng.uniform(0.8, 2.0)
                tb = thc + np.degrees(rng.normal(0, 3.0) / self.Rp_at(yc))
                yb = yc + rng.normal(0, 2.5)
                if self.hoop_at(yb, R):
                    continue
                idx = self.ix.q(tb, yb, np.degrees((R + 0.6) / self.Rp_at(yb)), R + 0.6)
                idx = idx[self.tank[idx]]
                ds, dy = self.loc(idx, tb, yb)
                d = np.hypot(ds, dy)
                bl = 0.13 * np.clip(1 - (d / R) ** 2, 0, 1) ** 0.7
                if rng.random() < 0.55:
                    ang = np.arctan2(dy, ds)
                    rr = 0.45 * R * (1 + 0.3 * np.sin(ang * 5 + b))
                    crater = d < rr
                    bl = np.where(crater, bl - 0.12 * (1 - d / rr), bl)
                    o["cav"][idx] = np.maximum(o["cav"][idx], crater * 0.8)
                o["h"][idx] += bl
                o["rust"][idx] = np.maximum(o["rust"][idx], (d < R * 1.15) * 1.0)
        # сквозные прогары (глубокая чаша с рваным краем): сзади под обручем, сбоку у низа, у заплаты
        for (thc, yc, R0) in ((165.0, 85.5, 1.6), (-120.0, 59.5, 1.2), (PATCH[0] - 1.2, 97.5, 1.4)):
            idx = self.ix.q(thc, yc, np.degrees((R0 * 3) / self.Rp_at(yc)), R0 * 3)
            idx = idx[self.tank[idx]]
            ds, dy = self.loc(idx, thc, yc)
            d = np.hypot(ds, dy)
            ang = np.arctan2(dy, ds)
            Rr = R0 * (1 + 0.28 * (n2(np.cos(ang) * 2 + 5, np.sin(ang) * 2, int(thc) & 0xFF) - 0.5) * 2)
            hole = d < Rr
            o["h"][idx] = np.where(hole, o["h"][idx] - 0.65 * np.clip(1 - (d / Rr) ** 2, 0.3, 1), o["h"][idx]
                                   - 0.05 * np.clip(1 - (d - Rr) / 1.5, 0, 1))
            o["cav"][idx] = np.maximum(o["cav"][idx], hole * 1.0)
            o["rust"][idx] = np.maximum(o["rust"][idx], np.clip(1 - (d - Rr) / (2.2 * R0), 0, 1))

    # ---------------------------------------------------------------- обручи
    def hoops(self):
        o = self.o
        for hi, (yc, gap, (lth, ltype)) in enumerate(HOOPS):
            idx = np.where((np.abs(self.y - yc) < HOOP_HW + 2.2) & (self.tank | self.lid))[0]
            dy = self.y[idx] - yc
            th = self.th[idx]
            if gap:                                       # нижний обруч упирается в рамку проёма
                keep = self.dopen[idx] > FRAME_W - 0.5
                idx, dy, th = idx[keep], dy[keep], th[keep]
            R0 = self.Rp_at(yc)
            per = int(round(2 * np.pi * R0 / 2.6))
            cellh = 2 * np.pi * R0 / per
            s = np.radians(th % 360.0) * R0                     # 0..2πR, ячейки шумов кратны окружности
            ca, sa = np.cos(np.radians(th)), np.sin(np.radians(th))
            seed = 500 + hi
            edgew = HOOP_HW - 0.25 * np.abs(np.sin(s * 0.9 + hi)) * 0           # ровная полоса
            prof = sstep(edgew + 0.02, edgew - 0.28, np.abs(dy))
            crown = 0.06 * (1 - (dy / HOOP_HW) ** 2)
            hm = 0.035 * (fbm2(ca * R0 * 0.5 + dy * 0.31, sa * R0 * 0.5 - dy * 0.17, seed, 3) - 0.5)
            f1, f2, cx, cy, h1, h2 = voronoi_c(s, dy * 1.4, cellh, seed + 1, per)  # следы молотка на шине
            hm += -0.03 * np.clip(f1 / 1.4, 0, 1) ** 2
            # 2–3 забоины по кромке
            nick = np.zeros(len(idx))
            for k in range(3):
                tn = self.rng.uniform(0, 360)
                dsn = np.radians(wrapdeg(th - tn)) * R0
                nick = np.maximum(nick, np.exp(-(dsn / 1.2) ** 2) * sstep(HOOP_HW - 1.3, HOOP_HW - 0.2, np.abs(dy)))
            hh = HOOP_T * prof + (crown + hm) * prof - 0.18 * nick
            win = self.put(idx, np.where(prof > 0.01, hh, -9), mat=MAT["hoop"], sid=20 + hi,
                           tone=0.5 + 0.2 * (self.rng.random() - 0.5))
            o["wear"][idx] = np.where(win, np.clip(1 - np.abs(dy) / (HOOP_HW * 0.75), 0, 1) * 0.9 * prof
                                      + 0.6 * sstep(HOOP_HW - 0.6, HOOP_HW - 0.2, np.abs(dy)) * prof, o["wear"][idx])
            o["dent"][idx] = np.where(win, nick, o["dent"][idx])
            # ржавая чешуя под нижней кромкой обруча (ржавчина пухнет в щели)
            band = (dy < -HOOP_HW + 0.1) & (dy > -HOOP_HW - 1.8) & ~win
            if band.any():
                perf = int(round(2 * np.pi * R0 / 1.1))
                f1, f2, cx, cy, h1, h2 = voronoi_c(s[band], dy[band], 2 * np.pi * R0 / perf, seed + 3, perf)
                keepf = (h1 < 0.55 + 0.3 * n2(ca[band] * 4, sa[band] * 4, seed)) * 1.0
                fl = keepf * (0.09 * sstep(-HOOP_HW - 1.8, -HOOP_HW - 0.2, dy[band]) - 0.04 * sstep(0.18, 0.03, f2 - f1))
                ib = idx[band]
                o["h"][ib] += fl
                o["rust"][ib] = np.maximum(o["rust"][ib], keepf * 0.9)
            # заклёпки по обручу через ~7 см
            step = np.degrees(7.0 / R0)
            a = self.rng.uniform(0, step)
            while a < 360:
                tha = wrapdeg(a)
                if not gap or self.dI_wall(tha, yc) > FRAME_W + 1.5:
                    if abs(wrapdeg(tha - lth)) * np.pi / 180 * R0 > 7.5 and abs(wrapdeg(tha - HOOK[0])) * np.pi / 180 * R0 > 3:
                        kind = 1 if self.rng.random() < 0.08 else 0
                        self.rivet(tha, yc, base=None, R=0.95, hgt=0.5, kind=kind)
                a += step * self.rng.uniform(0.93, 1.07)
            if gap:                                       # концы у рамки — по паре заклёпок
                for sgn in (-1, 1):
                    ths = np.arange(0, 85, 0.25) * sgn
                    dd = np.array([self.dI_wall(t, yc) for t in ths])
                    thx = ths[np.argmax(dd > FRAME_W + 1.6)]
                    self.rivet(thx, yc + 1.3, R=0.95)
                    self.rivet(thx, yc - 1.3, R=0.95)
            self.lock(yc, lth, ltype, hi)

    def lock(self, yc, lth, ltype, hi):
        """Замок обруча: lap — внахлёст на 3 заклёпках; bolt — накладка с квадратной головкой болта; weld — кузнечная
        сварка косым швом."""
        R0 = self.Rp_at(yc)
        idx = self.ix.q(lth, yc, np.degrees(9.0 / R0), HOOP_HW + 1.0)
        idx = idx[(self.tank | self.lid)[idx]]
        ds, dy = self.loc(idx, lth, yc)
        H = self.o["h"]
        if ltype == "lap":
            # верхний конец шины лежит поверх нижнего: ступень 0.6 см, конец скошен
            xe = -4.5 + 0.6 * dy / HOOP_HW
            on = (ds > xe) & (ds < 4.5) & (np.abs(dy) < HOOP_HW - 0.05)
            lift = 0.55 * sstep(xe, xe + 0.3, ds) * sstep(4.5, 1.5, ds)
            hh = H[idx] + np.where(on, lift, 0)
            self.put(idx, hh, mat=MAT["hoop"], sid=20 + hi, wear=on * sstep(xe + 0.4, xe, ds) * 0.8)
            self.o["cav"][idx] = np.maximum(self.o["cav"][idx], on * np.exp(-((ds - xe) / 0.25) ** 2) * 0.7)
            for k, x in enumerate((-2.8, 0.2, 3.1)):
                self.rivet(lth + np.degrees(x / R0), yc + (0.9 if k == 1 else -0.9), R=1.0, hgt=0.55)
        elif ltype == "bolt":
            on = (np.abs(ds) < 4.0) & (np.abs(dy) < HOOP_HW + 0.5)
            plate = HOOP_T + 0.45 * sstep(4.0, 3.7, np.abs(ds)) * sstep(HOOP_HW + 0.5, HOOP_HW + 0.2, np.abs(dy))
            hh = np.where(on, plate + 0.03 * (n2(ds, dy, 9 + hi) - 0.5), -9)
            self.put(idx, hh, mat=MAT["hoop"], sid=30 + hi)
            q = np.maximum(np.abs(ds), np.abs(dy)) / 1.2           # квадратная головка 2.4 см, фаска
            head = plate + 0.75 * np.clip((1 - q) / 0.25, 0, 1) ** 0.5 * (q < 1)
            win = self.put(idx, np.where(q < 1.0, head, -9), mat=MAT["bolt"], rivet=(q < 1) * 1.0,
                           wear=np.clip(1 - q, 0, 1) * 0.6)
            for x in (-2.8, 2.8):
                self.rivet(lth + np.degrees(x / R0), yc, R=0.85, hgt=0.45)
        else:
            # кузнечная сварка: косой шов поперёк шины — пологий валик с чешуйками
            u = ds - 0.5 * dy
            on = np.abs(dy) < HOOP_HW - 0.1
            bead = np.clip(1 - (u / 1.0) ** 2, 0, 1) * on
            rip = 0.5 + 0.5 * np.cos(dy / 0.7 * 2 * np.pi + u)
            hh = H[idx] + 0.18 * bead ** 0.7 * (0.8 + 0.2 * rip)
            self.put(idx, hh, mat=MAT["hoop"], wear=bead * 0.6)

    # ---------------------------------------------------------------- проём: рамка, откосы, петли, порог
    def frame(self):
        """Рамка-подкова по скосу проёма: плита 6 мм от горла до 12.5 см (2–3 см заходит на стенку), внутренний обод
        завальцован, окалина пластинками, заклёпки по средней линии. Координаты — фронтальная проекция (x, y)."""
        o = self.o
        m = np.where(self.front & (self.dopen < FRAME_W + 1.0) & (self.tank | self.reveal) & (self.y > SILL[1] + 0.5))[0]
        d = self.dopen[m]
        X, yy = self.P[m, 0], self.y[m]
        wob = 0.4 * (fbm2(X * 0.25, yy * 0.25, 61, 3) - 0.5) * 2
        dout = FRAME_W + wob - d                            # до наружной кромки рамки
        plate = 0.6 * sstep(-0.05, 0.3, dout)
        lip = 0.3 * sstep(2.4, 1.6, d)                     # внутренний обод — завальцованная кромка
        f1, f2, cx, cy, h1, h2 = voronoi_c(X, yy, 3.2, 63)
        ham = -0.05 * np.clip(f1 / 1.7, 0, 1) ** 2
        g1, g2, _, _, k1, _ = voronoi_c(X * 1.1, yy, 1.6, 65)   # окалина: пластинки 1–2 см
        keep = (k1 < 0.5) * sstep(FRAME_W, 3.0, d)
        flake = keep * (0.05 - 0.05 * sstep(0.16, 0.03, g2 - g1))
        hh = plate + lip + (ham + flake) * (plate > 0.05)
        win = self.put(m, np.where(dout > -0.3, hh, -9), mat=MAT["frame"], sid=40,
                       tone=0.5 + 0.1 * (n2(X * 0.1, yy * 0.1, 7) - 0.5))
        o["wear"][m] = np.where(win, np.maximum(0.8 * sstep(0.5, 0.0, dout) * (dout > -0.3), 0.6 * lip / 0.3), o["wear"][m])
        o["cav"][m] = np.where(win, np.maximum(o["cav"][m], keep * sstep(0.12, 0.02, g2 - g1) * 0.6), o["cav"][m])
        o["rust"][m] = np.where(win, (1 - keep) * 0.35 * sstep(5, 10, d), o["rust"][m])
        o["heat"][m] = np.where(win, 1.0, o["heat"][m])
        # заклёпки по средней линии рамки (7 см от горла), шаг ~6.5 см
        for (x, y) in self.offset_path(7.0, 6.5):
            if y < SILL[1] + 2.5 or self.hoop_at(y, 1.2):
                continue
            if x < G.CX and any(abs(y - yh) < 3.5 for yh in HINGES_Y):
                continue
            self.rivet_xy(x, y, R=1.0, hgt=0.6, kind=1 if self.rng.random() < 0.1 else 0)

    def offset_path(self, off, step):
        """Точки на расстоянии off снаружи от горла (фронтальная проекция), через step см."""
        L = self.polyI
        pts = []
        n = len(L)
        for i in range(n):
            a, b = L[i], L[(i + 1) % n]
            e = b - a
            ln = np.linalg.norm(e)
            k = max(int(ln / 0.5), 1)
            for t in np.linspace(0, 1, k, endpoint=False):
                pts.append(a + e * t)
        pts = np.array(pts)
        # грубая кривая смещения: для каждой точки контура — точка снаружи на off по нормали, оставить точные
        cand = []
        for i in range(len(pts)):
            e = pts[(i + 1) % len(pts)] - pts[i - 1]
            nrm = np.array([e[1], -e[0]]) / (np.linalg.norm(e) + 1e-9)
            for sg in (1, -1):
                q = pts[i] + sg * nrm * off
                dq, ins = poly_sdist(np.array([q[0]]), np.array([q[1]]), L)
                if not ins[0] and abs(dq[0] - off) < 0.6:
                    cand.append(q)
                    break
        out, acc = [], None
        for q in cand:
            if acc is None or np.linalg.norm(q - acc) >= step:
                out.append(q)
                acc = q
        return out

    def rivet_xy(self, x, y, R=0.95, hgt=0.55, kind=0):
        """Заклёпка в фронтальной проекции (на скосе проёма координаты (th, y) вырождаются)."""
        m = np.where(self.front & (np.abs(self.P[:, 0] - x) < R + 1.0) & (np.abs(self.y - y) < R + 1.0))[0]
        if len(m) == 0:
            return
        dx, dy = self.P[m, 0] - x, self.y[m] - y
        dd = np.hypot(dx + (0.3 * dy if kind == 1 else 0), dy)
        b = self.o["h"][m]
        hh = np.where(dd < R, b + dome(dd, R, hgt, 0.6), b + 0.05 * np.exp(-((dd - R * 1.04) / 0.12) ** 2))
        self.put(m, hh, mat=MAT["rivet"], rivet=(dd < R) * 1.0, wear=np.clip(1 - dd / (0.55 * R), 0, 1) * 0.8,
                 tone=self.rng.random())

    def _inside(self, p):
        _, ins = poly_sdist(np.array([p[0]]), np.array([p[1]]), self.poly_s)
        return bool(ins[0])

    def hinges(self):
        """Петли пропавшей дверцы: на рамке слева — карта с 2 заклёпками и два кольца-навеса с видимым штырём."""
        o = self.o
        for k, yh in enumerate(HINGES_Y):
            idx = np.where(self.front & (np.abs(self.y - yh) < 4.0) & (self.dopen < 9.0)
                           & (self.P[:, 0] < G.CX) & (self.tank | self.reveal))[0]
            d = self.dopen[idx]
            dy = self.y[idx] - yh
            base = 0.6
            leaf = (np.abs(dy) < 1.6) & (d > 1.6) & (d < 7.3)
            hl = base + 0.35 * sstep(7.3, 7.0, d) * sstep(1.6, 1.35, np.abs(dy))
            self.put(idx, np.where(leaf, hl + 0.02 * (n2(d * 2, dy * 2, 70 + k) - 0.5), -9), mat=MAT["hinge"], sid=41)
            # кольца-навесы: два бочонка 1.8 см и зазор с штырём посередине
            kx = 1.15
            dk = d - 1.5
            barrel = (np.abs(dk) < kx) & (np.abs(dy) < 2.9) & (np.abs(dy) > 0.75)
            hb = base + 0.25 + np.sqrt(np.clip(kx ** 2 - dk ** 2, 0, None)) * 0.95
            hb -= 0.15 * sstep(2.6, 2.9, np.abs(dy))
            pin = (np.abs(dk) < 0.42) & (np.abs(dy) <= 0.75)
            hp = base + 0.25 + np.sqrt(np.clip(0.42 ** 2 - dk ** 2, 0, None)) * 0.95
            hh = np.where(barrel, hb, np.where(pin, hp, -9))
            self.put(idx, hh, mat=MAT["hinge"], sid=41, wear=barrel * np.clip(1 - np.abs(dk) / kx, 0, 1) * 0.7,
                     rivet=pin * 1.0)
            o["cav"][idx] = np.maximum(o["cav"][idx], (np.abs(np.abs(dy) - 0.75) < 0.15) * (np.abs(dk) < kx) * 0.9)
            for dx in (3.9, 6.2):
                q = np.where(np.abs(dy) < 0.3)[0]
                if len(q) == 0:
                    continue
                j = q[np.argmin(np.abs(d[q] - dx))]
                self.rivet_xy(self.P[idx[j], 0], yh, R=0.75, hgt=0.4)

    def patch(self):
        """Рифлёная заплата: ромбики шагом 3 см (±45°), кромки рубленые, заклёпки по бокам; верх и низ — под обручами."""
        th0, th1, y0, y1 = PATCH
        idx = self.ix.q((th0 + th1) / 2, (y0 + y1) / 2, (th1 - th0) / 2 + 3, (y1 - y0) / 2 + 1)
        idx = idx[self.tank[idx]]
        ds, dy = self.loc(idx, th0, y0)
        yy = self.y[idx]
        Rm = self.Rp[idx]
        w = np.radians(th1 - th0) * Rm
        wobL = 0.3 * (fbm2(yy * 0.35, 1, 81, 3) - 0.5) * 2
        wobR = 0.3 * (fbm2(yy * 0.35, 2, 82, 3) - 0.5) * 2
        inside = (ds > wobL) & (ds < w + wobR) & (yy > y0) & (yy < y1)
        edge = np.minimum(ds - wobL, w + wobR - ds)
        base = self.o["h"][idx].copy()
        plate = 0.32 * sstep(-0.02, 0.2, edge)
        # ромбики
        gx, gy = ds / 3.0, dy / 3.0
        i, j = np.floor(gx), np.floor(gy)
        lx, ly = (gx - i - 0.5) * 3.0, (gy - j - 0.5) * 3.0
        sgn = np.where(((i + j) % 2) == 0, 1.0, -1.0)
        u = (lx + sgn * ly) / np.sqrt(2)
        v = (lx - sgn * ly) / np.sqrt(2)
        q = (u / 1.25) ** 2 + (v / 0.33) ** 2
        lug = 0.16 * np.clip(1 - q, 0, 1) ** 0.5 * (edge > 0.8)
        wear_l = np.clip(1 - q, 0, 1) * 0.8
        # плита повторяет ковку листа под ней (облегает), но вдвое мягче
        hh = 0.5 * np.maximum(base, -0.1) + plate + lug
        self.put(idx, np.where(inside, hh, -9), mat=MAT["checker"], sid=42, knot=(q < 1) * (edge > 0.8) * 1.0,
                 wear=wear_l, tone=0.45)
        self.o["cav"][idx] = np.maximum(self.o["cav"][idx], inside * np.exp(-(edge / 0.2) ** 2) * 0.6)
        # заклёпки по боковым кромкам
        for side, thx in ((0, th0), (1, th1)):
            yr = y0 + 4.5
            while yr < y1 - 4.0:
                if not self.hoop_at(yr, 1.2):
                    off = np.degrees(1.5 / self.Rp_at(yr)) * (1 if side == 0 else -1)
                    self.rivet(thx + off, yr, R=0.9, hgt=0.5)
                yr += 4.2

    # ---------------------------------------------------------------- затычка, крюк, ковш
    def plug(self):
        thc, yc = PLUG
        idx = self.ix.q(thc, yc - 5, 18.0, 13.0)
        idx = idx[self.tank[idx]]
        ds, dy = self.loc(idx, thc, yc)
        d = np.hypot(ds, dy)
        ang = np.arctan2(dy, ds)
        # тряпка вокруг горлышка: складки, бечёвка в 2 витка
        rag_r = 4.3 + 0.35 * np.sin(ang * 5 + 1.3) + 0.25 * np.sin(ang * 9)
        ragm = (d < rag_r) & (d > 2.1)
        t = np.clip((d - 2.3) / (rag_r - 2.3), 0, 1)
        hr = 2.05 * (1 - t ** 1.6) + 0.22 * np.sin(ang * 7 + 3 * n2(d, ang, 5)) * (1 - t) + 0.25
        hr = hr * sstep(rag_r, rag_r - 0.35, d)
        hr += 0.06 * (n2(ds * 2, dy * 2, 17) - 0.5)
        # хвост тряпки вниз
        tail_c = 0.6 * np.sin(dy * 0.5)
        tw = 1.7 + 0.3 * n2(dy * 0.3, 0, 19)
        tail = (dy < -2.5) & (dy > -11.5) & (np.abs(ds - tail_c) < tw)
        ht = 0.75 + 0.25 * np.sin((ds - tail_c) / tw * 3 + dy * 0.4) - 0.04 * (-dy - 2.5)
        ht = ht * sstep(tw, tw - 0.35, np.abs(ds - tail_c)) * sstep(-11.5, -10.6, dy)
        hcloth = np.maximum(np.where(ragm, hr, -9), np.where(tail, ht, -9))
        base = self.o["h"][idx]
        cl = hcloth > -1
        self.put(idx, np.where(cl, np.maximum(base, 0) + hcloth, -9), mat=MAT["rag"], sid=43,
                 wear=np.clip(np.sin(ang * 7) * 0.5, 0, 1) * cl, tone=0.5)
        # бечёвка: два витка
        for k, rr in enumerate((2.85, 3.35)):
            tw_ = np.abs(d - rr)
            twine = tw_ < 0.26
            htw = 2.05 * (1 - np.clip((rr - 2.3) / 2.0, 0, 1) ** 1.6) + 0.25 + np.sqrt(np.clip(0.26 ** 2 - tw_ ** 2, 0, None))
            htw += 0.06 * np.cos(ang * 40 + k)                 # свив
            self.put(idx, np.where(twine, np.maximum(base, 0) + htw, -9), mat=MAT["twine"], sid=44)
        # пробка: торец с годичными кольцами, радиальная трещина, фаска
        pm = d < 2.35
        hp = 2.5 - 0.35 * sstep(1.85, 2.35, d)
        rings = 0.5 + 0.5 * np.cos(2 * np.pi * (d + 0.15 * np.sin(ang * 3)) / 0.62)
        crack = np.exp(-((np.angle(np.exp(1j * (ang - 0.9))) * d) / 0.16) ** 2) * (d > 0.3)
        hp = hp - 0.035 * rings - 0.22 * crack
        self.put(idx, np.where(pm, np.maximum(base, 0) + hp, -9), mat=MAT["plug"], sid=45, knot=rings * pm,
                 cav=crack * pm)

    def ladle(self):
        """Крюк (лапка на 2 заклёпках, гнутый пруток), петля бечёвки, ковш ~33 см: ручка с гранями ножа, чаша 10 × 12 см
        между обручами 62.5 и 91.5 (ручка ложится поверх обруча 91.5)."""
        thc, yh = HOOK
        idx = self.ix.q(thc, 88.0, 14.0, 24.0)
        idx = idx[self.tank[idx]]
        ds, dy = self.loc(idx, thc, 0.0)
        yy = self.y[idx]
        base = np.maximum(self.o["h"][idx], 0)
        lap = (np.abs(ds) < 1.3) & (yy > yh - 2.2) & (yy < yh + 2.0)
        self.put(idx, np.where(lap, base + 0.4 * sstep(1.3, 1.05, np.abs(ds)) * sstep(yh + 2.0, yh + 1.75, yy), -9),
                 mat=MAT["hook"], sid=46)
        for yr in (yh + 1.0, yh - 1.3):
            self.rivet(thc, yr, R=0.7, hgt=0.35)
        yt = yy - (yh - 1.6)
        hc = 0.7 + 1.8 * sstep(0, -4.0, yt)
        rod = (np.abs(ds) < 0.45) & (yt < 0.5) & (yt > -5.8)
        hr = hc + np.sqrt(np.clip(0.45 ** 2 - ds ** 2, 0, None))
        self.put(idx, np.where(rod, base + hr, -9), mat=MAT["hook"], sid=46,
                 wear=rod * np.clip(1 - np.abs(ds) / 0.45, 0, 1) * 0.6)
        cy0 = yh - 7.4
        eu, ev = ds / 1.25, (yy - cy0) / 2.7
        rr = np.hypot(eu, ev)
        loop = np.abs(rr - 1.0) < 0.2
        hl = 1.9 - 0.6 * (yy < cy0) + np.sqrt(np.clip(0.25 ** 2 - ((rr - 1) * 1.25) ** 2, 0, None))
        self.put(idx, np.where(loop, base + hl + 0.05 * np.cos(np.arctan2(ev, eu) * 30), -9), mat=MAT["twine"], sid=47)
        yt0, yt1 = yh - 5.6, 85.6
        hand = (yy < yt0) & (yy > yt1)
        wdt = 1.45 - 0.3 * (yt0 - yy) / (yt0 - yt1)
        on = hand & (np.abs(ds) < wdt)
        fi = np.floor((yy - yt1) / 2.6)
        a1 = 0.3 + 0.25 * n2(fi, 1, 91)
        a2 = 0.3 + 0.25 * n2(fi, 2, 92)
        xq = ds / wdt
        fac = 0.95 - 2 * a1 * np.clip(-xq - 0.3, 0, None) - 2 * a2 * np.clip(xq - 0.3, 0, None)   # грани ножа
        hhand = 0.8 + np.clip(fac, 0.15, 0.95) * 1.1 - 0.15 * sstep(yt0 - 1.0, yt0, yy)
        hole = np.hypot(ds, yy - (yt0 - 1.6)) < 0.55
        hhand = np.where(hole, 0.7, hhand)
        grain = 0.5 + 0.5 * np.sin(ds * 7 + 1.5 * n2(yy * 0.4, ds, 93))
        self.put(idx, np.where(on, base + hhand + 0.03 * grain, -9), mat=MAT["ladle"], sid=48, knot=grain * on * 0.5,
                 cav=hole * 1.0)
        cy = 79.6
        q = np.hypot(ds / 5.2, (yy - cy) / 6.2)
        rim = 2.9 - 1.7 * np.clip(1 - (q / 0.86) ** 2, 0, 1) ** 0.8
        rim = np.where(q < 1, rim - 0.3 * sstep(0.9, 1.0, q), 2.6 * sstep(1.12, 1.0, q))
        bowl = q < 1.12
        grain2 = 0.5 + 0.5 * np.sin((yy - cy) * 5 + 2 * n2(ds * 0.5, yy * 0.3, 94))
        self.put(idx, np.where(bowl, base + rim + 0.03 * grain2, -9), mat=MAT["ladle"], sid=48,
                 cav=np.clip(1 - q / 0.7, 0, 1) * 0.5 * bowl, wear=bowl * sstep(0.8, 0.95, q) * sstep(1.05, 0.97, q) * 0.7,
                 knot=grain2 * bowl * 0.4)

    # ---------------------------------------------------------------- накипь
    def drips(self):
        """Корка накипи: потёки-ленты с толщиной 0.5–1.2 мм из-под обручей, швов и затычки, капля на конце, 2–3
        наслоения. Длины по степенному закону, гроздьями; у топки (жарко) мало."""
        rng = np.random.default_rng(55)
        o = self.o
        srcs = []
        hy = [h[0] for h in HOOPS]
        for k, yc in enumerate(hy):
            below = [h for h in hy if h < yc]
            stop = (max(below) + HOOP_HW + 0.4) if below else 55.5
            ncl = (3, 4, 4, 3, 2)[k]
            for c in range(ncl):
                thc = rng.uniform(-180, 180)
                if abs(thc) < 70 and yc < 120:
                    thc = 70 + rng.uniform(0, 110) if thc > 0 else -70 - rng.uniform(0, 110)
                back = abs(thc) > 110
                for d in range(rng.integers(2, 7 if back else 5)):
                    Lmax = yc - HOOP_HW - stop
                    L = min(3.0 * (1 - rng.random()) ** (-1 / 1.2), Lmax)
                    w = rng.uniform(1.3, 2.6)
                    srcs.append((thc + np.degrees(rng.normal(0, 4.5) / self.Rp_at(yc)), yc - HOOP_HW + 0.1, L, w,
                                 rng.uniform(0.11, 0.24)))
        srcs.append((PLUG[0] + 0.3, PLUG[1] - 11.0, 14.0, 1.9, 0.25))       # из-под тряпки — до самого низа
        srcs.append((PLUG[0] + 2.4, PLUG[1] - 9.0, 7.0, 1.2, 0.16))
        srcs.append((165.0, 84.0, 22.0, 1.6, 0.2))                          # из прогара сзади
        for (thc, y0, L, w, t) in srcs:
            if L < 1.0:
                continue
            idx = self.ix.q(thc, y0 - L / 2, np.degrees((w + 2) / self.Rp_at(y0)), L / 2 + w + 1)
            idx = idx[self.tank[idx]]
            if len(idx) == 0:
                continue
            ds, dy = self.loc(idx, thc, y0)
            tt = np.clip(-dy / L, 0, 1)
            seed = int(abs(thc * 7 + y0 * 3)) % 9999
            cen = 0.5 * w * (n2(-dy * 0.25, seed, seed) - 0.5) * 2 + 0.25 * np.sin(-dy * 0.6 + seed)
            wid = w * (1 - 0.4 * tt) * (0.85 + 0.3 * n2(-dy * 0.5, seed + 1, seed))
            x = (ds - cen) / (wid / 2)
            body = (np.abs(x) < 1) & (dy < 0.2) & (dy > -L)
            prof = np.sqrt(np.clip(1 - x ** 2, 0, 1)) ** 0.6
            # наслоения: ступеньки поперёк потёка
            terr = 0.75 + 0.25 * np.clip(np.sin(-dy / 1.7 * np.pi + seed) * 2, -1, 1)
            hb = t * prof * terr * sstep(0.2, -0.5, dy)
            bulb_c = -L + 0.2
            bd = np.hypot(ds - (cen if np.isscalar(cen) else cen), (dy - bulb_c) * 0.9)
            Rb = 0.65 * w * 0.7
            bulb = bd < Rb
            hbulb = 1.6 * t * np.clip(1 - (bd / Rb) ** 2, 0, 1) ** 0.5
            hh = np.maximum(np.where(body, hb, 0), np.where(bulb, hbulb, 0))
            on = hh > 0.002
            sel = idx[on]
            o["h"][sel] += hh[on]
            o["crust"][sel] = np.maximum(o["crust"][sel], np.clip(hh[on] / (0.6 * t), 0, 1))

    # ---------------------------------------------------------------- крышка
    def lid_top(self):
        o = self.o
        m = np.where(self.lid)[0]
        u = self.P[m, 0] - G.CX
        v = self.P[m, 2] - G.CZ
        rr = np.hypot(u, v)
        ang = np.degrees(np.arctan2(u, v))
        petals = (10.0, 82.0, 158.0, 228.0, 300.0)
        hm = np.zeros(len(m))
        sid = np.zeros(len(m))
        for k, a in enumerate(petals):
            x = np.radians(wrapdeg(ang - a)) * np.maximum(rr, 1)
            wob = 0.3 + 0.2 * (n2(rr * 0.4, k, 120 + k) - 0.5) * 2
            lap = 0.25 * np.clip(1 - (x + wob) / 4.5, 0, 1) ** 0.6 * sstep(-wob - 0.02, -wob + 0.18, x) * (x < 6)
            hm += lap
            o["cav"][m] = np.maximum(o["cav"][m], 0.5 * np.exp(-((x + wob + 0.1) / 0.25) ** 2))
        f1, f2, cx, cy, h1, h2 = voronoi_c(u, v, 4.0, 131)
        hm += 0.02 * ((u - cx) * np.cos(6.28 * h1) + (v - cy) * np.sin(6.28 * h1)) - 0.1 * np.clip(f1 / 2.4, 0, 1) ** 2
        # завальцованная кромка крышки
        hm += 0.45 * np.exp(-((rr - 26.8) / 0.9) ** 2)
        o["h"][m] += hm
        o["mat"][m] = MAT["lid"]
        o["sid"][m] = 50
        o["tone"][m] = 0.5
        o["wear"][m] = np.maximum(o["wear"][m], np.exp(-((rr - 26.8) / 0.7) ** 2) * 0.8)
        # кольцо заклёпок и заклёпки по швам лепестков
        Pl = self.P[m]
        for k in range(22):
            a = 2 * np.pi * k / 22 + 0.1
            self._lid_rivet(Pl, m, G.CX + np.sin(a) * 22.5, G.CZ + np.cos(a) * 22.5)
        for a in petals:
            for rad in (12.0, 17.0):
                ar = np.radians(a) + 1.3 / rad
                self._lid_rivet(Pl, m, G.CX + np.sin(ar) * rad, G.CZ + np.cos(ar) * rad)

    def lid_stones(self):
        """Колотый базальт на крышке вокруг отверстия: камни 3–8 см — грани раскола (минимум из 5 плоскостей),
        усечённый верх, сколы рёбер, щели между камнями; поверх — второй ярус мелочи. Видно сверху."""
        o = self.o
        m = np.where(self.lid)[0]
        u = self.P[m, 0] - G.CX
        v = self.P[m, 2] - G.CZ
        rr = np.hypot(u, v)
        zone = (rr > 9.0) & (rr < 21.8)
        base = o["h"][m].copy()
        # горка выше в середине кольца; всё ниже 3.6 см — вытяжка лучей запекания группы 4 см
        prof = 0.4 + 1.0 * np.sin(np.pi * np.clip((rr - 9.0) / 12.8, 0, 1))

        def tier(cell, seed, hmin, hmax, keep):
            f1, f2, cx, cy, h1, h2 = voronoi_c(u, v, cell, seed)
            du, dv = u - cx, v - cy
            planes = []
            for k in range(5):
                a = 2 * np.pi * (k / 5 + h1 + 0.07 * np.sin(k * 3.1 + h2 * 9))
                s = 0.55 + 0.7 * ((h2 * 7.3 + k * 0.37) % 1.0)
                planes.append(-s * (du * np.cos(a) + dv * np.sin(a)))
            planes = np.stack(planes, 0)
            ps = np.sort(planes, 0)
            T = hmin + (hmax - hmin) * h2
            hs = np.minimum(T + ps[0], T - 0.35 * cell * 0.1)                  # усечённый верх
            ridge = sstep(0.35, 0.0, ps[1] - ps[0]) + sstep(0.4, 0.0, (T - 0.035 * cell) - (T + ps[0]))
            chip = (n2(u * 1.4 + seed, v * 1.4, seed + 1) > 0.66) * ridge * 0.45
            hs = hs - chip + 0.05 * (n2(u * 2.2, v * 2.2, seed + 2) - 0.5)
            gap = f2 - f1
            ok = keep(h1) & (gap > 0.22)
            hs = np.where(ok, hs * sstep(0.22, 0.6, gap) ** 0.3, -9)
            return hs, ridge * ok, h1, ok

        h_big, r_big, id_big, ok_big = tier(5.2, 301, 1.4, 2.6, lambda h: h < 0.92)
        h_sm, r_sm, id_sm, ok_sm = tier(2.6, 303, 0.8, 1.5, lambda h: h < 0.45)
        h_sm = np.where(ok_sm, h_sm + prof * 0.8, -9)
        h_big = np.where(ok_big, h_big + prof * 0.6, -9)
        hs = np.minimum(np.maximum(h_big, h_sm), 3.6)
        on = zone & (hs > base)
        sel = m[on]
        o["h"][sel] = hs[on]
        o["mat"][sel] = MAT["stone"]
        o["wear"][sel] = np.where(h_big[on] >= h_sm[on], r_big[on], r_sm[on])
        o["cav"][sel] = 0
        o["rivet"][sel] = 0
        o["tone"][sel] = np.where(h_big[on] >= h_sm[on], id_big[on], id_sm[on])
        o["sid"][sel] = 51
        # между камнями — щели до крышки (тень), их цвет — сажа
        gapz = zone & ~on
        o["cav"][m[gapz]] = np.maximum(o["cav"][m[gapz]], 0.45)

    def _lid_rivet(self, Pl, m, x, z, R=0.95):
        d = np.hypot(Pl[:, 0] - x, Pl[:, 2] - z)
        near = d < R + 0.3
        idx = m[near]
        dd = d[near]
        hh = self.o["h"][idx] + dome(dd, R, 0.55, 0.6)
        self.put(idx, hh, mat=MAT["rivet"], rivet=(dd < R) * 1.0, wear=np.clip(1 - dd / (0.55 * R), 0, 1) * 0.8)

    # ---------------------------------------------------------------- откосы проёма
    def reveal_face(self):
        o = self.o
        m = np.where(self.reveal)[0]
        u = np.radians(self.th[m]) * 30.0
        yy = self.y[m]
        g1, g2, _, _, k1, _ = voronoi_c(u * 1.1 + self.r[m] * 0.5, yy, 1.6, 141)
        keep = k1 < 0.55
        o["h"][m] += keep * (0.05 - 0.05 * sstep(0.16, 0.03, g2 - g1)) + 0.04 * (fbm2(u * 0.4, yy * 0.4, 142, 3) - 0.5)
        o["mat"][m] = np.where(o["mat"][m] == MAT["frame"], MAT["frame"], MAT["reveal"])
        o["cav"][m] = np.maximum(o["cav"][m], keep * sstep(0.14, 0.02, g2 - g1) * 0.6)
        o["heat"][m] = 1.0

    # ---------------------------------------------------------------- пояс реек
    def boards(self):
        o = self.o
        m = np.where(self.board)[0]
        th = self.th[m]
        yy = self.y[m]
        RB = 47.0
        rng = np.random.default_rng(71)
        H = np.zeros(len(m))
        cav = np.zeros(len(m))
        grain = np.zeros(len(m))
        knot = np.zeros(len(m))
        rivet = np.zeros(len(m))
        char = np.zeros(len(m))
        tone = np.zeros(len(m)) + 0.5
        sid = np.zeros(len(m))
        mat = np.full(len(m), float(MAT["slat"]))
        rust = np.zeros(len(m))
        dent = np.zeros(len(m))
        self.nails = []
        board_id = 0
        for row in range(4):
            y0, y1 = ROWS[row], ROWS[row + 1]
            Hh = y1 - y0
            inrow = (yy >= y0 - (0 if row == 0 else 0.0)) & (yy < y1 + (0.5 if row == 3 else 0))
            if row == 0:
                inrow |= yy < y0
            # стыки досок в ряду (вразбежку)
            start = rng.uniform(-180, 180)
            joints = [start]
            a = start
            while True:
                a += rng.uniform(70, 115)
                if a > start + 360 - 55:
                    break
                joints.append(a)
            joints = np.array(joints)
            rel = (th[inrow] - start) % 360
            jr = (joints - start) % 360
            bi = np.searchsorted(jr, rel, "right") - 1
            bi = np.clip(bi, 0, len(joints) - 1)
            a0 = jr[bi]
            a1 = np.append(jr[1:], 360.0)[bi]
            xa = np.radians(rel - a0) * RB                   # от левого торца доски, см
            xb = np.radians(a1 - rel) * RB                   # до правого торца
            Lb = np.radians(a1 - a0) * RB
            v = yy[inrow] - y0                               # поперёк доски, снизу
            sel = np.where(inrow)[0]
            # толщина внахлёст: внизу 0.9, вверху 0.25 (нижняя кромка верхнего ряда ложится на верх нижнего)
            SLOT = 0.75 if row > 0 else 0.0
            vv = v - SLOT
            hb = 0.3 + 0.9 * np.clip(1 - vv / (Hh - SLOT), 0, 1)
            # коробление: кромки чуть выше середины
            hb += 0.18 * ((2 * vv / (Hh - SLOT) - 1) ** 2 - 0.3)
            # нижняя кромка доски — чёткая (скругление 2.5 мм), под ней щель-тень до железа
            hb -= 0.35 * sstep(0.25, 0.0, vv)
            slot = vv < 0
            hb = np.where(slot, -0.25 + 0.05 * n2(xa * 0.7, row, 76), hb)
            if row == 0:                                     # нижний ряд: размочаленная кромка
                fr = 0.6 + 0.5 * n2(xa * 0.8, 0, 73)
                hb -= 0.35 * sstep(fr, 0.0, v) * (0.6 + 0.4 * n2(xa * 2.5, v * 2, 74))
            if row == 3:                                     # верхняя кромка — тонкий торец
                hb -= 0.15 * sstep(Hh - 0.5, Hh + 0.3, v)
            # торцы: зазор, фаска
            xe = np.minimum(xa, xb)
            gap = xe < 0.18
            hb = np.where(gap, 0.02, hb - 0.18 * sstep(0.7, 0.18, xe))
            ccv = np.maximum(gap * 1.0 + 0.4 * sstep(0.5, 0.18, xe), slot * 1.0)
            # волокна, сучки, трещины — у каждой доски свои
            gr = np.zeros(len(sel))
            kn = np.zeros(len(sel))
            cr = np.zeros(len(sel))
            ub = np.unique(bi)
            for b in ub:
                mb = bi == b
                seed = 700 + board_id + b
                L_ = Lb[mb][0]
                rb = np.random.default_rng(seed)
                knots = [(rb.uniform(8, max(L_ - 8, 9)), rb.uniform(2.5, Hh - 2.5), rb.uniform(0.8, 1.7))
                         for _ in range(rb.integers(0, 3))]
                g = grain_relief(xa[mb], v[mb], rb.uniform(0.5, 4.0), rb.uniform(-0.03, 0.03), rb.uniform(-8, Hh + 8),
                                 rb.uniform(2.8, 3.8), seed, knots)
                gr[mb] = g
                for (ka, kc, kr) in knots:
                    dk = np.hypot((xa[mb] - ka) / 1.25, v[mb] - kc)
                    kn[mb] = np.maximum(kn[mb], sstep(kr * 1.05, kr * 0.8, dk))
                    if rb.random() < 0.25:                    # выпавший сучок — дыра с тёмным дном
                        cr[mb] = np.maximum(cr[mb], 2 * sstep(kr * 0.85, kr * 0.6, dk))
                # торцевые трещины от каждого торца + продольная трещина усушки
                for end in (0, 1):
                    for _ in range(rb.integers(0, 2)):
                        vc = rb.uniform(3, Hh - 3)
                        ln = rb.uniform(2.5, 6.5)
                        xx = (xa[mb] if end == 0 else xb[mb])
                        w_ = 0.12 * np.clip(1 - xx / ln, 0, 1) ** 1.2
                        cen = vc + 0.3 * np.sin(xx * 0.3 + vc)
                        cr[mb] = np.maximum(cr[mb], sstep(w_ + 0.12, w_ * 0.4, np.abs(v[mb] - cen)) * (xx < ln))
                tone[sel[mb]] = 0.5 + 0.8 * (rb.random() - 0.5)
                sid[sel[mb]] = board_id + b
            # глубже вытерто у низа (вода), под проёмом — обуглено
            hb += np.where(slot, 0, (0.14 + 0.04 * (row == 0)) * (gr - 0.35) + 0.12 * (fbm2(xa * 0.08, v * 0.35, 75 + row, 3) - 0.5))
            hb -= 0.35 * np.clip(cr, 0, 1) * (cr <= 1.0) + 0.45 * (cr > 1.0)
            hb += 0.05 * kn - 0.02 * kn * (n2(xa * 3, v * 3, 77) - 0.5)
            H[sel] = hb
            cav[sel] = np.maximum(ccv, np.clip(cr, 0, 1))
            grain[sel] = gr
            knot[sel] = kn
            # гвозди: по 2 у каждого торца, пары через ~40 см
            for b in ub:
                a0b, a1b = joints[b], (joints[(b + 1) % len(joints)] if b + 1 < len(joints) else joints[0] + 360)
                L_ = np.radians(a1b - a0b) * RB
                xs = [3.0, L_ - 3.0] + list(np.arange(40.0, L_ - 20.0, 40.0))
                for xn in xs:
                    for vf in (0.33, 0.7):
                        tn = a0b + np.degrees(xn / RB) + rng.normal(0, 0.3)
                        self.nails.append((wrapdeg(tn), y0 + vf * Hh + rng.normal(0, 0.4), rng.integers(0, 6)))
            board_id += len(joints)
        o["h"][m] = H
        o["cav"][m] = cav
        o["wear"][m] = grain
        o["knot"][m] = knot
        o["tone"][m] = tone
        o["sid"][m] = sid
        o["mat"][m] = mat
        # доска от поддона (верхний ряд сзади-слева): дуги пилы, старые дыры от гвоздей
        pb = m[(np.abs(wrapdeg(th + 115)) < 16) & (yy > ROWS[2]) & (yy < ROWS[3])]
        if len(pb):
            sp, dyp = self.loc(pb, -115, ROWS[2])
            arc = np.hypot(sp + 18, dyp + 24)
            o["h"][pb] += 0.04 * np.sin(2 * np.pi * arc / 1.5)
            for (hx, hy) in ((-8, 3.5), (-8, 6.0), (-8, 8.5), (6, 4.0), (6, 7.5), (11, 9.0)):
                dh = np.hypot(sp - hx, dyp - hy)
                o["h"][pb] -= 0.35 * sstep(0.35, 0.2, dh)
                o["cav"][pb] = np.maximum(o["cav"][pb], sstep(0.4, 0.2, dh))
                o["rust"][pb] = np.maximum(o["rust"][pb], 0.6 * sstep(1.0, 0.3, dh))
        # выпавший кусок верхнего ряда сзади: в дыре — ржавое железо бака с раковинами
        mb = m[(np.abs(wrapdeg(th - 158)) < 11) & (yy > ROWS[3] + 0.8)]
        if len(mb):
            sp, dyp = self.loc(mb, 158, ROWS[3])
            wob = 0.8 * (n2(dyp * 0.5, 1, 160) - 0.5) * 2
            edge = np.radians(11) * 47 - np.abs(sp) + wob
            out = edge > 0
            f1, f2, cx, cy, h1, h2 = voronoi_c(sp, dyp, 1.1, 161)
            pits = (f1 < 0.4) & (h2 < 0.5)
            hin = -0.1 - 0.06 * pits * np.clip(1 - f1 / 0.4, 0, 1)
            o["h"][mb] = np.where(out, hin, o["h"][mb])
            o["mat"][mb] = np.where(out, MAT["behind"], o["mat"][mb])
            o["rust"][mb] = np.where(out, 1.0, o["rust"][mb])
            o["cav"][mb] = np.where(out, 0.4 + 0.6 * pits, np.maximum(o["cav"][mb], sstep(0.6, 0.0, edge) * 0.8))
        # обугливание под проёмом: два верхних ряда, сильнее к порогу
        cz = m[(np.abs(wrapdeg(th - G.OPEN_TH)) < 50) & (yy > 34)]
        if len(cz):
            sp, dyp = self.loc(cz, G.OPEN_TH, 0)
            edge = fbm2(sp * 0.09, self.y[cz] * 0.15, 173, 3)
            wid = np.radians(26 + 16 * fbm2(self.y[cz] * 0.2, 3, 174, 2)) * 47
            amt = sstep(39, 48, self.y[cz] + 12 * (edge - 0.5)) * sstep(wid + 6, wid - 3, np.abs(sp))
            amt = np.clip(amt * (0.7 + 0.6 * n2(sp * 0.15, self.y[cz] * 0.15, 171)), 0, 1)
            dh, crk = alligator(sp, self.y[cz], 2.4, 172)
            o["h"][cz] += dh * amt
            o["char"][cz] = amt
            o["cav"][cz] = np.maximum(o["cav"][cz], crk * amt)
            o["mat"][cz] = np.where(amt > 0.35, MAT["char"], o["mat"][cz])

    def nails_and_wire(self):
        o = self.o
        for (tn, yn, kind) in self.nails:
            if not self.board_at(tn, yn):
                continue
            idx = self.ix.q(tn, yn, np.degrees(2.2 / 47), 2.2)
            idx = idx[self.board[idx]]
            if len(idx) == 0 or (o["mat"][idx] == MAT["behind"]).any() or (o["mat"][idx] == MAT["sill"]).any():
                continue
            ds, dy = self.loc(idx, tn, yn)
            r = 0.68
            q = ((np.abs(ds) / r) ** 4 + (np.abs(dy) / r) ** 4) ** 0.25
            lift = {0: 0.1, 1: 0.0, 2: 0.3, 3: 0.14, 4: 0.1, 5: 0.1}[int(kind)]
            dd = np.hypot(ds, dy)
            base = o["h"][idx]
            o["h"][idx] -= 0.06 * np.clip(1 - ((dd - 0.95) / 0.4) ** 2, 0, 1)       # смятое дерево вокруг
            if kind == 1:
                o["h"][idx] -= 0.15 * np.clip(1 - (dd / 1.3) ** 2, 0, 1) ** 2         # забит глубже, воронка
            hh = base + lift + 0.14 * np.sqrt(np.clip(1 - q ** 2, 0, 1)) - 0.04 * (np.abs(ds) + np.abs(dy)) / r
            if kind == 3:
                hh += 0.15 * ds / r
            head = q < 1
            self.put(idx, np.where(head, hh, -9), mat=MAT["nail"], rivet=head * 1.0, wear=head * 0.3)
            o["rust"][idx] = np.maximum(o["rust"][idx], np.clip(1 - dd / 2.0, 0, 1) * 0.8)
            if kind == 4:                                      # «улыбка» молотка рядом
                a = self.rng.uniform(0, 2 * np.pi)
                cx, cy = 1.25 * np.cos(a), 1.25 * np.sin(a)
                dc = np.hypot(ds - cx, dy - cy)
                arc = np.exp(-((dc - 0.95) / 0.16) ** 2) * (((ds - cx) * np.cos(a) + (dy - cy) * np.sin(a)) > 0.3)
                o["h"][idx] -= 0.07 * arc
                o["dent"][idx] = np.maximum(o["dent"][idx], arc)
        # проволока: 2 пряди Ø 6 мм, свив 1.4 см; под ней борозда в досках
        for wi, yw in enumerate(WIRES):
            idx = np.where(self.board & (np.abs(self.y - yw) < 2.0))[0]
            s = np.radians(self.th[idx] % 360.0) * 47.0
            sag = 0.4 * np.sin(np.radians(self.th[idx]) * 3 + wi)
            pitch = 2 * np.pi * 47.0 / round(2 * np.pi * 47.0 / 1.4)
            dy = self.y[idx] - yw - sag
            o["h"][idx] -= 0.08 * np.exp(-(dy / 0.45) ** 2)
            base = o["h"][idx]
            best = np.full(len(idx), -9.0)
            for k in range(2):
                ph = 2 * np.pi * s / pitch + k * np.pi
                cy = 0.19 * np.cos(ph)
                cz = 0.3 + 0.19 * np.sin(ph)
                dd = np.abs(dy - cy)
                hk = np.where(dd < 0.3, base.max() * 0 + np.maximum(base, 0.2) + cz + np.sqrt(np.clip(0.3 ** 2 - dd ** 2, 0, None)), -9)
                best = np.maximum(best, hk)
            self.put(idx, best, mat=MAT["wire"], rivet=(best > -1) * 0.0, wear=(best > -1) * 0.3, sid=60 + wi)
            o["rust"][idx] = np.maximum(o["rust"][idx], (best > -1) * 1.0 + 0.2 * np.exp(-(dy / 1.0) ** 2))
        # скрутка верхней проволоки: косичка вниз на 3.5 см
        idx = self.ix.q(TWIST_TH, WIRES[0] - 2, 6.0, 4.0)
        idx = idx[self.board[idx]]
        ds, dy = self.loc(idx, TWIST_TH, WIRES[0])
        on = (dy < 0.3) & (dy > -3.6)
        best = np.full(len(idx), -9.0)
        for k in range(2):
            ph = 2 * np.pi * dy / 0.9 + k * np.pi
            cx = 0.22 * np.cos(ph)
            cz = 0.65 + 0.22 * np.sin(ph) - 0.06 * (-dy)
            dd = np.abs(ds - cx)
            best = np.maximum(best, np.where(on & (dd < 0.3), np.maximum(o["h"][idx], 0.2) + cz + np.sqrt(np.clip(0.09 - dd ** 2, 0, None)), -9))
        self.put(idx, best, mat=MAT["wire"], wear=(best > -1) * 0.3, sid=62)

    def board_at(self, th, y):
        return y < BOARD_TOP - 0.5

    def sill(self):
        """Железный порог под проёмом: полоса на заклёпках, задиры от поленьев, светлый металл в задирах."""
        o = self.o
        idx = np.where((np.abs(wrapdeg(self.th - G.OPEN_TH)) < G.OPEN_HW + 4) & (self.y > SILL[0] - 0.5)
                       & (self.y < SILL[1] + 0.5) & ~self.reveal)[0]
        s = np.radians(wrapdeg(self.th[idx] - G.OPEN_TH)) * 47.0
        yy = self.y[idx]
        w = np.radians(G.OPEN_HW + 4) * 47.0
        wob = 0.3 * (fbm2(s * 0.3, 0, 181, 3) - 0.5) * 2
        e = np.minimum(np.minimum(w - np.abs(s), yy - SILL[0] - wob), 99)
        plate = 0.9 + 0.05 * (n2(s * 0.5, yy * 0.5, 182) - 0.5) + 0.15 * sstep(SILL[0] + 2.5, SILL[0] + 0.3, yy)
        hh = plate * sstep(-0.02, 0.22, e)
        sc = np.zeros(len(idx))
        rng = np.random.default_rng(183)
        for _ in range(7):
            yc = rng.uniform(SILL[0] + 1.2, 55.5)
            sc0, L = rng.uniform(-w + 6, w - 6), rng.uniform(6, 15)
            t = (s - sc0) / L
            on = (t > 0) & (t < 1)
            dyy = yy - (yc + 0.4 * t)
            g = np.exp(-(dyy / 0.3) ** 2) * on * np.sin(np.pi * np.clip(t, 0, 1)) ** 0.5
            sc = np.maximum(sc, g)
        hh -= 0.06 * sc
        win = self.put(idx, np.where(e > -0.3, hh, -9), mat=MAT["sill"], sid=49, wear=sc * 1.0, tone=0.5)
        o["dent"][idx] = np.where(win, sc, o["dent"][idx])
        for k in range(-5, 6):
            thr = G.OPEN_TH + np.degrees(k * 7.4 / 47.0)
            self.rivet(thr, SILL[0] + 2.0, R=0.95, hgt=0.55)

    # ---------------------------------------------------------------- всё вместе
    def run(self, log=print):
        import time
        t = time.time()
        steps = [("sheets", self.sheets), ("dents", self.dents), ("pillows", self.pillows), ("rust", self.rust),
                 ("lid", self.lid_top), ("stones", self.lid_stones), ("reveal", self.reveal_face),
                 ("boards", self.boards),
                 ("hoops", self.hoops), ("frame", self.frame), ("hinges", self.hinges), ("patch", self.patch),
                 ("sill", self.sill), ("plug", self.plug), ("ladle", self.ladle), ("nails", self.nails_and_wire),
                 ("drips", self.drips)]
        for name, fn in steps:
            fn()
            log(f"  field {name}: {time.time() - t:.1f} s")
        return self.o


def body(P, N, log=print):
    return Body(np.asarray(P, float), np.asarray(N, float)).run(log)


# ====================================================================== нутро топки (острова 3, 5, 6)
FX, FZ, FY0 = 4.5, 2.5, 56.0          # центр топки и уровень пола, см
LOGS = (  # (x, z центра, угол оси град. в плоскости xz, длина, радиус, приподнят над золой, колотое?)
    (-4.0, 6.0, 25.0, 34.0, 4.3, 0.0, False),
    (7.0, 9.0, -38.0, 30.0, 4.6, 4.5, False),
    (2.0, -9.0, 82.0, 28.0, 4.0, 0.0, True),
    (-11.0, -4.0, -70.0, 22.0, 3.2, 0.0, False),
)


class Fire:
    """Нутро топки: свод и стенки — кладка шамотного кирпича; пол — зола, берёзовые поленья, угли (свечение — в маске
    heat). Видно только через проём; огонь игра рисует сама."""

    def __init__(self, P, N, seed=9):
        self.P, self.N = P, N
        n = len(P)
        self.o = {k: np.zeros(n) for k in KEYS}
        self.o["tone"][:] = 0.5
        self.o["sid"][:] = -1
        self.floor = (N[:, 1] > 0.6) & (P[:, 1] < 61)
        self.wall = ~self.floor

    def bricks(self):
        o = self.o
        m = np.where(self.wall)[0]
        P = self.P[m]
        dx, dz = P[:, 0] - FX, P[:, 2] - FZ
        r = np.hypot(dx, dz)
        az = np.arctan2(dx, dz)
        el = np.arctan2(P[:, 1] - FY0, np.maximum(r, 1.0))
        R = 34.0
        u = az * np.maximum(r, 12.0)                       # вдоль ряда
        v = el * R                                         # по меридиану
        BH, BL, J = 10.5, 21.0, 1.0                        # кирпич 21 × 10.5, шов 1 см
        row = np.floor(v / BH)
        fv = v - row * BH
        uo = u + (row % 2) * BL * 0.5 + 3.1 * row
        col = np.floor(uo / BL)
        fu = uo - col * BL
        du = np.minimum(fu, BL - fu)
        dv = np.minimum(fv, BH - fv)
        d = np.minimum(du, dv)
        hid = (col * 7919 + row * 104729) % 1000 / 1000.0
        joint = sstep(J * 0.5 + 0.15, J * 0.5 - 0.1, d)
        face = 0.06 * np.clip(d / 2.5, 0, 1) ** 0.5            # лицо кирпича чуть выпуклое
        chip = (n2(u * 0.9, v * 0.9, 201) > 0.68) * sstep(2.2, 0.6, d) * 0.18   # сколы углов и кромок
        crack_line = np.abs(fu - BL * (0.3 + 0.4 * hid) - 1.2 * np.sin(fv * 0.6 + hid * 9))
        crack = (hid > 0.75) * sstep(0.22, 0.05, crack_line) * (d > 0.6)
        missing = (hid > 0.965)                             # выпавший кирпич: видно железо
        h = face - 0.35 * joint - chip - 0.25 * crack + 0.03 * (n2(u * 1.5, v * 1.5, 202) - 0.5)
        h = np.where(missing, -0.6 + 0.04 * n2(u * 2, v * 2, 203), h)
        o["h"][m] = h
        o["cav"][m] = np.clip(joint + crack + missing * 0.5, 0, 1)
        o["wear"][m] = sstep(1.5, 0.6, d) * (1 - joint) * 0.6
        o["mat"][m] = np.where(missing, MAT["behind"], np.where(joint > 0.5, MAT["mortar"], MAT["brick"]))
        o["tone"][m] = 0.5 + 0.5 * (hid - 0.5)
        o["sid"][m] = 0
        o["heat"][m] = sstep(78, 58, P[:, 1]) * 0.25           # низ стенок у углей — слабый отсвет (в цвете)

    def floor_heap(self):
        o = self.o
        m = np.where(self.floor)[0]
        P = self.P[m]
        x, z = P[:, 0], P[:, 2]
        rr = np.hypot(x - FX, z - FZ)
        # зола: бугры и мелкая крупка; к стенкам выше (сгребли)
        ash = 0.9 * (fbm2(x * 0.12, z * 0.12, 211, 3) - 0.5) + 0.12 * (n2(x * 1.6, z * 1.6, 212) - 0.5) + 0.04 * rr
        H = ash.copy()
        mat = np.full(len(m), float(MAT["ash"]))
        cav = np.zeros(len(m))
        wear = np.zeros(len(m))
        knot = np.zeros(len(m))
        char = np.zeros(len(m))
        heat = np.zeros(len(m))
        sid = np.zeros(len(m))
        # угли: куски 1.5–3 см с трещинами, гнездом в центре и под поленьями
        f1, f2, cx, cy, h1, h2 = voronoi_c(x, z, 2.4, 213)
        nest = sstep(16, 4, rr) * (n2(x * 0.15, z * 0.15, 214) * 0.6 + 0.6)
        is_c = (h1 < nest) & (f2 - f1 > 0.25)
        lump = (0.6 + 0.9 * h2) * np.clip(1 - (f1 / 1.4) ** 2, 0, 1) ** 0.6
        g1, g2, _, _, _, _ = voronoi_c(x * 1.3, z * 1.3, 0.9, 215)
        ccr = sstep(0.12, 0.02, g2 - g1)
        hc = ash + 0.3 + lump - 0.25 * ccr
        on = is_c & (hc > H)
        H = np.where(on, hc, H)
        mat = np.where(on, MAT["ember"], mat)
        cav = np.where(on, ccr, cav)
        heat = np.where(on, np.clip(nest * (0.35 + 0.65 * ccr) + 0.2 * (h2 > 0.6), 0, 1), heat)
        heat = np.maximum(heat, sstep(14, 3, rr) * 0.25 * (n2(x * 0.5, z * 0.5, 216) > 0.55))   # тлеющая зола в центре
        # поленья: цилиндры, частично в золе; береста с чечевичками-валиками, колотое — грань с волокном
        for k, (lx, lz, ang, L, R, lift, split) in enumerate(LOGS):
            a = np.radians(ang)
            ax, az_ = np.sin(a), np.cos(a)
            px, pz = x - lx, z - lz
            t = px * ax + pz * az_                          # вдоль оси
            d = -px * az_ + pz * ax                          # поперёк
            inside = (np.abs(t) < L / 2) & (np.abs(d) < R)
            yc = ash.mean() * 0 + R * 0.55 + lift              # ось над полом
            top = yc + np.sqrt(np.clip(R * R - d * d, 0, None))
            if split:
                top = np.minimum(top, yc + R * 0.35)           # колотая грань сверху
            end = sstep(L / 2 - 1.2, L / 2, np.abs(t))
            top = top - 1.5 * end
            on = inside & (top > H)
            phi = np.arcsin(np.clip(d / R, -1, 1))
            circ = phi * R
            # чечевички: поперечные чёрточки 2–3 см, валик 0.6 мм
            lent = (np.abs(((t + 3 * k) % 3.2) - 1.6) < 0.22) * (np.abs(((circ + 0.8 * np.floor((t + 3 * k) / 3.2)) % 4.0) - 2.0) < 1.2)
            bark = 0.05 * lent + 0.03 * (n2(t * 0.5, circ * 2.0, 220 + k) - 0.5)
            flat = split & (top >= yc + R * 0.35 - 1e-6)
            grain = 0.5 + 0.5 * np.sin(d * 5.0 + 1.5 * n2(t * 0.15, d, 230 + k))
            hl = top + np.where(flat, 0.04 * grain, bark)
            H = np.where(on, hl, H)
            mat = np.where(on, np.where(flat | (end > 0.5), MAT["logwood"], MAT["bark"]), mat)
            knot = np.where(on, np.where(flat, grain, lent * 1.0), knot)
            # низ поленьев у углей обуглен, трещины светятся
            low = on & (top < yc + R * 0.55) & (rr < 18)
            ch, ck = alligator(t, circ, 1.6, 240 + k)
            H = np.where(low, H + 0.6 * ch, H)
            char = np.where(low, 1.0, char)
            cav = np.where(on, np.where(low, ck, 0.0), cav)
            heat = np.where(low, np.clip(ck * 0.8 * sstep(18, 6, rr), 0, 1), np.where(on, 0, heat))
            sid = np.where(on, k + 1, sid)
        o["h"][m] = H
        o["mat"][m] = mat
        o["cav"][m] = cav
        o["wear"][m] = wear
        o["knot"][m] = knot
        o["char"][m] = char
        o["heat"][m] = heat
        o["sid"][m] = sid
        o["tone"][m] = 0.5 + 0.3 * (n2(x * 0.2, z * 0.2, 250) - 0.5)

    def run(self, log=print):
        import time
        t = time.time()
        self.bricks()
        log(f"  fire bricks: {time.time() - t:.1f} s")
        self.floor_heap()
        log(f"  fire floor: {time.time() - t:.1f} s")
        return self.o


def fire(P, N, log=print):
    return Fire(np.asarray(P, float), np.asarray(N, float)).run(log)
