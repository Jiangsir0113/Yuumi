import os
from pathlib import Path
import tempfile
import unittest

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from cat_model import ACTIONS
from main import CatWindow


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pet = CatWindow(Path(self.temp.name)/"state.json", testing=True)
        self.pet.timer.stop()
        self.pet.model.settings["roam"] = False
        self.pet.show()
        self.app.processEvents()

    def tearDown(self):
        self.pet.timer.stop()
        self.pet.save_timer.stop()
        if self.pet.panel:
            self.pet.panel.close()
        self.pet.stop_toy()
        self.pet.animator.close()
        self.pet.close()
        self.pet.deleteLater()
        self.app.processEvents()
        self.temp.cleanup()

    def test_every_action_has_valid_transparent_frames(self):
        for action in ACTIONS:
            self.pet.model.start(action)
            self.pet.repaint()
            for pix in self.pet.frames[ACTIONS[action].sprite]:
                self.assertFalse(pix.isNull(), action)
                image = pix.toImage()
                self.assertEqual(image.pixelColor(0,0).alpha(), 0, action)
            shot = self.pet.grab().toImage()
            self.assertEqual(shot.pixelColor(0,100).alpha(), 0, action)

    def test_real_mouse_press_maps_head_chin_back_and_paws(self):
        for x,y,expected in [(160,85,"head"), (160,140,"chin"), (160,220,"back"), (135,275,"paw")]:
            self.pet.model.start("idle")
            self.pet.animator.reset_for_test("idle")
            self.pet.sync_animation(0);self.pet.repaint();self.app.processEvents()
            QTest.mouseClick(self.pet, Qt.MouseButton.LeftButton, pos=QPoint(x,y))
            QTest.qWait(QApplication.doubleClickInterval()+80)
            self.assertEqual(self.pet.model.action, expected)

    def test_alt_drag_moves_window_and_clamps_to_screen(self):
        start = self.pet.pos()
        self.pet.move_safe(start+QPoint(-100,0))
        start = self.pet.pos()
        QTest.mousePress(self.pet, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.AltModifier, QPoint(160,120))
        self.assertTrue(self.pet.dragging)
        QTest.mouseMove(self.pet, QPoint(200,120))
        QTest.mouseRelease(self.pet, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.AltModifier, QPoint(200,120))
        self.assertFalse(self.pet.dragging)
        self.assertGreater(self.pet.x(),start.x())
        self.pet.move_safe(QPoint(-99999,99999))
        self.assertTrue(self.pet.available_rect().contains(self.pet.geometry()))

    def test_care_panel_buttons_and_settings(self):
        self.pet.open_panel()
        panel = self.pet.panel
        QTest.mouseClick(panel.action_buttons["chin"],Qt.MouseButton.LeftButton)
        self.assertEqual(self.pet.model.action,"chin")
        panel.name_edit.setText("小金豆")
        panel.rename()
        self.assertEqual(self.pet.model.settings["name"],"小金豆")
        panel.size_slider.setValue(85)
        self.assertAlmostEqual(self.pet.scale,.85)
        self.assertTrue(self.pet.available_rect().contains(self.pet.geometry()))
        self.pet.setting("sound",False)
        self.assertFalse(self.pet.model.settings["sound"])

    def test_food_walk_finishes_into_real_care_sequence(self):
        self.pet.perform("food")
        self.assertEqual(self.pet.care_pending,"food")
        for _ in range(120):
            self.pet.last_clock -= .1
            self.pet.tick()
        self.assertIsNone(self.pet.care_pending)
        self.assertIn(self.pet.model.action,{"eat","lick","groom"})

    def test_toy_can_start_and_stop_without_losing_cat(self):
        self.pet.perform("toy")
        self.assertTrue(self.pet.toy_mode)
        self.pet.stop_toy()
        self.assertFalse(self.pet.toy_mode)
        self.pet.perform("ball")
        self.assertIsNotNone(self.pet.toy_ball)
        self.pet.perform("head")
        self.assertIsNone(self.pet.scene.activity)
        self.assertIsNotNone(self.pet.scene.ball)
        self.assertEqual(self.pet.model.action,"head")
        self.pet.perform("ball")
        self.assertIsNotNone(self.pet.toy_ball)
        self.pet.model.start("idle")
        self.pet.animator.reset_for_test("idle")
        self.pet.sync_animation(0);self.pet.repaint();self.app.processEvents()
        QTest.mouseClick(self.pet,Qt.MouseButton.LeftButton,pos=QPoint(160,85))
        QTest.qWait(QApplication.doubleClickInterval()+80)
        self.assertIsNone(self.pet.scene.activity)
        self.assertIsNotNone(self.pet.scene.ball)
        self.assertIsNone(self.pet.ball_target)
        self.assertEqual(self.pet.model.action,"head")

    def test_double_click_opens_panel_without_touch_reward_or_cancel(self):
        self.pet.perform('ball')
        before=self.pet.model.affinity
        QTest.mouseClick(self.pet,Qt.MouseButton.LeftButton,pos=QPoint(160,85))
        QTest.qWait(50)
        QTest.mouseDClick(self.pet,Qt.MouseButton.LeftButton,pos=QPoint(160,85))
        QTest.qWait(QApplication.doubleClickInterval()+30)
        self.assertIsNotNone(self.pet.panel)
        self.assertTrue(self.pet.panel.isVisible())
        self.assertEqual(self.pet.model.affinity,before)
        self.assertEqual(self.pet.scene.activity.kind,'ball')

    def test_scratcher_controls_and_put_away(self):
        self.pet.perform('scratch')
        self.assertIsNotNone(self.pet.scene.scratcher)
        prop=self.pet.scene_view.windows['scratcher']
        self.assertFalse(prop.image.isNull())
        self.pet.perform('track')
        self.assertEqual(self.pet.scene.activity.kind,'track')
        self.pet.perform('stop')
        self.assertIsNone(self.pet.scene.activity)
        self.assertIsNotNone(self.pet.scene.scratcher)
        self.pet.perform('put_away')
        self.assertIsNone(self.pet.scene.scratcher)

    def test_scratcher_real_click_regions_and_dragging(self):
        self.pet.perform('scratch')
        prop=self.pet.scene_view.windows['scratcher']
        original=self.pet.scene.scratcher.x
        point=QPoint(prop.width()//2,round(prop.height()*.55))
        QTest.mousePress(prop,Qt.MouseButton.LeftButton,pos=point)
        QTest.mouseMove(prop,point+QPoint(30,0),delay=20)
        QTest.mouseRelease(prop,Qt.MouseButton.LeftButton,pos=point+QPoint(30,0))
        self.assertNotEqual(self.pet.scene.scratcher.x,original)
        self.assertEqual(self.pet.scene.activity.kind,'scratch')
        QTest.mouseClick(prop,Qt.MouseButton.LeftButton,pos=QPoint(prop.width()//2,round(prop.height()*.96)))
        self.assertEqual(self.pet.scene.activity.kind,'track')
        self.assertGreater(self.pet.scene.scratcher.taps,0)
        QTest.mouseClick(self.pet.scene_view.buttons['put_away'],Qt.MouseButton.LeftButton)
        self.assertIsNone(self.pet.scene.scratcher)

    def test_prop_scales_without_stretching(self):
        self.pet.perform('scratch')
        prop=self.pet.scene_view.windows['scratcher']
        ratio=prop.image.width()/prop.image.height()
        for scale in [.65,1.,1.5]:
            self.pet.change_size(scale);prop.sync()
            self.assertAlmostEqual(self.pet.scene.scratcher.width/self.pet.scene.scratcher.height,ratio,places=6)
            self.assertLess(abs(prop.width()/prop.height()-ratio),1/prop.height())
            self.assertLess(prop.height(),175*scale*.8+1)

    def test_hidden_tick_does_not_render_or_animate(self):
        before=self.pet.animator.clock
        self.pet.toggle_visible()
        self.pet.last_clock-=.2
        self.pet.tick()
        self.assertEqual(self.pet.animator.clock,before)
        self.assertEqual(self.pet.timer.interval(),250)
        self.assertFalse(self.pet.scene_view.toolbar.isVisible())

    def test_click_through_can_be_recovered_from_tray_path(self):
        self.pet.setting('click_through',True)
        self.assertTrue(self.pet.windowFlags() & Qt.WindowType.WindowTransparentForInput)
        self.pet.recover()
        self.assertFalse(self.pet.model.settings['click_through'])
        self.assertFalse(self.pet.windowFlags() & Qt.WindowType.WindowTransparentForInput)

    def test_smooth_animation_uses_manual_clock_and_encoded_timeline(self):
        self.assertEqual(self.pet.timer.interval(),8)
        self.pet.model.start("walk")
        self.pet.animator.reset_for_test("walk",phase=.4)
        self.pet.sync_animation(0)
        self.pet.frame()
        info=self.pet.motion_info["walk"]
        self.assertGreaterEqual(info["fps"],60)
        self.assertGreater(len(info["frame_ends"]),60)
        self.assertEqual(self.pet.model.settings["name"],"悠米")
        self.pet.open_panel()
        self.assertNotIn("belly",self.pet.panel.action_buttons)
        self.assertNotIn("roll",self.pet.panel.action_buttons)


if __name__ == "__main__":
    unittest.main()
