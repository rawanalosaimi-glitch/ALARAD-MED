"""
MEASURED (personal) vs. MODELED (area, inverse-square) worker-position
estimate conversion, per ICAIRE_Simulation_Validation_Methodology.md
section 1.
"""

from __future__ import annotations


def inverse_square_estimate(area_reading: float, reference_distance_m: float,
                             worker_distance_m: float, shielding: float,
                             exponent: float = 2.0) -> float:
    """reading x (reference distance / worker distance)^exponent x shielding.

    With exponent=2.0 this is the exact formula the frozen v1.2.3 engine
    documents for its MODELED worker-position estimate (methodology
    section 1): an inverse-square point-source approximation, self-
    disclosed there as limited -- real-room scatter does not follow it.

    This function also accepts a non-2.0 exponent so the Phase 1 simulator
    can generate a worker's true physical exposure with a different
    exponent than the engine's fixed modeling assumption -- reproducing,
    in a generalized/parameterized form, the MEASURED-vs-MODELED
    discrepancy test already documented for scenario S4 in
    Ground_Truth_Scenarios_S1-S13.md ("the modeled dose is expected to
    under-estimate the measured one"). The engine itself always uses
    exponent=2.0; only the simulator's ground-truth generation uses a
    different exponent, to create a true discrepancy for later-phase
    evaluation to detect.
    """
    if worker_distance_m <= 0:
        raise ValueError("worker_distance_m must be positive")
    return area_reading * (reference_distance_m / worker_distance_m) ** exponent * shielding
