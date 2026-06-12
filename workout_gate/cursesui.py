"""Shared curses styling so every interactive screen (dashboard, stats,
wizard) looks the same: one palette, one safe draw helper. Degrades to
monochrome attributes if the terminal has no colors."""
import curses


def palette() -> dict:
    """Call once inside curses.wrapper. Returns named attributes."""
    try:
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_GREEN, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        curses.init_pair(4, curses.COLOR_RED, -1)
        cyan, green, yellow, red = (curses.color_pair(i) for i in (1, 2, 3, 4))
    except curses.error:
        cyan = green = yellow = red = 0
    return {
        "title": cyan | curses.A_BOLD,
        "ok": green,
        "warn": yellow,
        "bad": red,
        "bold": curses.A_BOLD,
        "dim": curses.A_DIM,
        "sel": curses.A_REVERSE | curses.A_BOLD,
        "plain": 0,
    }


def put(scr, y, x, text, attr=0):
    """addstr that never raises if it runs past the window edge."""
    try:
        scr.addstr(y, x, text, attr)
    except curses.error:
        pass


def bar(value, maxv, width):
    filled = round(width * value / maxv) if maxv > 0 else 0
    return "█" * filled + "░" * (width - filled)
