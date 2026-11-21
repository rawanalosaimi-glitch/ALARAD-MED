"""
Verifies the frozen engine's own API surface this adapter depends on is
actually present and callable -- the automatic "stop and report" guard
required by Phase 2A's restrictions.
"""

from __future__ import annotations

import unittest

from phase2a_adapter.engine_bridge import EngineBridge, verify_frozen_release_hash, FROZEN_RELEASE_PATH
from phase2a_adapter.engine_contract import verify_contract, snapshot_engine_constants, EngineContractError


class TestEngineContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = EngineBridge().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    def test_frozen_release_hash_matches_recorded_value(self):
        # Re-verified independently of EngineBridge's own constructor check.
        actual = verify_frozen_release_hash(FROZEN_RELEASE_PATH)
        self.assertEqual(
            actual, "92e897dd0ff1738f083df829b53f7f46377e042b7019bb9776232792261182ee")

    def test_contract_verifies_against_the_real_engine(self):
        result = verify_contract(self.bridge)
        self.assertEqual(result["evaluateExposure"], "function")
        self.assertEqual(result["SimLab.pure.buildEpisodes"], "function")
        self.assertEqual(result["AlaradSafety.sensorStep"], "function")

    def test_snapshot_engine_constants_matches_known_values(self):
        # These exact values were read directly from the frozen source
        # during this session's investigation -- re-checked here so a
        # silent drift in either would be caught by this test.
        snap = snapshot_engine_constants(self.bridge)
        self.assertEqual(snap["baselineRates"]["Cath Lab 1"], 90)
        self.assertEqual(snap["baselineRates"]["Fluoroscopy Suite"], 70)
        self.assertEqual(snap["CONFIG"]["devElevated"], 0.5)
        self.assertEqual(snap["CONFIG"]["devCritical"], 1.5)

    def test_contract_failure_is_reported_not_swallowed(self):
        # A deliberately wrong expectation must raise, not pass silently.
        from phase2a_adapter import engine_contract as ec
        original = dict(ec.REQUIRED_BINDINGS)
        ec.REQUIRED_BINDINGS["thisFunctionDoesNotExist"] = "function"
        try:
            with self.assertRaises(EngineContractError):
                verify_contract(self.bridge)
        finally:
            ec.REQUIRED_BINDINGS.clear()
            ec.REQUIRED_BINDINGS.update(original)


if __name__ == "__main__":
    unittest.main()
