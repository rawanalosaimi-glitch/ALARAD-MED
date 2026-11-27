"""
The three separately-named, separately-owned dose quantities specified
in `PHASE3B_ROTATION_ALGORITHM_DESIGN.md` section 3a (Revision 3) --
never collapsed into one number, never compared against the wrong
threshold. This module is the single place all three are computed, so
nothing else in this package re-derives any of them independently.

- `WorkerAccumulatedShiftDose`: this project's own genuine running
  total (`WorkerProfile.cumulative_dose_mSv`, kept live by
  `phase3c_rotation_infra.runtime`). A plain accessor here, named to
  match the design document exactly.
- `EngineProjectedTaskDose`: the frozen engine's own real quantity
  (its source calls it `cumulativeDose`, a misnomer repeated nowhere in
  this project's own code or documentation from Revision 3 onward) --
  obtained by calling the real, unmodified `evaluateExposure()` and
  reading its own `.cumulativeDose` field directly, never re-derived in
  Python. Compared only against `CONFIG.doseElevated`/`doseCritical`.
- `ProjectedShiftTotalDose`: a new, adapter-only quantity (analogous in
  kind to Phase 3A's `forecast_cumulative_dose` -- also new, adapter-
  only, never an engine capability): accrued dose plus a projected
  increment from the worker's last trusted reading. Compared only
  against the worker's own `max_dose_per_shift_mSv` duty limit.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from phase1_simulator.units import dose_increment_mSv
from phase2a_adapter.engine_bridge import EngineBridge

from .staffing import WorkerProfile

ENGINE_PROJECTION_HORIZON_MINUTES = 30  # the frozen engine's own fixed `dur` at every real call site (HORIZON_MIN/HORIZON = 30); reused, not re-chosen


def worker_accumulated_shift_dose_mSv(worker: WorkerProfile) -> float:
    """WorkerAccumulatedShiftDose(W, t): the genuine running total this
    project already maintains live on `WorkerProfile.cumulative_dose_mSv`
    (see `phase3c_rotation_infra.runtime`). A named accessor, not a new
    computation."""
    return worker.cumulative_dose_mSv


def engine_projected_task_dose_mSv(bridge: EngineBridge, room: str, proc_mult: float,
                                    rate_uSv_h: float, mode: str = "personal",
                                    dur_minutes: int = ENGINE_PROJECTION_HORIZON_MINUTES
                                    ) -> Optional[float]:
    """EngineProjectedTaskDose(W, t): calls the real, unmodified
    `evaluateExposure()` and returns its own `.cumulativeDose` field
    directly -- the engine's actual, memoryless, single-reading
    projection (PHASE3C_A_DOSE_THRESHOLD_SEMANTIC_AUDIT.md). Returns
    `None` if the engine itself rejects the input as invalid
    (`result.invalid`) -- never substituting a computed value for a
    rejected reading."""
    result = bridge.evaluate(
        "(args) => evaluateExposure(args)",
        {"room": room, "procMult": proc_mult, "rate": rate_uSv_h, "dur": dur_minutes,
         "dist": 1, "refDist": 1, "shield": 1, "mode": mode},
    )
    if result.get("invalid"):
        return None
    return result["cumulativeDose"]


def engine_projected_task_dose_mSv_batch(bridge: EngineBridge, items: Sequence[Dict[str, Any]],
                                          dur_minutes: int = ENGINE_PROJECTION_HORIZON_MINUTES
                                          ) -> List[Optional[float]]:
    """Same as `engine_projected_task_dose_mSv`, for many workers in one
    `bridge.evaluate` round trip (one real browser call instead of one
    per worker) -- matters at campaign scale, where a per-worker call
    would otherwise dominate runtime. `items` is a list of
    `{"room", "procMult", "rate", "mode"}` dicts, one per worker, in the
    same order as the returned list. No arithmetic is duplicated in
    Python: the engine's own `evaluateExposure()` is called once per
    item, inside the single round trip."""
    args = [{**item, "dur": dur_minutes, "dist": 1, "refDist": 1, "shield": 1,
             "mode": item.get("mode", "personal")} for item in items]
    results = bridge.evaluate(
        "(items) => items.map(a => evaluateExposure(a))", args,
    )
    return [None if r.get("invalid") else r["cumulativeDose"] for r in results]


def projected_shift_total_dose_mSv(worker: WorkerProfile, horizon_hours: float) -> Optional[float]:
    """ProjectedShiftTotalDose(W, t, h): WorkerAccumulatedShiftDose(W, t)
    plus the increment `worker.last_valid_rate_uSv_h` held constant over
    `horizon_hours`. Returns `None` (undefined, never a silently-
    substituted value) if no trusted reading exists yet --
    `worker.last_valid_rate_uSv_h` is only ever set from a `HEALTHY`-
    classified minute (`phase3c_rotation_infra.sensor_validity.
    TRUSTED_FOR_TRIGGER`; see `phase3c_rotation_infra.runtime`), so this
    function never has to re-check sensor state itself -- it trusts the
    field's own invariant."""
    if worker.last_valid_rate_uSv_h is None:
        return None
    increment_mSv = dose_increment_mSv(worker.last_valid_rate_uSv_h, horizon_hours)
    return worker_accumulated_shift_dose_mSv(worker) + increment_mSv
