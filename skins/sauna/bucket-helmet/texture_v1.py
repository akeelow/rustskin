"""Sauna Bucket: карты под слоты редактора из запечённого (bake/) — палитра сета, мокрое, разводы, ржавчина.

Запуск (.venv):  python skins/sauna/bucket-helmet/texture_v1.py [--ver v1]
Вход:  bake/{normal,color,id,msk,poshi,poslo,ao}.png (4096), bake/aowide.png (1024), bake/layout.json,
       uv/ids_4096.png
Выход: export/SaunaBucket_<ver>_{diffuse,normal,specgloss,occlusion,fuzzmask}.png — 1024 (Lanczos из 4096).

Что здесь только цветом (у этого нет формы, PLAN.md, раздел 4): тон дерева сухое → мокрое, мокрое кольцо на
днище, белые минеральные разводы, ржавые потёки (источники — положения заклёпок, гвоздей и кромок обручей из
геометрии), облезлая синяя краска на вкладыше, пыль и засаленность. Остальное — из запечённой геометрии:
цвет деталей (цвета вершин), впадины и свежие срезы (маски вершин), AO.
"""
import argparse
import json
import os

import numpy as np
from PIL import Image

from noise_np import fbm, vnoise

HERE = os.path.dirname(os.path.abspath(__file__))
BK = os.path.join(HERE, "bake")
EX = os.path.join(HERE, "export")
S = 2048          # рабочий размер для цвета (вдвое больше экспорта); нормаль — из 4096
OUTSZ = {"diffuse": 1024, "normal": 1024, "specgloss": 1024, "occlusion": 1024, "fuzzmask": 1024}
IDS = {"wood": 1, "endgrain": 2, "fresh": 3, "iron": 4, "rivet": 5, "nail": 6, "tin": 7, "rope": 8,
       "leaf": 9, "resin": 10, "wire": 11, "lead": 12, "paint": 13}
POS_LO = np.array([-0.17, 0.10, -0.17])
POS_HI = np.array([0.17, 0.42, 0.17])


def hexc(h):
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255


def load(name, mode="RGB", size=S, nearest=False):
    im = Image.open(os.path.join(BK, name)).convert(mode)
    if im.size != (size, size):
        im = im.resize((size, size), Image.NEAREST if nearest else (Image.BOX if im.size[0] > size else Image.BILINEAR))
    return np.asarray(im).astype(np.float32) / 255


def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def blur(a, r):
    if r < 1:
        return a
    for _ in range(2):
        k = 2 * r + 1
        c = np.cumsum(np.pad(a, ((r + 1, r), (0, 0)) + ((0, 0),) * (a.ndim - 2), mode="edge"), axis=0)
        a = (c[k:] - c[:-k]) / k
        c = np.cumsum(np.pad(a, ((0, 0), (r + 1, r)) + ((0, 0),) * (a.ndim - 2), mode="edge"), axis=1)
        a = (c[:, k:] - c[:, :-k]) / k
    return a


def dilate_fill(arr, mask, n):
    a = arr.copy()
    m = mask.copy()
    for _ in range(n):
        acc = np.zeros_like(a)
        cnt = np.zeros(m.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            sm = np.roll(np.roll(m, dy, 0), dx, 1)
            sa = np.roll(np.roll(a, dy, 0), dx, 1)
            acc += sa * sm[..., None] if a.ndim == 3 else sa * sm
            cnt += sm
        grow = (~m) & (cnt > 0)
        if a.ndim == 3:
            a[grow] = acc[grow] / cnt[grow][:, None]
        else:
            a[grow] = acc[grow] / cnt[grow]
        m = m | grow
    return a


def mix(a, b, t):
    t = np.asarray(t, np.float32)
    if t.ndim >= 1 and t.shape[-1] != 3:
        t = t[..., None]
    return a * (1 - t) + b * t


# палитра (sRGB 0..1)
WOOD_SET = np.array([148, 132, 108], np.float32) / 255     # сухая осина в тон кресла сета (замер 143/128/106)
WOOD_WET = hexc("7A5A3C")
WOOD_OLD = hexc("45332A")
FRESH = hexc("D6C29C")
IRON = hexc("2A2826")
EDGE = hexc("57524C")
RUST = hexc("8C4A26")
RUST_DARK = hexc("5A2E18")
MINERAL = hexc("D2CEC3")
PAINT = hexc("3B6E9C")          # синяя краска старого ведра, выцветшая
TIN = hexc("8E9092")


def grade_to(col, mask, target, k=0.8):
    if mask.sum() < 50:
        return col
    m = col[mask].mean(0)
    lm, lt = m.mean(), target.mean()
    l = col.mean(-1, keepdims=True)
    c = col - l
    new = l * (lt / lm) + (c - (m - lm)) * k + (target - lt)
    return np.where(mask[..., None], np.clip(new, 0, 1), col)


def streaks(src, isl, down, length, seed):
    """Потёки от источников src по столбцам (вниз по миру = вниз по строкам на острове 1, v растёт с y)."""
    step = 1 if down else -1
    acc = src.copy()
    cur = src.copy()
    decay = 1 - 1.0 / length
    for _ in range(int(length * 2.2)):
        cur = np.roll(cur, step, 0) * decay
        cur *= isl
        acc = np.maximum(acc, cur)
    cols = np.arange(S)[None, :]
    lines = vnoise(np.stack([cols / 7.0 + 0 * np.arange(S)[:, None], np.arange(S)[:, None] / 900.0 + 0 * cols,
                             np.full((S, S), seed, np.float32)], -1), seed)
    return acc * smooth((lines - 0.35) / 0.4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ver", default="v1")
    a = ap.parse_args()
    ids_img = np.asarray(Image.open(os.path.join(HERE, "uv", "ids_4096.png")).convert("RGB")).astype(np.int32)
    isl = (ids_img[..., 0] + ids_img[..., 1] * 256)[::4096 // S, ::4096 // S]
    inside = isl > 0
    print("load", flush=True)
    col = load("color.png")
    idr = load("id.png", nearest=True)[..., 0]
    ID = np.round((idr * 255 - 8) / 16).astype(np.int32)
    msk = load("msk.png")
    Rm, Gm, Bm = msk[..., 0], msk[..., 1], msk[..., 2]
    nrm = load("normal.png", size=4096)
    ao = load("ao.png")[..., 0]
    aow = load("aowide.png")[..., 0]
    q = (load("poshi.png", nearest=True) * 255 * 256 + load("poslo.png", nearest=True) * 255) / 65535
    P = POS_LO + q * (POS_HI - POS_LO)
    Y = P[..., 1]
    lay = json.load(open(os.path.join(BK, "layout.json")))
    wall = isl == 1
    top = isl == 3
    inner = np.isin(isl, (7, 37))
    is_wood = np.isin(ID, (IDS["wood"], IDS["endgrain"])) & inside
    is_fresh = (ID == IDS["fresh"]) & inside
    is_iron = np.isin(ID, (IDS["iron"], IDS["rivet"], IDS["nail"])) & inside
    is_tin = (ID == IDS["tin"]) & inside
    is_wire = (ID == IDS["wire"]) & inside
    is_rope = (ID == IDS["rope"]) & inside
    is_leaf = (ID == IDS["leaf"]) & inside
    rng = np.random.default_rng(5)

    # ---------------------------------------------------------------- дерево
    print("wood", flush=True)
    c = grade_to(col, is_wood & (Y < 0.33) & wall, WOOD_SET, 0.95)
    c = np.where(is_wood[..., None] & ~(wall & (Y < 0.33))[..., None], grade_to(col, is_wood, WOOD_SET, 0.95), c)
    zc = 0.0128
    rho_top = np.sqrt(P[..., 0] ** 2 + (P[..., 2] - zc) ** 2)
    n_big = fbm(np.stack([P[..., 0] * 18, P[..., 1] * 18, P[..., 2] * 18], -1), 4, 7)
    n_mid = fbm(np.stack([P[..., 0] * 60, P[..., 1] * 60, P[..., 2] * 60], -1), 3, 8)
    # мокрое (решение 1): макушка и утор — шайка стояла днищем в воде; верх стенки темнеет к макушке;
    # нижний край чуть темнее (дождь на голове)
    wet = np.zeros((S, S), np.float32)
    wet += wall * (0.55 * smooth((Y - 0.30) / 0.09) + 0.22 * smooth((0.20 - Y) / 0.05))
    wet += top * (0.55 + 0.25 * smooth((rho_top - 0.085) / 0.03))
    wet += inner * 0.35
    wet *= 0.8 + 0.4 * n_big
    wet = np.clip(wet + 0.12 * (n_mid - 0.5), 0, 1)
    wood_m = (is_wood | is_fresh)
    oldt = smooth((wet - 0.65) / 0.3) * (is_wood)
    c = np.where(is_wood[..., None], mix(c, c * (WOOD_WET / WOOD_SET), wet * 0.85), c)
    c = np.where(is_wood[..., None], mix(c, WOOD_OLD * (0.9 + 0.2 * n_mid[..., None]), oldt * 0.6), c)
    # мокрое пятно на днище: шайка стояла в воде — снаружи от неровной границы темнее, по границе слабая линия
    # высохшей воды (v1: две ровные окружности читались мишенью)
    ang = np.arctan2(P[..., 0], P[..., 2] - zc)
    edge_r = 0.066 + 0.010 * (fbm(np.stack([np.cos(ang) * 2.5, np.sin(ang) * 2.5, np.full_like(ang, 3.3)], -1), 3, 17) - 0.5) * 2
    outer = smooth((rho_top - edge_r) / 0.012) * top
    tide_l = np.exp(-((rho_top - edge_r) / 0.0022) ** 2) * top * (0.5 + 0.5 * fbm(np.stack([np.cos(ang) * 9, np.sin(ang) * 9, np.full_like(ang, 1.1)], -1), 3, 18))
    c = mix(c, c * 0.72, outer * 0.7 * is_wood)
    c = mix(c, c * 0.8, tide_l * 0.45 * is_wood)
    # свежий срез: светлый, чуть грязный у самой кромки
    c = np.where(is_fresh[..., None], mix(col, FRESH, 0.6) * (0.92 + 0.1 * n_mid[..., None]), c)
    # белые минеральные разводы: линии высохших капель на дереве (тонко, полупрозрачно) и на макушке
    drops = vnoise(np.stack([P[..., 0] * 140, P[..., 1] * 40, P[..., 2] * 140], -1), 13)
    tide = np.exp(-((wet - 0.42) / 0.03) ** 2) * smooth((drops - 0.55) / 0.2)
    minr = np.clip(0.35 * tide + 0.25 * smooth((fbm(np.stack([P[..., 0] * 30, P[..., 1] * 9, P[..., 2] * 30], -1), 3, 14) - 0.62) / 0.15), 0, 1)
    minr = minr * wood_m * (wall | top)
    c = mix(c, MINERAL, minr * 0.45)
    # засаленность на висках (где надевают)
    th = np.degrees(np.arctan2(P[..., 0], P[..., 2] - 0.008))
    grease = wall * np.exp(-((np.abs(th) - 90) / 22) ** 2) * smooth((0.24 - Y) / 0.06)
    c = mix(c, c * 0.8, grease * 0.5 * is_wood)

    # ---------------------------------------------------------------- ржавчина и потёки
    print("rust", flush=True)
    srcB = np.where(wall, Bm, 0).astype(np.float32)
    src = smooth((srcB - 0.25) / 0.5)
    down = streaks(src, wall.astype(np.float32), True, 110, 31)
    up = streaks(src * 0.7, wall.astype(np.float32), False, 70, 32)   # старые — к днищу (шайка стояла днищем вниз)
    rs = np.clip(0.75 * down + 0.4 * up, 0, 1) * (is_wood | is_fresh)
    rs *= 0.7 + 0.6 * n_mid
    c = mix(c, mix(RUST, RUST_DARK, n_mid * 0.6) * (0.85 + 0.2 * c.mean(-1, keepdims=True)), np.clip(rs, 0, 1) * 0.55)

    # ---------------------------------------------------------------- железо
    print("iron", flush=True)
    rust_iron = np.clip(Gm * 1.1 + 0.08 * smooth((n_mid - 0.6) / 0.3), 0, 1)
    ci = IRON * (0.85 + 0.3 * n_big[..., None])
    ci = mix(ci, EDGE, np.clip(Rm, 0, 1) * 0.8)
    ci = mix(ci, mix(RUST, RUST_DARK, n_mid), rust_iron * 0.75)
    iron_min = smooth((fbm(np.stack([P[..., 0] * 50, P[..., 1] * 120, P[..., 2] * 50], -1), 3, 15) - 0.6) / 0.15)
    ci = mix(ci, MINERAL * 0.7, iron_min * 0.35)
    c = np.where(is_iron[..., None], ci, c)
    # дробь (свинец)
    c = np.where((ID == IDS["lead"])[..., None] & inside[..., None], hexc("55575A") * (0.9 + 0.2 * n_mid[..., None]), c)
    # смола
    c = np.where((ID == IDS["resin"])[..., None] & inside[..., None], col * 0.9, c)

    # ---------------------------------------------------------------- жесть вкладыша и латки
    print("tin", flush=True)
    paint_n = fbm(np.stack([P[..., 0] * 70, P[..., 1] * 70, P[..., 2] * 70], -1), 5, 21)
    paint_n = paint_n + 0.12 * (vnoise(np.stack([P[..., 0] * 400, P[..., 1] * 400, P[..., 2] * 400], -1), 22) - 0.5)
    paint = smooth((paint_n - 0.40) / 0.025) * inner     # краска держится на ~70 %, облезла сколами
    chip_edge = np.exp(-((paint_n - 0.40) / 0.008) ** 2) * inner
    ct = TIN * (0.8 + 0.3 * n_mid[..., None])
    ct = mix(ct, PAINT * (0.85 + 0.25 * n_big[..., None]), paint)
    ct = mix(ct, RUST_DARK, np.clip(chip_edge * 0.6 + Gm * 0.6, 0, 1))
    ct = mix(ct, EDGE * 1.4, Rm * 0.5)
    c = np.where(is_tin[..., None], ct, c)

    # ---------------------------------------------------------------- проволока, верёвка, лист
    cw = mix(col * 0.9, mix(RUST, RUST_DARK, 0.4), np.clip(Gm * 0.9, 0, 1) * 0.7)
    cw = mix(cw, MINERAL, smooth((n_mid - 0.65) / 0.2) * 0.4)
    c = np.where(is_wire[..., None], cw, c)
    c = np.where(is_rope[..., None], col * (0.85 + 0.2 * n_mid[..., None]) * 0.92, c)
    lg = col * 0.78
    lg = lg.mean(-1, keepdims=True) * 0.2 + lg * 0.8          # мокрый лист темнее и глуше (v1 был ярко-зелёный)
    c = np.where(is_leaf[..., None], lg, c)

    # ---------------------------------------------------------------- AO в цвет
    occ_small = np.clip(ao, 0, 1)
    c = c * (0.45 + 0.55 * occ_small[..., None]) ** 1.0
    c = c * (0.75 + 0.25 * aow[..., None])
    c = np.clip(c, 0, 1)

    # ---------------------------------------------------------------- блик и глянец (Unity Specular)
    print("spec", flush=True)
    spec = np.full((S, S, 3), 0.05, np.float32)       # дерево — диэлектрик
    gloss = np.full((S, S), 0.22, np.float32)
    gloss = np.where(is_wood | is_fresh, 0.18 + 0.32 * wet + 0.06 * n_mid, gloss)
    gloss = np.where(is_fresh, 0.14, gloss)
    gloss -= 0.12 * minr
    iron_spec = 0.28 + 0.18 * Rm - 0.2 * rust_iron
    spec = np.where(is_iron[..., None], np.repeat(iron_spec[..., None], 3, -1) * np.array([1.0, 0.97, 0.93]), spec)
    gloss = np.where(is_iron, 0.30 + 0.2 * Rm - 0.18 * rust_iron, gloss)
    tin_spec = np.where(paint > 0.5, 0.06, 0.45)
    spec = np.where(is_tin[..., None], np.repeat(tin_spec[..., None], 3, -1), spec)
    gloss = np.where(is_tin, np.where(paint > 0.5, 0.35, 0.45) - 0.2 * Gm, gloss)
    spec = np.where(is_wire[..., None], 0.32 - 0.2 * Gm[..., None], spec)
    gloss = np.where(is_wire, 0.35 - 0.2 * Gm, gloss)
    spec = np.where((ID == IDS["lead"])[..., None], 0.38, spec)
    gloss = np.where(ID == IDS["lead"], 0.4, gloss)
    gloss = np.where(is_rope, 0.12, gloss)
    spec = np.where(is_rope[..., None], 0.03, spec)
    gloss = np.where(is_leaf, 0.52, gloss)
    spec = np.where(is_leaf[..., None], 0.07, spec)
    gloss = np.where((ID == IDS["resin"]) & inside, 0.8, gloss)
    spec = np.where(((ID == IDS["resin"]) & inside)[..., None], 0.08, spec)
    gloss *= 0.75 + 0.25 * occ_small               # во впадинах матовее
    gloss = np.clip(gloss, 0, 1)

    # ---------------------------------------------------------------- нормаль: детали ×1.3
    n = nrm * 2 - 1
    n[..., :2] *= 1.3
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-8
    n = n * 0.5 + 0.5
    inside4 = np.repeat(np.repeat(inside, 4096 // S, 0), 4096 // S, 1)
    n = np.where(inside4[..., None], n, np.array([0.5, 0.5, 1.0])).astype(np.float32)

    # ---------------------------------------------------------------- fuzz
    fz = np.zeros((S, S), np.float32)
    fz = np.where(is_wood, 0.22 * (1 - wet), fz)
    fz = np.where(is_fresh, 0.35, fz)
    fz = np.where(is_rope, 1.0, fz)
    fz = np.where(is_leaf, 0.15, fz)

    # ---------------------------------------------------------------- сборка: 4096 → 1024, отступы
    os.makedirs(EX, exist_ok=True)
    pre = os.path.join(EX, f"SaunaBucket_{a.ver}")
    small = np.asarray(Image.fromarray(inside.astype(np.uint8) * 255).resize((1024, 1024), Image.BOX)) > 40

    def down(arr, size):
        arr = np.clip(arr, 0, 1)
        if arr.ndim == 2:
            out = np.asarray(Image.fromarray(arr.astype(np.float32), "F").resize((size, size), Image.LANCZOS))
        else:
            out = np.stack([np.asarray(Image.fromarray(arr[..., k].astype(np.float32), "F").resize((size, size), Image.LANCZOS))
                            for k in range(arr.shape[-1])], -1)
        return np.clip(out, 0, 1)

    def fin(arr, size):
        d = down(arr, size)
        m = small if size == 1024 else np.asarray(Image.fromarray(small.astype(np.uint8) * 255).resize((size, size))) > 127
        return dilate_fill(d.astype(np.float32), m, 16)

    def save(arr, path, mode):
        Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), mode).save(path)
        print("  ->", os.path.basename(path), flush=True)

    print("write", flush=True)
    d = fin(c, 1024)
    save(np.concatenate([d, np.ones_like(d[..., :1])], -1), f"{pre}_diffuse.png", "RGBA")
    nn = fin(n, 1024) * 2 - 1
    nn /= np.linalg.norm(nn, axis=-1, keepdims=True) + 1e-8
    nn = nn * 0.5 + 0.5
    save(np.concatenate([nn[..., :2], np.ones_like(nn[..., :2])], -1), f"{pre}_normal.png", "RGBA")
    sg = fin(np.concatenate([spec, gloss[..., None]], -1), 1024)
    save(sg, f"{pre}_specgloss.png", "RGBA")
    occ = np.clip(aow, 0, 1)[..., None] * 0 + 0
    occ_full = np.asarray(Image.fromarray((np.clip(aow, 0, 1) * 255).astype(np.uint8)).resize((S, S), Image.BILINEAR)) / 255.0 \
        if aow.shape[0] != S else aow
    occ = np.clip(occ_full * (0.55 + 0.45 * occ_small), 0, 1)
    o = fin(occ, 1024)
    save(np.repeat(o[..., None], 3, -1), f"{pre}_occlusion.png", "RGB")
    f = fin(fz, 1024)
    save(np.repeat(f[..., None], 3, -1), f"{pre}_fuzzmask.png", "RGB")
    print("done", flush=True)


if __name__ == "__main__":
    main()
