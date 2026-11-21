# Phase 2A — Detection Evaluation Integration: Reproducibility Instructions

Covers `phase2a_adapter/`: the detection-evaluation adapter built against
the frozen ALARAD v1.2.3 release, per the Phase 2A approval.

## What this is, in one paragraph

This package does **not** reimplement the frozen engine's detection logic.
It loads the unmodified frozen HTML file in a real headless browser
(Playwright) and calls the engine's own, already-exposed functions
(`evaluateExposure`, `SimLab.pure.buildEpisodes`, `SimLab.pure.matchEvents`,
`SimLab.pure.metrics`, `AlaradSafety.sensorStep`) directly, feeding them
Phase 1 synthetic data. `tests/test_reference_reproduction.py` proves this
is faithful, not approximated: it reconstructs the engine's own built-in
reference scenarios from scratch through this adapter's call sequence and
confirms an exact match against the engine's own `SimLab.run()` /
`SafetyLab.run()` output.

## Requirements

- Python 3.11 (same as Phase 1).
- **One new dependency: `playwright`** (already installed in this
  session; version used: see `python3 -m pip show playwright`). This is
  the one place Phase 2A departs from Phase 1's "stdlib only" rule,
  because driving the real, unmodified frozen engine requires a real
  browser — there is no stdlib way to execute the frozen file's
  JavaScript faithfully.
- The pre-installed Chromium at `/opt/pw-browsers/chromium`, for the same
  reason recorded in `Verification_Rerun_Report.md`: the network policy
  in this environment blocks downloading Playwright's pinned Chromium
  build. The same disclosed version caveat (141.0.7390.37 pinned vs.
  153.0.8010.12 actually used) applies to every test and smoke run in
  this package.

## Running the tests

From `research-demo/validation-dev/`:
```
python3 -m unittest discover -s phase2a_adapter/tests -t . -v
```
All 25 tests are expected to pass; `PHASE2A_SMOKE_TEST_REPORT.md` records
the actual run, including one real bug this suite caught and that was
fixed during this session (not hidden).

These tests launch a real browser per test class (one browser, reused
across that class's tests, via `setUpClass`/`tearDownClass`) and take
roughly 10 seconds total — slower than Phase 1's pure-Python tests, but
that cost is the price of testing against the real engine rather than an
approximation of it.

## Running the smoke test

From `research-demo/validation-dev/`:
```
python3 -m phase2a_adapter.run_phase2a_smoke
```
Writes `phase2a_smoke_output/smoke_rows.json` (per-worker results) and
`smoke_summary.json` (aggregated metrics per method) by default. This is
explicitly a smoke test (10 personal-mode archetypes, one seed each), not
the statistical evaluation campaign described in
`ICAIRE_Simulation_Validation_Methodology.md` section 7.

## What "integration, not approximation" means here, concretely

- Zero lines of this package reimplement per-minute risk classification,
  episode/confirmation-window logic, ground-truth matching, or
  precision/recall/F1. Every one of those calls goes to the real,
  unmodified frozen file, loaded read-only.
- `phase2a_adapter/baselines.py`'s two new comparison baselines (fixed-
  threshold, moving-average) are the one place genuinely new
  classification logic was written — and they are never called "the
  detector," never claimed equivalent to it, and are scored through the
  same real-engine `buildEpisodes`/`matchEvents`/`metrics` calls as the
  real candidate, so any difference in results reflects the
  classification rule under test, not the scoring methodology.
- `engine_contract.py` checks, every time a bridge session starts, that
  every function/object this adapter depends on is still present and
  still the right type in the live page — if a future copy of the
  release ever breaks that contract, this fails loudly with
  `EngineContractError`, rather than this adapter silently falling back
  to guessing what the engine would have done.

## Known, disclosed input-scale issue and its fix (read before extending this adapter)

Phase 1's provisional procedure-class baselines
(`phase1_simulator/config/simulation_config.json`) and the frozen
engine's own `baselineRates`/`CONFIG` thresholds are two independently-
chosen numeric scales. Feeding Phase 1's raw values into the engine
directly produces near-meaningless results (both for radiation
classification, where the deviation-from-baseline calculation would be
dominated by the scale mismatch rather than the injected event, and for
the sensor-fault layer, where `AlaradSafety`'s 0.1 µSv/h repeat-value
quantization produced spurious `SUSPECTED_FROZEN` false positives at
Phase 1's smaller scale). `detection_adapter.rescale_to_engine_baseline`
fixes this by preserving each reading's ratio to its own (Phase 1)
baseline while re-expressing it against the engine's real baseline for
that room/procMult; `dq_adapter.build_observations` applies the same
rescaling. See `PHASE2A_SMOKE_TEST_REPORT.md` for the real before/after
numbers from this session.

## Package layout

```
phase2a_adapter/
  engine_bridge.py       read-only Playwright session against the frozen file, with SHA-256 re-verification
  engine_contract.py      the exact API surface this adapter depends on, and a verifier
  detection_adapter.py     radiation-anomaly evaluation (personal-mode only -- see PHASE2A_LIMITATIONS.md)
  dq_adapter.py            sensor/data-quality fault evaluation (mode-independent)
  baselines.py             Baseline 0 (always-normal), 1 (engine K=1 ablation), 2 (fixed-threshold, new), 3 (moving-average, new)
  metrics_extra.py         false-alarms-per-worker-shift, detection-delay distribution, degenerate-case handling
  config.py / config/phase2a_config.json   provisional baseline thresholds, enforced-labeled
  run_phase2a_smoke.py     small smoke-test CLI
  tests/
    test_engine_contract.py           the automatic "stop and report" guard
    test_reference_reproduction.py    task 8: exact-match proof against the engine's own S1-S6/S7
    test_ground_truth_matching.py     task 7: matching, temporal alignment, false alarms, missing data, zero-event
    test_baselines.py
    test_dual_layer.py                task 4: radiation vs. DQ independence
```
