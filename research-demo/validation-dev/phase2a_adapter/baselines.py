"""
Comparison baselines for radiation-anomaly detection (methodology section
4a). These are NOT the frozen detector and are never presented as
equivalent to it: Baseline 0 and Baseline 2/3 are independently
implemented here, in plain Python, using no code from the frozen release.
Baseline 1 (the engine's own confirmation-window ablated to K=1) is simply
the real adapter called with K=1 -- it is not reimplemented, and is
provided here only as a thin, clearly-labeled wrapper for symmetry when
comparing all four side by side.

Every baseline's per-minute `flagged` array is scored through the SAME
real-engine primitives used for the candidate detector
(`SimLab.pure.buildEpisodes` / `matchEvents` / `metrics`), so that any
difference in reported precision/recall/F1 between methods reflects a
difference in the per-minute classification rule under test, not a
difference in scoring methodology.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .detection_adapter import (
    classify_series,
    decode_observed_value,
    evaluate_radiation_detection,
    phase1_baseline_rate,
    rescale_to_engine_baseline,
    valid_mask,
)
from .engine_bridge import EngineBridge


def _score_against_engine(bridge: EngineBridge, flagged: List[bool],
                           truth_events: List[Dict[str, int]], K: int, grace: int) -> Dict[str, Any]:
    episodes_result = bridge.evaluate(
        "(args) => SimLab.pure.buildEpisodes(args.flagged, args.K, null)",
        {"flagged": flagged, "K": K},
    )
    episodes = episodes_result["episodes"]
    match_result = bridge.evaluate(
        "(args) => SimLab.pure.matchEvents(args.events, args.episodes, args.grace)",
        {"events": truth_events, "episodes": episodes, "grace": grace},
    )
    TP = sum(1 for m in match_result["matches"] if m is not None)
    FN = len(truth_events) - TP
    FP = len(match_result["fp"])
    mm = bridge.evaluate(
        "(args) => SimLab.pure.metrics(args.TP, args.FP, args.FN)",
        {"TP": TP, "FP": FP, "FN": FN},
    )
    detection_delays = []
    for i, m in enumerate(match_result["matches"]):
        if m is not None:
            detection_delays.append(episodes[m]["det"] - truth_events[i]["start"])
    return {"episodes": episodes, "TP": TP, "FP": FP, "FN": FN,
            "precision": mm["precision"], "recall": mm["recall"], "f1": mm["f1"],
            "detection_delays_minutes": detection_delays}


def baseline_0_always_normal(bridge: EngineBridge, worker: Dict[str, Any],
                              grace: int = 2) -> Dict[str, Any]:
    """Never flags any minute. A sanity floor."""
    n = len(worker["series"]["observed_rate_uSv_h"])
    truth_events = [{"start": e["start"], "end": e["end"]} for e in worker["truth_events"]]
    result = _score_against_engine(bridge, [False] * n, truth_events, K=1, grace=grace)
    result.update({"baseline": "baseline_0_always_normal", "worker_id": worker["worker_id"]})
    return result


def baseline_1_engine_k1(bridge: EngineBridge, worker: Dict[str, Any],
                          phase1_config, engine_baselines: Dict[str, float],
                          grace: int = 2) -> Dict[str, Any]:
    """The REAL engine's own detector, confirmation window ablated to
    K=1. Not a reimplementation -- this is evaluate_radiation_detection
    itself, called with K=1."""
    result = evaluate_radiation_detection(
        bridge, worker, phase1_config, engine_baselines, K=1, grace=grace)
    result["baseline"] = "baseline_1_engine_k1"
    return result


def baseline_2_fixed_threshold(bridge: EngineBridge, worker: Dict[str, Any],
                                phase1_config, engine_baselines: Dict[str, float],
                                phase2a_config, grace: int = 2) -> Dict[str, Any]:
    """Independently-specified: an instantaneous per-reading comparison
    against a fixed multiple of the engine's own baseline for this room/
    procMult. No averaging window, no confirmation window. The threshold
    comparison itself does not call evaluateExposure or any other engine
    classification function -- deliberately not derived from the engine's
    own tuned thresholds. The VALIDITY gate (which minutes are even
    eligible to be compared) is now shared with the candidate detector
    via `valid_mask` (Phase 2C item 2, PHASE2B_INTEGRATION_AUDIT.md
    section 5, Finding 1) -- previously this baseline used its own
    narrower `None`/NaN-only check, which happened to agree with the
    engine's real validity rule for every fault Phase 1 currently
    generates, but was not guaranteed to in general."""
    cfg = phase2a_config.baseline("baseline_2_fixed_threshold")
    multiple = cfg["fixed_multiple"]

    room = worker["room"]
    p1_baseline = phase1_baseline_rate(worker, phase1_config)
    engine_baseline = engine_baselines[room] * worker["proc_mult"]
    observed = [decode_observed_value(v) for v in worker["series"]["observed_rate_uSv_h"]]
    rescaled = rescale_to_engine_baseline(observed, p1_baseline, engine_baseline)
    valid = valid_mask(bridge, rescaled)

    flagged = []
    for v, is_valid in zip(rescaled, valid):
        if not is_valid:
            flagged.append(False)
        else:
            flagged.append(v >= engine_baseline * multiple)

    truth_events = [{"start": e["start"], "end": e["end"]} for e in worker["truth_events"]]
    result = _score_against_engine(bridge, flagged, truth_events, K=1, grace=grace)
    result.update({
        "baseline": "baseline_2_fixed_threshold", "worker_id": worker["worker_id"],
        "fixed_multiple": multiple, "engine_baseline_uSv_h": engine_baseline,
    })
    return result


def baseline_3_moving_average(bridge: EngineBridge, worker: Dict[str, Any],
                               phase1_config, engine_baselines: Dict[str, float],
                               phase2a_config, grace: int = 2) -> Dict[str, Any]:
    """Independently-specified: a fixed-window trailing moving average of
    readings, compared against a fixed multiple of the engine's own
    baseline. No confirmation window. Its characterization as
    'conventional practice' is explicitly withdrawn (methodology section
    4a, Revision 2) pending a citation -- see phase2a_config.json's
    disclaimer and Parameter Registry row 6. The validity gate is shared
    with the candidate detector via `valid_mask` (Phase 2C item 2), same
    as baseline_2_fixed_threshold above."""
    cfg = phase2a_config.baseline("baseline_3_moving_average")
    window = cfg["window_minutes"]
    multiple = cfg["fixed_multiple"]

    room = worker["room"]
    p1_baseline = phase1_baseline_rate(worker, phase1_config)
    engine_baseline = engine_baselines[room] * worker["proc_mult"]
    observed = [decode_observed_value(v) for v in worker["series"]["observed_rate_uSv_h"]]
    rescaled = rescale_to_engine_baseline(observed, p1_baseline, engine_baseline)
    valid = valid_mask(bridge, rescaled)

    flagged = []
    for t in range(len(rescaled)):
        win = [v for v, is_valid in zip(rescaled[max(0, t - window + 1):t + 1],
                                          valid[max(0, t - window + 1):t + 1])
               if is_valid]  # only engine-valid readings enter the average
        if not win:
            flagged.append(False)
            continue
        avg = sum(win) / len(win)
        flagged.append(avg >= engine_baseline * multiple)

    truth_events = [{"start": e["start"], "end": e["end"]} for e in worker["truth_events"]]
    result = _score_against_engine(bridge, flagged, truth_events, K=1, grace=grace)
    result.update({
        "baseline": "baseline_3_moving_average", "worker_id": worker["worker_id"],
        "fixed_multiple": multiple, "window_minutes": window,
        "engine_baseline_uSv_h": engine_baseline,
    })
    return result
