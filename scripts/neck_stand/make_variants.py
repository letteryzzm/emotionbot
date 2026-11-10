"""旧底座转接环的 5 个方案，全部装在 v1 立柱上，LIFT 相同。

运行：.venv/bin/python scripts/neck_stand/make_variants.py，结果在 outputs/neck_stand/variants/
A 1 键转锁；B 3 刚性键转锁；C 1 键转锁 + 2 颗 M3 顶丝；D 1 刚性键 + 2 弹性键转锁；E 直落 4 键 + 四爪压板 + M4
"""
import itertools
import math
import os
import sys

import numpy as np
from manifold3d import Manifold

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_adapter_v1 as ad
import make_stand_v2 as v2
from make_stand_v2 import LOCAL, box, frustum, local, sector, to_trimesh

LIFT = 20.0
OUT = f'{v2.OUT_DIR}/variants'
HEXR = v2.LIP_AF_R / math.cos(math.radians(30))


def key(ang, h):
    bottom = box(-9.3, 9.3, -3.5, 3.5, -1, 0)
    top = Manifold.hull(Manifold.compose([box(-9.3, 9.3, -3.5, 3.5, -0.01, 0), box(-8.3, 8.3, -2.5, 2.5, h - 0.01, h)]))
    a = math.radians(ang)
    M = np.array([[math.cos(a), math.sin(a), 0, 31.5 * math.sin(a)], [-math.sin(a), math.cos(a), 0, 31.5 * math.cos(a)], [0, 0, 1, 0]])
    return (bottom + top).transform(M)


def pad(ang, half=20):
    return (frustum(v2.PAD_R, -2.3, v2.PAD_R, 0.0) + frustum(24.0, -14.4, v2.PAD_R, -2.0)) ^ sector(ang - half, ang + half)


def lip(gap):
    # 孔在 ±30°、±150° 的上沿有 45° 倒角：r = w + 20.67。唇边斜面和它平行，间隙 gap
    w0 = v2.SHAFT_R - 20.67 + gap
    w1 = w0 + (v2.LIP_R - v2.SHAFT_R)
    m = (frustum(v2.SHAFT_R, w0, v2.LIP_R, w1) + frustum(v2.LIP_R, w1, v2.LIP_R, w1 + 2.0)) ^ frustum(HEXR, w0 - 1, HEXR, w1 + 3, 6)
    return (m ^ sector(-56, 56)) + frustum(v2.SHAFT_R, -0.5, v2.SHAFT_R, w1 + 2.0), w1


def finish(top, w1, cuts=None, extra=None):
    """top 在头骨局部坐标（w=0 是底板下表面），加脖子和鞍座，减内腔和立柱负形"""
    top = top.translate((0, 0, LIFT))
    solid = top + frustum(29.0, -3.5, 29.0, LIFT - 1.0) + box(-36, 36, 13, 38, -3.5, 5.0)
    solid = solid - frustum(v2.BORE_R, -8, v2.BORE_R, LIFT + w1 + 3)
    solid = solid - box(13.5, 18.5, 24, 31, -8, 12) - box(-18.5, -13.5, 24, 31, -8, 12)
    solid = solid - box(-7, 7, 14, 50, -8, LIFT + w1 + 4)
    if cuts is not None:
        solid = solid - cuts.translate((0, 0, LIFT))
    if extra is not None:
        solid = solid + extra.translate((0, 0, LIFT))
    solid = local(solid)
    old = ad.old_stand()
    neg = None
    for dx, dy in itertools.product((-.25, .25), (-.25, .25)):
        m = old.translate((dx, dy, 0.1))
        neg = m if neg is None else neg + m
    return solid - neg, old


RELIEF = 1.6


def relief():
    """后半圈法兰降低，转动时底板后部才能下沉，越过孔的倒角两端"""
    return (frustum(40, -RELIEF, 40, 0.5) - frustum(v2.SHAFT_R, -3, v2.SHAFT_R, 2)) ^ sector(-88, 88)


def flange():
    return frustum(v2.FLANGE_R, -2.3, v2.FLANGE_R, 0.0)


def variant_A():
    s, w1 = lip(0.3)
    return finish(flange() + pad(150) + s + key(150, 1.0), w1, cuts=relief())


def variant_B():
    s, w1 = lip(2.4)      # 底板要同时越过 1 mm 后键和倒角两端
    return finish(flange() + pad(150) + pad(30) + pad(-30) + s + key(150, 1.0) + key(30, 1.0) + key(-30, 1.0), w1)


def variant_C():
    s, w1 = lip(0.3)
    holes = relief()
    for a in (30, -30):
        r = math.radians(a)
        holes = holes + frustum(1.25, -20, 1.25, 3, 32).translate((32 * math.sin(r), 32 * math.cos(r), 0))
    return finish(flange() + pad(150) + pad(30) + pad(-30) + s + key(150, 1.0), w1, cuts=holes)


def ring(r0, r1, w0, w1):
    return frustum(r1, w0, r1, w1) - frustum(r0, w0 - 1, r0, w1 + 1)


def variant_D(pressed=False):
    s, w1 = lip(0.3)
    cuts = relief(); extra = None
    for sgn in (1, -1):
        a0, a1 = sorted((sgn * 8, sgn * 50)); r0, r1 = sorted((sgn * 48, sgn * 57))
        cuts = cuts + (ring(29.0, 29.6, -4, 1) ^ sector(a0, a1))
        tab = ring(29.7, 35.2, -1.8 - RELIEF, -RELIEF) ^ sector(*sorted((sgn * 8, sgn * 57)))
        root = (frustum(35.2, -2.3 - RELIEF, 35.2, -RELIEF) + frustum(24.0, -13.2 - RELIEF, 35.2, -2.0 - RELIEF)) ^ sector(r0, r1)
        e = tab + root
        if not pressed:
            e = e + (key(sgn * 30, 1.0 + RELIEF).translate((0, 0, -RELIEF)) ^ ring(29.7, 35.2, -RELIEF - 0.5, 2))
        extra = e if extra is None else extra + e
    return finish(flange() + pad(150) + s + key(150, 1.0), w1, cuts=cuts, extra=extra)


def variant_E():
    fl = (frustum(v2.PAD_R, -2.3, v2.PAD_R, 0.0) + frustum(24.0, -14.4, v2.PAD_R, -2.0)) ^ box(-30.2, 30.2, -60, 60, -30, 1)
    plug = (frustum(HEXR, -0.5, HEXR, 3.9, 6).rotate((0, 0, 30)) ^ frustum(27.0, -1, 27.0, 5))
    top = fl + plug
    for a in (30, -30, 150, -150):
        top = top + key(a, 1.6)
    bar = box(-22, 22, -6, 6, -14, -8) - frustum(2.25, -20, 2.25, 0, 32)
    s, a = finish(top, 4.0)
    s = s + local(bar.translate((0, 0, LIFT)))
    # 四爪压板：爪朝 ±30°、±150°，斜面压在孔的倒角上；穿孔时转 30°，爪对着孔角
    w0 = 24.5 - 20.67 + 0.15
    body = frustum(24.5, w0, 27.0, w0 + 2.5) + frustum(27.0, w0 + 2.5, 27.0, w0 + 5.5)
    arms = None
    for ang in (30, -30, 150, -150):
        arm = box(-5, 5, 0, 30, 0, 20).rotate((0, 0, -ang))
        arms = arm if arms is None else arms + arm
    tri = (body ^ (arms + frustum(9.0, 0, 9.0, 20)))
    tri = tri - frustum(2.25, 0, 2.25, 20, 32) - frustum(4.15, w0 + 2.3, 4.15, 20, 6)
    return s, a, local(tri.translate((0, 0, LIFT)))


def save(name, solid, old, mode, extra=None, twist_lift=0.0):
    os.makedirs(OUT, exist_ok=True)
    t = to_trimesh(solid)
    both = solid + old + (extra if extra is not None else Manifold())
    b = to_trimesh(both)
    np.savez(f'{OUT}/{name}.npz', V=b.vertices, F=b.faces, M=LOCAL, lift=LIFT, mode=mode, twist_lift=twist_lift)
    Linv = np.linalg.inv(np.r_[LOCAL, [[0, 0, 0, 1]]])[:3]
    p = to_trimesh(solid.transform(Linv)); p.apply_translation((0, 0, -p.bounds[0][2])); p.export(f'{OUT}/{name}.stl')
    print(name, 'watertight', p.is_watertight, 'parts', len(solid.decompose()), 'cm3', round(solid.volume() / 1000, 1), 'size', (p.bounds[1] - p.bounds[0]).round(1).tolist())


def variant_nokey():
    s, w1 = lip(0.3)
    return finish(flange() + s, w1, cuts=relief())


if __name__ == '__main__':
    s, o = variant_nokey(); save('_无键对照', s, o, 'seat')
    s, o = variant_A(); save('A_一键转锁', s, o, 'twist')
    s, o = variant_B(); save('B_三键转锁', s, o, 'twist', twist_lift=1.1)
    s, o = variant_C(); save('C_顶丝转锁', s, o, 'twist')
    s, o = variant_D(); save('D_弹性键', s, o, 'seat')
    s, o = variant_D(True); save('D_弹性键_压下状态', s, o, 'twist')
    s, o, t = variant_E(); save('E_直落压板', s, o, 'drop'); save('E_直落压板_夹紧状态', s, o, 'seat', t)
    tm = to_trimesh(t); Linv = np.linalg.inv(np.r_[LOCAL, [[0, 0, 0, 1]]])[:3]
    p = to_trimesh(t.transform(Linv)); p.apply_translation((0, 0, -p.bounds[0][2])); p.export(f'{OUT}/E_四爪压板.stl')
    print('clamp watertight', p.is_watertight, 'parts', len(t.decompose()), 'size', (p.bounds[1] - p.bounds[0]).round(1).tolist())
