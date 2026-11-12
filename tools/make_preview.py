from pathlib import Path
import json
import bisect
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[1]
assets = root/"assets"
out = root.parents[1]/"outputs"/"Youmi"
manifest = json.loads((assets/"manifest.json").read_text())
states = [("idle","慢眨眼，陪你发呆",2.2),("walk","自己散个步",6),
          ("head","摸摸头，呼噜…",2),("sleep","蜷起来睡觉",.65),
          ("eat","咔嚓咔嚓吃猫粮",3),("knead","小爪子踩奶",3)]
font=ImageFont.truetype("C:/Windows/Fonts/msyh.ttc",16)
movies={}
for state,_,_ in states:
    decoded=[]
    ends=[]
    elapsed=0.
    with Image.open(assets/"motion"/f"{state}.webp") as movie:
        for i in range(movie.n_frames):
            movie.seek(i)
            movie.load()
            decoded.append(movie.convert("RGBA").copy())
            elapsed+=movie.info.get("duration",33)/1000
            ends.append(elapsed)
    movies[state]=(decoded,ends)
frames=[]
for tick in range(100):
    canvas=Image.new("RGB",(768,496),"#f7f1e7")
    draw=ImageDraw.Draw(canvas)
    for i,(state,label,fps) in enumerate(states):
        x,y=i%3*256,i//3*248
        decoded,ends=movies[state]
        index=min(len(decoded)-1,bisect.bisect_right(ends,(tick/30)%ends[-1]))
        frame=decoded[index].resize((256,208),Image.Resampling.LANCZOS)
        canvas.paste(frame,(x,y+8),frame.getchannel("A"))
        draw.text((x+128,y+224),label,font=font,fill="#785c3e",anchor="mm")
    frames.append(canvas)
frames[0].save(out/"动作预览.gif",save_all=True,append_images=frames[1:],duration=33,loop=0,optimize=False)
print(out/"动作预览.gif")
