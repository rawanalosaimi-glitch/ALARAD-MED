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
any future phase attempts one.

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

## 5. New provisional parameter not yet in the registry

`baseline_exponential_smoothing.alpha` (currently 0.5,
`phase3a_config.json`) is a new choice introduced this phase and is not
yet a row in `SCIENTIFIC_PARAMETER_REVIEW_PACKAGE.md`'s registry. Per
task 8, it is labeled `PROVISIONAL` in its own config file, but has not
been added as a new numbered registry row — consistent with this
project's established practice of not silently expanding that document
without being asked, and flagged here so the gap is not lost (the same
treatment `SENSOR_P` received before being added as row 19).

## 6. No statistical campaign has been run

Every number in `PHASE3A_SMOKE_TEST_REPORT.md` describes 8 specific
seeds. No claim of clinical or scientific predictive validity is made
anywhere in this phase's deliverables, per the explicit restriction.
