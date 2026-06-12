"""Full-screen terminal dashboard: arrow-key navigation over every setting,
live stats, and a shortcut to force a challenge. Stdlib curses only.

Run with: python -m workout_gate ui
Keys: up/down navigate - left/right change value - enter/space activate - q quit
"""
import curses
import os

from . import store
from .trigger import PRESETS, apply_preset

SPARK = "▁▂▃▄▅▆▇█"
TRIGGERS = ["prompts", "time", "roulette"]
MODES = ["sync", "detached"]
PRESET_CYCLE = [None, "chill", "demo", "hardcore"]


def _cycle(options, current, delta):
    return options[(options.index(current) + delta) % len(options)]


PRESET_KEYS = {"trigger", "every_n_prompts", "time_interval_min", "roulette_chance_pct",
               "reps_min", "reps_max"}


def _adjust(config, key, delta):
    """Apply a left/right change to one settings row. Mutates config."""
    if key == "enabled":
        config["enabled"] = not config["enabled"]
    elif key == "preset":
        name = _cycle(PRESET_CYCLE, config.get("preset"), delta)
        if name:
            apply_preset(config, name)
        else:
            config["preset"] = None
    elif key == "trigger":
        config["trigger"] = _cycle(TRIGGERS, config["trigger"], delta)
    elif key == "every_n_prompts":
        config[key] = max(1, min(99, config[key] + delta))
    elif key == "time_interval_min":
        config[key] = max(5, min(240, config[key] + 5 * delta))
    elif key == "roulette_chance_pct":
        config[key] = max(5, min(100, config[key] + 5 * delta))
    elif key == "reps_min":
        config[key] = max(1, min(config["reps_max"], config[key] + delta))
    elif key == "reps_max":
        config[key] = max(config["reps_min"], min(50, config[key] + delta))
    elif key == "mode":
        config["mode"] = _cycle(MODES, config["mode"], delta)
    if key in PRESET_KEYS:
        config["preset"] = None  # manual change leaves preset land


def _rows(config):
    active = config["trigger"]
    return [
        ("Gate", "ON" if config["enabled"] else "OFF", "enabled"),
        ("Preset", config.get("preset") or "-", "preset"),
        ("Trigger", config["trigger"], "trigger"),
        ("  every N prompts", f"{config['every_n_prompts']}" + (" *" if active == "prompts" else ""), "every_n_prompts"),
        ("  time interval", f"{config['time_interval_min']} min" + (" *" if active == "time" else ""), "time_interval_min"),
        ("  roulette chance", f"{config['roulette_chance_pct']:.0f}%" + (" *" if active == "roulette" else ""), "roulette_chance_pct"),
        ("Reps min", str(config["reps_min"]), "reps_min"),
        ("Reps max", str(config["reps_max"]), "reps_max"),
        ("Mode", config["mode"], "mode"),
        ("Force a challenge now", "", "@challenge"),
        ("Quit", "", "@quit"),
    ]


def _sparkline(days):
    top = max((n for _, n in days), default=0)
    if top == 0:
        return SPARK[0] * len(days)
    return "".join(SPARK[min(7, int(n / top * 7 + 0.5))] for _, n in days)


def _put(scr, y, x, text, attr=0):
    try:
        scr.addstr(y, x, text, attr)
    except curses.error:
        pass  # terminal too small; drop what doesn't fit


def _draw(scr, config, state, selected, message):
    scr.erase()
    h, w = scr.getmaxyx()
    bold, dim = curses.A_BOLD, curses.A_DIM

    _put(scr, 0, 2, "WORKOUT GATE", bold)
    debt = state["debt_reps"]
    headline = f"debt: {debt} {state['debt_exercise']}" if debt else "no debt"
    if config["trigger"] == "prompts":
        headline += f"  -  prompts: {state['prompt_count']}/{config['every_n_prompts']}"
    _put(scr, 0, 16, headline, dim)

    for i, (label, value, key) in enumerate(_rows(config)):
        y = 2 + i + (1 if key.startswith("@") else 0)
        marker = "> " if i == selected else "  "
        attr = curses.A_REVERSE if i == selected else 0
        if key.startswith("@"):
            _put(scr, y, 2, f"{marker}[ {label} ]", attr | bold)
        else:
            _put(scr, y, 2, f"{marker}{label:<20} {value:<12}", attr)

    stats = store.load_stats()
    by_day = stats["by_day"]
    days = store.last_days(by_day)
    record = store.best_day(by_day)
    sy = 2 + len(_rows(config)) + 2
    _put(scr, sy, 2, "STATS", bold)
    _put(scr, sy + 1, 2,
         f"total {stats['total_reps']}  -  today {by_day.get(store.today(), 0)}"
         f"  -  streak {store.streak_days(by_day)}d"
         + (f"  -  record {record[1]} ({record[0][5:]})" if record else ""))
    _put(scr, sy + 2, 2, f"last 7 days  {_sparkline(days)}  ({days[0][0][5:]} to {days[-1][0][5:]})")

    if message:
        _put(scr, sy + 4, 2, message, bold)
    _put(scr, h - 1, 2, "up/down navigate - left/right change - enter select - q quit", dim)
    scr.refresh()


def _menu(scr, message=""):
    curses.curs_set(0)
    scr.keypad(True)
    selected = 0
    while True:
        config = store.load_config()
        rows = _rows(config)
        _draw(scr, config, store.load_state(), selected, message)
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


def main():
    os.environ.setdefault("ESCDELAY", "25")  # snappy ESC
    message = ""
    while True:
        action = curses.wrapper(_menu, message)
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
