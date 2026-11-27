"""
Dose attribution over the two-layer exposure/assignment model (task 2,
part 3; PHASE3B_ROTATION_ALGORITHM_DESIGN.md section 5a point 3, section
7a's dose-accounting definitions).

Reads the exposure layer; never mutates it. Reuses
phase1_simulator.units.dose_increment_mSv / MINUTE_H for the dose
formula -- not re-derived.

Deliberately fails loudly (raises) rather than silently summing when the
same worker is attributed dose from two different rooms at the same
minute -- an exclusivity violation that assignment.py's batch
reservation is supposed to make impossible, and this module independently
checks for rather than assuming (the same "never trust a structural
argument alone" discipline already applied in assignment.py).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from phase1_simulator.units import MINUTE_H, dose_increment_mSv

from .exposure_layer import AssignmentSlot


class AttributionConflictError(ValueError):
    pass


def build_full_occupancy_assignment(slots_by_room: Dict[str, List[AssignmentSlot]],
                                     initial_worker_by_room: Dict[str, str],
                                     shift_minutes: int) -> Dict[str, List[Optional[str]]]:
    """The "no-rotation" assignment layer (ROTATION_RECOMMENDER_DESIGN_SPEC.md
    section 4.1): each room's originally-scheduled worker occupies every
    minute of the whole shift, with no gap."""
    return {room: [initial_worker_by_room[room]] * shift_minutes for room in slots_by_room}


def apply_rotation(assignment_by_room: Dict[str, List[Optional[str]]], room: str,
                    t_effective: int, new_worker_id: str) -> None:
    """Applies a COMPLETED swap to an assignment layer in place, from
    t_effective (inclusive) to the end of that room's schedule -- the
    outgoing worker's attribution for minutes before t_effective is left
    untouched, matching section 3d's "outgoing worker occupies through
    the last minute before T_effective; incoming worker from T_effective
    onward."""
    series = assignment_by_room[room]
    for t in range(t_effective, len(series)):
        series[t] = new_worker_id


def attribute_dose(slots_by_room: Dict[str, List[AssignmentSlot]],
                    exposure_by_slot: Dict[str, List[float]],
                    assignment_by_room: Dict[str, List[Optional[str]]],
                    shift_minutes: int) -> Dict[str, List[float]]:
    """Per-worker attributed dose-RATE series over the full shift (0.0
    where a worker is not assigned at a given minute). Raises
    AttributionConflictError if the same worker is claimed by two
    different rooms at the same minute -- see module docstring."""
    worker_series: Dict[str, List[float]] = {}
    claimed_by: Dict[Tuple[str, int], str] = {}
    for room, assigned in assignment_by_room.items():
        for slot in slots_by_room[room]:
            series = exposure_by_slot[slot.slot_id]
            for offset, t in enumerate(range(slot.start_minute, slot.end_minute)):
                worker_id = assigned[t]
                if worker_id is None:
                    continue
                key = (worker_id, t)
                if key in claimed_by:
                    raise AttributionConflictError(
                        f"worker {worker_id!r} attributed dose from both "
                        f"room {claimed_by[key]!r} and {room!r} at minute {t}"
                    )
                claimed_by[key] = room
                if worker_id not in worker_series:
                    worker_series[worker_id] = [0.0] * shift_minutes
                worker_series[worker_id][t] = series[offset]
    return worker_series


def cumulative_dose_per_worker(attributed_rates: Dict[str, List[float]]) -> Dict[str, float]:
    """Individual cumulative dose (section 7a.1), via the existing,
    unmodified dose-integration rule."""
    return {
        worker_id: sum(dose_increment_mSv(rate, MINUTE_H) for rate in series)
        for worker_id, series in attributed_rates.items()
    }


def collective_dose_mSv(cumulative_per_worker: Dict[str, float]) -> float:
    """Collective dose (section 7a.3): sum across the entire roster
    present in the run. Explicitly a simplified, project-internal
    quantity -- not the formal ICRP collective-effective-dose concept."""
    return sum(cumulative_per_worker.values())


def max_individual_dose_mSv(cumulative_per_worker: Dict[str, float]) -> float:
    """Maximum individual dose (section 7a.2), at the point this is
    called -- a caller sampling this at multiple times across the shift
    gets the trajectory-level measure; this function itself is a single
    snapshot."""
    return max(cumulative_per_worker.values()) if cumulative_per_worker else 0.0


def total_exposure_mSv(slots_by_room: Dict[str, List[AssignmentSlot]],
                        exposure_by_slot: Dict[str, List[float]]) -> float:
    """The reference total: sum of dose_increment_mSv over every slot-
    minute's exposure value, regardless of assignment. Under full,
    gapless occupancy (every slot-minute assigned to exactly one
    worker), collective_dose_mSv(...) must equal this value exactly --
    the section 7b invariant, checked directly (not assumed) by
    test_dose_attribution.py's conservation test."""
    total = 0.0
    for slots in slots_by_room.values():
        for slot in slots:
            for rate in exposure_by_slot[slot.slot_id]:
                total += dose_increment_mSv(rate, MINUTE_H)
    return total
