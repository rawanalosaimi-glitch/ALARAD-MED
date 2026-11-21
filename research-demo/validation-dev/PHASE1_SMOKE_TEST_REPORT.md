# Phase 1 Smoke Test Report

**This is a smoke test, not scientific validation.** It answers one
question only: *does the Phase 1 simulator run end-to-end and produce
structurally sane output, for one seed per archetype?* It does not answer
whether any detector, forecaster, or rotation recommender performs well —
none exists yet (Phase 1 scope). It does not involve the ≥30-seeds-per-
class statistical campaign, baselines, or significance testing described
in `ICAIRE_Simulation_Validation_Methodology.md` sections 4–9 — that
campaign is explicitly later-phase work and was not run. Nothing below is
a scientific-validation claim.

All numbers in this report were produced by actually running the code in
this session on 2026-11-21, not estimated or invented.

## 1. Unit test run (real output)

Command run:
```
python3 -m unittest discover -s phase1_simulator/tests -t . -v
```

**First run** surfaced a real, genuine bug: `test_config_with_unlabeled_parameter_is_rejected`
failed, because `SimulationConfig.every_provisional_item_is_labeled()`'s
recursion vacuously accepted a parameter block like `{"value": 1.0}` that
had no nested dict children and no `"status"` key of its own — it
recursed into the scalar `1.0`, which trivially returns "fine," instead of
flagging the missing status. This is exactly the kind of bug Phase 1 item
5's testing requirement exists to catch; it was not concealed:

```
FAIL: test_config_with_unlabeled_parameter_is_rejected
AssertionError: ConfigValidationError not raised
----------------------------------------------------------------------
Ran 40 tests in 0.037s
FAILED (failures=1)
```

The bug was fixed in `phase1_simulator/config.py` (a leaf parameter block
is now defined as any dict with a non-dict, non-`"status"` value, and such
a block is required to carry its own recognized `"status"`). The suite
was then rerun:

```
Ran 40 tests in 0.061s
OK
```

**Final result: 40 passed, 0 failed, 0 skipped, 1 error-to-fix found and
fixed during this session** (not hidden — recorded here per the same
"do not silently exclude failures" discipline used in
`Verification_Rerun_Report.md`).

Coverage by required area (Phase 1 deliverable C):
| Area | File | Tests |
|---|---|---|
| Dose integration | `test_dose_integration.py` | 7 |
| Seed reproducibility | `test_seed_reproducibility.py` | 5 |
| Event timing | `test_event_timing.py` | 7 |
| Ground-truth consistency | `test_ground_truth_consistency.py` | 8 |
| Output schema (+ provisional-labeling enforcement) | `test_output_schema.py` | 13 |
| **Total** | | **40** |

## 2. Smoke batch run (real output)

Command run:
```
python3 -m phase1_simulator.run_smoke_batch
```

Actual console output (13 archetypes, 1 seed each, as printed by the
script):

```
  normal-1001                            shift= 720min workers=1 truth_events=0 fault_events=0
  gradual_increase-1002                  shift= 240min workers=1 truth_events=1 fault_events=0
  sudden_increase-1003                   shift=  60min workers=1 truth_events=1 fault_events=0
  transient_spike-1004                   shift= 480min workers=1 truth_events=0 fault_events=0
  area_relocation-1005                   shift=  60min workers=1 truth_events=1 fault_events=0
  multi_worker_mixed-1006                shift= 720min workers=3 truth_events=2 fault_events=0
  fault_missing-1007                     shift= 240min workers=1 truth_events=0 fault_events=1
  fault_invalid-1008                     shift= 720min workers=1 truth_events=0 fault_events=1
  fault_frozen-1009                      shift= 720min workers=1 truth_events=0 fault_events=1
  fault_delayed-1010                     shift= 720min workers=1 truth_events=0 fault_events=1
  fault_during_event-1011                shift= 480min workers=1 truth_events=1 fault_events=1
  multi_worker_faults-1012               shift= 480min workers=3 truth_events=1 fault_events=3
  concurrent_alert_and_fault-1013        shift=  60min workers=1 truth_events=1 fault_events=1

Wrote 13 runs and manifest.json to .../smoke_test_output
```

Observations against what each archetype is supposed to do:
- `normal`: 0 truth events, 0 faults — correct (no injection requested).
- `gradual_increase`, `sudden_increase`, `area_relocation`,
  `fault_during_event`, `multi_worker_faults` (1 of 3 workers has an
  event), `concurrent_alert_and_fault`: each produced exactly the single
  truth event expected of its archetype.
- `transient_spike`: 0 truth events — correct; by the reused S5
  convention (`Ground_Truth_Scenarios_S1-S13.md`), a short transient is
  deliberately not labelled as an abnormal event.
- `multi_worker_mixed`: 2 truth events across 3 workers — correct (one
  worker gets an unlabelled transient spike, the other two get labelled
  ramp/step events).
- `fault_missing`, `fault_invalid`, `fault_frozen`, `fault_delayed`: each
  produced exactly 1 fault event, 0 truth events — correct.
- `fault_during_event`, `concurrent_alert_and_fault`: each produced 1
  truth event **and** 1 fault event on the same worker — correct, this is
  the point of these two archetypes.
- `multi_worker_faults`: 3 fault events (one per worker) and 1 truth
  event (on the one worker that also gets a step pattern) — correct.

## 3. Determinism check (real output)

The smoke batch was run twice in this session, as two separate process
invocations to two separate output directories:
```
python3 -m phase1_simulator.run_smoke_batch --out <dir A>
python3 -m phase1_simulator.run_smoke_batch --out <dir B>
diff -q <dir A> <dir B>
```
Result: **no differences reported** — every one of the 13 generated JSON
files, plus `manifest.json`, was byte-identical across the two independent
runs.

## 4. Sample output inspection (real data, one file)

`smoke_test_output/sudden_increase-1003.json`, worker `W-00`:
- `truth_events`: `[{"start": 36, "end": 41, "label": "Sudden increase"}]`
- `fault_events`: `[]`
- `true_dose_mSv`: `0.0060555714870947856`
- `observed_dose_mSv`: `0.006044700870188324`

The small difference between true and observed dose (≈0.18%) is exactly
the expected effect of the ±5% measurement-noise model on a dose
computation integrated over 60 one-minute readings — not a bug, and not a
claim about real dosimeter noise (that noise fraction is itself flagged
`INHERITED_FROM_V1.2.3_UNVERIFIED`, Parameter Registry row 11).

## 5. What this report does not claim

- It does not claim the provisional numeric ranges (procedure multipliers,
  event/fault magnitudes and durations, shift lengths) are realistic —
  they are placeholders, explicitly labeled as such in
  `simulation_config.json` and enforced as such by
  `test_config_with_unlabeled_parameter_is_rejected` and related tests.
- It does not claim any detection, forecasting, or rotation-recommendation
  capability — none is implemented.
- It does not claim statistical adequacy — one seed per archetype is a
  smoke test, not the ≥30-seeds-per-class evaluation sample the
  methodology document specifies for the next phase.
- It does not claim cross-platform or cross-Python-version reproducibility
  — only same-Python-version reproducibility was tested, and that scope is
  stated explicitly in `PHASE1_README.md`.
