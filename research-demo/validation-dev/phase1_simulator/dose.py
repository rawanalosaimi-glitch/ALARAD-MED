"""
Dose accounting: true dose (from the simulator's ground-truth rate) and
observed dose (from the post-fault observation stream, partitioned into
trusted / uncertain / unmonitored minutes), per
ICAIRE_Simulation_Validation_Methodology.md section 1's accumulation rule.

The trusted/uncertain/unmonitored partition and the "6 identical readings
-> SUSPECTED_FROZEN" convention are reused as design precedent from
Ground_Truth_Scenarios_S1-S13.md, but this is an independent, from-scratch
implementation for the standalone Phase 1 simulator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .units import MINUTE_H, dose_increment_mSv, is_valid_rate

# Matches the documented SUSPECTED_FROZEN convention: after 6 identical
# consecutive readings, a reading is treated as uncertain rather than
# trusted (still accumulated, but flagged -- never silently dropped).
FROZEN_REPEAT_THRESHOLD = 6


@dataclass
class DoseAccount:
    observed_dose_mSv: float = 0.0
    trusted_minutes: int = 0
    uncertain_minutes: int = 0
    unmonitored_minutes: int = 0
    per_minute_status: List[str] = field(default_factory=list)


def accumulate_true_dose(true_series: List[float]) -> float:
    """Ground-truth cumulative dose from the noiseless true rate series.

    This is never derived from, or compared against, faulted/noisy data --
    it is the simulator's own ground truth, used only for later-phase
    scoring, never fed to any detector or forecaster.
    """
    total = 0.0
    for rate in true_series:
        total += dose_increment_mSv(rate, MINUTE_H)
    return total


def accumulate_observed_dose(observed_series: List[Optional[float]]) -> DoseAccount:
    """Cumulative dose from what was actually observed, with completeness
    tracked explicitly rather than assumed.

    - unmonitored: no valid reading this minute (missing, invalid, or out
      of bounds) -- contributes no dose, and is never silently treated as
      zero exposure.
    - uncertain: a valid-looking reading that has repeated identically for
      FROZEN_REPEAT_THRESHOLD or more consecutive minutes (suspected
      frozen sensor, not a confirmed fault) -- still accumulated, but
      flagged, consistent with "readings are shown but are not verified
      current measurements."
    - trusted: a valid reading with no such repeat-run flag.
    """
    acc = DoseAccount()
    repeat_run = 0
    last_value: Optional[float] = None
    for v in observed_series:
        if not is_valid_rate(v):
            acc.per_minute_status.append("unmonitored")
            acc.unmonitored_minutes += 1
            repeat_run = 0
            last_value = None
            continue
        if last_value is not None and v == last_value:
            repeat_run += 1
        else:
            repeat_run = 1
        last_value = v
        if repeat_run >= FROZEN_REPEAT_THRESHOLD:
            acc.per_minute_status.append("uncertain")
            acc.uncertain_minutes += 1
        else:
            acc.per_minute_status.append("trusted")
            acc.trusted_minutes += 1
        acc.observed_dose_mSv += dose_increment_mSv(v, MINUTE_H)
    return acc
