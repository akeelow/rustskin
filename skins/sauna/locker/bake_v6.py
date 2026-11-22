"""Sauna Changing Locker v6: high-poly поверх шкафчика и запекание на его развёртку (4096; экспорт 2048 — texture_v6.py).

План: PLAN_v6.md. Каждая деталь — геометрия из fields_v6.py; маски цвета — атрибуты вершин той же геометрии.

Нормаль. Панели шкафчика в игре освещены ровно (жёсткие рёбра; нормали в OBJ испорчены — PLAN_v6.md, 1.5), поэтому
печём прямо в касательном пространстве ПЛОСКИХ граней low-poly (без переноса на сглаженную модель, как у полока).

Общие развёртки (PLAN_v6.md, 1.6): high-poly строится на ОДНОЙ копии, цель запекания — только грани этой копии
(по uv/v6/faces.json), остальные копии получают те же тексели. AO общих островов — только от разрешённых соседей.

Запуск (из корня репозитория):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/locker/bake_v6.py -- \
      [--groups door,frame,side,back,wall,floor,ceiling,shelfA,shelfB] [--size 4096] [--gpu] [--blend] [--nobake]
Пишет bake/v6/{normal,ao,m1,m2,m3,idc,pos,cover,mask}.png; с --groups — сливает в прошлое запекание.
"""
import json
import sys
import time
from pathlib import Path

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "bake" / "v6"
sys.path.insert(0, str(HERE))
import fields_v6 as FV  # noqa: E402

OBJ = HERE / "originals" / "locker.obj"

ATTRS = ("m1", "m2", "m3", "idc", "pos")
STEP = FV.STEP


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


# ---------------------------------------------------------------- low-poly из OBJ (номера граней = номера в OBJ)
def load_obj(path):
    """Как parts.load (parts.py тянет PIL, которого в Python Blender нет)."""
    Vv, Tt, Ff = [], [], []
    for line in open(path, encoding="utf8", errors="replace"):
        if line.startswith("v "):
            Vv.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("vt "):
            Tt.append([float(x) for x in line.split()[1:3]])
        elif line.startswith("f "):
            idx = [p.split("/") for p in line.split()[1:]]
            Ff.append(([int(p[0]) - 1 for p in idx], [int(p[1]) - 1 for p in idx], None))
    return np.array(Vv), np.array(Tt), None, Ff


V, T, N, F = load_obj(OBJ)
REC = json.loads((HERE / "uv" / "v6" / "faces.json").read_text(encoding="utf8"))


def lowpoly(faces, name):
    """Плоская low-poly только из граней faces (индексы OBJ), с развёрткой."""
    verts, polys, uvs = [], [], []
    for f in faces:
        vi, ti, _ = F[f]
        base = len(verts)
        verts += [tuple(V[i]) for i in vi]
        polys.append(tuple(range(base, base + len(vi))))
        q = T[ti]
        q = q - np.floor(q.min(0) + 1e-6)          # u < 0 у копий (острова 6, 19): та же плитка 0..1
        uvs += [tuple(c) for c in q]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], polys)
    uv = me.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", np.asarray(uvs, np.float32).ravel())
    me.polygons.foreach_set("use_smooth", np.zeros(len(polys), bool))
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def pick(island, cond=lambda c, n: True):
    isl = island if isinstance(island, (tuple, list, set)) else (island,)
    return [f for f, r in enumerate(REC) if r["island"] in isl and cond(np.array(r["c"]), np.array(r["n"]))]


# ---------------------------------------------------------------- сетки из numpy
def mesh_np(name, Vv, Q, attrs, group):
    me = bpy.data.meshes.new(name)
    n, m = len(Vv), len(Q)
    me.vertices.add(n)
    me.vertices.foreach_set("co", np.asarray(Vv, np.float32).ravel())
    me.loops.add(m * 4)
    me.loops.foreach_set("vertex_index", np.asarray(Q, np.int32).ravel())
    me.polygons.add(m)
    me.polygons.foreach_set("loop_start", (np.arange(m) * 4).astype(np.int32))
    me.update(calc_edges=True)
    me.validate(verbose=False)
    for k in ATTRS:
        a = me.color_attributes.new(k, "FLOAT_COLOR", "POINT")
        buf = np.ones((n, 4), np.float32)
        buf[:, :3] = np.asarray(attrs[k], np.float32).reshape(n, 3)
        a.data.foreach_set("color", buf.ravel())
    me.polygons.foreach_set("use_smooth", np.ones(m, bool))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob["group"] = group
    return ob


def axis_range(a0, a1, margin=0.3):
    n = int(np.ceil((a1 - a0 + 2 * margin) / STEP)) + 1
    return np.linspace(a0 - margin, a1 + margin, n)


def plane(name, group, k, s, c, ra, rb, fn, base=None, margin=0.3):
    """Поле высот на плоскости x_k = c (наружу s·e_k). ra, rb — диапазоны двух других осей (по возрастанию номера).
    fn(A, B[, base]) -> Field. Сдвиг вершин на s·h вдоль оси k."""
    ia, ib = [i for i in range(3) if i != k]
    A, B = np.meshgrid(axis_range(*ra, margin), axis_range(*rb, margin))     # (nb, na)
    fl = fn(A, B) if base is None else fn(A, B, base(A, B))
    P = np.zeros(A.shape + (3,))
    P[..., ia], P[..., ib] = A, B
    P[..., k] = (c if base is None else base(A, B)) + s * fl.h
    attrs = fl.attrs(P)
    nb, na = A.shape
    ii = np.arange(na * nb).reshape(nb, na)
    Q = np.stack([ii[:-1, :-1], ii[:-1, 1:], ii[1:, 1:], ii[1:, :-1]], -1).reshape(-1, 4)
    # обход: нормаль квада = e_ia × e_ib; если смотрит не туда — разворачиваем
    e = np.zeros(3)
    e[ia], e2 = 1, np.zeros(3)
    e2[ib] = 1
    if np.cross(e, e2)[k] * s < 0:
        Q = Q[:, ::-1]
    log(f"  {name}: {na}×{nb}")
    return mesh_np(name, P.reshape(-1, 3), Q, {kk: v.reshape(-1, 3) for kk, v in attrs.items()}, group)


def const_attrs(n, mat, grain=None, tone=0.5, misc=None, edge=None, board=0, P=None):
    z = np.zeros(n)
    pos = (P - FV.POS_LO) / (FV.POS_HI - FV.POS_LO) if P is not None else np.zeros((n, 3))
    return {"m1": np.stack([z if grain is None else grain, z, z], -1), "m2": np.stack([z, z, z], -1),
            "m3": np.stack([z if edge is None else edge, z if misc is None else misc, z + tone], -1),
            "idc": np.stack([z + FV.MAT[mat] / 32.0, z + board / 16.0, z], -1), "pos": np.clip(pos, 0, 1)}


class Acc:
    def __init__(self):
        self.V, self.Q, self.A, self.n = [], [], {k: [] for k in ATTRS}, 0

    def add(self, Vv, Q, attrs):
        self.V.append(np.asarray(Vv, float))
        self.Q.append(np.asarray(Q) + self.n)
        for k in ATTRS:
            self.A[k].append(np.asarray(attrs[k], float).reshape(len(Vv), 3))
        self.n += len(Vv)

    def build(self, name, group):
        return mesh_np(name, np.concatenate(self.V), np.concatenate(self.Q),
                       {k: np.concatenate(v) for k, v in self.A.items()}, group)


def tube(C, R, seg=10, twist=0.0, ridge=0.0):
    """Трубка по ломаной C с радиусами R (как bed/bake_v2.tube; обход — нормали наружу)."""
    C = np.asarray(C, float)
    k = len(C)
    R = np.broadcast_to(np.asarray(R, float), (k,))
    Tn = np.gradient(C, axis=0)
    Tn /= np.linalg.norm(Tn, axis=1, keepdims=True) + 1e-9
    up = np.where(np.abs(Tn[:, 2:3]) > 0.9, np.array([[1.0, 0, 0]]), np.array([[0, 0, 1.0]]))
    B1 = np.cross(Tn, up)
    B1 /= np.linalg.norm(B1, axis=1, keepdims=True)
    B2 = np.cross(Tn, B1)
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    ph = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    rid = (np.sin(3 * ph[None, :] + (s[:, None] / twist) * 2 * np.pi) * 0.5 + 0.5) if twist else np.zeros((k, seg))
    rr = R[:, None] * (1 + ridge * (rid - 0.5) * 2)
    Vv = C[:, None, :] + rr[..., None] * (np.cos(ph)[None, :, None] * B1[:, None, :] + np.sin(ph)[None, :, None] * B2[:, None, :])
    ii = np.arange(k * seg).reshape(k, seg)
    Q = np.stack([ii[:-1], np.roll(ii[:-1], -1, 1), np.roll(ii[1:], -1, 1), ii[1:]], -1).reshape(-1, 4)
    return Vv.reshape(-1, 3), Q, rid.reshape(-1)


# ---------------------------------------------------------------- части high-poly
def door_polys():
    return [V[F[f][0]] for f in pick(67, lambda c, n: n[2] > 0.1)]


def build_door():
    polys = door_polys()
    base = lambda A, B: np.where(np.isnan(z := FV.faces_base(A, B, polys, 2)), 26.0, z)
    return [plane("hp_door", "door", 2, 1, 0.0, FV.DOOR_X, FV.DOOR_Y, FV.door_front, base=base)]


def build_frame():
    x0, x1 = FV.FRAME_X
    ox0, ox1, oy0, oy1 = FV.FRAME_OPEN
    rects = (((x0, ox0), (0.0, 223.85)), ((ox1, x1), (0.0, 223.85)), ((ox0, ox1), (oy1, 223.85)), ((ox0, ox1), (0.0, oy0)))
    out = []
    for i, (ra, rb) in enumerate(rects):
        out.append(plane(f"hp_frame_{i}", "frame", 2, 1, 25.83, ra, rb, FV.frame_front, margin=0.3 if i < 2 else 0.0))
    return out


def build_side():
    # x = −89.94, наружу −x; оси: a = y, b = z
    return [plane("hp_side", "side", 0, -1, -89.94, FV.SIDE_Y, FV.SIDE_Z, lambda Y, Z: FV.side_panel(Z, Y))]


def build_back():
    out = [plane("hp_back", "back", 2, 1, FV.NICHE_Z_BACK, FV.NICHE_X, FV.NICHE_Y, FV.niche_back)]
    # полотенце: два конца разной длины через колышек, у каждого — бахрома
    acc = Acc()
    for (Vt, Qt, mk, fringe) in FV.towel_mesh():
        a = const_attrs(len(Vt), "towel", grain=mk["fold"], misc=mk["stripe"], edge=mk["stitch"], tone=0.5, P=Vt)
        acc.add(Vt, Qt, a)
        for C in fringe:
            Vf, Qf, rid = tube(C, 0.22, seg=6, twist=0.7, ridge=0.25)
            acc.add(Vf, Qf, const_attrs(len(Vf), "towel", grain=rid, edge=np.ones(len(Vf)), P=Vf))
    out.append(acc.build("hp_towel", "back"))
    # веник
    vp = FV.venik_parts()
    acc = Acc()
    for (kind, C, R, tw) in vp["tubes"]:
        Rr = np.broadcast_to(np.asarray(R, float), (len(C),))
        Vf, Qf, rid = tube(C, Rr, seg=8, twist=tw, ridge=0.2 if tw else 0.0)
        acc.add(Vf, Qf, const_attrs(len(Vf), kind, grain=rid, P=Vf))
    rng = np.random.default_rng(552)
    for (xl, yl, zl, ang, L, tilt) in vp["leaves"]:
        x, y, h, vein = FV.leaf_grid(L, rng)
        ca, sa = np.cos(ang), np.sin(ang)
        Pp = np.stack([xl + x * ca - y * sa, yl + x * sa + y * ca, zl + h + tilt * (x - L / 2)], -1)
        nu, nv = x.shape
        ii = np.arange(nu * nv).reshape(nu, nv)
        Q = np.stack([ii[:-1, :-1], ii[1:, :-1], ii[1:, 1:], ii[:-1, 1:]], -1).reshape(-1, 4)
        acc.add(Pp.reshape(-1, 3), Q, const_attrs(nu * nv, "leaf", grain=vein.ravel(), tone=rng.random(), P=Pp.reshape(-1, 3)))
    out.append(acc.build("hp_venik", "back"))
    return out


def build_wall():
    # правая стенка левой ниши: x = −30.82, наружу −x; a = y, b = z
    out = [plane("hp_wall", "wall", 0, -1, -30.82, FV.NICHE_Y, FV.WALL_Z, lambda Y, Z: FV.niche_wall(Z, Y))]
    # уступы у спинки и у рамы (та же развёртка): плоскости x = −36.74 (наружу −x)
    out.append(plane("hp_wall_lip", "wall", 0, -1, -36.74, FV.NICHE_Y, (21.42, 25.83), lambda Y, Z: FV.niche_wall(Z, Y), margin=0.15))
    out.append(plane("hp_wall_step", "wall", 0, -1, -36.74, FV.NICHE_Y, (-27.64, -24.83), lambda Y, Z: FV.niche_wall(Z, Y), margin=0.15))
    # полоса у спинки, смотрит вперёд: z = −24.83, x −36.74..−30.82
    out.append(plane("hp_wall_flange", "wall", 2, 1, -24.83, (-36.74, -30.82), FV.NICHE_Y,
                     lambda X, Y: FV.niche_wall(X + 60.0, Y), margin=0.15))
    return out


def build_occluders():
    """Только для AO спинки, пола, потолка и полок: левая стенка ниши (зеркало правой) — та же геометрия."""
    src = [o for o in bpy.data.objects if o.get("group") == "wall" and o.name == "hp_wall"]
    out = []
    for o in src:
        me = o.data.copy()
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        co[:, 0] = (-89.10 - 30.82) - co[:, 0]
        me.vertices.foreach_set("co", co.ravel())
        me.update()
        ob = bpy.data.objects.new("occ_wall_left", me)
        bpy.context.scene.collection.objects.link(ob)
        ob["group"] = "occ"
        out.append(ob)
    return out


def build_floor():
    # y = 15.45, наружу +y; a = x, b = z
    return [plane("hp_floor", "floor", 1, 1, 15.45, (-89.10, -30.82), (-27.64, 25.83), FV.niche_floor, margin=0.15)]


def build_ceiling():
    return [plane("hp_ceiling", "ceiling", 1, -1, 217.45, (-89.10, -30.82), (-27.64, 25.83), FV.niche_ceiling, margin=0.15)]


def build_shelf(key):
    y0, y1 = FV.SHELF_Y[key]
    top = plane(f"hp_shelf{key}", f"shelf{key}", 1, 1, y1, FV.SHELF_X, FV.SHELF_Z, lambda X, Z: FV.shelf_top(X, Z, key))
    edge = plane(f"hp_shelf{key}_edge", f"shelf{key}", 2, 1, FV.SHELF_Z[1], FV.SHELF_X, (y0, y1),
                 lambda X, Y: FV.shelf_edge(X, Y, y0, y1), margin=0.1)
    return [top, edge]


def build_shelf_c():
    polys = [V[F[f][0]] for f in pick(30) if REC[f]["piece"] == 4 and REC[f]["n"][1] > 0.5]

    def base(X, Z):
        b = FV.faces_base(X, Z, polys, 1)
        return np.where(np.isnan(b), 47.0, b)
    top = plane("hp_shelfC", "shelfC", 1, 1, 0.0, FV.SHELF_X, FV.SHELF_Z, FV.shelf_c_top, base=base)
    edge = plane("hp_shelfC_edge", "shelfC", 2, 1, FV.SHELF_Z[1], FV.SHELF_X, (43.6, 49.2), FV.shelf_c_edge, margin=0.1)
    return [top, edge]


# группа: (части, грани-цели, вытяжка лучей см, какие ещё группы видны для AO)
LEFT = lambda c, n: c[0] < -29.95
GROUPS = {
    "door": (build_door, lambda: pick(67), 2.5, ()),
    "frame": (build_frame, lambda: pick(4, lambda c, n: -90 < c[0] < -29.9 and n[2] > 0.5), 1.5, ("side",)),
    "side": (build_side, lambda: pick(5, lambda c, n: c[0] < -89.0), 3.0, ()),
    "back": (build_back, lambda: pick(2, LEFT), 9.0, ("wall", "occ", "floor", "ceiling", "shelfA", "shelfB")),
    "wall": (build_wall, lambda: pick(19, lambda c, n: -37.0 < c[0] < -30.5), 1.5, ()),
    "floor": (build_floor, lambda: pick(22, LEFT), 3.5, ("back", "wall", "occ")),
    "ceiling": (build_ceiling, lambda: pick(20, LEFT), 1.5, ("back", "wall", "occ")),
    "shelfA": (lambda: build_shelf("A"), lambda: [f for f in pick((24, 26)) if REC[f]["piece"] == 9 and REC[f]["n"][1] > -0.5], 1.5,
               ("back", "wall", "occ")),
    "shelfC": (build_shelf_c, lambda: [f for f in pick((30, 32)) if REC[f]["piece"] == 4 and REC[f]["n"][1] > -0.5], 1.5,
               ("back", "wall", "occ")),
    "shelfB": (lambda: build_shelf("B"), lambda: [f for f in pick((36, 38)) if REC[f]["piece"] == 10 and REC[f]["n"][1] > -0.5], 1.5,
               ("back", "wall", "occ")),
}


# ---------------------------------------------------------------- запекание
def hp_material():
    m = bpy.data.materials.new("hp")
    m.use_nodes = True
    Nn, L = m.node_tree.nodes, m.node_tree.links
    out = next(n for n in Nn if n.type == "OUTPUT_MATERIAL")
    bs = next(n for n in Nn if n.type == "BSDF_PRINCIPLED")
    em = {}
    for k in ATTRS:
        a = Nn.new("ShaderNodeVertexColor")
        a.layer_name = k
        e = Nn.new("ShaderNodeEmission")
        L.new(a.outputs["Color"], e.inputs["Color"])
        em[k] = e
    w = Nn.new("ShaderNodeEmission")
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
    sc.world.light_settings.distance = 4.0      # AO: 4 см


def new_img(name, size):
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    return img


def save_png(size, path, arr):
    out = bpy.data.images.new(path.stem + "_out", size, size, alpha=False)
    out.colorspace_settings.name = "Non-Color"
    buf = np.ones((size, size, 4), np.float32)
    buf[..., :3] = arr
    out.pixels.foreach_set(buf.ravel())
    out.filepath_raw = str(path)
    out.file_format = "PNG"
    out.save()
    bpy.data.images.remove(out)
    log("  ->", path.name)


def bake_pass(target, hp, kind, size, name, extr, samples=1, filt=1.5, margin=4):
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
    bk.normal_space = "TANGENT"
    bk.normal_r, bk.normal_g, bk.normal_b = "POS_X", "POS_Y", "POS_Z"   # OpenGL, как Unity
    bk.margin = margin
    bk.margin_type = "EXTEND"
    sc.cycles.samples = samples
    sc.cycles.filter_width = filt
    bpy.ops.object.select_all(action="DESELECT")
    for o in hp or ():
        o.select_set(True)
    ob = target["ob"]
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    log("bake", name, kind)
    bpy.ops.object.bake(type=kind, use_clear=True, margin=margin)
    return img


def make_target(ob):
    m = bpy.data.materials.new(ob.name + "_bake")
    m.use_nodes = True
    tex = m.node_tree.nodes.new("ShaderNodeTexImage")
    ob.data.materials.clear()
    ob.data.materials.append(m)
    for attr in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission",
                 "visible_volume_scatter", "visible_shadow"):
        setattr(ob, attr, False)
    return {"ob": ob, "mat": m, "tex": tex}


def pixels(img):
    size = img.size[0]
    px = np.empty(size * size * 4, np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(size, size, 4)[..., :3]


def piece_mask(target, size, tag):
    m = bpy.data.materials.new(f"mask_{tag}")
    m.use_nodes = True
    Nn, L = m.node_tree.nodes, m.node_tree.links
    out = next(n for n in Nn if n.type == "OUTPUT_MATERIAL")
    e = Nn.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (1, 1, 1, 1)
    L.new(e.outputs[0], out.inputs["Surface"])
    tex = Nn.new("ShaderNodeTexImage")
    ob = target["ob"]
    old = list(ob.data.materials)
    ob.data.materials.clear()
    ob.data.materials.append(m)
    img = bake_pass({"ob": ob, "mat": m, "tex": tex}, None, "EMIT", size, f"{tag}_mask", 1.0, filt=0.01, margin=0)
    ob.data.materials.clear()
    for mm in old:
        ob.data.materials.append(mm)
    return pixels(img)[..., 0] > 0.5


def bake_group(tag, faces, hp, size, extr, mat, ao_visible):
    for o in hp:
        o.data.materials.clear()
        o.data.materials.append(mat[0])
    target = make_target(lowpoly(faces, f"low_{tag}"))
    res = {}
    set_pass(mat, "view")
    res["normal"] = pixels(bake_pass(target, hp, "NORMAL", size, f"{tag}_n", extr))
    hidden = [o for o in bpy.data.objects if o.get("group") not in (None, tag, *ao_visible)]
    for o in hidden:
        o.hide_render = True
    res["ao"] = pixels(bake_pass(target, hp, "AO", size, f"{tag}_ao", extr, samples=64))
    for o in hidden:
        o.hide_render = False
    for k in (*ATTRS, "cover"):
        set_pass(mat, k)
        res[k] = pixels(bake_pass(target, hp, "EMIT", size, f"{tag}_{k}", extr,
                                  filt=0.01 if k in ("idc", "pos") else 1.5))
    set_pass(mat, "view")
    mask = piece_mask(target, size, tag)
    for im in list(bpy.data.images):
        if im.name.startswith(tag + "_"):
            bpy.data.images.remove(im)
    return res, mask


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 4096
    groups = argv[argv.index("--groups") + 1].split(",") if "--groups" in argv else list(GROUPS)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    setup_cycles("--gpu" in argv)
    # high-poly всех нужных групп (и соседей для AO)
    need = set(groups)
    for g in groups:
        need |= {x for x in GROUPS[g][3] if x in GROUPS}
    hp = []
    for g in [g for g in GROUPS if g in need]:
        log("build", g)
        hp += GROUPS[g][0]()
    if need & {"back", "floor", "ceiling", "shelfA", "shelfB", "shelfC"}:
        hp += build_occluders()
    log("high-poly:", {o.name: len(o.data.vertices) for o in hp})
    if "--nobake" not in argv:
        OUT.mkdir(parents=True, exist_ok=True)
        mat = hp_material()
        result = {}
        if "--groups" in argv:
            for k in ("ao", *ATTRS, "cover", "normal", "mask"):
                path = OUT / f"{k}.png"
                if path.exists():
                    im = bpy.data.images.load(str(path))
                    im.colorspace_settings.name = "Non-Color"
                    result[k] = pixels(im).copy()
                    bpy.data.images.remove(im)
            log("merging into the previous bake:", sorted(result))
        for g in groups:
            ghp = [o for o in hp if o.get("group") == g]
            faces = GROUPS[g][1]()
            log("group", g, "faces", len(faces), "hp", [o.name for o in ghp])
            res, mask = bake_group(g, faces, ghp, size, GROUPS[g][2], mat, GROUPS[g][3])
            for k, arr in res.items():
                if k not in result:
                    result[k] = np.zeros_like(arr) + ((0.5, 0.5, 1.0) if k == "normal" else 0.0)
                result[k][mask] = arr[mask]
            result.setdefault("mask", np.zeros((size, size, 3), np.float32))
            result["mask"][mask] = 1.0
            log("group", g, "texels", int(mask.sum()))
        for k, arr in result.items():
            save_png(size, OUT / f"{k}.png", arr)
    if "--blend" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "highpoly.blend"))
    log("done")


if __name__ == "__main__":
    main()
