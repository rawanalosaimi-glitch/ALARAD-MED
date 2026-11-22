# Phase 3A Smoke Test Report

**This is a smoke test, not scientific validation** — same discipline as
every prior phase's report. It answers: *does the forecasting adapter
run end-to-end against the real `linearForecast`, on real Phase 1
output, with no leakage?* It does not answer whether `linearForecast`,
persistence, or exponential smoothing forecasts well in any general
sense. All numbers below came from actually running the code in this
session on 2026-11-22.

## 1. Test run (real output)

Command: `python3 -m unittest discover -s phase3a_forecasting/tests -t . -v`

**Result: 33 passed, 0 failed, 0 skipped.**

| File | Tests | Purpose |
|---|---|---|
| `test_forecast_contract.py` | 4 | `linearForecast` present, behaves as documented, always returns exactly 3 future points |
| `test_forecast_adapter.py` | 9 | constant/rising/falling exposure, missing observations, sensor faults (hand-built + real Phase 1 output) |
| `test_temporal_leakage.py` | 3 | proved by mutating future data, not by code inspection |
| `test_baselines.py` | 6 | persistence/exponential-smoothing sanity, skill-score comparison, provisional labeling |
| `test_dose_rate_vs_cumulative.py` | 5 | rate-forecast vs. cumulative-dose-forecast distinction |
| `test_edge_cases.py` | 6 | zero-dose and other degenerate inputs |

## 2. Smoke batch results (real, 8 archetypes, one seed each)

Command: `python3 -m phase3a_forecasting.run_phase3a_smoke`

| Archetype | Windows | Skipped | Mean \|cumulative-dose forecast error\| (mSv) |
|---|---|---|---|
| normal | 477 | 0 | 3.4 × 10⁻⁶ |
| gradual_increase | 237 | 0 | 6.5 × 10⁻⁶ |
| sudden_increase | 477 | 0 | 3.3 × 10⁻⁵ |
| transient_spike | 717 | 0 | 6.1 × 10⁻⁶ |
| fault_missing | 237 | 11 | 3.1 × 10⁻⁶ |
| fault_invalid | 237 | 5 | 5.5 × 10⁻⁶ |
| fault_frozen | 477 | 0 | 3.2 × 10⁻⁶ |
| fault_delayed | 237 | 6 | 1.3 × 10⁻⁵ |

Every fault archetype's skip count is consistent with its fault window
touching at least one 4-point trailing window — confirmed individually
by `test_forecast_adapter.py`'s fault-specific tests, not just inferred
from this table.

## 3. Aggregate forecast accuracy (real, pooled across all 8 runs, 3,096 windows)

| Method | Horizon 1 min MAE (µSv/h) | Horizon 2 min MAE | Horizon 3 min MAE | Skill vs. persistence (h=1/2/3) |
|---|---|---|---|---|
| **Candidate (`linearForecast`)** | 0.257 | 0.359 | 0.466 | **−0.27 / −0.86 / −1.68** |
| Baseline: persistence | 0.206 | 0.237 | 0.265 | (reference) |
| Baseline: exponential smoothing (α=0.5) | 0.204 | 0.234 | 0.264 | +0.32 / +0.33 / +0.33 |

**This is a real, verified result for these 8 seeds — not an artifact
of a wrong adapter call.** At this smoke scale, `linearForecast`'s skill
score against persistence is **negative** at every horizon (worse than
simply repeating the last reading), while exponential smoothing is
consistently positive. See `PHASE3A_LIMITATIONS.md` section 4 for the
likely mechanism (OLS trend-fitting amplifying noise on short,
mostly-flat windows) and the explicit caveat that this smoke batch is
not a statistical sample.

## 4. Dose-rate vs. cumulative-dose distinction (confirmed, not just asserted)

For a flat 100 µSv/h series, the real engine's rate forecast is exactly
`[100, 100, 100]` µSv/h; the derived cumulative-dose forecast (new,
adapter-only logic — not an engine capability) is
`[0.001667, 0.003333, 0.005000]` mSv, matching the hand-computed
`Dose(mSv) = Rate(µSv/h) × Duration(h) / 1000` integration exactly
(`test_dose_rate_vs_cumulative.py`). The two outputs differ by roughly
five orders of magnitude in this example — confirming they cannot be
confused for one another in any report derived from this adapter.

## 5. What this report does not claim

- Does not claim `linearForecast`, persistence, or exponential smoothing
  is accurate or validated in any general sense — 8 seeds is a smoke
  test.
- Does not claim the negative skill score in §3 generalizes beyond this
  specific, flat-weighted smoke batch.
- Does not claim any forecast horizon beyond 3 minutes was evaluated —
  it was not, and is not achievable with the existing function (see
  `PHASE3A_LIMITATIONS.md` §1).
- Does not claim clinical or scientific predictive validity anywhere.
