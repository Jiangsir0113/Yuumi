from pathlib import Path
import json
import random
import tempfile
import unittest

from cat_model import CatModel
from scene_model import CAT_GROUND, CAT_WIDTH, SceneController


LIMITS = (100, 24, 1300, 760)
ORIGIN = (470, 425)


class CompanionshipTests(unittest.TestCase):
    def setUp(self):
        self.model = CatModel(rng=random.Random(1))
        self.scene = SceneController()

    def begin(self, kind):
        self.assertTrue(self.scene.begin(kind, self.model, *ORIGIN, 1., LIMITS))

    def tick(self, dt=1/60, position=ORIGIN, autonomy=False):
        self.scene.update(dt, self.model, *position, 1., True, 0., limits=LIMITS,
                          allow_autonomy=autonomy)

    def test_sunbeam_approach_rest_and_player_interrupt(self):
        self.begin('sunbeam')
        beam = self.scene.sunbeam
        arrival = self.scene.destination
        self.assertEqual(arrival, (beam.x + (beam.width - CAT_WIDTH) / 2,
                                  beam.floor - CAT_GROUND))
        self.assertEqual(self.model.action, 'walk')
        self.tick(position=arrival)
        self.assertEqual(self.scene.activity.stage, 'rest')
        self.assertEqual(self.model.action, 'loaf')

        self.scene.cancel()
        self.model.request('head')
        self.tick(position=arrival, autonomy=True)
        self.assertEqual(self.model.action, 'head')
        self.assertIs(self.scene.sunbeam, beam)
        self.assertIsNone(self.scene.activity)

    def test_moved_sunbeam_waits_for_drag_to_settle(self):
        self.begin('sunbeam')
        arrival = self.scene.destination
        self.tick(position=arrival)
        self.scene.sunbeam.x += 80
        self.tick(.25, arrival)
        self.scene.sunbeam.x += 20
        self.tick(.25, arrival)
        self.tick(.25, arrival)
        self.assertEqual(self.scene.activity.stage, 'rest')
        self.tick(.2, arrival)
        self.assertEqual(self.scene.activity.stage, 'approach')
        self.assertEqual(self.model.action, 'walk')
        self.assertEqual(self.scene.destination[0], arrival[0] + 100)

    def test_sleepy_cat_stays_loafed_when_light_moves(self):
        self.begin('sunbeam')
        arrival = self.scene.destination
        self.tick(position=arrival)
        self.model.energy = 30.
        self.scene.sunbeam.x += 80
        for _ in range(3):
            self.tick(.25, arrival)
        self.assertIsNone(self.scene.activity)
        self.assertEqual(self.model.action, 'loaf')

    def test_thirst_starts_a_real_drink_from_an_existing_fountain(self):
        self.begin('water')
        fountain = self.scene.fountain
        self.scene.cancel(self.model)
        self.scene.next_autonomy_at = 0.
        self.scene.message = '不打扰'
        self.model.thirst = 40.
        self.tick(autonomy=True)
        self.assertTrue(self.scene.activity.autonomous)
        self.assertEqual(self.scene.activity.kind, 'water')
        self.assertEqual(self.scene.message, '不打扰')
        self.assertIs(self.scene.fountain, fountain)
        arrival = self.scene.destination
        for _ in range(20):
            self.tick(.25, arrival)
            self.model.tick(.25)
        self.assertGreater(self.model.thirst, 40.)
        self.assertLess(fountain.amount, 1.)

    def test_autonomy_uses_existing_scratcher_and_respects_cooldown(self):
        self.begin('scratch')
        scratcher = self.scene.scratcher
        self.scene.cancel(self.model)
        self.scene.clock = 20.
        self.tick(autonomy=True)
        self.assertIs(self.scene.scratcher, scratcher)
        self.assertEqual(self.scene.activity.kind, 'scratch')
        self.assertTrue(self.scene.activity.autonomous)
        self.scene.cancel(self.model)
        self.tick(autonomy=True)
        self.assertIsNone(self.scene.activity)

    def test_autonomy_respects_settings_user_input_and_existing_device_supply(self):
        self.begin('water')
        self.scene.cancel(self.model)
        self.scene.clock = 20.
        self.model.thirst = 35.
        for setting, value in (('roam', False), ('autonomy', False), ('quiet', True)):
            with self.subTest(setting=setting):
                previous = self.model.settings[setting]
                self.model.settings[setting] = value
                self.tick(autonomy=True)
                self.assertIsNone(self.scene.activity)
                self.model.settings[setting] = previous
        self.tick(autonomy=False)
        self.assertIsNone(self.scene.activity)
        self.model.start('head')
        self.tick(autonomy=True)
        self.assertIsNone(self.scene.activity)
        self.model.start('idle')
        self.scene.fountain.amount = 0.
        self.tick(autonomy=True)
        self.assertIsNone(self.scene.activity)

    def test_layout_round_trip_and_reprojection_across_displays(self):
        for action in ('food', 'water', 'snack', 'ball', 'scratch', 'sunbeam'):
            self.begin(action)
        self.scene.feeder.stock = 3
        self.scene.fountain.amount = .28
        self.scene.ball.velocity = 200.
        self.model.scene_layout = self.scene.snapshot_layout(1., LIMITS)
        self.model.settings.update(autonomy=False)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'state.json'
            self.model.save(path)
            restored = CatModel.load(path)
        self.assertFalse(restored.settings['autonomy'])
        copy = SceneController()
        copy.restore_layout(restored.scene_layout, 1., LIMITS)
        self.assertIsNone(copy.activity)
        self.assertEqual(copy.ball.velocity, 0.)
        self.assertEqual(copy.feeder.stock, 3)
        self.assertEqual(copy.fountain.amount, .28)
        for name in restored.scene_layout:
            prop = getattr(copy, name)
            original = getattr(self.scene, name)
            self.assertAlmostEqual(prop.x, original.x)
            self.assertAlmostEqual(prop.floor, original.floor)
        target = (-1700, 44, -720, 710)
        copy.restore_layout(restored.scene_layout, .8, target)
        for name, placed in copy.snapshot_layout(.8, target).items():
            self.assertAlmostEqual(placed['x'], restored.scene_layout[name]['x'])
            self.assertAlmostEqual(placed['y'], restored.scene_layout[name]['y'])

    def test_legacy_and_bad_layout_do_not_lose_valid_props(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'state.json'
            path.write_text(json.dumps({'version': 2, 'settings': {'roam': False}}),
                            encoding='utf-8')
            restored = CatModel.load(path)
        self.assertEqual(restored.scene_layout, {})
        self.assertFalse(restored.settings['roam'])
        self.scene.restore_layout({'sunbeam': {'x': .5, 'y': .5},
                                   'ball': {'x': float('nan'), 'y': True},
                                   'snack': [0, 1]}, 1., LIMITS)
        self.assertIsNotNone(self.scene.sunbeam)
        self.assertIsNone(self.scene.ball)
        self.assertIsNone(self.scene.snack)

    def test_remove_prop_cancels_only_activity_using_that_prop(self):
        self.begin('ball')
        self.begin('sunbeam')
        self.assertTrue(self.scene.remove_prop('ball', self.model))
        self.assertEqual(self.scene.activity.kind, 'sunbeam')
        self.assertTrue(self.scene.remove_prop('sunbeam', self.model))
        self.assertIsNone(self.scene.sunbeam)
        self.assertIsNone(self.scene.activity)
        self.assertIsNone(self.scene.destination)
        self.assertEqual(self.model.action, 'idle')


if __name__ == '__main__':
    unittest.main()
