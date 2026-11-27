"""
Experiment C -- duty limits, HELD state, and RSO acknowledgement
(final supplementary validation round, section 2). Twelve controlled
sub-cases, each targeting one specific trigger clause, eligibility
sub-check, or scheduling state transition that the audit found was
never exercised by the original 390-run campaign (clauses (b)/(c),
the projected-dose duty-limit exclusion, HELD, and RSO acknowledgement
all had zero occurrences there).

Respects the three distinct dose quantities throughout (never
conflated): EngineProjectedTaskDose (clause b, vs. CONFIG.doseElevated),
WorkerAccumulatedShiftDose (clause a, vs. the research-only reference
level), ProjectedShiftTotalDose (clause c AND the duty-limit exclusion,
vs. the worker's own max_dose_per_shift_mSv).
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Dict, List, Optional

from ..config import Phase3CConfig, load_config
from ..policies import CGDTR
from ..scheduling import ABORTED, COMPLETED, HELD, INFEASIBLE, PENDING
from ..simulation import run_policy_on_run
from .controlled_builders import DEFAULT_PROCEDURE_CLASS, DEFAULT_ROOM, WorkerSpec, build_roster, build_single_room_run, inject_fault

ROOM = DEFAULT_ROOM
PROC = DEFAULT_PROCEDURE_CLASS


def _w(worker_id, dose=0.0, max_dose=5.0, rotations_so_far=0, max_rotations=3,
       state="FREE", credentialed=True, availability=None, last_rate=None):
    return WorkerSpec(
        worker_id=worker_id,
        credentialed_rooms=(ROOM,) if credentialed else (),
        credentialed_procedure_classes=(PROC,) if credentialed else (),
        cumulative_dose_mSv=dose, max_dose_per_shift_mSv=max_dose,
        rotations_so_far=rotations_so_far, max_rotations_per_shift=max_rotations,
        state=state, availability_windows=availability, last_valid_rate_uSv_h=last_rate,
    )


def c1_accumulated_dose_threshold(bridge, seed, cfg):
    """Clause (a) alone: accumulated dose preset above threshold_a
    (0.05 mSv), rate kept low enough that neither clause (b) nor (c)
    could also fire at the same decision point."""
    shift = 120
    run = build_single_room_run(seed, shift, rate_uSv_h=20.0, room=ROOM, procedure_class=PROC, n_slots=4)
    roster = build_roster([_w("W00", dose=0.08, max_dose=5.0), _w("W01", dose=0.0)], shift)
    res = run_policy_on_run(bridge, run, roster, CGDTR, cfg)
    return res, {"isolates": "clause (a)"}


def c2_engine_projected_task_dose(bridge, seed, cfg):
    """Clause (b) alone: a single boundary at t=1 so almost no real
    dose has accrued (clause (a) false), but the rate (350 uSv/h) is
    high enough that the engine's own 30-minute EngineProjectedTaskDose
    already exceeds CONFIG.doseElevated (0.15 mSv): 350*0.5/1000=0.175."""
    shift = 121
    run = build_single_room_run(seed, shift, rate_uSv_h=350.0, room=ROOM, procedure_class=PROC,
                                 boundaries=[0, 1, 60, shift])
    roster = build_roster([_w("W00", dose=0.0, max_dose=50.0), _w("W01", dose=0.0)], shift)
    res = run_policy_on_run(bridge, run, roster, CGDTR, cfg)
    return res, {"isolates": "clause (b)", "engine_projection_mSv_expected": 350 * 0.5 / 1000}


def c3_projected_shift_total_dose(bridge, seed, cfg):
    """Clause (c) alone: modest rate (100 uSv/h, so clauses (a)/(b)
    stay false at t=1) but a long remaining slot and a deliberately low
    max_dose_per_shift_mSv (0.15) for the outgoing worker, so accrued +
    rate*remaining_hours exceeds their own cap."""
    shift = 121
    # Deliberately only two checked boundaries (t=1, then shift end):
    # an earlier middle boundary would let accumulated dose grow enough
    # by then to also satisfy clause (a) first, breaking this case's
    # isolation of clause (c) alone. The resulting attempt lands exactly
    # at t_effective == shift_minutes and is correctly reported as
    # UNRESOLVED_AT_SHIFT_END (this round's own fix) rather than
    # COMPLETED -- clause isolation is this case's point, not completion.
    run = build_single_room_run(seed, shift, rate_uSv_h=100.0, room=ROOM, procedure_class=PROC,
                                 boundaries=[0, 1, shift])
    roster = build_roster([_w("W00", dose=0.0, max_dose=0.15), _w("W01", dose=0.0)], shift)
    res = run_policy_on_run(bridge, run, roster, CGDTR, cfg)
    return res, {"isolates": "clause (c)"}


def c4_candidate_excluded_by_projected_duty_limit(bridge, seed, cfg):
    """The projected-dose duty-limit exclusion in assignment.py (the
    Phase 3C-A gap-3 closure) -- zero occurrences in the original
    390-run campaign (PHASE3C_AUDIT_REPORT.md issue 3/5). W00 triggers
    on clause (a). W01 (the only other credentialed worker) is primed
    with a last_valid_rate_uSv_h from an earlier (synthetic, directly-
    set) exposure and a low max_dose_per_shift_mSv, so assigning it the
    intended remaining slot would push its OWN projected total over its
    OWN cap -- it must be excluded, leaving the trigger INFEASIBLE even
    though a credentialed, otherwise-FREE candidate exists."""
    shift = 120
    run = build_single_room_run(seed, shift, rate_uSv_h=20.0, room=ROOM, procedure_class=PROC, n_slots=4)
    roster = build_roster([
        _w("W00", dose=0.08, max_dose=5.0),
        _w("W01", dose=0.10, max_dose=0.12, last_rate=50.0),  # 0.10 + 50*~ (remaining hours) will exceed 0.12
    ], shift)
    res = run_policy_on_run(bridge, run, roster, CGDTR, cfg)
    return res, {"isolates": "projected-duty-limit exclusion (assignment.py)"}


def c5_no_safe_replacement(bridge, seed, cfg):
    """Same structural condition as Experiment A's A10 -- included here
    too (cross-referenced, not duplicated in the write-up) because
    Experiment C's own sub-case list names it explicitly."""
    shift = 120
    run = build_single_room_run(seed, shift, rate_uSv_h=20.0, room=ROOM, procedure_class=PROC, n_slots=4)
    roster = build_roster([
        _w("W00", dose=0.08),
        _w("W01", state="ASSIGNED"),
    ], shift)
    res = run_policy_on_run(bridge, run, roster, CGDTR, cfg)
    return res, {"isolates": "no eligible candidate (see also Experiment A case A10)"}


def _held_scenario(seed, cfg, fault_kind="missing", ack_delay_boundaries=0):
    """Builds a scenario where a sensor fault is injected to span EXACTLY
    the computed t_effective of the first rotation attempt, forcing
    HELD, then (unless ack_delay_boundaries pushes the fault further)
    clears it so the attempt can complete at the next valid boundary.
    Returns (run, roster, cfg, t_decide, t_ready, t_effective)."""
    from .. import scheduling as scheduling_mod
    min_handoff = cfg.block("handoff")["min_handoff_duration_minutes"]
    shift = 180
    boundaries = [0, 30, 60, 90, 120, 150, 180]
    run = build_single_room_run(seed, shift, rate_uSv_h=20.0, room=ROOM, procedure_class=PROC,
                                 boundaries=boundaries)
    roster = build_roster([_w("W00", dose=0.08), _w("W01", dose=0.0)], shift)
    t_decide = 30  # first checked boundary (t=0 is skipped by design)
    t_ready = scheduling_mod.compute_t_ready(t_decide, min_handoff)
    t_effective = scheduling_mod.compute_t_effective(t_ready, boundaries, shift)
    # Fault the INCOMING candidate (W01) so it is FLAGGED exactly at
    # t_effective -- forces HELD per simulation.py's own incident check.
    fault_start = t_effective - 2
    fault_end = t_effective + 1 + ack_delay_boundaries * 30
    inject_fault(run, ROOM, fault_start, fault_end, fault_kind)
    return run, roster, t_decide, t_ready, t_effective, boundaries, shift


def c6_held_state(bridge, seed, cfg):
    """RSO acknowledgement NOT modeled as a separate signal in this
    orchestrator (module docstring simplification #3): HELD resolves as
    soon as the underlying fault clears. This case: fault clears exactly
    one boundary after t_effective, so the attempt should go HELD then
    COMPLETE at the next boundary after the fault clears."""
    run, roster, t_decide, t_ready, t_eff, boundaries, shift = _held_scenario(seed, cfg, ack_delay_boundaries=0)
    res = run_policy_on_run(bridge, run, roster, CGDTR, cfg)
    return res, {"isolates": "HELD state", "t_decide": t_decide, "t_ready": t_ready, "t_effective": t_eff}


def c7_rso_acknowledgement_received(bridge, seed, cfg):
    """Same as C6 -- in this implementation, 'acknowledgement' IS fault
    clearance (module docstring simplification #3; no separate ack
    signal exists). Included as its own named case per the task's own
    list, with an explicit note that C6/C7 are the same underlying
    mechanism in this codebase."""
    return c6_held_state(bridge, seed, cfg)


def c8_rso_acknowledgement_delayed(bridge, seed, cfg):
    """Fault clears several boundaries later than C6/C7 -- the attempt
    must recompute to the FIRST valid boundary at or after the real
    clearance time, never the stale original t_effective."""
    run, roster, t_decide, t_ready, t_eff, boundaries, shift = _held_scenario(seed, cfg, ack_delay_boundaries=2)
    res = run_policy_on_run(bridge, run, roster, CGDTR, cfg)
    return res, {"isolates": "delayed acknowledgement / recompute", "t_decide": t_decide, "t_effective_original": t_eff}


def c9_rso_acknowledgement_absent(bridge, seed, cfg):
    """Fault never clears before shift end -- must resolve to the new
    UNRESOLVED_AT_SHIFT_END category (the bug this round found and
    fixed in simulation.py), never silently dropped."""
    from .. import scheduling as scheduling_mod
    min_handoff = cfg.block("handoff")["min_handoff_duration_minutes"]
    shift = 90
    boundaries = [0, 30, 60, 90]
    run = build_single_room_run(seed, shift, rate_uSv_h=20.0, room=ROOM, procedure_class=PROC, boundaries=boundaries)
    roster = build_roster([_w("W00", dose=0.08), _w("W01", dose=0.0)], shift)
    t_decide = 30
    t_ready = scheduling_mod.compute_t_ready(t_decide, min_handoff)
    t_eff = scheduling_mod.compute_t_effective(t_ready, boundaries, shift)
    inject_fault(run, ROOM, t_eff - 2, shift, "missing")  # never clears
    res = run_policy_on_run(bridge, run, roster, CGDTR, cfg)
    return res, {"isolates": "acknowledgement absent / shift-end unresolved", "t_effective": t_eff}


def c10_rso_acknowledgement_rejected(bridge, seed, cfg):
    """Checks whether the implemented state machine supports an explicit
    'acknowledgement rejected' transition at all. It does not --
    scheduling.py defines only PROPOSED/PENDING/HELD/COMPLETED/
    ABORTED/INFEASIBLE, and `recompute_after_acknowledgement` has no
    rejection branch, only clear-vs-still-open. Reported as NOT
    IMPLEMENTED, per this round's own explicit instruction, rather than
    inventing a behavior for it."""
    return None, {"isolates": "acknowledgement rejected", "status": "NOT_IMPLEMENTED",
                  "detail": "scheduling.py has no ACK-REJECTED state or transition; "
                            "RotationAttempt.status is one of PROPOSED/PENDING/HELD/"
                            "COMPLETED/ABORTED/INFEASIBLE and recompute_after_acknowledgement "
                            "only distinguishes fault-cleared vs. still-open, never a rejection."}


def c11_repeated_triggers_while_pending(bridge, seed, cfg):
    """simulation.py's own `if r in pending_attempts: continue` (one
    attempt at a time per room) should prevent a second trigger from
    even being evaluated while one is already PENDING/HELD for that
    room. Verified by constructing a case where, were this guard absent,
    the second boundary (t=60) would also satisfy clause (a) for the
    SAME outgoing worker -- confirm only ONE attempt is ever open for
    this room at a time."""
    shift = 150
    boundaries = [0, 30, 60, 90, 120, 150]
    run = build_single_room_run(seed, shift, rate_uSv_h=20.0, room=ROOM, procedure_class=PROC, boundaries=boundaries)
    roster = build_roster([_w("W00", dose=0.08), _w("W01", dose=0.0, availability=[(0, 40)])], shift)
    # W01 (the only other credentialed worker) is unavailable past t=40,
    # so the first trigger (t=30) is INFEASIBLE, and the room has NO
    # pending attempt going into the second boundary (t=60) -- this
    # case checks the inverse-but-related invariant: a room with an
    # INFEASIBLE (not pending) first attempt is correctly re-evaluated
    # at the next boundary, not permanently skipped.
    res = run_policy_on_run(bridge, run, roster, CGDTR, cfg)
    return res, {"isolates": "one-attempt-per-room guard / re-evaluation after INFEASIBLE"}


def c12_simultaneous_safety_events(bridge, seed, cfg):
    """Two independent rooms both trigger at the same decision minute --
    confirms the atomic batch reservation (assignment.batch_resolve,
    already proven in the main campaign and its own unit tests) extends
    correctly to a duty-limit/HELD-adjacent context: both rooms' outgoing
    workers are above threshold_a simultaneously, and the only two
    candidates could in principle collide."""
    shift = 120
    boundaries = [0, 30, 60, 90, 120]
    room_b = "CT Suite"
    run = build_single_room_run(seed, shift, rate_uSv_h=20.0, room=ROOM, procedure_class=PROC, boundaries=boundaries)
    run_b = build_single_room_run(seed + 1, shift, rate_uSv_h=20.0, room=room_b, procedure_class=PROC, boundaries=boundaries)
    run["slots_by_room"][room_b] = run_b["slots_by_room"][room_b]
    run["exposure_by_slot"].update(run_b["exposure_by_slot"])
    run["observations_by_room"][room_b] = run_b["observations_by_room"][room_b]
    roster = build_roster([
        _w("W00", dose=0.08, credentialed=True),
        _w("W01", dose=0.08, credentialed=True),
        _w("W02", dose=0.0),
    ], shift)
    roster["W00"].credentialed_rooms = frozenset([ROOM])
    roster["W01"].credentialed_rooms = frozenset([room_b])
    roster["W02"].credentialed_rooms = frozenset([ROOM, room_b])
    for w in roster.values():
        w.credentialed_procedure_classes = frozenset([PROC])
    res = run_policy_on_run(bridge, run, roster, CGDTR, cfg)
    return res, {"isolates": "simultaneous cross-room trigger / atomic reservation"}


SUB_CASES_C = [
    ("C1", "Accumulated-shift-dose threshold reached", c1_accumulated_dose_threshold),
    ("C2", "Engine-projected task-dose threshold reached", c2_engine_projected_task_dose),
    ("C3", "Projected-shift-total-dose limit reached", c3_projected_shift_total_dose),
    ("C4", "Candidate excluded by projected duty limit", c4_candidate_excluded_by_projected_duty_limit),
    ("C5", "No eligible replacement exists", c5_no_safe_replacement),
    ("C6", "HELD state", c6_held_state),
    ("C7", "RSO acknowledgement received", c7_rso_acknowledgement_received),
    ("C8", "RSO acknowledgement delayed", c8_rso_acknowledgement_delayed),
    ("C9", "RSO acknowledgement absent", c9_rso_acknowledgement_absent),
    ("C10", "RSO acknowledgement rejected", c10_rso_acknowledgement_rejected),
    ("C11", "Repeated triggers while an event is pending", c11_repeated_triggers_while_pending),
    ("C12", "Simultaneous safety events (two rooms)", c12_simultaneous_safety_events),
]

EXPERIMENT_C_SEED_BASE = 930000
SEEDS_PER_SUB_CASE = 30


def run_experiment_c(bridge, p3c_cfg: Optional[Phase3CConfig] = None,
                      seeds_per_case: int = SEEDS_PER_SUB_CASE) -> List[Dict]:
    cfg = p3c_cfg or load_config()
    rows = []
    for c_idx, (case_id, title, fn) in enumerate(SUB_CASES_C):
        if fn is c10_rso_acknowledgement_rejected:
            _, meta = fn(bridge, 0, cfg)
            rows.append({"experiment": "C", "case_id": case_id, "title": title, "seed": None, **meta})
            print(f"  Experiment C {case_id:4s} ({title}) -- NOT_IMPLEMENTED, no seeds run")
            continue
        for i in range(seeds_per_case):
            seed = EXPERIMENT_C_SEED_BASE + c_idx * 1000 + i
            res, meta = fn(bridge, seed, cfg)
            rows.append({
                "experiment": "C", "case_id": case_id, "title": title, "seed": seed,
                **meta, "simulation_result": asdict(res),
            })
        print(f"  Experiment C {case_id:4s} ({title}) -- {seeds_per_case} seeds done")
    return rows
