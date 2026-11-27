"""Task 7: a small end-to-end wiring test combining staffing, the
exposure layer, atomic reservation, scheduling, and dose attribution --
WITHOUT any CGDTR trigger/selection logic. Rotation requests here are
supplied directly by the test (synthetic/programmatic), exactly as
PHASE3C-A's scope requires. Exercises overall seed reproducibility and
exposure-layer identity across two different, directly-supplied
assignment policies."""

from __future__ import annotations

import unittest
from pathlib import Path

from phase1_simulator import config as p1_config_mod
from phase1_simulator.scenario import ROOMS
from phase3c_rotation_infra.assignment import RotationRequest, batch_resolve, complete_reservation
from phase3c_rotation_infra.dose_attribution import (
    apply_rotation,
    attribute_dose,
    build_full_occupancy_assignment,
    collective_dose_mSv,
    cumulative_dose_per_worker,
    total_exposure_mSv,
)
from phase3c_rotation_infra.exposure_layer import generate_exposure_layer, generate_slots_for_room
from phase3c_rotation_infra.scheduling import COMPLETED, resolve_attempt, start_attempt
from phase3c_rotation_infra.staffing import generate_roster

P1_CONFIG_PATH = Path(p1_config_mod.__file__).parent / "config" / "simulation_config.json"
PROCEDURE_CLASSES = ["diagnostic_fluoroscopy", "interventional_cath_lab", "ct", "pet_ct"]
ROOMS_USED = ["Cath Lab 1", "CT Suite"]
SHIFT_MINUTES = 120


def _build_pipeline(seed: int):
    p1_cfg = p1_config_mod.load_config(P1_CONFIG_PATH)
    roster = generate_roster(seed, SHIFT_MINUTES, len(ROOMS_USED), ROOMS, PROCEDURE_CLASSES)
    roster_by_id = {w.worker_id: w for w in roster}
    slots_by_room = {room: generate_slots_for_room(seed, room, SHIFT_MINUTES, p1_cfg) for room in ROOMS_USED}
    exposure_by_slot = generate_exposure_layer(seed, slots_by_room)
    return roster_by_id, slots_by_room, exposure_by_slot


class TestIntegrationSmoke(unittest.TestCase):
    def test_pipeline_is_seed_reproducible_end_to_end(self):
        r1, s1, e1 = _build_pipeline(321)
        r2, s2, e2 = _build_pipeline(321)
        self.assertEqual(sorted(r1), sorted(r2))
        self.assertEqual(e1, e2)

    def test_two_policies_on_identical_exposure_layer_simultaneous_rotation_requests(self):
        p1_cfg = p1_config_mod.load_config(P1_CONFIG_PATH)
        # Roster sized for 3 "concurrent rooms" (not the real 2) so that,
        # after the 2 initial assignments, at least 2 spare workers exist
        # -- enough for both rooms' simultaneous requests to each get a
        # DISTINCT replacement, which is what this test needs to exercise
        # (a staffing shortage that leaves only one spare is itself a
        # legitimate, separately-tested infeasible outcome -- see
        # test_assignment.py's dedicated exclusivity tests for that case).
        roster = generate_roster(777, SHIFT_MINUTES, 3, ROOMS, PROCEDURE_CLASSES)
        roster_by_id = {w.worker_id: w for w in roster}
        slots_by_room = {room: generate_slots_for_room(777, room, SHIFT_MINUTES, p1_cfg) for room in ROOMS_USED}
        exposure_by_slot = generate_exposure_layer(777, slots_by_room)
        worker_ids = sorted(roster_by_id)
        initial = {"Cath Lab 1": worker_ids[0], "CT Suite": worker_ids[1]}

        # Policy A: no rotation at all.
        assignment_a = build_full_occupancy_assignment(slots_by_room, initial, SHIFT_MINUTES)

        # Policy B: a synthetic, programmatically-supplied simultaneous
        # rotation request in BOTH rooms at the same boundary -- not a
        # dose-triggered decision (none is implemented this round).
        requests = [
            RotationRequest(room="Cath Lab 1", outgoing_worker_id=initial["Cath Lab 1"],
                             candidate_order=[w for w in worker_ids if w not in initial.values()]),
            RotationRequest(room="CT Suite", outgoing_worker_id=initial["CT Suite"],
                             candidate_order=[w for w in worker_ids if w not in initial.values()]),
        ]
        t_decide = 30
        min_handoff = 10
        boundaries = {room: [s.start_minute for s in slots_by_room[room]] + [SHIFT_MINUTES]
                      for room in ROOMS_USED}

        # First pass: compute a provisional t_effective per room (needed
        # by batch_resolve's forward-looking availability check) using
        # each room's own boundary set.
        t_eff_guess = {room: min(b for b in boundaries[room] if b >= t_decide + min_handoff)
                       for room in ROOMS_USED}
        outcomes = batch_resolve(requests, roster_by_id, t_decide, t_eff_guess)
        self.assertTrue(all(o.status == "RESERVED" for o in outcomes))
        reserved = {o.room: o.reserved_worker_id for o in outcomes}
        self.assertEqual(len(set(reserved.values())), 2)  # never double-reserved

        assignment_b = build_full_occupancy_assignment(slots_by_room, initial, SHIFT_MINUTES)
        for room, candidate_id in reserved.items():
            attempt = start_attempt(room, initial[room], candidate_id, t_decide,
                                     min_handoff, boundaries[room], SHIFT_MINUTES)
            resolved = resolve_attempt(attempt)
            self.assertEqual(resolved.status, COMPLETED)
            complete_reservation(roster_by_id[candidate_id])
            apply_rotation(assignment_b, room, resolved.t_effective, candidate_id)

        # The exposure layer itself must be untouched and identical --
        # only the assignment differs between policy A and policy B.
        self.assertEqual(
            generate_exposure_layer(777, slots_by_room), exposure_by_slot,
            "exposure layer must not be mutated or regenerated by policy B",
        )

        rates_a = attribute_dose(slots_by_room, exposure_by_slot, assignment_a, SHIFT_MINUTES)
        rates_b = attribute_dose(slots_by_room, exposure_by_slot, assignment_b, SHIFT_MINUTES)
        cum_a = cumulative_dose_per_worker(rates_a)
        cum_b = cumulative_dose_per_worker(rates_b)

        reference_total = total_exposure_mSv(slots_by_room, exposure_by_slot)
        self.assertAlmostEqual(collective_dose_mSv(cum_a), reference_total, places=9)
        self.assertAlmostEqual(collective_dose_mSv(cum_b), reference_total, places=9)
        self.assertAlmostEqual(collective_dose_mSv(cum_a), collective_dose_mSv(cum_b), places=9)
        # individual doses differ -- rotation redistributed, did not
        # change the total (the exact distinction task 7 requires).
        self.assertNotEqual(cum_a, cum_b)


if __name__ == "__main__":
    unittest.main()
