"""Small independent transparent windows for world objects (not a desktop overlay)."""
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QWidget,QHBoxLayout,QPushButton,QMenu
from pathlib import Path
import math

class PropWindow(QWidget):
    def __init__(self,cat,kind,assets):
        super().__init__(None,Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|
                         Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.WindowDoesNotAcceptFocus)
        self.cat,self.kind=cat,kind
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle('悠米 · '+{'scratcher':'大蒜猫抓板','bowl':'小食盆','ball':'小球'}[kind])
        self.setWindowIcon(cat.windowIcon())
        self.image=QPixmap(str(Path(assets)/'props/garlic-scratcher.png')) if kind=='scratcher' else None
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
        elif self.kind=='bowl':
            self.resize(round(84*s),round(38*s))
            self.move(round(data.x-42*s),round(data.floor-36*s))
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
                    x=data.width*(.12 if direction>0 else .88)+i*data.width*.035*direction
                    p.drawLine(QPointF(x,data.height*.64),QPointF(x-data.width*.02*direction,data.height*.80))
        elif self.kind=='bowl':
            p.scale(s,s)
            p.setPen(QPen(QColor('#a88b6a'),1.3))
            p.setBrush(QColor('#dfd2b8'))
            p.drawRoundedRect(QRectF(5,12,74,22),9,9)
            p.setBrush(QColor('#f8edda'))
            p.drawEllipse(QRectF(4,5,76,23))
            p.setPen(Qt.PenStyle.NoPen)
            if data.kind=='water':
                p.setBrush(QColor('#9ac5d0'))
                p.drawEllipse(QRectF(12,9,60,15*max(.15,data.amount)))
                p.setPen(QPen(QColor('#d7edf0'),1.3));p.drawArc(QRectF(18,10,47,10),20*16,125*16)
            else:
                for i in range(round(data.amount*19)):
                    xx=17+(i*17)%48; yy=11+(i*7)%10
                    p.setBrush(QColor('#b98957' if data.kind=='food' else '#d4a06c'))
                    p.drawEllipse(QRectF(xx,yy,5,3.5))
        else:
            p.translate(self.width()/2,self.height()/2)
            p.rotate(math.degrees(data.angle))
            radius=data.radius
            self._sphere(p,QPointF(),radius,'#dba58b')
            p.setPen(QPen(QColor('#fff1d7'),radius*.32))
            p.drawArc(QRectF(-radius*.7,-radius*.8,radius*1.4,radius*1.6),85*16,170*16)
        p.end()

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.RightButton:
            menu=QMenu(self)
            if self.kind=='scratcher':
                menu.addAction('抓白色绳面',lambda:self.cat.perform('scratch'))
                menu.addAction('拨圆槽小球',lambda:self.cat.perform('track'))
            else:
                menu.addAction('叫悠米过来',lambda:self.cat.perform(self.data.kind if self.kind=='bowl' else 'ball'))
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
        elif self.kind=='bowl':
            data.x=px+self.width()/2;data.floor=py+36*self.cat.scale
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
            else:self.cat.perform(self.data.kind if self.kind=='bowl' else 'ball')
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
        for label,action in [('抓绳','scratch'),('拨球','track'),('结束','stop'),('收起','put_away')]:
            button=QPushButton(label)
            button.clicked.connect(lambda checked=False,a=action:cat.perform(a))
            row.addWidget(button);self.buttons[action]=button
        self.toolbar.adjustSize()

    def sync(self,visible):
        cat=self.cat
        for kind in ['bowl','ball','scratcher']:
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
            self.toolbar.adjustSize()
            rect=cat.available_rect()
            x=max(rect.left(),min(cat.x()+30,rect.right()-self.toolbar.width()+1))
            y=max(rect.top(),min(cat.y()-42,rect.bottom()-self.toolbar.height()+1))
            self.toolbar.move(x,y)

    def close(self):
        for window in self.windows.values():window.close()
        self.windows.clear()
        self.toolbar.close()
