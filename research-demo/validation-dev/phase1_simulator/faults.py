"""
Sensor/data-quality fault injection for the Phase 1 simulator.

Reimplements, from the specification already documented in
Ground_Truth_Scenarios_S1-S13.md ("Fault semantics implemented in
faultAt()/runWorker()"), the four fault kinds exercised by the frozen
v1.2.3 engine -- as an independent, standalone implementation for this
research simulator. Nothing here reads or copies code from the frozen
release.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

Observation = Optional[float]


@dataclass(frozen=True)
class FaultWindow:
    kind: str  # "missing" | "invalid" | "frozen" | "delayed"
    start: int
    end: int  # exclusive
    params: Dict = field(default_factory=dict)


def apply_faults(noisy_series: List[float],
                  fault_windows: List[FaultWindow]) -> List[Observation]:
    """Returns the *observed* stream after applying fault windows.

    - missing: observation is None for [start, end).
    - invalid: observation is a non-physical value (NaN by default, or an
      explicit value from params["invalid_value"]) at every minute in
      [start, end), or only at params["invalid_minutes"] if given.
    - frozen: observation repeats the exact value from one minute before
      the window, for the whole window.
    - delayed: no observation for params["lag"] minutes at the start of
      the window, then observations carry the value from `lag` minutes
      earlier (a stale, out-of-date reading) for the rest of the window.
    """
    observed: List[Observation] = list(noisy_series)
    for f in fault_windows:
        if f.kind == "missing":
            for t in range(f.start, min(f.end, len(observed))):
                observed[t] = None
        elif f.kind == "invalid":
            invalid_minutes = f.params.get(
                "invalid_minutes", list(range(f.start, f.end)))
            invalid_value = f.params.get("invalid_value", float("nan"))
            for t in invalid_minutes:
                if 0 <= t < len(observed):
                    observed[t] = invalid_value
        elif f.kind == "frozen":
            freeze_value = noisy_series[max(0, f.start - 1)]
            for t in range(f.start, min(f.end, len(observed))):
                observed[t] = freeze_value
        elif f.kind == "delayed":
            lag = int(f.params.get("lag", 1))
            for t in range(f.start, min(f.start + lag, f.end, len(observed))):
                observed[t] = None
            for t in range(f.start + lag, min(f.end, len(observed))):
                src = max(0, t - lag)
                observed[t] = noisy_series[src]
        else:
            raise ValueError(f"Unknown fault kind: {f.kind!r}")
    return observed
