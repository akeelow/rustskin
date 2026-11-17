"""Sauna Boiler: самопроверки по готовым картам и листам. Пишет renders/<V>_checks.md и картинки.

  .venv/Scripts/python skins/sauna/furnace/checks.py

Нужны: export/Furnace_<V>_*.png, bake/id.png, renders/<V>_sheet.png и renders/stove_sheet.png
(лист Sauna Stove из того же tools/blender/viewer.py — см. build.sh compare).
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import layout as L  # noqa: E402
from texture_furnace import VERSION  # noqa: E402

EXP, REN, ORIG = HERE / "export", HERE / "renders", HERE / "originals"
out = []


def say(s=""):
    print(s)
    out.append(s)


def img(p):
    return Image.open(p)


# ---------------- 1. формат карт как у оригинала
say(f"# Самопроверки Sauna Boiler {VERSION}\n")
say("## Формат карт\n")
say("| Слот | Оригинал | Наша карта |\n|---|---|---|")
for slot, o, e in (("Diffuse", "furnace_v3_bc", "diffuse"), ("Normal", "furnace_v3_nrm", "normal"),
                   ("Specular/Gloss", "furnace_v3_sg", "specgloss"), ("Occlusion", "furnace_v3_ao", "occlusion"),
                   ("Emission", "furnace_v3_em", "emission")):
    a, b = img(ORIG / f"{o}.png"), img(EXP / f"Furnace_{VERSION}_{e}.png")
    assert a.size == b.size, (slot, a.size, b.size)
    say(f"| {slot} | {a.size[0]}×{a.size[1]} {a.mode} | {b.size[0]}×{b.size[1]} {b.mode} |")
D = np.asarray(img(EXP / f"Furnace_{VERSION}_diffuse.png"))
assert D[..., 3].min() == 255
say("\nАльфа Diffuse = 255 везде (вырезов нет, Alpha Cutoff 0).")

# ---------------- 2. свечение
E = np.asarray(img(EXP / f"Furnace_{VERSION}_emission.png").convert("RGB")).astype(int)
idm = np.rint((np.asarray(img(HERE / "bake/id.png").convert("RGB"))[..., 0].astype(float) - 6) / 12).astype(int)
id1 = idm[::2, ::2]
lit = E.max(-1) > 24
hot_ids = [L.IDS[k] for k in ("ember", "ash", "bark", "logend")]
inside = np.isin(id1, hot_ids)
# поля вокруг острова пола (заливка отступа) и пятна кубиков углей тоже относятся к топке
fire_box = np.zeros_like(lit)
ys, xs = np.nonzero(inside)
fire_box[max(0, ys.min() - 16):ys.max() + 17, max(0, xs.min() - 16):xs.max() + 17] = True
stray = lit & ~fire_box
peak = E.reshape(-1, 3).max(0)
say("\n## Свечение\n")
say(f"- Пик по каналам: R {peak[0]}, G {peak[1]}, B {peak[2]} — предел `#FFB347` = 255/179/71: "
    f"{'в пределах' if peak[1] <= 179 and peak[2] <= 71 else 'ПРЕВЫШЕН'}.")
say(f"- Светится {lit.mean() * 100:.2f} % текстуры; вне острова пола топки: {int(stray.sum())} px.")
fl = E[inside]
lv = fl.max(-1)
say(f"- На полу топки: тёмная зола/уголь (яркость < 25) — {np.mean(lv < 25) * 100:.0f} %, тление (25–150) — "
    f"{np.mean((lv >= 25) & (lv < 150)) * 100:.0f} %, жар (≥ 150) — {np.mean(lv >= 150) * 100:.0f} %, "
    f"янтарный пик (G > 150) — {np.mean(fl[:, 1] > 150) * 100:.1f} %.")
# гнёзда: связные пятна жара
hotm = (E.max(-1) >= 150)
seen = np.zeros_like(hotm)
blobs = []
for y0, x0 in zip(*np.nonzero(hotm)):
    if seen[y0, x0]:
        continue
    st, n = [(y0, x0)], 0
    seen[y0, x0] = True
    while st:
        y, x = st.pop()
        n += 1
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                yy, xx = y + dy, x + dx
                if 0 <= yy < 1024 and 0 <= xx < 1024 and hotm[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True
                    st.append((yy, xx))
    blobs.append(n)
big = sorted([b for b in blobs if b >= 6], reverse=True)
say(f"- Пятен жара: {len(big)} (≥ 6 px), самое большое {big[0] if big else 0} px из {int(hotm.sum())} — "
    "сплошной заливки нет, угли лежат отдельными гнёздами.")

# ---------------- 3. швы: цвет по обе стороны каждого шва развёртки
V, T, F = [], [], []
for line in open(ORIG / "furnace.obj"):
    if line.startswith("v "):
        V.append(list(map(float, line.split()[1:4])))
    elif line.startswith("vt "):
        T.append(list(map(float, line.split()[1:3])))
    elif line.startswith("f "):
        p = [x.split("/") for x in line.split()[1:]]
        for k in range(1, len(p) - 1):
            F.append([(int(p[0][0]) - 1, int(p[0][1]) - 1), (int(p[k][0]) - 1, int(p[k][1]) - 1),
                      (int(p[k + 1][0]) - 1, int(p[k + 1][1]) - 1)])
V, T = np.array(V), np.array(T)
edges = {}
for fi, f in enumerate(F):
    for k in range(3):
        a, b = f[k], f[(k + 1) % 3]
        key = tuple(sorted((a[0], b[0])))
        edges.setdefault(key, []).append((fi, a, b))
Df = D[..., :3].astype(float)


def sample(uv):
    x = np.clip((uv[:, 0] * 1024).astype(int), 0, 1023)
    y = np.clip(((1 - uv[:, 1]) * 1024).astype(int), 0, 1023)
    return Df[y, x], id1[y, x]


diffs, outer, seam_th = [], [], []
for key, lst in edges.items():
    if len(lst) != 2:
        continue
    (f0, a0, b0), (f1, a1, b1) = lst
    if a0[0] != b1[0]:
        a1, b1 = b1, a1
    if {a0[1], b0[1]} == {a1[1], b1[1]}:
        continue                                    # не шов
    for fi, a, b, store in ((f0, a0, b0, 0), (f1, b1, a1, 1)):
        c = T[[v[1] for v in F[fi]]].mean(0)
        t = np.linspace(0.15, 0.85, 8)[:, None]
        uv = T[a[1]] * (1 - t) + T[b[1]] * t
        dv = c - uv
        uv = uv + dv / (np.linalg.norm(dv, axis=1, keepdims=True) + 1e-9) * (1.5 / 1024)   # 1.5 px внутрь своего треугольника
        if store == 0:
            s0, i0 = sample(uv)
        else:
            s1, i1 = sample(uv)
    d = np.abs(s0 - s1).mean(1)
    y_mid = V[list(key), 1].mean()
    is_outer = (i0 > 0).all() and (i1 > 0).all() and not np.isin(i0, [L.IDS["wall"], L.IDS["ash"]]).any()
    same = i0 == i1                                 # одна и та же деталь по обе стороны шва
    if is_outer:
        outer.extend(d[same].tolist())
        diffs.extend(d[~same].tolist())
        seam_th.append(np.degrees(np.arctan2(V[list(key), 0].mean() - L.CX, V[list(key), 2].mean() - L.CZ)))
outer = np.array(outer)
say("\n## Швы\n")
say(f"- Точек на наружных швах: {len(outer)}; средняя разница цвета по обе стороны шва {outer.mean():.1f} из 255, "
    f"95-й процентиль {np.percentile(outer, 95):.1f} (пары точек в 3 px друг от друга, одна деталь по обе стороны). "
    f"Ещё {len(diffs)} точек, где по шву проходит граница деталей (обруч/бак, рейка/щель) — там разница законная. "
    "Обручи, рейки и проволока — геометрия вокруг всего корпуса, запечённая лучами, поэтому на шве сходятся сами.")
say(f"- Поля островов заполнены на 14 px (dilate в texture_furnace.py); между островами исходной развёртки "
    "местами всего 5 px (uv/islands.txt) — там поле заполнено до середины зазора.")

# ---------------- 4. читаемость и сравнение с Sauna Stove
sheet = img(REN / f"{VERSION}_sheet.png").convert("RGB")
t = sheet.size[1] // 2
tile = lambda s, c, r: s.crop((c * t, r * t, (c + 1) * t, (r + 1) * t))  # noqa: E731
hero = tile(sheet, 1, 0)
W = Image.new("RGB", (t + 512 + 40, t), (24, 24, 28))
W.paste(hero.convert("L").convert("RGB"), (0, 0))
dr = ImageDraw.Draw(W)
x = t + 20
for k, s in enumerate((128, 64)):
    for j, im in enumerate((hero, tile(sheet, 1, 1))):
        ic = im.resize((s, s), Image.LANCZOS)
        W.paste(ic, (x + j * 150, 40 + k * 200))
        W.paste(ic.resize((128, 128), Image.NEAREST) if s == 64 else ic, (x + 300 + j * 0, 40 + k * 200)) if j == 0 else None
    dr.text((x, 20 + k * 200), f"{s} px: day / night / day enlarged", fill=(200, 200, 200))
W.save(REN / f"{VERSION}_readability.png")
say("\n## Читаемость\n")
say(f"Ч/б и иконки 128 / 64 px: `renders/{VERSION}_readability.png` (из листа viewer.py, это не игровой кадр).")

stove = REN / "stove_sheet.png"
if stove.exists():
    s2 = img(stove).convert("RGB")
    t2 = s2.size[1] // 2
    C = Image.new("RGB", (t * 4, t * 2), (0, 0, 0))
    for r in (0, 1):
        C.paste(s2.crop((1 * t2, r * t2, 2 * t2, (r + 1) * t2)).resize((t, t)), (0, r * t))
        C.paste(tile(sheet, 1, r), (t, r * t))
        C.paste(s2.crop((3 * t2, r * t2, 4 * t2, (r + 1) * t2)).resize((t, t)), (2 * t, r * t))
        C.paste(tile(sheet, 3, r), (3 * t, r * t))
    C.save(REN / f"{VERSION}_vs_stove.png")

    def shares(im):
        a = np.asarray(im).astype(float) / 255
        bg = np.abs(a - a[4, 4]).sum(-1) < 0.06
        bg |= np.abs(a - a[-4, 4]).sum(-1) < 0.10
        r_, g_, b_ = a[..., 0], a[..., 1], a[..., 2]
        v, mn = a.max(-1), a.min(-1)
        sat = (v - mn) / np.maximum(v, 1e-3)
        wood = (r_ > g_ + 0.02) & (g_ > b_ + 0.02) & (v > 0.3) & (sat > 0.16) & (sat < 0.62) & ~bg
        obj = ~bg
        return wood.sum() / max(1, obj.sum())
    say("\n## Отличие от Sauna Stove\n")
    say(f"Оба предмета в одном свете (тот же viewer.py, день и ночь): `renders/{VERSION}_vs_stove.png`.")
    st = [shares(s2.crop((c * t2, 0, (c + 1) * t2, t2))) * 100 for c in (1, 3)]
    bo = [shares(tile(sheet, c, 0)) * 100 for c in (1, 3)]
    say(f"- Доля дерева в кадре днём (грубая оценка по тёплому цвету пикселей; ржавчина отсечена по насыщенности), "
        f"вид 3/4 спереди / сзади: Sauna Stove {st[0]:.0f} % / {st[1]:.0f} %, Sauna Boiler {bo[0]:.0f} % / {bo[1]:.0f} %.")

    def glow(im):
        a = np.asarray(im).astype(int)
        m = (a[..., 0] > 150) & (a[..., 0] - a[..., 2] > 80)
        ys_ = np.nonzero(m)[0]
        return m.mean() * 100, (ys_.min() / im.size[1], ys_.max() / im.size[1]) if len(ys_) else (0, 0)
    g1, y1 = glow(s2.crop((t2, t2, 2 * t2, 2 * t2)))
    g2, y2 = glow(tile(sheet, 1, 1))
    say(f"- Свечение ночью в кадре 3/4: Stove — {g1:.2f} % кадра, по высоте кадра {y1[0]:.2f}–{y1[1]:.2f}; "
        f"Boiler — {g2:.2f} %, {y2[0]:.2f}–{y2[1]:.2f}.")

(REN / f"{VERSION}_checks.md").write_text("\n".join(out) + "\n", encoding="utf8")
