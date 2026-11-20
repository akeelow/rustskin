"""Sauna Bench v2: рельеф настила как поле высот на numpy (общий для bake_v2.py в Blender и проверок в .venv).

Настил строится одной сеткой с шагом 1.5 мм над верхом матраса: z = DECK_Z + h(x, y). Всё, что даёт форму,
считается здесь функциями, и те же функции пишут маски для цвета (рельеф и цвет совпадают пиксель в пиксель):
  рейки, щели (сужаются), фаски (скругление по износу), волокна (ранняя древесина вытерта, гребни поздней),
  сучки (волокна огибают, радиальные трещины, один выпал), торцевые и продольные трещины, вмятины, царапины,
  гвозди (кованые шляпки, утопленные с воронкой, торчащий), «улыбки» от молотка, доска от поддона (дуги пилы,
  старые дыры), новая составная рейка со стальной скобой на стыке, отщеп, поднятая щепа, обугленный угол.

Единицы — сантиметры, оси модели: x — длина (+x изголовье), y — ширина, z — вверх.
Размеры деталей — под 5.8 px/см экспорта (1 px = 1.7 мм): см. PLAN_v2.md, раздел 1.
"""
import numpy as np

# ------------------------------------------------------------------ noise
def vnoise(p, seed=0):
    """Value noise по точкам (..., 2 или 3) -> (...) 0..1."""
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


# ------------------------------------------------------------------ layout
DECK_X = (-111.2, 110.4)      # края настила по длине (рейки — с разбросом концов)
DECK_Y = (-53.6, 55.6)        # по ширине: внешние рейки скругляются по плечу матраса
DECK_Z = 55.05                # верх реек (как v1)
GAP_FLOOR = -1.2              # дно щели (тёмная полость)
STEP = 0.15                   # шаг сетки, см
N_SLATS = 13
JOISTS = (-100.0, -82.0, -56.0, -27.5, -9.5, 21.5, 40.5, 67.0, 84.0, 100.5)
PALLET, TWISTED, NEW = 4, 9, 7          # индексы реек от -y
JOINT_X = -27.5                         # стык новой составной рейки — над ламелью
SIT_SLAT = 0                            # сидячий край: рейка у -y, середина длины
BENT_NAIL = (-56.0, -22.0)
TUB = (-86.0, -27.0, 12.5)              # кольцо от шайки (только цвет) — вокруг вмятины
CHAR_CORNER = (-111.2, -53.6)           # обугленный угол у изножья (к каменке)
TOWEL_FLAP_X = 44.0                     # хвост полотенца лежит на настиле от x 44 до подушки (59)

# коды материалов в маске id (texture_v2.py)
MAT = {"slat": 1, "pallet": 2, "new": 3, "gap": 4, "nail": 5, "strap": 6, "char": 7, "apron": 8, "patch": 9,
       "tin": 10, "towel": 11, "leaf": 12, "twig": 13, "twine": 14}


class Deck:
    """Раскладка реек и все детали; field(X, Y) -> h и маски."""

    def __init__(self, seed=21):
        rng = np.random.default_rng(seed)
        self.rng = rng
        w = rng.uniform(7.2, 9.6, N_SLATS)
        gaps = rng.uniform(0.35, 0.55, N_SLATS - 1)
        k = (DECK_Y[1] - DECK_Y[0] - gaps.sum()) / w.sum()
        w = w * k
        y = DECK_Y[0]
        self.gc = []          # центры щелей при x = 0, наклон центра, ширина при x=-110 и x=+110
        self.slat_y = []
        for i in range(N_SLATS):
            y0 = y
            y += w[i]
            self.slat_y.append((y0, y))
            if i < N_SLATS - 1:
                g = gaps[i]
                self.gc.append((y + g / 2, rng.uniform(-0.0012, 0.0012),
                                g * rng.uniform(0.6, 1.0), g * rng.uniform(1.0, 1.5)))
                y += g
        # концы реек вразбег
        self.x0 = DECK_X[0] + rng.uniform(-0.3, 0.7, N_SLATS)
        self.x1 = DECK_X[1] + rng.uniform(-0.7, 0.3, N_SLATS)
        # волокна: у каждой рейки своё бревно
        self.grain = []
        for i in range(N_SLATS):
            yc = sum(self.slat_y[i]) / 2
            quarter = rng.random() < 0.3
            self.grain.append(dict(
                quarter=quarter,
                c=yc + rng.uniform(-2.5, 2.5),
                d0=rng.uniform(1.2, 3.5) if not quarter else rng.uniform(14, 20),
                tilt=rng.uniform(0.012, 0.03) * rng.choice((-1, 1)),
                s=rng.uniform(0.85, 1.25),
                amp=rng.uniform(0.09, 0.13),
                seed=int(rng.integers(1000)),
                tone=rng.random(),
                top=rng.uniform(-0.08, 0.08),
            ))
        self.grain[NEW]["amp"] = 0.035
        self.grain[PALLET]["amp"] = 0.08
        self._features(rng)

    # -------------------------------------------------------------- features (позиции — по истории)
    def slat_at(self, y):
        for i, (a, b) in enumerate(self.slat_y):
            if a - 0.3 <= y <= b + 0.3:
                return i
        return None

    def _features(self, rng):
        sy = self.slat_y
        mid = lambda i: (sy[i][0] + sy[i][1]) / 2
        # гвозди: над каждой ламелью; чаще по два, часть пропущена; список (x, y, kind)
        # kind: 0 — обычный, 1 — утоплен с воронкой, 2 — торчит, 3 — светлый новый
        nails = []
        for i in range(N_SLATS):
            for jx in JOISTS:
                if i == NEW:
                    for dy in (-1.8, 1.8):
                        nails.append((jx + rng.uniform(-0.4, 0.4), mid(i) + dy, 3))
                    continue
                if abs(jx - BENT_NAIL[0]) < 1 and sy[i][0] <= BENT_NAIL[1] <= sy[i][1]:
                    continue
                r = rng.random()
                if r < 0.1:
                    continue
                n = 2 if r < 0.82 else 1
                for j in range(n):
                    dy = (j - 0.5) * rng.uniform(3.0, 4.2) if n == 2 else rng.uniform(-1.2, 1.2)
                    kind = 1 if rng.random() < 0.18 else 0
                    nails.append((jx + rng.uniform(-0.8, 0.8), mid(i) + dy, kind))
        # торчащий гвоздь (на него не садятся) и перебитый рядом со старой дыркой
        nails.append((40.5 + 0.3, mid(2) + 1.6, 2))
        self.renail_hole = (84.0 - 0.2, mid(10) - 1.2)
        nails.append((84.0 + 1.9, mid(10) - 0.9, 0))
        self.nails = nails
        # «улыбки»: у части гвоздей дуговая вмятина от промаха молотком
        self.smiles = []
        for (x, y, k) in nails:
            if k != 3 and rng.random() < 0.28:
                a = rng.uniform(0, 2 * np.pi)
                self.smiles.append((x, y, a))
        # сучки: (x, y, радиус, выпал)
        knots = []
        while len(knots) < 9:
            x, y = rng.uniform(-105, 40), rng.uniform(-50, 52)
            i = self.slat_at(y)
            if i is None or i == NEW:
                continue
            if min(abs(x - j) for j in JOISTS) < 4 or abs(x - JOINT_X) < 5:
                continue
            if any(np.hypot(x - a, y - b) < 15 for a, b, *_ in knots):
                continue
            knots.append((x, y, rng.uniform(0.5, 1.4), False))
        knots[3] = (knots[3][0], knots[3][1], 0.8, True)
        self.knots = knots
        # трещины: (x0, x1, y, глубина, полуширина, seed). Торцевые — от концов реек, гуще у изножья
        cracks = []
        for i in range(N_SLATS):
            if i == NEW:
                continue
            a, b = sy[i]
            for _ in range(rng.integers(1, 3)):
                L = rng.uniform(2.5, 9.0)
                y = rng.uniform(a + 1.2, b - 1.2)
                cracks.append((self.x0[i] - 0.5, self.x0[i] + L, y, 0.3, 0.22, int(rng.integers(1000))))
            if rng.random() < 0.45:
                L = rng.uniform(2.0, 5.0)
                y = rng.uniform(a + 1.2, b - 1.2)
                cracks.append((self.x1[i] - L, self.x1[i] + 0.5, y, 0.25, 0.18, int(rng.integers(1000))))
        # продольные трещины усушки в изножной трети
        for _ in range(9):
            i = int(rng.integers(N_SLATS))
            if i == NEW:
                continue
            a, b = sy[i]
            x = rng.uniform(-104, -50)
            L = rng.uniform(5, 20)
            cracks.append((x, x + L, rng.uniform(a + 1.5, b - 1.5), 0.25, 0.17, int(rng.integers(1000))))
        self.cracks = cracks
        # вмятины: (x, y, r, глубина) — гнездом у шайки, редкие по всему настилу
        dents = []
        tx, ty, tr = TUB
        for _ in range(6):
            a = rng.uniform(0, 2 * np.pi)
            rr = tr + rng.uniform(-2.0, 1.5)
            dents.append((tx + rr * np.cos(a), ty + rr * np.sin(a), rng.uniform(0.8, 1.8), rng.uniform(0.05, 0.09)))
        for _ in range(12):
            r = rng.pareto(2.2) * 0.6 + 0.7
            dents.append((rng.uniform(-108, 40), rng.uniform(-52, 54), min(r, 2.2), 0.03 + 0.025 * min(r, 2.2)))
        # сидячий край: мелкие вмятины вдоль -y
        for _ in range(6):
            dents.append((rng.uniform(-50, 30), sy[SIT_SLAT][0] + rng.uniform(1.0, 3.0), rng.uniform(0.6, 1.1), 0.04))
        self.dents = dents
        # царапины от днища шайки: поперёк волокон, около кольца
        scr = []
        for _ in range(5):
            x = tx + rng.uniform(-10, 12)
            y = ty + rng.uniform(-12, 10)
            ang = np.pi / 2 + rng.uniform(-0.45, 0.45)
            L = rng.uniform(5, 14)
            scr.append((x, y, ang, L, rng.uniform(0.025, 0.04)))
        self.scratches = scr
        # забоины на кромках досок: гуще у изножья и на сидячем крае (x, y кромки, r, глубина)
        nicks = []
        for _ in range(70):
            i = int(rng.integers(N_SLATS))
            side = int(rng.integers(2))
            x = rng.uniform(-110, 108)
            if rng.random() < 0.5:
                x = rng.uniform(-110, -60)
            y = sy[i][side]
            nicks.append((x, y, rng.uniform(0.35, 1.1), rng.uniform(0.07, 0.16)))
        for _ in range(12):
            nicks.append((rng.uniform(-60, 35), sy[SIT_SLAT][0], rng.uniform(0.5, 1.2), rng.uniform(0.1, 0.2)))
        self.nicks = nicks
        # отщеп на углу рейки у изножья и поднятая щепа
        self.chip = (2, -1)           # рейка 2, конец у -x
        i = 10
        self.splinter = (-79.0, sy[i][0] + 2.2, 2.6, 0.35)   # x, y, длина, ширина
        # старые дыры доски от поддона: 4 группы по 3 (шаг стрингеров поддона)
        yc = mid(PALLET)
        self.pallet_holes = [(hx + 0.7 * (k - 1) + rng.uniform(-0.4, 0.4), yc + dy)
                             for hx in (-92.0, -31.0, 30.0, 88.0) for k, dy in enumerate((-2.6, 0.0, 2.6))]
        self.pallet_holes.append(self.renail_hole)

    # -------------------------------------------------------------- field
    def field(self, X, Y):
        """X, Y — сетка (см). Возвращает dict: h (см), маски 0..1 и коды."""
        H = np.zeros_like(X)
        out = {}
        sy = self.slat_y
        # ---- какая рейка, расстояние до кромок
        idx = np.zeros(X.shape, np.int64)
        for (g0, s, wa, wb) in self.gc:
            idx += (Y > g0 + s * X)
        lo = np.full(X.shape, -1e9)
        hi = np.full(X.shape, 1e9)
        gw = lambda wa, wb: wa + (wb - wa) * (X - DECK_X[0]) / (DECK_X[1] - DECK_X[0])
        for k, (g0, s, wa, wb) in enumerate(self.gc):
            c = g0 + s * X
            w = gw(wa, wb)
            lo = np.where(idx == k + 1, c + w / 2, lo)
            hi = np.where(idx == k, c - w / 2, hi)
        lo = np.where(idx == 0, DECK_Y[0], lo)
        hi = np.where(idx == N_SLATS - 1, DECK_Y[1], hi)
        x0 = np.asarray(self.x0)[idx]
        x1 = np.asarray(self.x1)[idx]
        dy_lo, dy_hi = Y - lo, hi - Y
        # стык новой рейки
        joint = (idx == NEW)
        dx_lo = np.where(joint & (X > JOINT_X), X - (JOINT_X + 0.12), X - x0)
        dx_hi = np.where(joint & (X <= JOINT_X), (JOINT_X - 0.12) - X, x1 - X)
        inside = (dy_lo > 0) & (dy_hi > 0) & (dx_lo > 0) & (dx_hi > 0)
        dside = np.minimum(dy_lo, dy_hi)
        dend = np.minimum(dx_lo, dx_hi)

        # ---- зоны по истории
        lie = sstep(0, 1, (1 - np.abs((X + 5) / 72) ** 2.5)) * sstep(0, 1, 1 - np.abs(Y / 38) ** 3)
        lie = np.clip(lie * (0.85 + 0.3 * fbm2(X * 0.05, Y * 0.05, 211, 2)), 0, 1)
        foot = sstep(-60, -108, X)
        out["lie"], out["foot"] = lie, foot

        # ---- фаски: скругление радиусом r (у новой — острее, в зоне лежания и на сидячем крае — круглее)
        r_side = 0.32 + 0.25 * lie + 0.1 * foot
        r_side = np.where(idx == NEW, 0.18, r_side)
        sit = (idx == SIT_SLAT) & (dy_lo < dy_hi)
        r_side = np.where(sit, r_side + 0.85 * sstep(-75, -40, X) * sstep(45, 15, X), r_side)
        # внешние рейки следуют плечу матраса
        outer = ((idx == 0) & (dy_lo < dy_hi)) | ((idx == N_SLATS - 1) & (dy_hi < dy_lo))
        r_side = np.where(outer & ~sit, 1.3, r_side)
        r_end = np.where(idx == NEW, 0.2, 0.45 + 0.3 * foot)
        def round_drop(d, r):
            t = np.clip(r - d, 0, None)
            t = np.minimum(t, r)
            return r - np.sqrt(np.maximum(r * r - t * t, 0))
        drop = np.maximum(round_drop(dside, r_side), round_drop(dend, r_end))
        H -= drop * np.where(outer & (dside < r_side), 1.25, 1.0)

        # ---- доска: уровень, чашка, волны, перекос
        top = np.asarray([g["top"] for g in self.grain])[idx]
        wdt = np.maximum(hi - lo, 1.0)
        cu = ((Y - (lo + hi) / 2) / (wdt / 2))
        H += top - 0.05 * (1 - np.clip(cu, -1, 1) ** 2)
        H += 0.05 * (n2(X * 0.04, Y * 0.3 + idx * 13.0, 31) - 0.5)
        # следы рубанка: пологие лунки поперёк 3-6 см (ручная строжка)
        H += 0.025 * (n2(X * 0.25, Y * 0.06 + idx * 7.0, 37) - 0.5) * (1 - 0.5 * lie)
        H += np.where(idx == TWISTED, 0.25 * (X / 110.0) * np.clip(cu, -1, 1), 0)

        # ---- волокна
        g_ridge = np.zeros_like(X)
        amp = np.zeros_like(X)
        for i, g in enumerate(self.grain):
            m = idx == i
            if not m.any():
                continue
            xs, ys = X[m], Y[m]
            warp = 0.45 * (fbm2(xs * 0.025, ys * 0.12, g["seed"], 3) - 0.5) + 0.12 * (n2(xs * 0.12, ys * 0.5, g["seed"] + 3) - 0.5)
            if g["quarter"]:
                ph = (ys - g["c"]) / (g["s"] * 0.8) + 2.5 * warp
            else:
                d = g["d0"] + g["tilt"] * xs + 0.6 * warp
                ph = np.sqrt((ys - g["c"]) ** 2 + d * d) / g["s"] + warp
            # сучки: волокна огибают
            for (kx, ky, kr, _) in self.knots:
                dd = np.hypot((xs - kx) / 1.5, ys - ky)
                ph = ph + 1.6 * kr * np.exp(-(dd / (2.4 * kr)) ** 2) / g["s"]
            f = ph - np.floor(ph)
            ridge = np.exp(-((f - 0.82) / 0.11) ** 2) + np.exp(-((f + 1 - 0.82) / 0.11) ** 2) + np.exp(-((f - 1.82) / 0.11) ** 2)
            g_ridge[m] = ridge
            amp[m] = g["amp"]
        wear = 1.0 - 0.6 * lie + 0.35 * foot
        wear = np.where(idx == NEW, 0.5, wear)
        H += amp * wear * (g_ridge - 0.35)
        out["grain"] = g_ridge

        # ---- доска от поддона: дуги циркулярной пилы
        pal = idx == PALLET
        if pal.any():
            yc = (sy[PALLET][0] + sy[PALLET][1]) / 2
            R = 34.0
            xp = X - (R - np.sqrt(np.maximum(R * R - (Y - yc - 20) ** 2, 0)))
            ph = xp / 1.6 + 1.2 * fbm2(X * 0.04, Y * 0.1, 77, 2)
            saw = np.abs(np.sin(ph * np.pi)) ** 3 * (0.5 + 0.5 * n2(X * 0.3, Y * 0.3, 79))
            H += np.where(pal, -0.014 * saw * (1 - 0.6 * lie), 0)

        cav = np.zeros_like(X)          # полости (щели, трещины, дыры): 0..1
        dent_m = np.zeros_like(X)
        scr_m = np.zeros_like(X)

        # ---- сучки
        knot_m = np.zeros_like(X)
        for (kx, ky, kr, fallen) in self.knots:
            dd = np.hypot((X - kx) / 1.35, Y - ky)
            core = sstep(kr, kr * 0.8, dd)
            ring = np.exp(-((dd - kr) / 0.12) ** 2)
            if fallen:
                H -= 0.9 * sstep(kr * 0.95, kr * 0.75, dd)
                cav = np.maximum(cav, sstep(kr * 0.95, kr * 0.7, dd))
            else:
                H += 0.07 * core - 0.05 * ring
                ang = np.arctan2(Y - ky, X - kx)
                for a0 in (0.4 + kx, 2.5 + ky, 4.3 + kx * 0.3):
                    da = np.abs(np.angle(np.exp(1j * (ang - a0))))
                    tt = dd * da
                    rad = (tt < 0.14) & (dd < kr * 0.85)
                    H -= np.where(rad, 0.12 * (1 - tt / 0.14), 0)
            knot_m = np.maximum(knot_m, core)
        out["knot"] = knot_m

        # ---- трещины (вдоль волокон, клин с мягкими концами, извилистые)
        for (xa, xb, yc0, dep, hw, sd) in self.cracks:
            box = (X > xa - 1) & (X < xb + 1) & (np.abs(Y - yc0) < 2)
            if not box.any():
                continue
            xs, ys = X[box], Y[box]
            t = np.clip((xs - xa) / (xb - xa), 0, 1)
            yc = yc0 + 0.35 * (n2(xs * 0.18, sd * 1.0, sd) - 0.5) + 0.08 * (n2(xs * 0.9, sd * 2.0, sd + 1) - 0.5)
            prof = np.sin(np.pi * t) ** 0.6
            if xa < -100:          # торцевая трещина у изножья: шире у торца
                prof = (1 - t) ** 0.6
            elif xb > 100:         # у изголовья
                prof = t ** 0.6
            w = hw * prof + 1e-3
            v = np.clip(1 - np.abs(ys - yc) / w, 0, 1)
            H[box] -= dep * prof * v ** 0.8
            cav[box] = np.maximum(cav[box], v * prof)

        # ---- вмятины (чаша без ободка)
        for (x, y, r, d) in self.dents:
            dd = np.hypot(X - x, Y - y)
            u = np.clip(1 - (dd / r) ** 2, 0, 1) ** 2
            H -= d * u
            dent_m = np.maximum(dent_m, u)
        # ---- царапины поперёк волокон
        for (x, y, ang, L, d) in self.scratches:
            ca, sa = np.cos(ang), np.sin(ang)
            u = (X - x) * ca + (Y - y) * sa
            v = -(X - x) * sa + (Y - y) * ca
            t = np.clip(u / L, 0, 1)
            within = (u > 0) & (u < L)
            prof = np.sin(np.pi * t) ** 0.5
            g = np.clip(1 - np.abs(v) / 0.13, 0, 1) * within * prof
            H -= d * g
            scr_m = np.maximum(scr_m, g)

        # ---- забоины кромок (вырез с неровным дном)
        for (x, y, r, d) in self.nicks:
            box = (np.abs(X - x) < r * 1.6 + 0.2) & (np.abs(Y - y) < r + 0.2)
            if not box.any():
                continue
            dd = np.hypot((X[box] - x) / 1.5, Y[box] - y)
            u = np.clip(1 - (dd / r) ** 2, 0, 1)
            H[box] -= d * u * (0.7 + 0.6 * n2(X[box] * 3, Y[box] * 3, 17))
            dent_m[box] = np.maximum(dent_m[box], u)

        # ---- старые дыры от гвоздей (доска поддона, перебитый гвоздь)
        for (x, y) in self.pallet_holes:
            dd = np.hypot(X - x, Y - y)
            H -= 0.06 * np.clip(1 - (dd / 0.6) ** 2, 0, 1) + 0.6 * sstep(0.26, 0.18, dd)
            cav = np.maximum(cav, sstep(0.28, 0.18, dd))

        # ---- отщеп на углу рейки (клин) и поднятая щепа
        ci, cend = self.chip
        cx = self.x0[ci] if cend < 0 else self.x1[ci]
        cy = sy[ci][1]
        u, v = (X - cx) * (-cend), cy - Y               # от торца внутрь, от кромки внутрь
        wedge = (idx == ci) & (u > -0.5) & (v > -0.5) & (u / 3.2 + v / 1.6 < 1)
        H = np.where(wedge, np.minimum(H, -0.35 - 0.25 * (1 - (u / 3.2 + v / 1.6)) + 0.05 * (n2(X * 3, Y * 3, 5) - 0.5)), H)
        sx, syy, sl, sw = self.splinter
        u, v = X - sx, Y - syy
        sp = np.clip(1 - np.abs(v) / (sw / 2), 0, 1) * sstep(0, 0.5, u) * sstep(sl, sl - 0.3, u)
        H += 0.12 * sp * np.clip(u / sl, 0, 1)
        cut = np.exp(-((np.abs(v) - sw / 2) / 0.05) ** 2) * (u > 0) * (u < sl)
        H -= 0.06 * cut

        # ---- гвозди: кованая шляпка (скруглённый квадрат), утопленные — с воронкой
        nail_m = np.zeros_like(X)
        for (x, y, kind) in self.nails:
            box = (np.abs(X - x) < 2.2) & (np.abs(Y - y) < 2.2)
            if not box.any():
                continue
            xs, ys = X[box] - x, Y[box] - y
            a = (x * 7.3 + y * 3.1) % 1.57
            ca, sa = np.cos(a), np.sin(a)
            u, v = xs * ca + ys * sa, -xs * sa + ys * ca
            r = 0.55 if kind != 3 else 0.5
            q = ((np.abs(u) / r) ** 4 + (np.abs(v) / r) ** 4) ** 0.25
            head = np.clip(1 - q, 0, 1)
            dome = np.sqrt(np.clip(1 - q ** 2, 0, 1))
            lift = {0: 0.03, 1: -0.06, 2: 0.22, 3: 0.04}[kind]
            hh = lift + 0.09 * dome - 0.02 * np.maximum(np.abs(u), np.abs(v)) / r
            dd = np.hypot(xs, ys)
            if kind == 1:   # воронка от добойника
                H[box] -= 0.09 * np.clip(1 - (dd / 1.1) ** 2, 0, 1) ** 2
            # смятое дерево вокруг шляпки
            H[box] -= 0.025 * np.clip(1 - ((dd - 0.75) / 0.35) ** 2, 0, 1)
            inside_h = q < 1
            hb = H[box]
            H[box] = np.where(inside_h, np.maximum(hb, hh), hb)
            nail_m[box] = np.maximum(nail_m[box], sstep(1.02, 0.92, q))
        # загнутый гвоздь: шляпка и стержень, лежащий на доске
        bx, by = BENT_NAIL
        u, v = X - (bx - 2.6), Y - by
        dd = np.hypot(u, v)
        bent = sstep(0.55, 0.45, dd) * 0.25
        shank = np.clip(1 - (np.abs(v) / 0.2) ** 2, 0, 1) ** 0.5 * (u > 0) * (u < 2.9)
        H = np.maximum(H, np.where(dd < 0.55, 0.05 + bent, -10))
        H = np.maximum(H, np.where(shank > 0, 0.02 + 0.18 * shank + 0.04 * u / 2.9, -10))
        nail_m = np.maximum(nail_m, np.maximum(sstep(0.55, 0.45, dd), (shank > 0.05) * 1.0))

        # ---- «улыбки» молотка: дуга радиусом 1.2 см, промах по краю бойка
        for (x, y, a) in self.smiles:
            cx, cy = x + 1.0 * np.cos(a), y + 1.0 * np.sin(a)
            dd = np.hypot(X - cx, Y - cy)
            ang = np.arctan2(Y - cy, X - cx)
            win = np.clip(np.cos(ang - a) * 1.6 - 0.2, 0, 1)
            sm = np.exp(-((dd - 1.15) / 0.13) ** 2) * win
            H -= 0.045 * sm
            dent_m = np.maximum(dent_m, sm)

        # ---- стальная пластина на стыке новой рейки (4 × 6 см, 1.5 мм) на четырёх гвоздиках
        # (узкая скоба 5 × 2 вместе с линией стыка читалась крестом)
        yc = (sy[NEW][0] + sy[NEW][1]) / 2
        u, v = X - JOINT_X, Y - yc
        q = np.maximum(np.abs(u) / 2.0, np.abs(v) / 3.0)
        strap = sstep(1.0, 0.94, q)
        strap_h = 0.15 * strap + 0.02 * (n2(X * 2, Y * 2, 91) - 0.5) * strap
        H = np.where(strap > 0.02, np.maximum(H, strap_h + 0.0), H)
        for sx2, sy2 in ((-1.3, -2.1), (1.3, -2.1), (-1.3, 2.1), (1.3, 2.1)):
            dd = np.hypot(u - sx2, v - sy2)
            H = np.where(dd < 0.38, np.maximum(H, 0.15 + 0.08 * np.sqrt(np.clip(1 - (dd / 0.38) ** 2, 0, 1))), H)
            nail_m = np.maximum(nail_m, sstep(0.4, 0.32, dd))
        out["strap"] = strap

        # ---- обугленный угол у изножья: «крокодилова кожа»
        cx, cy = CHAR_CORNER
        rr = np.hypot((X - cx) / 1.15, Y - cy) + 4.0 * (fbm2(X * 0.12, Y * 0.12, 301, 3) - 0.5)
        char = sstep(17.0, 11.0, rr)
        if (char > 0).any():
            m = char > 0
            f1, f2 = _voronoi(X[m], Y[m], 1.5, 303)
            edge = f2 - f1
            crackv = sstep(0.16, 0.04, edge)
            cell = np.clip(1 - f1 / 1.2, 0, 1)
            hc = -0.08 + 0.04 * cell - 0.22 * crackv
            H[m] = H[m] * (1 - char[m] * 0.6) + char[m] * hc
            cav[m] = np.maximum(cav[m], crackv * char[m])
        out["char"] = char

        # ---- щели: ниже всего
        H = np.where(inside, H, GAP_FLOOR)
        cav = np.where(inside, cav, 1.0)
        out["h"] = H
        out["cavity"] = cav
        out["dent"] = np.maximum(dent_m, scr_m * 0.0)
        out["scratch"] = scr_m
        out["nail"] = nail_m * inside
        out["slat"] = idx
        out["inside"] = inside
        tone = np.asarray([g["tone"] for g in self.grain])[idx]
        out["tone"] = tone
        mat = np.full(X.shape, MAT["slat"])
        mat = np.where(idx == PALLET, MAT["pallet"], mat)
        mat = np.where(idx == NEW, MAT["new"], mat)
        mat = np.where(char > 0.5, MAT["char"], mat)
        mat = np.where(strap > 0.5, MAT["strap"], mat)
        mat = np.where(out["nail"] > 0.5, MAT["nail"], mat)
        mat = np.where(inside, mat, MAT["gap"])
        out["mat"] = mat
        return out


# ------------------------------------------------------------------ фартук и жестяные уголки
# стороны: 0 — бок y-, 1 — бок y+, 2 — торец изножья x-, 3 — торец изголовья x+
# a — координата вдоль стороны (x для боков, y для торцов), z — высота; h — сдвиг наружу от бока матраса (см)
CORNER_R = 10.5
CORNERS = {(-1, -1): (-101.2, -43.6), (-1, 1): (-101.2, 45.4), (1, -1): (100.1, -43.6), (1, 1): (100.1, 45.4)}
TIN_TH = {(1, 1): (-20, 110), (-1, 1): (70, 200), (-1, -1): (160, 290), (1, -1): (250, 380)}   # градусы
SIDE_A = {0: (-99.0, 98.0), 1: (-99.0, 98.0), 2: (-42.0, 43.5), 3: (-42.0, 43.5)}   # концы досок уходят под жесть
APRON_Z = ((37.7, 46.2), (46.5, 55.0))
APRON_OFF = 0.3


def round_drop(d, r):
    t = np.clip(r - d, 0, None)
    t = np.minimum(t, r)
    return r - np.sqrt(np.maximum(r * r - t * t, 0))


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
    """Кованая шляпка (скруглённый квадрат) в локальных координатах U, V; возвращает новую H и маску."""
    q = ((np.abs(U) / r) ** 4 + (np.abs(V) / r) ** 4) ** 0.25
    dome = np.sqrt(np.clip(1 - q ** 2, 0, 1))
    lift = {0: 0.03, 1: -0.06, 2: 0.22, 3: 0.04}[kind]
    hh = base + lift + 0.09 * dome - 0.02 * np.maximum(np.abs(U), np.abs(V)) / r
    dd = np.hypot(U, V)
    H = H - 0.025 * np.clip(1 - ((dd - 0.75) / 0.35) ** 2, 0, 1)
    if kind == 1:
        H = H - 0.09 * np.clip(1 - (dd / 1.1) ** 2, 0, 1) ** 2
    H = np.where(q < 1, np.maximum(H, hh), H)
    return H, sstep(1.02, 0.92, q)


class Apron:
    def __init__(self, seed=33):
        rng = np.random.default_rng(seed)
        self.boards = {}
        for side in range(4):
            for row in range(2):
                self.boards[(side, row)] = dict(
                    seed=int(rng.integers(1000)), d0=rng.uniform(1.2, 3.0),
                    tilt=rng.uniform(0.01, 0.025) * rng.choice((-1, 1)), c=rng.uniform(-2, 2), s=rng.uniform(0.85, 1.2),
                    amp=rng.uniform(0.09, 0.12), tone=rng.random(), quarter=rng.random() < 0.25,
                    top=rng.uniform(-0.06, 0.06))
        # заплата: бок y-, нижний ряд, обрезок другой доски
        self.patch = (0, 0, -33.0, -7.0)
        self.patch_b = dict(seed=777, d0=2.0, tilt=0.02, c=0.5, s=0.9, amp=0.1, tone=0.95, quarter=False, top=0.1)
        # гвозди: пара по высоте на каждой доске через ~45 см
        self.nails = []
        for side in range(4):
            a0, a1 = SIDE_A[side]
            n = 5 if side < 2 else 3
            for j in range(n):
                a = a0 + 6 + (a1 - a0 - 12) * j / (n - 1) + rng.uniform(-2.5, 2.5)
                for row, (z0, z1) in enumerate(APRON_Z):
                    zc = (z0 + z1) / 2
                    for dz in (-2.2, 2.2):
                        if rng.random() < 0.12:
                            continue
                        self.nails.append((side, a + rng.uniform(-0.6, 0.6), zc + dz + rng.uniform(-0.4, 0.4),
                                           1 if rng.random() < 0.2 else 0))
        ps, prow, pa0, pa1 = self.patch
        for a in (pa0 + 2.0, pa1 - 2.0):
            for dz in (-2.2, 2.2):
                self.nails.append((ps, a, (APRON_Z[0][0] + APRON_Z[0][1]) / 2 + dz, 0))
        self.knots = {}
        for key in self.boards:
            side, row = key
            a0, a1 = SIDE_A[side]
            z0, z1 = APRON_Z[row]
            self.knots[key] = [(rng.uniform(a0 + 10, a1 - 10), rng.uniform(z0 + 2, z1 - 2), rng.uniform(0.5, 1.1))
                               for _ in range(int(rng.integers(0, 3)))]
        self.cracks = []
        for side in range(4):
            a0, a1 = SIDE_A[side]
            for _ in range(10 if side < 2 else 6):
                a = rng.uniform(a0, a0 + 45) if (side < 2 and rng.random() < 0.6) else rng.uniform(a0, a1)
                row = int(rng.integers(2))
                z0, z1 = APRON_Z[row]
                self.cracks.append((side, a, a + rng.uniform(4, 16), rng.uniform(z0 + 1.2, z1 - 1.2),
                                    rng.uniform(0.2, 0.3), rng.uniform(0.15, 0.22), int(rng.integers(1000))))
        self.dents = []
        for side in range(4):
            a0, a1 = SIDE_A[side]
            for _ in range(10):
                self.dents.append((side, rng.uniform(a0, a1), rng.uniform(38.5, 54), rng.uniform(0.5, 1.6),
                                   rng.uniform(0.04, 0.1)))

    def field(self, side, A, Z):
        a0, a1 = SIDE_A[side]
        row = (Z >= APRON_Z[1][0] - 0.15).astype(np.int64)
        # нижняя кромка нижней доски размочалена: неровная линия
        zb = APRON_Z[0][0] + 0.25 + 0.35 * fbm2(A * 0.3, A * 0 + side * 5.0, 401 + side, 3)
        z_lo = np.where(row == 0, zb, APRON_Z[1][0])
        z_hi = np.where(row == 0, APRON_Z[0][1], APRON_Z[1][1])
        dz = np.minimum(Z - z_lo, z_hi - Z)
        da = np.minimum(A - a0, a1 - A)
        ps, prow, pa0, pa1 = self.patch
        prow_m = (side == ps) & (row == prow)
        in_patch = prow_m & (A > pa0) & (A < pa1)
        da = np.where(in_patch, np.minimum(A - pa0 - 0.12, pa1 - 0.12 - A), da)
        da = np.where(prow_m & ~in_patch, np.minimum(da, np.where(A <= pa0, pa0 - 0.12 - A, A - pa1 - 0.12)), da)
        inside = (dz > 0) & (da > 0)
        bottom_edge = (row == 0) & (Z - z_lo < z_hi - Z)
        r_edge = np.where(bottom_edge, 0.6, 0.35)
        H = APRON_OFF - np.maximum(round_drop(dz, r_edge), round_drop(da, 0.35))
        grain = np.zeros_like(A)
        tone = np.zeros_like(A)
        for r in (0, 1):
            for patch in (False, True):
                m = (row == r) & (in_patch == patch)
                if not m.any():
                    continue
                b = self.patch_b if patch else self.boards[(side, r)]
                zc = (APRON_Z[r][0] + APRON_Z[r][1]) / 2
                kn = [] if patch else [(ka, kz - zc, kr) for ka, kz, kr in self.knots[(side, r)]]
                g = grain_relief(A[m], Z[m] - zc, b["d0"], b["tilt"], b["c"], b["s"], b["seed"], kn, b["quarter"])
                grain[m] = g
                tone[m] = b["tone"]
                wear = 1.0 + 0.4 * sstep(a0 + 40, a0, A[m]) * (side < 2) + 0.4 * (side == 2)
                H[m] += b["amp"] * wear * (g - 0.35) + b["top"] + (0.15 if patch else 0)
                H[m] += 0.04 * (n2(A[m] * 0.05, Z[m] * 0.3 + r * 9 + side * 3, 411) - 0.5)
        fr = sstep(1.2, 0.0, Z - z_lo) * (row == 0)          # размочаленный низ
        H -= fr * (0.15 + 0.25 * n2(A * 0.4, Z * 3.0, 421)) * (0.6 + 0.8 * n2(A * 2.5, Z * 0.5, 423))
        cav = np.zeros_like(A)
        knot_m = np.zeros_like(A)
        for r in (0, 1):
            for (ka, kz, kr) in self.knots[(side, r)]:
                dd = np.hypot((A - ka) / 1.35, Z - kz)
                core = sstep(kr, kr * 0.8, dd) * (row == r)
                H += 0.07 * core - 0.05 * np.exp(-((dd - kr) / 0.12) ** 2) * (row == r)
                knot_m = np.maximum(knot_m, core)
        for (sd, xa, xb, zc0, dep, hw, seed) in self.cracks:
            if sd != side:
                continue
            box = (A > xa - 1) & (A < xb + 1) & (np.abs(Z - zc0) < 2)
            if not box.any():
                continue
            t = np.clip((A[box] - xa) / (xb - xa), 0, 1)
            zc = zc0 + 0.35 * (n2(A[box] * 0.18, seed, seed) - 0.5)
            prof = np.sin(np.pi * t) ** 0.6
            v = np.clip(1 - np.abs(Z[box] - zc) / (hw * prof + 1e-3), 0, 1)
            H[box] -= dep * prof * v ** 0.8
            cav[box] = np.maximum(cav[box], v * prof)
        dent_m = np.zeros_like(A)
        for (sd, a, z, r, d) in self.dents:
            if sd != side:
                continue
            u = np.clip(1 - ((A - a) ** 2 + (Z - z) ** 2) / r ** 2, 0, 1) ** 2
            H -= d * u
            dent_m = np.maximum(dent_m, u)
        nail_m = np.zeros_like(A)
        for (sd, a, z, kind) in self.nails:
            if sd != side:
                continue
            box = (np.abs(A - a) < 2) & (np.abs(Z - z) < 2)
            if not box.any():
                continue
            hb, nm = nail_head(H[box], A[box] - a, Z[box] - z, APRON_OFF, kind)
            H[box] = hb
            nail_m[box] = np.maximum(nail_m[box], nm)
        # обугливание у угла изножья (бок y- и торец x-)
        char = np.zeros_like(A)
        if side in (0, 2):
            corner_a = -99.0 if side == 0 else -42.0
            rr = np.hypot((A - corner_a) / 1.2, (Z - 52.0) * 0.8) + 4.0 * (fbm2(A * 0.12, Z * 0.12, 305 + side, 3) - 0.5)
            char = sstep(15.0, 9.0, rr)
        if (char > 0).any():
            m = char > 0
            f1, f2 = _voronoi(A[m], Z[m], 1.5, 307 + side)
            crackv = sstep(0.16, 0.04, f2 - f1)
            hc = APRON_OFF - 0.08 + 0.04 * np.clip(1 - f1 / 1.2, 0, 1) - 0.22 * crackv
            H[m] = H[m] * (1 - char[m] * 0.6) + char[m] * hc
            cav[m] = np.maximum(cav[m], crackv * char[m])
        H = np.where(inside, H, -0.6)
        cav = np.where(inside, cav, 1.0)
        mat = np.where(in_patch, MAT["patch"], MAT["apron"])
        mat = np.where(char > 0.5, MAT["char"], mat)
        mat = np.where(nail_m > 0.5, MAT["nail"], mat)
        mat = np.where(inside, mat, MAT["gap"])
        return dict(h=H, grain=grain, cavity=cav, dent=dent_m, nail=nail_m * inside, knot=knot_m, char=char,
                    tone=tone, mat=mat)


def tin_field(corner, TH, Z):
    """Жестяной уголок на скруглённом углу: TH — угол вокруг центра скругления (рад), Z — высота; h — наружу, см."""
    sx, sy = corner
    rng = np.random.default_rng(101 + 3 * (sx + 1) + (sy + 1))
    th0, th1 = TH.min(), TH.max()
    arc = (TH - th0) * CORNER_R
    L = (th1 - th0) * CORNER_R
    zt = 54.6 + 0.25 * (n2(arc * 0.2, arc * 0 + sx * 3 + sy, 501) - 0.5)
    zb = 38.4 + 0.3 * (n2(arc * 0.2, arc * 0 + sx * 5 + sy, 503) - 0.5)
    inside = (Z > zb) & (Z < zt) & (arc > 0.2) & (arc < L - 0.2)
    H = np.full_like(TH, 0.45)
    d_edge = np.minimum(arc, L - arc)
    H += 0.12 * np.exp(-((d_edge - 0.45) / 0.3) ** 2)          # подогнутые кромки
    dzt = np.minimum(Z - zb, zt - Z)
    H += 0.08 * np.exp(-((dzt - 0.35) / 0.25) ** 2)
    H += 0.06 * (fbm2(arc * 0.15, Z * 0.15, 505 + sx + 3 * sy, 3) - 0.5)   # волны листа
    dent_m = np.zeros_like(TH)
    for _ in range(5):
        a, z, r, d = rng.uniform(2, L - 2), rng.uniform(40, 53), rng.uniform(0.8, 2.2), rng.uniform(0.08, 0.18)
        u = np.clip(1 - ((arc - a) ** 2 + (Z - z) ** 2) / r ** 2, 0, 1) ** 2
        H -= d * u
        dent_m = np.maximum(dent_m, u)
    nail_m = np.zeros_like(TH)
    for ae in (1.2, L - 1.2):
        for z in np.linspace(40.0, 53.0, 4):
            dd = np.hypot(arc - ae, Z - z - rng.uniform(-0.6, 0.6))
            dome = np.sqrt(np.clip(1 - (dd / 0.42) ** 2, 0, 1))
            H -= 0.04 * np.clip(1 - ((dd - 0.6) / 0.3) ** 2, 0, 1)    # лист продавлен вокруг гвоздя
            H = np.where(dd < 0.42, np.maximum(H, 0.5 + 0.08 * dome), H)
            nail_m = np.maximum(nail_m, sstep(0.45, 0.36, dd))
    H = np.where(inside, H, -0.6)
    mat = np.where(nail_m > 0.5, MAT["nail"], MAT["tin"])
    mat = np.where(inside, mat, MAT["gap"])
    z0 = np.zeros_like(TH)
    return dict(h=H, grain=z0, cavity=np.where(inside, 0.0, 1.0), dent=dent_m, nail=nail_m, knot=z0, char=z0,
                tone=z0 + 0.5, mat=mat)


# ------------------------------------------------------------------ полотенце (подушка #1) и его хвост на настиле
ROLL_C = (69.5, 59.6)          # центр валика в плоскости xz
ROLL_PITCH = 1.7               # шаг витка спирали (толщина слоя с зазором), см: на торцах 3.9 px/см -> ~6.5 px
FOLD_X = 74.5                  # складка между валиком и стопкой
STACK_PITCH = 2.3              # шаг слоёв стопки по высоте
STACK_Z0 = 54.2
HEAD = (88.0, 1.0, 13.0, 1.1)  # вмятина от головы: x, y, радиус, глубина
STRIPES = ((38.8, 1.7), (35.6, 0.5))   # |y| центра и полуширина кирпичных полос (как v1.2)
TOWEL_END = 44.5               # |y| края полотенца (примерно; торцы подушки)


def towel_disp(P, N, y_end):
    """Сдвиг по нормали (см) и маски для точек подушки. P, N: (n, 3); y_end: |y| торца у этой точки."""
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    nx, ny, nz = N[:, 0], N[:, 1], N[:, 2]
    n = len(x)
    d = np.zeros(n)
    cav = np.zeros(n)
    stitch = np.zeros(n)
    end_w = sstep(0.45, 0.75, np.abs(ny))              # торцы
    roll = x < FOLD_X + 0.5
    # ---- торцы: сечение слоёв
    cx, cz = ROLL_C
    r = np.hypot(x - cx, (z - cz) * 1.08)
    th = np.arctan2(z - cz, x - cx) / (2 * np.pi)
    f = ((r - 0.5 - ROLL_PITCH * th) / ROLL_PITCH) % 1.0
    lay_roll = np.sqrt(np.clip(1 - (2 * f - 1) ** 2, 0, 1))          # каждый виток — скруглённый край слоя
    g_roll = np.exp(-((np.minimum(f, 1 - f)) / 0.1) ** 2)            # щель между витками
    k = np.floor((z - STACK_Z0) / STACK_PITCH)
    fz = ((z - STACK_Z0) / STACK_PITCH) % 1.0
    lay_st = np.sqrt(np.clip(1 - (2 * fz - 1) ** 2, 0, 1))
    g_st = np.exp(-((np.minimum(fz, 1 - fz)) / 0.09) ** 2)
    # слои стопки не вровень: каждый сдвинут по y на свои ±0.6 см, концы чуть волной
    off = 0.6 * (np.sin(k * 2.3 + 1.0) * 0.8 + 0.2 * np.sin(k * 5.1))
    d_end = np.where(roll & (r < 7.2), 0.45 * lay_roll - 0.55 * g_roll,
                     0.4 * lay_st - 0.5 * g_st + off * sstep(FOLD_X, FOLD_X + 3, x))
    cav_end = np.where(roll & (r < 7.2), g_roll, g_st)
    d += end_w * d_end
    cav = np.maximum(cav, end_w * cav_end)
    # ---- зад (к спинке): петли сгибов стопки
    back_w = sstep(0.45, 0.75, nx)
    d += back_w * (0.45 * lay_st - 0.55 * g_st)
    cav = np.maximum(cav, back_w * g_st)
    # ---- верх и перед: валик, складка, вмятина, складки сжатия, жатость
    top_w = np.clip(1 - end_w - back_w, 0, 1)
    fold = np.exp(-((x - FOLD_X) / 1.7) ** 2) * sstep(0.2, 0.6, nz)
    d -= 2.6 * fold * top_w
    cav = np.maximum(cav, fold * top_w * 0.8)
    d += 0.6 * np.exp(-((x - 68.5) / 4.0) ** 2) * sstep(0.1, 0.5, nz) * top_w        # валик круглее
    # край последнего витка на валике спереди-снизу (уступ ткани)
    lip_th = np.arctan2(z - cz, x - cx)
    lip = sstep(-2.2, -2.05, lip_th) * sstep(-1.2, -1.35, lip_th)
    d += 0.35 * lip * roll * top_w
    hx, hy, hr, hd = HEAD
    dh = np.hypot((x - hx) / 1.15, y - hy)
    dent = np.clip(1 - (dh / hr) ** 2, 0, 1) ** 2 * sstep(0.3, 0.7, nz)
    d -= hd * dent * top_w
    ang = np.arctan2(y - hy, x - hx)
    rays = np.clip(np.sin(ang * 7 + 0.8 * np.sin(ang * 3)), 0, 1) ** 3
    ring = np.exp(-((dh - hr * 1.05) / (hr * 0.35)) ** 2)
    d += 0.3 * rays * ring * top_w * (x > FOLD_X + 2)                                # складки вокруг вмятины
    # складки сжатия: длинные мягкие гребни, извилистые
    for (a0, b0, w, amp, s) in ((0.35, 20.0, 1.4, 0.35, 1), (-0.5, -18.0, 1.2, 0.3, 2), (1.3, 5.0, 1.8, 0.28, 3),
                                (0.1, 30.0, 1.0, 0.25, 4), (-1.2, -32.0, 1.3, 0.3, 5)):
        u = (y - b0) * np.cos(a0) - (x - 86) * np.sin(a0) + 2.0 * (n2(x * 0.08, y * 0.08, 600 + s) - 0.5)
        d += amp * np.exp(-(u / w) ** 2) * top_w * (x > FOLD_X + 1.5) * sstep(0.3, 0.6, nz)
    # складки на валике вдоль него (ткань собрана)
    d += 0.18 * (np.abs(np.sin(y * 0.33 + 2.0 * fbm2(y * 0.05, z * 0.1, 611, 2))) - 0.5) * roll * top_w
    # жатый лён: ячейки 1-3 см
    cr = fbm2(x * 0.45 + z * 0.3, y * 0.45, 621, 3) - 0.5
    cr2 = n2(x * 1.2 + z, y * 1.2, 623) - 0.5
    d += 0.16 * cr + 0.05 * cr2
    # подгиб кромок у торцов (по всему контуру слоя) и строчка
    de = y_end - np.abs(y)                     # расстояние до торца по y
    hem = np.exp(-((de - 1.4) / 0.6) ** 2) * (1 - end_w)
    d += 0.18 * hem
    along = x + z                              # строчка идёт вдоль кромки
    st_line = np.exp(-((de - 2.2) / 0.12) ** 2) * (1 - end_w)
    dash = sstep(0.25, 0.4, ((along / 1.1) % 1.0)) * sstep(0.95, 0.8, ((along / 1.1) % 1.0))
    stitch = st_line * dash
    d -= 0.07 * stitch
    stripe = np.zeros(n)
    ay = np.abs(y)
    for (c, w) in STRIPES:
        stripe = np.maximum(stripe, sstep(0.12, 0.0, np.abs(ay - c) - w))
    return d, dict(cavity=np.clip(cav, 0, 1), dent=dent, stitch=stitch, stripe=stripe)


FLAP_X = (41.0, 63.0)          # хвост полотенца на настиле: от бахромы до-под подушку
FLAP_Y = (-43.5, 44.5)
FLAP_EDGE = 44.6               # подшитый край, от него бахрома к -x


def flap_field(X, Y, deck_h):
    """Хвост полотенца на настиле. deck_h — высота настила под ним (поле Deck). h — над DECK_Z, см."""
    from_edge = X - FLAP_EDGE
    base = np.maximum(deck_h, -0.15)
    # ткань ложится на доски мягко: сглаженный настил
    k = 9
    pad = np.pad(base, k, mode="edge")
    c = np.cumsum(np.cumsum(pad, 0), 1)
    c = np.pad(c, ((1, 0), (1, 0)))
    sm = (c[2 * k + 1:, 2 * k + 1:] - c[:-2 * k - 1, 2 * k + 1:] - c[2 * k + 1:, :-2 * k - 1] + c[:-2 * k - 1, :-2 * k - 1]) / (2 * k + 1) ** 2
    cloth = np.maximum(sm, base - 0.05) + 0.45
    wr = 0.22 * (fbm2(X * 0.12, Y * 0.05, 701, 3) - 0.5) + 0.12 * (fbm2(X * 0.4 + Y * 0.1, Y * 0.4, 703, 3) - 0.5)
    folds = 0.3 * np.exp(-(((Y - 8 + 0.4 * (X - 50)) % 23 - 11.5) / 1.6) ** 2)
    in_cloth = (from_edge > 0) & (Y > FLAP_Y[0]) & (Y < FLAP_Y[1])
    edge_y = np.minimum(Y - FLAP_Y[0], FLAP_Y[1] - Y)
    hem = 0.2 * np.exp(-((from_edge - 0.7) / 0.45) ** 2) + 0.15 * np.exp(-((edge_y - 0.7) / 0.45) ** 2)
    H = cloth + wr + folds * sstep(0, 3, from_edge) + hem
    H -= 0.25 * sstep(0.6, 0.0, np.minimum(from_edge, edge_y))      # край ткани скруглён к доскам
    dash = sstep(0.25, 0.4, (Y / 1.1) % 1.0) * sstep(0.95, 0.8, (Y / 1.1) % 1.0)
    stitch = np.exp(-((from_edge - 1.6) / 0.12) ** 2) * dash * in_cloth
    H -= 0.07 * stitch
    # бахрома: скрученные кисточки 3.5 см, через 1.6 см, легли чуть веером
    fr = np.zeros_like(X)
    yk = np.arange(FLAP_Y[0] + 0.9, FLAP_Y[1] - 0.5, 2.0)
    for i, y0 in enumerate(yk):
        a = 0.25 * np.sin(i * 1.7) + 0.1 * np.sin(i * 4.3)
        L = 3.2 + 0.5 * np.sin(i * 2.9)
        u = -(from_edge) * np.cos(a) + (Y - y0) * np.sin(a)          # вдоль кисточки (от края к -x)
        v = (Y - y0) * np.cos(a) + from_edge * np.sin(a)
        w = 0.36 * (1 - 0.35 * np.clip(u / L, 0, 1))
        m = (u > -0.3) & (u < L) & (np.abs(v) < w)
        prof = np.sqrt(np.clip(1 - (v / w) ** 2, 0, 1))
        twist = 0.5 + 0.5 * np.sin((u * 1.0 + v * 2.0) / 0.5 * np.pi)
        tip = sstep(L, L - 0.6, u)
        fr = np.maximum(fr, np.where(m, (0.25 + 0.12 * twist) * prof * tip, 0))
    fr_zone = (from_edge <= 0.2)
    Hf = base + 0.05 + fr
    H = np.where(in_cloth, H, np.where(fr_zone & (fr > 0.01), Hf, -3.0))
    mask = in_cloth | (fr_zone & (fr > 0.01))
    stripe = np.zeros_like(X)
    for (c, w) in STRIPES:
        stripe = np.maximum(stripe, sstep(0.12, 0.0, np.abs(np.abs(Y) - c) - w))
    return dict(h=H, mask=mask, stitch=stitch, stripe=stripe * mask, fringe=(fr > 0.01) & fr_zone,
                cavity=np.zeros_like(X), dent=np.zeros_like(X))


def _voronoi(x, y, cell, seed):
    """F1, F2 по случайным точкам в клетках размера cell (джиттер-сетка)."""
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
            px, py = (cx + jx) * cell, (cy + jy) * cell
            d = np.hypot(x - px, y - py)
            f2 = np.where(d < f1, f1, np.minimum(f2, d))
            f1 = np.minimum(f1, d)
    return f1, f2


def deck_grid(step=STEP):
    xs = np.arange(DECK_X[0] - 0.6, DECK_X[1] + 0.6 + 1e-6, step)
    ys = np.arange(DECK_Y[0] - 0.3, DECK_Y[1] + 0.3 + 1e-6, step)
    return np.meshgrid(xs, ys)


if __name__ == "__main__":
    # быстрая проверка в .venv: теневой рельеф настила (как будет видно в нормали) -> plan_v2/deck_relief.png
    import sys
    from pathlib import Path
    from PIL import Image
    step = float(sys.argv[1]) if len(sys.argv) > 1 else STEP
    X, Y = deck_grid(step)
    d = Deck()
    f = d.field(X, Y)
    H = f["h"]
    gy, gx = np.gradient(H, step)
    L = np.array([-0.55, 0.35, 0.76])
    L /= np.linalg.norm(L)
    nx, ny, nz = -gx, -gy, np.ones_like(H)
    nn = np.sqrt(nx * nx + ny * ny + nz * nz)
    shade = np.clip((nx * L[0] + ny * L[1] + nz * L[2]) / nn, 0, 1)
    img = (shade ** 1.2 * 255).astype(np.uint8)[::-1]
    out = Path(__file__).parent / "plan_v2" / "deck_relief.png"
    Image.fromarray(img).save(out)
    print(out, H.shape, "h range", H.min(), H.max())
