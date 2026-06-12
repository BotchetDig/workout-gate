import math
import unittest
from collections import namedtuple

from workout_gate.detector import (
    L_ELBOW, L_HIP, L_SHOULDER, L_WRIST, PushupCounter, RepCounter, angle_at,
)

Lm = namedtuple("Lm", "x y visibility")


def feed(counter, angles):
    return sum(1 for a in angles for _ in range(3) if counter.update(a))


def hold(angle, frames=5):
    return [angle] * frames


class TestRepCounter(unittest.TestCase):
    def test_one_full_rep(self):
        c = RepCounter()
        for a in hold(170) + hold(80) + hold(170):
            c.update(a)
        self.assertEqual(c.count, 1)

    def test_three_reps(self):
        c = RepCounter()
        seq = []
        for _ in range(3):
            seq += hold(165) + hold(70)
        seq += hold(165)
        for a in seq:
            c.update(a)
        self.assertEqual(c.count, 3)

    def test_half_rep_not_counted(self):
        """Going down to 120° (not a real bottom) then back up counts nothing."""
        c = RepCounter()
        for a in hold(170) + hold(120) + hold(170):
            c.update(a)
        self.assertEqual(c.count, 0)

    def test_jitter_around_threshold_not_counted(self):
        """Single-frame noise spikes must not produce reps (smoothing)."""
        c = RepCounter()
        seq = hold(170, 10)
        seq[4] = 80  # one noisy frame
        for a in seq:
            c.update(a)
        self.assertEqual(c.count, 0)

    def test_staying_down_counts_once_on_rise(self):
        c = RepCounter()
        for a in hold(170) + hold(70, 30) + hold(170):
            c.update(a)
        self.assertEqual(c.count, 1)


class TestAngle(unittest.TestCase):
    def test_straight_arm(self):
        self.assertAlmostEqual(angle_at((0, 0), (1, 0), (2, 0)), 180.0, places=3)

    def test_right_angle(self):
        self.assertAlmostEqual(angle_at((0, 0), (1, 0), (1, 1)), 90.0, places=3)


def make_landmarks(elbow_angle, horizontal=True, visibility=0.9):
    """Synthetic profile-view landmarks with the left arm at a given elbow angle."""
    lms = [Lm(0.0, 0.0, 0.0)] * 33
    if horizontal:
        shoulder, hip = Lm(0.4, 0.6, visibility), Lm(0.7, 0.62, visibility)
    else:  # standing
        shoulder, hip = Lm(0.5, 0.3, visibility), Lm(0.5, 0.6, visibility)
    r = 0.15
    elbow = Lm(shoulder.x, shoulder.y + r, visibility)
    # rotate the elbow->shoulder vector (0, -r) by elbow_angle to place the wrist
    theta = math.radians(elbow_angle)
    wrist = Lm(elbow.x + r * math.sin(theta), elbow.y - r * math.cos(theta), visibility)
    lms[L_SHOULDER], lms[L_ELBOW], lms[L_WRIST], lms[L_HIP] = shoulder, elbow, wrist, hip
    return lms


class TestPushupCounter(unittest.TestCase):
    def test_full_rep_horizontal(self):
        c = PushupCounter()
        seq = [170] * 5 + [70] * 5 + [170] * 5
        completed = sum(1 for a in seq if c.update(make_landmarks(a)))
        self.assertEqual(completed, 1)
        self.assertEqual(c.count, 1)
        self.assertTrue(c.posture_ok)

    def test_standing_person_never_counts(self):
        c = PushupCounter()
        seq = [170] * 5 + [70] * 5 + [170] * 5
        for a in seq:
            c.update(make_landmarks(a, horizontal=False))
        self.assertEqual(c.count, 0)
        self.assertFalse(c.posture_ok)

    def test_low_visibility_ignored(self):
        c = PushupCounter()
        for a in [170] * 5 + [70] * 5 + [170] * 5:
            c.update(make_landmarks(a, visibility=0.2))
        self.assertEqual(c.count, 0)
        self.assertFalse(c.body_visible)

    def test_no_landmarks(self):
        c = PushupCounter()
        self.assertFalse(c.update(None))
        self.assertFalse(c.body_visible)


if __name__ == "__main__":
    unittest.main()
