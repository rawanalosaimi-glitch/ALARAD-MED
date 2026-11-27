"""Task 5 / 7: sensor-fault escalation, independent of dose-trigger
logic (PHASE3B section 3h)."""

from __future__ import annotations

import unittest

from phase2a_adapter.dq_adapter import run_sensor_state_machine
from phase2a_adapter.engine_bridge import EngineBridge
from phase3c_rotation_infra.escalation import ACKNOWLEDGED, NONE, RAISED, RESOLVED, evaluate_escalation


class TestEscalationPureLogic(unittest.TestCase):
    def test_fault_shorter_than_threshold_never_raises(self):
        states = ["OK"] * 5 + ["STALE"] * 3 + ["OK"] * 10
        rec = evaluate_escalation("W1", states, shift_minutes=len(states),
                                   escalate_after_minutes=10)
        self.assertEqual(rec.state, NONE)
        self.assertIsNone(rec.raised_at)

    def test_fault_at_threshold_raises(self):
        states = ["STALE"] * 10 + ["OK"] * 5
        rec = evaluate_escalation("W1", states, shift_minutes=len(states),
                                   escalate_after_minutes=10)
        self.assertEqual(rec.raised_at, 9)  # 0-indexed: 10th consecutive minute

    def test_raised_resolves_when_fault_clears_unacknowledged(self):
        states = ["STALE"] * 12 + ["OK"] * 5
        rec = evaluate_escalation("W1", states, shift_minutes=len(states),
                                   escalate_after_minutes=10)
        self.assertEqual(rec.state, RESOLVED)
        self.assertEqual(rec.resolution_reason, "sensor_fault_cleared")

    def test_acknowledgement_before_fault_clears(self):
        states = ["STALE"] * 20
        rec = evaluate_escalation("W1", states, shift_minutes=len(states),
                                   escalate_after_minutes=10, ack_minute=12)
        self.assertEqual(rec.acknowledged_at, 12)
        # still raised->acknowledged->resolved at shift end (fault never cleared)
        self.assertEqual(rec.state, RESOLVED)
        self.assertEqual(rec.resolution_reason, "acknowledged_shift_ended")

    def test_unacknowledged_at_shift_end_is_flagged_distinctly(self):
        states = ["STALE"] * 20
        rec = evaluate_escalation("W1", states, shift_minutes=len(states),
                                   escalate_after_minutes=10, ack_minute=None)
        self.assertEqual(rec.state, RESOLVED)
        self.assertEqual(rec.resolution_reason, "unacknowledged_at_shift_end")
        self.assertIsNone(rec.acknowledged_at)

    def test_escalation_never_mentions_dose_values(self):
        """Structural guarantee, checked directly: evaluate_escalation's
        signature and audit log carry no dose-related field at all."""
        states = ["STALE"] * 20
        rec = evaluate_escalation("W1", states, shift_minutes=len(states), escalate_after_minutes=10)
        for entry in rec.audit_log:
            for key in entry:
                self.assertNotIn("dose", key.lower())

    def test_audit_log_is_never_empty_once_raised(self):
        states = ["STALE"] * 20
        rec = evaluate_escalation("W1", states, shift_minutes=len(states), escalate_after_minutes=10)
        self.assertGreater(len(rec.audit_log), 0)
        events = [e["event"] for e in rec.audit_log]
        self.assertIn("raised", events)
        self.assertIn("resolved", events)


class TestEscalationAgainstRealEngine(unittest.TestCase):
    """Integration check: feed the real, unmodified AlaradSafety.sensorStep
    output (via phase2a_adapter.dq_adapter, reused unchanged) into
    evaluate_escalation, so this module is proven to interoperate with
    the actual frozen engine's sensor states, not just a hand-written
    state list."""

    def test_real_missing_sensor_sequence_raises_escalation(self):
        # 15 consecutive missing readings -> engine states step through
        # STALE then DISCONNECTED, both in DQ_FLAGGED_STATES.
        observations = [None] * 15 + [{"ts": t, "value": 50.0} for t in range(15, 25)]
        with EngineBridge() as bridge:
            steps = run_sensor_state_machine(bridge, observations)
        sensor_states = [s["state"] for s in steps]
        rec = evaluate_escalation("W1", sensor_states, shift_minutes=len(sensor_states),
                                   escalate_after_minutes=5)
        self.assertEqual(rec.state, RESOLVED)
        self.assertIsNotNone(rec.raised_at)
        self.assertEqual(rec.resolution_reason, "sensor_fault_cleared")


if __name__ == "__main__":
    unittest.main()
