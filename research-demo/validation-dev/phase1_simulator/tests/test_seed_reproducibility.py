"""
Unit tests for deterministic seed reproducibility (Phase 1 deliverable C, item 2).
"""

from __future__ import annotations

import unittest
from pathlib import Path

from phase1_simulator import config as cfg_mod
from phase1_simulator import output, scenario

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "simulation_config.json"


class TestSeedReproducibility(unittest.TestCase):
    def setUp(self):
        self.config = cfg_mod.load_config(CONFIG_PATH)

    def _run_dict(self, archetype, seed):
        run = scenario.generate_run(archetype, seed, self.config)
        simulated = scenario.simulate_run(run, self.config)
        return output.run_to_dict(simulated, self.config)

    def test_same_seed_same_archetype_is_identical(self):
        d1 = self._run_dict("gradual_increase", 42)
        d2 = self._run_dict("gradual_increase", 42)
        self.assertEqual(d1, d2)

    def test_different_seed_differs(self):
        d1 = self._run_dict("gradual_increase", 42)
        d2 = self._run_dict("gradual_increase", 43)
        self.assertNotEqual(d1, d2)

    def test_different_archetype_same_seed_differs(self):
        d1 = self._run_dict("sudden_increase", 99)
        d2 = self._run_dict("fault_missing", 99)
        self.assertNotEqual(d1, d2)

    def test_all_archetypes_generate_without_error_and_are_reproducible(self):
        for archetype in scenario.ARCHETYPES:
            d_a = self._run_dict(archetype, 777)
            d_b = self._run_dict(archetype, 777)
            self.assertEqual(d_a, d_b, msg=f"archetype {archetype!r} was not reproducible")

    def test_worker_count_is_at_least_one_for_every_archetype(self):
        for archetype in scenario.ARCHETYPES:
            run = scenario.generate_run(archetype, 555, self.config)
            self.assertGreaterEqual(len(run.workers), 1, msg=archetype)


if __name__ == "__main__":
    unittest.main()
