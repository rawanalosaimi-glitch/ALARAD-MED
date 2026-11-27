"""
Procedure-boundary and handoff scheduling (task 4;
PHASE3B_ROTATION_ALGORITHM_DESIGN.md section 3d's explicit event
timeline, section 8/8a-ext's state machine).

Pure, deterministic functions over a scripted timeline (boundaries,
whether an incident is open at a given minute, whether the reserved
candidate's eligibility still holds at a given minute) -- this phase
builds and tests the scheduling MACHINERY, not a live continuous-time
simulation loop. A future phase that runs this against a real evolving
roster would call these same functions once per decision point.

T_decide -> T_ready -> T_effective, exactly as specified: T_effective is
always the smallest scheduled boundary at or after T_ready, so a swap
can never take effect mid-procedure except via the one sanctioned
emergency-override path, which this module logs distinctly and never
invokes on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

PROPOSED = "PROPOSED"
PENDING = "PENDING"
HELD = "HELD"
COMPLETED = "COMPLETED"
ABORTED = "ABORTED"
INFEASIBLE = "INFEASIBLE"


@dataclass
class RotationAttempt:
    room: str
    outgoing_worker_id: str
    reserved_worker_id: Optional[str]
    t_decide: int
    t_ready: Optional[int] = None
    t_effective: Optional[int] = None
    status: str = PROPOSED
    reason: Optional[str] = None
    override_used: bool = False
    audit_log: List[Dict] = field(default_factory=list)

    def log(self, event: str, **fields) -> None:
        self.audit_log.append({"event": event, **fields})


def compute_t_ready(t_decide: int, min_handoff_duration_minutes: int) -> int:
    """T_ready = T_decide + min_handoff_duration_minutes -- the earliest
    the handoff could be physically done (section 3d)."""
    return t_decide + min_handoff_duration_minutes


def compute_t_effective(t_ready: int, boundaries: List[int], shift_minutes: int) -> Optional[int]:
    """The smallest scheduled boundary B_j such that B_j >= t_ready and
    B_j <= shift_minutes -- never an arbitrary mid-procedure minute.
    `boundaries` must include the shift-end boundary itself (section 3d's
    "shift end is itself always treated as a procedure boundary"); if
    the caller's boundary list omits it, this function adds it so a
    rotation is never spuriously starved of a landing point by an
    incomplete boundary list.

    Returns None if no such boundary exists (infeasible -- section 3d/4
    case 6, now defined precisely by this test)."""
    all_boundaries = set(boundaries)
    all_boundaries.add(shift_minutes)
    candidates = [b for b in all_boundaries if t_ready <= b <= shift_minutes]
    return min(candidates) if candidates else None


def start_attempt(room: str, outgoing_worker_id: str, reserved_worker_id: Optional[str],
                   t_decide: int, min_handoff_duration_minutes: int,
                   boundaries: List[int], shift_minutes: int) -> RotationAttempt:
    """Section 3d/3g: builds the attempt and computes T_ready/T_effective
    up front. `reserved_worker_id=None` means the batch reservation
    (assignment.batch_resolve) could not find an eligible candidate --
    the attempt starts life already INFEASIBLE, distinct from an attempt
    that becomes infeasible for lack of a boundary."""
    attempt = RotationAttempt(room=room, outgoing_worker_id=outgoing_worker_id,
                               reserved_worker_id=reserved_worker_id, t_decide=t_decide)
    if reserved_worker_id is None:
        attempt.status = INFEASIBLE
        attempt.reason = "no_eligible_candidate"
        attempt.log("infeasible", reason=attempt.reason)
        return attempt
    attempt.t_ready = compute_t_ready(t_decide, min_handoff_duration_minutes)
    attempt.t_effective = compute_t_effective(attempt.t_ready, boundaries, shift_minutes)
    if attempt.t_effective is None:
        attempt.status = INFEASIBLE
        attempt.reason = "no_boundary_at_or_after_t_ready_before_shift_end"
        attempt.log("infeasible", reason=attempt.reason)
        return attempt
    attempt.status = PENDING
    attempt.log("pending", t_ready=attempt.t_ready, t_effective=attempt.t_effective)
    return attempt


def resolve_attempt(attempt: RotationAttempt,
                     incident_open_fn: Callable[[int], bool] = lambda t: False,
                     eligibility_still_holds_fn: Callable[[int], bool] = lambda t: True,
                     emergency_override: bool = False) -> RotationAttempt:
    """Advances a PENDING attempt to its terminal/held state, given a
    scripted timeline:

    - `incident_open_fn(t)`: True if the room/incoming worker's
      incident_state is open at minute t (section 3e).
    - `eligibility_still_holds_fn(t)`: True if the reserved candidate's
      eligibility (section 3b/3g) still holds at minute t -- False at
      some t in [t_decide, t_effective) models an interrupted handoff
      (section 3d's "interrupted handoffs").
    - `emergency_override`: the one sanctioned exception (section 3d) --
      if set, the swap takes effect immediately at t_decide, bypassing
      boundary alignment entirely. This function never sets this itself;
      a caller representing the algorithm must never pass True here on
      its own authority (section 3h) -- only an RSO-reviewed override
      does, which is why this parameter exists and defaults to False.
    """
    if attempt.status != PENDING:
        return attempt

    if emergency_override:
        attempt.status = COMPLETED
        attempt.t_effective = attempt.t_decide
        attempt.override_used = True
        attempt.reason = "emergency_override"
        attempt.log("completed", via="emergency_override", t_effective=attempt.t_effective)
        return attempt

    for t in range(attempt.t_decide, attempt.t_effective):
        if not eligibility_still_holds_fn(t):
            attempt.status = ABORTED
            attempt.reason = "eligibility_changed_mid_handoff"
            attempt.log("aborted", reason=attempt.reason, at_minute=t)
            return attempt

    if incident_open_fn(attempt.t_effective):
        attempt.status = HELD
        attempt.reason = "incident_open_at_t_effective"
        attempt.log("held", reason=attempt.reason, t_effective=attempt.t_effective)
        return attempt

    attempt.status = COMPLETED
    attempt.reason = None
    attempt.log("completed", t_effective=attempt.t_effective)
    return attempt


def recompute_after_acknowledgement(attempt: RotationAttempt, t_ack: int,
                                     boundaries: List[int], shift_minutes: int) -> RotationAttempt:
    """Task 4's explicit requirement: "if a handoff is held by an
    incident, recompute the next valid effective boundary after
    acknowledgement; never execute a delayed swap mid-procedure."

    The original t_effective has already passed (it is what triggered
    HELD); the new effective time is the next scheduled boundary at or
    after t_ack -- itself always a boundary, via compute_t_effective --
    never the stale original boundary and never an arbitrary minute."""
    if attempt.status != HELD:
        return attempt
    new_t_eff = compute_t_effective(t_ack, boundaries, shift_minutes)
    if new_t_eff is None:
        attempt.status = ABORTED
        attempt.reason = "no_boundary_after_acknowledgement_before_shift_end"
        attempt.log("aborted", reason=attempt.reason, t_ack=t_ack)
        return attempt
    attempt.t_effective = new_t_eff
    attempt.status = COMPLETED
    attempt.reason = "completed_after_incident_acknowledgement"
    attempt.log("completed", via="post_acknowledgement", t_ack=t_ack, t_effective=new_t_eff)
    return attempt
