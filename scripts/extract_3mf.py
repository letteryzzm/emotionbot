"""从 3mf 里按 object id 导出 STL（处理 components + transform）。用法: extract_3mf.py model.3mf/解压目录 id 输出.stl"""
import sys, re, struct, numpy as np, xml.etree.ElementTree as ET, os
root_dir, oid, out = sys.argv[1], sys.argv[2], sys.argv[3]
NS = {'m': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
files = {}
def load(path):
    if path not in files:
        files[path] = ET.parse(os.path.join(root_dir, path.lstrip('/'))).getroot()
    return files[path]
def tf(s):
    if not s: return np.eye(4)
    v = list(map(float, s.split())); M = np.eye(4)
    M[:3, :3] = np.array(v[:9]).reshape(3, 3).T  # 3mf 行向量约定
    M[:3, 3] = v[9:12]; return M
def tris(path, oid, M):
    r = load(path)
    for o in r.iter('{%s}object' % NS['m']):
        if o.get('id') != oid: continue
        mesh = o.find('m:mesh', NS)
        if mesh is not None:
            V = np.array([[float(v.get(k)) for k in 'xyz'] for v in mesh.find('m:vertices', NS)])
            F = np.array([[int(t.get(k)) for k in ('v1', 'v2', 'v3')] for t in mesh.find('m:triangles', NS)])
            V = V @ M[:3, :3].T + M[:3, 3]; return V[F]
        out = []
        for c in o.find('m:components', NS):
            p = c.get('{http://schemas.microsoft.com/3dmanufacturing/production/1105}path') or path
            out.append(tris(p, c.get('objectid'), M @ tf(c.get('transform'))))
        return np.concatenate(out)
R0 = load('3D/3dmodel.model'); M0 = np.eye(4)
for it in R0.iter('{%s}item' % NS['m']):
    if it.get('objectid') == oid: M0 = tf(it.get('transform'))  # 按原作者在打印盘上的摆放方向
T = tris('3D/3dmodel.model', oid, M0)
T = T - [T[..., 0].mean(), T[..., 1].mean(), T[..., 2].min()]  # 放到原点、底面 z=0
with open(out, 'wb') as f:
    f.write(b'\0' * 80); f.write(struct.pack('<I', len(T)))
    for t in T:
        n = np.cross(t[1] - t[0], t[2] - t[0]); n = n / (np.linalg.norm(n) or 1)
        f.write(struct.pack('<12fH', *n, *t.ravel(), 0))
print(out, len(T), 'tris, size', (T.reshape(-1, 3).max(0) - T.reshape(-1, 3).min(0)).round(2))
