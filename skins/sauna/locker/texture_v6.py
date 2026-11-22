"""Sauna Changing Locker v6: карты из запекания bake_v6.py (4096) -> экспорт 2048 (Lanczos).

Форма — уже в геометрии (bake/v6/normal, m1..m3, idc, pos). Здесь только:
  - палитра по маскам той же геометрии (волокно, полость, вмятина, шляпка, сучок, эмаль/краска, кромка, разное, тон);
  - то, у чего формы нет: мокрый низ, минеральные потёки, ржавые потёки и ореолы, засаленность у замка, запотевание
    стекла и сердечко, пыль;
  - Spec/Gloss (Unity Specular), Occlusion из AO, Emission от смоделированных источников (плафон, паз под полками,
    паз потолка, окно, пролом) и отсвет под полками на спинке ниши.
Тексели, которых v6 ещё не касался, — из v5.4 (вертикальный срез).

    .venv/Scripts/python skins/sauna/locker/texture_v6.py [--tag v6.0]
Выход: export/Locker_<tag>_{diffuse,normal,specgloss,occlusion,emission}.png (2048).
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fields_v6 as FV  # noqa: E402

BAKE = HERE / "bake" / "v6"
OUT = HERE / "export"
PREV = "v5.4"
S = 4096
EXPORT = 2048
MAT = FV.MAT
sstep = FV.sstep


def hexc(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255


def rgb(*c):
    return np.array(c, np.float32) / 255


# палитра Diffuse (sRGB). Солнце редактора осветляет и желтит (§9.6): цель в игре — референс Nano Banana
DOOR = rgb(140, 128, 114)        # выветренная липа дверцы, S ≈ 0.19 (в игре ≈ (182, 165, 152))
LEDGE = rgb(134, 122, 108)
WFRAME = rgb(146, 134, 118)
SIDE = rgb(132, 120, 104)        # вагонка бока
NICHE = rgb(72, 56, 44)          # чайное нутро ниш (тёмное — полотенце и веник читаются)
SHELF = rgb(110, 92, 76)
GRATE = rgb(98, 82, 68)
PEG = rgb(126, 98, 72)
LAMPW = rgb(122, 102, 82)
GAP = rgb(20, 16, 13)
KNOT = rgb(70, 52, 38)
NAIL = rgb(46, 43, 40)
RUST = hexc("#8C4A26")
RUST_DK = rgb(78, 46, 32)
ENAMEL = rgb(124, 129, 129)      # светлая серая эмаль старого шкафчика, чуть в голубизну (v6.0: была синее)
STEEL = rgb(58, 56, 53)
STEEL_BRIGHT = rgb(120, 118, 114)
BRASS = rgb(92, 72, 38)
DIAL = rgb(206, 196, 170)
TICK = rgb(36, 32, 28)
RED = rgb(168, 44, 34)
BLUE = rgb(48, 92, 156)
FOG = rgb(124, 130, 134)
SEE = rgb(48, 52, 56)            # сквозь протёртое стекло — тёмное нутро
MUD = rgb(92, 79, 64)
MUD_LIGHT = rgb(112, 98, 80)
LEAF_Y = rgb(184, 146, 62)       # жёлтый лист на дверце
LINEN = rgb(192, 184, 166)
BRICK = hexc("#8E3A30")
THREAD = rgb(166, 156, 136)
LEAF_OL = rgb(94, 92, 60)        # сухой веник: олива / хаки (v6.0: зелёный «салат»)
LEAF_KH = rgb(122, 108, 70)
TWIG = rgb(88, 62, 46)
TWINE = rgb(168, 152, 122)
GLOWC = rgb(232, 214, 176)
SPLIT = rgb(26, 19, 15)
MINERAL = rgb(212, 208, 198)
WARM = np.array([1.0, 0.72, 0.42], np.float32)     # тёплый свет (не неон)


def load(name, mode="RGB"):
    return np.asarray(Image.open(BAKE / f"{name}.png").convert(mode), np.float32) / 255.0


def prev(slot, mode):
    im = Image.open(OUT / f"Locker_{PREV}_{slot}.png").convert(mode)
    return np.asarray(im.resize((S, S), Image.LANCZOS), np.float32) / 255.0


def _box(a, w, axis):
    pad = [(0, 0)] * a.ndim
    pad[axis] = (w // 2 + 1, w // 2)
    c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis, dtype=np.float64)
    hi = np.take(c, np.arange(w, c.shape[axis]), axis=axis)
    lo = np.take(c, np.arange(0, c.shape[axis] - w), axis=axis)
    return ((hi - lo) / w).astype(np.float32)


def blur(a, r):
    """Гаусс радиуса r ≈ три прохода box-фильтра (numpy; PIL не размывает float)."""
    if a.ndim == 3:
        return np.stack([blur(a[..., i], r) for i in range(a.shape[-1])], -1)
    w = max(int(round(np.sqrt(4 * r * r + 1))), 1) | 1
    out = a.astype(np.float32)
    for _ in range(3):
        out = _box(_box(out, w, 0), w, 1)
    return out


def mix(col, c, t):
    t = np.asarray(t, np.float32)
    return col * (1 - t[..., None]) + np.asarray(c, np.float32) * t[..., None]


def extend(maps, own, steps):
    """Продлить значения own-текселей на steps px наружу (ближайший свой тексель) — отступы вокруг островов."""
    idx = np.where(own, np.arange(own.size).reshape(own.shape), -1)
    for _ in range(steps):
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            cand = np.roll(np.roll(idx, dy, 0), dx, 1)
            idx = np.where((idx < 0) & (cand >= 0), cand, idx)
    have = idx >= 0
    src = idx[have]
    for k, v in maps.items():
        flat = v.reshape(own.size, -1) if v.ndim == 3 else v.reshape(-1)
        v[have] = flat[src]
    return have


def down(a):
    """4096 -> 2048 Lanczos, поканально во float."""
    if a.ndim == 2:
        return np.asarray(Image.fromarray(a.astype(np.float32), "F").resize((EXPORT, EXPORT), Image.LANCZOS))
    return np.stack([down(a[..., i]) for i in range(a.shape[-1])], -1)


def build():
    print("load bake")
    nb = load("normal")
    ao = load("ao", "L")
    m1, m2, m3, idc, pos = load("m1"), load("m2"), load("m3"), load("idc"), load("pos")
    mask = load("mask", "L") > 0.5
    cover = load("cover", "L") > 0.5
    mat = np.rint(idc[..., 0] * 32).astype(np.int32)
    board = np.rint(idc[..., 1] * 16).astype(np.int32)
    glow = idc[..., 2]
    grain, cav, dent = m1[..., 0], m1[..., 1], m1[..., 2]
    nail, knot, coat = m2[..., 0], m2[..., 1], m2[..., 2]
    edge, misc, tone = m3[..., 0], m3[..., 1], m3[..., 2]
    P = FV.POS_LO + pos * (FV.POS_HI - FV.POS_LO)
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    M = lambda k: mat == MAT[k]
    wood_light = M("board") | M("ledge") | M("frame")
    nz = lambda a, b, s: (FV.fbm2(a * s, b * s, 77, 3).astype(np.float32) - 0.5)

    print("diffuse")
    col = np.zeros((S, S, 3), np.float32)
    # ---- дерево: тон доски, волокна (гребни светлее, впадины темнее), сучки, полости
    for key, base, var in (("mud", DOOR, 0.07), ("board", DOOR, 0.07), ("ledge", LEDGE, 0.06), ("frame", WFRAME, 0.05), ("side", SIDE, 0.08),
                           ("niche", NICHE, 0.1), ("shelf", SHELF, 0.08), ("grate", GRATE, 0.08), ("peg", PEG, 0.05),
                           ("lamp", LAMPW, 0.05)):
        m = M(key)
        c = base * (1 + var * (tone[m, None] - 0.5) * 2)
        c = c * (0.95 + 0.09 * grain[m, None])
        col[m] = c
    wood = M("board") | M("ledge") | M("frame") | M("side") | M("niche") | M("shelf") | M("grate") | M("peg") | M("lamp")
    col = np.where(wood[..., None], mix(col, KNOT, knot * 0.8), col)
    col = np.where(wood[..., None], col * (1 - 0.55 * cav[..., None]), col)
    col = np.where(wood[..., None], mix(col, col * 1.12, edge * 0.5), col)          # затёртые кромки светлее
    col = np.where(wood[..., None], col * (1 - 0.12 * dent[..., None]), col)
    # ---- сталь: эмаль / голый металл / ржавчина в раковинах и по кромкам сколов
    st = M("steel") | M("plate") | M("stub")
    rusty = np.clip(grain * 1.2 * (1 - coat) + edge * 0.5, 0, 1)
    sc = mix(STEEL[None, None] * np.ones_like(col), RUST, np.clip(rusty * 0.9 + 0.2 * nz(x, y, 0.15), 0, 1))
    sc = mix(sc, ENAMEL, coat)
    sc = mix(sc, RUST_DK, knot * 0.3)                                                  # пузыри ржавчины
    col = np.where(st[..., None], sc, col)
    # площадка замка: старая чёрная краска пятнами на ржавой стали, царапины ключа — светлый металл
    pl = M("plate")
    pc = mix(mix(STEEL[None, None] * np.ones_like(col), RUST, 0.55 + 0.3 * nz(x, y, 0.4)), rgb(38, 36, 34), coat * 0.9)
    pc = mix(pc, STEEL_BRIGHT, misc)
    col = np.where(pl[..., None], pc, col)
    col = np.where(M("stub")[..., None], mix(STEEL * np.ones_like(col), RUST_DK, 0.55 + 0.3 * nz(x, y, 0.5)), col)
    # гвозди, шляпки болтов
    col = np.where(M("nail")[..., None], mix(NAIL * np.ones_like(col), RUST_DK, 0.35 + 0.3 * nz(x, y, 1.0)), col)
    col = np.where(((nail > 0.5) & st)[..., None], mix(col, STEEL, 0.6), col)
    # латунь, циферблаты, стекло окна
    col = np.where(M("brass")[..., None], BRASS * (0.75 + 0.45 * edge[..., None]), col)
    dial = M("dial")
    dc = mix(DIAL * np.ones_like(col), np.where((board == 9)[..., None], RED, BLUE), edge)
    dc = mix(dc, TICK, np.clip(misc, 0, 1))
    col = np.where(dial[..., None], dc, col)
    gl = M("glass")
    gc = mix(FOG * np.ones_like(col), SEE, np.clip(misc * 1.1, 0, 1))
    col = np.where(gl[..., None], gc, col)
    # грязь сапога, лист, пролом
    col = np.where(M("mud")[..., None], mix(col, mix(MUD * np.ones_like(col), MUD_LIGHT, 1 - misc), 0.55 + 0.3 * misc), col)
    col = np.where((M("leaf") & (z > 20))[..., None], LEAF_Y * (0.9 + 0.15 * grain[..., None]), col)
    col = np.where(M("split")[..., None], SPLIT, col)
    col = np.where(M("gap")[..., None], GAP * (1 + 0.3 * (1 - cav[..., None])), col)
    # полотенце, веник
    tw = M("towel")
    tcol = mix(LINEN * (0.92 + 0.12 * grain[..., None]), BRICK, misc * 0.92)
    tcol = mix(tcol, THREAD, edge * 0.6)
    col = np.where(tw[..., None], tcol, col)
    lf = M("leaf") & (z < 0)
    col = np.where(lf[..., None], mix(LEAF_OL * np.ones_like(col), LEAF_KH, tone) * (0.88 + 0.2 * grain[..., None]), col)
    col = np.where(M("twig")[..., None], TWIG * (0.9 + 0.2 * grain[..., None]), col)
    col = np.where(M("twine")[..., None], TWINE * (0.85 + 0.25 * grain[..., None]), col)
    col = np.where(M("glow")[..., None], GLOWC, col)
    col = np.where((M("shelf") & (misc > 0.5))[..., None], col * 0.78, col)

    print("history (no form): water, minerals, rust streaks, grease")
    # мокрый низ: дверца и бок (по высоте; у бока копии не перевёрнуты по высоте)
    wet = sstep(14.0, 0.0, y - 48.0) * M("board") + sstep(12.0, 0.0, y - 15.45) * M("side")
    col = col * (1 - 0.18 * wet[..., None])
    # ржавый потёк из-под площадки замка вниз по волокнам (как в референсе)
    lx, ly = FV.LOCK
    run = sstep(4.5, 1.0, np.abs(x - lx + 2.2 + 0.6 * np.sin(y * 0.4))) * sstep(ly - 7.4, ly - 9.0, y) * sstep(ly - 34.0, ly - 9.0, y)
    run = run * (0.5 + 0.3 * (FV.n2(x * 0.8, y * 0.08, 91) > 0.45))
    col = np.where((wood_light & ~M("plate"))[..., None], mix(col, RUST, run * 0.55), col)
    # ореолы ржавчины вокруг гвоздей на дереве
    halo = np.clip(blur(M("nail").astype(np.float32), 6) * 3.0, 0, 1)
    col = np.where(wood[..., None], mix(col, RUST_DK, halo * 0.45), col)
    # засаленность вокруг замка (misc у досок — полировка руками)
    col = np.where(wood_light[..., None], col * (1 - 0.12 * misc[..., None]), col)
    # минеральные потёки под шпонками бока (редко и слабо — в игре «полосы», §9.6)
    stripes = (FV.n2(z * 1.7, 3.0, 5) > 0.72) * 1.0
    under = np.zeros_like(y)
    for (b0, b1) in FV.BATTENS:
        under = np.maximum(under, sstep(0.0, 1.0, b0 - y) * sstep(b0 - 14.0, b0 - 2.0, y))
    col = np.where(M("side")[..., None], mix(col, MINERAL, under * stripes * 0.12), col)
    # ржавые потёки вниз от сколов на стальном цоколе и карнизе
    col = np.where(st[..., None], mix(col, RUST, (1 - coat) * sstep(20.0, 2.0, y) * 0.25), col)
    # пол ниши: тёмные мокрые пятна и минеральные кольца между рейками
    col = np.where(M("grate")[..., None], col * (1 - 0.15 * (nz(x, z, 0.12) > 0.1)[..., None]), col)

    print("specular/gloss")
    spec = np.full((S, S), 0.06, np.float32)
    gloss = np.full((S, S), 0.2, np.float32)
    spec = np.where(wood, 0.06, spec)
    gloss = np.where(wood, 0.18 + 0.12 * edge + 0.15 * misc * wood_light, gloss)
    gloss = np.where(M("niche"), 0.26, gloss)
    spec = np.where(st, 0.06 + 0.24 * (1 - coat) * (1 - rusty), spec)
    gloss = np.where(st, 0.42 * coat + (0.32 * (1 - rusty) + 0.12 * rusty) * (1 - coat), gloss)
    spec = np.where(pl, 0.1 + 0.3 * misc, spec)
    gloss = np.where(pl, 0.2 + 0.35 * misc, gloss)
    spec = np.where(M("nail"), 0.2, spec)
    gloss = np.where(M("nail"), 0.3, gloss)
    spec = np.where(M("brass"), 0.45, spec)
    gloss = np.where(M("brass"), 0.5 + 0.2 * edge, gloss)
    spec = np.where(dial | gl, 0.22, spec)
    gloss = np.where(dial, 0.86, gloss)
    gloss = np.where(gl, 0.55 + 0.35 * misc, gloss)
    spec = np.where(tw, 0.04, spec)
    gloss = np.where(tw, 0.12, gloss)
    spec = np.where(M("leaf") | M("twig") | M("twine") | M("mud"), 0.05, spec)
    gloss = np.where(M("leaf"), 0.3, np.where(M("mud"), 0.1, gloss))
    spec_rgb = np.repeat(spec[..., None], 3, -1)
    spec_rgb = np.where(M("brass")[..., None], spec[..., None] * np.array([1.0, 0.8, 0.45], np.float32), spec_rgb)

    print("emission")
    em = np.zeros((S, S, 3), np.float32)
    em += (M("glow") * 0.9)[..., None] * WARM
    em += (gl * (0.06 + 0.26 * np.clip(misc, 0, 1)))[..., None] * WARM
    em += (M("split") * 0.3)[..., None] * WARM
    # отсвет пазов под полками и потолком на спинке ниши (спинка одинакова во всех нишах — можно по высоте)
    wash = np.zeros_like(y)
    for ys in (FV.SHELF_Y["A"][0], FV.SHELF_Y["B"][0], 217.45):
        wash = np.maximum(wash, np.exp(-np.clip(ys - y, 0, None) / 16.0) * (y < ys))
    back_obj = (M("niche") | tw | M("leaf") | M("twig") | M("twine") | M("peg")) & (z < -15) & (x < -30)
    em += (back_obj * wash * 0.26)[..., None] * col * WARM * 1.6
    # плафон: свет на дерево вокруг
    llx, lly = FV.LAMP[0], FV.LAMP[1]
    halo_l = np.exp(-np.hypot(x - llx, (y - lly) * 1.3) / 9.0) * (M("niche") | M("lamp"))
    em += (halo_l * 0.3)[..., None] * col * WARM * 1.6

    print("normal: detail x1.5")
    n = nb * 2 - 1
    detail = n - blur(n, 6.0)
    n2 = n + 0.5 * detail
    n2[..., 2] = np.maximum(n2[..., 2], 0.05)
    n2 /= np.linalg.norm(n2, axis=-1, keepdims=True)
    n_out = n2 * 0.5 + 0.5

    occ = np.clip(ao, 0, 1) ** 0.85
    occ = np.where(M("glow") | gl, 1.0, occ)

    # ---- отступы: значения группы продлеваются за кромки островов (не на чужие острова)
    print("padding")
    ids = np.asarray(Image.open(HERE / "uv" / "v6" / "ids.png").convert("RGB").resize((S, S), Image.NEAREST)).astype(np.int32)
    ids = ids[..., 0] + 256 * ids[..., 1]
    mine_isl = np.unique(ids[mask & (ids > 0)])
    foreign = (ids > 0) & ~np.isin(ids, mine_isl)
    maps = {"col": col, "spec": spec_rgb, "gloss": gloss, "em": em, "n": n_out, "occ": occ}
    own = mask & cover
    have = extend(maps, own, 16)
    region = have & ~foreign

    print("merge with", PREV)
    d0 = prev("diffuse", "RGBA")
    n0 = prev("normal", "RGB")
    s0 = prev("specgloss", "RGBA")
    e0 = prev("emission", "RGB")
    o0 = np.asarray(Image.open(HERE / "originals" / "locker_ao.png").convert("L").resize((S, S), Image.LANCZOS), np.float32) / 255
    R = region[..., None]
    diff = np.concatenate([np.where(R, maps["col"], d0[..., :3]), np.where(region, 1.0, d0[..., 3])[..., None]], -1)
    nrm = np.where(R, maps["n"], n0)
    sg = np.concatenate([np.where(R, maps["spec"], s0[..., :3]), np.where(region, maps["gloss"], s0[..., 3])[..., None]], -1)
    emis = np.where(R, maps["em"], e0)
    occl = np.where(region, maps["occ"], o0)
    return dict(diffuse=diff, normal=nrm, specgloss=sg, emission=emis, occlusion=occl, region=region)


def save(a, path, mode):
    a = np.clip(a, 0, 1)
    if a.ndim == 2:
        a = np.repeat(a[..., None], 3, -1)
    Image.fromarray((a * 255 + 0.5).astype(np.uint8), mode).save(path)
    print("  ->", path.name)


def main():
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "v6.0"
    out = build()
    OUT.mkdir(exist_ok=True)
    print("export", EXPORT)
    d = down(out["diffuse"])
    d[..., 3] = np.where(d[..., 3] > 0.5, 1.0, 0.0)          # альфа — как была: вырезы крайних дверец
    save(d, OUT / f"Locker_{tag}_diffuse.png", "RGBA")
    n = down(out["normal"]) * 2 - 1
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-6
    save(n * 0.5 + 0.5, OUT / f"Locker_{tag}_normal.png", "RGB")
    save(down(out["specgloss"]), OUT / f"Locker_{tag}_specgloss.png", "RGBA")
    save(down(out["emission"]), OUT / f"Locker_{tag}_emission.png", "RGB")
    save(down(out["occlusion"]), OUT / f"Locker_{tag}_occlusion.png", "RGB")


if __name__ == "__main__":
    main()
