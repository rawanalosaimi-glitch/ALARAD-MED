"""
Sensor-fault logging and simulated escalation (task 5), deliberately
INDEPENDENT of dose-trigger logic -- this module never reads
CONFIG.doseElevated/doseCritical or any projected/cumulative dose value.
This decoupling is not only what this round's instructions ask for; it
is also the safe choice given this round's own read-only audit
(PHASE3C_A_DOSE_THRESHOLD_SEMANTIC_AUDIT.md), which found that
PHASE3B_ROTATION_ALGORITHM_DESIGN.md section 3a's assumption about those
thresholds' semantics does not match the frozen engine's actual code --
this module cannot inherit that unverified assumption because it does
not depend on it at all.

Implements the escalation state machine in
PHASE3B_ROTATION_ALGORITHM_DESIGN.md section 3h: a persistent sensor
fault raises an escalation that is never silently cleared without either
an explicit (simulated) RSO-acknowledgement or the fault itself clearing.
The escalation threshold is a new, explicitly PROVISIONAL parameter
(config/phase3c_config.json `escalation` block) -- NOT connected to any
real paging/notification system, per the explicit restriction.

Sensor-fault *states* themselves are not reimplemented here -- they come
from the frozen engine's own `AlaradSafety.sensorStep`, reused unchanged
via phase2a_adapter.dq_adapter.run_sensor_state_machine /
DQ_FLAGGED_STATES (imported, not duplicated).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional

from phase2a_adapter.dq_adapter import DQ_FLAGGED_STATES

from .config import Phase3CConfig, load_config

NONE = "NONE"
RAISED = "RAISED"
ACKNOWLEDGED = "ACKNOWLEDGED"
RESOLVED = "RESOLVED"


@dataclass
class EscalationRecord:
    """`state`/`raised_at`/`acknowledged_at`/`resolved_at`/
    `resolution_reason` reflect only the MOST RECENT escalation episode
    -- a worker can have more than one independent episode within a
    single shift (fault, resolve, fault again), and these scalar fields
    are overwritten by each new episode. `audit_log` is the append-only,
    never-overwritten record of every episode's events; read it, not the
    scalar fields, for a complete per-shift history."""
    worker_id: str
    state: str = NONE
    raised_at: Optional[int] = None
    acknowledged_at: Optional[int] = None
    resolved_at: Optional[int] = None
    resolution_reason: Optional[str] = None
    audit_log: List[Dict] = field(default_factory=list)

    def log(self, event: str, **fields) -> None:
        self.audit_log.append({"event": event, "worker_id": self.worker_id, **fields})


def evaluate_escalation(worker_id: str, sensor_states: List[str],
                         shift_minutes: int, ack_minute: Optional[int] = None,
                         escalate_after_minutes: Optional[int] = None,
                         flagged_states: FrozenSet[str] = DQ_FLAGGED_STATES,
                         p3c_cfg: Optional[Phase3CConfig] = None) -> EscalationRecord:
    """Walks `sensor_states` (one entry per minute, from the real
    engine's sensorStep -- see dq_adapter.run_sensor_state_machine)
    minute by minute. Raises escalation once a run of consecutive
    minutes in `flagged_states` reaches `escalate_after_minutes`;
    re-raises (stays RAISED) while unacknowledged and the fault
    persists; moves to ACKNOWLEDGED at `ack_minute` if supplied while
    RAISED; resolves when the fault clears (acknowledged or not) or
    shift end is reached while still RAISED (logged distinctly as
    "unacknowledged_at_shift_end" -- section 3h's required distinction,
    never treated the same as an acknowledged resolution).

    Does NOT relax any constraint and does NOT decide to rotate anyone
    -- it only detects and logs (section 3h's explicit scope limit)."""
    cfg = p3c_cfg or load_config()
    if escalate_after_minutes is None:
        escalate_after_minutes = cfg.block("escalation")["escalate_after_consecutive_fault_minutes"]

    rec = EscalationRecord(worker_id=worker_id)
    consecutive = 0
    for t, state in enumerate(sensor_states):
        flagged = state in flagged_states
        if flagged:
            consecutive += 1
        else:
            consecutive = 0
            if rec.state in (RAISED, ACKNOWLEDGED):
                reason = ("sensor_fault_cleared" if rec.state == RAISED
                          else "sensor_fault_cleared_after_acknowledgement")
                rec.state = RESOLVED
                rec.resolved_at = t
                rec.resolution_reason = reason
                rec.log("resolved", reason=reason, at_minute=t)
                continue

        # Bug found during the final supplementary validation round
        # (Experiment B, "repeated faults" sub-case): this used to read
        # `rec.state == NONE` only, which meant a worker whose FIRST
        # fault episode resolved could never raise a SECOND, independent
        # episode later in the same shift -- once RESOLVED, this guard
        # would never again be true. `raised_at`/`resolved_at`/
        # `resolution_reason` remain single (latest-episode) fields by
        # design (see the dataclass docstring); `audit_log` is the
        # append-only record of every episode, and already correctly
        # captured each one once this guard was fixed.
        if rec.state in (NONE, RESOLVED) and consecutive >= escalate_after_minutes:
            rec.state = RAISED
            rec.raised_at = t
            rec.log("raised", at_minute=t, consecutive_fault_minutes=consecutive)

        if rec.state == RAISED and ack_minute is not None and t == ack_minute:
            rec.state = ACKNOWLEDGED
            rec.acknowledged_at = t
            rec.log("acknowledged", at_minute=t)

    if rec.state == RAISED:
        rec.state = RESOLVED
        rec.resolved_at = shift_minutes
        rec.resolution_reason = "unacknowledged_at_shift_end"
        rec.log("resolved", reason=rec.resolution_reason, at_minute=shift_minutes)
    elif rec.state == ACKNOWLEDGED:
        rec.state = RESOLVED
        rec.resolved_at = shift_minutes
        rec.resolution_reason = "acknowledged_shift_ended"
        rec.log("resolved", reason=rec.resolution_reason, at_minute=shift_minutes)

    return rec
