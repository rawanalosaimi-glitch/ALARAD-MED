"""
Live, per-minute runtime stepping for a worker's dose and sensor state
(closes PHASE3C_A_REVIEW_AGAINST_REVISION_3.md section 2 item 2: "the
live dose-update field is declared but never written"). Ties together
`sensor_validity.py` (per-minute validity queries) and `staffing.py`
(the mutable `WorkerProfile` fields they update) -- no dose or
sensor-state logic is reimplemented here; this module only sequences
calls to the real engine and the existing, already-tested dose formula.
"""

from __future__ import annotations

from phase1_simulator.units import MINUTE_H, dose_increment_mSv, is_valid_rate
from phase2a_adapter.engine_bridge import EngineBridge

from .sensor_validity import TRUSTED_FOR_TRIGGER, new_sensor_state, query_sensor_validity, sensor_step_batch
from .staffing import ASSIGNED, WorkerProfile


def initialize_worker_runtime(bridge: EngineBridge, worker: WorkerProfile) -> None:
    """Must be called once per worker before `advance_worker_one_minute`
    is called for the first time in a run -- sets the real engine's own
    initial sensor state (`AlaradSafety.newSensor()`), matching
    `dq_adapter.run_sensor_state_machine`'s own `prev = AlaradSafety.newSensor()`
    starting point exactly."""
    worker.sensor_state_obj = new_sensor_state(bridge)
    worker.sensor_state_label = worker.sensor_state_obj["state"]


def advance_worker_one_minute(bridge: EngineBridge, worker: WorkerProfile,
                               reading, t: int) -> None:
    """Advances exactly one minute for one worker:
    1. Steps the real sensor-state machine (`sensor_validity.query_sensor_validity`)
       -- never reimplemented, always the live engine call.
    2. Updates `worker.last_valid_rate_uSv_h`/`last_valid_rate_minute`
       only when this minute's state is `TRUSTED_FOR_TRIGGER` (HEALTHY)
       -- the conservative, explicit rule stated in `sensor_validity.py`,
       never a stale value silently carried forward.
    3. Accrues dose into `worker.cumulative_dose_mSv` using the existing,
       unmodified `Dose(mSv) = Rate(uSv/h) x Duration(h) / 1000` formula,
       for this minute's reading, **only if the worker is currently
       `ASSIGNED`** (not FREE/RESERVED/RESTING -- unassigned minutes
       attribute no dose, matching `dose_attribution.py`'s existing
       rule exactly) **and** the reading is `usable` per the engine's
       own sensor state (matching `phase1_simulator.dose`'s existing
       "invalid/missing reading contributes no dose" convention, not a
       new rule invented here).

    `reading` is `None` if no sample was received this minute (the
    engine's own `obs=null` case), otherwise the single current-minute
    rate in uSv/h.
    """
    if worker.sensor_state_obj is None:
        initialize_worker_runtime(bridge, worker)

    query = query_sensor_validity(bridge, worker.sensor_state_obj, reading, t)
    worker.sensor_state_obj = query.next_state_obj
    worker.sensor_state_label = query.state

    if query.state in TRUSTED_FOR_TRIGGER and reading is not None and is_valid_rate(reading):
        worker.last_valid_rate_uSv_h = reading
        worker.last_valid_rate_minute = t

    if worker.state == ASSIGNED and query.usable and reading is not None and is_valid_rate(reading):
        worker.cumulative_dose_mSv += dose_increment_mSv(reading, MINUTE_H)


def advance_workers_one_minute_batch(bridge: EngineBridge, worker_readings, t: int) -> None:
    """Same as `advance_worker_one_minute`, for several workers in one
    round trip -- matters at campaign scale, where stepping every
    concurrently-occupied room's assigned worker one call at a time
    would otherwise dominate runtime. `worker_readings` is an iterable
    of `(worker, reading)` pairs. Produces byte-identical results to
    calling `advance_worker_one_minute` once per pair (verified by
    `tests/test_runtime.py::test_batch_matches_sequential_single_calls`)."""
    pairs = list(worker_readings)
    for worker, _ in pairs:
        if worker.sensor_state_obj is None:
            initialize_worker_runtime(bridge, worker)

    items = [{"prev": worker.sensor_state_obj, "reading": reading, "t": t} for worker, reading in pairs]
    steps = sensor_step_batch(bridge, items)

    for (worker, reading), step in zip(pairs, steps):
        worker.sensor_state_obj = step["s"]
        worker.sensor_state_label = step["state"]

        if step["state"] in TRUSTED_FOR_TRIGGER and reading is not None and is_valid_rate(reading):
            worker.last_valid_rate_uSv_h = reading
            worker.last_valid_rate_minute = t

        if worker.state == ASSIGNED and step["usable"] and reading is not None and is_valid_rate(reading):
            worker.cumulative_dose_mSv += dose_increment_mSv(reading, MINUTE_H)
