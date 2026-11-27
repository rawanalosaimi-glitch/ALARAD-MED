"""
Controlled-scenario construction for the final supplementary validation
round. Reuses the real `WorkerProfile`/`AssignmentSlot` classes and the
real exposure-generation helpers (`phase1_simulator.patterns.flat`/
`apply_measurement_noise`) exactly as `exposure_layer.py` already does
for Phase 3C-A -- no staffing, trigger, selection, scheduling, or
dose-attribution logic is reimplemented anywhere in this package. The
ONLY thing this module controls that the main campaign leaves to random
sampling (`staffing.generate_roster`, `campaign_scenarios.build_campaign_run`)
is the INPUT data: exactly which workers exist, their exact credentials,
exact starting accumulated dose, exact availability/duty-limit state,
and the exact exposure trajectory for each room-track. Every downstream
decision (trigger evaluation, candidate ranking, atomic reservation,
handoff timing, dose accrual, sensor-state stepping) is made by the
real, unmodified `policies.py`/`assignment.py`/`scheduling.py`/
`runtime.py`/`dose_attribution.py` functions, run through the real
`simulation.run_policy_on_run` orchestrator unchanged.

This module is NEW code for the supplementary round; it does not touch
any file the original Phase 3C-B campaign used, and the original
campaign's own `phase3c_campaign_output/` is never read or written by
anything here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from phase1_simulator import patterns
from phase1_simulator.rng import make_rng

from ..exposure_layer import AssignmentSlot
from ..staffing import FREE, RESTING, WorkerProfile

DEFAULT_ROOM = "Cath Lab 1"
DEFAULT_PROCEDURE_CLASS = "interventional_cath_lab"
DEFAULT_PROC_MULT = 1.0


@dataclass(frozen=True)
class WorkerSpec:
    """One worker's exact, hand-chosen starting condition for a
    controlled scenario -- every field maps 1:1 onto a real
    `WorkerProfile` field; nothing here is a new concept."""
    worker_id: str
    credentialed_rooms: Tuple[str, ...]
    credentialed_procedure_classes: Tuple[str, ...]
    cumulative_dose_mSv: float = 0.0
    max_dose_per_shift_mSv: float = 5.0
    min_rest_between_assignments_minutes: int = 10
    max_rotations_per_shift: int = 3
    rotations_so_far: int = 0
    last_rotation_out_minute: Optional[int] = None
    state: str = FREE
    availability_windows: Optional[List[Tuple[int, int]]] = None  # default: full shift
    # Only the current room OCCUPANT's sensor is stepped each minute
    # (simulation.py's main loop only advances `roster[occupant[r]]`) --
    # an idle candidate who has never yet occupied a room would
    # therefore always have `last_valid_rate_uSv_h=None`, making the
    # projected-dose duty-limit check (assignment.py's `intended_minutes`
    # branch) untestable for a "fresh" candidate. Setting this directly
    # constructs the controlled INITIAL CONDITION "this candidate was
    # exposed earlier and is now idle with a known last reading" --
    # exactly what Experiment C's sub-case C4 needs -- without
    # reimplementing or bypassing any decision logic.
    last_valid_rate_uSv_h: Optional[float] = None


def build_worker(spec: WorkerSpec, shift_minutes: int) -> WorkerProfile:
    """Materializes a `WorkerSpec` into the real `WorkerProfile`
    dataclass -- the exact same class `staffing.generate_roster`
    produces, just with every field set explicitly instead of sampled."""
    windows = spec.availability_windows if spec.availability_windows is not None else [(0, shift_minutes)]
    return WorkerProfile(
        worker_id=spec.worker_id,
        credentialed_rooms=frozenset(spec.credentialed_rooms),
        credentialed_procedure_classes=frozenset(spec.credentialed_procedure_classes),
        max_dose_per_shift_mSv=spec.max_dose_per_shift_mSv,
        min_rest_between_assignments_minutes=spec.min_rest_between_assignments_minutes,
        max_rotations_per_shift=spec.max_rotations_per_shift,
        availability_windows=windows,
        state=spec.state,
        rotations_so_far=spec.rotations_so_far,
        cumulative_dose_mSv=spec.cumulative_dose_mSv,
        last_rotation_out_minute=spec.last_rotation_out_minute,
        last_valid_rate_uSv_h=spec.last_valid_rate_uSv_h,
    )


def build_roster(specs: List[WorkerSpec], shift_minutes: int) -> Dict[str, WorkerProfile]:
    return {s.worker_id: build_worker(s, shift_minutes) for s in specs}


def constant_rate_series(seed: int, slot_id: str, duration_minutes: int,
                          rate_uSv_h: float, noise_fraction: float = 0.02) -> List[float]:
    """A deterministic (given seed+slot_id), controlled exposure series:
    the real `patterns.flat` + `patterns.apply_measurement_noise`
    (Phase 3C-A's own synthetic-exposure helpers, unchanged), not a new
    noise model. A small, explicit noise fraction keeps runs from being
    bit-for-bit identical across seeds (so seed-to-seed statistical
    replicates are genuine) while leaving the controlled *structural*
    condition (which workers are eligible, their relative dose ordering)
    fixed by construction, not by chance."""
    true_series = patterns.flat(duration_minutes, rate_uSv_h)
    rng = make_rng(seed, "phase3c_supplementary_exposure", slot_id)
    return patterns.apply_measurement_noise(true_series, rng, noise_fraction)


def build_single_room_run(seed: int, shift_minutes: int, rate_uSv_h: float,
                           room: str = DEFAULT_ROOM, procedure_class: str = DEFAULT_PROCEDURE_CLASS,
                           proc_mult: float = DEFAULT_PROC_MULT,
                           n_slots: int = 1, noise_fraction: float = 0.02,
                           boundaries: Optional[List[int]] = None) -> Dict:
    """A one-room, controlled `campaign_run`-shaped dict -- the exact
    shape `simulation.run_policy_on_run` already consumes
    (`slots_by_room`, `exposure_by_slot`, `observations_by_room`,
    `shift_minutes`), built by hand instead of via
    `campaign_scenarios.build_campaign_run`'s randomized Phase-1
    archetypes, so the procedure-boundary timing (which drives when
    CGDTR's trigger is even checked) is exactly controlled rather than
    randomly spaced. `n_slots` evenly divides the shift into that many
    equal procedure-boundary segments (all the same procedure_class/
    proc_mult, for this experiment's purposes)."""
    if boundaries is None:
        boundary_step = max(1, shift_minutes // n_slots)
        boundaries = sorted(set([0] + [min(shift_minutes, i * boundary_step) for i in range(1, n_slots + 1)] + [shift_minutes]))
    else:
        boundaries = sorted(set(boundaries) | {0, shift_minutes})
    slots: List[AssignmentSlot] = []
    exposure_by_slot: Dict[str, List[float]] = {}
    observations_by_room: Dict[str, List[Optional[Dict]]] = {room: []}
    for i in range(len(boundaries) - 1):
        start, end = boundaries[i], boundaries[i + 1]
        slot_id = f"{room}-{i}"
        slots.append(AssignmentSlot(
            slot_id=slot_id, room=room, procedure_class=procedure_class,
            start_minute=start, end_minute=end, proc_mult=proc_mult,
            baseline_rate_uSv_h=rate_uSv_h,
        ))
        series = constant_rate_series(seed, slot_id, end - start, rate_uSv_h, noise_fraction)
        exposure_by_slot[slot_id] = series
        for v in series:
            observations_by_room[room].append({"ts": None, "value": v})  # ts filled in by caller if needed

    # ts defaults to the current minute index (matches the live
    # orchestrator's own actual behavior -- see
    # ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md Experiment B finding on
    # delayed-fault timestamp handling for why this matters).
    for t, obs in enumerate(observations_by_room[room]):
        obs["ts"] = t

    return {
        "slots_by_room": {room: slots},
        "exposure_by_slot": exposure_by_slot,
        "observations_by_room": observations_by_room,
        "shift_minutes": shift_minutes,
        "archetype": "supplementary_controlled",
        "seed": seed,
    }


def inject_fault(campaign_run: Dict, room: str, start_minute: int, end_minute: int,
                  kind: str, frozen_value: Optional[float] = None,
                  claimed_lag_minutes: Optional[int] = None) -> None:
    """Mutates `campaign_run["observations_by_room"][room]` in place to
    inject one of the four fault kinds Experiment B requires, over
    [start_minute, end_minute). This is INPUT-DATA construction only --
    it does not touch `sensorStep`, `AlaradSafety`, or any engine logic;
    the real engine's own sensor-state machine (called unchanged via
    `runtime.py`/`sensor_validity.py`) is what classifies the resulting
    observation sequence into HEALTHY/STALE/DISCONNECTED/INVALID/
    SUSPECTED_FROZEN -- never decided here.

    kind:
      "missing"  -> obs = None for every minute in the window (no sample).
      "invalid"  -> obs = {"ts": t, "value": -1.0} (a non-physical,
                    out-of-range reading; the engine's own validReading
                    check is what classifies this, not this function).
      "frozen"   -> obs = {"ts": t, "value": frozen_value} for every
                    minute (an unchanging, repeated-value reading --
                    the engine's own repeat-detection is what classifies
                    this as SUSPECTED_FROZEN, not this function).
      "delayed"  -> obs = {"ts": t - claimed_lag_minutes, "value": v}
                    (the *claimed* timestamp is stale by
                    claimed_lag_minutes, exactly matching
                    phase2a_adapter.dq_adapter.build_observations's own
                    "delayed fault" reconstruction for the minutes it
                    applies to) -- kept for use with
                    `sensor_validity.sensor_step_once` directly (which
                    DOES read a caller-supplied `ts`); see the
                    Experiment B finding about whether the live
                    orchestrator's own per-minute loop actually passes
                    this claimed `ts` through (it does not -- it only
                    ever reads `obs["value"]`, see `simulation.py`).
    """
    obs_list = campaign_run["observations_by_room"][room]
    # For "frozen," capture ONE value from the window's first minute
    # ONCE, before the loop, and repeat that SAME value every minute --
    # otherwise each minute would just re-read its own already-different
    # noisy value back onto itself, a no-op that never actually produces
    # a repeated-value reading for the engine's own repeat-detection to
    # classify as SUSPECTED_FROZEN.
    frozen_v = frozen_value
    if kind == "frozen" and frozen_v is None:
        first = obs_list[start_minute] if start_minute < len(obs_list) else None
        frozen_v = first["value"] if first else 50.0
    for t in range(start_minute, min(end_minute, len(obs_list))):
        if kind == "missing":
            obs_list[t] = None
        elif kind == "invalid":
            obs_list[t] = {"ts": t, "value": -1.0}
        elif kind == "frozen":
            obs_list[t] = {"ts": t, "value": frozen_v}
        elif kind == "delayed":
            lag = claimed_lag_minutes if claimed_lag_minutes is not None else 5
            v = obs_list[t]["value"] if obs_list[t] else 50.0
            obs_list[t] = {"ts": max(0, t - lag), "value": v}
        else:
            raise ValueError(f"unknown fault kind: {kind!r}")
        # also zero the dose-ready exposure_by_slot value for "missing"/"invalid"
        # minutes, matching the real campaign's own "invalid/missing reading
        # contributes no dose" convention (campaign_scenarios.py's own rule) --
        # exposure_by_slot is keyed by slot_id, not room, so find the owning slot.
    if kind in ("missing", "invalid"):
        for slot in campaign_run["slots_by_room"][room]:
            for t in range(max(start_minute, slot.start_minute), min(end_minute, slot.end_minute)):
                idx = t - slot.start_minute
                series = campaign_run["exposure_by_slot"][slot.slot_id]
                if 0 <= idx < len(series):
                    series[idx] = 0.0
