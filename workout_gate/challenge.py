"""Challenge orchestration: webcam loop, pose detection, rep counting,
debt settlement. Persists progress after every rep so an interruption
(ESC, window closed, kill) loses nothing."""
import contextlib
import os
import random
import sys
import time

# Quiet MediaPipe/TensorFlow C++ logging before it loads (env-var path).
os.environ.setdefault("GLOG_minloglevel", "3")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import cv2
import mediapipe as mp
from mediapipe.tasks.python.core.base_options import BaseOptions
from mediapipe.tasks.python import vision

from . import store, ui
from .detector import make_counter
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


def _set_tall_capture(cap):
    """Prefer a 4:3-or-squarer capture mode. The default is 16:9, which is a
    vertical CROP of the sensor; a taller mode gives more vertical field of
    view so a standing body (squats) fits without backing up so far - and a
    square frame films better for vertical/social video. Falls back silently
    to whatever the camera offers."""
    for w, h in ((1920, 1440), (1280, 960), (640, 480)):
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        aw, ah = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        if ah and aw / ah <= 1.4:
            return


def _make_landmarker():
    options = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path())),
        running_mode=vision.RunningMode.VIDEO,
        min_pose_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    return vision.PoseLandmarker.create_from_options(options)


def run_challenge(offers, chosen=None, on_choice=None, on_rep=None) -> bool:
    """Open the webcam window. If `chosen` is given (resuming a locked debt),
    run it straight away; otherwise present `offers` (a list of
    {"exercise","reps"}) and let the user pick one. Calls on_choice(exercise,
    reps) once picked and on_rep(exercise) after each rep. Returns True if
    fully completed, False if aborted (ESC / window closed)."""
    store.write_challenge_pid()
    debug = store.load_config().get("debug", False) or os.environ.get("WORKOUT_GATE_DEBUG") == "1"
    with _hush_native_stderr():
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            store.clear_challenge_pid()
            raise RuntimeError("webcam unavailable")
        _set_tall_capture(cap)
        landmarker = _make_landmarker()
        ui.open_window(cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        try:
            if chosen is None:
                if len(offers) == 1:
                    chosen = offers[0]
                else:
                    chosen = _choice_phase(cap, offers)
                    if chosen is None:
                        return False  # aborted before choosing — offers stay owed
                if on_choice:
                    on_choice(chosen["exercise"], chosen["reps"])

            exercise, target = chosen["exercise"], chosen["reps"]
            counter = make_counter(exercise)
            t0 = time.monotonic()
            done = 0
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
                            on_rep(exercise)
                    if debug and landmarks is not None:
                        ui.draw_skeleton(frame, landmarks)
                    ui.draw_hud(frame, exercise, done, target,
                                counter.body_visible, counter.posture_ok, counter.is_down,
                                angle=counter.angle, debug=debug)
                    if done >= target:
                        _show_validated(cap, frame, target)
                        return True

                ui.show(frame)
                if cv2.waitKey(1) & 0xFF == ESC or ui.window_closed():
                    return False
        finally:
            store.clear_challenge_pid()
            landmarker.close()
            cap.release()
            ui.close_window()


def _choice_phase(cap, offers):
    """Show the menu and wait for the user to pick. Keys: 1/2... or the
    exercise's first letter. Returns the chosen offer, or None if aborted."""
    keymap = {}
    for i, off in enumerate(offers):
        keymap[ord(str(i + 1))] = off
        keymap[ord(off["exercise"][0].lower())] = off
        keymap[ord(off["exercise"][0].upper())] = off
    while True:
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError("webcam read failed")
        frame = cv2.flip(frame, 1)
        ui.draw_choice(frame, offers)
        ui.show(frame)
        k = cv2.waitKey(1) & 0xFF
        if k == ESC or ui.window_closed():
            return None
        if k in keymap:
            return keymap[k]


def _show_validated(cap, last_frame, seed=0):
    t0 = time.monotonic()
    frame = last_frame
    while time.monotonic() - t0 < VALIDATED_SECONDS:
        ok, fresh = cap.read()
        if ok:
            frame = cv2.flip(fresh, 1)
        ui.draw_validated(frame, seed)
        ui.show(frame)
        if cv2.waitKey(1) & 0xFF == ESC:
            return


def new_debt() -> list:
    """Build the challenge offers (one rep count per enabled exercise, drawn
    from its range) and persist them. In "random" mode a single exercise is
    pre-picked. Returns the offers list."""
    config = store.load_config()
    names = store.enabled_exercises(config)
    if config.get("exercise_mode") == "random":
        names = [random.choice(names)]
    offers = []
    for ex in names:
        ec = config["exercises"][ex]
        offers.append({"exercise": ex, "reps": random.randint(ec["reps_min"], ec["reps_max"])})
    def _set(state):
        state["debt_offers"] = offers
        state["debt_reps"] = 0
    store.mutate_state(_set)
    return offers


def pending_summary(state: dict) -> str:
    """Human-readable description of what's owed, for hook messages."""
    if state.get("debt_reps", 0) > 0:
        return f"{state['debt_reps']} {state['debt_exercise']}"
    return " or ".join(f"{o['reps']} {o['exercise']}" for o in state.get("debt_offers", []))


def settle_debt() -> bool:
    """Run the pending challenge. Each completed rep is persisted immediately
    (debt decremented + stats recorded), so quitting at 4/8 leaves 4 owed and
    4 in the stats. The chosen exercise is locked on first pick, so a resume
    skips the choice screen. Returns True if fully paid."""
    state = store.load_state()
    if state.get("debt_reps", 0) > 0:  # locked debt, resume directly
        chosen = {"exercise": state.get("debt_exercise", "pushups"), "reps": state["debt_reps"]}
        offers = [chosen]
    elif state.get("debt_offers"):
        chosen, offers = None, state["debt_offers"]
    else:
        return True

    def on_choice(exercise, reps):
        def _c(st):
            st["debt_exercise"] = exercise
            st["debt_reps"] = reps
            st["debt_offers"] = []
        store.mutate_state(_c)

    def on_rep(exercise):
        def _dec(st):
            st["debt_reps"] = max(0, st["debt_reps"] - 1)
        store.mutate_state(_dec)
        store.record_rep(exercise)

    if run_challenge(offers, chosen=chosen, on_choice=on_choice, on_rep=on_rep):
        def _done(st):
            st["debt_reps"] = 0
            st["debt_offers"] = []
            st["prompt_count"] = 0
            st["last_challenge_ts"] = time.time()
        store.mutate_state(_done)
        return True
    return False


def should_externalize() -> bool:
    """Whether to run the webcam challenge in a separate Terminal window rather
    than in-process. Under a macOS desktop app (Claude/Codex desktop) the gate
    hook has no controlling terminal of its own; opening the webcam there pins
    the camera-permission prompt to the app (or python) and the OpenCV window
    may not surface. Routing through Terminal.app pins the permission to
    Terminal — which onboarding already primed — and guarantees a visible
    window. The CLI, which already has a terminal, keeps the snappier in-process
    path. Force either way with WORKOUT_GATE_TERMINAL=1/0."""
    env = os.environ.get("WORKOUT_GATE_TERMINAL")
    if env in ("0", "1"):
        return env == "1"
    if sys.platform != "darwin":
        return False
    try:  # a controlling terminal exists -> we're in a CLI, stay in-process
        fd = os.open("/dev/tty", os.O_RDONLY)
        os.close(fd)
        return False
    except OSError:  # no controlling terminal -> desktop app
        return True


def _terminal_command(python: str, root: str, source: str = "claude") -> str:
    """The shell command Terminal.app runs to settle the debt: cd into the code
    dir (so `workout_gate` imports) and exec the paying CLI in that window.
    WORKOUT_GATE_CLAIMED tells that CLI the gate already claimed the slot on its
    behalf, so it skips its own "a challenge is already open" guard and takes
    ownership of the pid. WORKOUT_GATE_SOURCE carries the speaker tag across to
    the child (the env doesn't survive osascript's fresh login shell)."""
    import shlex
    return (f"cd {shlex.quote(root)} && exec env WORKOUT_GATE_CLAIMED=1 "
            f"WORKOUT_GATE_SOURCE={shlex.quote(source)} {shlex.quote(python)} -m workout_gate pay")


def _debt_clear(state: dict) -> bool:
    return state.get("debt_reps", 0) <= 0 and not state.get("debt_offers")


def settle_external(timeout_s: float = 285.0, poll_s: float = 0.4, _runner=None) -> bool:
    """Pop `workout pay` in a Terminal window so the camera prompt attaches to
    Terminal.app, then block until the challenge finishes. Returns True if the
    debt was fully paid. Falls back to in-process settle if Terminal can't be
    launched. The timeout stays under the hook's 300s ceiling.

    The caller (the gate) has already claimed the slot (challenge.pid = its own
    pid); we do NOT clear it, so no other tool can slip a second window into the
    gap before the Terminal child takes the pid over."""
    import subprocess
    from .paths import PROJECT_DIR, python_bin

    source = os.environ.get("WORKOUT_GATE_SOURCE", "claude")
    inner = _terminal_command(str(python_bin()), str(PROJECT_DIR), source)
    osa = f'tell application "Terminal" to do script "{inner}"'

    def _default_runner():
        subprocess.run(["osascript", "-e", osa], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        (_runner or _default_runner)()
    except (OSError, subprocess.SubprocessError):
        return settle_debt()  # no Terminal available -> best-effort in-process

    me = os.getpid()
    deadline = time.monotonic() + timeout_s
    started = False
    while time.monotonic() < deadline:
        if _debt_clear(store.load_state()):
            return True  # paid — return at once, don't wait out the timeout
        pid = store.running_challenge_pid()
        if pid and pid != me:
            started = True            # the Terminal challenge took the slot
        elif started and pid is None:
            break                     # it ran and exited without paying -> aborted
        time.sleep(poll_s)
    return _debt_clear(store.load_state())
