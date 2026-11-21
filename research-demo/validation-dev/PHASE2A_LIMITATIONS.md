# Phase 2A — Unresolved Limitations

Reported per the Phase 2A instruction to deliver "any unresolved
limitations." Nothing below has been silently worked around; each is
either a real, disclosed scope boundary or an open item for a later
phase.

## 1. Area-mode radiation-anomaly evaluation is not implemented

`detection_adapter.evaluate_radiation_detection` raises `NotImplementedError`
for any worker whose `mode` is `"area"` rather than `"personal"`.

**Why:** calling the real `evaluateExposure` correctly for an area-mode
worker requires `dist`, `refDist`, and `shield` — the area-monitoring
geometry. Phase 1's committed output schema
(`phase1_simulator/output.py`) does not currently carry this geometry for
area-mode workers (it is generated internally by `phase1_simulator/scenario.py`
but not serialized to the JSON output). Inventing plausible-looking
geometry values here, rather than using what Phase 1 actually simulated,
would be exactly the kind of silent approximation Phase 2A's restrictions
prohibit.

**Scope impact:** of Phase 1's 13 archetypes, only `area_relocation` is
area-mode; the other 12 are evaluated normally. `tests/test_reference_reproduction.py`'s
`test_s4_area_mode_is_explicitly_not_reproduced` documents this via a
passing test (confirming the skip is deliberate, not an oversight), rather
than silently omitting S4 from the reproduction check.

**What would resolve this:** extending Phase 1's `output.py` to serialize
each area-mode worker's `area_params` (reference distance, distance-
over-time, shielding, true exponent), then extending
`detection_adapter.py` with an area-mode evaluation path that calls
`evaluateExposure` with `mode: 'area'` and the correct per-minute `dist`.
Not attempted in Phase 2A; this is a direct instruction boundary ("Do not
modify... keep new files inside research-demo/validation-dev/" did not
forbid it, but extending an already-accepted Phase 1 deliverable without
being asked was judged out of scope for this phase).

## 2. Phase 1 / frozen-engine baseline-scale mismatch (found and fixed this phase, but the underlying mismatch itself remains)

Phase 1's provisional procedure-class baselines and the frozen engine's
own `baselineRates`/`CONFIG` are two independently-chosen numeric scales
(a few µSv/h vs. tens of µSv/h). This was discovered empirically during
this phase's own smoke testing (see `PHASE2A_SMOKE_TEST_REPORT.md`): it
first showed up as a spurious sensor-fault false positive on an archetype
with zero injected faults.

**What was done:** `detection_adapter.rescale_to_engine_baseline` and its
reuse in `dq_adapter.build_observations` now re-express every Phase-1-
generated reading on the engine's own baseline scale before it is fed to
any real-engine function, preserving the reading's ratio to its own
(Phase 1) baseline exactly.

**What is NOT resolved:** the rescaling is a disclosed adapter-layer
transformation, not a reconciliation of the two underlying provisional
parameter sets. Phase 1's procedure-class baselines (Parameter Registry
row 1) and the engine's own `baselineRates`/`CONFIG` (not currently a
registry row at all) remain two separate, still-provisional numbers. If a
future phase needs them to represent the *same* real-world quantity (e.g.
for a paper claim about absolute dose rates, not just relative event
shapes), they still need independent, evidence-based reconciliation —
rescaling does not provide that evidence, it only makes the *shape*
comparable.

## 3. Immediate-alert (dose-based confirmation-window bypass) is out of scope

The frozen engine's `buildEpisodes(flagged, K, imm)` accepts an optional
`imm` array that lets a dose-based immediate-alert criterion bypass the
confirmation window (`AlaradSafety.immediateAlert`/`immediateThreshold`).
This adapter always calls `buildEpisodes` with `imm = null`, i.e. the
confirmation-window-only path. This was a deliberate scope decision (the
Phase 2A tasks ask for confirmation-window-based detection evaluation and
two new baselines, not for evaluating the dose-based bypass feature), not
an oversight, but it means this adapter's results do not reflect that
feature of the real engine.

## 4. Chromium version caveat carried forward unchanged

Every test and smoke run in this phase uses the same pre-installed
Chromium (153.0.8010.12) in place of Playwright's pinned build
(141.0.7390.37), for the same network-policy reason recorded in
`Verification_Rerun_Report.md`. That disclosed caveat is unresolved and
now applies to a second, independent body of work (Phase 2A) built on the
same workaround.

## 5. Baseline 2 and 3's threshold values remain provisional, unevidenced placeholders

`phase2a_config.json`'s `baseline_2_fixed_threshold.fixed_multiple` (2.0)
and `baseline_3_moving_average`'s window (5 minutes) and multiple (2.0)
are placeholders chosen only to make the two baselines runnable, per
Parameter Registry rows 5 and 6
(`ICAIRE_Simulation_Validation_Methodology.md` section 9). Baseline 3's
characterization as "conventional practice" remains explicitly withdrawn,
as it was in the methodology document itself — nothing in this phase's
implementation resolves either registry row; both still require the
expert review/citation the methodology document calls for.

## 6. No statistical evaluation was performed

Per Phase 2A task 9 and the methodology document, only a small (10-run)
integration smoke test was executed. No claim about detection performance,
baseline comparison, or significance is made or implied anywhere in this
phase's deliverables — the smoke numbers in `PHASE2A_SMOKE_TEST_REPORT.md`
describe 10 specific seeds, not a scientific result.
