"""v2 支架干涉检查：插入、转 30°、落座、下巴 0 到 45°。

/Volumes/Robotics/apps/Blender.app/Contents/MacOS/Blender -b --factory-startup --python scripts/neck_stand/verify_v2.py
"""
import math
import os

import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))
d = np.load(f'{ROOT}/outputs/assembly/mesh.npz')
V, F, G, names = d['V'].astype(float), d['F'], d['G'], [str(x) for x in d['names']]
s = np.load(os.environ.get('STAND_NPZ', f'{ROOT}/outputs/neck_stand/stand_v2_asm.npz'))
SV, SF, M = s['V'], s['F'], s['M']
BASE_LIFT = float(s['lift']) if 'lift' in s.files else 0.0   # 转接件把头抬高的量
R, O = M[:, :3], M[:, 3]
stand = BVHTree.FromPolygons([tuple(v) for v in SV], [tuple(int(i) for i in f) for f in SF], all_triangles=True)
L = (V - O) @ R                                # 全部顶点转到底板局部坐标

parts = {}
for g in np.unique(G):
    parts[int(g)] = F[G == g]
zmax = {g: V[np.unique(f), 2].max() for g, f in parts.items()}
ymax = {g: V[np.unique(f), 1].max() for g, f in parts.items()}
JAW = [g for g in parts if zmax[g] < -28 and ymax[g] < 45 and g != 0 and 'M4x0.70 x 16' not in names[g]]   # 这些 M4 固定在头骨上
AXIS_Y, AXIS_Z = -2.0, -41.0


def pose(th_deg=0.0, lift=0.0, jaw_deg=0.0, nod_deg=0.0, pivot_v=-30.0):
    """返回装配坐标下的全部顶点。th 绕局部 w 轴；nod>0 = 脸朝下，绕 v=pivot_v 的 u 向轴"""
    P = V
    if jaw_deg:
        a = math.radians(jaw_deg); P = P.copy()
        idx = np.unique(np.concatenate([parts[g].ravel() for g in JAW]))
        y = V[idx, 1] - AXIS_Y; z = V[idx, 2] - AXIS_Z
        P[idx, 1] = AXIS_Y + y * math.cos(a) - z * math.sin(a); P[idx, 2] = AXIS_Z + y * math.sin(a) + z * math.cos(a)
    Q = (P - O) @ R
    t = math.radians(th_deg); c, sn = math.cos(t), math.sin(t)
    Q = Q @ np.array([[c, sn, 0], [-sn, c, 0], [0, 0, 1]])
    if nod_deg:
        a = math.radians(nod_deg); pv = np.array([0, pivot_v, 0])
        Rx = np.array([[1, 0, 0], [0, math.cos(a), math.sin(a)], [0, -math.sin(a), math.cos(a)]])
        Q = (Q - pv) @ Rx + pv
    Q = Q + [0, 0, lift + BASE_LIFT]
    return Q @ R.T + O


def check(P):
    hits, near = {}, (1e9, None)
    used = set()
    for g, f in parts.items():
        ids = np.unique(f); remap = np.full(len(V), -1); remap[ids] = np.arange(len(ids))
        pts = P[ids]
        c = pts.mean(0)
        if pts[:, 2].min() > -20 or pts[:, 1].max() < -60:
            continue
        b = BVHTree.FromPolygons([tuple(p) for p in pts], [tuple(int(i) for i in t) for t in remap[f]], all_triangles=True)
        n = len(b.overlap(stand))
        if n:
            hits[names[g]] = n
        for p in pts[::3]:
            r = stand.find_nearest(Vector(p), 60)
            if r[0] is not None and r[3] < near[0]:
                near = (r[3], names[g])
    return hits, near


def run(label, **kw):
    h, n = check(pose(**kw))
    print(f'{label:34s} 干涉 {"无" if not h else h}   最近 {n[0]:.2f} mm {n[1][:22]}')


MODE = str(s['mode']) if 'mode' in s.files else 'full'


def hit(**kw):
    return bool(check_fast(pose(**kw)))


def check_fast(P):
    out = {}
    for g, f in parts.items():
        ids = np.unique(f); remap = np.full(len(V), -1); remap[ids] = np.arange(len(ids)); pts = P[ids]
        if pts[:, 2].min() > -20 or pts[:, 1].max() < -60:
            continue
        b = BVHTree.FromPolygons([tuple(p) for p in pts], [tuple(int(i) for i in t) for t in remap[f]], all_triangles=True)
        n = len(b.overlap(stand))
        if n:
            out[names[g]] = n
    return out


def line(label, **kw):
    h = check_fast(pose(**kw))
    print(f'RESULT {label}: {"无干涉" if not h else h}')


if MODE == 'full':
    print('jaw parts', len(JAW))
    run('落座', lift=0.05)
    for n in (0.2, 0.3, 0.4, 0.6):
        run(f'前沿压住，后部上翘 {n}°', lift=0.05, nod_deg=n)
    for lift in (0.2, 0.3, 0.4, 0.6, 1.0):
        run(f'整体上抬 {lift}', lift=lift)
    for sign in (1, -1):
        for th in (0, 5, 10, 15, 20, 25, 30):
            run(f'脸抬起 1.2° 转 {sign * th:+d}°', th_deg=sign * th, lift=0.1, nod_deg=-1.2, pivot_v=25)
    for sign in (1, -1):
        for lift in (0.5, 1, 2, 4, 6, 8, 10, 12, 14, 18):
            run(f'转 {sign * 30:+d}° 沿轴插入 抬 {lift}', th_deg=sign * 30, lift=lift)
    for j in (0, 15, 30, 45):
        run(f'下巴 {j}°', lift=0.05, jaw_deg=j)
else:
    line('落座', lift=0.05)
    n = 0.0
    while n < 4 and not hit(lift=0.05, nod_deg=n + 0.1, pivot_v=-37):   # 支点取最前的接触点，前面没有东西
        n += 0.1
    print(f'RESULT 前倾极限: {n:.1f}°')
    u = 0.05
    while u < 6 and not hit(lift=u + 0.05):
        u += 0.05
    print(f'RESULT 上提极限: {u:.2f} mm')
    for j in (0, 15, 30, 45):
        line(f'下巴 {j}°', lift=0.05, jaw_deg=j)
    if MODE == 'twist':
        full = float(s['twist_lift']) if 'twist_lift' in s.files else 0.0
        for th in (0, 5, 10, 15, 20, 25, 30):
            if full:
                line(f'整体抬 {full} 转 +{th}°', th_deg=th, lift=full)
            else:
                line(f'脸抬 2.4° 转 +{th}°', th_deg=th, lift=0.05, nod_deg=-2.4, pivot_v=2)
        for l in (1.1, 2, 4, 6, 8, 10, 12, 14, 18):
            line(f'+30° 插入 抬 {l}', th_deg=30, lift=l)
    if MODE == 'drop':
        for l in (0.5, 1, 2, 4, 6, 8, 10, 12, 14, 18):
            line(f'直落 抬 {l}', lift=l)
