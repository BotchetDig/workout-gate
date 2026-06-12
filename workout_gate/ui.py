"""On-screen rendering for the challenge window. Built for video capture:
big, smooth, high contrast. Text and panels are drawn with Pillow (real
TrueType fonts, anti-aliased, rounded translucent cards) so the window looks
like a designed interface rather than a raw OpenCV demo. Window management and
the live skeleton stay on OpenCV. No detection logic here."""
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .detector import EXERCISES
from . import taunts

WINDOW = "WORKOUT GATE"

# BlazePose body skeleton (indices into the 33-point pose), face omitted.
POSE_CONNECTIONS = [
    (11, 12), (11, 23), (12, 24), (23, 24),          # shoulders + torso
    (11, 13), (13, 15), (12, 14), (14, 16),          # arms
    (23, 25), (25, 27), (24, 26), (26, 28),          # legs
    (27, 29), (27, 31), (29, 31),                    # left foot
    (28, 30), (28, 32), (30, 32),                    # right foot
]
SKELETON_MIN_VIS = 0.3
_SK_GREEN = (80, 220, 80)    # BGR (drawn via OpenCV)
_SK_YELLOW = (60, 200, 255)  # BGR

# UI palette — RGB (Pillow). Claude coral is the accent.
WHITE = (244, 244, 246)
INK = (16, 16, 20)
CORAL = (236, 122, 89)
GREEN = (96, 210, 124)
YELLOW = (246, 202, 76)
RED = (236, 96, 84)
PANEL = (20, 20, 26)


# ----------------------------------------------------------------------------
# window management (OpenCV)
# ----------------------------------------------------------------------------
def open_window(cap_w=1280, cap_h=720):
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    aspect = (cap_w / cap_h) if cap_h else (1280 / 720)
    h = 760
    cv2.resizeWindow(WINDOW, int(h * aspect), h)
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


# ----------------------------------------------------------------------------
# font + drawing helpers (Pillow)
# ----------------------------------------------------------------------------
_FONT_FILE = None
_FONTS = {}


def _font_file():
    """A bold TrueType font, resolved once. Prefers DejaVu Sans Bold shipped by
    matplotlib (a mediapipe dependency, so offline + redistributable), then
    common system fonts. Falls back to Pillow's bitmap default."""
    global _FONT_FILE
    if _FONT_FILE is not None:
        return _FONT_FILE
    import os
    cands = []
    try:
        import matplotlib
        d = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
        cands += [os.path.join(d, "DejaVuSans-Bold.ttf"), os.path.join(d, "DejaVuSans.ttf")]
    except Exception:
        pass
    cands += [
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    _FONT_FILE = next((c for c in cands if os.path.exists(c)), "")
    return _FONT_FILE


def _font(px):
    px = max(8, int(px))
    if px not in _FONTS:
        f = _font_file()
        try:
            _FONTS[px] = ImageFont.truetype(f, px) if f else ImageFont.load_default()
        except Exception:
            _FONTS[px] = ImageFont.load_default()
    return _FONTS[px]


def _begin(frame):
    return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert("RGBA")


def _commit(frame, img):
    frame[:] = cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def _text(d, xy, text, px, fill, anchor="mm", stroke=3):
    """Centered (by default) anti-aliased text with a dark outline for legibility
    over any background."""
    d.text(xy, text, font=_font(px), fill=fill, anchor=anchor,
           stroke_width=stroke, stroke_fill=INK)


def _fit(text, max_w, base_px):
    f_draw = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    px = base_px
    while px > 14 and f_draw.textlength(text, font=_font(px)) > max_w:
        px -= 2
    return px


def _fill_rule(img, panels):
    """Composite a list of translucent rounded panels in one pass.
    panels: (box, (r,g,b), radius, alpha)."""
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for box, rgb, radius, alpha in panels:
        od.rounded_rectangle(box, radius=radius, fill=(rgb[0], rgb[1], rgb[2], alpha))
    img.alpha_composite(ov)


def _bubble(img, text, accent=CORAL):
    """Claude's speech card: translucent rounded panel with a coral accent edge,
    a CLAUDE tag and one auto-fitted line of commentary. The screen-stealer."""
    w, h = img.size
    bw, bh = int(w * 0.88), int(h * 0.16)
    x0 = (w - bw) // 2
    y0 = int(h * 0.71)
    x1, y1 = x0 + bw, y0 + bh
    r = int(bh * 0.26)
    bar_w = max(6, int(w * 0.013))
    _fill_rule(img, [
        ((x0 + 6, y0 + 9, x1 + 6, y1 + 9), (0, 0, 0), r, 80),       # soft shadow
        ((x0, y0, x1, y1), PANEL, r, 216),                          # card
        ((x0, y0, x0 + bar_w, y1), accent, min(bar_w // 2, r), 255),  # accent edge
    ])
    d = ImageDraw.Draw(img)
    _text(d, (x0 + int(w * 0.055), y0 + int(bh * 0.30)), "CLAUDE",
          int(h * 0.030), accent, anchor="lm", stroke=2)
    px = _fit(text, int(bw * 0.88), int(h * 0.055))
    _text(d, ((x0 + x1) // 2, y0 + int(bh * 0.65)), text, px, WHITE, anchor="mm", stroke=3)


def _counter(d, img, done, target, cx, cy):
    """Big score: done in coral, ' / target' in white."""
    fpx = int(img.size[1] * 0.16)
    f = _font(fpx)
    a, sep, b = str(done), " / ", str(target)
    wa = d.textlength(a, font=f)
    ws = d.textlength(sep, font=f)
    wb = d.textlength(b, font=f)
    x = cx - (wa + ws + wb) / 2
    _text(d, (x, cy), a, fpx, CORAL, anchor="lm", stroke=5)
    _text(d, (x + wa, cy), sep, fpx, WHITE, anchor="lm", stroke=5)
    _text(d, (x + wa + ws, cy), b, fpx, WHITE, anchor="lm", stroke=5)


def _esc_hint(d, img):
    w, h = img.size
    _text(d, (int(w * 0.012), h - int(h * 0.02)),
          "[ESC] give up - progress is saved", int(h * 0.022), WHITE, anchor="lm", stroke=2)


# ----------------------------------------------------------------------------
# screens
# ----------------------------------------------------------------------------
def draw_choice(frame, offers):
    """Pick-your-pain screen: one labelled option per offer, chosen by number
    key or the exercise's first letter."""
    img = _begin(frame)
    w, h = img.size
    _fill_rule(img, [((0, 0, w, h), (8, 8, 12), 0, 130)])
    d = ImageDraw.Draw(img)
    _text(d, (w / 2, h * 0.20), "CHOOSE YOUR PAIN", int(h * 0.085), WHITE, stroke=5)
    n = len(offers)
    for i, off in enumerate(offers):
        label = EXERCISES.get(off["exercise"], {}).get("label", off["exercise"].upper())
        y = h * (0.43 + 0.16 * i) if n > 1 else h * 0.48
        key = off["exercise"][0].upper()
        _text(d, (w / 2, y), f"[{i + 1}/{key}]  {off['reps']} {label}", int(h * 0.06), YELLOW, stroke=4)
    _bubble(img, taunts.CHOICE)
    _esc_hint(d, img)
    _commit(frame, img)


def draw_announce(frame, exercise: str, target: int, seconds_left: float):
    """Pre-challenge screen: exercise name + countdown to get in position."""
    img = _begin(frame)
    w, h = img.size
    _fill_rule(img, [((0, 0, w, h), (8, 8, 12), 0, 120)])
    d = ImageDraw.Draw(img)
    _text(d, (w / 2, h * 0.26), exercise.upper(), int(h * 0.11), WHITE, stroke=6)
    _text(d, (w / 2, h * 0.40), f"{target} REPS TO UNLOCK YOUR PROMPT", int(h * 0.036), YELLOW, stroke=3)
    _text(d, (w / 2, h * 0.58), str(max(1, int(seconds_left + 0.999))), int(h * 0.20), CORAL, stroke=8)
    _bubble(img, taunts.announce_line(target))
    _esc_hint(d, img)
    _commit(frame, img)


def draw_skeleton(frame, landmarks):
    """Overlay the detected pose: green segments, yellow joints. Drawn directly
    on the BGR frame with OpenCV (fast, runs before the Pillow HUD pass)."""
    h, w = frame.shape[:2]

    def px(lm):
        return int(lm.x * w), int(lm.y * h)

    for a, b in POSE_CONNECTIONS:
        la, lb = landmarks[a], landmarks[b]
        if la.visibility > SKELETON_MIN_VIS and lb.visibility > SKELETON_MIN_VIS:
            cv2.line(frame, px(la), px(lb), _SK_GREEN, 3, cv2.LINE_AA)
    for lm in landmarks:
        if lm.visibility > SKELETON_MIN_VIS:
            cv2.circle(frame, px(lm), 5, _SK_YELLOW, -1, cv2.LINE_AA)


def draw_hud(frame, exercise: str, count: int, target: int,
             body_visible: bool, posture_ok: bool, is_down: bool,
             angle: float = None, debug: bool = False):
    img = _begin(frame)
    w, h = img.size

    # bubble content: a jab while grinding, a warning when tracking drops
    if not body_visible:
        b_text, accent = taunts.cant_see_line(target), RED
    elif not posture_ok:
        b_text, accent = EXERCISES.get(exercise, EXERCISES["pushups"])["cue"], YELLOW
    else:
        b_text, accent = taunts.grind_line(count, target), CORAL

    d = ImageDraw.Draw(img)
    name = exercise.upper()
    npx = int(h * 0.045)
    nw = d.textlength(name, font=_font(npx))
    pill_w = nw + int(w * 0.07)
    pill_h = int(h * 0.075)
    px0 = int(w / 2 - pill_w / 2)
    py0 = int(h * 0.028)
    bar_m = int(w * 0.09)
    bar_y0, bar_y1 = int(h * 0.905), int(h * 0.95)
    bar_h = bar_y1 - bar_y0

    # translucent panels (name pill + progress track) in one composite
    _fill_rule(img, [
        ((px0, py0, px0 + int(pill_w), py0 + pill_h), PANEL, pill_h // 2, 205),
        ((bar_m, bar_y0, w - bar_m, bar_y1), PANEL, bar_h // 2, 205),
    ])

    d = ImageDraw.Draw(img)
    _text(d, (w / 2, py0 + pill_h / 2), name, npx, WHITE, anchor="mm", stroke=3)
    _counter(d, img, count, target, w / 2, int(h * 0.42))
    if body_visible and posture_ok:
        _text(d, (w / 2, h * 0.55), "DOWN" if is_down else "UP",
              int(h * 0.040), YELLOW if is_down else GREEN, anchor="mm", stroke=3)

    _bubble(img, b_text, accent=accent)

    # progress fill (opaque coral) + percentage
    pct = min(1.0, count / target) if target > 0 else 0.0
    d = ImageDraw.Draw(img)
    fill_w = int((w - 2 * bar_m) * pct)
    if fill_w > 2:
        d.rounded_rectangle((bar_m, bar_y0, bar_m + fill_w, bar_y1),
                            radius=min(bar_h // 2, fill_w // 2), fill=CORAL)
    _text(d, (w / 2, (bar_y0 + bar_y1) / 2), f"{int(pct * 100)}%",
          int(bar_h * 0.66), WHITE, anchor="mm", stroke=2)

    if debug and angle is not None:
        dbg = f"angle {angle:.0f}  {'DOWN' if is_down else 'UP'}  vis={int(body_visible)} ok={int(posture_ok)}"
        _text(d, (int(w * 0.012), int(h * 0.02)), dbg, int(h * 0.026), GREEN, anchor="lm", stroke=2)
    _esc_hint(d, img)
    _commit(frame, img)


def draw_validated(frame, seed: int = 0):
    img = _begin(frame)
    w, h = img.size
    _fill_rule(img, [((0, 0, w, h), (24, 110, 44), 0, 150)])
    d = ImageDraw.Draw(img)
    _text(d, (w / 2, h * 0.40), "VALIDATED", int(h * 0.13), WHITE, stroke=7)
    s = int(h * 0.05)
    cx, cy = int(w / 2), int(h * 0.55)
    d.line([(cx - s, cy), (cx - s // 3, cy + s // 2), (cx + s, cy - s)],
           fill=WHITE, width=14, joint="curve")
    _bubble(img, taunts.validated_line(seed), accent=GREEN)
    _commit(frame, img)
