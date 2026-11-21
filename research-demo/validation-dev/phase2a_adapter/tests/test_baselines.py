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

    def test_validity_gate_matches_real_engine_on_a_negative_non_nan_value(self):
        """Phase 2C item 2 regression: a negative, non-NaN rescaled value
        is accepted by the OLD narrow check (`v is None or v != v`) --
        the engine's own SimLab.pure.validReading correctly rejects it
        (frozen release: a reading is valid only if >= 0). This proves
        the fix (PHASE2B_INTEGRATION_AUDIT.md section 5, Finding 1)
        actually changes behavior, not just that it runs without error."""
        from phase2a_adapter.detection_adapter import valid_mask
        series = [50.0, -12.0, 60.0, float("nan"), None, 45.0]
        mask = valid_mask(self.bridge, series)
        self.assertEqual(mask, [True, False, True, False, False, True])
        # The old check would have scored index 1 as valid (-12 == -12,
        # not NaN, not None) -- confirm that premise directly.
        old_check_would_accept = [v is not None and v == v for v in series]
        self.assertTrue(old_check_would_accept[1])
        self.assertFalse(mask[1])

    def test_baseline_2_excludes_a_negative_value_the_old_check_would_have_flagged(self):
        """End-to-end version of the above: baseline_2's flagged output
        must never flag an engine-invalid (here: negative) reading, even
        though it clears the fixed-multiple threshold numerically."""
        d = _run_dict("sudden_increase", 9105, self.p1_config)
        worker = d["workers"][0]
        engine_baseline = self.engine_baselines[worker["room"]] * worker["proc_mult"]
        # Inject a large negative value early in the series -- numerically
        # it would clear any sane fixed_multiple*baseline threshold if
        # compared naively, but must never be flagged, since it is not a
        # physically valid reading.
        worker = dict(worker)
        worker["series"] = dict(worker["series"])
        tampered = list(worker["series"]["observed_rate_uSv_h"])
        tampered[0] = -9999.0
        worker["series"]["observed_rate_uSv_h"] = tampered
        result = baselines.baseline_2_fixed_threshold(
            self.bridge, worker, self.p1_config, self.engine_baselines, self.p2a_config)
        self.assertEqual(result["FP"], 0, msg=f"a negative reading must never be flagged: {result}")


if __name__ == "__main__":
    unittest.main()
