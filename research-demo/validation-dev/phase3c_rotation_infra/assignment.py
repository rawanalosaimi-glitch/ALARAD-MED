"""
Worker-exclusivity state machine and atomic batch reservation (task 3;
PHASE3B_ROTATION_ALGORITHM_DESIGN.md section 3g, section 8a-ext).

Deliberately policy-agnostic: this module never decides WHICH worker a
room should want, or WHEN a rotation should be proposed (that is the
CGDTR trigger/selection logic, explicitly not implemented this round).
It only resolves, deterministically and exclusively, a set of already-
ranked `RotationRequest`s supplied by the caller (a test, or a future
policy module) at the same decision point.

**Duty-limit checking (section 3i, closes
PHASE3C_A_REVIEW_AGAINST_REVISION_3.md section 2 item 3):** `batch_resolve`
now accepts an optional `intended_assignment_minutes_by_room` map. When
given, a candidate projected (via `dose_quantities.projected_shift_total_dose_mSv`)
to reach their own `max_dose_per_shift_mSv` before the end of the
intended assignment is excluded -- one more condition in the same
step-6 filter, never a separate mechanism. When omitted (every call
site that predates this check), behavior is byte-for-byte unchanged
from before this check existed, so Phase 3C-A's own 55 tests keep
passing without modification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .dose_quantities import projected_shift_total_dose_mSv
from .staffing import ASSIGNED, FREE, RESERVED, RESTING, WorkerProfile


@dataclass
class RotationRequest:
    room: str
    outgoing_worker_id: str
    candidate_order: List[str]  # already ranked by whatever policy supplied this


@dataclass
class ReservationOutcome:
    room: str
    status: str  # "RESERVED" | "INFEASIBLE"
    reserved_worker_id: Optional[str] = None
    reason: Optional[str] = None


def batch_resolve(requests: List[RotationRequest], roster: Dict[str, WorkerProfile],
                   t_decide: int, t_effective_by_room: Dict[str, int],
                   intended_assignment_minutes_by_room: Optional[Dict[str, int]] = None
                   ) -> List[ReservationOutcome]:
    """Section 3g steps 1-6: one deterministic pass, rooms processed in
    ascending room-name order, each picking the first still-eligible
    candidate and marking them RESERVED immediately -- before the next
    room in the same batch is processed -- so no two rooms can ever
    reserve the same worker.

    A candidate is excluded from a room's list (step 6) if: not FREE,
    currently RESTING at t_decide, at their rotation-burden cap
    (rotations_so_far >= max_rotations_per_shift), their own
    availability_windows do not cover the full
    [t_decide, t_effective_by_room[room]] interval, or -- new, section
    3i, only checked when `intended_assignment_minutes_by_room` is
    given for this room -- they are projected to exceed their own
    `max_dose_per_shift_mSv` before the end of the intended assignment.
    A candidate with no trusted reading yet (`projected_shift_total_dose_mSv`
    returns `None`) is never excluded on this ground -- undefined is not
    "over limit," per this project's established "undefined is reported,
    never silently treated as a failure" discipline.
    """
    outcomes: List[ReservationOutcome] = []
    for req in sorted(requests, key=lambda r: r.room):
        t_eff = t_effective_by_room.get(req.room)
        intended_minutes = (intended_assignment_minutes_by_room or {}).get(req.room)
        chosen: Optional[WorkerProfile] = None
        for cand_id in req.candidate_order:
            w = roster.get(cand_id)
            if w is None:
                continue
            if w.state != FREE:
                continue
            if w.is_resting_at(t_decide):
                continue
            if w.rotations_so_far >= w.max_rotations_per_shift:
                continue
            if t_eff is not None and not w.is_within_availability_interval(t_decide, t_eff):
                continue
            if intended_minutes is not None:
                projected = projected_shift_total_dose_mSv(w, intended_minutes / 60.0)
                if projected is not None and projected >= w.max_dose_per_shift_mSv:
                    continue
            chosen = w
            break
        if chosen is None:
            outcomes.append(ReservationOutcome(
                room=req.room, status="INFEASIBLE",
                reason="no_eligible_candidate_free_through_interval"))
            continue
        chosen.state = RESERVED
        chosen.reserved_for_room = req.room
        outcomes.append(ReservationOutcome(
            room=req.room, status="RESERVED", reserved_worker_id=chosen.worker_id))
    return outcomes


def complete_reservation(worker: WorkerProfile) -> None:
    """RESERVED -> ASSIGNED (section 8a-ext)."""
    worker.state = ASSIGNED
    worker.reserved_for_room = None


def release_reservation(worker: WorkerProfile, to_resting: bool) -> None:
    """RESERVED -> FREE, or RESTING if the release coincides with a
    min-rest obligation from a *different*, earlier rotation-out
    (section 8a-ext: "FREE, or RESTING if min_rest applies")."""
    worker.reserved_for_room = None
    worker.state = RESTING if to_resting else FREE


def mark_rotated_out(worker: WorkerProfile, t: int) -> None:
    """ASSIGNED -> RESTING: the outgoing worker's rotation cycle ends
    (section 8a-ext)."""
    worker.last_rotation_out_minute = t
    worker.rotations_so_far += 1
    worker.state = RESTING


def advance_resting_to_free(worker: WorkerProfile, t: int) -> None:
    """RESTING -> FREE once min_rest_between_assignments_minutes has
    elapsed (section 8a-ext). A no-op if not currently RESTING or not
    yet eligible."""
    if worker.state == RESTING and not worker.is_resting_at(t):
        worker.state = FREE


def no_double_reservation(outcomes: List[ReservationOutcome]) -> bool:
    """Structural check (never trust the batch algorithm's own argument
    alone, per this project's established discipline): no reserved
    worker_id appears more than once across a batch's outcomes."""
    reserved = [o.reserved_worker_id for o in outcomes if o.reserved_worker_id is not None]
    return len(reserved) == len(set(reserved))
