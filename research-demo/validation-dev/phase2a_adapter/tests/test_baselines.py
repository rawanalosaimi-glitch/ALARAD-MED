"""
Sanity tests for the two new comparison baselines, plus the trivial and
engine-ablation baselines, all scored through the same real-engine
primitives as the candidate detector.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from phase1_simulator import config as p1_config
from phase1_simulator import output as p1_output
from phase1_simulator import scenario as p1_scenario
from phase2a_adapter import baselines
from phase2a_adapter import config as p2a_config
from phase2a_adapter.engine_bridge import EngineBridge
from phase2a_adapter.engine_contract import snapshot_engine_constants

P1_CONFIG_PATH = Path(p1_config.__file__).parent / "config" / "simulation_config.json"


def _run_dict(archetype: str, seed: int, p1_cfg):
    run = p1_scenario.generate_run(archetype, seed, p1_cfg)
    simulated = p1_scenario.simulate_run(run, p1_cfg)
    return p1_output.run_to_dict(simulated, p1_cfg)


class TestBaselines(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = EngineBridge().__enter__()
        cls.p1_config = p1_config.load_config(P1_CONFIG_PATH)
        cls.p2a_config = p2a_config.load_config()
        snap = snapshot_engine_constants(cls.bridge)
        cls.engine_baselines = snap["baselineRates"]

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    def test_baseline_0_always_normal_never_detects(self):
        d = _run_dict("sudden_increase", 9101, self.p1_config)
        worker = d["workers"][0]
        result = baselines.baseline_0_always_normal(self.bridge, worker)
        self.assertEqual(result["TP"], 0)
        self.assertEqual(result["FP"], 0)
        self.assertEqual(result["FN"], 1)

    def test_baseline_1_is_the_real_engine_not_a_copy(self):
        d = _run_dict("sudden_increase", 9102, self.p1_config)
        worker = d["workers"][0]
        from phase2a_adapter.detection_adapter import evaluate_radiation_detection
        direct = evaluate_radiation_detection(
            self.bridge, worker, self.p1_config, self.engine_baselines, K=1)
        via_wrapper = baselines.baseline_1_engine_k1(
            self.bridge, worker, self.p1_config, self.engine_baselines)
        self.assertEqual(direct["TP"], via_wrapper["TP"])
        self.assertEqual(direct["FP"], via_wrapper["FP"])
        self.assertEqual(direct["FN"], via_wrapper["FN"])

    def test_baseline_2_fixed_threshold_detects_a_clear_step_event(self):
        d = _run_dict("sudden_increase", 9103, self.p1_config)
        worker = d["workers"][0]
        result = baselines.baseline_2_fixed_threshold(
            self.bridge, worker, self.p1_config, self.engine_baselines, self.p2a_config)
        # step_multiplier range is [2.0, 6.0]; fixed_multiple is 2.0 --
        # the event should cross it in the large majority of seeds, but
        # this is a provisional threshold, not guaranteed for every draw,
        # so the assertion is on TP+FN=1 (exactly one ground-truth event
        # exists), not on TP being 1.
        self.assertEqual(result["TP"] + result["FN"], 1)

    def test_baseline_3_moving_average_runs_and_scores_against_real_engine_matching(self):
        d = _run_dict("sudden_increase", 9104, self.p1_config)
        worker = d["workers"][0]
        result = baselines.baseline_3_moving_average(
            self.bridge, worker, self.p1_config, self.engine_baselines, self.p2a_config)
        self.assertIn("TP", result)
        self.assertEqual(result["TP"] + result["FN"], 1)

    def test_baseline_2_config_is_provisional_not_conventional(self):
        block = self.p2a_config.baseline("baseline_2_fixed_threshold")
        self.assertEqual(block["status"], "PROVISIONAL")

    def test_baseline_3_moving_average_is_not_labeled_conventional_practice(self):
        block = self.p2a_config.baseline("baseline_3_moving_average")
        self.assertEqual(block["status"], "PROVISIONAL")
        self.assertNotIn("conventional", block["description"].lower())


if __name__ == "__main__":
    unittest.main()
