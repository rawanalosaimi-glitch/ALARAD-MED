"""
Synthetic staffing and credentialing module (task 1).

Implements PHASE3B_ROTATION_ALGORITHM_DESIGN.md section 2's
`WorkerProfile` schema, including the Revision 2 `state` field (section
2a) that supports exclusive assignment (section 3g). No real or synthetic
staffing/credentialing dataset existed anywhere in this project before
this module (ROTATION_RECOMMENDER_DESIGN_SPEC.md section 2.1; registry
row 8) -- this is the first implementation of it, illustrative until
reviewed, never presented as derived from real staffing data.

Seeded identically to the rest of a run via phase1_simulator.rng.make_rng
(reused unchanged, not reimplemented), so a roster is reproducible per
seed exactly like every other Phase 1/3 quantity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple

from phase1_simulator.rng import make_rng

from .config import Phase3CConfig, load_config

FREE = "FREE"
ASSIGNED = "ASSIGNED"
RESERVED = "RESERVED"
RESTING = "RESTING"
WORKER_STATES = {FREE, ASSIGNED, RESERVED, RESTING}


@dataclass
class WorkerProfile:
    worker_id: str
    credentialed_rooms: FrozenSet[str]
    credentialed_procedure_classes: FrozenSet[str]
    max_dose_per_shift_mSv: float
    min_rest_between_assignments_minutes: int
    max_rotations_per_shift: int
    availability_windows: List[Tuple[int, int]]
    incident_state: str = "clear"
    state: str = FREE
    rotations_so_far: int = 0
    cumulative_dose_mSv: float = 0.0
    last_rotation_out_minute: Optional[int] = None
    reserved_for_room: Optional[str] = None

    def is_credentialed_for(self, room: str, procedure_class: str) -> bool:
        return room in self.credentialed_rooms and procedure_class in self.credentialed_procedure_classes

    def is_within_availability(self, t: int) -> bool:
        return any(start <= t < end for start, end in self.availability_windows)

    def is_within_availability_interval(self, t_start: int, t_end: int) -> bool:
        """True only if some single availability window covers the whole
        [t_start, t_end) interval -- PHASE3B section 3g step 6's
        forward-looking requirement, not just a point-in-time check."""
        return any(start <= t_start and t_end <= end for start, end in self.availability_windows)

    def is_resting_at(self, t: int) -> bool:
        if self.last_rotation_out_minute is None:
            return False
        return t < self.last_rotation_out_minute + self.min_rest_between_assignments_minutes


def generate_roster(seed: int, shift_minutes: int, n_concurrent_rooms: int,
                     rooms: List[str], procedure_classes: List[str],
                     p3c_cfg: Optional[Phase3CConfig] = None) -> List[WorkerProfile]:
    """Builds a seeded, reproducible roster for one run.

    Roster size (PHASE3B section 2c step 1): at least
    `extra_workers_beyond_concurrent_rooms` more workers than the number
    of concurrently-occupied rooms, so a replacement can exist for every
    room at once in the worst case.
    """
    cfg = p3c_cfg or load_config()
    rg = cfg.block("roster_generation")
    n_workers = n_concurrent_rooms + int(rg["extra_workers_beyond_concurrent_rooms"])
    lo_cov, hi_cov = rg["credential_coverage_probability_range"]

    dl = cfg.block("duty_limits")
    dose_lo, dose_hi = dl["max_dose_per_shift_mSv_range"]
    rest_lo, rest_hi = dl["min_rest_between_assignments_minutes_range"]
    rot_lo, rot_hi = dl["max_rotations_per_shift_range"]

    roster: List[WorkerProfile] = []
    for i in range(n_workers):
        worker_id = f"W{i:02d}"
        rng = make_rng(seed, "phase3c_staffing", worker_id)
        coverage = rng.uniform(lo_cov, hi_cov)
        cred_rooms = frozenset(r for r in rooms if rng.random() < coverage)
        cred_procs = frozenset(p for p in procedure_classes if rng.random() < coverage)
        profile = WorkerProfile(
            worker_id=worker_id,
            credentialed_rooms=cred_rooms,
            credentialed_procedure_classes=cred_procs,
            max_dose_per_shift_mSv=rng.uniform(dose_lo, dose_hi),
            min_rest_between_assignments_minutes=rng.randint(rest_lo, rest_hi),
            max_rotations_per_shift=rng.randint(rot_lo, rot_hi),
            availability_windows=[(0, shift_minutes)],
        )
        roster.append(profile)
    return roster


def roster_by_id(roster: List[WorkerProfile]) -> Dict[str, WorkerProfile]:
    return {w.worker_id: w for w in roster}
