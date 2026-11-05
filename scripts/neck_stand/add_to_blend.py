"""把颈部支架放进装配 .blend（装配坐标），另存为 机器人头_带支架.blend"""
import os
import bpy
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))
bpy.ops.wm.open_mainfile(filepath=f'{ROOT}/outputs/assembly/机器人头装配.blend')
bpy.ops.wm.stl_import(filepath=f'{ROOT}/outputs/neck_stand/NeckStand_颈部支架_x1.stl')
o = bpy.context.selected_objects[0]
o.name = '颈部支架'; o.location.z = -148.0   # 打印坐标底面 z=0 → 装配坐标底面 z=-148
m = bpy.data.materials.new('颈部支架'); m.diffuse_color = (0.95, 0.55, 0.15, 1)
o.data.materials.clear(); o.data.materials.append(m)
c = bpy.data.collections.new('07 颈部支架'); bpy.context.scene.collection.children.link(c)
for uc in list(o.users_collection): uc.objects.unlink(o)
c.objects.link(o)
for scr in bpy.data.screens:
    for a in scr.areas:
        if a.type == 'VIEW_3D':
            r3 = a.spaces[0].region_3d
            r3.view_location = (0, 0, -40); r3.view_distance = 520
bpy.ops.wm.save_as_mainfile(filepath=f'{ROOT}/outputs/assembly/机器人头_带支架.blend', compress=True)
print('saved')
