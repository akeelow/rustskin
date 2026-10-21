"""Sauna Stone Box: showcase renders for the Steam Workshop page (Blender, Cycles).

Usage (from the repo root):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/wood-storage-box/workshop_renders.py -- [shot ...] [--samples 128]

Writes skins/sauna/wood-storage-box/workshop/<shot>.png (1920x1080). Uses the final v1.3 maps (lid and the burnt
rim cut with alpha, Alpha Cutoff 0.50) on the game-like OBJ (renders/concepts/box_game.obj: the inner walls wear
the outer ones, as in the client). The OBJ is metres, Y up, +Z front; imported Z up, the front faces -Y and
the stove side (+x, the burnt rim) faces +X.
Shots: hero (day), night, top (looking in at dusk), rim (the burnt edge up close at dusk), row (three boxes
side by side at night), set (next to the Sauna Stove, burnt rim towards it, dusk).
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
OBJ = HERE / "renders" / "concepts" / "box_game.obj"
PREFIX = HERE / "export" / "Box_v1.3"
STOVE_OBJ = HERE.parent / "electric-furnace" / "originals" / "electric.furnace.obj"
STOVE_PREFIX = HERE.parent / "electric-furnace" / "export" / "ElectricFurnace_v2"
OUT = HERE / "workshop"
EMISSION = 3.0                       # like viewer.py

# camera: (look-at point m, direction from target to eye, distance, lens mm, light preset)
SHOTS = {
    "hero": ((0.0, 0.0, 0.22), (0.75, -1.0, 1.0), 2.05, 40, "day"),
    "night": ((0.0, 0.0, 0.22), (0.75, -1.0, 1.0), 2.05, 40, "night"),
    "top": ((0.0, 0.0, 0.1), (0.25, -0.45, 1.0), 1.55, 40, "dusk"),
    "rim": ((0.3, -0.15, 0.48), (0.55, -1.0, 0.45), 0.85, 50, "dusk"),
    "row": ((0.0, 0.0, 0.25), (0.35, -1.0, 0.9), 3.6, 40, "night"),
    "set": ((0.55, 0.0, 0.45), (0.45, -1.0, 0.55), 3.9, 40, "dusk"),
}


def material(prefix, cutoff, gloss_kind="specgloss"):
    mat = bpy.data.materials.new(prefix.name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")

    def tex(name, colorspace):
        p = Path(f"{prefix}_{name}.png")
        if not p.exists():
            return None
        n = nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(str(p))
        n.image.colorspace_settings.name = colorspace
        return n

    d = tex("diffuse_cutout", "sRGB") or tex("diffuse", "sRGB")
    links.new(d.outputs["Color"], bsdf.inputs["Base Color"])
    if cutoff > 0:
        clip = nodes.new("ShaderNodeMath")
        clip.operation = "GREATER_THAN"
        clip.inputs[1].default_value = cutoff
        links.new(d.outputs["Alpha"], clip.inputs[0])
        links.new(clip.outputs[0], bsdf.inputs["Alpha"])
    sg = tex(gloss_kind, "Non-Color")
    sep = nodes.new("ShaderNodeSeparateColor")
    links.new(sg.outputs["Color"], sep.inputs["Color"])
    links.new(sep.outputs["Red"], bsdf.inputs["Metallic" if gloss_kind == "metalgloss" else "Specular IOR Level"])
    inv = nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    links.new(sg.outputs["Alpha"], inv.inputs[1])
    links.new(inv.outputs[0], bsdf.inputs["Roughness"])
    n = tex("normal", "Non-Color")
    nm = nodes.new("ShaderNodeNormalMap")
    links.new(n.outputs["Color"], nm.inputs["Color"])
    links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    e = tex("emission", "sRGB")
    if e:
        links.new(e.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = EMISSION
    return mat


def floor():
    """Weathered plank floor (stand-in for the in-game foundation)."""
    bpy.ops.mesh.primitive_plane_add(size=1)
    fl = bpy.context.active_object
    fl.scale = (10.0, 10.0, 1)
    m = bpy.data.materials.new("floor")
    m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (14.0, 1.0, 1.0)     # planks ~14 cm wide
    nt.links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "X"
    wave.inputs["Scale"].default_value = 1.0
    wave.inputs["Distortion"].default_value = 0.0
    nt.links.new(mapping.outputs["Vector"], wave.inputs["Vector"])
    grain = nt.nodes.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = 30.0
    grain.inputs["Detail"].default_value = 8.0
    nt.links.new(coord.outputs["Object"], grain.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.1, 0.075, 0.05, 1)
    ramp.color_ramp.elements[1].color = (0.45, 0.36, 0.25, 1)
    mix = nt.nodes.new("ShaderNodeMath")
    mix.operation = "MULTIPLY"
    nt.links.new(grain.outputs["Fac"], mix.inputs[0])
    gap = nt.nodes.new("ShaderNodeMath")
    gap.operation = "GREATER_THAN"
    gap.inputs[1].default_value = 0.03
    nt.links.new(wave.outputs["Fac"], gap.inputs[0])
    nt.links.new(gap.outputs[0], mix.inputs[1])
    nt.links.new(mix.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.85
    fl.data.materials.append(m)


def lights(scene, preset):
    world = bpy.data.worlds.new("w")
    scene.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    if preset == "day":
        bg.inputs["Color"].default_value = (0.62, 0.7, 0.85, 1)
        bg.inputs["Strength"].default_value = 0.7
        sun_rot, sun_energy, sun_color = (math.radians(45), math.radians(8), math.radians(35)), 4.0, (1.0, 0.95, 0.85)
    elif preset == "dusk":                       # low blue sky, a last warm sun from the side
        bg.inputs["Color"].default_value = (0.25, 0.28, 0.4, 1)
        bg.inputs["Strength"].default_value = 0.8
        sun_rot, sun_energy, sun_color = (math.radians(74), 0, math.radians(-120)), 1.6, (1.0, 0.7, 0.5)
    else:                                        # night: dark blue sky, a weak moon
        bg.inputs["Color"].default_value = (0.07, 0.09, 0.16, 1)
        bg.inputs["Strength"].default_value = 1.0
        sun_rot, sun_energy, sun_color = (math.radians(55), 0, math.radians(150)), 0.45, (0.65, 0.75, 1.0)
    bpy.ops.object.light_add(type="SUN", rotation=sun_rot)
    sun = bpy.context.active_object.data
    sun.energy = sun_energy
    sun.color = sun_color
    sun.angle = math.radians(2)


def camera(scene, target, direction, dist, lens):
    t = Vector(target)
    eye = t + Vector(direction).normalized() * dist
    bpy.ops.object.camera_add(location=eye)
    cam = bpy.context.active_object
    cam.rotation_euler = (t - eye).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = dist
    cam.data.dof.aperture_fstop = 5.6
    scene.camera = cam


def add_box(mat, x=0.0):
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="NEGATIVE_Z", up_axis="Y")
    ob = bpy.context.selected_objects[0]
    ob.location.x = x
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    return ob


def render(name, samples):
    target, direction, dist, lens, preset = SHOTS[name]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    mat = material(PREFIX, 0.5)
    if name == "row":                            # long sides touching, the way they stand in a base
        for k in (-1, 0, 1):
            add_box(mat, k * 0.715)
    else:
        add_box(mat)
    if name == "set":                            # the Sauna Stove on the box's burnt (+x) side
        bpy.ops.wm.obj_import(filepath=str(STOVE_OBJ), forward_axis="NEGATIVE_Z", up_axis="Y")
        stove = bpy.context.selected_objects[0]
        stove.location = (1.05, 0.15, 0.0)
        stove.data.materials.clear()
        stove.data.materials.append(material(STOVE_PREFIX, 0.99, "metalgloss"))   # in game Alpha Cutoff 1.00
    floor()
    lights(scene, preset)
    camera(scene, target, direction, dist, lens)
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = kind
        except TypeError:
            continue
        prefs.get_devices()
        if any(d.type == kind for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type == kind
            scene.cycles.device = "GPU"
            break
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
    OUT.mkdir(exist_ok=True)
    scene.render.filepath = str(OUT / f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print("rendered", name, flush=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    samples = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else 128
    names = [a for a in argv if a in SHOTS] or list(SHOTS)
    for name in names:
        render(name, samples)


if __name__ == "__main__":
    main()
