"""Sauna Chair: showcase renders for the Steam Workshop page (Blender, Cycles).

Usage (from the repo root):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/chair/workshop_renders.py -- [shot ...] [--samples 128]

Writes skins/sauna/chair/workshop/<shot>.png (1920x1080). Uses the final v1.4 maps (no alpha).
The OBJ is metres, Y up, +Z front; imported Z up, the chair's front then faces -Y.
Shots: hero, towel, seat, back, dusk (warm light from the stove side), set (next to the Sauna Bench).
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
OBJ = HERE / "originals" / "chair.obj"
PREFIX = HERE / "export" / "Chair_v1.4"
BED_OBJ = HERE.parent / "bed" / "originals" / "bed.obj"
BED_PREFIX = HERE.parent / "bed" / "export" / "Bed_v1.2"
OUT = HERE / "workshop"

# camera: (look-at point m, direction from target to eye, distance, lens mm, light preset)
SHOTS = {
    "hero": ((0.0, 0.0, 0.6), (0.75, -1.0, 0.5), 3.1, 40, "day"),
    "towel": ((-0.03, 0.29, 0.92), (0.35, -1.0, 0.25), 0.95, 50, "day"),
    "seat": ((-0.02, -0.08, 0.5), (0.2, -0.75, 1.0), 1.05, 45, "day"),
    "back": ((0.0, 0.1, 0.65), (-0.55, 1.0, 0.35), 2.4, 40, "day"),
    "dusk": ((0.0, 0.0, 0.6), (-0.7, -1.0, 0.45), 3.1, 40, "dusk"),
    "set": ((-1.05, 0.3, 0.45), (0.35, -1.0, 0.55), 5.4, 40, "day"),
}


def material(prefix, cutoff):
    mat = bpy.data.materials.new(prefix.name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")

    def tex(name, colorspace):
        n = nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(str(Path(f"{prefix}_{name}.png")))
        n.image.colorspace_settings.name = colorspace
        return n

    d = tex("diffuse", "sRGB")
    links.new(d.outputs["Color"], bsdf.inputs["Base Color"])
    if cutoff > 0:
        clip = nodes.new("ShaderNodeMath")
        clip.operation = "GREATER_THAN"
        clip.inputs[1].default_value = cutoff
        links.new(d.outputs["Alpha"], clip.inputs[0])
        links.new(clip.outputs[0], bsdf.inputs["Alpha"])
    sg = tex("specgloss", "Non-Color")
    sep = nodes.new("ShaderNodeSeparateColor")
    links.new(sg.outputs["Color"], sep.inputs["Color"])
    links.new(sep.outputs["Red"], bsdf.inputs["Specular IOR Level"])
    inv = nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    links.new(sg.outputs["Alpha"], inv.inputs[1])
    links.new(inv.outputs[0], bsdf.inputs["Roughness"])
    n = tex("normal", "Non-Color")
    nm = nodes.new("ShaderNodeNormalMap")
    links.new(n.outputs["Color"], nm.inputs["Color"])
    links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def floor():
    """Weathered plank floor (stand-in for the in-game foundation)."""
    bpy.ops.mesh.primitive_plane_add(size=1)
    fl = bpy.context.active_object
    fl.scale = (8.0, 8.0, 1)
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
        sun_rot, sun_energy, sun_color = (math.radians(50), math.radians(8), math.radians(35)), 4.0, (1.0, 0.95, 0.85)
    else:  # dusk: low blue sky, warm light from the stove in the next room (front left)
        bg.inputs["Color"].default_value = (0.25, 0.28, 0.4, 1)
        bg.inputs["Strength"].default_value = 0.35
        sun_rot, sun_energy, sun_color = (math.radians(75), 0, math.radians(-120)), 0.8, (0.7, 0.75, 1.0)
        bpy.ops.object.light_add(type="POINT", location=(-1.6, -1.5, 0.8))
        stove = bpy.context.active_object.data
        stove.energy = 380.0
        stove.color = (1.0, 0.5, 0.2)
        stove.shadow_soft_size = 0.35
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


def render(name, samples):
    target, direction, dist, lens, preset = SHOTS[name]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="NEGATIVE_Z", up_axis="Y")
    obj = bpy.context.selected_objects[0]
    obj.location.z = 0.018                         # the legs reach y -1.8 cm: stand them on the floor
    obj.data.materials.clear()
    obj.data.materials.append(material(PREFIX, 0.0))
    if name == "set":                              # the bench beside it, the chair at its foot end
        bpy.ops.wm.obj_import(filepath=str(BED_OBJ), forward_axis="Y", up_axis="Z")
        bed = bpy.context.selected_objects[0]
        bed.scale = (0.01, 0.01, 0.01)
        bed.location = (-1.9, 0.6, 0.038)
        bed.data.materials.clear()
        bed.data.materials.append(material(BED_PREFIX, 0.5))
        obj.rotation_euler.z = math.radians(25)
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
