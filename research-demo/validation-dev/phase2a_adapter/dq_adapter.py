"""
Sensor/data-quality fault detection evaluation adapter.

Deliberately a SEPARATE module from detection_adapter.py (task 4: "clearly
distinguish radiation anomalies from sensor/data-quality faults"). This
module never calls evaluateExposure, never reads truth_events, and never
mixes its TP/FP/FN with the radiation-layer numbers computed by
detection_adapter.py. It drives the frozen engine's own, real, unmodified
`AlaradSafety.sensorStep` state machine and -- like detection_adapter.py
-- reuses the engine's own `SimLab.pure.buildEpisodes`/`matchEvents`/
`metrics` for episode construction, ground-truth matching, and scoring.
No classification or matching logic is reimplemented here.

Mode-independent: sensorStep operates on observation validity/timing, not
on room geometry, so this module covers both personal- and area-mode
Phase 1 workers (unlike detection_adapter.py's radiation layer, which is
personal-mode only this phase -- see PHASE2A_LIMITATIONS.md).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from .detection_adapter import decode_observed_value, phase1_baseline_rate, rescale_to_engine_baseline
from .engine_bridge import EngineBridge

# States the frozen engine itself does not treat as "healthy and usable
# right now" -- reused directly from AlaradSafety's own documented
# UNAVAIL list (STALE, DISCONNECTED, INVALID) plus SUSPECTED_FROZEN, which
# AlaradSafety's own `uncertain` flag marks separately. A DQ episode is
# built from minutes where either is true.
DQ_FLAGGED_STATES = {"STALE", "DISCONNECTED", "INVALID", "SUSPECTED_FROZEN"}


def build_observations(worker: Dict[str, Any], phase1_config=None,
                        engine_baselines: Optional[Dict[str, float]] = None
                        ) -> List[Optional[Dict[str, Any]]]:
    """Reconstructs the {ts, value} (or None) observation the real engine's
    sensorStep expects, per minute, from a Phase 1 worker record's
    observed series and fault_events metadata.

    - missing fault minutes: obs = None (no sample received).
    - delayed fault minutes, after the initial lag-length gap: the value
      shown is Phase 1's own faults.py "stale, lag-minutes-old" value, but
      Phase 1's output does not separately carry *which* past timestamp it
      claims to be. This adapter reconstructs that claimed timestamp from
      the fault's own recorded `params["lag"]`, so sensorStep sees exactly
      the staleness the fault was designed to represent.
    - every other minute (including invalid/frozen fault minutes, whose
      effect is already encoded in the *value* itself): obs = {ts: t,
      value: v}, i.e. claimed to be current -- sensorStep's own validity
      and repeat-value logic then determines INVALID / SUSPECTED_FROZEN
      from the value, exactly as it would for a real sensor.

    **Rescaling (if phase1_config and engine_baselines are given):** valid
    readings are rescaled to the engine's own baseline for this worker's
    room/procMult, exactly as detection_adapter.rescale_to_engine_baseline
    does for the radiation layer. This was found necessary empirically,
    not assumed in advance: feeding Phase 1's raw, much-smaller
    provisional baseline values (a few uSv/h) directly into sensorStep
    caused spurious SUSPECTED_FROZEN false positives, because
    AlaradSafety's own repeat-value quantization (resolution = 0.1 uSv/h)
    is calibrated against the engine's own baseline scale (tens of uSv/h)
    -- at Phase 1's smaller scale, ordinary +/-5% measurement noise
    between consecutive minutes can round to the same 0.1 uSv/h bucket
    purely by coincidence, with no fault present. See
    PHASE2A_SMOKE_TEST_REPORT.md for the real smoke-batch run where this
    was first observed (sudden_increase: 0 faults injected, 1 false
    positive reported, before this rescaling was added).
    """
    series = [decode_observed_value(v) for v in worker["series"]["observed_rate_uSv_h"]]
    if phase1_config is not None and engine_baselines is not None:
        p1_baseline = phase1_baseline_rate(worker, phase1_config)
        engine_baseline = engine_baselines[worker["room"]] * worker["proc_mult"]
        series = rescale_to_engine_baseline(series, p1_baseline, engine_baseline)
    delayed_ts_offset: Dict[int, int] = {}
    for f in worker.get("fault_events", []):
        if f["kind"] == "delayed":
            lag = int(f["params"]["lag"])
            for t in range(f["start"] + lag, f["end"]):
                delayed_ts_offset[t] = lag

    obs: List[Optional[Dict[str, Any]]] = []
    for t, v in enumerate(series):
        if v is None:
            obs.append(None)
            continue
        if isinstance(v, float) and math.isnan(v):
            # NaN cannot cross JSON; represent as a value validateValue
            # will reject (negative), which is semantically equivalent
            # ("not a valid finite reading") for sensorStep's purposes.
            obs.append({"ts": t, "value": -1.0})
            continue
        ts = t - delayed_ts_offset[t] if t in delayed_ts_offset else t
        obs.append({"ts": ts, "value": v})
    return obs


def run_sensor_state_machine(bridge: EngineBridge,
                              observations: List[Optional[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Steps the engine's own AlaradSafety.sensorStep once per minute,
    threading its own returned state forward exactly as the real app
    would (previous -> next), never reimplemented."""
    js = """
    (obsList) => {
      let prev = AlaradSafety.newSensor();
      const out = [];
      for (let t = 0; t < obsList.length; t++) {
        const r = AlaradSafety.sensorStep(prev, obsList[t], t, null);
        out.push({ state: r.state, usable: r.usable, uncertain: r.uncertain, code: r.code });
        prev = r.s;
      }
      return out;
    }
    """
    return bridge.evaluate(js, observations)


def evaluate_dq_detection(bridge: EngineBridge, worker: Dict[str, Any],
                           phase1_config=None,
                           engine_baselines: Optional[Dict[str, float]] = None,
                           grace: int = 2) -> Dict[str, Any]:
    """Full sensor/data-quality fault evaluation for one Phase 1 worker
    record, against the real frozen engine's sensorStep. Mode-independent.

    Pass phase1_config and engine_baselines (as returned by
    engine_contract.snapshot_engine_constants(bridge)["baselineRates"])
    so observations are rescaled to the engine's own baseline scale --
    see build_observations' docstring for why this is required, not
    optional, for a meaningful result.
    """
    observations = build_observations(worker, phase1_config, engine_baselines)
    steps = run_sensor_state_machine(bridge, observations)
    flagged = [s["state"] in DQ_FLAGGED_STATES for s in steps]

    episodes_result = bridge.evaluate(
        "(args) => SimLab.pure.buildEpisodes(args.flagged, 1, null)",
        {"flagged": flagged},
    )
    episodes = episodes_result["episodes"]

    fault_windows = [{"start": f["start"], "end": f["end"]} for f in worker.get("fault_events", [])]
    match_result = bridge.evaluate(
        "(args) => SimLab.pure.matchEvents(args.events, args.episodes, args.grace)",
        {"events": fault_windows, "episodes": episodes, "grace": grace},
    )

    TP = sum(1 for m in match_result["matches"] if m is not None)
    FN = len(fault_windows) - TP
    FP = len(match_result["fp"])
    mm = bridge.evaluate(
        "(args) => SimLab.pure.metrics(args.TP, args.FP, args.FN)",
        {"TP": TP, "FP": FP, "FN": FN},
    )

    detection_delays = []
    for i, m in enumerate(match_result["matches"]):
        if m is not None:
            det = episodes[m]["det"]
            detection_delays.append(det - fault_windows[i]["start"])

    return {
        "worker_id": worker["worker_id"],
        "mode": worker["mode"],
        "grace": grace,
        "n_minutes": len(flagged),
        "states": [s["state"] for s in steps],
        "episodes": episodes,
        "TP": TP, "FP": FP, "FN": FN,
        "precision": mm["precision"], "recall": mm["recall"], "f1": mm["f1"],
        "detection_delays_minutes": detection_delays,
    }
