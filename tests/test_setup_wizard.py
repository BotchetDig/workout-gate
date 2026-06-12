import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from workout_gate.setup_wizard import derive_reps_range, run


class TestWizardFlow(unittest.TestCase):
    """Full run with scripted answers: max=12, time trigger every 45 min,
    no global install, no camera test."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["WORKOUT_GATE_DIR"] = self.tmp.name

    def tearDown(self):
        del os.environ["WORKOUT_GATE_DIR"]
        self.tmp.cleanup()

    def _run_with(self, answers):
        out = io.StringIO()
        with mock.patch("sys.stdin.isatty", return_value=True), \
             mock.patch("builtins.input", side_effect=answers), \
             redirect_stdout(out):
            run()
        return out.getvalue()

    def test_full_flow_saves_config(self):
        # pushups max 12, skip squats (0) -> only pushups, no pick question;
        # time trigger 45 min; no global; no camera test.
        from workout_gate import store
        self._run_with(["12", "0", "2", "45", "n", "n"])
        config = store.load_config()
        pu = config["exercises"]["pushups"]
        self.assertEqual((pu["reps_min"], pu["reps_max"]), (3, 6))
        self.assertTrue(pu["enabled"])
        self.assertFalse(config["exercises"]["squats"]["enabled"])
        self.assertEqual(config["trigger"], "time")
        self.assertEqual(config["time_interval_min"], 45)

    def test_both_exercises_and_pick_mode(self):
        # pushups 12, squats 20 -> both on -> pick question (2=random);
        # prompts trigger default; no global; no camera.
        from workout_gate import store
        self._run_with(["12", "20", "2", "1", "", "n", "n"])
        config = store.load_config()
        self.assertTrue(config["exercises"]["pushups"]["enabled"])
        self.assertTrue(config["exercises"]["squats"]["enabled"])
        self.assertEqual(config["exercise_mode"], "random")

    def test_defaults_accepted_with_enter(self):
        from workout_gate import store
        # pushups, squats, pick, trigger, freq, global, camera
        self._run_with(["", "", "", "", "", "n", "n"])
        config = store.load_config()
        pu = config["exercises"]["pushups"]
        self.assertEqual((pu["reps_min"], pu["reps_max"]), (5, 10))
        self.assertEqual(config["trigger"], "prompts")
        self.assertEqual(config["every_n_prompts"], 15)

    def test_ctrl_c_aborts_cleanly(self):
        output = self._run_with(["12", KeyboardInterrupt()])
        self.assertIn("aborted", output)

    def test_invalid_input_reprompts(self):
        from workout_gate import store
        self._run_with(["abc", "999", "12", "0", "1", "", "n", "n"])
        self.assertEqual(store.load_config()["exercises"]["pushups"]["reps_min"], 3)


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
        self.assertEqual(lo, 49)  # 25% of 200 clamped just under the cap

    def test_range_always_valid(self):
        for mx in range(1, 201):
            lo, hi = derive_reps_range(mx)
            self.assertTrue(2 <= lo <= hi <= 50, f"max={mx} gave {lo}-{hi}")


if __name__ == "__main__":
    unittest.main()
