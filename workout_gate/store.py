"""Config, state and stats persistence. No webcam, no UI knowledge.

All writes are atomic (temp file + os.replace) so an interruption mid-challenge
never corrupts history. Data lives in ~/.workout-gate/ (override with the
WORKOUT_GATE_DIR env var, mainly for tests).
"""
import datetime
import json
import os
from pathlib import Path

DEFAULT_CONFIG = {
    "enabled": True,
    "trigger": "prompts",  # "prompts" | "time" | "roulette"
    "every_n_prompts": 15,
    "time_interval_min": 30,
    "roulette_chance_pct": 10,
    "reps_min": 5,
    "reps_max": 10,
    "preset": None,
    "mode": "sync",  # "sync": hook waits for the challenge; "detached": window opens, prompt must be resent
}

DEFAULT_STATE = {
    "prompt_count": 0,
    "debt_reps": 0,
    "debt_exercise": "pushups",
    "last_challenge_ts": 0,
}

DEFAULT_STATS = {
    "total_reps": 0,
    "by_day": {},
    "by_exercise": {},
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
    return {**defaults, **data}


def _save(name: str, data: dict) -> None:
    path = data_dir() / name
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, path)


def load_config() -> dict:
    return _load("config.json", DEFAULT_CONFIG)


def save_config(config: dict) -> None:
    _save("config.json", config)


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
    save_stats(stats)


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
