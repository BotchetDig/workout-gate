"""Smoke coverage for the challenge-window renderer: every screen must draw onto
a frame without raising, across the bubble's content branches and both speaker
tags. No pixel assertions — just that the Pillow pipeline stays wired up."""
import os
import unittest

import numpy as np

from workout_gate import ui


class UIRenderTest(unittest.TestCase):
    def _frame(self):
        return np.full((320, 320, 3), 120, np.uint8)

    def test_hud_branches_render_and_modify_the_frame(self):
        f = self._frame()
        before = f.copy()
        ui.draw_hud(f, "pushups", 3, 8, True, True, False)        # grind
        self.assertFalse(np.array_equal(f, before))
        ui.draw_hud(self._frame(), "squats", 0, 9, False, True, False)   # can't-see (RED)
        ui.draw_hud(self._frame(), "pushups", 7, 8, True, False, True)   # posture cue (YELLOW)
        ui.draw_hud(self._frame(), "pushups", 4, 8, True, True, True, angle=92.0, debug=True)

    def test_message_screens_render(self):
        ui.draw_announce(self._frame(), "pushups", 8, 2.0)
        ui.draw_choice(self._frame(), [{"exercise": "pushups", "reps": 6},
                                       {"exercise": "squats", "reps": 9}])
        ui.draw_choice(self._frame(), [{"exercise": "pushups", "reps": 6}])  # single offer
        ui.draw_validated(self._frame(), 1)

    def test_renders_with_codex_speaker_tag(self):
        os.environ["WORKOUT_GATE_SOURCE"] = "codex"
        try:
            ui.draw_hud(self._frame(), "pushups", 2, 8, True, True, False)
            ui.draw_validated(self._frame(), 0)
        finally:
            os.environ.pop("WORKOUT_GATE_SOURCE", None)


if __name__ == "__main__":
    unittest.main()
