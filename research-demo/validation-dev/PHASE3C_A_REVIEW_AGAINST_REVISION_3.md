# Phase 3C-A Implementation — Review Against PHASE3B Revision 3

**Purpose:** this round's task 3. Reviews the existing, already-
delivered `phase3c_rotation_infra/` package (committed as Phase 3C-A)
against `PHASE3B_ROTATION_ALGORITHM_DESIGN.md`'s now-corrected §3a/§3i
(Revision 3), to confirm what already holds up and name exactly what
does not yet exist. **No code is changed by this document** — it is a
read-only review, and every gap it finds is listed as a blocker for
Phase 3C-B, not fixed here.

`PHASE3C_A_IMPLEMENTATION_REPORT.md` and
`PHASE3C_A_DOSE_THRESHOLD_SEMANTIC_AUDIT.md` are left exactly as they
were — this document supersedes nothing in either; it is a new,
separate review layered on top of them now that §3a/§3i exist.

---

## 1. What already holds up, confirmed by re-reading the actual code

### 1a. Dose attribution is already independent of the engine's misnomer

`phase3c_rotation_infra/dose_attribution.py` never reads
`CONFIG.doseElevated`/`doseCritical`, never calls `evaluateExposure()`,
and never uses the name `cumulativeDose`. Its `cumulative_dose_per_worker`
function computes a genuine running sum via
`phase1_simulator.units.dose_increment_mSv`/`MINUTE_H`, summed over
every attributed minute from shift start — this is **exactly**
§3a (Revision 3)'s `WorkerAccumulatedShiftDose(W, t)`, already
implemented correctly, by construction, before the corrected
terminology even existed. **Confirmed: no correction needed here.**

### 1b. No dose-trigger logic was implemented prematurely

Grepped `phase3c_rotation_infra/*.py` for `doseElevated`, `doseCritical`,
`CONFIG`, and `cumulativeDose`: no match outside comments/docstrings
explaining why they are *not* used. `assignment.py`'s `batch_resolve`
and `scheduling.py`'s `start_attempt`/`resolve_attempt` take a
caller-supplied `candidate_order` / `reserved_worker_id` — neither
module computes *whether* a rotation should be proposed, only what
happens once one has been. **Confirmed: Phase 3C-A built no trigger
formula, correct or otherwise, consistent with its own stated scope and
this round's restriction.**

### 1c. Escalation is already correctly decoupled

`phase3c_rotation_infra/escalation.py::evaluate_escalation` takes only
`sensor_states` (strings) and a minute-count threshold — no parameter
of any dose quantity exists in its signature, and
`test_escalation_never_mentions_dose_values`
(`tests/test_escalation.py`) already checks this structurally.
**Confirmed: matches §3a (Revision 3)'s escalation-decoupling statement
exactly, without needing any change.**

---

## 2. Incompatibilities and gaps requiring correction before Phase 3C-B

None of the following are defects in Phase 3C-A as delivered — they are
places where §3a/§3i's now-more-detailed specification names something
Phase 3C-A's own, already-disclosed scope did not yet build. Listed so
Phase 3C-B does not discover them mid-implementation.

1. **No per-worker "last valid reading" field exists anywhere in
   `staffing.WorkerProfile`.** §3a's clauses (b)/(c) both need
   `rate_last_valid_uSv_h(W)` at decision time; `WorkerProfile` today
   has `cumulative_dose_mSv` (present but, per item 2 below, never
   updated) and no live-rate field at all. **Phase 3C-B needs to add
   this field (or an equivalent live lookup), explicitly tied to the
   engine's own `validReading`/`sensorStep` validity checks (§3a's
   input-validity rule), not just a raw number.**
2. **`WorkerProfile.cumulative_dose_mSv` is declared but never written
   to.** `dose_attribution.py` computes cumulative dose correctly, but
   as a standalone post-hoc calculation over a full exposure+assignment
   layer — it does not feed its result back into the roster's own
   `WorkerProfile` objects. §3i's "live per-minute accumulated-dose
   update" requires this field to be kept current *during* a run, not
   only computed afterward. **This is the single largest concrete gap
   §3i names**: `assignment.batch_resolve`'s eligibility filtering has
   no live dose figure to read at all today.
3. **No duty-limit exclusion check exists in `assignment.batch_resolve`.**
   Already disclosed as a blocker in
   `PHASE3C_A_IMPLEMENTATION_REPORT.md` §4 item 3, before §3i existed to
   specify it precisely; §3i's exact exclusion condition (projected
   over the full intended assignment interval, not a point-in-time
   check) is now the precise spec Phase 3C-B should implement against,
   superseding the previous report's more general description of the
   gap.
4. **No mechanism queries sensor validity for a specific worker at a
   specific decision minute.** `escalation.py`'s sensor-state handling
   is driven by a pre-built `sensor_states` list per worker, built
   externally (as `test_escalation.py`'s integration test does, via
   `dq_adapter.run_sensor_state_machine`) — nothing in `scheduling.py`
   or `assignment.py` calls this to answer "is this specific candidate's
   reading valid right now," which §3a's clause (b)/(c) fail-safe rules
   need. **Phase 3C-B needs a function that answers this per-worker,
   per-minute question**, most naturally built by reusing
   `dq_adapter`'s state machine per worker, threaded forward minute by
   minute alongside the live dose update in item 2.
5. **`AssignmentSlot`'s "remaining scheduled minutes" is not exposed as
   a reusable helper.** §3a's horizon definitions and §3i's "intended
   assignment interval" both need "how many minutes remain in the
   upcoming/target slot from a given decision point" — today this is
   computed ad hoc (e.g., `slot.end_minute - t`) wherever it is needed,
   not as a named, tested function. A minor gap, but worth naming so
   Phase 3C-B does not duplicate this arithmetic three different ways.

---

## 3. What this review does not claim

- Does not claim Phase 3C-A's 55 tests need to be re-run or were wrong
  — they test exactly what Phase 3C-A built, and that remains correctly
  tested; the gaps above are about what was **not yet built**, not
  about any existing test being invalid.
- Does not claim the §3a/§3i correction retroactively invalidates
  `PHASE3C_A_IMPLEMENTATION_REPORT.md` — that report's own §4 already
  flagged items 2/3 above as open, in less precise terms than §3i now
  states them.
- Does not implement, or propose code for, any of the five gaps above
  — Phase 3C-B's own scope, not this round's.
