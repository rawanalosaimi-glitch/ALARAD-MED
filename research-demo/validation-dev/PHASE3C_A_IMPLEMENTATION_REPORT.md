# Phase 3C-A — Implementation Report

**Scope, restated:** Rotation Simulation Infrastructure and Safety
Foundations, for a limited, synthetic research prototype only. CGDTR
(the candidate trigger/selection algorithm) and the five-policy
comparison are **not** implemented. No statistical campaign was run.
The frozen v1.2.3 release was not modified (SHA-256
`92e897dd0ff1738f083df829b53f7f46377e042b7019bb9776232792261182ee`,
re-verified unchanged both before and after this round's work). Nothing
is deployed or merged. No dose-reduction result is reported anywhere.

---

## 1. Dose-threshold semantic audit (performed before any code was written)

Full findings: `PHASE3C_A_DOSE_THRESHOLD_SEMANTIC_AUDIT.md`. Summary:

**Verified finding:** the frozen engine's `CONFIG.doseElevated`/
`doseCritical` (line 1501-1503) are compared, inside `evaluateExposure()`
(line 1950-1991), against a variable named `cumulativeDose` that is
**not** a running/accumulated total despite its name — it is
`current_single_minute_rate x (dur/60) / 1000`, a fresh, memoryless
projection recomputed independently every call, with `dur` fixed at 30
minutes at every real call site (`SimLab.runWorker`, line 2947/2951;
the detection adapter's own call site, line 3426) and `rate` always a
single per-minute reading, never a trailing average or an accrued sum.

**Mismatch found:** `PHASE3B_ROTATION_ALGORITHM_DESIGN.md` section 3a
(Revision 2) had assumed these thresholds compare against "already-
accrued cumulative dose plus the projected increment." **This is
incorrect** — the real engine's comparison uses only the increment
alone; no accrued component exists anywhere in the real computation.

**Consequence for this round:** no dose-trigger formula is implemented
anywhere in Phase 3C-A (consistent with the explicit restriction
regardless of this finding). `escalation.py` was designed to never
depend on any dose value at all — not a workaround for this finding, but
an independently-correct decoupling the instructions already called
for, which this finding gives an additional reason to keep. The
correction this implies for `PHASE3B_ROTATION_ALGORITHM_DESIGN.md`
section 3a itself is listed as a blocker for Phase 3C-B (§4 below), not
made in this round.

---

## 2. Files created

All new, isolated, under `research-demo/validation-dev/` — **no
existing file in `phase1_simulator/`, `phase2a_adapter/`, or
`phase3a_forecasting/` was modified**, and none of their own test
suites were re-run or touched as part of this change (only imported
from, read-only).

| File | Purpose |
|---|---|
| `PHASE3C_A_DOSE_THRESHOLD_SEMANTIC_AUDIT.md` | the pre-coding audit (§1) |
| `PHASE3C_A_README.md` | reproducibility instructions |
| `PHASE3C_A_IMPLEMENTATION_REPORT.md` | this report |
| `phase3c_rotation_infra/__init__.py` | package docstring/scope statement |
| `phase3c_rotation_infra/config.py` | centralized provisional-parameter loader (task 6) |
| `phase3c_rotation_infra/config/phase3c_config.json` | the provisional parameters themselves, every block carrying `status` and a synthetic-assumption `source` |
| `phase3c_rotation_infra/staffing.py` | synthetic staffing/credentialing module (task 1) |
| `phase3c_rotation_infra/exposure_layer.py` | exposure layer: per-slot series generated once per seed (task 2 part 1) |
| `phase3c_rotation_infra/assignment.py` | worker exclusivity state machine + atomic batch reservation (task 3) |
| `phase3c_rotation_infra/scheduling.py` | procedure-boundary/handoff timeline and state machine (task 4) |
| `phase3c_rotation_infra/dose_attribution.py` | dose attribution over the two-layer model (task 2 part 3) |
| `phase3c_rotation_infra/escalation.py` | sensor-fault-driven escalation, independent of dose-trigger logic (task 5) |
| `phase3c_rotation_infra/.gitignore` | excludes `__pycache__`, matching every other phase package |
| `phase3c_rotation_infra/tests/__init__.py` | (empty, matching the existing test-package convention) |
| `phase3c_rotation_infra/tests/test_config.py` | 5 tests |
| `phase3c_rotation_infra/tests/test_staffing.py` | 7 tests |
| `phase3c_rotation_infra/tests/test_exposure_layer.py` | 6 tests |
| `phase3c_rotation_infra/tests/test_assignment.py` | 8 tests |
| `phase3c_rotation_infra/tests/test_scheduling.py` | 15 tests |
| `phase3c_rotation_infra/tests/test_dose_attribution.py` | 4 tests |
| `phase3c_rotation_infra/tests/test_escalation.py` | 8 tests |
| `phase3c_rotation_infra/tests/test_integration_smoke.py` | 2 tests |

---

## 3. Tests actually executed, with exact results

Command run, in this session, from `research-demo/validation-dev/`:
```
python3 -m unittest discover -s phase3c_rotation_infra/tests -t . -v
```

**Result: 55 passed, 0 failed, 0 skipped, 0 errors.** (One test,
`test_two_policies_on_identical_exposure_layer_simultaneous_rotation_requests`,
failed on its first run because its own roster-size assumption was
wrong for the staffing shortage it accidentally created — not a bug in
the module under test; fixed by sizing that test's roster correctly,
then re-run to the result below. No test anywhere was marked passing
without being executed.)

| File | Tests | Result |
|---|---|---|
| `test_config.py` | 5 | **5 passed** — provisional-labeling + synthetic-source enforcement |
| `test_staffing.py` | 7 | **7 passed** — seed reproducibility, roster sizing, credentialing, availability |
| `test_exposure_layer.py` | 6 | **6 passed** — boundary/slot reproducibility, exposure-series identity across repeated generation and across policies, Phase-1-baseline reuse |
| `test_assignment.py` | 8 | **8 passed** — no double reservation under contention, deterministic room-name ordering, forward-looking availability, rotation-burden cap, resting exclusion, full lifecycle transitions |
| `test_scheduling.py` | 15 | **15 passed** — T_effective always boundary-aligned, multi-boundary handoff spanning, infeasible-near-shift-end, never-mid-procedure-without-override, emergency override, interrupted handoff (ABORTED), incident hold (HELD), post-acknowledgement recompute (never the stale boundary), audit log |
| `test_dose_attribution.py` | 4 | **4 passed** — collective-dose conservation under fixed occupancy (rotated vs. not, both equal the reference total), double-counting raises `AttributionConflictError`, no missing attribution, unassigned minutes contribute zero |
| `test_escalation.py` | 8 | **8 passed** — threshold-based raise/no-raise, unacknowledged-vs-acknowledged resolution paths, no dose-related field anywhere in the escalation log, one integration test against the real, unmodified `AlaradSafety.sensorStep` via `phase2a_adapter.dq_adapter` |
| `test_integration_smoke.py` | 2 | **2 passed** — end-to-end seed reproducibility; two different, directly-supplied assignment policies sharing one unmutated exposure layer, with collective dose conserved and individual doses differing |

**Total: 55 tests, 55 passed, 0 failed.** Raw command output is not
reproduced verbatim here beyond the summary above, but was observed
directly in this session, per file and in aggregate, before this report
was written — no count above is inferred or assumed.

No test anywhere in this package uses `@unittest.skip`, and
`test_escalation.py`'s one real-engine test requires `EngineBridge` (a
live Playwright/Chromium session against the frozen file) and was run
successfully, not stubbed out.

---

## 4. Remaining blockers for Phase 3C-B

1. **`PHASE3B_ROTATION_ALGORITHM_DESIGN.md` section 3a needs a
   correction** (a future Revision 3) reflecting §1's audit finding,
   before any CGDTR trigger formula is implemented — implementing the
   trigger as currently written would compare against a quantity the
   real engine does not compute.
2. **No CGDTR trigger/selection logic, and no five-policy comparison,
   exist yet** — by design, this round's explicit restriction. Phase
   3C-B would need to decide the corrected trigger formula (per
   blocker 1) before wiring it into `assignment.batch_resolve`'s
   caller-supplied `candidate_order`.
3. **Duty-limit (`max_dose_per_shift_mSv`) checking is not wired into
   the live eligibility filter** — `assignment.py`'s own docstring
   flags this: it needs a live, per-minute dose figure this
   infrastructure phase does not maintain during batch reservation
   (dose accounting here is computed after the fact, over a full
   exposure+assignment layer, by `dose_attribution.py`). Whichever
   future phase wires live rotation decisions needs to decide how
   current dose is tracked and checked at decision time.
4. **The `procedure_boundaries` block's synthetic boundary-spacing
   range, and every other new provisional parameter introduced this
   round (`config/phase3c_config.json`), are not yet numbered rows in
   `ICAIRE_Simulation_Validation_Methodology.md` section 9** — flagged
   here, as this project's established practice requires, rather than
   silently expanding that document without being asked. No edit was
   made to the methodology document this round.
5. **`handoff.min_handoff_duration_minutes` and
   `escalation.escalate_after_consecutive_fault_minutes` are single
   illustrative values, not sensitivity-swept ranges** — consistent
   with this round's "implementation and tests only" scope, but a
   sensitivity sweep (as already specified for several parameters in
   `PHASE3B_ROTATION_ALGORITHM_DESIGN.md` section 9c) has not been run
   for either.
6. **Area-mode (modeled, not measured) workers are out of scope** for
   `exposure_layer.py`, the same scoping decision
   `phase2a_adapter.detection_adapter` made for its own radiation layer
   — not revisited this round.

---

## 5. What this round does not claim

- Does not claim CGDTR, or any rotation decision algorithm, has been
  implemented, tested, or evaluated — none exists in this package.
- Does not claim any dose-reduction, fairness, or collective-dose
  *result* — every number in this package's tests is either a
  structural/reproducibility check or a hand-constructed synthetic
  scenario built to exercise the infrastructure, not a reported finding
  about rotation's effectiveness.
- Does not claim the `PHASE3B_ROTATION_ALGORITHM_DESIGN.md` section 3a
  mismatch has been corrected — only identified, with exact evidence,
  and listed as a blocker.
- Does not claim clinical or regulatory validation anywhere.
