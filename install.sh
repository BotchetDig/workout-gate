#!/usr/bin/env bash
# Workout Gate installer: venv + deps + pose model. Run once after cloning.
#   ./install.sh            -> gate active in this folder only
#   ./install.sh --global   -> gate active in ALL your Claude Code sessions
set -euo pipefail
cd "$(dirname "$0")"

MODEL_URL="https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task"

echo "==> Creating virtualenv..."
python3 -m venv .venv

echo "==> Installing dependencies (mediapipe, opencv)..."
.venv/bin/pip install -q -r requirements.txt

if [ ! -f models/pose_landmarker_full.task ]; then
  echo "==> Downloading pose model (~9 MB)..."
  mkdir -p models
  curl -sL -o models/pose_landmarker_full.task "$MODEL_URL"
fi

echo "==> Running tests..."
.venv/bin/python -m unittest discover -s tests >/dev/null 2>&1 && echo "    all green"

if [ "${1:-}" = "--global" ]; then
  echo "==> Installing globally (all Claude Code sessions)..."
  .venv/bin/python -m workout_gate global on
fi

cat <<'EOF'

Done! Open a Claude Code session in this folder and the gate is live
(challenge every 15 prompts by default).

Try it now:        .venv/bin/python -m workout_gate now
From Claude Code:  /workout now | stats | preset demo | off
First run on macOS: grant camera access to your terminal when asked.
EOF
