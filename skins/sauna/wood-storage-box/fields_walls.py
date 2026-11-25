"""Sauna Stone Box v2: рельеф стенок — 16 досок и два обруча (PLAN_v2.md, 3.1-3.4). Чистый numpy: годится и для
Blender (bake_v2.py), и для проверок в .venv.

Единицы — см, оси OBJ (y вверх, +x — бок к печи, +z — перед с прорезью). Модель в OBJ в метрах — здесь ×100.
Каждая доска в атласе — короб целиком: наружная грань, верхняя и нижняя кромки, два торца (остров на доску);
изнанка в игре своих текселей не имеет (показывает наружную сторону).

Доска строится скруглённой коробкой по габаритам своего острова (bake_v2.rbox), грань — сетка (U, V), поле грани
возвращает h (сдвиг наружу, см) и маски:
  m1 = (волокно, полость, вмятина), m2 = (гвоздь, сучок, уголь), m3 = (пила/свежий скол, засаленность, тон доски)
Обруч — лента вдоль контура ящика: m1 = (раковина, полость, вмятина), m2 = (гвоздь/заклёпка, окалина, —),
m3 = (кромка, нахлёст, тон).
"""
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OBJ = HERE / "originals" / "box.wooden.obj"


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


def voronoi(x, y, cell, seed):
    """F1, F2 и номер ближайшей клетки по джиттер-сетке."""
    ix, iy = np.floor(x / cell).astype(np.int64), np.floor(y / cell).astype(np.int64)
    f1 = np.full(x.shape, 1e9)
    f2 = np.full(x.shape, 1e9)
    idn = np.zeros(x.shape, np.int64)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            cx, cy = ix + dx, iy + dy
            h = (cx * 73856093) ^ (cy * 19349663) ^ (seed * 83492791)
            h = (h ^ (h >> 13)) * 1274126177
            jx = ((h & 0xFFFF) / 65535.0) * 0.8 + 0.1
            jy = (((h >> 16) & 0xFFFF) / 65535.0) * 0.8 + 0.1
            d = np.hypot(x - (cx + jx) * cell, y - (cy + jy) * cell)
            closer = d < f1
            f2 = np.where(closer, f1, np.minimum(f2, d))
            idn = np.where(closer, h & 0xFFFFFF, idn)
            f1 = np.minimum(f1, d)
    return f1, f2, idn


def grain_relief(along, across, depth0, tilt, c, s, seed, knots=()):
    """Гребни поздней древесины (0..1): «арки» тангентальной доски; knots [(along, across, r)] — волокна огибают."""
    warp = 0.45 * (fbm2(along * 0.025, across * 0.12, seed, 3) - 0.5) + 0.12 * (n2(along * 0.12, across * 0.5, seed + 3) - 0.5)
    d = depth0 + tilt * along + 0.6 * warp
    ph = np.sqrt((across - c) ** 2 + d * d) / s + warp
    for (ka, kc, kr) in knots:
        dd = np.hypot((along - ka) / 1.5, across - kc)
        ph = ph + 1.6 * kr * np.exp(-(dd / (2.4 * kr)) ** 2) / s
    f = ph - np.floor(ph)
    return np.exp(-((f - 0.82) / 0.11) ** 2) + np.exp(-((f + 1 - 0.82) / 0.11) ** 2) + np.exp(-((f - 1.82) / 0.11) ** 2)


def crack_along(H, cav, U, V, u0, u1, v0, depth, hw, seed):
    """Трещина вдоль U от u0 до u1 на высоте v0: V-борозда, раскрытие 2*hw, сужается к концам."""
    box = (U > min(u0, u1) - 1) & (U < max(u0, u1) + 1) & (np.abs(V - v0) < 2)
    if not box.any():
        return H, cav
    t = np.clip((U[box] - u0) / (u1 - u0), 0, 1)
    vc = v0 + 0.9 * (n2(U[box] * 0.12, seed + 0.0, seed) - 0.5) + 0.25 * (n2(U[box] * 0.6, seed + 1.0, seed) - 0.5)
    prof = (1 - t) ** 0.7 * sstep(-0.05, 0.08, t)       # шире всего у u0 (торец доски), к u1 сходит на нет
    dv = np.abs(V[box] - vc)
    g = np.clip(1 - dv / (hw * prof + 1e-3), 0, 1)
    sh = np.clip(1 - dv / (3.2 * hw * prof + 1e-3), 0, 1)     # плечи: дерево у трещины проседает и раскрывается
    H[box] -= depth * prof * g ** 0.8 + 0.25 * depth * prof * sh ** 1.5
    cav[box] = np.maximum(cav[box], g * prof)
    return H, cav


def end_rings(U, V, pu, pv, s, seed):
    """Годичные кольца торца вокруг сердцевины (pu, pv): гребни 0..1 и радиальная трещина."""
    r = np.hypot(U - pu, V - pv) + 0.35 * (fbm2(U * 0.3, V * 0.3, seed, 2) - 0.5)
    f = (r / s) % 1.0
    ring = np.exp(-((f - 0.8) / 0.14) ** 2)
    ang = np.arctan2(V - pv, U - pu)
    da = np.abs(np.angle(np.exp(1j * (ang - (seed % 7) * 0.4 - 1.2))))
    chk = (r * da < 0.14) & (r > 0.5)
    return ring, chk


def nail_head(H, U, V, base, kind, r=0.55):
    """Кованая шляпка (скруглённый квадрат); kind 0 — обычная, 1 — забита глубже с воронкой, 2 — торчит."""
    q = ((np.abs(U) / r) ** 4 + (np.abs(V) / r) ** 4) ** 0.25
    dome = np.sqrt(np.clip(1 - q ** 2, 0, 1))
    lift = {0: 0.04, 1: -0.05, 2: 0.2}[kind]
    hh = base + lift + 0.1 * dome - 0.02 * np.maximum(np.abs(U), np.abs(V)) / r
    dd = np.hypot(U, V)
    H = H - 0.03 * np.clip(1 - ((dd - 0.78) / 0.3) ** 2, 0, 1)            # смятое волокно вокруг
    if kind == 1:
        H = H - 0.1 * np.clip(1 - (dd / 1.15) ** 2, 0, 1) ** 2
    H = np.where(q < 1, np.maximum(H, hh), H)
    return H, sstep(1.02, 0.92, q)


MAT = {"board": 1, "end": 2, "nail": 3, "hoop": 4, "rivet": 5, "char": 15, "tin": 16, "peg": 17}


# ------------------------------------------------------------------ доски
WALL_ISL = {"left": [8, 6, 7, 13], "right": [0, 2, 12, 15], "front": [16, 25, 27, 14], "back": [21, 4, 11, 22]}
# стенка: (ось нормали k, знак), ось вдоль доски
WALL_AX = {"left": (0, -1, 2), "right": (0, 1, 2), "front": (2, 1, 0), "back": (2, -1, 0)}
HOOPS = ((4.5, 9.0), (31.0, 35.5))            # y обручей (как v1): на досках 0 и 2
SLOT = dict(xc=-0.85, hw=15.15, flat=8.2, top=45.0)   # арка прорези в нижней кромке верхней торцевой доски
SAWN = {("left", 1), ("right", 3), ("front", 0), ("back", 2), ("right", 0), ("left", 3)}   # доски со следами пилы


def load_obj():
    v, vt, F = [], [], []
    for line in open(OBJ):
        p = line.split()
        if not p:
            continue
        if p[0] == "v":
            v.append([float(x) for x in p[1:4]])
        elif p[0] == "vt":
            vt.append([float(x) for x in p[1:3]])
        elif p[0] == "f":
            idx = [tuple(int(a) for a in s.split("/")) for s in p[1:]]
            for k in range(1, len(idx) - 1):
                F.append((idx[0], idx[k], idx[k + 1]))
    return np.array(v) * 100.0, np.array(vt), F


def island_of_faces(F):
    """Номер острова на каждый треугольник — в том же порядке, что islands.py (по убыванию числа граней)."""
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for t in F:
        ti = [c[1] - 1 for c in t]
        for x in ti[1:]:
            parent[find(x)] = find(ti[0])
    groups = {}
    for f, t in enumerate(F):
        groups.setdefault(find(t[0][1] - 1), []).append(f)
    order = sorted(groups.values(), key=lambda fs: -len(fs))
    isl = np.empty(len(F), int)
    for n, fs in enumerate(order):
        isl[fs] = n
    return isl


def boards():
    """16 досок: стенка, номер снизу (0..3), остров, габариты lo/hi (см), оси."""
    V, _, F = load_obj()
    isl = island_of_faces(F)
    P = np.array([[V[c[0] - 1] for c in t] for t in F])
    out = []
    rng = np.random.default_rng(5)
    for wall, ids in WALL_ISL.items():
        k, s, a = WALL_AX[wall]
        for plank, i in enumerate(ids):
            pp = P[isl == i].reshape(-1, 3)
            lo, hi = pp.min(0), pp.max(0)
            if wall in ("front", "back") and plank == 3:
                lo[1] = min(lo[1], 40.25)
            out.append(dict(wall=wall, plank=plank, island=int(i), lo=lo, hi=hi, k=k, s=s, a=a,
                            seed=100 + 10 * list(WALL_ISL).index(wall) + plank, tone=float(rng.uniform(0.1, 0.9)),
                            slot=wall in ("front", "back") and plank == 3))
    return out


def slot_bottom(x, base):
    """Нижняя кромка верхней торцевой доски с аркой прорези-ручки."""
    t = np.clip((np.abs(x - SLOT["xc"]) - SLOT["flat"]) / (SLOT["hw"] - SLOT["flat"]), 0, 1)
    return base + (SLOT["top"] - base) * np.sqrt(np.clip(1 - t ** 2, 0, 1))


def board_nails(b):
    """Гвозди на концах досок длинных боков (прибиты к торцевым доскам): [(along, y, kind)]."""
    if b["wall"] not in ("left", "right"):
        return []
    rng = np.random.default_rng(b["seed"] + 7)
    yc = (b["lo"][1] + b["hi"][1]) / 2
    out = []
    for end, za in ((1, 45.35), (-1, -44.8)):           # середина толщины торцевой доски
        for dy in (-3.6, 3.6):
            kind = 0
            r = rng.random()
            if r < 0.18:
                kind = 1
            elif r < 0.24:
                kind = 2
            out.append((za + rng.uniform(-0.25, 0.25), yc + dy + rng.uniform(-0.6, 0.6), kind))
    return out


NAILS_BENT = {("right", 1, -1), ("left", 3, 1)}       # (стенка, доска, конец): рядом гнутый гвоздь — перебили


# ------------------------------------------------------------------ сторона печи: уголь, зарубки, заплата, колышек
PATCH = dict(wall="right", plank=1, z=(31.5, 43.0), y=(15.2, 25.2))      # жесть из банки над прогоревшим углом
PEG = dict(wall="left", plank=1, z=-12.0, y=20.3, r=0.95)                # колышек в пулевом отверстии
NICKS = (-31.0, -12.5, 3.0, 17.5, 33.0)                                   # зарубки совка на кромке +x (z)


def char_depth(b, al, x):
    """Глубина обугливания от верха доски (см): верхние доски бока к печи и заход через углы на торцы."""
    if b["plank"] != 3:
        return None
    sd = b["seed"]
    tongue = 2.0 + 2.6 * fbm2(al * 0.07, 0.3, sd + 61, 3) + 2.2 * np.clip(np.sin(al * 0.21 + sd) - 0.55, 0, 1) / 0.45
    if b["wall"] == "right":
        return tongue
    if b["wall"] in ("front", "back"):
        return tongue * 0.8 * sstep(19.0, 29.0, x)
    return None


def hash01(i, j, seed):
    """Детерминированный шум 0..1 по целочисленной клетке."""
    h = (np.asarray(i, np.int64) * 73856093) ^ (np.asarray(j, np.int64) * 19349663) ^ (seed * 83492791)
    h = (h ^ (h >> 13)) * 1274126177
    return ((h >> 8) & 0xFFFF) / 65535.0


def char_blocks(u, v, cu, cv, sd):
    """Угольные блоки: ряды вдоль волокна (u), в ряду — поперечные трещины. Всё неровное, чтобы не читалось кладкой:
    границы рядов и трещин сдвинуты по клеткам, трещины косые и изогнутые, длина блоков гуляет.
    Возвращает расстояния до поперечной и продольной трещины (см), флаг «продольная трещина есть» и номер блока."""
    vw = v / cv + 0.45 * (fbm2(u * 0.12, v * 0.08, sd, 3) - 0.5)
    r0 = np.floor(vw)
    dv = np.full(u.shape, 9.0)
    for r in (r0, r0 + 1):                                                   # границы рядов со сдвигом
        b = r + 0.3 * (hash01(r, 7, sd + 9) - 0.5)
        dv = np.minimum(dv, np.abs(vw - b))
    row = r0
    fv = vw - row
    rs = 0.75 + 0.5 * hash01(row, 0, sd + 1)
    uw = u / (cu * rs) + hash01(row, 1, sd + 2) * 3.0 + 0.35 * (fbm2(v * 0.5, u * 0.08, sd + 3, 2) - 0.5)
    c0 = np.floor(uw)
    du = np.full(u.shape, 9.0)
    for c in (c0 - 1, c0, c0 + 1):                                           # трещины: сдвиг и наклон у каждой своей
        b = c + 0.5 * (hash01(c, row, sd + 5) - 0.5) + 0.5 * (hash01(c, row, sd + 6) - 0.5) * (fv - 0.5)
        du = np.minimum(du, np.abs(uw - b))
    du = du * cu * rs
    dv = dv * cv
    keep = hash01(c0, row, sd + 4) > 0.3                                    # часть продольных трещин не раскрылась
    return du, dv, keep, (c0 * 7919 + row * 104729).astype(np.int64)


def char_cells(H, cav, u, v, inzone, sd, deep=None):
    """Обугленное дерево (v2.2): плоские прямоугольные блоки, вытянутые вдоль волокна (u); главные трещины — поперёк
    волокна, продольные мельче; у границы угля (deep -> 0) блоки мельче. v2.1 — круглые выпуклые ячейки = «брусчатка»."""
    deep = inzone if deep is None else deep
    out = []
    for cu, cv, k in ((2.1, 1.05, 0), (1.25, 0.7, 1)):
        du, dv, keep, idn = char_blocks(u, v, cu, cv, sd + 31 * k)
        cx = sstep(0.13, 0.03, du)                                           # поперёк волокна: 2-3 мм, глубоко
        cy = sstep(0.09, 0.02, dv) * keep                                    # вдоль: 1-2 мм, мельче
        bev = sstep(0.0, 0.3, np.minimum(du, np.where(keep, dv, 9.0)))      # плоская макушка, скруглена только у трещины
        tilt = 0.015 * (hash01(idn, 5, sd) - 0.5)
        Hc = -0.12 - 0.04 * (1 - bev) - 0.22 * cx - 0.12 * cy + tilt
        out.append((Hc, np.maximum(cx, 0.7 * cy)))
    w = sstep(0.25, 0.7, deep)                                               # 1 — крупные блоки, 0 — мелкая сетка
    Hc = out[0][0] * w + out[1][0] * (1 - w)
    crack = out[0][1] * w + out[1][1] * (1 - w)
    Hc = Hc + 0.008 * (fbm2(u * 0.5, v * 3.0, sd + 7, 2) - 0.5)            # волокно сквозь уголь — едва
    H = np.where(inzone > 0, H * (1 - inzone) + Hc * inzone, H)
    cav = np.maximum(cav, crack * inzone * 0.9)
    return H, cav


def board_face(b, face, U, V, P):
    """Поле грани доски. face — 'x-'... по rbox; P — точки на скруглённой коробке (см)."""
    k, s, a = b["k"], b["s"], b["a"]
    lo, hi = b["lo"], b["hi"]
    sd = b["seed"]
    rng = np.random.default_rng(sd)
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    al = P[..., a]
    zero = np.zeros_like(U)
    H = zero.copy()
    cav = zero.copy()
    dent = zero.copy()
    nail = zero.copy()
    knot = zero.copy()
    saw = zero.copy()
    grease = zero.copy()
    mat = np.full(U.shape, MAT["board"])
    outer = face == "xyz"[k] + ("+" if s > 0 else "-")
    inner = face == "xyz"[k] + ("-" if s > 0 else "+")
    end = face[0] == "xyz"[a]
    yc = (lo[1] + hi[1]) / 2
    depth_c = (lo[k] + hi[k]) / 2
    top = b["plank"] == 3
    # годичные кольца лежат дугами по толщине: сердцевина ниже доски на 6-12 см (тангентальный распил)
    pith_up = rng.uniform(-14, -7) * rng.choice((-1, 1))
    if inner:
        return dict(h=zero, m1=np.stack([zero] * 3, -1), m2=np.stack([zero] * 3, -1),
                    m3=np.stack([zero, zero, zero + b["tone"]], -1), mat=mat)
    if end:                                            # торцы: кольца, пила, трещина
        across = P[..., k]
        ring, chk = end_rings(across, y, depth_c + rng.uniform(-0.5, 0.5), yc + pith_up, 1.05, sd)
        H += 0.045 * ring - 0.3 * chk
        H -= 0.025 * np.abs(np.sin((y + 0.5 * across) / 1.3 * np.pi)) ** 2     # следы пилы
        cav = np.maximum(cav, chk * 1.0)
        # сколы и смятые углы торца
        de = np.minimum(np.minimum(y - lo[1], hi[1] - y), np.minimum(across - lo[k], hi[k] - across))
        H -= 0.12 * sstep(0.55, 0.0, de) * sstep(0.55, 0.75, n2(y * 0.9, across * 2, sd + 9))
        mat = np.full(U.shape, MAT["end"])
        char = zero.copy()
        if b["wall"] == "right" and top:
            zone = sstep(4.0, 2.5, hi[1] - y)
            H, cav = char_cells(H, cav, y, across, zone, sd + 9)               # торец: трещины по кольцам
            char = zone
        return dict(h=H, m1=np.stack([ring, np.clip(cav, 0, 1), dent], -1), m2=np.stack([zero, zero, char], -1),
                    m3=np.stack([zero, zero, zero + b["tone"]], -1), mat=mat)
    knots = []
    for _ in range(rng.integers(0, 3)):
        knots.append((rng.uniform(lo[a] + 8, hi[a] - 8), rng.uniform(lo[1] + 3, hi[1] - 3), rng.uniform(0.7, 1.6)))
    if outer:
        across = y - yc
        rift = (sd % 3) == 0                                                       # треть досок — радиальный распил
        if rift:
            g = grain_relief(al, across, 0.0, 0.0, 40.0 * rng.choice((-1, 1)), rng.uniform(1.2, 1.6), sd,
                             [(ka, kc - yc, kr) for ka, kc, kr in knots])
        else:                                       # «арки»: сердцевина уходит вглубь и выходит вдоль доски
            g = grain_relief(al, across, rng.uniform(1.0, 3.0), rng.uniform(0.035, 0.06) * rng.choice((-1, 1)),
                             rng.uniform(-2.5, 2.5), rng.uniform(1.2, 1.7), sd, [(ka, kc - yc, kr) for ka, kc, kr in knots])
        wea = 0.65 + 0.7 * fbm2(al * 0.04, y * 0.08, sd + 21, 3)                  # выветрено неравномерно
        H += 0.08 * wea * (g - 0.35)
        H += 0.015 * (fbm2(al * 0.12, y * 1.6, sd + 1, 3) - 0.5)                  # волнистость вдоль волокон
        if (b["wall"], b["plank"]) in SAWN:                                        # следы ленточной пилы
            ph = (al + 0.18 * (y - yc) + 2.5 * (n2(al * 0.05, y * 0.1, sd) - 0.5)) / 1.4
            sw = np.abs(np.sin((ph + 0.15 * n2(np.floor(ph), 0.5, sd + 4)) * np.pi)) ** 4
            sw = sw * sstep(0.5, 0.8, n2(al * 0.05, y * 0.12, sd + 2))           # пятнами: выветрило не везде
            H -= 0.009 * sw          # v2.2: 0.018 в игре читалось «вельветом» поперёк доски
            saw = sw * 0.5
        # сучки: вытянуты вдоль волокна (2:1), тёмные, чуть выпуклые без кольца; трещина с одной стороны; один выпал
        # (v2.0 в игре: круглые с трещиной поперёк читались шляпками шурупов)
        for j, (ka, kc, kr) in enumerate(knots):
            dd = np.hypot((al - ka) / 2.2, (y - kc) / (1.0 + 0.15 * np.sin(j + sd)))
            kn = sstep(kr, kr * 0.55, dd)
            fell = (sd + j) % 7 == 3
            if fell:
                H -= 0.35 * sstep(kr * 0.75, kr * 0.55, dd)
                cav = np.maximum(cav, sstep(kr * 0.75, kr * 0.55, dd))
            else:
                H += 0.04 * kn
                side = 1 if (sd + j) % 2 else -1
                t = (al - ka) * side
                yy = kc + 0.15 * np.sin(t * 0.6 + j)
                w = 0.12 * sstep(kr * 6.0, kr * 1.5, t)
                rc = np.clip(1 - np.abs(y - yy) / (w + 1e-3), 0, 1) * (t > kr * 1.2) * (t < kr * 6.0)
                H -= 0.22 * rc
                cav = np.maximum(cav, rc)
            knot = np.maximum(knot, kn)
        # торцевые трещины от концов доски, у печи (+x) гуще и длиннее
        hot = b["wall"] == "right"
        for e, u_end in ((1, hi[a]), (-1, lo[a])):
            for _ in range(rng.integers(1, 3) + (2 if hot else 0)):
                L = rng.uniform(3, 7) * (1.6 if hot else 1.0)
                v0 = rng.uniform(lo[1] + 1.5, hi[1] - 1.5)
                H, cav = crack_along(H, cav, al, y, u_end + e * 0.3, u_end - e * L, v0, 0.3, 0.2, sd + int(v0 * 10))
        if hot:                                                                    # продольные трещины усушки
            for _ in range(2):
                u0 = rng.uniform(lo[a] + 10, hi[a] - 25)
                H, cav = crack_along(H, cav, al, y, u0, u0 + rng.uniform(8, 18), rng.uniform(lo[1] + 2, hi[1] - 2),
                                     0.28, 0.18, sd + 31)
        # вмятины от брошенных камней: у верха, гнёздами
        nd = 3 if top else 1
        for _ in range(nd):
            ca, cy0 = rng.uniform(lo[a] + 4, hi[a] - 4), rng.uniform(hi[1] - 4.5, hi[1] - 1.0) if top else rng.uniform(lo[1] + 2, hi[1] - 2)
            for _ in range(rng.integers(1, 3)):
                ra, d = rng.uniform(1.0, 2.0), rng.uniform(0.07, 0.12)
                u = np.clip(1 - ((al - ca - rng.uniform(-2, 2)) ** 2 + (y - cy0) ** 2) / ra ** 2, 0, 1) ** 2
                H -= d * u
                dent = np.maximum(dent, u)
        # выкрошенные кромки (вдоль верхнего и нижнего края лица)
        de = np.minimum(y - lo[1], hi[1] - y)
        H -= 0.12 * sstep(0.45, 0.0, de) * sstep(0.58, 0.78, fbm2(al * 0.35, y * 0.2 + sd, sd + 5, 3))
        if top:                                                                    # верх стёрт в дугу
            H -= 0.18 * sstep(1.2, 0.0, hi[1] - y) ** 2
        # гвозди
        for (ga, gy, kind) in board_nails(b):
            m = (np.abs(al - ga) < 2.2) & (np.abs(y - gy) < 2.2)
            if m.any():
                hb, nm = nail_head(H[m], (al[m] - ga), y[m] - gy, 0.0, kind)
                H[m] = hb
                nail[m] = np.maximum(nail[m], nm)
                if kind == 0 and (int(ga * 10) + int(gy * 10)) % 3 == 0:          # «улыбка» молотка
                    ang = np.arctan2(y[m] - gy, al[m] - ga)
                    dd = np.hypot(al[m] - ga, y[m] - gy)
                    sm = np.exp(-((dd - 1.25) / 0.22) ** 2) * sstep(0.2, 0.9, np.cos(ang - 1.0 - gy))
                    H[m] -= 0.05 * sm
                    dent[m] = np.maximum(dent[m], sm)
        for (w, p, e) in NAILS_BENT:                                                # загнутый гвоздь
            if (b["wall"], b["plank"]) == (w, p):
                ga = (45.35 if e > 0 else -44.8) - e * 1.4
                gy = yc + 0.5
                sh = (np.abs(y - gy) < 0.16) & (al * e < ga * e) & (al * e > (ga - e * 2.6) * e)
                H = np.where(sh, np.maximum(H, 0.18 - 0.03 * np.abs(al - ga)), H)
                nail = np.maximum(nail, sh * 1.0)
                hb, nm = nail_head(H, al - (ga - e * 2.6), y - gy, 0.0, 0, r=0.4)
                H = hb
                nail = np.maximum(nail, nm)
        # прорезь: верхняя кромка арки стёрта руками, вокруг засалено
        if b["slot"]:
            yb = slot_bottom(x, lo[1])
            inside = np.abs(x - SLOT["xc"]) < SLOT["hw"] + 1.5
            dl = y - yb
            H -= inside * 0.22 * sstep(0.9, 0.0, dl) ** 2
            grease = inside * sstep(4.5, 0.0, dl) * sstep(SLOT["hw"] + 3, SLOT["hw"] - 4, np.abs(x - SLOT["xc"]))
            for (px, d) in ((-5.0, 0.08), (2.5, 0.07), (-0.5, 0.06)):                # вмятинки от пальцев
                u = np.clip(1 - ((x - px) ** 2 / 1.1 ** 2 + (y - (yb + 0.9)) ** 2 / 0.7 ** 2), 0, 1) ** 2
                H -= d * u * inside
                dent = np.maximum(dent, u * inside)
        char = zero.copy()
        cd = char_depth(b, al, x)
        if cd is not None:                          # обугленный верх: угли сыплют совком через край
            dz = hi[1] - y
            zone = sstep(cd + 0.6, cd - 0.4, dz)
            H, cav = char_cells(H, cav, al, y, zone, sd, deep=sstep(0.2, 2.2, cd - dz))
            char = zone
            g = g * (1 - zone)
        rings = zero.copy()
        if (b["wall"], b["plank"]) == (PATCH["wall"], PATCH["plank"]):
            (z0, z1), (y0, y1) = PATCH["z"], PATCH["y"]
            ez = np.minimum.reduce([al - z0, z1 - al, y - y0, y1 - y])
            inp = ez > 0
            # жесть 0.8 мм из развёрнутой банки: параллельные рёбра (v2.1 кольца в игре — «мишень»), загнутый край,
            # верхний задний угол отогнут от доски (гвоздь выпал), помята; 5 гвоздиков
            yc_ = (y0 + y1) / 2 + 0.3 * np.sin(al * 0.4)
            rings = np.exp(-(((y - yc_) % 2.2 - 1.1) / 0.3) ** 2) * sstep(0.8, 1.8, ez)
            bead = np.exp(-((ez - 0.35) / 0.2) ** 2)
            dents = 0.06 * (fbm2(al * 0.35, y * 0.35, sd + 81, 3) - 0.5)
            lift = sstep(3.8, 0.3, (z1 - al) + (y1 - y) * 1.1) * inp                # передний верхний угол
            Hp = 0.12 + 0.03 * rings + 0.07 * bead + dents + 0.5 * lift ** 1.3
            H = np.where(inp, np.maximum(H * 0.3, Hp), H)
            H -= 0.04 * sstep(0.5, 0.0, np.abs(ez)) * (ez < 0)                     # смятое дерево по краю
            pnail = zero.copy()
            for (nz_, ny_) in ((z0 + 0.6, y0 + 0.6), (z1 - 0.6, y0 + 0.6), (z0 + 0.6, y1 - 0.6),
                               ((z0 + z1) / 2, y0 + 0.5), ((z0 + z1) / 2 - 0.4, y1 - 0.5)):
                dd = np.hypot(al - nz_, y - ny_)
                H = np.where(dd < 0.3, np.maximum(H, 0.19 + 0.04 * np.sqrt(np.clip(1 - (dd / 0.3) ** 2, 0, 1))), H)
                nail = np.maximum(nail, (dd < 0.32) * 1.0)
                pnail = np.maximum(pnail, np.exp(-(dd / 1.0) ** 2))
            grease = np.where(inp, np.maximum(sstep(1.6, 0.2, ez), pnail), grease)  # для заплаты: ржавчина от края и гвоздей
            mat = np.where(inp, MAT["tin"], mat)
            g = np.where(inp, 0, g)
        if (b["wall"], b["plank"]) == (PEG["wall"], PEG["plank"]):
            dd = np.hypot(al - PEG["z"], y - PEG["y"])
            pr = PEG["r"]
            plug = dd < pr
            ring, _ = end_rings(al, y, PEG["z"] + 0.3, PEG["y"] - 0.2, 0.28, sd + 91)
            H = np.where(plug, -0.05 + 0.03 * ring - 0.06 * (dd / pr) ** 2, H)
            H -= 0.12 * np.exp(-((dd - pr) / 0.08) ** 2)                            # щель вокруг колышка
            ang = np.arctan2(y - PEG["y"], al - PEG["z"])
            spl = sstep(0.5, 0.8, np.abs(np.sin(ang * 3 + 1.0))) * np.exp(-((dd - pr * 1.5) / 0.35) ** 2)
            H += 0.08 * spl * (np.abs(np.cos(ang)) > 0.5)                           # поднятая щепа по волокну
            mat = np.where(plug, MAT["peg"], mat)
            cav = np.maximum(cav, np.exp(-((dd - pr) / 0.08) ** 2))
            g = np.where(plug, ring, g)
        return dict(h=H, m1=np.stack([np.where(mat == MAT["tin"], rings, g), np.clip(cav, 0, 1), dent], -1),
                    m2=np.stack([nail, knot, char], -1), m3=np.stack([saw, grease, zero + b["tone"]], -1),
                    mat=np.where(nail > 0.5, MAT["nail"], mat))
    # кромки доски (верх/низ): волокна вдоль, у верхних досок — обод ящика: вмятины, стёртость
    across = P[..., k] - depth_c
    g = grain_relief(al, across, rng.uniform(0.6, 1.6), 0.0, 0.0, rng.uniform(1.05, 1.4), sd)
    H += 0.05 * (g - 0.35)
    if face == "y+" and top:
        for _ in range(4):
            ca, ra, d = rng.uniform(lo[a] + 3, hi[a] - 3), rng.uniform(0.9, 1.6), rng.uniform(0.07, 0.13)
            u = np.clip(1 - ((al - ca) ** 2 + (across * 1.2) ** 2) / ra ** 2, 0, 1) ** 2
            H -= d * u
            dent = np.maximum(dent, u)
        H -= 0.04 * (fbm2(al * 0.4, across, sd + 11, 2) - 0.5)
    char = zero.copy()
    if face == "y+" and top:
        cd = char_depth(b, al, x)
        if cd is not None:
            zone = sstep(0.3, 1.2, cd) * np.ones_like(al)
            H, cav = char_cells(H, cav, al, across, zone, sd + 5, deep=sstep(0.8, 2.5, cd) * np.ones_like(al))
            char = zone
        if b["wall"] == "right":                       # зарубки совка поперёк обода, со сколом наружной кромки
            for j, zc in enumerate(NICKS):
                zc2 = zc + 0.8 * np.sin(j * 2.3)
                dzn = np.abs(al - zc2 - 0.25 * across)
                gro = np.clip(1 - dzn / 0.32, 0, 1)
                H -= 0.32 * gro * sstep(-1.2, 0.6, across)
                chip = np.clip(1 - np.hypot((al - zc2) / 1.1, (across - 0.85) / 0.6), 0, 1)
                H -= 0.25 * chip
                cav = np.maximum(cav, gro * 0.6)
                dent = np.maximum(dent, chip)
    if face == "y-" and b["slot"]:                    # срез прорези: дуги сверла и пила
        inside = np.abs(x - SLOT["xc"]) < SLOT["hw"]
        H -= inside * 0.02 * np.abs(np.sin((x + 0.3 * across) / 1.1 * np.pi)) ** 2
        grease = inside * 0.7
    return dict(h=H, m1=np.stack([g, np.clip(cav, 0, 1), dent], -1), m2=np.stack([zero, zero, char], -1),
                m3=np.stack([zero, grease, zero + b["tone"]], -1), mat=mat)


# ------------------------------------------------------------------ обручи
def hoop_path(bs, plank, step=0.15):
    """Контур обруча на доске plank: вдоль боков, через торцы длинных досок, косо к торцевой стенке.
    Возвращает точки (n, 2) в плоскости xz, наружные нормали (n, 2), длину дуги s (n,)."""
    B = {b["wall"]: b for b in bs if b["plank"] == plank}
    L, R, Fr, Bk = B["left"], B["right"], B["front"], B["back"]
    XL, XLi = L["lo"][0], L["hi"][0]
    XR, XRi = R["hi"][0], R["lo"][0]
    ZF, ZB = Fr["hi"][2], Bk["lo"][2]
    LF, LB = max(L["hi"][2], R["hi"][2]), min(L["lo"][2], R["lo"][2])
    run = 4.5
    pts = [(XL, LB + 2), (XL, LF), (XLi, LF), (XLi + run, ZF), (XRi - run, ZF), (XRi, LF), (XR, LF), (XR, LB),
           (XRi, LB), (XRi - run, ZB), (XLi + run, ZB), (XLi, LB), (XL, LB), (XL, LB + 2)]
    pts = np.array(pts, float)
    # плотная ломаная -> скругление углов (Chaikin) -> равный шаг
    dense = [pts[0]]
    for p0, p1 in zip(pts[:-1], pts[1:]):
        n = max(int(np.linalg.norm(p1 - p0) / 0.5), 1)
        for t in np.linspace(0, 1, n + 1)[1:]:
            dense.append(p0 + (p1 - p0) * t)
    c = np.array(dense)
    for _ in range(4):
        q = 0.75 * c[:-1] + 0.25 * c[1:]
        r = 0.25 * c[:-1] + 0.75 * c[1:]
        c = np.empty((len(q) * 2, 2))
        c[0::2], c[1::2] = q, r
    seg = np.linalg.norm(np.diff(c, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    ss = np.arange(0, s[-1], step)
    C = np.column_stack([np.interp(ss, s, c[:, 0]), np.interp(ss, s, c[:, 1])])
    T = np.gradient(C, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-9
    N = np.column_stack([-T[:, 1], T[:, 0]])          # обход по часовой (вид сверху, y вверх): наружу
    ctr = np.array([(XL + XR) / 2, (ZF + ZB) / 2])
    if np.mean(np.sum((C - ctr) * N, 1)) < 0:
        N = -N
    return C, N, ss


def hoop_field(S, Y, y0, y1, length, seed, corners_s, joint_s):
    """Лента обруча: h — над деревом (см). S — дуга вдоль контура, Y — высота."""
    rng = np.random.default_rng(seed)
    zero = np.zeros_like(S)
    w = y1 - y0
    t = np.minimum(Y - y0, y1 - Y)                     # от кромки внутрь ленты
    TH = 0.25
    body = np.where(t >= 0, TH + 0.05 * sstep(0.45, 0.12, t) * sstep(-0.02, 0.12, t), -0.12)
    roll = np.sqrt(np.clip(1 - ((0.13 - np.clip(t, -1, 0.13)) / 0.13) ** 2, 0, 1))   # закатанная кромка
    H = np.where(t < 0.13, np.where(t >= 0, TH * roll + 0.02, -0.12), body)
    H += 0.012 * (fbm2(S * 0.5, Y * 0.5, seed, 2) - 0.5)                               # прокат, окалина
    edge = sstep(0.35, 0.05, t) * (t > -0.02)
    # нахлёст: верхний слой на 9 см, ступенька на концах
    lap = sstep(-0.15, 0.15, S - joint_s) * sstep(0.15, -0.15, S - (joint_s + 9.0)) * (t >= 0)
    H += 0.24 * lap
    cav = zero.copy()
    dent = zero.copy()
    nail = zero.copy()
    yc = (y0 + y1) / 2
    heads = []
    ss = np.arange(4.0, length - 2, 9.0)
    for sc in ss:
        if np.min(np.abs(np.array(corners_s) - sc)) < 3.0 or joint_s - 1.5 < sc < joint_s + 10.5:
            continue
        heads.append((sc + rng.uniform(-0.6, 0.6), yc + rng.uniform(-0.25, 0.25), 0.55, 0.13, 0))
    for k, off in enumerate((1.6, 4.5, 7.4)):                       # заклёпки нахлёста: третья новее и крупнее
        heads.append((joint_s + off, yc + (0.4 if k == 1 else -0.2), 0.62 if k < 2 else 0.75, 0.2, 1))
    for (sc, yy, r, hh, kind) in heads:
        dd = np.hypot(S - sc, Y - yy)
        m = dd < r * 2.2
        if not m.any():
            continue
        if kind == 0:                                   # кованый гвоздь: шляпка скруглённым квадратом
            q = ((np.abs(S[m] - sc) / r) ** 4 + (np.abs(Y[m] - yy) / r) ** 4) ** 0.25
        else:                                           # заклёпка: купол
            q = dd[m] / r
        dome = np.sqrt(np.clip(1 - q ** 2, 0, 1))
        base = H[m]
        H[m] = np.where(q < 1, np.maximum(base, base.max() * 0 + TH + 0.24 * lap[m] + 0.03 + hh * dome), base)
        H[m] -= 0.03 * np.exp(-((dd[m] - r * 1.15) / 0.12) ** 2)          # смятый металл вокруг дырки
        nail[m] = np.maximum(nail[m], sstep(1.02, 0.92, q))
    # раковины ржавчины гнёздами: у кромок, у гвоздей, на нахлёсте
    f1, f2, idn = voronoi(S, Y, 0.55, seed + 3)
    rr = 0.1 + 0.2 * ((idn % 997) / 997.0)
    near = np.zeros_like(S)
    for (sc, yy, r, hh, kind) in heads:
        near = np.maximum(near, np.exp(-((S - sc) ** 2 + (Y - yy) ** 2) / 3.0 ** 2))
    nest = np.clip(0.55 * sstep(0.45, 0.7, fbm2(S * 0.15, Y * 0.5, seed + 5, 3)) + 0.5 * edge + 0.6 * near + 0.4 * lap, 0, 1)
    nest = nest * sstep(0.35, 0.6, n2(np.floor(S / 0.55) * 0.9, np.floor(Y / 0.55) * 1.3, seed + 7) + 0.25 * nest)
    nest = nest * sstep(0.45, 0.75, nest)                 # v2.1: только у гвоздей, кромок и нахлёста
    pit = np.clip(1 - (f1 / rr) ** 2, 0, 1) * nest * (t > 0.05) * (1 - np.clip(nail, 0, 1))
    H -= 0.055 * pit
    # хлопья окалины: чуть приподнятые островки
    f1b, f2b, _ = voronoi(S, Y, 1.1, seed + 11)
    flake = sstep(0.12, 0.05, f2b - f1b) * 0 + sstep(0.55, 0.65, fbm2(S * 0.4, Y * 0.6, seed + 13, 2)) * (t > 0.1)
    H += 0.02 * flake
    # вмятины от молотка у углов
    for cs in corners_s:
        if rng.random() < 0.6:
            sc = cs + rng.uniform(-6, 6)
            u = np.clip(1 - ((S - sc) ** 2 + (Y - (yc + rng.uniform(-1, 1))) ** 2) / rng.uniform(1.2, 1.9) ** 2, 0, 1) ** 2
            H -= 0.07 * u * (t > 0)
            dent = np.maximum(dent, u)
    return dict(h=H, m1=np.stack([pit, cav, dent], -1), m2=np.stack([nail, flake, zero], -1),
                m3=np.stack([edge, lap, zero + 0.5], -1), heads=heads)


def hoop_layout(bs, plank, step=0.15):
    """Контур обруча и его разметка: точки, нормали, дуга, углы (где контур поворачивает), начало нахлёста
    (на заднем торце, левее середины)."""
    C, N, ss = hoop_path(bs, plank, step)
    T = np.gradient(C, axis=0)
    ang = np.abs(np.gradient(np.unwrap(np.arctan2(T[:, 1], T[:, 0]))))
    corners = [float(ss[i]) for i in range(len(ss)) if ang[i] > 0.02 and ang[i] == ang[max(0, i - 20):i + 20].max()]
    back = np.where((C[:, 1] < -45.0) & (np.abs(C[:, 0] + 9.0) < 1.0))[0]
    joint = float(ss[back[0]]) if len(back) else float(ss[-1] * 0.6)
    return C, N, ss, corners, joint


def hoop_heads(bs):
    """Гвозди и заклёпки обоих обручей в 3D: [(x, y, z, nx, nz)] — для потёков ржавчины в texture_v2.py."""
    out = []
    for hi_, ((y0, y1), plank) in enumerate(zip(HOOPS, (0, 2))):
        C, N, ss, corners, joint = hoop_layout(bs, plank)
        S, Y = np.meshgrid(np.array([0.0, 1.0]), np.array([y0, y1]), indexing="ij")
        f = hoop_field(S, Y, y0, y1, ss[-1], 300 + hi_, corners, joint)
        for (sc, yy, r, hh, kind) in f["heads"]:
            i = int(np.clip(np.searchsorted(ss, sc), 0, len(ss) - 1))
            out.append((C[i, 0], yy, C[i, 1], N[i, 0], N[i, 1]))
    return out


if __name__ == "__main__":
    # быстрая проверка в .venv: теневой рельеф наружной грани каждой доски -> plan_v2/walls_relief.png
    import sys
    from PIL import Image
    step = float(sys.argv[1]) if len(sys.argv) > 1 else 0.15
    rows = []
    for b in boards():
        k, s, a = b["k"], b["s"], b["a"]
        lo, hi = b["lo"], b["hi"]
        us = np.arange(lo[a], hi[a], step)
        ys = np.arange(lo[1], hi[1], step)
        A, Yg = np.meshgrid(us, ys)
        P = np.zeros(A.shape + (3,))
        P[..., a] = A
        P[..., 1] = Yg
        P[..., k] = hi[k] if s > 0 else lo[k]
        face = "xyz"[k] + ("+" if s > 0 else "-")
        f = board_face(b, face, A, Yg, P)
        if b["slot"]:
            f["h"] = np.where(Yg < slot_bottom(P[..., 0], lo[1]), -1.0, f["h"])
        Hh = f["h"]
        gy, gx = np.gradient(Hh, step)
        L = np.array([-0.6, 0.45, 0.66])
        L /= np.linalg.norm(L)
        sh = np.clip((-gx * L[0] - gy * L[1] + L[2]) / np.sqrt(gx * gx + gy * gy + 1), 0, 1)
        img = (sh ** 1.2 * 255).astype(np.uint8)[::-1]
        if s < 0 and a == 2 or s > 0 and a == 0:
            pass
        rows.append((b["wall"], b["plank"], img))
    W = max(r[2].shape[1] for r in rows)
    out = []
    for wall in WALL_ISL:
        for p in (3, 2, 1, 0):
            img = next(r[2] for r in rows if r[0] == wall and r[1] == p)
            pad = np.zeros((img.shape[0], W), np.uint8)
            pad[:, :img.shape[1]] = img
            out.append(pad)
        out.append(np.zeros((12, W), np.uint8))
    Image.fromarray(np.vstack(out)).save(HERE / "plan_v2" / "walls_relief.png")
    print("ok", np.vstack(out).shape)
