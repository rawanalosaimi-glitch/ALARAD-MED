# Phase 3C-A — Rotation Simulation Infrastructure and Safety Foundations: Reproducibility Instructions

Covers `phase3c_rotation_infra/`: implements the plumbing specified in
`PHASE3B_ROTATION_ALGORITHM_DESIGN.md` (Revision 2) -- synthetic
staffing/credentialing, the two-layer exposure/assignment counterfactual
model, worker exclusivity and rotation scheduling, dose attribution, and
sensor-fault escalation -- per the Phase 3C-A approval.

## What this is, in one paragraph

This package does **not** implement CGDTR (the candidate rotation
algorithm) or the five-policy comparison -- both are explicitly out of
scope this round. It implements and tests the infrastructure those
would run on top of: a seeded synthetic roster, a two-layer exposure/
assignment model that keeps the underlying exposure identical across
whatever assignment policy reads it, an atomic worker-exclusivity
reservation mechanism, boundary-aligned handoff scheduling (never
mid-procedure without an authorized override), dose attribution with a
checked collective-dose-conservation invariant, and sensor-fault-driven
escalation kept deliberately independent of any dose-trigger logic.
Rotation "requests" that exercise this machinery in tests are supplied
directly by the test (synthetic/programmatic), not produced by a
dose-trigger rule.

**Read `PHASE3C_A_DOSE_THRESHOLD_SEMANTIC_AUDIT.md` before assuming
anything about how `CONFIG.doseElevated`/`doseCritical` work** -- a
read-only audit performed before any code in this package was written
found that the frozen engine's actual semantics do not match what
`PHASE3B_ROTATION_ALGORITHM_DESIGN.md` section 3a assumed. This is why
no dose-trigger formula is implemented anywhere in this package.

## Requirements

Same as every prior phase: Python 3.11, `playwright` (already
installed; needed only by `tests/test_escalation.py`'s one real-engine
integration test), the pre-installed Chromium at
`/opt/pw-browsers/chromium`. No new dependency.

## Running the tests

From `research-demo/validation-dev/`:
```
python3 -m unittest discover -s phase3c_rotation_infra/tests -t . -v
```
55 tests. See `PHASE3C_A_IMPLEMENTATION_REPORT.md` for the exact,
actually-executed pass/fail counts per file.

## Package layout

```
phase3c_rotation_infra/
  config.py / config/phase3c_config.json   centralized provisional parameters (task 6);
                                            every numeric block requires BOTH a recognized
                                            'status' and a 'source' naming it a synthetic
                                            research-prototype assumption
  staffing.py        synthetic staffing/credentialing roster (task 1); WorkerProfile with the
                      Revision 2 FREE/ASSIGNED/RESERVED/RESTING state
  exposure_layer.py   the exposure layer (task 2 part 1): per-slot dose-rate series generated
                      once per seed, independent of assignment; reuses phase1_simulator.patterns
                      unchanged. Reuses Phase 1's existing procedure-class baseline, NOT a
                      room-based one -- carries forward, not resolves, registry row 16's
                      framing question
  assignment.py       worker exclusivity and atomic batch reservation (task 3; PHASE3B
                      section 3g) -- policy-agnostic, never decides WHO or WHEN to rotate
  scheduling.py        procedure-boundary/handoff timeline and state machine (task 4; PHASE3B
                      section 3d/8): T_decide -> T_ready -> T_effective, always boundary-
                      aligned except via an explicit emergency-override parameter
  dose_attribution.py  dose attribution over the two-layer model (task 2 part 3); individual/
                      collective/max-individual dose, and the conservation-invariant check
  escalation.py        sensor-fault-driven escalation (task 5), independent of dose-trigger
                      logic; reuses the real engine's sensorStep via phase2a_adapter.dq_adapter
  tests/
    test_config.py              provisional-labeling enforcement
    test_staffing.py            seed reproducibility, credentialing, availability
    test_exposure_layer.py      seed reproducibility, exposure-layer identity across policies
    test_assignment.py          worker exclusivity, full-assignment availability
    test_scheduling.py          boundary-aligned swaps, interrupted/delayed handoffs, shift end
    test_dose_attribution.py    collective-dose conservation, no double counting/missing dose
    test_escalation.py          sensor-fault escalation (pure logic + real-engine integration)
    test_integration_smoke.py   small end-to-end wiring check across all of the above
```

## What is explicitly deferred to Phase 3C-B or later

- CGDTR (the candidate trigger/selection algorithm) and the three
  baselines plus Ablation D (the five-policy comparison).
- Wiring duty-limit (`max_dose_per_shift_mSv`) checks into the live
  eligibility filter during batch reservation -- `assignment.py`
  documents this gap explicitly; it needs a live per-minute dose figure
  this infrastructure phase does not maintain during reservation.
- Correcting `PHASE3B_ROTATION_ALGORITHM_DESIGN.md` section 3a's dose-
  trigger formula per the semantic audit's finding.
- Any statistical campaign, deployment, or merge.
