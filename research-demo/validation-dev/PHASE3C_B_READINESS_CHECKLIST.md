# Phase 3C-B Readiness Checklist

**Purpose:** a single place that says, plainly, what is already in
place for implementing the corrected CGDTR trigger and live duty-limit
enforcement, and what specifically remains before Phase 3C-B could
start. Builds on `PHASE3A_FORECASTING_READINESS_CHECKLIST.md`'s format
and discipline — a checklist, not a decision, and not an approval.

---

## 1. Already in place

- [x] **The dose-trigger semantic mismatch is found, verified, and
  corrected in the design** — `PHASE3C_A_DOSE_THRESHOLD_SEMANTIC_AUDIT.md`
  (read-only, line-cited against the frozen `evaluateExposure()`) and
  `PHASE3B_ROTATION_ALGORITHM_DESIGN.md` §3a (Revision 3), which now
  names three separately-owned quantities (`EngineProjectedTaskDose`,
  `WorkerAccumulatedShiftDose`, `ProjectedShiftTotalDose`) instead of
  one conflated one.
- [x] **The revised trigger's three clauses are specified with exact
  units, horizons, and threshold ownership** (§3a clauses (a)/(b)/(c)),
  including per-clause sensor-validity handling and an explicit
  statement that sensor-fault escalation is independent of all three.
- [x] **The duty-limit eligibility gap is specified precisely** (§3i):
  live per-minute accumulated-dose updates, and a projected-duty-limit
  exclusion check over the full intended assignment interval, added as
  one more exclusion condition alongside §3g's existing ones — no
  existing constraint loosened.
- [x] **Phase 3C-A's infrastructure review found no incompatibility
  requiring rework** — only gaps where something not yet built is now
  precisely specified (`PHASE3C_A_REVIEW_AGAINST_REVISION_3.md`): dose
  attribution is already correctly independent of the engine's
  misnomer; no trigger logic was implemented prematurely; escalation is
  already correctly decoupled from dose.
- [x] **All of Phase 3C-A's new provisional parameters are now
  registered** (`ICAIRE_Simulation_Validation_Methodology.md` Revision
  6, rows 21-24; propagated to `SCIENTIFIC_PARAMETER_REVIEW_PACKAGE.md`,
  `SCIENTIFIC_PARAMETER_REVIEW_SUMMARY.md`,
  `UNRESOLVED_SCIENTIFIC_DECISIONS.md`), each marked illustrative and
  **unapproved for any clinical or operational use** — none implies
  Medical Physicist or RSO sign-off.
- [x] **55 tests from Phase 3C-A still pass, unaffected by this round's
  documentation-only changes** (no code was touched this round; the
  tests were not re-run because nothing they test changed, but nothing
  in this round's edits contradicts what they check either).

## 2. Concrete gaps Phase 3C-B must close (from `PHASE3C_A_REVIEW_AGAINST_REVISION_3.md` §2)

- [ ] **Add a live per-worker rate/last-valid-reading field** to
  `WorkerProfile` (or an equivalent live lookup), tied to the engine's
  own `validReading`/`sensorStep` validity checks — §3a clauses (b)/(c)
  need this; it does not exist today.
- [ ] **Wire `dose_attribution`'s running total back into
  `WorkerProfile.cumulative_dose_mSv` live, per minute** — the field
  exists but is never written; §3i's live-update requirement needs
  this closed before any trigger clause (a) or duty-limit clause (c)
  can read a current figure during a run.
- [ ] **Implement §3i's duty-limit exclusion check inside
  `assignment.batch_resolve`** — projected over the full intended
  assignment interval, as one more exclusion condition alongside §3g's
  existing ones (not a separate mechanism).
- [ ] **Add a per-worker, per-minute sensor-validity query function**,
  reusing `dq_adapter`'s state machine (not reimplementing it), so
  clauses (b)/(c)'s fail-safe rule has something to call.
- [ ] **Expose "remaining scheduled minutes of a target slot from a
  given decision point" as a named, tested helper** on `AssignmentSlot`
  or alongside it, rather than ad hoc arithmetic wherever needed.

## 3. Tests required to verify the corrected trigger mathematics (new; none implemented yet)

These correspond to the new/revised entries in
`PHASE3B_ROTATION_ALGORITHM_DESIGN.md` §9a (Revision 3):

- `test_clause_b_uses_engine_projected_task_dose_not_accrued_total` —
  prove clause (b) does not fire when accrued dose is high but the
  engine's single-reading projection is low.
- `test_clause_c_uses_projected_shift_total_against_duty_limit` — prove
  clause (c) compares only against `max_dose_per_shift_mSv`, never
  against `CONFIG.doseElevated`/`doseCritical`.
- `test_stale_sensor_reading_never_used_as_trigger_input` (revised) —
  per-clause: clause (a) unaffected by current sensor state; clauses
  (b)/(c) evaluate as not-met on stale/disconnected/invalid input.
- `test_dose_values_normalized_to_mSv_before_threshold_comparison` — a
  unit-consistency check across all three clauses.
- `test_sensor_fault_escalation_independent_of_all_three_dose_clauses` —
  prove the two channels (dose trigger, sensor escalation) never write
  to each other's state.

## 4. Tests required to verify live duty-limit enforcement (new; none implemented yet)

- `test_incoming_worker_excluded_if_projected_to_exceed_duty_limit_across_assignment_interval` —
  a candidate currently under the limit but projected to exceed it
  before the intended assignment ends must be excluded at the batch
  pass, not merely deprioritized.
- `test_live_accumulated_dose_update_matches_full_replay` — the
  incremental, per-minute update must equal a full-shift replay via
  `dose_attribution.cumulative_dose_per_worker`, never drift from it.
- A reproducibility test analogous to Phase 3C-A's existing seed-
  reproducibility tests, applied to the new live-update path
  specifically (same seed, same final accumulated-dose figures, with
  and without the live per-minute update path exercised).

## 5. What remains open regardless of code (decisions, not tests)

- Whether CGDTR's trigger should combine engine-owned and project-owned
  clauses in one decision at all, or keep them separate
  (`UNRESOLVED_SCIENTIFIC_DECISIONS.md` items 16-17;
  `PHASE3B_ROTATION_ALGORITHM_DESIGN.md` §10b items 1-2).
- The "intended assignment interval" convention for §3i's duty-limit
  projection when a slot's own future boundaries are not yet fixed
  (§10b item 3).
- Registry rows 21-24's own expert review — not required to *build*
  Phase 3C-B's code (illustrative values are enough to test the
  machinery, exactly as Phase 3C-A already did), but required before
  any Phase 3C-B *result* could be read as more than infrastructure
  testing, per the same discipline every prior phase has followed.

## 6. Is Phase 3C-B ready for implementation?

**Conditionally: the specification is ready; the code gaps in §2 are
not yet closed.** Everything CGDTR's corrected trigger and the
duty-limit check need has now been specified precisely enough to
implement against (§3a, §3i), and Phase 3C-A's infrastructure review
found no incompatibility requiring rework — only the five concrete,
narrowly-scoped gaps in §2, each of which is additive to existing code,
not a correction of it. **Phase 3C-B's own first step should be closing
§2's gaps** (live dose/sensor-validity plumbing) **before** writing
CGDTR's trigger/selection logic itself, so the trigger is built against
working inputs rather than placeholders. This checklist does not itself
authorize starting that work.
