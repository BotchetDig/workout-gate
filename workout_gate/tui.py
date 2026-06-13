"""Full-screen terminal dashboard: arrow-key navigation over every setting,
live stats, and a shortcut to force a challenge. Stdlib curses only.

Run with: python -m workout_gate ui
Keys: up/down navigate - left/right change value - enter/space activate - q quit
"""
import curses
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from . import cursesui, store
from .trigger import PRESETS, apply_preset

SPARK = "▁▂▃▄▅▆▇█"
TRIGGERS = ["prompts", "time", "roulette"]
EXERCISE_MODES = ["choice", "random"]
PRESET_CYCLE = [None, "chill", "demo", "hardcore"]


def _cycle(options, current, delta):
    return options[(options.index(current) + delta) % len(options)]


def _adjust(config, key, delta):
    """Apply a left/right change to one settings row. Mutates config.
    Manual changes clear the active preset (except pure navigation)."""
    touched_preset = True
    if key == "enabled":
        config["enabled"] = not config["enabled"]
        touched_preset = False
    elif key == "preset":
        name = _cycle(PRESET_CYCLE, config.get("preset"), delta)
        if name:
            apply_preset(config, name)
        else:
            config["preset"] = None
        return
    elif key == "trigger":
        config["trigger"] = _cycle(TRIGGERS, config["trigger"], delta)
    elif key == "every_n_prompts":
        config[key] = max(1, min(99, config[key] + delta))
    elif key == "time_interval_min":
        config[key] = max(5, min(240, config[key] + 5 * delta))
    elif key == "roulette_chance_pct":
        config[key] = max(5, min(100, config[key] + 5 * delta))
    elif key == "exercise_mode":
        config["exercise_mode"] = _cycle(EXERCISE_MODES, config.get("exercise_mode", "choice"), delta)
        touched_preset = False
    elif key == "debug":
        config["debug"] = not config.get("debug", False)
        touched_preset = False
    elif key.startswith("enable:"):
        ex = key.split(":", 1)[1]
        config["exercises"][ex]["enabled"] = not config["exercises"][ex].get("enabled")
        touched_preset = False
    elif key.startswith("repsmin:"):
        ex = key.split(":", 1)[1]
        ec = config["exercises"][ex]
        ec["reps_min"] = max(1, min(ec["reps_max"], ec["reps_min"] + delta))
    elif key.startswith("repsmax:"):
        ex = key.split(":", 1)[1]
        ec = config["exercises"][ex]
        ec["reps_max"] = max(ec["reps_min"], min(50, ec["reps_max"] + delta))
    if touched_preset:
        config["preset"] = None


def _rows(config):
    active = config["trigger"]
    rows = [
        ("Gate", "ON" if config["enabled"] else "OFF", "enabled"),
        ("Preset", config.get("preset") or "-", "preset"),
        ("Trigger", config["trigger"], "trigger"),
        ("  every N prompts", f"{config['every_n_prompts']}" + (" *" if active == "prompts" else ""), "every_n_prompts"),
        ("  time interval", f"{config['time_interval_min']} min" + (" *" if active == "time" else ""), "time_interval_min"),
        ("  roulette chance", f"{config['roulette_chance_pct']:.0f}%" + (" *" if active == "roulette" else ""), "roulette_chance_pct"),
        ("Exercise pick", config.get("exercise_mode", "choice"), "exercise_mode"),
    ]
    for ex, ec in config["exercises"].items():
        on = "on " if ec.get("enabled") else "off"
        rows.append((f"  {ex}", on, f"enable:{ex}"))
        rows.append((f"    {ex} reps min", str(ec["reps_min"]), f"repsmin:{ex}"))
        rows.append((f"    {ex} reps max", str(ec["reps_max"]), f"repsmax:{ex}"))
    rows += [
        ("Debug overlay", "on " if config.get("debug") else "off", "debug"),
        ("Force a challenge now", "", "@challenge"),
        ("Quit", "", "@quit"),
    ]
    return rows


def _sparkline(days):
    top = max((n for _, n in days), default=0)
    if top == 0:
        return SPARK[0] * len(days)
    return "".join(SPARK[min(7, int(n / top * 7 + 0.5))] for _, n in days)


def _draw(scr, C, config, state, selected, message):
    scr.erase()
    put = cursesui.put
    h, w = scr.getmaxyx()

    put(scr, 0, 2, "WORKOUT GATE", C["title"])
    from . import challenge
    headline = f"debt: {challenge.pending_summary(state)}" if (
        state.get("debt_reps") or state.get("debt_offers")) else "no debt"
    if config["trigger"] == "prompts":
        headline += f"  -  prompts: {state['prompt_count']}/{config['every_n_prompts']}"
    put(scr, 0, 16, headline, C["dim"])

    for i, (label, value, key) in enumerate(_rows(config)):
        y = 2 + i + (1 if key.startswith("@") else 0)
        marker = "› " if i == selected else "  "
        attr = C["sel"] if i == selected else C["plain"]
        if key.startswith("@"):
            put(scr, y, 2, f"{marker}[ {label} ]", attr | C["bold"])
        else:
            put(scr, y, 2, f"{marker}{label:<20} ", attr)
            put(scr, y, 24, f"{value:<12}", attr if i == selected else C["ok"])

    stats = store.load_stats()
    by_day = stats["by_day"]
    days = store.last_days(by_day)
    record = store.best_day(by_day)
    sy = 2 + len(_rows(config)) + 2
    put(scr, sy, 2, "STATS", C["title"])
    put(scr, sy + 1, 2,
        f"total {stats['total_reps']}  -  today {by_day.get(store.today(), 0)}"
        f"  -  streak {store.streak_days(by_day)}d"
        + (f"  -  record {record[1]} ({record[0][5:]})" if record else ""))
    put(scr, sy + 2, 2, "last 7 days  ", C["dim"])
    put(scr, sy + 2, 15, _sparkline(days), C["ok"])
    put(scr, sy + 2, 15 + len(days) + 2, f"({days[0][0][5:]} to {days[-1][0][5:]})", C["dim"])

    if message:
        put(scr, sy + 4, 2, message, C["warn"] | C["bold"])
    put(scr, h - 1, 2, "↑/↓ navigate   ←/→ change   enter select   q quit", C["dim"])
    scr.refresh()


def _menu(scr, message=""):
    curses.curs_set(0)
    scr.keypad(True)
    C = cursesui.palette()
    selected = 0
    while True:
        config = store.load_config()
        rows = _rows(config)
        _draw(scr, C, config, store.load_state(), selected, message)
        ch = scr.getch()
        message = ""
        if ch in (ord("q"), 27):
            return "quit"
        if ch in (curses.KEY_UP, ord("k")):
            selected = (selected - 1) % len(rows)
        elif ch in (curses.KEY_DOWN, ord("j")):
            selected = (selected + 1) % len(rows)
        elif ch in (curses.KEY_LEFT, curses.KEY_RIGHT, ord("\n"), curses.KEY_ENTER, ord(" ")):
            key = rows[selected][2]
            if key == "@quit":
                return "quit"
            if key == "@challenge":
                return "challenge"
            delta = -1 if ch == curses.KEY_LEFT else 1
            _adjust(config, key, delta)
            store.save_config(config)


def _no_tty_fallback():
    """Called from Claude Code's '!' prompt or a pipe: pop the dashboard in a
    real Terminal window instead (macOS), or explain the alternatives."""
    wrapper = Path(__file__).resolve().parent.parent / "workout"
    if sys.platform == "darwin" and wrapper.exists():
        runner = _write_dashboard_runner(wrapper)
        script = f'tell application "Terminal"\nactivate\ndo script "\'{runner}\'"\nend tell'
        try:
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10, check=True)
            print("Dashboard opened in a new Terminal window.")
            return
        except (OSError, subprocess.SubprocessError):
            pass
    print("The dashboard needs a real terminal (Terminal, iTerm...).\n"
          "Quick alternatives that work anywhere:\n"
          "  workout now      start a challenge\n"
          "  workout stats    totals, streak, record\n"
          "  workout status   current settings")


def _write_dashboard_runner(wrapper: Path) -> Path:
    """Script run inside the popped Terminal window: dashboard, then the
    window closes itself (a detached osascript closes the window owning this
    shell's tty - 'whose' filters on nested properties silently fail, hence
    the explicit loop; the tty goes through argv to avoid quoting)."""
    runner = Path(tempfile.gettempdir()) / "workout-gate-dashboard.sh"
    runner.write_text(f"""#!/bin/sh
clear
'{wrapper}'
exec osascript -e 'on run argv
tell application "Terminal"
repeat with w in windows
try
if tty of selected tab of w is (item 1 of argv) then close w
end try
end repeat
end tell
end run' "$(tty)" >/dev/null 2>&1
""")
    runner.chmod(0o755)
    return runner


def main():
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        _no_tty_fallback()
        return
    os.environ.setdefault("ESCDELAY", "25")  # snappy ESC
    message = ""
    while True:
        try:
            action = curses.wrapper(_menu, message)
        except curses.error:
            _no_tty_fallback()
            return
        if action != "challenge":
            return
        # leave curses entirely before opening the webcam window
        from . import challenge
        state = store.load_state()
        reps = state["debt_reps"] or challenge.new_debt()
        try:
            ok = challenge.settle_debt()
        except Exception as e:
            message = f"Challenge failed: {e}"
            continue
        message = (f"Validated! {reps} pushups done." if ok
                   else f"Aborted - {store.load_state()['debt_reps']} reps still owed.")
