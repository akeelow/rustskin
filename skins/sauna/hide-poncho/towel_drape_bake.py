"""Sauna Towel v5 (shoulder): a real towel - a high-poly sheet of fixed size, draped over the left
shoulder by cloth simulation on the hide poncho, overhangs folded back onto it, baked onto the
poncho's UVs.

v4.1 (a swept strip whose width followed the hide) looked awful: ragged, torn outline. Here the
towel is a fixed 22 cm wide terry sheet laid on the hide over the shoulder (front to back, ~95 cm).
Where an edge would hang off the hide, that edge is folded back over the towel along a straight line
(a folded corner / turned-in edge with a rounded crease), the towel's size unchanged. (A cloth
simulation was tried first: on this thin, holed collider the sheet crumpled into a rope.) Holes in the hide under the towel
that folding can't hide stay holes; compose_drape.py dresses them as worn holes in the terry.

  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/hide-poncho/towel_drape_bake.py [-- --blend]

Writes bake/towel_drape_{albedo,mask,ao,normal,uv}.png (2048), bake/towel_drape.blend (--blend);
then `.venv/Scripts/python skins/sauna/hide-poncho/compose_drape.py`.
"""
import importlib.util
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector, noise
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("towel_neck_bake", HERE / "towel_neck_bake.py")
tb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tb)

ORIG, OUT = HERE / "originals", HERE / "bake"
SIZE = 2048
W, L = 0.22, 1.00            # towel as it lies (folded once lengthwise), metres
NU, NV = 191, 45             # vertices along / across
LIFT = 0.02                  # start this far above the hide
CENTRE = Vector((0.0, 1.2, -0.02))


def lin(h):
    return tuple((int(h[i:i + 2], 16) / 255) ** 2.2 for i in (1, 3, 5))


TOWEL, BRICK, BRICK2, STITCH = lin("#D2CABB"), lin("#7E3127"), lin("#8E4639"), lin("#8C8272")


# ---------------------------------------------------------------- the sheet, laid over the shoulder
def surface_point(bvh, p, n, b, a):
    """Point on the hide at offset `a` across the strip (cast down along -n); flat if no hide."""
    q = p + b * a
    loc, hn, _, _ = bvh.ray_cast(q + n * 0.06, -n)
    if loc is not None and (loc - q).length < 0.03 and hn.dot(n) > 0.2             and hn.dot((loc - CENTRE).normalized()) > 0:
        # the toggle flap: two hide sheets with a torn edge (x < 0.095 below 1.32 m at the front);
        # the towel is folded clear of it rather than cut by its edge
        if loc.z > 0.05 and loc.y < 1.32 and loc.x < 0.095:
            return q, False
        return loc, True
    return q, False


def build_sheet(low):
    """A W x path-length towel on the hide over the left shoulder. Where it would hang off the hide
    (the front panel narrows, the neck opening, the shoulder's edge), that edge of the towel is
    folded back over itself along a straight line - a folded corner or a turned-in edge, the
    towel's size unchanged. Small holes in the hide under it stay holes (compose_drape.py)."""
    bvh = BVHTree.FromObject(low, bpy.context.evaluated_depsgraph_get(), deform=False)
    Pr, Nr, ss, Lp = tb.resample(tb.shoulder_path(low), step=0.004)
    Nn, Bn = tb.frames(Pr, Nr)
    rows = np.linspace(0, len(Pr) - 1, NU).round().astype(int)
    A = (np.arange(NV) / (NV - 1) - 0.5) * W
    S = ss[rows]
    pos = np.zeros((NU, NV, 3))
    sup = np.zeros((NU, NV), bool)
    nrm = np.zeros((NU, 3))
    for i, r in enumerate(rows):
        p, n, b = Vector(Pr[r]), Vector(Nn[r]), Vector(Bn[r])
        nrm[i] = n
        for j, a in enumerate(A):
            q, ok = surface_point(bvh, p, n, b, a)
            pos[i, j], sup[i, j] = q, ok
    # how far each side reaches on hide, per row
    mid = NV // 2
    reach = np.zeros((2, NU))
    for i in range(NU):
        for side, js in ((0, range(mid, -1, -1)), (1, range(mid, NV))):
            last = mid
            for j in js:
                if not sup[i, j]:
                    break
                last = j
            reach[side, i] = abs(A[last])
    # straight fold lines per side over each run of overhang, ramping out to the edge at 45 deg
    fold = np.full((2, NU), W / 2)
    for side in (0, 1):
        over = reach[side] < W / 2 - 0.006
        MARGIN = 0.018                                  # fold well inside the hide's ragged edge
        i = 0
        while i < NU:
            if not over[i]:
                i += 1
                continue
            i0 = i
            while i < NU and over[i]:
                i += 1
            i1 = i - 1
            ssel = S[i0:i1 + 1]
            r = reach[side, i0:i1 + 1] - MARGIN
            beta = np.polyfit(ssel, r, 1)[0] if len(ssel) > 2 else 0.0
            alpha = np.min(r - beta * ssel)                 # the line stays on the hide everywhere
            line = alpha + beta * S + np.maximum(0, np.maximum(S[i0] - S, S - S[i1]))
            fold[side] = np.minimum(fold[side], np.clip(line, 0.03, W / 2))
    # fold: mirror the part beyond the line back over the towel, one layer up
    out = pos.copy()
    folded = 0
    for i in range(NU):
        for j, a in enumerate(A):
            side = 0 if a < 0 else 1
            lim = fold[side, i]
            if abs(a) <= lim + 1e-6:
                continue
            a2 = np.sign(a) * (2 * lim - abs(a))
            a2 = float(np.clip(a2, -fold[0, i], fold[1, i]))
            r = rows[i]
            q, _ = surface_point(bvh, Vector(Pr[r]), Vector(Nn[r]), Vector(Bn[r]), a2)
            out[i, j] = np.array(q) + nrm[i] * 0.008
            folded += 1
    # the crease: vertices right at the fold line sit half a layer up, so the fold is rounded
    for i in range(NU):
        for j, a in enumerate(A):
            side = 0 if a < 0 else 1
            if abs(abs(a) - fold[side, i]) < (W / (NV - 1)) * 0.75 and fold[side, i] < W / 2 - 1e-6:
                out[i, j] = out[i, j] + nrm[i] * 0.004
    holes = int((~sup & (np.abs(A)[None, :] <= np.minimum(fold[0], fold[1])[:, None])).sum())
    print(f"towel {W:.2f} x {S[-1]:.2f} m: folded {folded} of {NU * NV} vertices, "
          f"{holes} vertices over holes in the hide", flush=True)
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")
    grid = [[bm.verts.new(Vector(out[i, j])) for j in range(NV)] for i in range(NU)]
    for i in range(NU - 1):
        for j in range(NV - 1):
            f = bm.faces.new((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]))
            for loop, (u, v) in zip(f.loops, ((i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j))):
                loop[uv_layer].uv = (u / (NU - 1), v / (NV - 1))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("towel")
    bm.to_mesh(me)
    bm.free()
    # make the sheet's normals face out (away from the body)
    c = np.mean(out.reshape(-1, 3), 0)
    if np.mean([p.normal.dot(Vector(p.center) - CENTRE) for p in me.polygons]) < 0:
        me.flip_normals()
    np.save(OUT / "towel_drape_grid.npy", np.concatenate([out.reshape(-1, 3), np.repeat(nrm, NV, 0)], 1))
    del c
    return me


def thicken(towel):
    so = towel.modifiers.new("thick", "SOLIDIFY")
    so.thickness = 0.008
    so.offset = 1.0
    sub = towel.modifiers.new("smooth", "SUBSURF")
    sub.levels = sub.render_levels = 1
    bpy.context.view_layer.objects.active = towel
    with bpy.context.temp_override(object=towel, active_object=towel):
        for m in list(towel.modifiers):
            bpy.ops.object.modifier_apply(modifier=m.name)
    # terry lumps and a little irregularity
    for v in towel.data.vertices:
        v.co += v.normal * (0.0012 * noise.noise(v.co * 160) + 0.0008 * noise.noise(v.co * 40))
    for p in towel.data.polygons:
        p.use_smooth = True


# ---------------------------------------------------------------- material (sheet UV: u along, v across)
def towel_material(kind):
    m = bpy.data.materials.new("towel_" + kind)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N, Lk = nt.nodes, nt.links
    out = N.new("ShaderNodeOutputMaterial")
    if kind in ("normal", "ao"):
        bs = N.new("ShaderNodeBsdfDiffuse")
        bs.inputs["Color"].default_value = (0.8, 0.8, 0.8, 1)
        Lk.new(bs.outputs[0], out.inputs[0])
        return m
    em = N.new("ShaderNodeEmission")
    Lk.new(em.outputs[0], out.inputs[0])
    if kind == "mask":
        em.inputs["Color"].default_value = (1, 1, 1, 1)
        return m
    tc = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(tc.outputs["UV"], sep.inputs[0])
    if kind == "uv":
        comb = N.new("ShaderNodeCombineColor")
        Lk.new(sep.outputs["X"], comb.inputs[0])
        Lk.new(sep.outputs["Y"], comb.inputs[1])
        Lk.new(comb.outputs[0], em.inputs["Color"])
        return m

    def mth(op, a, b=None):
        n = N.new("ShaderNodeMath")
        n.operation = op
        for idx, val in enumerate((a, b)):
            if val is None:
                continue
            if isinstance(val, (int, float)):
                n.inputs[idx].default_value = val
            else:
                Lk.new(val, n.inputs[idx])
        return n.outputs[0]

    along = mth("MULTIPLY", sep.outputs["X"], L)
    across = mth("MULTIPLY", sep.outputs["Y"], W)
    dend = mth("MINIMUM", along, mth("SUBTRACT", L, along))
    dside = mth("MINIMUM", across, mth("SUBTRACT", W, across))
    band = lambda d, c, w: mth("LESS_THAN", mth("ABSOLUTE", mth("SUBTRACT", d, c)), w)
    dash = lambda coord: mth("LESS_THAN", mth("FRACT", mth("DIVIDE", coord, 0.006)), 0.55)
    wide = band(dend, 0.085, 0.02)
    narrow = band(dend, 0.128, 0.007)
    hem = mth("LESS_THAN", dend, 0.03)
    hem_stitch = mth("MULTIPLY", band(dend, 0.028, 0.0012), dash(across))
    selv = mth("MULTIPLY", band(dside, 0.012, 0.0012), dash(along))
    fringe = mth("LESS_THAN", dend, 0.006)
    nz = N.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 900.0
    Lk.new(tc.outputs["Object"], nz.inputs["Vector"])
    mott = N.new("ShaderNodeTexNoise")
    mott.inputs["Scale"].default_value = 25.0
    Lk.new(tc.outputs["Object"], mott.inputs["Vector"])

    def mix(fac, a, b):
        mx = N.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        if isinstance(fac, float):
            mx.inputs["Factor"].default_value = fac
        else:
            Lk.new(fac, mx.inputs["Factor"])
        for idx, val in ((6, a), (7, b)):
            if isinstance(val, tuple):
                mx.inputs[idx].default_value = val + (1.0,)
            else:
                Lk.new(val, mx.inputs[idx])
        return mx.outputs[2]

    c = mix(0.25, TOWEL, nz.outputs["Color"])
    c = mix(mth("MULTIPLY", mott.outputs["Fac"], 0.25), c, (0.55, 0.5, 0.42))
    c = mix(wide, c, BRICK)
    c = mix(narrow, c, BRICK2)
    c = mix(mth("MULTIPLY", hem, 0.12), c, (0.3, 0.28, 0.24))
    c = mix(hem_stitch, c, STITCH)
    c = mix(selv, c, STITCH)
    c = mix(mth("MULTIPLY", fringe, 0.3), c, (0.4, 0.38, 0.33))
    Lk.new(c, em.inputs["Color"])
    return m


# ---------------------------------------------------------------- bake
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    bpy.ops.wm.obj_import(filepath=str(ORIG / "attire.hide.poncho_poncho.obj"), forward_axis="NEGATIVE_Z", up_axis="Y")
    low = bpy.context.selected_objects[0]
    low.name = "poncho"
    # simulate in the mesh's own (OBJ) space: no rotation on the collider
    low.matrix_world = Matrix_identity()
    OUT.mkdir(exist_ok=True)
    towel = bpy.data.objects.new("towel", build_sheet(low))
    scene.collection.objects.link(towel)
    thicken(towel)
    print("towel faces", len(towel.data.polygons), flush=True)

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
    scene.view_settings.view_transform = "Standard"
    scene.world = bpy.data.worlds.new("w")
    scene.world.light_settings.distance = 0.05

    tm = bpy.data.materials.new("target")
    tm.use_nodes = True
    low.data.materials.clear()
    low.data.materials.append(tm)
    tex = tm.node_tree.nodes.new("ShaderNodeTexImage")
    tm.node_tree.nodes.active = tex
    for attr in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission", "visible_shadow"):
        setattr(low, attr, False)
    bk = scene.render.bake
    bk.use_selected_to_active = True
    bk.use_cage = False
    bk.cage_extrusion = 0.06
    bk.max_ray_distance = 0.09
    bk.margin = 2
    bk.normal_space = "TANGENT"
    bk.normal_r, bk.normal_g, bk.normal_b = "POS_X", "POS_Y", "POS_Z"
    bpy.ops.object.select_all(action="DESELECT")
    towel.select_set(True)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low

    OUT.mkdir(exist_ok=True)
    for name, kind, btype, samples in (("albedo", "albedo", "EMIT", 4), ("mask", "mask", "EMIT", 1),
                                       ("uv", "uv", "EMIT", 1), ("normal", "normal", "NORMAL", 1),
                                       ("ao", "ao", "AO", 64)):
        towel.data.materials.clear()
        towel.data.materials.append(towel_material(kind))
        img = bpy.data.images.new("bake_" + name, SIZE, SIZE, alpha=False, float_buffer=True)
        img.colorspace_settings.name = "Non-Color"
        img.generated_color = (0, 0, 0, 1) if name != "normal" else (0.5, 0.5, 1, 1)
        tex.image = img
        scene.cycles.samples = samples
        bpy.ops.object.bake(type=btype, use_clear=False, margin=2)
        px = np.array(img.pixels[:], dtype=np.float32).reshape(SIZE, SIZE, 4)
        if name == "albedo":
            px[..., :3] = np.clip(px[..., :3], 0, 1) ** (1 / 2.2)
        out = bpy.data.images.new("out_" + name, SIZE, SIZE, alpha=True)
        out.colorspace_settings.name = "Non-Color"
        px[..., 3] = 1.0
        out.pixels[:] = np.clip(px, 0, 1).ravel()
        out.filepath_raw = str(OUT / f"towel_drape_{name}.png")
        out.file_format = "PNG"
        out.save()
        print("baked", name, flush=True)
    if "--blend" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "towel_drape.blend"))
    print("done", flush=True)


def Matrix_identity():
    from mathutils import Matrix
    return Matrix.Identity(4)


if __name__ == "__main__":
    main()
