"""First-run setup wizard: sizes the challenges to YOUR max, picks a trigger,
optionally installs globally, and runs a 2-rep camera test so the macOS
permission dialog happens now - not in the middle of your first gated prompt.

Run with: workout setup  (also launched by install.sh)
"""
import os
import sys

from . import store

BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[96m"
GREEN = "\033[92m"
END = "\033[0m"


def derive_reps_range(max_reps: int) -> tuple[int, int]:
    """A challenge should be repeatable many times a day: 25-50% of your
    one-set max, never below 2."""
    hi = min(50, max(3, round(max_reps * 0.5)))
    lo = min(max(2, round(max_reps * 0.25)), hi - 1)
    return lo, hi


def _ask_int(prompt: str, default: int, lo: int, hi: int) -> int:
    while True:
        raw = input(f"  {prompt} {DIM}[{default}]{END} ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
            if lo <= value <= hi:
                return value
        except ValueError:
            pass
        print(f"  {DIM}enter a number between {lo} and {hi}{END}")


def _ask_choice(prompt: str, options: list, default: int) -> int:
    print(f"  {prompt}")
    for i, label in enumerate(options, 1):
        print(f"    {CYAN}{i}{END}  {label}")
    while True:
        raw = input(f"  choice {DIM}[{default}]{END} ").strip()
        if not raw:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw)
        print(f"  {DIM}enter 1-{len(options)}{END}")


def _ask_yn(prompt: str, default: bool) -> bool:
    hint = "[Y/n]" if default else "[y/N]"
    raw = input(f"  {prompt} {DIM}{hint}{END} ").strip().lower()
    return default if not raw else raw in ("y", "yes", "o", "oui")


def run() -> None:
    if not sys.stdin.isatty():
        print("The setup wizard needs a real terminal. Run: workout setup")
        return
    try:
        _run()
    except (EOFError, KeyboardInterrupt):
        print(f"\n  {DIM}setup aborted - nothing else changed. Re-run anytime: workout setup{END}")


def _run() -> None:
    config = store.load_config()
    print(f"\n{BOLD}WORKOUT GATE SETUP{END}")
    print(f"{DIM}Exercise before prompts. Let's size this to you - 30 seconds.{END}\n")

    # 1. per-exercise challenge size, derived from the user's actual level
    print(f"  {DIM}Press Enter to skip an exercise (it stays off).{END}")
    DEFAULTS = {"pushups": 20, "squats": 30}
    any_on = False
    for ex in ("pushups", "squats"):
        mx = _ask_int(f"Max {ex} in one clean set? (0 to skip)", DEFAULTS[ex], 0, 200)
        if mx <= 0:
            config["exercises"][ex]["enabled"] = False
            continue
        lo, hi = derive_reps_range(mx)
        config["exercises"][ex].update(enabled=True, reps_min=lo, reps_max=hi)
        any_on = True
        print(f"  {GREEN}->{END} {ex}: challenges draw {BOLD}{lo}-{hi}{END} "
              f"{DIM}(25-50% of your max){END}")
    if not any_on:  # never leave the user with nothing enabled
        config["exercises"]["pushups"].update(enabled=True, reps_min=5, reps_max=10)
        print(f"  {DIM}Nothing picked - keeping pushups on (5-10).{END}")
    print()
    if len([e for e in config["exercises"].values() if e.get("enabled")]) > 1:
        m = _ask_choice("When both apply, how is the exercise picked?", [
            "You choose in the window  (default)",
            "Picked at random for you",
        ], 1)
        config["exercise_mode"] = "choice" if m == 1 else "random"
        print()

    # 2. trigger
    choice = _ask_choice("When should a challenge fire?", [
        "Every N prompts        (predictable - default)",
        "Time-based             (max one challenge per N minutes - the healthy one)",
        "Roulette               (N% chance on every prompt - you never know)",
    ], 1)
    if choice == 1:
        config["trigger"] = "prompts"
        config["every_n_prompts"] = _ask_int("Every how many prompts?", 15, 1, 99)
    elif choice == 2:
        config["trigger"] = "time"
        config["time_interval_min"] = _ask_int("Minimum minutes between challenges?", 30, 5, 240)
    else:
        config["trigger"] = "roulette"
        config["roulette_chance_pct"] = _ask_int("Chance per prompt (%)?", 10, 1, 100)
    config["preset"] = None
    config["enabled"] = True
    store.save_config(config)
    print(f"  {GREEN}->{END} saved\n")

    # 3. scope - irrelevant under the plugin (its hooks already fire everywhere)
    from . import installer
    if os.environ.get("WORKOUT_GATE_PLUGIN") == "1":
        launcher = installer._install_launcher()
        print(f"  {GREEN}->{END} 'workout' command installed ({launcher})\n")
    elif _ask_yn("Gate ALL your Claude Code sessions (recommended), not just this folder?", True):
        print("  " + installer.enable().replace("\n", "\n  "))
    print()

    # 4. camera test - get the macOS permission dialog out of the way NOW
    if _ask_yn("Quick 2-pushup camera test now? (triggers the macOS camera permission)", True):
        from . import challenge
        try:
            ok = challenge.run_challenge(2, on_rep=lambda _n: store.record_rep())
            print(f"  {GREEN}-> camera test passed, counting works{END}" if ok
                  else f"  {DIM}-> aborted, no problem - test again anytime with: workout now{END}")
        except RuntimeError as e:
            print(f"  {DIM}-> camera unavailable ({e}). Grant camera access to your terminal\n"
                  f"     in System Settings > Privacy > Camera, then run: workout now{END}")
    slash = "/workout-gate:workout" if os.environ.get("WORKOUT_GATE_PLUGIN") == "1" else "/workout"
    print(f"""
{BOLD}You're set.{END} Cheat sheet (in any terminal, or prefixed with {BOLD}!{END} inside Claude Code):
  workout            dashboard (arrow keys, live stats)
  workout now        force a challenge
  workout stop       close a running challenge
  workout off        quick disable   {DIM}(also: {slash} off, or WORKOUT_GATE_OFF=1
                     - you can never be locked out){END}
  workout setup      re-run this wizard
""")
