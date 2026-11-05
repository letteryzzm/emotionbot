"""头骨框架后下方的底面高度图（给颈部支架顶面贴合用）。输出 outputs/neck_stand/hmap.npz"""
import sys; sys.path.insert(0, 'scripts/assembly_render')
import numpy as np
from render import Scene
S = Scene('outputs/assembly/mesh.npz')
X0, X1, Y0, Y1 = -40, 40, 15, 100
T = np.concatenate([S.tris(g) for g in S.faces])
m = (T[..., 0].max(1) > X0) & (T[..., 0].min(1) < X1) & (T[..., 1].max(1) > Y0) & (T[..., 1].min(1) < Y1) & (T[..., 2].min(1) < 0)
T = T[m]
v0, v1, v2 = T[:, 0], T[:, 1], T[:, 2]
d = (v1[:, 1] - v2[:, 1]) * (v0[:, 0] - v2[:, 0]) + (v2[:, 0] - v1[:, 0]) * (v0[:, 1] - v2[:, 1])
ok = np.abs(d) > 1e-12; d = np.where(ok, d, 1)
xs = np.arange(X0, X1 + 0.01, 1.0); ys = np.arange(Y0, Y1 + 0.01, 1.0)
H = np.full((len(xs), len(ys)), np.nan)
for i, x in enumerate(xs):
    for j, y in enumerate(ys):
        l1 = ((v1[:, 1] - v2[:, 1]) * (x - v2[:, 0]) + (v2[:, 0] - v1[:, 0]) * (y - v2[:, 1])) / d
        l2 = ((v2[:, 1] - v0[:, 1]) * (x - v2[:, 0]) + (v0[:, 0] - v2[:, 0]) * (y - v2[:, 1])) / d
        l3 = 1 - l1 - l2; h = ok & (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        z = (l1 * v0[:, 2] + l2 * v1[:, 2] + l3 * v2[:, 2])[h]
        z = z[z < 0]
        if len(z): H[i, j] = z.min()
np.savez('outputs/neck_stand/hmap.npz', xs=xs, ys=ys, H=H)
for i in range(0, len(xs), 4):
    print('x%4d ' % xs[i] + ''.join(' %4s' % ('' if np.isnan(H[i, j]) else int(H[i, j])) for j in range(0, len(ys), 5)))
print('y:   ', list(ys[::5].astype(int)))
