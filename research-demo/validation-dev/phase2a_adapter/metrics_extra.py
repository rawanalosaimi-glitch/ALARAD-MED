"""
Aggregate metrics across multiple worker evaluation results: false alarms
per worker-shift, and event-level detection delay as a distribution --
per ICAIRE_Simulation_Validation_Methodology.md section 5a, including its
explicit convention for scenarios with no true events or no alerts
(undefined ratios are excluded from precision/recall aggregates, never
coerced to 0 or 1, but every run still contributes to the false-alarm
count).

Takes a list of per-worker evaluation result dicts, as produced by
detection_adapter.evaluate_radiation_detection, dq_adapter.evaluate_dq_detection,
or baselines.py's functions -- all of which share the same TP/FP/FN/
detection_delays_minutes shape.
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional


def false_alarms_per_worker_shift(results: List[Dict[str, Any]]) -> float:
    """Total FP count across all results, divided by the number of
    worker-shifts (one result = one worker's participation in one run).
    Every result contributes its FP count to the numerator and 1 to the
    denominator, including zero-true-event runs -- a run that correctly
    stays quiet must not be dropped from this count."""
    if not results:
        return 0.0
    total_fp = sum(r["FP"] for r in results)
    return total_fp / len(results)


def aggregate_precision_recall(results: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    """Mean precision/recall/F1 across results, excluding any result
    whose value is undefined (None, i.e. a 0/0 ratio) from that
    statistic's own mean -- per the methodology's explicit convention.
    A run contributing an undefined precision can still contribute a
    defined recall, and vice versa; each statistic's exclusion is
    independent.
    """
    out: Dict[str, Optional[float]] = {}
    for key in ("precision", "recall", "f1"):
        values = [r[key] for r in results if r.get(key) is not None]
        out[key] = statistics.mean(values) if values else None
        out[f"{key}_n_defined"] = len(values)
        out[f"{key}_n_excluded_undefined"] = len(results) - len(values)
    return out


def detection_delay_distribution(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Pools every matched event's detection delay (TP only; an
    undetected event contributes no delay value, per the methodology)
    across all results, and reports median/IQR rather than only a mean,
    since detection delay is not expected to be symmetric."""
    delays: List[int] = []
    for r in results:
        delays.extend(r.get("detection_delays_minutes", []))
    if not delays:
        return {"n": 0, "median": None, "q1": None, "q3": None, "min": None, "max": None}
    sorted_delays = sorted(delays)
    n = len(sorted_delays)
    return {
        "n": n,
        "median": statistics.median(sorted_delays),
        "q1": sorted_delays[max(0, n // 4 - 1)] if n >= 4 else sorted_delays[0],
        "q3": sorted_delays[min(n - 1, (3 * n) // 4)] if n >= 4 else sorted_delays[-1],
        "min": sorted_delays[0],
        "max": sorted_delays[-1],
    }


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """One convenience call combining all of the above for a batch of
    per-worker results from the same method (candidate or one baseline)."""
    return {
        "n_worker_shifts": len(results),
        "false_alarms_per_worker_shift": false_alarms_per_worker_shift(results),
        **aggregate_precision_recall(results),
        "detection_delay": detection_delay_distribution(results),
    }
