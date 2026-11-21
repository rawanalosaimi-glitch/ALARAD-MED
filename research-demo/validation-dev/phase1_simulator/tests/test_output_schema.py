"""
Unit tests for output schema (Phase 1 deliverable C, item 5), plus the
provisional-parameter-labeling enforcement required by Phase 1 items 6-7.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from phase1_simulator import config as cfg_mod
from phase1_simulator import output, scenario

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "simulation_config.json"

REQUIRED_TOP_LEVEL_KEYS = {
    "schema_version", "phase", "methodology_reference",
    "config_schema_version", "config_disclaimer", "units", "run_id",
    "archetype", "seed", "shift_minutes", "workers",
}
REQUIRED_WORKER_KEYS = {
    "worker_id", "room", "procedure_class", "proc_mult", "mode",
    "dose_label", "truth_events", "fault_events", "true_dose_mSv",
    "observed_dose_mSv", "trusted_minutes", "uncertain_minutes",
    "unmonitored_minutes", "series",
}


class TestOutputSchema(unittest.TestCase):
    def setUp(self):
        self.config = cfg_mod.load_config(CONFIG_PATH)

    def _generate(self, archetype, seed):
        run = scenario.generate_run(archetype, seed, self.config)
        simulated = scenario.simulate_run(run, self.config)
        return output.run_to_dict(simulated, self.config)

    def test_top_level_keys_present_for_every_archetype(self):
        for archetype in scenario.ARCHETYPES:
            d = self._generate(archetype, 4001)
            missing = REQUIRED_TOP_LEVEL_KEYS - set(d.keys())
            self.assertEqual(missing, set(), msg=archetype)

    def test_worker_keys_present(self):
        d = self._generate("multi_worker_faults", 4002)
        for w in d["workers"]:
            missing = REQUIRED_WORKER_KEYS - set(w.keys())
            self.assertEqual(missing, set())

    def test_units_block_matches_methodology(self):
        d = self._generate("normal", 4003)
        self.assertEqual(d["units"]["dose_rate"], "uSv/h")
        self.assertEqual(d["units"]["cumulative_dose"], "mSv")
        self.assertEqual(d["units"]["time_step_minutes"], 1)

    def test_output_is_json_round_trippable(self):
        d = self._generate("area_relocation", 4004)
        reloaded = json.loads(json.dumps(d))
        self.assertEqual(reloaded["run_id"], d["run_id"])
        self.assertEqual(reloaded, d)

    def test_phase_label_distinguishes_from_evaluation(self):
        d = self._generate("normal", 4005)
        self.assertIn("Phase 1", d["phase"])
        self.assertIn("No detector", d["phase"])

    def test_config_disclaimer_is_carried_into_output(self):
        d = self._generate("normal", 4006)
        self.assertIn("PROVISIONAL", d["config_disclaimer"].upper())

    def test_series_length_matches_shift_minutes(self):
        d = self._generate("sudden_increase", 4007)
        for w in d["workers"]:
            self.assertEqual(len(w["series"]["true_rate_uSv_h"]), d["shift_minutes"])
            self.assertEqual(len(w["series"]["observed_rate_uSv_h"]), d["shift_minutes"])
            self.assertEqual(len(w["series"]["observed_status_per_minute"]), d["shift_minutes"])

    def test_write_run_output_round_trip(self):
        run = scenario.generate_run("sudden_increase", 4008, self.config)
        simulated = scenario.simulate_run(run, self.config)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            output.write_run_output(simulated, self.config, path)
            self.assertTrue(path.exists())
            reloaded = json.loads(path.read_text())
            self.assertEqual(reloaded["run_id"], run.run_id)


class TestConfigProvisionalLabeling(unittest.TestCase):
    """Enforces Phase 1 items 6 and 7: provisional parameters must be
    labeled as provisional, and the config loader must refuse to load a
    configuration that fails to label them."""

    def test_shipped_config_passes_provisional_labeling_check(self):
        cfg = cfg_mod.load_config(CONFIG_PATH)
        self.assertTrue(cfg.every_provisional_item_is_labeled())

    def test_shipped_config_is_explicitly_not_clinically_validated(self):
        cfg = cfg_mod.load_config(CONFIG_PATH)
        self.assertIn("NOT CLINICALLY VALIDATED", cfg.raw["_disclaimer"].upper())

    def test_config_without_disclaimer_is_rejected(self):
        bad = {"schema_version": "1.0.0", "provisional_parameters": {}}
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.json"
            p.write_text(json.dumps(bad))
            with self.assertRaises(cfg_mod.ConfigValidationError):
                cfg_mod.load_config(p)

    def test_config_with_unlabeled_parameter_is_rejected(self):
        bad = {
            "_disclaimer": "PROVISIONAL - test",
            "schema_version": "1.0.0",
            "provisional_parameters": {"some_param": {"value": 1.0}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad2.json"
            p.write_text(json.dumps(bad))
            with self.assertRaises(cfg_mod.ConfigValidationError):
                cfg_mod.load_config(p)

    def test_config_with_fabricated_validated_status_is_rejected(self):
        # A status claiming clinical validation is not a recognized
        # provisional status -- it must be rejected, not accepted at
        # face value.
        bad = {
            "_disclaimer": "PROVISIONAL - test",
            "schema_version": "1.0.0",
            "provisional_parameters": {
                "some_param": {"value": 1.0, "status": "CLINICALLY_VALIDATED"}
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad3.json"
            p.write_text(json.dumps(bad))
            with self.assertRaises(cfg_mod.ConfigValidationError):
                cfg_mod.load_config(p)


if __name__ == "__main__":
    unittest.main()
