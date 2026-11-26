from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from cat_model import CatModel
from main import CatWindow


class CompanionWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.folder = TemporaryDirectory()
        self.state = Path(self.folder.name) / "state.json"
        self.pet = CatWindow(self.state, testing=True)
        self.pet.timer.stop()
        self.pet.save_timer.stop()
        self.pet.model.settings["roam"] = False
        self.pet.show()
        self.app.processEvents()

    def tearDown(self):
        if self.pet.panel:
            self.pet.panel.close()
        self.pet.close()
        self.app.processEvents()
        self.folder.cleanup()

    def test_sunbeam_drag_and_restart_restore_placement(self):
        self.pet.perform('sunbeam')
        beam = self.pet.scene.sunbeam
        window = self.pet.scene_view.windows['sunbeam']
        previous = beam.x
        center = QPoint(window.width() // 2, window.height() // 2)
        QTest.mousePress(window, Qt.MouseButton.LeftButton, pos=center)
        QTest.mouseMove(window, center - QPoint(38, 0), delay=20)
        QTest.mouseRelease(window, Qt.MouseButton.LeftButton, pos=center)
        self.assertLess(beam.x, previous)
        restored = CatWindow(self.state, testing=True)
        restored.timer.stop()
        restored.save_timer.stop()
        try:
            self.assertAlmostEqual(restored.scene.sunbeam.x, beam.x, delta=1)
            self.assertIsNone(restored.scene.activity)
            self.pet.remove_prop('sunbeam')
            self.assertNotIn('sunbeam', CatModel.load(self.state).scene_layout)
        finally:
            restored.close()

    def test_clicking_the_ball_during_rally_sends_a_return(self):
        self.pet.perform('rally')
        ball = self.pet.scene.ball
        ball.x = self.pet.x() + 300 * self.pet.scale
        self.pet.scene.activity.stage = 'wait'
        self.pet.scene_view.sync(True)
        window = self.pet.scene_view.windows['ball']
        point = QPoint(window.width() // 2, window.height() // 2)
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=point)
        self.assertEqual(self.pet.scene.activity.kind, 'rally')
        self.assertEqual(self.pet.scene.activity.stage, 'incoming')
        self.assertLess(ball.velocity, 0)
        self.assertFalse(self.pet.scene.rally.grabbed)
