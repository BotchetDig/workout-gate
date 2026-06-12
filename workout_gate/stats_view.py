"""Interactive stats viewer: left/right cycle through ALL + each exercise,
each with its own total, streak, record and 7-day chart. Stdlib curses.

Falls back to the static card (cli.render_stats) when there's no real
terminal (e.g. Claude Code's '!' prompt), so the same command works anywhere.
"""
import curses
import sys

from . import cursesui, store
from .detector import EXERCISES


def _views():
    return ["all"] + list(EXERCISES)


def _view_data(stats, view):
    """Return (title, total, day_counts) for the selected view."""
    if view == "all":
        return "ALL", stats.get("total_reps", 0), stats.get("by_day", {})
    label = EXERCISES.get(view, {}).get("label", view.upper())
    return label, stats.get("by_exercise", {}).get(view, 0), store.day_counts(stats, view)


def _bar(value, maxv, width):
    return cursesui.bar(value, maxv, width)


def _draw(scr, C, stats, idx):
    scr.erase()
    put = cursesui.put
    views = _views()
    view = views[idx]
    title, total, day_counts = _view_data(stats, view)
    streak = store.streak_days(day_counts)
    record = store.best_day(day_counts)
    days = store.last_days(day_counts)
    day_max = max((n for _, n in days), default=0)

    put(scr, 0, 2, "WORKOUT GATE", C["title"])
    put(scr, 0, 16, "· stats", C["dim"])
    put(scr, 2, 2, f"◀  {title}  ▶", C["sel"])
    put(scr, 2, 26, f"({idx + 1}/{len(views)})", C["dim"])

    put(scr, 4, 2, "Total   ", C["dim"])
    put(scr, 4, 10, str(total), C["bold"])
    put(scr, 5, 2, f"Streak  {streak} day" + ("s" if streak != 1 else "")
        + (" 🔥" if streak > 0 else ""))
    if record:
        put(scr, 6, 2, f"Record  {record[1]}  ({record[0][5:]})")

    put(scr, 8, 2, "Last 7 days", C["dim"])
    for i, (d, n) in enumerate(days):
        put(scr, 9 + i, 2, f"{d[5:]}  ", C["dim"])
        put(scr, 9 + i, 9, cursesui.bar(n, day_max, 20), C["ok"] if n else C["dim"])
        put(scr, 9 + i, 31, str(n), C["bold"] if n else C["dim"])

    put(scr, 9 + len(days) + 1, 2, "←/→ switch exercise   q quit", C["dim"])
    scr.refresh()


def _loop(scr):
    curses.curs_set(0)
    scr.keypad(True)
    C = cursesui.palette()
    idx = 0
    n = len(_views())
    while True:
        _draw(scr, C, store.load_stats(), idx)
        ch = scr.getch()
        if ch in (ord("q"), 27):
            return
        elif ch in (curses.KEY_LEFT, ord("h")):
            idx = (idx - 1) % n
        elif ch in (curses.KEY_RIGHT, ord("l")):
            idx = (idx + 1) % n


def main():
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        from .cli import render_stats
        print(render_stats(store.load_stats(), color=sys.stdout.isatty()))
        return
    try:
        curses.wrapper(_loop)
    except curses.error:
        from .cli import render_stats
        print(render_stats(store.load_stats(), color=True))
