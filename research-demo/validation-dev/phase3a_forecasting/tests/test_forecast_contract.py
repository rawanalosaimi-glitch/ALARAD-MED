"""
Verifies the frozen engine's forecasting API this adapter depends on is
present, callable, and behaves as documented -- the automatic
"stop and report" guard, same pattern as
phase2a_adapter/tests/test_engine_contract.py.
"""

from __future__ import annotations

import unittest

from phase2a_adapter.engine_bridge import EngineBridge
from phase3a_forecasting.forecast_contract import (
    ForecastContractError,
    verify_forecast_contract,
    verify_known_forecast_values,
)


class TestForecastContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = EngineBridge().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    def test_contract_verifies_against_the_real_engine(self):
        result = verify_forecast_contract(self.bridge)
        self.assertEqual(result["linearForecast"], "function")

    def test_known_forecast_values_match(self):
        verify_known_forecast_values(self.bridge)  # raises on mismatch

    def test_contract_failure_is_reported_not_swallowed(self):
        from phase3a_forecasting import forecast_contract as fc
        original = dict(fc.REQUIRED_BINDINGS)
        fc.REQUIRED_BINDINGS["thisFunctionDoesNotExist"] = "function"
        try:
            with self.assertRaises(ForecastContractError):
                verify_forecast_contract(self.bridge)
        finally:
            fc.REQUIRED_BINDINGS.clear()
            fc.REQUIRED_BINDINGS.update(original)

    def test_linear_forecast_always_returns_exactly_three_future_points(self):
        """Direct evidence for the horizon-mismatch finding documented in
        PHASE3A_LIMITATIONS.md section 1: regardless of input length, the
        real function hardcodes exactly 3 future points."""
        for n in (3, 4, 7, 10):
            points = list(range(n))  # 0,1,2,...,n-1 -- a perfect ramp
            result = self.bridge.evaluate("(p) => linearForecast(p)", points)
            self.assertEqual(len(result["next"]), 3, msg=f"n={n}")


if __name__ == "__main__":
    unittest.main()
