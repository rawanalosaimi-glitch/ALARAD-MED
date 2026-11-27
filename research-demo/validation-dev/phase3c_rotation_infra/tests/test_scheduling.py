"""Task 4 / 7: procedure-boundary and handoff scheduling --
PHASE3B section 3d's explicit timeline, and task 4's requirement that a
held-by-incident handoff recomputes the next valid boundary after
acknowledgement and never executes mid-procedure."""

from __future__ import annotations

import unittest

from phase3c_rotation_infra.scheduling import (
    ABORTED,
    COMPLETED,
    HELD,
    INFEASIBLE,
    PENDING,
    compute_t_effective,
    compute_t_ready,
    recompute_after_acknowledgement,
    resolve_attempt,
    start_attempt,
)


class TestScheduling(unittest.TestCase):
    def test_t_effective_always_lands_on_a_boundary(self):
        boundaries = [0, 20, 40, 60, 80, 100]
        for t_ready in range(0, 101):
            t_eff = compute_t_effective(t_ready, boundaries, shift_minutes=100)
            if t_eff is not None:
                self.assertIn(t_eff, boundaries)

    def test_t_effective_is_the_next_boundary_at_or_after_t_ready(self):
        boundaries = [0, 20, 40, 60, 80, 100]
        self.assertEqual(compute_t_effective(21, boundaries, 100), 40)
        self.assertEqual(compute_t_effective(20, boundaries, 100), 20)

    def test_infeasible_when_no_boundary_remains_before_shift_end(self):
        boundaries = [0, 20, 40]
        self.assertIsNone(compute_t_effective(50, boundaries, shift_minutes=40))

    def test_shift_end_is_always_treated_as_a_boundary_even_if_omitted(self):
        boundaries = [0, 20, 40]  # caller forgot to include 100
        self.assertEqual(compute_t_effective(50, boundaries, shift_minutes=100), 100)

    def test_handoff_spanning_multiple_boundaries_lands_on_first_valid_one(self):
        boundaries = [0, 10, 20, 30, 40, 50]
        # t_decide=5, handoff=12 -> t_ready=17 -> first boundary >= 17 is 20
        attempt = start_attempt("Room A", "W1", "W2", t_decide=5,
                                 min_handoff_duration_minutes=12,
                                 boundaries=boundaries, shift_minutes=50)
        self.assertEqual(attempt.status, PENDING)
        self.assertEqual(attempt.t_ready, 17)
        self.assertEqual(attempt.t_effective, 20)

    def test_rotation_infeasible_when_no_eligible_candidate(self):
        attempt = start_attempt("Room A", "W1", None, t_decide=5,
                                 min_handoff_duration_minutes=10,
                                 boundaries=[0, 20, 40], shift_minutes=40)
        self.assertEqual(attempt.status, INFEASIBLE)
        self.assertEqual(attempt.reason, "no_eligible_candidate")

    def test_rotation_infeasible_near_shift_end(self):
        attempt = start_attempt("Room A", "W1", "W2", t_decide=35,
                                 min_handoff_duration_minutes=10,
                                 boundaries=[0, 20, 40], shift_minutes=40)
        self.assertEqual(attempt.status, INFEASIBLE)
        self.assertEqual(attempt.reason, "no_boundary_at_or_after_t_ready_before_shift_end")

    def test_ordinary_completion(self):
        attempt = start_attempt("Room A", "W1", "W2", t_decide=0,
                                 min_handoff_duration_minutes=10,
                                 boundaries=[0, 20, 40], shift_minutes=40)
        resolved = resolve_attempt(attempt)
        self.assertEqual(resolved.status, COMPLETED)
        self.assertEqual(resolved.t_effective, 20)

    def test_never_completes_mid_procedure_without_override(self):
        boundaries = [0, 20, 40, 60]
        attempt = start_attempt("Room A", "W1", "W2", t_decide=5,
                                 min_handoff_duration_minutes=3,
                                 boundaries=boundaries, shift_minutes=60)
        # t_ready = 8, which is NOT a boundary -- t_effective must roll forward to 20
        self.assertEqual(attempt.t_effective, 20)
        resolved = resolve_attempt(attempt)
        self.assertEqual(resolved.status, COMPLETED)
        self.assertIn(resolved.t_effective, boundaries)
        self.assertFalse(resolved.override_used)

    def test_emergency_override_bypasses_boundary_alignment(self):
        boundaries = [0, 20, 40, 60]
        attempt = start_attempt("Room A", "W1", "W2", t_decide=5,
                                 min_handoff_duration_minutes=3,
                                 boundaries=boundaries, shift_minutes=60)
        resolved = resolve_attempt(attempt, emergency_override=True)
        self.assertEqual(resolved.status, COMPLETED)
        self.assertEqual(resolved.t_effective, 5)  # mid-procedure, by design, ONLY via override
        self.assertTrue(resolved.override_used)
        self.assertEqual(resolved.reason, "emergency_override")

    def test_interrupted_handoff_aborts_and_does_not_swap(self):
        boundaries = [0, 20, 40]
        attempt = start_attempt("Room A", "W1", "W2", t_decide=0,
                                 min_handoff_duration_minutes=10,
                                 boundaries=boundaries, shift_minutes=40)
        resolved = resolve_attempt(attempt, eligibility_still_holds_fn=lambda t: t < 5)
        self.assertEqual(resolved.status, ABORTED)
        self.assertEqual(resolved.reason, "eligibility_changed_mid_handoff")

    def test_incident_open_at_effective_time_holds_not_completes(self):
        boundaries = [0, 20, 40]
        attempt = start_attempt("Room A", "W1", "W2", t_decide=0,
                                 min_handoff_duration_minutes=10,
                                 boundaries=boundaries, shift_minutes=40)
        resolved = resolve_attempt(attempt, incident_open_fn=lambda t: True)
        self.assertEqual(resolved.status, HELD)

    def test_held_attempt_recomputes_next_boundary_after_acknowledgement_not_the_stale_one(self):
        boundaries = [0, 20, 40, 60, 80]
        attempt = start_attempt("Room A", "W1", "W2", t_decide=0,
                                 min_handoff_duration_minutes=10,
                                 boundaries=boundaries, shift_minutes=80)
        held = resolve_attempt(attempt, incident_open_fn=lambda t: True)
        self.assertEqual(held.status, HELD)
        self.assertEqual(held.t_effective, 20)  # the original, now-passed boundary
        ack_minute = 45  # acknowledged well after the original boundary passed
        recomputed = recompute_after_acknowledgement(held, t_ack=ack_minute,
                                                       boundaries=boundaries, shift_minutes=80)
        self.assertEqual(recomputed.status, COMPLETED)
        self.assertEqual(recomputed.t_effective, 60)  # next boundary at/after ack, never 20
        self.assertIn(recomputed.t_effective, boundaries)

    def test_held_attempt_aborts_if_no_boundary_remains_after_acknowledgement(self):
        boundaries = [0, 20, 40]
        attempt = start_attempt("Room A", "W1", "W2", t_decide=0,
                                 min_handoff_duration_minutes=10,
                                 boundaries=boundaries, shift_minutes=40)
        held = resolve_attempt(attempt, incident_open_fn=lambda t: True)
        self.assertEqual(held.status, HELD)
        recomputed = recompute_after_acknowledgement(held, t_ack=45, boundaries=boundaries, shift_minutes=40)
        self.assertEqual(recomputed.status, ABORTED)
        self.assertEqual(recomputed.reason, "no_boundary_after_acknowledgement_before_shift_end")

    def test_audit_log_records_every_transition(self):
        attempt = start_attempt("Room A", "W1", "W2", t_decide=0,
                                 min_handoff_duration_minutes=10,
                                 boundaries=[0, 20, 40], shift_minutes=40)
        resolve_attempt(attempt)
        events = [e["event"] for e in attempt.audit_log]
        self.assertIn("pending", events)
        self.assertIn("completed", events)


if __name__ == "__main__":
    unittest.main()
