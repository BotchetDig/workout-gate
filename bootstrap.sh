#!/bin/sh
# Workout Gate runtime bootstrap: installs the heavy bits OUTSIDE the code
# directory (into ~/.workout-gate/) so plugin updates never break the install,
# then runs the setup wizard. Idempotent - safe to re-run.
#   bootstrap.sh [--no-setup]
set -eu
ROOT="$(cd "$(dirname "$0")" && pwd)"
HOME_DIR="${WORKOUT_GATE_DIR:-$HOME/.workout-gate}"
VENV="$HOME_DIR/venv"
MODEL_URL="https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task"

B="\033[1m"; D="\033[2m"; G="\033[92m"; C="\033[96m"; E="\033[0m"

printf "\n${B}  WORKOUT GATE${E}  ${D}pushups before prompts${E}\n\n"

command -v python3 >/dev/null 2>&1 || { printf "  error: python3 (3.10+) is required\n"; exit 1; }

printf "  ${C}[1/3]${E} Python environment + dependencies ${D}(mediapipe, opencv - 1-2 min the first time)${E}\n"
mkdir -p "$HOME_DIR"
echo "$ROOT" > "$HOME_DIR/app-path"
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q -r "$ROOT/requirements.txt"

printf "  ${C}[2/3]${E} Pose model ${D}(~9 MB, one time)${E}\n"
mkdir -p "$HOME_DIR/models"
[ -f "$HOME_DIR/models/pose_landmarker_full.task" ] || \
  curl -fsSL -o "$HOME_DIR/models/pose_landmarker_full.task" "$MODEL_URL"

printf "  ${C}[3/3]${E} Sanity check\n"
(cd "$ROOT" && "$VENV/bin/python" -m unittest discover -s tests >/dev/null 2>&1) \
  && printf "        ${G}all tests green${E}\n"

if [ "${1:-}" = "--no-setup" ] || [ ! -t 0 ]; then
  printf "\n  ${G}Runtime ready.${E} Run the wizard anytime: ${B}workout setup${E}\n\n"
else
  cd "$ROOT" && WORKOUT_GATE_PLUGIN="${WORKOUT_GATE_PLUGIN:-1}" "$VENV/bin/python" -m workout_gate setup
fi
