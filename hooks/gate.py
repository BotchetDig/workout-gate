#!/usr/bin/env python3
"""UserPromptSubmit hook: the gate itself.

Exit 0 = prompt goes through. Exit 2 = prompt blocked (stderr shown to user).

Escape hatches (non-negotiable):
- prompts starting with /workout are whitelisted (so you can always turn it off)
- WORKOUT_GATE_OFF=1 env var bypasses everything
- config enabled=false bypasses
- any unexpected error -> FAIL OPEN: prompt goes through, error logged to
  ~/.workout-gate/gate.log. A broken webcam must never lock you out.
"""
import hashlib
import json
import os
import sys
import time
import traceback
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from workout_gate import store, trigger  # noqa: E402


def log(msg: str) -> None:
    try:
        with (store.data_dir() / "gate.log").open("a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except OSError:
        pass


def duplicate_invocation(payload: dict, window_s: float = 5.0) -> bool:
    """True if another gate hook already handled this very prompt (the gate
    can be wired as plugin AND project/global hook at once - count it once)."""
    raw = f"{payload.get('session_id', '')}:{payload.get('prompt', '')}"
    key = hashlib.md5(raw.encode()).hexdigest()
    path = store.data_dir() / "last-gate"
    now = time.time()
    try:
        prev_key, prev_ts = path.read_text().split(" ")
        if prev_key == key and now - float(prev_ts) < window_s:
            return True
    except (OSError, ValueError):
        pass
    path.write_text(f"{key} {now}")
    return False


def main() -> int:
    if os.environ.get("WORKOUT_GATE_OFF") == "1":
        return 0

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = {}
    prompt = (payload.get("prompt") or "").strip()
    if prompt.startswith("/workout"):
        return 0

    config = store.load_config()
    if not config["enabled"]:
        return 0

    if duplicate_invocation(payload):
        return 0

    state = store.load_state()
    state["prompt_count"] += 1
    due = trigger.challenge_due(config, state)
    store.save_state(state)
    if not due:
        return 0

    from workout_gate import challenge

    # Persist the debt BEFORE opening the window: closing everything mid-
    # challenge keeps it owed for the next session.
    if state["debt_reps"] <= 0 and not state.get("debt_offers"):
        challenge.new_debt()
    owed = challenge.pending_summary(store.load_state())
    log(f"challenge triggered: {owed} owed (prompt_count={state['prompt_count']})")

    if challenge.settle_debt():
        print(f"[workout-gate] The user just did {owed} to send this prompt.")
        return 0
    remaining = challenge.pending_summary(store.load_state())
    print(
        f"WORKOUT GATE: challenge aborted, {remaining} still owed. "
        "Resend your prompt to retry (or ! workout off, no judgment).",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log("FAIL-OPEN:\n" + traceback.format_exc())
        sys.exit(0)
