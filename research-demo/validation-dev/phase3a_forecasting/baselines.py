"""
Independent forecasting baselines: persistence and simple exponential
smoothing. Neither calls `linearForecast` or any other frozen-engine
forecasting logic -- both are implemented here, in plain Python, from
scratch. Both share the same validity gate as the real forecaster
(`forecast_adapter._window_valid_mask`, which calls the engine's own
`SimLab.pure.validReading`) so that any difference in scored accuracy
between methods reflects the forecasting method itself, not a difference
in which windows were even attempted -- the same design principle
already used for the detection baselines in phase2a_adapter/baselines.py.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .forecast_adapter import HORIZONS_MINUTES, TRAILING_POINTS, _window_valid_mask
from phase2a_adapter.engine_bridge import EngineBridge


def build_persistence_forecasts(bridge: EngineBridge, series: List[Optional[float]],
                                 trailing_points: int = TRAILING_POINTS) -> List[Dict[str, Any]]:
    """Forecast = the last valid reading in the window, repeated for
    every horizon. No parameters, no trend."""
    results = []
    n = len(series)
    for t in range(trailing_points - 1, n):
        window = series[t - trailing_points + 1: t + 1]
        if any(v is None for v in window) or not _window_valid_mask(bridge, window):
            results.append({"t": t, "skipped": True, "reason": "invalid_or_missing_in_window"})
            continue
        last = window[-1]
        results.append({
            "t": t, "skipped": False, "slope": 0.0,
            "forecast_rate_uSv_h": [last] * len(HORIZONS_MINUTES),
            "horizons_minutes": list(HORIZONS_MINUTES),
        })
    return results


def build_exponential_smoothing_forecasts(bridge: EngineBridge, series: List[Optional[float]],
                                           alpha: float, trailing_points: int = TRAILING_POINTS
                                           ) -> List[Dict[str, Any]]:
    """Simple (single) exponential smoothing over the same trailing
    window: s_1 = window[0]; s_i = alpha*window[i] + (1-alpha)*s_{i-1}.
    Forecast = the final smoothed level s_n, repeated for every horizon
    -- deliberately flat, unlike linearForecast's trend extrapolation,
    since simple exponential smoothing has no trend term.
    """
    results = []
    n = len(series)
    for t in range(trailing_points - 1, n):
        window = series[t - trailing_points + 1: t + 1]
        if any(v is None for v in window) or not _window_valid_mask(bridge, window):
            results.append({"t": t, "skipped": True, "reason": "invalid_or_missing_in_window"})
            continue
        level = window[0]
        for v in window[1:]:
            level = alpha * v + (1 - alpha) * level
        results.append({
            "t": t, "skipped": False, "slope": 0.0,
            "forecast_rate_uSv_h": [level] * len(HORIZONS_MINUTES),
            "horizons_minutes": list(HORIZONS_MINUTES),
            "alpha": alpha,
        })
    return results
