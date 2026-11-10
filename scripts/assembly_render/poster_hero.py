"""宣传海报主视觉：Blender Cycles 渲染机器人头。
用法：Blender -b outputs/assembly/机器人头装配.blend --python scripts/assembly_render/poster_hero.py -- 输出.png 宽 高 采样 [视图]
"""
import sys, math, bpy
from mathutils import Vector

a = sys.argv[sys.argv.index('--') + 1:]
OUT, W, H, SPP = a[0], int(a[1]), int(a[2]), int(a[3])
VIEW = a[4] if len(a) > 4 else 'hero'
sc = bpy.context.scene

for c in bpy.data.collections:           # .blend 里可能存着"只看某一步"的勾选状态，全部放开
    c.hide_render = False; c.hide_viewport = False


def show(lc):
    lc.exclude = False; lc.hide_viewport = False
    for k in lc.children:
        show(k)


show(bpy.context.view_layer.layer_collection)
for o in bpy.data.objects:
    o.hide_render = False; o.hide_viewport = False; o.hide_set(False)
for o in list(bpy.data.objects):
    if o.type != 'MESH':
        bpy.data.objects.remove(o)
meshes = [o for o in bpy.data.objects if o.type == 'MESH']


def bb(o):
    P = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return Vector((min(p[i] for p in P) for i in range(3))), Vector((max(p[i] for p in P) for i in range(3)))


lo = Vector((min(bb(o)[0][i] for o in meshes) for i in range(3)))
hi = Vector((max(bb(o)[1][i] for o in meshes) for i in range(3)))
U = 1.0 if (hi - lo).length > 50 else 0.001          # 模型单位：mm 或 m
print('BBOX', lo, hi, 'U', U)
mm = lambda v: v * U


def pbr(name, rgb, rough=.45, metal=0., emit=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1); b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1); b.inputs['Emission Strength'].default_value = 1.5
    return m


SHELL = pbr('shell', (.80, .81, .83), .42)
FRAME = pbr('frame', (.05, .055, .07), .38)
MECH = pbr('mech', (.60, .62, .66), .4)
SERVO = pbr('servo', (.015, .017, .022), .3)
LIP = pbr('lip', (.85, .25, .12), .4)
LID = pbr('lid', (.80, .81, .83), .35)
TEETH = pbr('teeth', (.9, .88, .82), .3)
BRASS = pbr('brass', (.85, .58, .22), .28, 1.)
BROW = pbr('brow', (.015, .016, .02), .6)


def eye_mat(cx, cy):
    m = bpy.data.materials.new('eye'); m.use_nodes = True; t = m.node_tree; n = t.nodes; b = n['Principled BSDF']
    b.inputs['Roughness'].default_value = .12; b.inputs['Coat Weight'].default_value = 1.
    g = n.new('ShaderNodeNewGeometry'); s = n.new('ShaderNodeSeparateXYZ'); t.links.new(g.outputs['Position'], s.inputs[0])
    dx = n.new('ShaderNodeMath'); dx.operation = 'SUBTRACT'; dx.inputs[1].default_value = cx; t.links.new(s.outputs[0], dx.inputs[0])
    d = n.new('ShaderNodeCombineXYZ'); t.links.new(dx.outputs[0], d.inputs[0]); t.links.new(s.outputs[2], d.inputs[1])
    L = n.new('ShaderNodeVectorMath'); L.operation = 'LENGTH'; t.links.new(d.outputs[0], L.inputs[0])
    r = n.new('ShaderNodeMath'); r.operation = 'DIVIDE'; r.inputs[1].default_value = mm(16); t.links.new(L.outputs['Value'], r.inputs[0])
    ramp = n.new('ShaderNodeValToRGB'); cr = ramp.color_ramp
    stops = [(0, (.0, .0, .0)), (.19, (.0, .0, .0)), (.205, (.02, .55, .62)), (.40, (.05, .95, .90)), (.53, (.0, .22, .32)), (.56, (.95, .95, .93)), (1, (.95, .95, .93))]
    cr.elements[0].position = 0; cr.elements[0].color = (*stops[0][1], 1); cr.elements[1].position = 1; cr.elements[1].color = (*stops[-1][1], 1)
    for p, c in stops[1:-1]:
        e = cr.elements.new(p); e.color = (*c, 1)
    t.links.new(r.outputs[0], ramp.inputs[0]); t.links.new(ramp.outputs[0], b.inputs['Base Color'])
    t.links.new(ramp.outputs[0], b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value = .18
    return m


def setm(o, m):
    o.data.materials.clear(); o.data.materials.append(m)


# 模型只画了一侧眉毛：缺的镜像补上
brow = next(c for c in bpy.data.collections if c.name.startswith('02'))
have = [(bb(o)[0] + bb(o)[1]) / 2 for o in brow.objects]
for o in list(brow.objects):
    l, h = bb(o); c = (l + h) / 2
    if l.x * h.x < 0:
        continue
    if not any((p - Vector((-c.x, c.y, c.z))).length < mm(3) for p in have):
        d = o.copy(); d.data = o.data.copy(); brow.objects.link(d)
        d.matrix_world = __import__('mathutils').Matrix.Scale(-1, 4, (1, 0, 0)) @ o.matrix_world

for col in bpy.data.collections:
    if col.name.startswith('步骤') or col.name.startswith('图'):
        continue
    for o in col.objects:
        if o.type != 'MESH':
            continue
        n = o.name
        if '眼球' in n:
            l, h = bb(o); setm(o, eye_mat((l.x + h.x) / 2, 0))
        elif n.startswith('M') and ('×' in n) or '台阶' in n or '热熔' in n or '垫' in n:
            setm(o, BRASS)
        elif 'MG9' in n or 'SG90' in n:
            setm(o, SERVO)
        elif 'Lid' in n:
            setm(o, LID)
        elif col.name.startswith('00'):
            setm(o, SHELL if any(k in n for k in ('后盖', '格栅', '额头', '颧骨')) else FRAME)
        elif col.name.startswith('02'):
            setm(o, BROW if '软眉毛' in n else MECH)
        elif col.name.startswith('04'):
            setm(o, LIP)
        elif col.name.startswith('05'):
            setm(o, TEETH)
        else:
            setm(o, MECH)

MOD = {'eyes': ('01',), 'brows': ('02',), 'mouth': ('03', '04', '05')}
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
ctr = (lo + hi) / 2
size = (hi - lo).length
fit = 3.95
if VIEW in MOD:
    keep = set()
    for c in bpy.data.collections:
        if c.name[:2] in MOD[VIEW]:
            keep |= set(c.objects)
    for o in meshes:
        o.hide_render = o not in keep
    B = [bb(o) for o in keep]
    l2 = Vector((min(b[0][i] for b in B) for i in range(3))); h2 = Vector((max(b[1][i] for b in B) for i in range(3)))
    ctr = (l2 + h2) / 2; fit = 3.95 * (h2 - l2).length / size * 1.02

cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 110; cam.data.sensor_fit = 'VERTICAL'; cam.data.clip_end = 1e5; cam.data.clip_start = 1
d = {'hero': Vector((.34, -1, .12)), 'eyes': Vector((.3, -1, .35)), 'brows': Vector((.3, -1, .45)), 'mouth': Vector((.42, -1, .1))}[VIEW].normalized()
cam.location = ctr + d * size * fit
cam.rotation_euler = (ctr - cam.location).to_track_quat('-Z', 'Y').to_euler()


def area(name, loc, power, rgb, s):
    L = bpy.data.lights.new(name, 'AREA'); L.energy = power * size * size * 0.35; L.color = rgb; L.size = size * s
    o = bpy.data.objects.new(name, L); sc.collection.objects.link(o); o.location = ctr + Vector(loc) * size
    o.rotation_euler = (ctr - o.location).to_track_quat('-Z', 'Y').to_euler()


area('key', (-.9, -1.3, 1.0), 60, (1, .93, .85), .9)
area('rimR', (1.4, .6, .5), 130, (.15, .85, 1), .5)
area('rimL', (-1.3, .9, .2), 90, (1, .28, .15), .5)
area('fill', (.3, -1.5, -.5), 14, (.6, .75, 1), 1.2)

w = bpy.data.worlds.new('w'); w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (.01, .012, .02, 1); w.node_tree.nodes['Background'].inputs[1].default_value = .4
sc.world = w
sc.render.engine = 'CYCLES'; sc.cycles.samples = SPP; sc.cycles.use_denoising = True
try:
    p = bpy.context.preferences.addons['cycles'].preferences; p.compute_device_type = 'METAL'; p.get_devices()
    for dv in p.devices: dv.use = True
    sc.cycles.device = 'GPU'
except Exception as e:
    print('no gpu', e)
sc.render.film_transparent = True
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
