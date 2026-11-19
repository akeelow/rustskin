"""Просмотр Sauna Bucket на голове-болванке (tools/blender/viewer.py --wear не сажает шлем на голову: OBJ шлема
в координатах головы, а манекен viewer.py стоит на земле — ведро уходит за кадр, renders/orig_sheet.png).

Это рендеры Blender, а не игровые кадры. Unity Specular приближён так: металличность = доля блика (spec > 0.08),
цвет металла берётся из блика, шероховатость = 1 − глянец; Occlusion умножается на цвет.

  blender -b -P skins/sauna/bucket-helmet/helmet_view.py -- --tex <prefix> --out <renders/v1> [--orig] [--blend f.blend]
        [--only sheet,close,icon,grey,compare,lineup]
--tex: <prefix>_{diffuse,normal,specgloss,occlusion}.png. --orig: оригинальные карты Facepunch.
Пишет <out>_sheet.png (день/ночь × 6 видов), <out>_close.png, <out>_icon.png (128 и 64 на 3/4), <out>_grey.png
(ч/б), <out>_compare.png (с оригиналом), <out>_lineup.png (с халатом и ящиком сета в одном свете).
"""
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(name, default=None):
    return args[args.index(name) + 1] if name in args else default


OUT = Path(opt("--out", str(HERE / "renders" / "v1"))).resolve()
ONLY = set(opt("--only", "sheet,close,icon,grey,compare,lineup").split(","))
ORIG = {"diffuse": HERE / "originals" / "metal_improvised_helmet_02_bc.png",
        "normal": HERE / "originals" / "metal_improvised_helmet_02_nrm.png",
        "specgloss": HERE / "originals" / "metal_improvised_helmet_02_sg.png",
        "occlusion": HERE / "originals" / "metal_improvised_helmet_02_ao.png"}


def maps_of(prefix):
    if prefix == "orig":
        return ORIG
    return {k: Path(f"{prefix}_{k}.png").resolve() for k in ("diffuse", "normal", "specgloss", "occlusion")}


def look_at(eye, tgt, up=Vector((0, 0, 1))):
    f = (tgt - eye).normalized()
    if abs(f.dot(up)) > 0.995:
        up = Vector((0, 1, 0))
    r = f.cross(up).normalized()
    u = r.cross(f)
    return Matrix(((r.x, u.x, -f.x, eye.x), (r.y, u.y, -f.y, eye.y), (r.z, u.z, -f.z, eye.z), (0, 0, 0, 1)))


def skin_material(name, maps, grey=False, cutoff=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.use_backface_culling = True
    N, L = m.node_tree.nodes, m.node_tree.links
    bs = next(n for n in N if n.type == "BSDF_PRINCIPLED")

    def tex(k, cs):
        p = maps.get(k)
        if not p or not Path(p).exists():
            return None
        n = N.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(str(p), check_existing=True)
        n.image.colorspace_settings.name = cs
        return n
    d = tex("diffuse", "sRGB")
    o = tex("occlusion", "Non-Color")
    s = tex("specgloss", "Non-Color")
    nm = tex("normal", "Non-Color")
    if d is None:
        rgb = N.new("ShaderNodeRGB")
        rgb.outputs[0].default_value = (0.5, 0.5, 0.5, 1)
        base = rgb.outputs[0]
    else:
        base = d.outputs["Color"]
    if cutoff > 0 and d is not None:
        gt = N.new("ShaderNodeMath")
        gt.operation = "GREATER_THAN"
        gt.inputs[1].default_value = cutoff
        L.new(d.outputs["Alpha"], gt.inputs[0])
        L.new(gt.outputs[0], bs.inputs["Alpha"])
        try:
            m.surface_render_method = "DITHERED"
        except (AttributeError, TypeError):
            pass
    if o:
        mul = N.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs["Factor"].default_value = 1.0
        L.new(base, mul.inputs[6])
        L.new(o.outputs["Color"], mul.inputs[7])
        base = mul.outputs[2]
    if s:
        sep = N.new("ShaderNodeSeparateColor")
        L.new(s.outputs["Color"], sep.inputs["Color"])
        met = N.new("ShaderNodeMapRange")
        met.inputs["From Min"].default_value = 0.10
        met.inputs["From Max"].default_value = 0.75
        L.new(sep.outputs["Red"], met.inputs["Value"])
        L.new(met.outputs["Result"], bs.inputs["Metallic"])
        mix = N.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        L.new(met.outputs["Result"], mix.inputs["Factor"])
        L.new(base, mix.inputs[6])
        L.new(s.outputs["Color"], mix.inputs[7])
        base = mix.outputs[2]
        inv = N.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        L.new(s.outputs["Alpha"], inv.inputs[1])
        L.new(inv.outputs[0], bs.inputs["Roughness"])
    else:
        bs.inputs["Roughness"].default_value = 0.7
    if grey:
        g = N.new("ShaderNodeRGBToBW")
        L.new(base, g.inputs["Color"])
        base = g.outputs["Val"]
    L.new(base, bs.inputs["Base Color"])
    if nm:
        nmap = N.new("ShaderNodeNormalMap")
        L.new(nm.outputs["Color"], nmap.inputs["Color"])
        L.new(nmap.outputs["Normal"], bs.inputs["Normal"])
    return m


def import_obj(path, mat, offset=(0, 0, 0)):
    bpy.ops.wm.obj_import(filepath=str(path), forward_axis="NEGATIVE_Z", up_axis="Y")
    obs = list(bpy.context.selected_objects)
    for o in obs:
        o.data.materials.clear()
        o.data.materials.append(mat)
        o.location = Vector(offset)
    return obs


def plain(name, rgb, rough=0.6):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    return m


def head(offset=(0, 0, 0)):
    """Голова и плечи болванки под ведром (Blender: x, −z OBJ, y OBJ). Лицо — к −y Blender (+z OBJ)."""
    mat = plain("dummy", (0.32, 0.30, 0.28))
    ox, oy, oz = offset
    parts = []

    def blob(loc, sc, kind="sphere"):
        if kind == "sphere":
            bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=(loc[0] + ox, loc[1] + oy, loc[2] + oz))
        else:
            bpy.ops.mesh.primitive_cylinder_add(vertices=48, location=(loc[0] + ox, loc[1] + oy, loc[2] + oz))
        o = bpy.context.active_object
        o.scale = sc
        bpy.ops.object.shade_smooth()
        o.data.materials.append(mat)
        parts.append(o)
    blob((0, -0.005, 0.215), (0.082, 0.098, 0.115))           # голова
    blob((0, -0.075, 0.205), (0.016, 0.03, 0.02))              # нос
    blob((0, 0.005, 0.07), (0.05, 0.05, 0.07), "cyl")         # шея
    blob((0, 0.01, -0.03), (0.21, 0.11, 0.055))                # плечи
    blob((0, 0.01, -0.17), (0.17, 0.12, 0.15))                 # грудь
    return parts


def lights(scene, mode):
    w = scene.world or bpy.data.worlds.new("w")
    scene.world = w
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    for o in [o for o in scene.objects if o.type == "LIGHT"]:
        bpy.data.objects.remove(o)
    if mode == "day":
        bg.inputs["Color"].default_value = (0.55, 0.62, 0.75, 1)
        bg.inputs["Strength"].default_value = 0.8
        d, e, c = Vector((-0.5, 0.6, -0.9)), 3.5, (1.0, 0.96, 0.9)
    elif mode == "studio":
        bg.inputs["Color"].default_value = (0.42, 0.42, 0.42, 1)
        bg.inputs["Strength"].default_value = 0.9
        d, e, c = Vector((-0.4, 0.7, -0.6)), 3.0, (1.0, 0.98, 0.95)
    else:
        bg.inputs["Color"].default_value = (0.03, 0.04, 0.07, 1)
        bg.inputs["Strength"].default_value = 1.0
        d, e, c = Vector((-0.3, 0.6, -0.8)), 0.35, (0.6, 0.7, 1.0)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.active_object
    sun.matrix_world = look_at(Vector((0, 0, 0)), d)
    sun.data.energy = e
    sun.data.color = c
    sun.data.angle = math.radians(3)


def cam(scene, eye, tgt, lens=50):
    c = scene.camera
    if c is None:
        bpy.ops.object.camera_add()
        c = bpy.context.active_object
        scene.camera = c
        c.data.clip_start = 0.005
    c.matrix_world = look_at(Vector(eye), Vector(tgt))
    c.data.lens = lens


def render(scene, path, size):
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(str(path))
    a = np.array(img.pixels[:], np.float32).reshape(size, size, 4)[::-1, :, :3]
    bpy.data.images.remove(img)
    Path(path).unlink()
    return a


def save_sheet(tiles, cols, path):
    rows = [np.concatenate(tiles[i:i + cols], 1) for i in range(0, len(tiles), cols)]
    a = np.concatenate(rows, 0)
    h, w = a.shape[:2]
    im = bpy.data.images.new("sheet", w, h, alpha=False)
    buf = np.ones((h, w, 4), np.float32)
    buf[..., :3] = a[::-1]
    im.pixels.foreach_set(buf.ravel())
    im.filepath_raw = str(path)
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)
    print("->", path, flush=True)


T = Vector((0, -0.005, 0.27))        # центр ведра в Blender
VIEWS = [("front", (0, -0.85, 0.32)), ("q34_left", (0.6, -0.6, 0.40)), ("q34_right", (-0.6, -0.6, 0.40)),
         ("side", (0.85, 0, 0.30)), ("back", (0.0, 0.85, 0.36)), ("top", (0.25, -0.45, 0.85))]
CLOSE = [("hole", (0.05, -0.32, 0.24), (0.0, -0.12, 0.22), 50), ("leaf", (0.32, -0.25, 0.32), (0.10, -0.09, 0.30), 55),
         ("joint", (-0.33, -0.17, 0.35), (-0.11, -0.05, 0.34), 55), ("top", (0.06, -0.12, 0.62), (0.0, -0.012, 0.39), 45),
         ("ear", (0.36, -0.08, 0.15), (0.15, 0.0, 0.15), 70), ("inside", (0.0, -0.18, -0.02), (0.0, 0.0, 0.32), 32)]


def setup(prefix, grey=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"
    vt = [v.identifier for v in scene.view_settings.bl_rna.properties["view_transform"].enum_items]
    scene.view_settings.view_transform = "AgX" if "AgX" in vt else "Filmic"
    mat = skin_material("bucket", maps_of(prefix), grey, cutoff=0.5)   # v2: сетка вырезана альфой
    import_obj(HERE / "originals" / "bucket.helmet.obj", mat)
    head()
    return scene


def main():
    prefix = "orig" if "--orig" in args else opt("--tex")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_name("_tmp.png")
    if "sheet" in ONLY:
        scene = setup(prefix)
        tiles = []
        for mode in ("day", "night"):
            lights(scene, mode)
            for name, eye in VIEWS:
                cam(scene, eye, T, 50)
                tiles.append(render(scene, tmp, 512))
        save_sheet(tiles, 6, OUT.with_name(OUT.name + "_sheet.png"))
        if "--blend" in args:
            lights(scene, "day")
            bpy.ops.wm.save_as_mainfile(filepath=str(Path(opt("--blend")).resolve()))
    if "close" in ONLY:
        scene = setup(prefix)
        lights(scene, "day")
        tiles = []
        for name, eye, tgt, lens in CLOSE:
            cam(scene, eye, tgt, lens)
            tiles.append(render(scene, tmp, 640))
        save_sheet(tiles, 3, OUT.with_name(OUT.name + "_close.png"))
    if "grey" in ONLY:
        scene = setup(prefix, grey=True)
        lights(scene, "studio")
        tiles = []
        for name, eye in (VIEWS[0], VIEWS[1], VIEWS[5]):
            cam(scene, eye, T, 50)
            tiles.append(render(scene, tmp, 512))
        save_sheet(tiles, 3, OUT.with_name(OUT.name + "_grey.png"))
    if "icon" in ONLY:
        scene = setup(prefix)
        lights(scene, "studio")
        tiles = []
        for name, eye in (VIEWS[0], VIEWS[1]):
            cam(scene, eye, T, 58)
            a = render(scene, tmp, 512)
            for sz in (128, 64):
                k = 512 // sz
                s = a.reshape(sz, k, sz, k, 3).mean((1, 3))
                big = np.repeat(np.repeat(s, k, 0), k, 1)     # показ крупно, по пикселям иконки
                tiles.append(big)
        save_sheet(tiles, 4, OUT.with_name(OUT.name + "_icon.png"))
    if "compare" in ONLY:
        tiles = []
        for pre in ("orig", prefix):
            scene = setup(pre)
            lights(scene, "day")
            for name, eye in (VIEWS[1], VIEWS[3]):
                cam(scene, eye, T, 50)
                tiles.append(render(scene, tmp, 512))
        save_sheet(tiles, 4, OUT.with_name(OUT.name + "_compare.png"))
    if "nd" in ONLY:   # проверка «всё рельефное — геометрией»: только Normal (серый, скользящий свет) против только Diffuse
        tiles = []
        mp = maps_of(prefix)
        for kind in ("normal", "diffuse"):
            scene = setup("orig")
            if kind == "normal":
                m = skin_material("n_only", {"normal": mp["normal"]})
                b_ = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
                b_.inputs["Base Color"].default_value = (0.5, 0.5, 0.5, 1)
            else:
                m = bpy.data.materials.new("d_only")
                m.use_nodes = True
                m.use_backface_culling = True
                N_, L_ = m.node_tree.nodes, m.node_tree.links
                out = next(n for n in N_ if n.type == "OUTPUT_MATERIAL")
                t = N_.new("ShaderNodeTexImage")
                t.image = bpy.data.images.load(str(mp["diffuse"]))
                e = N_.new("ShaderNodeEmission")
                L_.new(t.outputs["Color"], e.inputs["Color"])
                L_.new(e.outputs[0], out.inputs["Surface"])
            for o in scene.objects:
                if o.type == "MESH" and o.data.materials and o.data.materials[0].name.startswith("bucket"):
                    o.data.materials[0] = m
            lights(scene, "studio")
            sun = next(o for o in scene.objects if o.type == "LIGHT")
            sun.matrix_world = look_at(Vector((0, 0, 0)), Vector((-1.0, 0.15, -0.12)))   # скользящий свет сбоку
            for name, eye, tgt, lens in (CLOSE[0], CLOSE[1], CLOSE[2], CLOSE[3]):
                cam(scene, eye, tgt, lens)
                tiles.append(render(scene, tmp, 512))
        save_sheet(tiles, 4, OUT.with_name(OUT.name + "_nd.png"))
    if "lineup" in ONLY:
        scene = setup(prefix)
        lights(scene, "day")
        box = ROOT / "skins" / "sauna" / "wood-storage-box"
        bm = skin_material("box", {"diffuse": box / "export" / "Box_v1.6_diffuse.png",
                                   "normal": box / "export" / "Box_v1.6_normal.png",
                                   "specgloss": box / "export" / "Box_v1.6_specgloss.png",
                                   "occlusion": box / "export" / "Box_v1.6_occlusion.png"}, cutoff=0.5)
        import_obj(box / "originals" / "box.wooden.obj", bm, (-0.75, 0.25, -0.35))
        sj = ROOT / "skins" / "sauna" / "snow-jacket"
        jm = skin_material("robe", {"diffuse": sj / "export" / "SnowJacket_v2.5_diffuse.png",
                                    "normal": sj / "export" / "SnowJacket_v2.5_normal.png",
                                    "specgloss": sj / "export" / "SnowJacket_v2.5_specgloss.png"})
        import_obj(sj / "originals" / "jacket.snow.obj", jm, (0.0, 0.0, -0.86))
        cam(scene, (0.35, -1.9, 0.25), (-0.25, 0.0, -0.15), 35)
        save_sheet([render(scene, tmp, 900)], 1, OUT.with_name(OUT.name + "_lineup.png"))


if __name__ == "__main__":
    main()
