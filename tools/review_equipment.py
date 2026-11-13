"""Actual native renderer contact sheets; no desktop capture or user state."""
from pathlib import Path
import os,sys,json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter,QColor,QFont,QFontDatabase
from PySide6.QtCore import QPoint,QRect,Qt
from main import CatWindow,VERSION
from cat_model import ACTIONS
import time

out=ROOT/'qa/equipment-review';out.mkdir(parents=True,exist_ok=True)
app=QApplication([]);app.setQuitOnLastWindowClosed(False)
fid=QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
font=QFontDatabase.applicationFontFamilies(fid)[0]
poster=QImage(1400,960,QImage.Format.Format_RGB32);poster.fill(QColor('#f7f1e7'))
pp=QPainter(poster)
records=[]
for index,(kind,action,title) in enumerate([('scratch','scratch','1.2 倍猫咪高度 · 前腿抓绳'),('food','eat','小佩 SOLO · 弗列加特烘焙粮'),('water','drink','小佩 SOLO SE · 流水饮水'),('snack','treat','弗列加特主食猫条 · 开口舔食')]):
    pet=CatWindow(out/f'{kind}-state.json',testing=True)
    pet.timer.stop();pet.fullscreen_timer.stop();pet.save_timer.stop()
    pet.available_rect=lambda:QRect(0,0,700,450)
    pet.model.settings.update(roam=False,quiet=False,click_through=False)
    pet.model.satiety=pet.model.thirst=30
    pet.move_safe(QPoint(45,130));pet.show();pet.perform(kind)
    for _ in range(8):pet.scene.update(.25,pet.model,pet.x(),pet.y(),1,True,0)
    target=pet.scene.destination or (pet.x(),pet.y())
    pet.move_safe(QPoint(round(target[0]),round(target[1])))
    pet.scene.update(0,pet.model,pet.x(),pet.y(),1,True,0)
    pet.model.queue.clear();pet.model.start(action,90)
    pet.direction=pet.scene.direction
    key=ACTIONS[action].sprite
    deadline=time.monotonic()+10
    while key not in pet.animator.bank.decoded and time.monotonic()<deadline:
        pet.animator.bank.sample(key,0);app.processEvents();time.sleep(.01)
    assert key in pet.animator.bank.decoded
    pet.animator.reset_for_test(action,phase=.18 if kind=='scratch' else .35,direction=pet.direction)
    pet.sync_animation(0);pet.bubble_until=0;pet.hovered=False
    pet.scene_view.sync(True);app.processEvents();pet.repaint()
    shot=QImage(700,480,QImage.Format.Format_RGB32);shot.fill(QColor('#f7f1e7'))
    p=QPainter(shot);p.setFont(QFont(font,18));p.setPen(QColor('#6c573e'))
    p.drawText(QRect(10,15,680,40),Qt.AlignmentFlag.AlignCenter,title)
    for prop in pet.scene_view.windows.values():p.drawPixmap(prop.pos(),prop.grab())
    p.drawPixmap(pet.pos(),pet.grab());p.end()
    shot.save(str(out/f'{kind}.png'));pp.drawImage(QPoint(index%2*700,index//2*480),shot)
    records.append({'kind':kind,'cat_x':pet.x(),'cat_y':pet.y(),'direction':pet.direction,'stage':pet.scene.activity.stage})
    pet.scene_view.close();pet.animator.close();pet.hide();pet.deleteLater();app.processEvents()
pp.end();poster.save(str(out/'v1.4.0-equipment.png'))
(out/'review.json').write_text(json.dumps(records,indent=2))
print('EQUIPMENT_REVIEW_READY',flush=True)
