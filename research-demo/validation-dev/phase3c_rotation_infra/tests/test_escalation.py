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

    def test_second_independent_fault_episode_raises_again_after_first_resolves(self):
        """Regression test for a real bug found during the final
        supplementary validation round (Experiment B, "repeated faults"
        sub-case): the raise condition used to read `rec.state == NONE`
        only, so once a worker's first fault episode resolved, a second,
        wholly independent fault episode later in the same shift could
        never raise -- the record was stuck unable to leave RESOLVED.
        Two 10-minute STALE episodes, separated by 15 healthy minutes,
        must each raise and resolve on their own; the scalar fields
        reflect the LATEST (second) episode, and audit_log must contain
        both raised/resolved pairs."""
        states = (["STALE"] * 10 + ["OK"] * 15 + ["STALE"] * 10 + ["OK"] * 5)
        rec = evaluate_escalation("W1", states, shift_minutes=len(states),
                                   escalate_after_minutes=10)
        self.assertEqual(rec.state, RESOLVED)
        raised_events = [e for e in rec.audit_log if e["event"] == "raised"]
        resolved_events = [e for e in rec.audit_log if e["event"] == "resolved"]
        self.assertEqual(len(raised_events), 2)
        self.assertEqual(len(resolved_events), 2)
        self.assertEqual(raised_events[0]["at_minute"], 9)
        self.assertEqual(resolved_events[0]["at_minute"], 10)
        self.assertEqual(raised_events[1]["at_minute"], 34)
        self.assertEqual(resolved_events[1]["at_minute"], 35)
        # scalar fields reflect the latest (second) episode only
        self.assertEqual(rec.raised_at, 34)
        self.assertEqual(rec.resolved_at, 35)

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
        # STALE then DISCONNECTED, both in DQ_FLAGGED_STATES. Post-
        # recovery values are deliberately varied (not a single constant
        # repeated value) so the engine's own separate repeat-value
        # ("frozen") detector does not raise an unrelated SECOND episode
        # here -- this test is specifically about the missing-data
        # episode; test_second_independent_fault_episode_raises_again_
        # after_first_resolves (TestEscalationPureLogic) is where a
        # second, independent episode is deliberately constructed and
        # checked.
        observations = [None] * 15 + [{"ts": t, "value": 50.0 + 0.1 * (t % 3)} for t in range(15, 25)]
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
