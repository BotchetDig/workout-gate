# Workout Gate 🏋️

> Your AI works hard, so should you.

A Claude Code hook that blocks your prompt until you work out — push-ups or
squats, counted live via webcam. When a challenge fires you pick your pain
(say 6 push-ups *or* 9 squats). Random reps, session-persistent debt (no
closing the tab to skip), streak stats, and three trigger modes.

*Version française : [README.fr.md](README.fr.md)*

## Requirements

- **Python 3.10–3.12** — MediaPipe has no wheels for 3.13+ yet, and <3.10 won't run.
- A **webcam** + an internet connection (first run downloads MediaPipe/OpenCV and a ~9 MB pose model).
- **macOS** for the zero-config plugin onboarding — it pops the setup in a Terminal and triggers the camera-permission dialog. Linux/Windows work too; Claude just points you at `bootstrap.sh` to run once by hand.
- `git` and `python3` on your PATH.

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
| `! workout` | open the web dashboard (settings + live stats) in your browser |
| `! workout tui` | the terminal dashboard instead (curses, arrow keys) |
| `! workout now` | force a challenge right now (great for filming) |
| `! workout stats` | per-exercise totals + 7-day chart (arrow keys to switch exercise in a real terminal) |
| `! workout status` | gate state (counter, debt, settings) |
| `! workout on` / `off` | enable / disable |
| `! workout stop` | close a running challenge window |
| `! workout preset chill\|demo\|hardcore` | see presets below |
| `! workout enable\|disable squats` | turn an exercise on/off |
| `! workout set reps squats 8 15` | rep range for one exercise |
| `! workout set mode choice\|random` | pick the exercise yourself, or at random |
| `! workout debug on\|off` | overlay the detected skeleton + live joint angle (handy when adding exercises) |
| `! workout set freq 15` | one challenge every 15 prompts |
| `! workout set time 30` | time-based: at most one challenge per 30 min |
| `! workout set chance 10` | roulette: 10% chance on every prompt |

> There's also a `/workout-gate:workout` slash command, but it routes through
> Claude and costs tokens — prefer `! workout` for everything above.

### Dashboard

`! workout` (or `workout` in a terminal) opens the **web dashboard** in your
browser. It's organised in **tabs**: an **Overview** tab (all the settings —
preset, trigger, gate on/off — plus combined stats) and **one tab per
exercise**, each with its own enable toggle, rep range, today/total counters and
7-day chart. Add an exercise (one entry in `detector.py`) and its tab appears on
its own. A "force a challenge" button is one click away. It's a tiny local-only
server (stdlib, no dependencies, bound to `127.0.0.1`) that shuts itself down a
few minutes after you close the tab.

Prefer the terminal? `! workout tui` opens the curses **settings** dashboard
(arrow keys to navigate, left/right to change values), and `! workout stats` is
the dedicated **stats** viewer (←/→ cycles through ALL + each exercise: total,
streak, record, 7-day chart). Both pop up in a Terminal window on macOS; the
webcam challenge itself is unchanged everywhere.

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

## Statusline segment (optional)

Show your reps right in the Claude Code statusline. `workout statusline` prints
a compact self-colored segment — `🏋 36 🔥4d` (today's reps + day streak).

Claude Code runs one statusline command (`statusLine` in `settings.json`). If
you already have a statusline script, append the segment to its output:

```sh
# near the end of your statusline script, before the final printf
WG="$HOME/.local/bin/workout"
[ -x "$WG" ] && wg=$("$WG" statusline 2>/dev/null)
# ...then add  ${wg:+ $wg}  to your printf
```

Or, for a statusline that's *only* the workout segment, set in
`settings.json`:

```json
"statusLine": { "type": "command", "command": "workout statusline" }
```

## Add your own exercise (forking)

Everything routes through one registry, `detector.EXERCISES`. Adding an
exercise is two steps in `workout_gate/detector.py` and nothing else:

1. **A counter** — subclass `ExerciseCounter`, declare the joint angle to
   track and the down/up thresholds (override `posture()` to reject bad form):

   ```python
   class SitupCounter(ExerciseCounter):
       SIDES = ((L_HIP, L_SHOULDER, L_KNEE), (R_HIP, R_SHOULDER, R_KNEE))
       DOWN_ANGLE = 55.0   # torso folded
       UP_ANGLE = 110.0    # lying back
   ```

2. **A registry entry**:

   ```python
   "situps": {
       "label": "SIT-UPS", "counter": SitupCounter,
       "cue": "LIE DOWN - SIDE-ON",
       "default_reps": (8, 15), "default_max": 30,
   },
   ```

Config defaults, presets, the setup wizard, the dashboard, the choice screen
and per-exercise stats all read the registry — they pick it up automatically.
Run the tests (`test_factory.py` proves a new entry flows end-to-end).
