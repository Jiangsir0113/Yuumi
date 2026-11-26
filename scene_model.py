"""World-coordinate care/play. No UI, timers, network or platform dependencies."""
from dataclasses import dataclass, field
import math
import json
from pathlib import Path
from cat_model import CARE_ACTIONS, clamp

TAU=math.tau
CAT_WIDTH = 320
CAT_GROUND = 286
MOUTH_X = 286
# Window-local contact points for the scratch sweep and the lowered batting paw.
SCRATCH_PAW = (276, 165)
TRACK_PAW = (270, 270)
DEVICE_ATTR = {'food': 'feeder', 'water': 'fountain', 'snack': 'snack'}

@dataclass
class Bowl:
    x: float
    floor: float
    kind: str
    amount: float=1.
    facing: int=1
    scale: float=1.
    logical_height: float=215.
    aspect: float=1.
    mouth: tuple=(.25,.82)
    stock: int=8
    dispensing: float=0.
    pulse: float=0.
    logical_extra: float=0.

    @property
    def height(self): return self.logical_height*self.scale
    @property
    def width(self): return self.height*self.aspect
    @property
    def left(self): return self.x-self.width*(self.mouth[0] if self.facing>0 else 1-self.mouth[0])
    @property
    def y(self): return self.floor-self.height
    @property
    def contact_y(self): return self.y+self.height*self.mouth[1]
    @property
    def extra_width(self): return self.logical_extra*self.scale

    def dispense(self):
        if self.kind!='food' or self.amount>.01 or self.dispensing>0 or self.stock<=0:return False
        self.stock-=1;self.dispensing=1.2;self.amount=0.
        return True

    def step(self,dt):
        if self.dispensing>0:
            before=self.dispensing
            self.dispensing=max(0.,before-dt)
            self.amount=min(1.,self.amount+(before-self.dispensing)/1.2)
        self.pulse=max(0.,self.pulse-dt)

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
    logical_height: float=264.
    source_width: int=413
    source_height: int=768
    rope_left: tuple=(.24,.54)
    rope_right: tuple=(.76,.54)
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

    def contact_point(self, kind, direction):
        if kind == 'scratch':
            u, v = self.rope_left if direction > 0 else self.rope_right
        else:
            u = self.track_center[0] - direction * self.track_radius[0]
            v = self.track_center[1]
        return self.x + self.width * u, self.y + self.height * v

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
        self.equipment_layout=json.loads((Path(__file__).resolve().parent/'assets/props/equipment-layout.json').read_text(encoding='utf-8'))
        self.activity=None
        self.bowl=None
        self.feeder=self.fountain=self.snack=None
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
        self.feeder=self.fountain=self.snack=None

    def refill(self,kind):
        obj=getattr(self,DEVICE_ATTR[kind])
        if obj is None:return False
        if kind=='food':
            obj.stock=8
            self.message='弗列加特猫粮已补满；点喂食器出一份'
        else:
            obj.amount=1.
            self.message='SOLO SE 已续水' if kind=='water' else '换好一支弗列加特猫条'
        obj.pulse=1.
        return True

    def _target(self,x,y):
        l,t,r,b=self.limits
        return (clamp(x,l,r),clamp(y,t,b))

    def _reachable(self, x, y):
        target = self._target(x, y)
        # Screen geometry and native window positions round to integer pixels.
        return target if math.dist((x, y), target) <= 1 else None

    def _care_target(self, obj, left, scale):
        floor = obj.contact_y + 94 * scale if obj.kind == 'snack' else obj.floor
        for direction in (obj.facing, -obj.facing):
            mouth, offset = obj.mouth[0], MOUTH_X
            if direction < 0:
                mouth, offset = 1 - mouth, CAT_WIDTH - offset
            mouth_x = left + obj.width * mouth
            target = self._reachable(mouth_x - offset * scale, floor - CAT_GROUND * scale)
            if target is not None:
                return target, direction, mouth_x
        return None

    def _scratcher_target(self, obj, kind, scale):
        paw_x = SCRATCH_PAW[0] if kind == 'scratch' else TRACK_PAW[0]
        for direction in (1, -1):
            x, _ = obj.contact_point(kind, direction)
            offset = paw_x if direction > 0 else CAT_WIDTH - paw_x
            target = self._reachable(x - offset * scale, obj.floor - CAT_GROUND * scale)
            if target is not None:
                return target, direction
        return None

    def _place_equipment(self,obj,preferred,scale):
        """Place complete silhouettes, including the food bag, inside the screen."""
        l,_,r,_=self.limits
        obstacles=[(o.left,o.left+o.width+o.extra_width) for o in (self.feeder,self.fountain,self.snack) if o and o is not obj]
        if self.scratcher:obstacles.append((self.scratcher.x,self.scratcher.x+self.scratcher.width))
        width=obj.width+obj.extra_width
        rightmost = r + CAT_WIDTH * scale - width
        if rightmost < l:
            return False
        candidates=[preferred-obj.width*obj.mouth[0],l,rightmost]
        for left,right in obstacles:candidates.extend([left-width-20*scale,right+20*scale])
        def score(left):
            overlap=sum(max(0.,min(left+width,right)-max(left,start)) for start,right in obstacles)
            placement = self._care_target(obj, left, scale)
            mouth_x = placement[2] if placement else left + obj.width * obj.mouth[0]
            return placement is None, overlap * 100 + abs(mouth_x - preferred)
        left=min((clamp(c,l,rightmost) for c in candidates),key=score)
        placement = self._care_target(obj, left, scale)
        if placement is None:
            return False
        _, obj.facing, obj.x = placement
        return True

    def begin(self,kind,model,x,y,scale,limits):
        if self.activity and self.activity.kind==kind:
            return False
        if kind in {'food','snack'} and model.satiety>96:
            self.message='已经吃饱啦，等会儿再吃～'
            return False
        if kind=='water' and model.thirst>97:
            self.message='水分很充足，等会儿再喝～'
            return False
        device = getattr(self, DEVICE_ATTR[kind]) if kind in DEVICE_ATTR else None
        if device is not None and device.amount <= .01:
            needs_refill = (device.stock <= 0 and device.dispensing <= 0) if kind == 'food' else True
            if needs_refill:
                self.message = {
                    'food': '粮仓空啦，右键喂食器补充弗列加特猫粮',
                    'water': '请先右键续水',
                    'snack': '猫条吃完啦，右键换一支',
                }[kind]
                return False
        self.limits=limits
        if device is not None and self._care_target(device, device.left, scale) is None:
            self.message='暂时够不到，试试往桌面中间挪一点'
            return False
        floor=y+CAT_GROUND*scale
        l,t,r,b=limits
        if kind in DEVICE_ATTR:
            attr=DEVICE_ATTR[kind]
            obj=device
            if obj is None:
                bx=x+355*scale
                facing=1
                if bx>r+290*scale: bx=x-35*scale;facing=-1
                if self.scratcher:
                    prop=self.scratcher
                    candidates=[]
                    left_bowl=prop.x-30*scale
                    right_bowl=prop.x+prop.width+50*scale
                    if left_bowl-286*scale>=l:candidates.append((left_bowl,1,left_bowl-286*scale))
                    if right_bowl-34*scale<=r:candidates.append((right_bowl,-1,right_bowl-34*scale))
                    if candidates:
                        bx,facing,_=min(candidates,key=lambda c:abs(c[2]-x))
                # Leave the seated cat's space free and avoid other equipment.
                for other in (self.feeder,self.fountain,self.snack):
                    if other and abs(bx-other.x)<180*scale:bx=other.x+200*scale
                layout=self.equipment_layout[{'food':'petkit-solo','water':'petkit-solo-se','snack':'fregate-treat'}[kind]]
                height=layout['logical_height']
                # Treat opening is raised to the same mouth level as drinking.
                efloor=floor-(94-height*(1-layout['contact'][1]))*scale if kind=='snack' else floor
                obj=Bowl(clamp(bx,l+80*scale,r+180*scale),max(efloor,t+height*scale),kind,
                         amount=0. if kind=='food' else 1.,facing=facing,scale=scale,
                         logical_height=height,aspect=layout['width']/layout['height'],mouth=tuple(layout['contact']))
                if kind=='food':
                    packet=self.equipment_layout['fregate-food']
                    obj.logical_extra=height*.38*packet['width']/packet['height']+10
                if not self._place_equipment(obj,bx,scale):
                    self.message='暂时没有能靠近的摆放位置'
                    return False
                setattr(self,attr,obj)
            self.bowl=obj
            if kind=='food':
                obj.dispense()
            self.message={'food':'SOLO 正在出粮，悠米会走到食盆前','water':'去 SOLO SE 喝水啦','snack':'尝一口弗列加特猫条'}[kind]
        elif kind=='ball':
            if self.ball is None:
                bx=x+365*scale
                if bx>r+300*scale: bx=x-30*scale
                self.ball=Ball(clamp(bx,l+15,r+305*scale),floor,25*scale,radius=12*scale)
            self.message='小球会留在桌面，碰到才会拨动'
        elif kind in {'scratch','track'}:
            obj = self.scratcher
            if obj is None:
                sx=clamp(x+285*scale,l+30*scale,r+100*scale)
                layout=self.prop_layout
                sf=clamp(floor,t+max(layout['logical_height'],CAT_GROUND)*scale,b+CAT_GROUND*scale)
                obj=Scratcher(sx,sf,scale,layout['logical_height'],layout['source_width'],layout['source_height'],
                              tuple(layout['rope_left']),tuple(layout['rope_right']),tuple(layout['track_center']),tuple(layout['track_radius']))
            if self._scratcher_target(obj, kind, scale) is None:
                self.message='暂时够不到，试试往桌面中间挪一点'
                return False
            self.scratcher = obj
            self.message='抓抓白色绳面' if kind=='scratch' else '用小爪拨动圆槽里的球'
        elif kind=='wand':
            self.message='缓缓移动鼠标，悠米会注视、蓄力和扑抓'
        else:
            raise ValueError('Unknown scene activity')
        self.cancel()
        self.activity=Activity(kind)
        model.queue.clear()
        if kind=='wand':
            self.activity.stage='watch'
            model.start('look')
        else:
            self.update(0.,model,x,y,scale,True,0.,limits=limits)
        return self.activity is not None

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
        for equipment in (self.feeder,self.fountain,self.snack):
            if equipment:equipment.step(dt)
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
        if kind in DEVICE_ATTR:
            obj=self.bowl
            placement = self._care_target(obj, obj.left, scale)
            if placement is None:
                self.cancel(model)
                self.message='暂时够不到，试试往桌面中间挪一点'
                return
            target, obj.facing, obj.x = placement
            self.direction = obj.facing
        elif kind=='ball':
            obj=self.ball
            self.direction=1 if obj.x>x+160*scale else -1
            offset=270 if self.direction>0 else 50
            target=self._target(obj.x-offset*scale,obj.floor-286*scale)
        else:
            obj=self.scratcher
            placement = self._scratcher_target(obj, kind, scale)
            if placement is None:
                self.cancel(model)
                self.message='暂时够不到，试试往桌面中间挪一点'
                return
            target, self.direction = placement
        distance=math.hypot(target[0]-x,target[1]-y)
        if a.stage=='approach':
            self.destination=target
            if distance<4*scale:
                self.destination=None
                if kind=='food' and obj.dispensing>0:
                    if model.action!='look':model.start('look')
                    return
                if kind in DEVICE_ATTR:
                    if not model.request(kind, interrupt_care=True):
                        self.cancel()
                        self.message=model.last_message
                        return
                    self.last_need=model.thirst if kind=='water' else model.satiety
                else:
                    model.queue.clear();model.start('ball' if kind=='ball' else kind,90)
                a.stage='interact';a.stage_time=0.;a.contact_cycle=-1
            else:
                if model.action not in {'walk','trot'}:
                    model.queue.clear();model.start('walk')
                # The scene owns the gait until the cat reaches the prop.
                model.remaining = max(model.remaining, 1.)
            return
        if kind in DEVICE_ATTR:
            if distance>15*scale:
                self._enter('approach',model,'walk');self.destination=target
                return
            need=model.thirst if kind=='water' else model.satiety
            serving=45 if kind=='water' else 12 if kind=='snack' else 35
            intake=max(0.,need-self.last_need)
            available=obj.amount*serving
            if intake>available:
                need-=intake-available
                if kind=='water':model.thirst=need
                else:model.satiety=need
            obj.amount=max(0.,obj.amount-min(intake,available)/serving)
            self.last_need=need
            if obj.amount<=.00001 and model.action in {'eat','drink','treat'}:
                model.sequence(['lick','groom'] if kind=='food' else ['lick'])
            if model.action not in CARE_ACTIONS:
                self.cancel()
            return
        needs_reposition = distance > (30 if kind == 'ball' else 12) * scale
        if needs_reposition and (kind != 'ball' or a.stage_time-a.struck_at>.35):
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
            hit=False
            if kind in {'scratch', 'track'}:
                paw_x, paw_y = SCRATCH_PAW if kind == 'scratch' else TRACK_PAW
                if self.direction < 0:
                    paw_x = CAT_WIDTH - paw_x
                paw = x + paw_x * scale, y + paw_y * scale
                if kind == 'scratch' and math.dist(obj.contact_point(kind, self.direction), paw) <= 16 * scale:
                    obj.scratches += 1
                    obj.glow = .2
                    obj.glow_side = self.direction
                    hit = True
                elif kind == 'track':
                    distances = [math.dist(obj.ball_position(i), paw) for i in range(3)]
                    index = min(range(3), key=distances.__getitem__)
                    if distances[index] <= min(18 * scale, obj.width * .20):
                        obj.impulse(index, 3.8 * self.direction)
                        hit = True
            else:
                contact_x=x+(270 if self.direction>0 else 50)*scale
                if abs(obj.x-contact_x)<24*scale:
                    obj.velocity+=105*scale*self.direction
                    hit=True
            if hit:
                a.contact_cycle=cycle
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
