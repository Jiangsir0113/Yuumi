"""World-coordinate care/play. No UI, timers, network or platform dependencies."""
from dataclasses import dataclass, field
import math
import json
from pathlib import Path
from cat_model import CARE_ACTIONS, clamp

TAU=math.tau

@dataclass
class Bowl:
    x: float
    floor: float
    kind: str
    amount: float=1.
    facing: int=1

@dataclass
class Ball:
    x: float
    floor: float
    velocity: float=0.
    angle: float=0.
    radius: float=12.

    def step(self,dt,left,right):
        for _ in range(max(1,math.ceil(dt/.008))):
            step=dt/max(1,math.ceil(dt/.008))
            self.x+=self.velocity*step
            self.angle+=self.velocity*step/max(1,self.radius)
            self.velocity*=math.exp(-step*1.25)
            if self.x<left+self.radius:
                self.x=left+self.radius
                self.velocity=abs(self.velocity)*.72
            elif self.x>right-self.radius:
                self.x=right-self.radius
                self.velocity=-abs(self.velocity)*.72

@dataclass
class Scratcher:
    x: float
    floor: float
    scale: float=1.
    logical_height: float=132.
    source_width: int=413
    source_height: int=768
    rope_left: tuple=(.12,.72)
    rope_right: tuple=(.88,.72)
    track_center: tuple=(.5,.935)
    track_radius: tuple=(.365,.035)
    angles: list=field(default_factory=lambda:[.5,2.6,4.7])
    speeds: list=field(default_factory=lambda:[0.,0.,0.])
    scratches: int=0
    taps: int=0
    glow: float=0.
    glow_side: int=1

    @property
    def width(self): return self.height*self.source_width/self.source_height
    @property
    def height(self): return self.logical_height*self.scale
    @property
    def y(self): return self.floor-self.height

    def ball_position(self,i):
        a=self.angles[i]
        return (self.x+self.width*(self.track_center[0]+self.track_radius[0]*math.cos(a)),
                self.y+self.height*(self.track_center[1]+self.track_radius[1]*math.sin(a)))

    def impulse(self,index,velocity=3.5):
        self.speeds[index]=max(-7.,min(7.,self.speeds[index]+velocity))
        self.taps+=1

    def step(self,dt):
        steps=max(1,math.ceil(dt/.008))
        for _ in range(steps):
            for i in range(3):
                self.angles[i]=(self.angles[i]+self.speeds[i]*dt/steps)%TAU
                self.speeds[i]*=math.exp(-dt/steps*.65)
            for i,j in [(0,1),(1,2),(2,0)]:
                delta=(self.angles[j]-self.angles[i]+math.pi)%TAU-math.pi
                if abs(delta)<.24:
                    rel=self.speeds[j]-self.speeds[i]
                    if delta*rel<0:
                        self.speeds[i],self.speeds[j]=self.speeds[j]*.9,self.speeds[i]*.9
                    correction=(.24-abs(delta))/2
                    sign=1 if delta>=0 else -1
                    self.angles[i]-=sign*correction
                    self.angles[j]+=sign*correction
        self.glow=max(0.,self.glow-dt)

@dataclass
class Activity:
    kind: str
    stage: str='approach'
    elapsed: float=0.
    stage_time: float=0.
    last_phase: float=0.
    contact_cycle: int=-1
    strikes: int=0
    struck_at: float=-100.

class SceneController:
    def __init__(self):
        self.prop_layout=json.loads((Path(__file__).resolve().parent/'assets/props/garlic-layout.json').read_text(encoding='utf-8'))
        self.activity=None
        self.bowl=None
        self.ball=None
        self.scratcher=None
        self.destination=None
        self.direction=1
        self.pounce_velocity=0.
        self.revision=0
        self.last_pointer=None
        self.pointer_speed=0.
        self.clock=0.
        self.message=''
        self.last_need=0.
        self.limits=(0.,0.,1200.,700.)

    def cancel(self,model=None):
        self.revision+=1
        self.activity=None
        self.destination=None
        self.pounce_velocity=0.
        self.last_pointer=None
        if model is not None:
            model.queue.clear()
            model.start('idle')

    def put_away(self,model=None):
        self.cancel(model)
        self.bowl=self.ball=self.scratcher=None

    def _target(self,x,y):
        l,t,r,b=self.limits
        return (clamp(x,l,r),clamp(y,t,b))

    def begin(self,kind,model,x,y,scale,limits):
        if self.activity and self.activity.kind==kind:
            return False
        if kind in {'food','snack'} and model.satiety>96:
            self.message='已经吃饱啦，等会儿再吃～'
            return False
        if kind=='water' and model.thirst>97:
            self.message='水分很充足，等会儿再喝～'
            return False
        self.cancel()
        self.limits=limits
        self.activity=Activity(kind)
        floor=y+286*scale
        l,t,r,b=limits
        if kind in {'food','water','snack'}:
            # Keep an existing bowl where it was put, replenishing its contents.
            if self.bowl is None or self.bowl.kind!=kind:
                bx=x+355*scale
                facing=1
                if bx>r+290*scale: bx=x-35*scale;facing=-1
                if self.scratcher:
                    prop=self.scratcher
                    candidates=[]
                    left_bowl=prop.x-30*scale
                    right_bowl=prop.x+prop.width+50*scale
                    if left_bowl-260*scale>=l:candidates.append((left_bowl,1,left_bowl-260*scale))
                    if right_bowl-60*scale<=r:candidates.append((right_bowl,-1,right_bowl-60*scale))
                    if candidates:
                        bx,facing,_=min(candidates,key=lambda c:abs(c[2]-x))
                self.bowl=Bowl(clamp(bx,l+35*scale,r+285*scale),floor,kind,facing=facing)
            else:
                self.bowl.amount=1.
            self.message='水碗放好啦' if kind=='water' else '食盆放好啦，悠米自己走过去'
        elif kind=='ball':
            if self.ball is None:
                bx=x+365*scale
                if bx>r+300*scale: bx=x-30*scale
                self.ball=Ball(clamp(bx,l+15,r+305*scale),floor,25*scale,radius=12*scale)
            self.message='小球会留在桌面，碰到才会拨动'
        elif kind in {'scratch','track'}:
            if self.scratcher is None:
                sx=clamp(x+285*scale,l+30*scale,r+100*scale)
                layout=self.prop_layout
                sf=clamp(floor,t+layout['logical_height']*scale,b+286*scale)
                self.scratcher=Scratcher(sx,sf,scale,layout['logical_height'],layout['source_width'],layout['source_height'],
                                         tuple(layout['rope_left']),tuple(layout['rope_right']),tuple(layout['track_center']),tuple(layout['track_radius']))
            self.message='抓抓白色绳面' if kind=='scratch' else '用小爪拨动圆槽里的球'
        elif kind=='wand':
            self.activity.stage='watch'
            model.queue.clear()
            model.start('look')
            self.message='缓缓移动鼠标，悠米会注视、蓄力和扑抓'
        else:
            raise ValueError('Unknown scene activity')
        if kind!='wand':
            model.queue.clear()
            self.update(0.,model,x,y,scale,True,0.,limits=limits)
        return True

    def _enter(self,stage,model,action):
        self.activity.stage=stage
        self.activity.stage_time=0.
        self.activity.contact_cycle=-1
        model.queue.clear()
        model.start(action)

    def update(self,dt,model,x,y,scale,ready,phase,pointer=None,limits=None):
        dt=max(0.,min(.25,dt))
        self.clock+=dt
        if limits is not None: self.limits=limits
        l,t,r,b=self.limits
        if self.ball:
            self.ball.step(dt,l,r+320*scale)
        if self.scratcher:
            self.scratcher.step(dt)
        self.destination=None
        self.pounce_velocity=0.
        if not self.activity:
            return
        a=self.activity
        a.elapsed+=dt
        a.stage_time+=dt
        if a.kind in {'wand','ball','scratch','track'} and model.energy<18:
            self.cancel()
            model.sequence(['yawn','loaf','sleep'])
            self.message='有点困了，先休息一会儿'
            return
        if a.elapsed>90:
            self.cancel(model)
            self.message='玩了一会儿，休息一下吧'
            return
        if a.kind=='wand':
            self._wand(dt,model,x,y,scale,ready,phase,pointer)
            return
        kind=a.kind
        if kind in {'food','water','snack'}:
            obj=self.bowl
            self.direction=obj.facing
            offset=260 if self.direction>0 else 60
            target=self._target(obj.x-offset*scale,obj.floor-286*scale)
        elif kind=='ball':
            obj=self.ball
            self.direction=1 if obj.x>x+160*scale else -1
            offset=270 if self.direction>0 else 50
            target=self._target(obj.x-offset*scale,obj.floor-286*scale)
        else:
            obj=self.scratcher
            # Prefer a side with room for the entire cat; turn toward the prop.
            paw=282 if kind=='scratch' else 270
            left_x=obj.rope_left[0] if kind=='scratch' else obj.track_center[0]-obj.track_radius[0]
            right_x=obj.rope_right[0] if kind=='scratch' else obj.track_center[0]+obj.track_radius[0]
            left_target=obj.x+obj.width*left_x-paw*scale
            right_target=obj.x+obj.width*right_x-(320-paw)*scale
            self.direction=1 if left_target>=l else -1
            target=self._target(left_target if self.direction>0 else right_target,obj.floor-286*scale)
        distance=math.hypot(target[0]-x,target[1]-y)
        if a.stage=='approach':
            self.destination=target
            if distance<4*scale:
                self.destination=None
                a.stage='interact';a.stage_time=0.;a.contact_cycle=-1
                if kind in {'food','water','snack'}:
                    self.last_need=model.thirst if kind=='water' else model.satiety
                    model.request(kind)
                else:
                    model.queue.clear();model.start('ball' if kind=='ball' else kind,90)
            elif model.action not in {'walk','trot'}:
                model.queue.clear();model.start('walk')
            return
        if kind in {'food','water','snack'}:
            need=model.thirst if kind=='water' else model.satiety
            serving=45 if kind=='water' else 12 if kind=='snack' else 35
            obj.amount=max(0.,obj.amount-max(0.,need-self.last_need)/serving)
            self.last_need=need
            if model.action not in CARE_ACTIONS:
                self.cancel()
            return
        if distance>30*scale and a.stage_time-a.struck_at>.35:
            self._enter('approach',model,'walk')
            self.destination=target
            return
        model.remaining=max(model.remaining,1.)
        if not ready:
            return
        duration=1.4 if kind=='scratch' else 1.328
        cycle=int(phase/duration)
        fraction=phase/duration-cycle
        strike=.10<=fraction<=.30 if kind=='scratch' else .48<=fraction<=.75
        if strike and a.contact_cycle!=cycle:
            a.contact_cycle=cycle
            hit=False
            if kind=='scratch':
                obj.scratches+=1;obj.glow=.2
                obj.glow_side=self.direction
                hit=True
            elif kind=='track':
                contact_x=x+(278 if self.direction>0 else 42)*scale
                index=min(range(3),key=lambda i:abs(obj.ball_position(i)[0]-contact_x))
                # A bat occurs only when a ball reaches the paw's contact arc.
                if abs(obj.ball_position(index)[0]-contact_x)<min(18*scale,obj.width*.20):
                    obj.impulse(index,3.8*self.direction)
                    hit=True
            else:
                contact_x=x+(270 if self.direction>0 else 50)*scale
                if abs(obj.x-contact_x)<24*scale:
                    obj.velocity+=105*scale*self.direction
                    hit=True
            if hit:
                a.strikes+=1
                a.struck_at=a.stage_time
                model.happiness=clamp(model.happiness+.45)
                model.energy=clamp(model.energy-.18)
        if a.stage_time>14 and kind in {'scratch','track'}:
            self.cancel()
            model.sequence(['groom','loaf'])
            self.message='爪爪活动好了，歇一会儿'

    def _wand(self,dt,model,x,y,scale,ready,phase,pointer):
        a=self.activity
        if pointer is None: return
        px,py=pointer
        if self.last_pointer is not None and dt>0:
            speed=math.dist(pointer,self.last_pointer)/dt
            self.pointer_speed+=(min(2000.,speed)-self.pointer_speed)*(1-math.exp(-dt/.12))
        self.last_pointer=pointer
        distance=math.hypot(px-(x+160*scale),(py-(y+160*scale))*.55)
        if a.stage=='pounce':
            model.remaining=max(model.remaining,.15)
            if ready:
                self.pounce_velocity=self.direction*min(140*scale,abs(px-(x+220*scale*self.direction))*2)
                if model.elapsed>.75:
                    if distance<130*scale:
                        model.happiness=clamp(model.happiness+2)
                    self._enter('recover',model,'idle')
            return
        if a.stage=='recover':
            if a.stage_time>.65:
                self._enter('watch',model,'look')
            return
        near=distance<260*scale and y-100*scale<py<y+350*scale
        if not near:
            if a.stage!='watch': self._enter('watch',model,'look')
            return
        self.direction=1 if px>x+160*scale else -1
        if a.stage=='watch':
            self._enter('charge',model,'crouch')
        elif a.stage=='charge' and ready:
            model.remaining=max(model.remaining,.5)
            wait=.65+min(.7,self.pointer_speed/900.)
            if a.stage_time>wait:
                self._enter('pounce',model,'pounce')
