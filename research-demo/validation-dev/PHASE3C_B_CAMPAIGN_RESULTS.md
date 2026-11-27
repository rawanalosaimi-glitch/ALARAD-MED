# Phase 3C-B / Phase 3A — Campaign Results

**Status: real, actually-executed campaign results, reported exactly as
produced** (`phase3c_campaign_output/analysis_summary.json`,
`phase3c_campaign_output/sensitivity_results.json`,
`phase3a_campaign_output/campaign_summary.json`). This document states
findings as found, including negative/null ones, per this round's own
explicit instruction not to force a conclusion.

---

## 1. Rotation campaign — scope achieved

**Full target reached: all 13 scenario classes x 30 seeds = 390 runs x
5 policies, 0 failed runs** (`phase3c_campaign_output/manifest.json`:
`completed=390`, `failed=0`). Seed base 700000 (disjoint from every
other seed block used this round or previously). Command:
```
python3 -m phase3c_rotation_infra.run_campaign --seeds-per-class 30
```

## 2. Collective-dose conservation invariant

**Holds to floating-point precision across the entire campaign.**
Checked 1,950 policy-run pairs (390 runs x 5 policies); maximum absolute
deviation = **2.22e-16 mSv**; **0 violations** at the 1e-6 mSv tolerance.
This confirms, at full campaign scale (not merely in unit tests), that
no policy's rotation decisions created or destroyed dose -- every
individual-dose difference reported below is a *redistribution* of a
fixed total, never a reduction in total exposure. Mean collective dose
was identical across all five policies: **0.04642 mSv** (paired on the
same exposure layer per seed, as designed).

## 3. Per-policy descriptive results (max individual dose, n=390 runs each)

| Policy | Mean max individual dose (mSv) | Bootstrap 95% CI | Rotations completed | Infeasible attempts | Runs with ≥2 consecutive infeasible attempts* |
|---|---|---|---|---|---|
| No rotation | 0.03877 | [0.03520, 0.04245] | 0 | 0 | 0 |
| Fixed-interval | 0.03820 | [0.03470, 0.04187] | 21 | 112 | 0 |
| Reference-rule | 0.03767 | [0.03423, 0.04121] | 20 | 985 | 72 |
| Ablation D | 0.03820 | [0.03470, 0.04187] | 21 | 112 | 0 |
| CGDTR | 0.03767 | [0.03423, 0.04121] | 20 | 985 | 72 |

**Correction (post-hoc audit, see `PHASE3C_AUDIT_REPORT.md`):** no
ABORTED events occurred in any policy (`n_aborted=0`), but the original
wording here ("all held attempts resolved before shift end") was
inaccurate -- **zero HELD attempts occurred at all**, in any policy, in
any of the 1,950 policy-run evaluations (`n_held=0` everywhere, verified
directly against `analysis_summary.json` and a raw-data re-scan). The
HELD -> simulated-RSO-acknowledgement code path
(`simulation.py` lines ~164-193) is unit-tested via a scripted scenario
(`test_simulation.py::TestHeldAndEscalation`) but was never organically
triggered by this campaign's actual conditions.

**Notable finding, stated plainly, and now verified by direct
instrumentation (`phase3c_rotation_infra/audit_diagnostics/`, see the
audit report for the exact method):** CGDTR and reference-rule produced
**byte-identical** per-run results throughout the campaign (every paired
difference in max individual dose is exactly 0.0; see section 5) --
**confirmed to be a property of this campaign's roster/credential
configuration, not an implementation defect.** Across all 1,005
dose-threshold trigger events in the campaign: 845 (84.1%) had *zero*
credentialed candidates at all; after the full eligibility filter
(state, duty limits, availability), 985 (98.0%) had *zero* eligible
candidates and 16 (1.6%) had exactly one -- leaving only **4 of 1,005
trigger events (0.4%) with two or more simultaneously eligible
candidates**, the only condition under which the two selection rules
could possibly diverge. In **all 4** of those events, the eligible
candidates' accumulated doses were tied at exactly 0.0 mSv (neither had
yet accrued any dose this shift), so CGDTR's lowest-dose sort collapsed
to its own ascending-worker-ID tie-break -- the same rule reference-rule
uses directly -- so even these 4 rare opportunities were structurally
incapable of producing a different winner. `rank_candidates`'s two
branches are independently correct and do produce different orderings
when given a mixed-dose, multi-candidate input (verified by
`test_policies.py`'s dedicated unit tests); the campaign itself simply
never presented such an input. **This is an underpowered experimental
design for the selection-rule question specifically, not a selection-
logic defect** -- see section 6 (ablation decomposition), section 9
(limitations), and `PHASE3C_AUDIT_REPORT.md` issues 1-2 for full detail.

**Trigger-rule effects dominate.** The dose-threshold trigger
(CGDTR/reference-rule) attempted a rotation far more often than the
fixed-interval trigger (1,005 total trigger events = 20 completed + 985
infeasible, vs. 133 = 21 + 112), but the overwhelming majority of
dose-threshold trigger events were **infeasible** (no credentialed,
available replacement at that moment) -- only 20 of 1,005 dose-threshold
trigger events (≈2%) actually completed a rotation, vs. 21 of 133
(≈16%) for the fixed-interval trigger. The dose-threshold trigger's
illustrative parameters (`rotation_threshold_fraction=0.5`,
`reference_level_mSv_per_shift=0.1` mSv, i.e. a 0.05 mSv trigger level)
are crossed quickly relative to typical per-shift accumulated dose in
this simulation, so it fires often -- but the illustrative roster
(`extra_workers_beyond_concurrent_rooms=1`,
`credential_coverage_probability_range=[0.4, 0.7]`) rarely has an
eligible, idle, credentialed replacement on hand at the moment it fires.
This is a property of this round's illustrative parameter choices, not
a general claim about dose-threshold triggering.

**Infeasibility root-cause breakdown (CGDTR, all 1,005 trigger events,
from `phase3c_rotation_infra/audit_diagnostics/audit_infeasibility_reasons.py`,
a read-only replay instrument added during the post-hoc audit -- the
committed `rotation_events` log itself only stores the single generic
reason string `"no_eligible_candidate_free_through_interval"` and
cannot answer this breakdown on its own):**

| Root cause | Count | % of all triggers |
|---|---|---|
| No credentialed candidate at all (nobody else credentialed for that room+procedure) | 845 | 84.1% |
| Credentialed candidate(s) existed, but all were occupying another room (`not_free_assigned`) | 133 | 13.2% |
| All credentialed candidates blocked specifically by the max-rotations-per-shift duty limit | 7 | 0.7% |
| Had at least one eligible candidate -> completed | 20 | 2.0% |

The dominant driver (84%) is **credential scarcity** (small illustrative
roster x moderate credential-coverage probability x the compound
room-AND-procedure-class credentialing requirement), not scheduling
conflicts or duty limits. The `max_rotations_per_shift` duty-limit
sub-check did fire for real in this campaign (7 times, concentrated in
the `transient_spike` archetype) -- confirmed working as specified on
live data, not only in unit tests. Two other sub-checks never fired at
all in the real campaign: the projected-dose duty-limit sub-check
(`projected_shift_total_dose_mSv >= max_dose_per_shift_mSv`, the
Phase 3C-A gap-3 closure) and the availability-window check -- the
latter is structurally unexercisable in this campaign by construction,
since `generate_roster` always grants every worker full-shift
availability (`availability_windows=[(0, shift_minutes)]`). Both remain
validated only by `test_assignment.py`'s dedicated unit tests, not by
this campaign's own data.

## 4. Per-archetype trigger/completion breakdown (CGDTR)

| Archetype | n runs | Completed | Infeasible | Runs with ≥2 consecutive infeasible attempts* |
|---|---|---|---|---|
| area_relocation | 30 | 0 | 52 | 3 |
| concurrent_alert_and_fault | 30 | 3 | 54 | 5 |
| fault_delayed | 30 | 1 | 16 | 1 |
| fault_during_event | 30 | 2 | 128 | 8 |
| fault_frozen | 30 | 1 | 49 | 4 |
| fault_invalid | 30 | 0 | 30 | 5 |
| fault_missing | 30 | 1 | 70 | 4 |
| gradual_increase | 30 | 2 | 150 | 9 |
| multi_worker_faults | 30 | 2 | 131 | 7 |
| multi_worker_mixed | 30 | 1 | 146 | 11 |
| normal | 30 | 2 | 43 | 5 |
| sudden_increase | 30 | 1 | 74 | 5 |
| transient_spike | 30 | 4 | 42 | 5 |

*Not the sensor-fault-persistence channel -- see the correction immediately below.

**Correction (post-hoc audit):** the "runs with escalation" column
above was mislabeled in the original version of this document as "the
sensor-fault-persistence channel (`escalation.py`)." **That is
incorrect.** `escalation.py::evaluate_escalation` -- the actual
sensor-fault-persistence state machine task 5 implemented and
unit-tested (`test_escalation.py`, 8 tests including one real-engine-
integration test) -- is imported by `simulation.py` but **never called
anywhere in the live orchestrator** (confirmed by inspecting
`simulation.py`'s source directly: the import exists, no call site
does). The counts shown above are actually
`simulation.py`'s own, separate, simpler per-room counter for "2 or
more consecutive INFEASIBLE rotation *attempts*" (the module's own
documented simplification #5 -- a dose-concern/scheduling-infeasibility
signal, with no connection to sensor faults at all). **The real
sensor-fault-persistence escalation channel was never exercised by this
or any other run in the campaign** -- it remains validated only in
isolation, by scripted/engineered unit-test scenarios, never by live
campaign data. See `PHASE3C_AUDIT_REPORT.md` issue 5 for full detail.

## 5. Paired comparisons (Wilcoxon signed-rank, Holm-Bonferroni corrected, n=390 pairs, family of 14 tests)

| Comparison | Mean diff., max individual dose (mSv) | Raw p (dose) | Holm-corrected significant? | Raw p (fairness variance) | Holm-corrected significant? |
|---|---|---|---|---|---|
| CGDTR vs. no-rotation | -0.001104 | 1.96e-4 | **Yes** | 5.17e-4 | **Yes** |
| Fixed-interval vs. no-rotation | -0.000569 | 4.38e-4 | **Yes** | 2.90e-3 | **Yes** |
| Reference-rule vs. no-rotation | -0.001104 | 1.96e-4 | **Yes** | 5.17e-4 | **Yes** |
| Ablation D vs. no-rotation | -0.000569 | 4.38e-4 | **Yes** | 2.90e-3 | **Yes** |
| CGDTR vs. fixed-interval | -0.000535 | 0.0980 | No | 0.4528 | No |
| CGDTR vs. reference-rule | 0.0 (all diffs exactly 0) | undefined (all diffs zero) | No | undefined | No |
| CGDTR vs. Ablation D | -0.000535 | 0.0980 | No | 0.4528 | No |

**Honest reading of this table:** every rotation policy significantly
reduced max individual dose, and significantly reduced roster dose-
variance (improved fairness), relative to no rotation, at this sample
size. **CGDTR did NOT show a statistically detectable advantage over
the simpler fixed-interval baseline** (p=0.098, not significant after
correction) **on either max individual dose or fairness**, and was
statistically indistinguishable from reference-rule (identical values).
This is a genuine negative/null finding for the specific comparison the
project was most interested in (does the more sophisticated dose-aware
trigger+selection beat a simple timer?), reported as found, not
reframed.

**Disclosure added by post-hoc audit -- effective (nonzero) pair counts
and the conditional effect size.** `scipy.stats.wilcoxon`'s default
`zero_method='wilcox'` drops zero-difference pairs before computing the
test statistic (standard, not a defect), but the `n_pairs` field this
project's own `stats_common.py::wilcoxon_paired` reports is the raw
pair count (390), not the effective count the test actually used. The
table above was not previously annotated with this breakdown:

| Comparison | n = 390 pairs | Zero-difference pairs | Nonzero pairs | Direction of the nonzero pairs | Mean diff. over the nonzero pairs only |
|---|---|---|---|---|---|
| CGDTR vs. no-rotation | 390 | 372 (95.4%) | 18 (4.6%) | all 18 favor CGDTR | −0.0239 mSv |
| CGDTR vs. fixed-interval | 390 | 365 (93.6%) | 25 (6.4%) | 14 favor CGDTR, 11 favor fixed-interval | n/a (mixed direction) |
| CGDTR vs. Ablation D | 390 | 365 (93.6%) | 25 (6.4%) | 14 favor CGDTR, 11 favor Ablation D | n/a (mixed direction) |
| CGDTR vs. reference-rule | 390 | 390 (100%) | 0 (0%) | -- | -- |

The CGDTR-vs-no-rotation p-value (1.96e-4) is a real, legitimate signal
-- it reflects all 18 nonzero pairs agreeing in direction, which is
exactly why the Wilcoxon statistic is 0 and the p-value is small despite
an effective sample of only 18 -- but the headline mean difference
reported above (−0.001104 mSv, a **2.85%** relative reduction against
no-rotation's own mean of 0.03877 mSv) is a **population average
diluted by the 372 runs where nothing differed at all**. Read as "the
average expected benefit of deploying CGDTR across this campaign's full
scenario mix," 2.85% is the correct number. Read as "how large is the
effect when CGDTR's rotation actually changes the outcome," the correct
number is the conditional mean over the 18 affected runs: −0.0239 mSv,
a ≈29.7% relative reduction against no-rotation's own mean restricted
to those same 18 runs (0.0806 mSv) -- not the full-campaign average
used for the population-level 2.85% figure. Both numbers are correct; neither should be quoted alone
without the other and without the 4.6% affected-run rate that produces
the gap between them. See `PHASE3C_AUDIT_REPORT.md` issue 4.

## 6. 2x2 ablation decomposition (trigger-rule effect vs. selection-rule effect)

| Effect | Mean (mSv) | Bootstrap 95% CI |
|---|---|---|
| Selection-rule effect (CGDTR vs. reference-rule, averaged with fixed-interval vs. Ablation D) | 0.0 | [0.0, 0.0] |
| Trigger-rule effect (CGDTR vs. fixed-interval, averaged with reference-rule vs. Ablation D) | -0.000535 | [-0.000924, -0.000186] |

**Reading:** the entire measured difference between CGDTR and the
simpler baselines is attributable to the *trigger rule* (dose-threshold
vs. fixed-interval), not to the *selection rule* (lowest-accumulated-
dose vs. plain worker-ID) -- the selection-rule effect is exactly zero
throughout this campaign (section 3's byte-identical-outcomes finding).
Note the apparent tension with section 5: the ablation's bootstrap CI
on the trigger effect excludes zero, while the corresponding formal
paired Wilcoxon test (CGDTR vs. fixed-interval, n=390) was *not*
significant after Holm-Bonferroni correction (p=0.098). Both statements
are correctly computed from the same data; the difference is that the
ablation CI pools two related paired comparisons (CGDTR-vs-fixed-
interval and reference-rule-vs-Ablation-D) into one bootstrap sample of
780 differences, which narrows the CI relative to either individual
n=390 Wilcoxon test. Neither number should be read as stronger evidence
than the other; both are reported so a reader can see exactly what each
method does and does not support. The correctly-sized-for-the-family
formal test (section 5) is the one that should drive any claim of
significance for the CGDTR-vs-fixed-interval comparison specifically.

## 7. Sensitivity analysis (5 provisional parameters, separate seed block, seed base 850000, n=15 per sweep point, 3 archetypes: normal / multi_worker_mixed / fault_missing)

Command: `python3 -m phase3c_rotation_infra.run_sensitivity`

| Parameter | Values swept | Mean max indiv. dose range (mSv) | Mean completed range | Mean infeasible range |
|---|---|---|---|---|
| `cgdtr_trigger.rotation_threshold_fraction` | 0.1, 0.3, 0.5, 0.7, 0.9 | 0.0327 - 0.0508 | 0.00 - 0.67 | 0.00 - 18.73 |
| `fixed_interval_baseline.fixed_interval_minutes` | 20, 40, 60, 80, 100 | 0.0340 - 0.0615 | 0.00 - 0.13 | 2.00 - 6.20 |
| `handoff.min_handoff_duration_minutes` | 5, 10, 15, 20, 30 | 0.0284 - 0.0586 | 0.00 - 0.33 | 0.87 - 5.80 |
| `duty_limits.max_rotations_per_shift_range` | [1,1], [1,2], [1,3], [2,4] | 0.0342 - 0.0486 | 0.00 - 0.13 | 2.47 - 4.53 |
| `roster_generation.credential_coverage_probability_range` | [0.2,0.3], [0.4,0.7], [0.8,0.95] | 0.0325 - 0.0466 | 0.00 - 0.20 | 0.53 - 3.80 |

**Monotonic, interpretable pattern:** `rotation_threshold_fraction` and
`credential_coverage_probability_range` both show mean infeasible
attempts dropping monotonically as the parameter rises (a higher
threshold triggers less often; higher credential coverage makes more
replacements eligible when it does trigger) -- consistent with the main
campaign's finding that infeasibility, not dose outcome, is the
parameter-sensitive quantity for this policy under this illustrative
roster.

**No clean dose-response signal for the other three parameters** at
n=15 per point -- `fixed_interval_minutes`, `min_handoff_duration_minutes`,
and `max_rotations_per_shift_range` show non-monotonic mean-max-dose
values across their swept range. This is read as "no detectable trend
at this sample size," not as "these parameters have no effect" --
n=15 per point is the methodology's own small-sweep budget (chosen to
avoid tuning on the main campaign's own evaluation runs), not a
confirmatory sample size.

**Pre-registration discipline followed:** this sweep used a seed block
(850000+) and sample size (n=15/point) disjoint from, and much smaller
than, the main campaign (seed 700000+, n=30/point) specifically so these
exploratory sensitivity results could never be mistaken for, or
silently substituted into, the main campaign's own performance claims.

## 8. Forecasting campaign (Phase 3A)

**Full target reached: all 13 scenario classes x 30 seeds, 187,110
pooled scored forecast windows, 0 run failures**
(`phase3a_campaign_output/campaign_summary.json`). Seed base 90000
(disjoint from the design set 20260601-13, the 8-seed smoke batch
3001-3008, and the rotation campaign's 700000+/850000+ blocks). Series
rescaled onto the frozen engine's own room baselines before forecasting
(resolving the previously-identified exposure-scale mismatch). Only the
three horizons the real `linearForecast` actually produces (1/2/3
minutes) were evaluated -- no 15-minute capability is claimed. Command:
```
python3 -m phase3a_forecasting.run_phase3a_statistical_campaign --seeds-per-class 30
```

**Two real defects were found and fixed in this round's own new
analysis code (not in any previously-validated module) before these
numbers were accepted as final** -- see section 8d. The numbers below
are from the corrected code, re-run in full after the fixes.

### 8a. Pooled MAE / RMSE by horizon (uSv/h, rescaled to engine baseline; n = 183,402-184,716 scored windows per horizon)

| Horizon | Method | MAE | RMSE |
|---|---|---|---|
| 1 min | linearForecast (candidate) | 3.960 | 16.735 |
| 1 min | Persistence | 3.201 | 14.092 |
| 1 min | Exponential smoothing (alpha=0.5) | 3.211 | 14.884 |
| 2 min | linearForecast (candidate) | 5.498 | 24.200 |
| 2 min | Persistence | 3.686 | 18.087 |
| 2 min | Exponential smoothing | 3.676 | 18.591 |
| 3 min | linearForecast (candidate) | 7.105 | 31.596 |
| 3 min | Persistence | 4.135 | 21.037 |
| 3 min | Exponential smoothing | 4.107 | 21.354 |

### 8b. Pooled skill vs. persistence (skill = 1 - MSE(method)/MSE(persistence); 0 = tied, negative = worse)

| Horizon | linearForecast skill | Exp. smoothing skill |
|---|---|---|
| 1 min | -0.410 | -0.115 |
| 2 min | -0.790 | -0.056 |
| 3 min | -1.256 | -0.030 |

**Clear, honest finding: `linearForecast` did NOT show a skill
advantage over persistence in this balanced campaign -- it performed
*worse* than plain persistence at every evaluated horizon, and the gap
widens with horizon** (skill -0.41 at 1 minute, -1.26 at 3 minutes;
i.e. `linearForecast`'s MSE is more than double persistence's MSE at
the 3-minute horizon). Exponential smoothing also underperformed
persistence, but only slightly (skill -0.03 to -0.12), and its gap does
not widen with horizon the way `linearForecast`'s does. **This result
must be reported as a negative finding, not reframed**: under this
round's balanced, rescaled, 13-archetype campaign, neither alternative
tested beats the simplest possible forecast (persistence) at predicting
the engine's own short-horizon radiation rate, and the engine's own
`linearForecast` is the weakest of the three methods compared here.

### 8c. Per-class skill, every archetype (linearForecast vs. persistence)

| Archetype | n windows | n skipped | Skill, 1 min | Skill, 2 min | Skill, 3 min |
|---|---|---|---|---|---|
| normal | 10,470 | 0 | -0.277 | -0.863 | -1.684 |
| gradual_increase | 11,430 | 0 | -0.441 | -0.709 | -1.025 |
| sudden_increase | 12,090 | 0 | -0.510 | -0.784 | -1.165 |
| transient_spike | 12,570 | 0 | -0.251 | -0.854 | -1.662 |
| area_relocation | 11,010 | 0 | -0.653 | -1.049 | -1.468 |
| multi_worker_mixed | 31,590 | 0 | -0.377 | -0.793 | -1.222 |
| fault_missing | 11,190 | 440 | -0.251 | -0.871 | -1.670 |
| fault_invalid | 10,650 | 151 | -0.248 | -0.852 | -1.648 |
| fault_frozen | 10,590 | 0 | -0.264 | -0.858 | -1.667 |
| fault_delayed | 9,330 | 169 | -0.266 | -0.866 | -1.647 |
| fault_during_event | 11,070 | 185 | -0.349 | -0.584 | -1.092 |
| multi_worker_faults | 35,550 | 570 | -0.466 | -0.761 | -1.152 |
| concurrent_alert_and_fault | 9,570 | 161 | -0.311 | -0.565 | -1.197 |

**`linearForecast` underperforms persistence in every single one of
the 13 scenario classes, at every horizon, with no exception.** This is
a consistent, not archetype-specific, finding. Skipped-window counts
(missing/invalid readings inside the trailing window, correctly
excluded rather than scored as zero error) are concentrated, as
expected, in the four `fault_*`/`concurrent_alert_and_fault` archetypes
that deliberately inject missing or invalid readings.

### 8d. Two defects found in this round's own forecasting-analysis code, and fixed before these numbers were finalized

Both defects were in **new code written this round**
(`phase3a_forecasting/metrics.py` and
`run_phase3a_statistical_campaign.py`), not in any previously-validated
module (`linearForecast` itself, `forecast_adapter.py`'s no-leakage
window construction, and `mae_rmse_by_horizon` were all unaffected and
remain exactly as previously validated).

1. **NaN leak in `skill_vs_persistence`.** `fault_invalid`'s
   legitimately-NaN actual readings (the project's own established
   encoding for an invalid/non-physical reading, via
   `detection_adapter.decode_observed_value`) were filtered out of
   `mae_rmse_by_horizon` correctly, but **not** out of
   `skill_vs_persistence`, which lacked the equivalent NaN check -- so
   a NaN actual value could make the entire skill score for that class
   literally `NaN` instead of excluding just that one data point. Fixed
   by adding the same `isinstance(x, float) and math.isnan(x)` guard
   already used in `mae_rmse_by_horizon`. Pinned by
   `test_metrics.py::test_nan_actual_excluded_not_propagated_as_nan`.
2. **Cross-series key collision in `skill_vs_persistence`'s pairing
   dict (the more serious of the two).** The function paired candidate
   and persistence rows by a dict keyed on bare `t` (a per-series,
   0-based minute index). This is correct for comparing two methods'
   output on a *single* series, but the campaign script pools rows from
   many different (seed, worker) series -- each restarting its own `t`
   at 0 -- into one flat list before calling this function for the
   per-class and pooled skill scores. Every series after the first
   **silently overwrote** the dict entries of every earlier series that
   shared the same `t` value, so the reported pooled/per-class skill
   score reflected only the *last*-processed series, not an aggregate
   over the intended thousands of windows. (This was caught because the
   first run's pooled skill values were found to exactly match the last
   archetype's per-class values -- not a plausible coincidence.) Fixed
   by tagging every row with a `series_id` (`f"{archetype}:{seed}:
   {worker_id}"`) in `run_phase3a_statistical_campaign.py` and pairing
   on `(series_id, t)` in `metrics.py`. Pinned by
   `test_metrics.py::test_pooling_two_series_with_colliding_t_does_not_drop_data`
   and `::test_pooling_two_series_distinguishes_different_skill_per_series`.

Both fixes are covered by 14 new unit tests in
`phase3a_forecasting/tests/test_metrics.py` (all passing, see
`PHASE3C_B_TEST_EVIDENCE.md` section on this file), and the full
forecasting campaign was **re-run in full from scratch** after both
fixes, not patched after the fact -- every number in sections 8a-8c is
from that corrected, complete re-run.

## 9. Limitations specific to these results (not repeating `PHASE3C_B_ASSUMPTIONS_LIMITATIONS_AND_THREATS_TO_VALIDITY.md`)

1. **The selection-rule ablation is uninformative at this roster size.**
   Because CGDTR and reference-rule never differed in this campaign,
   this round cannot speak to whether a dose-aware selection rule would
   help at a larger roster or higher credential coverage -- the
   sensitivity sweep's `credential_coverage_probability_range=[0.8,0.95]`
   point (section 7) is the one condition most likely to surface a
   selection-rule effect, and a follow-up campaign specifically crossing
   high credential coverage with the main campaign's full seed count
   would be needed to test that directly; this round did not run that
   specific combination at full scale.
2. **CGDTR's infeasibility rate (98%) is a property of this round's
   illustrative parameters, not a finding about dose-threshold
   triggering in general.** A different `rotation_threshold_fraction`
   or roster size could change this substantially (section 7 shows the
   direction).
3. **Small-n ablation CI vs. formal test tension (section 6)** should be
   read via the formal, family-corrected test, not the pooled ablation
   CI, for any claim of statistical significance.
