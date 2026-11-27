# ALARAD Technical Research Completion Report

**Scope: the "Complete Remaining Technical Research Work" task (12
sections) on branch `research/icaire-v123-validation`.** This report
states, exactly, what was completed, what was verified, what remains a
scientific limitation, and what is still open. Per that task's own
explicit instruction: **this project is NOT reported as fully completed
unless every required technical deliverable has been generated and
verified** -- section 9 below states plainly what that means for this
round.

---

## 1. Repository protection and initial verification (section 1 of the task)

- All work this round was confined to `research/icaire-v123-validation`,
  entirely under `research-demo/validation-dev/`. The frozen release
  `research-demo/releases/html/ALARAD_Prototype_Research_Demo_v1.2.3.html`
  was never opened for editing; it was read-only, driven only through
  Playwright's `page.evaluate()` via the existing, unmodified
  `EngineBridge`.
- **Frozen file SHA-256, verified at the start and again at the end of
  this round, unchanged:**
  `92e897dd0ff1738f083df829b53f7f46377e042b7019bb9776232792261182ee`
- All ten required documents (`PHASE3B_ROTATION_ALGORITHM_DESIGN.md`
  Rev 3, `PHASE3C_A_DOSE_THRESHOLD_SEMANTIC_AUDIT.md`,
  `PHASE3C_A_IMPLEMENTATION_REPORT.md`,
  `PHASE3C_A_REVIEW_AGAINST_REVISION_3.md`,
  `PHASE3C_B_READINESS_CHECKLIST.md`,
  `ICAIRE_Simulation_Validation_Methodology.md` Rev 6,
  `ROTATION_RECOMMENDER_DESIGN_SPEC.md`,
  `SCIENTIFIC_PARAMETER_REVIEW_PACKAGE.md`,
  `UNRESOLVED_SCIENTIFIC_DECISIONS.md`,
  `PHASE3A_FORECASTING_READINESS_CHECKLIST.md`) were read before any new
  implementation work began this round.

## 2. What was completed (mapped to the task's 12 sections)

| Section | Status | Evidence |
|---|---|---|
| 1. Repo protection / verification | **Done** | Section 1 above |
| 2. Close 5 Phase 3C-A infrastructure gaps | **Done** | `sensor_validity.py`, `dose_quantities.py`, `runtime.py`, `assignment.py` duty-limit check, `exposure_layer.py::remaining_minutes` |
| 3. CGDTR rotation algorithm | **Done** | `policies.py`, `simulation.py`; see section 3 below |
| 4. All 5 comparison policies + 2x2 ablation | **Done** | `policies.py` (shared trigger/selection function objects); campaign section 4 below |
| 5. Safety/correctness testing | **Done** | 156/156 tests passing; section 4 below |
| 6. Phase 3A forecasting evaluation | **Done** | 13/13 archetypes x 30 seeds, 187,110 windows; two defects found and fixed mid-round |
| 7. Final simulation campaign | **Done** | 390/390 rotation runs, 0 failures; 13/13 forecasting archetypes, 0 failures |
| 8. Statistical analysis | **Done** | `analyze_rotation_campaign.py` run on full 390-run dataset |
| 9. Sensitivity analyses | **Done** | 5 parameters x up to 5 values each, separate seed block |
| 10. Publication-ready outputs | **Done** | 7 figures, campaign results doc, architecture/methods doc, limitations doc, test evidence doc, manuscript handoff doc |
| 11. Quality gates / automated continuation | **Done** | See section 6 (defects found and fixed without stopping for approval) |
| 12. Final verification and delivery | **Done** | This report; section 7 below |

## 3. CGDTR and the four comparison policies -- what was implemented

Full design and pseudocode: `PHASE3C_B_ARCHITECTURE_AND_METHODS.md`.
Summary: a deterministic, non-learning trigger with three clauses, each
reading a separately-owned dose quantity against its own threshold
(never cross-compared): `EngineProjectedTaskDose` (the real engine's
own 30-minute projection, vs. `CONFIG.doseElevated`/`doseCritical`),
`WorkerAccumulatedShiftDose` (this project's running total, vs.
`rotation_threshold_fraction x reference_level_mSv_per_shift`), and
`ProjectedShiftTotalDose` (accrued + projected increment, vs.
`max_dose_per_shift_mSv`). Selection ranks by ascending accumulated
dose (CGDTR/fixed-interval) or by worker ID alone (reference-rule/
Ablation D). All five policies share identical eligibility, scheduling,
incident, and escalation mechanics -- verified both by unit test
(`test_policies.py`, `test_simulation.py`) and by the campaign's own
ablation decomposition (section 6 of
`PHASE3C_B_CAMPAIGN_RESULTS.md`).

## 4. Testing -- exact commands and results

```
cd research-demo/validation-dev
python3 -m unittest discover -s phase3c_rotation_infra/tests -t .   # 109 tests, 109 passed
python3 -m unittest discover -s phase3a_forecasting/tests -t .      # 47 tests, 47 passed
python3 -m unittest discover -s phase2a_adapter/tests -t .          # 31 tests, 31 passed (pre-existing, unaffected)
python3 -m unittest discover -s phase1_simulator/tests -t .         # 40 tests, 40 passed (pre-existing, unaffected)
```
**Combined (rotation + forecasting, this round's own test scope): 156
tests, 156 passed, 0 failed, 0 skipped, 0 errors.** Re-run a final time
at the end of this round, after all implementation and documentation
work, with the result above. Full per-file breakdown and mandatory-
coverage cross-reference: `PHASE3C_B_TEST_EVIDENCE.md`.

## 5. Simulation campaign -- exact scope achieved

- **Rotation:** `python3 -m phase3c_rotation_infra.run_campaign --seeds-per-class 30`
  -- all 13 scenario classes x 30 seeds = **390/390 runs, 0 failed**,
  5 policies evaluated per run on an identical exposure layer (paired
  design). Seed base 700000.
- **Forecasting:** `python3 -m phase3a_forecasting.run_phase3a_statistical_campaign --seeds-per-class 30`
  -- all 13 scenario classes x 30 seeds, **187,110 pooled scored
  windows, 0 run failures**. Seed base 90000. Rescaled onto the engine's
  own baseline; restricted to the real 1/2/3-minute horizons only.
- **Sensitivity:** `python3 -m phase3c_rotation_infra.run_sensitivity`
  -- 5 parameters, up to 5 values each, n=15 runs/point, 3 archetypes.
  Seed base 850000 (disjoint from both campaigns above).
- Configuration snapshots, raw per-run outputs, and the incrementally-
  updated manifest for the rotation campaign are stored under
  `phase3c_campaign_output/` (`config_snapshot.json`, `raw_runs/*.json`,
  `manifest.json`); the forecasting campaign's summary is
  `phase3a_campaign_output/campaign_summary.json`.

## 6. Statistical results, sensitivity results, and figures -- see `PHASE3C_B_CAMPAIGN_RESULTS.md` for full detail

**Headline findings, stated exactly as found (both negative/null):**

1. **Collective-dose conservation invariant held to floating-point
   precision across the entire campaign**: 1,950 policy-run pairs
   checked, max deviation 2.22e-16 mSv, 0 violations.
2. **CGDTR did not show a statistically detectable advantage over the
   simpler fixed-interval baseline** (Wilcoxon signed-rank,
   Holm-Bonferroni-corrected, p=0.098, n=390 paired runs) and was
   statistically **indistinguishable from reference-rule** (every
   paired difference exactly zero) -- the selection-rule effect this
   campaign was designed to isolate did not materialize at this
   illustrative roster size (only ~2% of CGDTR's dose-threshold trigger
   events found an eligible replacement at all). All rotation policies
   did significantly beat no-rotation.
3. **`linearForecast` performed worse than plain persistence at every
   evaluated horizon and in every one of the 13 scenario classes**
   (pooled skill -0.41/-0.79/-1.26 at 1/2/3 minutes); exponential
   smoothing underperformed persistence by a smaller, horizon-stable
   margin (-0.12/-0.06/-0.03).

**Figures produced** (`research-demo/validation-dev/figures/`, 7
total): `forecast_error_comparison.png`, `forecast_skill_by_archetype.png`,
`max_individual_dose_by_policy.png`, `collective_dose_invariant.png`,
`safety_constraint_counts.png`, `dose_trajectory_example.png`,
`sensitivity_plots.png`.

**Documents produced this round** (all in `research-demo/validation-dev/`):
`PHASE3C_B_ARCHITECTURE_AND_METHODS.md`,
`PHASE3C_B_ASSUMPTIONS_LIMITATIONS_AND_THREATS_TO_VALIDITY.md`,
`PHASE3C_B_TEST_EVIDENCE.md`, `PHASE3C_B_CAMPAIGN_RESULTS.md`,
`RESEARCH_HANDOFF_FOR_MANUSCRIPT.md`, this report.

## 7. Code/analysis defects found and fixed this round (full disclosure)

Quality-gate discipline required fixing implementation errors found
along the way rather than reporting around them. Three were found,
all in **new code written this round** (none in any previously-
validated module):

1. **Off-by-one occupant-attribution ordering in `simulation.py`**
   (found and fixed during implementation, before any campaign run):
   minute `t_effective` was being attributed to the outgoing worker
   instead of the incoming one. Fixed by reordering: resolve attempts
   reaching `t_effective` before advancing per-minute state for `t`.
2. **NaN leak in `metrics.py::skill_vs_persistence`** (found after the
   first forecasting campaign run, by inspecting the `fault_invalid`
   archetype's output): a legitimately-NaN actual reading was not
   excluded the way `mae_rmse_by_horizon` already excludes it, so the
   skill score itself could become `NaN`. Fixed; the full forecasting
   campaign was re-run after the fix.
3. **Cross-series key collision in the same function** (found
   immediately after fixing #2, by noticing the pooled skill values
   exactly matched the last-processed archetype's own values -- not a
   plausible coincidence): pairing candidate/persistence rows by bare,
   per-series-relative `t` silently discarded all but the last series'
   data once rows from many series were pooled. Fixed by tagging rows
   with a `series_id` and pairing on `(series_id, t)`. The full
   forecasting campaign was re-run a second time, from scratch, after
   this fix -- the numbers in `PHASE3C_B_CAMPAIGN_RESULTS.md` section 8
   are from that final, corrected run.

Both of the `metrics.py` fixes are pinned by 14 new unit tests
(`phase3a_forecasting/tests/test_metrics.py`), including two tests that
reconstruct the exact collision scenario and assert the fix prevents
it. **No test was weakened, skipped, or removed to obtain a passing
result at any point this round.**

## 8. Scientific limitations and open items (not resolved by this round, by design)

Full detail: `PHASE3C_B_ASSUMPTIONS_LIMITATIONS_AND_THREATS_TO_VALIDITY.md`
and `PHASE3C_B_CAMPAIGN_RESULTS.md` section 9. Highlights:

- Every provisional parameter (dose-threshold trigger fraction,
  reference level, fixed-interval period, duty limits, handoff
  duration, credential coverage, roster size) remains illustrative and
  unreviewed by a Medical Physicist or RSO; none is a chosen final
  value, per `UNRESOLVED_SCIENTIFIC_DECISIONS.md` and
  `SCIENTIFIC_PARAMETER_REVIEW_PACKAGE.md`.
- The selection-rule ablation is uninformative at this round's
  illustrative roster size (CGDTR and reference-rule never diverged);
  a follow-up campaign at higher credential coverage would be needed to
  test the selection rule's effect directly.
- `linearForecast`'s underperformance relative to persistence is a
  property of this round's balanced, rescaled synthetic campaign, not a
  general claim about the algorithm; see `PHASE3C_B_CAMPAIGN_RESULTS.md`
  section 8 for the full per-class breakdown.
- Personal-mode dosimetry only; area-mode (modeled) workers remain out
  of scope for rotation, unchanged from Phase 2A/3C-A's own scoping.
- No part of this round's work constitutes, or is represented as,
  clinical or regulatory validation of any kind.

## 9. Final completion statement

**Every required technical deliverable listed in the 12-section task
was generated and verified this round**, including both of the
negative/null findings produced by the real campaign data, and
including full disclosure of the two mid-round defects found in this
round's own new analysis code and their fixes. Nothing was reported as
passing without being actually executed; nothing was reframed to avoid
a negative result. The two items in section 8 that are explicitly
*not* resolved (the parameter-review items, and the selection-rule
ablation's inconclusiveness at this roster size) are pre-existing,
acknowledged scientific limitations, not incomplete technical work --
resolving them requires expert review and/or a follow-up campaign
outside this round's own technical scope, exactly as
`UNRESOLVED_SCIENTIFIC_DECISIONS.md` already anticipated.

## 10. Reproduction instructions

From `research-demo/validation-dev/` (requires the Python dependencies
already in the repository's environment, plus `scipy`, `numpy`,
`matplotlib` -- installed this round via
`python3 -m pip install --user scipy numpy matplotlib pillow`, disclosed
in `PHASE3C_B_ARCHITECTURE_AND_METHODS.md` section 6):

```
# Tests
python3 -m unittest discover -s phase3c_rotation_infra/tests -t .
python3 -m unittest discover -s phase3a_forecasting/tests -t .

# Campaigns (each is independent; order does not matter)
python3 -m phase3c_rotation_infra.run_campaign --seeds-per-class 30
python3 -m phase3a_forecasting.run_phase3a_statistical_campaign --seeds-per-class 30
python3 -m phase3c_rotation_infra.run_sensitivity

# Analysis and figures (after the campaigns above have written their output)
python3 analyze_rotation_campaign.py
python3 generate_figures.py
```

## 11. Manuscript-integration readiness checklist

- [x] Rotation algorithm (CGDTR) and all 4 comparison policies implemented, tested, documented.
- [x] Full-scale rotation campaign run (390/390), statistically analyzed, invariant-verified.
- [x] Full-scale forecasting campaign run (13/13 archetypes), two code defects found and fixed, re-run to completion.
- [x] Sensitivity analysis run on a disjoint seed block.
- [x] All 7 planned figures generated from final, verified data.
- [x] Methodology, pseudocode, test evidence, limitations, and manuscript-handoff documents written.
- [x] No unsupported clinical/regulatory claim anywhere in this round's output (explicitly checked in `RESEARCH_HANDOFF_FOR_MANUSCRIPT.md` section 8 and `..._LIMITATIONS...md` section 4).
- [x] Frozen v1.2.3 release untouched; SHA-256 verified unchanged before and after.
- [x] Full test suite (156 tests, this round's scope) passing at time of this report.
- [ ] Expert (Medical Physicist/RSO) review of provisional parameters -- explicitly out of this round's scope; see section 8.
- [ ] Selection-rule-effect follow-up campaign at higher credential coverage -- explicitly out of this round's scope; see section 8.
