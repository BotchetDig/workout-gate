---
description: Workout Gate - on/off, force a challenge, stats, presets, settings
allowed-tools: Bash(.venv/bin/python -m workout_gate:*)
---

The user manages the Workout Gate (pushup challenge before prompts). Their request: "$ARGUMENTS"

Run the matching command with Bash, from the project root, exactly in this form:

- `on` / `off` → `.venv/bin/python -m workout_gate on` (or `off`)
- `now` (force a challenge immediately, opens the webcam window) → `.venv/bin/python -m workout_gate now` — run it WITHOUT sandboxing (webcam access needed) and with a 300000ms timeout
- `stats` → `.venv/bin/python -m workout_gate stats` (totals, streak, record, last 7 days)
- `status` (also the default if no arguments) → `.venv/bin/python -m workout_gate status`
- `preset chill|demo|hardcore` → `.venv/bin/python -m workout_gate preset <name>` (chill: rare & light; demo: every prompt, for filming; hardcore: every 5 prompts, 15-25 reps)
- `freq N` (challenge every N prompts) → `.venv/bin/python -m workout_gate set freq N`
- `reps MIN MAX` → `.venv/bin/python -m workout_gate set reps MIN MAX`
- `time N` (time-based: at most one challenge per N minutes) → `.venv/bin/python -m workout_gate set time N`
- `chance P` (roulette: P% chance on every prompt) → `.venv/bin/python -m workout_gate set chance P`

Relay the command output to the user concisely. If `now` fails with a webcam/permission error, tell the user to run it themselves with: `! .venv/bin/python -m workout_gate now` (macOS may need camera permission granted to the terminal first).
