import math
import unittest
from collections import namedtuple

from workout_gate.detector import (
    EXERCISES, L_ANKLE, L_ELBOW, L_HIP, L_KNEE, L_SHOULDER, L_WRIST,
    PushupCounter, RepCounter, SquatCounter, angle_at, make_counter,
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


def make_squat_landmarks(knee_angle, upright=True, visibility=0.9):
    """Synthetic landmarks for a leg at a given knee angle. Hip and ankle are
    fixed with a large vertical span (upright); the knee slides forward to
    realize the angle."""
    lms = [Lm(0.0, 0.0, 0.0)] * 33
    if upright:
        hip, ankle = Lm(0.5, 0.3, visibility), Lm(0.5, 0.7, visibility)
        if knee_angle >= 179.9:
            d = 0.0
        else:
            c = math.cos(math.radians(knee_angle))
            d = math.sqrt(0.04 * (1 + c) / (1 - c))
        knee = Lm(0.5 + d, 0.5, visibility)
    else:  # lying down (pushup pose): no vertical leg span -> guard fails
        hip, knee, ankle = (Lm(0.4, 0.5, visibility), Lm(0.5, 0.5, visibility),
                            Lm(0.6, 0.5, visibility))
    lms[L_HIP], lms[L_KNEE], lms[L_ANKLE] = hip, knee, ankle
    return lms


class TestSquatCounter(unittest.TestCase):
    def test_full_rep_upright(self):
        c = SquatCounter()
        seq = [175] * 5 + [70] * 5 + [175] * 5
        completed = sum(1 for a in seq if c.update(make_squat_landmarks(a)))
        self.assertEqual(completed, 1)
        self.assertEqual(c.count, 1)
        self.assertTrue(c.posture_ok)

    def test_shallow_bend_not_counted(self):
        c = SquatCounter()
        for a in [175] * 5 + [140] * 5 + [175] * 5:  # 140 never reaches the 100 bottom
            c.update(make_squat_landmarks(a))
        self.assertEqual(c.count, 0)

    def test_lying_down_never_counts(self):
        # ankle level with knee (horizontal body) -> feet-below-knees guard fails
        c = SquatCounter()
        for a in [175] * 5 + [70] * 5 + [175] * 5:
            c.update(make_squat_landmarks(a, upright=False))
        self.assertEqual(c.count, 0)
        self.assertFalse(c.posture_ok)

    def test_low_visibility_ignored(self):
        c = SquatCounter()
        for a in [175] * 5 + [70] * 5 + [175] * 5:
            c.update(make_squat_landmarks(a, visibility=0.2))
        self.assertEqual(c.count, 0)
        self.assertFalse(c.body_visible)

    def test_deep_squat_keeps_posture_ok(self):
        """At the bottom of a deep squat the hip drops near the ankle; the
        guard must still pass (regression: the old hip->ankle span rejected
        it, dropping the deepest frames and missing reps)."""
        c = SquatCounter()
        # hip low (near ankle), but ankle still well below knee -> valid squat
        lms = [Lm(0.0, 0.0, 0.0)] * 33
        lms[L_HIP] = Lm(0.45, 0.62, 0.9)    # hip dropped low
        lms[L_KNEE] = Lm(0.60, 0.55, 0.9)   # knee forward & a bit higher
        lms[L_ANKLE] = Lm(0.50, 0.80, 0.9)  # ankle planted, below knee
        c.update(lms)
        self.assertTrue(c.posture_ok)


class TestRegistry(unittest.TestCase):
    def test_known_exercises(self):
        self.assertIn("pushups", EXERCISES)
        self.assertIn("squats", EXERCISES)

    def test_make_counter(self):
        self.assertIsInstance(make_counter("pushups"), PushupCounter)
        self.assertIsInstance(make_counter("squats"), SquatCounter)
        self.assertIsInstance(make_counter("unknown"), PushupCounter)  # safe fallback


if __name__ == "__main__":
    unittest.main()
