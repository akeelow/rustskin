"""Sauna Bench v2: рельеф брусковых кусков — спинка (двери), стойки, ламели, железо (PLAN_v2.md, 3.4-3.7).

Каждый кусок — скруглённая коробка по габаритам low-poly (bake_v2.rbox). Грань — сетка в своих координатах:
  грань 'x-'/'x+': u = y, v = z;  'y-'/'y+': u = x, v = z;  'z-'/'z+': u = y, v = x.
Поле грани возвращает h (сдвиг наружу, см) и маски (те же каналы, что у настила, смысл — по материалу):
  дерево:  m1 = (волокно, полость, вмятина), m2 = (гвоздь, сучок, краска 0/0.5 грунт/1 верхний слой),
           m3 = (край скола/хлопья, —, тон)
  железо:  m1 = (раковина, полость/отверстие, вмятина), m2 = (болт, пузырь, эмаль), m3 = (край скола, шов, тон)
Общие развёртки (стойки, ламели, железо) повёрнуты на 180° — здесь только детали без «верха/низа» и «у ног».
"""
import numpy as np

from fields_v2 import _voronoi, fbm2, grain_relief, n2, nail_head, sstep

MATB = {"door": 15, "brass": 17, "post": 18, "joist": 19, "enamel": 20, "steel": 21, "bolt": 22, "wire": 23,
        "plug": 24}


def edge_dist(U, V, ur, vr):
    return np.minimum(np.minimum(U - ur[0], ur[1] - U), np.minimum(V - vr[0], vr[1] - V))


def groove(H, d, w, depth):
    """V-бороздка шириной w по расстоянию d."""
    return H - depth * np.clip(1 - np.abs(d) / w, 0, 1)


def crack_along(H, cav, U, V, u0, u1, v0, depth, hw, seed):
    box = (U > u0 - 1) & (U < u1 + 1) & (np.abs(V - v0) < 2)
    if not box.any():
        return H, cav
    t = np.clip((U[box] - u0) / (u1 - u0), 0, 1)
    vc = v0 + 0.3 * (n2(U[box] * 0.18, seed + 0.0, seed) - 0.5)
    prof = np.sin(np.pi * t) ** 0.6
    g = np.clip(1 - np.abs(V[box] - vc) / (hw * prof + 1e-3), 0, 1)
    H[box] -= depth * prof * g ** 0.8
    cav[box] = np.maximum(cav[box], g * prof)
    return H, cav


def end_rings(U, V, pu, pv, s, seed):
    """Годичные кольца торца вокруг сердцевины (pu, pv) — гребни 0..1 и радиальная трещина."""
    r = np.hypot(U - pu, V - pv) + 0.35 * (fbm2(U * 0.3, V * 0.3, seed, 2) - 0.5)
    f = (r / s) % 1.0
    ring = np.exp(-((f - 0.8) / 0.12) ** 2)
    ang = np.arctan2(V - pv, U - pu)
    da = np.abs(np.angle(np.exp(1j * (ang - (seed % 7)))))
    chk = (r * da < 0.12) & (r > 0.5)
    return ring, chk


def out(H, z, **k):
    d = dict(h=H, m1=np.stack([k.get("a1", z), k.get("b1", z), k.get("c1", z)], -1),
             m2=np.stack([k.get("a2", z), k.get("b2", z), k.get("c2", z)], -1),
             m3=np.stack([k.get("a3", z), k.get("b3", z), k.get("c3", z)], -1), mat=k["mat"])
    return d


# ------------------------------------------------------------------ спинка: две доски от двери
HB = {3: dict(z=(63.7, 82.2), seed=11, green=True), 4: dict(z=(47.4, 64.8), seed=23, green=False)}
HB_Y = (-62.8, 64.5)
POST_Y = (-53.9, 56.5)


def door_face(board, face, U, V, P):
    b = HB[board]
    z0, z1 = b["z"]
    zc = (z0 + z1) / 2
    sd = b["seed"]
    rng = np.random.default_rng(sd)
    zero = np.zeros_like(U)
    H = np.zeros_like(U)
    cav = zero.copy()
    dent = zero.copy()
    nail = zero.copy()
    paint = zero.copy()
    edge = zero.copy()
    mat = np.full(U.shape, MATB["door"])
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    if face in ("y-", "y+"):                       # торцы: кольца, следы пилы, трещина
        ring, chk = end_rings(U, V, 111.6, zc - 22.0, 0.55, sd + (face == "y+"))
        H += 0.05 * ring - 0.3 * chk
        H += 0.02 * np.sin((V + 0.3 * U) / 0.9 * np.pi)
        cav = np.maximum(cav, chk * 1.0)
        return out(H, zero, a1=ring, b1=cav, c3=zero + 0.5, mat=mat)
    inner = face == "x-"
    # ---- волокна вдоль доски
    g = grain_relief(y, (z if face[0] == "x" else x) - zc, rng.uniform(0.8, 1.8), 0.04 * rng.choice((-1, 1)), rng.uniform(-2, 2),
                     rng.uniform(1.0, 1.4), sd)     # v2.4: арки вместо ровной «гофры»
    # ---- краска: грунт (синий) и верхний слой; меньше у кромок и на верхней кромке
    if face[0] == "x":
        de = np.minimum(np.minimum(z - z0, z1 - z), np.minimum(y - HB_Y[0], HB_Y[1] - y))
        bias = -0.18 * sstep(2.5, 0.0, de) - (0.06 if not inner else 0.0)
        pn = fbm2(y * 0.045 + 11 * (board == 3), z * 0.11 + 5 * inner, sd + 41, 5) + 0.1 * (g - 0.5) + bias
        pn = pn + 0.08 * (n2(y * 0.5, z * 0.9, sd + 43) - 0.5)
        t_top = 0.47 if b["green"] else 0.46       # v2.4: краски больше (референс), было 0.56/0.54
        top = sstep(t_top, t_top + 0.006, pn)
        prim = sstep(t_top - 0.035, t_top - 0.029, pn) if b["green"] else top
        paint = np.maximum(0.5 * prim, top)
        # кракелюр в краске
        f1, f2 = _voronoi(y, z, 1.3, sd + 51)
        crq = sstep(0.07, 0.02, f2 - f1) * top
        # хлопья: по границе островов местами приподняты
        band = sstep(t_top + 0.02, t_top + 0.006, pn) * top
        flake = band * sstep(0.62, 0.7, n2(y * 0.8, z * 0.8, sd + 53))
        edge = np.maximum(sstep(t_top - 0.03, t_top - 0.006, pn) * (1 - top), flake)
        H += 0.075 * (1 - prim) * (g - 0.35) * (1.2 if not inner else 1.0)   # голое дерево выветрено глубже
        H += 0.03 * prim * (g - 0.35)
        H += 0.025 * prim + 0.025 * top - 0.018 * crq + 0.07 * flake
        # V-паз вагонки посередине доски и (на верхней доске изнутри) калёвка у верха
        H = groove(H, z - zc, 0.45, 0.32)
        cav = np.maximum(cav, np.clip(1 - np.abs(z - zc) / 0.25, 0, 1))
        if board == 3 and inner:
            H += 0.14 * np.sqrt(np.clip(1 - ((z - (z1 - 2.4)) / 0.45) ** 2, 0, 1))
            H = groove(H, z - (z1 - 3.0), 0.12, 0.12)
        # трещины вдоль волокон
        for k in range(3):
            u0 = rng.uniform(HB_Y[0] + 5, HB_Y[1] - 25)
            H, cav = crack_along(H, cav, y, z, u0, u0 + rng.uniform(8, 22), rng.uniform(z0 + 2, z1 - 2), 0.3, 0.18,
                                 sd + 60 + k)
        # гвозди в стойки (изнутри), один гнутый рядом
        if inner:
            for py in POST_Y:
                for dz in (-3.5, 3.5):
                    m = (np.abs(y - py) < 2) & (np.abs(z - zc - dz) < 2)
                    if m.any():
                        hb, nm = nail_head(H[m], y[m] - py - rng.uniform(-0.3, 0.3), z[m] - zc - dz, 0.0, 0, r=0.62)
                        H[m] = hb
                        nail[m] = np.maximum(nail[m], nm)
            if board == 4:                              # след снятой петли: менее выветрено, 3 дыры от шурупов
                hg = (np.abs(y - 28.0) < 4.0) & (np.abs(z - 56.0) < 1.6)
                H = np.where(hg, 0.02 + 0.02 * (g - 0.35), H)
                paint = np.where(hg, 0, paint)
                for sy in (25.3, 28.0, 30.7):
                    dd = np.hypot(y - sy, z - 56.0)
                    H -= 0.45 * sstep(0.27, 0.2, dd) + 0.04 * np.clip(1 - ((dd - 0.35) / 0.15) ** 2, 0, 1)
                    cav = np.maximum(cav, sstep(0.27, 0.2, dd))
            if board == 3:                              # латунная накладка скважины и пробка в дыре от ручки
                ey, ez = 8.0, 73.0
                q = np.hypot((y - ey) / 1.6, np.maximum(np.abs(z - ez) - 2.4, 0) / 1.6)
                plate = sstep(1.0, 0.95, q)
                H = np.where(plate > 0.01, np.maximum(H, 0.1 + 0.05 * np.sqrt(np.clip(1 - q ** 2, 0, 1))), H)
                key = (np.hypot(y - ey, z - (ez + 0.6)) < 0.45) | ((np.abs(y - ey) < 0.17) & (z > ez - 0.9) & (z < ez + 0.6))
                H = np.where(key & (plate > 0.5), -0.6, H)
                for pz in (ez + 3.3, ez - 3.3):
                    dd = np.hypot(y - ey, z - pz)
                    H = np.where(dd < 0.22, np.maximum(H, 0.18), H)
                mat = np.where(plate > 0.5, MATB["brass"], mat)
                cav = np.where(plate > 0.5, (key & (plate > 0.5)) * 1.0, cav)     # паз вагонки под накладкой не виден
                paint = np.where(plate > 0.5, 0, paint)
                py_, pz_ = 46.0, 73.0
                dd = np.hypot(y - py_, z - pz_)
                plug = dd < 1.3
                pr = np.exp(-((((dd / 0.33) % 1.0) - 0.8) / 0.15) ** 2)
                H = np.where(plug, -0.04 + 0.02 * pr - 0.2 * (np.abs(y - py_ + 0.2 * (z - pz_)) < 0.05), H)
                H -= 0.18 * np.exp(-((dd - 1.32) / 0.05) ** 2)
                mat = np.where(plug, MATB["plug"], mat)
                paint = np.where(dd < 1.45, 0, paint)
        else:                                           # снаружи: следы поперечных планок двери с дырами
            for c in (-29.5, 29.5):
                bd = np.abs(y - c) < 4.5
                H = np.where(bd, H * 0.4 + 0.03, H)
                paint = np.where(bd, paint * 0.3, paint)
                for dz in (-4.0, 4.0):
                    dd = np.hypot(y - c, z - zc - dz)
                    H -= 0.5 * sstep(0.28, 0.2, dd)
                    cav = np.maximum(cav, sstep(0.28, 0.2, dd))
        # вмятины
        for _ in range(8):
            a, c, r, d = rng.uniform(*HB_Y), rng.uniform(z0 + 1, z1 - 1), rng.uniform(0.6, 1.6), rng.uniform(0.05, 0.1)
            u = np.clip(1 - ((y - a) ** 2 + (z - c) ** 2) / r ** 2, 0, 1) ** 2
            H -= d * u
            dent = np.maximum(dent, u)
    else:                                               # верхняя и нижняя кромки доски
        H += 0.1 * (g - 0.35)
        if face == "z+" and board == 3:                 # за верх хватаются: стёрт, вмятины и зарубки
            for _ in range(10):
                a, r, d = rng.uniform(*HB_Y), rng.uniform(0.5, 1.3), rng.uniform(0.08, 0.16)
                u = np.clip(1 - ((y - a) ** 2 + ((x - 111.55) * 1.5) ** 2) / r ** 2, 0, 1) ** 2
                H -= d * u
                dent = np.maximum(dent, u)
            for a in (-18.0, 31.0):
                H = groove(H, y - a, 0.25, 0.35)
    return out(H, zero, a1=g, b1=np.clip(cav, 0, 1), c1=dent, a2=nail, c2=paint, a3=edge, c3=zero + b["seed"] / 30.0,
               mat=mat)


# ------------------------------------------------------------------ стойки (общие развёртки парами)
def post_face(post, face, U, V, P, lo, hi):
    sd = 70 + post
    rng = np.random.default_rng(sd)
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    zero = np.zeros_like(U)
    H = np.zeros_like(U)
    cav = zero.copy()
    dent = zero.copy()
    knot = zero.copy()
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    if face in ("z+", "z-"):
        ring, chk = end_rings(x, y, cx + 0.7, cy - 1.5, 0.5, sd)
        H += 0.05 * ring - 0.35 * chk
        cav = chk * 1.0
        if face == "z+":                              # срублен топором: две грани с гребнем
            H -= 0.35 * np.abs(y - cy) / ((hi[1] - lo[1]) / 2) + 0.1 * (n2(x * 2, y * 0.5, sd) - 0.5)
            H -= 0.06 * np.abs(np.sin((y - cy) / 0.9 * np.pi)) ** 3
        return out(H, zero, a1=ring, b1=cav, c3=zero + 0.5, mat=np.full(U.shape, MATB["post"]))
    across = U
    g = grain_relief(z, across - (cy if face[0] == "x" else cx), 3.5, 0.012, 1.0, 1.05, sd)
    H += 0.07 * (g - 0.35)
    # тесание топором: лунки 6-9 см вдоль, 3-5 см поперёк, рядами вразбег
    f1, f2 = _voronoi(across * 1.0, z * 0.35, 2.6, sd + 3)      # v2.4: мельче и площе (были «подушки»)
    H -= 0.1 * np.clip(1 - (f1 / 1.8) ** 2, 0, 1) - 0.03 * sstep(0.25, 0.0, f2 - f1)
    # трещины усушки: длинная на широкой грани, короткая на узкой
    span = hi[2] - lo[2]
    if face[0] == "x":
        H, cav = crack_along(H, cav, z, across, lo[2] + span * 0.2, lo[2] + span * 0.75, cy + rng.uniform(-2, 2), 0.5,
                             0.22, sd + 5)
    else:
        H, cav = crack_along(H, cav, z, across, lo[2] + span * 0.45, lo[2] + span * 0.65, cx, 0.35, 0.16, sd + 6)
    # низ размочален, сучок, вмятины
    fr = sstep(8.0, 0.0, z - lo[2])
    H -= fr * (0.1 + 0.2 * n2(across * 2.0, z * 0.6, sd + 7))
    kz = lo[2] + span * rng.uniform(0.3, 0.7)
    dd = np.hypot((z - kz) / 1.4, across - (cy if face[0] == "x" else cx))
    if face == "x+":
        knot = sstep(1.0, 0.8, dd)
        H += 0.07 * knot - 0.05 * np.exp(-((dd - 1.0) / 0.12) ** 2)
    for _ in range(5):
        a, c, r, d = rng.uniform(lo[2] + 5, hi[2] - 3), rng.uniform(-3, 3), rng.uniform(0.6, 1.4), rng.uniform(0.05, 0.12)
        u = np.clip(1 - ((z - a) ** 2 + (across - (cy if face[0] == "x" else cx) - c) ** 2) / r ** 2, 0, 1) ** 2
        H -= d * u
        dent = np.maximum(dent, u)
    return out(H, zero, a1=g, b1=np.clip(cav, 0, 1), c1=dent, b2=knot, c3=zero + 0.5, mat=np.full(U.shape, MATB["post"]))


# ------------------------------------------------------------------ ламель (одна развёртка на 10, часть перевёрнута)
def joist_face(face, U, V, P, lo, hi):
    sd = 91
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    zero = np.zeros_like(U)
    H = np.zeros_like(U)
    cav = zero.copy()
    cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
    mat = np.full(U.shape, MATB["joist"])
    if face in ("y-", "y+"):                         # торцы видны сбоку: кольца, пила, сколы, щепа
        ring, chk = end_rings(x, z, cx + 3.0, cz - 9.0, 0.6, sd + (face == "y+"))
        H += 0.05 * ring - 0.3 * chk + 0.025 * np.sin((x + 0.4 * z) / 0.8 * np.pi)
        cav = chk * 1.0
        # отщеп на углу и щепа по кромке
        H -= 0.4 * sstep(1.6, 0.6, np.hypot(x - (hi[0] - 0.3), z - (hi[2] - 0.2)))
        return out(H, zero, a1=ring, b1=cav, c3=zero + 0.5, mat=mat)
    g = grain_relief(y, (x if face[0] == "z" else z) - cx, 2.5, 0.02, 0.5, 1.0, sd)
    H += 0.08 * (g - 0.35)
    saw = np.abs(np.sin((y + 0.4 * n2(x * 0.3, y * 0.05, sd) * 3) / 1.25 * np.pi)) ** 3
    H -= 0.02 * saw
    # трещины от обоих торцов (симметрично: копии повёрнуты)
    for (u0, u1, v0) in ((lo[1] - 0.5, lo[1] + 9.0, cx + 3.0), (hi[1] - 7.0, hi[1] + 0.5, cx - 4.0)):
        H, cav = crack_along(H, cav, y, x if face[0] == "z" else z, u0, u1, v0 if face[0] == "z" else cz, 0.35, 0.2, sd + 3)
    # щепа по длинным кромкам у торцов
    near_end = sstep(4.0, 0.0, np.minimum(y - lo[1], hi[1] - y))
    H -= near_end * 0.15 * sstep(0.6, 0.75, n2(y * 1.5, x * 1.5 + z, sd + 5))
    return out(H, zero, a1=g, b1=np.clip(cav, 0, 1), c3=zero + 0.5, mat=mat)


# ------------------------------------------------------------------ железо: эмаль старой кровати
IRON = {17: dict(seed=31), 19: dict(seed=37), 23: dict(seed=41), 27: dict(seed=43)}


def iron_face(piece, face, U, V, P, lo, hi):
    sd = IRON[piece]["seed"]
    rng = np.random.default_rng(sd)
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    zero = np.zeros_like(U)
    H = np.zeros_like(U)
    ur = {"x": (lo[1], hi[1]), "y": (lo[0], hi[0]), "z": (lo[1], hi[1])}[face[0]]
    vr = {"x": (lo[2], hi[2]), "y": (lo[2], hi[2]), "z": (lo[0], hi[0])}[face[0]]
    de = edge_dist(U, V, ur, vr)
    # эмаль: облезла на ~половину, у кромок — сколы
    en_n = fbm2(U * 0.15, V * 0.3 + 3 * (face[1] == "+"), sd, 5) + 0.1 * (n2(U * 1.2, V * 1.2, sd + 1) - 0.5) - 0.28 * sstep(1.6, 0.0, de)
    en = sstep(0.47, 0.475, en_n)
    edge = sstep(0.44, 0.47, en_n) * (1 - en)
    # раковины в голом металле: гнёздами
    f1, f2 = _voronoi(U, V, 0.55, sd + 3)
    nest = sstep(0.45, 0.65, fbm2(U * 0.12, V * 0.3, sd + 5, 3)) * (1 - en)
    rr = 0.12 + 0.18 * (n2(np.floor(U / 0.55), np.floor(V / 0.55), sd + 7))
    pit = np.clip(1 - (f1 / rr) ** 2, 0, 1) * nest
    # пузыри ржавчины под эмалью
    b1, _ = _voronoi(U, V, 3.0, sd + 9)
    blist = np.clip(1 - (b1 / 0.75) ** 2, 0, 1) * en * sstep(0.62, 0.7, n2(np.floor(U / 3) * 1.3, np.floor(V / 3) * 1.7, sd + 11))
    H += 0.03 * en - 0.07 * pit + 0.06 * blist
    H += 0.015 * (fbm2(U * 0.5, V * 0.5, sd + 13, 2) - 0.5)        # окалина, неровность проката
    cav = zero.copy()
    dent = zero.copy()
    bolt = zero.copy()
    weld = zero.copy()
    for _ in range(4 if ur[1] - ur[0] > 8 and vr[1] - vr[0] > 3 else 0):    # вмятины от молотка (кромки)
        a = rng.uniform(ur[0] + 3, ur[1] - 3)
        c = vr[1] - rng.uniform(0.3, 1.5) if rng.random() < 0.5 else vr[0] + rng.uniform(0.3, 1.5)
        r, d = rng.uniform(1.0, 1.8), rng.uniform(0.06, 0.12)
        u = np.clip(1 - ((U - a) ** 2 + (V - c) ** 2) / r ** 2, 0, 1) ** 2
        H -= d * u
        dent = np.maximum(dent, u)
    mat = np.where(en > 0.5, MATB["enamel"], MATB["steel"])
    outer = (piece == 27 and face == "y+") or (piece == 17 and face == "x-")
    if outer:                                           # ряд пробитых овальных отверстий (симметрично по длине)
        uc = (ur[0] + ur[1]) / 2
        vc = (vr[0] + vr[1]) / 2
        pos = (-80.0, -40.0, 0.0, 40.0, 80.0) if piece == 27 else (-36.0, 36.0)
        for a in pos:
            q = np.hypot((U - uc - a) / 0.6, (V - vc) / 1.3)
            H -= 1.2 * sstep(1.0, 0.93, q) + 0.06 * np.exp(-((q - 1.15) / 0.12) ** 2)
            cav = np.maximum(cav, sstep(1.0, 0.93, q))
    if piece == 27 and face == "y+":                    # заваренная трещина поперёк стенки
        wu = 18.0 + 0.25 * np.sin(V * 0.8)
        dw = np.abs(U - wu)
        bead = np.sqrt(np.clip(1 - (dw / 0.55) ** 2, 0, 1))
        rip = 0.5 + 0.5 * np.cos((V + 0.3 * dw) / 0.7 * 2 * np.pi)
        H = np.maximum(H, 0.02 + 0.13 * bead * (0.8 + 0.2 * rip))
        weld = np.maximum(sstep(0.6, 0.4, dw), 0.5 * sstep(2.5, 0.6, dw))
        for _ in range(9):                              # брызги
            a, c = wu.mean() + rng.normal(0, 1.3), rng.uniform(vr[0] + 0.5, vr[1] - 0.5)
            dd = np.hypot(U - a, V - c)
            H = np.where(dd < 0.13, np.maximum(H, 0.06), H)
        mat = np.where(weld > 0.5, MATB["steel"], mat)
    if piece == 23 and face == "x+":                    # пластина: два болта с шайбами и гнутый гвоздь вместо третьего
        for (by, bz) in ((-62.6, 28.3), (-62.6, 32.8)):
            dd = np.hypot(y - by, z - bz)
            wash = sstep(1.5, 1.4, dd)
            ang = np.arctan2(z - bz, y - by)
            hexr = 0.85 / np.cos(((ang + 0.3) % (np.pi / 3)) - np.pi / 6)
            head = sstep(hexr, hexr - 0.06, dd)
            H = np.maximum(H, 0.2 * wash + 0.45 * head * (1 - 0.15 * sstep(0.2, 0.6, dd / hexr)))
            bolt = np.maximum(bolt, wash)
        dd = np.hypot(y + 45.9, z - 30.5)
        H = np.maximum(H, np.where(dd < 0.45, 0.15, -9))
        sh = (np.abs(z - 30.5) < 0.17) & (y > -45.9) & (y < -43.4)
        H = np.where(sh, np.maximum(H, 0.22), H)
        bolt = np.maximum(bolt, (dd < 0.45) | sh)
        mat = np.where(bolt > 0.5, MATB["bolt"], mat)
    return out(H, zero, a1=pit, b1=np.clip(cav, 0, 1), c1=dent, a2=bolt * 1.0, b2=blist, c2=en, a3=edge, b3=weld,
               c3=zero + 0.5, mat=mat)
