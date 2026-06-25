# Multi-tool QA checklist

The automated suite (`python -m unittest discover -s tests`, green on
Python 3.9 + 3.13) covers the logic: escape hatches, turn dedup, the locked
counter, single-flight fail-open, the externalize decision, Codex install, and
runtime vendoring. What it **can't** cover is live behavior that needs real apps
and a real webcam. Run this matrix by hand once before sharing.

Supported surfaces: **Claude Code CLI**, **Claude Code desktop**, **Codex CLI**.
Codex Desktop currently discovers the hooks but did not run `UserPromptSubmit`
in local testing, so it is tracked as unsupported for now. Shared runtime:
`~/.workout-gate/` (debt, prompt counter, stats, streak, config).

## Per-surface install

- [ ] **Claude CLI** — plugin installed; new session; setup wizard completes;
      a forced challenge (`workout now`) counts reps and clears.
- [ ] **Claude desktop** — same plugin/hooks (settings are shared with the CLI);
      gate fires; **challenge opens in a Terminal window** (not in the app), and
      the macOS camera prompt is attributed to **Terminal**, not Claude.
- [ ] **Codex CLI plugin** — add the local/published marketplace, install
      `workout-gate` from `/plugins`, start a new session, approve via `/hooks`,
      gate fires, reps counted.
- [ ] **Codex CLI manual hook** — `workout codex on`, approve via `/hooks`,
      new session, gate fires, reps counted.
- [ ] **Codex Desktop** — not supported yet: verify it still discovers hooks but
      does not gate prompts before advertising any desktop support.

## Shared-state invariants (cross-surface)

- [ ] **Debt follows you**: trigger + abort a challenge in Claude CLI (leaves reps
      owed) → the next prompt in **Codex** is gated for the remaining debt.
- [ ] **Stats are combined**: reps done in any surface show up in `workout stats`
      everywhere; the streak is one shared streak.
- [ ] **Counter is global**: with `preset demo` (every prompt) off, set
      `set freq 3`; alternate one prompt in Claude and one in Codex → the 3rd
      prompt overall triggers, regardless of which tool sent it.
- [ ] **off is universal**: `workout off` in a terminal disables the gate in every
      surface; `workout on` re-enables.

## Concurrency (two surfaces at once)

- [ ] **No double-trigger**: with a challenge pending, submit in two tools at
      nearly the same moment → only one webcam window opens; the other prompt
      fails open (check `~/.workout-gate/gate.log` for "challenge already
      active").
- [ ] **No lost counts**: fire many prompts quickly across two tools → the prompt
      counter advances by exactly the number of (deduped) prompts, never fewer.
- [ ] **Pay in A, free in B**: while paying a challenge in Claude, a prompt in
      Codex is let through (anti-lockout), and once A completes the debt is clear
      for both.

## Escape hatches (each surface)

- [ ] `workout off` in a terminal → next prompt passes.
- [ ] `WORKOUT_GATE_OFF=1` in the env → passes.
- [ ] `/workout ...` (Claude) and bare `workout ...` / `wg ...` (Codex) prompts
      are never gated.
- [ ] Kill the webcam mid-challenge (close window / ESC) → reps done so far are
      saved, the rest stays owed, the prompt is not lost.

## Runtime versioning

- [ ] `~/.workout-gate/app/` holds the vendored code after a session start
      (`installer.sync_app`), and `gate.sh` runs from it (so Claude and Codex run
      the same version against the shared state).
- [ ] A curl/git install (`~/.workout-gate/app/.git` present) is **not**
      overwritten by `sync_app` — that dir stays git-managed.

## Notes / known unknowns

- Camera-permission attribution under desktop apps is the one thing to verify by
  eye — the Terminal-routing strategy is designed to make it attach to
  Terminal.app (primed at onboarding), but confirm the first-run prompt names
  Terminal, not Claude/Codex/`python`.
- Codex payload fields used by the hook: `prompt`, `session_id`, `turn_id`
  (confirmed present). If a future Codex changes these, only `hooks/gate.py`'s
  `duplicate_invocation` / `main` read them.
