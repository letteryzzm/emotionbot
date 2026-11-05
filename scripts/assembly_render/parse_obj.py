"""把参考装配 OBJ 解析成 npz：顶点(mm)、三角面、每个面属于哪个 group 实例。"""
import sys, numpy as np, re
F, OUT = sys.argv[1], sys.argv[2]
V = []; Fc = []; Fg = []; names = []; gi = -1
with open(F, 'rb') as fh:
    for line in fh:
        if line.startswith(b'v '):
            V.append(line[2:].split())
        elif line.startswith(b'f '):
            idx = [int(p.split(b'/')[0]) for p in line[2:].split()]
            for k in range(1, len(idx) - 1):
                Fc.append((idx[0], idx[k], idx[k + 1])); Fg.append(gi)
        elif line.startswith(b'g '):
            names.append(line[2:].decode('utf8', 'replace').strip()); gi += 1
V = np.array(V, np.float32) * 1000
Fc = np.array(Fc, np.int32) - 1
np.savez_compressed(OUT, V=V, F=Fc, G=np.array(Fg, np.int16), names=np.array(names))
print(V.shape, Fc.shape, len(names))
