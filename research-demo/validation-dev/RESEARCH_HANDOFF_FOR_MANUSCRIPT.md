# Research Handoff — ALARAD/ICAIRE Rotation and Forecasting Evaluation

**Supplementary round note (added later, not altering anything below):**
`ALARAD_MANUSCRIPT_RESULTS_HANDOFF.md` supplements this document with
a later, targeted supplementary validation round that directly tested
the candidate-selection, sensor-fault, and duty-limit/escalation
mechanisms this document's own section 5 (CGDTR vs. reference-rule)
flags as inconclusive rather than negative. Read both; this document's
own claims below are unchanged.

**For: the manuscript-writing team. Purpose: a concise, honest summary
of what was implemented, what was actually tested and run, and what
the results do and do not demonstrate — written so a drafting pass can
start directly from this document without re-deriving any of it from
code.** Every claim below is backed by a specific file in
`research-demo/validation-dev/`; none is asserted from memory.

---

## 1. What was implemented

- **A deterministic, non-learning rotation algorithm (CGDTR)** and four
  comparison policies (no-rotation, fixed-interval, reference-rule,
  and "Ablation D," a diagnostic-only policy completing a 2x2 design),
  sharing identical eligibility, scheduling, incident, and escalation
  mechanics — only the trigger and replacement-selection logic differ
  between them (`phase3c_rotation_infra/policies.py`, `simulation.py`).
- **A two-layer exposure/assignment simulation**: the underlying
  radiation exposure for a room is generated once per seed (reusing
  Phase 1's own 13 archetype generators, unchanged) and is identical
  across every policy compared on that seed; only who is assigned to
  each room, minute by minute, differs by policy.
- **Live, per-minute dose and sensor-state tracking** against the real,
  unmodified frozen engine (`AlaradSafety.sensorStep`,
  `evaluateExposure()`), closing five infrastructure gaps identified in
  a prior round's implementation review.
- **A corrected, three-clause dose trigger** that keeps three distinct
  dose quantities, and their owning thresholds, strictly separate:
  the frozen engine's own 30-minute projection (compared only to the
  engine's own prototype thresholds), this project's own running
  accrued dose (compared to a research-only reference level), and a
  new projected-shift-total quantity (compared only to a research-only
  duty limit).
- **A balanced forecasting evaluation** of the frozen engine's own
  `linearForecast` against two independent baselines (persistence,
  simple exponential smoothing), across all 13 scenario classes with
  fresh, independent seeds, with series rescaled onto the engine's own
  room-baseline scale (resolving a previously-identified scale
  mismatch).
- **Statistical analysis tooling**: paired Wilcoxon signed-rank tests,
  Holm-Bonferroni correction, bootstrap confidence intervals, and the
  2x2 ablation decomposition (`stats_common.py`,
  `analyze_rotation_campaign.py`).

## 2. What was actually tested

**156 automated tests, actually executed, 156 passed, 0 failed, 0
skipped** (`PHASE3C_B_TEST_EVIDENCE.md` has the full breakdown and
exact commands). Coverage includes: dose-rate/cumulative-dose math and
threshold ownership; sensor validity and missing/faulty data; worker
exclusivity under simultaneous rotation requests; procedure-boundary-
aligned scheduling, including interrupted and delayed handoffs;
simulated RSO acknowledgement; escalation persistence and audit
logging (both the sensor-fault channel and the persistent-infeasible-
rotation channel); shift-end unresolved events; deterministic replay;
identical exposure layers across every policy; no double-counted dose;
collective-dose conservation under fixed occupancy; and a structural
check that no code path ever self-invokes the one emergency-override
exception.

## 3. Which comparisons were performed

- **Rotation**: all 13 scenario classes (`PHASE3C_B_CAMPAIGN_RESULTS.md`
  states the exact achieved seed count per class — see that document
  for whether the full 30-per-class target was reached, and if not,
  exactly how far the campaign got). All five policies, paired on
  identical exposure/staffing per seed. A 2x2 ablation isolating the
  trigger-rule effect from the selection-rule effect. A sensitivity
  sweep over five provisional parameters, on a separate seed block from
  the main campaign.
- **Forecasting**: `linearForecast` vs. persistence vs. exponential
  smoothing, at the three horizons the real function actually produces
  (1/2/3 minutes — **no 15-minute capability exists or is claimed**),
  across all 13 scenario classes, pooled and per-class, rescaled onto
  the engine's own baseline.

## 4. What the results demonstrate

**Full numbers in `PHASE3C_B_CAMPAIGN_RESULTS.md`.** Two honest,
negative-leaning findings, stated here exactly as that document reports
them:

- **Rotation:** every rotation policy (fixed-interval, reference-rule,
  Ablation D, CGDTR) significantly reduced max individual dose and
  improved roster-dose fairness relative to no rotation (n=390 paired
  runs, Holm-Bonferroni corrected). **CGDTR did not show a statistically
  detectable advantage over the simpler fixed-interval baseline**
  (p=0.098, not significant after correction), and was statistically
  **indistinguishable from reference-rule** — every paired difference
  between them was exactly zero, because the illustrative roster rarely
  had more than one eligible replacement available when the trigger
  fired, so the dose-aware selection rule and the plain-worker-ID
  selection rule always picked the same worker.
- **Forecasting:** across the full balanced 13-archetype, 30-seed-per-
  class campaign (187,110 scored windows), **`linearForecast` performed
  worse than plain persistence at every evaluated horizon and in every
  single scenario class** (skill −0.41 at 1 minute, widening to −1.26 at
  3 minutes). Exponential smoothing also underperformed persistence,
  but only slightly (skill −0.03 to −0.12).

The one result confirmed with certainty, independent of either specific
numeric finding: **the collective-dose conservation invariant held, to
floating-point precision, across every run and every policy in the
campaign** (1,950 policy-run pairs, max deviation 2.22e-16 mSv, 0
violations) — redistribution of exposure among workers was never
produced or reported as a reduction in total exposure.

## 5. What the results do not demonstrate

- **Not real-world effectiveness.** Every number is a property of this
  project's own synthetic exposure, noise, and staffing models — see
  `PHASE3C_B_ASSUMPTIONS_LIMITATIONS_AND_THREATS_TO_VALIDITY.md` section
  1 for the precise does/does-not boundary, and
  `ROTATION_RECOMMENDER_DESIGN_SPEC.md` section 0 for the standing
  caveat this project has carried since the rotation work began.
- **Not clinical or regulatory validation of any threshold.** Every
  provisional parameter (the engine's own prototype thresholds, and
  every new research-only parameter this round introduced) remains
  illustrative and unapproved by any Medical Physicist or RSO.
- **Not a demonstration that `linearForecast` is superior** unless
  `PHASE3C_B_CAMPAIGN_RESULTS.md`'s actual numbers say so — this
  document does not assume the answer either way.

## 6. Which tables and figures should be included in the paper

All produced and verified against the final campaign data, in
`research-demo/validation-dev/figures/` (PNGs) and
`phase3c_campaign_output/analysis_summary.json` /
`phase3a_campaign_output/campaign_summary.json` (underlying numbers):

- `figures/forecast_error_comparison.png` — forecast error (MAE/RMSE) by horizon, pooled.
- `figures/forecast_skill_by_archetype.png` — forecast skill-vs-persistence by scenario class.
- `figures/max_individual_dose_by_policy.png` — maximum individual dose by policy, with bootstrap CIs.
- `figures/collective_dose_invariant.png` — collective dose by policy (the invariant-check figure).
- `figures/safety_constraint_counts.png` — rotation-attempt outcome counts (completed/infeasible/aborted/held) by policy.
- `figures/dose_trajectory_example.png` — one example run's per-minute dose trajectory, no-rotation vs. CGDTR.
- `figures/sensitivity_plots.png` — sensitivity plots for the five swept parameters.

## 7. Suggested Methods and Results wording (strictly from verified evidence)

**Methods (draft wording, to be adjusted to the paper's own style):**
> "We implemented a deterministic, rule-based worker-rotation
> recommender (CGDTR) and compared it against three baseline policies
> and one diagnostic ablation condition, using a synthetic simulation
> that reuses [N] independently seeded scenario classes per archetype,
> paired by seed across policies so that any observed difference
> reflects the rotation policy rather than differences in simulated
> exposure. CGDTR's trigger evaluates three distinct quantities against
> three separately-owned thresholds: [cite the frozen engine's own
> prototype alert thresholds], a research-only accrued-dose reference
> level, and a research-only per-shift duty limit — none of which has
> been reviewed or approved by a radiation safety professional. We
> additionally evaluated the existing system's own linear-trend
> forecaster against persistence and exponential-smoothing baselines
> across the same scenario classes, restricted to the three forecast
> horizons (1/2/3 minutes) the function is capable of producing."

**Results (now filled in from the final, verified
`PHASE3C_B_CAMPAIGN_RESULTS.md` — adjust phrasing to the paper's own
style, but do not change the values without re-deriving them from that
document):**
> "Across 30 seeds per scenario class (390 total paired runs), CGDTR
> did not show a statistically detectable reduction in maximum
> individual dose relative to the fixed-interval baseline
> (Wilcoxon signed-rank, Holm-Bonferroni-corrected p = 0.098; mean
> difference −0.000535 mSv). CGDTR was statistically indistinguishable
> from the reference-rule baseline (every paired difference exactly
> zero). All four rotation policies did show a statistically
> significant reduction in maximum individual dose relative to no
> rotation (p < 0.0005 in every case, Holm-Bonferroni corrected).
> Collective dose was identical across all five policies to within
> floating-point precision (max deviation 2.22×10⁻¹⁶ mSv across 1,950
> checks), confirming that any individual-dose difference reflects
> redistribution, not a reduction in total exposure. The ablation
> decomposition attributed 0 mSv to the selection rule and −0.000535
> mSv (95% CI [−0.000924, −0.000186]) to the trigger rule. Forecasting:
> linearForecast's skill score relative to persistence was negative at
> every evaluated horizon and in every one of the 13 scenario classes
> (pooled skill −0.41, −0.79, and −1.26 at the 1/2/3-minute horizons
> respectively, n = 183,402–184,716 scored windows per horizon);
> exponential smoothing also underperformed persistence but by a
> smaller, horizon-stable margin (pooled skill −0.12, −0.06, and −0.03)."

**Do not** state a conclusion stronger than the values above actually
show; a null or negative finding is a legitimate, reportable result
under this project's own stated discipline, and that is exactly what
both the rotation and forecasting campaigns produced here.

## 8. Explicit non-claims (repeated once more, because it matters)

No citation, validation study, expert approval, or regulatory
determination is invented anywhere in this project's materials. Any
citation appearing in a manuscript must be added by the manuscript
team from real literature, not sourced from this codebase, which
contains none beyond the two already-disclosed, already-unverified
quotations from the frozen engine's own help text
(`SCIENTIFIC_PARAMETER_REVIEW_PACKAGE.md` section 6).
