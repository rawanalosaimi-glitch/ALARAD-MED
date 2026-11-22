# Phase 3A — Remaining Limitations

Per task 10's instruction, mismatches between the existing forecasting
logic and the evaluation methodology are documented here, found and
verified *before* any evaluation code was written on top of an
assumption about them.

## 1. The methodology's "15-minute horizon" placeholder is not achievable with the existing `linearForecast` (verified, not assumed)

`ICAIRE_Simulation_Validation_Methodology.md` section 5 (registry row 7)
lists a "longer horizon (e.g. 15 minutes)" as a placeholder for forecast
evaluation. Verified directly against the live frozen engine in this
session: `linearForecast`'s return value hardcodes exactly 3 future
points (`next:[n,n+1,n+2]`) regardless of how many points are given as
input — tested with input lengths 3, 4, 7, and 10, all returning exactly
3 future values (`test_forecast_contract.py::test_linear_forecast_always_returns_exactly_three_future_points`).

**This means the real function cannot produce a 15-minute-ahead forecast
no matter how it is called.** Reaching that horizon would require either:
(a) feeding the function's own 3-step predictions back into itself as
if they were new observations (a cascading/recursive technique the
frozen engine does not use anywhere, and which would compound
uncertainty in a way that has not been characterized), or (b) a
different forecasting function entirely. Both are explicitly out of
scope for this phase (no new forecasting model may be implemented).
**Phase 3A therefore evaluates only the 1-, 2-, and 3-minute horizons
the real function actually produces**, and registry row 7's placeholder
remains open and now additionally flagged as needing a decision about
*how* (not just *what value*) a longer horizon would be reached, before
any future phase attempts one. **Update:** the methodology document's
"15-minute horizon" placeholder language has since been corrected
(`ICAIRE_Simulation_Validation_Methodology.md` Revision 5, §5 and
registry row 7) to describe this 3-sample limit directly, rather than
leaving it as an open placeholder value.

## 2. `linearForecast` is used in three different contexts in the frozen engine; only one was evaluated

Found while inspecting the source (task 1): `linearForecast` is called
in three places —
1. `SimLab.runWorker` (frozen release line 2971): on the last 4 **real**
   per-minute dose-rate readings, as an early-warning trigger. **This is
   the usage Phase 3A evaluates** (`TRAILING_POINTS=4`, matching
   `PRED_LEN`).
2. `evaluateExposure`'s own internal display chart (line 1977): on a
   **seeded, synthetic** trailing series (explicitly documented in-engine
   as *"SIMULATED trailing history: seeded pseudo-data (not real
   measurements)"*) with the current `cumulativeDose` appended. Evaluating
   this as "forecast accuracy" would be scoring a decorative chart
   against data it was never meant to predict — not attempted.
3. The Live Demo's `demoRefresh` (line 2690): on the trailing
   **contiguous** run of valid readings (3 or 4, not a fixed 4 with a
   strict "any invalid cancels the whole window" rule like usage 1) —
   a legitimate real-history usage, but with a different windowing
   convention than usage 1. Not separately evaluated in this phase; the
   4-point, all-valid convention from usage 1 was chosen as the single
   evaluated contract since it is the one the methodology's own
   forecasting-baseline comparison (section 4b) was written against.

## 3. Rate forecast vs. cumulative-dose forecast: the latter is entirely new, adapter-only logic

`linearForecast` forecasts dose **rate** (µSv/h). The frozen engine
never forecasts cumulative **dose** using a trend model anywhere — its
own `cumulativeDose` field (used in `evaluateExposure`) is a
constant-rate *projection* (current rate held constant), explicitly
documented as *"not a trend forecast"* in
`ICAIRE_Simulation_Validation_Methodology.md` section 1.
`forecast_adapter.forecast_cumulative_dose` is new code written for this
phase, integrating a rate forecast forward using the already-established
dose formula. It is clearly separated (different function, different
output key, different unit) from the rate forecast throughout this
package's code and tests, per task 7 — but it should not be mistaken for
an existing engine capability; it is a derived calculation this project
added, not something being "evaluated" in the sense of rows 1-19's
engine-config parameters.

## 4. Smoke-scale result: the real forecaster showed *negative* skill vs. persistence (genuine finding, not a bug)

The Phase 3A smoke run (8 archetypes, one seed each — see
`PHASE3A_SMOKE_TEST_REPORT.md`) found `linearForecast`'s skill score
against persistence was **negative** at every horizon (−0.27 at 1
minute, down to −1.68 at 3 minutes), while simple exponential smoothing
scored positively (+0.32 at every horizon). This is a real, verified
result for these 8 specific seeds, not an error in the adapter (the
contract tests independently confirm `linearForecast` itself behaves
exactly as documented on known inputs). The likely mechanism: most of
this smoke batch's archetypes are flat or near-flat with ±5% noise, and
fitting an OLS trend line to 4 noisy points with little real trend
amplifies that noise into the extrapolation, whereas persistence (and
smoothing, which averages out noise) is more robust when there is
nothing real to extrapolate. **This is not a claim about
`linearForecast`'s general performance** — the smoke batch is 8 seeds,
heavily weighted toward flat/near-flat scenarios, not the ≥30-seed-per-
class, balanced statistical campaign that would be needed to say
anything general. It is reported here exactly as observed, per the
discipline established in every prior phase.

## 5. New provisional parameter not yet in the registry — RESOLVED

`baseline_exponential_smoothing.alpha` (currently 0.5,
`phase3a_config.json`) was a new choice introduced this phase and, at the
time this section was first written, was not yet a row in
`SCIENTIFIC_PARAMETER_REVIEW_PACKAGE.md`'s registry. **It has since been
added** as **Parameter Registry row 20**
(`ICAIRE_Simulation_Validation_Methodology.md` Revision 5) and as a
priority item in `SCIENTIFIC_PARAMETER_REVIEW_PACKAGE.md` §2, alongside
rows 14/15/17/19 which it matches in kind (a provisional constant this
project's own code depends on, not yet reviewed). What remains open is
the review itself (no expert has assessed `alpha=0.5`) and the question
of selection method — see `UNRESOLVED_SCIENTIFIC_DECISIONS.md` item 14.

## 6. The forecasting adapter does not rescale onto the engine's baseline scale, unlike the detection adapter (new finding, this documentation round)

Checked directly in `forecast_adapter.py` (grep for `rescale`/`baseline`:
no match beyond the unrelated word "baselines" in an import) and
confirmed by inspection of `run_phase3a_smoke.py`: unlike
`detection_adapter.py`, which calls
`rescale_to_engine_baseline` to re-anchor Phase 1's own small provisional
baselines (3–8 µSv/h) onto the frozen engine's room baselines (35–92
µSv/h, registry row 14) before evaluating detection, the forecasting
adapter scores `linearForecast` directly against Phase 1's raw,
un-rescaled series. Every MAE/RMSE figure in
`PHASE3A_SMOKE_TEST_REPORT.md` §3 is therefore on Phase 1's own small
scale, not the engine's room scale.

**Whether this matters was checked numerically, not assumed.** Using the
already-built `EngineBridge`, `build_rate_forecasts`,
`score_against_ground_truth`, `mae_rmse_by_horizon`, and
`skill_vs_persistence` (read-only; no code changed to produce this
check), a 40-point noisy-trend test series was built on Phase 1's own
`diagnostic_fluoroscopy` baseline (4.0 µSv/h, registry row 1) and
re-scored after multiplying every value by `k = 92.0 / 4.0 = 23.0` — the
exact ratio between that Phase 1 baseline and the engine's Cath Lab 3
room baseline (registry row 14), so the test uses two values already on
the record rather than an arbitrary number. Result:

| Horizon | MAE ratio (scaled/raw) | RMSE ratio (scaled/raw) | Skill vs. persistence, raw | Skill vs. persistence, scaled |
|---|---|---|---|---|
| 1 min | 23.0000 | 23.0000 | 0.300889463962662 | 0.300889463962664 |
| 2 min | 23.0000 | 23.0000 | 0.638424100239878 | 0.638424100239878 |
| 3 min | 23.0000 | 23.0000 | 0.725285959326467 | 0.725285959326467 |

MAE and RMSE scale **exactly** by the rescaling factor `k` at every
horizon (confirmed to the displayed precision). The skill-vs-persistence
score — a ratio of the candidate's and persistence's mean-squared errors,
both of which scale by `k²` — is **numerically unchanged** by rescaling,
to 12+ significant figures at every horizon.

**Conclusion, precisely stated:**
- The absolute MAE/RMSE values in `PHASE3A_SMOKE_TEST_REPORT.md` §3 are
  on Phase 1's own illustrative scale, not the engine's room scale — they
  would need rescaling first before being quoted as "the forecast error
  on a realistic room's dose-rate scale."
- The **relative** comparisons already reported — `linearForecast`'s
  skill score being negative at every horizon while persistence and
  exponential smoothing are not — are **unaffected** by this gap and
  remain valid as reported, because skill-vs-persistence is
  mathematically scale-invariant (confirmed above, not merely argued).
- This is a documentation finding, not a code change: per this round's
  explicit restriction, `forecast_adapter.py` has not been modified.
  Whether to add rescaling before any future *absolute*-unit result is
  reported is recorded as open in
  `UNRESOLVED_SCIENTIFIC_DECISIONS.md` item 13.

## 7. No statistical campaign has been run

Every number in `PHASE3A_SMOKE_TEST_REPORT.md` describes 8 specific
seeds. No claim of clinical or scientific predictive validity is made
anywhere in this phase's deliverables, per the explicit restriction.
