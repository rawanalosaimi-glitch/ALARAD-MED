"""
The live simulation orchestrator: runs ONE policy (task 2/3) over ONE
campaign run (`campaign_scenarios.build_campaign_run`), minute by
minute, producing per-worker dose outcomes, rotation events, and
safety-constraint counters. Calls into `assignment.py` (exclusivity/
reservation), `scheduling.py` (timeline/state machine),
`policies.py` (trigger/selection), `runtime.py` (live dose/sensor
state), and `dose_attribution.py` (post-hoc cross-check) -- no
scheduling, trigger, or dose logic is reimplemented here.

**Explicit, documented simplifications this orchestrator makes** (none
of them silently -- each is a stated research assumption, not a hidden
shortcut):

1. **Incident state is derived from the current occupant's own sensor-
   fault state** (STALE/DISCONNECTED/INVALID/SUSPECTED_FROZEN), not a
   separately-modeled incident-management system. A room has an "open
   incident" exactly when its current occupant's sensor is in one of
   these states.
2. **A worker's sensor-state history resets to HEALTHY at the start of
   each new assignment** (a fresh `AlaradSafety.newSensor()`), rather
   than carrying continuity across non-contiguous assignments in
   different rooms -- modeling "a freshly connected dosimeter for this
   assignment," not a single device followed across the whole shift
   regardless of location.
3. **Simulated RSO acknowledgement of a HELD handoff is modeled as
   occurring at the first minute the underlying incident (sensor fault)
   clears** -- a proxy for "a human noticed and cleared it," not a real
   acknowledgement-latency model. This is explicitly simpler than
   PHASE3B section 3h's own notification/acknowledgement framing, and
   is reported as such.
4. **Mid-handoff eligibility changes (section 3d's "interrupted
   handoff") do not arise naturally in this orchestrator** -- nothing
   in this simplified live model revokes a RESERVED candidate's
   eligibility between reservation and completion. That code path is
   exercised by `scheduling.py`'s own unit tests with synthetic
   scripted scenarios, not by this orchestrator's campaign runs.
5. **Persistent-infeasible-dose-concern escalation (section 3h's
   original concept) is tracked as a simple per-room counter in this
   module**, deliberately kept separate from `escalation.py`'s own
   sensor-fault-persistence state machine (task 5) -- the two are
   different concerns (a dose trigger with no feasible rotation, vs. a
   persisting sensor fault regardless of any trigger) that happen to
   share a similar NONE/RAISED/ACKNOWLEDGED/RESOLVED shape; this module
   does not overload one state machine for both.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from phase1_simulator.units import is_valid_rate
from phase2a_adapter.engine_bridge import EngineBridge
from phase2a_adapter.engine_contract import snapshot_engine_constants

from . import assignment as assignment_mod
from . import dose_attribution
from . import scheduling as scheduling_mod
from .config import Phase3CConfig, load_config
from .escalation import evaluate_escalation
from .exposure_layer import AssignmentSlot
from .policies import PolicySpec, TriggerContext, evaluate_trigger, rank_candidates
from .runtime import advance_workers_one_minute_batch, initialize_worker_runtime
from .sensor_validity import FLAGGED_STATES
from .staffing import ASSIGNED, FREE, RESTING, WorkerProfile


@dataclass
class RotationEventLog:
    room: str
    outgoing: str
    incoming: Optional[str]
    t_decide: int
    t_effective: Optional[int]
    status: str  # RESERVED-pending outcome: COMPLETED / ABORTED / HELD-then-COMPLETED / INFEASIBLE
    reason: Optional[str]
    clause: Optional[str]


@dataclass
class SimulationResult:
    policy_name: str
    seed: int
    archetype: str
    shift_minutes: int
    assignment_by_room: Dict[str, List[Optional[str]]] = field(default_factory=dict)
    cumulative_dose_per_worker: Dict[str, float] = field(default_factory=dict)
    collective_dose_mSv: float = 0.0
    max_individual_dose_mSv: float = 0.0
    rotation_events: List[RotationEventLog] = field(default_factory=list)
    n_completed: int = 0
    n_infeasible: int = 0
    n_aborted: int = 0
    n_held: int = 0
    n_unresolved_at_shift_end: int = 0
    n_violations: int = 0
    escalated_rooms: Dict[str, int] = field(default_factory=dict)  # room -> consecutive infeasible count at escalation
    trigger_clause_counts: Dict[str, int] = field(default_factory=dict)  # "a"/"b"/"c"/"interval" -> count


def _pick_initial_occupant(room: str, procedure_class: str, roster: Dict[str, WorkerProfile],
                            already_assigned: set) -> str:
    candidates = sorted(
        wid for wid, w in roster.items()
        if wid not in already_assigned and w.is_credentialed_for(room, procedure_class)
    )
    if not candidates:
        candidates = sorted(wid for wid in roster if wid not in already_assigned)
    if not candidates:
        candidates = sorted(roster.keys())
    return candidates[0]


def run_policy_on_run(bridge: EngineBridge, campaign_run: Dict[str, Any],
                       roster: Dict[str, WorkerProfile], policy: PolicySpec,
                       p3c_cfg: Optional[Phase3CConfig] = None) -> SimulationResult:
    cfg = p3c_cfg or load_config()
    engine_config = snapshot_engine_constants(bridge)
    min_handoff = cfg.block("handoff")["min_handoff_duration_minutes"]

    slots_by_room: Dict[str, List[AssignmentSlot]] = campaign_run["slots_by_room"]
    exposure_by_slot: Dict[str, List[float]] = campaign_run["exposure_by_slot"]
    observations_by_room: Dict[str, List[Optional[Dict]]] = campaign_run["observations_by_room"]
    shift_minutes: int = campaign_run["shift_minutes"]

    result = SimulationResult(policy_name=policy.name, seed=campaign_run["seed"],
                               archetype=campaign_run["archetype"], shift_minutes=shift_minutes)

    assignment_by_room: Dict[str, List[Optional[str]]] = {r: [None] * shift_minutes for r in slots_by_room}
    boundaries_by_room = {r: sorted({s.start_minute for s in slots} | {s.end_minute for s in slots})
                           for r, slots in slots_by_room.items()}
    slot_at_minute = {
        r: {t: s for s in slots for t in range(s.start_minute, s.end_minute)}
        for r, slots in slots_by_room.items()
    }

    occupant: Dict[str, str] = {}
    already = set()
    for r, slots in slots_by_room.items():
        proc_class = slots[0].procedure_class if slots else ""
        wid = _pick_initial_occupant(r, proc_class, roster, already)
        occupant[r] = wid
        already.add(wid)
        roster[wid].state = ASSIGNED
        initialize_worker_runtime(bridge, roster[wid])

    pending_attempts: Dict[str, scheduling_mod.RotationAttempt] = {}
    consecutive_infeasible: Dict[str, int] = {}

    rooms_order = sorted(slots_by_room.keys())

    for t in range(shift_minutes):
        # 1. resolve any attempt whose t_effective == t, BEFORE advancing
        #    anyone's per-minute state for t -- the incident-open check
        #    uses each worker's state as carried over from t-1 (section
        #    3d: "outgoing worker occupies through the last minute
        #    before T_effective; incoming worker from T_effective
        #    onward" -- so a completed swap must update `occupant[r]`
        #    before minute t's own reading is attributed to anyone).
        for r in rooms_order:
            attempt = pending_attempts.get(r)
            if attempt is None or attempt.t_effective != t:
                continue
            incident_open = roster[attempt.reserved_worker_id].sensor_state_label in FLAGGED_STATES \
                if attempt.reserved_worker_id else False
            outgoing_incident_open = roster[occupant[r]].sensor_state_label in FLAGGED_STATES
            if outgoing_incident_open or incident_open:
                attempt.status = scheduling_mod.HELD
                attempt.reason = "incident_open_at_t_effective"
                result.n_held += 1
                pending_attempts[r] = attempt
            else:
                _complete_attempt(attempt, r, occupant, roster, assignment_by_room, result, t)
                del pending_attempts[r]

        # 1b. check HELD attempts for simulated acknowledgement (incident
        #     cleared as of t-1's state), also before advancing for t.
        for r in list(pending_attempts.keys()):
            attempt = pending_attempts[r]
            if attempt.status != scheduling_mod.HELD:
                continue
            still_open = roster[occupant[r]].sensor_state_label in FLAGGED_STATES
            if not still_open:
                recomputed = scheduling_mod.recompute_after_acknowledgement(
                    attempt, t_ack=t, boundaries=boundaries_by_room[r], shift_minutes=shift_minutes)
                if recomputed.status == scheduling_mod.ABORTED:
                    result.n_aborted += 1
                    assignment_mod.release_reservation(roster[attempt.reserved_worker_id], to_resting=False)
                    del pending_attempts[r]
                elif recomputed.status == scheduling_mod.COMPLETED and recomputed.t_effective == t:
                    _complete_attempt(recomputed, r, occupant, roster, assignment_by_room, result, t)
                    del pending_attempts[r]
                # else: COMPLETED scheduled for a later t -- keep waiting.

        # 2. advance every room's current (possibly just-updated) occupant
        #    one minute (batched), using minute t's own reading.
        readings = []
        for r in rooms_order:
            obs = observations_by_room[r][t] if t < len(observations_by_room[r]) else None
            reading = None if obs is None else obs["value"]
            readings.append((roster[occupant[r]], reading))
        advance_workers_one_minute_batch(bridge, readings, t)

        for r in rooms_order:
            assignment_by_room[r][t] = occupant[r]

        # 3. advance RESTING -> FREE across the whole roster.
        for w in roster.values():
            assignment_mod.advance_resting_to_free(w, t)

        # 4. at each room's procedure boundary (start of a new slot), evaluate the trigger.
        for r in rooms_order:
            if r in pending_attempts:
                continue  # one attempt at a time per room
            slot = slot_at_minute[r].get(t)
            if slot is None or slot.start_minute != t or t == 0:
                continue  # only at a boundary, and not the very first minute (nothing to rotate out of)
            w = roster[occupant[r]]
            ctx = TriggerContext(room=r, worker=w, t=t,
                                  remaining_minutes_in_slot=slot.remaining_minutes(t),
                                  procedure_class=slot.procedure_class, proc_mult=slot.proc_mult)
            outcome = evaluate_trigger(policy, bridge, ctx, cfg, engine_config)
            if not outcome.fired:
                consecutive_infeasible[r] = 0
                continue
            result.trigger_clause_counts[outcome.clause] = result.trigger_clause_counts.get(outcome.clause, 0) + 1

            candidate_ids = [wid for wid, cw in roster.items()
                             if wid != w.worker_id and cw.is_credentialed_for(r, slot.procedure_class)]
            ranked = rank_candidates(policy, roster, candidate_ids)
            req = assignment_mod.RotationRequest(room=r, outgoing_worker_id=w.worker_id, candidate_order=ranked)
            t_ready = scheduling_mod.compute_t_ready(t, min_handoff)
            t_eff_guess = scheduling_mod.compute_t_effective(t_ready, boundaries_by_room[r], shift_minutes)
            # section 3i's "intended assignment interval": the conservative
            # default (the single slot the candidate would join, from
            # t_effective to that slot's own end) -- never a longer,
            # speculative projection (PHASE3B_ROTATION_ALGORITHM_DESIGN.md
            # section 3i's explicit default).
            intended_minutes = None
            if t_eff_guess is not None:
                joining_slot = slot_at_minute[r].get(t_eff_guess, slot)
                intended_minutes = joining_slot.remaining_minutes(t_eff_guess)
            outcomes = assignment_mod.batch_resolve(
                [req], roster, t, {r: t_eff_guess} if t_eff_guess is not None else {},
                {r: intended_minutes} if intended_minutes is not None else None,
            )
            out = outcomes[0]
            if out.status == "INFEASIBLE":
                result.n_infeasible += 1
                consecutive_infeasible[r] = consecutive_infeasible.get(r, 0) + 1
                if consecutive_infeasible[r] >= 2 and r not in result.escalated_rooms:
                    result.escalated_rooms[r] = consecutive_infeasible[r]
                result.rotation_events.append(RotationEventLog(
                    room=r, outgoing=w.worker_id, incoming=None, t_decide=t, t_effective=None,
                    status="INFEASIBLE", reason=out.reason, clause=outcome.clause))
                continue

            consecutive_infeasible[r] = 0
            attempt = scheduling_mod.start_attempt(r, w.worker_id, out.reserved_worker_id, t,
                                                    min_handoff, boundaries_by_room[r], shift_minutes)
            if attempt.status == scheduling_mod.INFEASIBLE:
                result.n_infeasible += 1
                assignment_mod.release_reservation(roster[out.reserved_worker_id], to_resting=False)
                result.rotation_events.append(RotationEventLog(
                    room=r, outgoing=w.worker_id, incoming=out.reserved_worker_id, t_decide=t,
                    t_effective=None, status="INFEASIBLE", reason=attempt.reason, clause=outcome.clause))
                continue
            attempt_tagged = attempt
            attempt_tagged.__dict__["clause"] = outcome.clause
            pending_attempts[r] = attempt_tagged

    # Bug found during the final supplementary validation round (see
    # ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md, Experiment A sub-case A8):
    # `scheduling.compute_t_effective` legitimately allows t_effective ==
    # shift_minutes (its own docstring: "shift end is itself always
    # treated as a procedure boundary"), so `start_attempt` can leave an
    # attempt PENDING with t_effective == shift_minutes. The main loop
    # above only ever iterates t in range(shift_minutes) -- it never
    # reaches minute shift_minutes -- so such an attempt was previously
    # silently dropped from every counter (not completed, not infeasible,
    # not aborted, not held). The same drop applies to a HELD attempt
    # whose incident simply never clears before shift end -- it too would
    # sit in `pending_attempts` forever, uncounted. Fixed by resolving any
    # leftover attempt (PENDING or HELD) explicitly here, in its own
    # category: completing a t_effective==shift_minutes attempt would
    # misrepresent a swap with zero actual occupancy minutes as a real
    # rotation, so both cases are counted separately, never silently
    # folded into n_completed/n_infeasible/n_held. Reservations are
    # released (not left dangling) for roster-state hygiene.
    for r in rooms_order:
        attempt = pending_attempts.get(r)
        if attempt is None:
            continue
        result.n_unresolved_at_shift_end += 1
        reason = ("t_effective_equals_shift_minutes_never_reached_by_main_loop"
                  if attempt.status == scheduling_mod.PENDING
                  else "held_incident_never_cleared_before_shift_end")
        if attempt.reserved_worker_id is not None:
            assignment_mod.release_reservation(roster[attempt.reserved_worker_id], to_resting=False)
        result.rotation_events.append(RotationEventLog(
            room=r, outgoing=attempt.outgoing_worker_id, incoming=attempt.reserved_worker_id,
            t_decide=attempt.t_decide, t_effective=attempt.t_effective,
            status="UNRESOLVED_AT_SHIFT_END", reason=reason,
            clause=getattr(attempt, "clause", None)))
        del pending_attempts[r]

    # final roll-up
    result.assignment_by_room = assignment_by_room
    attributed = dose_attribution.attribute_dose(slots_by_room, exposure_by_slot, assignment_by_room, shift_minutes)
    result.cumulative_dose_per_worker = dose_attribution.cumulative_dose_per_worker(attributed)
    result.collective_dose_mSv = dose_attribution.collective_dose_mSv(result.cumulative_dose_per_worker)
    result.max_individual_dose_mSv = dose_attribution.max_individual_dose_mSv(result.cumulative_dose_per_worker)
    return result


def _complete_attempt(attempt, room, occupant, roster, assignment_by_room, result, t) -> None:
    incoming_id = attempt.reserved_worker_id
    outgoing_id = occupant[room]
    assignment_mod.complete_reservation(roster[incoming_id])
    assignment_mod.mark_rotated_out(roster[outgoing_id], t)
    occupant[room] = incoming_id
    # Fresh "device" for the new assignment (module docstring simplification 2):
    # re-initialized lazily on the new occupant's next advance_*_one_minute call.
    roster[incoming_id].sensor_state_obj = None
    result.n_completed += 1
    result.rotation_events.append(RotationEventLog(
        room=room, outgoing=outgoing_id, incoming=incoming_id, t_decide=attempt.t_decide,
        t_effective=attempt.t_effective, status="COMPLETED", reason=attempt.reason,
        clause=getattr(attempt, "clause", None)))
