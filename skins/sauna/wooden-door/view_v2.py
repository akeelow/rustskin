"""Sauna Door v2: проверочные рендеры (Blender, Cycles) — модель со своими сглаженными нормалями, как в игре.
Это проверка модели и карт, а не игровые кадры.

Режимы (--mode):
  grey     серый материал + только карта нормалей: что видно здесь — смоделировано (проверка «Diffuse против Normal»)
  diffuse  только Diffuse без освещения (emission): что нарисовано цветом
  full     все карты, как в редакторе: Diffuse с Alpha Cutoff 0.5 (--cutoff), Normal, Spec/Gloss, Occlusion, Emission
  night    full ночью: тёмное небо, свечение окна
За дверью — «улица» (столб, бочка, ящик на земле), чтобы было видно, что просвечивает сквозь потёки.

  blender -b -P skins/sauna/wooden-door/view_v2.py -- --tex export/Door_v2.0 --mode full \
          --shots front,window,low --out renders/v2/full [--size 1200] [--cutoff 0.5]
Пути — от папки двери. Пишет <out>_<кадр>.png.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
OBJ = HERE / "originals" / "door.hinged.wood.obj"
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(name, default=None):
    return args[args.index(name) + 1] if name in args else default


# Blender-координаты в см после импорта с переводом осей: x — ширина (−121 … 0), −y — перед двери, z — вверх.
# кадр: (камера, цель, фокусное, азимут солнца °, высота солнца °)
SHOTS = {
    "front": ((60, -330, 150), (-60, 0, 105), 32, -120, 35),
    "front_34": ((-250, -250, 170), (-60, 0, 105), 35, -60, 30),
    "window": ((-10, -95, 165), (-32, 0, 154), 45, -130, 25),
    "window_side": ((-110, -80, 160), (-32, 0, 154), 40, -40, 25),
    "towel": ((-40, -110, 160), (-80, 0, 160), 40, -140, 25),
    "handle": ((-140, -90, 110), (-100, 0, 95), 40, -150, 20),
    "low": ((-20, -120, 45), (-60, 0, 25), 35, -100, 15),
    "back": ((-120, 300, 150), (-60, 0, 105), 35, 60, 30),
    "window_back": ((-50, 95, 160), (-32, 0, 154), 45, 50, 25),
    "edge": ((60, -60, 120), (0, 0, 110), 45, -30, 25),
}


def material(mode, cutoff):
    m = bpy.data.materials.new("skin")
    m.use_nodes = True
    m.use_backface_culling = True
    N, L = m.node_tree.nodes, m.node_tree.links
    bs = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL")
    base = opt("--tex")

    def tex(key, cs):
        if not base:
            return None
        p = (HERE / f"{base}_{key}.png").resolve()
        if not p.exists():
            return None
        t = N.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(p))
        t.image.colorspace_settings.name = cs
        t.image.alpha_mode = "CHANNEL_PACKED"
        return t

    nrm = tex("normal", "Non-Color")
    if nrm and mode != "diffuse":
        nm = N.new("ShaderNodeNormalMap")
        L.new(nrm.outputs["Color"], nm.inputs["Color"])
        L.new(nm.outputs["Normal"], bs.inputs["Normal"])
    dif = tex("diffuse", "sRGB")
    if mode == "grey":
        bs.inputs["Base Color"].default_value = (0.42, 0.42, 0.42, 1)
        bs.inputs["Roughness"].default_value = 0.75
        if dif:
            mix_alpha(N, L, bs, out, dif, cutoff)
        return m
    if mode == "diffuse":
        em = N.new("ShaderNodeEmission")
        L.new(dif.outputs["Color"], em.inputs["Color"])
        mix_alpha(N, L, em, out, dif, cutoff)
        return m
    occ = tex("occlusion", "Non-Color")
    col = dif.outputs["Color"]
    if occ:
        mul = N.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs[0].default_value = 0.5
        L.new(col, mul.inputs[6])
        L.new(occ.outputs["Color"], mul.inputs[7])
        col = mul.outputs[2]
    L.new(col, bs.inputs["Base Color"])
    sg = tex("specgloss", "Non-Color")
    if sg:
        inv = N.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        L.new(sg.outputs["Alpha"], inv.inputs[1])
        L.new(inv.outputs[0], bs.inputs["Roughness"])
        L.new(sg.outputs["Color"], bs.inputs["Specular Tint"])
    em = tex("emission", "sRGB")
    if em:
        L.new(em.outputs["Color"], bs.inputs["Emission Color"])
        bs.inputs["Emission Strength"].default_value = 3.0 if mode == "night" else 1.0
    mix_alpha(N, L, bs, out, dif, cutoff)
    return m


def mix_alpha(N, L, shader, out, dif, cutoff):
    gt = N.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = cutoff if cutoff > 0 else -1.0
    L.new(dif.outputs["Alpha"], gt.inputs[0])
    # как в Unity (Cull Back): изнанка граней не рисуется — сквозь дырку в одной стороне двери видно насквозь
    geo = N.new("ShaderNodeNewGeometry")
    sub = N.new("ShaderNodeMath")
    sub.operation = "SUBTRACT"
    sub.use_clamp = True
    L.new(gt.outputs[0], sub.inputs[0])
    L.new(geo.outputs["Backfacing"], sub.inputs[1])
    tr = N.new("ShaderNodeBsdfTransparent")
    mx = N.new("ShaderNodeMixShader")
    L.new(sub.outputs[0], mx.inputs[0])
    L.new(tr.outputs[0], mx.inputs[1])
    L.new(shader.outputs[0], mx.inputs[2])
    L.new(mx.outputs[0], out.inputs["Surface"])


def prop(kind, loc, size, color):
    if kind == "box":
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    else:
        bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=1, location=loc)
    o = bpy.context.object
    o.scale = size
    m = bpy.data.materials.new("p")
    m.use_nodes = True
    next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (*color, 1)
    o.data.materials.append(m)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type == "OPTIX"
        sc.cycles.device = "GPU"
    except Exception:  # noqa: BLE001
        pass
    sc.cycles.samples = int(opt("--samples", "64"))
    sc.cycles.use_denoising = True
    sc.cycles.transparent_max_bounces = 16
    size = int(opt("--size", "1100"))
    sc.render.resolution_x, sc.render.resolution_y = size, int(size * 0.75)
    sc.view_settings.view_transform = "Standard"
    mode = opt("--mode", "grey")
    cutoff = float(opt("--cutoff", "0.5"))
    bpy.ops.wm.obj_import(filepath=str(OBJ))                       # Y вверх -> Z вверх
    ob = bpy.context.selected_objects[0]
    ob.scale = (100, 100, 100)
    ob.data.materials.clear()
    ob.data.materials.append(material(mode, cutoff))
    # земля и «улица» по обе стороны двери
    bpy.ops.mesh.primitive_plane_add(size=3000, location=(0, 0, 0))
    fl = bpy.context.object
    fm = bpy.data.materials.new("floor")
    fm.use_nodes = True
    next(n for n in fm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.32, 0.3, 0.27, 1)
    fl.data.materials.append(fm)
    for sgn in (1, -1):
        prop("cyl", (-75, sgn * 330, 110), (12, 12, 220), (0.35, 0.22, 0.12))        # столб — за окном
        prop("cyl", (-140, sgn * 420, 45), (28, 28, 90), (0.55, 0.12, 0.08))         # бочка
        prop("box", (60, sgn * 480, 60), (60, 60, 120), (0.2, 0.35, 0.55))           # ящик
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    night = mode == "night"
    bg.inputs["Color"].default_value = (0.55, 0.62, 0.75, 1) if not night else (0.02, 0.03, 0.06, 1)
    bg.inputs["Strength"].default_value = 0.0 if mode == "diffuse" else (0.35 if not night else 0.4)
    sc.world = w
    sun_d = bpy.data.lights.new("sun", "SUN")
    sun_d.energy = 4.0 if not night else 0.05
    sun_d.angle = math.radians(1.5)
    sun = bpy.data.objects.new("sun", sun_d)
    sc.collection.objects.link(sun)
    cam_d = bpy.data.cameras.new("cam")
    cam_d.clip_start, cam_d.clip_end = 1, 8000
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    out = opt("--out", "renders/v2/check")
    for name in opt("--shots", "front").split(","):
        pos, tgt, lens, az, el = SHOTS[name]
        cam.location = pos
        cam.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
        cam_d.lens = lens
        a, e = math.radians(az), math.radians(el)
        d = Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))
        sun.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        path = (HERE / f"{out}_{name}.png").resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        sc.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        print("->", path, flush=True)


if __name__ == "__main__":
    main()
