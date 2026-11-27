"""
Experiment B -- sensor faults and safety escalation, exercised end to
end against the real per-minute runtime path (final supplementary
validation round, section 2).

Captures the real orchestrator's own per-minute sensor-state sequence
(via a thin, documented monkeypatch of `simulation.advance_workers_one_minute_batch`
-- the SAME real function the live orchestrator calls every minute;
nothing about sensor-state classification is reimplemented) and feeds
it to the real `escalation.evaluate_escalation`, closing the audit's
"imported but never called" finding WITHOUT modifying the live
orchestrator's own decision path (CGDTR/reference-rule/etc. still never
call `evaluate_escalation` themselves -- this experiment verifies the
function works correctly end-to-end on real engine-driven data, as a
separate, explicit analysis step, exactly as `escalation.py`'s own
module docstring already scopes it: "does NOT decide to rotate anyone
-- it only detects and logs.")
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Dict, List, Optional

from .. import simulation as simulation_mod
from ..config import Phase3CConfig, load_config
from ..escalation import evaluate_escalation
from ..policies import CGDTR, NO_ROTATION
from ..sensor_validity import FLAGGED_STATES, TRUSTED_FOR_TRIGGER
from ..simulation import run_policy_on_run
from .controlled_builders import DEFAULT_PROCEDURE_CLASS, DEFAULT_ROOM, WorkerSpec, build_roster, build_single_room_run, inject_fault

ROOM = DEFAULT_ROOM
PROC = DEFAULT_PROCEDURE_CLASS
RATE_UV_H = 150.0
SHIFT_MINUTES = 90


class _SensorHistoryCapture:
    """Context manager: wraps `simulation_mod.advance_workers_one_minute_batch`
    for its duration, recording (worker_id, t) -> {state, usable} from
    the real engine's own return values -- the exact same values
    `runtime.py` already writes onto `WorkerProfile.sensor_state_label`
    every minute, just also kept in a side list so this experiment can
    feed them to `evaluate_escalation` afterward. Restores the original
    function on exit regardless of success/failure."""

    def __init__(self):
        self.history: Dict[str, List[str]] = {}
        self._orig = None

    def __enter__(self):
        self._orig = simulation_mod.advance_workers_one_minute_batch

        def wrapped(bridge, worker_readings, t):
            pairs = list(worker_readings)
            self._orig(bridge, pairs, t)
            for worker, _reading in pairs:
                self.history.setdefault(worker.worker_id, []).append(worker.sensor_state_label)
            return None

        simulation_mod.advance_workers_one_minute_batch = wrapped
        return self

    def __exit__(self, *exc):
        simulation_mod.advance_workers_one_minute_batch = self._orig
        return False


def _single_worker_run(seed: int, shift_minutes: int = SHIFT_MINUTES, rate_uSv_h: float = RATE_UV_H):
    run = build_single_room_run(seed, shift_minutes, rate_uSv_h, room=ROOM, procedure_class=PROC, n_slots=1)
    spec = WorkerSpec("W00", (ROOM,), (PROC,))
    roster = build_roster([spec], shift_minutes)
    return run, roster


def run_fault_case(bridge, case_id: str, fault_kind: str, fault_start: int, fault_end: int,
                    seed: int, p3c_cfg: Optional[Phase3CConfig] = None,
                    shift_minutes: int = SHIFT_MINUTES, rate_uSv_h: float = RATE_UV_H,
                    frozen_value: Optional[float] = None, claimed_lag_minutes: Optional[int] = None,
                    policy=NO_ROTATION, second_worker: bool = False) -> Dict:
    """Runs one fault-injection sub-case through the real orchestrator,
    capturing the real per-minute sensor-state history, then applying
    the real `evaluate_escalation` to it. `second_worker=True` builds a
    second, independently-faulted worker in a second room (sub-case B8,
    "multiple simultaneous worker faults" -- correct per-worker
    attribution)."""
    cfg = p3c_cfg or load_config()
    run, roster = _single_worker_run(seed, shift_minutes, rate_uSv_h)
    inject_fault(run, ROOM, fault_start, fault_end, fault_kind,
                 frozen_value=frozen_value, claimed_lag_minutes=claimed_lag_minutes)

    second_room = "CT Suite"
    if second_worker:
        run2 = build_single_room_run(seed + 500000, shift_minutes, rate_uSv_h, room=second_room,
                                      procedure_class=PROC, n_slots=1)
        inject_fault(run2, second_room, fault_start, fault_end, fault_kind, frozen_value=frozen_value)
        run["slots_by_room"][second_room] = run2["slots_by_room"][second_room]
        run["exposure_by_slot"].update(run2["exposure_by_slot"])
        run["observations_by_room"][second_room] = run2["observations_by_room"][second_room]
        spec2 = WorkerSpec("W01", (second_room,), (PROC,))
        roster.update(build_roster([spec2], shift_minutes))

    with _SensorHistoryCapture() as cap:
        res = run_policy_on_run(bridge, run, roster, policy, cfg)

    escalations = {}
    for worker_id, states in cap.history.items():
        rec = evaluate_escalation(worker_id, states, shift_minutes, p3c_cfg=cfg)
        escalations[worker_id] = {
            "state": rec.state, "raised_at": rec.raised_at, "resolved_at": rec.resolved_at,
            "resolution_reason": rec.resolution_reason, "audit_log": rec.audit_log,
        }

    return {
        "experiment": "B", "case_id": case_id, "fault_kind": fault_kind,
        "fault_window": [fault_start, fault_end], "seed": seed,
        "sensor_state_history": cap.history,
        "escalation_results": escalations,
        "simulation_result": asdict(res),
    }


# Fault-window and shift parameters chosen so a 10-consecutive-minute
# fault (the default escalate_after_consecutive_fault_minutes) comfortably
# both raises AND (for the "recovery" cases) resolves within the shift.
SUB_CASES_B = [
    {"case_id": "B1", "title": "Missing sensor readings", "fault_kind": "missing",
     "fault_start": 10, "fault_end": 30},
    {"case_id": "B2", "title": "Invalid sensor readings", "fault_kind": "invalid",
     "fault_start": 10, "fault_end": 30},
    {"case_id": "B3", "title": "Frozen sensor readings", "fault_kind": "frozen",
     "fault_start": 10, "fault_end": 30},
    {"case_id": "B4", "title": "Delayed readings (orchestrator-path vs. direct-path comparison)",
     "fault_kind": "delayed", "fault_start": 10, "fault_end": 30, "claimed_lag_minutes": 15},
    {"case_id": "B5", "title": "Repeated faults with recovery between episodes", "fault_kind": "missing",
     "fault_start": 10, "fault_end": 25, "second_episode": (40, 55)},
    {"case_id": "B6", "title": "Fault recovery", "fault_kind": "invalid",
     "fault_start": 10, "fault_end": 25},
    {"case_id": "B7", "title": "Concurrent elevated exposure and sensor fault", "fault_kind": "invalid",
     "fault_start": 10, "fault_end": 30, "elevated_rate": True},
    {"case_id": "B8", "title": "Multiple simultaneous worker faults", "fault_kind": "missing",
     "fault_start": 10, "fault_end": 30, "second_worker": True},
]


EXPERIMENT_B_SEED_BASE = 920000
SEEDS_PER_SUB_CASE = 30


def run_experiment_b(bridge, p3c_cfg: Optional[Phase3CConfig] = None,
                      seeds_per_case: int = SEEDS_PER_SUB_CASE) -> List[Dict]:
    cfg = p3c_cfg or load_config()
    rows = []
    for c_idx, spec in enumerate(SUB_CASES_B):
        for i in range(seeds_per_case):
            seed = EXPERIMENT_B_SEED_BASE + c_idx * 1000 + i
            rate = 400.0 if spec.get("elevated_rate") else RATE_UV_H
            row = run_fault_case(
                bridge, spec["case_id"], spec["fault_kind"], spec["fault_start"], spec["fault_end"],
                seed, cfg, rate_uSv_h=rate, claimed_lag_minutes=spec.get("claimed_lag_minutes"),
                second_worker=spec.get("second_worker", False),
            )
            if "second_episode" in spec:
                # Re-run with a second, independent fault episode after a
                # clean recovery window -- tests RAISED->RESOLVED->RAISED again.
                run, roster = _single_worker_run(seed, SHIFT_MINUTES, RATE_UV_H)
                inject_fault(run, ROOM, spec["fault_start"], spec["fault_end"], spec["fault_kind"])
                inject_fault(run, ROOM, spec["second_episode"][0], spec["second_episode"][1], spec["fault_kind"])
                with _SensorHistoryCapture() as cap:
                    res2 = run_policy_on_run(bridge, run, roster, NO_ROTATION, cfg)
                rec = evaluate_escalation("W00", cap.history["W00"], SHIFT_MINUTES, p3c_cfg=cfg)
                row["second_episode_escalation"] = {
                    "state": rec.state, "audit_log": rec.audit_log,
                }
            row["title"] = spec["title"]
            rows.append(row)
        print(f"  Experiment B {spec['case_id']:4s} ({spec['title']}) -- {seeds_per_case} seeds done")

    # B4's direct comparison: feed the SAME delayed-fault observation
    # directly to sensor_step_once (which DOES honor a caller-supplied
    # ts), vs. what the live orchestrator path actually produced above
    # (which does not -- see simulation.py's own per-minute loop, which
    # extracts only obs["value"]). This is read-only comparison code,
    # not a change to the live orchestrator.
    from ..sensor_validity import new_sensor_state, sensor_step_once
    seed = EXPERIMENT_B_SEED_BASE  # first B4 seed
    run, _ = _single_worker_run(seed, SHIFT_MINUTES, RATE_UV_H)
    inject_fault(run, ROOM, 10, 30, "delayed", claimed_lag_minutes=15)
    prev = new_sensor_state(bridge)
    direct_states = []
    for t, obs in enumerate(run["observations_by_room"][ROOM]):
        if obs is None:
            step = sensor_step_once(bridge, prev, None, t)
        else:
            step = bridge.evaluate(
                "(args) => AlaradSafety.sensorStep(args.prev, args.obs, args.t, null)",
                {"prev": prev, "obs": {"ts": obs["ts"], "value": obs["value"]}, "t": t},
            )
        prev = step["s"]
        direct_states.append(step["state"])
    rows.append({
        "experiment": "B", "case_id": "B4_direct_path_comparison",
        "title": "Delayed-fault ts handling: direct sensor_step_once (honors claimed stale ts) vs. live orchestrator path (discards it, uses current t)",
        "seed": seed, "direct_path_states": direct_states,
    })
    return rows
