"""Extract generated v1.3 poses and register them for the existing renderer."""
from pathlib import Path
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent/'build-deps'))
import cv2
import numpy as np
from PIL import Image

assets=ROOT/'assets'
manifest=json.loads((assets/'manifest.json').read_text())

def clean(im):
    a=np.array(im.convert('RGBA'))
    _,labels,stats,_=cv2.connectedComponentsWithStats((a[:,:,3]>70).astype(np.uint8))
    if len(stats)<2:
        raise ValueError('Missing foreground')
    main=1+int(np.argmax(stats[1:,cv2.CC_STAT_AREA]))
    mask=cv2.dilate((labels==main).astype(np.uint8),np.ones((3,3),np.uint8))
    a[:,:,3]=np.where(mask>0,a[:,:,3],0)
    a[a[:,:,3]<12]=0
    result=Image.fromarray(a)
    return result.crop(result.getbbox())

def sheet(name):
    im=Image.open(ROOT/'art-source'/name).convert('RGBA')
    return [clean(im.crop((round(c*im.width/4),round(r*im.height/2),
                          round((c+1)*im.width/4),round((r+1)*im.height/2))))
            for r in range(2) for c in range(4)]

def save(name,raw,height,seconds,bridge=False):
    scale=min(height/max(p.height for p in raw),270/max(p.width for p in raw))
    frames=[]
    for pose in raw:
        pose=pose.resize((round(pose.width*scale),round(pose.height*scale)),Image.Resampling.LANCZOS)
        frame=Image.new('RGBA',(320,260))
        frame.alpha_composite(pose,((320-pose.width)//2,250-pose.height))
        frames.append(frame)
    if name=='bridge_stand_turn':
        frames[0]=Image.open(assets/'walk-0.png').convert('RGBA')
        frames[-1]=frames[0].transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    for i,frame in enumerate(frames):
        frame.save(assets/f'{name}-{i}.png')
    manifest[name]={'frames':len(frames),'width':320,'height':260,'bounds':list(frames[0].getbbox()),
                    'source_sheet':'v13-generated','seconds':seconds,'bridge':bridge}

poses=sheet('scratch-turn.png')
save('scratch',poses[:4],220,1.4)
save('bridge_stand_turn',poses[4:],175,.46,True)
care=sheet('prop-interactions.png')
save('ball',care[:4],205,1.328)
save('eat',care[4:],175,1.328)
save('drink',care[4:],175,1.328)
save('sniff',care[4:],175,2.)
prop=clean(Image.open(ROOT/'art-source/garlic-scratcher.png'))
prop.thumbnail((512,768),Image.Resampling.LANCZOS)
prop.save(assets/'props/garlic-scratcher.png')
(assets/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(ROOT/'qa').mkdir(exist_ok=True)
print('V13_ASSETS_READY',flush=True)
