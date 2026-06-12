"""Exercise detection from pose landmarks. No UI, no files, no webcam.

Three layers:
- RepCounter: hysteresis state machine fed joint angles (unit-testable).
- PushupCounter / SquatCounter: extract landmarks from a MediaPipe pose
  result, apply posture guards, feed a RepCounter.
- EXERCISES: registry mapping a name to its counter and on-screen cue, so
  adding an exercise is one entry here and nothing else changes.

Deliberately dumb and solid: a rep is one full down (joint angle < down)
followed by a full up (joint angle > up), with smoothing to ignore jitter.
"""
import math
from collections import deque

# MediaPipe pose landmark indices
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24
L_KNEE, R_KNEE = 25, 26
L_ANKLE, R_ANKLE = 27, 28

DOWN_ANGLE = 95.0   # elbow angle below this = bottom of the pushup
UP_ANGLE = 150.0    # elbow angle above this = arms extended
KNEE_DOWN_ANGLE = 100.0  # knee angle below this = bottom of the squat
KNEE_UP_ANGLE = 160.0    # knee angle above this = standing
MIN_VISIBILITY = 0.5
MAX_TORSO_TILT = 45.0   # degrees from horizontal; lying-ish body required (pushups)
MIN_SHIN_SPAN = 0.05    # normalized vertical knee->ankle span; shin points down
                        # (true standing AND deep-squatting; false when lying = pushup)
SMOOTH_FRAMES = 3


def angle_at(a, b, c) -> float:
    """Angle ABC in degrees, points as (x, y)."""
    v1 = (a[0] - b[0], a[1] - b[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1 = math.hypot(*v1)
    n2 = math.hypot(*v2)
    if n1 == 0 or n2 == 0:
        return 180.0
    cos = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
    return math.degrees(math.acos(cos))


class RepCounter:
    """Counts down→up transitions of the elbow angle with hysteresis."""

    def __init__(self, down_angle: float = DOWN_ANGLE, up_angle: float = UP_ANGLE):
        self.down_angle = down_angle
        self.up_angle = up_angle
        self.count = 0
        self.is_down = False
        self._window = deque(maxlen=SMOOTH_FRAMES)

    def update(self, elbow_angle: float) -> bool:
        """Feed one frame's elbow angle. Returns True if a rep just completed."""
        self._window.append(elbow_angle)
        smoothed = sum(self._window) / len(self._window)
        if not self.is_down and smoothed < self.down_angle:
            self.is_down = True
        elif self.is_down and smoothed > self.up_angle:
            self.is_down = False
            self.count += 1
            return True
        return False

    @property
    def smoothed_angle(self) -> float:
        return sum(self._window) / len(self._window) if self._window else 180.0


class PushupCounter:
    """Feeds MediaPipe pose landmarks into a RepCounter with posture guards."""

    def __init__(self):
        self.reps = RepCounter()
        self.body_visible = False
        self.posture_ok = False
        self.elbow_angle = 180.0

    @property
    def count(self) -> int:
        return self.reps.count

    @property
    def is_down(self) -> bool:
        return self.reps.is_down

    def update(self, landmarks) -> bool:
        """landmarks: sequence of objects with .x, .y, .visibility (MediaPipe
        pose_landmarks.landmark), or None. Returns True on a completed rep."""
        self.body_visible = False
        self.posture_ok = False
        if landmarks is None:
            return False

        # Profile view: use whichever side the camera sees best.
        side = self._best_side(landmarks)
        if side is None:
            return False
        shoulder, elbow, wrist, hip = side
        self.body_visible = True

        # Guard: body roughly horizontal (pushup position), not standing.
        tilt = math.degrees(math.atan2(abs(shoulder.y - hip.y), abs(shoulder.x - hip.x) + 1e-6))
        self.posture_ok = tilt < MAX_TORSO_TILT
        if not self.posture_ok:
            return False

        self.elbow_angle = angle_at(
            (shoulder.x, shoulder.y), (elbow.x, elbow.y), (wrist.x, wrist.y)
        )
        return self.reps.update(self.elbow_angle)

    @staticmethod
    def _best_side(landmarks):
        return _best_side(landmarks,
                          ((L_SHOULDER, L_ELBOW, L_WRIST, L_HIP),
                           (R_SHOULDER, R_ELBOW, R_WRIST, R_HIP)))


class SquatCounter:
    """Counts squats from the knee angle (hip-knee-ankle), body upright."""

    def __init__(self):
        self.reps = RepCounter(down_angle=KNEE_DOWN_ANGLE, up_angle=KNEE_UP_ANGLE)
        self.body_visible = False
        self.posture_ok = False
        self.knee_angle = 180.0

    @property
    def count(self) -> int:
        return self.reps.count

    @property
    def is_down(self) -> bool:
        return self.reps.is_down

    def update(self, landmarks) -> bool:
        self.body_visible = False
        self.posture_ok = False
        if landmarks is None:
            return False

        side = _best_side(landmarks,
                          ((L_HIP, L_KNEE, L_ANKLE), (R_HIP, R_KNEE, R_ANKLE)))
        if side is None:
            return False
        hip, knee, ankle = side
        self.body_visible = True

        # Guard: shin points downward (ankle below knee). Holds while standing
        # AND at the bottom of a deep squat - unlike a hip->ankle span, which
        # collapses when the hips drop and would reject the deepest reps. Fails
        # for a lying (pushup) body, where the shin is horizontal.
        self.posture_ok = (ankle.y - knee.y) > MIN_SHIN_SPAN
        if not self.posture_ok:
            return False

        self.knee_angle = angle_at(
            (hip.x, hip.y), (knee.x, knee.y), (ankle.x, ankle.y)
        )
        return self.reps.update(self.knee_angle)


def _best_side(landmarks, side_ids):
    """Pick whichever body side the camera sees best (highest min visibility)."""
    sides = []
    for ids in side_ids:
        pts = [landmarks[i] for i in ids]
        vis = min(p.visibility for p in pts)
        sides.append((vis, pts))
    vis, pts = max(sides, key=lambda s: s[0])
    return pts if vis >= MIN_VISIBILITY else None


EXERCISES = {
    "pushups": {
        "label": "PUSHUPS",
        "counter": PushupCounter,
        "cue": "GET IN PUSHUP POSITION - PROFILE VIEW",
    },
    "squats": {
        "label": "SQUATS",
        "counter": SquatCounter,
        "cue": "STAND BACK - FULL BODY IN FRAME",
    },
}


def make_counter(exercise: str):
    return EXERCISES.get(exercise, EXERCISES["pushups"])["counter"]()
