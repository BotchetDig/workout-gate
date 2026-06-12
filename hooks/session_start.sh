#!/bin/sh
# SessionStart hook: plugins can't run install scripts, so first-run setup
# happens here - pop the bootstrap (deps + wizard) in a Terminal window, once.
# stdout becomes session context, so Claude can tell the user what's going on.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOME_DIR="$HOME/.workout-gate"
mkdir -p "$HOME_DIR"
# keep the launcher pointed at the current code (plugin cache moves on update)
echo "$ROOT" > "$HOME_DIR/app-path"

PY="$HOME_DIR/venv/bin/python"
[ -x "$PY" ] || PY="$ROOT/.venv/bin/python"
if [ -x "$PY" ]; then  # already set up: refresh the launcher, then stay silent
    ( cd "$ROOT" && "$PY" -c "from workout_gate import installer; installer._install_launcher()" ) >/dev/null 2>&1 || true
    exit 0
fi

FLAG="$HOME_DIR/onboarding-shown"
[ -f "$FLAG" ] && exit 0  # don't reopen a window every session
touch "$FLAG"

if command -v osascript >/dev/null 2>&1 && \
   osascript -e 'tell application "Terminal"' -e 'activate' \
             -e "do script \"exec '$ROOT/bootstrap.sh'\"" -e 'end tell' >/dev/null 2>&1; then
  echo "Workout Gate plugin: first-run setup just opened in a separate Terminal window (installs dependencies, then a 30-second wizard with a 2-pushup camera test). Let the user know and invite them to complete it there. Prompts are not gated until setup is done."
else
  echo "Workout Gate plugin is installed but not set up yet. Tell the user to run this once in a terminal: $ROOT/bootstrap.sh"
fi
exit 0
