# Phase 2C: Corrective Integration Implementation — Report

Implements the corrections recommended in `PHASE2B_INTEGRATION_AUDIT.md`,
in the order given there. All code changes are inside
`research-demo/validation-dev/`; the frozen v1.2.3 release was not
modified (SHA-256 re-verified unchanged:
`92e897dd0ff1738f083df829b53f7f46377e042b7019bb9776232792261182ee`); the
public prototype was not touched or deployed; no forecasting or rotation
algorithm was implemented; no statistical campaign was run.

---

## 1. Immediate-alert behavior restored (audit §4)

**Code:** `phase2a_adapter/detection_adapter.py` — `classify_series` now
computes, per minute, exactly what `SimLab.runWorker`/`SafetyLab.runWorker`
compute (frozen release line 2964): `valid && AlaradSafety.immediateAlert({cumulativeDose}, {mode:'dose', doseMsv: AlaradSafety.policy().doseMsv})`,
reading the engine's own **live** policy rather than a hardcoded value.
`evaluate_radiation_detection` gained `use_immediate_alert: bool = True`
(default **on**, matching the engine's own default policy
`{mode:'dose', doseMsv:null}`), and now calls
`buildEpisodes(flagged, K, imm)` with the real `imm` array instead of
always passing `null`.

**Regression test (not a smoke check — an exact-match proof), new in
`tests/test_reference_reproduction.py::TestImmediateAlertReproduction`:**
- `test_s8_immediate_alert_fires_and_matches_engine_at_k3_and_k5`: extracts
  S8's real rates from `SafetyLab.run('S8', K)` for K=3 and K=5,
  independently redrives `evaluateExposure` → `immediateAlert` →
  `buildEpisodes(flagged, K, imm)` → `matchEvents` → `metrics`, and
  confirms an **exact match** against the engine's own TP/FP/FN and full
  episode list (both episodes, `immediate: true`, detected at their own
  run-start minutes 15 and 40 — not delayed by the confirmation window).
- `test_s8_without_immediate_alert_detects_later_at_k3_and_k5`: confirms
  the bypass is actually doing something — with `imm=null` forced, the
  same input detects strictly later than minute 15 at both K values.

Both pass. This closes the one finding in the audit with a demonstrated,
nonzero effect on real detection timing.

---

## 2. Baseline/candidate validity handling aligned (audit §5, Finding 1)

**Code:** new shared helper `detection_adapter.valid_mask(bridge, series)`,
calling the engine's own `SimLab.pure.validReading` — the same check the
candidate already used. `baselines.py`'s `baseline_2_fixed_threshold` and
`baseline_3_moving_average` now call it instead of their own narrower
`v is None or v != v` check. **The classification rules themselves
(fixed-threshold comparison, moving-average) remain independently
defined** — only the gate deciding which minutes are even eligible to be
compared changed, per the instruction to keep the baselines independent.

**Regression tests, new in `tests/test_baselines.py`:**
- `test_validity_gate_matches_real_engine_on_a_negative_non_nan_value`:
  constructs a series with a negative, non-NaN value; confirms the OLD
  check would have accepted it (`v is not None and v == v` is `True`)
  while `valid_mask` correctly rejects it, matching the engine's own rule.
- `test_baseline_2_excludes_a_negative_value_the_old_check_would_have_flagged`:
  end-to-end — injects a large negative value into real Phase 1 output
  and confirms `baseline_2_fixed_threshold` never flags it, even though
  it would clear the fixed-multiple threshold numerically.

Both pass, demonstrating the fix is real, not merely non-breaking.

---

## 3. Phase 1 output schema extended additively (audit §3)

**Code:** `phase1_simulator/scenario.py`'s `simulate_run` now includes
`"area_monitor_raw_rate_uSv_h"` (the raw, pre-inverse-square-conversion
area-monitor reading — previously a local variable, discarded) in each
worker's result dict, `None` for personal-mode workers.
`phase1_simulator/output.py`'s `run_to_dict` serializes this new series
field plus a new `"area_params"` field (the geometry already held
internally, now exposed), both `None` for personal-mode workers. **No
existing field's shape changed.**

**Regression check:** Phase 1's full existing test suite (40 tests) was
rerun unchanged after this edit — still 40/40 passing, confirming the
addition is genuinely additive and did not alter Phase 1's
already-accepted behavior for any existing consumer.

---

## 4. S4 area-mode evaluation pathway implemented (audit §3)

**Code:** `detection_adapter.evaluate_radiation_detection` no longer
raises `NotImplementedError` for area-mode workers. It reads the new
`area_params`/`area_monitor_raw_rate_uSv_h` fields, rescales the **raw**
monitor series (not Phase 1's own already-converted estimate), computes
`dist(t)` from `area_params["move_at"]`/`distance_before_m`/
`distance_after_m`, and calls `evaluateExposure(mode:'area', dist, refDist, shield)`
per minute — the real engine performs its own fixed-exponent-2
conversion, exactly as it does for its own S4.

**Regression test, new in `test_reference_reproduction.py::TestRadiationLayerReproduction.test_s4_area_mode_reference_scenario_reproduces_exactly`:**
extracts S4's own `dist`/`engineRate` per minute from `SimLab.run('S4',1,0)`,
derives the raw monitor reading that would produce that `engineRate`
under the engine's own known conversion, independently redrives
`evaluateExposure(mode:'area', ...)` on that derived raw value, and
confirms an exact TP/FP/FN match. Separately confirmed end-to-end on
real Phase 1 `area_relocation` output (smoke run, §8 below): TP=1,
FP=0, FN=0, detected at minute 31.

S4 moves from **Missing** to **Covered** in the coverage matrix (§5).

---

## 5. Scenario coverage: S8–S13 addressed, with evidence (audit §7)

**Approach:** rather than building new Phase 1 archetypes for every
engine scenario's exact dynamic (a larger, separate effort — see
"Not done" below), this phase extended the *reproduction-testing*
methodology itself (which needs no Phase 1 analog — it extracts the
engine's own data and redrives it) from S1–S3/S5–S7 to **all thirteen**
scenarios, both layers:

- `TestDataQualityLayerReproduction.test_all_dq_reference_scenarios_reproduce_exactly`
  now iterates S7–S13: for each, extracts the real per-minute
  observations (reconstructing `{ts, value}` from `recv`, including
  S13's documented 3-minute `delayed` lag — taken from
  `Ground_Truth_Scenarios_S1-S13.md`, not guessed, and independently
  confirmed to reproduce the engine's own state sequence before being
  used in the test), redrives `sensorStep` → `buildEpisodes` →
  `matchEvents` (against the engine's own `dqEvents` ground truth) →
  `metrics`, and asserts an exact match on the full state sequence and
  dTP/dFP/dFN.
- `test_radiation_layer_on_dq_scenarios_reproduces_exactly` does the same
  for the radiation layer on S8, S9, S12, S13 (the four DQ scenarios that
  also carry a radiation ground truth), against the engine's own
  `revents`/TP/FP/FN.

**Result: all of S1–S13 now have an exact-match reproduction test**,
for whichever layer(s) that scenario actually exercises. **This is a
claim about adapter fidelity (does this code call the real engine
correctly), not about Phase 1's generative coverage** — seep §5 of the
updated coverage matrix below for why those are different claims, and
which one is being made for which scenario.

**Not done:** no new Phase 1 archetype was built for S10's "frozen
sensor masks a real event" dynamic or S11's "fault fully resolves, then
a separate later event" dynamic — Phase 1 still has no generator that
produces that *specific* combination (confirmed by re-reading
`scenario.py`'s `fault_frozen`/`fault_missing` branches: no radiation
event is ever added alongside those faults). This was a lower-priority
item in the audit's recommendations (§9, item 6) and was judged out of
scope for this corrective pass, which focused on adapter fidelity rather
than expanding Phase 1's generative scope. It remains open — see §7 of
the updated coverage matrix.

---

## 6. Engine's illustrative parameters registered (audit §6, §8)

**Code:** new `phase2a_adapter/config/engine_provisional_parameters.json`,
a read-only snapshot of the frozen engine's own `baselineRates`, `CONFIG`,
the 30-minute horizon, and the default immediate-alert policy — each
carrying the engine's own source comment verbatim (e.g. *"CONFIGURABLE,
ILLUSTRATIVE placeholder values (not derived from real data)"*) and an
explicit `PROVISIONAL` status, cross-referenced to new Parameter Registry
rows.

**Methodology update:** `ICAIRE_Simulation_Validation_Methodology.md`
Revision 3 adds rows 14–18 to §9's registry (the engine's own
`baselineRates`, `CONFIG`, the rescaling's physical coherence, the
immediate-alert bypass's clinical basis, and S10/S11's realism once a
generator for them exists) — additive only; Revision 2's content is
otherwise unchanged, per the instruction to preserve the existing
methodology.

**Regression test, new in `test_engine_contract.py::test_registered_engine_parameters_match_the_live_engine`:**
confirms the registered snapshot's values, read from the committed JSON
file, match a **live** read from the engine — guarding against the
registered copy silently drifting from what the engine actually reports.

---

## 7. Audit: can dose-rate rescaling be eliminated safely? — **Decision: retained, not eliminated**

Re-examined specifically against the three things this instruction asked
to be demonstrated, building on `PHASE2B_INTEGRATION_AUDIT.md` §1 and
re-verified numerically in this session (not merely re-asserted):

1. **Detection thresholds:** the deviation-based classification term is
   provably scale-invariant under this rescaling (`PHASE2B_INTEGRATION_AUDIT.md`
   §1.3 — unchanged by anything in this phase). The dose-based term is
   not scale-invariant in general, but **re-checked numerically after
   adding the immediate-alert bypass (item 1 above), which also depends
   on absolute `cumulativeDose`:** for the engine's own room baselines
   (35–92 µSv/h) and `doseCritical=0.35` mSv over the 30-minute horizon,
   the immediate-alert threshold requires an event magnitude of
   **7.6×–20×** baseline (computed per room, this session). Phase 1's
   own provisional event-magnitude range (registry row 3) tops out at
   **6.0×**. So, for the ranges actually in force right now, rescaling
   changes neither the ordinary classification outcome nor the
   immediate-alert outcome on any Phase-1-generated event — confirmed
   by both this calculation and the smoke run (§8: `n_immediate_episodes`
   is 0 across all 11 smoke runs). **This is still a property of the
   current specific constants, not a structural guarantee** — if Phase
   1's event-magnitude range were ever widened past roughly 7.6× (e.g.
   to approach S8's own ×9 design), this would need re-verification.
2. **Cumulative dose:** unchanged from the Phase 2B finding — the
   engine's internally-computed `cumulativeDose` is on the engine's
   baseline scale, not Phase 1's, and the two are not currently compared
   anywhere in this codebase, so no inconsistency has occurred in
   practice, but they remain non-interchangeable numbers.
3. **Comparability of results:** eliminating rescaling cleanly (the
   audit's §2 proposal — redefining Phase 1's `procedure_classes` to
   derive baseline from the engine's own `baselineRates[room]`) would
   change Phase 1's **already-accepted** output schema's numeric
   content (not just add a field, as §3 did) — a change of a different
   kind than this phase's other, purely additive corrections, and one
   that was not itself asked for in this phase's task list. Per the
   instruction — *"If scientific approval is needed, retain the current
   approach and document the limitation"* — that is the situation here:
   eliminating rescaling is a Phase 1 re-approval matter, not a Phase 2C
   corrective-implementation matter.

**Decision: the current rescaling approach is retained, unchanged, in
this phase.** The limitation is the same one already registered as
Parameter Registry row 16 (§6 above): rescaling preserves pattern shape
and (for the ranges currently in force) classification outcomes, but it
does not establish that Phase 1's procedure-class framing and the
engine's room-based framing represent the same real-world quantity —
that remains open, pending the domain review row 16 calls for.

---

## 8. Regression tests and smoke evaluation (real results, this session)

**Phase 1 full suite:** `python3 -m unittest discover -s phase1_simulator/tests -t .`
→ **40 passed, 0 failed** (rerun after the additive schema change, §3).

**Phase 2A/2C full suite:** `python3 -m unittest discover -s phase2a_adapter/tests -t .`
→ **31 passed, 0 failed** (up from Phase 2A's 25 — 6 net new tests: the
immediate-alert regression class (2), the baseline-validity regression
tests (2), the registered-parameters test (1), and the expanded
reproduction suite replacing the old 3-test file with new coverage
across S1–S13 and S4; some old test names were superseded, others kept).

**Smoke batch** (`python3 -m phase2a_adapter.run_phase2a_smoke`, 11
archetypes incl. `area_relocation`, one seed each):

| Method | TP+FN (events) | FP (false alarms) | Notes |
|---|---|---|---|
| Candidate (imm bypass **on**, K=1) | 5 true events, 5 detected | 1 (the deliberate S5-style transient) | `n_immediate_episodes=0` in every run — consistent with §7's analysis |
| Baseline 0 (always-normal) | 0 detected of 4 (personal-only) | 0 | floor |
| Baseline 2 (fixed-threshold) | 4 of 4 detected (personal-only) | 1 | |
| Baseline 3 (moving-average) | 4 of 4 detected (personal-only) | 0 | smoothed the transient |
| Data-quality layer | 6 of 6 faults detected (all 11 workers) | 0 | |
| Area-mode worker (new) | 1 of 1 detected | 0 | first real area-mode result from this adapter |

This is a smoke test (11 single-seed runs), not a statistical result —
restated explicitly per the recurring discipline in every prior phase's
reports.

---

## Updated scenario coverage matrix

Two distinct axes, kept separate per item 5's instruction not to claim
coverage loosely:
- **Reproduction-verified**: an exact-match test exists against that
  scenario's own engine-computed output. This is a claim about *adapter
  fidelity*.
- **Phase 1 generator analog**: a Phase 1 archetype exists that produces
  a structurally similar dynamic, usable for the future statistical
  campaign. This is a claim about *generative coverage*, independent of
  the first.

| Scenario | Layer(s) | Reproduction-verified | Phase 1 generator analog | Notes |
|---|---|---|---|---|
| S1 | Radiation | **Yes** | `normal` | |
| S2 | Radiation | **Yes** | `gradual_increase` | |
| S3 | Radiation | **Yes** | `sudden_increase` | |
| S4 | Radiation (area) | **Yes (new, Phase 2C)** | `area_relocation` | |
| S5 | Radiation | **Yes** | `transient_spike` | |
| S6 | Radiation | **Yes** | `multi_worker_mixed` | |
| S7 | DQ | **Yes** | `fault_missing` | |
| S8 | DQ + Radiation | **Yes (new, Phase 2C)**, incl. immediate-alert at K=3/K=5 | `fault_during_event`/`concurrent_alert_and_fault` (analog only) | upgraded from Partial |
| S9 | DQ + Radiation | **Yes (new, Phase 2C)** | none exact (two separate invalid sub-windows) | upgraded from Partial |
| S10 | DQ + Radiation | **Yes (new, Phase 2C)** | **None** | masked-event dynamic not yet generatable; upgraded reproduction only |
| S11 | DQ + Radiation | **Yes (new, Phase 2C)** | **None** | recovery-then-later-event dynamic not yet generatable; upgraded reproduction only |
| S12 | DQ + Radiation | **Yes (new, Phase 2C)** | `multi_worker_faults` | |
| S13 | DQ + Radiation | **Yes (new, Phase 2C)** | `concurrent_alert_and_fault` (analog only) | required reconstructing the documented 3-minute lag |
| Baseline 0/1/2/3 | Radiation only | tested | personal-mode only | no DQ-layer baseline exists (unchanged from Phase 2B) |
| Immediate-alert bypass | Radiation (timing) | **Yes (new, Phase 2C)** | n/a | S8 at K=3/K=5 |
| Forecasting | — | — | — | Track A, still not implemented, by design |
| Rotation | — | — | — | Track B, no algorithm exists, by design |

---

## Remaining limitations (not resolved by this phase)

1. **No Phase 1 generator exists for S10's or S11's specific dynamic**
   (§5). Reproduction-testing closed the adapter-fidelity gap; it does
   not create new statistical-campaign data for these dynamics.
2. **Dose-rate rescaling is retained, not eliminated** (§7) — the
   Phase-1-vs-engine baseline framing question (registry row 16) remains
   open, pending domain review.
3. **No DQ-layer baseline comparator exists** (carried over from Phase
   2B, unchanged — out of scope for this corrective pass).
4. **The two new baselines (2/3) remain personal-mode-only** — not
   extended to area mode in this phase; the methodology never specified
   an area-mode variant for them.
5. **Chromium version caveat** carries forward unchanged (141 pinned vs.
   153 used, per every prior phase's disclosure).
6. **Baseline 2/3 threshold values, and the engine's own `baselineRates`/
   `CONFIG`/immediate-alert policy, remain unevidenced placeholders**
   (registry rows 5, 6, 14, 15, 17) — now at least all registered, none
   resolved.
7. **No statistical campaign has been run.** Every number in this report
   describes specific seeds and specific reference scenarios, not a
   sample.

---

## Recommendation: is the detection integration ready for formal statistical evaluation?

**Not yet — ready for the *next* gated step (domain/expert review of the
registry), not for the statistical campaign itself.**

What this phase establishes with real evidence: the adapter's call
sequence is now verified, by exact reproduction, to faithfully invoke the
real engine's detection logic — including the immediate-alert bypass —
across all 13 reference scenarios and both the radiation and
data-quality layers, for every pathway the engine actually exercises for
them. That is a genuine, demonstrated increase in confidence that the
software does what it is supposed to do.

What is still missing before a statistical campaign would produce
scientifically interpretable results is not, at this point, mostly a
software question — it is the set of open Parameter Registry rows (23
total: 13 from Revision 2, 5 newly added in Revision 3), none of which
this phase resolved, because none were resolvable in code. Chief among
them for readiness: the engine's own `baselineRates`/`CONFIG` (rows
14–15) and the Phase-1-to-engine rescaling's physical coherence (row 16)
are now both registered but **unreviewed** — running a statistical
campaign before that review would produce numbers whose absolute scale
and whose event-severity framing have not been validated by anyone with
the relevant domain expertise, regardless of how faithfully the adapter
reproduces the engine.

**Concretely recommended before proceeding to the full campaign:**
expert review of registry rows 14–17 (the engine's own thresholds, the
rescaling's physical coherence, and the immediate-alert bypass's clinical
basis) — the three items this phase's own work made newly load-bearing.
Rows 1–13 remain open from before and are not newly urgent because of
this phase's work, but are no less required before any paper-facing
claim.
