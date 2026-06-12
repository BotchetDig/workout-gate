import unittest

from workout_gate.cli import _bar, _pretty_date, render_stats, render_statusline


class RenderStatsTest(unittest.TestCase):
    def test_empty_stats_no_crash(self):
        out = render_stats({"total_reps": 0, "by_day": {}, "by_exercise": {}}, color=False)
        self.assertIn("WORKOUT GATE", out)
        self.assertIn("Total", out)

    def test_no_color_has_no_escape_codes(self):
        out = render_stats({"total_reps": 5, "by_day": {"2026-06-12": 5},
                            "by_exercise": {"pushups": 5}}, color=False)
        self.assertNotIn("\033[", out)
        self.assertIn("pushups", out)
        self.assertIn("5", out)

    def test_color_has_escape_codes(self):
        out = render_stats({"total_reps": 5, "by_day": {}, "by_exercise": {}}, color=True)
        self.assertIn("\033[", out)

    def test_bar_scales(self):
        self.assertEqual(_bar(10, 10, 10), "█" * 10)
        self.assertEqual(_bar(0, 10, 10), "░" * 10)
        self.assertEqual(_bar(5, 10, 10).count("█"), 5)
        self.assertEqual(_bar(3, 0, 10), "░" * 10)  # maxv 0 -> empty, no div by zero

    def test_pretty_date(self):
        self.assertEqual(_pretty_date("2026-06-12"), "Jun 12")
        self.assertEqual(_pretty_date("2026-01-05"), "Jan  5")


class StatuslineTest(unittest.TestCase):
    def test_today_and_streak(self):
        out = render_statusline({"total_reps": 36, "by_day": {}}, color=False)
        self.assertIn("🏋", out)

    def test_no_ansi_when_color_off(self):
        self.assertNotIn("\033", render_statusline({"total_reps": 5, "by_day": {}}, color=False))

    def test_ansi_when_color_on(self):
        self.assertIn("\033", render_statusline({"total_reps": 5, "by_day": {}}, color=True))


if __name__ == "__main__":
    unittest.main()
