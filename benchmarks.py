"""Diagnostic-only live window throughput check; normal play is unchanged."""
from pathlib import Path
import json
import time
from PySide6.QtCore import QTimer
from cat_model import ACTIONS


class LiveBenchmark:
    def __init__(self,pet,output):
        self.pet=pet
        self.output=Path(output)
        self.actions=list(ACTIONS)
        self.results=[]
        pet.fullscreen_timer.stop()
        pet.model.settings["hide_fullscreen"]=False
        pet.model.settings["roam"]=False
        pet.care_pending=None
        pet.ball_target=None
        # Force diagnostic loops so short one-shot actions can be measured for
        # two seconds of active playback. This does not modify files or saves.
        for name,info in pet.motion_info.items():
            if not name.startswith("bridge_"):
                info["once"]=False
        self.index=-1
        QTimer.singleShot(500,self.next)

    def next(self):
        self.index+=1
        if self.index>=len(self.actions):
            report={"version":"1.2.0","diagnostic_looping":True,"encoded_fps":64,
                "all_actions_rendered_at_least_60fps":all(r["render_fps"]>=60 for r in self.results),
                "states":self.results}
            self.output.parent.mkdir(parents=True,exist_ok=True)
            self.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
            self.pet.quit_app()
            return
        self.action=self.actions[self.index]
        self.pet.model.queue.clear()
        self.pet.model.start(self.action,500)
        self.pet.direction=1
        self.pet.urgent_animation=True
        self.started=time.monotonic()
        self.before=(self.pet.paint_count,self.pet.animator.bank.frame_events,self.pet.animator.non_identical_frames)
        QTimer.singleShot(2000,self.finish)

    def finish(self):
        end=time.monotonic()
        duration=end-self.started
        times=[t for t in self.pet.paint_times if self.started<=t<=end]
        gaps=sorted((b-a)*1000 for a,b in zip(times,times[1:]))
        self.results.append({"action":self.action,"seconds":round(duration,3),
            "render_fps":round((self.pet.paint_count-self.before[0])/duration,2),
            "animation_events_per_second":round((self.pet.animator.bank.frame_events-self.before[1])/duration,2),
            "non_identical_frames_per_second":round((self.pet.animator.non_identical_frames-self.before[2])/duration,2),
            "p95_frame_gap_ms":round(gaps[int(len(gaps)*.95)] if gaps else 0,2),
            "max_frame_gap_ms":round(max(gaps,default=0),2)})
        self.next()
