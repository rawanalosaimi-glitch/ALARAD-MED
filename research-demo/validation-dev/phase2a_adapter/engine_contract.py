"""
The explicit contract this adapter depends on from the frozen v1.2.3
engine, plus a verifier that checks it is actually present before any
evaluation runs.

This operationalizes the Phase 2A restriction "if direct integration is
not possible, stop and report the technical limitation before proceeding"
as an automatic, re-checkable guard rather than a one-time manual finding:
if a future copy of the release renames or removes one of these bindings,
`verify_contract` raises `EngineContractError` naming every mismatch,
instead of some other part of the adapter silently falling back to a
reimplementation.

Every name below, and the fact that each one is directly callable via
page.evaluate() against the unmodified frozen file, was empirically
verified in this session before any adapter code was written (not
assumed from reading the source alone).
"""

from __future__ import annotations

from typing import Dict

from .engine_bridge import EngineBridge, EngineBridgeError

REQUIRED_BINDINGS: Dict[str, str] = {
    "evaluateExposure": "function",
    "baselineRates": "object",
    "CONFIG": "object",
    "SimLab": "object",
    "SimLab.pure.validReading": "function",
    "SimLab.pure.buildEpisodes": "function",
    "SimLab.pure.matchEvents": "function",
    "SimLab.pure.metrics": "function",
    "AlaradSafety": "object",
    "AlaradSafety.sensorStep": "function",
    "AlaradSafety.workerStatus": "function",
    "AlaradSafety.validateValue": "function",
    "AlaradSafety.newSensor": "function",
}


class EngineContractError(EngineBridgeError):
    pass


def verify_contract(bridge: EngineBridge) -> Dict[str, str]:
    """Checks every REQUIRED_BINDINGS entry exists with the expected
    `typeof` in the live page. Returns the actual typeof results on
    success; raises EngineContractError naming every mismatch (not just
    the first one) on failure."""
    actual: Dict[str, str] = {}
    problems = []
    for name, expected in REQUIRED_BINDINGS.items():
        t = bridge.type_of(name)
        actual[name] = t
        if t != expected:
            problems.append(f"{name}: expected typeof {expected!r}, got {t!r}")
    if problems:
        raise EngineContractError(
            "Frozen engine contract check failed -- direct integration is "
            "not possible as this adapter is currently written. Problems:\n  "
            + "\n  ".join(problems)
        )
    return actual


def snapshot_engine_constants(bridge: EngineBridge) -> Dict[str, Dict]:
    """Reads the engine's own baselineRates and CONFIG at verification
    time. Used by detection_adapter's rescaling logic, and recorded in
    evaluation output so every result is traceable to the exact constants
    that were actually read from the live engine, not assumed."""
    return {
        "baselineRates": bridge.evaluate("baselineRates"),
        "CONFIG": bridge.evaluate("CONFIG"),
    }
