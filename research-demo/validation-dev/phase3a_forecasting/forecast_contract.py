"""
The explicit contract this forecasting adapter depends on from the
frozen v1.2.3 engine, and a verifier -- same discipline as
phase2a_adapter/engine_contract.py's "stop and report if integration is
not possible" guard, applied to the one additional global function this
package needs: `linearForecast`.
"""

from __future__ import annotations

from typing import Dict

from phase2a_adapter.engine_bridge import EngineBridge, EngineBridgeError

REQUIRED_BINDINGS: Dict[str, str] = {
    "linearForecast": "function",
    "SimLab.pure.validReading": "function",
}


class ForecastContractError(EngineBridgeError):
    pass


def verify_forecast_contract(bridge: EngineBridge) -> Dict[str, str]:
    actual: Dict[str, str] = {}
    problems = []
    for name, expected in REQUIRED_BINDINGS.items():
        t = bridge.type_of(name)
        actual[name] = t
        if t != expected:
            problems.append(f"{name}: expected typeof {expected!r}, got {t!r}")
    if problems:
        raise ForecastContractError(
            "Frozen engine forecasting contract check failed -- direct "
            "integration is not possible as this adapter is currently "
            "written. Problems:\n  " + "\n  ".join(problems)
        )
    return actual


def verify_known_forecast_values(bridge: EngineBridge) -> None:
    """Sanity-checks linearForecast's own documented behavior against two
    hand-computable cases, so a future change to the frozen release (or a
    wrong file being loaded) is caught immediately rather than silently
    producing wrong forecasts downstream."""
    flat = bridge.evaluate("(p) => linearForecast(p)", [50.0, 50.0, 50.0, 50.0])
    if flat["slope"] != 0 or flat["next"] != [50.0, 50.0, 50.0]:
        raise ForecastContractError(
            f"linearForecast on a flat series returned unexpected output: {flat}"
        )
    ramp = bridge.evaluate("(p) => linearForecast(p)", [10.0, 20.0, 30.0, 40.0])
    if ramp["slope"] != 10 or ramp["next"] != [50.0, 60.0, 70.0]:
        raise ForecastContractError(
            f"linearForecast on a known linear ramp returned unexpected output: {ramp}"
        )
