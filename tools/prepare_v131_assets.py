"""Register the generated low scratch cycle; do not change other cat artwork."""
from pathlib import Path
import sys
import json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent/'build-deps'))
import cv2
import numpy as np
from PIL import Image

source=Image.open(ROOT/'art-source/scratch-low.png').convert('RGBA')
poses=[]
for row in range(2):
    for col in range(2):
        im=source.crop((round(col*source.width/2),round(row*source.height/2),round((col+1)*source.width/2),round((row+1)*source.height/2)))
        a=np.array(im)
        _,labels,stats,_=cv2.connectedComponentsWithStats((a[:,:,3]>70).astype(np.uint8))
        main=1+int(np.argmax(stats[1:,cv2.CC_STAT_AREA]))
        mask=cv2.dilate((labels==main).astype(np.uint8),np.ones((3,3),np.uint8))
        a[:,:,3]=np.where(mask,a[:,:,3],0);a[a[:,:,3]<12]=0
        im=Image.fromarray(a);poses.append(im.crop(im.getbbox()))
scale=min(175/max(p.height for p in poses),270/max(p.width for p in poses))
frames=[]
for i,im in enumerate(poses):
    im=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.LANCZOS)
    frame=Image.new('RGBA',(320,260));frame.alpha_composite(im,((320-im.width)//2,250-im.height))
    frame.save(ROOT/'assets'/f'scratch-{i}.png');frames.append(frame)
path=ROOT/'assets/manifest.json';manifest=json.loads(path.read_text())
manifest['scratch'].update({'bounds':list(frames[0].getbbox()),'source_sheet':'scratch-low','seconds':1.4})
path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(ROOT/'qa').mkdir(exist_ok=True)
print('LOW_SCRATCH_READY',frames[0].getbbox())
