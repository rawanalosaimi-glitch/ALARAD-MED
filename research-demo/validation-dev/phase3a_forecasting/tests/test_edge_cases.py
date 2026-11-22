"""
Phase 3A task 6: zero-dose edge cases, and other degenerate inputs that
must be handled explicitly rather than crashing or silently producing a
misleading number.
"""

from __future__ import annotations

import unittest

from phase2a_adapter.engine_bridge import EngineBridge
from phase3a_forecasting.baselines import build_persistence_forecasts
from phase3a_forecasting.forecast_adapter import (
    build_rate_forecasts,
    forecast_cumulative_dose,
    score_against_ground_truth,
)
from phase3a_forecasting.metrics import mae_rmse_by_horizon, skill_vs_persistence


class TestEdgeCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = EngineBridge().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    def test_all_zero_dose_rate_series_forecasts_zero_without_crashing(self):
        series = [0.0, 0.0, 0.0, 0.0, 0.0]
        forecasts = build_rate_forecasts(self.bridge, series)
        r = forecasts[0]
        self.assertFalse(r["skipped"])
        self.assertEqual(r["forecast_rate_uSv_h"], [0.0, 0.0, 0.0])
        self.assertEqual(r["slope"], 0)

    def test_zero_dose_rate_gives_zero_cumulative_dose_forecast(self):
        series = [0.0, 0.0, 0.0, 0.0]
        rate_forecasts = build_rate_forecasts(self.bridge, series)
        with_dose = forecast_cumulative_dose(rate_forecasts)[0]
        self.assertEqual(with_dose["forecast_cumulative_dose_mSv"], [0.0, 0.0, 0.0])

    def test_zero_series_gives_undefined_mae_rmse_not_a_crash_when_no_scored_pairs_exist(self):
        """A 4-point zero series has exactly one window (t=3) whose
        future (t+1,t+2,t+3) does not exist in the series at all --
        there is no ground truth to score against, so MAE/RMSE at every
        horizon must be reported as undefined (n=0), not as 0 (which
        would misleadingly imply perfect accuracy was measured)."""
        series = [0.0, 0.0, 0.0, 0.0]
        scored = score_against_ground_truth(build_rate_forecasts(self.bridge, series), series)
        stats = mae_rmse_by_horizon(scored)
        for h, s in stats.items():
            self.assertEqual(s["n"], 0, msg=f"horizon {h}")
            self.assertIsNone(s["mae"], msg=f"horizon {h}")
            self.assertIsNone(s["rmse"], msg=f"horizon {h}")

    def test_zero_dose_skill_score_is_undefined_not_crashing(self):
        series = [0.0] * 8
        candidate = score_against_ground_truth(build_rate_forecasts(self.bridge, series), series)
        persistence = score_against_ground_truth(build_persistence_forecasts(self.bridge, series), series)
        skill = skill_vs_persistence(candidate, persistence)
        for h, s in skill.items():
            self.assertIsNone(s, msg=f"horizon {h}")

    def test_empty_series_produces_no_forecasts_without_crashing(self):
        forecasts = build_rate_forecasts(self.bridge, [])
        self.assertEqual(forecasts, [])

    def test_series_shorter_than_trailing_points_produces_no_forecasts(self):
        forecasts = build_rate_forecasts(self.bridge, [10.0, 20.0, 30.0])  # only 3 < TRAILING_POINTS=4
        self.assertEqual(forecasts, [])


if __name__ == "__main__":
    unittest.main()
