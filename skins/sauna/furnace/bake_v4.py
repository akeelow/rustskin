"""Sauna Boiler v4: high-poly поверх Furnace и запекание на его развёртку (4096; экспорт 1024 — texture_v4.py).

План: PLAN_v4.md. Каждая деталь — геометрия; маски цвета пишутся в атрибуты вершин той же геометрии (fields_v4.py).
Основа — electric-furnace/bake_v3.py (Sauna Stove v3).

Как устроено (вертикальный срез: бак — остров 0, пояс реек — острова 1, 2):
  high-poly = копия граней модели, подразделённая до рёбер ≤ --edge см и смещённая вдоль нормалей полем fields_v4.body;
  рядом — та же копия без смещения. Нормаль (гайд §9.2, «вычитание» — PROMPT_next_skin §5):
    n = норм(n_гладкой low-poly + (n_смещённой − n_копии без смещения)), всё в object space с плоской копии,
  затем перенос на сглаженную low-poly (нормали OBJ) -> tangent space MikkTSpace, как в Unity. Гранёность модели в
  нормаль не попадает, остаётся только смоделированное.
  AO и маски (m1, m2, m3, idc, pos) — с той же смещённой копии.

Запуск (из корня репозитория):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/furnace/bake_v4.py -- \\
      [--size 4096] [--edge 0.18] [--gpu] [--blend]
Пишет bake/v4/{normal,ao,m1,m2,m3,idc,pos,cover,mask,used}.png.
"""
import sys
import time
from pathlib import Path

import bmesh
import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
OBJ = HERE / "originals" / "furnace.obj"
OUT = HERE / "bake" / "v4"
sys.path.insert(0, str(HERE))
import fields_v4 as FV  # noqa: E402
import geom_v4 as G  # noqa: E402

ATTRS = ("m1", "m2", "m3", "idc", "pos")
POS_LO, POS_SPAN = np.array([-55.0, 0.0, -55.0]), np.array([110.0, 165.0, 110.0])   # pos = (OBJ см - LO) / SPAN
CM = 0.01


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


# ---------------------------------------------------------------- low-poly
def load_low():
    """Оригинал как есть: свои нормали OBJ (сглаженные, как в игре). Меш — в координатах OBJ (м), объект повёрнут."""
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="NEGATIVE_Z", up_axis="Y")
    low = bpy.context.selected_objects[0]
    low.name = "low_smooth"
    isl = G.island_of_face()
    assert len(low.data.polygons) == len(isl), (len(low.data.polygons), len(isl))
    V, T, N, F = G.load()
    for fi in (0, len(isl) - 1):
        c_obj = V[F[fi][:, 0]].mean(0) * CM
        c_bl = np.array(low.data.polygons[fi].center)
        assert np.abs(c_obj - c_bl).max() < 1e-4, (fi, c_obj, c_bl)
    return low


def subset(low, keep, name, flat=False):
    """Копия low-poly только с гранями островов keep. flat: нормали граней + разрез острых рёбер (для лучей)."""
    me = low.data.copy()
    ob = bpy.data.objects.new(name, me)
    ob.matrix_world = low.matrix_world
    bpy.context.scene.collection.objects.link(ob)
    isl = G.island_of_face()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if isl[f.index] not in keep], context="FACES")
    if flat:
        sharp = [e for e in bm.edges if len(e.link_faces) == 2
                 and e.link_faces[0].normal.angle(e.link_faces[1].normal, 0) > 0.7]
        bmesh.ops.split_edges(bm, edges=sharp)
    bm.to_mesh(me)
    bm.free()
    if flat:
        bpy.context.view_layer.objects.active = ob
        with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
        for p in me.polygons:
            p.use_smooth = False
    return ob


# ---------------------------------------------------------------- mesh from numpy
def set_attrs(me, attrs, nv):
    for k in ATTRS:
        a = me.color_attributes.get(k) or me.color_attributes.new(k, "FLOAT_COLOR", "POINT")
        buf = np.zeros((nv, 4), np.float32)
        buf[:, 3] = 1
        if k in attrs:
            buf[:, :3] = np.asarray(attrs[k], np.float32).reshape(nv, 3)
        a.data.foreach_set("color", buf.ravel())


def mesh_np(name, V, Q, attrs, low, group):
    """Объект из массивов (координаты OBJ в см): V (n, 3), Q (m, 3); attrs {имя: (n, 3)}."""
    me = bpy.data.meshes.new(name)
    n, m = len(V), len(Q)
    k = Q.shape[1]
    me.vertices.add(n)
    me.vertices.foreach_set("co", (np.asarray(V, np.float64) * CM).astype(np.float32).ravel())
    me.loops.add(m * k)
    me.loops.foreach_set("vertex_index", np.asarray(Q, np.int32).ravel())
    me.polygons.add(m)
    me.polygons.foreach_set("loop_start", (np.arange(m) * k).astype(np.int32))
    me.update(calc_edges=True)
    me.validate(verbose=False)
    set_attrs(me, attrs, n)
    me.polygons.foreach_set("use_smooth", np.ones(m, bool))
    ob = bpy.data.objects.new(name, me)
    ob.matrix_world = low.matrix_world
    bpy.context.scene.collection.objects.link(ob)
    ob["group"] = group
    return ob


def field_attrs(r, V):
    return {"m1": np.stack([np.clip(r["wear"], 0, 1), np.clip(r["cav"], 0, 1), np.clip(r["dent"], 0, 1)], -1),
            "m2": np.stack([np.clip(r["rivet"], 0, 1), np.clip(r["knot"], 0, 1), np.clip(r["char"], 0, 1)], -1),
            "m3": np.stack([np.clip(r["rust"], 0, 1), np.clip(r["crust"], 0, 1), np.clip(r["tone"], 0, 1)], -1),
            "idc": np.stack([r["mat"] / 32.0, (r["sid"] + 1) / 64.0, np.clip(r["heat"], 0, 1)], -1),
            "pos": np.clip((V - POS_LO) / POS_SPAN, 0, 1)}


def displaced(low, name, group, islands, edge):
    """Подразделённая копия граней модели (рёбра до edge см), смещённая полем fields_v4 вдоль нормалей вершин; рядом —
    та же копия без смещения (plain_of = группа) для вычитания гранёности."""
    src = subset(low, islands, f"tmp_{name}")
    # сглаженные нормали OBJ в атрибут вершин: при подразделении они интерполируются, и смещение идёт вдоль гладкого
    # поля нормалей — во впадинах бугристого основания поверхность не складывается (v4.0: крапинка по граням)
    sme = src.data
    cn = np.empty(len(sme.loops) * 3, np.float32)
    sme.corner_normals.foreach_get("vector", cn)
    lv = np.empty(len(sme.loops), np.int32)
    sme.loops.foreach_get("vertex_index", lv)
    acc = np.zeros((len(sme.vertices), 3))
    np.add.at(acc, lv, cn.reshape(-1, 3))
    acc /= np.linalg.norm(acc, axis=1, keepdims=True) + 1e-9
    at_sn = sme.attributes.new("sn", "FLOAT_VECTOR", "POINT")
    at_sn.data.foreach_set("vector", acc.astype(np.float32).ravel())
    bm = bmesh.new()
    bm.from_mesh(src.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    for it in range(12):
        # делятся ВСЕ рёбра граней, у которых есть длинное ребро: треугольник -> 4 подобных (без вырожденных щепок)
        faces = [f for f in bm.faces if max(e.calc_length() for e in f.edges) > edge * CM]
        if not faces:
            break
        edges = list({e for f in faces for e in f.edges})
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=1, use_grid_fill=True)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
        log(f"  subdivide {it}: {len(faces)} faces split, {len(bm.faces)} faces")
    me = bpy.data.meshes.new("tmp_sub")
    bm.to_mesh(me)
    bm.free()
    bpy.data.objects.remove(src, do_unlink=True)
    nv = len(me.vertices)
    V = np.empty(nv * 3, np.float32)
    me.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3).astype(np.float64) / CM
    Nv = np.empty(nv * 3, np.float32)
    me.attributes["sn"].data.foreach_get("vector", Nv)
    Nv = Nv.reshape(-1, 3).astype(np.float64)
    Nv /= np.linalg.norm(Nv, axis=1, keepdims=True) + 1e-9
    me.calc_loop_triangles()
    nt = len(me.loop_triangles)
    Fi = np.empty(nt * 3, np.int32)
    me.loop_triangles.foreach_get("vertices", Fi)
    Fi = Fi.reshape(-1, 3)
    bpy.data.meshes.remove(me)
    log("  high-poly", nv, "verts", nt, "tris")
    r = FV.body(V, Nv, log=lambda *a: log(*a))
    at = field_attrs(r, V)
    ob = mesh_np(name, V + Nv * r["h"][:, None], Fi, at, low, group)
    pl = mesh_np(name + "_plain", V, Fi, at, low, group + "_plain")
    pl["plain_of"] = group
    pl.hide_render = True
    log("displaced", name, nv, "h", float(r["h"].min()), float(r["h"].max()))
    return [ob]


GROUPS = {"body": ({G.TANK, G.BASE_R, G.BASE_L}, 0.04)}


# ---------------------------------------------------------------- запекание
def hp_material():
    m = bpy.data.materials.new("hp")
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL")
    bs = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    em = {}
    for k in ATTRS:
        a = N.new("ShaderNodeVertexColor")
        a.layer_name = k
        e = N.new("ShaderNodeEmission")
        L.new(a.outputs["Color"], e.inputs["Color"])
        em[k] = e
    w = N.new("ShaderNodeEmission")
    w.inputs["Color"].default_value = (1, 1, 1, 1)
    em["cover"] = w
    return m, out, bs, em


def set_pass(mat, which):
    m, out, bs, em = mat
    L = m.node_tree.links
    for l in list(out.inputs["Surface"].links):
        L.remove(l)
    L.new((bs if which == "view" else em[which]).outputs[0], out.inputs["Surface"])


def setup_cycles(gpu):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    if gpu:
        try:
            prefs = bpy.context.preferences.addons["cycles"].preferences
            for kind in ("OPTIX", "CUDA"):
                try:
                    prefs.compute_device_type = kind
                    prefs.get_devices()
                    ok = [d for d in prefs.devices if d.type == kind]
                    if ok:
                        for d in prefs.devices:
                            d.use = d.type == kind
                        sc.cycles.device = "GPU"
                        log("GPU", kind)
                        break
                except TypeError:
                    continue
        except Exception as e:  # noqa: BLE001
            log("GPU off:", e)
    sc.cycles.use_denoising = False
    sc.cycles.samples = 1
    if sc.world is None:
        sc.world = bpy.data.worlds.new("bake")
    sc.world.light_settings.distance = 0.04      # AO: 4 см


def new_img(name, size):
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    return img


def save_png(img, path, arr=None):
    size = img.size[0]
    if arr is not None:
        buf = np.ones((size, size, 4), np.float32)
        buf[..., :3] = arr
        img.pixels.foreach_set(buf.ravel())
    out = bpy.data.images.new(img.name + "_out", size, size, alpha=False)
    out.colorspace_settings.name = "Non-Color"
    px = np.empty(size * size * 4, np.float32)
    img.pixels.foreach_get(px)
    out.pixels.foreach_set(px)
    out.filepath_raw = str(path)
    out.file_format = "PNG"
    out.save()
    bpy.data.images.remove(out)
    log("  ->", path.name)


def bake_pass(target, hp, kind, size, name, extr, samples=1, filt=1.5, margin=4, space="TANGENT"):
    sc = bpy.context.scene
    bk = sc.render.bake
    img = new_img(name, size)
    target["tex"].image = img
    target["mat"].node_tree.nodes.active = target["tex"]
    bk.use_selected_to_active = hp is not None
    bk.use_cage = False
    bk.cage_extrusion = extr
    bk.max_ray_distance = extr * 2.0
    bk.target = "IMAGE_TEXTURES"
    bk.normal_space = space
    bk.normal_r, bk.normal_g, bk.normal_b = "POS_X", "POS_Y", "POS_Z"   # OpenGL, как Unity
    bk.margin = margin
    bk.margin_type = "EXTEND"
    sc.cycles.samples = samples
    sc.cycles.filter_width = filt
    bpy.ops.object.select_all(action="DESELECT")
    if hp:
        for o in hp:
            o.select_set(True)
    ob = target["ob"]
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    log("bake", name, kind, space if kind == "NORMAL" else "")
    bpy.ops.object.bake(type=kind, use_clear=True, margin=margin)
    return img


def make_target(ob, use_map=None):
    m = bpy.data.materials.new(ob.name + "_bake")
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    tex = N.new("ShaderNodeTexImage")
    if use_map is not None:
        src = N.new("ShaderNodeTexImage")
        src.image = use_map
        src.interpolation = "Closest"
        nm = N.new("ShaderNodeNormalMap")
        nm.space = "OBJECT"
        bs = next(n for n in N if n.type == "BSDF_PRINCIPLED")
        L.new(src.outputs["Color"], nm.inputs["Color"])
        L.new(nm.outputs["Normal"], bs.inputs["Normal"])
    ob.data.materials.clear()
    ob.data.materials.append(m)
    for attr in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission",
                 "visible_volume_scatter", "visible_shadow"):
        setattr(ob, attr, False)
    return {"ob": ob, "mat": m, "tex": tex}


def white_mask(ob, size, tag):
    m = bpy.data.materials.new(f"mask_{tag}")
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL")
    e = N.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (1, 1, 1, 1)
    L.new(e.outputs[0], out.inputs["Surface"])
    tex = N.new("ShaderNodeTexImage")
    old = list(ob.data.materials)
    ob.data.materials.clear()
    ob.data.materials.append(m)
    img = bake_pass({"ob": ob, "mat": m, "tex": tex}, None, "EMIT", size, f"{tag}_mask", 0.01, filt=0.01, margin=0)
    ob.data.materials.clear()
    for mm in old:
        ob.data.materials.append(mm)
    return img


def pixels(img):
    size = img.size[0]
    px = np.empty(size * size * 4, np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(size, size, 4)[..., :3]


def bake_group(low, keep, hp, size, extr, tag, mat):
    for o in hp:
        o.data.materials.clear()
        o.data.materials.append(mat[0])
    flat = make_target(subset(low, keep, f"ray_{tag}", flat=True))
    res = {}
    set_pass(mat, "view")
    obj_n = bake_pass(flat, hp, "NORMAL", size, f"{tag}_nobj", extr, space="OBJECT")
    plain = [o for o in bpy.data.objects if o.get("plain_of") == tag]
    for o in plain:
        o.data.materials.clear()
        o.data.materials.append(mat[0])
        o.hide_render = False
    for o in hp:
        o.hide_render = True
    n0 = pixels(bake_pass(flat, plain, "NORMAL", size, f"{tag}_n0", extr, space="OBJECT")) * 2 - 1
    for o in plain:
        o.hide_render = True
    for o in hp:
        o.hide_render = False
    nd = pixels(obj_n) * 2 - 1
    sm0 = make_target(subset(low, keep, f"sm0_{tag}"))
    ns = pixels(bake_pass(sm0, None, "NORMAL", size, f"{tag}_ns", extr, space="OBJECT")) * 2 - 1
    n = ns + (nd - n0)
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-6
    buf = np.ones((size, size, 4), np.float32)
    buf[..., :3] = n * 0.5 + 0.5
    obj_n.pixels.foreach_set(buf.ravel())
    res["ao"] = pixels(bake_pass(flat, hp, "AO", size, f"{tag}_ao", extr, samples=64))
    for k in (*ATTRS, "cover"):
        set_pass(mat, k)
        res[k] = pixels(bake_pass(flat, hp, "EMIT", size, f"{tag}_{k}", extr, filt=0.01 if k == "idc" else 1.5))
    set_pass(mat, "view")
    smooth = make_target(subset(low, keep, f"smooth_{tag}"), use_map=obj_n)
    res["normal"] = pixels(bake_pass(smooth, None, "NORMAL", size, f"{tag}_ntan", extr))
    mask = pixels(white_mask(smooth["ob"], size, tag))[..., 0] > 0.5
    for im in list(bpy.data.images):
        if im.name.startswith(tag + "_"):
            bpy.data.images.remove(im)
    return res, mask


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 4096
    edge = float(argv[argv.index("--edge") + 1]) if "--edge" in argv else 0.18
    bpy.ops.wm.read_factory_settings(use_empty=True)
    setup_cycles("--gpu" in argv)
    low = load_low()
    low.hide_render = True
    hp = displaced(low, "hp_body", "body", GROUPS["body"][0], edge)
    OUT.mkdir(parents=True, exist_ok=True)
    holder = new_img("holder", size)
    low.hide_render = False
    save_png(holder, OUT / "used.png", pixels(white_mask(low, size, "used")))
    low.hide_render = True
    mat = hp_material()
    result = {}
    for g, (keep, extr) in GROUPS.items():
        ghp = [o for o in hp if o["group"] == g]
        res, mask = bake_group(low, keep, ghp, size, extr, g, mat)
        for k, arr in res.items():
            result.setdefault(k, np.zeros_like(arr) + ((0.5, 0.5, 1.0) if k == "normal" else 0))[mask] = arr[mask]
        result.setdefault("mask", np.zeros((size, size, 3), np.float32))[mask] = 1.0
        log("group", g, "texels", int(mask.sum()))
    for k, arr in result.items():
        save_png(holder, OUT / f"{k}.png", arr)
    if "--blend" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "highpoly.blend"))
    log("done")


if __name__ == "__main__":
    main()
