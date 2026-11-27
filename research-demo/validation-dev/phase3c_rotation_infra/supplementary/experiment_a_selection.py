"""
Experiment A -- multi-candidate worker selection (final supplementary
validation round, section 2). Ten controlled sub-cases, each built so
that the dose-threshold trigger (clause (a), the same real
`evaluate_dose_threshold_trigger` CGDTR and reference-rule both call,
unchanged) fires reliably and deterministically, and the candidate
pool's eligibility/dose pattern is exactly controlled rather than left
to chance -- directly answering the audit's finding that only 4 of
1,005 real-campaign trigger events ever had >=2 eligible candidates.

Each sub-case is run through the real `simulation.run_policy_on_run`
orchestrator, unmodified, for all 5 policies
(no_rotation/fixed_interval/reference_rule/ablation_d/cgdtr).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from ..config import Phase3CConfig, load_config
from ..policies import ALL_POLICIES
from ..simulation import run_policy_on_run
from .controlled_builders import (
    DEFAULT_PROCEDURE_CLASS, DEFAULT_ROOM, WorkerSpec, build_roster, build_single_room_run,
)

ROOM = DEFAULT_ROOM
PROC = DEFAULT_PROCEDURE_CLASS
SHIFT_MINUTES = 120  # boundaries at 0,30,60,90,120 with n_slots=4
RATE_UV_H = 150.0  # moderate rate; doesn't by itself cross the dose threshold within one 30-min slot

# threshold_a = rotation_threshold_fraction(0.5) * reference_level_mSv_per_shift(0.1) = 0.05 mSv
ABOVE_THRESHOLD = 0.08
BELOW_THRESHOLD = 0.0


@dataclass(frozen=True)
class SubCase:
    case_id: str
    title: str
    hypothesis: str
    worker_specs: List[WorkerSpec]
    expect_eligible_ge2: bool
    expect_cgdtr_ref_diverge: Optional[bool]  # None = not determinate/not the point of this case
    notes: str = ""


def _w(worker_id, dose=0.0, max_dose=5.0, rotations_so_far=0, max_rotations=3,
       state="FREE", credentialed=True, availability=None):
    from ..staffing import FREE
    return WorkerSpec(
        worker_id=worker_id,
        credentialed_rooms=(ROOM,) if credentialed else (),
        credentialed_procedure_classes=(PROC,) if credentialed else (),
        cumulative_dose_mSv=dose,
        max_dose_per_shift_mSv=max_dose,
        rotations_so_far=rotations_so_far,
        max_rotations_per_shift=max_rotations,
        state=state,
        availability_windows=availability,
    )


def build_sub_cases() -> List[SubCase]:
    cases = []

    # A1: two eligible candidates, unequal doses, lowest-dose NOT the
    # lowest worker_id -- the single cleanest test of whether the two
    # selection rules CAN diverge.
    cases.append(SubCase(
        "A1", "Two eligible candidates, unequal doses",
        "CGDTR picks the lower-dose W02; reference-rule picks W01 (first by ID) -- they MUST diverge here if selection logic works.",
        [_w("W00", dose=ABOVE_THRESHOLD), _w("W01", dose=0.03), _w("W02", dose=0.01)],
        expect_eligible_ge2=True, expect_cgdtr_ref_diverge=True,
    ))

    # A2: three or more eligible candidates, unequal doses.
    cases.append(SubCase(
        "A2", "Three eligible candidates, unequal doses",
        "CGDTR picks the globally lowest-dose candidate (W02); reference-rule picks W01.",
        [_w("W00", dose=ABOVE_THRESHOLD), _w("W01", dose=0.04), _w("W02", dose=0.01), _w("W03", dose=0.02)],
        expect_eligible_ge2=True, expect_cgdtr_ref_diverge=True,
    ))

    # A3: equal doses -> deterministic tie-break must agree with reference-rule.
    cases.append(SubCase(
        "A3", "Equal accumulated doses -> deterministic tie-break",
        "Both W01 and W02 are tied at 0.02 mSv; CGDTR's (dose, worker_id) sort and reference-rule's worker_id-only sort both pick W01 -- NOT a divergence, by design of the tie-break rule.",
        [_w("W00", dose=ABOVE_THRESHOLD), _w("W01", dose=0.02), _w("W02", dose=0.02)],
        expect_eligible_ge2=True, expect_cgdtr_ref_diverge=False,
        notes="This reproduces, under controlled conditions, the exact tie-break collapse the audit found in all 4 real-campaign multi-candidate events.",
    ))

    # A4: lowest-dose worker unavailable for the needed interval.
    cases.append(SubCase(
        "A4", "Lowest-dose worker unavailable",
        "W02 has the lowest dose (0.01) but its availability window excludes the handoff interval, so it is filtered out upstream of ranking; CGDTR then picks the lowest-dose ELIGIBLE candidate (W03=0.02), reference-rule picks W01 (first eligible by ID). Divergence driven by correct exclusion, not by ranking alone.",
        [_w("W00", dose=ABOVE_THRESHOLD), _w("W01", dose=0.03),
         _w("W02", dose=0.01, availability=[(0, 20)]),  # window ends before any rotation can complete
         _w("W03", dose=0.02)],
        expect_eligible_ge2=True, expect_cgdtr_ref_diverge=True,
    ))

    # A5: lowest-dose worker ineligible due to credentials.
    cases.append(SubCase(
        "A5", "Lowest-dose worker not credentialed",
        "W02 has the lowest dose (0.01) but is not credentialed for this room/procedure, so it never enters the candidate pool at all (simulation.py's own upstream credential filter). CGDTR picks W03 (0.02), reference-rule picks W01.",
        [_w("W00", dose=ABOVE_THRESHOLD), _w("W01", dose=0.03),
         _w("W02", dose=0.01, credentialed=False), _w("W03", dose=0.02)],
        expect_eligible_ge2=True, expect_cgdtr_ref_diverge=True,
    ))

    # A6: lowest-dose worker ineligible due to duty limits (max_rotations_so_far reached).
    cases.append(SubCase(
        "A6", "Lowest-dose worker at duty-limit cap",
        "W02 has the lowest dose (0.01) but has already used all 3 of its allowed rotations this shift, so assignment.batch_resolve excludes it (section 3g step 6). CGDTR picks W03 (0.02), reference-rule picks W01.",
        [_w("W00", dose=ABOVE_THRESHOLD), _w("W01", dose=0.03),
         _w("W02", dose=0.01, rotations_so_far=3, max_rotations=3), _w("W03", dose=0.02)],
        expect_eligible_ge2=True, expect_cgdtr_ref_diverge=True,
    ))

    # A7: lowest-dose worker busy in another required assignment (not FREE).
    cases.append(SubCase(
        "A7", "Lowest-dose worker occupied elsewhere (not FREE)",
        "W02 has the lowest dose (0.01) but starts the shift ASSIGNED (representing occupancy in another room this single-room experiment does not itself model) and is therefore never FREE/eligible for this room's rotation. CGDTR picks W03 (0.02), reference-rule picks W01.",
        [_w("W00", dose=ABOVE_THRESHOLD), _w("W01", dose=0.03),
         _w("W02", dose=0.01, state="ASSIGNED"), _w("W03", dose=0.02)],
        expect_eligible_ge2=True, expect_cgdtr_ref_diverge=True,
    ))

    # A8: sequential rotations -- doses evolve, candidate pool membership changes over time.
    cases.append(SubCase(
        "A8", "Sequential rotations with evolving accumulated doses",
        "W00 triggers at t=30 (dose preset above threshold); the winner is reassessed at t=60 once W00 (now RESTING->FREE, with its own newly-accrued dose from the first rotation) becomes a candidate again, alongside a freshly-primed W03 (dose preset above threshold to trigger again at t=60). Tests that ranking correctly uses CURRENT, not initial, accumulated dose.",
        [_w("W00", dose=ABOVE_THRESHOLD), _w("W01", dose=0.03), _w("W02", dose=0.01),
         _w("W03", dose=ABOVE_THRESHOLD, max_rotations=1)],
        expect_eligible_ge2=True, expect_cgdtr_ref_diverge=None,
        notes="Multi-trigger case; min_rest_between_assignments_minutes must be short enough that W00 is FREE again before t=60.",
    ))

    # A9: greedy (myopic) selection vs. a simple lookahead counterfactual.
    cases.append(SubCase(
        "A9", "Greedy selection is locally but not necessarily globally optimal",
        "W02 (lowest current dose) has a much lower max_dose_per_shift_mSv cap than W01, so assigning it now (CGDTR's myopic choice) uses up proportionally more of ITS OWN duty-limit headroom than assigning W01 would. This case does not change the algorithm -- it runs the real CGDTR choice and separately reports what a simple lookahead heuristic (minimize post-assignment dose AS A FRACTION OF max_dose_per_shift_mSv, not absolute dose) would have chosen instead, as an external, clearly-labeled analytical comparison.",
        [_w("W00", dose=ABOVE_THRESHOLD), _w("W01", dose=0.03, max_dose=5.0),
         _w("W02", dose=0.01, max_dose=0.5)],
        expect_eligible_ge2=True, expect_cgdtr_ref_diverge=True,
    ))

    # A10: no safe replacement exists at all.
    cases.append(SubCase(
        "A10", "No safe replacement exists",
        "Every other credentialed worker is excluded (busy, duty-limited, or unavailable) -- the trigger must report INFEASIBLE, not silently skip or fabricate a candidate.",
        [_w("W00", dose=ABOVE_THRESHOLD),
         _w("W01", dose=0.03, state="ASSIGNED"),
         _w("W02", dose=0.01, rotations_so_far=3, max_rotations=3),
         _w("W03", dose=0.02, credentialed=False)],
        expect_eligible_ge2=False, expect_cgdtr_ref_diverge=False,
    ))

    return cases


# Per-case timeline override: (shift_minutes, n_slots). A8 is the
# explicit "sequential rotations" case and needs a longer multi-boundary
# timeline; every other case is a single, clean, one-decision test.
TIMELINE_OVERRIDES: Dict[str, Tuple[int, int]] = {
    "A8": (240, 8),
}


def run_sub_case(bridge, case: SubCase, seed: int, p3c_cfg: Optional[Phase3CConfig] = None,
                  shift_minutes: Optional[int] = None, rate_uSv_h: float = RATE_UV_H,
                  n_slots: Optional[int] = None) -> Dict:
    cfg = p3c_cfg or load_config()
    override = TIMELINE_OVERRIDES.get(case.case_id, (SHIFT_MINUTES, 4))
    shift_minutes = shift_minutes if shift_minutes is not None else override[0]
    n_slots = n_slots if n_slots is not None else override[1]
    run = build_single_room_run(seed, shift_minutes, rate_uSv_h, room=ROOM,
                                 procedure_class=PROC, n_slots=n_slots)
    results = {}
    for policy in ALL_POLICIES:
        roster = build_roster(case.worker_specs, shift_minutes)
        res = run_policy_on_run(bridge, run, roster, policy, cfg)
        results[policy.name] = res
    return results


# Seed base disjoint from every other block used in this project:
# design set 20260601-13, Phase 3A smoke 3001-3008, Phase 3A campaign
# 90000+, Phase 3C-B campaign 700000+, sensitivity 850000+.
EXPERIMENT_A_SEED_BASE = 910000
SEEDS_PER_SUB_CASE = 30  # matches this project's own established minimum (ICAIRE_Simulation_Validation_Methodology.md section 7/8); justified, not merely convenient, by reuse of the same precision rationale already accepted for the main campaign.


def run_experiment_a(bridge, p3c_cfg: Optional[Phase3CConfig] = None,
                      seeds_per_case: int = SEEDS_PER_SUB_CASE) -> List[Dict]:
    """Runs every sub-case x every seed x all 5 policies; returns one
    flat list of per-run records (JSON-serializable)."""
    from dataclasses import asdict
    cfg = p3c_cfg or load_config()
    cases = build_sub_cases()
    rows = []
    for c_idx, case in enumerate(cases):
        for i in range(seeds_per_case):
            seed = EXPERIMENT_A_SEED_BASE + c_idx * 1000 + i
            results = run_sub_case(bridge, case, seed, cfg)
            per_policy = {name: asdict(res) for name, res in results.items()}
            rows.append({
                "experiment": "A", "case_id": case.case_id, "title": case.title,
                "seed": seed, "expect_eligible_ge2": case.expect_eligible_ge2,
                "expect_cgdtr_ref_diverge": case.expect_cgdtr_ref_diverge,
                "policies": per_policy,
            })
        print(f"  Experiment A {case.case_id:4s} ({case.title}) -- {seeds_per_case} seeds done")
    return rows
