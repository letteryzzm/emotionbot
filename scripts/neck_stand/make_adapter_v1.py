"""转接件：装在 v1 支架立柱上，顶部是 v2 的转锁接口，头比 v2 抬高 LIFT。

运行：.venv/bin/python scripts/neck_stand/make_adapter_v1.py
底面是 v1 立柱的负形。立柱前段留给竖筋转动，只有后段用鞍座包住，并用 2 根扎带穿 v1 的扎带孔固定。
"""
import itertools
import os
import sys

import numpy as np
import trimesh
from manifold3d import Manifold, Mesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_stand_v2 as v2
from make_stand_v2 import LOCAL, box, frustum, local, sector, to_trimesh

LIFT = float(os.environ.get('ADAPTER_LIFT', 20.0))
OUT = v2.OUT_DIR


def old_stand():
    d = np.load(f'{OUT}/stand_asm.npz')
    return Manifold(Mesh(d['V'].astype(np.float32), d['F'].astype(np.uint32)))


def build():
    w0 = v2.PLATE_T + v2.LIP_GAP - (25 - v2.SHAFT_R)
    w1 = w0 + (v2.LIP_R - v2.SHAFT_R)
    hexr = v2.LIP_AF_R / np.cos(np.radians(30))
    lip = (frustum(v2.SHAFT_R, w0, v2.LIP_R, w1) + frustum(v2.LIP_R, w1, v2.LIP_R, w1 + 2.0)) ^ frustum(hexr, w0 - 1, hexr, w1 + 3, 6)
    lip = lip ^ sector(-56, 56)
    pad = (frustum(v2.PAD_R, -2.3, v2.PAD_R, 0.0) + frustum(24.0, -14.4, v2.PAD_R, -2.0)) ^ sector(v2.KEY_ANG - 20, v2.KEY_ANG + 20)
    top = frustum(v2.FLANGE_R, -2.3, v2.FLANGE_R, 0.0) + pad + frustum(v2.SHAFT_R, -0.5, v2.SHAFT_R, w1 + 2.0) + lip + v2.key(v2.KEY_ANG)
    top = top.translate((0, 0, LIFT))

    neck = frustum(29.0, -3.5, 29.0, LIFT - 1.0)
    saddle = box(-36, 36, 13, 38, -3.5, 8.0)
    solid = top + neck + saddle

    bore = frustum(v2.BORE_R, -8, v2.BORE_R, LIFT + w1 + 3)
    tie = box(13.5, 18.5, 24, 31, -8, 12) + box(-18.5, -13.5, 24, 31, -8, 12)     # 扎带从立柱内侧穿上来
    slot = box(-7, 7, 14, 50, -8, LIFT + w1 + 4)
    solid = solid - bore - tie - slot
    solid = local(solid)

    old = old_stand()
    neg = None
    for dx, dy in itertools.product((-.25, .25), (-.25, .25)):
        m = old.translate((dx, dy, 0.1))
        neg = m if neg is None else neg + m
    return solid - neg, old


def main():
    a, old = build()
    t = to_trimesh(a)
    print('adapter LIFT', LIFT, 'watertight', t.is_watertight, 'cm3', round(a.volume() / 1000, 1), 'genus', a.genus(), 'components', len(a.decompose()))
    both = to_trimesh(a + old)
    np.savez(f'{OUT}/adapter_v1_asm.npz', V=both.vertices, F=both.faces, M=LOCAL, lift=LIFT)
    Linv = np.linalg.inv(np.r_[LOCAL, [[0, 0, 0, 1]]])[:3]
    p = to_trimesh(a.transform(Linv)); p.apply_translation((0, 0, -p.bounds[0][2]))
    print('print size', (p.bounds[1] - p.bounds[0]).round(1).tolist())
    p.export(f'{OUT}/NeckStand_v1转接环_x1.stl')


if __name__ == '__main__':
    main()
