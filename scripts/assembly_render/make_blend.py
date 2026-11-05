"""在 Blender 里生成「机器人头装配.blend」：模块分组、中文名、螺丝按规格上色、每一步一个集合、螺丝拧入动画。

blender -b --factory-startup --python scripts/assembly_render/make_blend.py
"""
import json, os
import bpy
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))
OBJ = f'{ROOT}/upstream/Head_α2.0.33/Printing and Assembly/Reference Assembly (Open with Microsoft 3D Viewer or Blender).obj'
META = json.load(open(f'{ROOT}/outputs/assembly/meta.json'))
OUT = f'{ROOT}/outputs/assembly/机器人头装配.blend'
EXPLODE = 14.0  # mm

# ---------- 清空场景、单位 mm ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.unit_settings.system = 'METRIC'
sc.unit_settings.scale_length = 0.001
sc.unit_settings.length_unit = 'MILLIMETERS'

bpy.ops.wm.obj_import(filepath=OBJ, global_scale=1000.0, forward_axis='Y', up_axis='Z',
                      use_split_objects=False, use_split_groups=True)
objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
print('imported', len(objs))

# ---------- 按质心匹配到 meta ----------
def centroid(o):
    vs = o.data.vertices
    s = Vector((0, 0, 0))
    for v in vs:
        s += o.matrix_world @ v.co
    return s / max(len(vs), 1)

metas = META['objs']
used = set()
match = {}
for o in objs:
    c = centroid(o)
    best, bd = None, 1e9
    for m in metas:
        if m['gi'] in used:
            continue
        d = (Vector(m['c']) - c).length
        if d < bd:
            best, bd = m, d
    if best and bd < 2.0:
        used.add(best['gi']); match[o.name] = best
print('matched', len(match), 'of', len(objs))

# ---------- 材质 ----------
SCREW_C = {'M2': (0.96, 0.55, 0.12), 'M2.5': (0.62, 0.38, 0.85), 'M3': (0.86, 0.22, 0.22),
           'M4': (0.62, 0.10, 0.18), 'S3': (0.10, 0.62, 0.45), 'S4': (0.05, 0.45, 0.55)}
PART_C = {
    '上颌座': (0.55, 0.70, 0.92), '下颌座': (0.45, 0.62, 0.90), '头骨框架': (0.90, 0.89, 0.85), '颧骨': (0.80, 0.86, 0.72),
    'MG90S': (0.22, 0.24, 0.28), 'MG90S(眼)': (0.22, 0.24, 0.28), 'MG996R': (0.20, 0.27, 0.40), 'MG996R圆舵盘': (0.97, 0.97, 0.97),
    '眼球': (0.98, 0.98, 0.98), '牙齿/牙龈/舌头': (0.95, 0.80, 0.82), 'M4热熔螺母': (0.85, 0.66, 0.25),
    'M5平垫': (0.75, 0.75, 0.78), 'M4平垫': (0.75, 0.75, 0.78), '软眉毛TPU': (0.35, 0.30, 0.28),
}
MODULE_C = {'00 头骨 外壳 颧骨': (0.90, 0.89, 0.85), '01 眼部机构': (0.72, 0.76, 0.86), '02 眉毛机构': (0.86, 0.80, 0.68),
            '03 嘴部 结构': (0.55, 0.70, 0.92), '04 嘴部 嘴唇连杆': (0.55, 0.82, 0.58), '05 牙齿 舌头': (0.95, 0.80, 0.82)}
_mats = {}


def mat(key, rgb):
    if key in _mats:
        return _mats[key]
    m = bpy.data.materials.new(key)
    m.diffuse_color = (*rgb, 1.0)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*rgb, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.55
    if key.startswith('螺丝'):
        bsdf.inputs['Metallic'].default_value = 0.6
    _mats[key] = m
    return m


# ---------- 集合 ----------
def coll(name, parent=None):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    p = parent or sc.collection
    if c.name not in p.children:
        p.children.link(c)
    return c


mods = {}
scr_root = coll('06 螺丝（按规格）')
steps_root = coll('步骤（Ctrl+点勾选框 = 只看这一步）')
step_colls = {n: coll(n, steps_root) for n in META['step_order']}

for o in objs:
    m = match.get(o.name)
    if not m:
        continue
    o.name = m['cn']
    o.data.name = m['cn']
    for c in list(o.users_collection):
        c.objects.unlink(o)
    if 'screw' in m:
        sub = coll('螺丝 ' + m['screw'], scr_root)
        sub.objects.link(o)
        o.data.materials.clear(); o.data.materials.append(mat('螺丝 ' + m['spec'], SCREW_C[m['spec']]))
        o['螺丝规格'] = m['screw']
    else:
        mods.setdefault(m['module'], coll(m['module'])).objects.link(o)
        base = m['cn'].split(' #')[0]
        rgb = PART_C.get(base, MODULE_C.get(m['module'], (0.8, 0.8, 0.8)))
        o.data.materials.clear(); o.data.materials.append(mat(base if base in PART_C else m['module'], rgb))
    o['原名'] = m['name']
    for st in m['steps']:
        step_colls[st].objects.link(o)

# 集合排序：模块在前
for name in sorted(mods):
    sc.collection.children.unlink(mods[name]); sc.collection.children.link(mods[name])
for c in (scr_root, steps_root):
    sc.collection.children.unlink(c); sc.collection.children.link(c)

# 原点放到零件中心，方便旋转、聚焦
bpy.ops.object.select_all(action='DESELECT')
for o in objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
bpy.ops.object.select_all(action='DESELECT')

# ---------- 螺丝拧入动画：第 1 帧拔出 14 mm，第 48 帧装好 ----------
sc.frame_start, sc.frame_end = 1, 60
for o in objs:
    m = match.get(o.name) or next((x for x in metas if x['cn'] == o.name), None)
    if not m or 'axis' not in m:
        continue
    a = Vector(m['axis'])
    home = o.location.copy()
    o.location = home - a * EXPLODE
    o.keyframe_insert('location', frame=1)
    o.location = home
    o.keyframe_insert('location', frame=48)
sc.frame_set(60)

# 步骤集合默认不参与显示（需要时 Ctrl+点勾选框单独看）
vl = bpy.context.view_layer


def find_lc(lc, name):
    if lc.collection.name == name:
        return lc
    for ch in lc.children:
        r = find_lc(ch, name)
        if r:
            return r


find_lc(vl.layer_collection, steps_root.name).exclude = True

# 灯光（渲染用；视口用 Solid 不需要）
sun = bpy.data.objects.new('太阳光', bpy.data.lights.new('太阳光', 'SUN'))
sun.data.energy = 3
sun.rotation_euler = (0.8, 0.2, 0.6)
sc.collection.objects.link(sun)

# 视口：Solid + 材质颜色 + 凹槽阴影，镜头范围按 mm
for scr in bpy.data.screens:
    for area in scr.areas:
        if area.type != 'VIEW_3D':
            continue
        for sp in area.spaces:
            if sp.type != 'VIEW_3D':
                continue
            sp.shading.type = 'SOLID'
            sp.shading.color_type = 'MATERIAL'
            sp.shading.show_cavity = True
            sp.shading.show_object_outline = True
            sp.clip_start = 0.5
            sp.clip_end = 20000
            sp.overlay.show_floor = False
            r3 = sp.region_3d
            if r3:
                r3.view_location = (0, -10, 0)
                r3.view_distance = 420

bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('saved', OUT)
