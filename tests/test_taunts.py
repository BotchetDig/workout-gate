import unittest

from workout_gate import taunts


class TauntTest(unittest.TestCase):
    def test_grind_covers_whole_set_without_error(self):
        for target in (1, 2, 5, 8, 13):
            lines = [taunts.grind_line(d, target) for d in range(target + 1)]
            self.assertTrue(all(isinstance(s, str) and s for s in lines))

    def test_zero_done_is_a_waiting_line(self):
        self.assertIn(taunts.grind_line(0, 8), taunts.WAITING)

    def test_last_rep_is_an_almost_line(self):
        # done == target - 1 (and target > 1) means one to go
        self.assertIn(taunts.grind_line(7, 8), taunts.ALMOST)

    def test_single_rep_set_has_no_almost_phase(self):
        # target 1: done 0 waits, done 1+ never hits the almost branch
        self.assertIn(taunts.grind_line(0, 1), taunts.WAITING)

    def test_selection_is_stable_for_a_given_seed(self):
        for pick in (taunts.announce_line, taunts.validated_line, taunts.cant_see_line):
            self.assertEqual(pick(8), pick(8))


if __name__ == "__main__":
    unittest.main()
