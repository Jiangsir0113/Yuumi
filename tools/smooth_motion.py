"""Build motion-compensated 64fps WebP animations from approved sprite pixels.

Offline asset encoding. Runtime playback is implemented in animation_engine.py.
"""
from pathlib import Path
import hashlib
import json
import math
import sys
import argparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent/"build-deps"))
sys.path.insert(0,str(ROOT))
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from cat_model import ACTIONS

ASSETS=ROOT/"assets"
OUT=ASSETS/"motion"
OUT.mkdir(exist_ok=True)
FPS=64
ONCE={"yawn":3.,"stretch":4.,"refuse":2.,"pounce":.9}
flow_cache={}


def prepare_pair(a,b):
    key=hashlib.sha256(a.tobytes()+b.tobytes()).hexdigest()
    if key in flow_cache:
        return flow_cache[key]
    # Neutral background creates a clean silhouette for dense inverse search.
    af=a.astype(np.float32)/255
    bf=b.astype(np.float32)/255
    ag=np.round((af[:,:,:3]*af[:,:,3:4]+.4*(1-af[:,:,3:4]))*255).astype(np.uint8)
    bg=np.round((bf[:,:,:3]*bf[:,:,3:4]+.4*(1-bf[:,:,3:4]))*255).astype(np.uint8)
    g0=cv2.cvtColor(ag,cv2.COLOR_RGB2GRAY)
    g1=cv2.cvtColor(bg,cv2.COLOR_RGB2GRAY)
    dis=cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    dis.setFinestScale(0)
    dis.setGradientDescentIterations(48)
    dis.setVariationalRefinementIterations(8)
    forward=dis.calc(g0,g1,None)
    backward=dis.calc(g1,g0,None)
    # Limit spurious extrapolation outside moving silhouettes.
    forward=np.clip(forward,-42,42)
    backward=np.clip(backward,-42,42)
    af[:,:,:3]*=af[:,:,3:4]
    bf[:,:,:3]*=bf[:,:,3:4]
    flow_cache[key]=(af,bf,forward,backward)
    return flow_cache[key]


def between(a,b,t):
    if t<.0001 or np.array_equal(a,b):
        return Image.fromarray(a)
    if t>.9999:
        return Image.fromarray(b)
    af,bf,forward,backward=prepare_pair(a,b)
    height,width=a.shape[:2]
    x,y=np.meshgrid(np.arange(width,dtype=np.float32),np.arange(height,dtype=np.float32))
    wa=cv2.remap(af,x-forward[:,:,0]*t,y-forward[:,:,1]*t,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
    wb=cv2.remap(bf,x-backward[:,:,0]*(1-t),y-backward[:,:,1]*(1-t),cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
    mixed=(1-t)*wa+t*wb
    alpha=mixed[:,:,3:4]
    mixed[:,:,:3]=np.divide(mixed[:,:,:3],alpha,out=np.zeros_like(mixed[:,:,:3]),where=alpha>.003)
    mixed[alpha[:,:,0]<.015]=0
    return Image.fromarray(np.round(np.clip(mixed,0,1)*255).astype(np.uint8))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--states",nargs="+")
    args=parser.parse_args()
    manifest=json.loads((ASSETS/"manifest.json").read_text())
    report=json.loads((OUT/"manifest.json").read_text()) if args.states else {"fps":FPS,"renderer_target_fps":120,"states":{},"method":"bidirectional DIS flow on premultiplied RGBA, generated source pixels"}
    review=[]
    for name,info in manifest.items():
        if args.states and name not in args.states:
            continue
        source=[np.array(Image.open(ASSETS/f"{name}-{i}.png").convert("RGBA")) for i in range(info["frames"])]
        rate=next((a.keyframe_fps for a in ACTIONS.values() if a.sprite==name),16)
        once=name in ONCE or info.get("bridge",False)
        duration=info.get("seconds",ONCE.get(name,len(source)/rate))
        count=max(2,round(duration*FPS))
        frames=[]
        for k in range(count):
            phase=k/(count-1)*(len(source)-1) if once else k/count*len(source)
            idx=int(phase)
            t=phase-idx
            # Ease at held endpoints without altering the walk cycle's cadence.
            if name not in {"walk","knead","groom"}:
                t=t*t*(3-2*t)
            frame=between(source[min(idx,len(source)-1)],source[min(idx+1,len(source)-1) if once else (idx+1)%len(source)],t)
            frames.append(frame)
        durations=[round((i+1)*1000/FPS)-round(i*1000/FPS) for i in range(count)]
        frames[0].save(OUT/f"{name}.webp",save_all=True,append_images=frames[1:],
            duration=durations,loop=1 if once else 0,lossless=True,method=4,allow_mixed=False)
        # The encoder merges held identical frames; retain their exact timeline.
        ends=[]
        elapsed=0.
        with Image.open(OUT/f"{name}.webp") as encoded:
            for index in range(encoded.n_frames):
                encoded.seek(index)
                encoded.load()
                elapsed+=encoded.info.get("duration",33)/1000
                ends.append(round(elapsed,6))
        # Metrics quantify the reduction of visible step changes, not frame repeats.
        def delta(a,b):
            a=np.array(a,dtype=np.float32)/255;b=np.array(b,dtype=np.float32)/255
            a[:,:,:3]*=a[:,:,3:4];b[:,:,:3]*=b[:,:,3:4]
            return float(np.abs(a-b).mean())
        old=max(delta(Image.fromarray(source[i]),Image.fromarray(source[(i+1)%len(source)])) for i in range(len(source)))
        new=max(delta(frames[i],frames[i+1]) for i in range(len(frames)-1))
        report["states"][name]={"source_frames":len(source),"output_frames":count,"fps":FPS,"once":once,
            "frame_ends":ends,"duration":elapsed,
            "source_max_step":round(old,6),"output_max_step":round(new,6)}
        if name in {"walk","head","groom","pounce","roll"}:
            # Source endpoint, quarter, halfway, three-quarter, next endpoint.
            samples=[between(source[0],source[min(1,len(source)-1)],t) for t in [0,.25,.5,.75,1]]
            review.append((name,samples))
        print(name,count,flush=True)
    (OUT/"manifest.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    sheet=Image.new("RGB",(320*5,290*len(review)),"#f7f1e7")
    draw=ImageDraw.Draw(sheet)
    font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf",18)
    for row,(name,frames) in enumerate(review):
        for col,frame in enumerate(frames):
            sheet.paste(frame,(col*320,row*290),frame.getchannel("A"))
            draw.text((col*320+10,row*290+265),f"{name}: {col*25}%",font=font,fill="#72583c")
    if review:
        sheet.save(ROOT/"qa"/("motion-between-review-"+"-".join(args.states)+".jpg" if args.states else "motion-between-review.jpg"),quality=92)
    print("MOTION_READY",sum(v["output_frames"] for v in report["states"].values()),flush=True)


if __name__=="__main__":
    main()
