"""Sauna Robe v3: high-poly халата из поля высот fields_v3.py и запекание на развёртку Snow Jacket (PLAN_v3.md, §5).

Плотная копия low-poly по группам островов (рёбра ≤ --edge мм), каждая вершина сдвигается по нормали на H (мм) из
bake/v3/fields.npz (выборка по UV вершины, 2048), маски пишутся в цвет вершин. Запекание selected-to-active на
сглаженную low-poly (нормали OBJ) в касательном пространстве, плюс та же копия без рельефа (normal_base): в
texture_v3.py нормаль = рельеф − база, поэтому гранёность low-poly не запекается (как у перчаток).

Группы (лучи одной группы не ловят high-poly другой: клапаны стоят над телом на 4 мм):
  front {0} · back {3} · sleeve_l {1} · sleeve_r {2} · cuffends {11, 12} · collar {4, 10} · flaps {5, 6, 8, 9} · hem {7}

  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/snow-jacket/bake_v3.py -- \
      [--size 4096] [--edge 1.2] [--groups torso,sleeves] [--only normal,ao] [--preview] [--nobake] [--blend] [--cpu]

Пишет bake/v3/{normal,normal_base,ao,m1,m2,m3}.png (16 бит), cover = альфа (где запечено);
  m1 = (полость вафли, кант, канавка шва/строчки), m2 = (код материала / 16, подпалина, нитка), m3 = (высота (H+10)/35).
--preview: renders/v3_hp_{front,back,side}.png — серый high-poly (Workbench) до запекания.
"""
import sys
import time
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector, kdtree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))
from uv_zones import load_obj  # noqa: E402
from islands_v3 import islands  # noqa: E402

OBJ = HERE / "originals" / "jacket.snow.obj"
OUT = HERE / "bake" / "v3"
REN = HERE / "renders"
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default):
    return type(default)(ARGS[ARGS.index(name) + 1]) if name in ARGS else default


SIZE = arg("--size", 4096)
EDGE = arg("--edge", 1.0)
MM = 0.001
# Группы: лучи одной группы не ловят high-poly другой. Перёд и спина раздельно — у горловины лучи переда
# с вылетом 26 мм (под узел) залетали внутрь и ловили спину; торцы манжет отдельно от рукавов.
GROUPS = {"front": ({0}, 26.0), "back": ({3}, 12.0), "sleeve_l": ({1}, 8.0), "sleeve_r": ({2}, 8.0),
          "cuffends": ({11, 12}, 4.0), "collar": ({4, 10}, 10.0), "flaps": ({5, 6, 8, 9}, 3.0), "hem": ({7}, 8.0)}
SHRINK = {"front": 7.0, "back": 5.0, "sleeve_l": 3.0, "sleeve_r": 3.0, "cuffends": 1.0, "collar": 3.0,
          "flaps": 0.6, "hem": 2.0}   # мм, цель внутрь на время AO
AO_DIST = {"flaps": 0.0025, "cuffends": 0.003}   # м; у остальных 6 мм
T0 = time.time()


def log(*a):
    print("[%6.1fs]" % (time.time() - T0), *a, flush=True)


# ----------------------------------------------------------------- поля
FLD = np.load(OUT / "fields.npz")
FR = FLD["H"].shape[0]
FH = FLD["H"].astype(np.float32)
FM1 = np.dstack([FLD["CAV"], FLD["STRIPE"], FLD["GROOVE"]]).astype(np.float32)
FCODE = FLD["CODE"].astype(np.float32)
FM2b = np.dstack([FLD["SCORCH"], FLD["THREAD"]]).astype(np.float32)


def bilinear(a, px):
    x = np.clip(px[:, 0] - 0.5, 0, FR - 1.001)
    y = np.clip(px[:, 1] - 0.5, 0, FR - 1.001)
    x0, y0 = x.astype(int), y.astype(int)
    fx, fy = x - x0, y - y0
    if a.ndim == 3:
        fx, fy = fx[:, None], fy[:, None]
    return (a[y0, x0] * (1 - fx) * (1 - fy) + a[y0, x0 + 1] * fx * (1 - fy)
            + a[y0 + 1, x0] * (1 - fx) * fy + a[y0 + 1, x0 + 1] * fx * fy)


def nearest(a, px):
    x = np.clip(px[:, 0].astype(int), 0, FR - 1)
    y = np.clip(px[:, 1].astype(int), 0, FR - 1)
    return a[y, x]


# ----------------------------------------------------------------- low-poly
def load_low():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="Y", up_axis="Z")
    low = bpy.context.selected_objects[0]
    low.name = "low"
    me = low.data
    V, T, F = load_obj(OBJ)
    I = islands(F)
    fi = np.zeros(len(F), np.int32)
    for n, fs in enumerate(I):
        fi[fs] = n
    cen = np.array([np.mean([V[i] for i in vi], 0) for vi, _ in F])
    kd = kdtree.KDTree(len(cen))
    for i, c in enumerate(cen):
        kd.insert(c, i)
    kd.balance()
    isl = [int(fi[kd.find(p.center)[1]]) for p in me.polygons]
    att = me.attributes.new("isl", "INT", "FACE")
    att.data.foreach_set("value", isl)
    log("low:", len(me.polygons), "граней, свои нормали:", me.has_custom_normals,
        "| bbox y", round(min(v.co.y for v in me.vertices), 3), round(max(v.co.y for v in me.vertices), 3))
    return low


def face_isl(ob):
    a = ob.data.attributes["isl"]
    v = np.empty(len(a.data), np.int32)
    a.data.foreach_get("value", v)
    return v


def dense_copy(low, isls, max_edge, name):
    ob = low.copy()
    ob.data = low.data.copy()
    ob.name = name
    bpy.context.scene.collection.objects.link(ob)
    fi = face_isl(ob)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if fi[f.index] not in isls], context="FACES")
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    prev = None
    for _ in range(16):
        long_e = [e for e in bm.edges if e.calc_length() > max_edge]
        if not long_e or (prev is not None and abs(len(long_e) - prev) < 0.02 * prev):
            break
        prev = len(long_e)
        bmesh.ops.subdivide_edges(bm, edges=long_e, cuts=1, use_grid_fill=True)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    # дробление оставляет треугольники нулевой площади (130 тыс. на торсе) и вершины с нулевой нормалью: такие
    # вершины не смещаются, соседи уходят на миллиметры — в предпросмотре «осколки» перевёрнутых граней
    nf0 = len(bm.faces)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=bm.edges[:])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    log(f"{name}: вырожденных граней убрано {nf0 - len(bm.faces)}")
    el = np.array([e.calc_length() for e in bm.edges])
    log(f"{name}: рёбра медиана {np.median(el) * 1000:.2f} мм, 99 % {np.percentile(el, 99) * 1000:.2f}, "
        f"макс {el.max() * 1000:.2f}")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    ob.data.polygons.foreach_set("use_smooth", [True] * len(ob.data.polygons))
    if ob.data.has_custom_normals:
        bpy.context.view_layer.objects.active = ob
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    log(name, len(ob.data.vertices), "вершин", len(ob.data.polygons), "граней")
    return ob


def vdata(ob):
    me = ob.data
    n = len(me.vertices)
    co = np.empty(n * 3)
    nr = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    me.vertices.foreach_get("normal", nr)
    nl = len(me.loops)
    lv = np.empty(nl, np.int64)
    me.loops.foreach_get("vertex_index", lv)
    uvl = np.empty(nl * 2)
    me.uv_layers.active.data.foreach_get("uv", uvl)
    uvl = uvl.reshape(-1, 2)
    UV = np.zeros((n, 2))
    UV[lv] = uvl
    px = np.stack([UV[:, 0] * FR, (1 - UV[:, 1]) * FR], 1)
    return co.reshape(n, 3), nr.reshape(n, 3), px


def color_attr(me, name, rgb):
    a = me.color_attributes.new(name, "FLOAT_COLOR", "POINT")
    buf = np.ones((len(me.vertices), 4), np.float32)
    buf[:, :3] = rgb
    a.data.foreach_set("color", buf.ravel())


MODEL = None


def model():
    """Растр low-poly на атласе 2048 (fields_v3.model): положение, сглаженная нормаль, остров, px/мм."""
    global MODEL
    if MODEL is None:
        import fields_v3 as FV
        V, T, F, I, fi, pos, nrm, isl, pxmm = FV.model()
        cov = isl >= 0
        pos = np.nan_to_num(pos)
        # за край островов на 1 тексель — чтобы сетка доходила до шва
        isl_d = isl.copy()
        for _ in range(1):
            for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                sh = np.roll(isl_d, (dy, dx), (0, 1))
                isl_d = np.where(isl_d < 0, sh, isl_d)
        pos = FV.dilate(pos, cov, 6)
        nrm = FV.dilate(nrm, cov, 6)
        MODEL = (pos.astype(np.float32), nrm.astype(np.float32), isl_d, pxmm)
    return MODEL


def grid_mesh(name, isls):
    """Регулярная сетка в мм развёртки каждого острова (шаг EDGE): без вырожденных граней, ровно по вафле.
    Положение — по растру low-poly (плоские грани, гранёность снимает вычитание normal_base), нормаль сглажена."""
    pos, nrm, isl_d, pxmm = model()
    Vs, Ns, PXs, Fs = [], [], [], []
    off = 0
    for n in sorted(isls):
        ys, xs = np.nonzero(isl_d == n)
        step = EDGE * pxmm[n]
        gx = np.arange(xs.min(), xs.max() + 1 + step, step)
        gy = np.arange(ys.min(), ys.max() + 1 + step, step)
        GX, GY = np.meshgrid(gx, gy)
        inside = isl_d[np.clip(GY.astype(int), 0, FR - 1), np.clip(GX.astype(int), 0, FR - 1)] == n
        idx = -np.ones(GX.shape, np.int64)
        idx[inside] = np.arange(inside.sum()) + off
        a, b, c, d = idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]
        q = (a >= 0) & (b >= 0) & (c >= 0) & (d >= 0)
        # строки атласа идут вниз: обход (a, d, c), (a, c, b) даёт нормаль наружу (проверяется ниже)
        tri = np.concatenate([np.stack([a[q], d[q], c[q]], 1), np.stack([a[q], c[q], b[q]], 1)])
        px = np.stack([GX[inside], GY[inside]], 1)
        Vs.append(bilinear(pos, px + 0.5))
        Ns.append(bilinear(nrm, px + 0.5))
        PXs.append(px + 0.5)
        Fs.append(tri)
        off += inside.sum()
    V = np.concatenate(Vs)
    N = np.concatenate(Ns)
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
    PX = np.concatenate(PXs)
    Fa = np.concatenate(Fs)
    # ориентация: нормаль грани должна смотреть по сглаженной нормали
    e1 = V[Fa[:, 1]] - V[Fa[:, 0]]
    e2 = V[Fa[:, 2]] - V[Fa[:, 0]]
    fn = np.cross(e1, e2)
    flip = (fn * N[Fa].mean(1)).sum(1) < 0
    Fa[flip] = Fa[flip][:, ::-1]
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(V))
    me.vertices.foreach_set("co", V.astype(np.float32).ravel())
    me.loops.add(len(Fa) * 3)
    me.loops.foreach_set("vertex_index", Fa.astype(np.int32).ravel())
    me.polygons.add(len(Fa))
    me.polygons.foreach_set("loop_start", np.arange(0, len(Fa) * 3, 3, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(len(Fa), 3, np.int32))
    me.update()
    me.validate()
    me.polygons.foreach_set("use_smooth", [True] * len(Fa))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    log(f"{name}: {len(V)} вершин, {len(Fa)} граней (шаг {EDGE} мм), перевёрнуто при сборке {flip.sum()}")
    return ob, V, N, PX


def build_group(low, key):
    isls, _ = GROUPS[key]
    hp, co, nr, px = grid_mesh(f"hp_{key}", isls)
    H = bilinear(FH, px)
    base = hp.copy()
    base.data = hp.data.copy()
    base.name = f"base_{key}"
    bpy.context.scene.collection.objects.link(base)
    hp.data.vertices.foreach_set("co", (co + nr * (H[:, None] * MM)).astype(np.float32).ravel())
    hp.data.update()
    color_attr(hp.data, "m1", np.clip(bilinear(FM1, px), 0, 1))
    m2 = np.zeros((len(H), 3), np.float32)
    m2[:, 0] = nearest(FCODE, px) / 16.0
    m2[:, 1:] = np.clip(bilinear(FM2b, px), 0, 1)
    color_attr(hp.data, "m2", m2)
    color_attr(hp.data, "m3", np.repeat(((H + 10) / 35)[:, None], 3, 1))
    log(f"{key}: H {H.min():.1f}…{H.max():.1f} мм")
    return hp, base


# ----------------------------------------------------------------- запекание
def bake_material():
    m = bpy.data.materials.new("hp")
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL")
    bs = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    bs.inputs["Base Color"].default_value = (0.6, 0.6, 0.6, 1)
    em = {}
    for name in ("m1", "m2", "m3"):
        a = N.new("ShaderNodeVertexColor")
        a.layer_name = name
        e = N.new("ShaderNodeEmission")
        L.new(a.outputs["Color"], e.inputs["Color"])
        em[name] = e
    return m, out, bs, em


def set_pass(mat, which):
    m, out, bs, em = mat
    L = m.node_tree.links
    for l in list(out.inputs["Surface"].links):
        L.remove(l)
    L.new((bs if which == "view" else em[which]).outputs[0], out.inputs["Surface"])


def setup_cycles(scene):
    scene.render.engine = "CYCLES"
    scene.cycles.use_denoising = False
    scene.cycles.samples = 1
    scene.cycles.device = "CPU"
    if "--cpu" in ARGS:
        return
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for dt in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = dt
            prefs.get_devices()
            devs = [d for d in prefs.devices if d.type == dt]
            if devs:
                for d in prefs.devices:
                    d.use = d.type == dt
                scene.cycles.device = "GPU"
                log("Cycles:", dt, [d.name for d in devs])
                return
        except TypeError:
            continue


def low_subset(low, isls, name):
    ob = low.copy()
    ob.data = low.data.copy()
    ob.name = name
    ob.hide_render = False
    bpy.context.scene.collection.objects.link(ob)
    fi = face_isl(ob)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if fi[f.index] not in isls], context="FACES")
    bm.to_mesh(ob.data)   # свои нормали OBJ (custom split normals) bmesh сохраняет в слое данных петель
    bm.free()
    ob.data.update()
    return ob


def save_png16(name, arr, alpha=None):
    """PNG 16 бит через Blender (без PIL): arr (S, S, 3) 0…1, строки сверху вниз как в атласе."""
    size = arr.shape[0]
    im = bpy.data.images.new(name, size, size, alpha=alpha is not None, float_buffer=True)
    im.colorspace_settings.name = "Non-Color"
    buf = np.ones((size, size, 4), np.float32)
    buf[..., :3] = np.clip(arr, 0, 1)
    if alpha is not None:
        buf[..., 3] = alpha
    im.pixels[:] = buf[::-1].ravel()
    im.filepath_raw = str(OUT / f"{name}.png")
    im.file_format = "PNG"
    sc = bpy.context.scene
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "16"
    sc.render.image_settings.color_mode = "RGBA" if alpha is not None else "RGB"
    im.save_render(str(OUT / f"{name}.png"), scene=sc)
    bpy.data.images.remove(im)


def bake_all(low, built):
    scene = bpy.context.scene
    setup_cycles(scene)
    mat = bake_material()
    if scene.world is None:
        scene.world = bpy.data.worlds.new("bake")
    scene.world.light_settings.distance = 0.006
    lm = bpy.data.materials.new("bake_target")
    lm.use_nodes = True
    tex = lm.node_tree.nodes.new("ShaderNodeTexImage")
    lm.node_tree.nodes.active = tex
    allhp = [o for k in built for o in built[k]]
    for o in allhp:
        o.data.materials.clear()
        o.data.materials.append(mat[0])
    lows = {}
    for k in built:
        lg = low_subset(low, GROUPS[k][0], f"low_{k}")
        lg.data.materials.clear()
        lg.data.materials.append(lm)
        lows[k] = lg
    bk = scene.render.bake
    bk.use_selected_to_active = True
    bk.use_cage = False
    bk.target = "IMAGE_TEXTURES"
    bk.normal_space = "TANGENT"
    bk.normal_r, bk.normal_g, bk.normal_b = "POS_X", "POS_Y", "POS_Z"   # OpenGL, как в Unity
    passes = (("normal", "NORMAL", "view", 4, False), ("normal_base", "NORMAL", "view", 4, True),
              ("ao", "AO", "view", 48, False), ("m1", "EMIT", "m1", 4, False),
              ("m2", "EMIT", "m2", 1, False), ("m3", "EMIT", "m3", 4, False))
    only = arg("--only", "").split(",") if "--only" in ARGS else None
    for name, kind, shader, samples, use_base in passes:
        if only and name not in only:
            continue
        set_pass(mat, shader)
        scene.cycles.samples = samples
        scene.cycles.filter_width = 0.01 if name == "m2" else 1.5
        img = bpy.data.images.new(f"bake_{name}", SIZE, SIZE, alpha=True, float_buffer=True)
        img.colorspace_settings.name = "Non-Color"
        img.generated_color = (0, 0, 0, 0)
        partial = len(built) < len(GROUPS) and (OUT / f"{name}.png").exists()
        if partial:   # перепекаются не все группы: остальное берём из прошлого запекания
            old = bpy.data.images.load(str(OUT / f"{name}.png"))
            old.colorspace_settings.name = "Non-Color"
            img.pixels[:] = old.pixels[:]
            bpy.data.images.remove(old)
            log(f"{name}: поверх прошлого запекания")
        tex.image = img
        for gi, k in enumerate(built):
            hp, base = built[k]
            src = base if use_base else hp
            lg = lows[k]
            for o in allhp:
                o.hide_render = o is not src
            low.hide_render = True
            for l2 in lows.values():
                l2.hide_render = l2 is not lg
            ext = GROUPS[k][1]
            scene.world.light_settings.distance = AO_DIST.get(k, 0.006)
            sh = SHRINK[k] if name == "ao" else 0.0
            if sh:
                me = lg.data
                co0 = np.empty(len(me.vertices) * 3)
                nr0 = np.empty(len(me.vertices) * 3)
                me.vertices.foreach_get("co", co0)
                me.vertices.foreach_get("normal", nr0)
                me.vertices.foreach_set("co", (co0 - nr0 * sh * MM).astype(np.float32))
                me.update()
            bk.cage_extrusion = (ext + sh) * MM
            bk.max_ray_distance = (ext * 2.2 + sh) * MM
            bpy.ops.object.select_all(action="DESELECT")
            src.select_set(True)
            lg.select_set(True)
            bpy.context.view_layer.objects.active = lg
            log(f"запекание {name}, группа {k}…")
            bpy.ops.object.bake(type=kind, use_clear=(gi == 0 and not partial), margin=0)
            if sh:
                me.vertices.foreach_set("co", co0.astype(np.float32))
                me.update()
        px = np.array(img.pixels[:], np.float32).reshape(SIZE, SIZE, 4)[::-1]
        save_png16(name, px[..., :3], alpha=(px[..., 3] > 0).astype(np.float32))
        log("записано", name)
        bpy.data.images.remove(img)


# ----------------------------------------------------------------- предпросмотр high-poly
def preview(built):
    REN.mkdir(exist_ok=True)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "SINGLE"
    sc.display.shading.single_color = (0.72, 0.66, 0.56)
    sc.display.shading.show_cavity = False
    sc.render.resolution_x, sc.render.resolution_y = 1400, 1800
    for o in bpy.data.objects:
        o.hide_render = not o.name.startswith("hp_")
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = "ORTHO"
    views = {"front": ((0, 0.55, 2.0), (0, 0.55, 0), 0.75), "back": ((0, 0.55, -2.0), (0, 0.55, 0), 0.75),
             "side": ((2.0, 0.55, 0.3), (0, 0.55, 0), 0.75),
             "front_close": ((0.05, 0.52, 2.0), (0.05, 0.52, 0), 0.30),
             "neck_close": ((0.0, 0.74, 2.0), (0.0, 0.74, 0), 0.30)}
    for name, (loc, tgt, scale) in views.items():
        cam.location = loc
        d = Vector(tgt) - Vector(loc)
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        cam.data.ortho_scale = scale
        sc.render.filepath = str(REN / f"v3_hp_{name}.png")
        bpy.ops.render.render(write_still=True)
        log("предпросмотр", name)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    low = load_low()
    keys = arg("--groups", ",".join(GROUPS)).split(",")
    built = {k: build_group(low, k) for k in keys}
    if "--preview" in ARGS:
        preview(built)
    if "--blend" in ARGS:
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "highpoly.blend"))
    if "--nobake" not in ARGS and "--preview" not in ARGS:
        for o in bpy.data.objects:
            o.hide_render = False
        bake_all(low, built)
    log("готово")


if __name__ == "__main__":
    main()
