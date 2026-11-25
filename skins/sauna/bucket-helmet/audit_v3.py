"""Проверка Sauna Bucket v2 по урокам §9 (25.11.2026): нормали модели, гранёность в запечённой нормали, плотность
текселей по осям, копии на общих UV, насыщенность нормали рельефом против оригинала и принятых деревянных шлемов.

Запуск (.venv):  python skins/sauna/bucket-helmet/audit_v3.py
Вход:  originals/bucket.helmet.obj, uv/faces_obj.json, uv/ids.png, export/SaunaBucket_v2_normal.png,
       originals/metal_improvised_helmet_02_nrm.png, кэш Steam (принятые Wood Armor Helmet).
Выход: check_v3/audit.md (таблицы), check_v3/crops_*.png (вырезы атласа).
"""
import json
import math
import os
from collections import defaultdict

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "check_v3")
OBJ = os.path.join(HERE, "originals", "bucket.helmet.obj")
STEAM = "C:/Program Files (x86)/Steam/steamapps/workshop/content/252490"
WOOD_HELMETS = ["3793503336", "3793532594", "3805626764", "3814377112"]   # принятые Wood Armor Helmet в кэше
OUR_ID = "3842910954"


def load_obj():
    V, T, N, F = [], [], [], []
    for line in open(OBJ):
        p = line.split()
        if not p:
            continue
        if p[0] == "v":
            V.append([float(x) for x in p[1:4]])
        elif p[0] == "vt":
            T.append([float(x) for x in p[1:3]])
        elif p[0] == "vn":
            N.append([float(x) for x in p[1:4]])
        elif p[0] == "f":
            F.append([[int(i) - 1 for i in q.split("/")] for q in p[1:]])
    return np.array(V), np.array(T), np.array(N), F


def gblur(a, s):
    """Гаусс по осям (numpy, без scipy)."""
    r = int(3 * s)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / s) ** 2)
    k /= k.sum()
    out = a.astype(np.float32)
    for ax in (0, 1):
        pad = [(0, 0)] * out.ndim
        pad[ax] = (r, r)
        p = np.pad(out, pad, mode="edge")
        acc = np.zeros_like(out)
        for i, w in enumerate(k):
            sl = [slice(None)] * out.ndim
            sl[ax] = slice(i, i + out.shape[ax])
            acc += w * p[tuple(sl)]
        out = acc
    return out


def nrm_xy(path, size=1024):
    im = Image.open(path).convert("RGB")
    if im.size != (size, size):
        im = im.resize((size, size), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32) / 255 * 2 - 1
    return a[..., :2]


def highpass_rms(xy, mask, s=6):
    """RMS наклона мелкого рельефа: нормаль − размытая нормаль (σ = s px), только внутри маски (эрозия 4 px)."""
    m = mask.copy()
    for _ in range(4):
        m = m & np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)
    hp = xy - gblur(xy, s)
    t = np.linalg.norm(hp, axis=-1)[m]
    return float(np.sqrt((t ** 2).mean())) if t.size else float("nan"), float(np.percentile(t, 95)) if t.size else 0.0


def main():
    os.makedirs(OUT, exist_ok=True)
    V, T, N, F = load_obj()
    isl = json.load(open(os.path.join(HERE, "uv", "faces_obj.json")))
    md = ["# Проверка v2 по урокам §9 (audit_v3.py, 25.11.2026)", ""]

    # ------------------------------------------------ 1. нормали модели: угол vn к нормали грани, жёсткие рёбра
    ang = defaultdict(list)
    fn_of = []
    for fi, f in enumerate(F):
        p = V[[c[0] for c in f]]
        n = np.zeros(3)
        for k in range(1, len(p) - 1):
            n += np.cross(p[k] - p[0], p[k + 1] - p[0])
        n /= np.linalg.norm(n) + 1e-12
        fn_of.append(n)
        for c in f:
            vn = N[c[2]] / (np.linalg.norm(N[c[2]]) + 1e-12)
            ang[isl[fi]].append(math.degrees(math.acos(np.clip(vn @ n, -1, 1))))
    # рёбра: одна позиция, разные vn у соседних граней — разрез нормалей (жёсткое ребро)
    edge = defaultdict(list)
    for fi, f in enumerate(F):
        for a, b in zip(f, f[1:] + f[:1]):
            k = (min(a[0], b[0]), max(a[0], b[0]))
            edge[k].append((fi, {a[0]: a[2], b[0]: b[2]}))
    hard = defaultdict(int)
    inner = defaultdict(int)
    dihed = defaultdict(list)
    for k, lst in edge.items():
        if len(lst) != 2:
            continue
        (f1, n1), (f2, n2) = lst
        if isl[f1] != isl[f2]:
            continue
        inner[isl[f1]] += 1
        d = math.degrees(math.acos(np.clip(fn_of[f1] @ fn_of[f2], -1, 1)))
        dihed[isl[f1]].append(d)
        if any(not np.allclose(N[n1[v]], N[n2[v]], atol=1e-4) for v in k):
            hard[isl[f1]] += 1
    md += ["## 1. Нормали модели (OBJ)", "",
           "Угол между нормалью вершины `vn` и нормалью грани; «двугранный» — угол между соседними гранями внутри острова; "
           "«жёстких» — внутренних рёбер острова с разными `vn` у двух граней.", "",
           "| остров | граней | угол vn↔грань ср. | p95 | макс | двугранный ср. | макс | жёстких рёбер / всего |",
           "|---:|---:|---:|---:|---:|---:|---:|---|"]
    main_isl = [1, 3, 5, 6, 7, 8, 9, 37]
    for i in main_isl:
        a = np.array(ang[i])
        d = np.array(dihed[i]) if dihed[i] else np.zeros(1)
        md.append(f"| {i} | {sum(1 for x in isl if x == i)} | {a.mean():.1f}° | {np.percentile(a, 95):.1f}° | {a.max():.1f}° | "
                  f"{d.mean():.1f}° | {d.max():.1f}° | {hard[i]} / {inner[i]} |")
    w = [x for i in range(10, 46) if i not in (37,) for x in ang[i]]
    md.append(f"| сетка 2, 4, 10–45 | — | {np.mean(w):.1f}° | {np.percentile(w, 95):.1f}° | {np.max(w):.1f}° | — | — | (вырезана альфой) |")
    md.append("")

    # ------------------------------------------------ 2. плотность по осям (px/см при 1024)
    md += ["## 2. Плотность текселей по осям (px/см при 1024; 4096-запекание — ×4)", "",
           "Для каждой грани — растяжение UV→3D по двум главным направлениям (сингулярные числа), медиана по острову, "
           "взвешенная по площади. Минимум детали: 3–4 px → мм; повторяющийся рисунок: 5–6 px → мм.", "",
           "| остров | что | px/см (мин. ось) | px/см (макс. ось) | деталь ≥ (мм) | рисунок ≥ (мм) |",
           "|---:|---|---:|---:|---:|---:|"]
    what = {1: "стенка снаружи", 3: "макушка (утор + днище)", 5: "ушко снаружи (2 копии)", 6: "торец окна",
            7: "изнанка (жесть)", 8: "гвоздь ушка (2 копии)", 9: "ушко изнутри (2 копии)", 37: "внутреннее дно"}
    dens = {}
    for i in main_isl:
        s1, s2, wts = [], [], []
        for fi, f in enumerate(F):
            if isl[fi] != i:
                continue
            for k in range(1, len(f) - 1):
                c = [f[0], f[k], f[k + 1]]
                P = V[[q[0] for q in c]]
                U = T[[q[1] for q in c]] * 1024
                E = np.stack([P[1] - P[0], P[2] - P[0]], 1) * 100   # см, 3×2
                D = np.stack([U[1] - U[0], U[2] - U[0]], 1)          # px, 2×2
                if abs(np.linalg.det(D)) < 1e-6:
                    continue
                J = E @ np.linalg.inv(D)                             # см на px
                sv = np.linalg.svd(J, compute_uv=False)
                area = 0.5 * np.linalg.norm(np.cross(E[:, 0], E[:, 1]))
                s1.append(1 / sv[0])
                s2.append(1 / sv[1])
                wts.append(area)
        o = np.argsort(s1)
        cw = np.cumsum(np.array(wts)[o])
        lo = np.array(s1)[o][np.searchsorted(cw, cw[-1] / 2)]
        o2 = np.argsort(s2)
        cw2 = np.cumsum(np.array(wts)[o2])
        hi = np.array(s2)[o2][np.searchsorted(cw2, cw2[-1] / 2)]
        dens[i] = (lo, hi)
        md.append(f"| {i} | {what[i]} | {lo:.1f} | {hi:.1f} | {35 / lo:.1f} | {55 / lo:.1f} |")
    md.append("")

    # ------------------------------------------------ 3. копии на общих UV: преобразование наименьшими квадратами
    md += ["## 3. Копии на общих UV (наименьшие квадраты)", ""]
    for i in (5, 8, 9):
        by_vt = defaultdict(set)
        for fi, f in enumerate(F):
            if isl[fi] == i:
                for c in f:
                    by_vt[c[1]].add(c[0])
        pairs = [sorted(s) for s in by_vt.values() if len(s) == 2]
        if not pairs:
            md.append(f"- остров {i}: копий нет")
            continue
        # разделить вершины на две копии по знаку x (ушки на ±90°)
        A = np.array([V[a] if V[a][0] < V[b][0] else V[b] for a, b in pairs])
        B = np.array([V[b] if V[a][0] < V[b][0] else V[a] for a, b in pairs])
        ca, cb = A.mean(0), B.mean(0)
        H = (A - ca).T @ (B - cb)
        U_, S_, Vt = np.linalg.svd(H)
        R = Vt.T @ U_.T
        det = np.linalg.det(R)
        res = np.linalg.norm((A - ca) @ R.T + cb - B, axis=1)
        # с зеркалом: x → −x
        Am = A * np.array([-1, 1, 1])
        resm = np.linalg.norm(Am - B, axis=1)
        md.append(f"- остров {i}: {len(pairs)} пар вершин; лучший поворот det={det:+.2f}, невязка ср. {res.mean() * 1000:.2f} мм; "
                  f"зеркало x→−x: невязка ср. {resm.mean() * 1000:.2f} мм, макс {resm.max() * 1000:.2f} мм")
    md.append("")

    # ------------------------------------------------ 4. насыщенность нормали рельефом
    ids = np.asarray(Image.open(os.path.join(HERE, "uv", "ids.png")).convert("RGB")).astype(np.int32)
    idm = ids[..., 0] + ids[..., 1] * 256
    ours = nrm_xy(os.path.join(HERE, "export", "SaunaBucket_v2_normal.png"))
    orig = nrm_xy(os.path.join(HERE, "originals", "metal_improvised_helmet_02_nrm.png"))
    md += ["## 4. Насыщенность нормали рельефом (1024)", "",
           "RMS наклона мелкого рельефа = |n − размытая n|, σ = 6 px (≈ 4 мм на стенке); p95 — сильные детали. "
           "Наклон 0.10 ≈ склон 6°. Общий наклон — |n.xy| без размытия (низкочастотное тоже).", "",
           "| остров | наш v2: мелкий RMS | p95 | общий наклон ср. | оригинал FP: мелкий RMS | p95 | общий ср. |",
           "|---:|---:|---:|---:|---:|---:|---:|"]
    for i in main_isl:
        m = idm == i
        r1, p1 = highpass_rms(ours, m)
        r2, p2 = highpass_rms(orig, m)
        t1 = float(np.linalg.norm(ours, axis=-1)[m].mean())
        t2 = float(np.linalg.norm(orig, axis=-1)[m].mean())
        md.append(f"| {i} | {r1:.3f} | {p1:.3f} | {t1:.3f} | {r2:.3f} | {p2:.3f} | {t2:.3f} |")
    md.append("")
    md += ["Принятые **Wood Armor Helmet** из кэша (другая развёртка — сравнение только по силе рельефа: все пиксели "
           "с отклонением от плоской нормали; плотность у шлема близкая, голова того же размера):", "",
           "| скин | карта | мелкий RMS | p95 | общий наклон ср. |", "|---|---|---:|---:|---:|"]
    for wid in WOOD_HELMETS + [OUR_ID]:
        p = os.path.join(STEAM, wid, "_BumpMap0.png")
        if not os.path.exists(p):
            continue
        im = Image.open(p)
        xy = nrm_xy(p)
        tilt = np.linalg.norm(xy, axis=-1)
        m = gblur(tilt, 3) > 0.02
        r, p95 = highpass_rms(xy, m)
        md.append(f"| {'наш v2 (кэш)' if wid == OUR_ID else wid} | {im.size[0]} | {r:.3f} | {p95:.3f} | {float(tilt[m].mean()):.3f} |")
    md.append("")

    # ------------------------------------------------ 5. гранёность: сравнение с картой «грань против vn»
    # Если бы в нормаль запеклась гранёность low-poly, низкие частоты карты повторяли бы рисунок граней:
    # внутри грани плоская нормаль грани, выраженная в касательном базисе сглаженной vn.
    # Предсказываем этот рисунок и считаем корреляцию с размытой картой (σ = 3 px).
    pred = np.zeros((1024, 1024, 2), np.float32)
    have = np.zeros((1024, 1024), bool)
    for fi, f in enumerate(F):
        if isl[fi] not in (1, 3, 7):
            continue
        for k in range(1, len(f) - 1):
            c = [f[0], f[k], f[k + 1]]
            P = V[[q[0] for q in c]]
            Ut = T[[q[1] for q in c]]
            Nn = N[[q[2] for q in c]]
            px = np.array([[u * 1024, (1 - v) * 1024] for u, v in Ut])
            x0, y0 = np.floor(px.min(0)).astype(int)
            x1, y1 = np.ceil(px.max(0)).astype(int)
            x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, 1023), min(y1, 1023)
            if x1 < x0 or y1 < y0:
                continue
            ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
            Q = np.stack([xs + 0.5, ys + 0.5], -1)
            Mx = np.array([[px[1, 0] - px[0, 0], px[2, 0] - px[0, 0]], [px[1, 1] - px[0, 1], px[2, 1] - px[0, 1]]])
            if abs(np.linalg.det(Mx)) < 1e-9:
                continue
            bc = (Q - px[0]) @ np.linalg.inv(Mx).T
            l1, l2 = bc[..., 0], bc[..., 1]
            l0 = 1 - l1 - l2
            ins = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
            if not ins.any():
                continue
            vn = l0[..., None] * Nn[0] + l1[..., None] * Nn[1] + l2[..., None] * Nn[2]
            vn /= np.linalg.norm(vn, axis=-1, keepdims=True) + 1e-12
            # касательные по UV (как MikkTSpace до ортогонализации)
            E1, E2 = P[1] - P[0], P[2] - P[0]
            d1, d2 = Ut[1] - Ut[0], Ut[2] - Ut[0]
            r = d1[0] * d2[1] - d2[0] * d1[1]
            if abs(r) < 1e-12:
                continue
            tg = (E1 * d2[1] - E2 * d1[1]) / r
            bt = (E2 * d1[0] - E1 * d2[0]) / r
            fn = np.cross(E1, E2)
            fn /= np.linalg.norm(fn) + 1e-12
            tt = tg - vn * (vn @ tg)[..., None]
            tt /= np.linalg.norm(tt, axis=-1, keepdims=True) + 1e-12
            sgn = np.sign(np.cross(vn, tt) @ bt)[..., None]
            bb = np.cross(vn, tt) * sgn
            x = tt @ fn
            y = bb @ fn
            sub = pred[y0:y1 + 1, x0:x1 + 1]
            sub[ins] = np.stack([x[ins], y[ins]], -1)
            have[y0:y1 + 1, x0:x1 + 1] |= ins
    md += ["## 5. Гранёность в запечённой нормали", "",
           "Рисунок «плоская грань в базисе сглаженной vn» (так выглядела бы нормаль, запечённая с гранёной копии) против "
           "размытой карты (σ = 3 px). Корреляция ~1 — гранёность запеклась, ~0 — нет. Амплитуда рисунка — насколько "
           "грани вообще отличаются от сглаженных нормалей.", "",
           "| остров | амплитуда рисунка граней (ср. |xy|) | корреляция с v2 | корреляция с оригиналом FP |",
           "|---:|---:|---:|---:|"]
    sm_o = gblur(ours, 3)
    sm_f = gblur(orig, 3)
    for i in (1, 3, 7):
        m = have & (idm == i)
        for _ in range(3):
            m = m & np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)
        a = pred[m] - pred[m].mean(0)
        b = sm_o[m] - sm_o[m].mean(0)
        c = sm_f[m] - sm_f[m].mean(0)
        cor_o = float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-12))
        cor_f = float((a * c).sum() / (np.sqrt((a * a).sum() * (c * c).sum()) + 1e-12))
        md.append(f"| {i} | {float(np.linalg.norm(pred[m], axis=-1).mean()):.3f} | {cor_o:+.2f} | {cor_f:+.2f} |")
    md.append("")
    vis = np.clip((pred * 2.5) * 0.5 + 0.5, 0, 1)
    vis = np.concatenate([vis, np.ones_like(vis[..., :1])], -1)
    vis[~have] = 0.15
    Image.fromarray((vis * 255).astype(np.uint8)).save(os.path.join(OUT, "facet_pattern.png"))

    # ------------------------------------------------ 6. вырезы атласа: наш v2 и оригинал (Diffuse + Normal)
    # окна (x, y, размер) в атласе 1024: стенка — полоса y 487…1004, u = 0.5 + азимут/360 (окно по центру)
    crops = {"wall_venik_towel (az -80)": (160, 487, 256), "wall_knot (az +80)": (640, 487, 256),
             "wall_low_copper (az +45)": (560, 748, 256), "wall_back (az 170)": (880, 600, 144),
             "top (isl 3)": (68, 136, 256), "ear (isl 5) + rim": (270, 300, 256), "inner (isl 7)": (520, 200, 256)}
    srcs = [("ours v2 Diffuse", os.path.join(HERE, "export", "SaunaBucket_v2_diffuse.png")),
            ("ours v2 Normal", os.path.join(HERE, "export", "SaunaBucket_v2_normal.png")),
            ("FP Diffuse", os.path.join(HERE, "originals", "metal_improvised_helmet_02_bc.png")),
            ("FP Normal", os.path.join(HERE, "originals", "metal_improvised_helmet_02_nrm.png"))]
    ims = [Image.open(p).convert("RGB").resize((1024, 1024), Image.LANCZOS) for _, p in srcs]
    rows = []
    for name, (x, y, s) in crops.items():
        row = Image.new("RGB", (4 * 2 * 256 + 30, 2 * s), (30, 30, 30))
        for k, im in enumerate(ims):
            row.paste(im.crop((x, y, x + s, y + s)).resize((2 * s, 2 * s), Image.NEAREST), (k * (2 * s + 10), 0))
        rows.append((name, row))
    W = rows[0][1].size[0]
    sheet = Image.new("RGB", (W, sum(r.size[1] + 24 for _, r in rows) + 24), (20, 20, 20))
    dr = ImageDraw.Draw(sheet)
    dr.text((8, 4), "   |   ".join(n for n, _ in srcs) + "   (crop of 1024 atlas, x2)", fill=(230, 230, 230))
    yy = 24
    for name, r in rows:
        dr.text((8, yy), name, fill=(255, 220, 120))
        sheet.paste(r, (0, yy + 18))
        yy += r.size[1] + 24
    sheet.save(os.path.join(OUT, "crops_v2_vs_fp.png"))

    # принятые деревянные шлемы: вырезы нормали и диффуза (центр самого рельефного места)
    tiles = []
    for wid in WOOD_HELMETS:
        d = os.path.join(STEAM, wid)
        if not os.path.exists(os.path.join(d, "_BumpMap0.png")):
            continue
        nm = Image.open(os.path.join(d, "_BumpMap0.png")).convert("RGB").resize((1024, 1024), Image.LANCZOS)
        df = Image.open(os.path.join(d, "_MainTex0.png")).convert("RGB").resize((1024, 1024), Image.LANCZOS)
        xy = np.asarray(nm).astype(np.float32) / 127.5 - 1
        e = gblur(np.linalg.norm(xy[..., :2] - gblur(xy[..., :2], 6), axis=-1), 40)
        cy, cx = np.unravel_index(np.argmax(e), e.shape)
        x, y = int(np.clip(cx - 128, 0, 768)), int(np.clip(cy - 128, 0, 768))
        t = Image.new("RGB", (2 * 256 * 2 + 10, 256 * 2), (30, 30, 30))
        t.paste(df.crop((x, y, x + 256, y + 256)).resize((512, 512), Image.NEAREST), (0, 0))
        t.paste(nm.crop((x, y, x + 256, y + 256)).resize((512, 512), Image.NEAREST), (522, 0))
        tiles.append((wid, t))
    if tiles:
        Wt = tiles[0][1].size[0]
        sh = Image.new("RGB", (Wt, sum(t.size[1] + 22 for _, t in tiles)), (20, 20, 20))
        dr = ImageDraw.Draw(sh)
        yy = 0
        for wid, t in tiles:
            dr.text((8, yy + 4), f"accepted Wood Armor Helmet {wid}: Diffuse | Normal (most relief, 256 px of 1024, x2)",
                    fill=(255, 220, 120))
            sh.paste(t, (0, yy + 20))
            yy += t.size[1] + 22
        sh.save(os.path.join(OUT, "crops_wood_helmets.png"))

    open(os.path.join(OUT, "audit.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
