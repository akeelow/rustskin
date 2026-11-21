"""Sauna Stove v3: колотый базальт и укладка кучей (numpy; меши строит bake_v3.py). PLAN_v3.md §3.3, §3.9.

Камень: икосфера, сплюснутая эллипсоидом, срезанная 5–9 плоскостями раскола (точки за плоскостью проецируются на
неё — плоские грани с острыми рёбрами), рёбра слегка скруглены, на рёбрах — раковистые сколы (выемки), на гранях —
редкие поры и шероховатость, у крупных — 1–2 трещины от жара. Маски на вершинах:
  m1 = (грань/скол — светлее на сколе, полость (поры, трещины), 0)   m2 = (0, 0, жар — низ камня и трещины)
  m3 = (0, белая корка накипи на верхних гранях, тон камня)
Размеры — см (PLAN_v3.md §1: грань 15–50 мм, скол 6–12 мм, поры 3–5 мм).
"""
import numpy as np


def icosphere(sub):
    t = (1 + 5 ** 0.5) / 2
    V = np.array([[-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0], [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
                  [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1]], float)
    F = np.array([[0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11], [1, 5, 9], [5, 11, 4], [11, 10, 2],
                  [10, 7, 6], [7, 1, 8], [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9], [4, 9, 5], [2, 4, 11],
                  [6, 2, 10], [8, 6, 7], [9, 8, 1]])
    V /= np.linalg.norm(V, axis=1, keepdims=True)
    for _ in range(sub):
        cache = {}
        Vl = list(V)

        def midp(a, b):
            k = (a, b) if a < b else (b, a)
            if k not in cache:
                m = (Vl[a] + Vl[b]) / 2
                Vl.append(m / np.linalg.norm(m))
                cache[k] = len(Vl) - 1
            return cache[k]

        nf = []
        for a, b, c in F:
            ab, bc, ca = midp(a, b), midp(b, c), midp(c, a)
            nf += [[a, ab, ca], [b, bc, ab], [c, ca, bc], [ab, bc, ca]]
        V, F = np.array(Vl), np.array(nf)
    return V, F


_ICO = {}


def ico(sub):
    if sub not in _ICO:
        _ICO[sub] = icosphere(sub)
    return _ICO[sub]


def vnoise3(p, seed=0):
    i = np.floor(p).astype(np.int64)
    f = p - i
    f = f * f * (3 - 2 * f)
    out = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                x = ((i[:, 0] + dx) * 73856093) ^ ((i[:, 1] + dy) * 19349663) ^ ((i[:, 2] + dz) * 83492791) ^ (seed * 2654435761)
                x = (x ^ (x >> 13)) * 1274126177
                h = ((x ^ (x >> 16)) & 0xFFFF).astype(np.float64) / 65535
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                out = out + h * w
    return out


def vertex_normals(V, F):
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    vn = np.zeros_like(V)
    for k in range(3):
        np.add.at(vn, F[:, k], n)
    return vn / (np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12)


def stone(size, rng, sub=4, cracks=True):
    """Один колотый камень с центром в 0 (y — вверх). size — наибольший размер, см.
    Возвращает V (n, 3), F (m, 3), маски {m1, m2, m3} (n, 3)."""
    V0, F = ico(sub)
    V = V0 * (np.array([1.0, rng.uniform(0.5, 0.75), rng.uniform(0.7, 0.95)]) * size / 2)
    # плоскости раскола: широкие грани сверху/снизу и по бокам
    planes = []
    nplanes = int(rng.integers(7, 12))
    for k in range(nplanes):
        n = rng.normal(size=3)
        if k == 0:
            n = np.array([rng.normal(0, 0.25), -1.0, rng.normal(0, 0.25)])        # низ — плоский (лежит)
        n /= np.linalg.norm(n)
        sup = (V @ n).max()
        d = sup * rng.uniform(0.5, 0.82)
        planes.append((n, d))
        over = V @ n - d
        V = V - np.clip(over, 0, None)[:, None] * n[None, :]
    # скругление рёбер: лёгкое сглаживание по соседям (2 прохода, 25 %)
    nbr = [[] for _ in range(len(V))]
    for a, b, c in F:
        nbr[a] += [b, c]
        nbr[b] += [a, c]
        nbr[c] += [a, b]
    for _ in range(1):
        avg = np.array([V[list(set(n))].mean(0) for n in nbr])
        V = V * 0.85 + avg * 0.15
    vn = vertex_normals(V, F)
    chip = np.zeros(len(V))
    cav = np.zeros(len(V))
    hot = np.zeros(len(V))
    # сколы на рёбрах: вершины, где активны две плоскости (близко к обеим)
    act = np.stack([np.abs(V @ n - d) < 0.04 * size for n, d in planes], 1).sum(1)
    edge_ids = np.where(act >= 2)[0]
    for _ in range(int(rng.integers(3, 7))):
        if len(edge_ids) == 0:
            break
        p = V[rng.choice(edge_ids)]
        rc = rng.uniform(0.5, 1.1) * (size / 5) ** 0.5
        d = np.linalg.norm(V - p, axis=1)
        u = np.clip(1 - (d / rc) ** 2, 0, 1)
        dep = rng.uniform(0.12, 0.22) * rc
        V = V - vn * (dep * u ** 1.5)[:, None]
        chip = np.maximum(chip, (u > 0.05) * (0.4 + 0.6 * u))
    # шероховатость и поры
    q = V / max(size, 1e-3)
    rough = vnoise3(V * 1.8, 11) - 0.5 + 0.5 * (vnoise3(V * 4.5, 12) - 0.5)
    V = V + vn * (0.035 * rough)[:, None]
    if size > 3.0:
        for _ in range(int(size * 2)):
            p = V[rng.integers(len(V))]
            rp = rng.uniform(0.15, 0.25)
            d = np.linalg.norm(V - p, axis=1)
            u = np.clip(1 - (d / rp) ** 2, 0, 1)
            V = V - vn * (0.1 * u)[:, None]
            cav = np.maximum(cav, u)
    # трещины от жара: борозда вдоль кривой плоскости через камень
    if cracks and size > 4.0:
        for _ in range(int(rng.integers(1, 3))):
            n = rng.normal(size=3)
            n[1] *= 0.3
            n /= np.linalg.norm(n)
            off = rng.uniform(-0.2, 0.2) * size
            s = V @ n - off + 0.15 * size * (vnoise3(V * 0.8, 21) - 0.5)
            u = np.clip(1 - np.abs(s) / 0.12, 0, 1)
            # трещина обрывается: только на части поверхности
            u *= vnoise3(V * 0.5, 23) > 0.4
            V = V - vn * (0.12 * u ** 1.2)[:, None]
            cav = np.maximum(cav, u)
            hot = np.maximum(hot, u)
    vn = vertex_normals(V, F)
    y0 = V[:, 1].min()
    hot = np.maximum(hot, np.clip(1 - (V[:, 1] - y0) / (0.25 * size), 0, 1) ** 2 * 0.8)
    tone = np.full(len(V), rng.random())
    z = np.zeros(len(V))
    masks = {"m1": np.stack([chip, cav, z], -1), "m2": np.stack([z, z, hot], -1), "m3": np.stack([z, z, tone], -1),
             "vn": vn}
    return V, F, masks


def charcoal(size, rng, sub=4):
    """Кусок древесного угля: брусок с 4–6 плоскостями, сетка трещин-«кубиков» (ячейка 0.7–1 см), торцевые кольца.
    Маски как у камня; m2.z (жар) — в трещинах, m1.y (полость) — трещины."""
    V, F, m = stone(size, rng, sub=sub, cracks=False)
    V = V * np.array([1.0, 0.8, 0.7])
    cell = rng.uniform(0.7, 1.0)
    fx = np.abs(np.sin(V[:, 0] * np.pi / cell))
    fz = np.abs(np.sin((V[:, 2] + 0.3 * V[:, 1]) * np.pi / (cell * 1.3)))
    crack = np.clip(1 - np.minimum(fx, fz) / 0.18, 0, 1)
    vn = vertex_normals(V, F)
    V = V - vn * (0.12 * crack)[:, None]
    m["m1"][:, 1] = np.maximum(m["m1"][:, 1], crack)
    m["m2"][:, 2] = np.maximum(m["m2"][:, 2] * 0.5, crack)
    m["vn"] = vertex_normals(V, F)
    return V, F, m


def rot(rng):
    """Случайный поворот: вокруг вертикали — любой, наклон — до 25°."""
    a = rng.uniform(0, 2 * np.pi)
    b = rng.uniform(-0.45, 0.45)
    c = rng.uniform(-0.45, 0.45)
    Ry = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    Rx = np.array([[1, 0, 0], [0, np.cos(b), -np.sin(b)], [0, np.sin(b), np.cos(b)]])
    Rz = np.array([[np.cos(c), -np.sin(c), 0], [np.sin(c), np.cos(c), 0], [0, 0, 1]])
    return Ry @ Rx @ Rz


def heap(center, r, base_y, rng, n_big, big, n_small, small, sub=4, crust=True, cell=0.2, lean=0.0):
    """Куча на круглом основании (центр (x, z), радиус r, уровень base_y). Крупные — по кругу и в середине, мелкие —
    сверху и в щели. Каждый камень опускается до опоры по карте высот кучи (с утоплением 15 % — камни сцеплены).
    lean — подъём кучи к −z (задней стенке топки), см на см. Возвращает список (V, F, masks)."""
    cx, cz = center
    n = int(np.ceil(2 * (r + 4) / cell))
    hm = np.full((n, n), base_y)
    xs = cx - r - 4 + (np.arange(n) + 0.5) * cell
    zs = cz - r - 4 + (np.arange(n) + 0.5) * cell

    def idx(x, z):
        return (np.clip(((z - zs[0]) / cell).round().astype(int), 0, n - 1),
                np.clip(((x - xs[0]) / cell).round().astype(int), 0, n - 1))

    out = []
    sizes = [rng.uniform(*big) for _ in range(n_big)] + [rng.uniform(*small) for _ in range(n_small)]
    for k, s in enumerate(sizes):
        V, F, m = stone(s, rng, sub=sub if s > 3 else max(sub - 1, 2))
        R = rot(rng)
        V = V @ R.T
        m["vn"] = m["vn"] @ R.T
        # насыпание: из 24 случайных мест (внутри основания, с учётом размера) камень ложится туда, где выйдет ниже
        # всего — заполняет ямы, куча не растёт столбом
        ext = np.abs(V[:, [0, 2]]).max()
        best = None
        for _ in range(24):
            ang = rng.uniform(0, 2 * np.pi)
            rr = (max(r - 0.55 * ext, 0.0)) * np.sqrt(rng.uniform(0, 1))
            px, pz = cx + rr * np.cos(ang), cz + rr * np.sin(ang)
            iz, ix = idx(V[:, 0] + px, V[:, 2] + pz)
            y_off = (hm[iz, ix] - V[:, 1]).max() - 0.12 * s * 0.6
            y_off = max(y_off, base_y - V[:, 1].min() + lean * max(0.0, -(pz - cz)))
            score = y_off + V[:, 1].max() + 0.15 * rr * (k < n_big) - 2.2 * lean * max(0.0, -(pz - cz))   # склон к −z
            if best is None or score < best[0]:
                best = (score, px, pz, y_off)
        _, px, pz, y_off = best
        iz, ix = idx(V[:, 0] + px, V[:, 2] + pz)
        V = V + np.array([px, y_off, pz])
        # обновить карту высот вершинами камня (и соседними ячейками)
        for dz in (-1, 0, 1):
            for dx in (-1, 0, 1):
                np.maximum.at(hm, (np.clip(iz + dz, 0, n - 1), np.clip(ix + dx, 0, n - 1)), V[:, 1])
        out.append((V, F, m))
    # корка накипи: верхние грани камней, которые сверху никто не закрывает, пятнами
    if crust:
        top = max(V[:, 1].max() for V, _, _ in out)
        for V, F, m in out:
            up = np.clip((m["vn"][:, 1] - 0.45) / 0.4, 0, 1)
            iz, ix = idx(V[:, 0], V[:, 2])
            exposed = (V[:, 1] >= hm[iz, ix] - 0.25)
            patch = np.clip((vnoise3(V * 0.55, 31) - 0.35) * 2.5, 0, 1)
            hi = np.clip((V[:, 1] - base_y) / max(top - base_y, 1e-3), 0, 1)
            m["m3"][:, 1] = up * exposed * patch * (0.4 + 0.6 * hi)
    return out
