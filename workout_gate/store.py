"""Config, state and stats persistence. No webcam, no UI knowledge.

All writes are atomic (temp file + os.replace) so an interruption mid-challenge
never corrupts history. Data lives in ~/.workout-gate/ (override with the
WORKOUT_GATE_DIR env var, mainly for tests).
"""
from __future__ import annotations  # PEP 604 (str | None) on Python 3.9

import copy
import datetime
import json
import os
from pathlib import Path

from .detector import EXERCISES, default_exercises_config

DEFAULT_CONFIG = {
    "enabled": True,
    "trigger": "prompts",  # "prompts" | "time" | "roulette"
    "every_n_prompts": 15,
    "time_interval_min": 30,
    "roulette_chance_pct": 10,
    # per-exercise enable + rep range, derived from the detector.EXERCISES
    # registry — add an exercise there and it shows up here automatically.
    "exercises": default_exercises_config(),
    "exercise_mode": "choice",  # "choice": pick in the window | "random": picked for you
    "debug": False,             # overlay the detected skeleton + live angle/state
    "preset": None,
}

DEFAULT_STATE = {
    "prompt_count": 0,
    "debt_offers": [],          # [{"exercise","reps"}, ...] — challenge created, exercise not yet chosen
    "debt_reps": 0,             # remaining reps of the chosen exercise (0 = none/not chosen)
    "debt_exercise": "pushups",
    "last_challenge_ts": 0,
}

DEFAULT_STATS = {
    "total_reps": 0,
    "by_day": {},          # date -> total reps that day (all exercises)
    "by_exercise": {},     # exercise -> lifetime total
    "by_day_ex": {},       # date -> {exercise -> reps that day}
}


def data_dir() -> Path:
    d = Path(os.environ.get("WORKOUT_GATE_DIR", Path.home() / ".workout-gate"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load(name: str, defaults: dict) -> dict:
    path = data_dir() / name
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
    # deepcopy defaults so nested mutables (by_day, exercises...) are never
    # aliased to the module-level DEFAULT_* dicts and mutated across calls.
    return {**copy.deepcopy(defaults), **data}


def _save(name: str, data: dict) -> None:
    path = data_dir() / name
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, path)


def load_config() -> dict:
    config = _load("config.json", DEFAULT_CONFIG)
    defaults = default_exercises_config()
    if "exercises" not in (_raw_config() or {}):
        # Pre-squats config: seed pushups from legacy top-level reps_min/max.
        config["exercises"] = defaults
        if "reps_min" in config:
            config["exercises"]["pushups"].update(
                reps_min=config["reps_min"], reps_max=config["reps_max"])
    else:
        # Fill in any exercise/field added in a newer version (new registry entries).
        for name, d in defaults.items():
            config["exercises"].setdefault(name, dict(d))
            for k, v in d.items():
                config["exercises"][name].setdefault(k, v)
    config.pop("reps_min", None)
    config.pop("reps_max", None)
    return config


def _raw_config() -> dict:
    path = data_dir() / "config.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_config(config: dict) -> None:
    _save("config.json", config)


def enabled_exercises(config: dict) -> list:
    """Names of enabled exercises, in registry order; never empty."""
    names = [n for n, c in config["exercises"].items() if c.get("enabled")]
    return names or ["pushups"]


def load_state() -> dict:
    return _load("state.json", DEFAULT_STATE)


def save_state(state: dict) -> None:
    _save("state.json", state)


def load_stats() -> dict:
    return _load("stats.json", DEFAULT_STATS)


def save_stats(stats: dict) -> None:
    _save("stats.json", stats)


def today() -> str:
    return datetime.date.today().isoformat()


def record_rep(exercise: str = "pushups") -> None:
    """Record one completed rep. Called after every rep so an interruption
    keeps everything done so far."""
    stats = load_stats()
    stats["total_reps"] += 1
    stats["by_day"][today()] = stats["by_day"].get(today(), 0) + 1
    stats["by_exercise"][exercise] = stats["by_exercise"].get(exercise, 0) + 1
    day_ex = stats.setdefault("by_day_ex", {}).setdefault(today(), {})
    day_ex[exercise] = day_ex.get(exercise, 0) + 1
    save_stats(stats)


def day_counts(stats: dict, exercise: str | None = None) -> dict:
    """date -> reps. exercise=None gives the combined daily totals; a name
    gives that exercise's daily counts (only from when per-exercise tracking
    began)."""
    if exercise is None:
        return stats.get("by_day", {})
    return {d: exs.get(exercise, 0) for d, exs in stats.get("by_day_ex", {}).items()}


def write_challenge_pid() -> None:
    (data_dir() / "challenge.pid").write_text(str(os.getpid()))


def clear_challenge_pid() -> None:
    (data_dir() / "challenge.pid").unlink(missing_ok=True)


def running_challenge_pid() -> int | None:
    """PID of a live challenge process, or None. Cleans up stale files."""
    path = data_dir() / "challenge.pid"
    try:
        pid = int(path.read_text())
        os.kill(pid, 0)  # existence check, no signal sent
        return pid
    except (OSError, ValueError):
        path.unlink(missing_ok=True)
        return None


def streak_days(by_day: dict, ref: str | None = None) -> int:
    """Consecutive days with at least one rep, ending today (or yesterday if
    today has none yet — an ongoing streak isn't broken at midnight)."""
    day = datetime.date.fromisoformat(ref or today())
    if by_day.get(day.isoformat(), 0) <= 0:
        day -= datetime.timedelta(days=1)
    streak = 0
    while by_day.get(day.isoformat(), 0) > 0:
        streak += 1
        day -= datetime.timedelta(days=1)
    return streak


def best_day(by_day: dict):
    """(date, reps) of the record day, or None if no reps ever."""
    if not by_day:
        return None
    date = max(by_day, key=lambda d: by_day[d])
    return date, by_day[date]


def last_days(by_day: dict, n: int = 7, ref: str | None = None) -> list:
    """[(date, reps)] for the last n days, oldest first."""
    end = datetime.date.fromisoformat(ref or today())
    return [
        ((end - datetime.timedelta(days=i)).isoformat(),
         by_day.get((end - datetime.timedelta(days=i)).isoformat(), 0))
        for i in range(n - 1, -1, -1)
    ]
