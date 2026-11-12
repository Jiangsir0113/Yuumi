"""Register generated posture bridges to exact approved endpoint sprites."""
from pathlib import Path
import json
from PIL import Image
from prepare_assets import extract, remove_tiny_detached

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/"assets"
BRIDGES={
    "sit_stand":("idle-0","walk-0",220,.46),
    "sit_loaf":("idle-0","loaf-0",220,.40),
    "loaf_sleep":("loaf-0","sleep-0",168,.46),
}
manifest=json.loads((ASSETS/"manifest.json").read_text())
for name,(start,end,height,seconds) in BRIDGES.items():
    raw=extract(ROOT/"art-source"/f"bridge_{name}.png")
    scale=min(height/raw[0].height,300/max(p.width for p in raw))
    frames=[]
    for i,pose in enumerate(raw):
        pose=pose.resize((round(pose.width*scale),round(pose.height*scale)),Image.Resampling.LANCZOS)
        frame=Image.new("RGBA",(320,260))
        frame.alpha_composite(pose,((320-pose.width)//2,250-pose.height))
        frames.append(remove_tiny_detached(frame))
    frames[0]=Image.open(ASSETS/f"{start}.png").convert("RGBA")
    frames[-1]=Image.open(ASSETS/f"{end}.png").convert("RGBA")
    for i,frame in enumerate(frames):
        frame.save(ASSETS/f"bridge_{name}-{i}.png")
    manifest[f"bridge_{name}"]={"frames":len(frames),"width":320,"height":260,
        "bounds":list(frames[0].getbbox()),"source_sheet":f"bridge_{name}",
        "bridge":True,"seconds":seconds}
(ASSETS/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
print("BRIDGES_READY",len(BRIDGES))
