"""Build the exact standalone deliverable from the current verified source."""
from pathlib import Path
import subprocess
import sys
import argparse
import os
import json
import shutil
import uuid

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
parser.add_argument("--portable-folder", action="store_true")
args = parser.parse_args()
OUTPUT = args.output_dir.resolve()
OUTPUT.mkdir(parents=True, exist_ok=True)
staging=ROOT/"build-assets"/uuid.uuid4().hex[:8]/"assets"
staging.mkdir(parents=True)
(staging/"motion").mkdir()
asset_info=json.loads((ROOT/"assets/manifest.json").read_text())
for name,info in asset_info.items():
    for i in range(info["frames"]):
        shutil.copy2(ROOT/"assets"/f"{name}-{i}.png",staging)
    shutil.copy2(ROOT/"assets/motion"/f"{name}.webp",staging/"motion")
for name in ["manifest.json","cat.ico","purr.wav"]:
    shutil.copy2(ROOT/"assets"/name,staging)
shutil.copy2(ROOT/"assets/motion/manifest.json",staging/"motion")
build_env=os.environ.copy()
build_deps=ROOT.parent/"build-deps"
if build_deps.exists():
    # Hook subprocesses must see the same NumPy wheel as module analysis.
    build_env["PYTHONPATH"]=str(build_deps)
numpy_libs=build_deps/"numpy.libs"
extra_binaries=[]
if numpy_libs.exists():
    for library in numpy_libs.glob("*.dll"):
        extra_binaries.extend(["--add-binary",str(library)+";numpy.libs"])
# Resolve Windows' native ICU from System32. Unrelated PDF/image tools on PATH
# can otherwise cause PyInstaller to bundle an incompatible third-party ICU.
build_env["PATH"]=os.pathsep.join(([str(numpy_libs)] if numpy_libs.exists() else [])+[sys.base_prefix,str(Path(sys.base_prefix)/"Scripts"),
    str(Path(os.environ["SystemRoot"])/"System32"),os.environ["SystemRoot"]])
subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
    "--onedir" if args.portable_folder else "--onefile", "--windowed", "--name", "悠米", "--icon", str(ROOT/"assets/cat.ico"),
    "--add-data", str(staging)+";assets",
    "--add-data", str(ROOT/"licenses")+";licenses",
    "--exclude-module", "PyQt6", "--exclude-module", "PyQt5",
    "--exclude-module", "tkinter", "--exclude-module", "matplotlib",
    "--exclude-module", "scipy", "--exclude-module", "torch",
    "--paths", str(ROOT.parent/"build-deps"),
    "--distpath", str(OUTPUT), "--workpath", str(ROOT/"build"),
    "--specpath", str(ROOT), *extra_binaries, str(ROOT/"main.py")], check=True, cwd=ROOT,env=build_env)
print(OUTPUT / "悠米.exe")
