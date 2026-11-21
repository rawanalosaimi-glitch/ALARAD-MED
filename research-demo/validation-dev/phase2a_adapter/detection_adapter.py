"""
Radiation-anomaly detection evaluation adapter.

This module feeds Phase 1 synthetic observations into the frozen engine's
own, real, unmodified functions -- `evaluateExposure` for per-minute
classification, `SimLab.pure.buildEpisodes` for confirmation-window episode
detection, `SimLab.pure.matchEvents` for ground-truth matching, and
`SimLab.pure.metrics` for precision/recall/F1 -- and nothing else computes
or approximates that logic. Task 8's requirement ("confirm the adapter
reproduces the frozen detector's outputs on reference scenarios") is
checked in tests/test_reference_reproduction.py by running this exact
call sequence against the engine's own built-in S1-S6 scenarios and
diffing against `SimLab.run()`'s own output.

**Scope limitation (see PHASE2A_LIMITATIONS.md item 1): personal-mode
workers only.** Phase 1's output schema (phase1_simulator/output.py) does
not currently carry the area-monitoring geometry (distance-over-time,
shielding, reference distance) needed to call `evaluateExposure` correctly
for area-mode workers. Calling it with invented geometry would be exactly
the kind of silent approximation Phase 2A is required not to do, so
area-mode radiation-anomaly evaluation is not implemented here; attempting
it raises NotImplementedError rather than guessing.

**The rescaling problem (see PHASE2A_LIMITATIONS.md item 2):** Phase 1's
provisional procedure-class baselines (phase1_simulator/config/
simulation_config.json) and the frozen engine's own `baselineRates`/
`CONFIG` thresholds are two independently-chosen provisional parameter
sets, not calibrated to each other. Feeding Phase 1's raw µSv/h values
into the engine as-is would produce near-meaningless classifications (a
"step to 4x Phase-1-baseline" event can still be far below the engine's
own, much larger, baseline). `rescale_to_engine_baseline` preserves the
*ratio* of each reading to Phase 1's own baseline exactly, while mapping
that ratio onto the engine's own baseline for the same room/procMult --
so the engine classifies the data using its own real thresholds, against
an injected pattern whose *shape* is exactly what Phase 1 generated. This
is a disclosed, documented input transformation performed by the adapter,
not a change to either Phase 1's or the frozen engine's own logic.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from .engine_bridge import EngineBridge

HORIZON_MIN = 30  # matches the frozen engine's own SimLab HORIZON_MIN default


def decode_observed_value(v: Any) -> Optional[float]:
    """Reverses phase1_simulator.output._json_safe's NaN/Infinity string
    encoding. None stays None (missing). Does not touch Phase 1's files;
    this only decodes values already read from a Phase 1 output dict."""
    if v is None:
        return None
    if v == "NaN":
        return float("nan")
    if v == "Infinity":
        return float("inf")
    if v == "-Infinity":
        return float("-inf")
    return float(v)


def phase1_baseline_rate(worker: Dict[str, Any], phase1_config) -> float:
    """Reconstructs the exact baseline_rate_uSv_h Phase 1 used for this
    worker, by reapplying phase1_simulator.scenario._make_worker's own
    formula (baseline = procedure's configured rate * proc_mult) against
    Phase 1's own shipped config -- not a new or independently guessed
    number."""
    proc_cfg = phase1_config.procedure_classes()[worker["procedure_class"]]
    return proc_cfg["baseline_rate_uSv_h"] * worker["proc_mult"]


def rescale_to_engine_baseline(observed_series: List[Optional[float]],
                                phase1_baseline: float,
                                engine_baseline: float) -> List[Optional[float]]:
    """Multiplies every valid reading by (engine_baseline / phase1_baseline),
    preserving each reading's ratio to its own (Phase 1) baseline exactly,
    while re-expressing it against the engine's own baseline for this
    room/procMult. None/NaN/Infinity pass through unchanged -- fault
    semantics (missing/invalid) are a property of the reading's validity,
    not its magnitude, and must not be altered by rescaling.
    """
    ratio = engine_baseline / phase1_baseline
    out = []
    for v in observed_series:
        if v is None:
            out.append(None)
            continue
        fv = decode_observed_value(v) if isinstance(v, str) else v
        if fv is None or (isinstance(fv, float) and (math.isnan(fv) or math.isinf(fv))):
            out.append(fv)
        else:
            out.append(fv * ratio)
    return out


def classify_series(bridge: EngineBridge, rescaled_series: List[Optional[float]],
                     room: str, proc_mult: float, dur_min: int = HORIZON_MIN) -> List[Dict[str, Any]]:
    """Calls the engine's own evaluateExposure once per minute, exactly as
    the engine's own SimLab.runWorker does: a reading is only passed to
    evaluateExposure if SimLab.pure.validReading accepts it (the engine's
    own validity gate, reused here rather than re-derived); otherwise the
    minute is recorded as the engine's own 'invalid'/not-flagged outcome,
    matching the real app's own call pattern.
    """
    js = """
    (args) => {
      const { series, room, procMult, dur } = args;
      return series.map(r => {
        if (r === null || !SimLab.pure.validReading(r)) {
          return { valid: false, riskClass: 'invalid', flagged: false };
        }
        const ev = evaluateExposure({ room, procMult, rate: r, dur, dist: 1, refDist: 1, shield: 1, mode: 'personal' });
        return { valid: true, riskClass: ev.riskClass, flagged: ev.riskClass !== 'low', deviation: ev.deviation, workerRate: ev.workerRate };
      });
    }
    """
    # NaN cannot cross JSON (page.evaluate serializes args as JSON); encode
    # as null, which validReading already rejects -- semantically correct
    # (an invalid/non-physical reading), not a loss of information for
    # this call's purpose.
    safe_series = [None if (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) else v
                   for v in rescaled_series]
    return bridge.evaluate(js, {"series": safe_series, "room": room, "procMult": proc_mult, "dur": dur_min})


def evaluate_radiation_detection(bridge: EngineBridge, worker: Dict[str, Any],
                                  phase1_config, engine_baselines: Dict[str, float],
                                  K: int = 1, grace: int = 2) -> Dict[str, Any]:
    """Full radiation-anomaly evaluation for one Phase 1 worker record
    (as produced by phase1_simulator.output.run_to_dict), against the real
    frozen engine. Personal mode only -- see module docstring.

    Returns a dict with: per-minute classification, episodes (from the
    real engine), TP/FP/FN, precision/recall/F1 (from the real engine),
    and per-matched-event detection delay.
    """
    if worker["mode"] != "personal":
        raise NotImplementedError(
            "Area-mode radiation-anomaly evaluation is out of scope for "
            "Phase 2A -- see PHASE2A_LIMITATIONS.md item 1. "
            f"worker_id={worker.get('worker_id')!r} mode={worker['mode']!r}"
        )

    room = worker["room"]
    if room not in engine_baselines:
        raise ValueError(
            f"Room {room!r} is not one of the engine's own baselineRates "
            f"keys ({sorted(engine_baselines)}); cannot evaluate faithfully."
        )

    p1_baseline = phase1_baseline_rate(worker, phase1_config)
    engine_baseline = engine_baselines[room] * worker["proc_mult"]

    observed = [decode_observed_value(v) for v in worker["series"]["observed_rate_uSv_h"]]
    rescaled = rescale_to_engine_baseline(observed, p1_baseline, engine_baseline)

    per_minute = classify_series(bridge, rescaled, room, worker["proc_mult"])
    flagged = [m["flagged"] for m in per_minute]

    episodes_result = bridge.evaluate(
        "(args) => SimLab.pure.buildEpisodes(args.flagged, args.K, null)",
        {"flagged": flagged, "K": K},
    )
    episodes = episodes_result["episodes"]

    truth_events = [{"start": e["start"], "end": e["end"]} for e in worker["truth_events"]]
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
            det = episodes[m]["det"]
            detection_delays.append(det - truth_events[i]["start"])

    return {
        "worker_id": worker["worker_id"],
        "room": room,
        "proc_mult": worker["proc_mult"],
        "phase1_baseline_uSv_h": p1_baseline,
        "engine_baseline_uSv_h": engine_baseline,
        "rescale_ratio": engine_baseline / p1_baseline,
        "K": K,
        "grace": grace,
        "n_minutes": len(flagged),
        "episodes": episodes,
        "TP": TP, "FP": FP, "FN": FN,
        "precision": mm["precision"], "recall": mm["recall"], "f1": mm["f1"],
        "detection_delays_minutes": detection_delays,
    }
