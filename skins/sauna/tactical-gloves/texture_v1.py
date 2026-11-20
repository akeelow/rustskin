"""Sauna Mitts v1: доводка запечённых карт (.venv) — палитра, тон без формы, Spec/Gloss, Fuzz, отступы, экспорт.

python skins/sauna/tactical-gloves/texture_v1.py
Вход:  source/bake/*.png (4096, bake_gloves.py)
Выход: export/SaunaMitts_v1_{diffuse,normal,specgloss,occlusion,fuzz}.png — 2048 (размер слотов предмета)
       export/1024/SaunaMitts_v1_*.png — на случай, если редактор ужмёт до 1024 (тест test_slotsize.py)
       uv/v1_preview.png — карты рядом, 1024

Что здесь только цветом (у этого нет формы): тон шерсти (пряди), сажа на кончиках, засаленность ладони,
пепел в бороздах, общая грязь манжеты, выцветание полосы. Всё, у чего есть форма, пришло из запечённой
геометрии: цвет деталей — из цвета вершин high-poly, маски износа — из той же геометрии.
"""
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import noise_np as NN  # noqa: E402

BK = os.path.join(HERE, "source", "bake")
EX = os.path.join(HERE, "export")
VER = "v1"
NAME = "SaunaMitts"
POS_LO = np.array([0.40, 0.19, -0.01])
POS_HI = np.array([0.53, 0.43, 0.15])
IDS = {"felt": 1, "leather": 2, "suede": 3, "bark": 4, "thread": 5, "linen": 6, "stripe": 7, "twine": 8,
       "wood": 9}
# цель по медиане материала (sRGB) — палитра сета
TARGET = {"felt": "B3A48A", "leather": "8A6646", "suede": "9A7A58", "bark": "E3DDCF", "thread": "CFC6B4",
          "linen": "CFC6B4", "stripe": "8E3A30", "twine": "B9A272", "wood": "D2B98E"}
# (блик 0–255, глянец 0–255, Fuzz 0–1)
MAT = {"felt": (10, 25, 1.0), "leather": (35, 90, 0.0), "suede": (15, 30, 0.5), "bark": (25, 70, 0.0),
       "thread": (12, 35, 0.6), "linen": (12, 30, 0.55), "stripe": (12, 30, 0.55), "twine": (12, 25, 0.9),
       "wood": (18, 45, 0.0)}


def load(name, mode="RGB"):
    return np.asarray(Image.open(os.path.join(BK, name + ".png")).convert(mode), np.float32) / 255


def s2l(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def l2s(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def hexl(h):
    return s2l(np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32))


def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def down(arr, size, cov):
    """Lanczos с учётом покрытия (пустота вокруг островов не подмешивается к краю)."""
    out = []
    covd = np.asarray(Image.fromarray(cov.astype(np.float32), "F").resize((size, size), Image.LANCZOS))
    for k in range(arr.shape[2]):
        ch = np.asarray(Image.fromarray((arr[..., k] * cov).astype(np.float32), "F").resize((size, size), Image.LANCZOS))
        out.append(ch / np.maximum(covd, 1e-4))
    return np.stack(out, 2), covd > 0.5


def dilate(arr, m, px):
    """Отступ: px шагов наружу от островов, среднее по соседям."""
    arr = arr.copy()
    m = m.copy()
    for _ in range(px):
        acc = np.zeros_like(arr)
        cnt = np.zeros(m.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            mm = np.roll(m, (dy, dx), (0, 1))
            acc += np.roll(arr, (dy, dx), (0, 1)) * mm[..., None]
            cnt += mm
        new = (~m) & (cnt > 0)
        arr[new] = acc[new] / cnt[new, None]
        m |= new
    return arr


def save(arr, name, size_dir="", mode="RGB"):
    d = os.path.join(EX, size_dir)
    os.makedirs(d, exist_ok=True)
    a = np.clip(arr * 255 + 0.5, 0, 255).astype(np.uint8)
    Image.fromarray(a if mode != "L" else a[..., 0], mode).save(os.path.join(d, f"{NAME}_{VER}_{name}.png"))


def main():
    cov = load("coverage", "L") > 0.5
    idm = np.round(load("id", "RGB")[..., 0] * 255 - 8) / 16
    idm = np.where(cov, np.round(idm), 0).astype(np.int32)
    N = idm.shape[0]
    print("покрытие %.1f %%" % (cov.mean() * 100), {k: int((idm == v).sum()) for k, v in IDS.items()})

    # --- положение (для шума без шва)
    hi, lo = load("poshi"), load("poslo")
    q = (np.round(hi * 255) * 256 + np.round(lo * 255)) / 65535
    pos = POS_LO + q * (POS_HI - POS_LO)
    pmm4 = (pos * 1000)[::4, ::4]
    del hi, lo, q, pos

    def nz(scale, oct, seed):
        """Шум по 3D-положению (без швов), считается на 1/4 и растягивается — тон без формы, крупнее пикселя."""
        a = NN.fbm(pmm4 / scale, oct, seed).astype(np.float32)
        return np.asarray(Image.fromarray(a, "F").resize((N, N), Image.BILINEAR))

    # --- нормаль: запечённая минус та же копия без рельефа (гранёность low-poly уходит)
    nh = load("normal") * 2 - 1
    nb = load("normal_base") * 2 - 1
    xy = (nh[..., :2] - nb[..., :2]) * 1.15
    z = np.sqrt(np.clip(1 - (xy ** 2).sum(-1), 0.02, 1))
    nrm = np.concatenate([xy, z[..., None]], -1)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    nrm = np.where(cov[..., None], nrm, [0, 0, 1])
    # конец ремешка (остров 7, кромка нахлёста 3 см²): лучи промахиваются на тонкой кромке — где наклон > 60°
    # и это не нитка, нормаль сглаживается к плоской (плетение остаётся там, где запеклось)
    ids7 = np.asarray(Image.open(os.path.join(HERE, "uv", "ids_2048.png")).resize((N, N), Image.NEAREST)) == 7
    bad = ids7 & (nrm[..., 2] < 0.5)
    nrm[bad] = nrm[bad] * 0.15 + np.array([0, 0, 0.85])
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    flat = cov & (np.abs(nb[..., 0]) < 2)
    del nh, nb

    ao = load("ao", "L")
    ao = np.where(cov, 1 - (1 - ao) * 0.8, 1.0)   # между пальцами AO слишком чёрный — мягче
    col = s2l(load("color"))
    m1 = load("msk1")
    m2 = load("msk2")
    worn, char, dark = m1[..., 0], m1[..., 1], m1[..., 2]
    soot, grease, inner = m2[..., 0], m2[..., 1], m2[..., 2]

    # --- палитра: медиана каждого материала к цели сета (форма и износ остаются)
    for k, v in IDS.items():
        m = idm == v
        if m.sum() < 100:
            continue
        sel = m & (dark < 0.3) & (char < 0.2) & (worn < 0.3)
        if sel.sum() < 100:
            sel = m
        med = np.median(col[sel], 0)
        gain = hexl(TARGET[k]) / np.maximum(med, 1e-4)
        col[m] *= gain
        print(f"{k:8s} медиана sRGB {np.round(l2s(med) * 255).astype(int)} → {TARGET[k]}")

    felt = idm == IDS["felt"]
    linen = np.isin(idm, (IDS["linen"], IDS["stripe"]))
    # тон шерсти: серые и бежевые пряди (облака 1–3 см) и мелкая неровность — формы нет
    t1 = nz(18.0, 3, 61) - 0.5
    t2 = nz(4.0, 2, 62) - 0.5
    grey = np.array([0.92, 0.95, 1.02], np.float32)
    w = np.clip(0.5 + t1 * 2.2, 0, 1)[..., None]
    col = np.where(felt[..., None], col * (1 + 0.16 * t1[..., None] + 0.08 * t2[..., None]) * (w * grey + (1 - w)), col)
    # пепел в бороздах войлока: светло-серый налёт в глубоких местах
    ash = felt & (ao < 0.75)
    col = np.where(ash[..., None], col * 0.85 + hexl("A8A196") * 0.15 * sstep(0.75, 0.45, ao)[..., None], col)
    # сажа на кончиках: тёмная, пятнами
    sn = nz(3.0, 3, 63)
    s = np.clip(soot * (0.75 + 0.5 * sn), 0, 1) * 0.85
    s = np.where(linen, 0, s)
    col = col * (1 - s[..., None]) + hexl("2B2622") * s[..., None]
    # засаленность ладони
    g = grease * (0.6 + 0.4 * nz(6.0, 2, 64))
    col *= (1 - 0.18 * g)[..., None]
    # манжета: застиранная, с серыми пятнами; ближе к кисти грязнее; изнанка чище
    dirt = (nz(9.0, 3, 65) - 0.45) * 2
    dl = np.clip(dirt, 0, 1) * 0.22 * (1 - 0.6 * inner)
    col = np.where(linen[..., None], col * (1 - dl[..., None]) + hexl("8F877A") * dl[..., None] * 0.5, col)
    col = np.where((inner > 0.5)[..., None] & linen[..., None], col * 1.05, col)
    # выцветшая полоса: неровно
    st = idm == IDS["stripe"]
    fade = 0.25 * nz(7.0, 2, 66)
    col = np.where(st[..., None], col * (1 - fade[..., None]) + hexl("B88A7E") * fade[..., None], col)
    # береста: засаленная и закопчённая у печи — не белая бумага (тон, формы нет)
    bk = idm == IDS["bark"]
    g1 = np.clip((nz(5.0, 3, 67) - 0.35) * 2.0, 0, 1)
    bark_t = hexl("D8CDB6") / hexl("E3DDCF")
    col = np.where(bk[..., None], col * bark_t * (1 - 0.22 * g1[..., None]) + hexl("6E5A44") * 0.10 * g1[..., None], col)
    # тень в бороздах деталей (из запечённой AO геометрии): мягко
    col *= (0.62 + 0.38 * ao)[..., None]
    diffuse = l2s(col)

    # --- Specular/Gloss
    spec = np.zeros((N, N), np.float32)
    glos = np.zeros((N, N), np.float32)
    fuzz = np.zeros((N, N), np.float32)
    for k, v in IDS.items():
        m = idm == v
        sp, gl, fz = MAT[k]
        spec[m], glos[m], fuzz[m] = sp / 255, gl / 255, fz
    lea = idm == IDS["leather"]
    spec = np.where(lea, spec + worn * 18 / 255, spec)
    glos = np.where(lea, glos + worn * 60 / 255 + grease * 12 / 255, glos)
    glos = np.where(felt, glos + char * 18 / 255, glos)
    fuzz = np.where(felt, fuzz * (1 - 0.8 * char) * (1 - 0.3 * soot), fuzz)
    spec *= 0.5 + 0.5 * ao
    warm = np.array([1.0, 0.93, 0.82], np.float32)
    sg = np.concatenate([spec[..., None] * np.where(lea[..., None], warm, 1.0), glos[..., None]], -1)

    # --- в размер слотов, отступ
    for size, sub in ((2048, ""), (1024, "1024")):
        pad = 16 if size == 2048 else 10
        d, m = down(diffuse, size, cov)
        save(dilate(d, m, pad), "diffuse", sub)
        n_, _ = down(nrm, size, cov)
        n_ /= np.maximum(np.linalg.norm(n_, axis=-1, keepdims=True), 1e-6)
        n_ = dilate(n_, m, pad)
        n_[~m & (np.abs(n_).sum(-1) == 0)] = (0, 0, 1)
        save(n_ * 0.5 + 0.5, "normal", sub)
        s_, _ = down(sg, size, cov)
        s_ = dilate(s_, m, pad)
        sgimg = np.clip(s_ * 255 + 0.5, 0, 255).astype(np.uint8)
        Image.fromarray(sgimg, "RGBA").save(os.path.join(EX, sub, f"{NAME}_{VER}_specgloss.png"))
        a_, _ = down(ao[..., None], size, cov)
        save(dilate(a_, m, pad), "occlusion", sub, "L")
        f_, _ = down(fuzz[..., None], size, cov)
        save(dilate(f_, m, pad), "fuzz", sub, "L")
        print("экспорт", size)
    # предпросмотр
    prev = [Image.open(os.path.join(EX, f"{NAME}_{VER}_{k}.png")).convert("RGB").resize((1024, 1024))
            for k in ("diffuse", "normal", "specgloss", "occlusion", "fuzz")]
    W = Image.new("RGB", (1024 * 3, 2048), "black")
    for i, im in enumerate(prev):
        W.paste(im, (1024 * (i % 3), 1024 * (i // 3)))
    W.save(os.path.join(HERE, "uv", f"{VER}_maps.png"))
    print("ok")


if __name__ == "__main__":
    main()
