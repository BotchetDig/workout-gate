import os
import tempfile
import unittest
from unittest import mock

from workout_gate import setup_wizard, store
from workout_gate.setup_wizard import _apply_max, derive_reps_range, finalize


class TestDeriveRepsRange(unittest.TestCase):
    def test_average_dev(self):
        self.assertEqual(derive_reps_range(20), (5, 10))

    def test_beginner_never_below_two(self):
        lo, hi = derive_reps_range(1)
        self.assertEqual(lo, 2)
        self.assertGreater(hi, lo)

    def test_strong(self):
        self.assertEqual(derive_reps_range(40), (10, 20))

    def test_monster_capped_at_fifty(self):
        lo, hi = derive_reps_range(200)
        self.assertEqual(hi, 50)
        self.assertEqual(lo, 49)

    def test_range_always_valid(self):
        for mx in range(1, 201):
            lo, hi = derive_reps_range(mx)
            self.assertTrue(2 <= lo <= hi <= 50, f"max={mx} gave {lo}-{hi}")


class TestFinalize(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["WORKOUT_GATE_DIR"] = self.tmp.name

    def tearDown(self):
        del os.environ["WORKOUT_GATE_DIR"]
        self.tmp.cleanup()

    def test_apply_max_sets_reps(self):
        config = store.load_config()
        _apply_max(config, "pushups", 12)
        self.assertTrue(config["exercises"]["pushups"]["enabled"])
        self.assertEqual((config["exercises"]["pushups"]["reps_min"],
                          config["exercises"]["pushups"]["reps_max"]), (3, 6))

    def test_apply_max_zero_disables(self):
        config = store.load_config()
        _apply_max(config, "squats", 0)
        self.assertFalse(config["exercises"]["squats"]["enabled"])

    def test_finalize_respects_enabled_map(self):
        config = store.load_config()
        finalize(config, {"pushups": 20, "squats": 30},
                 {"pushups": True, "squats": False})
        self.assertTrue(config["exercises"]["pushups"]["enabled"])
        self.assertFalse(config["exercises"]["squats"]["enabled"])
        self.assertTrue(config["enabled"])
        self.assertIsNone(config["preset"])

    def test_finalize_never_leaves_nothing_enabled(self):
        config = store.load_config()
        finalize(config, {"pushups": 20, "squats": 30},
                 {"pushups": False, "squats": False})
        self.assertTrue(any(c.get("enabled") for c in config["exercises"].values()))

    def test_run_finish_saves_config(self):
        """run() orchestration: a 'finish' from the curses layer persists the
        config (curses + key parsing mocked away)."""
        with mock.patch.object(setup_wizard.curses, "wrapper", return_value="finish"), \
             mock.patch.object(setup_wizard, "_post_finish"), \
             mock.patch("sys.stdin.isatty", return_value=True), \
             mock.patch("sys.stdout.isatty", return_value=True):
            setup_wizard.run()
        self.assertTrue(store.load_config()["enabled"])

    def test_run_cancel_writes_nothing(self):
        with mock.patch.object(setup_wizard.curses, "wrapper", return_value="cancel"), \
             mock.patch("sys.stdin.isatty", return_value=True), \
             mock.patch("sys.stdout.isatty", return_value=True):
            setup_wizard.run()
        self.assertFalse((__import__("pathlib").Path(self.tmp.name) / "config.json").exists())


if __name__ == "__main__":
    unittest.main()
