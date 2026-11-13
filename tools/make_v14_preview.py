"""Record the actual native scene/animation code at a controlled 64fps timeline."""
from pathlib import Path
import os
import sys
import time
import json
import subprocess
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT.parent/'preview-deps'))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint,QRect,QPointF,Qt
from PySide6.QtGui import QImage,QPainter,QColor,QFont,QFontDatabase
import numpy as np
import imageio_ffmpeg
from main import CatWindow,VERSION

out=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'qa/scene-preview'
out.mkdir(parents=True,exist_ok=True)
app=QApplication([]);app.setQuitOnLastWindowClosed(False)
font_id=QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
font_family=QFontDatabase.applicationFontFamilies(font_id)[0]
app.setFont(QFont(font_family,10))
pet=CatWindow(out/'preview-state.json',testing=True)
pet.timer.stop();pet.fullscreen_timer.stop();pet.save_timer.stop()
pet.available_rect=lambda:QRect(0,0,960,560)
pet.model.settings.update({'roam':False,'quiet':False,'click_through':False})
pet.model.satiety=35
pet.move_safe(QPoint(65,230));pet.show()
pet.model.start('idle',90)
pet.animator.reset_for_test('idle')
events=[(.5,'scratch'),(6.,'track'),(11.,'stop'),(12.,'food'),(27.,'water'),(41.,'snack'),(53.,'head'),(55.,'stop')]
labels={'scratch':'1.2 倍高度 · 双前腿抓绳','track':'圆形槽道 · 拨球',
        'food':'小佩 SOLO · 弗列加特烘焙粮','water':'小佩 SOLO SE · 流水饮水',
        'snack':'弗列加特主食猫条 · 开口舔食','head':'随时打断 · 摸摸头',
        'stop':'结束互动 · 道具保留'}
encoder=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-hide_banner','-loglevel','error',
    '-f','rawvideo','-pix_fmt','rgb24','-s','960x600','-r','64','-i','-','-an',
    '-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',
    str(out/f'Yuumi-v{VERSION}-preview.mp4')],stdin=subprocess.PIPE)
index=0;label='悠米 · 安静陪伴'
metrics={'version':VERSION,'fps':64,'frames':58*64,'scratch_strikes':0,'track_taps':0,'equipment':{},'events':[]}
for frame in range(58*64):
    now=frame/64
    if index<len(events) and now>=events[index][0]:
        action=events[index][1];pet.perform(action);label=labels[action]
        metrics['events'].append({'time':now,'action':action});index+=1
    pet.last_clock=time.monotonic()-1/64
    pet.tick()
    app.processEvents()
    canvas=QImage(960,600,QImage.Format.Format_RGB888);canvas.fill(QColor('#f7f1e7'))
    p=QPainter(canvas);p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setFont(QFont(font_family,22));p.setPen(QColor('#6c573e'))
    p.drawText(QRect(0,20,960,46),Qt.AlignmentFlag.AlignCenter,'悠米 '+VERSION+' · '+label)
    for prop in pet.scene_view.windows.values():
        if prop.isVisible():p.drawPixmap(prop.pos(),prop.grab())
    p.drawPixmap(pet.pos(),pet.grab())
    p.setFont(QFont(font_family,12));p.setPen(QColor('#9c8363'))
    p.drawText(QRect(0,560,960,30),Qt.AlignmentFlag.AlignCenter,'实际程序渲染 · 64 FPS 素材 · 可中断动作与独立场景道具')
    p.end()
    pixels=np.frombuffer(canvas.bits(),dtype=np.uint8).reshape(600,canvas.bytesPerLine())[:,:960*3]
    encoder.stdin.write(pixels.tobytes())
    if frame in (4*64,9*64,22*64,37*64,49*64):
        canvas.save(str(out/f'scene-{frame//64:02d}.png'))
    if pet.scene.scratcher:
        metrics['scratch_strikes']=max(metrics['scratch_strikes'],pet.scene.scratcher.scratches)
        metrics['track_taps']=max(metrics['track_taps'],pet.scene.scratcher.taps)
    for kind in ['feeder','fountain','snack']:
        obj=getattr(pet.scene,kind)
        if obj:metrics['equipment'][kind]={'amount':round(obj.amount,4),'stock':obj.stock}
    if frame%320==0:print('PREVIEW_FRAME',frame,flush=True)
encoder.stdin.close();assert encoder.wait()==0
(out/'preview.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
pet.scene_view.close();pet.animator.close();pet.hide()
print('PREVIEW_READY',json.dumps(metrics,ensure_ascii=True),flush=True)
