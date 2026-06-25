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
WHITE = (245, 246, 248)
INK = (10, 11, 16)
CORAL = (240, 130, 96)
CORAL_HI = (250, 170, 140)
GREEN = (104, 214, 132)
YELLOW = (247, 205, 90)
RED = (238, 102, 92)
PANEL = (17, 18, 25)
DIM = (151, 154, 168)


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


def _text(d, xy, text, px, fill, anchor="mm", stroke=0, shadow=True):
    """Centered (by default) anti-aliased text. A soft offset drop-shadow does
    the legibility work (over the scrim) instead of a thick outline — the heavy
    stroke is what made the old HUD read as a cheap OpenCV demo."""
    if shadow:
        off = max(1, int(px * 0.045))
        d.text((xy[0] + off, xy[1] + off), text, font=_font(px),
               fill=(0, 0, 0, 150), anchor=anchor)
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


_SCRIM = {}


def _scrim_overlay(size):
    """A cached darkening layer: a gentle global dim plus stronger gradients top
    and bottom, so the HUD text/chips read cleanly over a bright webcam without
    heavy per-glyph outlines — while the picture stays clearly visible. Cached
    per window size (constant during a challenge), so it's ~free per frame."""
    if size in _SCRIM:
        return _SCRIM[size]
    w, h = size
    a = np.full((h, w), 44.0, dtype=np.float32)          # gentle overall dim
    th, bh = int(h * 0.22), int(h * 0.44)
    a[:th] += np.linspace(120, 0, th)[:, None]           # top band
    a[h - bh:] += np.linspace(0, 180, bh)[:, None]       # bottom band (bubble + bar)
    a = np.clip(a, 0, 240).astype(np.uint8)
    rgb = np.empty((h, w, 3), np.uint8)
    rgb[:] = (8, 9, 14)
    ov = Image.fromarray(np.dstack([rgb, a]), "RGBA")
    _SCRIM[size] = ov
    return ov


def _scrim(img):
    img.alpha_composite(_scrim_overlay(img.size))


def _dim(img, alpha, rgb=(8, 9, 14)):
    """Full-frame wash for the message screens (announce / choice)."""
    w, h = img.size
    _fill_rule(img, [((0, 0, w, h), rgb, 0, alpha)])


def _chip(img, cx, cy, label, dot_color, label_px, label_fill=WHITE,
          pad_x=None, height=None, alpha=205):
    """A centered rounded pill: a colored status dot + a label. Used for the
    exercise name and the UP/DOWN state."""
    w, h = img.size
    d0 = ImageDraw.Draw(img)
    lw = d0.textlength(label, font=_font(label_px))
    dot = int(label_px * 0.62)
    gap = int(label_px * 0.45)
    pad_x = pad_x if pad_x is not None else int(label_px * 0.85)
    ch = height if height is not None else int(label_px * 1.7)
    cw = int(pad_x * 2 + dot + gap + lw)
    x0, y0 = int(cx - cw / 2), int(cy - ch / 2)
    _fill_rule(img, [((x0, y0, x0 + cw, y0 + ch), PANEL, ch // 2, alpha)])
    d = ImageDraw.Draw(img)
    dy = y0 + ch / 2
    dx = x0 + pad_x
    d.ellipse((dx, dy - dot / 2, dx + dot, dy + dot / 2), fill=dot_color)
    _text(d, (dx + dot + gap, dy), label, label_px, label_fill, anchor="lm")


def _bubble(img, text, accent=CORAL):
    """The coach's speech card: translucent rounded panel with a coral accent
    edge, a dot + speaker tag and one auto-fitted line. The screen-stealer."""
    w, h = img.size
    bw, bh = int(w * 0.88), int(h * 0.158)
    x0 = (w - bw) // 2
    y0 = int(h * 0.706)
    x1, y1 = x0 + bw, y0 + bh
    r = int(bh * 0.30)
    bar_w = max(6, int(w * 0.010))
    bx = x0 + int(w * 0.022)
    _fill_rule(img, [
        ((x0, y0 + 11, x1, y1 + 11), (0, 0, 0), r, 64),                 # soft shadow
        ((x0, y0, x1, y1), PANEL, r, 228),                              # card
        ((bx, y0 + int(bh * 0.22), bx + bar_w, y1 - int(bh * 0.22)),    # accent edge
         accent, bar_w // 2, 255),
    ])
    d = ImageDraw.Draw(img)
    nx = bx + bar_w + int(w * 0.028)
    ny = y0 + int(bh * 0.32)
    dot = int(h * 0.0125)
    d.ellipse((nx, ny - dot / 2, nx + dot, ny + dot / 2), fill=accent)
    _text(d, (nx + dot + int(w * 0.013), ny), taunts.coach_name(),
          int(h * 0.026), accent, anchor="lm")
    px = _fit(text, int(bw * 0.83), int(h * 0.050))
    _text(d, (nx, y0 + int(bh * 0.67)), text, px, WHITE, anchor="lm")


def _counter(d, img, done, target, cx, cy):
    """Big score: done in coral, a smaller dim ' / target', a REPS caption."""
    w, h = img.size
    fpx = int(h * 0.150)
    spx = int(fpx * 0.58)
    a, sep, b = str(done), "/", str(target)
    wa = d.textlength(a, font=_font(fpx))
    wsep = d.textlength(f"  {sep}  ", font=_font(spx))
    wb = d.textlength(b, font=_font(spx))
    x = cx - (wa + wsep + wb) / 2
    _text(d, (x, cy), a, fpx, CORAL, anchor="lm")
    _text(d, (x + wa, cy), f"  {sep}  ", spx, DIM, anchor="lm")
    _text(d, (x + wa + wsep, cy), b, spx, WHITE, anchor="lm")
    _text(d, (cx, cy + int(fpx * 0.60)), "REPS DONE", int(h * 0.023), DIM, anchor="mm")


def _esc_hint(d, img):
    w, h = img.size
    _text(d, (int(w * 0.022), h - int(h * 0.026)),
          "ESC  ·  give up, progress is saved", int(h * 0.020), DIM, anchor="lm")


# ----------------------------------------------------------------------------
# screens
# ----------------------------------------------------------------------------
def draw_choice(frame, offers):
    """Pick-your-pain screen: one card per offer, chosen by number key or the
    exercise's first letter."""
    img = _begin(frame)
    w, h = img.size
    _dim(img, 150)
    d = ImageDraw.Draw(img)
    _text(d, (w / 2, h * 0.155), "CHOOSE YOUR PAIN", int(h * 0.070), WHITE)
    _text(d, (w / 2, h * 0.225), "press the number, or the first letter", int(h * 0.026), DIM)
    n = len(offers)
    ow, oh = int(w * 0.66), int(h * 0.115)
    for i, off in enumerate(offers):
        label = EXERCISES.get(off["exercise"], {}).get("label", off["exercise"].upper())
        cy = h * (0.40 + 0.155 * i) if n > 1 else h * 0.45
        x0, y0 = int(w / 2 - ow / 2), int(cy - oh / 2)
        _fill_rule(img, [((x0, y0, x0 + ow, y0 + oh), PANEL, int(oh * 0.30), 212)])
        dd = ImageDraw.Draw(img)
        _text(dd, (x0 + int(oh * 0.6), cy), str(i + 1), int(oh * 0.50), CORAL, anchor="mm")
        _text(dd, (x0 + int(oh * 1.25), cy), f"{off['reps']}  {label}", int(oh * 0.38), WHITE, anchor="lm")
        _text(dd, (x0 + ow - int(oh * 0.4), cy), off["exercise"][0].upper(),
              int(oh * 0.32), DIM, anchor="rm")
    _bubble(img, taunts.CHOICE)
    _esc_hint(d, img)
    _commit(frame, img)


def draw_announce(frame, exercise: str, target: int, seconds_left: float):
    """Pre-challenge screen: exercise name + countdown to get in position."""
    img = _begin(frame)
    w, h = img.size
    _dim(img, 140)
    d = ImageDraw.Draw(img)
    _text(d, (w / 2, h * 0.19), exercise.upper(), int(h * 0.100), WHITE)
    _text(d, (w / 2, h * 0.285), f"{target} REPS TO UNLOCK YOUR PROMPT", int(h * 0.034), YELLOW)
    _text(d, (w / 2, h * 0.45), str(max(1, int(seconds_left + 0.999))), int(h * 0.195), CORAL)
    _text(d, (w / 2, h * 0.585), "GET IN POSITION", int(h * 0.026), DIM)
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


def _progress(img, count, target):
    """Bottom progress bar: subtle track + opaque coral fill + centered %."""
    w, h = img.size
    m = int(w * 0.085)
    y0, y1 = int(h * 0.900), int(h * 0.944)
    bh = y1 - y0
    pct = min(1.0, count / target) if target > 0 else 0.0
    _fill_rule(img, [((m, y0, w - m, y1), (255, 255, 255), bh // 2, 40)])  # track
    d = ImageDraw.Draw(img)
    fill_w = int((w - 2 * m) * pct)
    if fill_w >= bh:
        d.rounded_rectangle((m, y0, m + fill_w, y1), radius=bh // 2, fill=CORAL)
    _text(d, (w / 2, (y0 + y1) / 2), f"{int(pct * 100)}%", int(bh * 0.58), WHITE, anchor="mm")


def draw_hud(frame, exercise: str, count: int, target: int,
             body_visible: bool, posture_ok: bool, is_down: bool,
             angle: float = None, debug: bool = False):
    img = _begin(frame)
    w, h = img.size
    _scrim(img)

    # bubble content: a jab while grinding, a cue/warning when tracking drops
    if not body_visible:
        b_text, accent = taunts.cant_see_line(target), RED
    elif not posture_ok:
        b_text, accent = EXERCISES.get(exercise, EXERCISES["pushups"])["cue"], YELLOW
    else:
        b_text, accent = taunts.grind_line(count, target), CORAL

    _chip(img, w / 2, int(h * 0.072), exercise.upper(), CORAL, int(h * 0.040))

    d = ImageDraw.Draw(img)
    _counter(d, img, count, target, w / 2, int(h * 0.40))
    if body_visible and posture_ok:
        _chip(img, w / 2, int(h * 0.560), "DOWN" if is_down else "UP",
              YELLOW if is_down else GREEN, int(h * 0.028))

    _bubble(img, b_text, accent=accent)
    _progress(img, count, target)

    d = ImageDraw.Draw(img)
    if debug and angle is not None:
        _text(d, (int(w * 0.016), int(h * 0.02)),
              f"angle {angle:.0f}  {'DOWN' if is_down else 'UP'}  "
              f"vis={int(body_visible)} ok={int(posture_ok)}", int(h * 0.026), GREEN, anchor="lm")
    _esc_hint(d, img)
    _commit(frame, img)


def draw_validated(frame, seed: int = 0):
    img = _begin(frame)
    w, h = img.size
    _dim(img, 150, rgb=(22, 96, 44))  # green wash
    d = ImageDraw.Draw(img)
    _text(d, (w / 2, h * 0.37), "VALIDATED", int(h * 0.120), WHITE)
    s = int(h * 0.048)
    cx, cy = int(w / 2), int(h * 0.52)
    d.line([(cx - s, cy), (cx - s // 3, cy + s // 2), (cx + s, cy - s)],
           fill=WHITE, width=max(8, int(h * 0.013)), joint="curve")
    _bubble(img, taunts.validated_line(seed), accent=GREEN)
    _commit(frame, img)
