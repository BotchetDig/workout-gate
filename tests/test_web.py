import os
import tempfile
import unittest


class WebLogicTest(unittest.TestCase):
    """The dashboard's pure logic (build_state / apply_action) — no sockets."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["WORKOUT_GATE_DIR"] = self.tmp.name
        from workout_gate import web, store
        self.web = web
        self.store = store

    def tearDown(self):
        del os.environ["WORKOUT_GATE_DIR"]
        self.tmp.cleanup()

    def test_build_state_shape(self):
        st = self.web.build_state()
        for key in ("enabled", "trigger", "every_n_prompts", "exercises",
                    "stats", "status", "presets"):
            self.assertIn(key, st)
        self.assertIn("pushups", st["exercises"])
        self.assertEqual(len(st["stats"]["last7"]), 7)
        # sparkline has one value per shown day
        self.assertEqual(len(st["exercises"]["pushups"]["spark"]), 7)

    def test_stats_reflect_reps(self):
        self.store.record_rep("pushups")
        self.store.record_rep("squats")
        st = self.web.build_state()
        self.assertEqual(st["stats"]["total"], 2)
        self.assertEqual(st["stats"]["today"], 2)
        self.assertEqual(st["exercises"]["pushups"]["total"], 1)

    def test_toggle_gate(self):
        self.web.apply_action({"action": "set_enabled", "value": False})
        self.assertFalse(self.store.load_config()["enabled"])
        self.web.apply_action({"action": "set_enabled", "value": True})
        self.assertTrue(self.store.load_config()["enabled"])

    def test_freq_sets_trigger_and_clamps(self):
        st = self.web.apply_action({"action": "freq", "value": 7})
        self.assertEqual(st["every_n_prompts"], 7)
        self.assertEqual(st["trigger"], "prompts")
        # clamp out-of-range
        self.assertEqual(self.web.apply_action({"action": "freq", "value": 999})["every_n_prompts"], 99)
        self.assertEqual(self.web.apply_action({"action": "freq", "value": 0})["every_n_prompts"], 1)

    def test_preset_then_manual_clears_preset(self):
        self.assertEqual(self.web.apply_action({"action": "preset", "name": "chill"})["preset"], "chill")
        st = self.web.apply_action({"action": "freq", "value": 10})
        self.assertIsNone(st["preset"])

    def test_reps_clamp_and_order(self):
        st = self.web.apply_action({"action": "reps", "exercise": "pushups", "min": 3, "max": 99})
        self.assertEqual(st["exercises"]["pushups"]["reps_min"], 3)
        self.assertEqual(st["exercises"]["pushups"]["reps_max"], 50)  # capped
        # max never below min
        st = self.web.apply_action({"action": "reps", "exercise": "pushups", "min": 8, "max": 2})
        self.assertGreaterEqual(st["exercises"]["pushups"]["reps_max"],
                                st["exercises"]["pushups"]["reps_min"])

    def test_enable_disable_exercise(self):
        self.web.apply_action({"action": "enable", "exercise": "squats", "value": False})
        self.assertFalse(self.store.load_config()["exercises"]["squats"]["enabled"])

    def test_bad_action_is_safe(self):
        # unknown action must not raise and returns current state
        st = self.web.apply_action({"action": "nope"})
        self.assertIn("enabled", st)


if __name__ == "__main__":
    unittest.main()
