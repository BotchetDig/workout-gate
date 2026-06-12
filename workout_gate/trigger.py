"""Decides when a challenge is due. Pure logic, no I/O, no webcam.

Three trigger modes:
- "prompts": every N prompts (default)
- "time": at most one challenge per X minutes of activity
- "roulette": each prompt has a P% chance — you never know
A pending debt always means due, whatever the mode.
"""
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


PRESETS = {
    # everyday real use: rare, light
    "chill": {"trigger": "prompts", "every_n_prompts": 25,
              "reps": {"pushups": (3, 6), "squats": (5, 10)}},
    # filming: every prompt, readable rep counts
    "demo": {"trigger": "prompts", "every_n_prompts": 1,
             "reps": {"pushups": (5, 8), "squats": (8, 12)}},
    # for people who want to suffer
    "hardcore": {"trigger": "prompts", "every_n_prompts": 5,
                 "reps": {"pushups": (15, 25), "squats": (20, 35)}},
}


def apply_preset(config: dict, name: str) -> dict:
    preset = PRESETS[name]
    config["trigger"] = preset["trigger"]
    config["every_n_prompts"] = preset["every_n_prompts"]
    for ex, (lo, hi) in preset["reps"].items():
        config["exercises"].setdefault(ex, {"enabled": True})
        config["exercises"][ex]["reps_min"] = lo
        config["exercises"][ex]["reps_max"] = hi
    config["preset"] = name
    return config
