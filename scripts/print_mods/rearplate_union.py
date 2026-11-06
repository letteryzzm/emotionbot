"""Blender 无界面：RearPlate STL ∪ 封盖 → outputs/print_mods/RearPlate_无出风口.stl"""
import glob, os, struct
import bpy, bmesh
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'outputs/print_mods')
bpy.ops.wm.read_factory_settings(use_empty=True)
p = glob.glob(os.path.join(ROOT, 'print_package/STL/plate1*/RearPlate*'))[0]
b = open(p, 'rb').read(); n = int.from_bytes(b[80:84], 'little')
dt = np.dtype([('n', '<3f4'), ('v', '<9f4'), ('a', '<u2')])
T = np.frombuffer(b, dtype=dt, offset=84, count=n)['v'].reshape(-1, 3).astype(float)
u, inv = np.unique(np.round(T, 4), axis=0, return_inverse=True)
def obj(name, V, F):
    m = bpy.data.meshes.new(name); m.from_pydata([tuple(x) for x in V], [], [tuple(int(i) for i in f) for f in F]); m.update()
    o = bpy.data.objects.new(name, m); bpy.context.collection.objects.link(o); return o
A = obj('plate', u, inv.reshape(-1, 3))
c = np.load(os.path.join(OUT, 'cap.npz')); C = obj('cap', c['V'], c['F'])
md = A.modifiers.new('u', 'BOOLEAN'); md.operation = 'UNION'; md.object = C; md.solver = 'EXACT'
bpy.context.view_layer.objects.active = A
bpy.ops.object.modifier_apply(modifier='u')
bm = bmesh.new(); bm.from_mesh(A.data); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.002); bmesh.ops.dissolve_degenerate(bm, dist=0.002, edges=bm.edges); bmesh.ops.triangulate(bm, faces=bm.faces)
tri = np.array([[tuple(v.co) for v in f.verts] for f in bm.faces], dtype='<f4')
a = np.zeros(len(tri), dtype=dt); a['v'] = tri.reshape(-1, 9)
nn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); l = np.linalg.norm(nn, axis=1, keepdims=True); a['n'] = nn / np.where(l == 0, 1, l)
with open(os.path.join(OUT, 'RearPlate_无出风口.stl'), 'wb') as f:
    f.write(b'RearPlate vent closed, mm'.ljust(80, b' ')); f.write(np.uint32(len(a)).tobytes()); f.write(a.tobytes())
print('union tris', len(a))
