"""
Sanity tests for the two independently-implemented forecasting
baselines, plus the skill-score comparison against the real
linearForecast-based candidate.
"""

from __future__ import annotations

import unittest

from phase2a_adapter.engine_bridge import EngineBridge
from phase3a_forecasting.baselines import (
    build_exponential_smoothing_forecasts,
    build_persistence_forecasts,
)
from phase3a_forecasting.config import load_config
from phase3a_forecasting.forecast_adapter import build_rate_forecasts, score_against_ground_truth
from phase3a_forecasting.metrics import skill_vs_persistence, summarize


class TestBaselines(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = EngineBridge().__enter__()
        cls.config = load_config()

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    def test_persistence_repeats_last_value_at_every_horizon(self):
        series = [10.0, 20.0, 30.0, 40.0, 50.0]
        forecasts = build_persistence_forecasts(self.bridge, series)
        r = next(x for x in forecasts if x["t"] == 3)
        self.assertEqual(r["forecast_rate_uSv_h"], [40.0, 40.0, 40.0])

    def test_exponential_smoothing_is_flat_and_between_min_and_max_of_window(self):
        series = [10.0, 20.0, 30.0, 40.0]
        alpha = self.config.block("baseline_exponential_smoothing")["alpha"]
        forecasts = build_exponential_smoothing_forecasts(self.bridge, series, alpha)
        r = forecasts[0]
        self.assertFalse(r["skipped"])
        vals = r["forecast_rate_uSv_h"]
        self.assertEqual(vals[0], vals[1])
        self.assertEqual(vals[1], vals[2])
        self.assertGreaterEqual(vals[0], min(series))
        self.assertLessEqual(vals[0], max(series))

    def test_exponential_smoothing_alpha_is_provisional(self):
        block = self.config.block("baseline_exponential_smoothing")
        self.assertEqual(block["status"], "PROVISIONAL")

    def test_candidate_beats_persistence_on_a_clean_linear_ramp(self):
        """On a perfectly linear ramp with no noise, the real
        linearForecast should fit it exactly (zero error), while
        persistence (flat) necessarily lags behind a moving target --
        candidate's skill score should be strongly positive."""
        series = [float(10 * i) for i in range(10)]  # 0,10,20,...,90
        candidate = score_against_ground_truth(build_rate_forecasts(self.bridge, series), series)
        persistence = score_against_ground_truth(build_persistence_forecasts(self.bridge, series), series)
        skill = skill_vs_persistence(candidate, persistence)
        for h, s in skill.items():
            self.assertIsNotNone(s, msg=f"horizon {h}")
            self.assertGreater(s, 0.9, msg=f"horizon {h}: expected near-perfect skill on a clean ramp")

    def test_skill_score_is_undefined_not_crashing_when_persistence_is_perfect(self):
        """On a perfectly flat series, persistence has zero error at
        every horizon -- skill score must be reported as undefined
        (None), never as a divide-by-zero crash or a fabricated value."""
        series = [60.0] * 10
        candidate = score_against_ground_truth(build_rate_forecasts(self.bridge, series), series)
        persistence = score_against_ground_truth(build_persistence_forecasts(self.bridge, series), series)
        skill = skill_vs_persistence(candidate, persistence)
        for h, s in skill.items():
            self.assertIsNone(s, msg=f"horizon {h}: expected undefined skill, got {s}")

    def test_summarize_runs_end_to_end_without_persistence(self):
        series = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
        candidate = score_against_ground_truth(build_rate_forecasts(self.bridge, series), series)
        summary = summarize(candidate)
        self.assertIn("by_horizon", summary)
        self.assertNotIn("skill_vs_persistence", summary)


if __name__ == "__main__":
    unittest.main()
