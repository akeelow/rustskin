"""Plan v2: texel density and model normal smoothing per island; share of cut-out texels per island in cached doors."""
import sys, numpy as np
sys.path.insert(0, r"C:/Users/akeel/OneDrive/rustskin/skins/sauna/wooden-door/uv")
OBJ = r"C:/Users/akeel/OneDrive/rustskin/skins/sauna/wooden-door/originals/door.hinged.wood.obj"
v, vt, vn, tris = [], [], [], []
for line in open(OBJ):
    p = line.split()
    if not p: continue
    if p[0]=="v": v.append([float(x) for x in p[1:4]])
    elif p[0]=="vt": vt.append([float(x) for x in p[1:3]])
    elif p[0]=="vn": vn.append([float(x) for x in p[1:4]])
    elif p[0]=="f":
        idx=[tuple(int(a) for a in s.split("/")) for s in p[1:]]
        for k in range(1,len(idx)-1): tris.append((idx[0],idx[k],idx[k+1]))
v,vt,vn=map(np.array,(v,vt,vn))
P=np.array([[v[c[0]-1] for c in t] for t in tris]); T=np.array([[vt[c[1]-1] for c in t] for t in tris])
N=np.array([[vn[c[2]-1] for c in t] for t in tris]); VI=np.array([[c[1]-1 for c in t] for t in tris])
from analyze_uv import islands
ids=islands(VI)
fn=np.cross(P[:,1]-P[:,0],P[:,2]-P[:,0]); A3=np.linalg.norm(fn,axis=1)/2; fn/=np.linalg.norm(fn,axis=1,keepdims=True)+1e-12
A2=np.abs(np.cross(T[:,1]-T[:,0],T[:,2]-T[:,0]))/2
nn=N/np.linalg.norm(N,axis=2,keepdims=True)
ang=np.degrees(np.arccos(np.clip(np.einsum('tj,tkj->tk',fn,nn),-1,1))).max(1)
print("isl tris  area_m2  px/cm@1024  mm/px  bbox(x,y,z min..max)  normal dev deg (median/max)")
for i in np.unique(ids):
    m=ids==i; a3=A3[m].sum(); a2=A2[m].sum()
    d=np.sqrt(a2/a3)*1024/100 if a3>0 else 0
    pp=P[m].reshape(-1,3)
    print(f"{i:2d} {m.sum():4d} {a3:7.3f} {d:6.2f} {10/d if d else 0:5.2f}  x{pp[:,0].min():+.2f}..{pp[:,0].max():+.2f} y{pp[:,1].min():.2f}..{pp[:,1].max():.2f} z{pp[:,2].min():+.3f}..{pp[:,2].max():+.3f}   {np.median(ang[m]):5.1f}/{ang[m].max():5.1f}")

# --- cutout per island
import sys, json, numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, r"C:/Users/akeel/OneDrive/rustskin/skins/sauna/wooden-door/uv")
import analyze_uv as au
au.N=1024
P,T,VI=au.load(); ids=au.islands(VI)
owner,count=au.raster(T,ids)
base='C:/Program Files (x86)/Steam/steamapps/workshop/content/252490/'
W='C:/Users/akeel/OneDrive/rustskin/skins/sauna/wooden-door/'
names={0:'back low field',1:'mid rail',2:'FRONT',3:'low rail',4:'back up field',5:'top rail',6:'brace up',7:'brace low',8:'handle',9:'handle'}
tiles=[]
for i in ['3603679078','3663525831','3789166731','3793601148','3828029350']:
    m=json.load(open(base+i+'/manifest.txt')); cut=m['Groups'][0]['Floats']['_Cutoff']
    a=np.asarray(Image.open(base+i+'/_MainTex0.png').convert('RGBA'))
    # texture row 0 is top = v=1 ; raster in analyze_uv: check orientation by trying both
    al=a[...,3]
    for flip in (False,True):
        aa=al[::-1] if flip else al
        holes=(aa<cut*255)&(owner>=0)
        if flip==False: h0=holes.sum()
        else: h1=holes.sum()
    aa=al if h0<=h1 else al[::-1]  # pick orientation where fewer island texels are cut? ambiguous -> report both
    res=[]
    for k in range(10):
        msk=owner==k
        res.append(f"{names[k]}:{((al<cut*255)&msk).sum()/msk.sum()*100:.0f}%/{((al[::-1]<cut*255)&msk).sum()/msk.sum()*100:.0f}%")
    print(i,'cut',round(cut,2),' '.join(res))
