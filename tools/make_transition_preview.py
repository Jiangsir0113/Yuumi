"""Export actual renderer output at 64fps, including rapid interruptions."""
from pathlib import Path
import sys
import json
import time
import subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from animation_engine import Animator,cv2,np
from PIL import Image,ImageDraw,ImageFont

root=Path(__file__).resolve().parents[1]
output=Path(sys.argv[1]).resolve()
output.mkdir(parents=True,exist_ok=True)
anim=Animator(root/"assets")
events=[(0,"idle"),(1.0,"head"),(1.8,"chin"),(2.4,"back"),(2.6,"head"),
        (3.4,"walk"),(4.5,"trot"),(5.6,"idle"),(6.4,"loaf"),(7.1,"sleep"),
        (7.45,"head"),(8.6,"eat"),(9.5,"chin"),(10.5,"groom"),(11.5,"idle")]
encoder=None
if len(sys.argv)>2:
    encoder=subprocess.Popen([sys.argv[2],"-y","-hide_banner","-loglevel","error",
        "-f","rawvideo","-pix_fmt","rgb24","-s","640x400","-r","64","-i","-",
        "-an","-c:v","libx264","-preset","fast","-crf","18","-pix_fmt","yuv420p",
        "-movflags","+faststart",str(output/"切换实录-64FPS.mp4")],stdin=subprocess.PIPE)
else:
    writer=cv2.VideoWriter(str(output/"切换实录-64FPS.mp4"),cv2.VideoWriter_fourcc(*"mp4v"),64,(640,400))
    assert writer.isOpened(),"Video encoder unavailable"
font=ImageFont.truetype("C:/Windows/Fonts/msyh.ttc",22)
labels={"idle":"安静陪伴","head":"摸头","chin":"挠下巴","back":"摸背",
        "walk":"慢走","trot":"小跑","loaf":"揣手","sleep":"入睡",
        "eat":"吃粮","groom":"洗脸"}
checks=[]
event_index=-1
action="idle"
for tick in range(13*64):
    now=tick/64
    if event_index+1<len(events) and now>=events[event_index+1][0]:
        event_index+=1
        action=events[event_index][1]
        before=anim.last.copy() if anim.last is not None else None
        first=anim.update(action,0,urgent=True)
        error=0 if before is None else float(np.abs(first.astype(np.float32)-before).max())
        checks.append({"second":now,"action":action,"first_frame_max_error":error})
    frame=anim.update(action,1/64,urgent=True)
    canvas=np.full((400,640,3),[247,241,231],dtype=np.uint8)
    rgb=frame[:,:,:3].astype(np.float32)+(255-frame[:,:,3:4])*(np.array([247,241,231])/255)
    canvas[92:352,160:480]=np.clip(rgb,0,255).astype(np.uint8)
    im=Image.fromarray(canvas)
    draw=ImageDraw.Draw(im)
    draw.text((320,38),"悠米 1.2 · "+labels[action],font=font,fill="#745638",anchor="mm")
    draw.text((320,376),"64 FPS · 可中断姿势过渡",font=font,fill="#9d8161",anchor="mm")
    if encoder:
        encoder.stdin.write(np.array(im).tobytes())
    else:
        writer.write(cv2.cvtColor(np.array(im),cv2.COLOR_RGB2BGR))
if encoder:
    encoder.stdin.close()
    assert encoder.wait()==0,"H.264 encoder failed"
else:
    writer.release()
anim.close()
(output/"transition-continuity.json").write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding="utf-8")
assert all(c["first_frame_max_error"]==0 for c in checks)
print("PREVIEW_READY",len(checks),flush=True)
