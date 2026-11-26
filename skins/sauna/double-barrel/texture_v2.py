"""Sauna Shotgun v2: карты из запечённого bake_v2.py (4096) -> экспорт в размер слотов (PLAN_v2 §1.1, §4).

Вертикальный срез: заменяются тексели групп bake/v2/<часть>_<группа>_mask.png (трубы, приклад, рамка колодки);
остальное — из v1.11 (export/DoubleBarrel_v1.11_*). GRIP скрыт альфой, кроме спуска (острова 5, 6) — как у
принятого 3831501799 (PLAN_v2 §7, решение 26.11.2026).

  python skins/sauna/double-barrel/texture_v2.py [--ver v2.0] [barrel stock main grip sights]

Цвет: col из вершин high-poly (линейный) -> sRGB; железо — палитра v1.1–v1.11, проверенная в игре (Diffuse почти
чёрный #2A2826, блик 0.30), ржавчина и светлый металл — по маскам рельефа (m1), дерево приводится к тону сета
(141, 127, 104). Нормаль: усиление мелкого n + 0.5·(n − blur n) (§9.2).
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import texture_v1 as T1  # noqa: E402
from noise_np import fbm  # noqa: E402

V2 = os.path.join(HERE, "bake", "v2")
E = os.path.join(HERE, "export")
VER = sys.argv[sys.argv.index("--ver") + 1] if "--ver" in sys.argv else "v2.0"
BASE = "v1.11"
S = 4096
# (diffuse, normal, specgloss, occlusion) — у принятых все карты вкладки в размере её Diffuse (кэш, PLAN_v2 §1.1)
OUT_SIZE = {"barrel": (1024, 1024, 1024, 1024), "main": (1024, 1024, 1024, 1024), "stock": (512, 1024, 512, 512),
            "grip": (256, 256, 256, None), "sights": (512, 512, 512, None)}
GROUPS = {"barrel": ["tubes"], "stock": ["all"], "main": ["frame"]}
IDS = T1.IDS
hexc = T1.hexc


def load(path, size=S, mode="RGB", resample=Image.BILINEAR):
    return T1.load(path, size, mode, resample)


def push_pull(arr, mask):
    """Заполнить пиксели вне маски значениями ближайших внутри (пирамида среднего) — отступ без scipy."""
    a = arr * mask[..., None] if arr.ndim == 3 else arr * mask
    w = mask.astype(np.float32)
    pyr = [(a, w)]
    while pyr[-1][1].shape[0] > 1:
        a, w = pyr[-1]
        h = a.shape[0] // 2
        a2 = a.reshape(h, 2, h, 2, *a.shape[2:]).sum((1, 3))
        w2 = w.reshape(h, 2, h, 2).sum((1, 3))
        pyr.append((a2, w2))
    fill = None
    for a, w in reversed(pyr):
        val = a / np.maximum(w, 1e-6)[..., None] if a.ndim == 3 else a / np.maximum(w, 1e-6)
        if fill is not None:
            up = np.repeat(np.repeat(fill, 2, 0), 2, 1)
            hole = w < 1e-6
            val = np.where(hole[..., None] if a.ndim == 3 else hole, up, val)
        fill = val
    out = fill
    return np.where(mask[..., None] if arr.ndim == 3 else mask, arr, out)


def down(arr, size):
    """4096 -> размер слота, Lanczos по каналам (float)."""
    if arr.shape[0] == size:
        return arr
    ch = [arr] if arr.ndim == 2 else [arr[..., k] for k in range(arr.shape[2])]
    out = [np.asarray(Image.fromarray(c.astype(np.float32), "F").resize((size, size), Image.LANCZOS)) for c in ch]
    return out[0] if arr.ndim == 2 else np.stack(out, -1)


def positions(part):
    """Положение точки (координаты OBJ) по запеканию v1 (bake/<part>_pos*.png) — для копоти у дула и зон хвата."""
    hi = load(os.path.join(T1.B, f"{part}_poshi.png"), resample=Image.NEAREST)
    lo = load(os.path.join(T1.B, f"{part}_poslo.png"), resample=Image.NEAREST)
    return T1.POS_LO + (np.round(hi * 255) * 256 + np.round(lo * 255)) / 65535 * (T1.POS_HI - T1.POS_LO)


def boost(n):
    xy = (n[..., :2] - 0.5) + 0.5 * (n[..., :2] - T1.blur(n, 12)[..., :2])
    xy = np.clip(xy, -0.49, 0.49)
    z = np.sqrt(np.clip(0.25 - (xy ** 2).sum(-1), 0.01, 0.25))
    return np.concatenate([xy + 0.5, (z + 0.5)[..., None]], -1)


def compose(part, tag, P):
    """Цвет, нормаль, блик, глянец, AO группы в 4096 (значения валидны внутри маски)."""
    g = {k: load(os.path.join(V2, f"{part}_{tag}_{k}.png"), resample=Image.NEAREST if k in ("idc", "mask") else Image.BILINEAR)
         for k in ("normal", "ao", "col", "idc", "m1", "cover", "mask")}
    mask = g["mask"][..., 0] > 0.5
    ids = np.round((g["idc"][..., 0] * 255 - 8) / 16).astype(np.int32)
    col = T1.lin2srgb(g["col"])
    rust_m, bright_m, b_m = g["m1"][..., 0], g["m1"][..., 1], g["m1"][..., 2]
    ao = g["ao"][..., 0]
    seed = {"barrel": 1, "main": 2, "stock": 3}[part]
    n = boost(g["normal"])
    spec = np.full((S, S), 0.17, np.float32)
    gloss = np.full((S, S), 0.2, np.float32)

    # ---- железо: палитра v1.11 (проверена в игре) + ржавчина и светлый металл по маскам рельефа
    metal = (ids == IDS["metal"]) & mask
    n1 = fbm(P * 90, 3, seed)
    n2 = fbm(P * 400, 2, seed + 7)
    ci = T1.IRON[None, None] * (0.85 + 0.3 * n1[..., None])
    ci = ci * (1 - 0.18 * b_m[..., None]) + hexc("1F2124") * 0.18 * b_m[..., None]      # окалина
    # v2.0: оранжевые точки читались «перцем» — ржавчина в ямках тёмно-бурая, рыжее только в глубоких
    rust = np.clip((rust_m - 0.15) / 0.85 * (0.75 + 0.5 * n2), 0, 1)
    rc = hexc("3E2A1E")[None, None] * (1 - rust[..., None] ** 2) + T1.RUST_DARK * rust[..., None] ** 2
    ci = ci * (1 - 0.6 * rust[..., None]) + rc * 0.6 * rust[..., None]
    br = np.clip(bright_m, 0, 1) * (1 - 0.7 * rust)
    ci = ci * (1 - 0.55 * br[..., None]) + T1.EDGE * 0.55 * br[..., None]
    cav = np.clip((1 - ao) * 1.5, 0, 1)
    ci = ci * (1 - 0.35 * cav[..., None])
    sp_i = 0.30 + 0.14 * br - 0.20 * rust
    gl_i = 0.30 + 0.18 * br - 0.22 * rust + 0.05 * (n2 - 0.5)
    if part == "barrel":   # копоть у дула — по z (одинакова у обеих копий: поворот вокруг оси ствола)
        soot = T1.smooth((P[..., 2] - 0.33) / 0.09) * (0.7 + 0.3 * fbm(P * 140, 3, 4))
        ci = ci * (1 - soot[..., None] * 0.7) + T1.SOOT * soot[..., None] * 0.7
        gl_i = gl_i * (1 - 0.5 * soot)
        sp_i = sp_i * (1 - 0.4 * soot)
    col = np.where(metal[..., None], ci, col)
    spec = np.where(metal, sp_i, spec)
    gloss = np.where(metal, gl_i, gloss)

    # ---- дерево: тон сета, засал в хвате, тень в трещинах и вмятинах
    wood = np.isin(ids, [IDS["wood"], IDS["fore"], IDS["burn"]]) & mask
    if wood.any():
        col = T1.grade_to(col, wood & (ids == IDS["wood"]), np.array([141, 127, 104], np.float32) / 255, k=0.7)
        gz = T1.grip_zones(P, part)
        wd = (gz * (0.45 + 0.3 * fbm(P * 220, 3, seed + 5)))[..., None]
        cw = col * (1 - wd) + T1.WOOD_DARK * 0.85 * wd
        cw = cw * (1 - 0.45 * rust_m[..., None]) * (0.8 + 0.2 * ao[..., None])
        col = np.where(wood[..., None], cw, col)
        spec = np.where(wood, np.where(ids == IDS["burn"], 0.10, 0.17), spec)
        gloss = np.where(wood, 0.20 + 0.25 * gz * (1 - rust_m) - 0.08 * rust_m, gloss)

    # ---- ткань, береста, бечёвка, лист, гвозди, смола: цвет из вершин, матовые
    soft = {IDS["towel"]: (0.10, 0.05), IDS["bark"]: (0.18, 0.15), IDS["twine"]: (0.14, 0.07),
            IDS["leaf"]: (0.21, 0.43), IDS["resin"]: (0.24, 0.58), IDS["nail"]: (0.28, 0.30)}
    for k, (sp, gl) in soft.items():
        m = (ids == k) & mask
        spec = np.where(m, sp, spec)
        gloss = np.where(m, gl, gloss)
    towel = (ids == IDS["towel"]) & mask
    if towel.any():
        gz = T1.grip_zones(P, part)
        sm = (gz * 0.3 * T1.smooth((fbm(P * 300, 3, seed + 8) - 0.35) * 2))[..., None]
        ct = col * (1 - sm) + hexc("6E675C") * sm
        col = np.where(towel[..., None], ct * (0.75 + 0.25 * ao[..., None]), col)
    other = mask & ~metal & ~wood & ~towel
    col = np.where(other[..., None], col * (0.8 + 0.2 * ao[..., None]), col)

    # AO-карта: на общих островах стволов — мягкая (v1.2: полоса из стыка между копиями)
    ao_out = np.clip(ao, 0.0, 1.0)
    if part == "barrel":
        ao_out = 1 - 0.6 * (1 - ao_out)
    return mask, col, n, spec, gloss, ao_out


def base_maps(part, sizes):
    pre = os.path.join(E, f"DoubleBarrel_{BASE}_{part}")
    sd, sn, ss, so = sizes
    d = T1.load(f"{pre}_diffuse.png", sd, "RGBA")
    nn = T1.load(f"{pre}_normal.png", sn, "RGBA")
    sg = T1.load(f"{pre}_specgloss.png", ss, "RGBA")
    ao = T1.load(f"{pre}_occlusion.png", so, "RGB")[..., 0] if so else None
    return d, nn, sg, ao


def save(arr, path, mode):
    Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), mode).save(path)
    print("  ->", os.path.basename(path), flush=True)


def make(part):
    sizes = OUT_SIZE[part]
    d, nn, sg, ao_b = base_maps(part, sizes)
    sd, sn, ss, so = sizes
    if part in GROUPS:
        P = positions(part)
        for tag in GROUPS[part]:
            mask, col, n, spec, gloss, ao = compose(part, tag, P)
            mf = mask.astype(np.float32)
            col, n = push_pull(col, mask), push_pull(n, mask)
            spec, gloss, ao = push_pull(spec, mask), push_pull(gloss, mask), push_pull(ao, mask)
            # исходный AO Facepunch (крупные затенения) — кроме общих труб стволов
            if part != "barrel":
                ao_o = load(os.path.join(T1.O, f"{part}_ao.png"))[..., 0]
                ao = ao * np.sqrt(ao_o)
            m_d, m_n, m_s = down(mf, sd), down(mf, sn), down(mf, ss)
            md = np.clip(m_d, 0, 1)[..., None]
            d[..., :3] = d[..., :3] * (1 - md) + np.clip(down(col, sd), 0, 1) * md
            nd = down(n, sn)
            mn = np.clip(m_n, 0, 1)[..., None]
            nn[..., :2] = nn[..., :2] * (1 - mn) + nd[..., :2] * mn
            ms = np.clip(m_s, 0, 1)
            sg[..., :3] = sg[..., :3] * (1 - ms[..., None]) + np.clip(down(spec, ss), 0, 1)[..., None] * ms[..., None]
            sg[..., 3] = sg[..., 3] * (1 - ms) + np.clip(down(gloss, ss), 0, 1) * ms
            if so:
                mo = np.clip(down(mf, so), 0, 1)
                ao_b = ao_b * (1 - mo) + np.clip(down(ao, so), 0, 1) * mo
            print(f"  {part}/{tag}: {int(mask.sum())} текселей 4096", flush=True)
    if part == "grip":   # скрыть рукоять GRIP (лежит поверх шейки STOCK), оставить спуск 5, 6
        keep = T1.island_mask("grip", {5, 6}, sd)
        a = np.asarray(Image.fromarray((keep * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))) / 255
        d[..., 3] = (a > 0.5).astype(np.float32)
    nn[..., 2] = 1.0
    nn[..., 3] = 1.0
    pre = os.path.join(E, f"DoubleBarrel_{VER}_{part}")
    save(d, f"{pre}_diffuse.png", "RGBA")
    save(nn, f"{pre}_normal.png", "RGBA")
    save(sg, f"{pre}_specgloss.png", "RGBA")
    if so:
        save(np.repeat(ao_b[..., None], 3, -1), f"{pre}_occlusion.png", "RGB")


def main():
    parts = [a for a in sys.argv[1:] if a in OUT_SIZE] or list(OUT_SIZE)
    for p in parts:
        print("texture", p, flush=True)
        make(p)
    print("done")


if __name__ == "__main__":
    main()
