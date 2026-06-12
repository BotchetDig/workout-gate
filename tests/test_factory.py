"""Proves the exercise 'factory': adding ONE registry entry (+ a ~6-line
counter) flows through config defaults, presets and the wizard with no other
changes."""
import unittest
from collections import namedtuple
from unittest import mock

from workout_gate import detector
from workout_gate.detector import (
    ExerciseCounter, L_ELBOW, L_SHOULDER, L_WRIST, R_ELBOW, R_SHOULDER, R_WRIST,
    default_exercises_config,
)

Lm = namedtuple("Lm", "x y visibility")


class CurlCounter(ExerciseCounter):
    """A brand-new exercise in ~6 lines: elbow angle, no posture guard."""
    SIDES = ((L_SHOULDER, L_ELBOW, L_WRIST), (R_SHOULDER, R_ELBOW, R_WRIST))
    DOWN_ANGLE = 60.0
    UP_ANGLE = 150.0


def _arm(elbow_angle, visibility=0.9):
    import math
    lms = [Lm(0.0, 0.0, 0.0)] * 33
    shoulder = Lm(0.5, 0.3, visibility)
    elbow = Lm(0.5, 0.45, visibility)
    r = 0.15
    theta = math.radians(elbow_angle)
    wrist = Lm(elbow.x + r * math.sin(theta), elbow.y - r * math.cos(theta), visibility)
    lms[L_SHOULDER], lms[L_ELBOW], lms[L_WRIST] = shoulder, elbow, wrist
    return lms


class FactoryTest(unittest.TestCase):
    def test_base_class_counts_a_new_exercise(self):
        c = CurlCounter()
        completed = 0
        for a in [170] * 5 + [40] * 5 + [170] * 5:
            if c.update(_arm(a)):
                completed += 1
        self.assertEqual(completed, 1)
        self.assertEqual(c.count, 1)

    def test_registry_entry_flows_into_config_and_presets(self):
        fake = dict(detector.EXERCISES)
        fake["curls"] = {"label": "CURLS", "counter": CurlCounter,
                         "cue": "...", "default_reps": (6, 12), "default_max": 20}
        with mock.patch.object(detector, "EXERCISES", fake):
            # config defaults include the new exercise, no edits elsewhere
            cfg = default_exercises_config()
            self.assertIn("curls", cfg)
            self.assertEqual((cfg["curls"]["reps_min"], cfg["curls"]["reps_max"]), (6, 12))
            # presets size it from its own default range
            from workout_gate.trigger import apply_preset
            config = {"exercises": {"curls": {"enabled": True, "reps_min": 6, "reps_max": 12}}}
            apply_preset(config, "hardcore")
            self.assertGreater(config["exercises"]["curls"]["reps_min"], 6)


if __name__ == "__main__":
    unittest.main()
