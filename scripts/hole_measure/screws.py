import sys, re, numpy as np, pickle, os
F = sys.argv[1]; out = sys.argv[2]
cache = out + '/groups.pkl'
if os.path.exists(cache):
    groups = pickle.load(open(cache, 'rb'))
else:
    groups = []; cur = None; buf = []
    with open(F, 'rb') as fh:
        for line in fh:
            if line.startswith(b'v '):
                buf.append(line[2:].split())
            elif line.startswith(b'g '):
                if cur is not None:
                    groups.append((cur, np.array(buf, float) * 1000)); buf = []
                cur = line[2:].decode('utf8', 'replace').strip()
    groups.append((cur, np.array(buf, float) * 1000))
    pickle.dump(groups, open(cache, 'wb'))
print(len(groups), 'groups')
def is_screw(n): return n.startswith('Hex socket') or 'Shoulder' in n
res = []
for gi, (name, V) in enumerate(groups):
    if not is_screw(name): continue
    c = V.mean(0); U, S, Vt = np.linalg.svd(V - c, full_matrices=False); a = Vt[0]
    t = (V - c) @ a; r = np.linalg.norm((V - c) - np.outer(t, a), axis=1)
    lo, hi = t.min(), t.max()
    # head = 端点附近半径更大的那一端
    rlo = r[t < lo + 1].max(); rhi = r[t > hi - 1].max()
    if rhi > rlo: a = -a; t = -t; lo, hi = -hi, -lo
    # now head at lo end
    L = hi - lo
    m = re.search(r'M(\d(?:\.\d)?)', name); d = float(m.group(1))
    # thread region: from tip back by thread length
    if 'Shoulder' in name:
        thr = 4.5 if d == 4 else 4.0
    else:
        thr = L - d  # cap head height ≈ d
    tip = hi; t0 = hi - thr
    hits = []
    for gj, (pn, P) in enumerate(groups):
        if gj == gi or is_screw(pn): continue
        # quick bbox prefilter
        q = P - c
        tp = q @ a
        sel = (tp > lo - 2) & (tp < hi + 2)
        if not sel.any(): continue
        rp = np.linalg.norm(q[sel] - np.outer(tp[sel], a), axis=1)
        near = rp < d / 2 + 4
        if not near.any(): continue
        tt = tp[sel][near]; rr = rp[near]
        # 分段：螺纹段 和 头下段
        def seg(mask):
            return (round(rr[mask].min() * 2, 2), round(tt[mask].min() - lo, 1), round(tt[mask].max() - lo, 1)) if mask.any() else None
        hits.append((pn, seg(tt >= t0 - 0.3), seg(tt < t0 - 0.3)))
    res.append(dict(name=name, idx=gi, L=round(L, 1), d=d, thr=round(thr, 1), hits=hits, center=c.round(1).tolist()))
pickle.dump(res, open(out + '/res.pkl', 'wb'))
for s in res:
    print(f"\n#{s['idx']} {s['name']}  L={s['L']} thread={s['thr']} @ {s['center']}")
    for pn, th, hd in s['hits']:
        print(f"   {pn:32s} thread-zone(holeØ,t0,t1)={th}  head-zone={hd}")
