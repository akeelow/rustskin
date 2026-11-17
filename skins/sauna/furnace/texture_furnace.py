"""Sauna Boiler: карты для редактора Rust из запечённых (bake_furnace.py).

Вход:  bake/{normal,ao,id,tone}.png (2048), bake/pos.npz, bake/layout.json.
Выход: export/Furnace_<VERSION>_{diffuse (RGBA), normal, specgloss (RGBA), emission}.png — 1024,
       _occlusion.png — 512; размеры и слоты как у оригинала (originals/furnace_v3_*).

Форма (Normal, AO) — только из запекания. Здесь по запечённым id / tone / позиции / AO / кривизне
раскладываются цвет по палитре сета и износ: ржавчина, накипь и подтёки, копоть, мокрый низ реек,
обугленные концы поленьев, свечение углей гнёздами. Мелкий рельеф зерна (ржавчина, волокна)
добавляется к запечённой нормали слабым слоем.

  .venv/Scripts/python skins/sauna/furnace/texture_furnace.py
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import layout as L  # noqa: E402

BAKE, OUT = HERE / "bake", HERE / "export"
VERSION = "v1"
EMIT_GAIN = 1.0


def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)


# палитра сета (skins/sauna/README.md) + железо и зола
ASPEN, STEAMED, CHARWOOD = hexc("C2A77E"), hexc("7A5A3C"), hexc("45332A")
BASALT, CORE, AMBER = hexc("3D3E41"), hexc("FF6A1F"), hexc("FFB347")
LINEN, STRIPE, BIRCH, RUST = hexc("CFC6B4"), hexc("8E3A30"), hexc("E3DDCF"), hexc("8C4A26")
IRON, IRON_DK, STEEL = hexc("403C39"), hexc("282524"), hexc("7C766F")
RUST_DK, SCALE, SCALE_DK = hexc("5A2E1B"), hexc("CFC6B4"), hexc("8F887C")
SOOT, ASH, ASH_LT = hexc("120E0C"), hexc("4C4946"), hexc("9A948A")


def _hash(ix, iy, iz, seed):
    h = (ix.astype(np.uint32) * np.uint32(374761393) + iy.astype(np.uint32) * np.uint32(668265263)
         + iz.astype(np.uint32) * np.uint32(2246822519) + np.uint32(seed * 144665 + 101))
    h = (h ^ (h >> np.uint32(13))) * np.uint32(1274126177)
    h = h ^ (h >> np.uint32(16))
    return (h & np.uint32(0xFFFF)).astype(np.float32) / 65535.0


def vnoise(x, y, z, seed=0):
    """Шум по 3D-позиции (без швов на развёртке), 0…1."""
    x0, y0, z0 = np.floor(x), np.floor(y), np.floor(z)
    fx, fy, fz = x - x0, y - y0, z - z0
    fx, fy, fz = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy), fz * fz * (3 - 2 * fz)
    ix, iy, iz = x0.astype(np.int64), y0.astype(np.int64), z0.astype(np.int64)
    out = 0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (fx if dx else 1 - fx) * (fy if dy else 1 - fy) * (fz if dz else 1 - fz)
                out = out + w * _hash(ix + dx, iy + dy, iz + dz, seed)
    return out.astype(np.float32)


def fbm(x, y, z, octaves=4, seed=0):
    a, s, t = 0.0, 0.5, 0.0
    for o in range(octaves):
        a = a + s * vnoise(x * 2 ** o, y * 2 ** o, z * 2 ** o, seed + o * 7)
        t += s
        s *= 0.5
    return a / t


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def mix(a, b, t):
    return a * (1 - t[..., None]) + b * t[..., None]


def blur(a, r):
    im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
    return np.asarray(im, np.float32) / 255


def load(name):
    return np.asarray(Image.open(BAKE / name).convert("RGB"), np.float32) / 255


def down(a, k=2):
    h, w = a.shape[:2]
    return a.reshape(h // k, k, w // k, k, *a.shape[2:]).mean((1, 3))


def dilate(img, valid, n=14):
    """Заполнить поля вокруг островов цветом ближайших текселей (защита от швов на мипах)."""
    img, valid = img.copy(), valid.copy()
    for _ in range(n):
        acc = np.zeros_like(img)
        cnt = np.zeros(valid.shape, np.float32)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            v = np.roll(valid, (dy, dx), (0, 1))
            acc += np.roll(img, (dy, dx), (0, 1)) * v[..., None]
            cnt += v
        new = (~valid) & (cnt > 0)
        img[new] = acc[new] / cnt[new][:, None]
        valid |= new
    return img


def main():
    info = json.loads((BAKE / "layout.json").read_text())
    op = info["opening"]
    idm = np.rint((load("id.png")[..., 0] * 255 - 6) / 12).astype(np.int32)
    S = idm.shape[0]
    tone2 = load("tone.png")
    nrm2 = load("normal.png") * 2 - 1
    ao2 = load("ao.png")[..., 0]
    pos2 = np.load(BAKE / "pos.npz")["pos"].astype(np.float32) / 65535
    valid2 = idm > 0

    # кривизна из запечённой нормали: > 0 — выпуклые рёбра, < 0 — щели
    curv2 = np.gradient(nrm2[..., 0], axis=1) - np.gradient(nrm2[..., 1], axis=0)
    curv2 = blur(np.clip(curv2 * 4 + 0.5, 0, 1), 1.2) * 2 - 1
    nail_halo2 = blur((idm == L.IDS["nail"]).astype(np.float32), 9)
    rivet_halo2 = blur((idm == L.IDS["rivet"]).astype(np.float32), 7)

    m = valid2
    ID = idm[m]
    tr, tg, tb = tone2[m].T
    ao = ao2[m]
    curv = curv2[m]
    nail_halo, rivet_halo = nail_halo2[m], rivet_halo2[m]
    P = pos2[m] * np.array(L.POS_SCALE, np.float32) - np.array(L.POS_OFF, np.float32)
    x, y, z = P.T
    th = np.degrees(np.arctan2(x - L.CX, z - L.CZ))
    r = np.hypot(x - L.CX, z - L.CZ)
    n = len(ID)
    is_ = lambda name: ID == L.IDS[name]  # noqa: E731

    def dth(a):                                     # расстояние по окружности до угла a, метры
        return np.abs((th - a + 180) % 360 - 180) * np.pi / 180 * np.maximum(r, 0.15)

    col = np.zeros((n, 3), np.float32)
    spec = np.full(n, 40, np.float32)
    gloss = np.full(n, 25, np.float32)
    emit = np.zeros(n, np.float32)
    bump = np.zeros(n, np.float32)                  # мелкий рельеф зерна для нормали

    # ---------------- общие поля износа
    blot = fbm(x * 9, y * 9, z * 9, 4, 1)
    fine = fbm(x * 70, y * 70, z * 70, 3, 2)
    streak = fbm(x * 55, y * 2.2, z * 55, 3, 3)      # вертикальные потёки
    streak_w = fbm(x * 16, y * 1.2, z * 16, 3, 4)    # широкие потёки
    grain = fbm(tg * 4 + tr * 31, tb * 26 + tr * 17, tr * 9, 4, 5)   # волокна вдоль рейки (координаты детали)

    oc = (op["th0"] + op["th1"]) / 2
    ow = (op["th1"] - op["th0"]) / 2 * np.pi / 180 * 0.42
    front = dth(oc)
    # копоть: веер вверх от проёма, по кромке проёма, вокруг отверстия в крышке
    up = np.clip(y - op["y1"] + 0.04, 0, None)
    soot = np.exp(-up / 0.15) * sstep(ow + 0.07 + up * 0.5, ow * 0.5, front) * (y > op["y0"])
    soot = np.clip(soot * (0.55 + 0.9 * streak_w) + 0.4 * sstep(0.09, 0.01, np.hypot(front - 0, y - (op["y0"] + op["y1"]) / 2) - ow), 0, 1)
    top = y > 1.535
    soot_top = sstep(0.17, 0.05, r) * top
    soot = np.clip(np.maximum(soot, soot_top * (0.6 + 0.5 * blot)), 0, 1)

    # накипь: белые минеральные потёки из-под обручей и швов, из-под затычки
    lime = np.zeros(n, np.float32)
    for hy, _ in L.HOOPS:
        below = hy - L.HOOP_W / 2 - y
        length = 0.025 + 0.20 * sstep(0.55, 0.85, vnoise(x * 7, x * 0 + hy * 9, z * 7, 6))
        lime = np.maximum(lime, (below > -0.004) * np.exp(-np.clip(below, 0, None) / length) * sstep(0.50, 0.68, streak) * sstep(0.32, 0.58, streak_w))
    lime = np.maximum(lime, 0.5 * sstep(0.004, 0.03, rivet_halo) * sstep(0.58, 0.74, streak) * 0.6)
    py, pt = L.PLUG[1], L.PLUG[0]
    drop = np.clip(py - 0.02 - y, 0, None)
    plug_run = (y < py - 0.015) * sstep(0.022 + drop * 0.20, 0.004, dth(pt) * (1 + 0.6 * (streak - 0.5))) * np.exp(-drop / 0.45)
    lime = np.clip(np.maximum(lime, plug_run * (0.55 + 0.6 * streak)) + 0.16 * sstep(0.62, 0.8, blot) * (y > 0.6), 0, 1)
    lime *= (1 - soot) ** 2

    rust = sstep(0.50, 0.70, 0.55 * blot + 0.25 * fine + 0.35 * (1 - ao) + 0.30 * np.clip(-curv, 0, 1))

    # ---------------- железо: бак, обручи, клёпки, рамка, основание
    tank = is_("tank")
    c = IRON * (0.78 + 0.5 * tr[:, None]) * (0.85 + 0.3 * blot[:, None])
    c = mix(c, RUST_DK, rust * 0.75)
    c = mix(c, RUST, rust * sstep(0.45, 0.8, fine) * 0.7)
    c = mix(c, STEEL, sstep(0.25, 0.7, curv) * 0.35)
    col[tank] = c[tank]
    spec[tank] = (95 - 50 * rust)[tank]
    gloss[tank] = (92 - 62 * rust)[tank]
    bump[tank] = (-0.5 * rust * fine)[tank]

    hoop = is_("hoop")
    c = IRON_DK * (0.85 + 0.4 * tr[:, None]) * (0.8 + 0.4 * blot[:, None])
    c = mix(c, RUST_DK, rust * 0.6)
    c = mix(c, STEEL, sstep(0.15, 0.6, curv) * 0.6)
    col[hoop] = c[hoop]
    spec[hoop] = (105 - 50 * rust)[hoop]
    gloss[hoop] = (100 - 60 * rust)[hoop]

    riv = is_("rivet")
    c = mix(IRON * 0.95, STEEL, sstep(0.0, 0.6, curv) * (0.35 + 0.5 * tr))
    c = mix(c, RUST, sstep(0.55, 0.9, 1 - ao) * 0.8)
    col[riv] = c[riv]
    spec[riv], gloss[riv] = 110, 105

    frame = is_("frame")
    c = mix(IRON_DK * 0.8, RUST_DK, rust * 0.35)
    c = mix(c, STEEL * 0.8, sstep(0.3, 0.8, curv) * 0.4)
    col[frame] = c[frame]
    spec[frame], gloss[frame] = 60, 45

    drum = is_("drum")
    ledge = drum & (y > 0.5)
    c = mix(IRON_DK * (0.9 + 0.4 * blot[:, None]), RUST_DK, np.clip(rust + 0.35, 0, 1))
    c = mix(c, RUST, sstep(0.5, 0.8, fine) * 0.3)
    dust = ledge * sstep(0.45, 0.15, front) * (0.5 + 0.5 * fine)          # зола, просыпанная у топки
    c = mix(c, ASH_LT * 0.8, dust * 0.8)
    col[drum] = c[drum]
    spec[drum], gloss[drum] = 50, 28
    bump[drum] = (-0.6 * fine)[drum]

    iron = tank | hoop | riv | frame | drum
    # накипь поверх железа: матовая корка, по краю светлее
    lt = np.where(iron & ~frame, lime, 0)
    scale_c = mix(np.broadcast_to(SCALE_DK, (n, 3)), SCALE, sstep(0.35, 0.9, lt * (0.6 + 0.6 * fine)))
    col = mix(col, scale_c, np.clip(lt * 0.95, 0, 0.85))
    spec = spec * (1 - lt) + 48 * lt
    gloss = gloss * (1 - lt) + 12 * lt
    bump += 0.5 * lt * fine
    st = np.where(iron, soot, 0)
    col = mix(col, SOOT, np.clip(st * 1.1, 0, 0.95))
    spec = spec * (1 - st) + 28 * st
    gloss = gloss * (1 - st) + 8 * st

    # ---------------- ограждение: рейки, гвозди, проволока
    slat = is_("slat")
    heat = sstep(0.50, 0.10, front) * sstep(0.26, 0.46, y)                 # жар из топки на верхние рейки
    c = ASPEN * (0.74 + 0.42 * tr[:, None]) * (0.90 + 0.2 * blot[:, None])
    c = mix(c, hexc("A8977C") * (0.8 + 0.3 * tr[:, None]), sstep(0.55, 0.9, vnoise(tr * 40, tr * 0, tr * 0, 8)))   # серые, выветренные
    c = c * (0.78 + 0.40 * grain[:, None])
    wet = sstep(0.19, 0.03, y + 0.07 * (streak_w - 0.5))
    c = mix(c, STEAMED * (0.85 + 0.3 * grain[:, None]), np.clip(wet * 0.9 + 0.25 * sstep(0.5, 0.8, streak_w) * (y < 0.3), 0, 1))
    c = mix(c, CHARWOOD, np.clip(heat * (0.6 + 0.6 * blot) + 0.5 * sstep(0.6, 1.0, 1 - ao), 0, 0.9))
    c = mix(c, SOOT * 1.6, np.clip(heat - 0.55, 0, 1) * 0.8)
    c = mix(c, RUST * 0.8, sstep(0.05, 0.5, nail_halo) * 0.6)              # ржавый ореол у гвоздей
    c = mix(c, ASPEN * 1.12, sstep(0.3, 0.8, curv) * 0.35 * (1 - wet) * (1 - heat))   # затёртые рёбра
    plug_wet = plug_run * 0.8
    c = mix(c, STEAMED * 0.7, plug_wet)
    c = mix(c, SCALE_DK, sstep(0.5, 0.75, streak) * plug_wet * 0.5 + 0.35 * sstep(0.62, 0.8, streak) * sstep(0.16, 0.26, y) * (1 - heat))
    col[slat] = c[slat]
    spec[slat] = 38
    gloss[slat] = (30 + 45 * wet + 30 * plug_wet)[slat]
    bump[slat] = (0.9 * (grain - 0.5))[slat]

    nail = is_("nail")
    col[nail] = mix(IRON_DK * 0.9, RUST, sstep(0.3, 0.8, fine) * 0.55)[nail]
    spec[nail], gloss[nail] = 85, 70
    wire = is_("wire")
    col[wire] = mix(mix(RUST_DK * np.ones((n, 1)), RUST, sstep(0.35, 0.7, fine)), STEEL, sstep(0.3, 0.7, curv) * 0.5)[wire]
    spec[wire], gloss[wire] = 75, 50

    # ---------------- топка
    nests = np.array(info["nests"], np.float32)
    act = np.array([1.0, 0.85, 0.5, 0.95, 0.22, 0.6], np.float32)           # гнёзда тлеют по-разному
    dn = np.hypot(x[:, None] - nests[None, :, 0], z[:, None] - nests[None, :, 1])
    glow_near = (np.exp(-dn ** 2 / (2 * 0.045 ** 2)) * act[None]).max(1)      # близость к живому гнезду

    wall = is_("wall")
    col[wall] = (SOOT * (0.9 + 0.5 * blot[:, None]) + 0.02 * fine[:, None])[wall]
    spec[wall], gloss[wall] = 25, 6
    lipz = tank & (r < 0.40) & (y < 0.9) & (front < 0.3) & (ao < 0.9)
    ash = is_("ash")
    c = mix(ASH * (0.8 + 0.4 * blot[:, None]), ASH_LT, sstep(0.55, 0.85, fine) * 0.7)
    c = mix(c, SOOT * 1.5, sstep(0.6, 0.85, fbm(x * 40, y * 40, z * 40, 3, 9)) * 0.8)      # угольная крошка
    col[ash] = c[ash]
    spec[ash], gloss[ash] = 30, 6
    bump[ash] = (0.8 * (fine - 0.5))[ash]

    bark = is_("bark")
    lent = sstep(0.62, 0.72, vnoise(tg * 90, tb * 7 + tr * 30, tr * 50, 10)) * sstep(0.3, 0.6, vnoise(tg * 14, tb * 3, tr * 20, 11))
    peel = sstep(0.62, 0.8, fbm(tg * 5, tb * 4, tr * 30, 3, 12))
    c = BIRCH * (0.86 + 0.14 * blot[:, None])
    c = mix(c, hexc("B89B74"), peel * 0.8)
    c = mix(c, hexc("2A2420"), np.clip(lent, 0, 1) * 0.9)
    char = np.clip(sstep(0.10, 0.035, dn.min(1)) * 1.2 + 0.6 * sstep(0.03, 0.0, y - L.FLOOR_Y - 0.012) * 0 + 0.35 * glow_near, 0, 1)
    crack = sstep(0.58, 0.66, fbm(x * 90, y * 90, z * 90, 2, 13))
    c = mix(c, SOOT * 1.3, np.clip(char * (0.8 + 0.5 * blot), 0, 1))
    col[bark] = c[bark]
    spec[bark], gloss[bark] = 40, 28
    emit[bark] = (0.55 * char * crack * glow_near)[bark]
    bump[bark] = (0.8 * lent - 0.6 * char * crack)[bark]

    end = is_("logend")
    rings = 0.5 + 0.5 * np.cos(tg * 55 + 4 * vnoise(tg * 6, tb * 6, tr * 9, 14))
    c = hexc("D9BE8C") * (0.86 + 0.16 * rings[:, None])
    c = mix(c, hexc("A98556"), sstep(0.8, 1.0, tg) * 0.6)
    c = mix(c, SOOT * 1.4, np.clip(char * 1.1, 0, 1))
    col[end] = c[end]
    spec[end], gloss[end] = 36, 22
    emit[end] = (0.5 * char * crack * glow_near)[end]

    emb = is_("ember")
    nest_act = act[np.clip((tb * 8).astype(int), 0, 5)]
    e = np.clip(tg * nest_act * (1.25 - 0.75 * ao) * (0.75 + 0.5 * tr), 0, 1)
    e = np.where(e > 0.16, e, e * 0.25)                                    # остывшие куски — чёрные
    col[emb] = mix(SOOT * 1.6 * np.ones((n, 1)), hexc("5A2410"), e)[emb]
    spec[emb], gloss[emb] = 30, 10
    emit[emb] = e[emb]
    # зола рядом с живым гнездом чуть подсвечена снизу
    emit[ash] = (0.30 * np.clip(glow_near - 0.35, 0, 1) * (0.6 + 0.8 * (1 - ao)))[ash]
    col = mix(col, SOOT, np.where(lipz, 0.85, 0))

    # ---------------- камни на крышке
    stn = is_("stone")
    c = BASALT * (0.70 + 0.60 * tr[:, None]) * (0.88 + 0.24 * blot[:, None])
    c = mix(c, hexc("6A6A6C"), sstep(0.2, 0.8, curv) * 0.45)                # сбитые рёбра светлее
    c = mix(c, SCALE_DK, sstep(0.66, 0.8, fbm(x * 30, y * 30, z * 30, 3, 15)) * 0.45)      # минеральный налёт
    c = mix(c, SOOT * 1.2, np.clip(soot_top * 0.9 + 0.5 * sstep(0.55, 0.15, ao), 0, 0.9))
    col[stn] = c[stn]
    spec[stn], gloss[stn] = 50, 48
    bump[stn] = (0.7 * (fine - 0.5))[stn]

    # ---------------- ковш, затычка, тряпка
    lad = is_("ladle")
    lg = fbm(x * 30, y * 240, z * 30, 3, 16) if False else fbm(x * 200, y * 8, z * 200, 3, 16)
    c = mix(STEAMED * (0.9 + 0.3 * lg[:, None]), hexc("A88660"), tg * 0.55)   # ручка светлее, затёрта
    c = mix(c, CHARWOOD, sstep(0.75, 0.35, ao) * 0.8)
    c = mix(c, hexc("B89468"), sstep(0.3, 0.8, curv) * 0.4)
    col[lad] = c[lad]
    spec[lad], gloss[lad] = 40, 52
    bump[lad] = (0.6 * (lg - 0.5))[lad]

    plug = is_("plug")
    c = mix(STEAMED * 0.75, CHARWOOD, 0.4 + 0.4 * (0.5 + 0.5 * np.cos(tg * 30)))
    col[plug] = c[plug]
    spec[plug], gloss[plug] = 42, 70
    rag = is_("rag")
    weave = 0.5 + 0.25 * np.sin(x * 2600) + 0.25 * np.sin(y * 2600)
    c = LINEN * (0.58 + 0.2 * blot[:, None]) * (0.92 + 0.1 * weave[:, None])
    c = mix(c, STRIPE, (tg > 0.5) * sstep(0.012, 0.006, np.abs(y - (py - 0.105))) * 0.85)   # выцветшая полоса
    c = mix(c, STEAMED * 0.8, np.clip(sstep(0.95, 0.5, ao) * 0.7 + (tg > 0.5) * sstep(py - 0.10, py - 0.17, y) * 0.5, 0, 0.85))
    col[rag] = c[rag]
    spec[rag], gloss[rag] = 30, 14
    bump[rag] = (0.5 * (weave - 0.5))[rag]

    # грязь в щелях для всего, кроме топки
    dirt = sstep(0.7, 0.25, ao) * 0.45
    outside = ~(wall | ash | emb | bark | end)
    col = np.where(outside[:, None], col * (1 - dirt[:, None]) + SOOT * 1.5 * dirt[:, None], col)

    # ---------------- свечение: чёрный → тёмно-красный → #FF6A1F → #FFB347 (выше не поднимается)
    e = np.clip(emit * EMIT_GAIN, 0, 1)
    stops = np.array([0.0, 0.22, 0.62, 1.0], np.float32)
    cols = np.stack([np.zeros(3, np.float32), hexc("6A1604"), CORE, AMBER])
    ecol = np.stack([np.interp(e, stops, cols[:, k]) for k in range(3)], 1).astype(np.float32)

    # ---------------- сборка 2048 → 1024
    def full(v, ch):
        a = np.zeros((S, S, ch), np.float32)
        a[m] = v.reshape(n, ch)
        return a

    cov = down(valid2.astype(np.float32))
    ok = cov > 0.4
    def fin(v, ch):  # noqa: E306
        a = down(full(v, ch)) / np.maximum(cov, 1e-3)[..., None]
        return dilate(np.where(ok[..., None], a, 0), ok)

    col1 = fin(np.clip(col, 0, 1), 3)
    sg1 = fin(np.stack([spec, gloss], 1) / 255, 2)
    em1 = fin(ecol, 3)
    # нормаль: запечённая + слабый слой зерна (градиент bump в пространстве развёртки)
    b2 = full(bump, 1)[..., 0]
    b2 = blur(b2 * 0.5 + 0.5, 0.8)
    gx, gy = np.gradient(b2, axis=1), -np.gradient(b2, axis=0)
    nn = nrm2.copy()
    nn[..., 0] -= gx * 1.6 * valid2
    nn[..., 1] -= gy * 1.6 * valid2
    nn = down(nn)
    nn /= np.linalg.norm(nn, axis=-1, keepdims=True) + 1e-9
    ao1 = down(down(ao2))
    occ = 0.22 + 0.78 * ao1

    # кубики углей — настоящая геометрия модели, у каждой группы на развёртке пятно ~9 px:
    # в пятно кладётся пёстрый уголь: у первой группы тлеет ~40 % площади, у второй ~20 %, третья чёрная
    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)  # noqa: E731
    D, E, SG = q(col1), q(em1), q(sg1)
    rs = np.random.RandomState(3)
    for (u, v), hot in (((0.9015, 0.1075), 0.5), ((0.9205, 0.1405), 0.25), ((0.9235, 0.0505), 0.0)):
        cx, cy = int(u * 1024), int(v * 1024)
        k = np.asarray(Image.fromarray((rs.rand(5, 5) * 255).astype(np.uint8)).resize((15, 15), Image.BICUBIC), np.float32) / 255
        e = np.clip((k - (1 - hot)) / 0.25, 0, 1) if hot else np.zeros((15, 15), np.float32)
        ec = np.stack([np.interp(e * 0.85, stops, cols[:, c]) for c in range(3)], -1)
        dc = (SOOT * 1.5)[None, None] * (0.7 + 0.9 * k[..., None]) * (1 - e[..., None]) + hexc("5A2410")[None, None] * e[..., None]
        D[cy - 7:cy + 8, cx - 7:cx + 8] = q(dc)
        E[cy - 7:cy + 8, cx - 7:cx + 8] = q(ec)
        SG[cy - 7:cy + 8, cx - 7:cx + 8] = (30, 10)

    OUT.mkdir(exist_ok=True)
    name = OUT / f"Furnace_{VERSION}"
    Image.fromarray(np.dstack([D, np.full((1024, 1024), 255, np.uint8)]), "RGBA").save(f"{name}_diffuse.png")
    Image.fromarray(q(nn * 0.5 + 0.5), "RGB").save(f"{name}_normal.png")
    Image.fromarray(np.dstack([SG[..., 0], SG[..., 0], SG[..., 0], SG[..., 1]]), "RGBA").save(f"{name}_specgloss.png")
    Image.fromarray(q(occ), "L").convert("RGB").save(f"{name}_occlusion.png")
    Image.fromarray(E, "RGB").save(f"{name}_emission.png")
    lit = (E.max(-1) > 40).mean() * 100
    print(f"wrote {name}_*.png; emission peak {E.reshape(-1, 3).max(0)}, lit area {lit:.2f}% of texture")


if __name__ == "__main__":
    main()
