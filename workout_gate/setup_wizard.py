"""First-run setup as an interactive curses screen, styled like the dashboard
and stats: colored, arrow-navigable, with a checkbox per exercise. Adapts to
detector.EXERCISES automatically. Run with: workout setup.

Pure helpers (derive_reps_range, _apply_max, finalize) are unit-tested; the
curses layer just drives them.
"""
import curses
import os
import sys

from . import cursesui, store
from .detector import EXERCISES

TRIGGERS = ["prompts", "time", "roulette"]
EXERCISE_MODES = ["choice", "random"]


def derive_reps_range(max_reps: int) -> tuple[int, int]:
    """A challenge should be repeatable many times a day: 25-50% of a one-set
    max, never below 2."""
    hi = min(50, max(3, round(max_reps * 0.5)))
    lo = min(max(2, round(max_reps * 0.25)), hi - 1)
    return lo, hi


def _apply_max(config: dict, ex: str, mx: int) -> None:
    """Set an exercise's enabled state + rep range from a one-set max
    (0 disables it)."""
    config["exercises"].setdefault(ex, {})
    if mx <= 0:
        config["exercises"][ex]["enabled"] = False
        return
    lo, hi = derive_reps_range(mx)
    config["exercises"][ex].update(enabled=True, reps_min=lo, reps_max=hi)


def _seed_maxes(config: dict) -> dict:
    """Per-exercise one-set max to show in the wizard, from the registry."""
    maxes = {}
    for ex, meta in EXERCISES.items():
        maxes[ex] = meta.get("default_max", 20)
    return maxes


def finalize(config: dict, maxes: dict, enabled: dict) -> dict:
    """Build the final config from the wizard's choices."""
    for ex in EXERCISES:
        _apply_max(config, ex, maxes[ex] if enabled.get(ex) else 0)
    if not any(c.get("enabled") for c in config["exercises"].values()):
        first = next(iter(EXERCISES))               # never leave nothing on
        _apply_max(config, first, maxes.get(first, 20) or 20)
    config["enabled"] = True
    config["preset"] = None
    return config


# ── curses layer ───────────────────────────────────────────────────────────

def _rows(enabled):
    rows = [("head_ex", None)]
    for ex in EXERCISES:
        rows.append(("exercise", ex))
    rows.append(("triggermode", None))
    rows.append(("triggerval", None))
    if sum(enabled.values()) > 1:
        rows.append(("pick", None))
    rows.append(("camera", None))
    rows.append(("finish", None))
    return rows


def _cycle(options, current, delta):
    return options[(options.index(current) + delta) % len(options)]


def _draw(scr, C, config, maxes, enabled, selected):
    scr.erase()
    cursesui.put(scr, 0, 2, "WORKOUT GATE", C["title"])
    cursesui.put(scr, 0, 16, "· setup", C["dim"])
    rows = _rows(enabled)
    y = 2
    for i, (kind, ex) in enumerate(rows):
        sel = i == selected
        attr = C["sel"] if sel else C["plain"]
        marker = "› " if sel else "  "
        if kind == "head_ex":
            cursesui.put(scr, y, 2, "EXERCISES", C["dim"])
            cursesui.put(scr, y, 14, "space toggle · ←/→ set your max", C["dim"])
        elif kind == "exercise":
            box = "[x]" if enabled[ex] else "[ ]"
            box_attr = C["ok"] if enabled[ex] else C["dim"]
            cursesui.put(scr, y, 2, marker, attr)
            cursesui.put(scr, y, 4, box, box_attr | (curses.A_REVERSE if sel else 0))
            if enabled[ex]:
                lo, hi = derive_reps_range(maxes[ex])
                cursesui.put(scr, y, 8, f"{ex:<9} max {maxes[ex]:<3}", attr)
                cursesui.put(scr, y, 25, f"→ {lo}-{hi} reps/challenge", C["ok"] if sel else C["dim"])
            else:
                cursesui.put(scr, y, 8, f"{ex:<9} off", C["dim"])
        elif kind == "triggermode":
            y += 1
            cursesui.put(scr, y, 2, marker, attr)
            cursesui.put(scr, y, 4, f"Trigger     {config['trigger']}", attr)
        elif kind == "triggerval":
            cursesui.put(scr, y, 2, marker, attr)
            cursesui.put(scr, y, 4, f"  {_trigger_val_label(config)}", attr)
        elif kind == "pick":
            y += 1
            cursesui.put(scr, y, 2, marker, attr)
            cursesui.put(scr, y, 4, f"Exercise pick   {config.get('exercise_mode', 'choice')}", attr)
        elif kind == "camera":
            y += 1
            cursesui.put(scr, y, 2, f"{marker}[ Camera test (2 reps) ]", attr | C["bold"])
        elif kind == "finish":
            cursesui.put(scr, y, 2, f"{marker}[ Save & finish ]", attr | C["bold"])
        y += 1
    h = scr.getmaxyx()[0]
    cursesui.put(scr, h - 1, 2,
                 "↑/↓ move   ←/→ change   space toggle   enter select   q cancel", C["dim"])
    scr.refresh()


def _trigger_val_label(config):
    t = config["trigger"]
    if t == "prompts":
        return f"every {config['every_n_prompts']} prompts"
    if t == "time":
        return f"every {config['time_interval_min']} min"
    return f"{config['roulette_chance_pct']:.0f}% chance per prompt"


def _adjust_trigger_val(config, delta):
    t = config["trigger"]
    if t == "prompts":
        config["every_n_prompts"] = max(1, min(99, config["every_n_prompts"] + delta))
    elif t == "time":
        config["time_interval_min"] = max(5, min(240, config["time_interval_min"] + 5 * delta))
    else:
        config["roulette_chance_pct"] = max(5, min(100, config["roulette_chance_pct"] + 5 * delta))


def _loop(scr, config, maxes, enabled):
    curses.curs_set(0)
    scr.keypad(True)
    C = cursesui.palette()
    selected = 1  # start on the first exercise
    while True:
        rows = _rows(enabled)
        selected = max(0, min(selected, len(rows) - 1))
        _draw(scr, C, config, maxes, enabled, selected)
        ch = scr.getch()
        kind, ex = rows[selected]
        if ch in (ord("q"), 27):
            return "cancel"
        elif ch in (curses.KEY_UP, ord("k")):
            selected -= 1
        elif ch in (curses.KEY_DOWN, ord("j")):
            selected += 1
        elif ch == ord(" ") and kind == "exercise":
            enabled[ex] = not enabled[ex]
        elif ch in (curses.KEY_LEFT, curses.KEY_RIGHT):
            delta = 1 if ch == curses.KEY_RIGHT else -1
            if kind == "exercise":
                maxes[ex] = max(0, min(200, maxes[ex] + delta * 2))
                enabled[ex] = maxes[ex] > 0
            elif kind == "triggermode":
                config["trigger"] = _cycle(TRIGGERS, config["trigger"], delta)
            elif kind == "triggerval":
                _adjust_trigger_val(config, delta)
            elif kind == "pick":
                config["exercise_mode"] = _cycle(EXERCISE_MODES, config.get("exercise_mode", "choice"), delta)
        elif ch in (ord("\n"), curses.KEY_ENTER):
            if kind == "camera":
                return "camera"
            if kind == "finish":
                return "finish"


def run() -> None:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        # No real terminal (e.g. Claude Code '!' prompt): apply sensible
        # defaults silently so the gate still works, and point the user at it.
        config = store.load_config()
        finalize(config, _seed_maxes(config),
                 {ex: True for ex in EXERCISES})
        store.save_config(config)
        print("Setup needs a real terminal for the interactive screen — applied "
              "defaults. Run 'workout setup' in a terminal to customize.")
        return

    os.environ.setdefault("ESCDELAY", "25")  # let curses parse arrow sequences
    config = store.load_config()
    maxes = _seed_maxes(config)
    enabled = {ex: config["exercises"].get(ex, {}).get("enabled", True) for ex in EXERCISES}
    while True:
        try:
            action = curses.wrapper(_loop, config, maxes, enabled)
        except curses.error:
            finalize(config, maxes, enabled)
            store.save_config(config)
            print("Saved defaults (terminal too small for the wizard).")
            return
        if action in ("cancel", None):
            print("Setup cancelled — nothing changed.")
            return
        if action == "finish":
            finalize(config, maxes, enabled)
            store.save_config(config)
            _post_finish(config)
            return
        if action == "camera":
            finalize(config, maxes, enabled)
            store.save_config(config)
            _camera_test(config)
            # loop back into the wizard


def _camera_test(config):
    from . import challenge
    ex = store.enabled_exercises(config)[0]
    print(f"Camera test: 2 {ex}. Window opening...")
    try:
        challenge.run_challenge([{"exercise": ex, "reps": 2}],
                                on_rep=lambda e: store.record_rep(e))
    except RuntimeError as e:
        print(f"  camera unavailable ({e}) — grant camera access, then: workout now")


def _post_finish(config):
    from . import installer
    if os.environ.get("WORKOUT_GATE_PLUGIN") == "1":
        installer._install_launcher()
    elif sys.stdin.isatty():
        pass  # project/global install handled by install.sh / `global on`
    slash = "/workout-gate:workout" if os.environ.get("WORKOUT_GATE_PLUGIN") == "1" else "/workout"
    active = ", ".join(store.enabled_exercises(config))
    print(f"\n  You're set — {active} enabled.")
    print(f"  workout        dashboard      workout now    force a challenge")
    print(f"  workout off    quick disable  ({slash} off / WORKOUT_GATE_OFF=1 also work)\n")
