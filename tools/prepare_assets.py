"""Extract generated art; deterministic alpha cleanup, scale, layout and previews only."""
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageFilter
from collections import deque
import json
import math
import random
import struct
import wave

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets"
OUT.mkdir(exist_ok=True)
CANVAS = (320, 260)
# One shared scale for each animation family, never independently fill each frame.
GROUPS = {
    "idle": ("idle", [0, 1, 2, 3, 4, 5], 220),
    "walk": ("walk_detail", list(range(12)), 175),
    "loaf": ("rest", [0, 1], 168),
    "sleep": ("rest", [2, 3], 148),
    "yawn": ("rest", [4, 5, 4], 220),
    "head": ("touch", [0, 1, 1, 0], 220),
    "chin": ("touch", [2, 3, 3, 2], 220),
    "back": ("touch", [4, 5, 5, 4], 210),
    "sniff": ("sniff_detail", list(range(6)), 210),
    "eat": ("care", [1, 2, 1, 2], 210),
    "lick": ("lick_detail", list(range(6)), 220),
    "groom": ("care_detail", [0, 1, 2, 3, 2, 1], 220),
    "drink": ("care_detail", [4, 5, 4, 5], 170),
    "refuse": ("moods", [0, 1, 1, 0], 220),
    "nuzzle": ("moods", [2, 3, 3, 2], 220),
    "knead": ("moods", [4, 5, 4, 5], 220),
    "paw": ("extras", [2, 3, 3, 2], 220),
    "crouch": ("play", [0, 1, 0, 1], 165),
    "pounce": ("pounce_detail", list(range(6)), 180),
    "ball": ("play", [4, 5, 4, 5], 205),
    "stretch": ("extras", [0, 1, 1, 0], 225),
    "wave": ("extras", [2, 3, 3, 2], 220),
    "look": ("extras", [4, 4, 5, 5], 220),
}


def remove_tiny_detached(im):
    width,height=im.size
    binary=bytearray(im.getchannel("A").point(lambda a: 1 if a>45 else 0).tobytes())
    kept=bytearray(len(binary))
    for start in range(len(binary)):
        if not binary[start]:
            continue
        todo=[start]
        binary[start]=0
        component=[]
        while todo:
            pos=todo.pop()
            component.append(pos)
            x,y=pos%width,pos//width
            for nxt in (pos-width if y else -1,pos+width if y<height-1 else -1,
                        pos-1 if x else -1,pos+1 if x<width-1 else -1):
                if nxt>=0 and binary[nxt]:
                    binary[nxt]=0
                    todo.append(nxt)
        if len(component)>=60:
            for pos in component:
                kept[pos]=255
    mask=Image.frombytes("L",im.size,bytes(kept)).filter(ImageFilter.MaxFilter(3))
    im.putalpha(ImageChops.multiply(im.getchannel("A"),mask))
    return im


def extract(path):
    source = Image.open(path).convert("RGBA")
    columns, rows = (4,3) if path.stem=="walk_detail" else (4,2) if path.stem.startswith("bridge_") else (3,2)
    im = source.copy()
    clean = []
    for r, g, b, a in im.get_flattened_data():
        delta = min(g, b) - r
        # A large cyan excess uniquely separates this warm-furred character.
        alpha = round(255 * max(0, min(1, (105 - delta) / 72))) if g > 110 and b > 110 else 255
        if alpha < 8:
            clean.append((0, 0, 0, 0))
        else:
            # Despill only cyan-contaminated edge pixels, preserve green eyes.
            if delta > 18 and b > 125:
                spill = min(delta - 18, 95)
                g, b = max(r, g - spill), max(r, b - spill)
            clean.append((r, g, b, min(a, alpha)))
    im.putdata(clean)
    # Recover complete connected poses across nominal grid lines. Generated ears
    # may cross an invisible slot boundary; fixed slicing would clip the ear and
    # leave a detached fragment in the preceding pose.
    width, height = im.size
    binary = bytearray(im.getchannel("A").point(lambda a: 1 if a > 65 else 0).tobytes())
    groups = [[] for _ in range(columns*rows)]
    for start in range(len(binary)):
        if not binary[start]:
            continue
        queue = deque([start])
        binary[start] = 0
        count = 0
        xmin = xmax = start % width
        ymin = ymax = start // width
        while queue:
            pos = queue.popleft()
            x, y = pos % width, pos // width
            count += 1
            xmin, xmax = min(xmin,x), max(xmax,x)
            ymin, ymax = min(ymin,y), max(ymax,y)
            for nxt in (pos-width if y else -1, pos+width if y<height-1 else -1,
                        pos-1 if x else -1, pos+1 if x<width-1 else -1):
                if nxt >= 0 and binary[nxt]:
                    binary[nxt] = 0
                    queue.append(nxt)
        if count > 500:
            col = min(columns-1, int(((xmin+xmax)/2)/width*columns))
            row = min(rows-1, int(((ymin+ymax)/2)/height*rows))
            groups[row*columns+col].append((count, (xmin,ymin,xmax+1,ymax+1)))
    poses = []
    for i, components in enumerate(groups):
        if not components:
            raise ValueError(f"Missing complete pose: {path} slot {i}")
        largest = max(c[0] for c in components)
        boxes = [b for area,b in components if area > largest*.025]
        bbox = (min(b[0] for b in boxes),min(b[1] for b in boxes),
                max(b[2] for b in boxes),max(b[3] for b in boxes))
        if bbox[0] <= 0 or bbox[1] <= 0 or bbox[2]>=width or bbox[3]>=height:
            raise ValueError(f"Clipped source pose: {path} slot {i}")
        bbox = (max(0,bbox[0]-4),max(0,bbox[1]-4),min(width,bbox[2]+4),min(height,bbox[3]+4))
        poses.append(im.crop(bbox))
    return poses


def main():
    sheets = {p.stem: extract(p) for p in (ROOT / "art-source").glob("*.png")}
    manifest = {}
    contacts = []
    for name, (sheet, indices, height) in GROUPS.items():
        raw = [sheets[sheet][i] for i in indices]
        # Sniffing and eating share the same visual size as a continuous sequence.
        family = sheets["care"][:3] if name == "eat" else raw
        scale = min(height / max(im.height for im in family), 300 / max(im.width for im in family))
        frames = []
        for j, pose in enumerate(raw):
            frame = Image.new("RGBA", CANVAS)
            pose = pose.resize((round(pose.width * scale), round(pose.height * scale)), Image.Resampling.LANCZOS)
            frame.alpha_composite(pose, ((320-pose.width)//2, 250-pose.height))
            frame=remove_tiny_detached(frame)
            frame.save(OUT / f"{name}-{j}.png")
            frames.append(frame)
        manifest[name] = {"frames": len(frames), "width": 320, "height": 260,
                          "bounds": list(frames[0].getbbox()), "source_sheet": sheet}
        duration = 150 if name == "walk" else (650 if name in {"sleep", "loaf"} else 320)
        # GIFs are preview exports only. Application uses full RGBA PNGs.
        bgframes = []
        for f in frames:
            bg = Image.new("RGB", CANVAS, "#f6f0e6")
            bg.paste(f, mask=f.getchannel("A"))
            bgframes.append(bg)
        bgframes[0].save(OUT / f"preview-{name}.gif", save_all=True,
                         append_images=bgframes[1:], duration=duration, loop=0)
        contacts.append((name, frames[0]))
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    contact = Image.new("RGB", (320*5, 300*math.ceil(len(contacts)/5)), "#f6f0e6")
    draw = ImageDraw.Draw(contact)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 22)
    for k, (name, f) in enumerate(contacts):
        x, y = k%5*320, k//5*300
        contact.paste(f, (x,y), f.getchannel("A"))
        draw.text((x+18, y+265), name, fill="#5c4635", font=font)
    contact.save(OUT / "action-contact.jpg", quality=92)
    icon = Image.open(OUT / "idle-0.png").crop((74, 20, 246, 192))
    icon.save(OUT / "cat.ico", sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
    # A quiet synthesized purr, optional and explicitly described as synthetic.
    rng = random.Random(12)
    rate = 22050
    with wave.open(str(OUT / "purr.wav"), "wb") as audio:
        audio.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        samples = bytearray()
        for i in range(rate*3):
            t = i/rate
            envelope = min(1, t*5, (3-t)*5)
            v = (math.sin(2*math.pi*48*t)+.3*math.sin(2*math.pi*96*t)+.12*rng.uniform(-1,1))
            v *= (.65+.35*math.sin(2*math.pi*1.1*t))*envelope*.13
            samples.extend(struct.pack("<h", round(v*32767)))
        audio.writeframes(samples)
    print(json.dumps({"states": len(manifest), "frames": sum(v["frames"] for v in manifest.values()), "assets": str(OUT)}))


if __name__ == "__main__":
    main()
