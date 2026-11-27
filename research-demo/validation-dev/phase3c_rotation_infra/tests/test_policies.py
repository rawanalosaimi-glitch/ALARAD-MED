"""Tests for the 5 policies' trigger/selection logic in isolation
(task 2/3) -- threshold ownership, clause separation, and the shared-
trigger/shared-selection guarantee across policies."""

from __future__ import annotations

import unittest

from phase1_simulator.scenario import ROOMS
from phase2a_adapter.engine_bridge import EngineBridge
from phase2a_adapter.engine_contract import snapshot_engine_constants
from phase3c_rotation_infra.config import load_config
from phase3c_rotation_infra.policies import (
    ABLATION_D,
    CGDTR,
    FIXED_INTERVAL,
    NO_ROTATION,
    REFERENCE_RULE,
    TriggerContext,
    evaluate_fixed_interval_trigger,
    evaluate_trigger,
    rank_candidates,
)
from phase3c_rotation_infra.staffing import generate_roster

PROCEDURE_CLASSES = ["diagnostic_fluoroscopy", "interventional_cath_lab", "ct", "pet_ct"]


def _roster():
    return generate_roster(5, 120, 2, ROOMS, PROCEDURE_CLASSES)


class TestFixedIntervalTrigger(unittest.TestCase):
    def test_fires_only_on_multiples_of_interval(self):
        self.assertFalse(evaluate_fixed_interval_trigger(0, 60).fired)
        self.assertFalse(evaluate_fixed_interval_trigger(59, 60).fired)
        self.assertTrue(evaluate_fixed_interval_trigger(60, 60).fired)
        self.assertEqual(evaluate_fixed_interval_trigger(60, 60).clause, "interval")
        self.assertTrue(evaluate_fixed_interval_trigger(120, 60).fired)


class TestDoseThresholdTrigger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = EngineBridge().__enter__()
        cls.engine_config = snapshot_engine_constants(cls.bridge)
        cls.cfg = load_config()

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    def _ctx(self, worker, room="Cath Lab 1", t=10, remaining=20):
        return TriggerContext(room=room, worker=worker, t=t, remaining_minutes_in_slot=remaining,
                               procedure_class="diagnostic_fluoroscopy", proc_mult=1.0)

    def test_no_clause_fires_for_a_fresh_low_dose_worker(self):
        roster = _roster()
        w = next(iter(roster))
        w = roster[0]
        outcome = evaluate_trigger(CGDTR, self.bridge, self._ctx(w), self.cfg, self.engine_config)
        self.assertFalse(outcome.fired)

    def test_clause_a_fires_on_accrued_dose_alone(self):
        roster = _roster()
        w = roster[0]
        trig_cfg = self.cfg.block("cgdtr_trigger")
        w.cumulative_dose_mSv = trig_cfg["rotation_threshold_fraction"] * trig_cfg["reference_level_mSv_per_shift"]
        outcome = evaluate_trigger(CGDTR, self.bridge, self._ctx(w), self.cfg, self.engine_config)
        self.assertTrue(outcome.fired)
        self.assertEqual(outcome.clause, "a")

    def test_clause_b_fires_on_engine_threshold_not_accrued_total(self):
        """Proves clause (b) uses EngineProjectedTaskDose (a fresh,
        memoryless projection) -- NOT WorkerAccumulatedShiftDose. A
        worker with near-zero accrued dose but a very high current rate
        must still trigger clause (b)."""
        roster = _roster()
        w = roster[0]
        w.cumulative_dose_mSv = 0.0001  # far below clause (a)'s threshold
        w.sensor_state_label = "HEALTHY"
        doseElevated = self.engine_config["CONFIG"]["doseElevated"]
        # rate such that rate * 0.5h/1000 >= doseElevated
        w.last_valid_rate_uSv_h = (doseElevated * 1000.0 / 0.5) * 1.5
        outcome = evaluate_trigger(CGDTR, self.bridge, self._ctx(w), self.cfg, self.engine_config)
        self.assertTrue(outcome.fired)
        self.assertEqual(outcome.clause, "b")

    def test_clause_b_does_not_fire_when_sensor_not_trusted(self):
        roster = _roster()
        w = roster[0]
        w.sensor_state_label = "STALE"
        doseElevated = self.engine_config["CONFIG"]["doseElevated"]
        w.last_valid_rate_uSv_h = (doseElevated * 1000.0 / 0.5) * 1.5
        outcome = evaluate_trigger(CGDTR, self.bridge, self._ctx(w), self.cfg, self.engine_config)
        self.assertFalse(outcome.fired)

    def test_clause_c_fires_on_duty_limit_not_engine_threshold(self):
        """Proves clause (c) compares ProjectedShiftTotalDose against
        the worker's OWN max_dose_per_shift_mSv -- a value far below
        CONFIG.doseElevated can still trigger clause (c) if it is close
        to this worker's own small duty limit."""
        roster = _roster()
        w = roster[0]
        w.max_dose_per_shift_mSv = 0.01  # a tiny duty limit
        w.cumulative_dose_mSv = 0.005
        w.sensor_state_label = "HEALTHY"
        w.last_valid_rate_uSv_h = 60.0  # small rate, would NOT trip clause (b)
        doseElevated = self.engine_config["CONFIG"]["doseElevated"]
        engine_dose = 60.0 * 0.5 / 1000.0
        self.assertLess(engine_dose, doseElevated, "sanity check: clause (b) must not fire here")
        outcome = evaluate_trigger(CGDTR, self.bridge, self._ctx(w, remaining=60), self.cfg, self.engine_config)
        self.assertTrue(outcome.fired)
        self.assertEqual(outcome.clause, "c")

    def test_reference_rule_shares_identical_trigger_with_cgdtr(self):
        roster = _roster()
        w = roster[0]
        trig_cfg = self.cfg.block("cgdtr_trigger")
        w.cumulative_dose_mSv = trig_cfg["rotation_threshold_fraction"] * trig_cfg["reference_level_mSv_per_shift"]
        cgdtr_outcome = evaluate_trigger(CGDTR, self.bridge, self._ctx(w), self.cfg, self.engine_config)
        ref_outcome = evaluate_trigger(REFERENCE_RULE, self.bridge, self._ctx(w), self.cfg, self.engine_config)
        self.assertEqual(cgdtr_outcome, ref_outcome)

    def test_ablation_d_shares_identical_trigger_with_fixed_interval(self):
        a = evaluate_trigger(FIXED_INTERVAL, self.bridge, self._ctx(_roster()[0], t=60), self.cfg, self.engine_config)
        b = evaluate_trigger(ABLATION_D, self.bridge, self._ctx(_roster()[0], t=60), self.cfg, self.engine_config)
        self.assertEqual(a, b)

    def test_no_rotation_never_fires(self):
        roster = _roster()
        w = roster[0]
        w.cumulative_dose_mSv = 999.0
        outcome = evaluate_trigger(NO_ROTATION, self.bridge, self._ctx(w), self.cfg, self.engine_config)
        self.assertFalse(outcome.fired)


class TestSelection(unittest.TestCase):
    def test_lowest_dose_ranking_ties_broken_by_worker_id(self):
        roster = _roster()
        ids = sorted(w.worker_id for w in roster)
        roster_by_id = {w.worker_id: w for w in roster}
        for wid in ids:
            roster_by_id[wid].cumulative_dose_mSv = 1.0  # all tied
        ranked = rank_candidates(CGDTR, roster_by_id, ids)
        self.assertEqual(ranked, sorted(ids))

    def test_lowest_dose_ranking_respects_actual_dose(self):
        roster = _roster()
        ids = sorted(w.worker_id for w in roster)
        roster_by_id = {w.worker_id: w for w in roster}
        for wid in ids:
            roster_by_id[wid].cumulative_dose_mSv = 9.0  # baseline, all high
        roster_by_id[ids[0]].cumulative_dose_mSv = 5.0
        roster_by_id[ids[1]].cumulative_dose_mSv = 1.0
        ranked = rank_candidates(CGDTR, roster_by_id, ids)
        self.assertEqual(ranked[0], ids[1])

    def test_first_in_order_ignores_dose(self):
        roster = _roster()
        ids = sorted(w.worker_id for w in roster)
        roster_by_id = {w.worker_id: w for w in roster}
        roster_by_id[ids[0]].cumulative_dose_mSv = 0.0
        roster_by_id[ids[-1]].cumulative_dose_mSv = 999.0
        ranked = rank_candidates(REFERENCE_RULE, roster_by_id, ids)
        self.assertEqual(ranked, sorted(ids))


if __name__ == "__main__":
    unittest.main()
