"""Shared Blender (Cycles) helpers for the Sauna set's Workshop renders and the collection picture.

Imported by <item>/workshop_renders.py (towel wrap, robe, locker) and workshop_collection.py:
  import sys; sys.path.insert(0, str(Path(__file__).resolve().parents[1])); import showcase

ITEMS lists every finished skin: its OBJ (axes, units, where it stands) and its final maps, wired like
the Rust editor slots (Diffuse + Alpha Cutoff, Normal, Specular/Gloss or Metal/Gloss, Occlusion,
Emission x3 like tools/blender/viewer.py). Clothing has no body in these shots ("ghost mannequin"):
the inside of the garment is shown darker instead of being culled, and a wooden dress-form stand holds it.
"""
import math
from pathlib import Path

import bpy
from mathutils import Vector

SAUNA = Path(__file__).resolve().parent
EMISSION = 3.0

# name: obj, axes ("y" = Y up +Z front, "z" = Z up 3ds Max), unit scale, z lift (feet to the floor),
#       map prefix, Alpha Cutoff, gloss map kind, occlusion (path, scale) or None
ITEMS = {
    "stove": dict(obj=SAUNA / "electric-furnace/originals/electric.furnace.obj", up="y", scale=1.0, lift=0.0,
                  prefix=SAUNA / "electric-furnace/export/ElectricFurnace_v2", cutoff=0.99, gloss="metalgloss"),
    "bench": dict(obj=SAUNA / "bed/originals/bed.obj", up="z", scale=0.01, lift=0.038,
                  prefix=SAUNA / "bed/export/Bed_v1.2", cutoff=0.5, gloss="specgloss"),
    "chair": dict(obj=SAUNA / "chair/originals/chair.obj", up="y", scale=1.0, lift=0.018,
                  prefix=SAUNA / "chair/export/Chair_v1.4", cutoff=0.0, gloss="specgloss"),
    "box": dict(obj=SAUNA / "wood-storage-box/renders/concepts/box_game.obj", up="y", scale=1.0, lift=0.0,
                prefix=SAUNA / "wood-storage-box/export/Box_v1.3", cutoff=0.5, gloss="specgloss"),
    "locker": dict(obj=SAUNA / "locker/originals/locker.obj", up="y", scale=0.01, lift=0.0,
                   prefix=SAUNA / "locker/export/Locker_v5", cutoff=0.5, gloss="specgloss",
                   ao=(SAUNA / "locker/originals/locker_ao.png", 0.75)),
    "robe": dict(obj=SAUNA / "snow-jacket/originals/jacket.snow.obj", up="y", scale=1.0, lift=0.0,
                 prefix=SAUNA / "snow-jacket/export/SnowJacket_v2", cutoff=0.0, gloss="specgloss", cloth="ghost"),
    "wrap": dict(obj=SAUNA / "burlap-headwrap/originals/burlap.headwrap.obj", up="y", scale=1.0, lift=0.0,
                 prefix=SAUNA / "burlap-headwrap/export/BurlapHeadwrap_v1", cutoff=0.79, gloss=None, cloth="cull"),
    # (cull back faces like the game: the outer side shows, the inside only through the eye slit)
    # (the wrap's original occlusion is not multiplied in: the game shades only ambient light with it,
    #  baked into the colour it turns the light linen olive)
}


def material(item):
    it = ITEMS[item]
    mat = bpy.data.materials.new(item)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")

    def tex(path, colorspace):
        path = Path(path)
        if not path.exists():
            return None
        n = nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(str(path))
        n.image.colorspace_settings.name = colorspace
        return n

    prefix = it["prefix"]
    d = tex(f"{prefix}_diffuse_cutout.png", "sRGB") or tex(f"{prefix}_diffuse.png", "sRGB")
    colour = d.outputs["Color"]
    if it.get("ao"):
        ao_path, ao_scale = it["ao"]
        ao = tex(ao_path, "Non-Color")
        mix = nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = ao_scale
        links.new(colour, mix.inputs[6])
        links.new(ao.outputs["Color"], mix.inputs[7])
        colour = mix.outputs[2]
    if it.get("cloth") == "ghost":               # inside of the garment: same cloth, in shadow
        geo = nodes.new("ShaderNodeNewGeometry")
        inner = nodes.new("ShaderNodeMix")
        inner.data_type = "RGBA"
        inner.blend_type = "MULTIPLY"
        inner.inputs[7].default_value = (0.32, 0.29, 0.26, 1)
        links.new(geo.outputs["Backfacing"], inner.inputs["Factor"])
        links.new(colour, inner.inputs[6])
        colour = inner.outputs[2]
    links.new(colour, bsdf.inputs["Base Color"])
    alpha = None
    if it["cutoff"] > 0:
        clip = nodes.new("ShaderNodeMath")
        clip.operation = "GREATER_THAN"
        clip.inputs[1].default_value = it["cutoff"]
        links.new(d.outputs["Alpha"], clip.inputs[0])
        alpha = clip.outputs[0]
    if it.get("cloth") == "cull":                # back faces invisible, as in the game; Rust OBJs are wound
        geo = nodes.new("ShaderNodeNewGeometry")  # clockwise (Unity), so the game's front is Blender's back
        front = geo.outputs["Backfacing"]
        if alpha is not None:
            both = nodes.new("ShaderNodeMath")
            both.operation = "MULTIPLY"
            links.new(alpha, both.inputs[0])
            links.new(front, both.inputs[1])
            alpha = both.outputs[0]
        else:
            alpha = front
    if alpha is not None:
        links.new(alpha, bsdf.inputs["Alpha"])
    sg = tex(f"{prefix}_{it['gloss']}.png", "Non-Color") if it["gloss"] else None
    if sg:
        sep = nodes.new("ShaderNodeSeparateColor")
        links.new(sg.outputs["Color"], sep.inputs["Color"])
        links.new(sep.outputs["Red"], bsdf.inputs["Metallic" if it["gloss"] == "metalgloss" else "Specular IOR Level"])
        inv = nodes.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        links.new(sg.outputs["Alpha"], inv.inputs[1])
        links.new(inv.outputs[0], bsdf.inputs["Roughness"])
    else:                                        # empty Specular/Gloss slot: Spec Color 51, Glossiness 0.28
        bsdf.inputs["Specular IOR Level"].default_value = 0.2
        bsdf.inputs["Roughness"].default_value = 0.85
    n = tex(f"{prefix}_normal.png", "Non-Color")
    nm = nodes.new("ShaderNodeNormalMap")
    links.new(n.outputs["Color"], nm.inputs["Color"])
    links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    e = tex(f"{prefix}_emission.png", "sRGB")
    if e:
        links.new(e.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = EMISSION
    return mat


def add(item, location=(0, 0, 0), rot_z=0.0, mat=None):
    """Import an item standing on the floor at `location` (front faces -Y before rot_z, degrees)."""
    it = ITEMS[item]
    if it["up"] == "z":
        bpy.ops.wm.obj_import(filepath=str(it["obj"]), forward_axis="Y", up_axis="Z")
    else:
        bpy.ops.wm.obj_import(filepath=str(it["obj"]), forward_axis="NEGATIVE_Z", up_axis="Y")
    mat = mat or material(item)
    obs = list(bpy.context.selected_objects)
    for ob in obs:
        if it.get("cloth") == "ghost":
            orient_outwards(ob)
        ob.scale = (it["scale"],) * 3
        ob.location = Vector(location) + Vector((0, 0, it["lift"]))
        ob.rotation_euler.z = math.radians(rot_z)
        ob.data.materials.clear()
        ob.data.materials.append(mat)
    return obs


def orient_outwards(ob):
    """Some garment OBJs come with faces wound inwards: flip them so that 'Backfacing' means the inside."""
    me = ob.data
    centre = sum((v.co for v in me.vertices), Vector()) / len(me.vertices)
    score = sum(p.normal.dot(p.center - centre) * p.area for p in me.polygons)
    if score < 0:
        me.flip_normals()


def wood(name, dark=(0.1, 0.075, 0.05), light=(0.45, 0.36, 0.25), plank=14.0, axis="X"):
    """Weathered planks (floor or a lining wall), planks ~100/plank cm wide."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (plank, 1.0, 1.0) if axis == "X" else (1.0, plank, 1.0)
    nt.links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = axis
    wave.inputs["Scale"].default_value = 1.0
    wave.inputs["Distortion"].default_value = 0.0
    nt.links.new(mapping.outputs["Vector"], wave.inputs["Vector"])
    grain = nt.nodes.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = 30.0
    grain.inputs["Detail"].default_value = 8.0
    nt.links.new(coord.outputs["Object"], grain.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*dark, 1)
    ramp.color_ramp.elements[1].color = (*light, 1)
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
    return m


def floor(size=10.0):
    bpy.ops.mesh.primitive_plane_add(size=1)
    fl = bpy.context.active_object
    fl.scale = (size, size, 1)
    fl.data.materials.append(wood("floor"))
    return fl


def wall(y, width=8.0, height=3.0, x=0.0, side=False):
    """Vertical lining-board wall (boards ~10 cm) facing -Y at depth y: a changing-room backdrop.
    side=True: the wall stands across X instead (at x = y), for shots from the side."""
    loc = (y, x, height / 2) if side else (x, y, height / 2)
    rot = (math.radians(90), 0, math.radians(90) if side else 0)
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=rot)
    w = bpy.context.active_object
    w.scale = (width, height, 1)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    w.data.materials.append(wood("wall", dark=(0.05, 0.032, 0.02), light=(0.2, 0.13, 0.075), plank=1.6))
    return w


def dress_form(top, neck_r=0.055, neck_h=0.12, bottom=0.0, base_r=0.22):
    """Wooden tailor's stand: round base, a pole up to the garment, a neck stub above `top` (m)."""
    m = bpy.data.materials.new("form")
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (0.09, 0.055, 0.032, 1)
    b.inputs["Roughness"].default_value = 0.55
    parts = []
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=base_r, depth=0.03, location=(0, 0, bottom + 0.015))
    parts.append(bpy.context.active_object)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.018, depth=top - bottom, location=(0, 0, (top + bottom) / 2))
    parts.append(bpy.context.active_object)
    if neck_h > 0:
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=neck_r, depth=neck_h, location=(0, 0, top + neck_h / 2))
        parts.append(bpy.context.active_object)
    for p in parts:
        bpy.ops.object.select_all(action="DESELECT")
        p.select_set(True)
        bpy.context.view_layer.objects.active = p
        bpy.ops.object.shade_smooth()
        p.data.materials.append(m)
    return parts


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


def stove_glow(stove_xy, energy=45):
    """The stove's firebox and rocks lighting the room (the emission alone is too weak to light it)."""
    return lamp((stove_xy[0] - 0.15, stove_xy[1] - 0.6, 0.55), energy)


def lamp(location, energy, color=(1.0, 0.55, 0.3), size=0.3):
    """Warm point light (the stove's glow on its surroundings)."""
    bpy.ops.object.light_add(type="POINT", location=location)
    li = bpy.context.active_object.data
    li.energy = energy
    li.color = color
    li.shadow_soft_size = size
    return li


def camera(scene, target, direction, dist, lens, fstop=5.6):
    t = Vector(target)
    eye = t + Vector(direction).normalized() * dist
    bpy.ops.object.camera_add(location=eye)
    cam = bpy.context.active_object
    cam.rotation_euler = (t - eye).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = dist
    cam.data.dof.aperture_fstop = fstop
    scene.camera = cam
    return cam


def render(scene, path, samples, size=(1920, 1080)):
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
    scene.render.resolution_x, scene.render.resolution_y = size
    Path(path).parent.mkdir(exist_ok=True)
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    print("rendered", path, flush=True)


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


ROBE_LIFT = 0.6        # robe OBJ y 0.20..0.91 -> hem at 0.8 m, collar at 1.51 m (player height)
WRAP_LIFT = 1.3        # wrap OBJ y 0.08..0.48 -> scarf on the shoulders, top of the head at 1.78 m


def figure(robe=True, wrap=True, location=(0, 0, 0), rot_z=0.0):
    """Ghost sauna-goer: robe and/or towel wrap on a wooden tailor's stand with a head form."""
    import bpy as _bpy
    before = set(_bpy.data.objects)
    top = ROBE_LIFT + 0.9 if robe else WRAP_LIFT + 0.08
    dress_form(top=top, neck_r=0.055, neck_h=0.12 if robe else 0.1)
    if wrap:
        _bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=(-0.01, 0.0, WRAP_LIFT + 0.36))
        head = _bpy.context.active_object
        head.scale = (0.085, 0.1, 0.115)
        _bpy.ops.object.shade_smooth()
        head.data.materials.append(_bpy.data.materials["form"])
        add("wrap", (0, 0, WRAP_LIFT))
    if robe:
        add("robe", (0, 0, ROBE_LIFT))
    root = _bpy.data.objects.new("figure", None)
    _bpy.context.scene.collection.objects.link(root)
    for ob in set(_bpy.data.objects) - before - {root}:
        ob.parent = root
    root.location = location
    root.rotation_euler.z = math.radians(rot_z)
    return root
