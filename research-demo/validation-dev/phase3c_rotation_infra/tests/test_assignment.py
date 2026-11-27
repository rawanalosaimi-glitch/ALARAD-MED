"""Task 3 / 7: worker exclusivity and full-assignment availability --
PHASE3B section 3g's atomic batch reservation."""

from __future__ import annotations

import unittest

from phase1_simulator.scenario import ROOMS
from phase3c_rotation_infra.assignment import (
    RotationRequest,
    advance_resting_to_free,
    batch_resolve,
    complete_reservation,
    mark_rotated_out,
    no_double_reservation,
    release_reservation,
)
from phase3c_rotation_infra.staffing import ASSIGNED, FREE, RESERVED, RESTING, generate_roster

PROCEDURE_CLASSES = ["diagnostic_fluoroscopy", "interventional_cath_lab", "ct", "pet_ct"]


def _roster_by_id(seed=20, shift_minutes=120, n_rooms=2):
    roster = generate_roster(seed, shift_minutes, n_rooms, ROOMS, PROCEDURE_CLASSES)
    return {w.worker_id: w for w in roster}


class TestAssignmentExclusivity(unittest.TestCase):
    def test_two_simultaneous_requests_with_the_same_top_candidate_never_double_reserve(self):
        roster = _roster_by_id()
        worker_ids = sorted(roster)
        # force both rooms to want the same top candidate
        shared_top = worker_ids[0]
        requests = [
            RotationRequest(room="Room B", outgoing_worker_id="X",
                             candidate_order=[shared_top] + worker_ids[1:]),
            RotationRequest(room="Room A", outgoing_worker_id="Y",
                             candidate_order=[shared_top] + worker_ids[1:]),
        ]
        t_eff = {"Room A": 50, "Room B": 50}
        outcomes = batch_resolve(requests, roster, t_decide=10, t_effective_by_room=t_eff)
        self.assertTrue(no_double_reservation(outcomes))
        reserved = {o.room: o.reserved_worker_id for o in outcomes if o.status == "RESERVED"}
        self.assertEqual(len(set(reserved.values())), len(reserved))

    def test_processing_order_is_deterministic_by_ascending_room_name(self):
        roster = _roster_by_id()
        worker_ids = sorted(roster)
        shared_top = worker_ids[0]
        requests = [
            RotationRequest(room="Zebra Room", outgoing_worker_id="X", candidate_order=[shared_top]),
            RotationRequest(room="Alpha Room", outgoing_worker_id="Y", candidate_order=[shared_top]),
        ]
        t_eff = {"Zebra Room": 50, "Alpha Room": 50}
        outcomes = batch_resolve(requests, roster, t_decide=10, t_effective_by_room=t_eff)
        by_room = {o.room: o for o in outcomes}
        # Alpha Room is processed first (ascending name) so it wins the shared top candidate.
        self.assertEqual(by_room["Alpha Room"].status, "RESERVED")
        self.assertEqual(by_room["Alpha Room"].reserved_worker_id, shared_top)
        self.assertEqual(by_room["Zebra Room"].status, "INFEASIBLE")

    def test_reserved_worker_excluded_from_a_later_batch_until_released(self):
        roster = _roster_by_id()
        w = next(iter(roster.values()))
        w.state = RESERVED
        requests = [RotationRequest(room="Room A", outgoing_worker_id="X", candidate_order=[w.worker_id])]
        outcomes = batch_resolve(requests, roster, t_decide=0, t_effective_by_room={"Room A": 20})
        self.assertEqual(outcomes[0].status, "INFEASIBLE")

    def test_candidate_must_be_available_through_the_full_handoff_interval(self):
        roster = _roster_by_id()
        w = next(iter(roster.values()))
        w.availability_windows = [(0, 15)]  # ends before t_effective
        requests = [RotationRequest(room="Room A", outgoing_worker_id="X", candidate_order=[w.worker_id])]
        outcomes = batch_resolve(requests, roster, t_decide=0, t_effective_by_room={"Room A": 20})
        self.assertEqual(outcomes[0].status, "INFEASIBLE")

    def test_candidate_at_rotation_cap_is_skipped(self):
        roster = _roster_by_id()
        ids = sorted(roster)
        roster[ids[0]].rotations_so_far = roster[ids[0]].max_rotations_per_shift
        requests = [RotationRequest(room="Room A", outgoing_worker_id="X", candidate_order=[ids[0], ids[1]])]
        outcomes = batch_resolve(requests, roster, t_decide=0, t_effective_by_room={"Room A": 20})
        self.assertEqual(outcomes[0].status, "RESERVED")
        self.assertEqual(outcomes[0].reserved_worker_id, ids[1])

    def test_resting_worker_excluded(self):
        roster = _roster_by_id()
        w = next(iter(roster.values()))
        w.last_rotation_out_minute = 0
        w.min_rest_between_assignments_minutes = 30
        requests = [RotationRequest(room="Room A", outgoing_worker_id="X", candidate_order=[w.worker_id])]
        outcomes = batch_resolve(requests, roster, t_decide=10, t_effective_by_room={"Room A": 20})
        self.assertEqual(outcomes[0].status, "INFEASIBLE")

    def test_full_lifecycle_state_transitions(self):
        roster = _roster_by_id()
        w = next(iter(roster.values()))
        self.assertEqual(w.state, FREE)
        w.state = RESERVED
        complete_reservation(w)
        self.assertEqual(w.state, ASSIGNED)
        mark_rotated_out(w, t=50)
        self.assertEqual(w.state, RESTING)
        self.assertEqual(w.rotations_so_far, 1)
        self.assertTrue(w.is_resting_at(55))
        advance_resting_to_free(w, t=55)
        self.assertEqual(w.state, RESTING)  # not yet elapsed
        advance_resting_to_free(w, t=50 + w.min_rest_between_assignments_minutes)
        self.assertEqual(w.state, FREE)

    def test_candidate_excluded_if_projected_to_exceed_duty_limit(self):
        """Closes gap 3 (section 3i): a candidate whose
        ProjectedShiftTotalDose would reach their own duty limit before
        the intended assignment ends must be excluded -- not merely
        deprioritized -- when intended_assignment_minutes_by_room is
        supplied."""
        roster = _roster_by_id()
        ids = sorted(roster)
        over_limit, under_limit = roster[ids[0]], roster[ids[1]]
        over_limit.cumulative_dose_mSv = over_limit.max_dose_per_shift_mSv - 0.001
        over_limit.last_valid_rate_uSv_h = 1000.0  # large increment over 60 min
        under_limit.last_valid_rate_uSv_h = 0.0
        requests = [RotationRequest(room="Room A", outgoing_worker_id="X",
                                     candidate_order=[ids[0], ids[1]])]
        outcomes = batch_resolve(
            requests, roster, t_decide=0, t_effective_by_room={"Room A": 20},
            intended_assignment_minutes_by_room={"Room A": 60},
        )
        self.assertEqual(outcomes[0].status, "RESERVED")
        self.assertEqual(outcomes[0].reserved_worker_id, ids[1])

    def test_candidate_with_no_trusted_reading_not_excluded_by_duty_limit(self):
        """Undefined (no trusted reading yet) must never be treated as
        'over limit' -- the candidate remains eligible."""
        roster = _roster_by_id()
        w = next(iter(roster.values()))
        self.assertIsNone(w.last_valid_rate_uSv_h)
        requests = [RotationRequest(room="Room A", outgoing_worker_id="X",
                                     candidate_order=[w.worker_id])]
        outcomes = batch_resolve(
            requests, roster, t_decide=0, t_effective_by_room={"Room A": 20},
            intended_assignment_minutes_by_room={"Room A": 60},
        )
        self.assertEqual(outcomes[0].status, "RESERVED")

    def test_duty_limit_check_skipped_when_not_provided(self):
        """Backward compatibility: omitting
        intended_assignment_minutes_by_room entirely must behave exactly
        as before this check existed, even for a worker who would fail
        it."""
        roster = _roster_by_id()
        w = next(iter(roster.values()))
        w.cumulative_dose_mSv = w.max_dose_per_shift_mSv
        w.last_valid_rate_uSv_h = 10000.0
        requests = [RotationRequest(room="Room A", outgoing_worker_id="X",
                                     candidate_order=[w.worker_id])]
        outcomes = batch_resolve(requests, roster, t_decide=0, t_effective_by_room={"Room A": 20})
        self.assertEqual(outcomes[0].status, "RESERVED")

    def test_release_reservation_goes_free_or_resting(self):
        roster = _roster_by_id()
        w = next(iter(roster.values()))
        w.state = RESERVED
        release_reservation(w, to_resting=False)
        self.assertEqual(w.state, FREE)
        w.state = RESERVED
        release_reservation(w, to_resting=True)
        self.assertEqual(w.state, RESTING)


if __name__ == "__main__":
    unittest.main()
