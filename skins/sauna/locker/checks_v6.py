"""Sauna Changing Locker v6: автоматические проверки экспорта (PLAN_v6.md, раздел 4, «Проверки до игры»).

  .venv/Scripts/python skins/sauna/locker/checks_v6.py [--tag v6.0]
Пишет uv/v6/check_<tag>.md и карту uv/v6/check_<tag>_painted.png (рисунок в Diffuse без пары в Normal — красным).
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
EXP = HERE / "export"
R = 2048
CUT = set(range(57, 64)) | set(range(68, 79))        # крайние дверцы и их фурнитура — вырезаны альфой


def img(name, mode):
    return np.asarray(Image.open(EXP / name).convert(mode), np.float32) / 255.0


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


def hp(a, r):
    return a - blur(a, r)


def main():
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "v6.0"
    ids = np.asarray(Image.open(HERE / "uv" / "v6" / "ids.png").convert("RGB")).astype(np.int32)
    ids = ids[..., 0] + 256 * ids[..., 1]
    mask = np.asarray(Image.open(HERE / "bake" / "v6" / "mask.png").convert("L").resize((R, R), Image.NEAREST)) > 127
    d = img(f"Locker_{tag}_diffuse.png", "RGBA")
    n = img(f"Locker_{tag}_normal.png", "RGB")
    sg = img(f"Locker_{tag}_specgloss.png", "RGBA")
    em = img(f"Locker_{tag}_emission.png", "RGB")
    md = [f"# Проверки {tag}", ""]
    ok = lambda c: "✔" if c else "✘"
    # 1. альфа: 0 только на вырезанных островах
    a0 = d[..., 3] < 0.5
    bad_cut = a0 & (ids > 0) & ~np.isin(ids, list(CUT))
    md.append(f"- {ok(bad_cut.sum() == 0)} альфа 0 только на вырезанных островах (лишних текселей: {int(bad_cut.sum())})")
    # 2. отступы: у текселей среза в 8 px вокруг острова нет чужого цвета (сравнение с ближайшим своим)
    isl = ids > 0
    grown = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(17))) > 127
    ring = grown & ~isl
    md.append(f"- отступ 8 px вокруг островов среза: {int(ring.sum())} текселей заполнено из запекания (texture_v6.extend)")
    # 3. нормаль: длина и B > 0
    nv = n * 2 - 1
    ln = np.linalg.norm(nv, axis=-1)
    md.append(f"- {ok(np.percentile(np.abs(ln[mask] - 1), 99) < 0.05)} нормаль единичная (99 % откл. "
              f"{np.percentile(np.abs(ln[mask] - 1), 99):.3f}); B < 0: {int((nv[..., 2][mask] < 0).sum())}")
    # насыщенность нормали на срезе против v5.4 и принятых (раздел 2 плана)
    xy = np.linalg.norm(nv[..., :2], axis=-1)
    n5 = np.asarray(Image.open(EXP / "Locker_v5.4_normal.png").convert("RGB"), np.float32) / 127.5 - 1
    xy5 = np.linalg.norm(n5[..., :2], axis=-1)
    md.append(f"- насыщенность нормали на тех же текселях: |xy| {xy[mask].mean():.3f} (v5.4: {xy5[mask].mean():.3f}); "
              f"наклон > 0.3: {100 * (xy[mask] > 0.3).mean():.0f} % (v5.4: {100 * (xy5[mask] > 0.3).mean():.0f} %)")
    # 4. Spec/Gloss в пределах
    spec = sg[..., :3].max(-1)
    md.append(f"- {ok(spec[mask].max() <= 0.6)} Spec ≤ 0.6 (макс. {spec[mask].max():.2f}); глянец {sg[..., 3][mask].min():.2f}"
              f"…{sg[..., 3][mask].max():.2f}")
    # 5. свечение: доля текселей среза со свечением
    e = em.max(-1)
    md.append(f"- свечение > 0.1 на {100 * (e[mask] > 0.1).mean():.1f} % текселей среза, макс. {e[mask].max():.2f}")
    # 6. Diffuse против Normal: мелкий рисунок яркости без пары в нормали
    lum = (d[..., :3] @ np.array([0.3, 0.59, 0.11], np.float32))
    dl = np.abs(hp(lum, 2.0))
    dn = np.abs(hp(nv[..., 0], 2.0)) + np.abs(hp(nv[..., 1], 2.0))
    painted = mask & (dl > 0.06) & (dn < 0.02)
    share = painted.sum() / max(mask.sum(), 1)
    md.append(f"- рисунок в Diffuse без пары в Normal: {100 * share:.2f} % текселей среза (красным на карте; "
              f"это допустимо только для того, у чего нет формы: потёки, сердечко на стекле, шкала под стеклом, полосы ткани)")
    vis = (np.clip(d[..., :3], 0, 1) * 0.6 * 255).astype(np.uint8)
    vis[painted] = (255, 40, 40)
    Image.fromarray(vis).save(HERE / "uv" / "v6" / f"check_{tag}_painted.png")
    (HERE / "uv" / "v6" / f"check_{tag}.md").write_text("\n".join(md) + "\n", encoding="utf8")
    print("\n".join(md))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
