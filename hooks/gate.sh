#!/bin/sh
# Plugin-friendly gate entry: resolve the runtime python wherever this code
# lives (plugin cache, git clone, dev checkout) and hand over to gate.py.
# Fail open: a missing runtime must never block a prompt.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HOME/.workout-gate/venv/bin/python"
[ -x "$PY" ] || PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || exit 0  # not bootstrapped yet; SessionStart handles onboarding
exec "$PY" "$ROOT/hooks/gate.py"
