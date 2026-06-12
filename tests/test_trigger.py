import copy
import unittest

from workout_gate.store import DEFAULT_CONFIG, DEFAULT_STATE, best_day, last_days, streak_days
from workout_gate.trigger import PRESETS, apply_preset, challenge_due


def cfg(**kw):
    return {**copy.deepcopy(DEFAULT_CONFIG), **kw}


def state(**kw):
    return {**copy.deepcopy(DEFAULT_STATE), **kw}


class TestChallengeDue(unittest.TestCase):
    def test_debt_always_due(self):
        for trig in ("prompts", "time", "roulette"):
            self.assertTrue(challenge_due(cfg(trigger=trig), state(debt_reps=3)))

    def test_prompts_below_threshold(self):
        self.assertFalse(challenge_due(cfg(), state(prompt_count=14)))
        self.assertTrue(challenge_due(cfg(), state(prompt_count=15)))

    def test_time_first_prompt_starts_clock(self):
        s = state()
        self.assertFalse(challenge_due(cfg(trigger="time"), s, now=1000.0))
        self.assertEqual(s["last_challenge_ts"], 1000.0)

    def test_time_due_after_interval(self):
        c = cfg(trigger="time", time_interval_min=30)
        s = state(last_challenge_ts=1000.0)
        self.assertFalse(challenge_due(c, s, now=1000.0 + 29 * 60))
        self.assertTrue(challenge_due(c, s, now=1000.0 + 31 * 60))

    def test_roulette_extremes(self):
        self.assertFalse(challenge_due(cfg(trigger="roulette", roulette_chance_pct=0), state()))
        self.assertTrue(challenge_due(cfg(trigger="roulette", roulette_chance_pct=100), state()))


class TestPresets(unittest.TestCase):
    def test_all_presets_only_touch_known_keys(self):
        for name in PRESETS:
            config = apply_preset(cfg(), name)
            self.assertEqual(config["preset"], name)
            self.assertEqual(set(config) - set(DEFAULT_CONFIG), set())
            for ec in config["exercises"].values():
                self.assertLessEqual(ec["reps_min"], ec["reps_max"])

    def test_demo_triggers_every_prompt(self):
        config = apply_preset(cfg(), "demo")
        self.assertTrue(challenge_due(config, state(prompt_count=1)))


class TestDerivedStats(unittest.TestCase):
    def test_streak_counts_back_from_today(self):
        by_day = {"2026-06-10": 5, "2026-06-11": 3, "2026-06-12": 8}
        self.assertEqual(streak_days(by_day, ref="2026-06-12"), 3)

    def test_streak_not_broken_before_first_rep_of_the_day(self):
        by_day = {"2026-06-10": 5, "2026-06-11": 3}
        self.assertEqual(streak_days(by_day, ref="2026-06-12"), 2)

    def test_streak_gap_resets(self):
        by_day = {"2026-06-08": 5, "2026-06-10": 2, "2026-06-12": 1}
        self.assertEqual(streak_days(by_day, ref="2026-06-12"), 1)

    def test_streak_empty(self):
        self.assertEqual(streak_days({}, ref="2026-06-12"), 0)

    def test_best_day(self):
        self.assertEqual(best_day({"2026-06-10": 5, "2026-06-11": 9}), ("2026-06-11", 9))
        self.assertIsNone(best_day({}))

    def test_last_days(self):
        days = last_days({"2026-06-12": 4}, n=3, ref="2026-06-12")
        self.assertEqual(days, [("2026-06-10", 0), ("2026-06-11", 0), ("2026-06-12", 4)])


if __name__ == "__main__":
    unittest.main()
