"""Sauna Shotgun v2: high-poly и запекание на развёртку оригинала (PLAN_v2.md, §4). Вертикальный срез: трубы стволов
(BARREL 1), приклад целиком (STOCK), рамка колодки (MAIN, FD.FRAME_ISL). Остальное пока от v1.11 (texture_v2.py).

Нормаль. Модель сглажена целиком (vn отклонены от граней на 17-26° в среднем, PLAN_v2 §1.3), и игра шейдит её этими
нормалями. Поэтому:
  1) high-poly строится на ПЛОСКОЙ копии граней (подразделение без скругления) + рельеф из fields_dbs.py — без
     Phong-скругления v1.9 (оно оставляло излом на стыках граней);
  2) запекание в object space с плоской копии (лучи по нормали грани): n_full; плюс object-space нормаль самой
     плоской копии n_b и сглаженной n_s;
  3) там, где high-poly построен на плоской основе (атрибут fb = 1), n_full поворачивается на угол (n_b -> n_s):
     остаётся только смоделированный рельеф, перенесённый на гладкую форму. Детали, построенные на своей гладкой
     основе (обмотки, манжеты, лист: fb = 0), берутся как есть;
  4) перенос: сглаженная low-poly (нормали OBJ) с этой картой через Normal Map (Object) -> NORMAL в касательном
     пространстве (MikkTSpace, как в Unity), без selected-to-active (§9.2 руководства).

Запуск (из корня репозитория, GPU общий — в фоне):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/double-barrel/bake_v2.py -- \
      [--parts barrel,stock,main] [--size 4096] [--gpu] [--look] [--nobake] [--blend]

Пишет bake/v2/<часть>_<группа>_{normal,ao,col,idc,m1,cover,mask}.png; --look — bake/v2/look_<часть>_<группа>_<k>.png
(high-poly в сером, до запекания).
  col — цвет вершин (линейный), idc — R = код материала * 16 + 8, m1 — маски fields_dbs (ржавчина/полость, светлое,
  своя), cover — где лучи попали в high-poly.
"""
import math
import random
import sys
import time
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bake_shotgun as BS  # noqa: E402
import fields_dbs as FD  # noqa: E402
import noise_np as NN  # noqa: E402

OUT = HERE / "bake" / "v2"
ATTRS = ("col", "idc", "m1", "fb")
MM = 0.001


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


# ---------------------------------------------------------------- атрибуты
def put(me, name, arr):
    n = len(me.vertices)
    a = me.color_attributes.get(name) or me.color_attributes.new(name, "FLOAT_COLOR", "POINT")
    buf = np.ones((n, 4), np.float32)
    buf[:, :3] = np.asarray(arr, np.float32).reshape(n, -1)[:, :3] if np.ndim(arr) > 1 else np.asarray(arr)[:, None]
    a.data.foreach_set("color", buf.ravel())


def set_np(me, col, ids, m1, fb):
    n = len(me.vertices)
    put(me, "col", col)
    idv = np.zeros((n, 3))
    idv[:, 0] = (np.asarray(ids) * 16 + 8) / 255
    put(me, "idc", idv)
    put(me, "m1", m1)
    put(me, "fb", np.tile(np.array([[fb, fb, fb]]), (n, 1)))


def ensure_attrs(ob):
    """Детали из v1 (bake_shotgun): у них есть col и idc; маски и fb — нули (основа у них своя, гладкая)."""
    me = ob.data
    n = len(me.vertices)
    for k in ("m1", "fb"):
        if me.color_attributes.get(k) is None:
            put(me, k, np.zeros((n, 3)))
    for p in me.polygons:
        p.use_smooth = True


# ---------------------------------------------------------------- копии граней
def face_set(low, pred):
    isl = low["isl"]
    return {p.index for p in low.data.polygons if pred(p, isl[p.index])}


def copy_faces(low, faces, name, keep_custom=True):
    me = low.data.copy()
    me.name = name
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    isl_l = bm.faces.layers.int.new("isl")
    isl = low["isl"]
    for f in bm.faces:
        f[isl_l] = isl[f.index]
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in faces], context="FACES")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if not keep_custom:
        bpy.context.view_layer.objects.active = ob
        with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
        me.polygons.foreach_set("use_smooth", np.zeros(len(me.polygons), bool))
    return ob


def field_copy(low, faces, name, step, fn, extra=None):
    """Плоская копия граней, раздробленная до шага `step`, со сдвигом по нормали fn(P, N, остров вершины)."""
    ob = copy_faces(low, faces, name, keep_custom=False)
    BS.even_mesh(ob, step * 4)
    BS.subdivided(ob, 2)
    me = ob.data
    me.update()
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    nr = np.empty(n * 3, np.float32)
    me.vertices.foreach_get("co", co)
    me.vertices.foreach_get("normal", nr)
    co, nr = co.reshape(n, 3).astype(np.float64), nr.reshape(n, 3).astype(np.float64)
    fi = np.zeros(len(me.polygons), np.int32)
    me.attributes["isl"].data.foreach_get("value", fi)
    vi = np.zeros(n, np.int32)
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lv)
    ls = np.empty(len(me.polygons), np.int32)
    lt = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_start", ls)
    me.polygons.foreach_get("loop_total", lt)
    vi[lv] = np.repeat(fi, lt)
    h, col, ids, m1 = fn(co, nr, vi) if extra is None else fn(co, nr, vi, *extra)
    me.vertices.foreach_set("co", (co + nr * h[:, None]).astype(np.float32).ravel())
    me.update()
    set_np(me, col, ids, m1, 1.0)
    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), bool))
    log(f"  {name}: {n} вершин, рельеф {h.min() / MM:+.2f}…{h.max() / MM:+.2f} мм")
    return ob


# ---------------------------------------------------------------- части
def build_tubes(low, rng):
    """Труба первого ствола (x > 0): второй делит с ней развёртку, печём один."""
    faces = face_set(low, lambda p, i: i == 1 and p.center.x > 0)
    tube = field_copy(low, faces, "hp_tube", 0.4 * MM, lambda P, N, vi: FD.tube_field(P, N))
    sleeves = BS.barrel_sleeves(low, rng)
    keep = []
    for o in sleeves:
        if o.name.endswith("_b"):
            bpy.data.objects.remove(o)
        else:
            ensure_attrs(o)
            keep.append(o)
    return faces, [tube] + keep, 0.006


def towel_wrap_v2(bvh, ax, s_a, s_b, th0, turns, width, name, seed):
    """Полоса вафельного полотенца по спирали (v1: гладкое полотенце с плетением 0.05 мм — в игре не читалось)."""
    TH = 0.0007

    def off(t, v, u_m):
        e = abs(v) * 2
        layer = 0.0004 + TH * (0.6 + 0.6 * t * turns)
        edge = 1.0 - 0.7 * BS.smooth01((e - 0.85) / 0.15)
        dist = (0.5 - abs(v)) * width
        h, w = FD.towel_relief(np.array([u_m]), np.array([v * width]), np.array([dist]), seed)
        tuck = -0.0006 * BS.smooth01((t - 0.96) / 0.04)
        return layer * edge + float(h[0]) - 0.0007 + tuck

    def col(t, v, u_m):
        c = BS.lin(BS.HEX["towel"])
        if 0.0 < v < 0.36:
            fade = 0.68 + 0.27 * (BS.noise.noise(Vector((u_m * 30, v * 4, seed))) * 0.5 + 0.5)
            c = BS.mix(c, BS.lin(BS.HEX["stripe"]), fade * BS.smooth01((min(v, 0.36 - v)) / 0.03))
        dirt = BS.noise.noise(Vector((u_m * 25, v * 3, seed + 2))) * 0.5 + 0.5
        c = BS.mix(c, BS.lin("9C927E"), 0.35 * BS.smooth01((dirt - 0.5) * 3))
        w = float(FD.waffle(np.array([u_m]), np.array([v * width]))[0])
        return BS.mix(c, BS.lin("B3A994"), 0.25 * (1 - w))   # в ячейках вафли тень и грязь

    return BS.wrap_strip(bvh, ax, s_a, s_b, th0, turns, width, off, du=0.0004, dv=0.0004, name=name,
                         color_fn=col, ident="towel",
                         width_fn=lambda t, u_m: 1.0 + 0.05 * BS.noise.noise(Vector((u_m * 90, seed, 0.2))))


def cloth_field(P, N, vi, dist, half):
    """Крестовая полоса полотенца на прикладе (на месте выпуклой обмотки Facepunch): вафля, складки, кромки."""
    ax_ = np.abs(N)
    side = ax_[:, 0] >= np.maximum(ax_[:, 1], ax_[:, 2])
    a = np.where(side, P[:, 1], P[:, 0])
    b = P[:, 2]
    u, v = (a + b) / np.sqrt(2), (a - b) / np.sqrt(2)
    h, w = FD.towel_relief(u, v, dist, 5.0)
    e = dist / half
    cw, cs, cd = FD.lin("CFC6B4"), FD.lin("8E3A30"), FD.lin("9C927E")
    col = cw + (cd - cw) * (0.35 * NN.smooth((NN.fbm(P * 90, 3, 92) - 0.5) * 3))[:, None]
    stripe = NN.smooth((e - 0.62) / 0.06) * NN.smooth((0.88 - e) / 0.06)
    fade = 0.6 + 0.3 * NN.fbm(P * 60, 2, 93)
    col = col * (1 - (stripe * fade)[:, None]) + cs * (stripe * fade)[:, None]
    col = col * (1 - 0.25 * (1 - w))[:, None]
    col = col * (1 - 0.35 * NN.smooth((1.2 * MM - dist) / (1.2 * MM)))[:, None]
    n = len(P)
    return h, col, np.full(n, FD.IDS["towel"]), np.stack([np.zeros(n), np.zeros(n), w], -1)


def build_stock(low, rng):
    isl = low["isl"]
    allf = {p.index for p in low.data.polygons}
    band = BS.cloth_faces(low, {1})
    butt = face_set(low, lambda p, i: BS.is_butt_end(i, p.center, p.normal))
    wood_f = face_set(low, lambda p, i: i in (1, 2, 3)) - band - butt
    hp = [field_copy(low, wood_f, "hp_wood", 0.6 * MM, FD.stock_field)]
    # полоса ткани: расстояние до её края — «поперёк полосы»
    bo = copy_faces(low, band, "tmp_band", keep_custom=False)
    bm = bmesh.new()
    bm.from_mesh(bo.data)
    edge_pts = []
    for e in bm.edges:
        if len(e.link_faces) == 1:
            a, b = np.array(e.verts[0].co), np.array(e.verts[1].co)
            edge_pts += [a + (b - a) * t for t in np.linspace(0, 1, 12)]
    bm.free()
    bpy.data.objects.remove(bo)
    E = np.array(edge_pts)

    def band_fn(P, N, vi):
        d = np.full(len(P), 1.0)
        for k in range(0, len(E), 2000):
            d = np.minimum(d, np.min(np.linalg.norm(P[:, None, :] - E[None, k:k + 2000], axis=2), axis=1))
        half = max(np.percentile(d, 97), 0.004)
        return cloth_field(P, N, vi, d, half)
    hp.append(field_copy(low, band, "hp_band", 0.45 * MM, band_fn))
    # железо: спусковая скоба и уголки затыльника; шурупы — как в v1
    iron_f = face_set(low, lambda p, i: i in (4, 5, 6))
    hp.append(field_copy(low, iron_f, "hp_iron", 0.5 * MM, lambda P, N, vi: FD.iron_field(P, N)))
    hp += BS.plate_screws(low, BS.BUTT_PLATES, "hp_screw")
    # затыльник — дерево в торец (v1, кольца крупнее не меняю до кадров)
    cen = [p.center for p in low.data.polygons if p.index in butt]
    c0 = sum(cen, Vector()) / len(cen)
    hp.append(BS.end_grain(low, BS.is_butt_end, "hp_stock_butt", (c0.x + 0.003, c0.y - 0.012, c0.z), "wood", 53,
                           cracks=((1.2, 0.03), (3.6, 0.02))))
    hp.append(BS.resin_drop(hp[0], Vector(tuple(FD.KNOT))))
    # обмотка шейки: вафельное полотенце, конец на гвоздике
    W = {2}
    bvh = BS.round_bvh(low, lambda i, c, n: i in (W | {3}))
    verts = [low.data.vertices[v].co.copy() for p in BS.polys_of(low, W) for v in p.vertices]
    ax = BS.Axis(verts, (0, 0, 1), (1, 0, 0)).refine(bvh)
    tw = towel_wrap_v2(bvh, ax, -0.238, -0.196, math.radians(200), 3.4, 0.021, "hp_towel_wrist", 4.2)
    hp.append(tw)
    end_th = math.radians(200) + 2 * math.pi * 3.4 - 0.25
    hit, d, _ = BS.surf(BS.join_bvh([tw]), ax, -0.196, end_th)
    if hit is not None:
        hp.append(BS.forged_nail(hit + d * 0.0003, d, 0.0021, "hp_nail_towel"))
    hp = [o for o in hp if o is not None]
    for o in hp:
        if o.data.color_attributes.get("fb") is None:
            ensure_attrs(o)
    return allf, hp, 0.006


def build_frame(low, rng):
    faces = face_set(low, lambda p, i: i in FD.FRAME_ISL)
    hp = [field_copy(low, faces, "hp_frame", 0.35 * MM, FD.frame_field)]
    top = BS.bvh_of(low, {16})
    hit, n, _, _ = top.ray_cast(Vector((0.0, 0.2, -0.108)), Vector((0, -1, 0)), 0.4)
    if hit is not None:   # лист на верхней планке — как в v1.3 (проверен в игре)
        for o in BS.leaf_mesh(hit + n * 0.0003, n, Vector((0.0, 0, 1)), 0.022, "hp_leaf_top", conform=BS.bvh_of(low)):
            ensure_attrs(o)
            hp.append(o)
    return faces, hp, 0.004


GROUPS = {"barrel": [("tubes", build_tubes)], "stock": [("all", build_stock)], "main": [("frame", build_frame)]}
LOOKS = {
    ("barrel", "tubes"): [((0.30, 0.04, 0.27), (0.037, 0.0, 0.27), 40), ((0.06, 0.16, 0.42), (0.037, 0.0, 0.38), 50),
                          ((0.10, 0.03, 0.17), (0.037, 0.0, 0.20), 50)],
    ("stock", "all"): [((0.42, -0.08, -0.33), (0.0, -0.10, -0.33), 45), ((-0.42, -0.08, -0.33), (0.0, -0.10, -0.33), 45),
                       ((0.12, -0.03, -0.40), (0.02, -0.11, -0.42), 50)],
    ("main", "frame"): [((0.26, 0.05, -0.02), (0.0, -0.035, -0.02), 40), ((0.04, 0.30, -0.02), (0.0, -0.01, -0.02), 40),
                        ((0.08, 0.05, -0.16), (0.0, -0.03, -0.10), 45)],
}


# ---------------------------------------------------------------- запекание
def hp_material():
    m = bpy.data.materials.new("hp")
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL")
    bs = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    bs.inputs["Base Color"].default_value = (0.5, 0.5, 0.5, 1)
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
                    if [d for d in prefs.devices if d.type == kind]:
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
    sc.world.light_settings.distance = 0.012   # AO: 1.2 см — только своё мелкое


def new_img(name, size):
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    return img


def pixels(img):
    size = img.size[0]
    px = np.empty(size * size * 4, np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(size, size, 4)[..., :3]


def save_png(arr, path):
    size = arr.shape[0]
    out = bpy.data.images.new(path.stem, size, size, alpha=False)
    out.colorspace_settings.name = "Non-Color"
    buf = np.ones((size, size, 4), np.float32)
    buf[..., :3] = np.clip(arr, 0, 1)
    out.pixels.foreach_set(buf.ravel())
    out.filepath_raw = str(path)
    out.file_format = "PNG"
    out.save()
    bpy.data.images.remove(out)
    log("  ->", path.name)


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
    for o in hp or []:
        o.select_set(True)
    ob = target["ob"]
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    t0 = time.time()
    bpy.ops.object.bake(type=kind, use_clear=True, margin=margin)
    log(f"  bake {name} {kind} {space if kind == 'NORMAL' else ''} {time.time() - t0:.0f} с")
    return img


def unit(a):
    return a / np.maximum(np.linalg.norm(a, axis=-1, keepdims=True), 1e-8)


def rotate_to(v, a, b):
    """Поворот векторов v на угол a -> b (по пикселям, Родриг)."""
    k = np.cross(a, b)
    s = np.linalg.norm(k, axis=-1, keepdims=True)
    c = (a * b).sum(-1, keepdims=True)
    k = k / np.maximum(s, 1e-8)
    return v * c + np.cross(k, v) * s + k * (k * v).sum(-1, keepdims=True) * (1 - c)


def bake_group(low, faces, hp, size, extr, tag, mat):
    for o in hp:
        o.data.materials.clear()
        o.data.materials.append(mat[0])
    flat = make_target(copy_faces(low, faces, f"flat_{tag}", keep_custom=False))
    smooth = make_target(copy_faces(low, faces, f"smooth_{tag}"))
    res = {}
    set_pass(mat, "view")
    n_full = unit(pixels(bake_pass(flat, hp, "NORMAL", size, f"{tag}_nfull", extr, space="OBJECT")) * 2 - 1)
    res["ao"] = pixels(bake_pass(flat, hp, "AO", size, f"{tag}_ao", extr, samples=64))
    for k in (*ATTRS, "cover"):
        set_pass(mat, k)
        res[k] = pixels(bake_pass(flat, hp, "EMIT", size, f"{tag}_{k}", extr, filt=0.01 if k == "idc" else 1.5))
    set_pass(mat, "view")
    n_b = unit(pixels(bake_pass(flat, None, "NORMAL", size, f"{tag}_nflat", extr, space="OBJECT")) * 2 - 1)
    n_s = unit(pixels(bake_pass(smooth, None, "NORMAL", size, f"{tag}_nsmooth", extr, space="OBJECT")) * 2 - 1)
    fb = res.pop("fb")[..., :1]
    cov = res["cover"][..., :1]
    n_rot = unit(rotate_to(n_full, n_b, n_s))
    n = unit(n_full * (1 - fb) + n_rot * fb)
    n = unit(n * cov + n_s * (1 - cov))      # лучи мимо high-poly — гладкая форма без детали
    corr = new_img(f"{tag}_ncorr", size)
    buf = np.ones((size, size, 4), np.float32)
    buf[..., :3] = n * 0.5 + 0.5
    corr.pixels.foreach_set(buf.ravel())
    smooth_t = make_target(smooth["ob"], use_map=corr)
    res["normal"] = pixels(bake_pass(smooth_t, None, "NORMAL", size, f"{tag}_ntan", extr))
    # маска текселей группы: эмиссия белым с самой low-poly
    m = bpy.data.materials.new(f"mask_{tag}")
    m.use_nodes = True
    N_, L_ = m.node_tree.nodes, m.node_tree.links
    e = N_.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (1, 1, 1, 1)
    L_.new(e.outputs[0], next(x for x in N_ if x.type == "OUTPUT_MATERIAL").inputs["Surface"])
    tx = N_.new("ShaderNodeTexImage")
    smooth["ob"].data.materials.clear()
    smooth["ob"].data.materials.append(m)
    res["mask"] = pixels(bake_pass({"ob": smooth["ob"], "mat": m, "tex": tx}, None, "EMIT", size, f"{tag}_mask",
                                   extr, filt=0.01, margin=0))
    # проверка: разброс нормали на гладких местах без детали (должна быть ровной)
    flat_area = (res["mask"][..., 0] > 0.5) & (cov[..., 0] > 0.5)
    t = res["normal"][flat_area]
    log(f"  {tag}: тексели {int(flat_area.sum())}, нормаль xy ср. {np.abs(t[:, :2] - 0.5).mean() * 255:.1f}")
    for im in list(bpy.data.images):
        if im.name.startswith(tag + "_"):
            bpy.data.images.remove(im)
    for o in (flat["ob"], smooth["ob"]):
        bpy.data.objects.remove(o)
    return res


def look(hp, part, tag):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "SINGLE"
    sc.display.shading.single_color = (0.6, 0.6, 0.6)
    sc.display.shading.show_cavity = False
    sc.render.resolution_x, sc.render.resolution_y = 1400, 900
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start = 0.002
    for k, (eye, tgt, lens) in enumerate(LOOKS.get((part, tag), [])):
        e, t = Vector(eye), Vector(tgt)
        cam.location = e
        f = (t - e).normalized()
        r = f.cross(Vector((0, 1, 0))).normalized()   # «вверх» — ось y OBJ
        u = r.cross(f)
        cam.rotation_euler = Matrix((r, u, -f)).transposed().to_euler()
        cam.data.lens = lens
        sc.render.filepath = str(OUT / f"look_{part}_{tag}_{k}.png")
        bpy.ops.render.render(write_still=True)
        log("  look", sc.render.filepath)
    bpy.data.objects.remove(cam)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 4096
    parts = argv[argv.index("--parts") + 1].split(",") if "--parts" in argv else list(GROUPS)
    OUT.mkdir(parents=True, exist_ok=True)
    for part in parts:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        random.seed(11)
        rng = random.Random(11)
        low = BS.load_low(part)
        low.hide_render = True
        for tag, builder in GROUPS[part]:
            log(part, tag, "high-poly")
            faces, hp, extr = builder(low, rng)
            log("  объекты:", {o.name: len(o.data.vertices) for o in hp})
            if "--look" in argv:
                low.hide_render = True
                look(hp, part, tag)
            if "--blend" in argv:
                bpy.ops.wm.save_as_mainfile(filepath=str(OUT / f"highpoly_{part}_{tag}.blend"))
            if "--nobake" in argv or "--look" in argv:
                continue
            setup_cycles("--gpu" in argv)
            res = bake_group(low, faces, hp, size, extr, f"{part}_{tag}", hp_material())
            for k, arr in res.items():
                save_png(arr, OUT / f"{part}_{tag}_{k}.png")
            for o in hp:
                bpy.data.objects.remove(o)
    log("done")


if __name__ == "__main__":
    main()
