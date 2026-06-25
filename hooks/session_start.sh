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
MODEL="$HOME_DIR/models/pose_landmarker_full.task"

# "Ready" means the runtime can actually run a challenge: venv python + deps
# importable + pose model on disk. The old check was just `[ -x "$PY" ]`, but
# bootstrap.sh creates the venv BEFORE installing deps and the model, so a first
# run that died half-way (network blip, closed window) left a python binary with
# no cv2/mediapipe/model - and this hook then treated it as set up forever, the
# gate silently fail-opening on every challenge. Verify for real: the cheap
# `ready` marker (written by bootstrap on success) is the fast path; an install
# from before the marker existed is blessed once via a real import check.
ready=0
if [ -x "$PY" ] && [ -f "$MODEL" ]; then
    if [ -f "$HOME_DIR/ready" ]; then
        ready=1
    elif "$PY" -c "import cv2, mediapipe" >/dev/null 2>&1; then
        : > "$HOME_DIR/ready"
        ready=1
    fi
fi

if [ "$ready" = 1 ]; then  # set up: refresh launcher + vendor newest code, stay silent
    ( cd "$ROOT" && "$PY" -c "from workout_gate import installer; installer._install_launcher(); installer.sync_app()" ) >/dev/null 2>&1 || true
    exit 0
fi

# Not ready: a first run, or a previous bootstrap that never finished. (Re)open
# it - but only one at a time, so several sessions starting at once don't run
# concurrent pip installs into the same venv. `mkdir` is the atomic claim; a
# stale lock (>15 min = the old attempt died) is cleared first. bootstrap.sh
# removes the lock and writes `ready` on success.
LOCK="$HOME_DIR/bootstrapping"
[ -n "$(find "$LOCK" -prune -mmin +15 2>/dev/null)" ] && rmdir "$LOCK" 2>/dev/null
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "Workout Gate is still finishing its first-run setup in another Terminal window (installing dependencies + pose model). Tell the user to let it complete; prompts aren't gated until it's done."
  exit 0
fi

if command -v osascript >/dev/null 2>&1 && \
   osascript -e 'tell application "Terminal"' -e 'activate' \
             -e "do script \"exec '$ROOT/bootstrap.sh'\"" -e 'end tell' >/dev/null 2>&1; then
  echo "Workout Gate plugin: first-run setup just opened in a separate Terminal window (installs dependencies, then a 30-second wizard with a 2-pushup camera test). Let the user know and invite them to complete it there. Prompts are not gated until setup is done."
else
  rmdir "$LOCK" 2>/dev/null  # nothing will finish the bootstrap, so don't hold the lock
  echo "Workout Gate plugin is installed but not set up yet. Tell the user to run this once in a terminal: $ROOT/bootstrap.sh"
fi
exit 0
