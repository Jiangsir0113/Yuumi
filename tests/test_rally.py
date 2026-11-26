import math
import unittest

from cat_model import CatModel
from scene_model import Ball, SceneController


LIMITS = (0.0, 0.0, 900.0, 600.0)
STEP = 1 / 64


class RallyTests(unittest.TestCase):
    def setUp(self):
        self.scene = SceneController()
        self.cat = CatModel()
        self.cat.settings.update(autonomy=False, roam=False)
        self.x = 100.0
        self.y = 200.0
        self.scale = 1.0

    def start(self):
        self.assertTrue(self.scene.begin('rally', self.cat, self.x, self.y, self.scale, LIMITS))

    def step(self, *, ready=True, phase=None):
        elapsed = self.cat.elapsed if phase is None else phase
        self.scene.update(STEP, self.cat, self.x, self.y, self.scale, ready, elapsed)
        destination = self.scene.destination
        if destination and self.cat.action in {'walk', 'trot'}:
            distance = math.dist((self.x, self.y), destination)
            speed = 95 if self.cat.action == 'trot' else 44
            portion = min(1.0, speed * self.scale * STEP / max(1e-6, distance))
            self.x += (destination[0] - self.x) * portion
            self.y += (destination[1] - self.y) * portion
        self.cat.tick(STEP, executing=ready)

    def run_until(self, condition, seconds=15):
        for _ in range(round(seconds / STEP)):
            if condition():
                return
            self.step()
        activity = self.scene.activity
        self.fail(f'Rally did not reach expected state, now {activity and activity.stage}')

    def push(self, velocity=None):
        return self.scene.rally.push(self.scene, self.cat, self.x, self.y, self.scale, velocity)

    def test_serve_waits_for_arrival_and_action_contact_frame(self):
        self.start()
        for _ in range(30):
            self.step(phase=0.75)
        self.assertEqual(self.scene.activity.strikes, 0)
        self.assertEqual(self.scene.ball.velocity, 0)
        self.assertEqual(self.scene.activity.stage, 'approach')

        self.run_until(lambda: self.scene.activity.stage == 'serve')
        self.step(ready=False, phase=0.75)
        self.step(phase=0.25)
        self.assertEqual(self.scene.activity.strikes, 0)

        self.step(phase=0.75)
        self.assertEqual(self.scene.activity.stage, 'retreat')
        self.assertEqual(self.scene.activity.strikes, 1)
        self.assertGreater(abs(self.scene.ball.velocity), 60)

    def test_click_returns_ball_and_cat_serves_again(self):
        self.start()
        self.run_until(lambda: self.scene.activity.stage == 'wait')
        ball_x = self.scene.ball.x
        self.assertTrue(self.push())
        self.assertEqual(self.scene.activity.stage, 'incoming')
        self.assertEqual(self.scene.ball.x, ball_x)
        self.assertFalse(self.push())

        self.run_until(lambda: self.scene.activity.stage == 'approach')
        self.assertGreaterEqual(abs(self.scene.ball.x - ball_x), 6 * self.scale)
        self.run_until(lambda: self.scene.activity.strikes == 2)

    def test_flick_follows_horizontal_direction(self):
        self.start()
        self.run_until(lambda: self.scene.activity.stage == 'wait')
        ball_x = self.scene.ball.x
        self.assertTrue(self.push(velocity=150))
        self.assertGreater(self.scene.ball.velocity, 0)
        self.step()
        self.assertGreater(self.scene.ball.x, ball_x)

    def test_ball_at_screen_edge_asks_for_help_and_recovers(self):
        self.scene.ball = Ball(LIMITS[2] + 308, self.y + 286)
        self.start()
        self.assertEqual(self.scene.activity.stage, 'wait')
        self.assertTrue(self.push(velocity=250))  # Outward flick gets safely redirected.
        self.assertLess(self.scene.ball.velocity, 0)
        self.run_until(lambda: self.scene.activity.strikes == 1)
        self.assertLess(self.scene.ball.x, LIMITS[2] + 270)

    def test_holding_ball_pauses_play_and_cancellation_keeps_old_ball_mode(self):
        self.start()
        ball = self.scene.ball
        self.scene.rally.grabbed = True
        self.step()
        self.assertIsNone(self.scene.destination)
        self.assertEqual(self.cat.action, 'look')
        self.assertTrue(self.scene.begin('ball', self.cat, self.x, self.y, self.scale, LIMITS))
        self.assertFalse(self.scene.rally.grabbed)
        self.assertEqual(self.scene.activity.kind, 'ball')
        self.assertIs(self.scene.ball, ball)
        self.assertFalse(self.push())

    def test_waiting_times_out_without_discarding_ball(self):
        self.start()
        self.run_until(lambda: self.scene.activity.stage == 'wait')
        self.scene.activity.stage_time = 25.1
        self.step()
        self.assertIsNone(self.scene.activity)
        self.assertIsNotNone(self.scene.ball)
        self.assertFalse(self.push())
