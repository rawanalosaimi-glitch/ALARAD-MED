"""
Builds the rotation campaign's scenario classes by reusing Phase 1's
own 13 archetype generators (`phase1_simulator.scenario`) UNCHANGED --
this module does not inject its own events, faults, or noise. Each
resulting Phase 1 "worker" record is repurposed as one room-track's
real exposure series (its own `observed_rate_uSv_h`, exactly as Phase 1
generated it, including whatever events/faults that archetype injects),
subdivided into procedure-boundary segments (for CGDTR's scheduling
only -- never regenerating or altering a single exposure value) using
`exposure_layer.generate_room_boundaries`.

Deliberately separate from `exposure_layer.generate_slots_for_room`/
`generate_exposure_series` (Phase 3C-A's own synthetic, flat-baseline-
plus-noise generator, kept unchanged and still exercised by Phase
3C-A's infrastructure tests) -- the final campaign needs Phase 1's real
archetype-driven events and faults, not a flat placeholder.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from phase1_simulator import output as p1_output
from phase1_simulator import scenario as p1_scenario
from phase1_simulator.config import SimulationConfig
from phase2a_adapter.detection_adapter import decode_observed_value, phase1_baseline_rate
from phase2a_adapter.dq_adapter import build_observations

from .config import Phase3CConfig
from .exposure_layer import AssignmentSlot, generate_room_boundaries


def build_campaign_run(seed: int, archetype: str, p1_cfg: SimulationConfig,
                        p3c_cfg: Phase3CConfig) -> Dict[str, Any]:
    """Returns a dict with:
      - slots_by_room: Dict[room_track, List[AssignmentSlot]]
      - exposure_by_slot: Dict[slot_id, List[float]] -- dose-ready
        (invalid/missing minutes are 0.0, the existing, already-
        established "invalid/missing reading contributes no dose"
        lower-bound rule -- phase1_simulator.dose's own convention,
        reused, not a new assumption).
      - observations_by_room: Dict[room_track, List[Optional[dict]]] --
        the raw, undecoded per-minute observation sequence (None or
        {ts, value}), for sensor-state stepping -- built via
        `phase2a_adapter.dq_adapter.build_observations`, reused
        unchanged, not reimplemented.
      - true_rate_by_room: Dict[room_track, List[float]] -- the
        noiseless ground-truth series, for reference/diagnostics only
        (never fed to any trigger or dose computation).
      - shift_minutes: int
      - archetype, seed: as given.
    """
    run = p1_scenario.generate_run(archetype, seed, p1_cfg)
    simulated = p1_scenario.simulate_run(run, p1_cfg)
    d = p1_output.run_to_dict(simulated, p1_cfg)
    shift_minutes = d["shift_minutes"]

    slots_by_room: Dict[str, List[AssignmentSlot]] = {}
    exposure_by_slot: Dict[str, List[float]] = {}
    observations_by_room: Dict[str, List[Optional[Dict[str, Any]]]] = {}
    true_rate_by_room: Dict[str, List[float]] = {}
    seen_rooms: Dict[str, int] = {}

    for worker in d["workers"]:
        base_room = worker["room"]
        seen_rooms[base_room] = seen_rooms.get(base_room, 0) + 1
        track_name = base_room if seen_rooms[base_room] == 1 else f"{base_room} ({seen_rooms[base_room]})"

        raw_series = [decode_observed_value(v) for v in worker["series"]["observed_rate_uSv_h"]]
        dose_ready_series = [
            v if (v is not None and v == v and v >= 0) else 0.0  # v==v excludes NaN
            for v in raw_series
        ]
        observations_by_room[track_name] = build_observations(worker)
        true_rate_by_room[track_name] = list(worker["series"]["true_rate_uSv_h"])

        boundaries = generate_room_boundaries(seed, track_name, shift_minutes, p3c_cfg)
        slots: List[AssignmentSlot] = []
        for i in range(len(boundaries) - 1):
            start, end = boundaries[i], boundaries[i + 1]
            slot_id = f"{track_name}-{i}"
            slots.append(AssignmentSlot(
                slot_id=slot_id, room=track_name, procedure_class=worker["procedure_class"],
                start_minute=start, end_minute=end, proc_mult=worker["proc_mult"],
                baseline_rate_uSv_h=phase1_baseline_rate(worker, p1_cfg),
            ))
            exposure_by_slot[slot_id] = dose_ready_series[start:end]
        slots_by_room[track_name] = slots

    return {
        "slots_by_room": slots_by_room,
        "exposure_by_slot": exposure_by_slot,
        "observations_by_room": observations_by_room,
        "true_rate_by_room": true_rate_by_room,
        "shift_minutes": shift_minutes,
        "archetype": archetype,
        "seed": seed,
    }


def room_boundaries_minutes(slots: List[AssignmentSlot]) -> List[int]:
    """The boundary-minute list CGDTR/scheduling needs, derived from an
    already-built slot list (never recomputed independently -- avoids
    a second, possibly-inconsistent boundary generation)."""
    if not slots:
        return [0]
    return [slots[0].start_minute] + [s.end_minute for s in slots]
