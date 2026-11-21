"""
Unit tests for ground-truth consistency (Phase 1 deliverable C, item 4).
"""

from __future__ import annotations

import unittest
from pathlib import Path

from phase1_simulator import config as cfg_mod
from phase1_simulator import scenario, units

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "simulation_config.json"


class TestGroundTruthConsistency(unittest.TestCase):
    def setUp(self):
        self.config = cfg_mod.load_config(CONFIG_PATH)

    def test_all_truth_and_fault_windows_are_within_shift_bounds(self):
        for archetype in scenario.ARCHETYPES:
            run = scenario.generate_run(archetype, 3001, self.config)
            for w in run.workers:
                for ev in w.truth_events:
                    self.assertGreaterEqual(ev.start, 0, msg=archetype)
                    self.assertLessEqual(ev.end, run.shift_minutes, msg=archetype)
                    self.assertLess(ev.start, ev.end, msg=archetype)
                for f in w.fault_windows:
                    self.assertGreaterEqual(f.start, 0, msg=archetype)
                    self.assertLessEqual(f.end, run.shift_minutes, msg=archetype)
                    self.assertLess(f.start, f.end, msg=archetype)

    def test_missing_fault_produces_none_observations_only_in_window(self):
        run = scenario.generate_run("fault_missing", 3002, self.config)
        simulated = scenario.simulate_run(run, self.config)
        w = run.workers[0]
        f = w.fault_windows[0]
        observed = simulated["workers"][0]["observed_series"]
        for t in range(f.start, f.end):
            self.assertIsNone(observed[t])
        for t in range(0, f.start):
            self.assertIsNotNone(observed[t])

    def test_frozen_fault_repeats_exact_value_for_whole_window(self):
        run = scenario.generate_run("fault_frozen", 3003, self.config)
        simulated = scenario.simulate_run(run, self.config)
        w = run.workers[0]
        f = w.fault_windows[0]
        observed = simulated["workers"][0]["observed_series"]
        frozen_value = observed[f.start]
        for t in range(f.start, f.end):
            self.assertEqual(observed[t], frozen_value)

    def test_invalid_fault_produces_non_physical_values(self):
        run = scenario.generate_run("fault_invalid", 3004, self.config)
        simulated = scenario.simulate_run(run, self.config)
        w = run.workers[0]
        f = w.fault_windows[0]
        observed = simulated["workers"][0]["observed_series"]
        for t in range(f.start, f.end):
            self.assertFalse(units.is_valid_rate(observed[t]))

    def test_delayed_fault_has_initial_gap_then_stale_values(self):
        run = scenario.generate_run("fault_delayed", 3005, self.config)
        simulated = scenario.simulate_run(run, self.config)
        w = run.workers[0]
        f = w.fault_windows[0]
        lag = f.params["lag"]
        observed = simulated["workers"][0]["observed_series"]
        for t in range(f.start, min(f.start + lag, f.end)):
            self.assertIsNone(observed[t])
        for t in range(f.start + lag, f.end):
            self.assertIsNotNone(observed[t])

    def test_no_truth_or_fault_events_for_normal_archetype(self):
        run = scenario.generate_run("normal", 3006, self.config)
        w = run.workers[0]
        self.assertEqual(w.truth_events, [])
        self.assertEqual(w.fault_windows, [])

    def test_ground_truth_schema_fields_present_and_typed(self):
        run = scenario.generate_run("concurrent_alert_and_fault", 3007, self.config)
        w = run.workers[0]
        self.assertTrue(w.truth_events)
        self.assertTrue(w.fault_windows)
        for ev in w.truth_events:
            self.assertIsInstance(ev.start, int)
            self.assertIsInstance(ev.end, int)
            self.assertIsInstance(ev.label, str)
        for f in w.fault_windows:
            self.assertIn(f.kind, {"missing", "invalid", "frozen", "delayed"})
            self.assertIsInstance(f.params, dict)

    def test_dual_layer_independence_multi_worker_faults(self):
        # Mirrors the S12 cross-worker-independence precedent in
        # Ground_Truth_Scenarios_S1-S13.md: perturbing one worker's fault
        # must not create a truth/fault event on a different worker.
        run = scenario.generate_run("multi_worker_faults", 3008, self.config)
        w0, w1, w2 = run.workers
        self.assertEqual(w0.truth_events, [])
        self.assertEqual(len(w0.fault_windows), 1)
        self.assertEqual(w0.fault_windows[0].kind, "missing")
        self.assertEqual(len(w1.truth_events), 1)
        self.assertEqual(len(w1.fault_windows), 1)
        self.assertEqual(w1.fault_windows[0].kind, "invalid")
        self.assertEqual(w2.truth_events, [])
        self.assertEqual(len(w2.fault_windows), 1)
        self.assertEqual(w2.fault_windows[0].kind, "frozen")


if __name__ == "__main__":
    unittest.main()
