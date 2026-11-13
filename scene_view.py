"""Small independent transparent windows for world objects (not a desktop overlay)."""
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QWidget,QHBoxLayout,QPushButton,QMenu,QLabel
from pathlib import Path
import math

class PropWindow(QWidget):
    def __init__(self,cat,kind,assets):
        super().__init__(None,Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|
                         Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.WindowDoesNotAcceptFocus)
        self.cat,self.kind=cat,kind
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle('悠米 · '+{'scratcher':'大蒜猫抓板','feeder':'小佩 SOLO 喂食器','fountain':'小佩 SOLO SE 饮水机','snack':'弗列加特猫条','ball':'小球'}[kind])
        self.setWindowIcon(cat.windowIcon())
        filename={'scratcher':'garlic-scratcher','feeder':'petkit-solo','fountain':'petkit-solo-se','snack':'fregate-treat'}.get(kind)
        self.image=QPixmap(str(Path(assets)/'props'/(filename+'.png'))) if filename else None
        self.reverse=QPixmap(str(Path(assets)/'props'/(filename+'-reverse.png'))) if kind in {'feeder','snack'} else None
        self.packet=QPixmap(str(Path(assets)/'props/fregate-food.png')) if kind=='feeder' else None
        self.press=None
        self.moving=False
        self.transparent=False
        self.setToolTip('点击绳面抓挠，点击底部圆槽拨球；拖动可搬家' if kind=='scratcher' else '点击互动，拖动可搬家')

    @property
    def data(self):
        return getattr(self.cat.scene,'scratcher' if self.kind=='scratcher' else self.kind)

    def sync(self,visible=True):
        data=self.data
        if data is None:
            self.hide();return
        s=self.cat.scale
        if self.kind=='scratcher':
            self.resize(round(data.width),round(data.height))
            self.move(round(data.x),round(data.y))
        elif self.kind in {'feeder','fountain','snack'}:
            extra=data.extra_width
            self.resize(round(data.width+extra),round(data.height))
            self.move(round(data.left),round(data.y))
            self.setToolTip({'feeder':f'SOLO · 粮仓 {data.stock}/8 份 · 食盆 {data.amount:.0%}\n点食盆叫悠米吃粮，点右侧粮袋补粮；右键更多',
                             'fountain':f'SOLO SE · 余水 {data.amount:.0%} · 右键续水',
                             'snack':f'弗列加特猫条 · 剩余 {data.amount:.0%} · 右键换一支'}[self.kind])
        else:
            self.resize(round(36*s),round(36*s))
            self.move(round(data.x-18*s),round(data.floor-30*s))
        transparent=self.cat.model.settings.get('click_through',False)
        if transparent!=self.transparent:
            self.transparent=transparent
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput,transparent)
        self.setVisible(visible)
        if visible:self.update()

    def _sphere(self,p,center,radius,color):
        gradient=QRadialGradient(center-QPointF(radius*.3,radius*.3),radius*1.3)
        gradient.setColorAt(0,QColor(color).lighter(145))
        gradient.setColorAt(1,QColor(color).darker(135))
        p.setPen(QPen(QColor(color).darker(120),.7))
        p.setBrush(gradient)
        p.drawEllipse(center,radius,radius)

    def paintEvent(self,event):
        data=self.data
        if data is None:return
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        s=self.cat.scale
        if self.kind=='scratcher':
            factor=min(self.width()/self.image.width(),self.height()/self.image.height())
            width,height=self.image.width()*factor,self.image.height()*factor
            fitted=QRectF((self.width()-width)/2,(self.height()-height)/2,width,height)
            p.drawPixmap(fitted,self.image,QRectF(self.image.rect()))
            # Clip to the track's opening; balls remain under the upper plate.
            for i in sorted(range(3),key=lambda n:math.sin(data.angles[n])):
                x,y=data.ball_position(i)
                p.save()
                p.setClipRect(QRectF(0,data.height*.902,data.width,data.height*.095))
                radius=data.width*.041*(.85+.15*math.sin(data.angles[i]))
                self._sphere(p,QPointF(x-data.x,y-data.y),radius,['#ddc79e','#85a57d','#d59886'][i])
                p.restore()
            if data.glow>0:
                p.setPen(QPen(QColor(245,221,165,round(160*data.glow/.2)),1.5*s))
                for i in range(3):
                    direction=1 if data.glow_side>0 else -1
                    x=data.width*(.24 if direction>0 else .76)+i*data.width*.035*direction
                    p.drawLine(QPointF(x,data.height*.35),QPointF(x-data.width*.02*direction,data.height*.65))
        elif self.kind in {'feeder','fountain','snack'}:
            p.save()
            picture=self.reverse if data.facing<0 and self.reverse is not None else self.image
            factor=min(data.width/picture.width(),data.height/picture.height())
            iw,ih=picture.width()*factor,picture.height()*factor
            p.drawPixmap(QRectF((data.width-iw)/2,(data.height-ih)/2,iw,ih),picture,QRectF(picture.rect()))
            if data.facing<0:
                p.translate(data.width,0);p.scale(-1,1)
            w,h=data.width,data.height
            if self.kind=='feeder':
                p.save();p.setClipRect(QRectF(w*.035,h*.77,w*.53,h*.105))
                p.setPen(Qt.PenStyle.NoPen)
                for i in range(round(data.amount*30)):
                    xx=w*(.11+((i*17)%34)/100);yy=h*(.795+((i*7)%5)/100)
                    p.setBrush(QColor('#a77844' if i%2 else '#bd905e'))
                    p.drawEllipse(QRectF(xx,yy,4*s,2.5*s))
                p.restore()
                if data.dispensing>0:
                    p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#a77b4c'))
                    for i in range(6):
                        f=(self.cat.scene.clock*2+i/6)%1
                        p.drawEllipse(QPointF(w*(.43-.17*f),h*(.735+.085*f*f)),1.7*s,1.3*s)
            elif self.kind=='fountain' and data.amount>.01:
                p.save();p.setClipRect(QRectF(w*.13,h*.11,w*.74,h*.18))
                for i in range(3):
                    f=(self.cat.scene.clock*.7+i/3)%1
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.setPen(QPen(QColor(115,180,193,round(130*(1-f))),max(.6,s)))
                    p.drawEllipse(QPointF(w*.50,h*.20),w*(.04+f*.34),h*(.01+f*.07))
                p.restore()
                p.setPen(QPen(QColor(117,179,191,65),s))
                level=h*(.91-data.amount*.42)
                p.drawLine(QPointF(w*.12,level),QPointF(w*.88,level))
            elif self.kind=='snack':
                p.setBrush(QColor(235,206,159,210));p.setPen(Qt.PenStyle.NoPen)
                if data.amount>.01:p.drawEllipse(QRectF(0,h*.42,6*s*data.amount,h*.22))
                p.setPen(QPen(QColor('#d8c9b5'),max(1,s)))
                p.drawLine(QPointF(w*.13,h*.94),QPointF(w*(.13+.8*data.amount),h*.94))
            p.restore()
            if self.packet:
                ph=data.height*.38;pw=ph*self.packet.width()/self.packet.height()
                p.drawPixmap(QRectF(data.width+8*s,data.height-ph,pw,ph),self.packet,QRectF(self.packet.rect()))
            if data.pulse>0:
                p.setPen(QPen(QColor(155,191,138,round(160*data.pulse)),2*s))
                p.setBrush(Qt.BrushStyle.NoBrush);p.drawRoundedRect(QRectF(1,1,self.width()-2,self.height()-2),8,8)
        else:
            p.translate(self.width()/2,self.height()/2)
            p.rotate(math.degrees(data.angle))
            radius=data.radius
            self._sphere(p,QPointF(),radius,'#dba58b')
            p.setPen(QPen(QColor('#fff1d7'),radius*.32))
            p.drawArc(QRectF(-radius*.7,-radius*.8,radius*1.4,radius*1.6),85*16,170*16)
        p.end()

    def refill(self):
        if self.data and self.cat.scene.refill(self.data.kind):
            self.cat.say(self.cat.scene.message);self.sync()

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.RightButton:
            menu=QMenu(self)
            if self.kind=='scratcher':
                menu.addAction('抓白色绳面',lambda:self.cat.perform('scratch'))
                menu.addAction('拨圆槽小球',lambda:self.cat.perform('track'))
            else:
                menu.addAction('叫悠米过来',lambda:self.cat.perform(self.data.kind if self.kind in {'feeder','fountain','snack'} else 'ball'))
                if self.kind in {'feeder','fountain','snack'}:
                    menu.addAction({'feeder':'补满弗列加特猫粮','fountain':'给 SOLO SE 续水','snack':'换一支弗列加特猫条'}[self.kind],self.refill)
            menu.addSeparator()
            menu.addAction('收起所有道具',lambda:self.cat.perform('put_away'))
            menu.exec(event.globalPosition().toPoint())
            return
        if event.button()==Qt.MouseButton.LeftButton:
            self.press=event.globalPosition().toPoint()
            self.origin=self.pos()
            self.moving=False

    def mouseMoveEvent(self,event):
        if self.press is None:return
        delta=event.globalPosition().toPoint()-self.press
        if delta.manhattanLength()>6:self.moving=True
        if not self.moving:return
        data=self.data
        if data is None:return
        rect=self.cat.available_rect()
        point=self.origin+delta
        px=max(rect.left(),min(point.x(),rect.right()-self.width()+1))
        py=max(rect.top(),min(point.y(),rect.bottom()-self.height()+1))
        if self.kind=='scratcher':
            data.x=px;data.floor=py+data.height
        elif self.kind in {'feeder','fountain','snack'}:
            minimum=rect.top()+286*self.cat.scale-data.height
            if self.kind=='snack':minimum=rect.top()+(286-94)*self.cat.scale-data.height*data.mouth[1]
            py=max(minimum,py)
            data.x=px+data.width*(data.mouth[0] if data.facing>0 else 1-data.mouth[0]);data.floor=py+data.height
        else:
            data.x=px+self.width()/2;data.floor=py+30*self.cat.scale;data.velocity=0.
        self.sync()

    def mouseReleaseEvent(self,event):
        if self.press is None:return
        if not self.moving and self.data:
            if self.kind=='scratcher':
                if event.position().y()>self.height()*.88:
                    data=self.data
                    world=(self.x()+event.position().x(),self.y()+event.position().y())
                    index=min(range(3),key=lambda i:math.dist(world,data.ball_position(i)))
                    data.impulse(index,3.)
                    self.cat.perform('track')
                else:self.cat.perform('scratch')
            elif self.kind=='feeder' and event.position().x()>self.data.width:self.refill()
            else:self.cat.perform(self.data.kind if self.kind in {'feeder','fountain','snack'} else 'ball')
        self.press=None
        self.moving=False

class SceneView:
    def __init__(self,cat,assets):
        self.cat,self.assets=cat,assets
        self.windows={}
        self.toolbar=QWidget(None,Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|
                             Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.WindowDoesNotAcceptFocus)
        self.toolbar.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.toolbar.setWindowTitle('悠米 · 互动控制')
        self.toolbar.setStyleSheet('QWidget{background:#fbf7ef;border-radius:9px;} QPushButton{background:#f4e8d5;border:0;border-radius:6px;padding:6px;color:#72583c;} QPushButton:hover{background:#e6cfab;}')
        row=QHBoxLayout(self.toolbar);row.setContentsMargins(5,4,5,4);row.setSpacing(4)
        self.buttons={}
        for label,action in [('抓绳','scratch'),('拨球','track'),('喂粮','food'),('喝水','water'),('猫条','snack'),('结束','stop'),('收起','put_away')]:
            button=QPushButton(label)
            button.clicked.connect(lambda checked=False,a=action:cat.perform(a))
            row.addWidget(button);self.buttons[action]=button
        self.toolbar.adjustSize()

    def sync(self,visible):
        cat=self.cat
        for kind in ['feeder','fountain','snack','ball','scratcher']:
            data=getattr(cat.scene,kind)
            if data is not None and kind not in self.windows:
                self.windows[kind]=PropWindow(cat,kind,self.assets)
                cat.raise_()
            if kind in self.windows:
                if data is None:
                    self.windows.pop(kind).close()
                else:self.windows[kind].sync(visible)
        show=visible and bool(self.windows or cat.scene.activity) and not cat.model.settings.get('click_through')
        self.toolbar.setVisible(show)
        if show:
            self.buttons['scratch'].setVisible(cat.scene.scratcher is not None)
            self.buttons['track'].setVisible(cat.scene.scratcher is not None)
            self.buttons['food'].setVisible(cat.scene.feeder is not None)
            self.buttons['water'].setVisible(cat.scene.fountain is not None)
            self.buttons['snack'].setVisible(cat.scene.snack is not None)
            self.toolbar.adjustSize()
            rect=cat.available_rect()
            x=max(rect.left(),min(cat.x()+30,rect.right()-self.toolbar.width()+1))
            y=max(rect.top(),min(cat.y()-42,rect.bottom()-self.toolbar.height()+1))
            self.toolbar.move(x,y)

    def close(self):
        for window in self.windows.values():window.close()
        self.windows.clear()
        self.toolbar.close()
