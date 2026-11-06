"""后盖 RearPlate 封掉出风口，第 1 步：拟合开口周围的外壳曲面，生成贴合的封盖（STL 打印坐标）。
第 2 步由 Blender 做布尔并集：blender -b -P scripts/print_mods/rearplate_union.py
"""
import glob, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'scripts/assembly_render'))
from render import Scene
import final_fig as f
OUT = os.path.join(ROOT, 'outputs/print_mods')
R_CAP, THICK, N_R, N_T = 35.5, 3.0, 36, 192
M = Scene(os.path.join(ROOT, 'outputs/assembly/mesh.npz'))
Tm, Ts = M.tris(7), f.stl('plate1*/RearPlate*')

# 模型 → STL 打印坐标：PCA 候选 + ICP
A = Tm.reshape(-1, 3); B = Ts.reshape(-1, 3)
rng = np.random.default_rng(0)
a = A[rng.choice(len(A), 2500, replace=False)]; b = B[rng.choice(len(B), 9000, replace=False)]
def nn(p, q):
    d = ((p[:, None] - q[None]) ** 2).sum(2); i = d.argmin(1); return q[i], np.sqrt(d.min(1))
def icp(R, t):
    for _ in range(40):
        p = a @ R.T + t; q, _ = nn(p, b)
        ca, cb = a.mean(0), q.mean(0); U, _, Vt = np.linalg.svd((a - ca).T @ (q - cb))
        D = np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))]); R = Vt.T @ D @ U.T; t = cb - R @ ca
    return R, t, nn(a @ R.T + t, b)[1].mean()
ea = np.linalg.svd(A - A.mean(0), full_matrices=False)[2]; eb = np.linalg.svd(B - B.mean(0), full_matrices=False)[2]
best = None
for s1 in (1, -1):
    for s2 in (1, -1):
        for perm in ((0, 1, 2), (1, 0, 2), (0, 2, 1), (2, 1, 0), (1, 2, 0), (2, 0, 1)):
            E = eb[list(perm)] * np.array([s1, s2, 1])[:, None]
            E[2] = np.cross(E[0], E[1])
            R = E.T @ ea
            r = icp(R, B.mean(0) - R @ A.mean(0))
            if best is None or r[2] < best[2]:
                best = r
R, t, err = best
print('ICP 平均误差 mm', round(float(err), 3))
np.savez(os.path.join(OUT, 'rear_tf.npz'), R=R, t=t)

# 开口中心和轴：用模型里的 RearVent
V = M.pts(9); o = V.mean(0); ax = np.linalg.svd(V - o, full_matrices=False)[2][2]; ax = ax if ax[1] > 0 else -ax
e1 = np.cross(ax, [1, 0, 0]); e1 /= np.linalg.norm(e1); e2 = np.cross(ax, e1)
# 外壳外表面：STL 三角形转回模型坐标，取法线朝外、开口外一圈
T = (Ts - t) @ R
n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
c = T.mean(1); u, v, h = (c - o) @ e1, (c - o) @ e2, (c - o) @ ax; r = np.hypot(u, v)
m = (r > 34.5) & (r < 50) & (n @ ax > .4) & (np.abs(h) < 40)
pts = (T[m].reshape(-1, 3) - o); U, W, Hh = pts @ e1, pts @ e2, pts @ ax
rv = np.hypot(U, W); k = (rv > 34) & (rv < 50); U, W, Hh = U[k], W[k], Hh[k]
DEG = 4
def feats(x, y):
    x, y = x / 40, y / 40
    return np.stack([x ** i * y ** j for i in range(DEG + 1) for j in range(DEG + 1 - i)], 1)
keep = np.ones(len(U), bool)
for _ in range(6):   # 迭代去掉开口边缘倒角等离群点
    coef = np.linalg.lstsq(feats(U[keep], W[keep]), Hh[keep], rcond=None)[0]
    res = feats(U, W) @ coef - Hh
    keep = np.abs(res) < max(3 * res[keep].std(), .05)
print('拟合点数', keep.sum(), '/', len(U), '残差 mm rms', round(float(res[keep].std()), 3), 'max', round(float(np.abs(res[keep]).max()), 3))

# 封盖网格：上表面 = 拟合曲面，下表面 = 上表面沿轴下移 THICK
rr = np.linspace(0, R_CAP, N_R + 1)[1:]; th = np.linspace(0, 2 * np.pi, N_T, endpoint=False)
X = np.outer(rr, np.cos(th)).ravel(); Y = np.outer(rr, np.sin(th)).ravel()
X = np.r_[0, X]; Y = np.r_[0, Y]; Z = feats(X, Y) @ coef
n1 = len(X)
P = np.r_[np.c_[X, Y, Z], np.c_[X, Y, Z - THICK]]
F = []
idx = lambda i, j: 1 + i * N_T + j % N_T
for j in range(N_T):
    F.append((0, idx(0, j), idx(0, j + 1)))
    F.append((n1, n1 + idx(0, j + 1), n1 + idx(0, j)))
    for i in range(N_R - 1):
        a0, a1, b0, b1 = idx(i, j), idx(i, j + 1), idx(i + 1, j), idx(i + 1, j + 1)
        F += [(a0, b0, b1), (a0, b1, a1), (n1 + a0, n1 + b1, n1 + b0), (n1 + a0, n1 + a1, n1 + b1)]
    a0, a1 = idx(N_R - 1, j), idx(N_R - 1, j + 1)
    F += [(a0, n1 + a0, n1 + a1), (a0, n1 + a1, a1)]
Pm = o + P[:, :1] * e1 + P[:, 1:2] * e2 + P[:, 2:3] * ax
Ps = Pm @ R.T + t
# e1 × e2 的朝向决定法线，保证朝外
F = np.array(F)
tri = Ps[F]; vol = np.einsum('ij,ij->i', tri[:, 0] - Ps.mean(0), np.cross(tri[:, 1] - Ps.mean(0), tri[:, 2] - Ps.mean(0))).sum() / 6
if vol < 0:
    F = F[:, ::-1]
np.savez(os.path.join(OUT, 'cap.npz'), V=Ps, F=F)
print('封盖体积 mm³', round(abs(vol)), '范围', Ps.min(0).round(1), Ps.max(0).round(1))
