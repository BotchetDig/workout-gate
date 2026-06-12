import json
import os
import tempfile
import unittest
from pathlib import Path

from workout_gate import installer


class InstallerTest(unittest.TestCase):
    """Runs against a fake HOME so the user's real ~/.claude is never touched."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_home = os.environ["HOME"]
        os.environ["HOME"] = self.tmp.name
        self.settings = Path(self.tmp.name) / ".claude" / "settings.json"

    def tearDown(self):
        os.environ["HOME"] = self.old_home
        self.tmp.cleanup()

    def test_enable_installs_launcher(self):
        installer.enable()
        launcher = Path(self.tmp.name) / ".local" / "bin" / "workout"
        self.assertTrue(launcher.exists())
        self.assertTrue(os.access(launcher, os.X_OK))
        content = launcher.read_text()
        self.assertIn(str(installer.PROJECT_DIR), content)
        self.assertIn(".workout-gate/venv", content)  # runtime venv preferred
        installer.disable()
        self.assertFalse(launcher.exists())

    def test_disable_keeps_foreign_launcher(self):
        bin_dir = Path(self.tmp.name) / ".local" / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "workout").write_text("#!/bin/sh\necho someone else's tool\n")
        installer.disable()
        self.assertTrue((bin_dir / "workout").exists())

    def test_enable_creates_hook_and_command(self):
        installer.enable()
        settings = json.loads(self.settings.read_text())
        entries = settings["hooks"]["UserPromptSubmit"]
        self.assertEqual(len(entries), 1)
        self.assertIn("gate.sh", entries[0]["hooks"][0]["command"])
        self.assertEqual(entries[0]["hooks"][0]["timeout"], 300)
        command = (Path(self.tmp.name) / ".claude" / "commands" / "workout.md").read_text()
        self.assertIn(installer.COMMAND_MARKER, command)
        self.assertNotIn(" .venv/bin/python", command)
        self.assertTrue(installer.is_installed())

    def test_enable_preserves_existing_settings(self):
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text(json.dumps({
            "model": "claude-fable-5",
            "hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": "echo hi"}]}]},
        }))
        installer.enable()
        settings = json.loads(self.settings.read_text())
        self.assertEqual(settings["model"], "claude-fable-5")
        self.assertEqual(len(settings["hooks"]["UserPromptSubmit"]), 2)
        self.assertEqual(settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"], "echo hi")
        # backup of the pre-existing file was kept
        self.assertTrue(self.settings.with_suffix(".json.workout-gate.bak").exists())

    def test_enable_is_idempotent(self):
        installer.enable()
        installer.enable()
        settings = json.loads(self.settings.read_text())
        self.assertEqual(len(settings["hooks"]["UserPromptSubmit"]), 1)

    def test_disable_removes_only_ours(self):
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text(json.dumps({
            "hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": "echo hi"}]}]},
        }))
        installer.enable()
        installer.disable()
        settings = json.loads(self.settings.read_text())
        self.assertEqual(len(settings["hooks"]["UserPromptSubmit"]), 1)
        self.assertEqual(settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"], "echo hi")
        self.assertFalse((Path(self.tmp.name) / ".claude" / "commands" / "workout.md").exists())
        self.assertFalse(installer.is_installed())

    def test_disable_cleans_empty_containers(self):
        installer.enable()
        installer.disable()
        settings = json.loads(self.settings.read_text())
        self.assertNotIn("hooks", settings)

    def test_disable_when_never_installed(self):
        installer.disable()  # must not raise
        self.assertFalse(installer.is_installed())


if __name__ == "__main__":
    unittest.main()
