"""Config, state and stats persistence. No webcam, no UI knowledge.

All writes are atomic (temp file + os.replace) so an interruption mid-challenge
never corrupts history. Data lives in ~/.workout-gate/ (override with the
WORKOUT_GATE_DIR env var, mainly for tests).
"""
import copy
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
    # per-exercise enable + rep range; add an exercise here and in detector.EXERCISES
    "exercises": {
        "pushups": {"enabled": True, "reps_min": 5, "reps_max": 10},
        "squats": {"enabled": True, "reps_min": 8, "reps_max": 15},
    },
    "exercise_mode": "choice",  # "choice": pick in the window | "random": picked for you
    "debug": False,             # overlay the detected skeleton + live angle/state
    "preset": None,
    "mode": "sync",  # "sync": hook waits for the challenge; "detached": window opens, prompt must be resent
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
    # Migrate legacy top-level reps_min/reps_max (pre-squats) into pushups.
    if "exercises" not in (_raw_config() or {}):
        config["exercises"] = {
            "pushups": {"enabled": True,
                        "reps_min": config.get("reps_min", 5),
                        "reps_max": config.get("reps_max", 10)},
            "squats": dict(DEFAULT_CONFIG["exercises"]["squats"]),
        }
    else:
        # Fill in any exercise/field added in a newer version.
        for name, defaults in DEFAULT_CONFIG["exercises"].items():
            config["exercises"].setdefault(name, dict(defaults))
            for k, v in defaults.items():
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
    save_stats(stats)


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
