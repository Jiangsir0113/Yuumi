"""Register inspected generated equipment and grounded interaction poses."""
from pathlib import Path
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent/'build-deps'))
import cv2
import numpy as np
from PIL import Image

def clean(im):
    a=np.array(im.convert('RGBA'))
    _,labels,stats,_=cv2.connectedComponentsWithStats((a[:,:,3]>70).astype(np.uint8))
    main=1+int(np.argmax(stats[1:,cv2.CC_STAT_AREA]))
    mask=cv2.dilate((labels==main).astype(np.uint8),np.ones((3,3),np.uint8))
    a[:,:,3]=np.where(mask,a[:,:,3],0);a[a[:,:,3]<12]=0
    im=Image.fromarray(a)
    return im.crop(im.getbbox())

assets=ROOT/'assets'
manifest=json.loads((assets/'manifest.json').read_text())
def row(name,row,rows=2):
    im=Image.open(ROOT/'art-source'/name)
    return [clean(im.crop((round(c*im.width/4),round(row*im.height/rows),round((c+1)*im.width/4),round((row+1)*im.height/rows)))) for c in range(4)]

def save(name,poses,height,seconds):
    factor=min(height/max(p.height for p in poses),270/max(p.width for p in poses))
    frames=[]
    for i,p in enumerate(poses):
        p=p.resize((round(p.width*factor),round(p.height*factor)),Image.Resampling.LANCZOS)
        frame=Image.new('RGBA',(320,260));frame.alpha_composite(p,((320-p.width)//2,250-p.height))
        frame.save(assets/f'{name}-{i}.png');frames.append(frame)
    manifest[name].update(frames=4,bounds=list(frames[0].getbbox()),source_sheet='v14-equipment',seconds=seconds)

save('scratch',row('scratch-turn.png',0),220,1.4)
care=row('equipment-feed.png',0,1)
save('eat',care,160,1.328)
save('sniff',care,160,2.)
care=row('equipment-care.png',1)
save('drink',care,160,1.328)
(assets/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
equipment={}
for name,height,contact in [('petkit-solo',215,[.25,.82]),('petkit-solo-se',120,[.16,.23]),('fregate-food',100,[.5,.5]),('fregate-treat',24,[.015,.60])]:
    im=clean(Image.open(ROOT/'art-source'/f'{name}.png'))
    im.thumbnail((768,768),Image.Resampling.LANCZOS)
    im.save(assets/'props'/f'{name}.png')
    equipment[name]={'width':im.width,'height':im.height,'logical_height':height,'contact':contact}
for name in ['petkit-solo-reverse','fregate-treat-reverse']:
    im=clean(Image.open(ROOT/'art-source'/f'{name}.png'))
    im.thumbnail((768,768),Image.Resampling.LANCZOS)
    im.save(assets/'props'/f'{name}.png')
(assets/'props/equipment-layout.json').write_text(json.dumps(equipment,indent=2),encoding='utf-8')
p=assets/'props/garlic-layout.json';layout=json.loads(p.read_text())
layout.update(logical_height=264,cat_reference_height=220,cat_height_ratio=1.2,rope_left=[.24,.54],rope_right=[.76,.54])
p.write_text(json.dumps(layout,indent=2),encoding='utf-8')
(ROOT/'qa').mkdir(exist_ok=True)
print('V14_ASSETS_READY',json.dumps(equipment),flush=True)
