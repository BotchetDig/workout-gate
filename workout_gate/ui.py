"""On-screen rendering for the challenge window. Built for video capture:
big, readable, high contrast. Draws on BGR frames, no detection logic here."""
import cv2
import numpy as np

WINDOW = "WORKOUT GATE"

WHITE = (255, 255, 255)
BLACK = (20, 20, 20)
GREEN = (80, 220, 80)
YELLOW = (60, 200, 255)
RED = (60, 60, 230)

FONT = cv2.FONT_HERSHEY_DUPLEX


def open_window():
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW, 1280, 720)
    try:
        cv2.setWindowProperty(WINDOW, cv2.WND_PROP_TOPMOST, 1)
    except cv2.error:
        pass


def close_window():
    cv2.destroyAllWindows()
    cv2.waitKey(1)


def show(frame):
    cv2.imshow(WINDOW, frame)


def window_closed() -> bool:
    return cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1


def _text(frame, text, center_x, y, scale, color, thickness):
    (w, _), _ = cv2.getTextSize(text, FONT, scale, thickness)
    x = int(center_x - w / 2)
    cv2.putText(frame, text, (x, y), FONT, scale, BLACK, thickness + 6, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), FONT, scale, color, thickness, cv2.LINE_AA)


def draw_announce(frame, exercise: str, target: int, seconds_left: float):
    """Pre-challenge screen: exercise name + countdown to get in position."""
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), BLACK, -1)
    cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)
    _text(frame, exercise.upper(), w // 2, int(h * 0.30), 3.0, WHITE, 7)
    _text(frame, f"{target} REPS TO UNLOCK YOUR PROMPT", w // 2, int(h * 0.45), 1.3, YELLOW, 3)
    _text(frame, "GET IN POSITION", w // 2, int(h * 0.62), 1.3, WHITE, 3)
    _text(frame, str(max(1, int(seconds_left + 0.999))), w // 2, int(h * 0.85), 4.0, YELLOW, 10)
    _esc_hint(frame)


def draw_hud(frame, exercise: str, count: int, target: int,
             body_visible: bool, posture_ok: bool, is_down: bool):
    h, w = frame.shape[:2]
    # top banner
    cv2.rectangle(frame, (0, 0), (w, int(h * 0.13)), BLACK, -1)
    _text(frame, exercise.upper(), w // 2, int(h * 0.095), 1.8, WHITE, 4)
    # giant counter
    _text(frame, f"{count} / {target}", w // 2, int(h * 0.48), 4.5, WHITE, 10)
    # down/up phase indicator
    if body_visible and posture_ok:
        phase = "DOWN" if is_down else "UP"
        _text(frame, phase, w // 2, int(h * 0.60), 1.2, YELLOW if is_down else GREEN, 3)
    else:
        hint = "GET IN PUSHUP POSITION - PROFILE VIEW" if body_visible else "I CAN'T SEE YOU"
        _text(frame, hint, w // 2, int(h * 0.60), 1.2, RED, 3)
    # progress bar
    bar_y0, bar_y1 = int(h * 0.90), int(h * 0.96)
    margin = int(w * 0.08)
    cv2.rectangle(frame, (margin, bar_y0), (w - margin, bar_y1), BLACK, -1)
    if target > 0:
        fill = margin + int((w - 2 * margin) * min(1.0, count / target))
        cv2.rectangle(frame, (margin, bar_y0), (fill, bar_y1), GREEN, -1)
    cv2.rectangle(frame, (margin, bar_y0), (w - margin, bar_y1), WHITE, 2)
    _esc_hint(frame)


def _esc_hint(frame):
    h, w = frame.shape[:2]
    text = "[ESC] give up - progress is saved"
    cv2.putText(frame, text, (12, h - 10), FONT, 0.55, BLACK, 4, cv2.LINE_AA)
    cv2.putText(frame, text, (12, h - 10), FONT, 0.55, WHITE, 1, cv2.LINE_AA)


def draw_validated(frame):
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), (30, 120, 30), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
    _text(frame, "VALIDATED", w // 2, int(h * 0.45), 3.5, WHITE, 8)
    _text(frame, "PROMPT UNLOCKED", w // 2, int(h * 0.62), 1.5, WHITE, 3)
    # hand-drawn checkmark (Hershey fonts have no unicode)
    cx, cy, s = w // 2, int(h * 0.78), int(h * 0.05)
    pts = np.array([(cx - s, cy), (cx - s // 3, cy + s // 2), (cx + s, cy - s)], np.int32)
    cv2.polylines(frame, [pts], False, WHITE, 12, cv2.LINE_AA)
