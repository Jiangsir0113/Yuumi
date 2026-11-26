"""Diagnostic-only live window throughput check; normal play is unchanged."""
from pathlib import Path
import json
import time
from PySide6.QtCore import QTimer
from cat_model import ACTIONS


class LiveBenchmark:
    def __init__(self,pet,output,version):
        self.pet=pet
        self.output=Path(output)
        self.version=version
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
            report={"version":self.version,"diagnostic_looping":True,"encoded_fps":64,
                "warmup_seconds_per_action":2,
                "all_actions_rendered_at_least_60fps":all(r["render_fps"]>=60 for r in self.results),
                "all_actions_sampled_at_least_60fps":all(
                    r["animation_events_per_second"]>=60 and r["steady_fallback_samples"]==0 for r in self.results),
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
        self.cold_started=time.monotonic()
        self.cold_counts=self.sampling_counts()
        QTimer.singleShot(2000,self.begin_measure)

    def sampling_counts(self):
        bank=self.pet.animator.bank
        return bank.selected_frame_events,bank.fallback_samples,bank.handoff_samples

    def begin_measure(self):
        self.started=time.monotonic()
        self.before=(self.pet.paint_count,self.pet.animator.bank.frame_events,self.pet.animator.non_identical_frames)
        self.steady_counts=self.sampling_counts()
        QTimer.singleShot(2000,self.finish)

    def finish(self):
        end=time.monotonic()
        duration=end-self.started
        times=[t for t in self.pet.paint_times if self.started<=t<=end]
        gaps=sorted((b-a)*1000 for a,b in zip(times,times[1:]))
        cold=[t for t in self.pet.paint_times if self.cold_started<=t<self.started]
        cold_gaps=[(b-a)*1000 for a,b in zip(cold,cold[1:])]
        selected,fallback,handoff=self.sampling_counts()
        self.results.append({"action":self.action,"seconds":round(duration,3),
            "render_fps":round((self.pet.paint_count-self.before[0])/duration,2),
            "animation_events_per_second":round((self.pet.animator.bank.frame_events-self.before[1])/duration,2),
            "decoded_frame_changes_per_second":round((selected-self.steady_counts[0])/duration,2),
            "steady_fallback_samples":fallback-self.steady_counts[1],
            "steady_handoff_samples":handoff-self.steady_counts[2],
            "cold_fallback_samples":self.steady_counts[1]-self.cold_counts[1],
            "cold_handoff_samples":self.steady_counts[2]-self.cold_counts[2],
            "non_identical_frames_per_second":round((self.pet.animator.non_identical_frames-self.before[2])/duration,2),
            "p95_frame_gap_ms":round(gaps[int(len(gaps)*.95)] if gaps else 0,2),
            "p99_frame_gap_ms":round(gaps[min(len(gaps)-1,int(len(gaps)*.99))] if gaps else 0,2),
            "cold_max_frame_gap_ms":round(max(cold_gaps,default=0),2),
            "max_frame_gap_ms":round(max(gaps,default=0),2)})
        self.next()
