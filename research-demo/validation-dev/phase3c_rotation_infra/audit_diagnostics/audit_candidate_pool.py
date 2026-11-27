"""
Read-only audit diagnostic (not part of the committed codebase): for
every trigger event CGDTR would fire in the real campaign (same seeds,
same roster-generation call as run_campaign.py), record:
  - size of the credentialed candidate pool BEFORE eligibility filtering
    (what simulation.py builds and hands to rank_candidates)
  - how many of those are actually eligible per assignment.batch_resolve's
    own filter (FREE, not resting, within availability, not duty-limited)
  - whether CGDTR's lowest-dose ranking and reference-rule's worker-id
    ranking would pick a DIFFERENT eligible winner, among just the
    eligible subset

No source file is modified. assignment.batch_resolve is wrapped (not
edited) to additionally record per-candidate eligibility without
changing its decision logic at all -- same inputs, same outputs, same
side effects (RESERVED is still set on the same winner it would have
picked unwrapped).
"""
import sys, json
sys.path.insert(0, "/home/user/alarad-med/research-demo/validation-dev")

from phase1_simulator import config as p1_config_mod
from phase1_simulator.scenario import ROOMS
from pathlib import Path

from phase2a_adapter.engine_bridge import EngineBridge
from phase3c_rotation_infra.campaign_scenarios import build_campaign_run
from phase3c_rotation_infra.config import load_config
from phase3c_rotation_infra.staffing import generate_roster, FREE
from phase3c_rotation_infra.policies import CGDTR, REFERENCE_RULE, rank_candidates
from phase3c_rotation_infra import assignment as assignment_mod
from phase3c_rotation_infra import simulation as simulation_mod

P1_CONFIG_PATH = Path(p1_config_mod.__file__).parent / "config" / "simulation_config.json"
PROCEDURE_CLASSES = ["diagnostic_fluoroscopy", "interventional_cath_lab", "ct", "pet_ct"]
SEED_BASE = 700000
ARCHETYPES = ["normal", "gradual_increase", "sudden_increase", "transient_spike", "area_relocation",
              "multi_worker_mixed", "fault_missing", "fault_invalid", "fault_frozen", "fault_delayed",
              "fault_during_event", "multi_worker_faults", "concurrent_alert_and_fault"]

diag = {"n_triggers": 0, "pool_sizes": [], "eligible_counts": [], "would_differ": 0,
        "eligible_ge2_examples": []}

_orig_batch_resolve = assignment_mod.batch_resolve

def wrapped_batch_resolve(requests, roster, t_decide, t_effective_by_room, intended_assignment_minutes_by_room=None):
    for req in requests:
        # Recreate the SAME eligibility filter batch_resolve itself applies,
        # read-only, just to count -- not altering any state here.
        t_eff = t_effective_by_room.get(req.room)
        intended_minutes = (intended_assignment_minutes_by_room or {}).get(req.room)
        from phase3c_rotation_infra.dose_quantities import projected_shift_total_dose_mSv
        eligible = []
        for cand_id in req.candidate_order:
            w = roster.get(cand_id)
            if w is None: continue
            if w.state != FREE: continue
            if w.is_resting_at(t_decide): continue
            if w.rotations_so_far >= w.max_rotations_per_shift: continue
            if t_eff is not None and not w.is_within_availability_interval(t_decide, t_eff): continue
            if intended_minutes is not None:
                projected = projected_shift_total_dose_mSv(w, intended_minutes / 60.0)
                if projected is not None and projected >= w.max_dose_per_shift_mSv:
                    continue
            eligible.append(cand_id)
        diag["n_triggers"] += 1
        diag["pool_sizes"].append(len(req.candidate_order))
        diag["eligible_counts"].append(len(eligible))
        if len(eligible) >= 2:
            ranked_cgdtr = rank_candidates(CGDTR, roster, list(eligible))
            ranked_ref = rank_candidates(REFERENCE_RULE, roster, list(eligible))
            if ranked_cgdtr[0] != ranked_ref[0]:
                diag["would_differ"] += 1
            diag["eligible_ge2_examples"].append({
                "room": req.room, "t": t_decide, "eligible": eligible,
                "doses": {c: round(roster[c].cumulative_dose_mSv, 6) for c in eligible},
                "cgdtr_top": ranked_cgdtr[0], "ref_top": ranked_ref[0],
            })
    return _orig_batch_resolve(requests, roster, t_decide, t_effective_by_room, intended_assignment_minutes_by_room)

assignment_mod.batch_resolve = wrapped_batch_resolve
simulation_mod.assignment_mod.batch_resolve = wrapped_batch_resolve

p1_cfg = p1_config_mod.load_config(P1_CONFIG_PATH)
p3c_cfg = load_config()

with EngineBridge() as bridge:
    for a_idx, archetype in enumerate(ARCHETYPES):
        for i in range(30):
            seed = SEED_BASE + a_idx * 1000 + i
            run = build_campaign_run(seed, archetype, p1_cfg, p3c_cfg)
            n_rooms = len(run["slots_by_room"])
            roster = {w.worker_id: w for w in generate_roster(
                seed, run["shift_minutes"], n_rooms + 1, ROOMS, PROCEDURE_CLASSES, p3c_cfg)}
            simulation_mod.run_policy_on_run(bridge, run, roster, CGDTR, p3c_cfg)
        print(f"done: {archetype} (roster size for n_rooms={n_rooms}: {len(roster)})")

print(json.dumps({
    "n_triggers": diag["n_triggers"],
    "pool_size_hist": {str(k): diag["pool_sizes"].count(k) for k in sorted(set(diag["pool_sizes"]))},
    "eligible_count_hist": {str(k): diag["eligible_counts"].count(k) for k in sorted(set(diag["eligible_counts"]))},
    "n_eligible_ge2": sum(1 for e in diag["eligible_counts"] if e >= 2),
    "would_differ_among_ge2": diag["would_differ"],
}, indent=2))

with open("/tmp/claude-0/-home-user-ALARAD-radiation-safety/e34bb4d9-0a73-5ad3-96ae-c81f2cb01e05/scratchpad/eligible_ge2_examples.json", "w") as f:
    json.dump(diag["eligible_ge2_examples"][:20], f, indent=2)
