# Phase 2A Smoke Test Report

**This is a smoke test, not scientific validation** — the same discipline
as `PHASE1_SMOKE_TEST_REPORT.md`. It answers: *does the adapter run
end-to-end against the real frozen engine, on real Phase 1 output, and
does it faithfully reproduce the engine's own behavior?* It does not
answer whether the candidate detector or either new baseline performs
well in any general sense — 10 runs, one seed each, is not a statistical
sample. All numbers below came from actually running the code in this
session on 2026-11-21.

## 1. Unit/integration test run (real output)

Command: `python3 -m unittest discover -s phase2a_adapter/tests -t . -v`

**Result: 25 passed, 0 failed, 0 skipped.** Full breakdown:

| File | Tests | Purpose |
|---|---|---|
| `test_engine_contract.py` | 4 | the engine API this adapter depends on is present and correctly typed; a deliberately broken contract is caught, not swallowed |
| `test_reference_reproduction.py` | 3 | task 8 — exact-match proof against the engine's own S1–S6 and S7 |
| `test_ground_truth_matching.py` | 9 | task 7 — matching, temporal alignment, false alarms, missing data, zero-event |
| `test_baselines.py` | 6 | the two new baselines run and score through real-engine primitives |
| `test_dual_layer.py` | 4 | task 4 — radiation/DQ independence |

## 2. Task 8 evidence, in detail (real, not asserted)

- **Radiation layer:** for each of S1, S2, S3, S4, S5, S6, this session
  extracted the exact noiseless per-minute rates `SimLab.run()` itself
  generated, fed them independently through this adapter's own
  `evaluateExposure → buildEpisodes → matchEvents → metrics` call
  sequence, and compared TP/FP/FN against the engine's own result.
  **All five personal-mode scenarios (S1, S2, S3, S5, S6) matched
  exactly.** S4 (area-mode) was explicitly not attempted — see
  `PHASE2A_LIMITATIONS.md` item 1 — and a passing test confirms that skip
  is deliberate.
- **Data-quality layer:** this session extracted S7's exact raw
  observation stream (including its missing-data gap) from
  `SafetyLab.run()`'s own output, fed it independently through this
  adapter's `sensorStep → buildEpisodes → matchEvents → metrics` call
  sequence, and confirmed **both the full per-minute state sequence
  (HEALTHY → STALE → DISCONNECTED → RECOVERING → HEALTHY) and dTP/dFP/dFN
  matched exactly.**

This is the concrete evidence behind the claim "the adapter reproduces
the frozen detector's outputs on reference scenarios" — not an assertion
made without it.

## 3. A real bug found and fixed during this phase's own smoke testing

The first smoke-batch run (10 personal-mode archetypes, one seed each)
produced a genuine, unexpected false positive:

```
sudden_increase   W-00   truth=1 faults=0   dq=0/1/0
```

`sudden_increase` injects **zero** sensor faults, yet the data-quality
layer reported one false positive. Investigated rather than dismissed:
the worker's raw Phase 1 values were ≈3.6–3.9 µSv/h (Phase 1's own
provisional procedure baseline), and the frozen engine's
`AlaradSafety.sensorStep` quantizes repeat-value detection at a 0.1 µSv/h
resolution — calibrated for the engine's own baseline scale (tens of
µSv/h). At Phase 1's much smaller scale, ordinary ±5% measurement noise
between consecutive minutes can land in the same 0.1 µSv/h bucket by pure
coincidence, which is exactly what happened at minutes 117–118, triggering
a spurious `SUSPECTED_FROZEN` state with no fault present.

**Fix:** `dq_adapter.build_observations` now applies the same
`rescale_to_engine_baseline` transformation already used by the radiation
layer, so sensor-fault evaluation also happens on the engine's own
baseline scale. After the fix, the full 10-run smoke batch and all 25
tests were rerun; the data-quality layer's false-alarm rate across all 10
runs is 0.0, and the result below reflects the corrected code.

## 4. Smoke batch results (real, 10 personal-mode archetypes, one seed each — corrected)

| Archetype | Truth events | Faults | Candidate TP/FP/FN | B0 (always-normal) | B2 (fixed-threshold) | B3 (moving-average) | DQ layer TP/FP/FN |
|---|---|---|---|---|---|---|---|
| normal | 0 | 0 | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 |
| gradual_increase | 1 | 0 | 1/0/0 | 0/0/1 | 1/0/0 | 1/0/0 | 0/0/0 |
| sudden_increase | 1 | 0 | 1/0/0 | 0/0/1 | 1/0/0 | 1/0/0 | 0/0/0 |
| transient_spike | 0 | 0 | 0/1/0 | 0/0/0 | 0/1/0 | 0/0/0 | 0/0/0 |
| fault_missing | 0 | 1 | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 | 1/0/0 |
| fault_invalid | 0 | 1 | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 | 1/0/0 |
| fault_frozen | 0 | 1 | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 | 1/0/0 |
| fault_delayed | 0 | 1 | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 | 1/0/0 |
| fault_during_event | 1 | 1 | 1/0/0 | 0/0/1 | 1/0/0 | 1/0/0 | 1/0/0 |
| concurrent_alert_and_fault | 1 | 1 | 1/0/0 | 0/0/1 | 1/0/0 | 1/0/0 | 1/0/0 |

**Candidate (real engine, K=1):** 4/4 true radiation events detected, 1
false positive (the deliberately-unlabelled transient spike — this is the
S5 convention working as intended, not a defect), 0 false negatives.
False alarms per worker-shift: 0.1.

**Baseline 0 (always-normal):** 0/4 events detected, as expected of a
floor.

**Baseline 2 (fixed-threshold, provisional 2.0× multiple):** matched the
candidate exactly on this batch (4/4 TP, 1 FP on the same transient
spike) — not evidence the two methods are equivalent in general, only
that this provisional threshold happened to agree with the real engine on
these 10 seeds.

**Baseline 3 (moving-average, provisional 5-minute window, 2.0×
multiple):** 4/4 TP, 0 FP — the averaging window smoothed out the
transient spike that both the candidate and Baseline 2 flagged.

**Data-quality layer (after the fix in §3):** 6/6 injected faults
detected, 0 false positives, across all 10 runs — false alarms per
worker-shift: 0.0.

## 5. What this report does not claim

- It does not claim the candidate detector, Baseline 2, or Baseline 3
  performs well, or that any is better than the others — 10 single-seed
  runs is a smoke test, not the ≥30-seeds-per-class campaign the
  methodology specifies.
- It does not claim area-mode radiation detection works — it is not
  implemented (see `PHASE2A_LIMITATIONS.md` item 1).
- It does not claim Phase 1's provisional baselines and the frozen
  engine's own baselines represent the same real-world quantity —
  rescaling preserves pattern shape, not absolute-value equivalence (see
  `PHASE2A_LIMITATIONS.md` item 2).
- It does not claim the provisional baseline-2/baseline-3 threshold
  values are realistic or evidence-based.
