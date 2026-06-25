#!/bin/sh
# Plugin-friendly gate entry, shared by Claude Code AND Codex (both expose
# CLAUDE_PLUGIN_ROOT, and this script resolves from its own path anyway).
# Prefer the vendored shared runtime (~/.workout-gate/app) so every tool runs
# ONE version against the shared state; else the code dir this script lives in
# (plugin cache, git clone, dev checkout). Fail open: a missing runtime must
# never block a prompt.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RT="${WORKOUT_GATE_DIR:-$HOME/.workout-gate}"
[ -f "$RT/app/hooks/gate.py" ] && ROOT="$RT/app"
PY="$RT/venv/bin/python"
[ -x "$PY" ] || PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || exit 0  # not bootstrapped yet; SessionStart handles onboarding
exec "$PY" "$ROOT/hooks/gate.py"
