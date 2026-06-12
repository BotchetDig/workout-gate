---
description: Workout Gate - on/off, challenge, stats, presets, settings
allowed-tools: Bash(.venv/bin/python -m workout_gate:*)
---

The user manages the Workout Gate (exercise challenge before prompts). Their request: "$ARGUMENTS"

Run the matching command with Bash, from the project root, exactly in this form, and relay the output concisely:

- no arguments → run `.venv/bin/python -m workout_gate status` and show a compact summary; remind the user that `! workout` pops the zero-token arrow-key dashboard in a Terminal window.
- `on` / `off` → `.venv/bin/python -m workout_gate on` (or `off`)
- `now` → `.venv/bin/python -m workout_gate now` — run it WITHOUT sandboxing (webcam access needed) and with a 300000ms timeout
- `stop` → `.venv/bin/python -m workout_gate stop` (closes a running challenge window)
- `stats` / `status` → `.venv/bin/python -m workout_gate stats` / `... status`
- `setup` → tell the user to run `! workout setup` themselves (interactive wizard, needs a terminal)
- `ui` → tell the user to type `! workout` (it pops the dashboard in a Terminal window; you cannot host it yourself)
- `debug on|off` → `.venv/bin/python -m workout_gate debug <action>` (overlay skeleton + live angle)
- `global on|off|status` → `.venv/bin/python -m workout_gate global <action>` (install/remove for ALL Claude Code sessions)
- `enable|disable <exercise>` → `.venv/bin/python -m workout_gate enable <exercise>` (or disable)
- `preset chill|demo|hardcore` → `.venv/bin/python -m workout_gate preset <name>`
- `freq N` → `.venv/bin/python -m workout_gate set freq N`
- `reps [EXERCISE] MIN MAX` → `.venv/bin/python -m workout_gate set reps EXERCISE MIN MAX` (exercise optional, defaults to pushups)
- `time N` / `chance P` → `.venv/bin/python -m workout_gate set time N` / `... set chance P`
- `mode choice|random` → `.venv/bin/python -m workout_gate set mode <value>`

If `now` fails with a webcam/permission error, tell the user to run it themselves with: `! workout now` (macOS may need camera permission granted to the terminal first).
