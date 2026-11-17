"""Разбор модели двустволки: какой грани какой материал.

В OBJ из редактора нет usemtl: корпус (BARREL + MAIN + SIGHTS) выгружен одним объектом.
Материал каждого UV-острова определяем по текстурам: у каждой текстуры свой фон (серый у
barrel/main, чёрный у sights); остров принадлежит той текстуре, где под ним меньше всего фона.

Запуск (.venv):  python split_materials.py
Выход: source/parts/<material>.obj (Y вверх, метры, как оригинал) и uv/materials.md.
"""
import os
from collections import defaultdict

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(HERE, "originals")
OUT = os.path.join(HERE, "source", "parts")

FILES = {
    "body": "shotgun.double_double_barrel_shotgun.obj",
    "stock": "shotgun.double_dbs_stock.obj",
    "grip": "shotgun.double_grip.obj",
    "shell": "shotgun.double_shotgun_shell.obj",
}
BODY_MATS = ["barrel", "main", "sights"]


def load_obj(path):
    V, T, N, F = [], [], [], []
    for line in open(path):
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
            F.append([[int(i) - 1 if i else -1 for i in (c.split("/") + ["", ""])[:3]] for c in p[1:]])
    return np.array(V), np.array(T), np.array(N), F


def uv_islands(F):
    """Острова по общим UV-индексам (union-find)."""
    parent = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for f in F:
        t0 = f[0][1]
        for c in f[1:]:
            ra, rb = find(t0), find(c[1])
            if ra != rb:
                parent[ra] = rb
    isl = defaultdict(list)
    for i, f in enumerate(F):
        isl[find(f[0][1])].append(i)
    return list(isl.values())


def background_mask(path):
    a = np.asarray(Image.open(path).convert("RGB")).astype(int)
    # фон — самый частый цвет по краю атласа
    edge = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    vals, cnt = np.unique(edge, axis=0, return_counts=True)
    bg = vals[cnt.argmax()]
    return (np.abs(a - bg).max(-1) <= 6), tuple(bg)


def sample(mask, uv):
    h, w = mask.shape
    x = np.clip((uv[:, 0] * w).astype(int), 0, w - 1)
    y = np.clip(((1 - uv[:, 1]) * h).astype(int), 0, h - 1)
    return mask[y, x]


def edge_contrast(img, T, F, faces, off=2.5):
    """Средний перепад цвета поперёк граничных UV-рёбер острова (в пикселях текстуры)."""
    h, w = img.shape[:2]
    cnt = defaultdict(int)
    tri = {}
    for fi in faces:
        ts = [c[1] for c in F[fi]]
        for i in range(len(ts)):
            e = tuple(sorted((ts[i], ts[(i + 1) % len(ts)])))
            cnt[e] += 1
            tri[e] = ts
    diffs = []
    for e, n in cnt.items():
        if n != 1:
            continue
        a, b = T[e[0]] * [w, h], T[e[1]] * [w, h]
        c = T[tri[e]].mean(0) * [w, h]
        d = b - a
        L = np.hypot(*d)
        if L < 1:
            continue
        nrm = np.array([-d[1], d[0]]) / L
        if np.dot(c - a, nrm) > 0:
            nrm = -nrm  # наружу
        for t in np.linspace(0.15, 0.85, max(2, int(L / 4))):
            p = a + d * t
            pi, po = p - nrm * off, p + nrm * off
            xi, yi = int(np.clip(pi[0], 0, w - 1)), int(np.clip(h - 1 - pi[1], 0, h - 1))
            xo, yo = int(np.clip(po[0], 0, w - 1)), int(np.clip(h - 1 - po[1], 0, h - 1))
            diffs.append(np.abs(img[yi, xi] - img[yo, xo]).sum())
    return float(np.mean(diffs)) if diffs else 0.0


def island_mask(T, F, faces, res):
    """Пиксели атласа (res×res), которые занимает остров (центры пикселей внутри треугольников)."""
    m = np.zeros((res, res), bool)
    for fi in faces:
        p = np.array([[u * res, (1 - v) * res] for u, v in T[[c[1] for c in F[fi]]]])
        x0, y0 = np.maximum(np.floor(p.min(0)).astype(int), 0)
        x1, y1 = np.minimum(np.ceil(p.max(0)).astype(int), res - 1)
        if x1 < x0 or y1 < y0:
            continue
        ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        px, py = xs + 0.5, ys + 0.5
        a, b, c = p
        e = lambda p0, p1: (p1[0] - p0[0]) * (py - p0[1]) - (p1[1] - p0[1]) * (px - p0[0])
        w0, w1, w2 = e(b, c), e(c, a), e(a, b)
        m[y0:y1 + 1, x0:x1 + 1] |= ((w0 >= 0) & (w1 >= 0) & (w2 >= 0)) | ((w0 <= 0) & (w1 <= 0) & (w2 <= 0))
    return m


def write_obj(path, name, V, T, N, F, faces):
    vi, ti, ni = {}, {}, {}
    lines_v, lines_t, lines_n, lines_f = [], [], [], []
    for fi in faces:
        out = []
        for v, t, n in F[fi]:
            if v not in vi:
                vi[v] = len(vi) + 1
                lines_v.append("v %.6f %.6f %.6f" % tuple(V[v]))
            if t not in ti:
                ti[t] = len(ti) + 1
                lines_t.append("vt %.6f %.6f" % tuple(T[t]))
            s = "%d/%d" % (vi[v], ti[t])
            if n >= 0:
                if n not in ni:
                    ni[n] = len(ni) + 1
                    lines_n.append("vn %.6f %.6f %.6f" % tuple(N[n]))
                s += "/%d" % ni[n]
            out.append(s)
        lines_f.append("f " + " ".join(out))
    with open(path, "w") as fh:
        fh.write("o %s\n" % name)
        fh.write("\n".join(lines_v + lines_t + lines_n + lines_f) + "\n")


def main():
    os.makedirs(OUT, exist_ok=True)
    report = ["# Материалы и части модели (split_materials.py)", ""]

    V, T, N, F = load_obj(os.path.join(ORIG, FILES["body"]))
    masks = {m: background_mask(os.path.join(ORIG, f"{m}_bc.png")) for m in BODY_MATS}
    texs = {m: np.asarray(Image.open(os.path.join(ORIG, f"{m}_bc.png")).convert("RGB")).astype(float)
            for m in BODY_MATS}
    islands = uv_islands(F)
    assign = defaultdict(list)
    rows = []
    # Свести всё вместе: острова от больших к малым; каждый — в тот материал, где он не лежит на фоне,
    # не налезает на уже разложенные острова этого материала (в атласе одного материала куски не
    # перекрываются, кроме копий с общими vt — они внутри одного «острова») и где край совпадает с краем
    # нарисованного куска. Первая версия брала только фон + край — гайки корпуса ушли в стволы.
    R = 512
    occ = {m: np.zeros((R, R), bool) for m in BODY_MATS}
    order = sorted(range(len(islands)), key=lambda k: -len(islands[k]))
    for k in order:
        faces = islands[k]
        # точки: центры треугольников + вершины (сдвинутые к центру, чтобы не попасть в кайму)
        pts = []
        for fi in faces:
            uv = T[[c[1] for c in F[fi]]]
            c = uv.mean(0)
            pts.append(c)
            pts.extend(c + (uv - c) * 0.7)
        pts = np.array(pts)
        bgfrac = {m: float(sample(masks[m][0], pts).mean()) for m in BODY_MATS}
        edge = {m: edge_contrast(texs[m], T, F, faces) for m in BODY_MATS}
        # 1) остров не должен лежать на фоне; 2) из оставшихся — где граница острова
        #    совпадает с краем нарисованного куска (резкий перепад цвета поперёк границы)
        mask = island_mask(T, F, faces, R)
        npx = max(mask.sum(), 1)
        ovl = {m: float((occ[m] & mask).sum() / npx) for m in BODY_MATS}
        emax = max(edge.values()) or 1.0
        cost = {m: 2.0 * bgfrac[m] + 3.0 * ovl[m] - edge[m] / emax for m in BODY_MATS}
        best = min(cost, key=cost.get)
        occ[best] |= mask
        bgfrac = {m: (round(bgfrac[m], 2), round(edge[m], 1), round(ovl[m], 2)) for m in BODY_MATS}
        assign[best].extend(faces)
        vs = V[[c[0] for fi in faces for c in F[fi]]]
        rows.append((best, len(faces), bgfrac, vs.min(0), vs.max(0)))

    report.append("Корпус `%s`: %d граней, %d UV-островов." % (FILES["body"], len(F), len(islands)))
    report.append("Фон текстур: " + ", ".join(f"{m} {masks[m][1]}" for m in BODY_MATS))
    report.append("")
    report.append("| материал | граней | островов | неуверенных |")
    report.append("|---|---:|---:|---:|")
    for m in BODY_MATS:
        rs = [r for r in rows if r[0] == m]
        unsure = sum(1 for r in rs if r[2][m][0] > 0.3 or r[2][m][2] > 0.2)
        report.append(f"| {m} | {len(assign[m])} | {len(rs)} | {unsure} |")
        write_obj(os.path.join(OUT, f"{m}.obj"), m, V, T, N, F, assign[m])
    report.append("")

    for part in ["stock", "grip", "shell"]:
        V2, T2, N2, F2 = load_obj(os.path.join(ORIG, FILES[part]))
        write_obj(os.path.join(OUT, f"{part}.obj"), part, V2, T2, N2, F2, range(len(F2)))
        report.append(f"- `{part}`: {len(F2)} граней, bbox {V2.min(0).round(3)} … {V2.max(0).round(3)}")

    report.append("")
    # патроны: своей вкладки нет — какая текстура их? (тот же разбор фона и края)
    V3, T3, N3, F3 = load_obj(os.path.join(ORIG, FILES["shell"]))
    sh = []
    for m in BODY_MATS:
        pts = np.array([T3[[c[1] for c in f]].mean(0) for f in F3])
        sh.append(f"{m}: фон {sample(masks[m][0], pts).mean():.2f}, край {edge_contrast(texs[m], T3, F3, range(len(F3))):.1f}")
    report.append("Патроны (shell) по текстурам корпуса — " + "; ".join(sh))
    report.append("")
    report.append("Неуверенные острова: на фоне > 30 % или налезают на другие > 20 % "
                  "(материал, граней, {текстура: (доля фона, перепад на краю, перекрытие)}, bbox):")
    for r in rows:
        if r[2][r[0]][0] > 0.3 or r[2][r[0]][2] > 0.2:
            report.append(f"- {r[0]} {r[1]} {r[2]} {r[3].round(3)} {r[4].round(3)}")
    os.makedirs(os.path.join(HERE, "uv"), exist_ok=True)
    with open(os.path.join(HERE, "uv", "materials.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(report) + "\n")
    print("\n".join(report))


if __name__ == "__main__":
    main()
