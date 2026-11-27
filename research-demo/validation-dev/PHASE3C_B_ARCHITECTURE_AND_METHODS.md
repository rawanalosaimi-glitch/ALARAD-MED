# Phase 3C-B — CGDTR Implementation: Architecture, Pseudocode, and Methods

**Status: implementation documentation for code that has been written,
tested, and run this round** (distinct from `PHASE3B_ROTATION_ALGORITHM_DESIGN.md`,
which remains the design specification this implementation follows).
Covers the five infrastructure-gap closures, CGDTR, the four
baseline/ablation policies, and the campaign/analysis scripts. The
frozen v1.2.3 release was not modified.

---

## 1. Package layout

```
phase3c_rotation_infra/
  staffing.py             WorkerProfile (+ live state fields added this round)
  exposure_layer.py        AssignmentSlot (+ remaining_minutes() helper, gap 5)
  sensor_validity.py        per-minute/batched real-engine sensorStep queries (gaps 1/4)
  dose_quantities.py        the three section 3a quantities (EngineProjectedTaskDose,
                            WorkerAccumulatedShiftDose, ProjectedShiftTotalDose)
  runtime.py                live per-minute dose/sensor state updates (gap 2)
  assignment.py              worker exclusivity + atomic batch reservation
                            (+ duty-limit exclusion, gap 3)
  scheduling.py              T_decide -> T_ready -> T_effective timeline,
                            PROPOSED/PENDING/HELD/COMPLETED/ABORTED/INFEASIBLE
  policies.py                CGDTR + 4 baseline/ablation policies: trigger + selection
  campaign_scenarios.py      reuses Phase 1's 13 archetypes, repurposed as room-tracks
  simulation.py               the live per-minute orchestrator (ties everything together)
  run_campaign.py             the campaign runner (13 archetypes x N seeds x 5 policies)
  run_sensitivity.py          parameter sensitivity sweeps (separate seed block)
  dose_attribution.py         (Phase 3C-A) individual/collective dose, conservation check
  escalation.py               (Phase 3C-A) sensor-fault-persistence escalation
  config.py / config/phase3c_config.json   all provisional parameters, centralized
  tests/                      109 tests (see PHASE3C_B_TEST_EVIDENCE.md)

Top-level (research-demo/validation-dev/):
  stats_common.py                     bootstrap CI, paired Wilcoxon, Holm-Bonferroni
  analyze_rotation_campaign.py          statistical analysis of the rotation campaign
  generate_figures.py                   figure generation from campaign/analysis JSON
  phase3a_forecasting/run_phase3a_statistical_campaign.py   balanced forecasting campaign
```

---

## 2. The three dose quantities (exact formulas, units, ownership)

Reused verbatim from `PHASE3B_ROTATION_ALGORITHM_DESIGN.md` section 3a
(Revision 3); implemented in `dose_quantities.py`:

| Quantity | Formula | Units | Owner |
|---|---|---|---|
| `EngineProjectedTaskDose(W,t)` | the real `evaluateExposure()`'s own `.cumulativeDose` field = `rate(t) x (30/60) / 1000` | mSv | frozen engine (`CONFIG.doseElevated`/`doseCritical`) |
| `WorkerAccumulatedShiftDose(W,t)` | `Σ Dose(mSv)` from shift start through `t` | mSv | this project (`rotation_threshold_fraction x reference_level_mSv_per_shift`) |
| `ProjectedShiftTotalDose(W,t,h)` | `WorkerAccumulatedShiftDose(W,t) + rate_last_valid(W) x h / 1000` | mSv | this project's own staffing model (`W.max_dose_per_shift_mSv`) |

**Dose increment formula, reused unchanged throughout:**
`Dose (mSv) = Rate (uSv/h) x Duration (h) / 1000` (`phase1_simulator.units.dose_increment_mSv`).

---

## 3. CGDTR trigger and selection -- pseudocode

```
at every procedure boundary t for room R, currently occupied by worker W:

  TRIGGER (any clause fires -> propose a rotation):
    (a) WorkerAccumulatedShiftDose(W, t) >= rotation_threshold_fraction * reference_level_mSv_per_shift
    (b) if W.sensor_state == HEALTHY and W.last_valid_rate is not None:
          EngineProjectedTaskDose(W, t) >= CONFIG.doseElevated     # real evaluateExposure() call
    (c) if W.last_valid_rate is not None:
          h = remaining_minutes(upcoming_slot, t) / 60
          ProjectedShiftTotalDose(W, t, h) >= W.max_dose_per_shift_mSv

  if no clause fires: no rotation (ordinary case)

  else:
    candidates = [every OTHER worker credentialed for R's room+procedure_class]
    ranked = SELECTION(candidates)               # policy-specific, below
    request = RotationRequest(R, W, ranked)
    # batched, atomic, across every room triggering at this same t:
    outcome = assignment.batch_resolve([request, ...other rooms' requests...])
    if outcome is INFEASIBLE: log infeasible; track consecutive-infeasible per room
    else:
      attempt = scheduling.start_attempt(...)      # computes T_ready, T_effective
      if attempt is INFEASIBLE (no boundary before shift end): release reservation; log
      else: pending_attempts[R] = attempt           # resolved later, at T_effective

at every minute t where a pending attempt's T_effective == t:
  if outgoing or incoming worker's sensor state is FLAGGED: HELD (incident open)
  else: COMPLETE -- swap occupant, mark outgoing RESTING, incoming ASSIGNED

while an attempt is HELD:
  each minute, if the incident has cleared: recompute the next valid
  boundary at/after this minute (never the stale original T_effective,
  never a non-boundary minute) and complete there.


SELECTION(candidates):
  CGDTR / fixed-interval:    rank by ascending WorkerAccumulatedShiftDose,
                             tie-break ascending worker_id
  reference-rule / ablation-d: ascending worker_id only (ignores dose)


TRIGGER kind by policy:
  no_rotation:       never
  fixed_interval:    t > 0 and t % N == 0
  reference_rule:    SAME three-clause trigger as CGDTR (shared function)
  ablation_d:        SAME fixed-interval trigger as fixed_interval (shared function)
  cgdtr:             the three-clause trigger above
```

**Shared-conditions guarantee:** all five policies call the exact same
`assignment.batch_resolve`, `scheduling.start_attempt`/
`resolve_attempt`/`recompute_after_acknowledgement`, and
`policies.evaluate_trigger`/`rank_candidates` function objects --
verified directly by `tests/test_policies.py` (trigger-sharing) and
`tests/test_simulation.py` (end-to-end timing-sharing), not merely
asserted in prose.

---

## 4. Documented simplifications (restated from `simulation.py`'s own docstring)

1. Incident state = current occupant's own sensor-fault state (no
   separate incident-management system).
2. A worker's sensor-state history resets to HEALTHY at the start of
   each new assignment (a fresh device per assignment, not one device
   followed across non-contiguous rooms).
3. Simulated RSO acknowledgement = the first minute the underlying
   sensor fault clears (a proxy, not a real acknowledgement-latency
   model).
4. Mid-handoff eligibility changes ("interrupted handoff") do not arise
   naturally in the live orchestrator -- exercised only by
   `scheduling.py`'s own scripted unit tests.
5. Persistent-infeasible-dose-concern escalation (the original section
   3h concept) is tracked as a simple per-room counter in
   `simulation.py`, kept deliberately separate from `escalation.py`'s
   sensor-fault-persistence channel (task 5) -- two different concerns,
   never merged into one state machine.
6. The exposure layer reuses Phase 1's existing procedure-class
   baseline (not a room-based one) -- the room-vs-procedure framing
   question registry row 16 already flags, carried forward not
   resolved.
7. `intended_assignment_minutes` for the duty-limit check (section 3i)
   defaults to the single upcoming slot's own length -- the conservative
   default section 3i's own text names, not a longer speculative
   projection.

None of these is a correctness defect; each is a scope choice a reader
needs in order to correctly interpret the campaign's results, stated
once here rather than left implicit.

---

## 5. New provisional parameters introduced for the trigger/campaign (not yet numbered registry rows)

| Parameter | Value | Purpose |
|---|---|---|
| `cgdtr_trigger.rotation_threshold_fraction` | 0.5 | clause (a) multiplier |
| `cgdtr_trigger.reference_level_mSv_per_shift` | 0.1 mSv | clause (a) reference level (illustrative per-shift stand-in for `CONFIG.refAnnual`) |
| `fixed_interval_baseline.fixed_interval_minutes` | 60 | fixed-interval/Ablation-D trigger period |

All marked `PROVISIONAL` with an explicit synthetic `source` field in
`config/phase3c_config.json`; none approved for clinical use; see
`UNRESOLVED_SCIENTIFIC_DECISIONS.md` items 1 and 4 (via
`PHASE3B_ROTATION_ALGORITHM_DESIGN.md` section 9d) for the open
questions these raise.

---

## 6. New dependencies introduced this round

`scipy` and `numpy` (statistical analysis: bootstrap CI, Wilcoxon
signed-rank) and `matplotlib` (figure generation) were installed via
`python3 -m pip install --user` in this session. These are **analysis-
and documentation-only** dependencies -- nothing in `phase3c_rotation_infra`,
`phase3a_forecasting`, `phase2a_adapter`, or `phase1_simulator` depends
on them; they are used only by `stats_common.py`,
`analyze_rotation_campaign.py`, and `generate_figures.py`. Not
previously part of any phase's requirements; disclosed here and in the
final completion report, not silently added.
