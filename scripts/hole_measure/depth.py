import pickle, numpy as np, sys
S=sys.argv[1]
groups=pickle.load(open(S+'/groups.pkl','rb')); res={r['idx']:r for r in pickle.load(open(S+'/res.pkl','rb'))}
def axis(V):
    c=V.mean(0); _,_,Vt=np.linalg.svd(V-c,full_matrices=False); a=Vt[0]
    t=(V-c)@a; r=np.linalg.norm((V-c)-np.outer(t,a),axis=1)
    lo,hi=t.min(),t.max()
    if r[t>hi-1].max()>r[t<lo+1].max(): a=-a; lo,hi=-hi,-lo
    return c,a,lo
def prof(si, part):
    c,a,lo=axis(groups[si][1])
    for n,P in groups:
        if n!=part: continue
        q=P-c; t=q@a-lo; r=np.linalg.norm(q-np.outer(q@a,a),axis=1)
        m=(r<4)&(t>-5)&(t<30)
        if m.sum()==0: continue
        rows=sorted(set((round(x,1),round(2*y,2)) for x,y in zip(t[m],r[m])))
        print(f"  {groups[si][0]} -> {part}: (t,Ø) rings:", rows[:40])
for si,part in [(1,'TopBase'),(81,'JawBase'),(114,'TopBase'),(5,'CheekBone'),(8,'SkullFrame'),(87,'TopBase'),(116,'JawBase'),(85,'UpperLeftLip'),(141,'Part 37'),(3,'SnapEyemech v20'),(3,'SkullFrame')]:
    prof(si,part)
for n,P in groups:
    if n=='M4Insert':
        c,a,lo=axis(P); t=(P-c)@a; r=np.linalg.norm((P-c)-np.outer(t,a),axis=1)
        print('M4Insert len',round(t.max()-t.min(),2),'OD',round(2*r.max(),2),'ID',round(2*r.min(),2))
