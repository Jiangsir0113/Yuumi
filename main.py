"""Jintuan: a small, offline Windows desktop companion."""
from __future__ import annotations

import argparse
import bisect
from collections import deque
import ctypes
from ctypes import wintypes
import json
import math
import os
from pathlib import Path
import sys
import time
import traceback


def diagnostic(message):
    flag="--self-test" if "--self-test" in sys.argv else "--benchmark" if "--benchmark" in sys.argv else None
    if flag:
        target=Path(sys.argv[sys.argv.index(flag)+1])
        target=target/"startup.txt" if flag=="--self-test" else target.with_suffix(".startup.txt")
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open("a",encoding="utf-8") as log:
            log.write(f"{time.monotonic():.3f} {message}\n")


diagnostic("Python runtime started")
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QCursor, QFont, QIcon, QMovie, QPainter, QPen, QPixmap
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QSlider, QSystemTrayIcon, QTabWidget, QVBoxLayout, QWidget)

from cat_model import ACTIONS, CARE_ACTIONS, CatModel, TOUCH_ACTIONS
from animation_engine import Animator, qimage
from scene_model import SceneController
from scene_view import SceneView
diagnostic("Qt modules imported")

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
ASSETS = ROOT / "assets"
VERSION = "1.3.1"


def state_path():
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "YoumiDesktop" / "state.json"


def fullscreen_on(screen_rect, own_handles=()):
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = wintypes.HWND
        handle = user32.GetForegroundWindow()
        if not handle or int(handle) in own_handles:
            return False
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(wintypes.HWND(handle), cls, 256)
        if cls.value in {"Progman", "WorkerW", "Shell_TrayWnd"}:
            return False
        rect = wintypes.RECT()
        user32.GetWindowRect(wintypes.HWND(handle), ctypes.byref(rect))
        return (rect.left <= screen_rect.left() and rect.top <= screen_rect.top()
                and rect.right >= screen_rect.right() and rect.bottom >= screen_rect.bottom())
    except (OSError, ValueError, AttributeError):
        return False


PANEL_STYLE = """
QDialog { background: #fbf7ef; color: #483b2e; }
QLabel { color: #483b2e; background: transparent; }
QLabel#title { font-size: 25px; font-weight: 700; }
QLabel#caption { color: #927f68; font-size: 11px; letter-spacing: 2px; }
QLabel#status { color: #8b7052; font-size: 13px; }
QTabWidget::pane { border: 0; padding-top: 12px; }
QTabBar::tab { background: #eee7da; color: #806b53; padding: 9px 18px; border-radius: 10px; margin-right: 5px; }
QTabBar::tab:selected { background: #cf9b60; color: white; }
QPushButton { color: #65503b; background: #fffdf8; border: 1px solid #e7d9c4;
  border-radius: 12px; padding: 11px 12px; font-size: 13px; min-height: 22px; }
QPushButton:hover { background: #f6ead7; border-color: #cba06a; }
QPushButton:pressed { background: #ecdbbd; }
QProgressBar { background: #ebe4d7; border: 0; border-radius: 4px; height: 8px; max-height: 8px; }
QProgressBar::chunk { background: #bb9569; border-radius: 4px; }
QLineEdit, QComboBox { background: #fffdf8; border: 1px solid #e7d9c4; padding: 9px; border-radius: 8px; color: #65503b; }
QCheckBox { color: #65503b; spacing: 8px; padding: 5px 0; }
QSlider::groove:horizontal { background: #e6dac7; height: 5px; border-radius: 2px; }
QSlider::handle:horizontal { background: #bf8f54; width: 17px; margin: -6px 0; border-radius: 8px; }
QScrollArea { border: 0; background: transparent; }
QScrollArea > QWidget > QWidget { background: #fbf7ef; }
"""


class CarePanel(QDialog):
    def __init__(self, pet):
        super().__init__(None, Qt.WindowType.Window)
        self.pet = pet
        self.setWindowTitle("悠米 1.3.1 · 陪伴小屋")
        self.setWindowIcon(pet.windowIcon())
        self.setMinimumWidth(440)
        self.resize(460, 610)
        self.setStyleSheet(PANEL_STYLE)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(12)
        cap = QLabel("A LITTLE CAT, A LITTLE COMPANY")
        cap.setObjectName("caption")
        root.addWidget(cap)
        self.title = QLabel()
        self.title.setObjectName("title")
        root.addWidget(self.title)
        self.status = QLabel()
        self.status.setObjectName("status")
        root.addWidget(self.status)
        row = QHBoxLayout()
        self.bars = {}
        for key, label in [("satiety", "饱饱"), ("thirst", "水分"), ("energy", "精神"), ("happiness", "开心"), ("affinity", "熟悉")]:
            col = QVBoxLayout()
            col.addWidget(QLabel(label))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            col.addWidget(bar)
            self.bars[key] = bar
            row.addLayout(col)
        root.addLayout(row)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.action_buttons = {}
        self.add_actions("撸猫", [("head", "摸摸头", "额头轻轻揉，眯眼呼噜"),
            ("chin", "挠下巴", "仰起小圆脸"), ("cheek", "揉揉脸", "把脸贴过来蹭蹭"),
            ("back", "顺顺毛", "弓背，抬起小尾巴"),
            ("paw", "碰爪爪", "伸爪，再轻轻收回来"), ("nuzzle", "蹭蹭你", "贴近一点点"),
            ("knead", "踩奶", "小爪子交替踩踩"), ("idle", "放松一会儿", "安静陪着你")],
            "也可以直接在猫咪身上按住左键轻轻移动。\n摸久了会想休息，给它一点自己的时间。")
        self.add_actions("照顾", [("food", "喂猫粮", "闻一闻、吃粮、舔嘴、洗脸"),
            ("snack", "小零食", "奖励一点点，饱了就不吃啦"), ("water", "喝点水", "补充水分"),
            ("sleep", "哄它睡觉", "从当前姿势安稳蜷起来"), ("wake", "轻轻叫醒", "睁眼，回到放松姿势"),
            ("groom", "洗脸理毛", "爱干净的小猫"), ("loaf", "揣手手", "安安静静陪你")],
            "离线不扣照顾分，也不会因为忘记喂食生病。\n吃喝过程中再点喂食，不会重复加饱腹。")
        self.add_actions("玩耍", [("toy", "逗猫棒", "鼠标靠近猫咪，它会伏低再扑抓"),
            ("ball", "拍小球", "玩一会儿，再洗洗脸"), ("wave", "叫叫它", "抬起小爪打招呼"),
            ("idle", "安静陪我", "回到放松的姿势"), ("stretch", "伸懒腰", "从前爪伸到小尾巴"),
            ("look", "看看四周", "好奇地左看右看"), ("walk", "散个步", "慢慢逛一会儿"),
            ("trot", "小跑一下", "精神满满"), ("scratch", "大蒜抓抓板", "抓白色绳面，活动前爪"),
            ("track", "拨圆槽小球", "小球沿底盘圆槽滚动、碰撞、减速"),
            ("stop", "结束互动", "道具留在原地，悠米先休息"),
            ("put_away", "收起道具", "收起食盆、小球和猫抓板")],
            "道具可拖动搬家。点猫抓板上部抓绳，点底盘拨球。\n互动时用桌面上的“结束”按钮或右键菜单停止。")
        self.add_settings()
        footer = QLabel("左键轻揉 · Alt + 拖动搬家 · 右键打开菜单")
        footer.setObjectName("status")
        root.addWidget(footer)
        self.refresh()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start(800)

    def add_actions(self, title, actions, note):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 3, 0, 0)
        grid = QGridLayout()
        grid.setSpacing(9)
        for i, (key, label, tip) in enumerate(actions):
            button = QPushButton(label)
            button.setObjectName("action_" + key)
            button.setToolTip(tip)
            button.clicked.connect(lambda checked=False, k=key: self.perform(k))
            self.action_buttons[key] = button
            grid.addWidget(button, i//2, i%2)
        layout.addLayout(grid)
        text = QLabel(note)
        text.setWordWrap(True)
        text.setObjectName("status")
        layout.addWidget(text)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        self.tabs.addTab(scroll, title)

    def perform(self, action):
        self.pet.perform(action)
        self.refresh()
        if action in {"toy", "ball", "scratch", "track"}:
            self.hide()

    def add_settings(self):
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(0, 4, 0, 0)
        col.addWidget(QLabel("小猫的名字"))
        self.name_edit = QLineEdit(self.pet.model.settings["name"])
        self.name_edit.setMaxLength(12)
        self.name_edit.editingFinished.connect(self.rename)
        col.addWidget(self.name_edit)
        col.addWidget(QLabel("桌宠大小"))
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(65, 150)
        self.size_slider.setValue(round(self.pet.scale * 100))
        self.size_slider.valueChanged.connect(lambda x: self.pet.change_size(x/100))
        col.addWidget(self.size_slider)
        col.addWidget(QLabel("活动屏幕"))
        self.screen_combo = QComboBox()
        for i, screen in enumerate(QApplication.screens()):
            self.screen_combo.addItem(f"屏幕 {i+1} · {screen.name()}", i)
        self.screen_combo.setCurrentIndex(self.pet.screen_index())
        self.screen_combo.currentIndexChanged.connect(self.pet.change_screen)
        col.addWidget(self.screen_combo)
        self.setting_checks={}
        for key, text in [("roam", "允许自己漫步"), ("quiet", "安静陪伴（暂停自主漫步和道具显示）"),
                          ("click_through", "鼠标穿透（从托盘恢复交互）"), ("sound", "轻柔呼噜声（合成音效）"),
                          ("hide_fullscreen", "全屏应用时自动隐藏")]:
            cb = QCheckBox(text)
            cb.setChecked(self.pet.model.settings[key])
            cb.toggled.connect(lambda checked, k=key: self.pet.setting(k, checked))
            self.setting_checks[key]=cb
            col.addWidget(cb)
        reset = QPushButton("把猫咪叫回屏幕中间")
        reset.clicked.connect(self.pet.recover)
        col.addWidget(reset)
        tip = QLabel("关闭小屋后猫咪会继续陪你。\n退出请用猫咪右键菜单或系统托盘。")
        tip.setObjectName("status")
        col.addWidget(tip)
        quit_button=QPushButton("保存并退出悠米")
        quit_button.clicked.connect(self.pet.quit_app)
        col.addWidget(quit_button)
        col.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        self.tabs.addTab(scroll, "设置")

    def rename(self):
        self.pet.model.settings["name"] = self.name_edit.text().strip()[:12] or "悠米"
        self.name_edit.setText(self.pet.model.settings["name"])
        self.pet.save()
        self.refresh()

    def refresh(self):
        self.title.setText(self.pet.model.settings["name"] + "的陪伴小屋")
        self.status.setText(self.pet.model.status())
        favorite=self.pet.model.favorite_region
        if favorite:
            self.status.setText(self.status.text()+" · 最喜欢"+{"head":"摸头","chin":"挠下巴","back":"顺毛","cheek":"揉脸","paw":"碰爪"}[favorite])
        for key, bar in self.bars.items():
            bar.setValue(round(getattr(self.pet.model, key)))
        for key,box in getattr(self,"setting_checks",{}).items():
            if box.isChecked()!=self.pet.model.settings[key]:
                box.blockSignals(True);box.setChecked(self.pet.model.settings[key]);box.blockSignals(False)


class SourceFrames:
    def __init__(self,paths):
        self.paths=paths

    def __len__(self):
        return len(self.paths)

    def __getitem__(self,index):
        return QPixmap(str(self.paths[index]))


class CatWindow(QWidget):
    def __init__(self, save_file=None, testing=False):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.testing = testing
        self.save_file = Path(save_file) if save_file else state_path()
        self.model = CatModel.load(self.save_file)
        self.scale = self.model.settings["size"]
        self.setWindowTitle("悠米 · 桌面猫咪")
        self.setObjectName("YoumiDesktopCat")
        self.setWindowIcon(QIcon(str(ASSETS / "cat.ico")))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        manifest = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
        self.frames = {key: SourceFrames([ASSETS / f"{key}-{i}.png" for i in range(info["frames"])])
                       for key, info in manifest.items()}
        if any(not p.exists() for seq in self.frames.values() for p in seq.paths):
            raise RuntimeError("猫咪素材不完整，请重新解压或下载。")
        self.bounds = {key: QRectF(*[info["bounds"][0], info["bounds"][1],
                       info["bounds"][2]-info["bounds"][0], info["bounds"][3]-info["bounds"][1]]) for key, info in manifest.items()}
        self.animator=Animator(ASSETS)
        self.motion_info=self.animator.bank.info
        self.current_pixmap=QPixmap()
        self.urgent_animation=False
        self.movie_frame_count = 0
        self.paint_count = 0
        self.tick_count = 0
        self.paint_times=deque(maxlen=24000)
        self.direction = 1
        self.velocity = 0.
        self.velocity_y=0.
        self.pos_float = QPointF()
        self.pressed = False
        self.dragging = False
        self.drag_ready = False
        self.drag_offset = QPoint()
        self.press_global = QPoint()
        self.last_touch_point = QPoint()
        self.last_touch_time = 0.
        self.gesture_id=0
        self.contact_active=False
        self.contact_region=None
        self.stroke_speed=0.
        self.candidate_region=None
        self.candidate_time=0.
        self.last_action = self.model.action
        self.last_clock = time.monotonic()
        self.menu_open = False
        self.manual_hidden = False
        self.fullscreen_hidden = False
        self.hovered = False
        self.bubble = "右键打开陪伴小屋"
        self.bubble_until = self.last_clock + 12
        self.toy_mode = False
        self.toy_until = 0.
        self.care_pending = None
        self.care_target = None
        self.care_deadline = 0.
        self.toy_ball = None
        self.ball_target = None
        self.ball_deadline = 0.
        self.panel = None
        self.scene=SceneController()
        self.scene_view=SceneView(self,ASSETS)
        self.resize(round(320*self.scale), round(307*self.scale))
        self.recover(restore=True)
        self.sound = QSoundEffect(self)
        self.sound.setSource(QUrl.fromLocalFile(str(ASSETS / "purr.wav")))
        self.sound.setVolume(.17)
        self.setup_tray()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.start(8)
        self.save_timer = QTimer(self)
        self.save_timer.timeout.connect(self.save)
        self.save_timer.start(30000)
        self.fullscreen_timer = QTimer(self)
        self.fullscreen_timer.timeout.connect(self.check_fullscreen)
        if not testing:
            self.fullscreen_timer.start(1200)
        QApplication.instance().screenRemoved.connect(lambda *_: self.recover())
        if self.model.settings.get("click_through"):
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput,True)
            self.show()

    def screen_index(self):
        return min(self.model.settings["screen"], max(0, len(QApplication.screens())-1))

    def active_screen(self):
        return QApplication.screens()[self.screen_index()]

    def available_rect(self):
        return self.active_screen().availableGeometry()

    def clamp_position(self, point):
        rect = self.available_rect()
        return QPoint(round(max(rect.left(), min(point.x(), rect.right()-self.width()+1))),
                      round(max(rect.top(), min(point.y(), rect.bottom()-self.height()+1))))

    def move_safe(self, point):
        pos = self.clamp_position(point)
        self.move(pos)
        self.pos_float = QPointF(pos)

    def recover(self, restore=False):
        if not restore and self.model.settings.get("click_through"):
            self.setting("click_through",False)
        rect = self.available_rect()
        saved = self.model.settings.get("position")
        point = QPoint(*saved) if restore and saved else QPoint(rect.center().x()-self.width()//2, rect.bottom()-self.height()+1)
        self.move_safe(point)
        self.manual_hidden = False
        if not self.fullscreen_hidden:
            self.show()
        if not restore:
            self.say("我回来啦，喵～")

    def setup_tray(self):
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip("悠米 · 右键照顾猫咪")
        menu = QMenu()
        menu.addAction("打开陪伴小屋", self.open_panel)
        menu.addAction("把猫咪叫回来", self.recover)
        menu.addAction("显示 / 隐藏猫咪", self.toggle_visible)
        self.through_action=menu.addAction("鼠标穿透（点击取消）")
        self.through_action.setCheckable(True)
        self.through_action.setChecked(self.model.settings.get("click_through",False))
        self.through_action.toggled.connect(lambda val:self.setting("click_through",val))
        menu.addAction("结束当前互动",lambda:self.perform("stop"))
        menu.addAction("收起所有道具",lambda:self.perform("put_away"))
        menu.addSeparator()
        menu.addAction("退出悠米", self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        if not self.testing:
            self.tray.show()

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_panel()
        elif reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.recover()

    def toggle_visible(self):
        self.manual_hidden = not self.manual_hidden
        if self.manual_hidden:
            self.hide()
            self.stop_toy()
        elif not self.fullscreen_hidden:
            self.show()
        self.scene_view.sync(self.isVisible() and not self.model.settings.get("quiet"))
        self.timer.setInterval(8 if self.isVisible() else 250)

    def check_fullscreen(self):
        handles = [int(self.winId())]
        if self.panel:
            handles.append(int(self.panel.winId()))
        hidden = self.model.settings["hide_fullscreen"] and fullscreen_on(self.active_screen().geometry(), handles)
        if hidden != self.fullscreen_hidden:
            self.fullscreen_hidden = hidden
            if hidden:
                self.stop_toy()
            self.hide() if hidden or self.manual_hidden else self.show()
            self.scene_view.sync(self.isVisible() and not self.model.settings.get("quiet"))
            self.timer.setInterval(8 if self.isVisible() else 250)

    def setting(self, key, val):
        self.model.settings[key] = val
        if key == "roam" and not val and self.model.action in {"walk", "trot"} and not self.care_pending:
            self.model.request("idle")
        if key == "sound" and not val:
            self.sound.stop()
        if key == "hide_fullscreen":
            self.check_fullscreen()
        if key=="click_through":
            visible=self.isVisible()
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput,bool(val))
            if visible:self.show()
            if hasattr(self,"through_action"):
                self.through_action.blockSignals(True)
                self.through_action.setChecked(bool(val))
                self.through_action.blockSignals(False)
            self.end_gesture()
        if key=="quiet" and val:
            self.scene.cancel(self.model)
            self.model.start("loaf")
        self.scene_view.sync(self.isVisible() and not self.model.settings.get("quiet"))
        self.save()

    def change_screen(self, index):
        self.scene.put_away()
        self.model.settings["screen"] = max(0, index)
        self.recover()
        self.save()

    def change_size(self, scale):
        baseline = self.y()+self.height()
        self.scale = max(.65, min(1.5, scale))
        self.model.settings["size"] = self.scale
        self.resize(round(320*self.scale), round(307*self.scale))
        if self.scene.scratcher:self.scene.scratcher.scale=self.scale
        if self.scene.ball:self.scene.ball.radius=12*self.scale
        self.move_safe(QPoint(self.x(), baseline-self.height()))
        self.save()

    def save(self):
        self.model.settings["position"] = [self.x(), self.y()]
        try:
            self.model.save(self.save_file)
        except OSError:
            # Keep running on a read-only profile; report it once in the cat bubble.
            self.say("这次没能保存设置，下次再试试")

    def say(self, message, seconds=4):
        self.bubble = message
        self.bubble_until = time.monotonic()+seconds
        self.update()

    def perform(self, action):
        self.urgent_animation=True
        self.end_gesture()
        self.model.last_message=""
        if action in {"food","water","snack","toy","ball","scratch","track"}:
            if self.model.settings.get("quiet"):
                self.setting("quiet",False)
            kind="wand" if action=="toy" else action
            self.scene.begin(kind,self.model,self.x(),self.y(),self.scale,self.scene_limits())
            self.toy_mode=kind=="wand"
            self.say(self.scene.message,6)
            self.scene_view.sync(self.isVisible() and not self.model.settings.get("quiet"))
            self.toy_ball=self.scene_view.windows.get("ball")
            a=self.scene.activity
            self.care_pending=a.kind if a and a.kind in {"food","water","snack"} and a.stage=="approach" else None
            return
        if action in {"stop","put_away"}:
            self.scene.put_away(self.model) if action=="put_away" else self.scene.cancel(self.model)
            self.toy_mode=False
            self.say("道具收好啦" if action=="put_away" else "先歇一会儿，想玩时再叫我")
            self.scene_view.sync(self.isVisible() and not self.model.settings.get("quiet"))
            return
        self.scene.cancel()
        self.toy_mode=False
        accepted=self.model.request(action)
        self.say(self.model.last_message or ACTIONS[self.model.action].label)
        if accepted and action in TOUCH_ACTIONS:
            self.purr()
        self.update()

    def scene_limits(self):
        rect=self.available_rect()
        return (rect.left(),rect.top(),rect.right()-self.width()+1,rect.bottom()-self.height()+1)

    def purr(self):
        if self.model.settings["sound"] and not self.sound.isPlaying():
            self.sound.play()

    def sync_animation(self,dt):
        pixels=self.animator.update(self.model.action,dt,self.direction,self.urgent_animation)
        self.urgent_animation=False
        self.current_pixmap=QPixmap.fromImage(qimage(pixels))
        self.movie_frame_count=self.animator.bank.frame_events

    def frame(self):
        if self.current_pixmap.isNull() or self.animator.action!=self.model.action or self.animator.direction!=self.direction:
            self.sync_animation(0)
        return self.current_pixmap

    def tick(self):
        self.tick_count += 1
        now = time.monotonic()
        dt = min(now-self.last_clock, .25)
        self.last_clock = now
        visible=self.isVisible() and not self.manual_hidden and not self.fullscreen_hidden
        self.timer.setInterval(8 if visible else 250)
        if not self.menu_open and not self.dragging:
            if self.contact_active and self.contact_region:
                age=now-self.last_touch_time
                speed=self.stroke_speed*math.exp(-max(0.,age-.04)/.15)
                self.model.contact(self.contact_region,dt,speed/self.scale)
            if visible:
                cursor=QCursor.pos()
                self.scene.update(dt,self.model,self.x(),self.y(),self.scale,
                                  self.animator.execution_ready and self.animator.action==self.model.action,
                                  self.animator.phase,(cursor.x(),cursor.y()),self.scene_limits())
                if self.scene.activity:
                    self.direction=self.scene.direction
                    if self.scene.destination and self.model.action in {"walk","trot"}:
                        dx=self.scene.destination[0]-self.x()
                        if abs(dx)>2:self.direction=1 if dx>0 else -1
            self.animator.request(self.model.action,self.direction,self.urgent_animation)
            self.model.tick(dt,touching=self.contact_active,
                            executing=self.animator.execution_ready if visible else True)
        if self.model.action != self.last_action:
            prior=self.last_action
            self.last_action = self.model.action
            if self.model.action in {"walk", "trot"} and prior not in {"walk","trot"} and self.scene.activity is None:
                self.direction = self.model.rng.choice([-1, 1])
            if self.model.action == "refuse":
                self.say("先歇一会儿，我一会儿再来找你")
            if self.model.action in {"nuzzle", "knead"}:
                self.purr()
        if not visible:
            self.scene_view.sync(False)
            return
        self.sync_animation(dt if not (self.dragging or self.menu_open) else 0)
        target_velocity=0.
        target_y=0.
        if self.model.action in {"walk","trot"} and not (self.pressed or self.menu_open or self.dragging):
            speed=(95 if self.model.action=="trot" else 44)*self.scale*self.animator.locomotion_weight
            if self.scene.destination:
                dx=self.scene.destination[0]-self.pos_float.x()
                dy=self.scene.destination[1]-self.pos_float.y()
                distance=math.hypot(dx,dy)
                factor=min(speed,distance*5)/max(.001,distance)
                target_velocity=dx*factor;target_y=dy*factor
            elif self.model.settings["roam"] and not self.model.settings.get("quiet"):
                l,_,r,_=self.scene_limits()
                distance=r-self.x() if self.direction>0 else self.x()-l
                if distance<2 and abs(self.velocity)<8 and self.animator.graph.ready:
                    self.direction*=-1
                    self.animator.request(self.model.action,self.direction,True)
                    self.velocity=0.
                target_velocity=self.direction*speed*min(1.,max(.06,distance/20))
        if self.model.action=="pounce" and self.animator.graph.ready:
            target_velocity=self.scene.pounce_velocity
        self.velocity+=(target_velocity-self.velocity)*(1-math.exp(-dt/.08))
        self.velocity_y+=(target_y-self.velocity_y)*(1-math.exp(-dt/.08))
        if self.dragging or self.pressed:
            self.velocity=self.velocity_y=0.
        if abs(self.velocity)>.05 or abs(self.velocity_y)>.05:
            x=self.pos_float.x()+self.velocity*dt
            y=self.pos_float.y()+self.velocity_y*dt
            candidate=self.clamp_position(QPoint(round(x),round(y)))
            if candidate.x()!=round(x) and self.velocity*self.direction>0:
                self.velocity=0.
                if self.scene.activity is None:self.direction*=-1
            self.move(candidate)
            self.pos_float=QPointF(x if candidate.x()==round(x) else candidate.x(),y if candidate.y()==round(y) else candidate.y())
        a=self.scene.activity
        self.toy_mode=bool(a and a.kind=="wand")
        self.care_pending=a.kind if a and a.kind in {"food","water","snack"} and a.stage=="approach" else None
        self.care_target=self.scene.destination[0] if self.care_pending and self.scene.destination else None
        self.ball_target=self.scene.ball.x if a and a.kind=="ball" and self.scene.ball else None
        self.scene_view.sync(not self.model.settings.get("quiet"))
        self.toy_ball=self.scene_view.windows.get("ball")
        self.update()

    def paintEvent(self, event):
        self.paint_count += 1
        self.paint_times.append(time.monotonic())
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.scale(self.scale, self.scale)
        p.save()
        action = self.model.action
        p.translate(0,36)
        current = self.frame()
        # Retain subpixel travel between native integer window positions.
        fractional_x = self.pos_float.x()-self.x() if action in {"walk","trot"} else 0
        p.drawPixmap(QPointF(fractional_x,0),current)
        p.setOpacity(1.)
        p.restore()
        if self.toy_mode:
            cursor = self.mapFromGlobal(QCursor.pos())
            tip = QPointF(max(12, min(308, cursor.x()/self.scale)), max(44, min(270, cursor.y()/self.scale)))
            p.setPen(QPen(QColor("#a98965"), 2))
            p.drawLine(tip+QPointF(18,-25), tip+QPointF(10,-9))
            p.setPen(QPen(QColor("#ce8975"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(tip+QPointF(10,-9), tip)
        visible_bubble = self.hovered or time.monotonic()<self.bubble_until
        if visible_bubble:
            message = self.bubble if time.monotonic()<self.bubble_until else f"{self.model.settings['name']} · {ACTIONS[action].label}"
            p.setFont(QFont("Microsoft YaHei UI", 9))
            width = min(312, p.fontMetrics().horizontalAdvance(message)+28)
            p.setPen(QPen(QColor(216,199,173,210), 1))
            p.setBrush(QColor(255,251,243,240))
            p.drawRoundedRect(QRectF((320-width)/2, 2, width, 29), 14, 14)
            p.setPen(QColor("#69533d"))
            text = p.fontMetrics().elidedText(message, Qt.TextElideMode.ElideRight, width-20)
            p.drawText(QRectF((320-width)/2+10,2,width-20,29), Qt.AlignmentFlag.AlignCenter, text)
        p.end()

    def region_at(self, point):
        self.frame()
        return self.animator.hit_test(point.x()/self.scale,point.y()/self.scale-36)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.end_gesture()
            self.context_menu(event.globalPosition().toPoint())
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.gesture_id+=1
            generation=self.gesture_id
            self.pressed = True
            self.contact_active=False
            self.press_global = event.globalPosition().toPoint()
            self.drag_offset = self.press_global-self.pos()
            self.last_touch_point = self.press_global
            self.last_touch_time = time.monotonic()
            self.press_region=self.region_at(event.position())
            self.stroke_speed=0.
            self.dragging = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier) or self.drag_ready
            self.drag_ready = False
            if self.dragging:
                self.scene.cancel()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            else:
                def held():
                    if self.pressed and self.gesture_id==generation and not self.contact_active:
                        self.activate_contact(self.press_region)
                QTimer.singleShot(QApplication.doubleClickInterval()+10,held)

    def activate_contact(self,region):
        if region is None:return
        self.scene.cancel()
        self.toy_mode=False
        self.care_pending=self.care_target=self.ball_target=None
        self.urgent_animation=True
        self.contact_active=True
        self.contact_region=region
        self.candidate_region=region
        self.candidate_time=time.monotonic()
        self.model.last_message=""
        accepted=self.model.touch(region,0.)
        self.say(self.model.last_message or ACTIONS[self.model.action].label)
        if accepted:self.purr()

    def end_gesture(self):
        self.gesture_id+=1
        self.pressed=False
        self.dragging=False
        self.contact_active=False
        self.contact_region=None
        self.press_region=None
        self.model.end_contact()
        self.unsetCursor()

    def mouseMoveEvent(self, event):
        if not self.pressed:
            return
        point = event.globalPosition().toPoint()
        if self.dragging:
            self.move_safe(point-self.drag_offset)
            return
        if (point-self.press_global).manhattanLength()>4:
            region=self.region_at(event.position())
            if not self.contact_active:
                self.activate_contact(region)
            now = time.monotonic()
            elapsed=max(.001,now-self.last_touch_time)
            speed=math.hypot(point.x()-self.last_touch_point.x(),point.y()-self.last_touch_point.y())/elapsed
            self.stroke_speed+=(min(2000.,speed)-self.stroke_speed)*(1-math.exp(-elapsed/.05))
            if region and region!=self.candidate_region:
                self.candidate_region=region;self.candidate_time=now
            if region and now-self.candidate_time>=.08:
                self.contact_region=region
            self.last_touch_point, self.last_touch_time = point, now

    def mouseReleaseEvent(self, event):
        dragging=self.dragging
        active=self.contact_active
        region=getattr(self,"press_region",None)
        self.end_gesture()
        if dragging:
            self.model.request("idle")
            self.say("这里也很舒服～")
            self.save()
        elif not active and region is not None:
            generation=self.gesture_id
            def tap():
                if generation!=self.gesture_id:return
                self.scene.cancel()
                self.urgent_animation=True
                self.model.last_message=""
                accepted=self.model.touch(region,.12)
                self.say(self.model.last_message or ACTIONS[self.model.action].label)
                if accepted:self.purr()
            QTimer.singleShot(QApplication.doubleClickInterval()+10,tap)

    def mouseDoubleClickEvent(self, event):
        self.end_gesture()
        self.open_panel()

    def enterEvent(self, event):
        self.hovered = True
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def leaveEvent(self, event):
        self.hovered = False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.stop_toy()

    def stop_toy(self):
        if self.scene.activity:
            self.scene.cancel(self.model)
        self.toy_mode=False
        self.ball_target=self.care_pending=self.care_target=None

    def open_panel(self):
        if self.panel is None:
            self.panel = CarePanel(self)
            rect = self.available_rect()
            x = self.x()-self.panel.width()-18
            if x < rect.left():
                x = self.x()+self.width()+18
            x = max(rect.left(), min(x,rect.right()-self.panel.width()+1))
            y = max(rect.top(), min(self.y()-150,rect.bottom()-self.panel.height()+1))
            self.panel.move(x,y)
        self.panel.refresh()
        self.panel.show()
        rect=self.available_rect()
        frame=self.panel.frameGeometry()
        self.panel.move(max(rect.left(),min(self.panel.x(),rect.right()-frame.width()+1)),
                        max(rect.top(),min(self.panel.y(),rect.bottom()-frame.height()+1)))
        self.panel.raise_()
        self.panel.activateWindow()

    def context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background:#fffcf6; color:#65503b; border:1px solid #dfcfb7; padding:6px; } QMenu::item { padding:7px 24px; } QMenu::item:selected { background:#f0e2cb; }")
        menu.addAction("打开陪伴小屋…", self.open_panel)
        menu.addSeparator()
        for label, key in [("喂猫粮", "food"), ("喝点水", "water"), ("摸摸头", "head"),
                           ("逗猫棒", "toy"), ("大蒜抓抓板", "scratch"), ("拨圆槽小球", "track"),
                           ("结束互动", "stop"), ("收起道具", "put_away"),
                           ("哄它睡觉", "sleep"), ("轻轻叫醒", "wake")]:
            menu.addAction(label, lambda k=key: self.perform(k))
        menu.addSeparator()
        roam = menu.addAction("允许自己漫步")
        roam.setCheckable(True)
        roam.setChecked(self.model.settings["roam"])
        roam.toggled.connect(lambda val: self.setting("roam", val))
        menu.addAction("搬家：接着拖动猫咪", self.arm_drag)
        menu.addAction("暂时隐藏（托盘找回）", self.toggle_visible)
        menu.addSeparator()
        menu.addAction("退出悠米", self.quit_app)
        self.menu_open = True
        try:
            menu.exec(pos)
        finally:
            self.menu_open = False
            self.pressed = False

    def arm_drag(self):
        self.drag_ready = True
        self.say("按住我拖到喜欢的位置吧", 8)
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def closeEvent(self, event):
        self.save()
        self.scene_view.close()
        self.timer.stop()
        self.save_timer.stop()
        self.animator.close()
        event.accept()

    def quit_app(self):
        self.save()
        self.animator.close()
        self.scene_view.close()
        self.tray.hide()
        QApplication.instance().quit()


def executable_self_test(pet, output):
    """Exercise real packaged assets/UI and leave reviewable evidence, then exit."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    pet.timer.stop()
    pet.fullscreen_timer.stop()
    errors = []
    checks = []
    try:
        for action in ACTIONS:
            pet.model.start(action)
            for t in (0., .8):
                pet.animator.reset_for_test(action,phase=t)
                pet.sync_animation(0)
                pet.repaint()
                QApplication.processEvents()
                pix = pet.grab()
                if pix.isNull():
                    raise AssertionError(f"Render failed: {action}")
                if pet.motion_info[ACTIONS[action].sprite]["fps"]<60:
                    raise AssertionError(f"Smooth animation missing: {action}")
            checks.append(action)
        pet.model.start("idle")
        pet.say("你好，我是悠米。右键就能照顾我。", 20)
        pet.grab().save(str(output / "desktop-cat.png"))
        pet.open_panel()
        QApplication.processEvents()
        pet.panel.grab().save(str(output / "care-panel.png"))
        pet.panel.perform("head")
        assert pet.model.action == "head"
        pet.change_size(.8)
        pet.change_size(1.)
        assert pet.available_rect().contains(pet.geometry())
        pet.save()
        restored = CatModel.load(pet.save_file)
        assert restored.settings["name"] == pet.model.settings["name"]
        pet.perform("scratch")
        assert pet.scene.scratcher is not None
        prop=pet.scene_view.windows["scratcher"]
        assert not prop.image.isNull(),"Packaged scratcher art is missing"
        QApplication.processEvents()
        prop.grab().save(str(output/"garlic-scratcher.png"))
        pet.perform("track")
        assert pet.scene.activity.kind=="track"
        pet.scene.scratcher.impulse(0,3.)
        angle=pet.scene.scratcher.angles[0]
        pet.scene.scratcher.step(.2)
        assert pet.scene.scratcher.angles[0]!=angle
        pet.perform("stop")
        assert pet.scene.scratcher is not None and pet.scene.activity is None
        pet.perform("put_away")
        assert pet.scene.scratcher is None
    except Exception:
        errors.append(traceback.format_exc())
    report = {"version": VERSION, "frozen_executable": bool(getattr(sys, "frozen", False)),
              "smooth_webp_valid":all(i["fps"]>=60 for i in pet.motion_info.values()), "render_timer_ms":pet.timer.interval(),
              "removed_actions":["roll","belly","side_sleep"],
              "scene_objects_valid":not errors,"rendered_actions": checks, "ok": not errors, "errors": errors}
    (output / "self-test.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    QApplication.instance().exit(0 if not errors else 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", metavar="OUTPUT_DIR")
    parser.add_argument("--state-file")
    parser.add_argument("--quit-after", type=int)
    parser.add_argument("--panel", action="store_true")
    parser.add_argument("--benchmark")
    parser.add_argument("--benchmark-all")
    args = parser.parse_args()
    first_launch = not Path(args.state_file or state_path()).exists()
    app = QApplication(sys.argv[:1])
    diagnostic("QApplication initialized")
    app.setApplicationName("YoumiDesktop")
    app.setOrganizationName("Youmi")
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Microsoft YaHei UI", 10))
    server = None
    if not args.self_test and not args.state_file:
        channel = "YoumiDesktop_"+os.environ.get("USERNAME", "user")
        socket = QLocalSocket()
        socket.connectToServer(channel)
        if socket.waitForConnected(250):
            socket.write(b"show")
            socket.waitForBytesWritten(500)
            socket.waitForReadyRead(400)
            running=bytes(socket.readAll()).decode(errors="replace")
            if running!=VERSION:
                QMessageBox.information(None,"先退出旧版悠米",
                    "旧版悠米仍在运行。请从系统托盘或猫咪右键菜单选择“退出悠米”，再打开这个 1.3.1 新版。")
            return 0
        server = QLocalServer()
        QLocalServer.removeServer(channel)
        if not server.listen(channel):
            raise RuntimeError("无法创建本地桌宠会话。")
    pet = CatWindow(args.state_file, testing=bool(args.self_test))
    diagnostic("Desktop cat initialized")
    app.aboutToQuit.connect(pet.save)
    app.aboutToQuit.connect(pet.animator.close)
    if server:
        def received():
            connection = server.nextPendingConnection()
            if connection:
                if connection.bytesAvailable()==0:
                    connection.waitForReadyRead(100)
                connection.readAll()
                connection.write(VERSION.encode())
                connection.flush()
                connection.waitForBytesWritten(100)
                connection.disconnectFromServer()
                connection.deleteLater()
            pet.recover()
        server.newConnection.connect(received)
    pet.show()
    if args.panel or (first_launch and not args.self_test and not args.state_file):
        pet.open_panel()
    if args.self_test:
        diagnostic("Scheduling self test")
        QTimer.singleShot(250, lambda: executable_self_test(pet, args.self_test))
    if args.benchmark:
        pet.fullscreen_timer.stop()
        pet.model.settings["hide_fullscreen"] = False
        pet.model.settings["roam"] = False
        pet.model.start("walk",20)
        started=time.monotonic()
        def finish_benchmark():
            duration=time.monotonic()-started
            report={"version":VERSION,"seconds":round(duration,3),
                "tick_fps":round(pet.tick_count/duration,2),
                "paint_fps":round(pet.paint_count/duration,2),
                "animation_frame_events_per_second":round(pet.movie_frame_count/duration,2),
                "non_identical_frames_per_second":round(pet.animator.non_identical_frames/duration,2),
                "movie_valid":all(i["fps"]>=60 for i in pet.motion_info.values()),
                "encoded_action_fps":64,"frozen":bool(getattr(sys,"frozen",False))}
            Path(args.benchmark).write_text(json.dumps(report,indent=2),encoding="utf-8")
            pet.quit_app()
        QTimer.singleShot(8000,finish_benchmark)
    if args.benchmark_all:
        from benchmarks import LiveBenchmark
        pet.live_benchmark=LiveBenchmark(pet,Path(args.benchmark_all))
    if args.quit_after:
        QTimer.singleShot(args.quit_after*1000, pet.quit_app)
    return app.exec()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        error = traceback.format_exc()
        log = Path(os.environ.get("TEMP", ".")) / "Jintuan-error.log"
        log.write_text(error, encoding="utf-8")
        if QApplication.instance():
            QMessageBox.critical(None, "悠米暂时没能醒来", f"请查看错误记录：\n{log}\n\n{error[-500:]}")
        raise
