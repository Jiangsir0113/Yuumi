from pathlib import Path
import json
import os
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cat_model import ACTIONS

root = Path(__file__).resolve().parents[1]
exe = Path(sys.argv[1]).resolve()
output = root / "qa" / "packaged" / exe.parent.name
output.mkdir(parents=True,exist_ok=True)
empty = root / "qa" / "empty-working-directory"
empty.mkdir(parents=True,exist_ok=True)
env = os.environ.copy()
for key in ["PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QML2_IMPORT_PATH"]:
    env.pop(key,None)
env["PATH"] = str(Path(os.environ["SystemRoot"])/"System32")
result = subprocess.run([str(exe),"--self-test",str(output),"--state-file",str(root/"qa"/"packaged-state.json")],
    cwd=empty,env=env,timeout=120,capture_output=True)
print(json.dumps({"returncode":result.returncode,"stdout":result.stdout.decode(errors="replace"),"stderr":result.stderr.decode(errors="replace")},ensure_ascii=True),flush=True)
if result.returncode!=0:
    raise RuntimeError("The packaged executable failed; a stale report will not be accepted")
report = json.loads((output/"self-test.json").read_text(encoding="utf-8"))
assert result.returncode==0 and report["ok"] and report["frozen_executable"],report
assert report["version"]=="1.3.1" and report["smooth_webp_valid"] and report["scene_objects_valid"]
assert len(report["rendered_actions"])==len(ACTIONS)
print(json.dumps({"exit_code":result.returncode,"packaged":report["frozen_executable"],
                  "actions":len(report["rendered_actions"]),"ok":report["ok"],
                  "isolated_path":True,"empty_working_directory":True}))
