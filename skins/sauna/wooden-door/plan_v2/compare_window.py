"""Plan v2: the window region of the atlas, front and back, ours vs cached skins (plan_v2/window_region_compare.jpg)."""
import sys, numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, r"C:/Users/akeel/OneDrive/rustskin/skins/sauna/wooden-door/uv")
import analyze_uv as au
P,T,VI=au.load()
def fit(mask):
    X=np.c_[P[mask].reshape(-1,3)[:,:2],np.ones(mask.sum()*3)]; Y=T[mask].reshape(-1,2)
    A,res,_,_=np.linalg.lstsq(X,Y,rcond=None); return A
front=(np.abs(P[:,:,2]-0.054).max(1)<1e-3)
ids=au.islands(VI); back=(ids==4)
Af=fit(front); Ab=fit(back)
def box(A,x0,x1,y0,y1):
    c=np.array([[x0,y0,1],[x1,y1,1]])@A; u0,u1=sorted(c[:,0]); v0,v1=sorted(c[:,1])
    return int(u0*1024),int((1-v1)*1024),int(u1*1024),int((1-v0)*1024)
bf=box(Af,-0.62,-0.02,1.15,1.93); bb=box(Ab,-0.62,-0.02,1.15,1.93)
print('front px box',bf,'back',bb, 'window uv front', box(Af,-0.52,-0.12,1.30,1.78))
base='C:/Program Files (x86)/Steam/steamapps/workshop/content/252490/'
W='C:/Users/akeel/OneDrive/rustskin/skins/sauna/wooden-door/'
rows=[('v1.2 ours',W+'export/Door_v1.2_diffuse.png',W+'export/Door_v1.2_normal.png'),
      ('original',W+'originals/logwood_window_doors_bc.png',W+'originals/logwood_window_doors_nrm.png')]
for i in ['3814305916','3828029350','3603679078','3789166731']:
    rows.append((i,base+i+'/_MainTex0.png',base+i+'/_BumpMap0.png'))
S=300
out=Image.new('RGB',(S*4+10,len(rows)*(S+18)),(30,30,30)); d=ImageDraw.Draw(out)
for r,(n,dp,npth) in enumerate(rows):
    for j,(p,b) in enumerate([(dp,bf),(npth,bf),(dp,bb),(npth,bb)]):
        im=Image.open(p).convert('RGB').resize((1024,1024),Image.LANCZOS).crop(b).resize((S,int(S*(b[3]-b[1])/(b[2]-b[0]))),Image.LANCZOS)
        out.paste(im,(j*S+(10 if j>1 else 0),r*(S+18)+18))
    d.text((4,r*(S+18)+3),n+'   front: diffuse | normal      back: diffuse | normal   (same atlas region, 1024)',fill=(255,255,255))
out.save(W+'plan_v2/window_region_compare.jpg',quality=88)
