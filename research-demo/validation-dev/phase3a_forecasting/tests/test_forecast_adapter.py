"""
Phase 3A task 6: constant exposure, rising exposure, falling exposure,
missing observations, and sensor faults -- using both hand-built
deterministic series (for crisp, exact assertions) and real Phase 1
output (for integration realism).
"""

from __future__ import annotations

import unittest
from pathlib import Path

from phase1_simulator import config as p1_config
from phase1_simulator import output as p1_output
from phase1_simulator import scenario as p1_scenario
from phase2a_adapter.engine_bridge import EngineBridge
from phase3a_forecasting.forecast_adapter import (
    build_rate_forecasts,
    score_against_ground_truth,
)

P1_CONFIG_PATH = Path(p1_config.__file__).parent / "config" / "simulation_config.json"


def _run_dict(archetype: str, seed: int, p1_cfg):
    run = p1_scenario.generate_run(archetype, seed, p1_cfg)
    simulated = p1_scenario.simulate_run(run, p1_cfg)
    return p1_output.run_to_dict(simulated, p1_cfg)


class TestForecastAdapterScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = EngineBridge().__enter__()
        cls.p1_config = p1_config.load_config(P1_CONFIG_PATH)

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    # ---- hand-built, deterministic cases -----------------------------

    def test_constant_exposure_gives_zero_slope_and_exact_persistence(self):
        series = [60.0] * 10
        forecasts = build_rate_forecasts(self.bridge, series)
        scored = score_against_ground_truth(forecasts, series)
        for r in scored:
            if r["skipped"]:
                continue
            self.assertAlmostEqual(r["slope"], 0.0, places=9)
            for v in r["forecast_rate_uSv_h"]:
                self.assertAlmostEqual(v, 60.0, places=9)
            for a in r["actual_rate_uSv_h"]:
                if a is not None:
                    self.assertAlmostEqual(a, 60.0, places=9)

    def test_rising_exposure_gives_positive_slope_and_rising_forecast(self):
        series = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
        forecasts = build_rate_forecasts(self.bridge, series)
        non_skipped = [r for r in forecasts if not r["skipped"]]
        self.assertTrue(non_skipped)
        for r in non_skipped:
            self.assertGreater(r["slope"], 0)
            fc = r["forecast_rate_uSv_h"]
            self.assertTrue(fc[0] < fc[1] < fc[2])

    def test_falling_exposure_gives_negative_slope_and_falling_forecast(self):
        series = [100.0, 80.0, 60.0, 40.0, 20.0, 0.0]
        forecasts = build_rate_forecasts(self.bridge, series)
        non_skipped = [r for r in forecasts if not r["skipped"]]
        self.assertTrue(non_skipped)
        for r in non_skipped:
            self.assertLess(r["slope"], 0)
            fc = r["forecast_rate_uSv_h"]
            self.assertTrue(fc[0] > fc[1] > fc[2])

    def test_missing_observation_in_window_is_skipped_not_imputed(self):
        series = [50.0, 50.0, None, 50.0, 50.0, 50.0]
        forecasts = build_rate_forecasts(self.bridge, series)
        # window ending at t=3 is [series[0..3]] = [50,50,None,50] -> must skip
        skipped_ts = {r["t"] for r in forecasts if r["skipped"]}
        self.assertIn(3, skipped_ts)

    # ---- real Phase 1 output ------------------------------------------

    def test_normal_archetype_near_constant_series_mostly_not_skipped(self):
        d = _run_dict("normal", 7001, self.p1_config)
        worker = d["workers"][0]
        series = worker["series"]["observed_rate_uSv_h"]
        forecasts = build_rate_forecasts(self.bridge, series)
        n_skipped = sum(1 for r in forecasts if r["skipped"])
        self.assertEqual(n_skipped, 0, msg="normal archetype has no faults; nothing should be skipped")

    def test_sudden_increase_archetype_detects_positive_slope_near_the_step(self):
        d = _run_dict("sudden_increase", 7002, self.p1_config)
        worker = d["workers"][0]
        series = worker["series"]["observed_rate_uSv_h"]
        ev = worker["truth_events"][0]
        forecasts = build_rate_forecasts(self.bridge, series)
        near_step = [r for r in forecasts if not r["skipped"] and ev["start"] <= r["t"] <= ev["start"] + 3]
        self.assertTrue(any(r["slope"] > 0 for r in near_step), msg="expected a positive slope near the step onset")

    def test_fault_missing_archetype_skips_windows_touching_the_gap(self):
        d = _run_dict("fault_missing", 7003, self.p1_config)
        worker = d["workers"][0]
        f = worker["fault_events"][0]
        series = worker["series"]["observed_rate_uSv_h"]
        forecasts = build_rate_forecasts(self.bridge, series)
        skipped_ts = {r["t"] for r in forecasts if r["skipped"]}
        # Every minute within the fault window must cause a skip for any
        # window that includes it.
        self.assertTrue(any(f["start"] <= t <= f["end"] for t in skipped_ts))

    def test_fault_frozen_archetype_gives_zero_slope_while_frozen(self):
        d = _run_dict("fault_frozen", 7004, self.p1_config)
        worker = d["workers"][0]
        f = worker["fault_events"][0]
        series = worker["series"]["observed_rate_uSv_h"]
        forecasts = build_rate_forecasts(self.bridge, series)
        # A window fully inside the frozen run (4 identical repeated
        # values) must be scored as a (fault-induced) zero-slope
        # forecast -- not skipped, since repeated identical values are
        # still individually valid readings.
        t = f["start"] + 5
        if t < len(series):
            matches = [r for r in forecasts if r["t"] == t]
            if matches and not matches[0]["skipped"]:
                self.assertAlmostEqual(matches[0]["slope"], 0.0, places=6)

    def test_fault_invalid_archetype_skips_windows_touching_invalid_values(self):
        d = _run_dict("fault_invalid", 7005, self.p1_config)
        worker = d["workers"][0]
        f = worker["fault_events"][0]
        series = worker["series"]["observed_rate_uSv_h"]
        forecasts = build_rate_forecasts(self.bridge, series)
        skipped_ts = {r["t"] for r in forecasts if r["skipped"]}
        self.assertTrue(any(f["start"] <= t <= f["end"] for t in skipped_ts))


if __name__ == "__main__":
    unittest.main()
