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
        for y, expected in [(85,"head"), (140,"chin"), (175,"back"), (275,"paw")]:
            self.pet.model.start("idle")
            QTest.mouseClick(self.pet, Qt.MouseButton.LeftButton, pos=QPoint(160,y))
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
        self.assertIsNone(self.pet.toy_ball)
        self.assertEqual(self.pet.model.action,"head")
        self.pet.perform("ball")
        self.assertIsNotNone(self.pet.toy_ball)
        self.pet.model.start("idle")
        QTest.mouseClick(self.pet,Qt.MouseButton.LeftButton,pos=QPoint(160,85))
        self.assertIsNone(self.pet.toy_ball)
        self.assertIsNone(self.pet.ball_target)
        self.assertEqual(self.pet.model.action,"head")

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
