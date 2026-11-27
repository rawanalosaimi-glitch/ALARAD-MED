"""Tests for the campaign scenario builder: reuses Phase 1's own
archetype generators unchanged, repurposed as room-tracks."""

from __future__ import annotations

import unittest
from pathlib import Path

from phase1_simulator import config as p1_config_mod
from phase1_simulator.scenario import ARCHETYPES
from phase3c_rotation_infra.campaign_scenarios import build_campaign_run, room_boundaries_minutes
from phase3c_rotation_infra.config import load_config

P1_CONFIG_PATH = Path(p1_config_mod.__file__).parent / "config" / "simulation_config.json"


class TestCampaignScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p1_cfg = p1_config_mod.load_config(P1_CONFIG_PATH)
        cls.p3c_cfg = load_config()

    def test_all_13_archetypes_build_without_error(self):
        for archetype in ARCHETYPES:
            run = build_campaign_run(99, archetype, self.p1_cfg, self.p3c_cfg)
            self.assertEqual(len(run["slots_by_room"]), len(run["observations_by_room"]))
            for room, slots in run["slots_by_room"].items():
                total = sum(len(run["exposure_by_slot"][s.slot_id]) for s in slots)
                self.assertEqual(total, run["shift_minutes"])
                self.assertEqual(len(run["observations_by_room"][room]), run["shift_minutes"])

    def test_reproducible_for_same_seed_and_archetype(self):
        run1 = build_campaign_run(42, "normal", self.p1_cfg, self.p3c_cfg)
        run2 = build_campaign_run(42, "normal", self.p1_cfg, self.p3c_cfg)
        self.assertEqual(run1["exposure_by_slot"], run2["exposure_by_slot"])
        self.assertEqual(list(run1["slots_by_room"].keys()), list(run2["slots_by_room"].keys()))

    def test_multi_worker_archetype_produces_multiple_room_tracks(self):
        run = build_campaign_run(99, "multi_worker_mixed", self.p1_cfg, self.p3c_cfg)
        self.assertGreater(len(run["slots_by_room"]), 1)

    def test_exposure_values_are_non_negative_floats(self):
        run = build_campaign_run(99, "fault_invalid", self.p1_cfg, self.p3c_cfg)
        for series in run["exposure_by_slot"].values():
            for v in series:
                self.assertIsInstance(v, float)
                self.assertGreaterEqual(v, 0.0)

    def test_room_boundaries_minutes_matches_slot_edges(self):
        run = build_campaign_run(99, "normal", self.p1_cfg, self.p3c_cfg)
        for room, slots in run["slots_by_room"].items():
            boundaries = room_boundaries_minutes(slots)
            self.assertEqual(boundaries[0], slots[0].start_minute)
            self.assertEqual(boundaries[-1], slots[-1].end_minute)


if __name__ == "__main__":
    unittest.main()
