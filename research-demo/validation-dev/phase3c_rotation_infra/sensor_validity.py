"""
Per-minute sensor-validity queries against the real, unmodified frozen
engine (closes PHASE3C_A_REVIEW_AGAINST_REVISION_3.md section 2 items
1/4: "no per-worker last-valid-reading field" and "no mechanism queries
sensor validity for a specific worker at a specific decision minute").

Reuses `AlaradSafety.newSensor`/`sensorStep` exactly as
`phase2a_adapter.dq_adapter.run_sensor_state_machine` does for a whole
pre-built sequence -- this module calls the same two real functions one
minute at a time instead, so a live run can query a specific worker's
validity at a specific minute without needing their whole future
sequence built in advance. No sensor-state classification logic is
reimplemented; every state comes from the real engine.

**Trigger-trust vs. dose-accrual are deliberately different gates,
stated once here because both are used elsewhere in this package:**
- `usable` (returned by `sensorStep`) governs *dose accrual* — true for
  HEALTHY, RECOVERING, and SUSPECTED_FROZEN alike, matching the existing
  "a repeating-but-fresh reading still contributes dose, flagged, not
  dropped" convention already used by `phase1_simulator.dose` and
  `phase3c_rotation_infra.dose_attribution`.
- `TRUSTED_FOR_TRIGGER` (this module's own, explicit, conservative
  choice) governs whether a reading may drive `PHASE3B_ROTATION_
  ALGORITHM_DESIGN.md` section 3a's trigger clauses (b)/(c) at all —
  **HEALTHY only**. RECOVERING and SUSPECTED_FROZEN readings are fresh
  enough to accrue dose, but Revision 3's fail-safe rule ("never
  substituting a stale or uncertain value for the purpose of a
  safety-relevant trigger decision") is read here as excluding them too
  — a conservative, explicit choice, not an oversight, flagged for
  review like every other new provisional design decision this round
  (see PHASE3C_B_READINESS_CHECKLIST.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from phase2a_adapter.dq_adapter import DQ_FLAGGED_STATES
from phase2a_adapter.engine_bridge import EngineBridge

TRUSTED_FOR_TRIGGER = {"HEALTHY"}

# Re-exported, not redefined, so this module and dq_adapter never drift
# apart on what counts as "flagged" for escalation purposes.
FLAGGED_STATES = DQ_FLAGGED_STATES


def new_sensor_state(bridge: EngineBridge) -> Dict[str, Any]:
    """The real engine's own initial sensor state, via `AlaradSafety.newSensor()`."""
    return bridge.evaluate("() => AlaradSafety.newSensor()")


def sensor_step_once(bridge: EngineBridge, prev_state_obj: Dict[str, Any],
                      reading: Optional[float], t: int) -> Dict[str, Any]:
    """One real `AlaradSafety.sensorStep` call for one worker, one
    minute. `reading=None` means no sample was received this minute
    (the engine's own `obs=null` case). Returns the engine's own
    `{s, state, usable, uncertain, code, age}` verbatim."""
    obs = None if reading is None else {"ts": t, "value": reading}
    return bridge.evaluate(
        "(args) => AlaradSafety.sensorStep(args.prev, args.obs, args.t, null)",
        {"prev": prev_state_obj, "obs": obs, "t": t},
    )


def sensor_step_batch(bridge: EngineBridge, items: Any) -> Any:
    """Same as `sensor_step_once`, for many workers in one round trip --
    matters at campaign scale (one call per minute across all
    concurrently-occupied rooms, instead of one call per room per
    minute). `items` is a list of `{"prev", "reading", "t"}` dicts, in
    the same order as the returned list."""
    args = [{"prev": it["prev"], "obs": (None if it["reading"] is None else {"ts": it["t"], "value": it["reading"]}),
             "t": it["t"]} for it in items]
    return bridge.evaluate(
        "(items) => items.map(a => AlaradSafety.sensorStep(a.prev, a.obs, a.t, null))", args,
    )


@dataclass(frozen=True)
class SensorQueryResult:
    state: str
    usable: bool
    uncertain: bool
    trusted_for_trigger: bool
    next_state_obj: Dict[str, Any]


def query_sensor_validity(bridge: EngineBridge, prev_state_obj: Dict[str, Any],
                           reading: Optional[float], t: int) -> SensorQueryResult:
    """The per-worker, per-minute validity query
    `PHASE3C_A_REVIEW_AGAINST_REVISION_3.md` section 2 item 4 names as
    missing. Wraps `sensor_step_once` with the `trusted_for_trigger`
    classification (this module's own, explicit rule above) alongside
    the engine's own raw fields, so a caller never has to re-derive it."""
    step = sensor_step_once(bridge, prev_state_obj, reading, t)
    return SensorQueryResult(
        state=step["state"],
        usable=step["usable"],
        uncertain=step["uncertain"],
        trusted_for_trigger=step["state"] in TRUSTED_FOR_TRIGGER,
        next_state_obj=step["s"],
    )
