"""Challenge orchestration: webcam loop, pose detection, rep counting,
debt settlement. Persists progress after every rep so an interruption
(ESC, window closed, kill) loses nothing."""
import contextlib
import os
import random
import time

# Quiet MediaPipe/TensorFlow C++ logging before it loads (env-var path).
os.environ.setdefault("GLOG_minloglevel", "3")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import cv2
import mediapipe as mp
from mediapipe.tasks.python.core.base_options import BaseOptions
from mediapipe.tasks.python import vision

from . import store, ui
from .detector import PushupCounter
from .paths import model_path

ANNOUNCE_SECONDS = 3.0
VALIDATED_SECONDS = 2.5
ESC = 27


@contextlib.contextmanager
def _hush_native_stderr():
    """Redirect OS-level stderr (fd 2) to /dev/null. The env vars above don't
    catch everything (glog init, GL context, XNNPACK), and that C++ noise
    would otherwise drown our one-line blocked-prompt message, which the hook
    shows to the user via stderr."""
    saved = os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, 2)
        yield
    finally:
        os.dup2(saved, 2)
        os.close(devnull)
        os.close(saved)


def _make_landmarker():
    options = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path())),
        running_mode=vision.RunningMode.VIDEO,
        min_pose_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    return vision.PoseLandmarker.create_from_options(options)


def run_challenge(target: int, exercise: str = "pushups", on_rep=None) -> bool:
    """Open the webcam window and count reps until target is reached.
    Calls on_rep(count) after each rep. Returns True if completed,
    False if aborted (ESC / window closed)."""
    counter = PushupCounter()
    store.write_challenge_pid()
    done = 0
    with _hush_native_stderr():
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            store.clear_challenge_pid()
            raise RuntimeError("webcam unavailable")
        landmarker = _make_landmarker()
        ui.open_window()
        t0 = time.monotonic()
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    raise RuntimeError("webcam read failed")
                frame = cv2.flip(frame, 1)
                elapsed = time.monotonic() - t0

                if elapsed < ANNOUNCE_SECONDS:
                    ui.draw_announce(frame, exercise, target, ANNOUNCE_SECONDS - elapsed)
                else:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    result = landmarker.detect_for_video(mp_image, int(elapsed * 1000))
                    landmarks = result.pose_landmarks[0] if result.pose_landmarks else None
                    if counter.update(landmarks):
                        done = counter.count
                        if on_rep:
                            on_rep(done)
                    ui.draw_hud(frame, exercise, done, target,
                                counter.body_visible, counter.posture_ok, counter.is_down)
                    if done >= target:
                        _show_validated(cap, frame)
                        return True

                ui.show(frame)
                if cv2.waitKey(1) & 0xFF == ESC or ui.window_closed():
                    return False
        finally:
            store.clear_challenge_pid()
            landmarker.close()
            cap.release()
            ui.close_window()


def _show_validated(cap, last_frame):
    t0 = time.monotonic()
    frame = last_frame
    while time.monotonic() - t0 < VALIDATED_SECONDS:
        ok, fresh = cap.read()
        if ok:
            frame = cv2.flip(fresh, 1)
        ui.draw_validated(frame)
        ui.show(frame)
        if cv2.waitKey(1) & 0xFF == ESC:
            return


def new_debt() -> int:
    """Draw a random rep count from the configured range and persist it as debt."""
    config = store.load_config()
    reps = random.randint(config["reps_min"], config["reps_max"])
    state = store.load_state()
    state["debt_reps"] = reps
    state["debt_exercise"] = "pushups"
    store.save_state(state)
    return reps


def settle_debt() -> bool:
    """Run a challenge for the currently owed reps. Each completed rep is
    persisted immediately (debt decremented + stats recorded), so quitting
    at 4/8 leaves 4 owed and 4 in the stats. Returns True if fully paid."""
    state = store.load_state()
    owed = state["debt_reps"]
    if owed <= 0:
        return True
    exercise = state.get("debt_exercise", "pushups")

    def on_rep(_count):
        st = store.load_state()
        st["debt_reps"] = max(0, st["debt_reps"] - 1)
        store.save_state(st)
        store.record_rep(exercise)

    if run_challenge(owed, exercise=exercise, on_rep=on_rep):
        st = store.load_state()
        st["debt_reps"] = 0
        st["prompt_count"] = 0
        st["last_challenge_ts"] = time.time()
        store.save_state(st)
        return True
    return False
