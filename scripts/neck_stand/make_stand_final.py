"""一体底座：方案 A 的转锁接口（贴合孔倒角、后半圈法兰下沉、1 个前键）直接做在底座上。

运行：.venv/bin/python scripts/neck_stand/make_stand_final.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_stand_v2 as v2
import make_variants as mv
from make_stand_v2 import BASE_T, BASE_TOP, BORE_R, LOCAL, box, extrude_yz, frustum, local, to_trimesh

OUT = v2.OUT_DIR


def build():
    s, w1 = mv.lip(0.3)
    head = mv.flange() + frustum(24.0, -8.0, v2.FLANGE_R, -2.0) + mv.pad(150) + s + mv.key(150, 1.0)
    above = local(box(-90, 90, -90, 90, -2.0, 60))
    main = extrude_yz([(46, BASE_TOP - 1), (93, BASE_TOP - 1), (93, -25), (46, -25)], -24, 24) - above
    gusset = extrude_yz([(46, -69), (60, -69), (60, -44), (29, -44), (29, -52)], -18, 18) - above
    solid = box(-70, 70, -105, 98, BASE_TOP - BASE_T, BASE_TOP) + main + gusset + local(head)
    cav = extrude_yz([(50, -136), (89, -136), (89, -25), (50, -25)], -20, 20) - local(box(-90, 90, -90, 90, -9.0, 60))
    chute = extrude_yz([(50, -65), (62, -65), (62, -38), (33, -38), (33, -48)], -13, 13) - local(box(-90, 90, -90, 90, -2.6, 60))
    bore = local(frustum(BORE_R, -3.3, BORE_R, w1 + 3) + frustum(13.0, -11.0, BORE_R, -3.0))
    solid = solid - (cav + chute + bore) - local(mv.relief())
    return solid - box(-7, 7, 80, 100, -136, -35) - local(box(-7, 7, 14, 50, -32, w1 + 4))


def main():
    solid = build()
    t = to_trimesh(solid)
    print('watertight', t.is_watertight, 'parts', len(solid.decompose()), 'cm3', round(solid.volume() / 1000, 1), 'bbox', t.bounds.round(1).tolist())
    np.savez(f'{OUT}/stand_final_asm.npz', V=t.vertices, F=t.faces, M=LOCAL, lift=0.0, mode='twist', twist_lift=0.0)
    p = t.copy(); p.apply_translation((0, 0, -(BASE_TOP - BASE_T))); p.export(f'{OUT}/NeckStand_一体底座_x1.stl')


if __name__ == '__main__':
    main()
