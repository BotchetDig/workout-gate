#!/bin/sh
# Workout Gate one-line installer:
#   curl -fsSL https://raw.githubusercontent.com/BotchetDig/workout-gate/main/get.sh | bash
#
# Clones (or updates) the app into ~/.workout-gate/app and runs the installer.
set -eu

REPO_URL="${WORKOUT_GATE_REPO:-https://github.com/BotchetDig/workout-gate.git}"
APP_DIR="${WORKOUT_GATE_APP_DIR:-$HOME/.workout-gate/app}"

command -v git >/dev/null 2>&1 || { echo "error: git is required"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "error: python3 (3.10+) is required"; exit 1; }

if [ -d "$APP_DIR/.git" ]; then
  echo "==> Updating existing install in $APP_DIR"
  git -C "$APP_DIR" pull --ff-only
else
  echo "==> Installing Workout Gate into $APP_DIR"
  mkdir -p "$(dirname "$APP_DIR")"
  git clone --depth 1 "$REPO_URL" "$APP_DIR"
fi

# When run as `curl | bash`, stdin is the script itself - reattach the real
# terminal so the setup wizard stays interactive.
if [ -t 0 ]; then
  exec "$APP_DIR/install.sh"
elif (exec </dev/tty) 2>/dev/null; then
  exec "$APP_DIR/install.sh" </dev/tty
else
  exec "$APP_DIR/install.sh" --no-setup
fi
