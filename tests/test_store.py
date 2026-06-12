import json
import os
import tempfile
import unittest
from pathlib import Path


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["WORKOUT_GATE_DIR"] = self.tmp.name
        # re-import fresh against the temp dir
        from workout_gate import store
        self.store = store

    def tearDown(self):
        del os.environ["WORKOUT_GATE_DIR"]
        self.tmp.cleanup()

    def test_defaults(self):
        config = self.store.load_config()
        self.assertTrue(config["enabled"])
        self.assertEqual(config["every_n_prompts"], 15)
        self.assertEqual(self.store.load_state()["debt_reps"], 0)
        self.assertEqual(self.store.load_stats()["total_reps"], 0)

    def test_roundtrip(self):
        state = self.store.load_state()
        state["debt_reps"] = 7
        self.store.save_state(state)
        self.assertEqual(self.store.load_state()["debt_reps"], 7)

    def test_record_rep(self):
        self.store.record_rep()
        self.store.record_rep()
        stats = self.store.load_stats()
        self.assertEqual(stats["total_reps"], 2)
        self.assertEqual(stats["by_day"][self.store.today()], 2)
        self.assertEqual(stats["by_exercise"]["pushups"], 2)

    def test_corrupt_file_falls_back_to_defaults(self):
        (Path(self.tmp.name) / "stats.json").write_text("{not json!!")
        self.assertEqual(self.store.load_stats()["total_reps"], 0)

    def test_atomic_write_leaves_no_partial_file(self):
        self.store.save_stats({"total_reps": 5, "by_day": {}, "by_exercise": {}})
        on_disk = json.loads((Path(self.tmp.name) / "stats.json").read_text())
        self.assertEqual(on_disk["total_reps"], 5)
        self.assertFalse((Path(self.tmp.name) / "stats.tmp").exists())

    def test_challenge_pid_lifecycle(self):
        self.assertIsNone(self.store.running_challenge_pid())
        self.store.write_challenge_pid()
        self.assertEqual(self.store.running_challenge_pid(), os.getpid())
        self.store.clear_challenge_pid()
        self.assertIsNone(self.store.running_challenge_pid())

    def test_stale_pid_cleaned_up(self):
        (Path(self.tmp.name) / "challenge.pid").write_text("99999999")
        self.assertIsNone(self.store.running_challenge_pid())
        self.assertFalse((Path(self.tmp.name) / "challenge.pid").exists())

    def test_unknown_keys_preserved_with_new_defaults(self):
        """A config written by an older/newer version keeps defaults for
        missing keys (forward-compat)."""
        (Path(self.tmp.name) / "config.json").write_text('{"enabled": false}')
        config = self.store.load_config()
        self.assertFalse(config["enabled"])
        self.assertEqual(config["exercises"]["pushups"]["reps_min"], 5)

    def test_legacy_reps_migrate_to_pushups(self):
        """A pre-squats config with top-level reps_min/reps_max seeds pushups."""
        (Path(self.tmp.name) / "config.json").write_text('{"reps_min": 7, "reps_max": 12}')
        config = self.store.load_config()
        self.assertEqual(config["exercises"]["pushups"]["reps_min"], 7)
        self.assertEqual(config["exercises"]["pushups"]["reps_max"], 12)
        self.assertIn("squats", config["exercises"])
        self.assertNotIn("reps_min", config)  # legacy keys dropped

    def test_load_config_does_not_mutate_defaults(self):
        c1 = self.store.load_config()
        c1["exercises"]["pushups"]["reps_min"] = 99
        self.assertEqual(self.store.DEFAULT_CONFIG["exercises"]["pushups"]["reps_min"], 5)


if __name__ == "__main__":
    unittest.main()
