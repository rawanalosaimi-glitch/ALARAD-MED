"""Task 2 (part 3) / 7: dose attribution over the two-layer model --
collective-dose conservation under fixed occupancy, and no double
counting or missing dose attribution (PHASE3B sections 5a, 7a, 7b)."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from phase1_simulator import config as p1_config_mod
from phase3c_rotation_infra.dose_attribution import (
    AttributionConflictError,
    apply_rotation,
    attribute_dose,
    build_full_occupancy_assignment,
    collective_dose_mSv,
    cumulative_dose_per_worker,
    total_exposure_mSv,
)
from phase3c_rotation_infra.exposure_layer import generate_exposure_layer, generate_slots_for_room

P1_CONFIG_PATH = Path(p1_config_mod.__file__).parent / "config" / "simulation_config.json"


class TestDoseAttribution(unittest.TestCase):
    def setUp(self):
        self.p1_cfg = p1_config_mod.load_config(P1_CONFIG_PATH)
        self.shift_minutes = 120
        self.slots_by_room = {
            "Cath Lab 1": generate_slots_for_room(5, "Cath Lab 1", self.shift_minutes, self.p1_cfg),
            "CT Suite": generate_slots_for_room(5, "CT Suite", self.shift_minutes, self.p1_cfg),
        }
        self.exposure_by_slot = generate_exposure_layer(5, self.slots_by_room)

    def test_collective_dose_conservation_under_fixed_occupancy_no_rotation_vs_rotated(self):
        """Two different assignment layers, same exposure layer, both
        with full (gapless) occupancy: the no-rotation baseline, and one
        where a rotation happens partway through each room but every
        minute is still assigned to exactly one worker throughout. Per
        the section 7b invariant, collective dose must be identical."""
        initial = {"Cath Lab 1": "W-A", "CT Suite": "W-C"}
        assignment_no_rotation = build_full_occupancy_assignment(
            self.slots_by_room, initial, self.shift_minutes)
        assignment_rotated = copy.deepcopy(assignment_no_rotation)
        apply_rotation(assignment_rotated, "Cath Lab 1", t_effective=60, new_worker_id="W-B")
        apply_rotation(assignment_rotated, "CT Suite", t_effective=40, new_worker_id="W-D")

        rates_no_rot = attribute_dose(self.slots_by_room, self.exposure_by_slot,
                                       assignment_no_rotation, self.shift_minutes)
        rates_rotated = attribute_dose(self.slots_by_room, self.exposure_by_slot,
                                        assignment_rotated, self.shift_minutes)

        cum_no_rot = cumulative_dose_per_worker(rates_no_rot)
        cum_rotated = cumulative_dose_per_worker(rates_rotated)

        collective_no_rot = collective_dose_mSv(cum_no_rot)
        collective_rotated = collective_dose_mSv(cum_rotated)
        reference_total = total_exposure_mSv(self.slots_by_room, self.exposure_by_slot)

        self.assertAlmostEqual(collective_no_rot, reference_total, places=9)
        self.assertAlmostEqual(collective_rotated, reference_total, places=9)
        self.assertAlmostEqual(collective_no_rot, collective_rotated, places=9)

        # but the INDIVIDUAL and MAX-INDIVIDUAL doses must differ --
        # rotation redistributes, it does not change the total (task 7).
        self.assertNotEqual(set(cum_no_rot), set(cum_rotated))
        self.assertIn("W-B", cum_rotated)
        self.assertIn("W-D", cum_rotated)

    def test_no_double_counting_conflicting_assignment_raises(self):
        initial = {"Cath Lab 1": "W-A", "CT Suite": "W-C"}
        assignment = build_full_occupancy_assignment(self.slots_by_room, initial, self.shift_minutes)
        # force a conflict: W-A also claimed by CT Suite at the same minutes
        assignment["CT Suite"] = ["W-A"] * self.shift_minutes
        with self.assertRaises(AttributionConflictError):
            attribute_dose(self.slots_by_room, self.exposure_by_slot, assignment, self.shift_minutes)

    def test_no_missing_attribution_every_exposure_minute_is_counted_exactly_once(self):
        initial = {"Cath Lab 1": "W-A", "CT Suite": "W-C"}
        assignment = build_full_occupancy_assignment(self.slots_by_room, initial, self.shift_minutes)
        rates = attribute_dose(self.slots_by_room, self.exposure_by_slot, assignment, self.shift_minutes)
        cum = cumulative_dose_per_worker(rates)
        self.assertAlmostEqual(sum(cum.values()),
                                total_exposure_mSv(self.slots_by_room, self.exposure_by_slot),
                                places=9)

    def test_unassigned_minutes_contribute_zero_dose(self):
        initial = {"Cath Lab 1": "W-A", "CT Suite": "W-C"}
        assignment = build_full_occupancy_assignment(self.slots_by_room, initial, self.shift_minutes)
        assignment["CT Suite"] = [None] * self.shift_minutes  # nobody assigned
        rates = attribute_dose(self.slots_by_room, self.exposure_by_slot, assignment, self.shift_minutes)
        self.assertNotIn("W-C", rates)
        cum = cumulative_dose_per_worker(rates)
        total = sum(cum.values())
        # only Cath Lab 1's exposure should be attributed
        cath_lab_total = sum(
            self._slot_dose(slot) for slot in self.slots_by_room["Cath Lab 1"]
        )
        self.assertAlmostEqual(total, cath_lab_total, places=9)

    def _slot_dose(self, slot):
        from phase1_simulator.units import MINUTE_H, dose_increment_mSv
        return sum(dose_increment_mSv(r, MINUTE_H) for r in self.exposure_by_slot[slot.slot_id])


if __name__ == "__main__":
    unittest.main()
