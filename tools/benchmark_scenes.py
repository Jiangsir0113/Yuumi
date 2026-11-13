"""Real-time native scene test, including the independent prop windows."""
from pathlib import Path
import json
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QTimer,QObject,QEvent
from PySide6.QtWidgets import QApplication
from main import CatWindow,VERSION

class PaintMonitor(QObject):
    def __init__(self):super().__init__();self.times={}
    def eventFilter(self,obj,event):
        if event.type()==QEvent.Type.Paint:
            self.times.setdefault(id(obj),[]).append(time.monotonic())
        return False

out=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'qa/v13-scene-performance.json'
app=QApplication([]);app.setQuitOnLastWindowClosed(False)
pet=CatWindow(ROOT/'qa/scene-benchmark-state.json',testing=True)
pet.model.settings.update({'roam':False,'hide_fullscreen':False,'quiet':False,'click_through':False})
pet.model.energy=85;pet.model.satiety=25
monitor=PaintMonitor()
results=[]
actions=['scratch','track','ball','food','water','snack']
index=-1

def next_scene():
    global index,started,before,action,measuring
    index+=1
    if index==len(actions):
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps({'version':VERSION,'real_time':True,'warmup_seconds':5,'measure_seconds':3,'scenes':results},indent=2),encoding='utf-8')
        pet.quit_app();return
    action=actions[index]
    pet.perform(action)
    for window in pet.scene_view.windows.values():window.installEventFilter(monitor)
    QTimer.singleShot(5000,begin_measure)

def begin_measure():
    global started,before
    started=time.monotonic();before=pet.paint_count
    QTimer.singleShot(3000,finish)

def finish():
    end=time.monotonic();duration=end-started
    times=[t for t in pet.paint_times if started<=t<=end]
    gaps=sorted((b-a)*1000 for a,b in zip(times,times[1:]))
    props=[]
    for kind,window in pet.scene_view.windows.items():
        ts=[t for t in monitor.times.get(id(window),[]) if started<=t<=end]
        props.append({'kind':kind,'paint_fps':round(len(ts)/duration,2)})
    results.append({'activity':action,'render_fps':round((pet.paint_count-before)/duration,2),
                    'p95_frame_gap_ms':round(gaps[int(len(gaps)*.95)] if gaps else 0,2),
                    'max_frame_gap_ms':round(max(gaps,default=0),2),'props':props,
                    'stage':pet.scene.activity.stage if pet.scene.activity else None})
    next_scene()

pet.show()
QTimer.singleShot(500,next_scene)
app.exec()
print('SCENE_BENCHMARK_READY',len(results))
