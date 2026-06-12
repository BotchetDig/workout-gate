---
description: Workout Gate - on/off, challenge, stats, presets, settings
allowed-tools: Bash(workout:*)
---

The user manages the Workout Gate (pushup challenge before prompts). Their request: "$ARGUMENTS"

The `workout` launcher is on the user's PATH (installed during setup). Run the matching command with Bash and relay the output concisely:

- no arguments → run `workout status && workout stats` (one Bash call), show a compact summary, and remind the user that running `workout` in a terminal (or typing `! workout`) opens the zero-token arrow-key dashboard.
- `on` / `off` → `workout on` (or `workout off`)
- `now` → `workout now` — run it WITHOUT sandboxing (webcam access needed) and with a 300000ms timeout
- `stop` → `workout stop` (closes a running challenge window)
- `stats` / `status` → `workout stats` / `workout status`
- `setup` → tell the user to run `workout setup` in a terminal themselves (interactive wizard)
- `ui` → tell the user to type `! workout` (it pops the dashboard in a Terminal window; you cannot host it yourself)
- `preset chill|demo|hardcore` → `workout preset <name>`
- `freq N` / `reps MIN MAX` / `time N` / `chance P` → `workout set freq N` / `workout set reps MIN MAX` / `workout set time N` / `workout set chance P`

If `workout` is not found on PATH, the runtime is not bootstrapped yet: tell the user to run `"${CLAUDE_PLUGIN_ROOT}/bootstrap.sh"` in a terminal (or start a new session to trigger onboarding).

If `now` fails with a webcam/permission error, tell the user to run `! workout now` themselves (macOS may need camera permission granted to the terminal first).
