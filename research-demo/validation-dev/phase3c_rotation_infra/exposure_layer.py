"""
Exposure layer: per-minute dose-rate series generated once per seed, keyed
to an `AssignmentSlot`, independent of which worker is assigned to it
(task 2, part 1; PHASE3B_ROTATION_ALGORITHM_DESIGN.md section 5a, layer 1).

Reuses phase1_simulator.patterns.flat / apply_measurement_noise and
phase1_simulator.rng.make_rng exactly as implemented -- no simulator
code is modified, and no code or data is copied from the frozen v1.2.3
release. Personal-mode only this phase (area-mode is out of scope, the
same scoping decision phase2a_adapter.detection_adapter made for its own
radiation layer -- see PHASE2A_LIMITATIONS.md).

Baseline convention, stated explicitly: this module reuses Phase 1's own
existing procedure-class baseline (`baseline_rate_uSv_h x proc_mult`),
NOT a room-based baseline. This carries forward, rather than resolves,
the procedure-vs-room framing question already registered as Parameter
Registry row 16 and PHASE3B_ROTATION_ALGORITHM_DESIGN.md section 9d item
5. A slot's `room` field is therefore scheduling/credentialing metadata
in this implementation; it does not drive the exposure numbers. Stated
here so it is not later assumed to mean something it doesn't.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from phase1_simulator import patterns
from phase1_simulator.config import SimulationConfig
from phase1_simulator.rng import make_rng

from .config import Phase3CConfig, load_config


@dataclass(frozen=True)
class AssignmentSlot:
    slot_id: str
    room: str
    procedure_class: str
    start_minute: int
    end_minute: int  # exclusive
    proc_mult: float
    baseline_rate_uSv_h: float  # = procedure class baseline * proc_mult


def generate_room_boundaries(seed: int, room: str, shift_minutes: int,
                              p3c_cfg: Phase3CConfig) -> List[int]:
    """Boundaries (minute indices) partitioning [0, shift_minutes) for one
    room-track, including 0 and shift_minutes. Spacing is sampled from a
    declared, explicitly-illustrative range -- not a clinical procedure-
    duration model (config.py's phase3c_config.json `procedure_boundaries`
    block, task 6)."""
    pb = p3c_cfg.block("procedure_boundaries")
    lo, hi = pb["boundary_spacing_minutes_range"]
    rng = make_rng(seed, "phase3c_boundaries", room)
    boundaries = [0]
    t = 0
    while t < shift_minutes:
        spacing = max(1, int(round(rng.uniform(lo, hi))))
        t = min(shift_minutes, t + spacing)
        boundaries.append(t)
    if boundaries[-1] != shift_minutes:
        boundaries.append(shift_minutes)
    # de-duplicate while preserving order (can happen if the last step lands exactly on shift_minutes twice)
    out = []
    for b in boundaries:
        if not out or out[-1] != b:
            out.append(b)
    return out


def generate_slots_for_room(seed: int, room: str, shift_minutes: int,
                             p1_cfg: SimulationConfig,
                             p3c_cfg: Phase3CConfig = None) -> List[AssignmentSlot]:
    """One room's full-shift slot schedule: a sequence of AssignmentSlots
    whose procedure_class and proc_mult are each sampled independently
    (seeded) from Phase 1's own existing procedure_classes config -- no
    new procedure taxonomy is introduced."""
    p3c_cfg = p3c_cfg or load_config()
    boundaries = generate_room_boundaries(seed, room, shift_minutes, p3c_cfg)
    classes = p1_cfg.procedure_classes()
    names = sorted(classes.keys())
    slots = []
    for i in range(len(boundaries) - 1):
        start, end = boundaries[i], boundaries[i + 1]
        rng = make_rng(seed, "phase3c_slot", room, str(i))
        proc_name = rng.choice(names)
        proc_cfg = classes[proc_name]
        lo, hi = proc_cfg["proc_mult_range"]
        proc_mult = rng.uniform(lo, hi)
        baseline = proc_cfg["baseline_rate_uSv_h"] * proc_mult
        slots.append(AssignmentSlot(
            slot_id=f"{room}-{i}", room=room, procedure_class=proc_name,
            start_minute=start, end_minute=end, proc_mult=proc_mult,
            baseline_rate_uSv_h=baseline,
        ))
    return slots


def generate_exposure_series(seed: int, slot: AssignmentSlot,
                              noise_fraction: float = 0.05) -> List[float]:
    """Deterministic, given (seed, slot.slot_id): flat baseline + additive
    measurement noise over the slot's own duration. Fixed once generated
    -- never regenerated per rotation policy (section 5a point 1); this
    function's caller is responsible for calling it exactly once per
    slot per seed and reusing the result across every policy compared."""
    duration = slot.end_minute - slot.start_minute
    true_series = patterns.flat(duration, slot.baseline_rate_uSv_h)
    rng = make_rng(seed, "phase3c_exposure", slot.slot_id)
    return patterns.apply_measurement_noise(true_series, rng, noise_fraction)


def generate_exposure_layer(seed: int, slots_by_room: Dict[str, List[AssignmentSlot]],
                             noise_fraction: float = 0.05) -> Dict[str, List[float]]:
    """All slots' exposure series in one call, keyed by slot_id -- the
    full "exposure layer" for a seed (section 5a)."""
    out: Dict[str, List[float]] = {}
    for slots in slots_by_room.values():
        for slot in slots:
            out[slot.slot_id] = generate_exposure_series(seed, slot, noise_fraction)
    return out
