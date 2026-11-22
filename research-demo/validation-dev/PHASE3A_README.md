# Phase 3A — Forecasting Evaluation: Reproducibility Instructions

Covers `phase3a_forecasting/`: evaluates the frozen ALARAD v1.2.3
engine's own existing `linearForecast` function, per the Phase 3A
approval. Builds directly on `phase2a_adapter/`'s `EngineBridge` (same
read-only Playwright session against the unmodified frozen file).

## What this is, in one paragraph

This package does not implement a new forecasting model. It calls the
frozen engine's own, real, unmodified `linearForecast` function and
scores its output against ground truth with an explicit no-leakage
guarantee (every forecast is produced from data strictly at or before
the minute it is made for; see `forecast_adapter.build_rate_forecasts`'s
docstring and `tests/test_temporal_leakage.py` for a direct proof, not
just a code-review claim). Two independently-implemented baselines
(persistence, simple exponential smoothing) provide context, scored
through the same metrics.

**Read `PHASE3A_LIMITATIONS.md` section 1 before assuming any forecast
horizon beyond 3 minutes is achievable** — this was verified empirically
in this session, not assumed, and it is a real mismatch with the
methodology document's own placeholder language.

## Requirements

Same as `phase2a_adapter/`: Python 3.11, `playwright` (already
installed), the pre-installed Chromium at `/opt/pw-browsers/chromium`
(same disclosed version caveat as every prior phase). No new
dependency.

## Running the tests

From `research-demo/validation-dev/`:
```
python3 -m unittest discover -s phase3a_forecasting/tests -t . -v
```
33 tests, covering: the forecast contract (including a direct check
that `linearForecast` always returns exactly 3 future points regardless
of input length); constant/rising/falling exposure, missing
observations, and sensor faults (both hand-built deterministic series
and real Phase 1 output); temporal leakage (proved by mutation, not
inspection); both baselines, including the provisional-labeling check on
the exponential-smoothing `alpha`; the dose-rate-vs-cumulative-dose
distinction; and zero-dose/degenerate edge cases.

## Running the smoke test

From `research-demo/validation-dev/`:
```
python3 -m phase3a_forecasting.run_phase3a_smoke
```
Writes `phase3a_smoke_output/smoke_rows.json` and `smoke_summary.json`.
Eight archetypes, one seed each — a smoke test, not the statistical
campaign in `ICAIRE_Simulation_Validation_Methodology.md` section 7.

## Package layout

```
phase3a_forecasting/
  forecast_contract.py    verifies linearForecast is present and behaves as documented
  forecast_adapter.py      the real linearForecast call sequence; also the dose-rate-vs-
                            cumulative-dose distinction (task 7) via forecast_cumulative_dose
  baselines.py              persistence and exponential smoothing, independently implemented
  metrics.py                MAE/RMSE/skill-vs-persistence per horizon, undefined-not-crashing
  config.py / config/phase3a_config.json   reused-from-engine vs. new-provisional parameters
  run_phase3a_smoke.py      small smoke-test CLI
  tests/
    test_forecast_contract.py
    test_forecast_adapter.py       constant/rising/falling/missing/faults
    test_temporal_leakage.py       proved by mutation
    test_baselines.py
    test_dose_rate_vs_cumulative.py
    test_edge_cases.py              zero-dose and other degenerate inputs
```
