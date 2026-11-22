"""Sauna Changing Locker v6: проверочные рендеры (Blender, Cycles). Модель с плоскими гранями — как в игре (PLAN_v6.md, 1.5).

Это рендеры Blender, а не игра: тон и свет в редакторе другие (§9.6 гайда). Для проверки формы и масок.

Режимы (--mode):
  grey     серый материал + только Normal: что видно здесь — смоделировано («Diffuse против Normal»)
  diffuse  только Diffuse без света: что нарисовано цветом
  full     все карты (Diffuse с альфой 0.5, Normal, Spec/Gloss, Occlusion, Emission), день
  night    то же ночью: слабое небо, без солнца — видно свечение

  blender -b -P skins/sauna/locker/view_v6.py -- --tag v6.0 --mode full --shots front34,niche --out renders/v6/full
Пишет <out>_<кадр>.png (пути — от папки шкафчика).
"""
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
OBJ = HERE / "originals" / "locker.obj"
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(name, default=None):
    return args[args.index(name) + 1] if name in args else default


# Blender: X = x, Y = −z (перед шкафа смотрит в −Y), Z = y (вверх). Кадр: камера, цель, фокусное, азимут и высота солнца
SHOTS = {
    "front34": ((-170, -270, 175), (-5, 0, 108), 30, -125, 38),
    "front": ((0, -360, 125), (0, 0, 112), 32, -100, 35),
    "niche": ((-25, -150, 150), (-60, 5, 118), 30, -120, 30),
    "door": ((8, -125, 140), (0, -27, 132), 34, -125, 30),
    "door_low": ((0, -110, 70), (0, -27, 95), 34, -140, 22),
    "side": ((-270, -80, 105), (-90, 0, 112), 33, -160, 18),
    "frame": ((-120, -110, 60), (-60, -26, 40), 34, -130, 25),
    "back": ((150, 300, 150), (0, 0, 112), 30, 60, 35),
    "top": ((-120, -200, 330), (-10, 0, 215), 30, -120, 45),
    "drawer": ((10, -90, 60), (0, -24, 32), 34, -130, 30),
}


def load_obj(path):
    Vv, Tt, Ff = [], [], []
    for line in open(path, encoding="utf8", errors="replace"):
        if line.startswith("v "):
            Vv.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("vt "):
            Tt.append([float(x) for x in line.split()[1:3]])
        elif line.startswith("f "):
            idx = [p.split("/") for p in line.split()[1:]]
            Ff.append(([int(p[0]) - 1 for p in idx], [int(p[1]) - 1 for p in idx]))
    return np.array(Vv), np.array(Tt), Ff


def model():
    V, T, F = load_obj(OBJ)
    verts, polys, uvs = [], [], []
    for vi, ti in F:
        b = len(verts)
        verts += [(V[i][0], -V[i][2], V[i][1]) for i in vi]
        polys.append(tuple(range(b, b + len(vi))))
        uvs += [tuple(T[t]) for t in ti]
    me = bpy.data.meshes.new("locker")
    me.from_pydata(verts, [], polys)
    me.uv_layers.new(name="UVMap").data.foreach_set("uv", np.asarray(uvs, np.float32).ravel())
    me.polygons.foreach_set("use_smooth", np.zeros(len(polys), bool))
    me.update()
    ob = bpy.data.objects.new("locker", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def material(mode, tag):
    m = bpy.data.materials.new("skin")
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    bs = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL")

    def tex(slot, cs):
        p = HERE / "export" / f"Locker_{tag}_{slot}.png"
        if not p.exists():
            return None
        t = N.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(p))
        t.image.colorspace_settings.name = cs
        return t

    dif = tex("diffuse", "sRGB")
    nrm = tex("normal", "Non-Color")
    if nrm is not None and mode != "diffuse":
        nm = N.new("ShaderNodeNormalMap")
        L.new(nrm.outputs["Color"], nm.inputs["Color"])
        L.new(nm.outputs["Normal"], bs.inputs["Normal"])
    if mode == "grey":
        bs.inputs["Base Color"].default_value = (0.42, 0.42, 0.42, 1)
        bs.inputs["Roughness"].default_value = 0.7
        mix_alpha(N, L, bs, out, dif)
        return m
    if mode == "diffuse":
        em = N.new("ShaderNodeEmission")
        L.new(dif.outputs["Color"], em.inputs["Color"])
        mix_alpha(N, L, em, out, dif)
        return m
    col = dif.outputs["Color"]
    occ = tex("occlusion", "Non-Color")
    if occ is not None:
        mul = N.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs[0].default_value = 0.75
        L.new(col, mul.inputs[6])
        L.new(occ.outputs["Color"], mul.inputs[7])
        col = mul.outputs[2]
    L.new(col, bs.inputs["Base Color"])
    sg = tex("specgloss", "Non-Color")
    if sg is not None:
        inv = N.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        L.new(sg.outputs["Alpha"], inv.inputs[1])
        L.new(inv.outputs[0], bs.inputs["Roughness"])
        L.new(sg.outputs["Color"], bs.inputs["Specular Tint"])
    em = tex("emission", "sRGB")
    if em is not None:
        L.new(em.outputs["Color"], bs.inputs["Emission Color"])
        bs.inputs["Emission Strength"].default_value = 1.0
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
    size = int(opt("--size", "1000"))
    sc.render.resolution_x, sc.render.resolution_y = size, int(size * 1.0)
    sc.view_settings.view_transform = "Standard"
    mode = opt("--mode", "grey")
    tag = opt("--tag", "v6.0")
    ob = model()
    ob.data.materials.append(material(mode, tag))
    bpy.ops.mesh.primitive_plane_add(size=1200, location=(0, 0, 0))
    fl = bpy.context.object
    fm = bpy.data.materials.new("floor")
    fm.use_nodes = True
    next(n for n in fm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.3, 0.27, 0.23, 1)
    fl.data.materials.append(fm)
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.55, 0.62, 0.75, 1) if mode != "night" else (0.05, 0.07, 0.12, 1)
    bg.inputs["Strength"].default_value = {"diffuse": 0.0, "night": 0.25}.get(mode, 0.4)
    sc.world = w
    sun_d = bpy.data.lights.new("sun", "SUN")
    sun_d.energy = 0.0 if mode in ("night", "diffuse") else 4.0
    sun_d.angle = math.radians(1.5)
    sun = bpy.data.objects.new("sun", sun_d)
    sc.collection.objects.link(sun)
    cam_d = bpy.data.cameras.new("cam")
    cam_d.clip_start, cam_d.clip_end = 1, 5000
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    out = opt("--out", "renders/v6/check")
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
