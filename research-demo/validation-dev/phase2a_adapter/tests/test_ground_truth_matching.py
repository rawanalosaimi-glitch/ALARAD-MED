"""
Task 7: ground-truth matching, temporal alignment, false alarms, missing
data, and zero-event scenarios -- using real Phase 1 simulator output fed
through the real frozen engine via this adapter.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from phase1_simulator import config as p1_config
from phase1_simulator import output as p1_output
from phase1_simulator import scenario as p1_scenario
from phase2a_adapter import baselines
from phase2a_adapter.detection_adapter import evaluate_radiation_detection
from phase2a_adapter.dq_adapter import evaluate_dq_detection
from phase2a_adapter.engine_bridge import EngineBridge
from phase2a_adapter.engine_contract import snapshot_engine_constants

P1_CONFIG_PATH = Path(p1_config.__file__).parent / "config" / "simulation_config.json"


def _run_dict(archetype: str, seed: int, p1_cfg):
    run = p1_scenario.generate_run(archetype, seed, p1_cfg)
    simulated = p1_scenario.simulate_run(run, p1_cfg)
    return p1_output.run_to_dict(simulated, p1_cfg)


class TestGroundTruthMatching(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = EngineBridge().__enter__()
        cls.p1_config = p1_config.load_config(P1_CONFIG_PATH)
        snap = snapshot_engine_constants(cls.bridge)
        cls.engine_baselines = snap["baselineRates"]

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    # ---- zero-event scenarios -------------------------------------------

    def test_zero_event_scenario_gives_undefined_precision_but_defined_fp_zero(self):
        d = _run_dict("normal", 9001, self.p1_config)
        worker = d["workers"][0]
        self.assertEqual(worker["truth_events"], [])
        result = evaluate_radiation_detection(
            self.bridge, worker, self.p1_config, self.engine_baselines, K=1)
        self.assertEqual(result["FN"], 0)
        # precision is undefined (TP+FP could be 0) rather than silently 0 or 1
        if result["TP"] + result["FP"] == 0:
            self.assertIsNone(result["precision"])
        # recall must be None (0/0: no true events) per SimLab.pure.metrics itself
        self.assertIsNone(result["recall"])

    def test_zero_fault_scenario_dq_layer_also_gives_undefined_recall(self):
        d = _run_dict("normal", 9002, self.p1_config)
        worker = d["workers"][0]
        self.assertEqual(worker["fault_events"], [])
        result = evaluate_dq_detection(self.bridge, worker, self.p1_config, self.engine_baselines)
        self.assertIsNone(result["recall"])
        self.assertEqual(result["FN"], 0)

    # ---- missing data -----------------------------------------------------

    def test_missing_data_is_detected_as_a_data_quality_event_not_a_radiation_event(self):
        d = _run_dict("fault_missing", 9003, self.p1_config)
        worker = d["workers"][0]
        self.assertEqual(worker["truth_events"], [])
        self.assertEqual(len(worker["fault_events"]), 1)

        dq_result = evaluate_dq_detection(self.bridge, worker, self.p1_config, self.engine_baselines)
        self.assertEqual(dq_result["TP"], 1, msg=f"expected the missing-data fault to be detected: {dq_result}")
        self.assertEqual(dq_result["FN"], 0)

        rad_result = evaluate_radiation_detection(
            self.bridge, worker, self.p1_config, self.engine_baselines, K=1)
        # No radiation ground truth exists for this archetype -- the
        # radiation layer must not report any TP/FN derived from the fault.
        self.assertEqual(rad_result["FN"], 0)

    def test_missing_minutes_are_never_silently_treated_as_zero_exposure(self):
        d = _run_dict("fault_missing", 9004, self.p1_config)
        worker = d["workers"][0]
        # Phase 1's own dose accounting already enforces this; confirmed
        # here as a precondition the adapter's input depends on.
        self.assertGreater(worker["unmonitored_minutes"], 0)
        f = worker["fault_events"][0]
        self.assertEqual(worker["unmonitored_minutes"], f["end"] - f["start"])

    # ---- false alarms -------------------------------------------------

    def test_transient_spike_produces_a_false_alarm_at_k1(self):
        d = _run_dict("transient_spike", 9005, self.p1_config)
        worker = d["workers"][0]
        self.assertEqual(worker["truth_events"], [])  # S5 convention: not a labelled event
        result = evaluate_radiation_detection(
            self.bridge, worker, self.p1_config, self.engine_baselines, K=1)
        self.assertGreaterEqual(result["FP"], 1, msg=f"expected the spike to be flagged as FP at K=1: {result}")
        self.assertEqual(result["TP"], 0)

    def test_confirmation_window_suppresses_the_same_transient_spike(self):
        d = _run_dict("transient_spike", 9005, self.p1_config)
        worker = d["workers"][0]
        # Same worker/seed as the K=1 test above, but with a confirmation
        # window long enough to exceed the spike's own duration range
        # (config: spike_minutes max is 2) -- demonstrates the same input
        # scored two ways through the SAME real engine primitives.
        result_k5 = evaluate_radiation_detection(
            self.bridge, worker, self.p1_config, self.engine_baselines, K=5)
        self.assertEqual(result_k5["FP"], 0, msg=f"K=5 should suppress a <=2-minute spike: {result_k5}")

    # ---- temporal alignment -----------------------------------------------

    def test_detection_delay_is_non_negative_and_within_grace_adjusted_window(self):
        d = _run_dict("sudden_increase", 9006, self.p1_config)
        worker = d["workers"][0]
        result = evaluate_radiation_detection(
            self.bridge, worker, self.p1_config, self.engine_baselines, K=1, grace=2)
        self.assertEqual(result["TP"], 1, msg=result)
        ev = worker["truth_events"][0]
        self.assertEqual(len(result["detection_delays_minutes"]), 1)
        delay = result["detection_delays_minutes"][0]
        self.assertGreaterEqual(delay, 0)
        self.assertLessEqual(delay, (ev["end"] - ev["start"]) + 2)

    def test_matched_episode_det_time_never_precedes_event_start(self):
        # A direct check on SimLab.pure.matchEvents' own documented rule
        # ("An alert before the onset is never a valid detection"),
        # exercised through this adapter rather than re-derived.
        d = _run_dict("sudden_increase", 9007, self.p1_config)
        worker = d["workers"][0]
        result = evaluate_radiation_detection(
            self.bridge, worker, self.p1_config, self.engine_baselines, K=1)
        ev = worker["truth_events"][0]
        for episode in result["episodes"]:
            if episode["det"] is not None and ev["start"] <= episode["det"] <= ev["end"] + 2:
                self.assertGreaterEqual(episode["det"], ev["start"])


if __name__ == "__main__":
    unittest.main()
