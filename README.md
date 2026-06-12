# Workout Gate 🏋️

> Your prompt is blocked until you drop and give the webcam some pushups.

Workout Gate holds your Claude Code prompts hostage behind a physical
challenge: pushups, counted live on your webcam. No pushups, no prompt. Close
the session to dodge it? The debt is waiting for you next time.

*Version française : [README.fr.md](README.fr.md)*

## Install (30 seconds)

```bash
git clone <this-repo> && cd pushup-gate
./install.sh
```

Open a Claude Code session in this folder — the gate is live. On macOS, grant
camera access to your terminal the first time a challenge opens.

## Usage

| In Claude Code | Effect |
|---|---|
| `/workout` | gate status (counter, debt, settings) |
| `/workout on` / `off` | enable / disable |
| `/workout now` | force a challenge right now (great for filming) |
| `/workout stats` | total, today, streak, record, last 7 days |
| `/workout preset chill\|demo\|hardcore` | see presets below |
| `/workout freq 15` | one challenge every 15 prompts |
| `/workout reps 5 10` | random rep count range |
| `/workout time 30` | time-based: at most one challenge per 30 min |
| `/workout chance 10` | roulette: 10% chance on every prompt |

Same commands from any terminal: `.venv/bin/python -m workout_gate <cmd>`.

### Presets

- **chill** — every 25 prompts, 3–6 reps. Everyday use.
- **demo** — every single prompt, 5–8 reps. Filming mode.
- **hardcore** — every 5 prompts, 15–25 reps. You asked for it.

## How it works

- A `UserPromptSubmit` hook counts your prompts. When a challenge is due, it
  draws a random rep count, **persists the debt to disk first**, opens the
  webcam window and freezes your prompt until you're done. Then the prompt
  sends itself. 
- Detection: MediaPipe Pose, **profile view, on the floor**. One rep = full
  descent (elbow < 95°) then full extension (elbow > 150°), with smoothing.
  A posture guard ignores everything unless your body is horizontal — no
  cheating standing up.
- Every rep is written to disk the moment it happens (atomic writes): quit at
  4/8 and you keep 4 in the stats, with 4 still owed next session.
- Data lives in `~/.workout-gate/`: `config.json`, `state.json`, `stats.json`,
  `gate.log`.

## Escape hatches (anti-lockout, by design)

1. `/workout off` — `/workout` prompts are never gated.
2. `.venv/bin/python -m workout_gate off` from any terminal.
3. `WORKOUT_GATE_OFF=1` env var bypasses everything.
4. **Fail-open**: no webcam, broken dependency, any crash → your prompt goes
   through and the error lands in `~/.workout-gate/gate.log`. You can never be
   locked out of your own tool.

## Modes

`config.json → "mode"`:
- `"sync"` (default): the hook waits for the challenge, then the prompt sends
  itself. Most satisfying on video. 5-minute hook timeout.
- `"detached"`: the window opens in the background, the prompt is blocked with
  a message; do your reps, then resend (↑ + Enter).

The hook is scoped to this project. To gate every Claude Code session, copy the
`hooks` block from `.claude/settings.json` into `~/.claude/settings.json`,
replacing `$CLAUDE_PROJECT_DIR` with this folder's absolute path.

## Tests

```bash
.venv/bin/python -m unittest discover -s tests
```

## Roadmap (if this takes off)

Squats, sit-ups, jumping jacks — the structure is ready: one exercise = one
counter in `detector.py`, nothing else to touch.
