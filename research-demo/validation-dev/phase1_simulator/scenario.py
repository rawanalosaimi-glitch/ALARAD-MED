"""
Scenario/run generation: builds a reproducible worker roster, per-worker
exposure pattern, and injected ground truth (radiation events and sensor
faults) for one simulated shift, from a seed and the provisional config
ranges.

The 13 archetypes below are a deliberately generalized, independently
designed and implemented analogue of the structure documented in
Ground_Truth_Scenarios_S1-S13.md (normal / gradual increase / sudden
increase / transient spike / relocation / multi-worker / each of the four
fault kinds / fault-during-event / multi-worker faults / concurrent
radiation+fault) -- generalized because, per
ICAIRE_Simulation_Validation_Methodology.md section 2/3, parameters here
are *sampled* from declared provisional ranges per seed, rather than
hand-fixed as the original 13 scenarios are. No code or data is copied from
the frozen v1.2.3 release or from Ground_Truth_Scenarios_S1-S13.md; this is
an independent implementation built to the methodology's specification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import area_model, faults, patterns
from .faults import FaultWindow
from .patterns import EventWindow
from .rng import make_rng

ARCHETYPES = [
    "normal",
    "gradual_increase",
    "sudden_increase",
    "transient_spike",
    "area_relocation",
    "multi_worker_mixed",
    "fault_missing",
    "fault_invalid",
    "fault_frozen",
    "fault_delayed",
    "fault_during_event",
    "multi_worker_faults",
    "concurrent_alert_and_fault",
]

ROOMS = [
    "Cath Lab 1", "Cath Lab 2", "Cath Lab 3",
    "Fluoroscopy Suite", "CT Suite", "PET/CT Suite",
]


@dataclass
class WorkerSpec:
    worker_id: str
    room: str
    procedure_class: str
    proc_mult: float
    mode: str  # "personal" | "area"
    baseline_rate_uSv_h: float
    pattern: Dict[str, Any]
    area_params: Optional[Dict[str, Any]]
    truth_events: List[EventWindow] = field(default_factory=list)
    fault_windows: List[FaultWindow] = field(default_factory=list)


@dataclass
class RunSpec:
    run_id: str
    archetype: str
    seed: int
    shift_minutes: int
    workers: List[WorkerSpec] = field(default_factory=list)


# ---------------------------------------------------------------- sampling --

def _pick_procedure(rng, config):
    classes = config.procedure_classes()
    names = sorted(classes.keys())
    name = rng.choice(names)
    return name, classes[name]


def _sample_proc_mult(rng, proc_cfg) -> float:
    lo, hi = proc_cfg["proc_mult_range"]
    return rng.uniform(lo, hi)


def _sample_shift_minutes(rng, config) -> int:
    return rng.choice(config.shift_lengths_minutes())


def _event_ranges(config):
    p = config.provisional_parameters
    return p["event_magnitude_range"], p["event_duration_range_minutes"]


def _fault_ranges(config):
    return config.provisional_parameters["fault_duration_range_minutes"]


def _make_worker(rng, config, worker_id: str, room: Optional[str] = None,
                  procedure: Optional[str] = None) -> WorkerSpec:
    if procedure is None:
        proc_name, proc_cfg = _pick_procedure(rng, config)
    else:
        proc_name, proc_cfg = procedure, config.procedure_classes()[procedure]
    room = room or rng.choice(ROOMS)
    proc_mult = _sample_proc_mult(rng, proc_cfg)
    baseline = proc_cfg["baseline_rate_uSv_h"] * proc_mult
    return WorkerSpec(
        worker_id=worker_id, room=room, procedure_class=proc_name,
        proc_mult=proc_mult, mode="personal", baseline_rate_uSv_h=baseline,
        pattern={"type": "flat"}, area_params=None,
    )


def _add_ramp(rng, worker: WorkerSpec, shift_minutes: int, config) -> None:
    mag, dur = _event_ranges(config)
    peak_mult = rng.uniform(*mag["ramp_peak_multiplier"])
    duration = int(rng.uniform(*dur["ramp_minutes"]))
    start = rng.randint(5, max(5, shift_minutes - duration - 10))
    peak_at = start + duration
    hold_until = min(peak_at + max(1, duration // 4), shift_minutes)
    worker.pattern = {
        "type": "ramp", "start": start, "peak_at": peak_at,
        "hold_until": hold_until, "peak_mult": peak_mult,
    }
    worker.truth_events.append(
        EventWindow(start=start, end=hold_until, label="Gradual increase"))


def _add_step(rng, worker: WorkerSpec, shift_minutes: int, config) -> None:
    mag, dur = _event_ranges(config)
    mult = rng.uniform(*mag["step_multiplier"])
    duration = int(rng.uniform(*dur["step_minutes"]))
    start = rng.randint(5, max(5, shift_minutes - duration - 5))
    end = start + duration
    worker.pattern = {"type": "step", "start": start, "end": end, "mult": mult}
    worker.truth_events.append(
        EventWindow(start=start, end=end, label="Sudden increase"))


def _add_spike(rng, worker: WorkerSpec, shift_minutes: int, config,
                label_truth: bool = False) -> None:
    mag, dur = _event_ranges(config)
    mult = rng.uniform(*mag["spike_multiplier"])
    length = int(rng.uniform(*dur["spike_minutes"]))
    length = max(1, length)
    at = rng.randint(5, max(5, shift_minutes - length - 5))
    worker.pattern = {
        "type": "spikes", "spikes": [{"at": at, "len": length, "mult": mult}],
    }
    if label_truth:
        worker.truth_events.append(
            EventWindow(start=at, end=at + length, label="Sudden increase"))
    # else: deliberately NOT added to truth_events. Reuses the S5
    # convention documented in Ground_Truth_Scenarios_S1-S13.md: a
    # transient this short is not a labelled abnormal event -- this is a
    # false-positive-suppression test case, not a missed-detection case.


def _add_fault(rng, worker: WorkerSpec, shift_minutes: int, config,
                kind: str) -> FaultWindow:
    lo, hi = _fault_ranges(config)[kind]
    duration = max(1, int(rng.uniform(lo, hi)))
    start = rng.randint(2, max(2, shift_minutes - duration - 2))
    end = start + duration
    params: Dict[str, Any] = {}
    if kind == "delayed":
        params["lag"] = max(1, duration // 2)
    fw = FaultWindow(kind=kind, start=start, end=end, params=params)
    worker.fault_windows.append(fw)
    return fw


# ----------------------------------------------------------- run building --

def generate_run(archetype: str, seed: int, config) -> RunSpec:
    """Build a fully-specified RunSpec (roster, patterns, injected ground
    truth) for one archetype and seed. Deterministic: the same (archetype,
    seed, config) always produces an identical RunSpec.
    """
    if archetype not in ARCHETYPES:
        raise ValueError(f"Unknown archetype: {archetype!r}")

    def rng_for(idx: int, purpose: str):
        return make_rng(seed, "worker", archetype, str(idx), purpose)

    shift_rng = make_rng(seed, "shift", archetype)
    shift_minutes = _sample_shift_minutes(shift_rng, config)

    run = RunSpec(run_id=f"{archetype}-{seed}", archetype=archetype,
                  seed=seed, shift_minutes=shift_minutes)

    if archetype == "normal":
        w = _make_worker(rng_for(0, "attrs"), config, "W-00")
        run.workers.append(w)

    elif archetype == "gradual_increase":
        w = _make_worker(rng_for(0, "attrs"), config, "W-00")
        _add_ramp(rng_for(0, "pattern"), w, shift_minutes, config)
        run.workers.append(w)

    elif archetype == "sudden_increase":
        w = _make_worker(rng_for(0, "attrs"), config, "W-00")
        _add_step(rng_for(0, "pattern"), w, shift_minutes, config)
        run.workers.append(w)

    elif archetype == "transient_spike":
        w = _make_worker(rng_for(0, "attrs"), config, "W-00")
        _add_spike(rng_for(0, "pattern"), w, shift_minutes, config,
                   label_truth=False)
        run.workers.append(w)

    elif archetype == "area_relocation":
        w = _make_worker(rng_for(0, "attrs"), config, "W-00")
        w.mode = "area"
        mag, dur = _event_ranges(config)
        prng = rng_for(0, "pattern")
        mult = prng.uniform(*mag["step_multiplier"])
        duration = int(prng.uniform(*dur["step_minutes"]))
        start = prng.randint(5, max(5, shift_minutes - duration - 10))
        move_at = start + duration // 2
        end = start + duration
        w.pattern = {"type": "step", "start": start, "end": end, "mult": mult}
        w.area_params = {
            "reference_distance_m": config.provisional_parameters[
                "area_monitor_model"]["reference_distance_m"],
            "distance_before_m": 1.0,
            "distance_after_m": 2.5,
            "move_at": move_at,
            "shielding": 1.0,
            "true_exponent": 1.7,
        }
        w.truth_events.append(
            EventWindow(start=start, end=move_at, label="High exposure near source"))
        run.workers.append(w)

    elif archetype == "multi_worker_mixed":
        w0 = _make_worker(rng_for(0, "attrs"), config, "W-00")
        _add_spike(rng_for(0, "pattern"), w0, shift_minutes, config, label_truth=False)
        w1 = _make_worker(rng_for(1, "attrs"), config, "W-01")
        _add_step(rng_for(1, "pattern"), w1, shift_minutes, config)
        w2 = _make_worker(rng_for(2, "attrs"), config, "W-02")
        _add_ramp(rng_for(2, "pattern"), w2, shift_minutes, config)
        run.workers.extend([w0, w1, w2])

    elif archetype in ("fault_missing", "fault_invalid", "fault_frozen", "fault_delayed"):
        kind = archetype.split("_", 1)[1]
        w = _make_worker(rng_for(0, "attrs"), config, "W-00")
        _add_fault(rng_for(0, "fault"), w, shift_minutes, config, kind)
        run.workers.append(w)

    elif archetype == "fault_during_event":
        w = _make_worker(rng_for(0, "attrs"), config, "W-00")
        _add_step(rng_for(0, "pattern"), w, shift_minutes, config)
        ev = w.truth_events[0]
        frng = rng_for(0, "fault")
        missing_hi = _fault_ranges(config)["missing"][1]
        fdur = max(1, min(int((ev.end - ev.start) * 0.4), int(missing_hi)))
        foffset = max(1, (ev.end - ev.start) // 4)
        fstart = ev.start + foffset
        fend = min(fstart + fdur, ev.end)
        w.fault_windows.append(FaultWindow(kind="missing", start=fstart, end=fend, params={}))
        # consume frng deterministically even though this archetype needs
        # no further random draws, so later archetypes' derived seeds are
        # unaffected by whether this branch draws from frng.
        frng.random()
        run.workers.append(w)

    elif archetype == "multi_worker_faults":
        w0 = _make_worker(rng_for(0, "attrs"), config, "W-00")
        _add_fault(rng_for(0, "fault"), w0, shift_minutes, config, "missing")
        w1 = _make_worker(rng_for(1, "attrs"), config, "W-01")
        _add_step(rng_for(1, "pattern"), w1, shift_minutes, config)
        _add_fault(rng_for(1, "fault"), w1, shift_minutes, config, "invalid")
        w2 = _make_worker(rng_for(2, "attrs"), config, "W-02")
        _add_fault(rng_for(2, "fault"), w2, shift_minutes, config, "frozen")
        run.workers.extend([w0, w1, w2])

    elif archetype == "concurrent_alert_and_fault":
        w = _make_worker(rng_for(0, "attrs"), config, "W-00")
        _add_step(rng_for(0, "pattern"), w, shift_minutes, config)
        ev = w.truth_events[0]
        frng = rng_for(0, "fault")
        lo, hi = _fault_ranges(config)["delayed"]
        fdur = max(1, int(frng.uniform(lo, hi)))
        fstart = min(ev.start + 2, max(0, shift_minutes - fdur - 1))
        fend = min(fstart + fdur, shift_minutes)
        lag = max(1, fdur // 2)
        w.fault_windows.append(
            FaultWindow(kind="delayed", start=fstart, end=fend, params={"lag": lag}))
        run.workers.append(w)

    return run


# ------------------------------------------------------------- simulation --

def _build_pattern_series(pattern: Dict[str, Any], shift_minutes: int,
                           baseline: float) -> List[float]:
    ptype = pattern["type"]
    if ptype == "flat":
        return patterns.flat(shift_minutes, baseline)
    if ptype == "ramp":
        return patterns.ramp(shift_minutes, baseline, pattern["start"],
                              pattern["peak_at"], pattern["hold_until"],
                              pattern["peak_mult"])
    if ptype == "step":
        return patterns.step(shift_minutes, baseline, pattern["start"],
                              pattern["end"], pattern["mult"])
    if ptype == "spikes":
        return patterns.spikes(shift_minutes, baseline, pattern["spikes"])
    raise ValueError(f"Unknown pattern type: {ptype!r}")


def _is_numeric(v) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def simulate_run(run: RunSpec, config) -> Dict[str, Any]:
    """Generate the true and observed per-minute series, and the dose
    accounting, for every worker in a RunSpec. Pure function of
    (run, config) -- deterministic given the same inputs."""
    noise_fraction = config.provisional_parameters["noise"]["flat_baseline_noise_fraction"]
    model_exponent = config.provisional_parameters["area_monitor_model"]["fixed_model_exponent"]

    from . import dose as dose_mod  # local import avoids a module cycle at import time

    workers_out = []
    for idx, w in enumerate(run.workers):
        noise_rng = make_rng(run.seed, "noise", run.archetype, str(idx))

        if w.mode == "personal":
            true_series = _build_pattern_series(w.pattern, run.shift_minutes, w.baseline_rate_uSv_h)
            raw_measured = patterns.apply_measurement_noise(true_series, noise_rng, noise_fraction)
            observed_series = faults.apply_faults(raw_measured, w.fault_windows)
            dose_label = "MEASURED"
        else:
            ap = w.area_params
            area_reading_series = _build_pattern_series(w.pattern, run.shift_minutes, w.baseline_rate_uSv_h)
            raw_area = patterns.apply_measurement_noise(area_reading_series, noise_rng, noise_fraction)
            observed_area_raw = faults.apply_faults(raw_area, w.fault_windows)

            true_series = []
            modeled_observed = []
            for t in range(run.shift_minutes):
                dist = ap["distance_before_m"] if t < ap["move_at"] else ap["distance_after_m"]
                true_series.append(
                    area_model.inverse_square_estimate(
                        area_reading_series[t], ap["reference_distance_m"], dist,
                        ap["shielding"], exponent=ap["true_exponent"]))
                raw = observed_area_raw[t]
                if raw is None or not _is_numeric(raw):
                    modeled_observed.append(raw)
                else:
                    modeled_observed.append(
                        area_model.inverse_square_estimate(
                            float(raw), ap["reference_distance_m"], dist,
                            ap["shielding"], exponent=model_exponent))
            observed_series = modeled_observed
            dose_label = "MODELED"

        true_dose = dose_mod.accumulate_true_dose(true_series)
        dose_account = dose_mod.accumulate_observed_dose(observed_series)

        workers_out.append({
            "worker": w,
            "true_series": true_series,
            "observed_series": observed_series,
            # Additive (Phase 2C item 3): the raw, pre-inverse-square-
            # conversion area-monitor reading (post-noise, post-fault),
            # None for personal-mode workers. observed_series above is
            # already Phase 1's own converted MODELED estimate; this is
            # the separate raw input a faithful area-mode adapter needs
            # so the frozen engine can perform its own conversion rather
            # than receiving an already-converted value.
            "area_monitor_raw_rate_uSv_h": observed_area_raw if w.mode == "area" else None,
            "true_dose_mSv": true_dose,
            "dose_account": dose_account,
            "dose_label": dose_label,
        })

    return {"run": run, "workers": workers_out}
