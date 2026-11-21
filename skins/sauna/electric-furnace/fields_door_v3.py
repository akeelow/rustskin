"""Sauna Stove v3: дверца топки — кованая рама, полосы-прутья, ручка с верёвкой, рамка фасада, обугленная стойка.
PLAN_v3.md §3.5 и референс ref_nb_door.jpg. numpy, см; оси OBJ (x вправо, y вверх, z вперёд).

Ковка: плоские грани от ударов молота (ячейки 1.5–3 см, каждая — свой наклон 3–6°), рёбра волнистые, окалина
хлопьями со ступенькой 0.25 мм (часть отслоилась — под ней ржавчина), раковины гнёздами, заклёпки с кованой
четырёхгранной головкой, бугристая сварка на углах окна. Один прут — арматура (рёбра).
"""
import numpy as np

import geom_v3 as G
from fields_v3 import MAT, STEP, char_field, fbm2, grain_relief, n2, nail_head, sstep, voronoi

DOOR_ISLANDS = {24}                                   # лицевая рама дверцы (z 33.7)
BAR_ISLANDS = {93, 94, 100, 102, 103, 105, 106, 107, 108, 112, 226, 228, 229, 230, 231, 232, 233, 235, 236, 239}
HANDLE_ISLANDS = {113, 114, 218, 220}
FRONT_ISLANDS = {20}                                  # фасад вокруг дверцы (z 29.4)
STRIP_ISLANDS = {80}                                  # передний торец обвязки левого бока (z 32.5)
WINDOW = (-22.9, 21.3, 51.7, 89.1)                    # окно рамы: x0, x1, y0, y1
BARS = {93: (4.53, 8.82), 94: (-4.08, 0.21), 100: (-12.71, -8.41), 102: (-21.32, -17.03), 103: (13.1, 17.44)}
BAR_Y = (47.47, 93.14)
BAR_Z = (33.86, 34.97)
REBAR = 94
HANDLE_X = (21.4, 25.2)


def voronoi_c(x, y, cell, seed):
    """Вороной с центрами: F1, F2, координаты ближайшего центра и его хеш (0..1, два числа)."""
    gx, gy = np.floor(x / cell).astype(np.int64), np.floor(y / cell).astype(np.int64)
    f1 = np.full(x.shape, 1e9)
    f2 = np.full(x.shape, 1e9)
    cxs, cys, h1, h2 = (np.zeros(x.shape) for _ in range(4))
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            cx, cy = gx + dx, gy + dy
            hsh = (cx * 73856093) ^ (cy * 19349663) ^ (seed * 83492791)
            hsh = (hsh ^ (hsh >> 13)) * 1274126177
            rx = (hsh & 0xFFFF) / 65535.0
            ry = ((hsh >> 16) & 0xFFFF) / 65535.0
            px, py = (cx + 0.15 + 0.7 * rx) * cell, (cy + 0.15 + 0.7 * ry) * cell
            d = np.hypot(x - px, y - py)
            closer = d < f1
            f2 = np.where(closer, f1, np.minimum(f2, d))
            f1 = np.where(closer, d, f1)
            cxs = np.where(closer, px, cxs)
            cys = np.where(closer, py, cys)
            h1 = np.where(closer, ((hsh >> 8) & 0xFFFF) / 65535.0, h1)
            h2 = np.where(closer, ((hsh >> 24) & 0xFF) / 255.0, h2)
    return f1, f2, cxs, cys, h1, h2


def hammer(U, V, seed, cell=2.0, amp=0.05):
    """Плоские грани ковки: в каждой ячейке Вороного — своя плоскость с наклоном 3–6° (удар бойка), пологая лунка,
    на границах — гребешки."""
    f1, f2, cx, cy, h1, h2 = voronoi_c(U * (1 + 0.2 * n2(U * 0.2, V * 0.2, seed + 5)), V, cell, seed)
    ang = 2 * np.pi * h1
    slope = 0.05 + 0.06 * h2
    plane = slope * ((U - cx) * np.cos(ang) + (V - cy) * np.sin(ang))
    dome = -amp * (f1 / cell) ** 2
    edge = sstep(0.12 * cell, 0.02 * cell, f2 - f1)
    return plane * 0.12 + dome + 0.3 * amp * edge, edge


def scale_flakes(U, V, seed, amt=0.55):
    """Окалина: хлопья 0.6–1.5 см, ступенька 0.25 мм; где хлопья нет — голый металл/ржавчина. -> dh, маска окалины,
    край хлопья (полость)."""
    f1, f2 = voronoi(U * 1.0, V * 0.8, 0.9, seed)
    keep = n2(np.floor(U / 0.9) * 1.3, np.floor(V / 0.72) * 1.7, seed + 3) < amt
    edge = sstep(0.1, 0.02, f2 - f1)
    sc = keep * (1 - edge)
    return 0.025 * sc - 0.01 * edge, sc, edge


def pyramid_rivet(H, U, V, base, s=0.75, hgt=0.5):
    """Заклёпка с кованой четырёхгранной головкой (основание 2s, высота hgt), скатами 25–35°."""
    q = np.maximum(np.abs(U), np.abs(V)) / s
    pyr = base + hgt * np.clip(1 - q, 0, 1) ** 0.9
    pyr -= 0.04 * np.exp(-((np.abs(U) - np.abs(V)) / 0.08) ** 2) * (q < 1)      # грань-ребро
    collar = base + 0.06 * np.exp(-((q - 1.05) / 0.12) ** 2)                      # осаженный край
    out = np.maximum(H, np.where(q < 1, pyr, collar))
    return out, sstep(1.05, 0.95, q)


def weld_blob(H, U, V, L, w, base, seed):
    """Бугристая сварка вдоль оси U (0..L): пологий валик шириной w с наплывами-чешуйками и брызгами."""
    t = np.clip(U / L, 0, 1)
    inside = (U > -w * 0.3) & (U < L + w * 0.3)
    prof = np.clip(1 - (V / (w * (0.8 + 0.4 * n2(U * 0.8, 1.0, seed)))) ** 2, 0, 1) * inside
    ripples = 0.5 + 0.5 * np.cos(U / 0.55 * 2 * np.pi - np.abs(V) * 3)
    hh = base + (0.32 + 0.12 * n2(U * 1.5, V * 1.5, seed + 1)) * prof ** 0.7 * (0.85 + 0.15 * ripples)
    hh = hh * 1.0 + (0.12 * (1 - np.abs(2 * t - 1)) * prof)
    return np.maximum(H, np.where(prof > 0, hh, H)), prof


class DoorFrame:
    """Лицевая рама дверцы (остров 24): поле Z(x, y)."""
    X = (-27.0, 26.0)
    Y = (45.8, 94.8)

    def grid(self, step=STEP):
        return np.meshgrid(np.arange(self.X[0], self.X[1] + 1e-6, step), np.arange(self.Y[0], self.Y[1] + 1e-6, step))

    def field(self, X, Y):
        base = G.raster_height(G.tris(islands=DOOR_ISLANDS), X, Y, 0, 1, 2, fill=np.nan)
        win = np.isnan(base)
        base = np.where(win, 29.0, base)
        z0 = np.zeros(X.shape)
        hm, edge = hammer(X, Y, 11, 2.4, 0.1)
        fl, scale, fedge = scale_flakes(X, Y, 13, 0.6)
        pits = (fbm2(X * 0.6, Y * 0.6, 15, 3) > 0.6) * sstep(0.2, 0.06, voronoi(X, Y, 0.5, 17)[0])
        H = base + (hm + fl - 0.05 * pits) * (~win)
        # волнистые кромки рамы (ковали вручную)
        rivet = z0.copy()
        weld = z0.copy()
        x0, x1, y0, y1 = WINDOW
        for (cx, cy, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
            # сварка по диагонали угла окна, наружу
            u = ((X - cx) * -dx + (Y - cy) * -dy) / np.sqrt(2)
            v = ((X - cx) * -dx - (Y - cy) * -dy) / np.sqrt(2)
            H, pw = weld_blob(H, u + 0.6, v, 3.8, 1.0, base + 0.03, int(abs(cx) * 3 + cy))
            weld = np.maximum(weld, pw)
        # заклёпки по раме: по углам и посередине сторон
        pts = [(-25.0, 48.5), (24.0, 48.5), (-25.0, 92.3), (24.0, 92.3), (-25.0, 70.4), (24.0, 70.4)]
        for (px, py) in pts:
            box = (np.abs(X - px) < 1.2) & (np.abs(Y - py) < 1.2)
            Hn, rm = pyramid_rivet(H[box], X[box] - px, Y[box] - py, base[box] + 0.03)
            H[box] = Hn
            rivet[box] = np.maximum(rivet[box], rm)
        mat = np.where(weld > 0.3, MAT["weld"], MAT["iron"])
        mat = np.where(rivet > 0.5, MAT["rivet"], mat).astype(float)
        cav = np.clip(fedge * 0.6 + pits + edge * 0.2, 0, 1)
        rust = np.clip(pits + (1 - scale) * 0.45 * (fbm2(X * 0.3, Y * 0.3, 19, 3) > 0.5), 0, 1)
        return dict(h=H, cav=cav, rust=rust, crust=scale * 1.0, mat=mat, grain=edge, nail=rivet, char=z0, dent=z0,
                    knot=z0, tone=0.5 + z0, sid=z0 + 1, bark=z0), win


def bar_face(bar, face, U, V, P):
    """Грань полосы-прута: грани ковки, окалина, кованые заклёпки у концов (над рамой); прут REBAR — арматура."""
    z0 = np.zeros(U.shape)
    x, y = P[..., 0], P[..., 1]
    front = face == "z+"
    h = z0.copy()
    rivet = z0.copy()
    if bar == REBAR:
        # арматура: косые рёбра через 1.1 см и продольное ребро; ржавая целиком
        cx = (BARS[bar][0] + BARS[bar][1]) / 2
        ph = (y + 0.55 * (x - cx)) / 1.1
        rib = np.exp(-((ph - np.round(ph)) / 0.12) ** 2) * (np.abs(x - cx) < 1.7)
        lng = np.exp(-((x - cx) / 0.18) ** 2)
        h += 0.14 * rib + 0.08 * lng + 0.03 * (n2(x * 3, y * 3, 5) - 0.5)
        mat = np.full(U.shape, MAT["rebar"], float)
        return dict(h=h, grain=rib, cav=z0, rust=z0 + 1, crust=z0, nail=z0, char=z0, dent=z0, knot=z0, mat=mat,
                    tone=z0 + 0.5, sid=z0 + 3, bark=z0)
    hm, edge = hammer(x * 1.0 + bar, y, 21 + bar, 2.0, 0.1)
    fl, scale, fedge = scale_flakes(x + bar * 3.1, y, 23 + bar, 0.55)
    pits = (fbm2(x * 0.7 + bar, y * 0.5, 25, 3) > 0.62) * sstep(0.18, 0.05, voronoi(x, y, 0.45, 27 + bar)[0])
    h += (hm + fl - 0.05 * pits) * (1.0 if front else 0.5)
    if front:
        cx = (BARS[bar][0] + BARS[bar][1]) / 2
        for py in (49.3, 91.4):
            box = (np.abs(x - cx) < 1.3) & (np.abs(y - py) < 1.3)
            Hn, rm = pyramid_rivet(h[box], x[box] - cx, y[box] - py, 0.0)
            h[box] = Hn
            rivet[box] = np.maximum(rivet[box], rm)
    mat = np.where(rivet > 0.5, MAT["rivet"], MAT["iron"]).astype(float)
    rust = np.clip(pits + (1 - scale) * 0.4 * (fbm2(x * 0.4, y * 0.3, 29 + bar, 3) > 0.5), 0, 1)
    return dict(h=h, grain=edge, cav=np.clip(fedge * 0.6 + pits, 0, 1), rust=rust, crust=scale * 1.0, nail=rivet,
                char=z0, dent=z0, knot=z0, mat=mat, tone=z0 + 0.5, sid=z0 + 3, bark=z0)


def handle_z(y):
    """Профиль ручки (лицевая сторона полосы) по модели: 34.5 у концов, 38.2 в середине."""
    zf = np.interp(y, [46.6, 51.0, 54.3, 56.0, 84.0, 86.0, 88.5, 93.1], [34.45, 34.55, 37.7, 38.18, 38.18, 37.6, 34.55, 34.45])
    return zf


class FrontFrame:
    """Фасад вокруг дверцы (остров 20, z 29.4): тёмное прокопчённое железо, видно узкой полосой вокруг дверцы."""
    X = (-29.8, 29.8)
    Y = (42.8, 98.0)

    def grid(self, step=STEP):
        return np.meshgrid(np.arange(self.X[0], self.X[1] + 1e-6, step), np.arange(self.Y[0], self.Y[1] + 1e-6, step))

    def field(self, X, Y):
        base = G.raster_height(G.tris(islands=FRONT_ISLANDS), X, Y, 0, 1, 2, fill=29.4)
        z0 = np.zeros(X.shape)
        hm, edge = hammer(X, Y, 41, 3.0, 0.04)
        pits = (fbm2(X * 0.5, Y * 0.5, 43, 3) > 0.6) * sstep(0.2, 0.06, voronoi(X, Y, 0.5, 45)[0])
        H = base + hm - 0.05 * pits
        return dict(h=H, cav=np.clip(pits + 0.2 * edge, 0, 1), rust=pits, crust=z0, mat=np.full(X.shape, float(MAT["soot_iron"])),
                    grain=edge, nail=z0, char=z0, dent=z0, knot=z0, tone=z0 + 0.5, sid=z0 + 2, bark=z0)


class Strip80:
    """Передний торец обвязки левого бока (остров 80, z 32.5, x −32.5…−29.4): обугленный горбыль, у концов — торцы
    верхнего и нижнего брусьев с кольцами."""
    X = (-32.6, -29.3)
    Y = (30.6, 110.3)

    def grid(self, step=STEP):
        return np.meshgrid(np.arange(self.X[0], self.X[1] + 1e-6, step), np.arange(self.Y[0], self.Y[1] + 1e-6, step))

    def field(self, X, Y):
        base = G.raster_height(G.tris(islands=STRIP_ISLANDS), X, Y, 0, 1, 2, fill=32.5)
        z0 = np.zeros(X.shape)
        ends = (Y > 105.6) | (Y < 35.8)
        gr = grain_relief(Y, X, 1.5, 0.01, -31.0, 1.1, 61)
        H = base + 0.05 * (gr - 0.35)
        # торцы: кольца вокруг сердцевины за пределами бруса
        cy = np.where(Y > 70, 108.0, 33.2)
        rr = np.hypot(X + 34.5, (Y - cy) * 1.2)
        f = rr / 0.32
        f = f - np.floor(f)
        rings = np.exp(-((f - 0.5) / 0.2) ** 2)
        H = np.where(ends, base + 0.03 * rings - 0.12 * (np.abs(Y - 105.6) < 0.1) - 0.12 * (np.abs(Y - 35.8) < 0.1), H)
        amt = np.clip(sstep(0.35, 0.6, fbm2(X * 0.2, Y * 0.05, 63, 3) + 0.3 * sstep(90, 50, Y)) * (~ends), 0, 1)
        char = z0.copy()
        cav = z0.copy()
        if (amt > 0).any():
            m = amt > 0
            dh, cr = char_field(X[m], Y[m], amt[m], 1.6, 65)
            H[m] += dh
            cav[m] = cr
            char = amt
        mat = np.where(char > 0.5, MAT["char"], MAT["frame"]).astype(float)
        return dict(h=H, cav=cav, rust=z0, crust=z0, mat=mat, grain=np.where(ends, rings, gr), nail=z0, char=char,
                    dent=z0, knot=z0, tone=z0 + 0.4, sid=z0 + 12, bark=z0)
