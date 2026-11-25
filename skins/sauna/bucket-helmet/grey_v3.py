"""Серые рендеры «только нормаль» для проверки по §9.2 (25.11.2026): гранёность и мыло.

Три ряда: без карты (только сглаженные нормали OBJ) | наша v2 | оригинал Facepunch. Серый материал, скользящий
солнечный свет и блик (roughness 0.35), чтобы гранёность low-poly и изломы по граням были видны. Сетка вырезана
альфой v2 (Alpha Cutoff 0.50), как в игре.

  blender -b -P skins/sauna/bucket-helmet/grey_v3.py -- [--tex <prefix>] [--out check_v3/grey]
Пишет <out>_sheet.png (3 ряда × 6 видов) и <out>_close.png (3 ряда × 4 крупных плана).
Это рендеры Blender, а не игровые кадры.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import helmet_view as hv   # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(name, default=None):
    return args[args.index(name) + 1] if name in args else default


TEX = opt("--tex", str(HERE / "export" / "SaunaBucket_v2"))
OUT = Path(opt("--out", str(HERE / "check_v3" / "grey"))).resolve()
ALPHA = Path(TEX + "_diffuse.png")

VIEWS = [("front", (0, -0.85, 0.32)), ("q34_left", (0.6, -0.6, 0.40)), ("q34_right", (-0.6, -0.6, 0.40)),
         ("side", (0.85, 0, 0.30)), ("back", (0.0, 0.85, 0.36)), ("top", (0.25, -0.45, 0.85))]
CLOSE = [("wall_left", (0.40, -0.18, 0.30), (0.12, -0.04, 0.29), 50),
         ("wall_right", (-0.40, -0.18, 0.30), (-0.12, -0.04, 0.29), 50),
         ("top", (0.06, -0.14, 0.62), (0.0, -0.012, 0.39), 45),
         ("back_low", (0.10, 0.40, 0.14), (0.0, 0.12, 0.20), 50)]


def grey_material(normal):
    m = bpy.data.materials.new("grey")
    m.use_nodes = True
    m.use_backface_culling = True
    N, L = m.node_tree.nodes, m.node_tree.links
    bs = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    bs.inputs["Base Color"].default_value = (0.45, 0.45, 0.45, 1)
    bs.inputs["Roughness"].default_value = 0.35
    if normal is not None:
        t = N.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(normal), check_existing=True)
        t.image.colorspace_settings.name = "Non-Color"
        nm = N.new("ShaderNodeNormalMap")
        L.new(t.outputs["Color"], nm.inputs["Color"])
        L.new(nm.outputs["Normal"], bs.inputs["Normal"])
    a = N.new("ShaderNodeTexImage")
    a.image = bpy.data.images.load(str(ALPHA), check_existing=True)
    gt = N.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = 0.5
    L.new(a.outputs["Alpha"], gt.inputs[0])
    L.new(gt.outputs[0], bs.inputs["Alpha"])
    try:
        m.surface_render_method = "DITHERED"
    except (AttributeError, TypeError):
        pass
    return m


def setup(normal):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"
    vt = [v.identifier for v in scene.view_settings.bl_rna.properties["view_transform"].enum_items]
    scene.view_settings.view_transform = "AgX" if "AgX" in vt else "Filmic"
    hv.import_obj(HERE / "originals" / "bucket.helmet.obj", grey_material(normal))
    hv.head()
    w = bpy.data.worlds.new("w")
    scene.world = w
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.35, 0.35, 0.37, 1)
    bg.inputs["Strength"].default_value = 0.35
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.active_object
    sun.data.energy = 4.0
    sun.data.angle = math.radians(2)
    return scene, sun


def aim_sun(sun, eye, tgt):
    """Свет сбоку от камеры и чуть сверху — скользящий по видимой стенке."""
    f = (Vector(tgt) - Vector(eye)).normalized()
    side = f.cross(Vector((0, 0, 1))).normalized()
    d = (f * 0.35 + side * 0.9 + Vector((0, 0, -0.35))).normalized()
    sun.matrix_world = hv.look_at(Vector((0, 0, 0)), d)


def main():
    rows = [("none", None), ("ours", Path(TEX + "_normal.png")),
            ("fp", HERE / "originals" / "metal_improvised_helmet_02_nrm.png")]
    tmp = OUT.with_name("_tmp.png")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    sheet, close = [], []
    for tag, nrm in rows:
        scene, sun = setup(nrm)
        for name, eye in VIEWS:
            hv.cam(scene, eye, hv.T, 50)
            aim_sun(sun, eye, hv.T)
            sheet.append(hv.render(scene, tmp, 420))
        for name, eye, tgt, lens in CLOSE:
            hv.cam(scene, eye, tgt, lens)
            aim_sun(sun, eye, tgt)
            close.append(hv.render(scene, tmp, 560))
    hv.save_sheet(sheet, 6, OUT.with_name(OUT.name + "_sheet.png"))
    hv.save_sheet(close, 4, OUT.with_name(OUT.name + "_close.png"))


main()
