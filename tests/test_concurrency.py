"""The cross-process lock around state's read-modify-write. Atomic writes stop
corruption; this stops lost updates when several tools/sessions fire at once."""
import multiprocessing
import os
import tempfile
import threading
import time
import unittest

from workout_gate import store


def _mp_increment(dirpath, k):
    """Worker run in a separate PROCESS (the real cross-tool case): bump the
    shared prompt counter k times under the lock."""
    os.environ["WORKOUT_GATE_DIR"] = dirpath
    from workout_gate import store as s

    def _inc(st):
        st["prompt_count"] = st["prompt_count"] + 1
    for _ in range(k):
        s.mutate_state(_inc)


def _mp_claim(dirpath, q):
    os.environ["WORKOUT_GATE_DIR"] = dirpath
    from workout_gate import store as s
    q.put(s.try_claim_challenge())
    time.sleep(0.3)  # hold the claim so the sibling definitely contends


class LockedMutateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["WORKOUT_GATE_DIR"] = self.tmp.name

    def tearDown(self):
        os.environ.pop("WORKOUT_GATE_DIR", None)
        self.tmp.cleanup()

    def test_concurrent_increments_are_not_lost(self):
        store.save_state(store.load_state())  # seed prompt_count=0
        N = 25

        def bump():
            def _inc(st):
                cur = st["prompt_count"]
                time.sleep(0.001)  # widen the read->write window
                st["prompt_count"] = cur + 1
            store.mutate_state(_inc)

        threads = [threading.Thread(target=bump) for _ in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(store.load_state()["prompt_count"], N)

    def test_locked_serializes_critical_sections(self):
        timeline = []

        def worker(tag):
            with store.locked():
                timeline.append(("enter", tag))
                time.sleep(0.005)
                timeline.append(("exit", tag))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # never two enters in a row without an exit between -> no overlap
        depth = 0
        for kind, _ in timeline:
            depth += 1 if kind == "enter" else -1
            self.assertIn(depth, (0, 1))

    def test_mutate_state_returns_mutator_value(self):
        out = store.mutate_state(lambda st: st["prompt_count"] + 100)
        self.assertEqual(out, 100)

    def test_multiprocess_increments_are_not_lost(self):
        """The real cross-tool case: separate processes, not threads."""
        store.save_state(store.load_state())  # seed prompt_count=0
        ctx = multiprocessing.get_context("spawn")
        P, K = 4, 12
        procs = [ctx.Process(target=_mp_increment, args=(self.tmp.name, K)) for _ in range(P)]
        for p in procs:
            p.start()
        for p in procs:
            p.join()
        self.assertEqual(store.load_state()["prompt_count"], P * K)


class ClaimSingleFlightTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["WORKOUT_GATE_DIR"] = self.tmp.name

    def tearDown(self):
        os.environ.pop("WORKOUT_GATE_DIR", None)
        self.tmp.cleanup()

    def test_only_one_process_claims_the_slot(self):
        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        procs = [ctx.Process(target=_mp_claim, args=(self.tmp.name, q)) for _ in range(2)]
        for p in procs:
            p.start()
        for p in procs:
            p.join()
        results = sorted([q.get(), q.get()])
        self.assertEqual(results, [False, True])  # exactly one winner


if __name__ == "__main__":
    unittest.main()
