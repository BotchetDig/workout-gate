"""installer.sync_app(): vendor one shared runtime into ~/.workout-gate/app so
Claude and Codex can't drive the shared state from two diverging code versions."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from workout_gate import installer


class SyncAppTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["WORKOUT_GATE_DIR"] = self.tmp.name
        self.app = Path(self.tmp.name) / "app"

    def tearDown(self):
        os.environ.pop("WORKOUT_GATE_DIR", None)
        self.tmp.cleanup()

    def _fake_src(self, version: str) -> Path:
        """A minimal but valid code dir with a given plugin version."""
        src = Path(self.tmp.name) / f"src-{version}"
        (src / ".claude-plugin").mkdir(parents=True)
        (src / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "workout-gate", "version": version}))
        (src / "hooks").mkdir()
        (src / "hooks" / "gate.py").write_text(f"# v{version}\n")
        (src / "workout_gate").mkdir()
        (src / "workout_gate" / "__main__.py").write_text("# main\n")
        (src / "requirements.txt").write_text("mediapipe\n")
        return src

    def test_fresh_vendor_copies_code(self):
        self.assertTrue(installer.sync_app(self._fake_src("1.0.0")))
        self.assertTrue((self.app / "hooks" / "gate.py").exists())
        self.assertTrue((self.app / "workout_gate" / "__main__.py").exists())
        self.assertTrue((self.app / "requirements.txt").exists())

    def test_same_version_is_noop(self):
        src = self._fake_src("1.0.0")
        self.assertTrue(installer.sync_app(src))
        self.assertFalse(installer.sync_app(src))

    def test_newer_version_overwrites(self):
        installer.sync_app(self._fake_src("1.0.0"))
        self.assertTrue(installer.sync_app(self._fake_src("2.3.1")))
        self.assertIn("v2.3.1", (self.app / "hooks" / "gate.py").read_text())

    def test_older_version_ignored(self):
        installer.sync_app(self._fake_src("2.0.0"))
        self.assertFalse(installer.sync_app(self._fake_src("1.0.0")))
        self.assertIn("v2.0.0", (self.app / "hooks" / "gate.py").read_text())

    def test_git_checkout_is_never_touched(self):
        # the curl/git installer owns app/ as a clone — leave it alone
        self.app.mkdir(parents=True)
        (self.app / ".git").mkdir()
        self.assertFalse(installer.sync_app(self._fake_src("9.9.9")))
        self.assertFalse((self.app / "hooks").exists())

    def test_real_project_vendors(self):
        # the actual repo is a valid source
        self.assertTrue(installer.sync_app())
        self.assertTrue((self.app / "workout_gate" / "store.py").exists())
        self.assertTrue((self.app / "hooks" / "gate.sh").exists())


if __name__ == "__main__":
    unittest.main()
