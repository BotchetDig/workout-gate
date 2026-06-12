"""Debt/offers/choice state machine, with run_challenge stubbed (no webcam)."""
import os
import tempfile
import unittest
from unittest import mock

from workout_gate import challenge, store


class ChallengeFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["WORKOUT_GATE_DIR"] = self.tmp.name

    def tearDown(self):
        del os.environ["WORKOUT_GATE_DIR"]
        self.tmp.cleanup()

    def _config(self, **kw):
        config = store.load_config()
        config.update(kw)
        store.save_config(config)

    def test_new_debt_choice_offers_all_enabled(self):
        self._config(exercise_mode="choice")
        offers = challenge.new_debt()
        names = {o["exercise"] for o in offers}
        self.assertEqual(names, {"pushups", "squats"})
        self.assertEqual(store.load_state()["debt_offers"], offers)

    def test_new_debt_random_picks_one(self):
        self._config(exercise_mode="random")
        offers = challenge.new_debt()
        self.assertEqual(len(offers), 1)

    def test_disabled_exercise_excluded(self):
        config = store.load_config()
        config["exercises"]["squats"]["enabled"] = False
        config["exercise_mode"] = "choice"
        store.save_config(config)
        offers = challenge.new_debt()
        self.assertEqual([o["exercise"] for o in offers], ["pushups"])

    def test_reps_within_configured_range(self):
        config = store.load_config()
        config["exercises"]["pushups"].update(reps_min=7, reps_max=7)
        store.save_config(config)
        for o in challenge.new_debt():
            if o["exercise"] == "pushups":
                self.assertEqual(o["reps"], 7)

    def test_pending_summary(self):
        self.assertEqual(
            challenge.pending_summary({"debt_reps": 0, "debt_offers": [
                {"exercise": "pushups", "reps": 6}, {"exercise": "squats", "reps": 9}]}),
            "6 pushups or 9 squats")
        self.assertEqual(
            challenge.pending_summary({"debt_reps": 4, "debt_exercise": "squats"}),
            "4 squats")

    def test_settle_completes_clears_everything(self):
        challenge.new_debt()

        def fake_run(offers, chosen=None, on_choice=None, on_rep=None):
            pick = chosen or offers[0]
            if on_choice and chosen is None:
                on_choice(pick["exercise"], pick["reps"])
            for _ in range(pick["reps"]):
                on_rep(pick["exercise"])
            return True

        with mock.patch.object(challenge, "run_challenge", fake_run):
            self.assertTrue(challenge.settle_debt())
        st = store.load_state()
        self.assertEqual(st["debt_reps"], 0)
        self.assertEqual(st["debt_offers"], [])
        self.assertEqual(st["prompt_count"], 0)

    def test_abort_mid_exercise_locks_remaining_debt(self):
        self._config(exercise_mode="choice")
        challenge.new_debt()

        def fake_abort(offers, chosen=None, on_choice=None, on_rep=None):
            pick = chosen or offers[0]
            on_choice(pick["exercise"], pick["reps"])   # user picked
            on_rep(pick["exercise"])                     # did 1 rep
            return False                                  # then quit

        with mock.patch.object(challenge, "run_challenge", fake_abort):
            self.assertFalse(challenge.settle_debt())
        st = store.load_state()
        # locked to the chosen exercise, remaining reps owed, offers cleared
        self.assertEqual(st["debt_offers"], [])
        self.assertEqual(st["debt_reps"], st["debt_reps"])  # >0, locked
        self.assertGreater(st["debt_reps"], 0)
        self.assertIn(st["debt_exercise"], ("pushups", "squats"))

    def test_abort_before_choice_keeps_offers(self):
        self._config(exercise_mode="choice")
        challenge.new_debt()

        def fake_abort_choice(offers, chosen=None, on_choice=None, on_rep=None):
            return False  # closed during the choice screen, never picked

        with mock.patch.object(challenge, "run_challenge", fake_abort_choice):
            self.assertFalse(challenge.settle_debt())
        st = store.load_state()
        self.assertEqual(len(st["debt_offers"]), 2)  # same menu next time
        self.assertEqual(st["debt_reps"], 0)

    def test_resume_locked_debt_skips_choice(self):
        st = store.load_state()
        st["debt_reps"] = 3
        st["debt_exercise"] = "squats"
        st["debt_offers"] = []
        store.save_state(st)
        seen = {}

        def fake_run(offers, chosen=None, on_choice=None, on_rep=None):
            seen["chosen"] = chosen
            seen["offers"] = offers
            for _ in range(chosen["reps"]):
                on_rep(chosen["exercise"])
            return True

        with mock.patch.object(challenge, "run_challenge", fake_run):
            challenge.settle_debt()
        self.assertEqual(seen["chosen"], {"exercise": "squats", "reps": 3})

    def test_stats_credited_per_exercise(self):
        st = store.load_state()
        st["debt_reps"] = 2
        st["debt_exercise"] = "squats"
        store.save_state(st)

        def fake_run(offers, chosen=None, on_choice=None, on_rep=None):
            for _ in range(chosen["reps"]):
                on_rep(chosen["exercise"])
            return True

        with mock.patch.object(challenge, "run_challenge", fake_run):
            challenge.settle_debt()
        self.assertEqual(store.load_stats()["by_exercise"].get("squats"), 2)


if __name__ == "__main__":
    unittest.main()
