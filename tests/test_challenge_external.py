"""Desktop routing decision: when to run the challenge in a Terminal window
instead of in-process (camera permission + visible window under desktop apps)."""
import os
import tempfile
import unittest
from unittest import mock

from workout_gate import challenge, store


class ShouldExternalizeTest(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("WORKOUT_GATE_TERMINAL", None)

    def test_env_force_on(self):
        os.environ["WORKOUT_GATE_TERMINAL"] = "1"
        self.assertTrue(challenge.should_externalize())

    def test_env_force_off(self):
        os.environ["WORKOUT_GATE_TERMINAL"] = "0"
        with mock.patch.object(challenge.sys, "platform", "darwin"):
            self.assertFalse(challenge.should_externalize())

    def test_non_darwin_is_inprocess(self):
        with mock.patch.object(challenge.sys, "platform", "linux"):
            self.assertFalse(challenge.should_externalize())

    def test_darwin_with_tty_is_inprocess(self):
        with mock.patch.object(challenge.sys, "platform", "darwin"), \
             mock.patch.object(challenge.os, "open", return_value=3), \
             mock.patch.object(challenge.os, "close"):
            self.assertFalse(challenge.should_externalize())

    def test_darwin_without_tty_externalizes(self):
        with mock.patch.object(challenge.sys, "platform", "darwin"), \
             mock.patch.object(challenge.os, "open", side_effect=OSError):
            self.assertTrue(challenge.should_externalize())


class TerminalCommandTest(unittest.TestCase):
    def test_command_cds_and_pays(self):
        cmd = challenge._terminal_command("/rt/venv/bin/python", "/code/app")
        self.assertIn("cd /code/app", cmd)
        self.assertIn("-m workout_gate pay", cmd)
        self.assertIn("/rt/venv/bin/python", cmd)

    def test_command_marks_the_slot_as_claimed(self):
        # the Terminal child must skip its own "already open" guard
        cmd = challenge._terminal_command("/rt/py", "/code/app")
        self.assertIn("WORKOUT_GATE_CLAIMED=1", cmd)

    def test_command_carries_the_source(self):
        cmd = challenge._terminal_command("/rt/py", "/code/app", source="codex")
        self.assertIn("WORKOUT_GATE_SOURCE=codex", cmd)

    def test_paths_with_spaces_are_quoted(self):
        cmd = challenge._terminal_command("/rt/py", "/Code Dir/app")
        self.assertIn("'/Code Dir/app'", cmd)  # shlex.quote protects the space


class SettleExternalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["WORKOUT_GATE_DIR"] = self.tmp.name

    def tearDown(self):
        os.environ.pop("WORKOUT_GATE_DIR", None)
        self.tmp.cleanup()

    def _owe(self, reps=5):
        st = store.load_state()
        st["debt_reps"] = reps
        st["debt_offers"] = []
        store.save_state(st)

    def test_falls_back_inprocess_when_terminal_unavailable(self):
        def boom():
            raise OSError("no Terminal")
        with mock.patch.object(challenge, "settle_debt", return_value=True) as fallback:
            self.assertTrue(challenge.settle_external(_runner=boom))
        fallback.assert_called_once()

    def test_returns_early_when_debt_cleared(self):
        self._owe()

        def runner():  # the "Terminal child" pays instantly
            st = store.load_state()
            st["debt_reps"] = 0
            st["debt_offers"] = []
            store.save_state(st)
        # large timeout: if it waited it out the test would hang — it must exit early
        self.assertTrue(challenge.settle_external(timeout_s=30, poll_s=0.01, _runner=runner))

    def test_times_out_to_false_when_nothing_runs(self):
        self._owe()
        self.assertFalse(
            challenge.settle_external(timeout_s=0.2, poll_s=0.01, _runner=lambda: None))


if __name__ == "__main__":
    unittest.main()
