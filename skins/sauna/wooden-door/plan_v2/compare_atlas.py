"""Plan v2: the whole atlas of cached Wooden Door skins vs ours (plan_v2/atlas_compare.jpg). .venv/Scripts/python skins/sauna/wooden-door/plan_v2/compare_atlas.py"""
from PIL import Image, ImageDraw
import numpy as np
base='C:/Program Files (x86)/Steam/steamapps/workshop/content/252490/'
W='C:/Users/akeel/OneDrive/rustskin/skins/sauna/wooden-door/'
skins=[('v1.2 (наш)',W+'export/Door_v1.2_diffuse.png',W+'export/Door_v1.2_normal.png')]
for i in ['3603679078','3663525831','3789166731','3793601148','3814305916','3828029350']:
    skins.append((i,base+i+'/_MainTex0.png',base+i+'/_BumpMap0.png'))
skins.append(('оригинал',W+'originals/logwood_window_doors_bc.png',W+'originals/logwood_window_doors_nrm.png'))
S=360
out=Image.new('RGB',(S*4,(S+20)*4),(40,40,40)); d=ImageDraw.Draw(out)
for k,(name,dp,np_) in enumerate(skins):
    r,c=divmod(k,2)
    for j,p in enumerate((dp,np_)):
        im=Image.open(p).convert('RGBA')
        a=np.asarray(im).copy()
        if j==0:
            al=a[...,3:4]/255.0; chk=((np.indices(a.shape[:2]).sum(0)//32)%2*60+90)[...,None]
            rgb=(a[...,:3]*al+chk*(1-al)).astype(np.uint8)
        else:
            rgb=a[...,:3]
            if rgb[...,2].mean()<100 and a[...,3].mean()>100: # DXT5nm style (AG)
                x=a[...,3]/255*2-1; y=a[...,1]/255*2-1; z=np.sqrt(np.clip(1-x*x-y*y,0,1))
                rgb=(np.stack([x,y,z],-1)*127.5+127.5).astype(np.uint8)
        t=Image.fromarray(rgb).resize((S,S),Image.LANCZOS)
        out.paste(t,(c*2*S+j*S,r*(S+20)+20))
    d.text((c*2*S+4,r*(S+20)+4),name,fill=(255,255,255))
out.save(W+'plan_v2/atlas_compare.jpg',quality=88)
