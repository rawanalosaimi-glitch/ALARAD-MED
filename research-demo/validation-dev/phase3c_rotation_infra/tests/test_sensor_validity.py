"""Closes gap 1/4 (PHASE3C_A_REVIEW_AGAINST_REVISION_3.md section 2):
per-minute sensor-validity queries against the real, unmodified engine."""

from __future__ import annotations

import unittest

from phase2a_adapter.dq_adapter import run_sensor_state_machine
from phase2a_adapter.engine_bridge import EngineBridge
from phase3c_rotation_infra.sensor_validity import (
    TRUSTED_FOR_TRIGGER,
    new_sensor_state,
    query_sensor_validity,
    sensor_step_once,
)


class TestSensorValidity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = EngineBridge().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    def test_new_sensor_state_is_healthy(self):
        s = new_sensor_state(self.bridge)
        self.assertEqual(s["state"], "HEALTHY")

    def test_single_valid_reading_is_usable_and_trusted(self):
        prev = new_sensor_state(self.bridge)
        step = sensor_step_once(self.bridge, prev, 50.0, 0)
        self.assertEqual(step["state"], "HEALTHY")
        self.assertTrue(step["usable"])

    def test_missing_reading_is_not_usable(self):
        prev = new_sensor_state(self.bridge)
        step = sensor_step_once(self.bridge, prev, None, 0)
        self.assertFalse(step["usable"])

    def test_sequential_single_steps_match_batch_state_machine(self):
        """Consistency check: stepping one minute at a time must produce
        exactly the same state sequence as dq_adapter's own batch call
        -- both call the identical real AlaradSafety.sensorStep, so any
        divergence would indicate a bug in how this module threads
        state forward, not a difference in engine behavior."""
        observations = (
            [{"ts": t, "value": 50.0} for t in range(5)]
            + [None] * 8  # long enough to pass through STALE into DISCONNECTED
            + [{"ts": t, "value": 50.0} for t in range(13, 18)]
        )
        batch_states = [s["state"] for s in run_sensor_state_machine(self.bridge, observations)]

        stepwise_states = []
        prev = new_sensor_state(self.bridge)
        for t, obs in enumerate(observations):
            reading = None if obs is None else obs["value"]
            step = sensor_step_once(self.bridge, prev, reading, t)
            stepwise_states.append(step["state"])
            prev = step["s"]

        self.assertEqual(batch_states, stepwise_states)

    def test_query_sensor_validity_trusted_for_trigger_only_when_healthy(self):
        prev = new_sensor_state(self.bridge)
        result = query_sensor_validity(self.bridge, prev, 50.0, 0)
        self.assertEqual(result.state, "HEALTHY")
        self.assertTrue(result.trusted_for_trigger)
        self.assertEqual(TRUSTED_FOR_TRIGGER, {"HEALTHY"})

    def test_query_sensor_validity_not_trusted_while_disconnected(self):
        prev = new_sensor_state(self.bridge)
        for t in range(10):
            result = query_sensor_validity(self.bridge, prev, None, t)
            prev = result.next_state_obj
        self.assertEqual(result.state, "DISCONNECTED")
        self.assertFalse(result.trusted_for_trigger)
        self.assertFalse(result.usable)


if __name__ == "__main__":
    unittest.main()
