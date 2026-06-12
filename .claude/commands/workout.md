---
description: Workout Gate - interactive menu, on/off, challenge, stats, presets
allowed-tools: Bash(.venv/bin/python -m workout_gate:*)
---

The user manages the Workout Gate (pushup challenge before prompts). Their request: "$ARGUMENTS"

## If arguments were given

Run the matching command with Bash, from the project root, exactly in this form, and relay the output concisely:

- `on` / `off` → `.venv/bin/python -m workout_gate on` (or `off`)
- `now` → `.venv/bin/python -m workout_gate now` — run it WITHOUT sandboxing (webcam access needed) and with a 300000ms timeout
- `stats` → `.venv/bin/python -m workout_gate stats`
- `status` → `.venv/bin/python -m workout_gate status`
- `ui` → tell the user to type `! .venv/bin/python -m workout_gate ui` themselves (it is a full-screen interactive dashboard; it needs their terminal, you cannot run it for them)
- `preset chill|demo|hardcore` → `.venv/bin/python -m workout_gate preset <name>`
- `freq N` → `.venv/bin/python -m workout_gate set freq N`
- `reps MIN MAX` → `.venv/bin/python -m workout_gate set reps MIN MAX`
- `time N` → `.venv/bin/python -m workout_gate set time N`
- `chance P` → `.venv/bin/python -m workout_gate set chance P`

## If NO arguments were given: interactive menu

1. Run `.venv/bin/python -m workout_gate status` and `.venv/bin/python -m workout_gate stats` (one Bash call, `&&`-joined). Show a compact 2-3 line summary.
2. Use the AskUserQuestion tool (this gives the user an arrow-key menu) with ONE question "Que veux-tu faire ?" and these 4 options:
   - "Défi maintenant 💪" — force a challenge, opens the webcam window
   - "ON/OFF" — label it "Désactiver" if the gate is ON, "Activer" if OFF
   - "Preset" — choose chill / demo / hardcore
   - "Réglages" — frequency, reps range, trigger mode
3. Act on the answer:
   - Défi → run the `now` command (no sandbox, 300000ms timeout).
   - ON/OFF → run `on` or `off`.
   - Preset → second AskUserQuestion with options "chill (tous les 25 prompts, 3-6 reps)", "demo (chaque prompt, 5-8 reps - pour filmer)", "hardcore (tous les 5 prompts, 15-25 reps)", then run `preset <name>`.
   - Réglages → second AskUserQuestion: "Fréquence (tous les N prompts)", "Fourchette de reps", "Mode temporel (max 1 défi / N min)", "Mode roulette (P% par prompt)". Then ask for the value with a third AskUserQuestion offering sensible choices (e.g. freq: 5/10/15/25 - reps: "3 6"/"5 10"/"10 15" - time: 15/30/60 - chance: 5/10/25), and run the matching `set` command.
4. Confirm with the command output, briefly. Mention once that `! .venv/bin/python -m workout_gate ui` opens the full-screen dashboard version.

If `now` fails with a webcam/permission error, tell the user to run it themselves with: `! .venv/bin/python -m workout_gate now` (macOS may need camera permission granted to the terminal first).
