"""v2 Sauna Bucket: полотенце с узлом и концами, веточка веника — high-poly поверх стенки (импортирует bake_bucket.py).

Полотенце намотано на верх шайки вместо верхнего обруча (решение 19.11: чтобы шайку нельзя было спутать с
«Wooden Bucket Hat» 2015 года — у того клёпки, два светлых обруча и сетка). Всё — геометрия, запекается в Normal,
AO и цвет: махра (бугорки 2–3 мм), складки сжатия, сходящиеся к узлу, подшитые кромки со строчкой, узел с
перехватом, два конца с бахромой; веник — прутья с корой, боковые веточки, листья внахлёст.
Полосы полотенца и тон — цвет вершин (у полосы нет формы).
"""
import math

import numpy as np
from mathutils import Vector

import noise_np as NN


def install(B):
    """B — модуль bake_bucket (общие mesh_np, tube, grid_faces, lin, HEX, axis_z и т. д.)."""
    D2R = B.D2R
    smooth = B.smooth
    lin = B.lin
    HEX = B.HEX

    def cyl_point(F, th, y, h):
        th = np.asarray(th, float)
        y = np.asarray(y, float)
        r = F.r(th, y) + h
        return np.stack([r * np.sin(th * D2R), y, B.axis_z(y) + r * np.cos(th * D2R)], -1)

    def outward(p):
        return Vector((p.x, 0, p.z - float(B.axis_z(p.y))))

    def towel_thickness(L, TH, Y):
        y0, y1 = L.towel
        v = (np.asarray(Y) - y0) / (y1 - y0)
        de = np.minimum(v, 1 - v) * (y1 - y0)
        return np.where((v > 0) & (v < 1), 0.0024 * np.sqrt(smooth(de / 0.0016)), 0.0)

    def leaf_at(F, ct, cy, ang, length, lift_fn, name, rng, dry=0.0):
        nu, nv = 110, 44
        U, Vv = np.meshgrid(np.linspace(0, 1, nu), np.linspace(-1, 1, nv), indexing="ij")
        half_w = 0.5 * length * 0.70 * np.sin(np.pi * np.clip(U, 0, 1) ** 0.72) ** 0.85 * (1 - 0.18 * U)
        sarc = U * length
        teeth = 0.0011 * (0.5 + 0.5 * np.sin(2 * np.pi * sarc / 0.0045)) + 0.0005 * (0.5 + 0.5 * np.sin(2 * np.pi * sarc / 0.0019))
        hw = np.maximum(half_w - teeth * (U > 0.08) * (U < 0.96), 0.0002)
        a = -U * length + length * 0.5
        b = Vv * hw
        mid = np.exp(-(b / 0.0008) ** 2) * (U < 0.95)
        vein = np.zeros_like(U)
        for i in range(7):
            bb = np.abs(b)
            d = np.abs(U - (0.12 + i * 0.11 + bb / length * 1.1)) * length * 0.75
            vein = np.maximum(vein, np.exp(-(d / 0.00045) ** 2) * (bb < hw * 0.92))
        curl = 0.0012 * np.abs(Vv) ** 3 + 0.0007 * (1 - np.cos(np.pi * U)) * dry
        hgt = 0.00045 + curl + 0.0006 * mid - 0.00025 * vein
        hgt = hgt + 0.0002 * (NN.vnoise(np.stack([U * 9, Vv * 4, U * 0 + float(rng.uniform(0, 50))], -1), 7) - 0.5)
        ca, sa = math.cos(ang), math.sin(ang)
        r0 = float(F.r(ct, cy))
        dx = b * ca - a * sa
        dy = b * sa + a * ca
        TH = ct + dx / r0 / D2R
        Y = cy + dy
        P = cyl_point(F, TH, Y, lift_fn(TH, Y) + hgt)
        lc, vc, ec = lin(HEX["leaf"]), lin(HEX["leaf_vein"]), lin(HEX["leaf_edge"])
        lc = lc * (1 - dry * 0.35) + lin("7A7A3A") * dry * 0.35
        tv = np.clip(0.8 * mid + 0.7 * vein, 0, 1)
        te = smooth((np.abs(Vv) - 0.8) / 0.2) * (0.5 + 0.4 * dry)
        col = np.empty(U.shape + (3,))
        for c in range(3):
            col[..., c] = (lc[c] * (1 - tv) + vc[c] * tv) * (1 - te) + ec[c] * te
        ob = B.mesh_np(name, P.reshape(-1, 3), B.grid_faces(nu, nv), col.reshape(-1, 3), "leaf",
                       np.stack([0 * U, 0.3 * vein, 0 * U], -1).reshape(-1, 3))
        B.flip_if_inward(ob, outward)
        return ob

    def towel_part(L, F, rng, step=0.00045):
        y0, y1 = L.towel
        rm = float(F.r(0.0, (y0 + y1) / 2))
        nth = int(round(2 * math.pi * rm / step))
        nv = int(round((y1 - y0) / 0.0004)) + 1
        TH, Y = np.meshgrid(np.linspace(-180, 180, nth, endpoint=False), np.linspace(y0, y1, nv), indexing="ij")
        v = (Y - y0) / (y1 - y0)
        arc = TH * D2R * rm
        t = towel_thickness(L, TH, Y)
        de = np.minimum(v, 1 - v) * (y1 - y0)
        hem = np.exp(-((de - 0.0028) / 0.0018) ** 2)            # подшитая кромка — валик
        t = t + 0.0007 * hem
        stitch = np.exp(-((de - 0.0045) / 0.00045) ** 2) * (0.5 + 0.5 * np.cos(2 * np.pi * arc / 0.0034)) ** 2
        t = t - 0.00018 * stitch                                 # строчка
        dk = ((TH - L.knot_th + 180) % 360 - 180)
        nearK = np.exp(-(dk / 55.0) ** 2)                        # складки сходятся к узлу
        slant = 0.9 * np.sign(dk) * nearK
        lam = 0.024 - 0.010 * nearK
        ph = (arc + slant * (Y - (y0 + y1) / 2) * 3.0 + 0.006 * np.sin(arc / 0.05)) / lam
        fold = (0.5 + 0.5 * np.cos(2 * np.pi * ph + 1.7 * NN.vnoise(np.stack([TH * 0.05, Y * 30, 0 * Y + 4], -1), 61))) ** 1.6
        t = t + 0.0013 * fold * smooth(de / 0.006) * (0.6 + 0.6 * nearK)
        pile = NN.vnoise(np.stack([arc / 0.0024, Y / 0.0024, 0 * Y + 7], -1), 62)   # махра
        t = t + 0.00028 * (pile - 0.5) * smooth(de / 0.001)
        col = np.tile(lin(HEX["towel"]), TH.shape + (1,))
        stripe = (smooth((v - 0.14) / 0.01) * (1 - smooth((v - 0.25) / 0.01)) +
                  smooth((v - 0.30) / 0.008) * (1 - smooth((v - 0.345) / 0.008)))
        sc = lin(HEX["stripe"])
        for c in range(3):
            col[..., c] = col[..., c] * (1 - stripe) + sc[c] * stripe
        col = col * (0.86 + 0.14 * (1 - fold))[..., None] * (0.92 + 0.12 * pile)[..., None]
        msk = np.stack([np.zeros_like(t), np.clip(stitch * 0.6, 0, 1), np.zeros_like(t)], -1)
        P = cyl_point(F, TH, Y, t + 0.0002)
        ob = B.mesh_np("hp_towel", P.reshape(-1, 3), B.grid_faces(nth, nv, closed_u=True), col.reshape(-1, 3), "towel",
                       msk.reshape(-1, 3))
        obs = [ob]
        # узел 38×30 мм, высота ~10 мм, перехват поперёк, складки по кругу
        kc_th, kc_y = L.knot_th, (y0 + y1) / 2 - 0.002
        rk = float(F.r(kc_th, kc_y))
        A, Bq = np.meshgrid(np.linspace(-1, 1, 140), np.linspace(-1, 1, 120), indexing="ij")
        rho = np.sqrt(A ** 2 + Bq ** 2)
        inside = rho <= 1.0
        hk = 0.0095 * np.clip(1 - rho ** 2, 0, 1) ** 0.55
        wrap = np.exp(-((A * 0.8 + Bq * 0.6) / 0.16) ** 2)
        hk = hk - 0.0022 * wrap * (rho < 0.95)
        hk = hk + 0.0007 * np.cos(7 * np.arctan2(Bq, A) + 3 * rho) * rho * (rho < 0.98)
        hk = hk + 0.00025 * (NN.vnoise(np.stack([A * 18, Bq * 18, 0 * A + 9], -1), 63) - 0.5)
        THk = kc_th + (A * 0.019) / rk / D2R
        Yk = kc_y + Bq * 0.015
        Pk = cyl_point(F, THk, Yk, towel_thickness(L, THk, Yk) + 0.0007 + np.maximum(hk, 0.0))
        colk = np.tile(lin(HEX["towel"]), A.shape + (1,)) * (0.88 + 0.1 * (1 - wrap))[..., None]
        sk = smooth((np.abs(A * 0.6 - Bq * 0.8) - 0.55) / 0.05) * (1 - smooth((np.abs(A * 0.6 - Bq * 0.8) - 0.72) / 0.05))
        for c in range(3):
            colk[..., c] = colk[..., c] * (1 - sk) + lin(HEX["stripe"])[c] * sk
        keep = inside[:-1, :-1] & inside[1:, :-1] & inside[1:, 1:] & inside[:-1, 1:]
        ok = B.mesh_np("hp_towel_knot", Pk.reshape(-1, 3), B.grid_faces(*A.shape, keep=keep), colk.reshape(-1, 3),
                       "towel", np.stack([0 * A, 0.5 * wrap, 0 * A], -1).reshape(-1, 3))
        B.flip_if_inward(ok, outward)
        obs.append(ok)
        # два конца с бахромой
        for ti, (dth, ln, w, sway) in enumerate(((-7.0, 0.078, 0.032, 0.005), (8.0, 0.060, 0.028, -0.006))):
            nl, nw = int(ln / 0.0004), int(w / 0.0004)
            S, Wq = np.meshgrid(np.linspace(0, 1, nl), np.linspace(-1, 1, nw), indexing="ij")
            cy_ = kc_y - 0.004 - S * ln
            cth = kc_th + dth + (sway * np.sin(S * 2.2) + 0.004 * S ** 2) / rk / D2R
            wd = w * (1 - 0.12 * S)
            THt = cth + Wq * (wd / 2) / rk / D2R
            Yt = cy_ + 0.002 * Wq * S
            dee = (1 - np.abs(Wq)) * wd / 2
            tt = 0.0021 * np.sqrt(smooth(dee / 0.0012)) + 0.0006 * np.exp(-((dee - 0.0026) / 0.0016) ** 2)
            tt = tt + 0.0011 * (0.5 + 0.5 * np.cos(2 * np.pi * (Wq * 1.3 + 0.15 * np.sin(S * 5 + ti)))) * smooth(dee / 0.004)
            tt = tt + 0.00026 * (NN.vnoise(np.stack([THt * D2R * rk / 0.0024, Yt / 0.0024, 0 * S + 11 + ti], -1), 64) - 0.5)
            lift = towel_thickness(L, THt, Yt) + 0.0005 + 0.0012 * (1 - S) ** 2
            Pt = cyl_point(F, THt, Yt, lift + tt)
            colt = np.tile(lin(HEX["towel"]), S.shape + (1,))
            st_ = (smooth((Wq - 0.30) / 0.05) * (1 - smooth((Wq - 0.62) / 0.05)) +
                   smooth((Wq - 0.72) / 0.04) * (1 - smooth((Wq - 0.82) / 0.04)))
            for c in range(3):
                colt[..., c] = colt[..., c] * (1 - st_) + lin(HEX["stripe"])[c] * st_
            ot = B.mesh_np(f"hp_towel_tail{ti}", Pt.reshape(-1, 3), B.grid_faces(nl, nw), colt.reshape(-1, 3), "towel")
            B.flip_if_inward(ot, outward)
            obs.append(ot)
            for fi in range(9):          # бахрома: нити Ø 1.2 мм
                wq = -0.85 + fi * 0.2125
                th_f = float(cth[-1, 0]) + wq * (float(wd[-1, 0]) / 2) / rk / D2R
                y_f = float(cy_[-1, 0])
                fl = float(rng.uniform(0.006, 0.010))
                pts = []
                for j in range(7):
                    yy = y_f - fl * j / 6
                    tt_ = th_f + float(rng.normal(0, 0.15)) * j / 6
                    pts.append(Vector(cyl_point(F, tt_, yy, 0.0011 + 0.0004 * (1 - j / 6)).tolist()))
                obs.append(B.tube(pts, 0.0006, f"hp_fringe{ti}_{fi}", "towel", lin(HEX["towel"]) * 0.9, seg=6,
                                  strands=2, groove=0.25))
        L.data["towel"] = [y0, y1, L.knot_th]
        return obs

    def venik_part(L, F, rng):
        obs = []
        vt = L.venik_th
        y_top = L.towel[0] + 0.012
        rv = float(F.r(vt, 0.27))
        twigs = []
        for i in range(6):
            ang = (i - 2.5) * 0.09 + float(rng.normal(0, 0.03))
            ln = float(rng.uniform(0.10, 0.135))
            pts = []
            for j in range(30):
                sj = j / 29
                d = ln * sj
                th_ = vt + (math.sin(ang) * d + 0.004 * math.sin(sj * 3 + i)) / rv / D2R + (i - 2.5) * 0.6
                y_ = y_top - math.cos(ang) * d
                lift = float(towel_thickness(L, np.array(th_), np.array(y_))) + 0.0013
                pts.append(Vector(cyl_point(F, th_, y_, lift).tolist()))
            twigs.append((pts, ang))
            obs.append(B.tube(pts, 0.0012, f"hp_twig{i}", "twig", lin(HEX["twig"]), seg=10, strands=5, groove=0.12,
                              twist=4.0, fray=lambda k: 1.0 - 0.45 * k / 29))
            k0 = int(rng.integers(10, 20))
            side = 1 if rng.random() < 0.5 else -1
            bp = pts[k0]
            th_b = math.degrees(math.atan2(bp.x, bp.z - float(B.axis_z(bp.y))))
            sp = [Vector(cyl_point(F, th_b + side * (0.022 * j / 9) * 0.8 / rv / D2R, bp.y - 0.022 * j / 9 * 0.6,
                                   0.0011).tolist()) for j in range(10)]
            obs.append(B.tube(sp, 0.0006, f"hp_twigside{i}", "twig", lin(HEX["twig"]), seg=6, strands=3, groove=0.1))
        for li in range(11):
            pts, ang = twigs[li % 6]
            p = pts[int(rng.integers(9, 29))]
            th_ = math.degrees(math.atan2(p.x, p.z - float(B.axis_z(p.y))))
            la = math.pi + ang + float(rng.uniform(-0.9, 0.9))
            lb = 0.0026 + 0.0009 * li / 11
            obs.append(leaf_at(F, th_, p.y, la, float(rng.uniform(0.034, 0.044)),
                               lambda T, Yy, lb=lb: towel_thickness(L, T, Yy) + lb, f"hp_vleaf{li}", rng,
                               float(rng.uniform(0.0, 0.7))))
        L.data["venik"] = [vt, y_top]
        return obs

    return towel_part, venik_part
