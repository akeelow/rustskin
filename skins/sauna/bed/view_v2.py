"""Sauna Bench v2: проверочные рендеры (Blender, Cycles) — модель со своими сглаженными нормалями, как в игре.

Режимы (--mode):
  grey     серый материал + только карта нормалей: что видно здесь — смоделировано (проверка «Diffuse против Normal»)
  diffuse  только Diffuse без освещения (emission): что нарисовано цветом
  full     все карты как в редакторе (Diffuse с альфой 0.5, Normal, Spec/Gloss, Occlusion)
Свет: низкое солнце (скользящий) + слабое небо. Кадры (--shots): см. SHOTS.

  blender -b -P skins/sauna/bed/view_v2.py -- --normal bake/v2/normal.png [--diffuse ...] [--specgloss ...]
          [--occlusion ...] --mode grey --shots deck_foot,deck_34 --out renders/v2/grey [--size 1200]
Пути карт — от папки полока. Пишет <out>_<кадр>.png.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
OBJ = HERE / "originals" / "bed.obj"
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(name, default=None):
    return args[args.index(name) + 1] if name in args else default


# кадр: (камера, цель, фокусное, азимут солнца °, высота солнца °) — координаты модели, см, z вверх, +x изголовье
SHOTS = {
    "overall": ((-300, -230, 190), (0, 0, 40), 45, -130, 35),
    "deck_34": ((-190, -150, 170), (-20, 0, 50), 50, -150, 18),
    "deck_foot": ((-150, -60, 105), (-80, -10, 55), 60, -160, 14),
    "deck_mid": ((10, -95, 120), (5, 5, 55), 55, 160, 14),
    "deck_head": ((5, -120, 150), (65, 0, 58), 45, -120, 22),
    "foot_end": ((-230, -40, 70), (-110, 0, 45), 55, -175, 20),
    "side": ((-20, -260, 70), (-20, 0, 40), 45, -100, 20),
    "towel": ((20, -90, 100), (82, 0, 60), 55, -60, 20),
    "towel_end": ((80, -130, 75), (82, -45, 60), 55, -80, 18),
    "headboard": ((-10, 0, 95), (111, 0, 64), 50, 180, 25),
    "headboard_back": ((260, 60, 110), (113, 0, 60), 50, 20, 25),
    "corner_foot": ((-170, -110, 55), (-115, -55, 30), 55, -140, 20),
    "corner_head": ((170, -110, 70), (115, -55, 40), 55, -40, 20),
}


def material(mode):
    m = bpy.data.materials.new("skin")
    m.use_nodes = True
    m.use_backface_culling = True
    N, L = m.node_tree.nodes, m.node_tree.links
    bs = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL")

    def tex(key, cs):
        p = opt("--" + key)
        if not p:
            return None
        t = N.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str((HERE / p).resolve()))
        t.image.colorspace_settings.name = cs
        return t

    nrm = tex("normal", "Non-Color")
    if nrm and mode in ("grey", "full"):
        nm = N.new("ShaderNodeNormalMap")
        L.new(nrm.outputs["Color"], nm.inputs["Color"])
        L.new(nm.outputs["Normal"], bs.inputs["Normal"])
    if mode == "grey":
        bs.inputs["Base Color"].default_value = (0.42, 0.42, 0.42, 1)
        bs.inputs["Roughness"].default_value = 0.75
        dif = tex("diffuse", "sRGB")
        if dif:   # альфа — чтобы одеяло было вырезано и в сером режиме
            mix_alpha(N, L, bs, out, dif)
        return m
    dif = tex("diffuse", "sRGB")
    if mode == "diffuse":
        em = N.new("ShaderNodeEmission")
        L.new(dif.outputs["Color"], em.inputs["Color"])
        L.new(em.outputs[0], out.inputs["Surface"])
        mix_alpha(N, L, em, out, dif)
        return m
    if dif:
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
        mix_alpha(N, L, bs, out, dif)
    sg = tex("specgloss", "Non-Color")
    if sg:   # Unity Specular: грубо — блеск из A, отражение из яркости Spec
        inv = N.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        L.new(sg.outputs["Alpha"], inv.inputs[1])
        L.new(inv.outputs[0], bs.inputs["Roughness"])
        L.new(sg.outputs["Color"], bs.inputs["Specular Tint"])
    return m


def mix_alpha(N, L, shader, out, dif):
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
    sc.render.resolution_x, sc.render.resolution_y = size, int(size * 0.62)
    sc.view_settings.view_transform = "Standard"
    mode = opt("--mode", "grey")
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="Y", up_axis="Z")
    ob = bpy.context.selected_objects[0]
    ob.data.materials.clear()
    ob.data.materials.append(material(mode))
    # пол
    bpy.ops.mesh.primitive_plane_add(size=1200, location=(0, 0, -4))
    fl = bpy.context.object
    fm = bpy.data.materials.new("floor")
    fm.use_nodes = True
    next(n for n in fm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.32, 0.3, 0.27, 1)
    fl.data.materials.append(fm)
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.55, 0.62, 0.75, 1)
    bg.inputs["Strength"].default_value = 0.35 if mode != "diffuse" else 0.0
    sc.world = w
    sun_d = bpy.data.lights.new("sun", "SUN")
    sun_d.energy = 4.0
    sun_d.angle = math.radians(1.5)
    sun = bpy.data.objects.new("sun", sun_d)
    sc.collection.objects.link(sun)
    cam_d = bpy.data.cameras.new("cam")
    cam_d.clip_start, cam_d.clip_end = 1, 5000
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    out = opt("--out", "renders/v2/check")
    for name in opt("--shots", "overall").split(","):
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
