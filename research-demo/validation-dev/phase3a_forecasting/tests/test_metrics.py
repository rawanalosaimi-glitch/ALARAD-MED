"""Unit tests for phase3a_forecasting/metrics.py -- pure functions, no
EngineBridge needed. Added after the statistical campaign surfaced a
real defect: skill_vs_persistence let NaN actual values (the project's
own established encoding for an invalid/non-physical reading, decoded
by phase2a_adapter.detection_adapter.decode_observed_value) leak into
the skill score as a literal NaN instead of being excluded like
mae_rmse_by_horizon already excludes them -- violating the "undefined
is reported, never silently NaN/0" discipline. These tests pin the fix.
"""

from __future__ import annotations

import math
import unittest

from phase3a_forecasting.metrics import mae_rmse_by_horizon, skill_vs_persistence


def _row(t, forecast, actual, skipped=False, series_id=None):
    return {"t": t, "skipped": skipped, "forecast_rate_uSv_h": forecast, "actual_rate_uSv_h": actual,
            "series_id": series_id}


class TestMaeRmseByHorizon(unittest.TestCase):
    def test_basic_mae_rmse(self):
        scored = [_row(0, [10.0, 10.0, 10.0], [12.0, 8.0, 10.0])]
        out = mae_rmse_by_horizon(scored)
        self.assertAlmostEqual(out[1]["mae"], 2.0)
        self.assertAlmostEqual(out[2]["mae"], 2.0)
        self.assertAlmostEqual(out[3]["mae"], 0.0)

    def test_skipped_rows_excluded(self):
        scored = [_row(0, [10.0, 10.0, 10.0], [100.0, 100.0, 100.0], skipped=True)]
        out = mae_rmse_by_horizon(scored)
        self.assertEqual(out[1]["n"], 0)
        self.assertIsNone(out[1]["mae"])

    def test_none_actual_row_excluded(self):
        scored = [_row(0, [10.0, 10.0, 10.0], None)]
        out = mae_rmse_by_horizon(scored)
        self.assertEqual(out[1]["n"], 0)

    def test_nan_actual_value_excluded_not_propagated(self):
        scored = [_row(0, [10.0, 10.0, 10.0], [float("nan"), 10.0, 10.0])]
        out = mae_rmse_by_horizon(scored)
        self.assertEqual(out[1]["n"], 0)
        self.assertIsNone(out[1]["mae"])
        self.assertEqual(out[2]["n"], 1)

    def test_empty_input_returns_undefined_not_crash(self):
        out = mae_rmse_by_horizon([])
        for h in (1, 2, 3):
            self.assertEqual(out[h]["n"], 0)
            self.assertIsNone(out[h]["mae"])
            self.assertIsNone(out[h]["rmse"])


class TestSkillVsPersistence(unittest.TestCase):
    def test_candidate_better_than_persistence_is_positive(self):
        cand = [_row(0, [10.0, 10.0, 10.0], [11.0, 11.0, 11.0])]
        pers = [_row(0, [5.0, 5.0, 5.0], [11.0, 11.0, 11.0])]
        out = skill_vs_persistence(cand, pers)
        self.assertGreater(out[1], 0)

    def test_identical_to_persistence_is_zero(self):
        cand = [_row(0, [10.0, 10.0, 10.0], [11.0, 11.0, 11.0])]
        pers = [_row(0, [10.0, 10.0, 10.0], [11.0, 11.0, 11.0])]
        out = skill_vs_persistence(cand, pers)
        self.assertAlmostEqual(out[1], 0.0)

    def test_zero_persistence_error_is_undefined_not_crash(self):
        cand = [_row(0, [10.0, 10.0, 10.0], [11.0, 11.0, 11.0])]
        pers = [_row(0, [11.0, 11.0, 11.0], [11.0, 11.0, 11.0])]
        out = skill_vs_persistence(cand, pers)
        self.assertIsNone(out[1])

    def test_no_shared_timestamps_is_undefined(self):
        cand = [_row(0, [10.0, 10.0, 10.0], [11.0, 11.0, 11.0])]
        pers = [_row(1, [10.0, 10.0, 10.0], [11.0, 11.0, 11.0])]
        out = skill_vs_persistence(cand, pers)
        self.assertIsNone(out[1])

    def test_nan_actual_excluded_not_propagated_as_nan(self):
        """Regression test for the defect this file documents: a NaN
        actual value (the project's own invalid-reading encoding) must
        never make the skill score itself NaN."""
        cand = [_row(0, [10.0, 10.0, 10.0], [float("nan"), 11.0, 11.0]),
                _row(1, [10.0, 10.0, 10.0], [12.0, 11.0, 11.0])]
        pers = [_row(0, [9.0, 9.0, 9.0], [float("nan"), 11.0, 11.0]),
                _row(1, [9.0, 9.0, 9.0], [12.0, 11.0, 11.0])]
        out = skill_vs_persistence(cand, pers)
        self.assertIsNotNone(out[1])
        self.assertFalse(isinstance(out[1], float) and math.isnan(out[1]))

    def test_nan_in_one_side_only_still_excludes_the_shared_timestamp(self):
        cand = [_row(0, [10.0, 10.0, 10.0], [float("nan"), 11.0, 11.0])]
        pers = [_row(0, [9.0, 9.0, 9.0], [10.5, 11.0, 11.0])]
        out = skill_vs_persistence(cand, pers)
        self.assertIsNone(out[1])

    def test_skipped_rows_excluded_from_pairing(self):
        cand = [_row(0, [10.0, 10.0, 10.0], [11.0, 11.0, 11.0], skipped=True)]
        pers = [_row(0, [9.0, 9.0, 9.0], [11.0, 11.0, 11.0])]
        out = skill_vs_persistence(cand, pers)
        self.assertIsNone(out[1])

    def test_pooling_two_series_with_colliding_t_does_not_drop_data(self):
        """Regression test for the defect this file documents: pooling
        rows from two different series that both use the same bare `t`
        domain (e.g. two different workers/runs, each starting at t=0)
        must use BOTH series' pairs, not silently keep only the last
        one written into the dict."""
        series_a_cand = [_row(0, [10.0] * 3, [20.0, 20.0, 20.0], series_id="A")]
        series_a_pers = [_row(0, [0.0] * 3, [20.0, 20.0, 20.0], series_id="A")]
        series_b_cand = [_row(0, [5.0] * 3, [5.0, 5.0, 5.0], series_id="B")]
        series_b_pers = [_row(0, [0.0] * 3, [5.0, 5.0, 5.0], series_id="B")]

        pooled_cand = series_a_cand + series_b_cand
        pooled_pers = series_a_pers + series_b_pers
        out = skill_vs_persistence(pooled_cand, pooled_pers)

        # Series A: cand off by 10 (sq err 100), pers off by 20 (sq err 400).
        # Series B: cand perfect (sq err 0), pers off by 5 (sq err 25).
        # Pooled MSE(cand) = (100 + 0) / 2 = 50, MSE(pers) = (400 + 25) / 2
        # = 212.5 -> skill = 1 - 50/212.5 = 13/17.
        # If the collision bug were present, only series B's pair would
        # survive (same bare t=0), giving skill = 1 - 0/25 = 1.0 instead.
        self.assertAlmostEqual(out[1], 13 / 17)

    def test_pooling_two_series_distinguishes_different_skill_per_series(self):
        """A pooling-collision bug would make this collapse to whichever
        series was listed last; with the fix both contribute."""
        series_a_cand = [_row(0, [10.0] * 3, [10.0, 10.0, 10.0], series_id="A")]  # cand perfect
        series_a_pers = [_row(0, [0.0] * 3, [10.0, 10.0, 10.0], series_id="A")]   # pers sq err 100
        series_b_cand = [_row(0, [0.0] * 3, [10.0, 10.0, 10.0], series_id="B")]   # cand sq err 100
        series_b_pers = [_row(0, [10.0] * 3, [10.0, 10.0, 10.0], series_id="B")]  # pers perfect

        pooled_cand = series_a_cand + series_b_cand
        pooled_pers = series_a_pers + series_b_pers
        out = skill_vs_persistence(pooled_cand, pooled_pers)
        # MSE(cand) = (0 + 100) / 2 = 50; MSE(pers) = (100 + 0) / 2 = 50 -> skill = 0.
        self.assertAlmostEqual(out[1], 0.0)
        # Without series_id, both series share bare t=0 and the dict
        # collision would keep only series B's rows for both methods,
        # giving MSE(cand)=100, MSE(pers)=0 -> skill undefined (None).
        cand_no_id = [dict(r, series_id=None) for r in pooled_cand]
        pers_no_id = [dict(r, series_id=None) for r in pooled_pers]
        collided = skill_vs_persistence(cand_no_id, pers_no_id)
        self.assertNotEqual(collided[1], out[1])


if __name__ == "__main__":
    unittest.main()
