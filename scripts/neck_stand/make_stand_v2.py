"""颈部支架 v2：用头骨底板的六边形孔做转 30° 锁定，不再靠扎带。

运行：.venv/bin/python scripts/neck_stand/make_stand_v2.py（需要 manifold3d、trimesh）

底板局部坐标 (u, v, w)：原点在六边形孔中心、底板下表面上；u = 模型 x，v 朝后，w 垂直底板朝上。
底板法向相对竖直倾斜 8°，头保持模型里的姿态。

实测（SkullFrame）：底板厚 6.3；六边形对边 50，角部半径 27.6；4 个盲槽 8.0 × 19.6、深 2，
槽中心距孔中心 31.5，方向与后方夹角 ±30°、±150°。
底板下方前半部有两条竖筋（|u| 30.5 到 34.5），会随头转动，所以法兰半径只能到 30。

受力：重心 y≈-9，比法兰前沿还靠前，头总是前沿下压、后部上翘。所以后方 ±30° 的唇边承力，
前方的凸键一直压在盲槽里防转。筋转动时会扫过 -150° 的位置，只在 +150° 放一个凸键。
"""
import math
import os

import numpy as np
import trimesh
from manifold3d import CrossSection, Manifold, Mesh

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))
OUT_DIR = f'{ROOT}/outputs/neck_stand'

N = np.array([0, .139, -.99]); N /= np.linalg.norm(N)      # 底板法向，朝下
EV = np.cross(N, [1.0, 0, 0]); EV = EV if EV[1] > 0 else -EV
ORIGIN = N * 44.6 + EV * 47.2
LOCAL = np.c_[[1.0, 0, 0], EV, -N, ORIGIN]                 # 3×4：局部 → 装配坐标

PLATE_T = 6.3
KEY_H = 1.0            # 凸键高度，盲槽深 2
KEY_ANG = 150          # 只放这一个
LIP_GAP = 0.3
SHAFT_R = 24.5         # 孔内切半径 25
LIP_R = 27.0           # 孔角部半径 27.6
LIP_AF_R = 24.6        # 唇边六边形内切半径（穿孔时要过 50 对边）
FLANGE_R = 30.0        # 竖筋内侧 30.5
PAD_R = 36.4           # 凸键下方局部加宽
BORE_R = 20.6
BASE_TOP, BASE_T = -142.0, 6.0
SEG = 128


def local(m):
    return m.transform(LOCAL)


def box(x0, x1, y0, y1, z0, z1):
    return Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def frustum(r0, w0, r1, w1, seg=SEG):
    return Manifold.cylinder(w1 - w0, r0, r1, seg).translate((0, 0, w0))


def extrude_yz(poly, x0, x1):
    """(y,z) 多边形沿 x 拉伸"""
    cs = CrossSection([poly])
    m = Manifold.extrude(cs, x1 - x0)       # 截面在 XY，沿 +Z 拉伸
    M = np.array([[0, 0, 1, x0], [1, 0, 0, 0], [0, 1, 0, 0]], float)   # (a,b,c) → (x=c+x0, y=a, z=b)
    return m.transform(M)


def key(ang):
    """盲槽里的凸键：底 7×18.6，顶 5×16.6，四周 45° 斜面，转入时当坡道用"""
    bottom = box(-9.3, 9.3, -3.5, 3.5, -1, 0)
    top = Manifold.hull(Manifold.compose([box(-9.3, 9.3, -3.5, 3.5, -0.01, 0), box(-8.3, 8.3, -2.5, 2.5, KEY_H - 0.01, KEY_H)]))
    a = math.radians(ang)
    # 局部 x 轴 = 切向，局部 y 轴 = 径向（与后方 +v 夹角 ang）
    M = np.array([[math.cos(a), math.sin(a), 0, 31.5 * math.sin(a)], [-math.sin(a), math.cos(a), 0, 31.5 * math.cos(a)], [0, 0, 1, 0]])
    return (bottom + top).transform(M)


def sector(a0, a1, r=90, w0=-40, w1=40):
    """局部坐标里与 +v 夹角 a0 到 a1 的扇形柱（度，朝 +u 为正）"""
    pts = [(0.0, 0.0)] + [(r * math.sin(math.radians(a)), r * math.cos(math.radians(a))) for a in np.linspace(a0, a1, 16)]
    return Manifold.extrude(CrossSection([pts[::-1]]), w1 - w0).translate((0, 0, w0))   # 角度增大是顺时针，反过来才是正向多边形


def build():
    w0 = PLATE_T + LIP_GAP - (25 - SHAFT_R)           # 倒角在 r=25 处刚好离底板上表面 LIP_GAP
    w1 = w0 + (LIP_R - SHAFT_R)
    hexr = LIP_AF_R / math.cos(math.radians(30))
    hexp = frustum(hexr, w0 - 1, hexr, w1 + 3, 6)     # 顶点在 ±u，锁定时压在孔的平边上
    lip = (frustum(SHAFT_R, w0, LIP_R, w1) + frustum(LIP_R, w1, LIP_R, w1 + 2.0)) ^ hexp
    lip = lip ^ sector(-56, 56)                       # 只留后方 ±30° 两处
    shaft_top = frustum(SHAFT_R, w0 - 0.01, SHAFT_R, w1 + 2.0)

    above = local(box(-90, 90, -90, 90, -1.0, 60))
    main = extrude_yz([(46, BASE_TOP - 1), (93, BASE_TOP - 1), (93, -25), (46, -25)], -24, 24) - above
    gusset = extrude_yz([(46, -69), (60, -69), (60, -44), (29, -44), (29, -52)], -18, 18) - above

    pad = (frustum(PAD_R, -2.3, PAD_R, 0.0) + frustum(24.0, -14.4, PAD_R, -2.0)) ^ sector(KEY_ANG - 20, KEY_ANG + 20)
    head = frustum(FLANGE_R, -2.3, FLANGE_R, 0.0) + frustum(24.0, -8.0, FLANGE_R, -2.0) + pad   # 法兰多伸 0.3 和圆台重叠，只贴面会留下非流形边
    head = head + frustum(SHAFT_R, -0.5, SHAFT_R, w1 + 2.0) + lip + key(KEY_ANG)
    base = box(-70, 70, -105, 98, BASE_TOP - BASE_T, BASE_TOP)
    solid = base + main + gusset + local(head)

    # 内腔：走线通道，斜面都在 45° 左右，不用支撑
    cav = extrude_yz([(50, -136), (89, -136), (89, -25), (50, -25)], -20, 20) - local(box(-90, 90, -90, 90, -9.0, 60))
    chute = extrude_yz([(50, -65), (62, -65), (62, -38), (33, -38), (33, -48)], -13, 13) - local(box(-90, 90, -90, 90, -2.6, 60))
    bore = local(frustum(BORE_R, -3.3, BORE_R, w1 + 3) + frustum(13.0, -11.0, BORE_R, -3.0))
    solid = solid - (cav + chute + bore)
    # 后方开口：线可以从侧面放进去；后方正对孔的角，避开 ±30° 的唇边受力位
    solid = solid - box(-7, 7, 80, 100, -136, -35) - local(box(-7, 7, 14, 50, -32, w1 + 4))
    return solid, w0, w1


def to_trimesh(m):
    me = m.simplify(0.01).to_mesh()      # 去掉极短边，否则存成单精度 STL 后点会并到一起，不再水密
    return trimesh.Trimesh(np.array(me.vert_properties)[:, :3], np.array(me.tri_verts), process=False)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    solid, w0, w1 = build()
    t = to_trimesh(solid)
    print('watertight', t.is_watertight, 'volume cm3', round(solid.volume() / 1000, 1), 'genus', solid.genus(), 'bbox', t.bounds.round(1).tolist(), 'lip w', round(w0, 2), round(w1, 2))
    np.savez(f'{OUT_DIR}/stand_v2_asm.npz', V=t.vertices, F=t.faces, M=LOCAL, w0=w0, w1=w1)

    # 打印件：底面 z=0
    p = t.copy(); p.apply_translation((0, 0, -(BASE_TOP - BASE_T))); p.export(f'{OUT_DIR}/NeckStand_v2_转锁支架_x1.stl')

    # 试配环：只留顶部，平放打印，先试孔和盲槽
    Linv = np.linalg.inv(np.r_[LOCAL, [[0, 0, 0, 1]]])[:3]
    ring = solid.transform(Linv) ^ box(-45, 45, -45, 45, -2.0, 30)
    r = to_trimesh(ring.translate((0, 0, 2.0)))
    print('ring watertight', r.is_watertight, 'volume cm3', round(ring.volume() / 1000, 1), 'bbox', r.bounds.round(1).tolist())
    r.export(f'{OUT_DIR}/NeckStand_v2_试配环_x1.stl')


if __name__ == '__main__':
    main()
