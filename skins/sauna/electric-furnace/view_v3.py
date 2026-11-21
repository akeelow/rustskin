"""Sauna Stove v3: проверочные рендеры (Blender, Cycles) — модель со своими сглаженными нормалями, как в игре.

Режимы (--mode):
  atlas    только текстура без света (--diffuse = атлас номеров uv/islands_v3_num.png): какой остров где на модели
  grey     серый материал + только карта нормалей: что видно здесь — смоделировано («Diffuse против Normal»)
  diffuse  только Diffuse без освещения
  full     все карты как в редакторе: Diffuse (альфа по Alpha Cutoff), Normal, Metal/Gloss (RGB металл, A глянец),
           Occlusion, Emission
Свет: солнце (--sun az,el для всех кадров или из SHOTS) + слабое небо; --night — без солнца, тусклое небо.

  blender -b -P skins/sauna/electric-furnace/view_v3.py -- --mode atlas --diffuse uv/islands_v3_num.png \
          --shots front,back,left,right,top --out renders/v3/atlas [--size 1100] [--samples 32]
Пути карт — от папки каменки. Пишет <out>_<кадр>.png.

Оси: OBJ (x вправо, y вверх, z вперёд) импортируется как в bake_v2 (forward −Z, up Y): в мире Blender перед — −Y,
верх — +Z, правый бок — +X. Метры.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
OBJ = HERE / "originals" / "electric.furnace.obj"
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(name, default=None):
    return args[args.index(name) + 1] if name in args else default


# кадр: (камера, цель, фокусное, азимут солнца °, высота солнца °), мир Blender, метры
SHOTS = {
    "front": ((0, -3.4, 0.62), (0, 0, 0.58), 50, -110, 35),
    "back": ((0, 3.4, 0.62), (0, 0, 0.58), 50, 70, 35),
    "left": ((-3.4, 0, 0.62), (0, 0, 0.58), 50, -160, 35),
    "right": ((3.4, 0, 0.62), (0, 0, 0.58), 50, -20, 35),
    "top": ((0, -0.25, 3.4), (0, 0, 1.1), 50, -120, 55),
    "34_left": ((-2.1, -2.5, 2.0), (0, 0, 0.6), 45, -150, 35),
    "34_right": ((2.1, -2.5, 2.0), (0, 0, 0.6), 45, -30, 35),
    "34_back": ((2.1, 2.5, 2.0), (0, 0, 0.6), 45, 30, 35),
    "firebox": ((0.0, -1.05, 0.78), (0, 0, 0.68), 40, -100, 30),
    "plinth": ((-1.3, -1.7, 0.4), (0, 0, 0.18), 45, -140, 20),
    "side_close": ((-1.25, -0.35, 0.9), (-0.32, 0.0, 0.7), 50, -170, 15),
    "top_close": ((0.25, -0.95, 1.75), (0.0, -0.05, 1.14), 45, -130, 25),
    "door_close": ((0.25, -1.1, 0.85), (0.0, -0.33, 0.7), 50, -120, 20),
}


def tex(N, key, cs):
    p = opt("--" + key)
    if not p:
        return None
    t = N.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(str((HERE / p).resolve()))
    t.image.colorspace_settings.name = cs
    t.interpolation = "Cubic" if key == "normal" else "Linear"
    return t


def mix_alpha(N, L, shader, out, dif, cut):
    gt = N.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = cut
    L.new(dif.outputs["Alpha"], gt.inputs[0])
    tr = N.new("ShaderNodeBsdfTransparent")
    mx = N.new("ShaderNodeMixShader")
    L.new(gt.outputs[0], mx.inputs[0])
    L.new(tr.outputs[0], mx.inputs[1])
    L.new(shader.outputs[0], mx.inputs[2])
    L.new(mx.outputs[0], out.inputs["Surface"])


def material(mode):
    m = bpy.data.materials.new("skin")
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    bs = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL")
    cut = float(opt("--cutoff", "0.99"))
    dif = tex(N, "diffuse", "sRGB")
    if mode in ("atlas", "diffuse"):
        em = N.new("ShaderNodeEmission")
        L.new(dif.outputs["Color"], em.inputs["Color"])
        if mode == "diffuse" and dif:
            mix_alpha(N, L, em, out, dif, cut)
        else:
            L.new(em.outputs[0], out.inputs["Surface"])
        return m
    nrm = tex(N, "normal", "Non-Color")
    if nrm:
        nm = N.new("ShaderNodeNormalMap")
        L.new(nrm.outputs["Color"], nm.inputs["Color"])
        L.new(nm.outputs["Normal"], bs.inputs["Normal"])
    if mode == "grey":
        bs.inputs["Base Color"].default_value = (0.42, 0.42, 0.42, 1)
        bs.inputs["Roughness"].default_value = 0.7
        if dif:
            mix_alpha(N, L, bs, out, dif, cut)
        return m
    col = dif.outputs["Color"]
    occ = tex(N, "occlusion", "Non-Color")
    if occ:
        mul = N.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs[0].default_value = 1.0
        L.new(col, mul.inputs[6])
        L.new(occ.outputs["Color"], mul.inputs[7])
        col = mul.outputs[2]
    L.new(col, bs.inputs["Base Color"])
    mg = tex(N, "metalgloss", "Non-Color")
    if mg:  # Unity Standard (metallic): RGB = металличность, A = глянец
        sep = N.new("ShaderNodeSeparateColor")
        L.new(mg.outputs["Color"], sep.inputs[0])
        L.new(sep.outputs[0], bs.inputs["Metallic"])
        inv = N.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        L.new(mg.outputs["Alpha"], inv.inputs[1])
        L.new(inv.outputs[0], bs.inputs["Roughness"])
    em = tex(N, "emission", "sRGB")
    if em:
        L.new(em.outputs["Color"], bs.inputs["Emission Color"])
        bs.inputs["Emission Strength"].default_value = float(opt("--emit", "4.0"))
    mix_alpha(N, L, bs, out, dif, cut)
    return m


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
    mode = opt("--mode", "grey")
    sc.cycles.samples = int(opt("--samples", "16" if mode == "atlas" else "64"))
    sc.cycles.use_denoising = mode != "atlas"
    size = int(opt("--size", "1100"))
    sc.render.resolution_x, sc.render.resolution_y = size, int(size * 0.75)
    sc.view_settings.view_transform = "Standard"
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="NEGATIVE_Z", up_axis="Y")
    ob = bpy.context.selected_objects[0]
    ob.data.materials.clear()
    ob.data.materials.append(material(mode))
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, -0.002))
    fl = bpy.context.object
    fm = bpy.data.materials.new("floor")
    fm.use_nodes = True
    next(n for n in fm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.3, 0.28, 0.25, 1)
    fl.data.materials.append(fm)
    night = "--night" in args
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.55, 0.62, 0.75, 1) if not night else (0.05, 0.06, 0.09, 1)
    bg.inputs["Strength"].default_value = 0.0 if mode in ("atlas", "diffuse") else (0.35 if not night else 0.2)
    sc.world = w
    sun_d = bpy.data.lights.new("sun", "SUN")
    sun_d.energy = 0.0 if (night or mode in ("atlas", "diffuse")) else 4.0
    sun_d.angle = math.radians(1.5)
    sun = bpy.data.objects.new("sun", sun_d)
    sc.collection.objects.link(sun)
    cam_d = bpy.data.cameras.new("cam")
    cam_d.clip_start, cam_d.clip_end = 0.01, 100
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    out = opt("--out", "renders/v3/check")
    sun_override = opt("--sun")
    for name in opt("--shots", "front").split(","):
        pos, tgt, lens, az, el = SHOTS[name]
        if sun_override:
            az, el = map(float, sun_override.split(","))
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
