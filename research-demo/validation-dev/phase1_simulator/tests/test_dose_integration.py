"""
Unit tests for dose integration (Phase 1 deliverable C, item 1).
"""

from __future__ import annotations

import unittest

from phase1_simulator import dose, units


class TestDoseIntegration(unittest.TestCase):
    def test_flat_rate_matches_hand_calculation(self):
        # 10 uSv/h held for 60 one-minute steps -> 10 * (60/60)/1000 mSv.
        series = [10.0] * 60
        total = dose.accumulate_true_dose(series)
        self.assertAlmostEqual(total, 10.0 * 1.0 / 1000.0, places=9)

    def test_dose_increment_formula_matches_methodology(self):
        # Dose (mSv) = Dose Rate (uSv/h) x Duration (h) / 1000
        self.assertAlmostEqual(
            units.dose_increment_mSv(60.0, 0.5), 60.0 * 0.5 / 1000.0)

    def test_running_sum_is_additive(self):
        series = [5.0, 10.0, 15.0]
        total = dose.accumulate_true_dose(series)
        expected = sum(units.dose_increment_mSv(v, units.MINUTE_H) for v in series)
        self.assertAlmostEqual(total, expected, places=12)

    def test_invalid_readings_contribute_no_observed_dose(self):
        series = [10.0, float("nan"), -5.0, None, 10.0]
        acc = dose.accumulate_observed_dose(series)
        self.assertEqual(acc.unmonitored_minutes, 3)
        self.assertEqual(acc.trusted_minutes, 2)
        expected = units.dose_increment_mSv(10.0, units.MINUTE_H) * 2
        self.assertAlmostEqual(acc.observed_dose_mSv, expected, places=12)

    def test_minute_classification_counts_sum_to_total(self):
        series = [10.0, None, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, float("nan"), 20.0]
        acc = dose.accumulate_observed_dose(series)
        total = acc.trusted_minutes + acc.uncertain_minutes + acc.unmonitored_minutes
        self.assertEqual(total, len(series))

    def test_frozen_repeat_becomes_uncertain_after_threshold_but_is_still_accumulated(self):
        series = [10.0] * 10  # identical from the first minute
        acc = dose.accumulate_observed_dose(series)
        self.assertEqual(acc.trusted_minutes, dose.FROZEN_REPEAT_THRESHOLD - 1)
        self.assertEqual(acc.uncertain_minutes, 10 - (dose.FROZEN_REPEAT_THRESHOLD - 1))
        self.assertEqual(acc.unmonitored_minutes, 0)
        # Uncertain minutes are flagged, not dropped: total observed dose
        # still equals what accumulate_true_dose would give for the same
        # numeric series.
        self.assertAlmostEqual(acc.observed_dose_mSv, dose.accumulate_true_dose(series), places=12)

    def test_out_of_bounds_rate_is_rejected(self):
        series = [10.0, 2_000_000.0, -1.0, 10.0]  # second and third are out of bounds
        acc = dose.accumulate_observed_dose(series)
        self.assertEqual(acc.unmonitored_minutes, 2)
        self.assertEqual(acc.trusted_minutes, 2)


if __name__ == "__main__":
    unittest.main()
