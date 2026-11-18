"""Шум на numpy (без PIL) — общий для bake_shotgun.py (Blender) и texture_v1.py (.venv)."""
import numpy as np


def vnoise(p, seed=0):
    """Value noise по 3D-точкам, векторно; p: (...,3) → (...) в 0..1."""
    p = np.asarray(p, np.float64)
    i = np.floor(p).astype(np.int64)
    f = p - i
    f = f * f * (3 - 2 * f)

    def h(dx, dy, dz):
        x = ((i[..., 0] + dx) * 73856093) ^ ((i[..., 1] + dy) * 19349663) ^ ((i[..., 2] + dz) * 83492791) ^ (seed * 2654435761)
        x = (x ^ (x >> 13)) * 1274126177
        return ((x ^ (x >> 16)) & 0xFFFF).astype(np.float32) / 65535

    out = 0
    for dx in (0, 1):
        wx = f[..., 0] if dx else 1 - f[..., 0]
        for dy in (0, 1):
            wy = f[..., 1] if dy else 1 - f[..., 1]
            for dz in (0, 1):
                wz = f[..., 2] if dz else 1 - f[..., 2]
                out = out + h(dx, dy, dz) * wx * wy * wz
    return out.astype(np.float32)


def fbm(p, oct=4, seed=0):
    p = np.asarray(p, np.float64)
    s, a, t = 0.0, 0.5, 0.0
    for k in range(oct):
        s = s + a * vnoise(p * (2 ** k), seed + k)
        t += a
        a *= 0.5
    return s / t


def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)
