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
    sub.add_parser("stats", help="totals, streak, record, last 7 days")
    sub.add_parser("status", help="show gate state")
    sub.add_parser("ui", help="full-screen interactive dashboard (arrow keys)")
    p_global = sub.add_parser("global", help="install/remove the gate for ALL Claude Code sessions")
    p_global.add_argument("action", choices=["on", "off", "status"])
    p_preset = sub.add_parser("preset", help="apply a preset")
    p_preset.add_argument("name", choices=sorted(PRESETS))
    p_set = sub.add_parser("set", help="set freq N | reps MIN MAX | trigger MODE | time MIN | chance PCT")
    p_set.add_argument("key", choices=["freq", "reps", "trigger", "time", "chance"])
    p_set.add_argument("values", nargs="+")
    args = parser.parse_args(argv)

    if args.cmd in (None, "ui"):
        from . import tui
        tui.main()
        return

    if args.cmd in ("on", "off"):
        config = store.load_config()
        config["enabled"] = args.cmd == "on"
        store.save_config(config)
        print(f"Workout gate {'ENABLED' if config['enabled'] else 'DISABLED'}.")

    elif args.cmd == "now":
        from . import challenge
        state = store.load_state()
        reps = state["debt_reps"] or challenge.new_debt()
        print(f"Challenge: {reps} pushups. Window opening...")
        ok = challenge.settle_debt()
        print("Validated!" if ok else f"Aborted. {store.load_state()['debt_reps']} reps still owed.")
        sys.exit(0 if ok else 1)

    elif args.cmd == "pay":
        from . import challenge
        if store.load_state()["debt_reps"] <= 0:
            print("No debt. You're free.")
            return
        ok = challenge.settle_debt()
        print("Debt paid!" if ok else f"Aborted. {store.load_state()['debt_reps']} reps still owed.")
        sys.exit(0 if ok else 1)

    elif args.cmd == "global":
        from . import installer
        print({"on": installer.enable, "off": installer.disable, "status": installer.status}[args.action]())

    elif args.cmd == "stats":
        stats = store.load_stats()
        by_day = stats["by_day"]
        print(f"Total pushups: {stats['total_reps']}")
        print(f"Today: {by_day.get(store.today(), 0)}")
        print(f"Streak: {store.streak_days(by_day)} day(s)")
        record = store.best_day(by_day)
        if record:
            print(f"Record: {record[1]} on {record[0]}")
        print("Last 7 days: " + "  ".join(f"{d[5:]}:{n}" for d, n in store.last_days(by_day)))

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
        print(f"Pending debt: {state['debt_reps']} {state['debt_exercise']}")
        print(f"Reps range: {config['reps_min']}-{config['reps_max']}, mode: {config['mode']}")

    elif args.cmd == "preset":
        config = apply_preset(store.load_config(), args.name)
        store.save_config(config)
        desc = {
            "chill": "rare and light - everyday use",
            "demo": "challenge on EVERY prompt - filming mode",
            "hardcore": "every 5 prompts, 15-25 reps - good luck",
        }[args.name]
        print(f"Preset '{args.name}' applied: {desc}")

    elif args.cmd == "set":
        config = store.load_config()
        try:
            _apply_setting(config, args.key, args.values)
        except (ValueError, IndexError):
            sys.exit("usage: set freq N | set reps MIN MAX | set trigger prompts|time|roulette "
                     "| set time MINUTES | set chance PERCENT")
        config["preset"] = None
        store.save_config(config)
        trig = config["trigger"]
        detail = {"prompts": f"every {config['every_n_prompts']} prompts",
                  "time": f"every {config['time_interval_min']} min",
                  "roulette": f"{config['roulette_chance_pct']}% per prompt"}[trig]
        print(f"trigger: {detail}, reps {config['reps_min']}-{config['reps_max']}")


def _apply_setting(config, key, values):
    if key == "freq":
        n = int(values[0])
        if n < 1:
            raise ValueError
        config["every_n_prompts"] = n
        config["trigger"] = "prompts"
    elif key == "reps":
        lo, hi = int(values[0]), int(values[1])
        if not 1 <= lo <= hi:
            raise ValueError
        config["reps_min"], config["reps_max"] = lo, hi
    elif key == "trigger":
        if values[0] not in ("prompts", "time", "roulette"):
            raise ValueError
        config["trigger"] = values[0]
    elif key == "time":
        minutes = int(values[0])
        if minutes < 1:
            raise ValueError
        config["time_interval_min"] = minutes
        config["trigger"] = "time"
    elif key == "chance":
        pct = float(values[0])
        if not 0 < pct <= 100:
            raise ValueError
        config["roulette_chance_pct"] = pct
        config["trigger"] = "roulette"


if __name__ == "__main__":
    main()
