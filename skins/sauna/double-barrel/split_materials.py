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
    for k, faces in enumerate(islands):
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
        ok = [m for m in BODY_MATS if bgfrac[m] < 0.3] or BODY_MATS
        best = max(ok, key=lambda m: edge[m])
        bgfrac = {m: (round(bgfrac[m], 2), round(edge[m], 1)) for m in BODY_MATS}
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
        unsure = sum(1 for r in rs if sorted(v[1] for v in r[2].values())[-2] > 0.6 * r[2][m][1])
        report.append(f"| {m} | {len(assign[m])} | {len(rs)} | {unsure} |")
        write_obj(os.path.join(OUT, f"{m}.obj"), m, V, T, N, F, assign[m])
    report.append("")

    for part in ["stock", "grip", "shell"]:
        V2, T2, N2, F2 = load_obj(os.path.join(ORIG, FILES[part]))
        write_obj(os.path.join(OUT, f"{part}.obj"), part, V2, T2, N2, F2, range(len(F2)))
        report.append(f"- `{part}`: {len(F2)} граней, bbox {V2.min(0).round(3)} … {V2.max(0).round(3)}")

    report.append("")
    report.append("Неуверенные острова: у второй текстуры перепад на границе > 60 % от лучшей "
                  "(материал, граней, {текстура: (доля фона, перепад)}, bbox):")
    for r in rows:
        if sorted(v[1] for v in r[2].values())[-2] > 0.6 * r[2][r[0]][1]:
            report.append(f"- {r[0]} {r[1]} {r[2]} {r[3].round(3)} {r[4].round(3)}")
    os.makedirs(os.path.join(HERE, "uv"), exist_ok=True)
    with open(os.path.join(HERE, "uv", "materials.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(report) + "\n")
    print("\n".join(report))


if __name__ == "__main__":
    main()
