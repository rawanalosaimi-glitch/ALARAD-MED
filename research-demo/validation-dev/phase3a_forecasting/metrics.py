"""
MAE, RMSE, and forecasting skill against persistence, at each of the
three horizons linearForecast actually produces (1, 2, 3 minutes ahead).

Only scored forecasts (not skipped, and with a non-None actual value at
that horizon) contribute to a given horizon's statistics -- a missing or
invalid future reading is excluded, never scored as zero error, matching
the "undefined, not 0" discipline already established in
phase2a_adapter/metrics_extra.py.
"""

from __future__ import annotations

import math
import statistics
from typing import Any, Dict, List, Optional

from .forecast_adapter import HORIZONS_MINUTES


def _pairs_for_horizon(scored: List[Dict[str, Any]], horizon_index: int) -> List[tuple]:
    pairs = []
    for r in scored:
        if r.get("skipped"):
            continue
        actual = r.get("actual_rate_uSv_h")
        if actual is None:
            continue
        a = actual[horizon_index]
        f = r["forecast_rate_uSv_h"][horizon_index]
        if a is None or (isinstance(a, float) and math.isnan(a)):
            continue
        pairs.append((f, a))
    return pairs


def mae_rmse_by_horizon(scored: List[Dict[str, Any]]) -> Dict[int, Dict[str, Optional[float]]]:
    out = {}
    for i, h in enumerate(HORIZONS_MINUTES):
        pairs = _pairs_for_horizon(scored, i)
        if not pairs:
            out[h] = {"n": 0, "mae": None, "rmse": None}
            continue
        errors = [f - a for f, a in pairs]
        mae = statistics.mean(abs(e) for e in errors)
        rmse = math.sqrt(statistics.mean(e * e for e in errors))
        out[h] = {"n": len(pairs), "mae": mae, "rmse": rmse}
    return out


def skill_vs_persistence(candidate_scored: List[Dict[str, Any]],
                          persistence_scored: List[Dict[str, Any]]) -> Dict[int, Optional[float]]:
    """Mean-squared-error skill score at each horizon:
        skill = 1 - MSE(candidate) / MSE(persistence)
    computed only over minutes `t` where BOTH methods produced a scored
    (non-skipped, non-None-actual) forecast at that horizon -- a paired
    comparison, not two independently-filtered samples.

    skill > 0: candidate beats persistence at this horizon.
    skill = 0: identical to persistence.
    skill < 0: worse than persistence.
    skill = None: undefined -- either no paired data, or persistence's
    own MSE is exactly 0 (a zero-error floor that cannot be improved on,
    reported as undefined rather than as -inf or a divide-by-zero).
    """
    cand_by_t = {r["t"]: r for r in candidate_scored if not r.get("skipped")}
    pers_by_t = {r["t"]: r for r in persistence_scored if not r.get("skipped")}
    shared_t = sorted(set(cand_by_t) & set(pers_by_t))

    out: Dict[int, Optional[float]] = {}
    for i, h in enumerate(HORIZONS_MINUTES):
        cand_sq, pers_sq = [], []
        for t in shared_t:
            c, p = cand_by_t[t], pers_by_t[t]
            actual_c = c.get("actual_rate_uSv_h")
            actual_p = p.get("actual_rate_uSv_h")
            if actual_c is None or actual_p is None:
                continue
            a_c, a_p = actual_c[i], actual_p[i]
            if a_c is None or a_p is None:
                continue
            cand_sq.append((c["forecast_rate_uSv_h"][i] - a_c) ** 2)
            pers_sq.append((p["forecast_rate_uSv_h"][i] - a_p) ** 2)
        if not cand_sq:
            out[h] = None
            continue
        mse_cand = statistics.mean(cand_sq)
        mse_pers = statistics.mean(pers_sq)
        if mse_pers == 0:
            out[h] = None
        else:
            out[h] = 1 - (mse_cand / mse_pers)
    return out


def summarize(scored: List[Dict[str, Any]], persistence_scored: Optional[List[Dict[str, Any]]] = None
              ) -> Dict[str, Any]:
    n_total = len(scored)
    n_skipped = sum(1 for r in scored if r.get("skipped"))
    result: Dict[str, Any] = {
        "n_windows": n_total,
        "n_skipped": n_skipped,
        "n_scored": n_total - n_skipped,
        "by_horizon": mae_rmse_by_horizon(scored),
    }
    if persistence_scored is not None:
        result["skill_vs_persistence"] = skill_vs_persistence(scored, persistence_scored)
    return result
