"""Sauna Stove v3: остальные плоские поверхности — поля по граням (PLAN_v3.md §3.4–3.12). numpy, см.

Каждый «фасад» — набор островов одной стороны (ось и знак наружу). Сетка в плоскости стороны, основа — растр модели
(наружная поверхность), материал выбирается по номеру острова под точкой. Материалы — функции рельефа и масок:
  planks   — доски (рейки, забор с краской, поддон): кромки, коробление, волокна, сучки, трещины, гвозди парами
  slab     — горбыль обвязки: тёсаная неровность, волокна, кора полосой, уголь у горячей кромки
  iron     — кованое/листовое железо: лунки молота, окалина хлопьями, раковины, заклёпки
  olive    — пояс: старая оливковая краска слоем, облезла, раковины снизу, вмятины, болты с шайбами
  brick    — цоколь: кирпич по буграм модели, сколы углов, выкрошенные грани, трещины, раствор с камешками,
             один кирпич заменён базальтом
  tin      — жестяная латка: загнутые края, вмятина, гвоздики
  soot     — копоть (внутри проёмов): шероховато, с тлением снизу
Оси сторон: x-сторона — (u, v) = (z, y); z-сторона — (x, y); y-сторона — (x, z). W — координата наружу (×знак).
"""
import numpy as np

import geom_v3 as G
from fields_v3 import (MAT, STEP, char_field, fbm2, grain_relief, n2, nail_head, round_drop, sstep, voronoi)
from fields_door_v3 import hammer, pyramid_rivet, scale_flakes

MAT.update({"fence": 24, "brick": 25, "mortar": 26, "olive": 27, "tin": 28, "ash": 29, "pallet": 30, "soot_wood": 31})


def zeros_like_out(U):
    z = np.zeros(U.shape)
    return dict(d=z.copy(), grain=z.copy(), cav=z.copy(), dent=z.copy(), nail=z.copy(), knot=z.copy(), char=z.copy(),
                rust=z.copy(), crust=z.copy(), tone=z + 0.5, mat=z.copy(), sid=z - 1, bark=z.copy())


# ------------------------------------------------------------------ доски
def planks(U, V, rect, along, seed, wr=(8.0, 12.0), gap=(0.25, 0.6), nails_b=(), knots=3, cracks=2, mat="slat",
           paint=0.0, saw=False, cup=0.26, char_fn=None, wet_v=None):
    """Доски в прямоугольнике rect = (u0, u1, v0, v1); along = 'v' (доски вертикальные) или 'u' (горизонтальные).
    nails_b — координаты вдоль доски, где по 2 гвоздя (поперечины). paint — доля площади под старой краской."""
    rng = np.random.default_rng(seed)
    u0, u1, v0, v1 = rect
    A, B = (U, V) if along == "v" else (V, U)                  # a — поперёк досок, b — вдоль
    a0, a1 = (u0, u1) if along == "v" else (v0, v1)
    b0, b1 = (v0, v1) if along == "v" else (u0, u1)
    o = zeros_like_out(U)
    n = max(1, int(round((a1 - a0) / np.mean(wr))))
    w = rng.uniform(*wr, n)
    g = rng.uniform(*gap, n - 1) if n > 1 else np.array([])
    w *= (a1 - a0 - g.sum()) / w.sum()
    edges, a = [], a0
    for i in range(n):
        edges.append((a, a + w[i]))
        a += w[i] + (g[i] if i < n - 1 else 0)
    inside_any = np.zeros(U.shape, bool)
    d = np.full(U.shape, -1.0)                                   # щель — глубже
    for i, (lo, hi) in enumerate(edges):
        sd = int(rng.integers(1000))
        lo_w = lo + 0.15 * (fbm2(B * 0.04, i * 3.0, sd, 2) - 0.5) * 2
        hi_w = hi + 0.15 * (fbm2(B * 0.04, i * 3.0 + 1.5, sd, 2) - 0.5) * 2
        ins = (A > lo_w) & (A < hi_w) & (B > b0 - 1) & (B < b1 + 1)
        if not ins.any():
            continue
        dside = np.minimum(A - lo_w, hi_w - A)
        uu = (A - (lo + hi) / 2) / max((hi - lo) / 2, 0.5)
        h = rng.uniform(-0.14, 0.1) + 0.2 * rng.uniform(-1, 1) * (B - (b0 + b1) / 2) / max(b1 - b0, 1) + cup * (np.clip(uu, -1, 1) ** 2 - 0.4) - round_drop(dside, 0.3 + 0.1 * n2(B * 0.2, i, sd))
        h += 0.04 * (n2(B * 0.05, A * 0.3 + i * 11, sd + 1) - 0.5)
        kn = []
        for _ in range(knots if rng.random() < 0.8 else 0):
            kb, ka = rng.uniform(b0 + 4, b1 - 4), rng.uniform(lo + 1.5, hi - 1.5)
            kn.append((kb, ka, rng.uniform(0.5, 1.1)))
        gr = grain_relief(B, A, rng.uniform(1, 3), rng.uniform(0.008, 0.02), (lo + hi) / 2 + rng.uniform(-3, 3),
                          rng.uniform(0.9, 1.4), sd + 2, kn, rng.random() < 0.35)
        amp = rng.uniform(0.06, 0.1)
        h += amp * (gr - 0.35)
        if saw:                                                  # дуги циркулярной пилы
            R = 34.0
            bp = B - (R - np.sqrt(np.maximum(R * R - (A - (lo + hi) / 2 - 20) ** 2, 0)))
            ph = bp / 1.4 + 1.2 * fbm2(B * 0.04, A * 0.1, sd + 3, 2)
            h -= 0.02 * np.abs(np.sin(ph * np.pi)) ** 3
        for (kb, ka, kr) in kn:
            dd = np.hypot((B - kb) / 1.35, A - ka)
            core = sstep(kr, kr * 0.8, dd)
            h += 0.06 * core - 0.05 * np.exp(-((dd - kr) / 0.12) ** 2)
            o["knot"] = np.maximum(o["knot"], core * ins)
        for _ in range(cracks):
            ba = rng.uniform(b0, b1 - 6)
            L = rng.uniform(5, 20)
            ac = rng.uniform(lo + 1, hi - 1)
            box = ins & (B > ba) & (B < ba + L)
            if box.any():
                t = (B[box] - ba) / L
                yc = ac + 0.3 * (n2(B[box] * 0.15, sd * 1.0, sd + 4) - 0.5)
                prof = np.sin(np.pi * t) ** 0.6
                vv = np.clip(1 - np.abs(A[box] - yc) / (0.17 * prof + 1e-3), 0, 1)
                h[box] -= 0.25 * prof * vv
                o["cav"][box] = np.maximum(o["cav"][box], vv * prof)
        d = np.where(ins, h, d)
        o["grain"] = np.where(ins, gr, o["grain"])
        o["tone"] = np.where(ins, np.clip(rng.random() * 0.5 + 0.6 * (fbm2(A * 1.1 + i * 17, B * 0.025, sd + 5, 3) - 0.5) + 0.25, 0, 1), o["tone"])
        o["sid"] = np.where(ins, i, o["sid"])
        inside_any |= ins
        for bb in nails_b:
            for k, da in enumerate((-0.25, 0.25)):
                na, nb = (lo + hi) / 2 + da * (hi - lo) + rng.uniform(-0.3, 0.3), bb + rng.uniform(-0.6, 0.6)
                kind = 0 if rng.random() > 0.2 else int(rng.choice([1, 3]))
                box = (np.abs(A - na) < 1.6) & (np.abs(B - nb) < 1.6) & ins
                if box.any():
                    ang = (na * 7.3 + nb * 3.1) % 1.57
                    ca, sa = np.cos(ang), np.sin(ang)
                    du, dv = A[box] - na, B[box] - nb
                    Hn, nm = nail_head(d[box], du * ca + dv * sa, -du * sa + dv * ca, 0.0, kind)
                    d[box] = Hn
                    o["nail"][box] = np.maximum(o["nail"][box], nm)
    o["cav"] = np.where(inside_any, o["cav"], 1.0)
    if paint > 0:                                                # старая краска островами, слоем 0.3 мм
        pm = (fbm2(U * 0.07, V * 0.07, seed + 50, 4) + 0.15 * (n2(U * 0.5, V * 0.5, seed + 51) - 0.5)) > 1 - paint
        c1, c2 = voronoi(U, V, 1.4, seed + 52)
        craz = sstep(0.07, 0.015, c2 - c1)
        d = np.where(pm & inside_any, d + 0.03 - 0.02 * craz, d - 0.04 * o["grain"] * inside_any)   # голое — вытерто глубже
        o["crust"] = (pm & inside_any) * 1.0
        o["cav"] = np.maximum(o["cav"], craz * pm * 0.5)
    if char_fn is not None:
        amt = np.clip(char_fn(U, V), 0, 1) * inside_any
        if (amt > 0).any():
            m = amt > 0
            dh, cr = char_field(A[m], B[m], amt[m], 1.7, seed + 60)
            d[m] += dh
            o["cav"][m] = np.maximum(o["cav"][m], cr)
            o["char"] = amt
    mt = np.full(U.shape, float(MAT[mat]))
    mt = np.where(o["char"] > 0.5, MAT["char"], mt)
    mt = np.where(o["nail"] > 0.5, MAT["nail"], mt)
    if paint > 0:
        mt = np.where((o["crust"] > 0.5) & (mt == MAT[mat]), MAT["fence"], mt)
    o["mat"] = np.where(inside_any, mt, MAT["soot_wood"])
    o["d"] = d
    return o


def slab(U, V, along, seed, width_edge=None, bark=0.0, char_fn=None, nails=()):
    """Горбыль (обвязка): тёсаная неровность, волокна вдоль бруса, полоса коры у кромки width_edge = (ось, значение,
    ширина) — кора там, где расстояние до этой кромки < ширины × bark; уголь по char_fn; гвозди."""
    o = zeros_like_out(U)
    A, B = (U, V) if along == "v" else (V, U)
    gr = grain_relief(B, A, 1.5, 0.01, 0.7, 1.2, seed)
    d = 0.07 * (gr - 0.35) + 0.08 * (fbm2(B * 0.06, A * 0.3, seed + 1, 3) - 0.5)
    if width_edge is not None and bark > 0:
        ax, val, wid = width_edge
        coord = U if ax == "u" else V
        dist = np.abs(coord - val)
        line = wid * bark * (0.6 + 0.6 * fbm2(B * 0.08, seed * 1.0, seed + 2, 3))
        bk = dist < line
        f1, f2 = voronoi(B * 0.22, A * 1.9, 0.9, seed + 3)
        furrow = sstep(0.18, 0.04, f2 - f1)
        bh = (0.16 + 0.05 * np.clip(1 - f1, 0, 1) - 0.14 * furrow + 0.03 * (n2(B * 2.0, A * 2.0, seed + 4) - 0.5)) * sstep(line, line - 0.25, dist)
        d = np.where(bk, d + bh, d)
        o["cav"] = np.where(bk, furrow * 0.8, o["cav"])
        o["bark"] = bk * 1.0
    if char_fn is not None:
        amt = np.clip(char_fn(U, V), 0, 1) * (o["bark"] < 0.5)
        if (amt > 0).any():
            m = amt > 0
            dh, cr = char_field(A[m], B[m], amt[m], 1.7, seed + 5)
            d[m] += dh
            o["cav"][m] = np.maximum(o["cav"][m], cr)
            o["char"] = amt
    for (a, b) in nails:
        box = (np.abs(U - a) < 1.6) & (np.abs(V - b) < 1.6)
        if box.any():
            Hn, nm = nail_head(d[box], U[box] - a, V[box] - b, 0.0, 0)
            d[box] = Hn
            o["nail"][box] = np.maximum(o["nail"][box], nm)
    o["d"], o["grain"] = d, gr
    mt = np.where(o["bark"] > 0.5, MAT["bark"], MAT["frame"])
    mt = np.where(o["char"] > 0.5, MAT["char"], mt)
    o["mat"] = np.where(o["nail"] > 0.5, MAT["nail"], mt).astype(float)
    o["tone"] = 0.35 + 0.0 * U
    return o


def iron(U, V, seed, amp=0.08, rivets=(), soot=False, rust_lo=None):
    """Железо: лунки молота, окалина хлопьями, раковины гнёздами; заклёпки (u, v); rust_lo — v ниже которого
    гуще ржавчина (вода снизу)."""
    o = zeros_like_out(U)
    hm, edge = hammer(U, V, seed, 2.2, amp)
    fl, scale, fedge = scale_flakes(U, V, seed + 1, 0.55)
    g1, _ = voronoi(U, V, 0.45, seed + 2)
    dens = fbm2(U * 0.5, V * 0.5, seed + 3, 3) + (0.25 * sstep(rust_lo + 4, rust_lo, V) if rust_lo is not None else 0)
    pits = (dens > 0.6) * sstep(0.2, 0.06, g1)
    d = hm + fl - 0.05 * pits
    riv = np.zeros(U.shape)
    for (a, b) in rivets:
        box = (np.abs(U - a) < 1.2) & (np.abs(V - b) < 1.2)
        if box.any():
            Hn, rm = pyramid_rivet(d[box], U[box] - a, V[box] - b, 0.0)
            d[box] = Hn
            riv[box] = np.maximum(riv[box], rm)
    o.update(d=d, grain=edge, cav=np.clip(fedge * 0.6 + pits, 0, 1), crust=scale * 1.0, nail=riv,
             rust=np.clip(pits + (1 - scale) * 0.25 * (fbm2(U * 0.3, V * 0.3, seed + 4, 3) > 0.55), 0, 1))
    mt = np.full(U.shape, float(MAT["soot_iron" if soot else "iron"]))
    o["mat"] = np.where(riv > 0.5, MAT["rivet"], mt)
    return o


def olive(U, V, seed, v_lo, bolts=(), dents=()):
    """Пояс над цоколем: оливковая краска слоем 0.3 мм, облезла ~50 % (сколы ступенькой), под ней железо с раковинами,
    гуще у нижней кромки; вмятины от ног; болты с шайбами."""
    o = iron(U, V, seed, amp=0.04, rust_lo=v_lo)
    pm = (fbm2(U * 0.09, V * 0.12, seed + 10, 4) + 0.3 * sstep(v_lo + 3, v_lo + 8, V)) > 0.5
    o["d"] = np.where(pm, o["d"] * 0.3 + 0.03, o["d"])
    o["crust"] = pm * 1.0
    o["rust"] = np.where(pm, 0, o["rust"])
    for (a, b, r, dep) in dents:
        dd = np.hypot(U - a, V - b)
        u = np.clip(1 - (dd / r) ** 2, 0, 1) ** 2
        o["d"] -= dep * u
        o["dent"] = np.maximum(o["dent"], u)
    for (a, b) in bolts:
        dd = np.hypot(U - a, V - b)
        ang = np.arctan2(V - b, U - a)
        hexr = 0.85 / np.cos(((ang + np.pi / 6) % (np.pi / 3)) - np.pi / 6)
        washer = (dd < 1.5) * 0.15
        head = (dd < hexr) * (0.55 + 0.05 * np.clip(1 - dd / 0.85, 0, 1))
        o["d"] = np.maximum(o["d"], np.maximum(washer, head) * (dd < 1.5))
        o["nail"] = np.maximum(o["nail"], (dd < 1.5) * 1.0)
    mt = np.where(pm, MAT["olive"], MAT["iron"])
    o["mat"] = np.where(o["nail"] > 0.5, MAT["rivet"], mt).astype(float)
    return o


def label(mask, iters=400):
    """Связные области маски (4-соседство), numpy: распространение минимальной метки."""
    lab = np.where(mask, np.arange(mask.size).reshape(mask.shape), mask.size + 1)
    for _ in range(iters):
        prev = lab
        m = lab.copy()
        m[1:] = np.minimum(m[1:], np.where(mask[:-1], lab[:-1], mask.size + 1))
        m[:-1] = np.minimum(m[:-1], np.where(mask[1:], lab[1:], mask.size + 1))
        m[:, 1:] = np.minimum(m[:, 1:], np.where(mask[:, :-1], lab[:, :-1], mask.size + 1))
        m[:, :-1] = np.minimum(m[:, :-1], np.where(mask[:, 1:], lab[:, 1:], mask.size + 1))
        lab = np.where(mask, m, mask.size + 1)
        if np.array_equal(lab, prev):
            break
    return np.where(mask, lab, -1)


def box_blur(a, r):
    a = np.asarray(a, float)
    for ax in (0, 1):
        pad = [(0, 0), (0, 0)]
        pad[ax] = (r + 1, r)
        c = np.cumsum(np.pad(a, pad, mode="edge"), axis=ax)
        hi = np.take(c, np.arange(2 * r + 1, c.shape[ax]), axis=ax)
        lo = np.take(c, np.arange(0, c.shape[ax] - 2 * r - 1), axis=ax)
        a = (hi - lo) / (2 * r + 1)
    return a


def brick(U, V, W, seed, stone_at=None):
    """Цоколь: бугры модели = кирпичи. Основа сглажена (грани low-poly не запекаются), кирпич — где бугор выше
    раствора. Сколы углов, выкрошенные лицевые грани, трещины; раствор утоплен, зернистый, с камешками; кирпич в точке
    stone_at (u, v) заменён плоским базальтом. Возвращает dict с абсолютной поверхностью 'abs'."""
    rng = np.random.default_rng(seed)
    o = zeros_like_out(U)
    Wf = np.where(np.isnan(W), np.nanmin(W), W)
    S = box_blur(box_blur(Wf, 4), 4)                          # ~0.8 см
    # раскладка по геометрии: горизонтальные швы — минимумы средней высоты по рядам сетки, вертикальные — минимумы
    # вдоль каждого ряда кирпичей (бугры модели — кирпичи, канавки — швы)
    us, vs = U[0], V[:, 0]
    pv = np.convolve(S.mean(1), np.ones(9) / 9, mode="same")
    rows = [vs[0]]
    for j in np.argsort(pv):
        if 25 < j < len(vs) - 25 and all(abs(vs[j] - r) > 4.5 for r in rows + [vs[-1]]) and len(rows) < 3:
            rows.append(vs[j])
    rows = sorted(rows[1:])
    bounds = [vs[0] - 1] + rows + [vs[-1] + 1]
    lab = np.full(U.shape, -1)
    dist = np.full(U.shape, 9.0)
    nid = 0
    for c in range(len(bounds) - 1):
        band = (V >= bounds[c]) & (V < bounds[c + 1])
        if not band.any():
            continue
        jb = np.where((vs >= bounds[c]) & (vs < bounds[c + 1]))[0]
        pu = np.convolve(S[jb].mean(0), np.ones(15) / 15, mode="same")
        joints = []
        for i in np.argsort(pu):
            if 20 < i < len(us) - 20 and all(abs(us[i] - q) > 13.0 for q in joints):
                if pu[i] < np.percentile(pu, 35):
                    joints.append(us[i])
        joints = sorted(joints)
        edges = [us[0] - 1] + joints + [us[-1] + 1]
        for k in range(len(edges) - 1):
            m = band & (U >= edges[k]) & (U < edges[k + 1])
            lab[m] = nid
            nid += 1
        dj = np.min(np.abs(U[..., None] - np.array(joints)[None, None, :]), -1) if joints else np.full(U.shape, 9.0)
        dr = np.minimum(np.abs(V - bounds[c]), np.abs(V - bounds[c + 1]))
        dist = np.where(band, np.minimum(dj, dr), dist)
    wob = 0.18 * (n2(U * 0.7, V * 0.7, seed + 11) - 0.5) + 0.1 * (n2(U * 2.5, V * 2.5, seed + 12) - 0.5)
    br = (dist + wob) > 0.55
    edge_d = np.clip((dist + wob - 0.55) / 1.2, 0, 1)
    rel = 0.42 + 0.25 * edge_d
    lab = np.where(br, lab, -1)
    ids = np.unique(lab[lab >= 0])
    # своя случайная величина для каждого кирпича
    rnd = {i: rng.random(4) for i in ids}
    r0 = np.zeros(U.shape)
    r1 = np.zeros(U.shape)
    for i in ids:
        m = lab == i
        r0[m], r1[m] = rnd[i][0], rnd[i][1]
    # расстояние до края кирпича (по относительной высоте): сколы углов и кромок
    edge = np.clip((rel - 0.42) / 0.25, 0, 1)
    chip = (edge < 0.6) & (n2(U * 0.9, V * 0.9, seed + 1) > 0.58) & br
    d = (S - Wf) * 0.0
    d = d + np.where(chip, -0.25 * (1 - edge), 0)
    # выкрошенные лица: кратеры на части кирпичей
    sp = fbm2(U * 0.22, V * 0.3, seed + 2, 4) + 0.15 * (n2(U * 1.5, V * 1.5, seed + 3) - 0.5)
    spall = (r0 > 0.5) & br & (sp > 0.6)
    d = d - spall * (0.1 + 0.04 * sstep(0.6, 0.75, sp)) - 0.03 * spall * (n2(U * 3, V * 3, seed + 13) - 0.5)
    # трещины
    c1, c2 = voronoi(U * 0.6, V * 1.4, 3.5, seed + 4)
    crack = sstep(0.05, 0.01, c2 - c1) * br * (r1 > 0.6)
    d = d - 0.15 * crack
    # шероховатость обожжённой глины
    d = d + br * 0.025 * (n2(U * 2.5, V * 2.5, seed + 5) - 0.5)
    # раствор: утоплен, зернистый, камешки 3–5 мм
    g1, _ = voronoi(U, V, 0.45, seed + 6)
    peb = sstep(0.22, 0.08, g1) * (n2(U * 1.3, V * 1.3, seed + 7) > 0.55)
    d = d + (~br) * (-0.12 + 0.06 * peb + 0.04 * (n2(U * 3, V * 3, seed + 8) - 0.5))
    mt = np.where(br, MAT["brick"], MAT["mortar"]).astype(float)
    if stone_at is not None:
        su, sv = stone_at
        dist = np.hypot(U - su, V - sv)
        target = lab[np.unravel_index(np.argmin(np.where(br, dist, 1e9)), U.shape)]
        st = lab == target
        d = np.where(st, (S - Wf) * 0 + 0.08 * (n2(U * 0.8, V * 0.8, seed + 9) - 0.5) + 0.05 * sstep(0.3, 0.0, np.abs(n2(U * 0.4, V * 0.4, seed + 10) - 0.5)), d)
        mt = np.where(st, MAT["stone"], mt)
    o.update(cav=np.clip((~br) * 0.6 + crack + spall * 0.3 + chip * 0.4, 0, 1), dent=spall * 1.0, grain=peb,
             tone=np.where(br, r0, 0.5), knot=chip * 1.0, mat=mt, sid=np.where(br, (lab % 29), -1).astype(float))
    o["abs"] = S + d
    return o


def tin(U, V, rect, seed):
    """Жестяная латка 1 мм: загнутые края (валик 0.6 см), вмятина, гвоздики по углам."""
    u0, u1, v0, v1 = rect
    o = zeros_like_out(U)
    de = np.minimum(np.minimum(U - u0, u1 - U), np.minimum(V - v0, v1 - V))
    ins = de > 0
    d = np.where(ins, 0.1 + 0.12 * np.exp(-((de - 0.35) / 0.25) ** 2) + 0.02 * (n2(U * 0.6, V * 0.6, seed) - 0.5), -0.05)
    cu, cv = (u0 + u1) / 2 + 1.5, (v0 + v1) / 2 - 2
    dd = np.hypot(U - cu, V - cv)
    dent = np.clip(1 - (dd / 2.5) ** 2, 0, 1) ** 2
    d -= 0.1 * dent * ins
    for (a, b) in ((u0 + 1.0, v0 + 1.0), (u1 - 1.0, v0 + 1.0), (u0 + 1.0, v1 - 1.0), (u1 - 1.0, v1 - 1.0)):
        box = (np.abs(U - a) < 1.2) & (np.abs(V - b) < 1.2)
        Hn, nm = nail_head(d[box], U[box] - a, V[box] - b, 0.1, 0, r=0.4)
        d[box] = Hn
        o["nail"][box] = np.maximum(o["nail"][box], nm)
    o.update(d=d, dent=dent * ins, rust=np.clip((fbm2(U * 0.3, V * 0.3, seed + 1, 3) - 0.45) * 3, 0, 1) * ins,
             mat=np.where(ins, np.where(o["nail"] > 0.5, MAT["nail"], MAT["tin"]), MAT["soot_wood"]).astype(float))
    return o


def soot(U, V, seed, ember_v=None):
    """Копоть внутри проёмов: шероховато, бугры нагара; ember_v — ниже этого v тлеет (маска char = жар)."""
    o = zeros_like_out(U)
    o["d"] = 0.04 * (fbm2(U * 0.6, V * 0.6, seed, 3) - 0.5)
    o["mat"] = np.full(U.shape, float(MAT["soot_iron"]))
    if ember_v is not None:
        o["char"] = sstep(ember_v, ember_v - 6, V) * np.clip(fbm2(U * 0.25, V * 0.25, seed + 1, 3) * 1.6 - 0.4, 0, 1)
    return o


def ash(U, V, seed):
    """Просыпанная зола: горки гранул 3–6 мм."""
    o = zeros_like_out(U)
    g1, _ = voronoi(U, V, 0.4, seed)
    pile = np.clip(fbm2(U * 0.15, V * 0.15, seed + 1, 3) * 1.8 - 0.6, 0, 1)
    o["d"] = pile * (0.15 + 0.08 * sstep(0.25, 0.05, g1))
    o["crust"] = pile
    o["mat"] = np.where(pile > 0.15, MAT["ash"], MAT["iron"]).astype(float)
    return o
