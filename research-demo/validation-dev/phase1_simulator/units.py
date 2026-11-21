"""
Dose-rate, cumulative-dose, and time-integration conventions.

These are not new inventions: they match the unit conventions documented in
ICAIRE_Simulation_Validation_Methodology.md section 1, which are themselves
extracted verbatim from the frozen ALARAD v1.2.3 engine's own in-page text
(line 1170 of the frozen release, quoted in the methodology document). This
module implements that same convention independently for the standalone
Phase 1 simulator -- it does not read or import anything from the frozen
release.
"""

from __future__ import annotations

DOSE_RATE_UNIT = "uSv/h"
CUMULATIVE_DOSE_UNIT = "mSv"
TIME_STEP_MINUTES = 1
MINUTE_H = 1.0 / 60.0

# Invalid-reading bounds, reused as a convention from the existing engine
# (methodology section 1): a reading below/above these bounds, or
# non-finite, is rejected and contributes no dose.
MIN_VALID_RATE_USV_H = 0.0
MAX_VALID_RATE_USV_H = 1_000_000.0


def is_valid_rate(value) -> bool:
    """A rate is valid if it is a finite number within the documented bounds."""
    if value is None:
        return False
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    if v != v:  # NaN
        return False
    if v in (float("inf"), float("-inf")):
        return False
    return MIN_VALID_RATE_USV_H <= v <= MAX_VALID_RATE_USV_H


def dose_increment_mSv(rate_uSv_h: float, duration_h: float) -> float:
    """Dose (mSv) = Dose Rate (uSv/h) x Duration (h) / 1000.

    This is the exact rule documented in the methodology (section 1),
    itself copied from the frozen engine's own in-page text. A reading
    held constant over one minute (duration_h = MINUTE_H) is the default
    usage throughout this package.
    """
    return rate_uSv_h * duration_h / 1000.0
