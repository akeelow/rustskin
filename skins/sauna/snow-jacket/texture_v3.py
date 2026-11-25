"""Sauna Robe v3: карты из запекания bake_v3.py (4096) -> экспорт 1024 (Lanczos) — PLAN_v3.md, §5.6.

Форма — уже в геометрии (bake/v3/normal, ao, m1–m3). Здесь только:
  - нормаль = рельеф − база (та же сетка без рельефа): гранёность low-poly уходит, остаётся смоделированное;
    мелкий рельеф усилен n + 0.5·(n − размытая n) (руководство §9.2);
  - палитра по маскам той же геометрии (материал, полость вафли, кант, канавки, подпалины, нитки);
  - то, у чего формы нет: неровный тон после стирки, сырость по подолу и манжетам, пожелтевшая горловина;
  - Spec/Gloss по материалам, Occlusion из AO (слот есть, тест 25.11), Fuzz Mask по вафле.

    .venv/Scripts/python skins/sauna/snow-jacket/texture_v3.py [--tag v3.0]
Выход: export/SnowJacket_<tag>_{diffuse,normal,specgloss,occlusion,fuzz}.png (1024).
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
sys.path.insert(0, str(HERE))
import fields_v3 as FV  # noqa: E402

BAKE = HERE / "bake" / "v3"
OUT = HERE / "export"
S = 4096
EXPORT = 1024
TAG = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "v3.0"
sstep = FV.sstep


def hexc(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255


CLOTH = hexc("#BBA889")      # вафля (v2.3–v2.5, проверено в игре)
BAND = hexc("#B09B7A")       # полоса, пояс, узел: плотнее, чуть темнее
FRINGE = hexc("#C9BA9C")
LINEN = hexc("#CFC6B4")
STRIPE = hexc("#8E3A30")
TWIG = hexc("#4E3A2C")
LEAF = hexc("#5C6A39")
SCORCH_HALO = hexc("#7A5634")
SCORCH_CORE = hexc("#2E2018")
DAMP = hexc("#8F7552")


def load(name):
    im = Image.open(BAKE / f"{name}.png")
    a = np.asarray(im.convert("RGBA"), np.float32) / 255
    return a[..., :3], a[..., 3] > 0.5


def _box(a, r, axis):
    c = np.cumsum(np.pad(a, [(r + 1, r) if k == axis else (0, 0) for k in range(a.ndim)], mode="edge"), axis=axis,
                  dtype=np.float64)
    n = a.shape[axis]
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return ((hi - lo) / (2 * r + 1)).astype(np.float32)


def blur(a, r):
    """≈ гаусс σ = r: три box-прохода по каждой оси."""
    if r <= 0:
        return a
    b = max(1, int(round(r * 0.9)))
    for _ in range(3):
        a = _box(_box(a, b, 0), b, 1)
    return a


def extend(a, cov, steps=None):
    """Заполнить незапечённое (отступ за край островов, щели между группами) — push-pull по пирамиде средних."""
    a = a.astype(np.float32)
    w = cov.astype(np.float32)
    if a.ndim == 3:
        w = w[..., None]
    A, W = [a * w], [w]
    while A[-1].shape[0] > 1:
        s = A[-1].shape
        A.append(A[-1].reshape(s[0] // 2, 2, s[1] // 2, 2, *s[2:]).sum((1, 3)))
        W.append(W[-1].reshape(s[0] // 2, 2, s[1] // 2, 2, *W[-1].shape[2:]).sum((1, 3)))
    fill = A[-1] / np.maximum(W[-1], 1e-9)
    for k in range(len(A) - 2, -1, -1):
        upf = np.repeat(np.repeat(fill, 2, 0), 2, 1)
        own = A[k] / np.maximum(W[k], 1e-9)
        fill = np.where(W[k] > 0, own, upf)
    return np.where(w > 0, a, fill).astype(np.float32)


def down(a):
    """4096 -> 1024 Lanczos по каналам."""
    if a.ndim == 2:
        return np.asarray(Image.fromarray(a.astype(np.float32), "F").resize((EXPORT, EXPORT), Image.LANCZOS))
    return np.dstack([down(a[..., k]) for k in range(a.shape[2])])


def up(a):
    """2048 -> 4096 (растры модели)."""
    return np.repeat(np.repeat(a, 2, 0), 2, 1)


def mix(c, col, t):
    t = np.clip(t, 0, 1)[..., None]
    return c * (1 - t) + col * t


def main():
    OUT.mkdir(exist_ok=True)
    nrel, _ = load("normal")            # у нормали Blender заливает фон плоской нормалью — альфа всегда 1
    nbase, _ = load("normal_base")
    ao, cov = load("ao")                 # покрытие: где запекание записало пиксель (альфа AO)
    m1, _ = load("m1")
    m2, _ = load("m2")
    _, _, _, _, _, pos, _, isl, _ = FV.model()
    pos = up(np.nan_to_num(pos))
    isl = up(isl)
    cov &= isl >= 0
    print("покрытие:", round(cov.mean() * 100, 1), "% атласа, островов", round((isl >= 0).mean() * 100, 1), "%")

    # ---------------------------------------------------------------- нормаль
    n = nrel * 2 - 1
    nb = nbase * 2 - 1
    d = n - nb
    nn = d + np.array([0, 0, 1], np.float32)
    nn /= np.linalg.norm(nn, axis=2, keepdims=True)
    detail = nn - blur(nn, 6)
    nn = nn + 0.5 * detail
    nn[..., 2] = np.maximum(nn[..., 2], 0.15)
    nn /= np.linalg.norm(nn, axis=2, keepdims=True)
    nn = extend(nn, cov)
    nn[~cov & (np.abs(nn).sum(2) == 0)] = (0, 0, 1)

    # ---------------------------------------------------------------- маски
    ao1 = extend(ao[..., 0], cov)
    cav, stripe, groove = (extend(m1[..., k], cov) for k in range(3))
    code = np.where(cov, np.rint(m2[..., 0] * 16), FV.BODY).astype(np.int32)   # коды не усредняются в отступах
    scorch, thread = extend(m2[..., 1], cov), extend(m2[..., 2], cov)

    X, Y, Z = pos[..., 0], pos[..., 1], pos[..., 2]

    # ---------------------------------------------------------------- Diffuse
    col = np.zeros((S, S, 3), np.float32) + CLOTH
    band = np.isin(code, (FV.BAND, FV.BELT, FV.KNOT, FV.LOOP))
    col[band] = BAND
    col[code == FV.FRINGE] = FRINGE
    col[code == FV.LINEN] = LINEN
    col[code == FV.TWIG] = TWIG
    col[code == FV.LEAF] = LEAF
    col = mix(col, STRIPE * 0.92 + CLOTH * 0.08, stripe * np.isin(code, (FV.BODY, FV.BAND, FV.CUFF, FV.LINEN)))
    # тон после стирки: неровно, крупными пятнами (формы нет — только цвет)
    wash = FV.fbm(X * 9 + 3, Y * 9 + Z * 5, 301) - 0.5
    col *= (1 + 0.10 * wash)[..., None]
    # полость вафли чуть темнее (пыль и сырость держатся в ячейках), гребни светлее
    cloth = ~np.isin(code, (FV.TWIG, FV.LEAF))
    col *= (1 - 0.05 * cav * cloth + 0.02 * (1 - cav) * cloth)[..., None]   # 0.10 давало «клетку»
    col *= (1 - 0.18 * groove)[..., None]
    # сырость: подол снизу и манжеты (по высоте и по расстоянию до кисти), гуще во впадинах
    damp = (1 - sstep(0.21, 0.30, Y)) * np.isin(isl, (0, 3, 7))
    damp = np.maximum(damp, np.isin(isl, (1, 2, 11, 12)) * sstep(0.40, 0.47, np.abs(X)) * 0.8)
    damp *= 0.55 + 0.45 * FV.fbm(X * 20, Y * 20 + Z * 7, 302)
    col = mix(col, DAMP, damp * (0.35 + 0.25 * cav))
    # горловина: пожелтела изнутри (обтачка и внутренняя сторона воротника)
    col = mix(col, hexc("#A88E62"), (isl == 10) * 0.35)
    # V-вырез — в тени
    col *= np.where(code == FV.INNER, 0.72, 1.0)[..., None]
    # подпалины: коричневый ореол, тёмная середина
    col = mix(col, SCORCH_HALO, sstep(0.05, 0.5, scorch) * 0.8)
    col = mix(col, SCORCH_CORE, sstep(0.6, 0.95, scorch))
    # AO в Diffuse — мягко (основное — в слоте Occlusion)
    # AO в Diffuse — только крупное (складки, под поясом, узел): ячейки вафли в цвете читались клеткой;
    # мелкое AO — в слоте Occlusion (в игре влияет на рассеянный свет)
    col *= (0.70 + 0.30 * blur(ao1, 14))[..., None]
    col = extend(np.clip(col, 0, 1), cov | (isl >= 0))

    # ---------------------------------------------------------------- Spec/Gloss, Fuzz, Occlusion
    spec = np.full((S, S), 0.05, np.float32)
    gloss = np.full((S, S), 0.10, np.float32)
    spec[code == FV.LEAF] = 0.08
    gloss[code == FV.LEAF] = 0.38
    spec[code == FV.TWIG] = 0.05
    gloss[code == FV.TWIG] = 0.22
    gloss += 0.10 * damp
    fuzz = np.where(cloth, 1.0 - 0.35 * cav, 0.0)
    fuzz = np.where(band, 0.8 - 0.25 * cav, fuzz)
    fuzz = np.where(code == FV.LINEN, 0.55, fuzz)
    occ = np.clip(ao1, 0, 1) ** 1.2

    # ---------------------------------------------------------------- экспорт
    def save(name, arr, mode):
        a = np.clip(down(arr), 0, 1)
        if mode == "RGBA":
            a = np.dstack([a, np.ones(a.shape[:2], np.float32)])
        Image.fromarray((a * 255 + 0.5).astype(np.uint8), mode).save(OUT / f"SnowJacket_{TAG}_{name}.png")

    nexp = down(nn)
    nexp /= np.linalg.norm(nexp, axis=2, keepdims=True)
    Image.fromarray(((nexp * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8), "RGB").save(OUT / f"SnowJacket_{TAG}_normal.png")
    save("diffuse", col, "RGBA")
    sg = np.dstack([spec, spec, spec, gloss])
    Image.fromarray((np.clip(down(sg), 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(OUT / f"SnowJacket_{TAG}_specgloss.png")
    save("occlusion", extend(occ, cov), "L")
    save("fuzz", extend(fuzz, cov), "L")
    print("записано: export/SnowJacket_%s_{diffuse,normal,specgloss,occlusion,fuzz}.png" % TAG)


if __name__ == "__main__":
    main()
