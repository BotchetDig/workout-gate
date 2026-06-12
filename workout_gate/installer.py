"""Global (un)install: wire the gate into ~/.claude/settings.json so every
Claude Code session is gated, not just this project.

Edits are surgical: only our own hook entry is added/removed, everything else
in the user's settings is preserved, writes are atomic, and a one-time backup
is kept next to the file.
"""
import json
import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
GATE = PROJECT_DIR / "hooks" / "gate.py"
PYTHON = PROJECT_DIR / ".venv" / "bin" / "python"


def _claude_dir() -> Path:
    return Path.home() / ".claude"


def _settings_path() -> Path:
    return _claude_dir() / "settings.json"


def _command_path() -> Path:
    return _claude_dir() / "commands" / "workout.md"


def _bin_dir() -> Path:
    local = Path.home() / ".local" / "bin"
    local.mkdir(parents=True, exist_ok=True)
    return local


def _launcher_path() -> Path:
    return _bin_dir() / "workout"


def _hook_command() -> str:
    return f'"{PYTHON}" "{GATE}"'


def _is_ours(entry: dict) -> bool:
    return any(str(GATE) in h.get("command", "") or "pushup-gate/hooks/gate.py" in h.get("command", "")
               for h in entry.get("hooks", []))


def _load_settings() -> dict:
    path = _settings_path()
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _write_settings(settings: dict) -> None:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = path.with_suffix(".json.workout-gate.bak")
    if path.exists() and not backup.exists():
        backup.write_text(path.read_text())
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(settings, indent=2) + "\n")
    os.replace(tmp, path)


def is_installed() -> bool:
    entries = _load_settings().get("hooks", {}).get("UserPromptSubmit", [])
    return any(_is_ours(e) for e in entries)


def enable() -> str:
    settings = _load_settings()
    entries = settings.setdefault("hooks", {}).setdefault("UserPromptSubmit", [])
    if not any(_is_ours(e) for e in entries):
        entries.append({"hooks": [{"type": "command", "command": _hook_command(), "timeout": 300}]})
        _write_settings(settings)
    _install_global_command()
    launcher = _install_launcher()
    on_path = str(launcher.parent) in os.environ.get("PATH", "").split(":")
    return (f"Global gate installed in {_settings_path()}\n"
            f"/workout command installed in {_command_path()}\n"
            f"'workout' launcher installed in {launcher}"
            + ("" if on_path else f"  (add {launcher.parent} to your PATH)") + "\n"
            "Type 'workout' in any terminal for the dashboard. "
            "Hook takes effect in NEW Claude Code sessions.")


def disable() -> str:
    settings = _load_settings()
    hooks = settings.get("hooks", {})
    entries = hooks.get("UserPromptSubmit", [])
    kept = [e for e in entries if not _is_ours(e)]
    if len(kept) != len(entries):
        if kept:
            hooks["UserPromptSubmit"] = kept
        else:
            hooks.pop("UserPromptSubmit", None)
        if not hooks:
            settings.pop("hooks", None)
        _write_settings(settings)
    cmd = _command_path()
    if cmd.exists() and str(PROJECT_DIR) in cmd.read_text():
        cmd.unlink()
    launcher = _launcher_path()
    if launcher.exists() and str(PROJECT_DIR) in launcher.read_text():
        launcher.unlink()
    return "Global gate removed. Existing sessions keep their snapshot; new ones are free."


def _install_launcher() -> Path:
    """A 'workout' command on PATH: no args = dashboard, otherwise the CLI."""
    path = _launcher_path()
    path.write_text(f'#!/bin/sh\nexec "{PYTHON}" -m workout_gate "$@"\n')
    path.chmod(0o755)
    return path


def _install_global_command() -> None:
    """Copy the project /workout command globally, with absolute paths so it
    works from any directory."""
    source = PROJECT_DIR / ".claude" / "commands" / "workout.md"
    text = source.read_text().replace(".venv/bin/python", str(PYTHON))
    text = text.replace("with Bash, from the project root, ", "with Bash ")
    target = _command_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def status() -> str:
    return ("Global gate: INSTALLED (all Claude Code sessions)" if is_installed()
            else "Global gate: not installed (this project only)")
