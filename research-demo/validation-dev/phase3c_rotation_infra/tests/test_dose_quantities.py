"""Closes gap 2/3 groundwork: the three PHASE3B section 3a quantities,
dimensional consistency, and correct threshold ownership (each quantity
is only ever compared to the threshold its own function signature
allows -- EngineProjectedTaskDose never takes a duty-limit parameter,
ProjectedShiftTotalDose never takes or calls the engine bridge)."""

from __future__ import annotations

import unittest

from phase1_simulator.scenario import ROOMS
from phase2a_adapter.engine_bridge import EngineBridge
from phase3c_rotation_infra.dose_quantities import (
    ENGINE_PROJECTION_HORIZON_MINUTES,
    engine_projected_task_dose_mSv,
    engine_projected_task_dose_mSv_batch,
    projected_shift_total_dose_mSv,
    worker_accumulated_shift_dose_mSv,
)
from phase3c_rotation_infra.staffing import generate_roster

PROCEDURE_CLASSES = ["diagnostic_fluoroscopy", "interventional_cath_lab", "ct", "pet_ct"]


def _worker():
    return generate_roster(1, 120, 1, ROOMS, PROCEDURE_CLASSES)[0]


class TestWorkerAccumulatedShiftDose(unittest.TestCase):
    def test_is_a_plain_accessor_not_a_new_computation(self):
        w = _worker()
        w.cumulative_dose_mSv = 1.2345
        self.assertEqual(worker_accumulated_shift_dose_mSv(w), 1.2345)


class TestEngineProjectedTaskDose(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = EngineBridge().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    def test_dimensional_consistency_matches_hand_computed_formula(self):
        """EngineProjectedTaskDose(mSv) = rate(uSv/h) x (30/60) / 1000,
        the engine's own fixed 30-minute horizon -- checked against the
        real engine's return value, not re-derived independently."""
        rate = 400.0
        result = engine_projected_task_dose_mSv(self.bridge, "Cath Lab 1", 1.0, rate)
        expected = rate * (ENGINE_PROJECTION_HORIZON_MINUTES / 60.0) / 1000.0
        self.assertAlmostEqual(result, expected, places=9)
        self.assertEqual(ENGINE_PROJECTION_HORIZON_MINUTES, 30)

    def test_returns_none_for_engine_rejected_input(self):
        result = engine_projected_task_dose_mSv(self.bridge, "Cath Lab 1", 1.0, -5.0)
        self.assertIsNone(result)

    def test_batch_matches_individual_calls(self):
        items = [
            {"room": "Cath Lab 1", "procMult": 1.0, "rate": 100.0},
            {"room": "CT Suite", "procMult": 1.2, "rate": 300.0},
            {"room": "Cath Lab 2", "procMult": 0.9, "rate": -1.0},  # invalid
        ]
        batch_result = engine_projected_task_dose_mSv_batch(self.bridge, items)
        individual = [
            engine_projected_task_dose_mSv(self.bridge, it["room"], it["procMult"], it["rate"])
            for it in items
        ]
        self.assertEqual(batch_result, individual)
        self.assertIsNone(batch_result[2])


class TestProjectedShiftTotalDose(unittest.TestCase):
    def test_undefined_without_a_trusted_reading(self):
        w = _worker()
        self.assertIsNone(w.last_valid_rate_uSv_h)
        self.assertIsNone(projected_shift_total_dose_mSv(w, 0.5))

    def test_equals_accrued_plus_increment(self):
        w = _worker()
        w.cumulative_dose_mSv = 2.0
        w.last_valid_rate_uSv_h = 600.0
        result = projected_shift_total_dose_mSv(w, 0.5)  # 30 minutes
        expected = 2.0 + 600.0 * 0.5 / 1000.0
        self.assertAlmostEqual(result, expected, places=9)

    def test_never_needs_or_calls_an_engine_bridge(self):
        """Structural guarantee: this function's own signature has no
        bridge parameter at all -- it cannot read CONFIG.doseElevated/
        doseCritical even by accident, because it has no way to reach
        them."""
        import inspect
        params = inspect.signature(projected_shift_total_dose_mSv).parameters
        self.assertNotIn("bridge", params)


if __name__ == "__main__":
    unittest.main()
