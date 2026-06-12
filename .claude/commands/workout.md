---
description: Workout Gate - on/off, challenge, stats, presets, settings
allowed-tools: Bash(.venv/bin/python -m workout_gate:*)
---

The user manages the Workout Gate (pushup challenge before prompts). Their request: "$ARGUMENTS"

Run the matching command with Bash, from the project root, exactly in this form, and relay the output concisely:

- no arguments → run `.venv/bin/python -m workout_gate status && .venv/bin/python -m workout_gate stats` (one Bash call), show a compact summary, and remind the user that typing `! workout` (or `! ./workout` if not globally installed) opens the instant zero-token interactive dashboard where they can change every setting with arrow keys.
- `on` / `off` → `.venv/bin/python -m workout_gate on` (or `off`)
- `now` → `.venv/bin/python -m workout_gate now` — run it WITHOUT sandboxing (webcam access needed) and with a 300000ms timeout
- `stats` → `.venv/bin/python -m workout_gate stats`
- `status` → `.venv/bin/python -m workout_gate status`
- `ui` → tell the user to type `! workout` themselves (full-screen dashboard; it needs their terminal, you cannot run it for them)
- `global on|off|status` → `.venv/bin/python -m workout_gate global <action>` (install/remove for ALL Claude Code sessions)
- `preset chill|demo|hardcore` → `.venv/bin/python -m workout_gate preset <name>`
- `freq N` → `.venv/bin/python -m workout_gate set freq N`
- `reps MIN MAX` → `.venv/bin/python -m workout_gate set reps MIN MAX`
- `time N` → `.venv/bin/python -m workout_gate set time N`
- `chance P` → `.venv/bin/python -m workout_gate set chance P`

If `now` fails with a webcam/permission error, tell the user to run it themselves with: `! workout now` (macOS may need camera permission granted to the terminal first).
