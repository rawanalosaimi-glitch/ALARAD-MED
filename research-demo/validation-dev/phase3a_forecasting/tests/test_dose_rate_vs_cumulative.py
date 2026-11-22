"""
Phase 3A task 7: confirms dose-RATE forecasting (what linearForecast
actually does) and cumulative-DOSE forecasting (an adapter-only derived
calculation, not present in the frozen engine) are visibly distinct
computations with distinct units, and that the derived cumulative-dose
forecast integrates correctly against hand-computed expectations.
"""

from __future__ import annotations

import unittest

from phase2a_adapter.engine_bridge import EngineBridge
from phase3a_forecasting.forecast_adapter import (
    build_rate_forecasts,
    forecast_cumulative_dose,
    true_cumulative_dose_over_horizon,
)


class TestDoseRateVsCumulativeDose(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = EngineBridge().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    def test_rate_forecast_and_cumulative_forecast_are_different_numbers_in_different_units(self):
        series = [100.0, 100.0, 100.0, 100.0]  # flat 100 uSv/h
        rate_forecasts = build_rate_forecasts(self.bridge, series)
        r = rate_forecasts[0]
        self.assertFalse(r["skipped"])
        # Rate forecast: flat series -> 100 uSv/h at every horizon.
        self.assertEqual(r["forecast_rate_uSv_h"], [100.0, 100.0, 100.0])

        with_dose = forecast_cumulative_dose(rate_forecasts)[0]
        # Hand-computed: 100 uSv/h for 1 minute = 100 * (1/60) / 1000 mSv
        # per minute, accumulated: minute1, minute1+2, minute1+2+3.
        per_minute = 100.0 * (1.0 / 60.0) / 1000.0
        expected_cumulative = [per_minute, per_minute * 2, per_minute * 3]
        for got, exp in zip(with_dose["forecast_cumulative_dose_mSv"], expected_cumulative):
            self.assertAlmostEqual(got, exp, places=12)

        # The two outputs must never be confused: different keys, and
        # the cumulative value is numerically tiny (mSv) compared with
        # the rate value (uSv/h) for any realistic reading.
        self.assertIn("forecast_rate_uSv_h", with_dose)
        self.assertIn("forecast_cumulative_dose_mSv", with_dose)
        self.assertLess(with_dose["forecast_cumulative_dose_mSv"][-1], with_dose["forecast_rate_uSv_h"][-1])

    def test_cumulative_dose_forecast_is_monotonically_non_decreasing_for_positive_rates(self):
        series = [20.0, 25.0, 30.0, 35.0]
        rate_forecasts = build_rate_forecasts(self.bridge, series)
        with_dose = forecast_cumulative_dose(rate_forecasts)[0]
        cum = with_dose["forecast_cumulative_dose_mSv"]
        self.assertTrue(cum[0] <= cum[1] <= cum[2])

    def test_true_cumulative_dose_over_horizon_matches_hand_calculation(self):
        # True (noiseless) series: minute-by-minute rates known exactly.
        series_true = [50.0, 50.0, 50.0, 50.0, 60.0, 70.0, 80.0]
        t = 3
        result = true_cumulative_dose_over_horizon(series_true, t)
        per_min_60 = 60.0 * (1.0 / 60.0) / 1000.0
        per_min_70 = 70.0 * (1.0 / 60.0) / 1000.0
        per_min_80 = 80.0 * (1.0 / 60.0) / 1000.0
        self.assertAlmostEqual(result[0], per_min_60, places=12)
        self.assertAlmostEqual(result[1], per_min_60 + per_min_70, places=12)
        self.assertAlmostEqual(result[2], per_min_60 + per_min_70 + per_min_80, places=12)

    def test_true_cumulative_dose_is_none_past_the_end_of_the_series(self):
        series_true = [10.0, 10.0, 10.0, 10.0]
        result = true_cumulative_dose_over_horizon(series_true, t=3)  # needs indices 4,5,6 -- none exist
        self.assertEqual(result, [None, None, None])

    def test_skipped_windows_have_no_cumulative_dose_forecast(self):
        series = [10.0, None, 10.0, 10.0]
        rate_forecasts = build_rate_forecasts(self.bridge, series)
        with_dose = forecast_cumulative_dose(rate_forecasts)
        for r in with_dose:
            if r["skipped"]:
                self.assertNotIn("forecast_cumulative_dose_mSv", r)


if __name__ == "__main__":
    unittest.main()
