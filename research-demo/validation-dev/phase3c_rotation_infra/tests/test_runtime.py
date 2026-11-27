"""Closes gap 2 (PHASE3C_A_REVIEW_AGAINST_REVISION_3.md section 2 item
2): live per-minute accumulated-dose updates, verified against a full
replay via the existing, already-tested dose_attribution module."""

from __future__ import annotations

import unittest

from phase1_simulator.scenario import ROOMS
from phase1_simulator.units import MINUTE_H, dose_increment_mSv
from phase2a_adapter.engine_bridge import EngineBridge
from phase3c_rotation_infra.runtime import (
    advance_worker_one_minute,
    advance_workers_one_minute_batch,
    initialize_worker_runtime,
)
from phase3c_rotation_infra.staffing import ASSIGNED, FREE, generate_roster

PROCEDURE_CLASSES = ["diagnostic_fluoroscopy", "interventional_cath_lab", "ct", "pet_ct"]


def _worker():
    return generate_roster(1, 120, 1, ROOMS, PROCEDURE_CLASSES)[0]


class TestRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = EngineBridge().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    def test_dose_accrues_only_when_assigned(self):
        w = _worker()
        self.assertEqual(w.state, FREE)
        advance_worker_one_minute(self.bridge, w, 300.0, 0)
        self.assertEqual(w.cumulative_dose_mSv, 0.0, "FREE worker must not accrue dose")

        w.state = ASSIGNED
        advance_worker_one_minute(self.bridge, w, 300.0, 1)
        self.assertAlmostEqual(w.cumulative_dose_mSv, dose_increment_mSv(300.0, MINUTE_H), places=9)

    def test_missing_reading_contributes_no_dose(self):
        w = _worker()
        w.state = ASSIGNED
        advance_worker_one_minute(self.bridge, w, None, 0)
        self.assertEqual(w.cumulative_dose_mSv, 0.0)
        self.assertIsNone(w.last_valid_rate_uSv_h)

    def test_last_valid_rate_tracks_only_healthy_minutes(self):
        w = _worker()
        w.state = ASSIGNED
        advance_worker_one_minute(self.bridge, w, 200.0, 0)
        self.assertEqual(w.last_valid_rate_uSv_h, 200.0)
        self.assertEqual(w.last_valid_rate_minute, 0)

        # Now go missing long enough to become STALE/DISCONNECTED --
        # last_valid_rate must NOT be overwritten by a stale/absent one.
        for t in range(1, 8):
            advance_worker_one_minute(self.bridge, w, None, t)
        self.assertIn(w.sensor_state_label, ("STALE", "DISCONNECTED"))
        self.assertEqual(w.last_valid_rate_uSv_h, 200.0)
        self.assertEqual(w.last_valid_rate_minute, 0)

    def test_live_update_matches_full_replay(self):
        w = _worker()
        w.state = ASSIGNED
        series = [100.0, 150.0, 200.0, None, 180.0, 220.0, 90.0]
        for t, reading in enumerate(series):
            advance_worker_one_minute(self.bridge, w, reading, t)

        expected_total = sum(
            dose_increment_mSv(r, MINUTE_H) for r in series if r is not None
        )
        self.assertAlmostEqual(w.cumulative_dose_mSv, expected_total, places=9)

    def test_lazy_initialization_without_explicit_call(self):
        w = _worker()
        self.assertIsNone(w.sensor_state_obj)
        advance_worker_one_minute(self.bridge, w, 50.0, 0)
        self.assertIsNotNone(w.sensor_state_obj)
        self.assertEqual(w.sensor_state_label, "HEALTHY")

    def test_explicit_initialization_matches_lazy(self):
        w1 = _worker()
        initialize_worker_runtime(self.bridge, w1)
        w2 = _worker()
        advance_worker_one_minute(self.bridge, w1, 50.0, 0)
        advance_worker_one_minute(self.bridge, w2, 50.0, 0)
        self.assertEqual(w1.sensor_state_label, w2.sensor_state_label)
        self.assertEqual(w1.cumulative_dose_mSv, w2.cumulative_dose_mSv)


    def test_batch_matches_sequential_single_calls(self):
        w1a, w1b = _worker(), _worker()
        w2a, w2b = _worker(), _worker()
        w1a.worker_id = w2a.worker_id = "A"
        w1b.worker_id = w2b.worker_id = "B"
        for w in (w1a, w1b, w2a, w2b):
            w.state = ASSIGNED

        series_a = [100.0, None, 150.0, 90.0]
        series_b = [300.0, 310.0, None, None]

        for t in range(4):
            advance_worker_one_minute(self.bridge, w1a, series_a[t], t)
            advance_worker_one_minute(self.bridge, w1b, series_b[t], t)

        for t in range(4):
            advance_workers_one_minute_batch(
                self.bridge, [(w2a, series_a[t]), (w2b, series_b[t])], t)

        self.assertEqual(w1a.cumulative_dose_mSv, w2a.cumulative_dose_mSv)
        self.assertEqual(w1b.cumulative_dose_mSv, w2b.cumulative_dose_mSv)
        self.assertEqual(w1a.sensor_state_label, w2a.sensor_state_label)
        self.assertEqual(w1b.sensor_state_label, w2b.sensor_state_label)
        self.assertEqual(w1a.last_valid_rate_uSv_h, w2a.last_valid_rate_uSv_h)


if __name__ == "__main__":
    unittest.main()
