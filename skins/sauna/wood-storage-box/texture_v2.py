"""Sauna Stone Box v2.0: карты из запекания bake_v2.py (4096) -> экспорт 1024 (Lanczos), все пять слотов.

Форма и всё, у чего она есть, — уже в геометрии (bake/v2/normal, m1-m3, idc). Здесь только:
  - палитра по маскам той же геометрии (волокно, полость, вмятина, гвоздь, сучок, раковина, скол, пепел, трещина угля);
  - то, у чего формы нет: тон доски, копоть на боку к печи, ржавые потёки под гвоздями, засаленность у прорезей,
    пепельная пыль на камнях, минеральный налёт на старых камнях;
  - свечение — набор v1.6 (решение 25.11): угли гнёздами (по маске трещин угля и глубине щелей), свет в щелях между
    досками и в прорезях-ручках;
  - Spec/Gloss по материалам (Unity Specular), Occlusion из AO.
Тон дерева — как у полока v2 (решение 1: темнее и серее v1.6). Крышка — альфа 0, как в v1.6.

    .venv/Scripts/python skins/sauna/wood-storage-box/texture_v2.py [--tag v2.0]
Выход: export/Box_<tag>_{diffuse,normal,specgloss,occlusion,emission}.png (1024).
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import concepts  # noqa: E402
import fields_floor as FF  # noqa: E402
import fields_walls as FW  # noqa: E402

BAKE = HERE / "bake" / "v2"
OUT = HERE / "export"
S = 4096
EXPORT = 1024
sstep = FW.sstep


def hexc(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255


# палитра (sRGB)
WOOD_WARM = hexc("#776B5D")     # осина у печи: как полок v2 (#72695D), чуть суше и теплее
WOOD_GREY = hexc("#6C6964")
GAP = hexc("#1A1511")
KNOT = hexc("#463527")
SOOT = hexc("#2A221D")
CHAR = hexc("#1B1714")
IRON = hexc("#2B2825")
IRON_EDGE = hexc("#5E5A55")
RUST = hexc("#8C4A26")
RUST_DARK = hexc("#5A3424")
FLOOR_WOOD = hexc("#3B2E25")
CHARCOAL = hexc("#141211")
ASH = hexc("#5F5A54")           # пепел: v2.0 #77726B в игре — белый «снег» (урок v1.1 «снежки»)
ASH_LIGHT = hexc("#6C6761")
STONE_SKIN = hexc("#29292A")    # габбро-диабаз: корка (v2.1 нейтральнее: в игре отдавал сиренью)
STONE_FACE = hexc("#323335")    # грань раскола: чуть светлее
STONE_CHIP = hexc("#4A4B4D")    # свежий скол: светлее — рёбра ловят свет (референс)
STONE_OLD = hexc("#2D2A28")     # окатанный старый
MINERAL = hexc("#B8B3A8")
LEAF_DRY = hexc("#6A5236")      # v2.1 темнее: #7E6342 в игре — «самородок»
LEAF_DARK = hexc("#4C3826")
TIN = hexc("#5A5854")            # v2.2 темнее: #6A6763 в игре по тону сливался с деревом
PEG = hexc("#857561")
CHAR_ASH = hexc("#4A4642")
EMB_EDGE = hexc("#B51805")
EMB_MID = hexc("#FF7A10")
EMB_HOT = hexc("#FFB347")
M = {**FW.MAT, **FF.MAT}


def load(name, mode="RGB"):
    return np.asarray(Image.open(BAKE / f"{name}.png").convert(mode), np.float32) / 255.0


def fbm(x, y, seed, octaves=3):
    return FW.fbm2(x, y, seed, octaves).astype(np.float32)


def mix(col, c, t):
    return col * (1 - t[..., None]) + np.asarray(c, np.float32) * t[..., None]


def fblur(a, r, passes=3):
    a = a.astype(np.float32)
    for _ in range(passes):
        for ax in (0, 1):
            pad = [(0, 0)] * a.ndim
            pad[ax] = (r + 1, r)
            c = np.cumsum(np.pad(a, pad, mode="edge"), axis=ax, dtype=np.float64)
            hi = np.take(c, np.arange(2 * r + 1, c.shape[ax]), axis=ax)
            lo = np.take(c, np.arange(0, c.shape[ax] - 2 * r - 1), axis=ax)
            a = ((hi - lo) / (2 * r + 1)).astype(np.float32)
    return a


def position_maps():
    """3D-точка и нормаль на тексель (см) для 16 досок и дна — по граням low-poly (UV дна сдвинуты в 0..1)."""
    concepts.SIZE = S
    V, T, F = concepts.load_obj(concepts.ORIG / "box.wooden.obj")
    Vv, _, Ft = FW.load_obj()
    isl = FW.island_of_faces(Ft)
    keep = set(sum(FW.WALL_ISL.values(), [])) | {35}
    # load_obj из tools/uv_zones отдаёт многоугольники как в файле (здесь все — треугольники, порядок тот же)
    assert len(F) == len(Ft)
    Fk = [f for f, i in zip(F, isl) if i in keep]
    pos, nrm = concepts.position_map(V, T, Fk)
    return pos.astype(np.float32) * 100.0, nrm.astype(np.float32)


def build():
    print("position map", S)
    pos, nrm = position_maps()
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    print("bake maps")
    nb = load("normal")
    ao = load("ao", "L")
    m1, m2, m3, idc = load("m1"), load("m2"), load("m3"), load("idc")
    mine = load("mask", "L") > 0.5
    cover = load("cover", "L") > 0.5
    mat = np.rint(idc[..., 0] * 32).astype(np.int32)
    tone = m3[..., 2]
    col = np.zeros((S, S, 3), np.float32) + GAP
    spec = np.full((S, S), 0.05, np.float32)
    gloss = np.full((S, S), 0.2, np.float32)
    heat = np.zeros((S, S), np.float32)
    floor = mine & (y < 5) & (nrm[..., 1] > 0.7)
    walls = mine & ~floor
    right = walls & (nrm[..., 0] > 0.7)
    left = walls & (nrm[..., 0] < -0.7)
    front = walls & (nrm[..., 2] > 0.7)
    back = walls & (nrm[..., 2] < -0.7)
    cap = walls & (np.abs(nrm[..., 1]) > 0.7)

    # ================= стенки
    wood = walls & np.isin(mat, [M["board"], M["end"]])
    grain, cav, dent = m1[..., 0], m1[..., 1], m1[..., 2]
    nail, knot = m2[..., 0], m2[..., 1]
    saw, grease = m3[..., 0], m3[..., 1]
    big = fbm(x * 0.03 + z * 0.03, y * 0.05, 903) - 0.5
    greyness = np.clip(0.3 + 0.55 * ((tone * 7.31) % 1.0) + 0.5 * big, 0, 1)
    base = mix(np.zeros_like(col) + WOOD_WARM, WOOD_GREY, greyness)
    base = base * (0.86 + 0.26 * tone[..., None])
    wc = base * (1.05 - 0.13 * np.clip(grain, 0, 1)[..., None])       # рисунок волокон — в основном рельефом
    fine = fbm(x * 0.5 + z * 0.5, y * 3.0, 905, 2) - 0.5
    wc = wc * (1 + 0.07 * fine[..., None])
    wc = wc * (1 - 0.05 * saw[..., None])
    wc = wc * (1 - 0.1 * dent[..., None])
    wc = mix(wc, KNOT, 0.75 * np.clip(knot, 0, 1))
    endg = wood & (mat == M["end"])
    wc = np.where(endg[..., None], wc * 0.8, wc)
    wc = mix(wc, GAP, np.clip(cav * 1.1, 0, 1))
    # кромки (видны в щелях и сверху обод): чуть светлее на верхнем ободе — стёрто
    rim = cap & (y > 52.5)
    wc = np.where(rim[..., None], wc * 1.06, wc)
    # засаленность у прорезей-ручек: темнее и теплее
    gr = np.clip(grease, 0, 1)
    wc = mix(wc, hexc("#3E3227"), 0.55 * gr)
    # копоть на боку к печи (+x): гуще у верха (сыплют совком через край) и снизу, пятнами
    sm = fbm(z * 0.06, y * 0.09, 907, 3)
    smoke = right * np.clip(0.25 + 0.5 * sm + 0.35 * sstep(44, 53, y) + 0.2 * sstep(10, 0, y), 0, 1)
    side_near = (front | back) * sstep(20, 33.5, x) * 0.5
    smoke = np.clip(smoke + side_near * (0.3 + 0.5 * sm), 0, 1)
    wc = mix(wc, SOOT, 0.42 * smoke)
    # ржавые потёки: под гвоздями досок и обручей, вниз по доске
    rust_st = np.zeros((S, S), np.float32)
    srcs = []
    for b in FW.boards():
        k, s, a = b["k"], b["s"], b["a"]
        for (ga, gy, kind) in FW.board_nails(b):
            p = np.zeros(3)
            p[a], p[1], p[k] = ga, gy, (b["hi"][k] if s > 0 else b["lo"][k])
            srcs.append((p, b["wall"], 0.7))
    for (hx, hy, hz, nx, nz) in FW.hoop_heads(FW.boards()):
        wall = "right" if nx > 0.7 else "left" if nx < -0.7 else "front" if nz > 0.7 else "back" if nz < -0.7 else None
        if wall:
            if int(abs(hx * 7.3 + hz * 3.1)) % 2 == 0:               # потекло не у всех гвоздей
                srcs.append((np.array([hx, hy - 2.3, hz]), wall, 0.6))
    wm = {"right": right, "left": left, "front": front, "back": back}
    for (p, wall, amp) in srcs:
        al = z if wall in ("left", "right") else x
        ga = p[2] if wall in ("left", "right") else p[0]
        sel = wm[wall] & (np.abs(al - ga) < 2.5) & (y < p[1] - 0.4) & (y > p[1] - 13)
        if not sel.any():
            continue
        d = p[1] - y[sel]
        w = 0.35 + 0.07 * d
        st = np.exp(-((al[sel] - ga - 0.15 * np.sin(d * 0.7 + ga)) / w) ** 2) * np.exp(-d / 5.0) * (0.55 + 0.45 * np.sin(d * 1.1 + ga) ** 2)
        rust_st[sel] = np.maximum(rust_st[sel], amp * st)
    wc = mix(wc, RUST_DARK, 0.38 * fblur(rust_st, 2) * wood)
    # ореол влаги и ржавчины в дереве вокруг гвоздей досок
    nm = (wood & (nail > 0.5)).astype(np.float32)
    halo = np.clip(fblur(nm, 8) * 3.0, 0, 1) * (1 - nm) * wood
    wc = mix(wc, hexc("#4E3424"), 0.4 * halo)
    # обугленный верх у печи (решение 2: формой): блоки угля, бурая подпалина вокруг.
    # v2.2: без светлых «пепельных» макушек (в игре с выпуклыми ячейками — «брусчатка»): макушки чёрные с атласным
    # блеском, трещины ещё темнее и матовые
    ch = np.clip(m2[..., 2], 0, 1) * wood
    scorch = np.clip(fblur(ch, 14) * 2.2, 0, 1) * (1 - ch) * wood
    wc = mix(wc, hexc("#3A2A20"), 0.55 * scorch)
    ccr = np.clip(cav * 1.4, 0, 1)
    cc = CHAR * (0.92 + 0.22 * fbm(x * 0.9 + z * 0.9, y * 1.4, 909, 2))[..., None] * (1 - 0.45 * ccr)[..., None]
    cc = mix(cc, CHAR_ASH, 0.1 * sstep(0.6, 0.85, fbm(x * 0.5 + z * 0.5, y * 0.5, 917, 3)) * (1 - ccr))
    wc = mix(wc, cc, ch)
    col = np.where(wood[..., None], wc, col)
    spec = np.where(wood, 0.05 + 0.04 * ch * (1 - ccr), spec)
    gloss = np.where(wood, (0.2 + 0.14 * gr - 0.08 * smoke) * (1 - ch) + ch * (0.36 - 0.24 * ccr), gloss)
    # жестяная заплата (v2.2: в игре светлая и чистая, ржавые кольца — «мишень»): тёмная жесть, ржавчина ползёт
    # от загнутого края и от гвоздей (m3[1] у жести), рёбра — едва; копоть гуще кверху (к углю)
    tin = walls & (mat == M["tin"])
    tr_ = np.clip(0.8 * sstep(0.15, 0.75, grease) * sstep(0.35, 0.7, fbm(z * 0.7, y * 0.7, 915, 3))   # пятнами, не рамкой
                  + 0.08 * np.clip(grain, 0, 1) + 0.45 * sstep(0.62, 0.85, fbm(z * 0.4, y * 0.4, 911, 3)), 0, 1)
    tc = mix(np.zeros_like(col) + TIN * (0.88 + 0.18 * fbm(z * 1.2, y * 1.2, 913, 2)[..., None]), RUST_DARK, 0.65 * tr_)
    tsoot = 0.35 + 0.25 * sstep(19.0, 25.0, y)
    tc = tc * (1 - tsoot[..., None]) + SOOT * tsoot[..., None]
    col = np.where(tin[..., None], tc, col)
    spec = np.where(tin, 0.16 - 0.1 * tr_, spec)          # v2.2: 0.3 — середина на солнце блестела светлым
    gloss = np.where(tin, 0.3 - 0.14 * tr_, gloss)
    # колышек: свежее дерево торцом, кольца темнее
    peg = walls & (mat == M["peg"])
    col = np.where(peg[..., None], PEG * (1.05 - 0.25 * np.clip(grain, 0, 1)[..., None]), col)
    # гвозди досок
    bn = walls & (mat == M["nail"])
    nrust = sstep(0.45, 0.8, fbm(x * 2 + z, y * 2, 921, 2))
    col = np.where(bn[..., None], mix(np.zeros_like(col) + IRON * 1.15, RUST * 0.75, 0.5 * nrust), col)
    spec = np.where(bn, 0.28 - 0.12 * nrust, spec)
    gloss = np.where(bn, 0.36 - 0.14 * nrust, gloss)
    # обручи: тёмное железо, ржавчина в раковинах и пятнами, светлее на кромках, окалина
    hoop = walls & np.isin(mat, [M["hoop"], M["rivet"]])
    pit, flake, edge, lap = m1[..., 0], m2[..., 1], m3[..., 0], m3[..., 1]
    rn = fbm(x * 0.2 + z * 0.2, y * 0.6, 931, 4)
    hc = mix(np.zeros_like(col) + IRON, RUST * 0.8, np.clip(0.2 + 0.6 * (rn - 0.45) * 2, 0, 1) * 0.55)
    hc = mix(hc, RUST_DARK * 1.1, 0.45 * np.clip(pit, 0, 1))          # ржавчина в раковинах — тёмная, не «крапинка»
    hc = mix(hc, hexc("#1E1B19"), 0.5 * np.clip(flake, 0, 1))
    hc = mix(hc, IRON_EDGE, 0.35 * np.clip(edge, 0, 1) * (1 - np.clip(pit, 0, 1)))
    hc = mix(hc, RUST_DARK, 0.35 * np.clip(lap, 0, 1))
    riv = hoop & (mat == M["rivet"])
    hc = np.where(riv[..., None], hc * 1.15, hc)
    hc = hc * (1 - 0.25 * smoke[..., None])
    col = np.where(hoop[..., None], hc, col)
    rust_amt = np.clip(0.2 + 0.6 * (rn - 0.45) * 2, 0, 1) * 0.55 + pit
    spec = np.where(hoop, 0.3 - 0.18 * np.clip(rust_amt, 0, 1) + 0.06 * edge, spec)
    gloss = np.where(hoop, 0.34 - 0.18 * np.clip(rust_amt, 0, 1) + 0.08 * edge, gloss)

    # свечение стенок (как v1.6): свет углей сквозь щели между досками и прорези-ручки
    seam = cap & (np.abs(y - 13.5) < 0.6)
    seam2 = cap & (np.abs(y - 26.75) < 0.6)
    nz_ = fbm(x * 0.3 + z * 0.3, y, 951, 2)
    gap_heat = np.maximum(seam * (0.4 + 0.6 * nz_) * 0.38, seam2 * (0.3 + 0.7 * nz_) * 0.22)   # v2.1: вдвое тише (днём «неон»)
    face_line = (walls & ~cap) & (np.minimum(np.abs(y - 13.45), np.abs(y - 26.75)) < 0.35)
    gap_heat = np.maximum(gap_heat, face_line * 0.06 * (0.3 + 0.7 * nz_))
    yb = FW.slot_bottom(x, 40.25)
    ends = front | back
    in_slot = ends & (np.abs(x - FW.SLOT["xc"]) < FW.SLOT["hw"]) & (y > 40.0) & (y < 45.5)
    slot_cut = in_slot & cap
    mid_x = 1 - np.clip(np.abs(x - FW.SLOT["xc"]) / FW.SLOT["hw"], 0, 1)
    slot_heat = slot_cut * (0.75 + 0.25 * mid_x)
    lip = ends & ~cap & (np.abs(x - FW.SLOT["xc"]) < FW.SLOT["hw"] + 1.0) & (y > yb - 0.2) & (y < yb + 2.0)
    slot_heat = np.maximum(slot_heat, lip * sstep(2.0, 0.0, y - yb) * 0.55 * (0.4 + 0.6 * mid_x))
    heat = np.maximum.reduce([heat, gap_heat * walls, slot_heat])

    # ================= дно
    up = np.clip(nb[..., 2] * 2 - 1, 0, 1)
    rip, fcav = m1[..., 0], m1[..., 1]
    ember_m, chip, ashm = m2[..., 0], m2[..., 1], m2[..., 2]
    rpit, charm = m3[..., 0], m3[..., 1]
    fl = floor
    # доски дна у стенок
    fw = fl & (mat == M["floor"])
    c = FLOOR_WOOD * (0.85 + 0.3 * fbm(x * 0.3, z * 0.05, 961, 3)[..., None]) * (1.05 - 0.2 * rip[..., None])
    c = mix(c, CHAR, 0.7 * charm)
    c = mix(c, GAP, np.clip(fcav, 0, 1))
    col = np.where(fw[..., None], c, col)
    # противень: ржавое железо, на кромке светлее (тёрли совком)
    tr = fl & (mat == M["tray"])
    rn2 = fbm(x * 0.15, z * 0.15, 963, 4)
    c = mix(np.zeros_like(col) + IRON, RUST * 0.85, np.clip(0.35 + 0.9 * (rn2 - 0.45), 0, 1))
    c = mix(c, RUST_DARK, 0.8 * np.clip(rpit, 0, 1))
    e = FF.tray_dist(x, z)
    c = mix(c, IRON_EDGE, 0.35 * sstep(0.5, 0.1, np.abs(e - 0.12)) * (1 - np.clip(rpit, 0, 1)))
    col = np.where(tr[..., None], c, col)
    spec = np.where(tr, 0.22, spec)
    gloss = np.where(tr, 0.26, gloss)
    # слой углей
    cb = fl & (mat == M["coalbed"])
    c = CHARCOAL * (0.8 + 0.5 * tone[..., None]) * (1 + 0.25 * up[..., None])
    fleck = sstep(0.62, 0.75, fbm(x * 0.8, z * 0.8, 965, 2)) * up
    c = mix(c, ASH, 0.45 * fleck)
    c = mix(c, hexc("#2A120A"), 0.6 * np.clip(ember_m, 0, 1))
    col = np.where(cb[..., None], c, col)
    spec = np.where(cb, 0.04, spec)
    gloss = np.where(cb, 0.1, gloss)
    # пепел
    ash = fl & (mat == M["ash"])
    c = mix(np.zeros_like(col) + ASH, ASH_LIGHT, fbm(x * 0.5, z * 0.5, 967, 3))
    su_, sv_ = FF.scoop_local(x, z)
    in_scoop = (np.abs(su_) < FF.SCOOP["L"] / 2) & (np.abs(sv_) < FF.SCOOP["W"] / 2)
    c = np.where(in_scoop[..., None], c * 0.7, c)
    c = c * (0.9 + 0.12 * up[..., None])
    col = np.where(ash[..., None], c, col)
    spec = np.where(ash, 0.03, spec)
    gloss = np.where(ash, 0.05, gloss)
    # камни: корка, грани раскола, свежие сколы; трещины тёмные; пепельная пыль сверху
    st = fl & (mat == M["stone"])
    so = fl & (mat == M["stone_old"])
    facew = np.clip(1 - np.abs(rip - 0.5) * 0.0, 0, 1)
    t3 = (tone * 5.17) % 1.0
    c = mix(np.zeros_like(col) + STONE_SKIN, STONE_FACE, 0.5 + 0.3 * (rip - 0.5))
    c = c * (0.85 + 0.3 * t3[..., None])
    c = mix(c, STONE_CHIP, 0.8 * np.clip(chip, 0, 1))
    c = np.where(so[..., None], STONE_OLD * (0.75 + 0.2 * t3[..., None]), c)
    c = mix(c, MINERAL, 0.08 * so * sstep(0.6, 0.8, fbm(x * 0.6, z * 0.6, 969, 2)) * up)
    dust = sstep(0.8, 1.0, up) * 0.1
    c = mix(c, ASH, dust)
    c = mix(c, GAP, np.clip(fcav * 1.2, 0, 1))
    stones = st | so
    col = np.where(stones[..., None], c, col)
    spec = np.where(stones, 0.06 + 0.05 * chip, spec)
    gloss = np.where(stones, 0.16 + 0.12 * chip, gloss)
    _ = facew
    # куски угля и обугленные поленья
    co = fl & np.isin(mat, [M["coal"], M["log"]])
    c = CHARCOAL * (0.9 + 0.35 * np.clip(rip, 0, 1)[..., None]) * (0.9 + 0.2 * tone[..., None])
    c = mix(c, hexc("#2A120A"), 0.7 * np.clip(ember_m, 0, 1))
    c = mix(c, ASH, 0.25 * sstep(0.85, 1.0, up) * (1 - np.clip(ember_m, 0, 1)))
    col = np.where(co[..., None], c, col)
    spec = np.where(co, 0.05, spec)
    gloss = np.where(co, 0.18, gloss)            # на изломе угля лёгкий блеск
    # совок
    sc = fl & (mat == M["scoop"])
    c = mix(np.zeros_like(col) + IRON, RUST * 0.8, np.clip(0.25 + 0.8 * (fbm(x * 0.4, z * 0.4, 971, 3) - 0.45), 0, 1))
    c = mix(c, IRON_EDGE, 0.4 * np.clip(rip, 0, 1))
    c = mix(c, IRON * 1.3, 0.6 * np.clip(chip, 0, 1))
    col = np.where(sc[..., None], c, col)
    spec = np.where(sc, 0.26, spec)
    gloss = np.where(sc, 0.3, gloss)
    # лист: сухой бурый, жилки светлее, конец подпалён
    lf = fl & (mat == M["leaf"])
    c = mix(np.zeros_like(col) + LEAF_DRY, LEAF_DARK, fbm(x * 1.5, z * 1.5, 973, 2))
    c = c * (1 + 0.18 * rip[..., None])
    c = mix(c, CHARCOAL, 0.85 * np.clip(charm, 0, 1))
    col = np.where(lf[..., None], c, col)
    spec = np.where(lf, 0.05, spec)
    gloss = np.where(lf, 0.22, gloss)

    # свечение дна (как v1.6: гнёзда, а не ровная сетка)
    cx, cz = (FF.TRAY[0] + FF.TRAY[1]) / 2, (FF.TRAY[2] + FF.TRAY[3]) / 2
    centre = np.clip(1 - np.hypot((x - cx) / 32, (z - cz) / 42), 0, 1)
    deep = sstep(0.85, 0.35, ao)
    pocket = np.zeros_like(x)
    for px, pz, r in ((-12.0, 20.0, 13.0), (15.0, -2.0, 11.0), (-5.0, -27.0, 12.0), (19.0, 31.0, 8.0), (2.0, 8.0, 7.0)):
        pocket = np.maximum(pocket, np.exp(-((x - px) ** 2 + (z - pz) ** 2) / (2 * (r * 0.8) ** 2)))
    flick = fbm(x * 0.25, z * 0.25, 975, 3)
    pocket = np.clip(pocket * (0.75 + 0.5 * flick), 0, 1)
    coal_heat = (cb | co) * np.clip(ember_m, 0, 1) * (0.35 + 0.65 * deep) * (0.4 + 0.6 * centre)
    gaps = fl & ~stones & ~ash & ~sc & ~lf & (mat != M["tray"]) & (mat != M["floor"])
    gap_glow = gaps * deep * 0.6 * (0.4 + 0.6 * centre)
    stone_heat = stones * sstep(0.7, 0.3, ao) * (0.25 + 0.75 * centre) * 0.4 * (1 - up)
    fheat = np.maximum.reduce([coal_heat, gap_glow, stone_heat])
    fheat = np.clip(1.4 * fheat * (0.06 + 0.94 * sstep(0.15, 0.75, pocket)), 0, 1)   # v1.5: ровно по всему дну — «лава»
    bounce = (stones * sstep(0.1, 0.8, pocket) * (1 - 0.6 * up) * 0.22)[..., None]
    col = np.where(fl[..., None], col * (1 - bounce) + hexc("#B4532A") * bounce, col)
    heat = np.maximum(heat, fheat * fl)

    # пропуски лучей — цвет соседнего дерева/угля, ровная нормаль
    nohit = mine & ~cover
    col = np.where((nohit & walls)[..., None], WOOD_GREY * 0.8, col)
    col = np.where((nohit & fl)[..., None], CHARCOAL, col)
    nb = np.where(nohit[..., None], np.array([0.5, 0.5, 1.0], np.float32), nb)
    # AO в цвет
    col = col * ((0.45 + 0.55 * ao[..., None]) ** 0.9)
    occ = 0.35 + 0.65 * ao
    c_mid = sstep(0.15, 0.65, heat)
    c_hot = sstep(0.65, 0.95, heat)
    emis = (EMB_EDGE * (1 - c_mid[..., None]) + EMB_MID * (c_mid - c_hot)[..., None] + EMB_HOT * c_hot[..., None]) * heat[..., None]
    col = np.where((heat > 0.3)[..., None], col * 0.8 + SOOT * 0.2, col)
    print("texels: walls", int(walls.sum()), "floor", int(fl.sum()), "no-hit", int(nohit.sum()))
    return dict(col=col, spec=spec, gloss=gloss, occ=occ, nrm=nb, emis=emis, mine=mine)


def extend(maps, own, steps):
    """Продлить свои тексели на steps пикселей в пустые соседние: одна карта индексов ближайшего своего текселя."""
    h, w = own.shape
    idx = np.where(own, np.arange(h * w, dtype=np.int64).reshape(h, w), -1)
    for _ in range(steps):
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            src = np.roll(np.roll(idx, dy, 0), dx, 1)
            take = (idx < 0) & (src >= 0)
            idx[take] = src[take]
    filled = idx >= 0
    src = idx[filled & ~own]
    for k, a in maps.items():
        flat = a.reshape(h * w, -1)
        flat[(filled & ~own).ravel()] = flat[src]
    return filled


def down(a):
    if a.ndim == 2:
        return np.asarray(Image.fromarray(a.astype(np.float32), "F").resize((EXPORT, EXPORT), Image.LANCZOS), np.float32)
    return np.stack([down(a[..., c]) for c in range(a.shape[-1])], -1)


def main():
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "v2.0"
    r = build()
    mine = r["mine"]
    maps = {k: r[k] for k in ("col", "spec", "gloss", "occ", "nrm", "emis")}
    # v2.2: нормаль перед 4096 -> 1024 слегка размыть (~0.7 мм): тоньше текселя 1024 всё равно не покажется,
    # а при уменьшении складывается в «вельвет»
    maps["nrm"] = np.stack([fblur(maps["nrm"][..., c], 1, passes=2) for c in range(3)], -1)
    area = extend(maps, mine.copy(), 32)
    print("downscale")
    col, spec, gloss, occ, nrm, emis = (down(maps[k]) for k in ("col", "spec", "gloss", "occ", "nrm", "emis"))
    use = (down(area.astype(np.float32)) > 0.5) | (down(mine.astype(np.float32)) > 0.5)
    # остальное (крышка, изнанка из OBJ, низ) — из v1.6: крышка там уже вырезана альфой
    old = lambda n, mode: np.asarray(Image.open(OUT / f"Box_v1.6_{n}.png").convert(mode).resize((EXPORT, EXPORT), Image.LANCZOS), np.float32) / 255
    od, on, osg, oo = old("diffuse", "RGBA"), old("normal", "RGB"), old("specgloss", "RGBA"), old("occlusion", "L")
    dif = od.copy()
    dif[..., :3] = np.where(use[..., None], col, od[..., :3])
    dif[..., 3] = np.where(use, 1.0, od[..., 3])
    n = nrm * 2 - 1
    # мелкий рельеф x1.5 (днём в игре рельеф слабее, чем в Blender); крупная поправка на сглаженную модель — как есть.
    # v2.2: поднимаем только средние детали (полоса fblur 1 .. fblur 3); v2.1 поднимал и рябь у самого текселя
    lowp = np.stack([fblur(n[..., c], 3) for c in range(3)], -1)
    midp = np.stack([fblur(n[..., c], 1, passes=2) for c in range(3)], -1)
    n = midp + (n - midp) * 0.85 + 0.5 * (midp - lowp) * np.array([1, 1, 0], np.float32)
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-6
    nrm_o = np.where(use[..., None], n * 0.5 + 0.5, on)
    sg = osg.copy()
    sg[..., 0] = sg[..., 1] = sg[..., 2] = np.where(use, spec, osg[..., 0])
    sg[..., 3] = np.where(use, gloss, osg[..., 3])
    occ_o = np.where(use, occ, oo)
    emis_o = np.where(use[..., None], emis, 0.0)
    q = lambda a: (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    Image.fromarray(q(dif), "RGBA").save(OUT / f"Box_{tag}_diffuse.png")
    Image.fromarray(q(nrm_o), "RGB").save(OUT / f"Box_{tag}_normal.png")
    Image.fromarray(q(sg), "RGBA").save(OUT / f"Box_{tag}_specgloss.png")
    Image.fromarray(q(occ_o), "L").save(OUT / f"Box_{tag}_occlusion.png")
    Image.fromarray(q(emis_o), "RGB").save(OUT / f"Box_{tag}_emission.png")
    print("->", OUT / f"Box_{tag}_*.png")


if __name__ == "__main__":
    main()
