import numpy as np, sys
sys.path.insert(0,'.')
from render import Scene, render
S=Scene('../../outputs/assembly/mesh.npz')
focus=[188,91,149,94,95,123,100]; screws=[87,117,112,120,124,97,107,178,163,182]
items=[]
for g in focus: items.append((S.tris(g),(0.62,0.74,0.9) if g==188 else (0.35,0.37,0.42),g))
E=14
fitp=[]
for s in screws:
    h,t,a,_=S.screw_axis(s); items.append((S.tris(s,-a*E),(0.95,0.55,0.15),s)); fitp.append(h-a*E)
a=np.mean([S.screw_axis(s)[2] for s in screws],0); a/=np.linalg.norm(a); print('axis',a)
perp=np.cross(a,[0,0,1]); perp=perp/np.linalg.norm(perp) if np.linalg.norm(perp)>0.1 else np.array([1.,0,0])
d=0.55*a+0.8*perp+0.3*np.array([0,0,-1.])
fit=np.concatenate([S.pts(g) for g in focus]+[np.array(fitp)])
im,proj,_=render(items,d,fit=fit)
im.save('/private/tmp/claude-501/-Users-lettery-Documents-zzm-note/a9a427e0-9bd2-4e6b-ad24-7dcb3fa11b9d/scratchpad/t1.png')
