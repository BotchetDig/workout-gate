import os
import tempfile
import unittest

from workout_gate import store
from workout_gate.stats_view import _bar, _view_data, _views


class PerExerciseDataTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["WORKOUT_GATE_DIR"] = self.tmp.name

    def tearDown(self):
        del os.environ["WORKOUT_GATE_DIR"]
        self.tmp.cleanup()

    def test_record_rep_tracks_per_exercise_per_day(self):
        store.record_rep("pushups")
        store.record_rep("pushups")
        store.record_rep("squats")
        stats = store.load_stats()
        today = store.today()
        self.assertEqual(stats["by_day_ex"][today], {"pushups": 2, "squats": 1})
        self.assertEqual(stats["by_day"][today], 3)

    def test_day_counts_per_exercise(self):
        store.record_rep("squats")
        stats = store.load_stats()
        self.assertEqual(store.day_counts(stats, "squats").get(store.today()), 1)
        self.assertEqual(store.day_counts(stats, "pushups").get(store.today(), 0), 0)
        self.assertEqual(store.day_counts(stats).get(store.today()), 1)  # combined


class ViewDataTest(unittest.TestCase):
    def test_views_include_all_and_exercises(self):
        v = _views()
        self.assertEqual(v[0], "all")
        self.assertIn("pushups", v)
        self.assertIn("squats", v)

    def test_view_data_all_vs_exercise(self):
        stats = {"total_reps": 5, "by_exercise": {"pushups": 3, "squats": 2},
                 "by_day": {"2026-06-12": 5},
                 "by_day_ex": {"2026-06-12": {"pushups": 3, "squats": 2}}}
        title, total, days = _view_data(stats, "all")
        self.assertEqual((title, total), ("ALL", 5))
        title, total, days = _view_data(stats, "squats")
        self.assertEqual((title, total), ("SQUATS", 2))
        self.assertEqual(days["2026-06-12"], 2)

    def test_bar(self):
        self.assertEqual(_bar(5, 5, 10), "█" * 10)
        self.assertEqual(_bar(0, 5, 10), "░" * 10)


if __name__ == "__main__":
    unittest.main()
