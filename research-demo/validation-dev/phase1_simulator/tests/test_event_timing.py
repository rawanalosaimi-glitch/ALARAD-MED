"""
Unit tests for event timing (Phase 1 deliverable C, item 3).
"""

from __future__ import annotations

import unittest
from pathlib import Path

from phase1_simulator import config as cfg_mod
from phase1_simulator import scenario

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "simulation_config.json"


class TestEventTiming(unittest.TestCase):
    def setUp(self):
        self.config = cfg_mod.load_config(CONFIG_PATH)

    def test_step_event_window_matches_pattern_parameters(self):
        run = scenario.generate_run("sudden_increase", 2001, self.config)
        w = run.workers[0]
        self.assertEqual(len(w.truth_events), 1)
        ev = w.truth_events[0]
        self.assertEqual(ev.start, w.pattern["start"])
        self.assertEqual(ev.end, w.pattern["end"])

    def test_step_series_is_elevated_only_within_window(self):
        run = scenario.generate_run("sudden_increase", 2002, self.config)
        simulated = scenario.simulate_run(run, self.config)
        w = run.workers[0]
        ev = w.truth_events[0]
        true_series = simulated["workers"][0]["true_series"]
        baseline = w.baseline_rate_uSv_h
        for t, v in enumerate(true_series):
            if ev.start <= t < ev.end:
                self.assertGreater(v, baseline * 1.5)
            else:
                self.assertAlmostEqual(v, baseline, places=9)

    def test_ramp_event_window_matches_pattern_parameters(self):
        run = scenario.generate_run("gradual_increase", 2004, self.config)
        w = run.workers[0]
        ev = w.truth_events[0]
        self.assertEqual(ev.start, w.pattern["start"])
        self.assertEqual(ev.end, w.pattern["hold_until"])

    def test_ramp_series_is_monotonic_non_decreasing_during_rise(self):
        run = scenario.generate_run("gradual_increase", 2006, self.config)
        simulated = scenario.simulate_run(run, self.config)
        w = run.workers[0]
        p = w.pattern
        true_series = simulated["workers"][0]["true_series"]
        prev = true_series[p["start"]]
        for t in range(p["start"], p["peak_at"]):
            self.assertGreaterEqual(true_series[t], prev - 1e-9)
            prev = true_series[t]

    def test_transient_spike_is_not_labelled_as_a_truth_event(self):
        # Reuses the S5 convention documented in
        # Ground_Truth_Scenarios_S1-S13.md: a short transient is a
        # false-positive-suppression test, not a labelled abnormal event.
        run = scenario.generate_run("transient_spike", 2003, self.config)
        w = run.workers[0]
        self.assertEqual(w.truth_events, [])
        self.assertEqual(w.pattern["type"], "spikes")

    def test_fault_window_duration_matches_configured_range(self):
        run = scenario.generate_run("fault_missing", 2005, self.config)
        w = run.workers[0]
        self.assertEqual(len(w.fault_windows), 1)
        f = w.fault_windows[0]
        lo, hi = self.config.provisional_parameters["fault_duration_range_minutes"]["missing"]
        self.assertGreaterEqual(f.end - f.start, 1)
        self.assertLessEqual(f.end - f.start, int(hi))

    def test_area_relocation_truth_window_ends_at_move_time(self):
        run = scenario.generate_run("area_relocation", 2007, self.config)
        w = run.workers[0]
        ev = w.truth_events[0]
        self.assertEqual(ev.end, w.area_params["move_at"])


if __name__ == "__main__":
    unittest.main()
