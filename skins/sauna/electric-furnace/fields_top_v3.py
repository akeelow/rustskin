"""Sauna Stove v3: верх плиты и борт — поля высот и грани брусков (PLAN_v3.md §3.2–3.3). numpy, см.

Маски — как в fields_v3.py (m1 = волокно/кольца, полость, вмятина; m2 = гвоздь, сучок, обугливание/выгорание;
m3 = ржавчина, накипь, тон; idc = код материала / 32, номер, кора).
"""
import numpy as np

import geom_v3 as G
from fields_v3 import MAT, STEP, char_field, fbm2, grain_relief, n2, nail_head, sstep, voronoi

# конфорки: центр (x, z), радиус чаши, радиус выреза альфой (v2.2), большая ли
BURNERS = [((14.17, 14.79), 9.0, 8.3, True), ((-14.29, -14.31), 9.0, 8.3, True),
           ((-14.35, 14.41), 6.9, 6.0, False), ((14.31, -14.36), 6.9, 6.0, False)]
TOP_ISLANDS = {3, 74, 75, 136, 137, 91, 92, 141, 142, 178, 179, 200, 201, 109, 110}
COIL_ISLANDS = {50, 51, 72, 73, 117, 134, 148, 151}
CAP_ISLANDS = {180}
RIM_ISLANDS = {26, 8, 6}


class Top:
    """Верх плиты: поле Y(x, z) поверх рельефа модели (плита 113.6, ободки конфорок до 115.7, чаши 114.2).
    Эмаль слоем 0.3 мм: остатки — у краёв, у конфорок выгорела до чёрного железа неровным краем; кракелюр, сколы
    ступенькой, окалина хлопьями, раковины, кольца старой конфорки, наплывы накипи (корка до 1.2 мм), вмятины."""
    X = (-32.2, 32.2)
    Z = (-32.2, 32.2)

    def __init__(self, seed=8):
        rng = np.random.default_rng(seed)
        # наплывы накипи: (центр, радиус, толщина, seed) — крупное пятно между конфорками спереди, мелкие у краёв
        self.crusts = [((-3.0, 3.5), 5.5, 0.12, 0), ((1.5, -1.5), 3.5, 0.09, 1), ((-24.5, 1.0), 3.0, 0.07, 2),
                       ((26.0, 3.0), 2.6, 0.06, 3)]
        self.dents = []
        for (c, r, _, big) in BURNERS:
            for _ in range(2):
                a = rng.uniform(0, 2 * np.pi)
                rr = r + 4.5 + rng.uniform(0, 4)
                self.dents.append((c[0] + rr * np.cos(a), c[1] + rr * np.sin(a), rng.uniform(1.0, 2.0), rng.uniform(0.05, 0.09)))
        self.chips = [(rng.uniform(-29, 29), rng.uniform(-29, 29), rng.uniform(0.6, 1.8)) for _ in range(26)]

    def grid(self, step=STEP):
        x = np.arange(self.X[0], self.X[1] + 1e-6, step)
        z = np.arange(self.Z[0], self.Z[1] + 1e-6, step)
        return np.meshgrid(x, z)

    def field(self, X, Z):
        base = G.raster_height(G.tris(islands=TOP_ISLANDS), X, Z, 0, 2, 1, fill=113.6)
        z0 = np.zeros(X.shape)
        rmin = np.full(X.shape, 1e9)
        rcup = np.zeros(X.shape)
        ang = np.zeros(X.shape)
        for (c, r, _, big) in BURNERS:
            d = np.hypot(X - c[0], Z - c[1])
            take = d - r < rmin - rcup
            rmin = np.where(take, d, rmin)
            rcup = np.where(take, r, rcup)
            ang = np.where(take, np.arctan2(Z - c[1], X - c[0]), ang)
        # ободок у модели гранёный (сглажен нормалями): заменяем осесимметричным профилем — медиана высоты по радиусу,
        # иначе грани запекутся в нормаль и в игре ободок станет многоугольником (PROMPT §5)
        for (c, r, _, big) in BURNERS:
            d = np.hypot(X - c[0], Z - c[1])
            zone = d < r + 3.6
            bins = np.round(d[zone] / 0.05).astype(int)
            prof = {}
            for b in np.unique(bins):
                prof[b] = np.median(base[zone][bins == b])
            keys = np.array(sorted(prof))
            vals = np.array([prof[k] for k in keys])
            vals = np.convolve(np.pad(vals, 3, mode="edge"), np.ones(7) / 7, mode="valid")    # сгладить ступени
            base = np.where(zone, np.interp(d / 0.05, keys, vals), base)
        cup = rmin < rcup + 0.05
        bezel = (~cup) & (base > 113.65)
        plate = ~cup & ~bezel
        # ---- выгоревшая зона: неровный край в 3–7 см от ободка
        burn_r = rcup + 3.0 + 3.2 * fbm2(np.cos(ang) * 2 + rcup, np.sin(ang) * 2, 41, 3) + 1.2 * (n2(X * 0.25, Z * 0.25, 43) - 0.5)
        enamel = plate & (rmin > burn_r)
        for (x, z, r) in self.chips:              # сколы эмали островами
            d = np.hypot(X - x, Z - z) + 0.6 * (n2(X * 0.8, Z * 0.8, int(abs(x) * 10) % 97) - 0.5)
            enamel &= d > r
        H = base.copy()
        # железо (выгорело): окалина хлопьями и раковины гнёздами
        f1, f2 = voronoi(X, Z, 0.9, 51)
        flake_edge = sstep(0.12, 0.02, f2 - f1)
        lift = 0.025 * np.clip(f1 / 0.5, 0, 1) * (n2(X * 0.7, Z * 0.7, 53) > 0.45)
        iron_h = 0.015 * (n2(X * 2.0, Z * 2.0, 55) - 0.5) + lift - 0.02 * flake_edge
        pits = fbm2(X * 0.9, Z * 0.9, 57, 3) > 0.62
        g1, _ = voronoi(X, Z, 0.45, 59)
        pit = sstep(0.22, 0.05, g1) * pits
        iron_h -= 0.06 * pit
        # кольца старой конфорки на ободке и вокруг: тонкие ступеньки окалины
        rings = np.zeros(X.shape)
        for k, dr in enumerate((0.9, 2.1, 3.4)):
            rr = rmin - rcup - dr - 0.3 * (n2(ang * 3, k * 1.0, 61) - 0.5)
            rings = np.maximum(rings, np.exp(-(rr / 0.12) ** 2) * (n2(ang * 4, k + 3.0, 63) > 0.3))
        iron_h += 0.03 * rings
        # эмаль: слой 0.3 мм, кракелюр; у края скола — ступенька (сама разница уровней)
        c1, c2 = voronoi(X * (1 + 0.15 * n2(X * 0.1, Z * 0.1, 65)), Z, 1.6, 67)
        craz = sstep(0.09, 0.015, c2 - c1)
        en_h = 0.03 - 0.022 * craz + 0.004 * (n2(X * 1.5, Z * 1.5, 69) - 0.5)
        H = H + np.where(enamel, en_h, np.where(cup, 0.01 * (n2(X * 2, Z * 2, 71) - 0.5) - 0.03 * pit, iron_h))
        # ---- наплывы накипи: бугристая корка с пузырями
        crust = z0.copy()
        for ((cx, cz), r, th, sd) in self.crusts:
            d = np.hypot(X - cx, (Z - cz) * 1.25) + r * 0.55 * (fbm2(X * 0.25, Z * 0.25, 80 + sd, 3) - 0.5)
            a = sstep(r, r * 0.55, d) * (~cup)
            if not a.any():
                continue
            lump = 0.5 + 0.5 * fbm2(X * 0.9, Z * 0.9, 85 + sd, 3)
            b1, _ = voronoi(X, Z, 0.35, 90 + sd)
            bubble = sstep(0.12, 0.03, b1) * (n2(X * 1.3, Z * 1.3, 93 + sd) > 0.5)
            H = H + th * a * lump - 0.04 * bubble * a
            crust = np.maximum(crust, a)
        # ---- вмятины от упавших камней
        dent = z0.copy()
        for (x, z, r, d) in self.dents:
            dd = np.hypot(X - x, Z - z)
            u = np.clip(1 - (dd / r) ** 2, 0, 1) ** 2 * plate
            H -= d * u
            dent = np.maximum(dent, u)
        mat = np.where(cup, MAT["cup"], np.where(enamel, MAT["plate_enamel"], MAT["plate_iron"]))
        mat = np.where(crust > 0.5, MAT["scale"], mat)
        rust = np.clip(pit + 0.6 * (~enamel & ~cup) * sstep(0.55, 0.75, fbm2(X * 0.2, Z * 0.2, 97, 3)), 0, 1)
        cav = np.clip(craz * enamel * 0.6 + pit * 0.8 + flake_edge * (~enamel) * 0.3, 0, 1)
        burnt = np.clip(1 - (rmin - rcup) / np.maximum(burn_r - rcup, 0.1), 0, 1) * (~cup)
        return dict(h=H, cav=cav, dent=dent, rust=rust, crust=crust, mat=mat.astype(float), char=burnt, grain=rings,
                    tone=0.5 + 0.5 * (fbm2(X * 0.05, Z * 0.05, 99, 2) - 0.5), nail=z0, knot=z0, sid=z0 - 1, bark=z0)

    @staticmethod
    def height_at(H, X, Z, x, z):
        """Билинейно: высота поля в точках (x, z) (листья на плите)."""
        xs, zs = X[0], Z[:, 0]
        fx = np.clip((np.asarray(x) - xs[0]) / (xs[1] - xs[0]), 0, len(xs) - 1.001)
        fz = np.clip((np.asarray(z) - zs[0]) / (zs[1] - zs[0]), 0, len(zs) - 1.001)
        i, j = fz.astype(int), fx.astype(int)
        tz, tx = fz - i, fx - j
        return (H[i, j] * (1 - tx) * (1 - tz) + H[i, j + 1] * tx * (1 - tz) + H[i + 1, j] * (1 - tx) * tz
                + H[i + 1, j + 1] * tx * tz)


# ------------------------------------------------------------------ борт плиты: 4 бруска
# (имя, lo, hi, ось длины): передний и задний — во всю длину, боковые — между ними
RIM_BOARDS = [("front", (-35.45, 109.45, 31.55), (35.45, 115.1, 35.45), 0),
              ("back", (-35.45, 109.45, -35.45), (35.45, 115.1, -31.55), 0),
              ("left", (-35.45, 109.45, -31.55), (-31.55, 115.1, 31.55), 2),
              ("right", (31.55, 109.45, -31.55), (35.45, 115.1, 31.55), 2)]
INNER = {"front": (2, -1), "back": (2, 1), "left": (0, 1), "right": (0, -1)}     # ось и знак внутренней грани


def rim_face(board, face, U, V, P, lo, hi, along_ax):
    """Грань бруска борта: волокна вдоль бруска, на торцах — кольца и трещина, внутренняя кромка у горячей плиты
    обуглена (верхняя и внутренняя грани), гвозди на верхней грани у концов. face = 'x-', 'y+' и т. п."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    seed = {"front": 1, "back": 2, "left": 3, "right": 4}[board]
    al = P[..., along_ax]
    ax = "xyz".index(face[0])
    up_face = face == "y+"
    is_end = ax == along_ax
    z0 = np.zeros(U.shape)
    h, cav = z0.copy(), z0.copy()
    if not is_end:
        other = [i for i in range(3) if i not in (ax, along_ax)][0]
        across = P[..., other]
        gr = grain_relief(al, across, 2.0 + seed, 0.01, (lo[other] + hi[other]) / 2 + 0.7, 1.0, 110 + seed)
        h += 0.06 * (gr - 0.35) + 0.04 * (fbm2(al * 0.05, across * 0.4, 120 + seed, 3) - 0.5)
    else:
        a, b = [P[..., i] for i in range(3) if i != ax]
        cc = (lo + hi) / 2
        ca, cb = [cc[i] for i in range(3) if i != ax]
        rr = np.hypot(a - ca - 2.5, b - cb - 3.0) + 0.3 * (n2(a * 0.6, b * 0.6, 130 + seed) - 0.5)
        f = rr / 0.35
        f = f - np.floor(f)
        gr = np.exp(-((f - 0.5) / 0.18) ** 2)
        h += 0.04 * gr - 0.02
        th = np.arctan2(b - cb, a - ca)
        crk = np.exp(-(np.angle(np.exp(1j * (th - 0.7 - seed))) / 0.08) ** 2)
        h -= 0.15 * crk
        cav = np.maximum(cav, crk)
    ia, isg = INNER[board]
    inner_edge = lo[ia] if isg < 0 else hi[ia]
    dist_in = np.abs(P[..., ia] - inner_edge)
    reach = (0.3 + 2.2 * np.clip(fbm2(al * 0.09, seed * 3.0, 140 + seed, 3) - 0.3, 0, 1)) * (fbm2(al * 0.04, seed * 5.0, 145 + seed, 2) > 0.38)
    if up_face:
        amt = sstep(reach + 1e-3, reach * 0.45, dist_in) * (reach > 0.2)
        cy = P[..., ia]
    elif ax == ia and face[1] == ("+" if isg > 0 else "-"):      # внутренняя грань (к плите): выше уровня плиты
        amt = sstep(112.6, 113.8, P[..., 1]) * np.clip(reach / 1.2, 0, 1)
        cy = P[..., 1]
    else:
        amt = z0
        cy = P[..., 1]
    char = z0.copy()
    if (amt > 0).any():
        m = amt > 0
        dh, cr = char_field(al[m], cy[m], amt[m], 1.5, 150 + seed, along_y=False)
        h[m] += dh
        cav[m] = np.maximum(cav[m], cr)
        char = amt
    nail = z0.copy()
    if up_face:
        cross_ax = 2 if along_ax == 0 else 0
        mid_c = (lo[cross_ax] + hi[cross_ax]) / 2 + 0.5 * (1 if isg > 0 else -1)
        L0, L1 = lo[along_ax], hi[along_ax]
        for e, kind in ((L0 + 2.0, 3), (L1 - 2.0, 0), ((L0 + L1) / 2 + 3.0 * seed - 7, 0)):
            Uu, Vv = al - e, P[..., cross_ax] - mid_c
            box = (np.abs(Uu) < 1.6) & (np.abs(Vv) < 1.6)
            if box.any():
                Hn, nm = nail_head(h[box], Uu[box], Vv[box], 0.0, kind)
                h[box] = Hn
                nail[box] = np.maximum(nail[box], nm)
    mat = np.where(char > 0.5, MAT["char"], MAT["rim"])
    mat = np.where(nail > 0.5, MAT["nail"], mat).astype(float)
    return dict(h=h, grain=gr, cav=cav, nail=nail, char=char, mat=mat, tone=z0 + 0.2 * seed, dent=z0, knot=z0,
                rust=z0, crust=z0, sid=z0 + 20 + seed, bark=z0)
