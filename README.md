# Workout Gate 🏋️

> Your AI works hard, so should you.

A Claude Code hook that blocks your prompt until you work out — push-ups or
squats, counted live via webcam. When a challenge fires you pick your pain
(say 6 push-ups *or* 9 squats). Random reps, session-persistent debt (no
closing the tab to skip), streak stats, and three trigger modes.

*Version française : [README.fr.md](README.fr.md)*

## Install

### As a Claude Code plugin (recommended)

```
/plugin marketplace add BotchetDig/workout-gate
/plugin install workout-gate@workout-gate
```

Then **start a new session** (or run `/reload-plugins`) — nothing happens
until you do. Onboarding pops up in a Terminal window on its own —
dependencies install, then a 30-second wizard (your max, trigger choice, a
2-pushup camera test). Until setup is done, prompts pass freely. The gate and
`/workout-gate:workout` then work in every session, and plugin updates never
break the install (the runtime lives in `~/.workout-gate/`).

### One line, without the plugin

```bash
curl -fsSL https://raw.githubusercontent.com/BotchetDig/workout-gate/main/get.sh | bash
```

Re-running the same line updates the install. Prefer to look around first?

```bash
git clone https://github.com/BotchetDig/workout-gate.git && cd workout-gate
./install.sh
```

The installer sets everything up (venv, dependencies, pose model) then walks
you through a 30-second wizard: it asks your one-set max to size the
challenges to you (25–50% of it), lets you pick a trigger, offers the global
install, and runs a 2-pushup camera test so the macOS permission dialog
happens now — not in the middle of your first gated prompt.

Re-run the wizard anytime with `workout setup`. Use `./install.sh --no-setup`
for a non-interactive install with defaults (every 15 prompts, 5–10 reps).

## Usage

Drive it with `! workout` from inside Claude Code (the `!` prefix runs a shell
command — instant, **zero tokens**), or just `workout` from any terminal.

| Command | Effect |
|---|---|
| `! workout` | open the dashboard (arrow keys, live stats) in a Terminal window |
| `! workout now` | force a challenge right now (great for filming) |
| `! workout stats` | total, today, streak, record, last 7 days |
| `! workout status` | gate state (counter, debt, settings) |
| `! workout on` / `off` | enable / disable |
| `! workout stop` | close a running challenge window |
| `! workout preset chill\|demo\|hardcore` | see presets below |
| `! workout enable\|disable squats` | turn an exercise on/off |
| `! workout set reps squats 8 15` | rep range for one exercise |
| `! workout set mode choice\|random` | pick the exercise yourself, or at random |
| `! workout set freq 15` | one challenge every 15 prompts |
| `! workout set time 30` | time-based: at most one challenge per 30 min |
| `! workout set chance 10` | roulette: 10% chance on every prompt |

> There's also a `/workout-gate:workout` slash command, but it routes through
> Claude and costs tokens — prefer `! workout` for everything above.

### Dashboard

`! workout` (or `workout` in a terminal) opens a full-screen dashboard: arrow
keys to navigate every setting, left/right to change values, live stats with a
7-day sparkline, and a "force a challenge" shortcut. Since the `!` prompt can't
host curses, it pops up in a new Terminal window (macOS) that closes itself
when you quit.

### Presets

- **chill** — every 25 prompts, 3–6 reps. Everyday use.
- **demo** — every single prompt, 5–8 reps. Filming mode.
- **hardcore** — every 5 prompts, 15–25 reps. You asked for it.

## How it works

- A `UserPromptSubmit` hook counts your prompts. When a challenge is due, it
  draws a random rep count, **persists the debt to disk first**, opens the
  webcam window and freezes your prompt until you're done. Then the prompt
  sends itself. 
- Detection: MediaPipe Pose. Push-ups from the elbow angle (**profile view,
  on the floor**, body horizontal); squats from the knee angle (**stand in
  full view, side-on**, body upright). One rep = full descent then full
  extension, with smoothing and a posture guard so you can't cheat.
- When more than one exercise is enabled, the challenge offers a choice
  ("pick your pain") — or picks at random in `mode random`.
- Every rep is written to disk the moment it happens (atomic writes): quit at
  4/8 and you keep 4 in the stats, with 4 still owed next session.
- Data lives in `~/.workout-gate/`: `config.json`, `state.json`, `stats.json`,
  `gate.log`.

## Escape hatches (anti-lockout, by design)

1. `! workout off` from inside Claude Code — prompts starting with `!` or
   `/workout` are never gated, so you can always reach this.
2. `workout off` from any terminal.
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

## Global install

By default the gate only fires in this folder. To gate **every** Claude Code
session on your machine (the plugin install does this for you):

```bash
./install.sh --global        # or: workout global on
workout global off           # to remove
```

This surgically adds one hook entry to `~/.claude/settings.json` (a backup of
your original file is kept next to it) and removes exactly that on `off`.
Takes effect in new sessions.

## Tests

```bash
.venv/bin/python -m unittest discover -s tests
```

## Roadmap (if this takes off)

Sit-ups, jumping jacks — the structure is ready: one exercise = one entry in
`detector.EXERCISES` (a counter + an on-screen cue), nothing else to touch.
