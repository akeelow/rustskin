"""Проверочные рендеры Sauna Mitts (Blender без окна). Это рендеры, не кадры из игры.

blender -b -P skins/sauna/tactical-gloves/gloves_view.py -- [--ver v1] [--set fp,sheet,night,close,dn,robe,atlas,orig]
Выход: renders/<ver>_*.png и сцена renders/<ver>_view.blend

  fp     «от первого лица»: обе руки тыльной стороной к камере, как при удержании оружия (поза приблизительная:
         модель в позе T, руки повёрнуты целиком, пальцы не согнуты — анимации игры не повторить)
  sheet  лист: тыл, ладонь, бок большого пальца, бок мизинца, манжета, застёжка — день
  night  ночь у печи: тёплый свет снизу сбоку, холодный слабый сверху
  close  крупно под скользящим светом: швы, береста, подушечки, ладонь, подпалины, манжета
  dn     только Diffuse (свет плоский) против только Normal (серый материал) — проверка «всё рельефное — геометрией»
  robe   рядом с рукавом Sauna Robe (Snow Jacket v2.5) в одном свете
  atlas  атлас номеров островов на модели (аудит поверхностей)
  orig   оригинал Facepunch в тех же ракурсах (для сравнения)
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
VER = ARGS[ARGS.index("--ver") + 1] if "--ver" in ARGS else "v1"
SETS = (ARGS[ARGS.index("--set") + 1] if "--set" in ARGS else "fp,sheet,night,close,dn,robe,atlas").split(",")
EX = HERE / "export"
REN = HERE / "renders"
OBJ = HERE / "originals" / "tactical.gloves.obj"


def maps(ver):
    if ver == "orig":
        o = HERE / "originals"
        return dict(diffuse=o / "TacticalGloves_bc.png", normal=o / "TacticalGloves_nrm.png",
                    specgloss=o / "TacticalGloves_sg.png", occlusion=o / "TacticalGloves_AO.png",
                    fuzz=o / "TacticalGloves_Fuzz.png")
    return {k: EX / f"SaunaMitts_{ver}_{k}.png" for k in ("diffuse", "normal", "specgloss", "occlusion", "fuzz")}


def img(path, data):
    im = bpy.data.images.load(str(path), check_existing=True)
    im.colorspace_settings.name = "Non-Color" if data else "sRGB"
    return im


def unity_material(name, M, mode="full", fuzz_amt=0.27):
    """Unity Specular (Rust) приблизительно в Principled: Diffuse × Occlusion, блик из Spec/Gloss, ворс — Sheen."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    b = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL")

    def tex(key, data):
        t = N.new("ShaderNodeTexImage")
        t.image = img(M[key], data)
        return t
    if mode in ("full", "diffuse"):
        d = tex("diffuse", False)
        ao = tex("occlusion", True)
        mul = N.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs["Factor"].default_value = 1.0
        L.new(d.outputs["Color"], mul.inputs[6])
        L.new(ao.outputs["Color"], mul.inputs[7])
        if mode == "diffuse":
            em = N.new("ShaderNodeEmission")
            L.new(mul.outputs[2], em.inputs["Color"])
            L.new(em.outputs[0], out.inputs["Surface"])
            return m
        L.new(mul.outputs[2], b.inputs["Base Color"])
    else:
        b.inputs["Base Color"].default_value = (0.42, 0.42, 0.42, 1)
    if mode in ("full", "normal"):
        nt = tex("normal", True)
        nm = N.new("ShaderNodeNormalMap")
        L.new(nt.outputs["Color"], nm.inputs["Color"])
        L.new(nm.outputs["Normal"], b.inputs["Normal"])
    if mode == "full":
        sg = tex("specgloss", True)
        sep = N.new("ShaderNodeSeparateColor")
        L.new(sg.outputs["Color"], sep.inputs["Color"])
        lvl = N.new("ShaderNodeMath")
        lvl.operation = "MULTIPLY"
        lvl.inputs[1].default_value = 1 / 0.08
        L.new(sep.outputs[0], lvl.inputs[0])
        L.new(lvl.outputs[0], b.inputs["Specular IOR Level"])
        rough = N.new("ShaderNodeMath")
        rough.operation = "SUBTRACT"
        rough.inputs[0].default_value = 1.0
        L.new(sg.outputs["Alpha"], rough.inputs[1])
        L.new(rough.outputs[0], b.inputs["Roughness"])
        fz = tex("fuzz", True)
        sc = N.new("ShaderNodeMath")
        sc.operation = "MULTIPLY"
        sc.inputs[1].default_value = fuzz_amt * 1.6
        L.new(fz.outputs["Color"], sc.inputs[0])
        L.new(sc.outputs[0], b.inputs["Sheen Weight"])
        b.inputs["Sheen Tint"].default_value = (1.0, 0.92, 0.74, 1)
        b.inputs["Sheen Roughness"].default_value = 0.5
    else:
        b.inputs["Roughness"].default_value = 0.55
    return m


def atlas_material():
    m = bpy.data.materials.new("atlas")
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    b = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    t = N.new("ShaderNodeTexImage")
    t.image = img(HERE / "uv" / "islands_atlas.png", False)
    L.new(t.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.8
    return m


def import_glove():
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="Y", up_axis="Z")
    ob = bpy.context.selected_objects[0]
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def setup_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 96
    sc.cycles.use_denoising = True
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type == "OPTIX"
        sc.cycles.device = "GPU"
    except TypeError:
        pass
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Base Contrast"
    sc.render.resolution_x, sc.render.resolution_y = 1200, 1200
    w = bpy.data.worlds.new("w")
    sc.world = w
    w.use_nodes = True
    return sc


def world(color, strength):
    bg = bpy.context.scene.world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (*color, 1)
    bg.inputs[1].default_value = strength


def light(name, kind, loc, rot, energy, color=(1, 1, 1), size=0.3):
    L = bpy.data.lights.new(name, kind)
    L.energy = energy
    L.color = color
    if kind == "AREA":
        L.size = size
    if kind == "SUN":
        L.angle = math.radians(1.5)
    o = bpy.data.objects.new(name, L)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = rot
    return o


def clear_lights():
    for o in list(bpy.data.objects):
        if o.type == "LIGHT":
            bpy.data.objects.remove(o)


def camera(loc, target, lens=50, ortho=None):
    sc = bpy.context.scene
    cam = sc.camera
    if cam is None:
        cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
        sc.collection.objects.link(cam)
        sc.camera = cam
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam.data.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        cam.data.ortho_scale = ortho
    cam.data.lens = lens
    cam.data.clip_start = 0.005
    return cam


def shoot(name):
    sc = bpy.context.scene
    sc.render.filepath = str(REN / f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print("render", name, flush=True)


def keep_right(ob):
    """Только правая перчатка (+x) — для листа и крупных планов."""
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    for p in ob.data.polygons:
        p.select = p.center.x < 0
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.delete(type="FACE")
    bpy.ops.object.mode_set(mode="OBJECT")


def fp_pose(ob_r, ob_l):
    """Руки «как держат оружие»: пальцы вперёд (+Y), тыл кисти вверх-наружу, кисти на ширине плеч.
    В OBJ правая кисть: пальцы −y, тыл +x, запястье у (0.44, 0.39, 0.04)."""
    wrist = Vector((0.445, 0.39, 0.045))
    # базис кисти в OBJ: вперёд (к пальцам) = −y, вверх (тыл) = +x, вбок = z
    f = Vector((0, -1, 0))
    u = Vector((1, 0, 0))
    s = f.cross(u)
    B = Matrix((s, f, u)).transposed()          # столбцы: s, f, u
    R = B.inverted()                            # OBJ → мир: f → +Y, u → +Z
    tilt = Matrix.Rotation(math.radians(-28), 4, "Y")   # тыл чуть наружу (правая)
    pitch = Matrix.Rotation(math.radians(12), 4, "X")   # кончики чуть вниз
    M = Matrix.Translation((0.13, 0.0, -0.10)) @ pitch @ tilt @ R.to_4x4() @ Matrix.Translation(-wrist)
    ob_r.matrix_world = M
    mirror = Matrix.Scale(-1, 4, (1, 0, 0))
    ob_l.matrix_world = mirror @ M
    # зеркало выворачивает нормали — у Cycles это видно только на задних гранях; оставляем как в игре


def main():
    sc = setup_scene()
    REN.mkdir(exist_ok=True)
    M = maps(VER if "orig" not in SETS else "orig")
    tag = VER
    if "orig" in SETS:
        tag = "orig"
        SETS.extend(["fp", "sheet"])
    mat = unity_material("mitts", M)

    if "fp" in SETS:
        r = import_glove()
        keep_right(r)
        l = r.copy()
        l.data = r.data
        sc.collection.objects.link(l)
        for o in (r, l):
            o.data.materials.clear()
            o.data.materials.append(mat)
        fp_pose(r, l)
        world((0.55, 0.6, 0.66), 0.55)
        light("sun", "SUN", (0, 0, 2), (math.radians(35), math.radians(-20), math.radians(30)), 3.2, (1.0, 0.96, 0.9))
        camera((0, -0.22, 0.02), (0, 0.07, -0.11), lens=22)
        shoot(f"{tag}_fp_day")
        clear_lights()
        world((0.05, 0.06, 0.08), 0.25)
        light("stove", "AREA", (0.35, 0.10, -0.35), (math.radians(-120), 0, math.radians(60)), 90, (1.0, 0.55, 0.25), 0.4)
        light("door", "AREA", (-0.4, -0.2, 0.5), (math.radians(40), math.radians(-35), 0), 25, (0.75, 0.85, 1.0), 0.6)
        shoot(f"{tag}_fp_night")
        clear_lights()
        # иконки и ч/б — из дневного кадра делает checks_img.py
        for o in (r, l):
            bpy.data.objects.remove(o)

    if any(k in SETS for k in ("sheet", "night", "close", "dn", "atlas", "robe")):
        g = import_glove()
        keep_right(g)
        g.data.materials.clear()
        g.data.materials.append(mat)
        c = Vector((0.472, 0.30, 0.068))
        views = {"back": (1, 0, 0.05), "palm": (-1, 0, 0.05), "thumb": (0.25, 0.1, -1), "little": (0.2, 0.1, 1),
                 "cuff": (0.5, 0.75, 0.35), "fingertips": (0.45, -1, 0.2)}
        if "sheet" in SETS:
            world((0.55, 0.6, 0.66), 0.6)
            light("sun", "SUN", (0, 0, 2), (math.radians(40), math.radians(15), math.radians(35)), 3.0, (1.0, 0.96, 0.9))
            for k, d in views.items():
                d = Vector(d).normalized()
                camera(c + d * 0.6, c, ortho=0.23)
                shoot(f"{tag}_view_{k}")
            clear_lights()
        if "night" in SETS:
            world((0.04, 0.05, 0.07), 0.2)
            light("stove", "AREA", (0.75, 0.05, 0.25), (0, math.radians(80), 0), 60, (1.0, 0.5, 0.22), 0.3)
            for k in ("back", "palm"):
                d = Vector(views[k]).normalized()
                camera(c + d * 0.6, c, ortho=0.23)
                shoot(f"{tag}_night_{k}")
            clear_lights()
        if "close" in SETS:
            world((0.3, 0.32, 0.35), 0.25)
            closes = {"seams": ((0.49, 0.235, 0.075), (1, -0.3, 0.6), 0.045),
                      "bark": ((0.495, 0.33, 0.07), (1, 0.1, 0.05), 0.06),
                      "pads": ((0.462, 0.23, 0.07), (-1, -0.35, 0.1), 0.05),
                      "palm": ((0.455, 0.31, 0.07), (-1, 0.05, 0.05), 0.07),
                      "burns": ((0.49, 0.37, 0.08), (1, 0.4, 0.1), 0.05),
                      "cuff": ((0.445, 0.39, 0.075), (0.3, 0.2, 1), 0.06),
                      "closure": ((0.43, 0.375, 0.012), (0.1, 0.05, -1), 0.04)}
            for k, (cc, d, sc_) in closes.items():
                cc, d = Vector(cc), Vector(d).normalized()
                camera(cc + d * 0.3, cc, ortho=sc_)
                # скользящий свет: почти вдоль поверхности
                rot = (cc - (cc + d * 0.3)).to_track_quat("-Z", "Y").to_euler()
                light("graze", "SUN", (0, 0, 1), (rot.x + math.radians(70), rot.y, rot.z + math.radians(25)), 4.0)
                shoot(f"{tag}_close_{k}")
                clear_lights()
        if "dn" in SETS:
            world((0.5, 0.5, 0.5), 1.0)
            for mode in ("diffuse", "normal"):
                g.data.materials.clear()
                g.data.materials.append(unity_material(f"m_{mode}", M, mode))
                if mode == "normal":
                    world((0.2, 0.2, 0.22), 0.3)
                    light("graze", "SUN", (0, 0, 1), (math.radians(60), math.radians(40), math.radians(20)), 4.0)
                for k in ("back", "palm"):
                    d = Vector(views[k]).normalized()
                    camera(c + d * 0.6, c, ortho=0.23)
                    shoot(f"{tag}_dn_{mode}_{k}")
                clear_lights()
            g.data.materials.clear()
            g.data.materials.append(mat)
        if "atlas" in SETS:
            g.data.materials.clear()
            g.data.materials.append(atlas_material())
            world((0.6, 0.6, 0.62), 0.9)
            light("sun", "SUN", (0, 0, 2), (math.radians(40), math.radians(15), math.radians(35)), 2.0)
            for k, d in views.items():
                d = Vector(d).normalized()
                camera(c + d * 0.6, c, ortho=0.23)
                shoot(f"{tag}_atlas_{k}")
            clear_lights()
            g.data.materials.clear()
            g.data.materials.append(mat)
        if "robe" in SETS:
            sj = ROOT / "skins" / "sauna" / "snow-jacket"
            bpy.ops.wm.obj_import(filepath=str(sj / "originals" / "jacket.snow.obj"), forward_axis="NEGATIVE_Z", up_axis="Y")
            j = bpy.context.selected_objects[0]
            for p in j.data.polygons:
                p.use_smooth = True
            jm = {k: sj / "export" / f"SnowJacket_v2.5_{k}.png" for k in ("diffuse", "normal", "specgloss")}
            jm["occlusion"] = HERE / "uv" / "white.png"
            jm["fuzz"] = sj / "export" / "SnowJacket_v2.5_fuzz.png"
            j.data.materials.clear()
            j.data.materials.append(unity_material("robe", jm, fuzz_amt=0.5))
            # куртка в осях Blender: OBJ (x, y, z) → (x, −z, y); перчатка импортирована как есть (x, y, z),
            # поэтому куртку переводим в оси перчатки: мир перчатки = OBJ
            j.matrix_world = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))
            # модели в разных координатах тела: ставим конец правого рукава на манжету перчатки по оси запястья
            W = [j.matrix_world @ v.co for v in j.data.vertices]
            xm = max(p.x for p in W)
            end = [p for p in W if p.x > xm - 0.015]
            mid = [p for p in W if xm - 0.12 < p.x < xm - 0.10]
            ce = sum(end, Vector()) / len(end)
            cm = sum(mid, Vector()) / len(mid)
            d_s = (ce - cm).normalized()
            cuff_c = Vector((0.4412, 0.389, 0.0389))
            ax = Vector((-0.322, 0.9, -0.292)).normalized()      # ось запястья, + к локтю (bake_gloves.CuffFrame)
            Rq = d_s.rotation_difference(-ax).to_matrix().to_4x4()
            j.matrix_world = Matrix.Translation(cuff_c + ax * 0.012) @ Rq @ Matrix.Translation(-ce) @ j.matrix_world
            world((0.55, 0.6, 0.66), 0.6)
            light("sun", "SUN", (0, 0, 2), (math.radians(40), math.radians(15), math.radians(35)), 3.0, (1.0, 0.96, 0.9))
            cc = Vector((0.43, 0.37, 0.05))
            for k, d in (("robe_back", (1, 0.6, 0.35)), ("robe_top", (0.4, 1, 0.5))):
                d = Vector(d).normalized()
                camera(cc + d * 0.6, cc, ortho=0.26)
                shoot(f"{tag}_{k}")
            clear_lights()
    bpy.ops.wm.save_as_mainfile(filepath=str(REN / f"{tag}_view.blend"), compress=True)


main()
