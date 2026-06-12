import copy
import unittest

from workout_gate.store import DEFAULT_CONFIG
from workout_gate.tui import _adjust, _cycle, _sparkline


def cfg(**kw):
    return {**copy.deepcopy(DEFAULT_CONFIG), **kw}


class TestAdjust(unittest.TestCase):
    def test_toggle_enabled_keeps_preset(self):
        config = cfg(enabled=True, preset="chill")
        _adjust(config, "enabled", 1)
        self.assertFalse(config["enabled"])
        self.assertEqual(config["preset"], "chill")

    def test_preset_cycle_applies_values(self):
        config = cfg()
        _adjust(config, "preset", 1)  # None -> chill
        self.assertEqual(config["preset"], "chill")
        self.assertEqual(config["every_n_prompts"], 25)

    def test_manual_change_clears_preset(self):
        config = cfg(preset="demo")
        _adjust(config, "every_n_prompts", 1)
        self.assertIsNone(config["preset"])

    def test_freq_clamped_at_one(self):
        config = cfg(every_n_prompts=1)
        _adjust(config, "every_n_prompts", -1)
        self.assertEqual(config["every_n_prompts"], 1)

    def test_reps_min_cannot_exceed_max(self):
        config = cfg()
        config["exercises"]["pushups"].update(reps_min=10, reps_max=10)
        _adjust(config, "repsmin:pushups", 1)
        self.assertEqual(config["exercises"]["pushups"]["reps_min"], 10)

    def test_reps_max_cannot_go_below_min(self):
        config = cfg()
        config["exercises"]["pushups"].update(reps_min=5, reps_max=5)
        _adjust(config, "repsmax:pushups", -1)
        self.assertEqual(config["exercises"]["pushups"]["reps_max"], 5)

    def test_toggle_exercise(self):
        config = cfg()
        config["exercises"]["squats"]["enabled"] = True
        _adjust(config, "enable:squats", 1)
        self.assertFalse(config["exercises"]["squats"]["enabled"])

    def test_exercise_mode_cycles(self):
        config = cfg(exercise_mode="choice")
        _adjust(config, "exercise_mode", 1)
        self.assertEqual(config["exercise_mode"], "random")

    def test_debug_toggles(self):
        config = cfg(debug=False)
        _adjust(config, "debug", 1)
        self.assertTrue(config["debug"])
        _adjust(config, "debug", 1)
        self.assertFalse(config["debug"])

    def test_trigger_cycles_both_ways(self):
        config = cfg(trigger="prompts")
        _adjust(config, "trigger", -1)
        self.assertEqual(config["trigger"], "roulette")
        _adjust(config, "trigger", 1)
        self.assertEqual(config["trigger"], "prompts")

    def test_cycle_wraps(self):
        self.assertEqual(_cycle(["a", "b"], "b", 1), "a")


class TestSparkline(unittest.TestCase):
    def test_empty_days_flat(self):
        self.assertEqual(_sparkline([("d", 0)] * 7), "▁" * 7)

    def test_peak_is_full_block(self):
        line = _sparkline([("a", 0), ("b", 5), ("c", 10)])
        self.assertEqual(line[-1], "█")
        self.assertEqual(line[0], "▁")


if __name__ == "__main__":
    unittest.main()
