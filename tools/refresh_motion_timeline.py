"""Refresh encoded WebP timelines without recalculating motion vectors."""
from pathlib import Path
from PIL import Image
import json

root=Path(__file__).resolve().parents[1]/"assets"/"motion"
manifest=json.loads((root/"manifest.json").read_text())
for name,info in manifest["states"].items():
    ends=[]
    elapsed=0.
    with Image.open(root/f"{name}.webp") as movie:
        for i in range(movie.n_frames):
            movie.seek(i)
            movie.load()
            elapsed+=movie.info.get("duration",33)/1000
            ends.append(round(elapsed,6))
    info["frame_ends"]=ends
    info["duration"]=elapsed
(root/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
print("Timelines",len(manifest["states"]))
