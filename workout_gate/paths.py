"""Runtime path resolution. Two install flavors share one codebase:

- dev / git-clone: venv and model live in the project folder (.venv/, models/)
- plugin: code lives in Claude Code's plugin cache (wiped on update), so the
  venv and model live in ~/.workout-gate/ alongside the data files

Everything resolves runtime-first, project-second.
"""
import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
MODEL_NAME = "pose_landmarker_full.task"


def runtime_home() -> Path:
    return Path(os.environ.get("WORKOUT_GATE_DIR", Path.home() / ".workout-gate"))


def python_bin() -> Path:
    runtime = runtime_home() / "venv" / "bin" / "python"
    return runtime if runtime.exists() else PROJECT_DIR / ".venv" / "bin" / "python"


def model_path() -> Path:
    runtime = runtime_home() / "models" / MODEL_NAME
    return runtime if runtime.exists() else PROJECT_DIR / "models" / MODEL_NAME
