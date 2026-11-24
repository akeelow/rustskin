"""Plan v2: the whole atlas of cached Wood Storage Box skins vs ours v1.6 and the original (plan_v2/atlas_compare.jpg),
and two atlas regions side by side (plan_v2/region_compare.jpg): the front end wall (islands 14/25/27/16) and the
inner floor (#35). .venv/Scripts/python skins/sauna/wood-storage-box/plan_v2/compare_atlas.py"""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

base = 'C:/Program Files (x86)/Steam/steamapps/workshop/content/252490/'
W = Path(__file__).resolve().parents[1]
ACC = ['3066298044', '3265029613', '3275030191', '3568745235', '3581736293', '3582123202', '3615632844',
       '3789475826', '3793813476', '3804827938', '3844767367']
skins = [('v1.6 ours (3840337593)', base + '3840337593/_MainTex0.png', base + '3840337593/_BumpMap0.png'),
         ('original Facepunch', str(W / 'originals/Wooden_Box_bc.png'), str(W / 'originals/Wooden_Box_nrm.png'))]
skins += [(i, base + i + '/_MainTex0.png', base + i + '/_BumpMap0.png') for i in ACC]


def rgb_of(p, normal):
    a = np.asarray(Image.open(p).convert('RGBA').resize((1024, 1024), Image.LANCZOS)).astype(np.float32)
    if not normal:
        al = a[..., 3:4] / 255.0
        chk = ((np.indices(a.shape[:2]).sum(0) // 32) % 2 * 60 + 90)[..., None]
        return (a[..., :3] * al + chk * (1 - al)).astype(np.uint8)
    if a[..., 2].mean() < 100 and a[..., 3].mean() > 100:   # DXT5nm-style (x in A, y in G)
        x = a[..., 3] / 255 * 2 - 1; y = a[..., 1] / 255 * 2 - 1; z = np.sqrt(np.clip(1 - x * x - y * y, 0, 1))
        return (np.stack([x, y, z], -1) * 127.5 + 127.5).astype(np.uint8)
    return a[..., :3].astype(np.uint8)


S = 300
cols = 3
rows = (len(skins) + cols - 1) // cols
out = Image.new('RGB', (S * 2 * cols, (S + 20) * rows), (40, 40, 40)); d = ImageDraw.Draw(out)
cache = {}
for k, (name, dp, np_) in enumerate(skins):
    r, c = divmod(k, cols)
    for j, p in enumerate((dp, np_)):
        rgb = rgb_of(p, j == 1); cache[(k, j)] = rgb
        out.paste(Image.fromarray(rgb).resize((S, S), Image.LANCZOS), (c * 2 * S + j * S, r * (S + 20) + 20))
    d.text((c * 2 * S + 4, r * (S + 20) + 4), name, fill=(255, 255, 255))
out.save(W / 'plan_v2/atlas_compare.jpg', quality=88)

# regions in 1024 px (x0, y0, x1, y1), from uv/islands.md (v from the top, wrapped into 0..1)
REG = {'front': (530, 448, 990, 805), 'floor': (530, 0, 1000, 170)}
pick = [0, 1] + [k for k in range(2, len(skins))]
H = {'front': 200, 'floor': 74}
Wd = 280
out = Image.new('RGB', (Wd * 4 + 12, len(pick) * (H['front'] + 18)), (30, 30, 30)); d = ImageDraw.Draw(out)
for r, k in enumerate(pick):
    y = r * (H['front'] + 18) + 18
    for j in (0, 1):
        im = Image.fromarray(cache[(k, j)]).crop(REG['front']).resize((Wd, H['front']), Image.LANCZOS)
        out.paste(im, (j * Wd, y))
        im = Image.fromarray(cache[(k, j)]).crop(REG['floor']).resize((Wd, H['front']), Image.LANCZOS)
        out.paste(im, (2 * Wd + 12 + j * Wd, y))
    d.text((4, y - 15), skins[k][0] + '    front end wall: diffuse | normal          inner floor: diffuse | normal', fill=(255, 255, 255))
out.save(W / 'plan_v2/region_compare.jpg', quality=88)
print('ok')
