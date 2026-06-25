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
SMOOTH_FRAMES = 3
LOST_RESET_FRAMES = 5   # consecutive frames with no usable body before a rep-in-progress is abandoned
SIDE_STICKY_MARGIN = 0.15  # the other side must beat the current one by this much in visibility to switch


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
        self._lost = 0

    def update(self, elbow_angle: float) -> bool:
        """Feed one frame's elbow angle. Returns True if a rep just completed."""
        self._lost = 0
        self._window.append(elbow_angle)
        smoothed = sum(self._window) / len(self._window)
        if not self.is_down and smoothed < self.down_angle:
            self.is_down = True
        elif self.is_down and smoothed > self.up_angle:
            self.is_down = False
            self.count += 1
            return True
        return False

    def lost(self) -> None:
        """Register a frame with no usable angle (body gone / out of frame /
        posture broken). After LOST_RESET_FRAMES in a row, abandon any descent
        in progress and clear the smoothing window, so a body that leaves and
        re-enters the frame can't complete a phantom rep from stale state — and
        pre-gap angles never blend into the first fresh frames. Biases toward
        under-counting on a dropout, which is the credible direction."""
        self._lost += 1
        if self._lost >= LOST_RESET_FRAMES:
            self._window.clear()
            self.is_down = False

    @property
    def smoothed_angle(self) -> float:
        return sum(self._window) / len(self._window) if self._window else 180.0


# ─────────────────────────────────────────────────────────────────────────
# HOW TO ADD AN EXERCISE (the whole "factory" lives here)
#
# 1. Write a counter subclassing ExerciseCounter: declare the joint angle to
#    track (SIDES = left/right (a, b, c) landmark triples, b is the vertex),
#    the DOWN/UP angle thresholds, and optionally override posture() to reject
#    frames where the body isn't in the right shape.
# 2. Add one entry to the EXERCISES registry below (label, counter, on-screen
#    cue, default rep range, and a one-set "default_max" used by the wizard).
#
# That's it. Config defaults, presets, the wizard, the dashboard, stats and
# the choice screen all read the registry — nothing else to touch. Fork away.
# ─────────────────────────────────────────────────────────────────────────


def _best_side(landmarks, side_ids, current=None, margin=0.0, required=None):
    """Pick the body side the camera sees best. Returns (side_index, points) or
    None if neither side is visible enough.

    `required` is how many of the triple's points must clear MIN_VISIBILITY
    (default: all of them); the side is ranked by the visibility of its
    `required`-th most-visible point, so a partially-occluded side (e.g. ankle
    off-frame on a laptop webcam) still qualifies.

    Stickiness: if `current` (the side chosen last frame) is still visible and
    within `margin` of the best side, keep it. This stops per-frame left/right
    flapping in profile views, where the two sides report different joint angles
    and a flip injects a fake jump into the smoothing window."""
    scored = []
    for idx, ids in enumerate(side_ids):
        pts = [landmarks[i] for i in ids]
        need = len(pts) if required is None else required
        vis_sorted = sorted((p.visibility for p in pts), reverse=True)
        vis = vis_sorted[need - 1]  # visibility of the need-th most-visible point
        scored.append((vis, idx, pts))
    best_vis, best_idx, best_pts = max(scored, key=lambda s: s[0])
    if best_vis < MIN_VISIBILITY:
        return None
    if current is not None:
        cur_vis, cur_idx, cur_pts = scored[current]
        if cur_vis >= MIN_VISIBILITY and best_vis - cur_vis <= margin:
            return cur_idx, cur_pts
    return best_idx, best_pts


class ExerciseCounter:
    """Base class: best-side selection + angle + down/up hysteresis. A concrete
    exercise sets SIDES / DOWN_ANGLE / UP_ANGLE and may override posture().

    Exposes the interface the UI relies on: count, is_down, angle,
    body_visible, posture_ok, and update(landmarks) -> True on a completed rep.
    """
    SIDES = ()          # ((a, b, c), (a, b, c)) landmark-index triples; b = vertex
    DOWN_ANGLE = 95.0
    UP_ANGLE = 150.0

    def __init__(self):
        self.reps = RepCounter(self.DOWN_ANGLE, self.UP_ANGLE)
        self.body_visible = False
        self.posture_ok = False
        self.angle = 180.0
        self._side = None   # last chosen side, for sticky selection

    @property
    def count(self) -> int:
        return self.reps.count

    @property
    def is_down(self) -> bool:
        return self.reps.is_down

    def posture(self, landmarks, side_idx, pts) -> bool:
        """Override to reject frames where the body isn't in position. pts are
        the chosen side's (a, b, c) landmarks; side_idx is 0 (left)/1 (right)
        for looking up other joints on the same side."""
        return True

    def update(self, landmarks) -> bool:
        """landmarks: sequence with .x, .y, .visibility (MediaPipe
        pose_landmarks.landmark), or None. Returns True on a completed rep."""
        self.body_visible = False
        self.posture_ok = False
        if landmarks is None:
            self.reps.lost()
            return False
        picked = _best_side(landmarks, self.SIDES, self._side, SIDE_STICKY_MARGIN)
        if picked is None:
            self.reps.lost()
            return False
        side_idx, pts = picked
        self._side = side_idx
        self.body_visible = True
        self.posture_ok = self.posture(landmarks, side_idx, pts)
        if not self.posture_ok:
            self.reps.lost()
            return False
        a, b, c = pts
        self.angle = angle_at((a.x, a.y), (b.x, b.y), (c.x, c.y))
        return self.reps.update(self.angle)


class PushupCounter(ExerciseCounter):
    """Elbow angle (shoulder-elbow-wrist), body horizontal."""
    SIDES = ((L_SHOULDER, L_ELBOW, L_WRIST), (R_SHOULDER, R_ELBOW, R_WRIST))
    DOWN_ANGLE = 95.0
    UP_ANGLE = 150.0

    def posture(self, landmarks, side_idx, pts) -> bool:
        shoulder = pts[0]
        hip = landmarks[L_HIP if side_idx == 0 else R_HIP]
        tilt = math.degrees(math.atan2(abs(shoulder.y - hip.y),
                                       abs(shoulder.x - hip.x) + 1e-6))
        return tilt < MAX_TORSO_TILT  # body roughly horizontal, not standing


class SquatCounter(ExerciseCounter):
    """Knee angle (hip-knee-ankle), feet below knees (survives deep squats).

    Laptop-webcam friendly: when the ankle is off-frame (common when the user
    sits close), it falls back to the thigh's tilt from vertical (hip->knee
    only) mapped onto the same knee-angle scale, so squats still count with
    just hip + knee. With the ankle visible it behaves exactly as before."""
    SIDES = ((L_HIP, L_KNEE, L_ANKLE), (R_HIP, R_KNEE, R_ANKLE))
    DOWN_ANGLE = KNEE_DOWN_ANGLE
    UP_ANGLE = KNEE_UP_ANGLE
    MIN_REQUIRED = 2  # hip + knee mandatory; ankle optional

    def update(self, landmarks) -> bool:
        self.body_visible = False
        self.posture_ok = False
        if landmarks is None:
            return False
        picked = _best_side(landmarks, self.SIDES, required=self.MIN_REQUIRED)
        if picked is None:
            return False
        side_idx, pts = picked
        self.body_visible = True
        hip, knee, ankle = pts
        ankle_seen = ankle.visibility >= MIN_VISIBILITY
        self.posture_ok = self._posture(hip, knee, ankle, ankle_seen)
        if not self.posture_ok:
            return False
        if ankle_seen:
            self.angle = angle_at((hip.x, hip.y), (knee.x, knee.y),
                                  (ankle.x, ankle.y))
        else:
            self.angle = self._thigh_proxy_angle(hip, knee)
        return self.reps.update(self.angle)

    @staticmethod
    def _posture(hip, knee, ankle, ankle_seen) -> bool:
        if ankle_seen:
            return ankle.y > knee.y   # standing or squatting, not lying down
        return knee.y > hip.y         # knee below hip: upright body, not lying

    @staticmethod
    def _thigh_proxy_angle(hip, knee) -> float:
        """Thigh tilt from vertical (hip->knee), mapped to the knee-angle
        scale: ~180 standing (thigh vertical) down to ~0 in a deep squat."""
        vx, vy = knee.x - hip.x, knee.y - hip.y
        n = math.hypot(vx, vy)
        if n == 0:
            return 180.0
        cos = max(-1.0, min(1.0, vy / n))  # dot with downward vertical (0, 1)
        tilt = math.degrees(math.acos(cos))
        return max(0.0, 180.0 - 2.0 * tilt)


EXERCISES = {
    "pushups": {
        "label": "PUSHUPS",
        "counter": PushupCounter,
        "cue": "GET IN PUSHUP POSITION - PROFILE VIEW",
        "default_reps": (5, 10),
        "default_max": 20,   # one clean set; seeds the setup wizard
    },
    "squats": {
        "label": "SQUATS",
        "counter": SquatCounter,
        "cue": "STAND BACK - FULL BODY IN FRAME",
        "default_reps": (8, 15),
        "default_max": 30,
    },
}


def make_counter(exercise: str):
    return EXERCISES.get(exercise, EXERCISES["pushups"])["counter"]()


def default_exercises_config() -> dict:
    """The per-exercise config block, derived from the registry. New exercises
    appear automatically."""
    return {name: {"enabled": True,
                   "reps_min": e["default_reps"][0],
                   "reps_max": e["default_reps"][1]}
            for name, e in EXERCISES.items()}
