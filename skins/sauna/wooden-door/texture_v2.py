"""Sauna Door v2.0: карты из запекания bake_v2.py (4096) -> экспорт 1024 (Lanczos; редактор держит у двери 1024).

Форма и всё, у чего она есть, — уже в геометрии (bake/v2/normal, m1-m3, idc). Здесь только:
  - палитра v1.2 (проверена в игре) по маскам той же геометрии: волокно, полость, вмятина, гвоздь, сучок, затёртость;
  - то, у чего формы нет: мокрый низ, ржавые подтёки под гвоздями, минеральные разводы, засаленность у ручки,
    запотевание стекла и свечение за ним;
  - прозрачные потёки: альфа 0 на стекле по fields_door.drip_cut — на переде и сзади в одних и тех же x, y
    (Alpha Cutoff 0.50; с Cutoff 0.00 тот же Diffuse даёт глухое запотевшее стекло с тёмными потёками);
  - Spec/Gloss (Unity Specular), Occlusion из AO, Emission.
Острова, которых v2 ещё не касался (зад, брусья, раскосы, ручка), берутся из v1.2 до своей очереди; у стекла сзади
меняется только альфа (и потёки в цвете).

    .venv/Scripts/python skins/sauna/wooden-door/texture_v2.py [--tag v2.0]
Выход: export/Door_<tag>_{diffuse,normal,specgloss,occlusion,emission}.png (1024).
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "uv"))
import fields_door as FD  # noqa: E402
import texture_v1 as T1  # noqa: E402

BAKE = HERE / "bake" / "v2"
OUT = HERE / "export"
S, EXPORT = 4096, 1024
OLD = "v1.2"
RIM = 0.6                      # v2.3: ободок у края потёков — свечение под ним ярче в (1 + RIM) раз (0 — без ободка, как v2.1)
MAT = FD.MAT
hexc, mix, smooth, vnoise, fbm = T1.hexc, T1.mix, T1.smooth, T1.vnoise, T1.fbm

# палитра v1.2 (texture_v1.py) — в игре проверена
ASPEN, ASPEN_GREY, ASPEN_FRESH = T1.ASPEN, T1.ASPEN_GREY, T1.ASPEN_FRESH
STEAMED, SMOKED, SOOT = T1.STEAMED, T1.SMOKED, T1.SOOT
LINEN, BRICK, RUST, IRON, MINERAL = T1.LINEN, T1.BRICK, T1.RUST, T1.IRON, T1.MINERAL
GLOW_CORE, GLOW_EDGE, LEAF, LEAF_DRY = T1.GLOW_CORE, T1.GLOW_EDGE, T1.LEAF, T1.LEAF_DRY
GAP = hexc("#1E1712")
PUTTY = hexc("#8E8676")
THREAD = hexc("#B3A994")
RUST_RUN = hexc("#6B4630")


def mineral_runs(x, y, gr, seed, step=2.6, keep=0.4):
    """Минеральные дорожки воды (v2.6). Раньше — шум 3/см по x: нити тоньше текселя, идеально прямые («линейки»).
    Теперь отдельные дорожки через ~step см (доля keep): каждая гуляет вбок (±1.5 см на ~25 см, мелкие изломы),
    рвётся на капли и кончается на своей высоте. Вокруг — ореол: вода впиталась в дерево пятнами, вытянутыми по
    волокну, с рваным краем и местами расплывом; по краю — тёмная кайма высохшей воды. Возвращает (ядро, ореол, кайма)."""
    xw = (x + 3.0 * (fbm(x * 0.03, y * 0.04, seed, 3) - 0.5)
          + 1.0 * (vnoise(x * 0.2, y * 0.16, seed + 1) - 0.5)
          + 0.3 * (vnoise(x * 0.5, y * 0.7, seed + 8) - 0.5))
    col = np.floor(xw / step)
    ci = col.astype(np.int64)
    h = lambda k: T1.hash1((ci * 7919 + k * 104729) & 0x7FFFFFFF, seed + k)
    on = h(1) < keep
    cx = (col + 0.5 + 0.5 * (h(2) - 0.5)) * step
    d = np.abs(xw - cx)
    stop = 8.0 + 70.0 * h(3) ** 1.5                     # где дорожка высохла (выше — источник)
    alive = smooth(stop - 3.0, stop + 10.0, y)
    beads = smooth(0.35, 0.65, vnoise(ci * 3.7 + 0.5, y * 0.3, seed + 4))   # разрывы и капли вдоль дорожки
    wcore = 0.14 + 0.1 * vnoise(ci * 5.1 + 0.5, y * 0.2, seed + 5)
    core = smooth(wcore, wcore * 0.3, d) * beads * alive * on
    bloom = 1 + 1.4 * smooth(0.6, 0.9, vnoise(ci * 2.9 + 0.5, y * 0.09, seed + 9))   # местами вода расплылась
    w = (0.8 + 1.0 * fbm(ci * 2.3 + 0.5, y * 0.07, seed + 6, 2)) * bloom
    # рваный край: порог по полю «близость к дорожке + пятна, вытянутые по волокну (по y в 4 раза длиннее)»
    blot = fbm(x * 0.9, y * 0.22, seed + 7, 3) - 0.5
    f = 1 - d / w + 0.9 * blot + 0.15 * (np.clip(gr, 0, 1) - 0.5)
    soak = smooth(0.0, 0.35, f) * (0.55 + 0.45 * fbm(x * 0.3, y * 0.1, seed + 10, 2))
    halo = soak * (0.35 + 0.65 * alive) * on
    tide = np.clip(1 - np.abs(f - 0.02) / 0.08, 0, 1) * (0.35 + 0.65 * alive) * on * 0.7
    return core, halo, tide


def load(name, mode="RGB"):
    return np.asarray(Image.open(BAKE / f"{name}.png").convert(mode), np.float32) / 255.0


def build():
    print("texel -> 3D", S)
    isl_img, pos_img, nz_img = T1.texel_points()
    bmask = load("mask", "L") > 0.5
    F = bmask & (isl_img == 2)
    x, y, z = (pos_img[F][:, i] * 100.0 for i in range(3))
    nz = nz_img[F]
    nb, ao = load("normal")[F], load("ao", "L")[F]
    m1, m2, m3, idc = load("m1")[F], load("m2")[F], load("m3")[F], load("idc")[F]
    cover = load("cover", "L")[F] > 0.5
    mat = np.rint(idc[:, 0] * 32).astype(np.int32)
    board = np.rint(idc[:, 1] * 16).astype(np.int32)
    grain, cav, dent = m1[:, 0], m1[:, 1], m1[:, 2]
    nail, knot, wear = m2[:, 0], m2[:, 1], m2[:, 2]
    r3, g3, tone = m3[:, 0], m3[:, 1], m3[:, 2]
    n = len(x)
    print("front texels", n, "no-hit", int((~cover).sum()))
    is_ = lambda k: mat == MAT[k]
    front_face = z > 4.5                          # плоскость переда (кромки — ниже)
    wood = (is_("board") | is_("patch")) & front_face
    frame = is_("frame") | is_("sill")

    col = np.zeros((n, 3), np.float32)
    spec = np.full(n, 0.05, np.float32)
    gloss = np.full(n, 0.16, np.float32)
    emis = np.zeros((n, 3), np.float32)

    # ---------------- дерево переда: тон доски (v1.2), волокна — по маске гребней геометрии (поздняя древесина темнее)
    tw_ = np.clip(tone, 0, 1)
    tn = mix(mix(ASPEN_GREY, ASPEN, np.clip(tw_ * 1.4, 0, 1)), ASPEN_FRESH, np.clip(tw_ - 0.6, 0, 1) * 0.9)
    tn = mix(tn, ASPEN_GREY, 0.45) * 0.90
    blotch = fbm(x * 0.07 + board * 3.1, y * 0.03, 9)
    gr = np.clip(grain, 0, 1)
    cf = tn * (1.03 - 0.10 * gr)[:, None] * (0.92 + 0.16 * blotch)[:, None]     # v2.1: в игре волокна «нарисованы» — тише
    cf = cf * (1 + 0.05 * (fbm(x * 0.9 + board * 7, y * 0.05, 3) - 0.5))[:, None]       # тонкие полосы ранней/поздней
    # мокрый низ (пар и вода с пола): рваный верхний край на каждой доске (как v1.2)
    rnd = ((board * 0.618) % 1.0).astype(np.float32)
    level = 36.0 + 16.0 * (vnoise(x * 0.09, x * 0 + 1.0, 31) - 0.5) + (rnd - 0.5) * 16.0
    yy = y + 7.0 * (vnoise(x * 1.6, y * 0.05, 32) - 0.5)
    wet = smooth(level + 9.0, level - 6.0, yy)
    damp = smooth(105.0, 25.0, y) * 0.22
    WET = STEAMED * 0.42 + SMOKED * 0.36 + ASPEN_GREY * 0.22
    cf = mix(cf, WET * (0.92 + 0.14 * (1 - gr))[:, None], np.clip(wet * 0.9 + damp, 0, 1))
    cf = mix(cf, SMOKED * 1.05, smooth(16.0, 0.0, y) * 0.55)
    # руки: засаленность у ручки по маске затёртости геометрии + мазок вниз
    hx, hy = FD.HANDLE
    smear = np.exp(-((x - hx - 1.0) / 5.0) ** 2) * smooth(55.0, 100.0, y) * (y < hy) * 0.7
    grime = np.clip(np.maximum(wear, smear) * (0.75 + 0.5 * blotch), 0, 1) * 0.6
    cf = mix(cf, STEAMED * 0.80, grime)
    # вода из-под подоконника
    wx0, wx1, wy0, wy1 = FD.WINDOW
    under = smooth(wx0 - 3, wx0 + 2, x) * smooth(wx1 + 4, wx1 - 1, x) * (y < FD.SILL[2])
    runs = (vnoise(x * 2.3, y * 0.02, 41) > 0.62) * under * smooth(55.0, wy0, y) ** 1.5
    cf = mix(cf, STEAMED * 0.9, np.clip(under * smooth(95.0, wy0, y) * 0.25 + runs * 0.3, 0, 1))
    # белые минеральные разводы в мокрой зоне и под подоконником (v2: реже и тише — урок полока)
    core, halo, tide = mineral_runs(x, y, gr, 43)
    env = smooth(2.0, 10.0, y) * smooth(level + 12, level - 12, y) * (0.4 + 0.6 * vnoise(x * 0.14, y * 0, 45))
    env = np.maximum(env, under * smooth(75.0, wy0 - 3, y) * 0.7 * (vnoise(x * 1.2, y * 0, 46) > 0.5))
    env = np.clip(env * 1.6, 0, 1)
    cf = mix(cf, cf * 0.9, tide * env * 0.5)
    cf = mix(cf, mix(cf, MINERAL, 0.5), halo * env * 0.45)
    cf = mix(cf, MINERAL, core * env * 0.4)
    # рамка и подоконник: та же осина, серее и выветреннее
    fc = mix(cf, ASPEN_GREY * (0.92 + 0.12 * (1 - gr))[:, None], 0.55)
    cf = np.where(frame[:, None], fc, cf)
    # сучки — тёмная смола по маске геометрии; вмятины чуть темнее (смятое волокно, грязь)
    cf = mix(cf, SMOKED * 0.9, np.clip(knot, 0, 1) * 0.8)
    cf = cf * (1 - 0.1 * dent)[:, None]
    # ржавые подтёки: под шляпками и загнутыми концами, вниз по доске
    fr = FD.Front()
    pts = [(hx_ / 100, hy_ / 100) for hx_, hy_, _ in fr.heads] + [(cx / 100, cy / 100) for cx, cy, _a, _l in fr.clinch]
    canvas, cx0, cy0, sc = T1.nail_runs(pts, 0.04, np.random.default_rng(23))
    run = T1.sample(canvas, x / 100, y / 100, cx0, cy0, sc)
    cf = mix(cf, RUST_RUN, np.clip(run, 0, 1) * 0.42)
    # трещины, щели, дыры — темно по маске полостей
    cf = mix(cf, GAP, np.clip(cav * 1.05, 0, 1) * 0.85)
    woodish = wood | frame
    col[woodish] = cf[woodish]
    gloss[woodish] = (0.17 + 0.05 * gr + 0.30 * wet + 0.25 * grime)[woodish]

    # ---------------- сталь: в щелях и полосой по кромке
    st = is_("steel") | is_("gap")
    rn = fbm(x * 0.4, y * 0.4, 61)
    sc_ = mix(mix(hexc("#4A3024"), IRON, smooth(0.3, 0.7, rn)), RUST * 0.75, smooth(0.62, 0.92, fbm(x * 0.9, y * 0.9 + z, 62)) * 0.4)
    sc_ = mix(sc_, GAP, np.clip(cav * 0.6, 0, 1))
    col[st] = sc_[st]
    gloss[st], spec[st] = 0.22, 0.12

    # ---------------- железо: шляпки, загнутые концы, гвоздь-крюк
    ir = is_("nail") | is_("hook")
    rr = fbm(x * 1.6, y * 1.6, 63)
    # v2.0 черновик: рыжие шляпки и концы читались «перцем» и красными царапинами — тёмное железо, ржавчина бурая
    ic = mix(IRON, hexc("#5A3A28"), smooth(0.35, 0.8, rr + 0.1) * 0.5)
    col[ir] = ic[ir]
    gloss[ir], spec[ir] = 0.32, 0.22
    # v2.2: сплющенный молотком стержень загнутого конца — светлый тёртый металл (в v2.0–v2.1 тёмный читался прорезью)
    cl = np.zeros(n, np.float32)
    for (cx, cy, a0, L) in fr.clinch:
        sel = ir & (np.abs(x - cx) < L + 1) & (np.abs(y - cy) < L + 1)
        if not sel.any():
            continue
        u = (x[sel] - cx) * np.cos(a0) + (y[sel] - cy) * np.sin(a0)
        v = -(x[sel] - cx) * np.sin(a0) + (y[sel] - cy) * np.cos(a0)
        half = 0.5 * (1 - 0.45 * np.clip(u / L, 0, 1)) + 0.06
        cl[sel] = np.maximum(cl[sel], ((u > -0.3) & (u < L)) * np.clip(1 - np.abs(v) / half, 0, 1) ** 0.5)
    cl = cl * ir
    col = mix(col, hexc("#7C746B") * (0.9 + 0.2 * rr)[:, None], cl * 0.75)
    gloss = np.where(cl > 0.3, 0.45, gloss)

    # ---------------- замазка: старая, серо-охристая, грязная в трещинах
    pu = is_("putty")
    pc = PUTTY * (0.9 + 0.2 * fbm(x * 0.8, y * 0.8, 65))[:, None]
    pc = mix(pc, GAP, np.clip(cav * 1.2, 0, 1) * 0.7)
    col[pu] = pc[pu]
    gloss[pu], spec[pu] = 0.25, 0.05

    # ---------------- стекло: запотевшее, свет каменки за ним (v1.2); потёки — насквозь
    gl = is_("glass")
    xi0, xi1, yi0, yi1 = FD.PANE
    u = np.clip((x - xi0) / (xi1 - xi0), 0, 1)
    v = np.clip((y - yi0) / (yi1 - yi0), 0, 1)
    heat = np.clip((1 - v) ** 1.1 * (0.62 + 0.38 * np.exp(-((u - 0.47) / 0.42) ** 2)) + 0.14, 0, 1)
    fog = 0.72 + 0.28 * fbm(x * 0.2, y * 0.2, 91)
    cut = FD.drip_cut(x, y) * gl
    rim = np.clip(smooth(0.0, 0.5, cut) - smooth(0.5, 1.0, cut), 0, 1)
    border = np.minimum(np.minimum(u, 1 - u) * (xi1 - xi0), np.minimum(v, 1 - v) * (yi1 - yi0))
    edge_dirt = smooth(3.0, 0.0, border)
    g_day = mix(hexc("#8F7458"), hexc("#BC966C"), heat) * fog[:, None]
    g_day = mix(g_day, hexc("#5A4636"), edge_dirt * 0.6)
    # под дырками (видно только при Alpha Cutoff 0): темнее — глухой вариант тоже читается потёками.
    # Тёмная кайма по краю дырки в черновике читалась прожжённой бумагой — края не темним.
    g_day = mix(g_day, hexc("#6A4C34"), np.clip(cut, 0, 1) * 0.7)
    col[gl] = g_day[gl]
    gloss[gl] = (0.45 + 0.35 * cut - 0.15 * edge_dirt)[gl]
    spec[gl] = 0.16
    e_col = mix(GLOW_CORE, GLOW_EDGE, np.clip(heat * 1.25 - 0.1, 0, 1) ** 1.2)
    e_int = (0.13 + 0.40 * heat ** 1.2) * (0.94 + 0.06 * fbm(x * 0.09, y * 0.09, 96)) * (1 - 0.7 * edge_dirt) * (1 - cut)
    emis[gl] = (e_col * e_int[:, None])[gl]
    near = (frame | pu) & (x > xi0 - 1.6) & (x < xi1 + 1.6) & (y > yi0 - 2.0) & (y < yi1 + 1.6)
    spill = 0.045 * (0.4 + 0.6 * np.clip(1 - (y - yi0) / (yi1 - yi0), 0, 1))
    emis[near] = (GLOW_CORE * spill[:, None] * col.mean(1, keepdims=True) * 2.2)[near]
    alpha = np.ones(n, np.float32)
    alpha[gl] = 1 - cut[gl]

    # ---------------- полотенце: застиранный лён, кирпичные полосы, строчка на подгибах
    tw = is_("towel")
    stitch, stripe, hem = np.clip(r3, 0, 1), np.clip(g3, 0, 1), np.clip(tone, 0, 1)
    cloth = LINEN * (0.92 + 0.08 * fbm(x * 0.3, y * 0.3, 71))[:, None]
    cloth = mix(cloth, hexc("#A89C86"), fbm(x * 0.09, y * 0.09, 72) * 0.35)
    strc = mix(BRICK, LINEN, 0.22 + 0.25 * fbm(x * 0.6, y * 0.6, 73))
    ct = mix(cloth, strc, stripe)
    ct = mix(ct, THREAD, stitch * 0.5)
    ct = mix(ct, ct * 0.8, smooth(142.0, 125.0, y) * 0.18)                              # подол влажный
    col[tw] = ct[tw]
    gloss[tw], spec[tw] = 0.08, 0.03

    # ---------------- листья
    lf = is_("leaf")
    lc = mix(mix(LEAF, LEAF_DRY, 0.45 + 0.4 * fbm(x * 0.7, y * 0.7, 81)), hexc("#5E5232"), 0.35)   # не «салат» (урок полока)
    lc = lc * (0.85 + 0.2 * np.clip(grain, 0, 1))[:, None]
    col[lf] = lc[lf]
    gloss[lf], spec[lf] = 0.4, 0.06

    # ---------------- кромки двери: доска переда, лист, доска зада, торцы брусьев
    side = ~front_face & ~st & ~ir & ~tw & ~lf
    back_layer = side & (z < 1.3)
    ec = np.where((z > 4.0)[:, None], tn * (1.0 - 0.15 * gr)[:, None], STEAMED * (0.95 - 0.2 * gr)[:, None])
    ec = np.where(is_("rail_end")[:, None], STEAMED * (0.85 + 0.25 * gr)[:, None], ec)
    ec = mix(ec, GAP, np.clip(cav, 0, 1))
    col[side] = ec[side]
    gloss[side] = 0.2
    del back_layer

    # ---------------- пропуски запекания — цвет доски, ровная нормаль
    miss = ~cover
    col[miss] = (tn * 0.9)[miss]
    nb[miss] = (0.5, 0.5, 1.0)

    # ---------------- AO в цвет (Occlusion в игре только приглушает рассеянный свет)
    soft = tw | gl
    col = col * np.where(soft, 0.75 + 0.25 * ao, (0.45 + 0.55 * ao) ** 0.9)[:, None]
    occ = np.where(tw, 0.55 + 0.45 * ao, np.where(gl, 1.0, 0.35 + 0.65 * ao))
    col = np.clip(col, 0.02, 0.92)

    def med(m):
        c = (np.median(col[m], 0) * 255).astype(int)
        return "#%02X%02X%02X" % tuple(c)
    dry = wood & (y > 60) & (y < 200) & (cav < 0.1) & (wear < 0.1)
    print("median: front dry", med(dry), "| wet low", med(wood & (y < 20)), "| towel", med(tw), "| glass", med(gl),
          "| see-through %.1f%% of glass" % (100 * (cut[gl] > 0.5).mean()))
    return dict(F=F, isl=isl_img, pos=pos_img, col=col, spec=spec, gloss=gloss, emis=emis, alpha=alpha, occ=occ, nrm=nb,
                glass=gl.astype(np.float32))


def fblur(a, r, passes=3):
    a = a.astype(np.float32)
    for _ in range(passes):
        for ax in (0, 1):
            pad = [(0, 0), (0, 0)]
            pad[ax] = (r + 1, r)
            c = np.cumsum(np.pad(a, pad, mode="edge"), axis=ax, dtype=np.float64)
            hi = np.take(c, np.arange(2 * r + 1, c.shape[ax]), axis=ax)
            lo = np.take(c, np.arange(0, c.shape[ax] - 2 * r - 1), axis=ax)
            a = ((hi - lo) / (2 * r + 1)).astype(np.float32)
    return a


def down(a):
    if a.ndim == 2:
        return np.asarray(Image.fromarray(a.astype(np.float32), "F").resize((EXPORT, EXPORT), Image.LANCZOS), np.float32)
    return np.stack([down(a[..., c]) for c in range(a.shape[-1])], -1)


BACK_ISL = (0, 1, 3, 4, 5, 6, 7)      # зад, брусья с кромками, раскосы (v2.4)
HANDLE_ISL = (8, 9)                    # ручка (v2.7): обе копии на одних текселях — только симметричное
HANDLE_WOOD = hexc("#614B39")          # тон v1.2 (медиана #534131): тёмная, засаленная
HANDLE_GREASE = hexc("#3F3125")
JUTE = hexc("#94805F")
JUTE_GRIME = hexc("#5E4F3B")


def glass_paint(x, y, gl, col, gloss, spec, emis, frame_like):
    """Стекло (обе стороны одинаково): запотевшее, свет каменки за ним; потёки — насквозь. Возвращает альфу."""
    xi0, xi1, yi0, yi1 = FD.PANE
    u = np.clip((x - xi0) / (xi1 - xi0), 0, 1)
    v = np.clip((y - yi0) / (yi1 - yi0), 0, 1)
    heat = np.clip((1 - v) ** 1.1 * (0.62 + 0.38 * np.exp(-((u - 0.47) / 0.42) ** 2)) + 0.14, 0, 1)
    fog = 0.72 + 0.28 * fbm(x * 0.2, y * 0.2, 91)
    cut = FD.drip_cut(x, y) * gl
    border = np.minimum(np.minimum(u, 1 - u) * (xi1 - xi0), np.minimum(v, 1 - v) * (yi1 - yi0))
    edge_dirt = smooth(3.0, 0.0, border)
    g_day = mix(hexc("#8F7458"), hexc("#BC966C"), heat) * fog[:, None]
    g_day = mix(g_day, hexc("#5A4636"), edge_dirt * 0.6)
    g_day = mix(g_day, hexc("#6A4C34"), np.clip(cut, 0, 1) * 0.7)
    col[gl] = g_day[gl]
    gloss[gl] = (0.45 + 0.35 * cut - 0.15 * edge_dirt)[gl]
    spec[gl] = 0.16
    e_col = mix(GLOW_CORE, GLOW_EDGE, np.clip(heat * 1.25 - 0.1, 0, 1) ** 1.2)
    e_int = (0.13 + 0.40 * heat ** 1.2) * (0.94 + 0.06 * fbm(x * 0.09, y * 0.09, 96)) * (1 - 0.7 * edge_dirt) * (1 - cut)
    emis[gl] = (e_col * e_int[:, None])[gl]
    near = frame_like & (x > xi0 - 1.6) & (x < xi1 + 1.6) & (y > yi0 - 2.0) & (y < yi1 + 1.6)
    spill = 0.045 * (0.4 + 0.6 * np.clip(1 - (y - yi0) / (yi1 - yi0), 0, 1))
    emis[near] = (GLOW_CORE * spill[:, None] * col.mean(1, keepdims=True) * 2.2)[near]
    alpha = np.ones(len(x), np.float32)
    alpha[gl] = 1 - cut[gl]
    return alpha, cut


def build_back(isl_img, pos_img):
    """Зад, брусья, колодка, раскосы, петли, кромки — палитра v1.2 (проверена в игре) по маскам геометрии."""
    bmask = load("mask", "L") > 0.5
    F = bmask & np.isin(isl_img, BACK_ISL)
    if not F.any():
        return None
    x, y, z = (pos_img[F][:, i] * 100.0 for i in range(3))
    nb, ao = load("normal")[F], load("ao", "L")[F]
    m1, m2, m3, idc = load("m1")[F], load("m2")[F], load("m3")[F], load("idc")[F]
    cover = load("cover", "L")[F] > 0.5
    mat = np.rint(idc[:, 0] * 32).astype(np.int32)
    board = np.rint(idc[:, 1] * 16).astype(np.int32)
    grain, cav, dent = m1[:, 0], m1[:, 1], m1[:, 2]
    nail, knot, wear = m2[:, 0], m2[:, 1], m2[:, 2]
    tone = m3[:, 2]
    n = len(x)
    print("back texels", n, "no-hit", int((~cover).sum()))
    is_ = lambda *k: np.isin(mat, [MAT[i] for i in k])
    col = np.zeros((n, 3), np.float32)
    spec = np.full(n, 0.05, np.float32)
    gloss = np.full(n, 0.2, np.float32)
    emis = np.zeros((n, 3), np.float32)
    gr = np.clip(grain, 0, 1)
    up = smooth(15.0, 205.0, y)
    blotch = fbm(x * 0.07 + board * 3.1, y * 0.03, 59)

    # ---------------- дерево парной: распаренное, кверху темнее (v1.2), брусья и раскосы чуть светлее
    wood = is_("board", "frame", "sill", "rail", "brace")
    tn = mix(STEAMED * 1.02, SMOKED * 1.12, up ** 0.85) * (0.86 + 0.28 * np.clip(tone, 0, 1))[:, None]
    planks = is_("rail", "brace")
    tn = np.where(planks[:, None], tn * 1.13, tn)
    fb = is_("frame", "sill")
    tn = np.where(fb[:, None], mix(STEAMED * 1.15, SMOKED * 1.3, up * 0.6), tn)
    cb = tn * (1.05 - 0.15 * gr)[:, None] * (0.9 + 0.2 * blotch)[:, None]    # 0.24 в рендере — брусья «вельветом»
    cb = cb * (1 - 0.12 * np.clip(dent, 0, 1))[:, None]                     # дно лунок топора темнее
    soot = np.clip(smooth(145.0, 208.0, y) * (0.45 + 0.6 * fbm(x * 0.05, y * 0.05, 51)), 0, 1)
    cb = mix(cb, SOOT, soot * 0.7)
    # затёртые кромки брусьев, раскосов и рамки — светлее (по маске скругления геометрии)
    cb = mix(cb, hexc("#8C7B66"), np.clip(wear, 0, 1) * (0.40 - 0.25 * soot) * (planks | fb | is_("board")))
    wetb = smooth(50.0, 0.0, y + 25.0 * (fbm(x * 0.06, y * 0.04, 52) - 0.5)) * 0.8
    cb = mix(cb, cb * 0.62, wetb)
    # минеральные полосы от подоконника вниз (вода с окна), тоньше по всей двери
    wx0, wx1, wy0, wy1 = FD.WINDOW
    underb = smooth(wx0 - 4, wx0 + 3, x) * smooth(wx1 + 5, wx1 - 2, x) * (y < FD.SILL[2])
    coreb, halob, tideb = mineral_runs(x, y, gr, 53, step=3.0, keep=0.35)
    envb = underb * smooth(5.0, 50.0, y) * 0.9 + (1 - underb) * smooth(120.0, 20.0, y) * 0.35 * (vnoise(x * 0.11, y * 0, 55) > 0.45)
    envb = np.clip(envb * 1.4, 0, 1) * np.where(planks, 0.5, 1.0)
    cb = mix(cb, cb * 0.9, tideb * envb * 0.5)
    cb = mix(cb, mix(cb, MINERAL * 0.92, 0.5), halob * envb * 0.4)
    cb = mix(cb, MINERAL * 0.92, coreb * envb * 0.35)
    # подтёки сажи под гвоздями
    fr = FD.Front()
    bk = FD.Back()
    pts = [(a / 100, b / 100) for a, b, _ in bk.heads] + [(a / 100, b / 100) for a, b in fr.through_rails + fr.through_braces]
    canvas, cx0, cy0, scl = T1.nail_runs(pts, 0.03, np.random.default_rng(29))
    cb = mix(cb, SOOT * 1.2, np.clip(T1.sample(canvas, x / 100, y / 100, cx0, cy0, scl), 0, 1) * 0.45)
    cb = mix(cb, SMOKED * 0.75, np.clip(knot, 0, 1) * 0.55)          # почти чёрные сучки читались дырками
    cb = mix(cb, GAP, np.clip(cav * 1.05, 0, 1) * 0.85)
    # v1 в игре: зад уходил в рыжий — насыщенность −30 %
    cb = mix(cb, cb.mean(1, keepdims=True) * np.array([1.06, 1.0, 0.93], np.float32), 0.30) * 0.94
    col[wood] = cb[wood]
    gloss[wood] = (0.22 + 0.10 * gr + 0.35 * wetb + 0.12 * (1 - soot))[wood]

    # ---------------- торцы: досок на кромках двери и брусьев на боковых кромках
    en = is_("end", "rail_end")
    front_layer = z > 3.0
    ec = np.where(front_layer[:, None], mix(ASPEN_GREY, STEAMED, 0.35) * 0.85, STEAMED * 0.95)
    ec = ec * (0.85 + 0.25 * gr)[:, None] * (1 - 0.3 * smooth(30.0, 0.0, y))[:, None]
    ec = mix(ec, SOOT, soot * 0.6)
    ec = mix(ec, GAP, np.clip(cav, 0, 1))
    col[en] = ec[en]
    gloss[en] = 0.18

    # ---------------- сталь, железо (в парной — чёрное от сажи), петли, проволока
    st = is_("steel", "gap")
    rn = fbm(x * 0.4, y * 0.4 + z, 61)
    sc_ = mix(mix(hexc("#4A3024"), IRON, smooth(0.3, 0.7, rn)), RUST * 0.75, smooth(0.62, 0.92, fbm(x * 0.9, y * 0.9 + z, 62)) * 0.4)
    col[st] = mix(sc_, GAP, np.clip(cav * 0.6, 0, 1))[st]
    gloss[st], spec[st] = 0.22, 0.12
    ir = is_("nail") | (is_("hinge") & (nail > 0.5))
    rr = fbm(x * 1.6, y * 1.6, 63)
    col[ir] = mix(mix(IRON, hexc("#5A3A28"), smooth(0.35, 0.8, rr) * 0.4), SOOT * 1.3, 0.45)[ir]
    gloss[ir], spec[ir] = 0.3, 0.2
    hg = is_("hinge") & ~ir
    hc = mix(IRON * 1.1, RUST * 0.9, smooth(0.3, 0.75, fbm(x * 0.5, y * 0.5, 64) + 0.15) * 0.55)
    hc = mix(hc, hexc("#6E655C"), np.clip(wear, 0, 1) * 0.35)                 # рёбра полосы и шарнира затёрты
    col[hg] = hc[hg]
    gloss[hg], spec[hg] = 0.32, 0.2
    wi = is_("wire")
    col[wi] = mix(hexc("#4A4038"), RUST * 0.8, 0.3 + 0.4 * gr)[wi]
    gloss[wi], spec[wi] = 0.3, 0.22

    # ---------------- окно сзади: замазка и стекло — как спереди
    pu = is_("putty")
    col[pu] = mix(PUTTY * 0.85 * (0.9 + 0.2 * fbm(x * 0.8, y * 0.8, 65))[:, None], GAP, np.clip(cav * 1.2, 0, 1) * 0.7)[pu]
    gloss[pu] = 0.25
    gl = is_("glass")
    alpha, cut = glass_paint(x, y, gl, col, gloss, spec, emis, fb | pu)

    miss = ~cover
    col[miss] = (tn * 0.9)[miss]
    nb[miss] = (0.5, 0.5, 1.0)
    soft = gl
    col = col * np.where(soft, 1.0, (0.45 + 0.55 * ao) ** 0.9)[:, None]
    occ = np.where(gl, 1.0, 0.35 + 0.65 * ao)
    col = np.clip(col, 0.02, 0.92)

    def med(m):
        return "#%02X%02X%02X" % tuple((np.median(col[m], 0) * 255).astype(int)) if m.any() else "-"
    print("median: back boards", med(is_("board") & (y > 40) & (y < 140)), "| rails", med(is_("rail")),
          "| braces", med(is_("brace")), "| hinges", med(hg), "| see-through %.1f%% of back glass" % (100 * (cut[gl] > 0.5).mean()))
    return dict(F=F, col=col, spec=spec, gloss=gloss, emis=emis, alpha=alpha, occ=occ, nrm=nb, glass=gl.astype(np.float32),
                isls=sorted(set(isl_img[F].tolist())))


def build_handle(isl_img, pos_img):
    """Ручка: дерево тоном v1.2, засаленный хват; бечёвка — джут, грязнее посередине хвата, свив светлее."""
    bmask = load("mask", "L") > 0.5
    F = bmask & np.isin(isl_img, HANDLE_ISL)
    if not F.any():
        return None
    P = pos_img[F] * 100.0
    lx, ly = P[:, 0] - FD.HC[0], P[:, 1] - FD.HC[1]
    lz = np.where(P[:, 2] < 0, FD.HANDLE_MIRROR - P[:, 2], P[:, 2])      # копия сзади → в координаты переда
    nb, ao = load("normal")[F], load("ao", "L")[F]
    m1, m2, idc = load("m1")[F], load("m2")[F], load("idc")[F]
    cover = load("cover", "L")[F] > 0.5
    mat = np.rint(idc[:, 0] * 32).astype(np.int32)
    gr, cav, dent, wear = np.clip(m1[:, 0], 0, 1), m1[:, 1], m1[:, 2], np.clip(m2[:, 2], 0, 1)
    n = len(lx)
    tw = mat == MAT["twine"]
    col = np.zeros((n, 3), np.float32)
    spec = np.full(n, 0.06, np.float32)
    gloss = np.full(n, 0.3, np.float32)
    # дерево: волокно, засаленность по маске затёртости (темнее и глаже), забоины и трещина темнее
    blot = fbm(lx * 0.4, ly * 0.4 + lz * 0.3, 71)
    wood = HANDLE_WOOD * ((1.04 - 0.16 * gr) * (0.92 + 0.16 * blot))[:, None]
    wood = mix(wood, HANDLE_GREASE, wear * 0.45)
    wood = mix(wood, wood * 0.7, np.clip(dent, 0, 1) * 0.5)
    wood = mix(wood, GAP, np.clip(cav, 0, 1) * 0.8)
    col[:] = wood
    gloss[:] = 0.3 + 0.3 * wear
    spec[:] = 0.06 + 0.03 * wear
    # бечёвка: свив (рёбра прядей светлее), грязь хвата — сильнее у середины половинок, где пальцы
    grip = np.exp(-((np.abs(lx) - 3.9) / 1.6) ** 2)
    jute = mix(JUTE * (0.94 + 0.12 * fbm(lx * 1.5, ly * 1.5 + lz, 72))[:, None], JUTE_GRIME, 0.25 + 0.3 * grip)
    jute = jute * (0.88 + 0.18 * np.clip(m1[:, 0], 0, 1))[:, None]
    col[tw] = jute[tw]
    gloss[tw] = 0.14 + 0.1 * grip[tw]
    spec[tw] = 0.04
    miss = ~cover
    col[miss] = HANDLE_WOOD * 0.9
    nb[miss] = (0.5, 0.5, 1.0)
    # бечёвка: бороздки между витками по 1–2 px в 1024 — полный AO давал «зебру»; на ней AO слабее
    aok = np.where(tw, 0.7 + 0.3 * ao, (0.45 + 0.55 * ao) ** 0.9)
    col = col * aok[:, None]
    occ = np.where(tw, 0.6 + 0.4 * ao, 0.35 + 0.65 * ao)
    col = np.clip(col, 0.02, 0.92)
    med = lambda m: "#%02X%02X%02X" % tuple((np.median(col[m], 0) * 255).astype(int)) if m.any() else "-"
    print("handle texels", n, "no-hit", int(miss.sum()), "| median wood", med(~tw), "| twine", med(tw), "(v1.2 #534131)")
    z = np.zeros(n, np.float32)
    return dict(F=F, col=col, spec=spec, gloss=gloss, emis=np.zeros((n, 3), np.float32), alpha=z + 1, occ=occ, nrm=nb,
                glass=z, isls=sorted(set(isl_img[F].tolist())))


def main():
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "v2.0"
    r = build()
    isl = r["isl"]
    rb = build_back(isl, r["pos"])
    rh = build_handle(isl, r["pos"])
    parts = [r] + [q_ for q_ in (rb, rh) if q_]
    baked = [2] + (rb["isls"] if rb else []) + (rh["isls"] if rh else [])
    print("baked islands:", baked)
    F = np.zeros((S, S), bool)
    for q_ in parts:
        F |= q_["F"]

    def img(key, ch):
        a = np.zeros((S, S, ch), np.float32)
        for q_ in parts:
            a[q_["F"]] = np.asarray(q_[key], np.float32).reshape(-1, ch)
        return a
    # v2.2–v2.3: по краю каждой дорожки — тонкий ободок свечения (край воды ловит свет): ночью дорожки читаются водой,
    # а не чёрными трещинами. Ширина ~1.5 px в 1024
    gl_img = img("glass", 1)[..., 0]
    hole = (1 - img("alpha", 1)[..., 0]) * gl_img
    ring = np.clip(fblur(hole, 5) * 2.5 - hole * 3.0, 0, 1) * gl_img * (hole < 0.5)
    # v2.3: не своя жёлтая яркость (v2.2: вверху стекла, где свечение тусклое, читалось неоновой обводкой), а то же
    # свечение, только ярче у края: внизу заметно, вверху еле видно
    e_img = img("emis", 3) * (1 + RIM * ring)[..., None]
    print("rim texels (4096):", int((ring > 0.2).sum()))
    maps = {"col": img("col", 3), "spec": img("spec", 1), "gloss": img("gloss", 1), "emis": e_img,
            "alpha": img("alpha", 1), "occ": img("occ", 1), "nrm": img("nrm", 3)}
    # ближайший остров для каждого пустого текселя (отступы делятся между соседями пополам)
    owner = isl.astype(np.int16).copy()
    for _ in range(48):
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            src = np.roll(np.roll(owner, dy, 0), dx, 1)
            take = (owner < 0) & (src >= 0)
            owner[take] = src[take]
    # отступ: свои тексели продлеваются на 40 px (4096) в пустые, ближние к перёду
    filled = F.copy()
    for _ in range(40):
        new = np.zeros_like(filled)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            src = np.roll(np.roll(filled, dy, 0), dx, 1)
            take = ~filled & ~new & src & np.isin(owner, baked) & (isl < 0)
            for k, a in maps.items():
                sh = np.roll(np.roll(a, dy, 0), dx, 1)
                a[take] = sh[take]
            new |= take
        filled |= new
    maps["alpha"][~filled] = 1.0
    print("downscale")
    d = {k: down(v) for k, v in maps.items()}
    use = down((np.isin(owner, baked) & filled).astype(np.float32)) > 0.5
    old = lambda nm, mode: np.asarray(Image.open(OUT / f"Door_{OLD}_{nm}.png").convert(mode), np.float32) / 255
    od, on, osg, oo, oe = old("diffuse", "RGBA"), old("normal", "RGB"), old("specgloss", "RGBA"), old("occlusion", "L"), old("emission", "RGB")

    dif = od.copy()
    dif[..., :3] = np.where(use[..., None], d["col"], od[..., :3])
    dif[..., 3] = np.where(use, np.clip(d["alpha"][..., 0], 0, 1), 1.0)
    dif[..., 3] = np.where(dif[..., 3] > 0.97, 1.0, dif[..., 3])     # v2.4: Lanczos у лужиц давал 254 вне стекла
    # стекло сзади (v1.2): та же маска потёков по x, y — альфа и потёки в цвете
    # v2.1: маска сзади считается в 4096 и уменьшается так же, как перед (в v2.0 — сразу в 1024, края ступенькой)
    P4 = r["pos"] * 100.0
    xi0, xi1, yi0, yi1 = FD.PANE
    bg4 = (isl == 4) & (4 not in baked) & (P4[..., 0] > xi0 + 1.3) & (P4[..., 0] < xi1 - 1.3) & (P4[..., 1] > yi0 + 1.3) & (P4[..., 1] < yi1 - 1.3)
    c4 = np.zeros((S, S), np.float32)
    c4[bg4] = FD.drip_cut(P4[..., 0][bg4], P4[..., 1][bg4])
    back_glass = down(bg4.astype(np.float32)) > 0.5
    cb = np.clip(down(c4), 0, 1) * back_glass
    dif[..., 3] = np.where(back_glass, 1 - cb, dif[..., 3])
    dif[..., :3] = np.where(back_glass[..., None], mix(dif[..., :3].reshape(-1, 3), hexc("#5E4430"), (cb * 0.75).reshape(-1)).reshape(dif[..., :3].shape), dif[..., :3])
    if back_glass.any():
        print("back glass (v1.2) texels (1024)", int(back_glass.sum()), "see-through %.1f%%" % (100 * (cb[back_glass] > 0.5).mean()))

    # нормаль: мелкая деталь ×1.5 (днём в игре рельеф слабее), крупная поправка на сглаженную модель — как есть
    n = d["nrm"] * 2 - 1
    lowp = np.stack([fblur(n[..., c], 2) for c in range(3)], -1)
    n = n + 0.5 * (n - lowp) * np.array([1, 1, 0], np.float32)
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-6
    nrm = np.where(use[..., None], n * 0.5 + 0.5, on)
    nrm[..., 2] = 1.0               # как у оригинала и v1.2: B = 255 (Z игра восстанавливает из X, Y)
    sg = osg.copy()
    sg[..., 0] = sg[..., 1] = sg[..., 2] = np.where(use, d["spec"][..., 0], osg[..., 0])
    sg[..., 3] = np.where(use, d["gloss"][..., 0], osg[..., 3])
    occ = np.where(use, d["occ"][..., 0], oo)
    emi = np.where(use[..., None], d["emis"], oe)
    ring_b = np.clip(fblur(cb.astype(np.float32), 1) * 2.5 - cb * 3.0, 0, 1) * back_glass * (cb < 0.5)
    emi = emi * (1 + RIM * ring_b)[..., None]
    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    OUT.mkdir(exist_ok=True)
    Image.fromarray(q(dif), "RGBA").save(OUT / f"Door_{tag}_diffuse.png")
    Image.fromarray(q(np.concatenate([nrm, np.ones_like(nrm[..., :1])], -1)), "RGBA").save(OUT / f"Door_{tag}_normal.png")
    Image.fromarray(q(sg), "RGBA").save(OUT / f"Door_{tag}_specgloss.png")
    Image.fromarray(q(np.repeat(occ[..., None], 3, -1)), "RGB").save(OUT / f"Door_{tag}_occlusion.png")
    Image.fromarray(q(emi), "RGB").save(OUT / f"Door_{tag}_emission.png")
    a = dif[..., 3]
    print("alpha < 0.5: %d texels (1024)" % int((a < 0.5).sum()))
    print("->", OUT / f"Door_{tag}_*.png")


if __name__ == "__main__":
    main()
