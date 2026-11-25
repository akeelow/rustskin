"""Sauna Robe v3: проверочные рендеры (Blender, Cycles) — low-poly со своими сглаженными нормалями, как в игре.
Образец — bed/view_v2.py. Это не игровые кадры: в игре свет, Fuzz и тон другие.

Режимы (--mode):
  grey     серый материал + только карта нормалей: что видно здесь — смоделировано («Diffuse против Normal»)
  diffuse  только Diffuse без освещения (emission): что нарисовано цветом
  full     Diffuse, Normal, Spec/Gloss, Occlusion
Свет: солнце (азимут и высота на кадр) + небо.

  blender -b -P skins/sauna/snow-jacket/view_v3.py -- --normal export/SnowJacket_v3.0_normal.png
          [--diffuse ...] [--specgloss ...] [--occlusion ...] --mode grey --shots front,belt --out renders/v3/grey
Пути карт — от папки халата. Пишет <out>_<кадр>.png.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
OBJ = HERE / "originals" / "jacket.snow.obj"
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(name, default=None):
    return args[args.index(name) + 1] if name in args else default


# кадр: (камера, цель, фокусное, азимут солнца °, высота солнца °); м, y вверх, +z перёд, +x левая сторона персонажа
SHOTS = {
    "front": ((0.0, 0.58, 2.6), (0.0, 0.55, 0.0), 50, 60, 35),
    "three_quarter": ((1.25, 0.80, 2.2), (0.0, 0.55, 0.0), 50, 40, 30),
    "back": ((0.0, 0.58, -2.6), (0.0, 0.55, 0.0), 50, -120, 35),
    "side": ((2.6, 0.58, 0.3), (0.0, 0.55, 0.0), 50, 10, 30),
    "belt": ((0.10, 0.52, 0.75), (0.03, 0.47, 0.0), 50, 60, 25),
    "neck": ((0.05, 0.78, 0.80), (0.0, 0.70, 0.0), 50, 70, 30),
    "pocket_roll": ((-0.25, 0.52, 0.65), (-0.12, 0.47, 0.05), 50, 120, 25),
    "sleeve": ((0.95, 0.50, 0.70), (0.38, 0.45, 0.0), 50, 30, 25),
    "back_hem": ((0.0, 0.40, -1.1), (0.0, 0.33, 0.0), 50, -100, 25),
}


def look(direction):
    """Поворот, при котором −Z объекта смотрит по direction, а +Y — вверх (мировая ось y)."""
    f = Vector(direction).normalized()
    r = f.cross(Vector((0, 1, 0)))
    if r.length < 1e-6:
        r = Vector((1, 0, 0))
    r.normalize()
    u = r.cross(f)
    return Matrix((r, u, -f)).transposed().to_euler()


def material(mode):
    m = bpy.data.materials.new("skin")
    m.use_nodes = True
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
        bs.inputs["Base Color"].default_value = (0.45, 0.45, 0.45, 1)
        bs.inputs["Roughness"].default_value = 0.8
        return m
    dif = tex("diffuse", "sRGB")
    if mode == "diffuse":
        em = N.new("ShaderNodeEmission")
        L.new(dif.outputs["Color"], em.inputs["Color"])
        L.new(em.outputs[0], out.inputs["Surface"])
        return m
    col = dif.outputs["Color"]
    occ = tex("occlusion", "Non-Color")
    if occ:
        mul = N.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs[0].default_value = 1.0
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
    bs.inputs["Specular IOR Level"].default_value = 0.2
    if "Sheen Weight" in bs.inputs:   # ворс ткани (в игре — Fuzz)
        bs.inputs["Sheen Weight"].default_value = 0.4
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
    sc.cycles.samples = int(opt("--samples", "48"))
    sc.cycles.use_denoising = True
    size = int(opt("--size", "1000"))
    sc.render.resolution_x, sc.render.resolution_y = size, int(size * 1.15)
    sc.view_settings.view_transform = "Standard"
    mode = opt("--mode", "grey")
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="Y", up_axis="Z")
    ob = bpy.context.selected_objects[0]
    ob.data.materials.clear()
    ob.data.materials.append(material(mode))
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.55, 0.62, 0.75, 1)
    bg.inputs["Strength"].default_value = 0.4 if mode != "diffuse" else 0.0
    sc.world = w
    sun_d = bpy.data.lights.new("sun", "SUN")
    sun_d.energy = 3.5
    sun_d.angle = math.radians(2)
    sun = bpy.data.objects.new("sun", sun_d)
    sc.collection.objects.link(sun)
    cam_d = bpy.data.cameras.new("cam")
    cam_d.clip_start, cam_d.clip_end = 0.01, 50
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    out = opt("--out", "renders/v3/check")
    for name in opt("--shots", "front").split(","):
        pos, tgt, lens, az, el = SHOTS[name]
        cam.location = pos
        cam.rotation_euler = look(Vector(tgt) - Vector(pos))
        cam_d.lens = lens
        a, e = math.radians(az), math.radians(el)
        d = Vector((math.cos(e) * math.sin(a), math.sin(e), math.cos(e) * math.cos(a)))   # y вверх, az от +z к +x
        sun.rotation_euler = look(-d)
        path = (HERE / f"{out}_{name}.png").resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        sc.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        print("->", path, flush=True)


if __name__ == "__main__":
    main()
