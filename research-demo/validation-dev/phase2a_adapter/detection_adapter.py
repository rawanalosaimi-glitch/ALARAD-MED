"""
Radiation-anomaly detection evaluation adapter.

This module feeds Phase 1 synthetic observations into the frozen engine's
own, real, unmodified functions -- `evaluateExposure` for per-minute
classification, `AlaradSafety.immediateAlert` for the dose-based
confirmation-window bypass (Phase 2C item 1 -- see below),
`SimLab.pure.buildEpisodes` for episode detection, `SimLab.pure.matchEvents`
for ground-truth matching, and `SimLab.pure.metrics` for precision/recall/
F1 -- and nothing else computes or approximates that logic. Task 8's
requirement ("confirm the adapter reproduces the frozen detector's
outputs on reference scenarios") is checked in
tests/test_reference_reproduction.py by running this exact call sequence
against the engine's own built-in reference scenarios and diffing against
`SimLab.run()`/`SafetyLab.run()`'s own output.

**Immediate-alert bypass (Phase 2C item 1, PHASE2B_INTEGRATION_AUDIT.md
section 4):** the frozen engine's own default policy
(`AlaradSafety.policy()` = `{mode:'dose', doseMsv:null}`) lets a
sufficiently high projected dose raise an alert immediately, bypassing
the K-minute confirmation window. Phase 2A's adapter always called
`buildEpisodes(flagged, K, null)`, ignoring this -- which the audit found
never actually mattered for S1-S6 (the bypass never fires there at any
tested K) but DOES matter for S8 at K=3/K=5 (live-checked:
`episode.immediate` is `true` there). `evaluate_radiation_detection` now
defaults to `use_immediate_alert=True`, reading the engine's own live
policy exactly as `SimLab.runWorker`/`SafetyLab.runWorker` do, so this
adapter's default behavior matches the engine's own default behavior.
Passing `use_immediate_alert=False` recovers the confirmation-only
comparison mode Phase 2A originally (and Baselines 2/3 by definition,
per the methodology, still) use.

**Area-mode evaluation (Phase 2C item 4, PHASE2B_INTEGRATION_AUDIT.md
section 3):** now implemented, using Phase 1's additive
`series.area_monitor_raw_rate_uSv_h` and `area_params` fields (the raw,
pre-inverse-square-conversion area-monitor reading and geometry) so the
frozen engine performs its own exponent-2 conversion via
`evaluateExposure(mode:'area', dist, refDist, shield)`, rather than this
adapter receiving an already-converted value.

**The rescaling problem (see PHASE2A_LIMITATIONS.md item 2,
PHASE2B_INTEGRATION_AUDIT.md sections 1-2):** Phase 1's provisional
procedure-class baselines and the frozen engine's own `baselineRates`/
`CONFIG` thresholds are two independently-chosen provisional parameter
sets, not calibrated to each other. `rescale_to_engine_baseline` preserves
the *ratio* of each reading to Phase 1's own baseline exactly, while
mapping that ratio onto the engine's own baseline for the same
room/procMult. The audit found this is severity-neutral for the
deviation-based classification term (provably scale-invariant) but not
for the dose-based term in general, though it does not change outcomes
for the engine's current CONFIG/baselineRates/dur combination -- see
PHASE2B_INTEGRATION_AUDIT.md section 1 and PHASE2C's own re-audit
(section 7 of PHASE2C_CORRECTIVE_IMPLEMENTATION.md) for why this
approach is retained rather than eliminated in this phase.
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
    number. Mode-independent: the formula is the same for personal- and
    area-mode workers."""
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


def _nan_safe(series: List[Optional[float]]) -> List[Optional[float]]:
    """NaN/Infinity cannot cross JSON (page.evaluate serializes args as
    JSON); encode as None, which the engine's own validReading already
    rejects -- semantically correct (an invalid/non-physical reading),
    not a loss of information for any call this is used in."""
    return [None if (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) else v
            for v in series]


def valid_mask(bridge: EngineBridge, series: List[Optional[float]]) -> List[bool]:
    """Returns, per minute, whether the engine's own `SimLab.pure.validReading`
    accepts the (already rescaled) reading. Shared by the candidate
    detector's classify_series and, per Phase 2C item 2, by baselines.py's
    independently-defined comparator algorithms -- so every method in
    this package gates on the SAME real validity rule, even though the
    classification logic that follows differs between methods."""
    return bridge.evaluate(
        "(series) => series.map(r => r !== null && SimLab.pure.validReading(r))",
        _nan_safe(series),
    )


def classify_series(bridge: EngineBridge, rescaled_series: List[Optional[float]],
                     room: str, proc_mult: float, dur_min: int = HORIZON_MIN,
                     mode: str = "personal",
                     dist_per_minute: Optional[List[float]] = None,
                     ref_dist: float = 1.0, shield: float = 1.0) -> List[Dict[str, Any]]:
    """Calls the engine's own evaluateExposure once per minute, exactly as
    the engine's own SimLab.runWorker/SafetyLab.runWorker do: a reading is
    only passed to evaluateExposure if SimLab.pure.validReading accepts it
    (the engine's own validity gate, reused here rather than re-derived);
    otherwise the minute is recorded as the engine's own 'invalid'/not-
    flagged outcome. Also computes, per minute, exactly what
    SimLab.runWorker computes for the immediate-alert bypass (line 2964
    of the frozen release): `valid && AlaradSafety.immediateAlert({cumulativeDose}, {mode:'dose', doseMsv: AlaradSafety.policy().doseMsv})`,
    reading the engine's own live policy rather than a hardcoded value.

    For mode='area', `dist_per_minute` (one entry per minute, from Phase 1's
    `area_params`) is required; the engine performs its own exponent-2
    inverse-square conversion internally from the raw `rate` passed in.
    """
    if mode == "area" and dist_per_minute is None:
        raise ValueError("dist_per_minute is required when mode='area'")

    js = """
    (args) => {
      const { series, room, procMult, dur, mode, distPerMinute, refDist, shield } = args;
      const pol = { mode: 'dose', doseMsv: AlaradSafety.policy().doseMsv };
      return series.map((r, t) => {
        if (r === null || !SimLab.pure.validReading(r)) {
          return { valid: false, riskClass: 'invalid', flagged: false, cumulativeDose: null, immediate: false };
        }
        const dist = mode === 'area' ? distPerMinute[t] : 1;
        const ev = evaluateExposure({ room, procMult, rate: r, dur, dist, refDist, shield, mode });
        const immediate = AlaradSafety.immediateAlert({ cumulativeDose: ev.cumulativeDose }, pol);
        return {
          valid: true, riskClass: ev.riskClass, flagged: ev.riskClass !== 'low',
          deviation: ev.deviation, workerRate: ev.workerRate,
          cumulativeDose: ev.cumulativeDose, immediate,
        };
      });
    }
    """
    return bridge.evaluate(js, {
        "series": _nan_safe(rescaled_series), "room": room, "procMult": proc_mult,
        "dur": dur_min, "mode": mode, "distPerMinute": dist_per_minute,
        "refDist": ref_dist, "shield": shield,
    })


def _dist_per_minute(area_params: Dict[str, Any], n_minutes: int) -> List[float]:
    move_at = area_params["move_at"]
    before = area_params["distance_before_m"]
    after = area_params["distance_after_m"]
    return [before if t < move_at else after for t in range(n_minutes)]


def evaluate_radiation_detection(bridge: EngineBridge, worker: Dict[str, Any],
                                  phase1_config, engine_baselines: Dict[str, float],
                                  K: int = 1, grace: int = 2,
                                  use_immediate_alert: bool = True) -> Dict[str, Any]:
    """Full radiation-anomaly evaluation for one Phase 1 worker record
    (as produced by phase1_simulator.output.run_to_dict), against the real
    frozen engine. Handles both personal- and area-mode workers.

    Returns a dict with: per-minute classification, episodes (from the
    real engine, including the real `immediate` flag per episode),
    TP/FP/FN, precision/recall/F1 (from the real engine), and per-matched-
    event detection delay.
    """
    room = worker["room"]
    if room not in engine_baselines:
        raise ValueError(
            f"Room {room!r} is not one of the engine's own baselineRates "
            f"keys ({sorted(engine_baselines)}); cannot evaluate faithfully."
        )

    p1_baseline = phase1_baseline_rate(worker, phase1_config)
    engine_baseline = engine_baselines[room] * worker["proc_mult"]

    if worker["mode"] == "personal":
        observed = [decode_observed_value(v) for v in worker["series"]["observed_rate_uSv_h"]]
        rescaled = rescale_to_engine_baseline(observed, p1_baseline, engine_baseline)
        per_minute = classify_series(bridge, rescaled, room, worker["proc_mult"], mode="personal")
    elif worker["mode"] == "area":
        if worker.get("area_params") is None or worker["series"].get("area_monitor_raw_rate_uSv_h") is None:
            raise ValueError(
                f"worker_id={worker.get('worker_id')!r} is area-mode but is missing "
                f"area_params / series.area_monitor_raw_rate_uSv_h -- regenerate it "
                f"with the current phase1_simulator.output schema (Phase 2C item 3)."
            )
        ap = worker["area_params"]
        raw = [decode_observed_value(v) for v in worker["series"]["area_monitor_raw_rate_uSv_h"]]
        rescaled = rescale_to_engine_baseline(raw, p1_baseline, engine_baseline)
        dist_pm = _dist_per_minute(ap, len(rescaled))
        per_minute = classify_series(
            bridge, rescaled, room, worker["proc_mult"], mode="area",
            dist_per_minute=dist_pm, ref_dist=ap["reference_distance_m"],
            shield=ap["shielding"])
    else:
        raise ValueError(f"Unknown worker mode {worker['mode']!r}")

    flagged = [m["flagged"] for m in per_minute]
    imm = [m["immediate"] for m in per_minute] if use_immediate_alert else None

    episodes_result = bridge.evaluate(
        "(args) => SimLab.pure.buildEpisodes(args.flagged, args.K, args.imm)",
        {"flagged": flagged, "K": K, "imm": imm},
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
        "mode": worker["mode"],
        "proc_mult": worker["proc_mult"],
        "phase1_baseline_uSv_h": p1_baseline,
        "engine_baseline_uSv_h": engine_baseline,
        "rescale_ratio": engine_baseline / p1_baseline,
        "K": K,
        "grace": grace,
        "use_immediate_alert": use_immediate_alert,
        "n_minutes": len(flagged),
        "episodes": episodes,
        "n_immediate_episodes": sum(1 for e in episodes if e.get("immediate")),
        "TP": TP, "FP": FP, "FN": FN,
        "precision": mm["precision"], "recall": mm["recall"], "f1": mm["f1"],
        "detection_delays_minutes": detection_delays,
    }
