"""Sauna Stove v3: рельеф сложных деталей (смещение подразделённой копии модели вдоль нормалей). numpy, см.

f(P (n, 3), N (n, 3)) -> h (n,) и маски (как fields_v3). Двумерный рисунок берётся в проекции на главную ось нормали
(трипланарно), поэтому лунки ковки и окалина ложатся на любую сторону детали. Гранёность модели в нормаль не
попадает: bake_v3 печёт копию без смещения и вычитает её (PROMPT_next_skin §5, «вычитание»).
"""
import numpy as np

from fields_v3 import MAT, fbm2, n2, sstep, voronoi
from fields_door_v3 import hammer, scale_flakes


def tri_uv(P, N):
    """Координаты проекции на плоскость, перпендикулярную главной оси нормали."""
    ax = np.argmax(np.abs(N), 1)
    u = np.where(ax == 0, P[:, 2], P[:, 0])
    v = np.where(ax == 1, P[:, 2], P[:, 1])
    return u, v, ax


def out(n, **k):
    z = np.zeros(n)
    o = dict(h=z.copy(), grain=z.copy(), cav=z.copy(), dent=z.copy(), nail=z.copy(), knot=z.copy(), char=z.copy(),
             rust=z.copy(), crust=z.copy(), tone=z + 0.5, mat=z.copy(), sid=z - 1, bark=z.copy())
    o.update(k)
    return o


def iron3d(seed, amp=0.07, scale_amt=0.55, soot=False, heavy=False):
    def f(P, N):
        u, v, ax = tri_uv(P, N)
        u = u + ax * 37.0
        hm, edge = hammer(u, v, seed, 1.8, amp)
        fl, sc, fedge = scale_flakes(u, v, seed + 1, scale_amt)
        g1, _ = voronoi(u, v, 0.4, seed + 2)
        pits = (fbm2(u * 0.6, v * 0.6, seed + 3, 3) > (0.5 if heavy else 0.6)) * sstep(0.18, 0.05, g1)
        h = hm + fl * (2.0 if heavy else 1.0) - 0.05 * pits
        return out(len(P), h=h, grain=edge, cav=np.clip(fedge * 0.6 + pits, 0, 1), crust=sc * 1.0,
                   rust=np.clip(pits + (1 - sc) * 0.2, 0, 1), mat=np.full(len(P), float(MAT["soot_iron" if soot else "iron"])))
    return f


def rebar3d(seed, axis=1):
    """Арматура: кольцевые косые рёбра через 1.1 см вдоль оси детали + продольное ребро."""
    def f(P, N):
        s = P[:, axis]
        ang = np.arctan2(N[:, 2], N[:, 0])
        ph = (s + 0.6 * ang / np.pi) / 1.1
        rib = np.exp(-((ph - np.round(ph)) / 0.13) ** 2)
        lng = np.exp(-((np.angle(np.exp(1j * (ang - 1.2)))) / 0.25) ** 2)
        h = 0.12 * rib + 0.07 * lng + 0.02 * (n2(P[:, 0] * 3 + P[:, 2], s * 3, seed) - 0.5)
        return out(len(P), h=h, grain=rib, rust=np.ones(len(P)), mat=np.full(len(P), float(MAT["rebar"])))
    return f


def charstick3d(seed):
    """Обгоревшая палка: угольные блоки (трещины поперёк и вдоль), остатки коры."""
    def f(P, N):
        u, v, ax = tri_uv(P, N)
        from fields_v3 import char_field
        dh, cr = char_field(u + ax * 11.0, v, np.ones(len(P)), 1.2, seed)
        return out(len(P), h=dh + 0.12, cav=cr, char=np.ones(len(P)), mat=np.full(len(P), float(MAT["char"])))
    return f


def knob3d(center, seed):
    """Точёная берёзовая ручка (ось z через center): 10 рифлёных выемок на боку, кольца на торце, риска-указатель
    на гребне — смещение по нормали; засаленность — в цвете."""
    cx, cy = center

    def f(P, N):
        ang = np.arctan2(P[:, 1] - cy, P[:, 0] - cx)
        side = np.clip(1 - np.abs(N[:, 2]) * 1.4, 0, 1)
        flute = 0.5 + 0.5 * np.cos(ang * 10)
        r = np.hypot(P[:, 0] - cx, P[:, 1] - cy)
        f_ = r / 0.28 - np.floor(r / 0.28)
        rings = np.exp(-((f_ - 0.5) / 0.2) ** 2) * (N[:, 2] > 0.6)
        h = -0.06 * flute * side + 0.025 * rings + 0.015 * (n2(P[:, 0] * 4, P[:, 1] * 4, seed) - 0.5)
        return out(len(P), h=h, grain=np.maximum(rings, flute * side * 0.5), cav=flute * side * 0.6,
                   tone=0.6 + 0.0 * r, mat=np.full(len(P), float(MAT["plaque"])))
    return f


def rosette3d(center, seed):
    """Жестяная розетка: вмятина, загнутый край валиком, два гвоздика."""
    cx, cy = center

    def f(P, N):
        r = np.hypot(P[:, 0] - cx, P[:, 1] - cy)
        h = 0.04 * (n2(P[:, 0] * 0.8, P[:, 1] * 0.8, seed) - 0.5)
        dent = np.clip(1 - (np.hypot(P[:, 0] - cx - 1.2, P[:, 1] - cy + 1.6) / 1.4) ** 2, 0, 1) ** 2
        h -= 0.08 * dent
        nail = np.zeros(len(P))
        for ang in (0.9, 0.9 + np.pi):
            nx, ny = cx + 2.7 * np.cos(ang), cy + 2.7 * np.sin(ang)
            d = np.hypot(P[:, 0] - nx, P[:, 1] - ny)
            hd = np.clip(1 - d / 0.42, 0, 1) ** 0.4 * (N[:, 2] > 0.5)
            h += 0.14 * hd
            nail = np.maximum(nail, (d < 0.42) * (N[:, 2] > 0.5))
        rust = np.clip((fbm2(P[:, 0] * 0.5, P[:, 1] * 0.5, seed + 1, 3) - 0.45) * 3, 0, 1)
        return out(len(P), h=h, dent=dent, nail=nail, rust=rust,
                   mat=np.where(nail > 0.5, MAT["nail"], MAT["tin"]).astype(float))
    return f


def soot3d(seed):
    """Копоть и обугленное дерево внутри проёмов: бугры нагара, редкие трещины."""
    def f(P, N):
        u, v, ax = tri_uv(P, N)
        h = 0.04 * (fbm2(u * 0.6 + ax * 7, v * 0.6, seed, 3) - 0.5)
        f1, f2 = voronoi(u + ax * 7, v, 1.6, seed + 1)
        cr = sstep(0.12, 0.02, f2 - f1) * (n2(u * 0.3, v * 0.3, seed + 2) > 0.5)
        return out(len(P), h=h - 0.08 * cr, cav=cr, mat=np.full(len(P), float(MAT["soot_wood"])))
    return f


def wood3d(seed, along=1):
    """Торцы/кромки досок и горбыля: волокна вдоль оси along, неровность, редкие трещины."""
    def f(P, N):
        from fields_v3 import grain_relief
        u, v, ax = tri_uv(P, N)
        b = P[:, along]
        a = np.where(ax == 0, P[:, 2], P[:, 0]) if along == 1 else P[:, 1]
        gr = grain_relief(b, a, 1.5, 0.01, 0.5, 1.1, seed)
        h = 0.06 * (gr - 0.35) + 0.05 * (fbm2(b * 0.06, a * 0.3, seed + 1, 3) - 0.5)
        return out(len(P), h=h, grain=gr, tone=0.4 + 0.0 * h, mat=np.full(len(P), float(MAT["frame"])))
    return f
