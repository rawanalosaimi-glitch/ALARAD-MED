"""
CGDTR and the four baseline/ablation policies (task 2/3 of this round;
PHASE3B_ROTATION_ALGORITHM_DESIGN.md section 3a/3b/3c, section 6/6a) --
trigger and selection logic ONLY. Scheduling, reservation, and dose/
sensor runtime state are implemented elsewhere (`assignment.py`,
`scheduling.py`, `dose_quantities.py`, `runtime.py`); this module
decides WHICH worker and WHEN, nothing about HOW a rotation actually
executes once decided.

All five policies share the exact same eligibility filter
(`assignment.batch_resolve`), handoff timeline (`scheduling.py`),
incident/escalation mechanics -- only the trigger (when to propose) and
selection (who to pick) differ, per policy, exactly as
PHASE3B_ROTATION_ALGORITHM_DESIGN.md section 6b's shared-conditions
guarantee requires.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from phase2a_adapter.engine_bridge import EngineBridge

from .config import Phase3CConfig
from .dose_quantities import (
    engine_projected_task_dose_mSv,
    projected_shift_total_dose_mSv,
    worker_accumulated_shift_dose_mSv,
)
from .sensor_validity import TRUSTED_FOR_TRIGGER
from .staffing import WorkerProfile

TRIGGER_DOSE_THRESHOLD = "dose_threshold"
TRIGGER_FIXED_INTERVAL = "fixed_interval"
TRIGGER_NEVER = "never"

SELECTION_LOWEST_DOSE = "lowest_dose"
SELECTION_FIRST_IN_ORDER = "first_in_order"
SELECTION_NONE = "none"


@dataclass(frozen=True)
class PolicySpec:
    name: str
    trigger: str
    selection: str


# The candidate (section 3): dose-threshold trigger, lowest-dose-ranked selection.
CGDTR = PolicySpec("cgdtr", TRIGGER_DOSE_THRESHOLD, SELECTION_LOWEST_DOSE)
# ROTATION_RECOMMENDER_DESIGN_SPEC.md section 4.1: never triggers.
NO_ROTATION = PolicySpec("no_rotation", TRIGGER_NEVER, SELECTION_NONE)
# section 4.2: timer-based trigger, lowest-dose-ranked selection (same selection as CGDTR).
FIXED_INTERVAL = PolicySpec("fixed_interval", TRIGGER_FIXED_INTERVAL, SELECTION_LOWEST_DOSE)
# section 4.3 / section 6a: SAME dose-threshold trigger as CGDTR, first-eligible selection.
REFERENCE_RULE = PolicySpec("reference_rule", TRIGGER_DOSE_THRESHOLD, SELECTION_FIRST_IN_ORDER)
# PHASE3B section 6a: completes the 2x2 -- NOT a plausible real-world baseline,
# exists only so trigger-effect and selection-effect can be estimated as
# independent main effects.
ABLATION_D = PolicySpec("ablation_d", TRIGGER_FIXED_INTERVAL, SELECTION_FIRST_IN_ORDER)

ALL_POLICIES: List[PolicySpec] = [NO_ROTATION, FIXED_INTERVAL, REFERENCE_RULE, ABLATION_D, CGDTR]
POLICIES_BY_NAME: Dict[str, PolicySpec] = {p.name: p for p in ALL_POLICIES}


@dataclass(frozen=True)
class TriggerContext:
    room: str
    worker: WorkerProfile
    t: int
    remaining_minutes_in_slot: int
    procedure_class: str
    proc_mult: float


@dataclass(frozen=True)
class TriggerOutcome:
    fired: bool
    clause: Optional[str] = None  # "a" | "b" | "c" | "interval"


def evaluate_dose_threshold_trigger(bridge: EngineBridge, ctx: TriggerContext,
                                     cfg: Phase3CConfig, engine_config: Dict) -> TriggerOutcome:
    """PHASE3B_ROTATION_ALGORITHM_DESIGN.md section 3a (Revision 3)'s
    three-clause trigger, used identically by CGDTR and the reference-
    rule baseline (section 6's shared-trigger ablation design). Clauses
    are checked in order (a)/(b)/(c); the first that fires is returned
    -- a worker triggering on multiple clauses simultaneously is
    reported as whichever is checked first, which is sufficient for
    this round's purposes (clause-specific rates are still reported
    accurately in aggregate; see the campaign's own per-clause counts)."""
    w = ctx.worker
    trig_cfg = cfg.block("cgdtr_trigger")

    accrued = worker_accumulated_shift_dose_mSv(w)
    threshold_a = trig_cfg["rotation_threshold_fraction"] * trig_cfg["reference_level_mSv_per_shift"]
    if accrued >= threshold_a:
        return TriggerOutcome(True, "a")

    if w.sensor_state_label in TRUSTED_FOR_TRIGGER and w.last_valid_rate_uSv_h is not None:
        engine_dose = engine_projected_task_dose_mSv(
            bridge, ctx.room, ctx.proc_mult, w.last_valid_rate_uSv_h)
        if engine_dose is not None and engine_dose >= engine_config["CONFIG"]["doseElevated"]:
            return TriggerOutcome(True, "b")

    if w.last_valid_rate_uSv_h is not None:
        horizon_hours = ctx.remaining_minutes_in_slot / 60.0
        projected = projected_shift_total_dose_mSv(w, horizon_hours)
        if projected is not None and projected >= w.max_dose_per_shift_mSv:
            return TriggerOutcome(True, "c")

    return TriggerOutcome(False, None)


def evaluate_fixed_interval_trigger(t: int, fixed_interval_minutes: int) -> TriggerOutcome:
    """ROTATION_RECOMMENDER_DESIGN_SPEC.md section 4.2: fires at every
    boundary that falls on a multiple of `fixed_interval_minutes`. `t=0`
    never fires (nothing to rotate out of yet)."""
    if t > 0 and t % fixed_interval_minutes == 0:
        return TriggerOutcome(True, "interval")
    return TriggerOutcome(False, None)


def evaluate_trigger(policy: PolicySpec, bridge: EngineBridge, ctx: TriggerContext,
                      cfg: Phase3CConfig, engine_config: Dict) -> TriggerOutcome:
    """Dispatches to the right trigger function for this policy. Both
    CGDTR and the reference-rule baseline share
    `evaluate_dose_threshold_trigger` unchanged; both fixed-interval and
    Ablation D share `evaluate_fixed_interval_trigger` unchanged --
    section 6b's shared-conditions guarantee, enforced here by sharing
    the same function object, not just the same formula restated twice."""
    if policy.trigger == TRIGGER_NEVER:
        return TriggerOutcome(False, None)
    if policy.trigger == TRIGGER_FIXED_INTERVAL:
        fixed_interval_minutes = cfg.block("fixed_interval_baseline")["fixed_interval_minutes"]
        return evaluate_fixed_interval_trigger(ctx.t, fixed_interval_minutes)
    if policy.trigger == TRIGGER_DOSE_THRESHOLD:
        return evaluate_dose_threshold_trigger(bridge, ctx, cfg, engine_config)
    raise ValueError(f"unknown trigger kind: {policy.trigger!r}")


def rank_candidates(policy: PolicySpec, roster: Dict[str, WorkerProfile],
                     candidate_ids: List[str]) -> List[str]:
    """Section 3c (lowest-dose-ranked) vs. section 6.3 (first-eligible-
    in-roster-order), shared identically between the policies that use
    each (CGDTR/fixed-interval share lowest-dose; reference-rule/
    Ablation D share first-in-order). `candidate_ids` is expected
    pre-sorted by ascending `worker_id` by the caller (the roster's own
    natural order) -- this function only re-sorts for the lowest-dose
    case; for first-in-order it returns the input order unchanged."""
    if policy.selection == SELECTION_LOWEST_DOSE:
        return sorted(candidate_ids,
                      key=lambda wid: (worker_accumulated_shift_dose_mSv(roster[wid]), wid))
    if policy.selection == SELECTION_FIRST_IN_ORDER:
        return sorted(candidate_ids)
    if policy.selection == SELECTION_NONE:
        return []
    raise ValueError(f"unknown selection kind: {policy.selection!r}")
