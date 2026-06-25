"""The UserPromptSubmit hook: escape hatches, dedup, single-flight, routing.
gate.py lives in hooks/ (not the package), so we load it by path."""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HOOKS = Path(__file__).resolve().parent.parent / "hooks"
_spec = importlib.util.spec_from_file_location("gate", HOOKS / "gate.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

from workout_gate import store


def _run(payload, env=None):
    """Run gate.main() with `payload` on stdin and an isolated environment.
    Swallows the hook's user-facing stdout/stderr to keep test output clean."""
    stdin = io.StringIO(json.dumps(payload))
    sink = io.StringIO()
    with mock.patch.object(gate.sys, "stdin", stdin), \
            mock.patch.dict(os.environ, env or {}, clear=False), \
            contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        return gate.main()


class EscapeHatchTest(unittest.TestCase):
    def test_is_escape_forms(self):
        for p in ("/workout", "/workout off", "workout", "workout off",
                  "WORKOUT STATUS", "wg", "wg off", "  workout stop  "):
            self.assertTrue(gate._is_escape(p), p)

    def test_non_escape(self):
        for p in ("make me rich", "fix the bug", "", "work on the gateway"):
            self.assertFalse(gate._is_escape(p), p)


class SourceDetectionTest(unittest.TestCase):
    def _src(self, payload, env):
        with mock.patch.dict(os.environ, env, clear=True):
            return gate._source(payload)

    def test_explicit_marker_wins(self):
        self.assertEqual(self._src({"model": "claude-x"}, {"WORKOUT_GATE_SOURCE": "codex"}), "codex")

    def test_bare_plugin_root_means_codex(self):
        self.assertEqual(self._src({}, {"PLUGIN_ROOT": "/x"}), "codex")

    def test_claude_plugin_root_only_is_claude(self):
        self.assertEqual(self._src({}, {"CLAUDE_PLUGIN_ROOT": "/x"}), "claude")

    def test_non_claude_model_hint(self):
        self.assertEqual(self._src({"model": "gpt-5-codex"}, {}), "codex")

    def test_claude_model_hint(self):
        self.assertEqual(self._src({"model": "claude-opus-4-8"}, {}), "claude")

    def test_default_is_claude(self):
        self.assertEqual(self._src({}, {}), "claude")


class GateFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["WORKOUT_GATE_DIR"] = self.tmp.name
        os.environ.pop("WORKOUT_GATE_OFF", None)

    def tearDown(self):
        os.environ.pop("WORKOUT_GATE_DIR", None)
        self.tmp.cleanup()

    def _due_state(self):
        # a pending debt makes challenge_due() True under any trigger
        st = store.load_state()
        st["debt_reps"] = 5
        st["debt_exercise"] = "pushups"
        store.save_state(st)

    def test_env_off_bypasses(self):
        self._due_state()
        self.assertEqual(_run({"prompt": "go"}, {"WORKOUT_GATE_OFF": "1"}), 0)

    def test_escape_prompt_bypasses(self):
        self._due_state()
        self.assertEqual(_run({"prompt": "workout off"}), 0)

    def test_disabled_config_bypasses(self):
        self._due_state()
        config = store.load_config()
        config["enabled"] = False
        store.save_config(config)
        self.assertEqual(_run({"prompt": "go"}), 0)

    def test_not_due_passes_and_counts(self):
        # default: every 15 prompts, no debt -> not due, but counter advances
        self.assertEqual(_run({"prompt": "hello", "session_id": "s1"}), 0)
        self.assertEqual(store.load_state()["prompt_count"], 1)

    def test_duplicate_same_turn_counted_once(self):
        p = {"prompt": "hello", "session_id": "s1", "turn_id": "t1"}
        _run(p)
        _run(p)  # plugin + global firing the same turn
        self.assertEqual(store.load_state()["prompt_count"], 1)

    def test_distinct_turns_both_count(self):
        _run({"prompt": "hello", "session_id": "s1", "turn_id": "t1"})
        _run({"prompt": "hello", "session_id": "s1", "turn_id": "t2"})
        self.assertEqual(store.load_state()["prompt_count"], 2)

    def test_single_flight_fails_open_when_challenge_running(self):
        self._due_state()
        store.write_challenge_pid()  # a live challenge (this very process)
        try:
            with mock.patch.object(gate, "log"):
                # challenge module must not even be reached
                self.assertEqual(_run({"prompt": "go", "session_id": "s9"}), 0)
        finally:
            store.clear_challenge_pid()

    def test_due_runs_challenge_and_passes(self):
        self._due_state()
        with mock.patch("workout_gate.challenge.should_externalize", return_value=False), \
             mock.patch("workout_gate.challenge.settle_debt", return_value=True) as settle, \
             mock.patch("workout_gate.challenge.pending_summary", return_value="5 pushups"), \
             mock.patch.object(gate, "log"):
            rc = _run({"prompt": "go", "session_id": "s2"})
        self.assertEqual(rc, 0)
        settle.assert_called_once()

    def test_aborted_challenge_blocks(self):
        self._due_state()
        with mock.patch("workout_gate.challenge.should_externalize", return_value=False), \
             mock.patch("workout_gate.challenge.settle_debt", return_value=False), \
             mock.patch("workout_gate.challenge.pending_summary", return_value="5 pushups"), \
             mock.patch.object(gate, "log"):
            rc = _run({"prompt": "go", "session_id": "s3"})
        self.assertEqual(rc, 2)

    def test_aborted_non_blocking_passes_and_resets(self):
        # blocking=false: an aborted challenge must NOT block — the prompt goes
        # through (rc 0) and the debt + counter reset so it doesn't nag.
        self._due_state()
        config = store.load_config()
        config["blocking"] = False
        store.save_config(config)
        st = store.load_state()
        st["prompt_count"] = 7
        store.save_state(st)
        with mock.patch("workout_gate.challenge.should_externalize", return_value=False), \
             mock.patch("workout_gate.challenge.settle_debt", return_value=False), \
             mock.patch("workout_gate.challenge.pending_summary", return_value="5 pushups"), \
             mock.patch.object(gate, "log"):
            rc = _run({"prompt": "go", "session_id": "s5"})
        self.assertEqual(rc, 0)
        s = store.load_state()
        self.assertEqual(s["debt_reps"], 0)
        self.assertEqual(s["debt_offers"], [])
        self.assertEqual(s["prompt_count"], 0)

    def test_desktop_routes_through_terminal(self):
        self._due_state()
        with mock.patch("workout_gate.challenge.should_externalize", return_value=True), \
             mock.patch("workout_gate.challenge.settle_external", return_value=True) as ext, \
             mock.patch("workout_gate.challenge.settle_debt") as inproc, \
             mock.patch("workout_gate.challenge.pending_summary", return_value="5 pushups"), \
             mock.patch.object(gate, "log"):
            rc = _run({"prompt": "go", "session_id": "s4"})
        self.assertEqual(rc, 0)
        ext.assert_called_once()
        inproc.assert_not_called()


if __name__ == "__main__":
    unittest.main()
