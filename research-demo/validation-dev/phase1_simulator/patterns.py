"""
Noiseless true-rate pattern generators and additive measurement noise.

Reuses the pattern taxonomy already described in
Ground_Truth_Scenarios_S1-S13.md (flat, ramp, step, spikes), but
reimplements it from scratch for this standalone Phase 1 simulator -- no
code or data is imported from, or copied out of, the frozen v1.2.3 release.
Parameters are *inputs* here; they are sampled from the provisional config
ranges by scenario.py, never hardcoded in this module.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class EventWindow:
    start: int
    end: int  # exclusive
    label: str


def flat(shift_minutes: int, baseline: float) -> List[float]:
    return [baseline] * shift_minutes


def ramp(shift_minutes: int, baseline: float, start: int, peak_at: int,
         hold_until: int, peak_mult: float) -> List[float]:
    series = [baseline] * shift_minutes
    for t in range(start, min(peak_at, shift_minutes)):
        frac = (t - start) / max(1, (peak_at - start))
        series[t] = baseline * (1.0 + frac * (peak_mult - 1.0))
    for t in range(peak_at, min(hold_until, shift_minutes)):
        series[t] = baseline * peak_mult
    return series


def step(shift_minutes: int, baseline: float, start: int, end: int,
         mult: float) -> List[float]:
    series = [baseline] * shift_minutes
    for t in range(start, min(end, shift_minutes)):
        series[t] = baseline * mult
    return series


def spikes(shift_minutes: int, baseline: float,
           spikes_spec: List[dict]) -> List[float]:
    series = [baseline] * shift_minutes
    for sp in spikes_spec:
        for t in range(sp["at"], min(sp["at"] + sp["len"], shift_minutes)):
            series[t] = baseline * sp["mult"]
    return series


def apply_measurement_noise(true_series: List[float], rng: random.Random,
                             noise_fraction: float) -> List[float]:
    """Independent +/- noise_fraction uniform perturbation per minute.

    Applied to the raw measured/area-reading stream -- never to the
    noiseless true_series used as ground truth for dose/forecast scoring
    in later phases.
    """
    out = []
    for v in true_series:
        jitter = rng.uniform(-noise_fraction, noise_fraction)
        out.append(max(0.0, v * (1.0 + jitter)))
    return out
