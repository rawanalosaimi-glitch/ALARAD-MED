# Forecasting Evaluation Readiness Checklist

**Purpose:** a single place that says, plainly, what is already built and
verified for forecasting evaluation, and what specifically remains before
`ICAIRE_Simulation_Validation_Methodology.md` §7's full statistical
campaign (≥30 seeds per class, balanced) could be run for forecasting.
This is a checklist, not a decision — nothing below has been run, and no
item being unchecked is being treated as resolved.

---

## 1. Already in place (built and verified, not assumed)

- [x] **Evaluation harness exists and runs end-to-end** against the real,
  unmodified, frozen `linearForecast` — `phase3a_forecasting/`, 33 tests
  passing (`PHASE3A_SMOKE_TEST_REPORT.md` §1).
- [x] **No-leakage proved by mutation**, not just code inspection
  (`tests/test_temporal_leakage.py`).
- [x] **The function's real contract is confirmed, not assumed**:
  `linearForecast` always returns exactly 3 future samples regardless of
  input length (tested for lengths 3/4/7/10) — the methodology document
  has been corrected to match this (Revision 5), rather than carrying an
  unexamined "15 minutes" placeholder.
- [x] **Two independent baselines exist and run**: persistence
  (parameter-free) and exponential smoothing (`alpha=0.5`, registry row
  20, marked `PROVISIONAL`).
- [x] **Metrics are defined and tested for degenerate cases**: MAE, RMSE,
  and skill-vs-persistence, all reporting `None`/undefined rather than 0
  or crashing when there is no scored pair or persistence's own MSE is 0
  (`tests/test_edge_cases.py`).
- [x] **Rate forecast vs. cumulative-dose forecast kept visibly
  distinct**, with the derived dose-integration calculation (adapter-only,
  not an engine capability) tested separately
  (`tests/test_dose_rate_vs_cumulative.py`).
- [x] **A smoke run across 8 archetypes has been executed and reported**,
  with an explicit, prominent statement that it is not a statistical
  sample (`PHASE3A_SMOKE_TEST_REPORT.md` §5).
- [x] **The real function's three call sites in the frozen engine have
  been inventoried**, and the one evaluated (`SimLab.runWorker`'s
  real-history, 4-point, all-valid-or-skip usage) has been identified as
  matching the methodology's own forecasting-baseline comparison design
  (`PHASE3A_LIMITATIONS.md` §2).
- [x] **The forecast-adapter/detection-adapter baseline-scale discrepancy
  has been found and its impact quantified**, not just flagged: absolute
  MAE/RMSE are on Phase 1's own scale, not the engine's room scale, but
  the already-reported skill-vs-persistence comparisons are
  mathematically scale-invariant and unaffected (`PHASE3A_LIMITATIONS.md`
  §6, verified numerically this round).

## 2. Remaining before the full statistical campaign

- [ ] **Decide whether `forecast_adapter.py` needs to rescale onto the
  engine's room baselines before computing absolute MAE/RMSE**, the way
  `detection_adapter.py` already does (`UNRESOLVED_SCIENTIFIC_DECISIONS.md`
  item 13). Not required for skill-score comparisons; required before any
  absolute-unit forecast-accuracy figure is reported as representing a
  realistic room's scale.
- [ ] **Resolve registry row 20** (the exponential-smoothing `alpha=0.5`)
  — either an RSO/domain sign-off that the illustrative value is an
  acceptable stand-in, or a sensitivity analysis sweeping `alpha` across
  a range (e.g. 0.1–0.9) so the campaign's baseline comparison is not
  silently sensitive to an unexamined constant
  (`UNRESOLVED_SCIENTIFIC_DECISIONS.md` item 14).
- [ ] **Decide the balanced-seed design for the forecasting campaign
  specifically** — the smoke batch's 8 archetypes were heavily weighted
  toward flat/near-flat scenarios (one likely cause of
  `linearForecast`'s negative smoke-scale skill score,
  `PHASE3A_LIMITATIONS.md` §4); the full campaign's per-archetype seed
  counts and class balance need to be chosen so this skew does not simply
  repeat at larger scale without comment.
- [ ] **Decide what to do, if anything, about the other two
  `linearForecast` call sites** (`evaluateExposure`'s synthetic display
  chart, and the Live Demo's contiguous-window convention,
  `PHASE3A_LIMITATIONS.md` §2) — currently out of scope; confirm this
  remains the case before the campaign, or scope a second evaluation if
  not.
- [ ] **Decide whether a longer forecast horizon is in scope for any
  future phase**, and if so by what technique, independently of running
  the campaign on the existing 3-sample horizon
  (`UNRESOLVED_SCIENTIFIC_DECISIONS.md` item 15; registry row 7,
  revised). Not a blocker for running the campaign on the horizons that
  exist, but should be decided so the campaign's scope statement is
  accurate.
- [ ] **Obtain at least the same sign-off priority already requested for
  detection** (registry rows 14/15/17/19) extended to row 20, before
  treating any campaign-scale forecasting result as more than a smoke
  test — per `SCIENTIFIC_PARAMETER_REVIEW_PACKAGE.md`'s own "must remain
  blocked" list (§7), which already names this.
- [ ] **Explicit approval to run the campaign itself** — per this round's
  restriction, no code has been written or run toward the full campaign;
  that remains a separate, future approval regardless of the items above.

## 3. What this checklist does not claim

- Does not claim the smoke-scale negative-skill finding for
  `linearForecast` is statistically established — it is 8 seeds,
  reported as preliminary throughout (`PHASE3A_SMOKE_TEST_REPORT.md` §3,
  `PHASE3A_LIMITATIONS.md` §4).
- Does not claim every unchecked item above is a hard blocker in the
  sense of "the campaign cannot technically run" — several (row 20's
  sign-off, the longer-horizon scope decision) are scientific-sign-off
  gates, not software defects. They are listed because running the
  campaign before they are addressed would produce numbers whose
  interpretation is contested before they are even reported, exactly the
  failure mode `SCIENTIFIC_PARAMETER_REVIEW_PACKAGE.md` exists to avoid.
- Does not itself approve, schedule, or run any future work.
