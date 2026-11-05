"""颈部支架（底座 + 两根斜立柱），立柱顶面贴合头骨框架后下方的底面横梁，用扎带固定。

blender -b --factory-startup --python scripts/neck_stand/make_stand.py

坐标沿用装配模型（mm，z 向上，y 负 = 脸前方）。设计依据：
- 下巴绕 MG996R 轴 (y=-2, z=-41) 转动，张嘴 45° 时扫到最低 z=-131、最靠后 y=40.9 → 立柱从 y=50 开始，底板顶面 z=-142
- 头骨框架后下方的底面横梁：y 50→90 时从 x≈33 斜到 x≈22，z 从 -38 升到 -31（outputs/neck_stand/hmap.npz）
- 整头约 870 g，重心 (x,y,z)≈(-1,-9,-7)，底板前缘到 y=-105，不会往前倒
"""
import os
import bmesh
import bpy
import numpy as np
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))
OUT_DIR = f'{ROOT}/outputs/neck_stand'
d = np.load(f'{OUT_DIR}/hmap.npz')
XS, YS, H = d['xs'], d['ys'], d['H']

PLATE_TOP = -142.0
PLATE_T = 6.0
CLEAR = 0.5           # 立柱顶面和框架底面的间隙
RAIL_W = 12.0         # 立柱厚度（垂直于中心线）
CENTER = [(33.0, 50.0), (28.0, 70.0), (22.0, 90.0)]  # 右侧立柱中心线 (x, y)，左侧镜像

bpy.ops.wm.read_factory_settings(use_empty=True)


def box(name, x0, x1, y0, y1, z0, z1):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector(((x0 + x1) / 2 + v.co.x * (x1 - x0), (y0 + y1) / 2 + v.co.y * (y1 - y0), (z0 + z1) / 2 + v.co.z * (z1 - z0)))
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o); return o


def prism(name, quad, ztop_fn, zbot):
    """quad: 4 个 (x,y) 逆时针；顶面每个角 z = ztop_fn(x,y)（平面，所以顶面是平的四边形）"""
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bot = [bm.verts.new((x, y, zbot)) for x, y in quad]
    top = [bm.verts.new((x, y, ztop_fn(x, y))) for x, y in quad]
    bm.faces.new(bot[::-1]); bm.faces.new(top)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o); return o


def strip_quads(center, w):
    qs = []
    segs = list(zip(center[:-1], center[1:]))
    for k, ((x0, y0), (x1, y1)) in enumerate(segs):
        t = np.array([x1 - x0, y1 - y0]); t /= np.linalg.norm(t); n = np.array([-t[1], t[0]]) * w / 2
        # 只在两段相接处多伸出 w/2 保证重叠，两头不伸（前端不能再往前，下巴会扫到 y≈41）
        a = np.array([x0, y0]) - (t * w / 2 if k > 0 else 0)
        b = np.array([x1, y1]) + (t * w / 2 if k < len(segs) - 1 else 0)
        qs.append([tuple(a - n), tuple(b - n), tuple(b + n), tuple(a + n)])
    return qs


def inside_quad(q, x, y):
    s = []
    for i in range(4):
        (x0, y0), (x1, y1) = q[i], q[(i + 1) % 4]
        s.append((x1 - x0) * (y - y0) - (y1 - y0) * (x - x0))
    return all(v >= 0 for v in s) or all(v <= 0 for v in s)


def fit_top(quads):
    """立柱范围内的框架底面格子 → 拟合平面 z=a+bx+cy，再整体往下挪到最小间隙 = CLEAR"""
    pts = []
    for i, x in enumerate(XS):
        for j, y in enumerate(YS):
            h = H[i, j]
            if np.isnan(h) or h > -28 or h < -45:   # 开口或别的零件，不算
                continue
            if any(inside_quad(q, x, y) for q in quads):
                pts.append((x, y, h))
    P = np.array(pts)
    A = np.c_[np.ones(len(P)), P[:, 0], P[:, 1]]
    coef, *_ = np.linalg.lstsq(A, P[:, 2], rcond=None)
    gap = P[:, 2] - A @ coef
    coef[0] += gap.min() - CLEAR
    gap = P[:, 2] - A @ coef
    print('top plane coef', coef.round(4), 'cells', len(P), 'gap min/mean/max', gap.min().round(2), gap.mean().round(2), gap.max().round(2))
    return lambda x, y: coef[0] + coef[1] * x + coef[2] * y, coef


parts = []
plate = box('plate', -70, 70, -105, 95, PLATE_TOP - PLATE_T, PLATE_TOP)
tops = {}
for side in (1, -1):
    C = [(side * x, y) for x, y in CENTER]
    qs = strip_quads(C, RAIL_W)
    if side < 0:
        qs = [q[::-1] for q in qs]
    fs = []
    for k, q in enumerate(qs):
        f, coef = fit_top([q])   # 每段单独拟合一个平面，贴得更紧
        fs.append(f)
        parts.append(prism(f'rail{side}_{k}', q, f, PLATE_TOP - 1))
    tops[side] = fs[-1]   # y=80 在第二段

# 加强：后横墙（上面留空走线）和前下横梁（在下巴扫过范围之后 y≥50）
parts.append(box('rear_wall', -24, 24, 84, 90, PLATE_TOP - 1, -75))
parts.append(box('front_beam', -32, 32, 50, 56, PLATE_TOP - 1, PLATE_TOP + 25))

# 合并
bpy.context.view_layer.objects.active = plate
for o in parts:
    m = plate.modifiers.new('u', 'BOOLEAN'); m.operation = 'UNION'; m.object = o; m.solver = 'EXACT'
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(o)

# 扎带孔：每根立柱在 y≈80 处横穿一个 5×3.5 mm 的孔，孔顶离立柱顶面 4 mm
for side in (1, -1):
    xc = side * 25.6
    zt = tops[side](xc, 80.0)
    t = box(f'tie{side}', min(xc - 10, xc + 10), max(xc - 10, xc + 10), 77.5, 82.5, zt - 7.5, zt - 4.0)
    m = plate.modifiers.new('d', 'BOOLEAN'); m.operation = 'DIFFERENCE'; m.object = t; m.solver = 'EXACT'
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(t)

# 底面倒角之类不做；导出两份：装配坐标（给渲染核对）+ 打印坐标（底面 z=0）
me = plate.data
V = np.array([v.co[:] for v in me.vertices])
F = []
bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.triangulate(bm, faces=bm.faces)
for fc in bm.faces:
    F.append([v.index for v in fc.verts])
bm.free()
np.savez(f'{OUT_DIR}/stand_asm.npz', V=V, F=np.array(F))
print('bbox', V.min(0).round(1), V.max(0).round(1), 'manifold check below')

bm = bmesh.new(); bm.from_mesh(me)
nm = [e for e in bm.edges if not e.is_manifold]
print('non-manifold edges', len(nm)); bm.free()

plate.location.z = -(PLATE_TOP - PLATE_T)
bpy.ops.object.select_all(action='DESELECT'); plate.select_set(True)
bpy.context.view_layer.objects.active = plate
bpy.ops.object.transform_apply(location=True)
os.makedirs(OUT_DIR, exist_ok=True)
bpy.ops.wm.stl_export(filepath=f'{OUT_DIR}/NeckStand_颈部支架_x1.stl', export_selected_objects=True, ascii_format=False, global_scale=1.0)
print('saved')
