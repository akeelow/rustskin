"""Sauna Boiler v4: проверочные рендеры (Blender, Cycles) — модель со своими сглаженными нормалями OBJ, как в игре.
Это не игровые кадры: только проверка формы и карт.

Режимы (--mode):
  bump     предпросмотр поля до запекания: высоты plan_v4/preview_h.npy (preview_v4.py) как Bump, серый материал
  grey     серый материал + только карта нормалей: что видно здесь — смоделировано («Diffuse против Normal»)
  diffuse  только Diffuse без освещения: что нарисовано цветом
  full     все карты (Diffuse, Normal, Spec/Gloss, Occlusion, Emission)

  blender -b -P skins/sauna/furnace/view_v4.py -- --mode grey --normal export/Furnace_v4.0_normal.png
          [--diffuse ... --specgloss ... --occlusion ... --emission ...] --shots front34,back --out renders/v4/grey
Пути — от папки котла. Пишет <out>_<кадр>.png.
"""
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
OBJ = HERE / "originals" / "furnace.obj"
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(name, default=None):
    return args[args.index(name) + 1] if name in args else default


# кадр: (камера, цель, фокусное, азимут солнца °, высота солнца °). Мир: z вверх, метры, топка смотрит в −Y
SHOTS = {
    "front34": ((1.25, -2.25, 1.6), (0.0, 0.0, 0.8), 42, -60, 35),
    "front": ((0.05, -2.7, 1.3), (0.0, 0.0, 0.78), 40, -100, 30),
    "opening": ((0.3, -1.25, 0.95), (0.0, -0.35, 0.68), 45, -70, 25),
    "plug": ((-0.75, -1.0, 0.85), (-0.3, -0.3, 0.7), 50, -140, 25),
    "ladle": ((0.95, -0.85, 0.95), (0.35, -0.25, 0.72), 50, -30, 25),
    "left": ((-2.5, -0.9, 1.35), (0.0, 0.0, 0.8), 40, -150, 30),
    "right": ((2.5, -0.9, 1.35), (0.0, 0.0, 0.8), 40, -20, 30),
    "back": ((-0.6, 2.6, 1.5), (0.0, 0.0, 0.85), 40, 110, 32),
    "back_close": ((-0.3, 1.25, 1.05), (0.0, 0.2, 0.95), 45, 120, 22),
    "base": ((0.95, -1.35, 0.45), (0.15, -0.3, 0.28), 45, -50, 18),
    "top": ((0.6, -1.3, 2.7), (0.0, 0.0, 1.45), 40, -60, 50),
}


def setup():
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
    sc.render.resolution_x, sc.render.resolution_y = int(size * 0.8), size
    sc.view_settings.view_transform = "Standard"
    return sc


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

    if mode == "bump":
        H = np.load(HERE / "plan_v4" / "preview_h.npy")
        s = H.shape[0]
        img = bpy.data.images.new("h", s, s, alpha=False, float_buffer=True)
        img.colorspace_settings.name = "Non-Color"
        buf = np.ones((s, s, 4), np.float32)
        buf[..., 0] = buf[..., 1] = buf[..., 2] = np.flipud(H)
        img.pixels.foreach_set(buf.ravel())
        t = N.new("ShaderNodeTexImage")
        t.image = img
        t.interpolation = "Cubic"
        b = N.new("ShaderNodeBump")
        b.inputs["Distance"].default_value = 0.01
        b.inputs["Strength"].default_value = 1.0
        L.new(t.outputs["Color"], b.inputs["Height"])
        L.new(b.outputs["Normal"], bs.inputs["Normal"])
        bs.inputs["Base Color"].default_value = (0.42, 0.42, 0.42, 1)
        bs.inputs["Roughness"].default_value = 0.7
        return m
    nrm = tex("normal", "Non-Color")
    if nrm and mode in ("grey", "full"):
        nm = N.new("ShaderNodeNormalMap")
        L.new(nrm.outputs["Color"], nm.inputs["Color"])
        L.new(nm.outputs["Normal"], bs.inputs["Normal"])
    if mode == "grey":
        bs.inputs["Base Color"].default_value = (0.42, 0.42, 0.42, 1)
        bs.inputs["Roughness"].default_value = 0.7
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
        mul.inputs[0].default_value = 0.65
        L.new(col, mul.inputs[6])
        L.new(occ.outputs["Color"], mul.inputs[7])
        col = mul.outputs[2]
    L.new(col, bs.inputs["Base Color"])
    sg = tex("specgloss", "Non-Color")
    if sg:   # Unity Specular, грубо: глянец из A -> шероховатость; сила отражения из яркости Spec
        inv = N.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        L.new(sg.outputs["Alpha"], inv.inputs[1])
        L.new(inv.outputs[0], bs.inputs["Roughness"])
        bw = N.new("ShaderNodeRGBToBW")
        L.new(sg.outputs["Color"], bw.inputs["Color"])
        mlt = N.new("ShaderNodeMath")
        mlt.operation = "MULTIPLY"
        mlt.inputs[1].default_value = 2.0
        L.new(bw.outputs[0], mlt.inputs[0])
        L.new(mlt.outputs[0], bs.inputs["Specular IOR Level"])
    em = tex("emission", "sRGB")
    if em:
        L.new(em.outputs["Color"], bs.inputs["Emission Color"])
        bs.inputs["Emission Strength"].default_value = float(opt("--emit", "3.0"))
    return m


def main():
    sc = setup()
    mode = opt("--mode", "grey")
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="NEGATIVE_Z", up_axis="Y")
    ob = bpy.context.selected_objects[0]
    ob.data.materials.clear()
    ob.data.materials.append(material(mode))
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, -0.003))
    fl = bpy.context.object
    fm = bpy.data.materials.new("floor")
    fm.use_nodes = True
    next(n for n in fm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.36, 0.32, 0.26, 1)
    fl.data.materials.append(fm)
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.55, 0.62, 0.75, 1)
    bg.inputs["Strength"].default_value = 0.0 if mode == "diffuse" else float(opt("--sky", "0.45"))
    sc.world = w
    sun_d = bpy.data.lights.new("sun", "SUN")
    sun_d.energy = float(opt("--sun", "4.0"))
    sun_d.angle = math.radians(1.5)
    sun = bpy.data.objects.new("sun", sun_d)
    sc.collection.objects.link(sun)
    cam_d = bpy.data.cameras.new("cam")
    cam_d.clip_start, cam_d.clip_end = 0.05, 100
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    out = opt("--out", "renders/v4/check")
    for name in opt("--shots", "front34").split(","):
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
