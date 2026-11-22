"""
Dose-rate forecasting evaluation adapter.

Calls the frozen engine's own, real, unmodified `linearForecast` function
-- nothing here reimplements or approximates its arithmetic. The only
code written for this module is the *orchestration* around that call:
building the trailing window, gating it on the engine's own
`SimLab.pure.validReading` (reused, not re-derived), and scoring the
result against ground truth that always lies strictly in the future of
the window used to produce it (see `build_rate_forecasts`'s docstring
for the exact no-leakage guarantee, and
`tests/test_temporal_leakage.py` for the proof).

**Exact contract, verified empirically in this session (not assumed from
reading the source alone) -- see PHASE3A documentation for the full
investigation:**
- `linearForecast(points)` fits an ordinary-least-squares line to
  `points` (equally spaced at x = 0, 1, ..., len(points)-1) and returns
  `{slope, next}`, where `next` is **always exactly 3 values**, at
  x = len(points), len(points)+1, len(points)+2 -- i.e. always exactly
  3 steps past the end of whatever window is given, regardless of the
  window's own length. This is hardcoded in the frozen release
  (`next:[n,n+1,n+2]`), not a configurable horizon.
- The engine's own real usage (`SimLab.runWorker`, frozen release line
  2971) calls it on a **fixed 4-point trailing window** of per-minute
  dose-rate readings (`PRED_LEN=4`), and **skips the forecast entirely**
  if any of those 4 readings is invalid (`win.some(x=>!x.valid)`). This
  module reproduces exactly that windowing and skip rule, reusing
  `PRED_LEN=4` from `phase3a_config.json` (itself copied from the
  frozen release, not independently chosen).
- **This function forecasts dose RATE (uSv/h), not cumulative dose.**
  See `forecast_cumulative_dose` below for a clearly separate, adapter-
  only derived calculation that integrates a rate forecast into a
  projected cumulative dose -- the frozen engine itself never does this
  (its own `cumulativeDose` field, documented in
  ICAIRE_Simulation_Validation_Methodology.md section 1, is a constant-
  rate *projection*, not a trend-based *forecast* of future dose).

**Mismatch with the methodology document, documented per Phase 3A task
10 before any assumption was made or any evaluation protocol changed:**
`ICAIRE_Simulation_Validation_Methodology.md` section 5 lists a
"longer horizon (e.g. 15 minutes)" as a placeholder for forecast
evaluation (registry row 7). The frozen engine's actual `linearForecast`,
as verified above, **cannot** produce a forecast beyond 3 steps past the
end of its input window, no matter how that window is constructed --
the 3-step limit is hardcoded in the function's own return value, not a
property of the call site. Reaching a 15-minute horizon would require
either (a) feeding the function's own 3-step predictions back into
itself as if they were new observations (a cascading/recursive technique
that compounds uncertainty and is not what the frozen engine does
anywhere), or (b) a different forecasting function entirely -- both
explicitly out of scope for this phase (no new forecasting model may be
implemented). This module therefore evaluates only the horizons the real
function actually produces: 1, 2, and 3 minutes ahead. See
PHASE3A_LIMITATIONS.md section 1.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from phase2a_adapter.detection_adapter import decode_observed_value
from phase2a_adapter.engine_bridge import EngineBridge

TRAILING_POINTS = 4  # frozen engine's own PRED_LEN, reused unchanged
HORIZONS_MINUTES = (1, 2, 3)  # frozen engine's own PRED_AHEAD=3, reused unchanged

DOSE_INCREMENT_FORMULA_NOTE = (
    "Dose (mSv) = Dose Rate (uSv/h) x Duration (h) / 1000 -- the same rule "
    "already established in phase1_simulator/units.py and documented in "
    "ICAIRE_Simulation_Validation_Methodology.md section 1, reused here, "
    "not redefined."
)


def _window_valid_mask(bridge: EngineBridge, window: List[Optional[float]]) -> bool:
    """True only if every reading in the window passes the engine's own
    validReading rule -- mirrors SimLab.runWorker's own
    `win.some(x=>!x.valid)` skip condition exactly (inverted)."""
    flags = bridge.evaluate(
        "(series) => series.map(r => r !== null && SimLab.pure.validReading(r))",
        [None if v is None else v for v in window],
    )
    return all(flags)


def build_rate_forecasts(bridge: EngineBridge, series: List[Optional[float]],
                          trailing_points: int = TRAILING_POINTS) -> List[Dict[str, Any]]:
    """For every minute `t` from `trailing_points - 1` to the end of
    `series`, builds the trailing window `series[t-trailing_points+1 : t+1]`
    (i.e. only data at or before `t`) and, if every reading in it is
    engine-valid, calls the real `linearForecast` on it.

    **No-leakage guarantee:** the window passed to `linearForecast` is a
    slice ending at index `t` (inclusive) -- it never includes
    `series[t+1]` or anything later. The result is returned without
    looking at `series[t+1:]` at all; any comparison against future
    ground truth (see `score_against_ground_truth`) happens strictly
    *after* this function has already produced its forecast, as a
    separate step, using the forecast value already computed. Changing
    `series[t+1:]` after calling this function cannot change what it
    already returned for minute `t` -- this is the property
    `tests/test_temporal_leakage.py` verifies directly, not merely by
    code inspection.
    """
    results = []
    n = len(series)
    for t in range(trailing_points - 1, n):
        window = series[t - trailing_points + 1: t + 1]
        if any(v is None for v in window) or not _window_valid_mask(bridge, window):
            results.append({"t": t, "skipped": True, "reason": "invalid_or_missing_in_window"})
            continue
        fc = bridge.evaluate("(p) => linearForecast(p)", window)
        results.append({
            "t": t, "skipped": False, "slope": fc["slope"],
            "forecast_rate_uSv_h": fc["next"],  # [t+1, t+2, t+3], in that order
            "horizons_minutes": list(HORIZONS_MINUTES),
        })
    return results


def score_against_ground_truth(forecasts: List[Dict[str, Any]],
                                series: List[Optional[float]]) -> List[Dict[str, Any]]:
    """Adds, to each non-skipped forecast, the actual future value at
    each horizon (series[t+h]), read only now -- after the forecast
    itself was already produced by build_rate_forecasts. A future value
    that is itself missing/invalid is recorded as None and excluded from
    any metric computed over these results (see metrics.py), never
    treated as zero error.
    """
    n = len(series)
    scored = []
    for r in forecasts:
        if r["skipped"]:
            scored.append(r)
            continue
        t = r["t"]
        actual = []
        for h in HORIZONS_MINUTES:
            idx = t + h
            v = series[idx] if idx < n else None
            actual.append(decode_observed_value(v) if isinstance(v, str) else v)
        out = dict(r)
        out["actual_rate_uSv_h"] = actual
        scored.append(out)
    return scored


def forecast_cumulative_dose(forecasts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Derived, adapter-only calculation -- NOT present anywhere in the
    frozen engine. Integrates each non-skipped rate forecast forward,
    one minute at a time, into a projected cumulative dose (mSv) over
    the same 3-minute horizon, using the dose-integration rule already
    established elsewhere in this project (see module docstring). This
    exists specifically to keep "forecasting dose rate" and "forecasting
    cumulative dose" visibly distinct outputs (Phase 3A task 7) rather
    than letting a reader conflate the two.
    """
    out = []
    for r in forecasts:
        if r["skipped"]:
            out.append(r)
            continue
        rates = r["forecast_rate_uSv_h"]
        cumulative = []
        running = 0.0
        for rate in rates:
            running += rate * (1.0 / 60.0) / 1000.0  # 1-minute step, uSv/h -> mSv
            cumulative.append(running)
        merged = dict(r)
        merged["forecast_cumulative_dose_mSv"] = cumulative
        out.append(merged)
    return out


def true_cumulative_dose_over_horizon(series_true: List[Optional[float]], t: int,
                                       horizons_minutes=HORIZONS_MINUTES) -> List[Optional[float]]:
    """The ACTUAL cumulative dose that accrues from minute t+1 through
    each horizon, computed from the true (noiseless) series -- the
    ground truth `forecast_cumulative_dose`'s output should be compared
    against. Returns None at any horizon where the true series does not
    extend far enough, rather than a truncated/wrong sum.
    """
    n = len(series_true)
    out = []
    running = 0.0
    ok = True
    last_h = 0
    for h in horizons_minutes:
        idx = t + h
        if idx >= n or not ok:
            out.append(None)
            ok = False
            continue
        for k in range(t + last_h + 1, idx + 1):
            v = series_true[k]
            if v is None:
                ok = False
                break
            running += v * (1.0 / 60.0) / 1000.0
        last_h = h
        out.append(running if ok else None)
    return out
