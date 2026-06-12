"""CLI: python -m workout_gate {on,off,now,pay,stats,status,preset,set}"""
import argparse
import sys

from . import store
from .trigger import PRESETS, apply_preset


def main(argv=None):
    parser = argparse.ArgumentParser(prog="workout_gate", description="Workout Gate for Claude Code")
    sub = parser.add_subparsers(dest="cmd")  # no subcommand -> dashboard
    sub.add_parser("on", help="enable the gate")
    sub.add_parser("off", help="disable the gate")
    sub.add_parser("now", help="force a challenge right now")
    sub.add_parser("pay", help="settle the pending debt (opens the webcam window)")
    sub.add_parser("stop", help="close a running challenge window (progress is saved)")
    sub.add_parser("setup", help="interactive setup wizard (sizes challenges to your max)")
    sub.add_parser("help", help="show this help")
    sub.add_parser("stats", help="totals, streak, record, last 7 days")
    sub.add_parser("status", help="show gate state")
    sub.add_parser("ui", help="full-screen interactive dashboard (arrow keys)")
    p_global = sub.add_parser("global", help="install/remove the gate for ALL Claude Code sessions")
    p_global.add_argument("action", choices=["on", "off", "status"])
    p_preset = sub.add_parser("preset", help="apply a preset")
    p_preset.add_argument("name", choices=sorted(PRESETS))
    p_set = sub.add_parser("set", help="freq N | reps [EXERCISE] MIN MAX | trigger M | time MIN | chance PCT | mode choice|random")
    p_set.add_argument("key", choices=["freq", "reps", "trigger", "time", "chance", "mode"])
    p_set.add_argument("values", nargs="+")
    p_enable = sub.add_parser("enable", help="enable an exercise")
    p_enable.add_argument("exercise")
    p_disable = sub.add_parser("disable", help="disable an exercise")
    p_disable.add_argument("exercise")
    p_debug = sub.add_parser("debug", help="overlay the detected skeleton + live angle")
    p_debug.add_argument("action", choices=["on", "off"])
    args = parser.parse_args(argv)

    if args.cmd in (None, "ui"):
        from . import tui
        tui.main()
        return

    if args.cmd == "help":
        parser.print_help()
        return

    if args.cmd == "setup":
        from . import setup_wizard
        setup_wizard.run()
        return

    if args.cmd in ("now", "pay") and store.running_challenge_pid():
        sys.exit("A challenge window is already open. Finish it, or close it with: workout stop")

    if args.cmd == "stop":
        pid = store.running_challenge_pid()
        if pid is None:
            print("No challenge running.")
            return
        import os
        import signal
        os.kill(pid, signal.SIGTERM)
        store.clear_challenge_pid()
        owed = store.load_state()["debt_reps"]
        print(f"Challenge window closed. Reps already done are saved"
              + (f"; {owed} still owed." if owed else "."))
        return

    if args.cmd in ("on", "off"):
        config = store.load_config()
        config["enabled"] = args.cmd == "on"
        store.save_config(config)
        print(f"Workout gate {'ENABLED' if config['enabled'] else 'DISABLED'}.")

    elif args.cmd == "now":
        from . import challenge
        state = store.load_state()
        if state["debt_reps"] <= 0 and not state.get("debt_offers"):
            challenge.new_debt()
        print(f"Challenge: {challenge.pending_summary(store.load_state())}. Window opening...")
        ok = challenge.settle_debt()
        print("Validated!" if ok else f"Aborted. {challenge.pending_summary(store.load_state())} still owed.")
        sys.exit(0 if ok else 1)

    elif args.cmd == "pay":
        from . import challenge
        st = store.load_state()
        if st["debt_reps"] <= 0 and not st.get("debt_offers"):
            print("No debt. You're free.")
            return
        ok = challenge.settle_debt()
        print("Debt paid!" if ok else f"Aborted. {challenge.pending_summary(store.load_state())} still owed.")
        sys.exit(0 if ok else 1)

    elif args.cmd == "global":
        from . import installer
        print({"on": installer.enable, "off": installer.disable, "status": installer.status}[args.action]())

    elif args.cmd == "debug":
        config = store.load_config()
        config["debug"] = args.action == "on"
        store.save_config(config)
        print(f"Debug overlay {'ON (skeleton + angle)' if config['debug'] else 'OFF'}.")

    elif args.cmd in ("enable", "disable"):
        from .detector import EXERCISES
        config = store.load_config()
        if args.exercise not in EXERCISES:
            sys.exit(f"unknown exercise '{args.exercise}'. Known: {', '.join(EXERCISES)}")
        config["exercises"].setdefault(args.exercise, {"reps_min": 5, "reps_max": 10})
        config["exercises"][args.exercise]["enabled"] = args.cmd == "enable"
        config["preset"] = None
        store.save_config(config)
        print(f"{args.exercise}: {'enabled' if args.cmd == 'enable' else 'disabled'}. "
              f"Active: {', '.join(store.enabled_exercises(config))}")

    elif args.cmd == "stats":
        from . import stats_view
        stats_view.main()

    elif args.cmd == "status":
        config, state = store.load_config(), store.load_state()
        print(f"Gate: {'ON' if config['enabled'] else 'OFF'}"
              + (f"  (preset: {config['preset']})" if config.get("preset") else ""))
        trig = config["trigger"]
        if trig == "prompts":
            print(f"Trigger: every {config['every_n_prompts']} prompts "
                  f"(currently {state['prompt_count']}/{config['every_n_prompts']})")
        elif trig == "time":
            print(f"Trigger: at most every {config['time_interval_min']} min")
        else:
            print(f"Trigger: roulette, {config['roulette_chance_pct']}% per prompt")
        from . import challenge
        print(f"Pending debt: {challenge.pending_summary(state) or 'none'}")
        for ex in store.enabled_exercises(config):
            ec = config["exercises"][ex]
            print(f"  {ex}: {ec['reps_min']}-{ec['reps_max']} reps")
        print(f"Exercise mode: {config.get('exercise_mode', 'choice')}, gate mode: {config['mode']}"
              + ("  [debug overlay ON]" if config.get("debug") else ""))

    elif args.cmd == "preset":
        config = apply_preset(store.load_config(), args.name)
        store.save_config(config)
        desc = {
            "chill": "rare and light - everyday use",
            "demo": "challenge on EVERY prompt - filming mode",
            "hardcore": "every 5 prompts, high reps - good luck",
        }[args.name]
        print(f"Preset '{args.name}' applied: {desc}")

    elif args.cmd == "set":
        config = store.load_config()
        try:
            msg = _apply_setting(config, args.key, args.values)
        except (ValueError, IndexError, KeyError):
            sys.exit("usage: set freq N | set reps [EXERCISE] MIN MAX | "
                     "set trigger prompts|time|roulette | set time MINUTES | "
                     "set chance PERCENT | set mode choice|random")
        if args.key != "reps":
            config["preset"] = None
        store.save_config(config)
        print(msg)


_MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _pretty_date(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{_MONTHS[int(m)]} {int(d):2d}"


def _bar(value: int, maxv: int, width: int = 20) -> str:
    filled = round(width * value / maxv) if maxv > 0 else 0
    return "█" * filled + "░" * (width - filled)


_SPARK = "▁▂▃▄▅▆▇█"


def _spark(values) -> str:
    top = max(values, default=0)
    if top <= 0:
        return _SPARK[0] * len(values)
    return "".join(_SPARK[min(7, int(v / top * 7 + 0.5))] for v in values)


def render_stats(stats: dict, color: bool = True) -> str:
    def c(code, s):
        return f"\033[{code}m{s}\033[0m" if color else s

    bold, dim, cyan, green = "1", "2", "96", "92"
    by_day = stats.get("by_day", {})
    by_ex = stats.get("by_exercise", {})
    total = stats.get("total_reps", 0)
    today = by_day.get(store.today(), 0)
    streak = store.streak_days(by_day)
    record = store.best_day(by_day)
    dates = [d for d, _ in store.last_days(by_day)]
    ex_max = max(by_ex.values(), default=0)

    L = ["", "  " + c(bold, c(cyan, "🏋  WORKOUT GATE")) + c(dim, "  ·  stats"),
         "  " + c(dim, "─" * 40)]
    L.append(f"  {c(dim, 'Total '.ljust(8))}{c(bold, total)} reps")
    L.append(f"  {c(dim, 'Today '.ljust(8))}{c(bold, today)}")
    L.append(f"  {c(dim, 'Streak'.ljust(8))}{c(bold, streak)} day" + ("s" if streak != 1 else "")
             + ("  🔥" if streak > 0 else ""))
    if record:
        L.append(f"  {c(dim, 'Record'.ljust(8))}{c(bold, record[1])}  {c(dim, _pretty_date(record[0]))}")

    # per-exercise: total bar + its own 7-day sparkline
    if by_ex:
        L.append("")
        for ex, n in by_ex.items():
            spark = _spark([store.day_counts(stats, ex).get(d, 0) for d in dates])
            L.append(f"  {ex:<9} {c(green, _bar(n, ex_max, 14))} {c(bold, str(n)):>3}   {c(green, spark)}")

    # combined daily history
    L.append("")
    L.append("  " + c(dim, "Last 7 days (all)"))
    day_max = max((by_day.get(d, 0) for d in dates), default=0)
    for d in dates:
        n = by_day.get(d, 0)
        bar = c(green, _bar(n, day_max, 18)) if n else c(dim, "░" * 18)
        L.append(f"  {c(dim, _pretty_date(d))}  {bar}  {c(bold, n) if n else c(dim, '0')}")
    L.append("")
    return "\n".join(L)


def _apply_setting(config, key, values) -> str:
    if key == "freq":
        n = int(values[0])
        if n < 1:
            raise ValueError
        config["every_n_prompts"] = n
        config["trigger"] = "prompts"
        return f"trigger: every {n} prompts"
    elif key == "reps":
        # "reps MIN MAX" -> pushups; "reps EXERCISE MIN MAX" -> that exercise
        if len(values) == 2:
            exercise, lo, hi = "pushups", int(values[0]), int(values[1])
        else:
            exercise, lo, hi = values[0], int(values[1]), int(values[2])
        if exercise not in config["exercises"] or not 1 <= lo <= hi:
            raise ValueError
        config["exercises"][exercise]["reps_min"] = lo
        config["exercises"][exercise]["reps_max"] = hi
        return f"{exercise} reps: {lo}-{hi}"
    elif key == "trigger":
        if values[0] not in ("prompts", "time", "roulette"):
            raise ValueError
        config["trigger"] = values[0]
        return f"trigger: {values[0]}"
    elif key == "time":
        minutes = int(values[0])
        if minutes < 1:
            raise ValueError
        config["time_interval_min"] = minutes
        config["trigger"] = "time"
        return f"trigger: at most every {minutes} min"
    elif key == "chance":
        pct = float(values[0])
        if not 0 < pct <= 100:
            raise ValueError
        config["roulette_chance_pct"] = pct
        config["trigger"] = "roulette"
        return f"trigger: roulette {pct:g}% per prompt"
    elif key == "mode":
        if values[0] not in ("choice", "random"):
            raise ValueError
        config["exercise_mode"] = values[0]
        return f"exercise mode: {values[0]}"
    raise ValueError


if __name__ == "__main__":
    main()
