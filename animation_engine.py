"""Interruptible posture graph and phase-continuous 64fps sprite playback.

Generated poses remain the artwork. This module only decodes, registers,
motion-compensates and samples those pixels; it does not draw a replacement cat.
"""
from __future__ import annotations
from collections import OrderedDict, deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import bisect
import json
import math
import sys

if not getattr(sys,"frozen",False):
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"build-deps"))
import cv2
import numpy as np
from PIL import Image
from PySide6.QtGui import QImage
from cat_model import ACTIONS

cv2.setNumThreads(1)
WIDTH,HEIGHT=320,260
GRID_X,GRID_Y=np.meshgrid(np.arange(WIDTH,dtype=np.float32),np.arange(HEIGHT,dtype=np.float32))
DIRECTIONAL={"walk","trot","crouch","pounce","sniff","eat","treat","drink","ball","track","scratch"}
STANDING={"walk","trot","back","sniff","eat","treat","drink","crouch","pounce","stretch","scratch"}
EDGES={
    "stand_right":("sit","stand_right","bridge_sit_stand",False,.46),
    "stand_left":("sit","stand_left","bridge_sit_stand",True,.46),
    "loaf":("sit","loaf","bridge_sit_loaf",False,.40),
    "sleep":("loaf","sleep","bridge_loaf_sleep",False,.46),
    "turn":("stand_right","stand_left","bridge_stand_turn",False,.46),
}


def premultiply(array):
    result=array.copy()
    result[:,:,:3]=((array[:,:,:3].astype(np.uint16)*array[:,:,3:4].astype(np.uint16)+127)//255).astype(np.uint8)
    return result


def qimage(array):
    array=np.ascontiguousarray(array)
    return QImage(array.data,WIDTH,HEIGHT,WIDTH*4,QImage.Format.Format_RGBA8888_Premultiplied).copy()


def descriptor(array):
    return cv2.resize(array,(32,26),interpolation=cv2.INTER_AREA).astype(np.float32)


class PixelBlend:
    """Short, current-pose to moving-pose blend with subpixel correspondence."""
    def __init__(self,start,target):
        self.start=start.copy()
        def gray(a):
            rgb=a[:,:,:3].astype(np.float32)+(255-a[:,:,3:4])*.36
            g=cv2.cvtColor(np.clip(rgb,0,255).astype(np.uint8),cv2.COLOR_RGB2GRAY)
            return cv2.resize(g,(160,130),interpolation=cv2.INTER_AREA)
        a,b=gray(start),gray(target)
        dis=cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST)
        dis.setFinestScale(0)
        dis.setGradientDescentIterations(12)
        dis.setVariationalRefinementIterations(2)
        self.forward=cv2.resize(dis.calc(a,b,None),(WIDTH,HEIGHT))*2
        self.backward=cv2.resize(dis.calc(b,a,None),(WIDTH,HEIGHT))*2
        self.forward=np.clip(self.forward,-36,36)
        self.backward=np.clip(self.backward,-36,36)

    def sample(self,target,t):
        if t<=0:
            return self.start.copy()
        if t>=1:
            return target
        t=t*t*(3-2*t)
        a=cv2.remap(self.start,GRID_X-self.forward[:,:,0]*t,GRID_Y-self.forward[:,:,1]*t,
                    cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
        b=cv2.remap(target,GRID_X-self.backward[:,:,0]*(1-t),GRID_Y-self.backward[:,:,1]*(1-t),
                    cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
        return cv2.addWeighted(a,1-t,b,t,0)


class PostureGraph:
    def __init__(self):
        self.node="sit"
        self.edge=None
        self.progress=0.
        self.velocity=0.
        self.goal="sit"
        self.urgent=False

    @staticmethod
    def path(start,goal):
        queue=deque([(start,[])])
        seen={start}
        while queue:
            node,path=queue.popleft()
            if node==goal:
                return path
            for key,(a,b,*_) in EDGES.items():
                nxt=b if node==a else a if node==b else None
                if nxt is not None and nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt,path+[(key,nxt)]))
        raise ValueError("Unreachable posture")

    def set_goal(self,goal,urgent=False):
        self.goal=goal
        self.urgent=urgent

    def advance(self,dt):
        if self.edge is None and self.node!=self.goal:
            self.edge,nxt=self.path(self.node,self.goal)[0]
            a,b,*_=EDGES[self.edge]
            self.progress=0. if self.node==a else 1.
            self.velocity=0.
            self.node=None
        if self.edge is None:
            return
        steps=max(1,math.ceil(dt/.008))
        for _ in range(steps):
            step=dt/steps
            if self.edge is None:
                if self.node!=self.goal:
                    self.advance(step)
                continue
            a,b,_,_,seconds=EDGES[self.edge]
            # Cycles are allowed: choose the nearest endpoint's remaining route.
            # Penalize routes that immediately retrace the current edge.
            def cost(node):
                path=self.path(node,self.goal)
                if path and path[0][0]==self.edge:
                    return float("inf")
                return sum(EDGES[key][4] for key,_ in path)
            ca=self.progress*seconds+cost(a)
            cb=(1-self.progress)*seconds+cost(b)
            sign=1 if cb<ca else -1
            speed=sign/(seconds*(.78 if self.urgent else 1.))
            self.velocity+=(speed-self.velocity)*(1-math.exp(-step/.045))
            self.progress+=self.velocity*step
            if self.progress<=0 and sign<0:
                self.node=a
                self.edge=None
                self.progress=0
                self.velocity=0
            elif self.progress>=1 and sign>0:
                self.node=b
                self.edge=None
                self.progress=1
                self.velocity=0

    @property
    def ready(self):
        return self.edge is None and self.node==self.goal


class MotionBank:
    """Background clip decoding with bounded memory and a live keyframe fallback."""
    def __init__(self,assets,cache_mb=192):
        self.assets=Path(assets)
        self.source_info=json.loads((self.assets/"manifest.json").read_text())
        self.info=json.loads((self.assets/"motion/manifest.json").read_text())["states"]
        self.sources={}
        self.descriptors={}
        for name,info in self.source_info.items():
            frames=[]
            for i in range(info["frames"]):
                with Image.open(self.assets/f"{name}-{i}.png") as im:
                    frames.append(premultiply(np.array(im.convert("RGBA"))))
            self.sources[name]=frames
            self.descriptors[name]=[descriptor(a) for a in frames]
        self.executor=ThreadPoolExecutor(max_workers=2,thread_name_prefix="Youmi-motion")
        self.pending=OrderedDict()
        self.decoded=OrderedDict()
        self.live_pairs=OrderedDict()
        self.cache_bytes=cache_mb*1024*1024
        self.decoded_bytes=0
        self.pending_sizes={}
        self.current=None
        self.errors={}
        self.pinned={key for key in self.info if key.startswith("bridge_")}
        self.warm=deque(sorted(self.pinned))
        self.frame_events=0
        self.last_index=None
        self.closed=False
        self.prefetch("idle")
        if self.warm:
            self.prefetch(self.warm.popleft())

    def _decode(self,key):
        with Image.open(self.assets/"motion"/f"{key}.webp") as movie:
            frames=np.empty((movie.n_frames,HEIGHT,WIDTH,4),dtype=np.uint8)
            for i in range(movie.n_frames):
                movie.seek(i)
                frames[i]=premultiply(np.array(movie.convert("RGBA")))
        return frames

    def _collect(self,current):
        for key,future in list(self.pending.items()):
            if future.done():
                self.pending.pop(key)
                self.pending_sizes.pop(key,None)
                if not future.cancelled():
                    try:
                        frames=future.result()
                    except Exception as exc:
                        self.errors[key]=str(exc)
                        continue
                    self.decoded[key]=frames
                    self.decoded_bytes+=frames.nbytes
        while self.decoded_bytes>self.cache_bytes and len(self.decoded)>1:
            key,frames=self.decoded.popitem(last=False)
            if key==current or key in self.pinned:
                self.decoded[key]=frames
                if all(k==current or k in self.pinned for k in self.decoded):
                    break
                continue
            self.decoded_bytes-=frames.nbytes
        if self.warm and len(self.pending)<2:
            if self.prefetch(self.warm[0]):
                self.warm.popleft()

    def prefetch(self,key):
        if self.closed or key in self.errors:
            return False
        if key in self.pending or key in self.decoded:
            return True
        if len(self.pending)>=2:
            return False
        size=len(self.info[key]["frame_ends"])*WIDTH*HEIGHT*4
        used=self.decoded_bytes+sum(self.pending_sizes.values())
        for old in list(self.decoded):
            if used+size<=self.cache_bytes:
                break
            if old==self.current or old in self.pinned:
                continue
            frames=self.decoded.pop(old)
            self.decoded_bytes-=frames.nbytes
            used-=frames.nbytes
        if used+size>self.cache_bytes:
            return False
        self.pending_sizes[key]=size
        self.pending[key]=self.executor.submit(self._decode,key)
        return True

    def nearest_phase(self,key,frame):
        target=descriptor(frame)
        scores=[float(np.square(d-target).mean()) for d in self.descriptors[key]]
        index=int(np.argmin(scores))
        denominator=max(1,len(scores)-1) if self.info[key]["once"] else len(scores)
        return index/denominator*self.info[key]["duration"]

    def sample(self,key,seconds,absolute=False):
        self.current=key
        self._collect(key)
        self.prefetch(key)
        info=self.info[key]
        duration=info["duration"]
        phase=min(max(0.,seconds),max(0.,duration-.000001)) if info["once"] or absolute else seconds%duration
        index=min(len(info["frame_ends"])-1,bisect.bisect_right(info["frame_ends"],phase))
        token=(key,int(phase*info["fps"]))
        if token!=self.last_index:
            self.frame_events+=1
            self.last_index=token
        if key in self.decoded:
            frames=self.decoded[key]
            self.decoded.move_to_end(key)
            return frames[min(index,len(frames)-1)]
        # A first-time action remains live while its full 64fps clip is decoded.
        source=self.sources[key]
        p=phase/duration*(len(source)-1 if info["once"] else len(source))
        i=min(len(source)-1,int(p))
        j=min(len(source)-1,i+1) if info["once"] else (i+1)%len(source)
        t=p-i
        # Never compute optical flow or wait for a worker in the GUI path.
        t=t*t*(3-2*t)
        return cv2.addWeighted(source[i],1-t,source[j],t,0)

    def close(self):
        if not self.closed:
            self.closed=True
            self.executor.shutdown(wait=False,cancel_futures=True)


class Animator:
    def __init__(self,assets):
        self.bank=MotionBank(assets)
        self.graph=PostureGraph()
        self.action="idle"
        self.phase=0.
        self.phase_speed=1.
        self.clock=0.
        self.direction=1
        self.last=None
        self.visual_key=None
        self.blend=None
        self.blend_elapsed=0.
        self.force_blend=False
        self.switches=deque(maxlen=128)
        self.interruptions=0
        self.non_identical_frames=0
        self.flow_worker=ThreadPoolExecutor(max_workers=1,thread_name_prefix="Youmi-blend")
        self.flow_future=None
        self.blend_start=None
        self.hit_mirrored=False

    @staticmethod
    def posture(action,direction):
        if action=="sleep":
            return "sleep"
        if action=="loaf":
            return "loaf"
        if action in STANDING:
            return "stand_left" if action in DIRECTIONAL and direction<0 else "stand_right"
        return "sit"

    def request(self,action,direction=1,urgent=False):
        if action not in ACTIONS:
            raise ValueError("Removed or unknown action")
        if action==self.action and direction==self.direction:
            self.graph.urgent=self.graph.urgent or urgent
            return
        old=self.action
        if self.graph.edge is not None or self.blend is not None:
            self.interruptions+=1
        same_clip=ACTIONS[old].sprite==ACTIONS[action].sprite
        key=ACTIONS[action].sprite
        if not same_clip:
            frame=self.last[:,::-1] if self.last is not None and action in DIRECTIONAL and direction<0 else self.last
            self.phase=0. if self.bank.info[key]["once"] or frame is None else self.bank.nearest_phase(key,frame)
        self.action,self.direction=action,direction
        self.graph.set_goal(self.posture(action,direction),urgent)
        self.bank.prefetch(key)
        # On an in-progress edge, reversal uses the exact current edge position.
        self.force_blend=self.last is not None and (self.blend is not None or (self.graph.edge is None and not same_clip))
        self.switches.append({"from":old,"to":action,"phase":round(self.phase,4),
            "posture_edge":self.graph.edge,"posture_progress":round(self.graph.progress,4)})

    def update(self,action,dt,direction=1,urgent=False):
        requested=action!=self.action or direction!=self.direction
        self.request(action,direction,urgent)
        dt=max(0.,min(dt,.25))
        if not requested and dt==0 and self.last is not None:
            return self.last
        self.clock+=dt
        speed=1.65 if action=="trot" else 1.
        self.phase_speed+=(speed-self.phase_speed)*(1-math.exp(-dt/.10))
        ready_before=self.graph.ready
        self.graph.advance(dt)
        if ready_before and self.graph.ready and self.blend_start is None:
            self.phase+=dt*self.phase_speed
        if self.graph.edge is not None:
            a,b,key,mirrored,_=EDGES[self.graph.edge]
            visual=("bridge",self.graph.edge)
            target=self.bank.sample(key,self.graph.progress*self.bank.info[key]["duration"],absolute=True)
        else:
            key=ACTIONS[action].sprite
            mirrored=action in DIRECTIONAL and direction<0
            visual=("clip",key,mirrored)
            target=self.bank.sample(key,self.phase)
        if mirrored:
            target=np.ascontiguousarray(target[:,::-1])
        self.hit_mirrored=mirrored
        # A common breathing clock never resets when the action changes.
        breath=1+math.sin(self.clock*2)*.0045
        lift=-14*math.sin(min(1.,self.phase/self.bank.info[key]["duration"])*math.pi) if action=="pounce" and self.graph.ready else 0.
        transform=np.array([[1,0,0],[0,breath,250*(1-breath)+lift]],dtype=np.float32)
        target=cv2.warpAffine(target,transform,(WIDTH,HEIGHT),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
        new_blend=self.last is not None and (visual!=self.visual_key or self.force_blend)
        if new_blend:
            if self.flow_future is not None:
                self.flow_future.cancel()
            self.blend_start=self.last.copy()
            self.blend=None
            self.flow_assist=0.
            self.flow_future=self.flow_worker.submit(PixelBlend,self.blend_start,target.copy())
            self.blend_elapsed=0.
        self.force_blend=False
        self.visual_key=visual
        if self.blend_start is not None:
            if not new_blend:
                self.blend_elapsed+=dt
            t=min(1.,self.blend_elapsed/.18)
            smooth=t*t*(3-2*t)
            result=cv2.addWeighted(self.blend_start,1-smooth,target,smooth,0)
            if self.flow_future is not None and self.flow_future.done() and not self.flow_future.cancelled():
                try:
                    self.blend=self.flow_future.result()
                except Exception:
                    self.blend=None
                self.flow_future=None
            if self.blend is not None:
                corrected=self.blend.sample(target,t)
                # Ramp assistance gently; a late worker result never snaps in.
                assist=min(1.,dt/.04) if not hasattr(self,"flow_assist") else min(1.,self.flow_assist+dt/.04)
                self.flow_assist=assist
                result=cv2.addWeighted(result,1-assist,corrected,assist,0)
            if self.blend_elapsed>=.18:
                self.blend=None
                self.blend_start=None
                self.flow_assist=0.
        else:
            result=target
        if self.last is not None and cv2.norm(self.last,result,cv2.NORM_L1)>0:
            self.non_identical_frames+=1
        self.last=result
        return result

    def hit_test(self,x,y):
        """Pose-relative landmarks follow the current silhouette and mirroring."""
        if self.last is None or not (0<=x<WIDTH and 0<=y<HEIGHT):
            return None
        frame=self.last
        if frame[int(y),int(x),3]<24:
            return None
        if self.hit_mirrored:
            x=WIDTH-1-x
            frame=frame[:,::-1]
        yy,xx=np.where(frame[:,:,3]>64)
        if not len(xx):
            return None
        nx=(x-xx.min())/max(1,xx.max()-xx.min())
        ny=(y-yy.min())/max(1,yy.max()-yy.min())
        if self.action=="scratch":
            points=[("head",.68,.18),("chin",.76,.30),("cheek",.58,.25),("back",.37,.53),("paw",.92,.48)]
        elif self.posture(self.action,self.direction).startswith("stand"):
            points=[("head",.80,.17),("chin",.88,.32),("cheek",.71,.27),("back",.35,.46),("paw",.72,.92)]
        elif self.action in {"ball","track"}:
            points=[("head",.64,.18),("chin",.70,.34),("cheek",.48,.27),("back",.31,.60),("paw",.87,.84)]
        else:
            points=[("head",.50,.16),("chin",.50,.40),("cheek",.27,.31),("cheek",.73,.31),("back",.50,.62),("paw",.50,.92)]
        return min(points,key=lambda p:((nx-p[1])*.9)**2+(ny-p[2])**2)[0]

    @property
    def execution_ready(self):
        return self.graph.ready and self.blend_start is None and not self.force_blend

    @property
    def locomotion_weight(self):
        if self.action not in {"walk","trot"}:
            return 0.
        if self.graph.ready:
            if self.blend_start is not None:
                return 0.
            return 1.
        if self.graph.edge in {"stand_left","stand_right"} and self.graph.goal.startswith("stand"):
            t=max(0.,min(1.,(self.graph.progress-.45)/.55))
            return t*t*(3-2*t)
        return 0.

    def reset_for_test(self,action,phase=0,direction=1):
        self.action=action
        self.direction=direction
        self.phase=phase
        self.graph=PostureGraph()
        self.graph.node=self.posture(action,direction)
        self.graph.goal=self.graph.node
        self.last=None
        self.blend=None
        self.blend_start=None
        self.visual_key=None
        return self.update(action,0,direction)

    def close(self):
        self.bank.close()
        if self.flow_future is not None:
            self.flow_future.cancel()
        self.flow_worker.shutdown(wait=False,cancel_futures=True)
