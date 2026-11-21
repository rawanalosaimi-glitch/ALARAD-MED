"""
Task 4: confirms radiation-anomaly and sensor/data-quality evaluation are
genuinely independent -- separate functions, separate inputs, separate
TP/FP/FN, never pooled -- even on a worker that has both a radiation event
and a sensor fault at once.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from phase1_simulator import config as p1_config
from phase1_simulator import output as p1_output
from phase1_simulator import scenario as p1_scenario
from phase2a_adapter.detection_adapter import evaluate_radiation_detection
from phase2a_adapter.dq_adapter import evaluate_dq_detection
from phase2a_adapter.engine_bridge import EngineBridge
from phase2a_adapter.engine_contract import snapshot_engine_constants

P1_CONFIG_PATH = Path(p1_config.__file__).parent / "config" / "simulation_config.json"


def _run_dict(archetype: str, seed: int, p1_cfg):
    run = p1_scenario.generate_run(archetype, seed, p1_cfg)
    simulated = p1_scenario.simulate_run(run, p1_cfg)
    return p1_output.run_to_dict(simulated, p1_cfg)


class TestDualLayerIndependence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = EngineBridge().__enter__()
        cls.p1_config = p1_config.load_config(P1_CONFIG_PATH)
        snap = snapshot_engine_constants(cls.bridge)
        cls.engine_baselines = snap["baselineRates"]

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    def test_concurrent_event_and_fault_are_scored_on_separate_ground_truth(self):
        d = _run_dict("concurrent_alert_and_fault", 9201, self.p1_config)
        worker = d["workers"][0]
        self.assertEqual(len(worker["truth_events"]), 1)
        self.assertEqual(len(worker["fault_events"]), 1)

        rad = evaluate_radiation_detection(
            self.bridge, worker, self.p1_config, self.engine_baselines, K=1)
        dq = evaluate_dq_detection(self.bridge, worker, self.p1_config, self.engine_baselines)

        # Each layer's TP/FN denominator must equal its OWN ground-truth
        # count, never the sum of both.
        self.assertEqual(rad["TP"] + rad["FN"], len(worker["truth_events"]))
        self.assertEqual(dq["TP"] + dq["FN"], len(worker["fault_events"]))

    def test_radiation_evaluation_never_reads_fault_events(self):
        d = _run_dict("fault_during_event", 9202, self.p1_config)
        worker = d["workers"][0]
        worker_no_faults = dict(worker)
        worker_no_faults["fault_events"] = []  # radiation layer must not need this
        rad = evaluate_radiation_detection(
            self.bridge, worker, self.p1_config, self.engine_baselines, K=1)
        rad_without_fault_field = evaluate_radiation_detection(
            self.bridge, worker_no_faults, self.p1_config, self.engine_baselines, K=1)
        self.assertEqual(rad["TP"], rad_without_fault_field["TP"])
        self.assertEqual(rad["FP"], rad_without_fault_field["FP"])
        self.assertEqual(rad["FN"], rad_without_fault_field["FN"])

    def test_dq_evaluation_never_reads_truth_events(self):
        d = _run_dict("fault_during_event", 9203, self.p1_config)
        worker = d["workers"][0]
        worker_no_truth = dict(worker)
        worker_no_truth["truth_events"] = []  # DQ layer must not need this
        dq = evaluate_dq_detection(self.bridge, worker, self.p1_config, self.engine_baselines)
        dq_without_truth_field = evaluate_dq_detection(self.bridge, worker_no_truth, self.p1_config, self.engine_baselines)
        self.assertEqual(dq["TP"], dq_without_truth_field["TP"])
        self.assertEqual(dq["FP"], dq_without_truth_field["FP"])
        self.assertEqual(dq["FN"], dq_without_truth_field["FN"])

    def test_multi_worker_faults_are_isolated_per_worker(self):
        # Reuses the S12 cross-worker-independence precedent: a fault on
        # one worker must not appear in another worker's DQ evaluation.
        d = _run_dict("multi_worker_faults", 9204, self.p1_config)
        w0, w1, w2 = d["workers"]
        dq0 = evaluate_dq_detection(self.bridge, w0, self.p1_config, self.engine_baselines)
        dq1 = evaluate_dq_detection(self.bridge, w1, self.p1_config, self.engine_baselines)
        dq2 = evaluate_dq_detection(self.bridge, w2, self.p1_config, self.engine_baselines)
        self.assertEqual(dq0["TP"] + dq0["FN"], len(w0["fault_events"]))
        self.assertEqual(dq1["TP"] + dq1["FN"], len(w1["fault_events"]))
        self.assertEqual(dq2["TP"] + dq2["FN"], len(w2["fault_events"]))


if __name__ == "__main__":
    unittest.main()
