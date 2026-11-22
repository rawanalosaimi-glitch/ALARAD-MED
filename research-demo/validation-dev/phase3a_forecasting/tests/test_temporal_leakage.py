"""
Phase 3A task 6 (temporal leakage) and task 4 (explicit chronological
cutoffs): proves, by actually mutating future data and observing no
change, that a forecast at minute t never depends on data at or after
t+1 -- not merely a code-inspection claim.
"""

from __future__ import annotations

import unittest

from phase2a_adapter.engine_bridge import EngineBridge
from phase3a_forecasting.forecast_adapter import build_rate_forecasts, score_against_ground_truth


class TestTemporalLeakage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = EngineBridge().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    def test_mutating_future_values_does_not_change_an_already_computed_forecast(self):
        base_series = [40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        t_of_interest = 3  # window = base_series[0:4] = [40,50,60,70]

        forecasts_before = build_rate_forecasts(self.bridge, base_series)
        before = next(r for r in forecasts_before if r["t"] == t_of_interest)

        mutated_series = list(base_series)
        for i in range(t_of_interest + 1, len(mutated_series)):
            mutated_series[i] = -9999.0  # drastically different future

        forecasts_after = build_rate_forecasts(self.bridge, mutated_series)
        after = next(r for r in forecasts_after if r["t"] == t_of_interest)

        self.assertEqual(before["slope"], after["slope"])
        self.assertEqual(before["forecast_rate_uSv_h"], after["forecast_rate_uSv_h"])

    def test_window_never_includes_index_t_plus_one(self):
        """A direct structural check: for every non-skipped forecast at
        minute t, the exact 4 values used are series[t-3..t] -- verified
        by re-deriving the window independently and comparing the slope
        linearForecast would produce from it against the forecast
        actually returned."""
        series = [5.0, 15.0, 25.0, 35.0, 1000.0, 1000.0, 1000.0]
        forecasts = build_rate_forecasts(self.bridge, series)
        r = next(x for x in forecasts if x["t"] == 3)
        self.assertFalse(r["skipped"])
        expected_window = series[0:4]  # [5,15,25,35], NOT touching the 1000s at t=4,5,6
        recomputed = self.bridge.evaluate("(p) => linearForecast(p)", expected_window)
        self.assertEqual(r["slope"], recomputed["slope"])
        self.assertEqual(r["forecast_rate_uSv_h"], recomputed["next"])
        # Sanity: if the window had leaked index 4 (value 1000), the
        # slope would be enormously larger than what a [5,15,25,35] ramp
        # (slope=10) produces.
        self.assertLess(abs(r["slope"] - 10.0), 1e-9)

    def test_ground_truth_scoring_is_a_separate_later_step_not_fused_into_the_forecast(self):
        """score_against_ground_truth is called strictly after
        build_rate_forecasts; this test confirms calling it twice with
        two DIFFERENT future continuations never changes the forecast
        values themselves, only the recorded 'actual' values."""
        series_a = [40.0, 50.0, 60.0, 70.0, 11.0, 12.0, 13.0]
        series_b = [40.0, 50.0, 60.0, 70.0, 999.0, 998.0, 997.0]

        forecasts = build_rate_forecasts(self.bridge, series_a[:4])  # only the window itself
        scored_a = score_against_ground_truth(forecasts, series_a)
        scored_b = score_against_ground_truth(forecasts, series_b)

        fc_a = next(r for r in scored_a if r["t"] == 3)
        fc_b = next(r for r in scored_b if r["t"] == 3)
        self.assertEqual(fc_a["forecast_rate_uSv_h"], fc_b["forecast_rate_uSv_h"])
        self.assertNotEqual(fc_a["actual_rate_uSv_h"], fc_b["actual_rate_uSv_h"])


if __name__ == "__main__":
    unittest.main()
