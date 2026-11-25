"""Sauna Stone Box v2: проверочные рендеры (Blender, Cycles) на модели «как в игре» (renders/concepts/box_game.obj:
изнанка стенок носит UV своей наружной стороны) со своими сглаженными нормалями. Это НЕ кадры из игры.

Режимы (--mode):
  grey     серый материал + только карта нормалей: что видно здесь — смоделировано («Diffuse против Normal»)
  diffuse  только Diffuse без освещения: что нарисовано цветом
  full     все карты как в редакторе (Diffuse с альфой 0.5, Normal, Spec/Gloss, Occlusion, Emission)
--night: солнце выключено, небо почти чёрное — смотреть свечение.

  blender -b -P skins/sauna/wood-storage-box/view_v2.py -- --tag v2.0 --mode full --shots 34,top --out renders/v2/full
Пишет <out>_<кадр>.png (пути от папки ящика).
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
OBJ = HERE / "renders" / "concepts" / "box_game.obj"
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(name, default=None):
    return args[args.index(name) + 1] if name in args else default


# кадр: (камера, цель, фокусное, азимут солнца °, высота солнца °) — координаты Blender, см: x как в OBJ,
# -y — перед ящика (+z OBJ, прорезь), z вверх; +x — бок к печи
SHOTS = {
    "34": ((125, -150, 120), (0, 0, 18), 40, -40, 35),
    "34b": ((-125, 150, 120), (0, 0, 18), 40, 140, 35),
    "34l": ((-130, -140, 110), (0, 0, 18), 40, -130, 35),
    "top": ((0.5, 0, 175), (0, 0, 0), 34, -60, 45),
    "inside": ((15, -40, 90), (0, 2, 4), 38, -40, 40),
    "floor_close": ((5, -12, 55), (2, 5, 4), 40, -50, 35),
    "corner": ((75, -95, 45), (34, -47, 24), 45, -20, 25),
    "slot": ((10, -105, 62), (0, -46, 42), 50, -70, 30),
    "rim": ((80, 10, 75), (34, 0, 50), 42, -10, 30),
    "inner_wall": ((-10, 25, 70), (-34, 0, 28), 42, 20, 25),
    "side": ((260, 0, 40), (0, 0, 25), 45, 20, 25),
}


def material(mode, tag):
    m = bpy.data.materials.new("skin")
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    bs = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL")

    def tex(key, cs):
        p = HERE / "export" / f"Box_{tag}_{key}.png"
        if not p.exists():
            return None
        t = N.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(p))
        t.image.colorspace_settings.name = cs
        return t

    nrm = tex("normal", "Non-Color")
    if nrm and mode in ("grey", "full"):
        nm = N.new("ShaderNodeNormalMap")
        L.new(nrm.outputs["Color"], nm.inputs["Color"])
        L.new(nm.outputs["Normal"], bs.inputs["Normal"])
    dif = tex("diffuse", "sRGB")
    if mode == "grey":
        bs.inputs["Base Color"].default_value = (0.42, 0.42, 0.42, 1)
        bs.inputs["Roughness"].default_value = 0.75
        mix_alpha(N, L, bs, out, dif)
        return m
    if mode == "diffuse":
        em = N.new("ShaderNodeEmission")
        L.new(dif.outputs["Color"], em.inputs["Color"])
        mix_alpha(N, L, em, out, dif)
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
        bs.inputs["Emission Strength"].default_value = float(opt("--emit", "1.0"))
    mix_alpha(N, L, bs, out, dif)
    return m


def mix_alpha(N, L, shader, out, dif):
    if dif is None:
        L.new(shader.outputs[0], out.inputs["Surface"])
        return
    gt = N.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = 0.5
    L.new(dif.outputs["Alpha"], gt.inputs[0])
    tr = N.new("ShaderNodeBsdfTransparent")
    mx = N.new("ShaderNodeMixShader")
    L.new(gt.outputs[0], mx.inputs[0])
    L.new(tr.outputs[0], mx.inputs[1])
    L.new(shader.outputs[0], mx.inputs[2])
    L.new(mx.outputs[0], out.inputs["Surface"])


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
    size = int(opt("--size", "1100"))
    sc.render.resolution_x, sc.render.resolution_y = size, int(size * 0.7)
    sc.view_settings.view_transform = "Standard"
    mode = opt("--mode", "grey")
    night = "--night" in args
    bpy.ops.wm.obj_import(filepath=str(OBJ))           # оси по умолчанию: y вверх в OBJ -> z вверх
    ob = bpy.context.selected_objects[0]
    ob.scale = (100, 100, 100)
    ob.data.materials.clear()
    ob.data.materials.append(material(mode, opt("--tag", "v2.0")))
    bpy.ops.mesh.primitive_plane_add(size=1200, location=(0, 0, -0.05))
    fl = bpy.context.object
    fm = bpy.data.materials.new("floor")
    fm.use_nodes = True
    next(n for n in fm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.5, 0.42, 0.32, 1)
    fl.data.materials.append(fm)
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.55, 0.62, 0.75, 1) if not night else (0.05, 0.06, 0.1, 1)
    bg.inputs["Strength"].default_value = (0.35 if not night else 0.05) if mode != "diffuse" else 0.0
    sc.world = w
    sun_d = bpy.data.lights.new("sun", "SUN")
    sun_d.energy = 0.0 if night else 4.0
    sun_d.angle = math.radians(1.5)
    sun = bpy.data.objects.new("sun", sun_d)
    sc.collection.objects.link(sun)
    cam_d = bpy.data.cameras.new("cam")
    cam_d.clip_start, cam_d.clip_end = 1, 5000
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    out = opt("--out", "renders/v2/check")
    for name in opt("--shots", "34").split(","):
        pos, tgt, lens, az, el = SHOTS[name]
        cam.location = pos
        cam.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
        cam_d.lens = lens
        a, e = math.radians(az), math.radians(el)
        d = Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))
        sun.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        path = (HERE / f"{out}_{name}{'_night' if night else ''}.png").resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        sc.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        print("->", path, flush=True)


if __name__ == "__main__":
    main()
