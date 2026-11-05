"""numpy 软件光栅化：把装配模型的若干零件渲染成 PNG（带描边），并返回投影函数给 SVG 标注用。"""
import numpy as np
from PIL import Image


class Scene:
    def __init__(self, npz):
        d = np.load(npz)
        self.V, self.F, self.G, self.names = d['V'], d['F'], d['G'], [str(x) for x in d['names']]
        order = np.argsort(self.G, kind='stable')
        self.F, self.G = self.F[order], self.G[order]
        bounds = np.searchsorted(self.G, np.arange(len(self.names) + 1))
        self.faces = {i: self.F[bounds[i]:bounds[i + 1]] for i in range(len(self.names)) if bounds[i + 1] > bounds[i]}
        self._axis = {}

    def tris(self, gi, offset=None):
        T = self.V[self.faces[gi]].astype(np.float64)
        if offset is not None:
            T = T + offset
        return T

    def pts(self, gi):
        return self.V[np.unique(self.faces[gi])].astype(np.float64)

    def screw_axis(self, gi):
        """返回 (head 点, tip 点, 单位方向 head→tip, 头部半径)"""
        if gi in self._axis:
            return self._axis[gi]
        X = self.pts(gi); c = X.mean(0)
        _, _, Vt = np.linalg.svd(X - c, full_matrices=False); a = Vt[0]
        t = (X - c) @ a; r = np.linalg.norm((X - c) - np.outer(t, a), axis=1)
        if r[t > t.max() - 1].max() > r[t < t.min() + 1].max():
            a = -a; t = -t
        res = (c + a * t.min(), c + a * t.max(), a, float(r.max()))
        self._axis[gi] = res
        return res


def look(dirv, up=(0, 0, 1)):
    """相机基：dirv = 视线方向（从相机指向场景）"""
    f = np.asarray(dirv, float); f /= np.linalg.norm(f)
    u = np.asarray(up, float)
    if abs(f @ u) > 0.95:
        u = np.array([0, 1.0, 0])
    r = np.cross(f, u); r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return r, u, f


def render(items, dirv, W=1000, H=760, ss=2, margin=0.06, fit=None, up=(0, 0, 1)):
    """items: list of (tris[n,3,3], rgb, pid)。返回 (PIL RGBA, proj(pt)->(x,y) 像素)"""
    r, u, f = look(dirv, up)
    allT = np.concatenate([it[0] for it in items])
    cols = np.concatenate([np.tile(np.array(it[1], float), (len(it[0]), 1)) for it in items])
    pids = np.concatenate([np.full(len(it[0]), it[2], np.int32) for it in items])
    P2 = np.stack([allT @ r, allT @ u, allT @ f], -1)  # x,y,depth
    FP = P2 if fit is None else np.stack([fit @ r, fit @ u, fit @ f], -1).reshape(-1, 3)
    FPf = FP.reshape(-1, 3)
    x0, x1 = FPf[:, 0].min(), FPf[:, 0].max(); y0, y1 = FPf[:, 1].min(), FPf[:, 1].max()
    Ws, Hs = W * ss, H * ss
    sc = min(Ws * (1 - 2 * margin) / (x1 - x0), Hs * (1 - 2 * margin) / (y1 - y0))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2

    def to_px(X, Y):
        return (X - cx) * sc + Ws / 2, -(Y - cy) * sc + Hs / 2

    px, py = to_px(P2[..., 0], P2[..., 1]); pz = P2[..., 2]
    # 法线着色（双面）
    n = np.cross(allT[:, 1] - allT[:, 0], allT[:, 2] - allT[:, 0])
    nl = np.linalg.norm(n, axis=1); ok = nl > 1e-12
    n = n[ok] / nl[ok, None]; px, py, pz, cols, pids = px[ok], py[ok], pz[ok], cols[ok], pids[ok]
    nv = n @ f
    n = np.where(nv[:, None] > 0, -n, n)  # 朝向相机
    L1 = np.array(-f * 0.6 + u * 0.6 - r * 0.3); L1 /= np.linalg.norm(L1)
    lam = np.clip(n @ L1, 0, 1)
    shade = 0.55 + 0.45 * lam
    # 光栅化
    zbuf = np.full(Ws * Hs, np.inf); ibuf = np.full(Ws * Hs, -1, np.int64)
    xs0 = np.clip(np.floor(px.min(1)), 0, Ws - 1).astype(np.int64); xs1 = np.clip(np.ceil(px.max(1)), 0, Ws - 1).astype(np.int64)
    ys0 = np.clip(np.floor(py.min(1)), 0, Hs - 1).astype(np.int64); ys1 = np.clip(np.ceil(py.max(1)), 0, Hs - 1).astype(np.int64)
    w = xs1 - xs0 + 1; h = ys1 - ys0 + 1; cnt = w * h
    valid = (px.max(1) >= 0) & (px.min(1) < Ws) & (py.max(1) >= 0) & (py.min(1) < Hs)
    cnt = np.where(valid, cnt, 0)
    tri_ids = np.nonzero(cnt)[0]
    CH = 8_000_000
    start = 0
    cum = np.cumsum(cnt[tri_ids])
    while start < len(tri_ids):
        base = cum[start - 1] if start else 0
        end = np.searchsorted(cum, base + CH, side='right')
        end = max(end, start + 1)
        ids = tri_ids[start:end]; c = cnt[ids]
        idx = np.repeat(ids, c)
        off = np.arange(c.sum()) - np.repeat(np.cumsum(c) - c, c)
        qx = xs0[idx] + off % w[idx] + 0.5; qy = ys0[idx] + off // w[idx] + 0.5
        ax, ay = px[idx, 0], py[idx, 0]; bx, by = px[idx, 1], py[idx, 1]; cx_, cy_ = px[idx, 2], py[idx, 2]
        den = (by - cy_) * (ax - cx_) + (cx_ - bx) * (ay - cy_)
        den = np.where(np.abs(den) < 1e-12, 1e-12, den)
        l1 = ((by - cy_) * (qx - cx_) + (cx_ - bx) * (qy - cy_)) / den
        l2 = ((cy_ - ay) * (qx - cx_) + (ax - cx_) * (qy - cy_)) / den
        l3 = 1 - l1 - l2
        ins = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
        z = l1 * pz[idx, 0] + l2 * pz[idx, 1] + l3 * pz[idx, 2]
        key = (qy.astype(np.int64)) * Ws + qx.astype(np.int64)
        key, z, tid = key[ins], z[ins], idx[ins]
        o = np.lexsort((z, key)); key, z, tid = key[o], z[o], tid[o]
        first = np.ones(len(key), bool); first[1:] = key[1:] != key[:-1]
        key, z, tid = key[first], z[first], tid[first]
        better = z < zbuf[key]
        zbuf[key[better]] = z[better]; ibuf[key[better]] = tid[better]
        start = end
    hit = ibuf >= 0
    img = np.zeros((Ws * Hs, 4))
    img[hit, :3] = cols[ibuf[hit]] * shade[ibuf[hit], None]
    img[hit, 3] = 1
    # 描边：零件边界 + 深度跳变 + 折痕
    pidb = np.full(Ws * Hs, -1); pidb[hit] = pids[ibuf[hit]]
    pidb = pidb.reshape(Hs, Ws); zb = zbuf.reshape(Hs, Ws); nb = np.zeros((Ws * Hs, 3)); nb[hit] = n[ibuf[hit]]; nb = nb.reshape(Hs, Ws, 3)
    zf = np.where(np.isinf(zb), 1e9, zb)
    edge = np.zeros((Hs, Ws), bool)
    for dy, dx in ((0, 1), (1, 0)):
        a_p = pidb[:Hs - dy, :Ws - dx]; b_p = pidb[dy:, dx:]
        a_z = zf[:Hs - dy, :Ws - dx]; b_z = zf[dy:, dx:]
        a_n = nb[:Hs - dy, :Ws - dx]; b_n = nb[dy:, dx:]
        e = (a_p != b_p) | (np.abs(a_z - b_z) > 1.2) | (((a_n * b_n).sum(-1) < 0.82) & (a_p >= 0))
        edge[:Hs - dy, :Ws - dx] |= e
    img = img.reshape(Hs, Ws, 4)
    img[edge, :3] = img[edge, :3] * 0.25 + 0.05
    img[edge, 3] = 1
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), 'RGBA').resize((W, H), Image.LANCZOS)

    def proj(p):
        p = np.asarray(p, float)
        X, Y = to_px(p @ r, p @ u)
        return X / ss, Y / ss

    return im, proj, (r, u, f)
