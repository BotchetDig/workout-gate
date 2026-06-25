#!/usr/bin/env python3
"""UserPromptSubmit hook: the gate itself.

Shared by supported surfaces — Claude Code CLI + desktop and Codex CLI — all
running this one file against the one runtime in ~/.workout-gate/. Codex's
UserPromptSubmit payload carries the same prompt/session_id (plus turn_id), so
no per-tool shim is needed here. Codex Desktop currently discovers hooks but did
not run this event in local testing.

Exit 0 = prompt goes through. Exit 2 = prompt blocked (stderr shown to user).

Escape hatches (non-negotiable):
- gate-management prompts are whitelisted so you can always turn it off:
  `/workout ...` (Claude slash command) AND the bare-word `workout ...` / `wg ...`
  forms (Codex may swallow a leading `/` as a UI command before the hook sees it)
- WORKOUT_GATE_OFF=1 env var bypasses everything
- config enabled=false bypasses
- a challenge already running in another tool/session -> fail open (no second
  webcam window); the debt stays pending and gates again later
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


def _is_escape(prompt: str) -> bool:
    """Gate-management prompts are never blocked, so you can always turn it off.
    `/workout` is the Claude slash command; the bare `workout`/`wg` forms are the
    fallback for Codex, where a leading `/` may be captured as a UI command
    before it ever reaches this hook."""
    p = prompt.strip().lower()
    return (p.startswith("/workout") or p in ("workout", "wg")
            or p.startswith("workout ") or p.startswith("wg "))


def _source(payload: dict) -> str:
    """Which tool is making the user pay right now — drives the speaker name on
    the challenge window (same voice, just the tag). Priority: an explicit
    WORKOUT_GATE_SOURCE (set by the Codex project/global hook configs we write);
    then the plugin path (Codex exposes a bare PLUGIN_ROOT, Claude only ever sets
    CLAUDE_PLUGIN_ROOT); then a payload hint (non-Claude model); else Claude."""
    env = os.environ.get("WORKOUT_GATE_SOURCE")
    if env:
        return env.lower()
    if os.environ.get("PLUGIN_ROOT"):
        return "codex"
    model = (payload.get("model") or "").lower()
    if model and not model.startswith("claude"):
        return "codex"
    return "claude"


def duplicate_invocation(payload: dict, window_s: float = 5.0) -> bool:
    """True if another gate hook already handled this very prompt (the gate
    can be wired as plugin AND project/global hook at once - count it once).
    Keyed on session+turn+prompt: Codex provides turn_id, which pins the dedup
    to a single turn even if the same prompt text recurs."""
    raw = (f"{payload.get('session_id', '')}:{payload.get('turn_id', '')}:"
           f"{payload.get('prompt', '')}")
    key = hashlib.md5(raw.encode()).hexdigest()
    path = store.data_dir() / "last-gate"
    now = time.time()
    # check-and-set under the shared lock, or plugin + global firing the same
    # prompt in parallel can both read a stale file and both pass.
    with store.locked():
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
    if _is_escape(payload.get("prompt") or ""):
        return 0

    config = store.load_config()
    if not config["enabled"]:
        return 0

    if duplicate_invocation(payload):
        return 0

    # Bump the prompt counter and decide under a cross-process lock so two tools
    # firing at once can't lose an increment or both trigger.
    def _bump(state):
        state["prompt_count"] += 1
        return trigger.challenge_due(config, state)
    due = store.mutate_state(_bump)
    if not due:
        return 0

    # Single-flight across tools: atomically claim the one challenge slot. If a
    # challenge is already active (another Claude/Codex session) this returns
    # False -> fail open (no second webcam window). The debt stays pending and
    # gates again once the active challenge is settled.
    if not store.try_claim_challenge():
        log("challenge already active in another session — letting prompt through")
        return 0

    try:
        # tag the challenge window with the tool that triggered this prompt
        os.environ["WORKOUT_GATE_SOURCE"] = _source(payload)
        from workout_gate import challenge

        # Persist the debt BEFORE opening the window: closing everything mid-
        # challenge keeps it owed for the next session.
        state = store.load_state()
        if state["debt_reps"] <= 0 and not state.get("debt_offers"):
            challenge.new_debt()
        owed = challenge.pending_summary(store.load_state())
        log(f"challenge triggered: {owed} owed")

        # Under a desktop app the hook has no terminal of its own, so route the
        # webcam window through Terminal.app (camera permission, visible window).
        paid = (challenge.settle_external() if challenge.should_externalize()
                else challenge.settle_debt())
    finally:
        store.clear_challenge_pid()  # release the claim (webcam process clears its own)

    if paid:
        print(f"[workout-gate] The user just did {owed} to send this prompt.")
        return 0
    remaining = challenge.pending_summary(store.load_state())
    print(
        f"WORKOUT GATE: challenge aborted, {remaining} still owed. "
        "Resend your prompt to retry (or run 'workout off' in a terminal, no judgment).",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log("FAIL-OPEN:\n" + traceback.format_exc())
        sys.exit(0)
