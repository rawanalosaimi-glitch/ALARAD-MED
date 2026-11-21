"""
Structured output writer for Phase 1 simulation runs.

Produces a JSON record per run matching the ground-truth record shape
proposed in ICAIRE_Simulation_Validation_Methodology.md section 3, plus
the full per-minute series and dose accounting needed for later-phase
evaluation. Every output explicitly labels itself as Phase 1 (simulator
and ground-truth generation only) so it cannot be mistaken for an
evaluation result.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict

from .units import CUMULATIVE_DOSE_UNIT, DOSE_RATE_UNIT, TIME_STEP_MINUTES

SCHEMA_VERSION = "1.0.0"

PHASE_LABEL = (
    "Phase 1 - simulator and ground-truth generation only. No detector, "
    "forecaster, baseline comparator, or evaluation metric (precision, "
    "recall, F1, MAE, etc.) is computed by this output. That evaluation "
    "work is explicitly a later phase, per "
    "ICAIRE_Simulation_Validation_Methodology.md -- this file is not a "
    "scientific validation result."
)


def _json_safe(v):
    """Round-trip-safe encoding for values that plain json.dumps cannot
    represent exactly (NaN/Infinity): encoded as explicit sentinel strings
    rather than silently becoming non-standard JSON tokens, so equality
    comparisons on the resulting dict behave as expected (NaN != NaN as a
    float, but the sentinel string compares equal to itself)."""
    if v is None:
        return None
    if isinstance(v, float):
        if math.isnan(v):
            return "NaN"
        if math.isinf(v):
            return "Infinity" if v > 0 else "-Infinity"
        return v
    return v


def run_to_dict(simulated: Dict[str, Any], config) -> Dict[str, Any]:
    run = simulated["run"]
    workers_out = []
    for wr in simulated["workers"]:
        w = wr["worker"]
        da = wr["dose_account"]
        workers_out.append({
            "worker_id": w.worker_id,
            "room": w.room,
            "procedure_class": w.procedure_class,
            "proc_mult": w.proc_mult,
            "mode": w.mode,
            "dose_label": wr["dose_label"],
            # Additive (Phase 2C item 3): area-monitoring geometry, None
            # for personal-mode workers. Previously computed internally
            # by scenario.py but not serialized -- see
            # PHASE2B_INTEGRATION_AUDIT.md section 3.
            "area_params": dict(w.area_params) if w.area_params is not None else None,
            "truth_events": [
                {"start": e.start, "end": e.end, "label": e.label}
                for e in w.truth_events
            ],
            "fault_events": [
                {"kind": f.kind, "start": f.start, "end": f.end, "params": f.params}
                for f in w.fault_windows
            ],
            "true_dose_mSv": wr["true_dose_mSv"],
            "observed_dose_mSv": da.observed_dose_mSv,
            "trusted_minutes": da.trusted_minutes,
            "uncertain_minutes": da.uncertain_minutes,
            "unmonitored_minutes": da.unmonitored_minutes,
            "series": {
                "true_rate_uSv_h": [_json_safe(v) for v in wr["true_series"]],
                "observed_rate_uSv_h": [_json_safe(v) for v in wr["observed_series"]],
                "observed_status_per_minute": list(da.per_minute_status),
                # Additive (Phase 2C item 3): raw, pre-conversion area-
                # monitor reading; None for personal-mode workers.
                "area_monitor_raw_rate_uSv_h": (
                    [_json_safe(v) for v in wr["area_monitor_raw_rate_uSv_h"]]
                    if wr.get("area_monitor_raw_rate_uSv_h") is not None else None
                ),
            },
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE_LABEL,
        "methodology_reference": "ICAIRE_Simulation_Validation_Methodology.md (Revision 2)",
        "config_schema_version": config.schema_version,
        "config_disclaimer": config.raw["_disclaimer"],
        "units": {
            "dose_rate": DOSE_RATE_UNIT,
            "cumulative_dose": CUMULATIVE_DOSE_UNIT,
            "time_step_minutes": TIME_STEP_MINUTES,
        },
        "run_id": run.run_id,
        "archetype": run.archetype,
        "seed": run.seed,
        "shift_minutes": run.shift_minutes,
        "workers": workers_out,
    }


def write_run_output(simulated: Dict[str, Any], config, path: Path) -> None:
    data = run_to_dict(simulated, config)
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
