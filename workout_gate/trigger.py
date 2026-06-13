"""Decides when a challenge is due. Pure logic, no I/O, no webcam.

Three trigger modes:
- "prompts": every N prompts (default)
- "time": at most one challenge per X minutes of activity
- "roulette": each prompt has a P% chance — you never know
A pending debt always means due, whatever the mode.
"""
from __future__ import annotations  # PEP 604 (float | None) on Python 3.9

import random
import time


def challenge_due(config: dict, state: dict, now: float | None = None) -> bool:
    """state['prompt_count'] must already include the current prompt.
    May mutate state (time-mode initialization); caller persists it."""
    if state.get("debt_reps", 0) > 0 or state.get("debt_offers"):
        return True

    mode = config.get("trigger", "prompts")
    if mode == "time":
        now = now if now is not None else time.time()
        last = state.get("last_challenge_ts", 0)
        if last <= 0:
            # first prompt in time mode: start the clock, don't punish immediately
            state["last_challenge_ts"] = now
            return False
        return now - last >= config["time_interval_min"] * 60
    if mode == "roulette":
        return random.random() * 100 < config["roulette_chance_pct"]
    return state["prompt_count"] >= config["every_n_prompts"]


# Reps are expressed as a multiplier of each exercise's registry default range,
# so a preset automatically sizes any exercise — including ones added later.
PRESETS = {
    "chill": {"trigger": "prompts", "every_n_prompts": 25, "reps_mult": 0.6},
    "demo": {"trigger": "prompts", "every_n_prompts": 1, "reps_mult": 1.0},
    "hardcore": {"trigger": "prompts", "every_n_prompts": 5, "reps_mult": 2.2},
}


def apply_preset(config: dict, name: str) -> dict:
    from .detector import EXERCISES
    preset = PRESETS[name]
    config["trigger"] = preset["trigger"]
    config["every_n_prompts"] = preset["every_n_prompts"]
    mult = preset["reps_mult"]
    for ex, ec in config["exercises"].items():
        base = EXERCISES.get(ex, {}).get("default_reps", (ec["reps_min"], ec["reps_max"]))
        ec["reps_min"] = max(1, round(base[0] * mult))
        ec["reps_max"] = max(ec["reps_min"], round(base[1] * mult))
    config["preset"] = name
    return config
