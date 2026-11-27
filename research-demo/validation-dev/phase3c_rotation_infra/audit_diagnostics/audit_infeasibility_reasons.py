"""
Read-only diagnostic #2: for CGDTR's 985 INFEASIBLE trigger events,
classify WHY EVERY candidate in the credentialed pool was rejected
(first failing check, in the same order batch_resolve itself checks),
aggregated by constraint and by archetype. No source file modified;
assignment.batch_resolve is wrapped only to additionally classify.
"""
import sys, json, collections
sys.path.insert(0, "/home/user/alarad-med/research-demo/validation-dev")

from pathlib import Path
from phase1_simulator import config as p1_config_mod
from phase1_simulator.scenario import ROOMS
from phase2a_adapter.engine_bridge import EngineBridge
from phase3c_rotation_infra.campaign_scenarios import build_campaign_run
from phase3c_rotation_infra.config import load_config
from phase3c_rotation_infra.staffing import generate_roster, FREE
from phase3c_rotation_infra.dose_quantities import projected_shift_total_dose_mSv
from phase3c_rotation_infra import assignment as assignment_mod
from phase3c_rotation_infra import simulation as simulation_mod
from phase3c_rotation_infra.policies import CGDTR

P1_CONFIG_PATH = Path(p1_config_mod.__file__).parent / "config" / "simulation_config.json"
PROCEDURE_CLASSES = ["diagnostic_fluoroscopy", "interventional_cath_lab", "ct", "pet_ct"]
SEED_BASE = 700000
ARCHETYPES = ["normal", "gradual_increase", "sudden_increase", "transient_spike", "area_relocation",
              "multi_worker_mixed", "fault_missing", "fault_invalid", "fault_frozen", "fault_delayed",
              "fault_during_event", "multi_worker_faults", "concurrent_alert_and_fault"]

reason_counts = collections.Counter()          # per-CANDIDATE first-failing-reason, across all trigger events
reason_by_archetype = collections.defaultdict(collections.Counter)
infeasible_root_cause = collections.Counter()  # per-TRIGGER, classifying the infeasible event itself
infeasible_root_cause_by_archetype = collections.defaultdict(collections.Counter)
current_archetype = [None]

def classify(w, t_decide, t_eff, intended_minutes):
    if w.state != FREE:
        return "not_free_" + w.state.lower()  # e.g. not_free_assigned, not_free_resting(shouldn't happen, RESTING is separate state actually used), not_free_reserved
    if w.is_resting_at(t_decide):
        return "resting_min_rest_not_elapsed"
    if w.rotations_so_far >= w.max_rotations_per_shift:
        return "duty_limit_max_rotations_reached"
    if t_eff is not None and not w.is_within_availability_interval(t_decide, t_eff):
        return "availability_window_insufficient"
    if intended_minutes is not None:
        projected = projected_shift_total_dose_mSv(w, intended_minutes / 60.0)
        if projected is not None and projected >= w.max_dose_per_shift_mSv:
            return "duty_limit_projected_dose_exceeded"
    return "eligible"

_orig_batch_resolve = assignment_mod.batch_resolve

def wrapped_batch_resolve(requests, roster, t_decide, t_effective_by_room, intended_assignment_minutes_by_room=None):
    for req in requests:
        t_eff = t_effective_by_room.get(req.room)
        intended_minutes = (intended_assignment_minutes_by_room or {}).get(req.room)
        per_candidate = []
        for cand_id in req.candidate_order:
            w = roster.get(cand_id)
            if w is None:
                continue
            reason = classify(w, t_decide, t_eff, intended_minutes)
            per_candidate.append(reason)
            reason_counts[reason] += 1
            reason_by_archetype[current_archetype[0]][reason] += 1
        n_credentialed = len(req.candidate_order)
        n_eligible = per_candidate.count("eligible")
        if n_credentialed == 0:
            root = "no_credentialed_candidate_at_all"
        elif n_eligible == 0:
            # classify by the single MOST COMMON blocking reason among this trigger's candidates
            blockers = collections.Counter(r for r in per_candidate if r != "eligible")
            root = "all_blocked:" + blockers.most_common(1)[0][0] if blockers else "unknown"
        else:
            root = "had_eligible_candidate"
        infeasible_root_cause[root] += 1
        infeasible_root_cause_by_archetype[current_archetype[0]][root] += 1
    return _orig_batch_resolve(requests, roster, t_decide, t_effective_by_room, intended_assignment_minutes_by_room)

assignment_mod.batch_resolve = wrapped_batch_resolve
simulation_mod.assignment_mod.batch_resolve = wrapped_batch_resolve

p1_cfg = p1_config_mod.load_config(P1_CONFIG_PATH)
p3c_cfg = load_config()

with EngineBridge() as bridge:
    for a_idx, archetype in enumerate(ARCHETYPES):
        current_archetype[0] = archetype
        for i in range(30):
            seed = SEED_BASE + a_idx * 1000 + i
            run = build_campaign_run(seed, archetype, p1_cfg, p3c_cfg)
            n_rooms = len(run["slots_by_room"])
            roster = {w.worker_id: w for w in generate_roster(
                seed, run["shift_minutes"], n_rooms + 1, ROOMS, PROCEDURE_CLASSES, p3c_cfg)}
            simulation_mod.run_policy_on_run(bridge, run, roster, CGDTR, p3c_cfg)
        print(f"done: {archetype}")

print("=== per-candidate first-failing-reason (all trigger events, all candidates) ===")
print(json.dumps(dict(reason_counts.most_common()), indent=2))
print()
print("=== per-trigger root cause (why the TRIGGER as a whole was infeasible, or had an eligible candidate) ===")
print(json.dumps(dict(infeasible_root_cause.most_common()), indent=2))
print()
print("=== root cause by archetype ===")
for arch, c in infeasible_root_cause_by_archetype.items():
    print(arch, dict(c))

with open("/tmp/claude-0/-home-user-ALARAD-radiation-safety/e34bb4d9-0a73-5ad3-96ae-c81f2cb01e05/scratchpad/infeasibility_breakdown.json", "w") as f:
    json.dump({
        "per_candidate_reason": dict(reason_counts),
        "per_trigger_root_cause": dict(infeasible_root_cause),
        "root_cause_by_archetype": {k: dict(v) for k, v in infeasible_root_cause_by_archetype.items()},
    }, f, indent=2)
