import json
from pathlib import Path
import random
import tempfile
import unittest

from cat_model import ACTIONS, CatModel


class ModelTests(unittest.TestCase):
    def cat(self):
        return CatModel(rng=random.Random(42))

    def test_food_has_full_sequence_and_no_duplicate_click_rewards(self):
        cat = self.cat()
        cat.satiety = 30
        self.assertTrue(cat.request("food"))
        self.assertEqual(cat.action, "sniff")
        cat.tick(2)
        self.assertEqual(cat.action, "eat")
        self.assertLess(cat.satiety, 30)
        self.assertFalse(cat.request("food"))
        self.assertEqual(cat.action, "eat")
        cat.tick(7)
        self.assertEqual(cat.action, "lick")
        self.assertGreater(cat.satiety, 64)
        cat.tick(2)
        self.assertEqual(cat.action, "groom")

    def test_sleep_can_be_interrupted_for_food(self):
        cat = self.cat()
        cat.start("sleep")
        cat.request("food")
        self.assertEqual(cat.action, "sniff")
        self.assertEqual(cat.queue, ["eat", "lick", "groom"])

    def test_overstimulation_refuses_and_recovers(self):
        cat = self.cat()
        for _ in range(20):
            cat.touch("head", .7)
            cat.tick(.2, touching=True)
        self.assertEqual(cat.action, "refuse")
        self.assertGreater(cat.cooldown, 0)
        self.assertFalse(cat.touch("head"))
        cat.tick(55)
        self.assertEqual(cat.cooldown, 0)
        self.assertTrue(cat.touch("head"))
        self.assertEqual(cat.action, "head")

    def test_sensitive_paw_and_regular_head_are_distinct(self):
        a, b = self.cat(), self.cat()
        a.touch("paw", .5)
        b.touch("head", .5)
        self.assertGreater(a.touch_load, b.touch_load)
        self.assertEqual(a.action, "paw")
        self.assertEqual(b.action, "head")

    def test_touch_interrupts_eating_and_preserves_partial_nutrition(self):
        cat = self.cat()
        cat.satiety=30
        cat.start("eat")
        cat.tick(2)
        self.assertGreater(cat.satiety,39)
        self.assertTrue(cat.touch("chin"))
        self.assertEqual(cat.action, "chin")
        self.assertEqual(cat.queue,[])
        self.assertLess(cat.satiety,41)

    def test_touch_does_not_require_full_waking_or_previous_sequence(self):
        cat=self.cat()
        cat.request("sleep")
        cat.touch("head")
        self.assertEqual(cat.action,"head")
        self.assertEqual(cat.queue,[])
        cat.touch("chin")
        self.assertEqual(cat.action,"chin")
        cat.tick(20,touching=True)
        self.assertEqual(cat.action,"chin")

    def test_belly_family_removed_everywhere(self):
        cat=self.cat()
        for name in ["roll","belly","side_sleep"]:
            self.assertNotIn(name,ACTIONS)
            with self.assertRaises(ValueError):
                cat.request(name)
        for _ in range(100):
            cat.autonomous()
            self.assertNotIn(cat.action,{"roll","belly","side_sleep"})

    def test_sleep_recovers_energy_and_all_needs_bounded(self):
        cat = self.cat()
        cat.energy = 15
        cat.start("sleep")
        cat.tick(100)
        self.assertGreater(cat.energy, 35)
        for _ in range(100):
            cat.tick(300)
        for k in ["satiety", "thirst", "energy", "happiness", "affinity", "touch_load"]:
            self.assertGreaterEqual(getattr(cat, k), 0)
            self.assertLessEqual(getattr(cat, k), 100)

    def test_no_autonomous_walk_when_roaming_off(self):
        cat = self.cat()
        cat.settings["roam"] = False
        for _ in range(500):
            cat.energy = 80
            cat.autonomous()
            self.assertNotIn(cat.action, {"walk", "trot"})

    def test_new_user_action_clears_previous_queue(self):
        cat = self.cat()
        cat.request("sleep")
        cat.request("toy")
        self.assertEqual(cat.action, "crouch")
        self.assertNotIn("sleep", cat.queue)

    def test_invalid_action_and_time_rejected(self):
        cat = self.cat()
        for val in [-1, float("nan"), float("inf")]:
            with self.assertRaises(ValueError):
                cat.tick(val)
        with self.assertRaises(ValueError):
            cat.request("unknown")
        with self.assertRaises(ValueError):
            cat.sequence(["idle", "unknown"])

    def test_atomic_persistence_and_corrupt_save_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"cat.json"
            cat = self.cat()
            cat.settings["name"] = "团团"
            cat.settings["size"] = .85
            cat.affinity = 62
            cat.save(path)
            restored = CatModel.load(path)
            self.assertEqual(restored.affinity, 62)
            self.assertEqual(restored.settings["name"], "团团")
            self.assertEqual(restored.settings["size"], .85)
            self.assertFalse(path.with_suffix(".tmp").exists())
            path.write_text("{bad json", encoding="utf-8")
            self.assertEqual(CatModel.load(path).settings["name"], "悠米")
            path.write_text(json.dumps({"needs": {"energy": 500, "satiety": -8},
                "settings": {"roam": "false", "size": 99, "screen": -5}}), encoding="utf-8")
            fixed = CatModel.load(path)
            self.assertEqual(fixed.energy, 100)
            self.assertEqual(fixed.satiety, 0)
            self.assertTrue(fixed.settings["roam"])
            self.assertEqual(fixed.settings["size"], 1.5)
            self.assertEqual(fixed.settings["screen"], 0)

    def test_full_cat_does_not_consume_more_food(self):
        cat = self.cat()
        cat.satiety = 99
        self.assertFalse(cat.request("food"))
        self.assertNotIn("eat", cat.queue)

    def test_legacy_cat_name_migrates_to_youmi(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"old.json"
            path.write_text(json.dumps({"settings":{"name":"金团"},"needs":{"affinity":73}}),encoding="utf-8")
            cat=CatModel.load(path)
            self.assertEqual(cat.settings["name"],"悠米")
            self.assertEqual(cat.affinity,73)


if __name__ == "__main__":
    unittest.main()
