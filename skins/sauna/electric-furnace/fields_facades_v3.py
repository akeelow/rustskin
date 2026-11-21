"""Sauna Stove v3: таблица фасадов — какие острова, с какой стороны и каким материалом (fields_rest_v3.py).

Оси сторон: x-сторона — (u, v) = (z, y); z-сторона — (x, y); y-сторона — (x, z). W — координата наружу (×знак).
Материал — функция f(U, V, W, ID) -> dict (d — смещение наружу от модели или abs — абсолютная поверхность; маски).
"""
import numpy as np

import geom_v3 as G
from fields_v3 import MAT, fbm2, grain_relief, n2, nail_head, round_drop, sstep
from fields_door_v3 import hammer, pyramid_rivet
from fields_rest_v3 import ash, box_blur, brick, iron, olive, planks, slab, soot, tin, zeros_like_out


def near(mask, r):
    """Близость к маске (0..1) на r ячеек — размытие."""
    return np.clip(box_blur(mask.astype(float), r) * 3, 0, 1)


def knob_centers():
    V, T, N, F = G.load()
    pc = G.piece_of_face()
    out = []
    for p in (38, 39, 40, 41, 42):
        pts = V[F[pc == p][:, :, 0]].reshape(-1, 3)
        out.append(((pts[:, 0].min() + pts[:, 0].max()) / 2, (pts[:, 1].min() + pts[:, 1].max()) / 2))
    return out


def blend(o, src, mask):
    for k in o:
        if k in src:
            o[k] = np.where(mask, src[k], o[k])
    return o


def m_right(U, V, W, ID):
    """+x: обвязка вокруг проёма (19) — горбыль, сверху кора, у верхнего проёма обуглена; нижний короб (18) —
    горизонтальные доски; задняя стенка верхнего проёма (22) — копоть и тление снизу; планки (36, 42) — железо."""
    o = zeros_like_out(U)
    fr = ID == 19
    opening = (ID != 19) & (ID >= 0)
    hot = near(opening & (V > 90), 25) * fr
    cf = lambda u, v: hot * sstep(0.35, 0.6, fbm2(u * 0.1, v * 0.1, 7, 3) + 0.3 * hot)
    sv = slab(U, V, "v", 201, char_fn=cf, nails=[(-31.0, 55.0), (31.0, 55.0), (-31.0, 85.0), (31.0, 85.0)])
    sh = slab(U, V, "u", 203, width_edge=("v", 110.3, 4.5), bark=1.0, char_fn=cf,
              nails=[(-30.5, 108.0), (30.5, 108.0), (-30.5, 33.0), (30.5, 33.0)])
    horiz = (V > 105.8) | (V < 35.6)
    blend(o, sv, fr & ~horiz)
    blend(o, sh, fr & horiz)
    pk = planks(U, V, (-29.0, 29.0, 27.0, 51.0), "u", 205, wr=(7.5, 9.0), nails_b=(-26.5, 0.0, 26.5),
                char_fn=lambda u, v: sstep(47.0, 51.0, v) * sstep(0.4, 0.6, fbm2(u * 0.1, v * 0.2, 11, 3)))
    blend(o, pk, ID == 18)
    blend(o, soot(U, V, 207, ember_v=100.0), ID == 22)
    blend(o, iron(U, V, 209, amp=0.07, rust_lo=52.0), np.isin(ID, [36, 42]))
    return o


def m_iron(seed, soot_=False, rivets=(), rust_lo=None):
    return lambda U, V, W, ID: iron(U, V, seed, rivets=rivets, soot=soot_, rust_lo=rust_lo)


def m_slab(seed, along, bark=0.0, edge=None, char=0.0):
    def f(U, V, W, ID):
        cf = (lambda u, v: char * sstep(0.4, 0.65, fbm2(u * 0.1, v * 0.06, seed, 3))) if char else None
        return slab(U, V, along, seed, width_edge=edge, bark=bark, char_fn=cf)
    return f


def m_soot(seed, ember_v=None):
    return lambda U, V, W, ID: soot(U, V, seed, ember_v)


def m_back(U, V, W, ID):
    """−z (вид сзади, u = x): доски забора с краской (4), лючок (7) — вертикальные доски, Z-шпонка, кованые петли,
    деревянная вертушка; жестяная латка (49); полоса с прорезями (38)."""
    o = planks(U, V, (-29.2, 29.2, 30.6, 110.3), "u", 301, wr=(10.0, 14.0), nails_b=(-26.5, 0.5, 26.5), paint=0.45,
               knots=2, cracks=2)
    hatch = ID == 7
    if hatch.any():
        h = planks(U, V, (-25.2, 25.2, 59.8, 96.2), "v", 303, wr=(9.0, 11.0), nails_b=(64.0, 92.0), knots=1, cracks=1)
        led = ((np.abs(V - 64.0) < 2.4) | (np.abs(V - 92.0) < 2.4)) & (np.abs(U) < 22.5)
        t = (U + 20.0) / 40.0
        diag_v = 66.0 + t * 24.0
        diag = (np.abs(V - diag_v) < 2.2) & (U > -20) & (U < 20)
        brace = led | diag
        de = np.minimum(np.minimum(np.abs(np.abs(V - 64.0) - 2.4), np.abs(np.abs(V - 92.0) - 2.4)), np.abs(np.abs(V - diag_v) - 2.2))
        gb = grain_relief(U, V, 2.0, 0.01, 78.0, 1.1, 305)
        hb = 1.2 - round_drop(np.clip(de, 0, None), 0.3) + 0.06 * (gb - 0.35)
        h["d"] = np.where(brace, np.maximum(h["d"], hb), h["d"])
        h["grain"] = np.where(brace, gb, h["grain"])
        h["mat"] = np.where(brace, MAT["slat"], h["mat"])
        for vv in (64.0, 92.0):                         # кованые петли слева: полосы 2.5 × 15 см, по 3 гвоздя
            strap = (np.abs(V - vv) < 1.25) & (U > -25.5) & (U < -10.5)
            hm, _ = hammer(U, V, 307, 1.4, 0.05)
            h["d"] = np.where(strap, 1.45 + hm, h["d"])
            h["mat"] = np.where(strap, MAT["iron"], h["mat"])
            for a in (-22.5, -17.5, -12.5):
                box = (np.abs(U - a) < 1.0) & (np.abs(V - vv) < 1.0)
                Hn, nm = nail_head(h["d"][box], U[box] - a, V[box] - vv, 1.45, 0, r=0.45)
                h["d"][box] = Hn
                h["nail"][box] = np.maximum(h["nail"][box], nm)
        cu, cv, ang = 21.0, 78.0, 0.35                  # вертушка-задвижка: брусок 3 × 8 см на гвозде
        ru = (U - cu) * np.cos(ang) + (V - cv) * np.sin(ang)
        rv = -(U - cu) * np.sin(ang) + (V - cv) * np.cos(ang)
        btn = (np.abs(ru) < 4.0) & (np.abs(rv) < 1.5)
        dbt = np.minimum(4.0 - np.abs(ru), 1.5 - np.abs(rv))
        hb2 = 1.2 - round_drop(np.clip(dbt, 0, None), 0.35) + 0.05 * (grain_relief(ru, rv, 1.0, 0.0, 0.0, 0.8, 309) - 0.35)
        h["d"] = np.where(btn, np.maximum(h["d"], hb2), h["d"])
        h["mat"] = np.where(btn, MAT["plaque"], h["mat"])
        box = (np.abs(U - cu) < 1.0) & (np.abs(V - cv) < 1.0)
        Hn, nm = nail_head(h["d"][box], U[box] - cu, V[box] - cv, 1.2, 0, r=0.45)
        h["d"][box] = Hn
        h["nail"][box] = np.maximum(h["nail"][box], nm)
        blend(o, h, hatch)
    blend(o, tin(U, V, (-23.0, -10.2, 62.2, 85.0), 311), ID == 49)
    ir = iron(U, V, 313, rust_lo=33.0)
    sl = np.zeros(U.shape)
    for k in range(8):                                  # 8 штампованных прорезей с вдавленной фаской
        cu = -19.25 + k * 5.5
        du, dv = np.abs(U - cu) - 1.3, np.abs(V - 35.5) - 0.45
        q = np.hypot(np.clip(du, 0, None), np.clip(dv, 0, None)) + np.minimum(np.maximum(du, dv), 0)
        sl = np.maximum(sl, sstep(0.15, -0.1, q))
        ir["d"] = ir["d"] - 0.45 * sstep(0.05, -0.15, q) + 0.06 * np.exp(-((q - 0.2) / 0.15) ** 2)
    ir["cav"] = np.maximum(ir["cav"], sl)
    blend(o, ir, ID == 38)
    return o


def m_front(U, V, W, ID):
    """+z: панель ручек (28) — берёзовые доски, насечки-метки над ручками; нижняя панель (29) — железо с заслонкой
    поддувала; планка (89) — железо."""
    o = planks(U, V, (-29.5, 29.6, 97.5, 110.4), "u", 401, wr=(6.0, 6.8), nails_b=(-27.5, 27.5), knots=1, cracks=1,
               char_fn=lambda u, v: sstep(100.5, 97.6, v) * sstep(0.35, 0.6, fbm2(u * 0.12, v * 0.3, 13, 3)))
    for (cx, cy) in knob_centers():                      # 3 V-насечки ножом над каждой ручкой
        for ang in (-0.5, 0.0, 0.5):
            px, py = cx + 3.1 * np.sin(ang), cy + 3.1 * np.cos(ang)
            ru = (U - px) * np.cos(ang) - (V - py) * np.sin(ang)
            rv = (U - px) * np.sin(ang) + (V - py) * np.cos(ang)
            g = np.clip(1 - np.abs(ru) / 0.12, 0, 1) * (np.abs(rv) < 0.5)
            o["d"] = o["d"] - 0.06 * g
            o["cav"] = np.maximum(o["cav"], g)
    o["mat"] = np.where(o["mat"] == MAT["slat"], MAT["plaque"], o["mat"])
    ir = iron(U, V, 403, rust_lo=32.0)
    dp = (U > -9.0) & (U < 6.0) & (V > 33.2) & (V < 37.6)          # заслонка 15 × 4.4 см, 2 мм
    de = np.minimum(np.minimum(U + 9.0, 6.0 - U), np.minimum(V - 33.2, 37.6 - V))
    hm, _ = hammer(U, V, 405, 1.5, 0.04)
    ir["d"] = np.where(dp, 0.2 - round_drop(np.clip(de, 0, None), 0.1) + hm, ir["d"])
    tab = (U > -11.6) & (U < -8.6) & (V > 34.4) & (V < 36.4)        # загнутый язычок
    ir["d"] = np.where(tab, 0.2 + 0.45 * np.clip((-8.6 - U) / 3.0, 0, 1) ** 0.7, ir["d"])
    for a in (-11.0, 8.5):                                          # заклёпки направляющих
        box = (np.abs(U - a) < 1.2) & (np.abs(V - 35.4) < 1.2)
        Hn, rm = pyramid_rivet(ir["d"][box], U[box] - a, V[box] - 35.4, 0.0, s=0.6, hgt=0.35)
        ir["d"][box] = Hn
        ir["nail"][box] = np.maximum(ir["nail"][box], rm)
    ir["mat"] = np.where(ir["nail"] > 0.5, MAT["rivet"], ir["mat"])
    blend(o, ir, ID == 29)
    blend(o, iron(U, V, 407, amp=0.06), ID == 89)
    return o


def m_olive(seed, v_lo, ends, front=False):
    def f(U, V, W, ID):
        dents = [(-12.0, 25.0, 2.2, 0.12), (4.0, 27.5, 1.6, 0.08), (15.0, 24.5, 2.6, 0.1)] if front else []
        return olive(U, V, seed, v_lo, bolts=[(e, 26.5) for e in ends], dents=dents)
    return f


def m_brick(seed, stone_at=None):
    return lambda U, V, W, ID: brick(U, V, W, seed, stone_at)


def m_pallet_top(U, V, W, ID):
    """Поддон сверху (+y, u = x, v = z): доски вдоль x, щели, дуги пилы, гвозди над 3 брусками, сломанный угол."""
    o = planks(U, V, (-39.2, 39.2, -39.2, 39.2), "u", 501, wr=(9.0, 11.5), gap=(0.8, 1.8), nails_b=(-31.0, 0.0, 31.0),
               knots=1, cracks=2, saw=True, mat="pallet")
    wedge = (U < -33.0) & (V > 30.0) & ((U + 39.2) / 6.2 + (39.2 - V) / 9.2 < 1)
    o["d"] = np.where(wedge, -0.9 + 0.1 * (n2(U * 3, V * 3, 503) - 0.5), o["d"])
    o["cav"] = np.where(wedge, 0.6, o["cav"])
    return o


def m_endgrain(seed, block=10.5):
    """Торцы досок: кольца в каждом блоке, щели между блоками."""
    def f(U, V, W, ID):
        o = zeros_like_out(U)
        k = np.floor((U + 40.0) / block)
        cu = (k + 0.5) * block - 40.0 + 2.0 * (n2(k * 3.1, 0.5, seed) - 0.5)
        cv = np.nanmin(V) - 3.0
        rr = np.hypot(U - cu, (V - cv) * 1.3) + 0.25 * (n2(U * 0.6, V * 0.6, seed + 1) - 0.5)
        f_ = rr / 0.35 - np.floor(rr / 0.35)
        rings = np.exp(-((f_ - 0.5) / 0.2) ** 2)
        gap = ((U + 40.0) % block) < 0.6
        o["d"] = 0.03 * rings - 0.02 - 0.5 * gap
        o["grain"] = rings
        o["cav"] = gap * 1.0
        o["mat"] = np.full(U.shape, float(MAT["pallet"]))
        o["tone"] = 0.3 + 0.0 * U
        return o
    return f


def m_ash(seed):
    return lambda U, V, W, ID: ash(U, V, seed)


# (имя, группа, острова, ось, знак, куски-фильтр, материал)
FACADES = [
    ("right", "right", {19, 18, 22, 36, 42}, 0, 1, None, m_right),
    ("right_in", "right", {37, 30}, 0, -1, None, m_soot(211)),
    ("right_edge_f", "right", {82}, 2, 1, None, m_slab(213, "v", 1.0, ("u", 33.0, 2.8))),
    ("right_edge_b", "right", {83}, 2, -1, None, m_slab(215, "v")),
    ("right_edge_t", "right", {101}, 1, 1, None, m_slab(217, "v")),
    ("left_edge_b", "right", {84}, 2, -1, None, m_slab(219, "v")),
    ("left_edge_t", "right", {111}, 1, 1, None, m_slab(221, "v")),
    ("rail85", "rails85", {31}, 0, 1, {85}, m_iron(231, rust_lo=91.0)),
    ("rail86", "rails86", {46}, 0, 1, {86}, m_iron(233)),
    ("post89", "post89", {27}, 0, 1, {89}, m_iron(235, rust_lo=34.0)),
    ("back", "back", {4, 7, 49, 38}, 2, -1, None, m_back),
    ("back_sides", "back", {77}, 0, 1, None, m_slab(303, "v")),
    ("back_sides2", "back", {79}, 0, -1, None, m_slab(305, "v")),
    ("front", "front2", {28, 29, 89}, 2, 1, None, m_front),
    ("front_up", "front2", {183, 97}, 1, 1, None, m_ash(411)),
    ("front_up2", "front2", {140, 131, 145}, 1, 1, None, m_iron(413, soot_=True)),
    ("front_dn", "front2", {95, 96, 132, 144, 147}, 1, -1, None, m_iron(415, soot_=True)),
    ("front_xp", "front2", {139, 163, 159}, 0, 1, None, m_iron(417, soot_=True)),
    ("front_xn", "front2", {138, 164, 160}, 0, -1, None, m_iron(419, soot_=True)),
    ("band_f", "band", {32}, 2, 1, None, m_olive(601, 22.2, (-29.0, 29.0), True)),
    ("band_b", "band", {33}, 2, -1, None, m_olive(603, 22.2, (-29.0, 29.0))),
    ("band_r", "band", {35}, 0, 1, None, m_olive(605, 22.2, (-29.0, 29.0))),
    ("band_l", "band", {34}, 0, -1, None, m_olive(607, 22.2, (-29.0, 29.0))),
    ("band_t", "band", {122, 124, 127, 129}, 1, 1, None, m_iron(609)),
    ("plinth_f", "plinth", {12}, 2, 1, None, m_brick(701, stone_at=(-11.0, 13.0))),
    ("plinth_b", "plinth", {13}, 2, -1, None, m_brick(703)),
    ("plinth_r", "plinth", {15}, 0, 1, None, m_brick(705)),
    ("plinth_l", "plinth", {14}, 0, -1, None, m_brick(707)),
    ("plinth_t", "plinth", {116, 135, 165}, 1, 1, None, m_brick(709)),
    ("pallet_t", "pallet", {5}, 1, 1, None, m_pallet_top),
    ("pallet_xp", "pallet", {149}, 0, 1, None, m_endgrain(801)),
    ("pallet_xn", "pallet", {152}, 0, -1, None, m_endgrain(803)),
    ("pallet_zp", "pallet", {154}, 2, 1, None, m_slab(805, "u")),
    ("pallet_zn", "pallet", {153}, 2, -1, None, m_slab(807, "u")),
    ("pallet_lo_xp", "pallet", {162}, 0, 1, None, m_slab(809, "u")),
    ("pallet_lo_xn", "pallet", {161}, 0, -1, None, m_slab(811, "u")),
    ("pallet_lo_zp", "pallet", {157}, 2, 1, None, m_endgrain(813, 26.0)),
    ("pallet_lo_zn", "pallet", {158}, 2, -1, None, m_endgrain(815, 26.0)),
]
def _split(specs, names):
    """Кромки на разной глубине перекрываются в проекции — по фасаду на остров."""
    out = []
    for s in specs:
        if s[0] in names:
            for i in sorted(s[2]):
                out.append((f"{s[0]}_{i}", s[1], {i}, s[3], s[4], s[5], s[6]))
        else:
            out.append(s)
    return out


FACADES = _split(FACADES, {"front_up", "front_up2", "front_dn", "front_xp", "front_xn", "plinth_t"})
UV_AXES = {0: (2, 1), 1: (0, 2), 2: (0, 1)}      # ось стороны -> (ось u, ось v)


def facade_field(spec, step=0.1, margin=0.3):
    """-> (P (ny, nx, 3) в см с NaN вне островов, r — маски) для одной записи FACADES."""
    name, group, isl, ax, sg, pcs, fn = spec
    T3, ids = G.tris_ids(islands=isl, pieces=pcs)
    au, av = UV_AXES[ax]
    lo = T3.reshape(-1, 3).min(0) - margin
    hi = T3.reshape(-1, 3).max(0) + margin
    U, Vg = np.meshgrid(np.arange(lo[au], hi[au] + 1e-6, step), np.arange(lo[av], hi[av] + 1e-6, step))
    W, ID = G.raster_height(T3, U, Vg, au, av, ax, sign=sg, fill=np.nan, ids=ids)
    r = fn(U, Vg, W, ID)
    Wabs = r["abs"] if "abs" in r else W + r["d"]
    Wabs = np.where(np.isnan(W), np.nan, Wabs)
    P = np.zeros(U.shape + (3,))
    P[..., au], P[..., av], P[..., ax] = U, Vg, sg * Wabs
    r["h"] = Wabs
    return P, r
