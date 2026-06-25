"""Global (un)install: wire the gate into ~/.claude/settings.json so every
Claude Code session is gated, not just this project.

Edits are surgical: only our own hook entry is added/removed, everything else
in the user's settings is preserved, writes are atomic, and a one-time backup
is kept next to the file.
"""
import json
import os
import shutil
from pathlib import Path

from .paths import PROJECT_DIR, app_dir, python_bin

GATE = PROJECT_DIR / "hooks" / "gate.py"
COMMAND_MARKER = "installed by workout-gate"

# Code dirs/files vendored into ~/.workout-gate/app (no venv, model, tests, git).
_CODE_DIRS = ("workout_gate", "hooks", "commands",
              ".claude-plugin", ".codex-plugin", ".codex")
_CODE_FILES = ("requirements.txt", "README.md", "README.fr.md", "bootstrap.sh")


def _claude_dir() -> Path:
    return Path.home() / ".claude"


def _codex_hooks_path() -> Path:
    return Path.home() / ".codex" / "hooks.json"


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
    return f'"{PROJECT_DIR / "hooks" / "gate.sh"}"'


def _is_ours(entry: dict) -> bool:
    needles = (str(GATE), str(PROJECT_DIR / "hooks" / "gate.sh"), "pushup-gate/hooks/gate.")
    return any(any(n in h.get("command", "") for n in needles)
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
    if cmd.exists() and COMMAND_MARKER in cmd.read_text():
        cmd.unlink()
    launcher = _launcher_path()
    if launcher.exists() and str(PROJECT_DIR) in launcher.read_text():
        launcher.unlink()
    return "Global gate removed. Existing sessions keep their snapshot; new ones are free."


def _install_launcher() -> Path:
    """A 'workout' command on PATH: no args = dashboard, otherwise the CLI.
    Resolves the app dir at runtime (~/.workout-gate/app-path, written by the
    plugin's SessionStart hook) so it survives plugin-cache updates; falls
    back to where this code lives now."""
    path = _launcher_path()
    # Resolve the app dir at RUN time. Prefer the vendored shared runtime
    # (~/.workout-gate/app, kept newest by sync_app on session start) so every
    # tool runs one version; else the newest plugin-cache version, so a reinstall
    # is picked up without waiting for a fresh session (stale app-path + lingering
    # old caches = silently old code).
    path.write_text(f"""#!/bin/sh
APP="$HOME/.workout-gate/app"
[ -f "$APP/workout_gate/__main__.py" ] || \
  APP="$(ls -dt "$HOME"/.claude/plugins/cache/*/workout-gate/*/ 2>/dev/null | head -n1)"
[ -d "$APP" ] || APP="$(cat "$HOME/.workout-gate/app-path" 2>/dev/null || true)"
[ -d "$APP" ] || APP="{PROJECT_DIR}"
PY="$HOME/.workout-gate/venv/bin/python"
[ -x "$PY" ] || PY="$APP/.venv/bin/python"
cd "$APP" && exec "$PY" -m workout_gate "$@"
""")
    path.chmod(0o755)
    return path


# ---- shared runtime vendoring (version divergence fix) ---------------------

def _version_of(root: Path) -> tuple:
    try:
        v = json.loads((root / ".claude-plugin" / "plugin.json").read_text())["version"]
        return tuple(int(x) for x in v.split("."))
    except Exception:
        return (0,)


def sync_app(src: Path = PROJECT_DIR) -> bool:
    """Vendor the runtime code into ~/.workout-gate/app so every surface
    (Claude/Codex, CLI/desktop) runs ONE shared version — the shared state must
    not be driven by two diverging code caches. Copies only when `src` is a
    newer version than what's vendored, and never touches a git-managed checkout
    (the curl installer owns app/ as a clone). Returns True if it copied."""
    dst = app_dir()
    if (dst / ".git").exists():
        return False  # curl/git installer manages this dir
    vendored = (dst / "hooks" / "gate.py").exists()
    if vendored and _version_of(src) <= _version_of(dst):
        return False
    dst.mkdir(parents=True, exist_ok=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    for d in _CODE_DIRS:
        s = src / d
        if s.is_dir():
            shutil.copytree(s, dst / d, dirs_exist_ok=True, ignore=ignore)
    for fn in _CODE_FILES:
        s = src / fn
        if s.is_file():
            shutil.copy2(s, dst / fn)
    return True


# ---- Codex global install (~/.codex/hooks.json) ----------------------------

def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _write_json(path: Path, data: dict) -> None:
    """Atomic write with a one-time backup, like _write_settings but for any
    hooks JSON file (Codex's ~/.codex/hooks.json)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = path.with_name(path.name + ".workout-gate.bak")
    if path.exists() and not backup.exists():
        backup.write_text(path.read_text())
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    os.replace(tmp, path)


def _codex_hook_command() -> str:
    # mark the source so the challenge window tags the speaker CODEX (same voice)
    return f"WORKOUT_GATE_SOURCE=codex {_hook_command()}"


def enable_codex() -> str:
    path = _codex_hooks_path()
    data = _load_json(path)
    entries = data.setdefault("hooks", {}).setdefault("UserPromptSubmit", [])
    if not any(_is_ours(e) for e in entries):
        entries.append({"hooks": [{"type": "command", "command": _codex_hook_command(), "timeout": 300}]})
        _write_json(path, data)
    return (f"Codex gate installed in {path}\n"
            "IMPORTANT: Codex does not auto-trust hooks — approve it once with "
            "/hooks inside Codex.\nTakes effect in NEW Codex sessions.")


def disable_codex() -> str:
    path = _codex_hooks_path()
    data = _load_json(path)
    hooks = data.get("hooks", {})
    entries = hooks.get("UserPromptSubmit", [])
    kept = [e for e in entries if not _is_ours(e)]
    if len(kept) != len(entries):
        if kept:
            hooks["UserPromptSubmit"] = kept
        else:
            hooks.pop("UserPromptSubmit", None)
        if not hooks:
            data.pop("hooks", None)
        _write_json(path, data)
    return "Codex gate removed. New Codex sessions are free."


def is_codex_installed() -> bool:
    entries = _load_json(_codex_hooks_path()).get("hooks", {}).get("UserPromptSubmit", [])
    return any(_is_ours(e) for e in entries)


def codex_status() -> str:
    return ("Codex gate: INSTALLED (all Codex sessions)" if is_codex_installed()
            else "Codex gate: not installed")


def _install_global_command() -> None:
    """Copy the project /workout command globally, with absolute paths so it
    works from any directory."""
    source = PROJECT_DIR / ".claude" / "commands" / "workout.md"
    text = source.read_text().replace(".venv/bin/python", str(python_bin()))
    text = text.replace("with Bash, from the project root, ", "with Bash ")
    text += f"\n<!-- {COMMAND_MARKER} from {PROJECT_DIR} -->\n"
    target = _command_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def status() -> str:
    return ("Global gate: INSTALLED (all Claude Code sessions)" if is_installed()
            else "Global gate: not installed (this project only)")
