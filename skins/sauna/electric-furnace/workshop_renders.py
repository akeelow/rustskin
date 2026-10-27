"""Sauna Stove: showcase renders for the Steam Workshop page (Blender, Cycles).

Usage (from the repo root):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/electric-furnace/workshop_renders.py -- [shot ...] [--samples 128]

Writes skins/sauna/electric-furnace/workshop/<shot>.png (1920x1080, collection.png 1024x1024).
Uses the v2.8 export maps with the coil cutout (Alpha Cutoff 0.5) and, like the game, a warm light
inside the lit firebox. Shots: studio (first on the page), hero, night, burners, firebox, back.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
OBJ = HERE / "originals" / "electric.furnace.obj"
PREFIX = HERE / "export" / "ElectricFurnace_v2.8"
OUT = HERE / "workshop"

# camera: (look-at point, direction from target to eye, distance, lens mm, light preset, resolution)
SHOTS = {
    # first image of the page: dark studio, warm key, cool rim, the firebox alight (like the accepted stoves)
    "studio": ((0, 0, 0.55), (0.55, -1.0, 0.34), 3.6, 45, "studio", (1920, 1080)),
    "hero": ((0, 0, 0.58), (0.62, -1.0, 0.5), 3.1, 40, "day", (1920, 1080)),
    "night": ((0, 0, 0.58), (0.45, -1.0, 0.32), 3.0, 40, "night", (1920, 1080)),
    "burners": ((0.0, -0.05, 1.1), (0.35, -0.75, 1.0), 1.75, 50, "day", (1920, 1080)),
    "firebox": ((0.0, -0.3, 0.7), (0.22, -1.0, 0.1), 1.5, 50, "dusk", (1920, 1080)),
    "back": ((0, 0, 0.58), (-0.7, 1.0, 0.45), 3.1, 40, "day", (1920, 1080)),
}


def material(cutout=True):
    mat = bpy.data.materials.new("skin")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")

    def tex(name, colorspace):
        n = nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(str(Path(f"{PREFIX}_{name}.png")))
        n.image.colorspace_settings.name = colorspace
        return n

    d = tex("diffuse_cutout" if cutout else "diffuse", "sRGB")
    links.new(d.outputs["Color"], bsdf.inputs["Base Color"])
    clip = nodes.new("ShaderNodeMath")
    clip.operation = "GREATER_THAN"
    clip.inputs[1].default_value = 0.5
    links.new(d.outputs["Alpha"], clip.inputs[0])
    links.new(clip.outputs[0], bsdf.inputs["Alpha"])
    mg = tex("metalgloss", "Non-Color")
    sep = nodes.new("ShaderNodeSeparateColor")
    links.new(mg.outputs["Color"], sep.inputs["Color"])
    links.new(sep.outputs["Red"], bsdf.inputs["Metallic"])
    inv = nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    links.new(mg.outputs["Alpha"], inv.inputs[1])
    links.new(inv.outputs[0], bsdf.inputs["Roughness"])
    n = tex("normal", "Non-Color")
    nm = nodes.new("ShaderNodeNormalMap")
    links.new(n.outputs["Color"], nm.inputs["Color"])
    links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    e = tex("emission", "sRGB")
    links.new(e.outputs["Color"], bsdf.inputs["Emission Color"])
    return mat, bsdf


def deck(scene, size=4.2):
    """Weathered plank deck under the stove (stand-in for the in-game foundation)."""
    bpy.ops.mesh.primitive_plane_add(size=1)
    deck = bpy.context.active_object
    deck.scale = (size, size, 1)
    m = bpy.data.materials.new("deck")
    m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1.0, 7.0, 1.0)      # planks ~14 cm wide along x
    nt.links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "Y"
    wave.inputs["Scale"].default_value = 1.0
    wave.inputs["Distortion"].default_value = 0.0
    nt.links.new(mapping.outputs["Vector"], wave.inputs["Vector"])
    grain = nt.nodes.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = 40.0
    grain.inputs["Detail"].default_value = 8.0
    nt.links.new(coord.outputs["Object"], grain.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.09, 0.06, 0.04, 1)
    ramp.color_ramp.elements[1].color = (0.42, 0.31, 0.2, 1)
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
    deck.data.materials.append(m)


def lights(scene, preset):
    world = bpy.data.worlds.new("w")
    scene.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    sun_rot = (math.radians(52), math.radians(8), math.radians(-38))
    if preset == "day":
        bg.inputs["Color"].default_value = (0.62, 0.7, 0.85, 1)
        bg.inputs["Strength"].default_value = 0.7
        sun_energy, sun_color, fire = 4.0, (1.0, 0.95, 0.85), 25.0
    elif preset == "dusk":
        bg.inputs["Color"].default_value = (0.35, 0.36, 0.48, 1)
        bg.inputs["Strength"].default_value = 0.35
        sun_energy, sun_color, fire = 1.2, (1.0, 0.7, 0.45), 40.0
        sun_rot = (math.radians(78), 0, math.radians(-60))
    elif preset == "studio":
        bg.inputs["Color"].default_value = (0.012, 0.01, 0.01, 1)
        bg.inputs["Strength"].default_value = 1.0
        sun_energy, sun_color, fire = 0.0, (1, 1, 1), 55.0
        for loc, rot, power, col, size in (
                ((-1.6, -1.8, 2.2), (math.radians(55), 0, math.radians(-40)), 120, (1.0, 0.82, 0.62), 1.2),  # warm key
                ((1.4, 1.5, 1.8), (math.radians(-60), 0, math.radians(140)), 380, (0.62, 0.74, 1.0), 0.6)):  # cool rim
            bpy.ops.object.light_add(type="AREA", location=loc)
            ar = bpy.context.active_object
            ar.data.energy, ar.data.color, ar.data.size = power, col, size
            ar.rotation_euler = (Vector((0, 0, 0.6)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    else:  # night
        bg.inputs["Color"].default_value = (0.03, 0.04, 0.07, 1)
        bg.inputs["Strength"].default_value = 1.0
        sun_energy, sun_color, fire = 0.5, (0.55, 0.65, 1.0), 45.0
        sun_rot = (math.radians(55), 0, math.radians(-25))   # moonlight from the front-left
    bpy.ops.object.light_add(type="SUN", rotation=sun_rot)
    sun = bpy.context.active_object.data
    sun.energy = sun_energy
    sun.color = sun_color
    sun.angle = math.radians(2)
    # the lit furnace glows inside, as in game: a warm light in the firebox and one under the plate
    for loc, power, size in (((0, 0.0, 0.62), fire, 0.25), ((0.27, 0.0, 0.75), fire * 0.35, 0.15)):
        bpy.ops.object.light_add(type="POINT", location=loc)
        lt = bpy.context.active_object.data
        lt.energy = power
        lt.color = (1.0, 0.42, 0.12)
        lt.shadow_soft_size = size
    return {"day": 3.0, "dusk": 5.0, "night": 6.0, "studio": 6.0}[preset]


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


def glare(scene):
    """Soft bloom on the glow, if this Blender's compositor API allows it (5.x node groups)."""
    try:
        tree = bpy.data.node_groups.new("comp", "CompositorNodeTree")
        scene.compositing_node_group = tree
        rl = tree.nodes.new("CompositorNodeRLayers")
        gl = tree.nodes.new("CompositorNodeGlare")
        out = tree.nodes.new("NodeGroupOutput")
        tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        for attr, val in (("glare_type", "FOG_GLOW"), ("quality", "HIGH")):
            if hasattr(gl, attr):
                setattr(gl, attr, val)
        for name, val in (("Threshold", 1.0), ("Size", 0.5), ("Strength", 0.6)):
            if name in gl.inputs:
                gl.inputs[name].default_value = val
        tree.links.new(rl.outputs["Image"], gl.inputs["Image"])
        tree.links.new(gl.outputs["Image"], out.inputs[0])
    except Exception as e:  # older/newer API: render without bloom
        print("no glare:", e)


def render(name, samples):
    target, direction, dist, lens, preset, res = SHOTS[name]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="NEGATIVE_Z", up_axis="Y")
    obj = bpy.context.selected_objects[0]
    mat, bsdf = material()
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    deck(scene, 1.5 if preset == "studio" else 4.2)       # studio: a small platform fading into the dark
    bsdf.inputs["Emission Strength"].default_value = lights(scene, preset)
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
    scene.render.resolution_x, scene.render.resolution_y = res
    glare(scene)
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
