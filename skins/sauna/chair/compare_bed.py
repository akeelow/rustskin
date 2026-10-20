"""One frame of the chair next to the finished bench (Bed v1.2), same light: are the wood, rust and
linen the same, built by the same hand? Uses tools/blender/viewer.py's material, light and camera.

  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/chair/compare_bed.py -- <chair prefix> <out.png> [day|night]
"""
import importlib.util
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
argv = sys.argv[sys.argv.index("--") + 1:]
CHAIR_TEX, OUT = argv[0], Path(argv[1]).resolve()
MODE = argv[2] if len(argv) > 2 else "day"

spec = importlib.util.spec_from_file_location("viewer", ROOT / "tools" / "blender" / "viewer.py")
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)


def load(obj, prefix, cutoff, zup, scale, loc, rot_z=0.0):
    V.PREFIX, V.CUTOFF = prefix, cutoff
    mat = V.material()
    if zup:
        bpy.ops.wm.obj_import(filepath=str(obj), forward_axis="Y", up_axis="Z")
    else:
        bpy.ops.wm.obj_import(filepath=str(obj), forward_axis="NEGATIVE_Z", up_axis="Y")
    for o in bpy.context.selected_objects:
        o.scale = (scale, scale, scale)
        o.location = loc
        o.rotation_euler.z = rot_z
        o.data.materials.clear()
        o.data.materials.append(mat)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    load(ROOT / "skins/sauna/bed/originals/bed.obj", str(ROOT / "skins/sauna/bed/export/Bed_v1.2"), 0.5, True, 0.01,
         (0.0, 0.0, 0.04))
    # the chair at the bench's foot end, turned a little toward the camera
    load(HERE / "originals/chair.obj", CHAIR_TEX, 0.0, False, 1.0, (-1.65, -0.35, 0.0), math.radians(-35))
    V.ground()
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"
    vt = [v.identifier for v in scene.view_settings.bl_rna.properties["view_transform"].enum_items]
    scene.view_settings.view_transform = "AgX" if "AgX" in vt else "Filmic"
    scene.render.resolution_x, scene.render.resolution_y = 1400, 800
    V.lights(scene, MODE)
    V.camera(scene, Vector((-0.95, 0.0, 0.5)), (-0.2, -1, 0.5), 4.4)
    scene.render.filepath = str(OUT)
    bpy.ops.render.render(write_still=True)
    print("saved", OUT)


if __name__ == "__main__":
    main()
