# Phase 3B — Worker-Rotation Algorithm and Counterfactual-Simulation Design

**Status: implementation-ready design specification. No code has been
written, no algorithm has been implemented, no simulation has been run,
and no dose-reduction result — simulated or otherwise — is reported
anywhere in this document.** This is the explicit restriction for this
round, and every section below is written to be buildable *from*, not a
substitute for, a future implementation phase that has not yet been
approved.

**Relationship to existing documents (read this before the rest):**
this is a **companion** to `ROTATION_RECOMMENDER_DESIGN_SPEC.md`, not a
replacement. That document's hard validity constraints (§2), scoring
objectives (§3), rotation baselines (§4), evaluation metrics (§5), and
ground-truth assumptions (§6) are **reused verbatim below**, cited by
section number, never restated with different wording or different
substance. Nothing in `ICAIRE_Simulation_Validation_Methodology.md` or
`ROTATION_RECOMMENDER_DESIGN_SPEC.md` has been edited to produce this
document, beyond one non-substantive forward-pointer note added to the
top of `ROTATION_RECOMMENDER_DESIGN_SPEC.md` (see its own "Update"
paragraph). **No prior approval is being silently revised by this
document.**

**Frozen release:** `ALARAD_Prototype_Research_Demo_v1.2.3.html`
(SHA-256 `92e897dd0ff1738f083df829b53f7f46377e042b7019bb9776232792261182ee`)
was not opened for writing at any point while producing this document,
and is not touched by anything specified below.

**Branch:** `research/icaire-v123-validation` (this file).

---

## Revision 2 — change log (this round; Revision 1 preserved below, not deleted)

**Trigger:** Phase 3B design review found Revision 1 "promising but
requiring Revision 2 before implementation approval," on five specific
issues. **Nothing in Revision 1 is deleted by this revision** — every
corrected subsection keeps Revision 1's original text, explicitly marked
**superseded**, immediately alongside the Revision 2 text that replaces
it, so the change is traceable. Additions (new subsections, new fields,
new tests) are marked **new in Revision 2** rather than superseding
anything.

| # | Issue (as given in the review) | Addressed in |
|---|---|---|
| 1 | Timing conflict between procedure-boundary decisions, handoff duration, and swap completion; swap must never take effect mid-procedure without an authorized emergency override | §3d (superseded and replaced) |
| 2 | Exclusive worker assignments; atomic reservation and conflict resolution for simultaneous requests | §2a (extended), §3b (extended), new §3g |
| 3 | Dose-trigger mathematics: additional vs. projected cumulative dose, mSv normalization, time horizon, stale/invalid-input handling, provisional-vs-regulatory threshold caveat | §3a (superseded and replaced) |
| 4 | Ablation comparisons isolating trigger-rule effect from replacement-selection effect; identical conditions across policies | §6 (extended with a 2×2 ablation design and a new ablation-only policy) |
| 5 | Safe failure and escalation when a dose concern persists but no valid rotation is possible; RSO notification, acknowledgement, audit logging, human authority | new §3h |
| — | Recheck collective-dose invariant under the above | §7b (rechecked, not contradicted) |
| — | Simultaneous rotations, interrupted handoffs, shift-end boundaries | §3d, §3g, §8 (state machine extended) |
| — | New unit tests, metrics, sensitivity items | §9 (extended) |
| — | New RSO/Medical-Physicist review items | §10 (extended) |

**Restrictions, unchanged from Revision 1:** no code was written or run
to prepare this revision; no simulator, forecasting, or frozen-release
file was touched; no statistical campaign was run; no dose-reduction,
fairness, or collective-dose result is reported anywhere.

---

## 0. What this document adds, in one paragraph

`ROTATION_RECOMMENDER_DESIGN_SPEC.md` specified *what any future
recommender must satisfy* (constraints, objectives, baselines, metrics)
without naming a specific algorithm, a specific staffing data model, or a
specific method for computing the counterfactual dose outcomes those
metrics need. This document supplies those four things — the candidate
algorithm (§3), the synthetic staffing/credentialing model (§2), the
counterfactual-simulation method (§5), and the full evaluation detail
(§9) — at a level a future implementer could build from directly,
without inventing any missing step themselves. It also makes one
modeling distinction explicit that the review round specifically asked
for (§7): collective dose, individual dose, and fairness are different
quantities, and an evaluation that reports only one of them risks
mistaking redistribution of exposure for a genuine reduction in it.

---

## 1. Review of the existing design spec and methodology (task 1)

Re-read in full while preparing this document, with no change made to
either:

- `ROTATION_RECOMMENDER_DESIGN_SPEC.md` §2–§6: constraints, objectives,
  baselines, metrics, and ground-truth assumptions — all reused below,
  unchanged.
- `ICAIRE_Simulation_Validation_Methodology.md` §1 (dose/unit
  definitions: µSv/h dose rate, mSv cumulative dose via
  `Dose (mSv) = Rate (µSv/h) × Duration (h) / 1000`, 1-minute time steps,
  personal-vs-area MEASURED/MODELED distinction, the invalid-reading
  rule), §2 (the existing multi-worker roster design: 1–3 workers per
  scenario today, widened to "a multi-worker roster per run" with
  per-worker independence already validated in S6/S12), and §6
  (operational constraints and scoring criteria, identical to
  `ROTATION_RECOMMENDER_DESIGN_SPEC.md` §2–§3 since that document reused
  them verbatim).
- `phase1_simulator/scenario.py`'s existing `WorkerSpec`/`RunSpec` data
  shapes (`worker_id`, `room`, `procedure_class`, `proc_mult`, `mode`,
  `baseline_rate_uSv_h`, `pattern`, `area_params`, `truth_events`,
  `fault_windows`; a `RunSpec` holding a `shift_minutes` and a list of
  `WorkerSpec`s) — reused as the base vocabulary for §2's staffing model
  and §5's counterfactual method, not redefined with different field
  names for the same concepts.

**Finding carried forward from this re-read, stated plainly:** the
current `phase1_simulator` ties one exposure pattern to one worker for
the entire run (one `WorkerSpec` = one fixed worker occupying one
room/procedure for the whole shift). Rotation — by definition — requires
more than one worker to be able to occupy the *same* room/procedure slot
across a shift. **This means the counterfactual-simulation method this
document specifies (§5) requires a structural extension to how exposure
is generated, not just a new scoring layer on top of today's
`phase1_simulator` output.** That extension is specified in detail below
(§5) but, per this round's restriction, is **not implemented** — it is
a prerequisite for a future implementation phase, flagged now so it is
not discovered as a surprise mid-implementation.

---

## 2. Synthetic staffing and credentialing model (task 3)

**Status: a provisional data schema, not a built dataset or code
module.** No real or synthetic staffing/credentialing dataset exists
anywhere in this project today (`ROTATION_RECOMMENDER_DESIGN_SPEC.md`
§2.1; registry row 8). This section specifies the schema a future
`phase1_simulator` extension (not yet built) would populate, synthetically
and seeded, exactly as every other Phase 1 quantity is — illustrative
until reviewed, never presented as derived from real staffing data.

### 2a. `WorkerProfile` (new; extends, does not replace, `WorkerSpec`)

| Field | Type | Illustrative example | Notes |
|---|---|---|---|
| `worker_id` | string | `"W03"` | Reuses `WorkerSpec.worker_id` exactly. |
| `credentialed_rooms` | set of room names | `{"Cath Lab 1", "Cath Lab 2"}` | Subset of the existing `ROOMS` list (`phase1_simulator/scenario.py`). **Not every worker is credentialed for every room** — this is the mechanism that makes eligibility (§3b below; design-spec §2.1) sometimes fail, which the evaluation must be able to observe, not just assume away. |
| `credentialed_procedure_classes` | set of procedure-class names | `{"diagnostic_fluoroscopy", "ct"}` | Subset of the existing `procedure_classes` config keys. |
| `max_dose_per_shift_mSv` | float, mSv | `2.0` | A **duty limit**, distinct from the engine's own alert thresholds (rows 14/15) — this is a staffing/scheduling limit on a worker's assignment, not a radiation-safety alarm. New provisional parameter (§10). |
| `min_rest_between_assignments_minutes` | int, minutes | `15` | Minimum gap after being rotated out before becoming eligible as a replacement again elsewhere in the same shift. New provisional parameter (§10). |
| `max_rotations_per_shift` | int | `2` | The rotation-burden fairness cap this document's algorithm enforces directly (§3, step 6); also referenced by `ROTATION_RECOMMENDER_DESIGN_SPEC.md` §2.4's "no worker disproportionately rotated" constraint. New provisional parameter (§10). |
| `availability_windows` | list of `(start_minute, end_minute)` | `[(0, 480)]` | When the worker is on shift at all, independent of assignment. A worker can be off-shift for part of the simulated window (e.g., a half-shift overlap) without that being a fault or incident. |
| `incident_state` | `"clear"` \| `"open"` | `"clear"` | Reuses the existing S7–S13 incident-state concept (`Ground_Truth_Scenarios_S1-S13.md`), not a new state machine. |
| `state` | `"FREE"` \| `"ASSIGNED"` \| `"RESERVED"` \| `"RESTING"` | `"FREE"` | **New in Revision 2 (addresses Issue 2).** The exclusivity state machine (§3g, §8a-ext): `ASSIGNED` = currently occupying a slot; `RESERVED` = selected as an incoming replacement for a `PENDING` rotation elsewhere, locked until that rotation resolves; `RESTING` = within `min_rest_between_assignments_minutes` of their last rotation-out. Supersedes treating "availability" as a single `availability_windows` check alone — Revision 1 did not distinguish these cases, which is exactly the gap that made simultaneous-request conflicts possible. |

### 2b. `AssignmentSlot` (new; the unit §5's counterfactual method operates over)

| Field | Type | Notes |
|---|---|---|
| `room` | string | One of `ROOMS`. |
| `procedure_class` | string | One of the configured procedure classes. |
| `start_minute`, `end_minute` | int | The span this room/procedure occupies this shift, before any rotation is applied — the "job to be staffed," independent of who staffs it. |
| `assigned_worker_id` | string, **time-varying** | Who occupies this slot at a given minute — the quantity a rotation policy actually changes. See §5. |

### 2c. Synthetic generation method (specified, not implemented)

For a given run (seed, archetype, `shift_minutes`, as already generated
by `phase1_simulator.scenario.generate_run`):

1. Generate the roster size as **at least one more worker than the
   number of concurrently-occupied rooms** in that run — otherwise no
   replacement can ever exist and every rotation decision point is
   trivially infeasible by construction, which would make the "no
   eligible replacement" path (§4) untestable. The exact extra-worker
   count is an open parameter (§10).
2. For each worker, sample `credentialed_rooms` and
   `credentialed_procedure_classes` from declared, explicitly-illustrative
   coverage-probability ranges (e.g., each worker credentialed for a
   random 40–70% of rooms) — **the exact range is a new provisional
   parameter, not chosen here** (§10), chosen only so that eligible
   replacements exist *sometimes*, not always and not never, which would
   each trivialize a different part of the evaluation.
3. Sample `max_dose_per_shift_mSv`, `min_rest_between_assignments_minutes`,
   and `max_rotations_per_shift` from declared illustrative ranges —
   open parameters (§10).
4. Default `availability_windows` to the full shift and `incident_state`
   to `"clear"` unless the run's own archetype already injects an
   incident (reusing, not duplicating, the existing fault/incident
   injection in `phase1_simulator.faults`).
5. This generation is **seeded identically to the rest of the run** (the
   same `make_rng(seed)` convention already used in `scenario.py`), so a
   staffing roster is reproducible per seed, exactly like every other
   Phase 1 quantity — not a second, uncontrolled source of randomness.

**No code implements this today.** This is the schema and generation
method a future `phase1_simulator.staffing` module (name illustrative)
would need to provide before any rotation evaluation could run even at
smoke scale.

---

## 3. The candidate algorithm — deterministic, non-learning, constraint-respecting (task 2)

**Name (illustrative, not binding):** Constrained Greedy Dose-Threshold
Rotation (CGDTR). Deterministic given its inputs and fixed parameters —
no randomness beyond the already-seeded scenario, no learned weights, no
training data, consistent with the explicit "deterministic, non-learning"
requirement.

**Decision points:** evaluated only at **procedure boundaries** (§4) —
never mid-procedure — once per boundary, per room.

**Inputs at each decision point** for a room `R` currently staffed by
worker `W`:
- `W`'s cumulative dose so far this shift (existing dose-accumulation
  rule, `ICAIRE_Simulation_Validation_Methodology.md` §1).
- `W`'s **projected** dose, using the engine's own existing
  constant-rate-held convention (*"current rate held constant for 30
  minutes"*, §1; **not** `linearForecast` — deliberately decoupled from
  Phase 3A's forecaster, see §3f below) over the lesser of 30 minutes or
  the room's remaining occupied time.
- The full `WorkerProfile` roster and each worker's current
  `incident_state`, `availability_windows`, and rotation count so far.
- `R`'s own `incident_state` (open/clear) if the engine's incident
  concept is room-scoped at that moment.

### 3a. Trigger condition — dose-trigger mathematics, precisely specified (Revision 2; supersedes Revision 1's version below, addresses Issue 3)

**All dose comparisons in this subsection are normalized to mSv before
being compared to any threshold.** A dose *rate* (µSv/h) is never
compared directly against an mSv threshold — it is first converted via
the existing rule `Dose (mSv) = Rate (µSv/h) × Duration (h) / 1000`
(`ICAIRE_Simulation_Validation_Methodology.md` §1), applied over the
exact horizon defined below.

**Two distinct dose quantities, not to be confused with each other
(Revision 1 used "projected dose" for both without distinguishing
them):**
- **Additional projected dose** `ΔD_proj(W, t)`: the *increment* `W` is
  projected to accrue over the horizon `H(t)` defined below, computed
  from `W`'s own last valid, non-stale observed dose rate (see the
  input-validity rule below) held constant over that horizon — reusing
  the engine's own existing "current rate held constant" convention
  (§1's "projected task dose"), not a new projection method. In mSv:
  `ΔD_proj(W, t) = rate_last_valid_uSv_h(W) × H(t)_hours / 1000`.
- **Projected cumulative dose** `D_cum_proj(W, t)`: `W`'s *already-
  accrued* cumulative dose through `t` (the existing, unprojected
  running total, §1) **plus** `ΔD_proj(W, t)`. This is the quantity
  actually compared against the engine's own `CONFIG.doseElevated`/
  `doseCritical` thresholds (rows 14/15) — those thresholds are
  themselves defined in the registry as projected-dose-*over-a-horizon*
  thresholds (row 15: "elevated projected dose ≥ 0.15 mSv ... over a
  fixed 30-minute horizon"), i.e. they are projected-*cumulative*, not
  increment-only, thresholds. Comparing the increment alone against them
  would be a unit/definition mismatch, not merely a stricter or looser
  check.

**Time horizon `H(t)`, defined exactly:** `H(t) = min(30 minutes,
remaining scheduled minutes of the upcoming AssignmentSlot that W would
continue into if not rotated)` — reusing the engine's own 30-minute
convention (§1) as the cap, and the upcoming slot's own scheduled
remaining duration (§2b) as the other bound, rather than either value
alone. If `H(t) = 0` (no upcoming slot — e.g., this boundary is the
shift's last), no projected-dose trigger clause applies at this decision
point; only the already-accrued clause below can fire.

**Trigger condition (Revision 2), propose a rotation for `W` out of `R`
if and only if:**
- `W`'s **already-accrued** cumulative dose through `t` (no projection
  involved) ≥ `rotation_threshold_fraction × reference_level`
  (mSv-normalized; mechanizing `ROTATION_RECOMMENDER_DESIGN_SPEC.md`
  §4.3's reference rule exactly — `rotation_threshold_fraction` is an
  open parameter, §9d), **or**
- `W`'s **projected cumulative dose** `D_cum_proj(W, t)` (as defined
  above, mSv-normalized, over horizon `H(t)`) crosses `CONFIG.doseElevated`
  or `doseCritical` (registry row 15, reused as-is, not a new threshold).

If neither holds, the algorithm's output at this decision point is **no
rotation**, by design, not by exception-handling (§4's "ordinary case").

**Input-validity rule (new in Revision 2, closes a gap Revision 1 did
not specify):** `rate_last_valid_uSv_h(W)` must be a reading that passes
the engine's own `SimLab.pure.validReading` check **and** is not
currently `STALE`, `DISCONNECTED`, `SUSPECTED_FROZEN`, or otherwise in
the engine's own `UNAVAIL` set (`AlaradSafety.SENSOR_P`, registry row
19) at decision time `t`. **If `W`'s most recent reading fails this
check, the projected-cumulative-dose trigger clause above is evaluated
as *not met* for this decision point** — a stale or invalid reading is
never substituted into the projection as if it were current, and the
trigger does not silently fall back to an older, possibly-stale value
either. (The already-accrued clause is unaffected, since it uses the
existing running total, not a live reading.) This is a deliberate
fail-safe default, not an oversight: see §3h for what happens when a
dose concern independently persists through a period of sensor
invalidity — that is an escalation question, not a trigger-math
question, and the two must not be conflated.

**Explicit caveat, restated here because this subsection is where a
reader is most likely to misread it:** `CONFIG.doseElevated`/
`doseCritical` (registry row 15) are **self-disclosed PROTOTYPE,
illustrative thresholds — not regulatory dose limits**
(`ICAIRE_Simulation_Validation_Methodology.md` §9 row 15's own text).
Crossing them triggers a *rotation proposal* in this design, nothing
more; it must never be reported or read as "the worker exceeded a
regulatory dose limit."

**Revision 1's original §3a (superseded by the above, kept here for
traceability):**
> Propose a rotation for `W` out of `R` **if and only if**:
> - `W`'s cumulative dose so far ≥ `rotation_threshold_fraction ×
>   reference_level` (mechanizing `ROTATION_RECOMMENDER_DESIGN_SPEC.md`
>   §4.3's reference rule exactly — `rotation_threshold_fraction` is an
>   open parameter, §10), **or**
> - `W`'s projected dose (as defined above) crosses the engine's own
>   `CONFIG.doseElevated` or `doseCritical` threshold (registry row 15,
>   reused as-is, not a new threshold).
>
> If neither holds, the algorithm's output at this decision point is
> **no rotation**, by design, not by exception-handling (§4's "ordinary
> case").

### 3b. Eligibility filter (reuses design-spec §2.1 exactly)

From the full roster, build the candidate set of workers who are: (a)
credentialed for `R`'s room **and** current `procedure_class`, (b) not
already at or within a declared margin of their own
`max_dose_per_shift_mSv`, (c) `incident_state == "clear"`, (d) within an
`availability_window` covering the decision point, and (e) not within
`min_rest_between_assignments_minutes` of their last rotation-out.
**(a)–(e) are unchanged from Revision 1.**

**New in Revision 2 (addresses Issue 2 — exclusive assignments), added
to the same candidate-set filter:** (f) currently `state == "FREE"`
(§2a) — not `ASSIGNED` to another occupied slot, not `RESERVED` for
another room's pending rotation, and not `RESTING`; and (g) projected to
remain `FREE`-eligible through the **entire** prospective handoff-and-
assignment interval `[t, T_effective]` (§3d), not merely free at the
instant of selection — enforced by the conservative, batch-level
procedure in §3g, which also resolves what happens when two rooms'
candidate sets overlap at the same decision point.

### 3c. Selection rule (deterministic tie-breaking, stated exactly)

Rank the candidate set by **ascending current cumulative dose**; ties
broken by **ascending `worker_id`** (a fixed, arbitrary, but fully
deterministic rule — not a heuristic choice presented as meaningful).
Select the first-ranked candidate whose selection would **not** cause
their `max_rotations_per_shift` count, or the roster's own rotation-burden
fairness bound (`ROTATION_RECOMMENDER_DESIGN_SPEC.md` §2.4), to be
exceeded. If every candidate fails this check, output is **no rotation**
(§4, case 5).

### 3d. Procedure-continuity, handoff timing, and swap-effective-time — explicit event timeline (Revision 2; supersedes Revision 1's version below, addresses Issue 1)

Revision 1 specified that a swap becomes `PENDING` at a decision
boundary and `COMPLETED` once `min_handoff_duration_minutes` elapses,
but did not specify what happens if that elapsed time runs past the
*next* procedure boundary — which could let the actual worker-for-worker
swap take effect in the middle of the next procedure, violating the
procedure-continuity constraint (`ROTATION_RECOMMENDER_DESIGN_SPEC.md`
§2.2) that a swap may only take effect *at* a boundary. Revision 2
closes this gap with an explicit timeline:

```
T_decide    = the procedure boundary B_k at which the trigger (§3a) fires
              and PROPOSED -> PENDING.
T_ready     = T_decide + min_handoff_duration_minutes
              (earliest the handoff COULD be physically done)
T_effective = the smallest scheduled procedure boundary B_j (j >= k) such
              that B_j >= T_ready -- i.e. the next boundary at or after
              T_ready, NEVER an arbitrary mid-procedure minute.
```

The swap executes **atomically at `T_effective`, and only at
`T_effective`**: the outgoing worker `W` occupies and accrues dose
normally through the last minute before `T_effective`; the incoming
worker occupies and accrues from `T_effective` onward. **`T_effective`
is, by construction, always a procedure boundary — the swap can never
take effect mid-procedure.**

**The one sanctioned exception:** an explicit, RSO-reviewed emergency-
override flag (`ROTATION_RECOMMENDER_DESIGN_SPEC.md` §2.2) may set
`T_effective = t` immediately, bypassing boundary alignment — this is
the *only* path by which a swap may take effect mid-procedure, must be
logged as an override (not an ordinary completion), and remains subject
to RSO review per the existing constraint; **nothing in this design
grants the algorithm itself authority to invoke this exception** (see
§3h).

**Shift-end boundary (new in Revision 2, addressing the "Also" item on
shift-end boundaries):** the scheduled shift end (`shift_minutes`) is
itself always treated as a procedure boundary `B_last`, whether or not a
procedure happens to end exactly there. If `T_ready > B_last` (not
enough boundaries remain before shift end for the handoff to complete),
the rotation is **infeasible** — this is Revision 1's §4 case 6, now
precisely defined as "no `B_j ≥ T_ready` exists with `B_j ≤ B_last`,"
rather than left as an informal "not enough time" check.

**Interrupted handoffs (new in Revision 2, addressing the "Also" item):**
if, at any point in `[T_decide, T_effective)`, the incoming worker's
eligibility (§3b) changes (e.g., their `incident_state` opens, or a
conflicting reservation claims them first per §3g), the rotation
transitions `PENDING → ABORTED` (§8), the reservation is released,
`T_effective` is discarded, and `W` continues in `R` unchanged —
**never** a partial or forced swap. The trigger (§3a) is re-evaluated
fresh at the next boundary from then-current state, exactly as an
ordinary non-triggered boundary would be.

The outgoing worker `W` continues to accrue dose normally throughout
`[T_decide, T_effective)` — a handoff is not modeled as removing `W`
from the room before the replacement is actually in place, consistent
with "a rotation is never instantaneous"
(`ROTATION_RECOMMENDER_DESIGN_SPEC.md` §2.3) — this part of Revision 1's
intent is preserved, only the completion timing is corrected.

**Revision 1's original §3d (superseded by the above, kept here for
traceability):**
> The proposed swap is queued, not executed immediately: it becomes
> `PENDING` at the decision point and `COMPLETED` only after
> `min_handoff_duration_minutes` (registry row 9, still open) elapses
> with no disqualifying event (§8's state machine). The outgoing worker
> `W` continues to accrue dose normally during the `PENDING` window — a
> handoff is not modeled as removing `W` from the room before the
> replacement is actually in place, consistent with "a rotation is
> never instantaneous" (`ROTATION_RECOMMENDER_DESIGN_SPEC.md` §2.3).

### 3e. Incident acknowledgement

If `R`'s `incident_state` becomes (or already is) `"open"` at or during
the `PENDING` window, the swap is **held** (not cancelled outright) until
an explicit RSO-acknowledgement flag is set for that incident — reusing
the S8 "an incident stays open through disconnect, never silently
auto-closed" precedent, applied here to rotation specifically: a rotation
must not be allowed to silently close or sidestep an open incident
either (`ROTATION_RECOMMENDER_DESIGN_SPEC.md` §2.3, final clause).

### 3f. Why the trigger does not use `linearForecast`

Phase 3A found `linearForecast`'s skill score **negative** against
simple persistence at smoke scale (`PHASE3A_SMOKE_TEST_REPORT.md` §3;
explicitly preliminary, not statistically established). Triggering a
safety-relevant rotation decision on a forecaster with an unresolved,
possibly-negative skill score would import that unresolved uncertainty
directly into the rotation evaluation. CGDTR's trigger (§3a) therefore
uses only the engine's own existing, already-registered constant-rate
projection and threshold convention (rows 14/15), not `linearForecast` —
a deliberate design choice, not an oversight, and one a future candidate
design could revisit once Phase 3A's forecasting-readiness checklist
items are resolved (`PHASE3A_FORECASTING_READINESS_CHECKLIST.md` §2).

### 3g. Atomic reservation and simultaneous-request conflict resolution (new in Revision 2, addresses Issue 2)

**The gap Revision 1 did not specify:** if two rooms both trigger a
rotation at the *same* boundary `B_k`, and their ranked candidate lists
(§3c) both put the *same* worker first, nothing in Revision 1 prevented
both rooms from independently "selecting" that worker — an exclusivity
violation (the same worker reserved, or assigned, to two slots at once).

**Resolution — a single deterministic batch pass per boundary, not two
independent selections racing each other:**

1. At boundary `B_k`, collect **every** room whose trigger (§3a) fires
   at this boundary into one batch — evaluated against one consistent
   snapshot of roster state (every worker's dose, `state`,
   `incident_state` as of the instant `B_k` begins).
2. Process the rooms in the batch in a **fixed, deterministic order**:
   ascending room name (an arbitrary but fully deterministic tie-break,
   exactly as `worker_id` ties are broken in §3c — not a priority
   judgment about which room matters more).
3. For each room in that order: build its ranked eligible-candidate
   list (§3b/§3c) **excluding any worker already marked `RESERVED`
   earlier in this same batch pass**; select the first-ranked still-
   `FREE` candidate; immediately set that candidate's `state =
   RESERVED` (for this room's pending rotation) **before** moving to
   the next room in the batch.
4. If a room's candidate list is exhausted (every remaining candidate
   already `RESERVED` by an earlier room in this batch, or otherwise
   ineligible), that room's rotation is **infeasible at this boundary**
   (§4 case 3/4) — not an error, and not retried within the same batch;
   it may re-trigger fresh at the next boundary.
5. A worker's `RESERVED` state persists until their reserving rotation
   reaches `COMPLETED` (state becomes `ASSIGNED` to the new slot) or
   `ABORTED`/never-reached-`T_effective` (state releases back to
   `FREE`, or to `RESTING` if `min_rest_between_assignments_minutes`
   applies from their *previous* rotation-out, whichever is more
   restrictive).
6. **Forward-looking eligibility (closes the "unavailable during the
   entire handoff and assignment interval" requirement):** because
   `T_effective` (§3d) can be later than `T_decide`, a candidate's
   eligibility must hold not just at selection time but through the
   full `[T_decide, T_effective]` interval and into their prospective
   occupancy of the new slot. This is enforced conservatively: a
   candidate already `RESERVED` elsewhere, or whose own
   `availability_window` does not cover `[T_decide, T_effective]` in
   full, or who would reach `min_rest_between_assignments_minutes`'s
   boundary mid-interval, is excluded from the candidate list at step 3
   — not merely deprioritized.

**No two rooms can ever reserve the same worker in the same batch**, by
construction of step 3's immediate `RESERVED` marking — this is a
property of the batch algorithm, not an assumption to be separately
verified at runtime, though §9a adds a test that checks it directly
anyway (never trust a structural argument alone, per this project's own
established discipline of checking rather than asserting).

### 3h. Safe failure and escalation when a dose concern persists but no rotation is possible (new in Revision 2, addresses Issue 5)

**The gap Revision 1 did not specify:** §4's cases 3/4 ("no eligible
candidate" / "every candidate breaches a bound") were logged as
`INFEASIBLE` and left there. If the underlying dose concern that caused
the trigger (§3a) is still true at the *next* boundary, Revision 1 had
no mechanism to distinguish "this keeps happening and nobody has looked
at it" from an ordinary, resolved one-off infeasibility.

**Escalation state (new, tracked per worker-room pair, independent of
the rotation `PROPOSED`/`PENDING`/etc. states in §8):**

```
NONE --(trigger fires AND rotation is infeasible/aborted at this
         boundary, Sec 4 cases 3/4/7)--------------------------> RAISED
RAISED --(still triggered AND still infeasible at the next boundary,
          unacknowledged)----------------------------------------> RAISED
          (re-raised, not silently cleared)
RAISED --(an explicit, simulated RSO-acknowledgement flag is set)--> ACKNOWLEDGED
ACKNOWLEDGED --(a feasible rotation subsequently becomes available and
               COMPLETEs, OR the trigger condition itself stops holding,
               OR shift ends)------------------------------------> RESOLVED
RAISED --(shift ends while still unacknowledged)------------------> RESOLVED
          (logged as "unacknowledged at shift end" -- a distinct,
          flagged outcome, not treated the same as an acknowledged
          resolution)
```

**What `RAISED` does, and explicitly does not do:**
- **Does:** generate an audit-log entry (timestamp, `worker_id`, `room`,
  both dose quantities from §3a in mSv, the specific infeasibility
  reason from §4, and the escalation state) and a simulated RSO-
  notification event (a logged event in this research framework — **not
  a real paging/alerting integration**, which is out of scope for this
  design). Re-raises at every subsequent boundary the condition
  persists, so a long-unacknowledged concern is visible in the audit
  trail, never silently dropped.
- **Does not:** relax any eligibility, duty-limit, or rotation-burden
  constraint (§3b/§3c) to force a rotation through; invoke the
  emergency-override exception (§3d) on its own authority — that
  remains an RSO-initiated action per the existing constraint
  (`ROTATION_RECOMMENDER_DESIGN_SPEC.md` §2.2); or claim to have
  "handled," "resolved," or "mitigated" the underlying radiation-safety
  concern by raising it. **Final decision authority for what to do
  about a persistent, no-feasible-rotation dose concern rests with the
  RSO/human operator, never with this algorithm** — this design's sole
  responsibility in this situation is accurate, persistent detection and
  logging, stated explicitly so a future reader cannot read
  `RAISED`→`ACKNOWLEDGED` as the software having independently resolved
  anything.

**Audit log fields (minimum set):** `timestamp`, `worker_id`, `room`,
`already_accrued_dose_mSv`, `projected_cumulative_dose_mSv`,
`horizon_minutes` (§3a's `H(t)`), `infeasibility_reason` (§4's case
number), `escalation_state`, `acknowledged_by` (placeholder field;
simulated in this research framework, not a real identity system),
`resolution_reason`.

---

## 4. Procedure boundaries, handoff duration, incident acknowledgement, and the "no rotation" conditions (task 4)

- **Procedure boundary:** the end of a `AssignmentSlot`'s declared
  `procedure_class` occupancy of a room (§2b), or an explicit
  emergency-override flag subject to RSO review
  (`ROTATION_RECOMMENDER_DESIGN_SPEC.md` §2.2) — the *only* times a
  rotation may take effect. A boundary is a property of the slot
  schedule, not of the candidate algorithm's own choosing.
- **Handoff duration:** `min_handoff_duration_minutes`, registry row 9,
  still open — the minimum time between a `PENDING` rotation and its
  `COMPLETED` state (§3d, §8).
- **Incident acknowledgement:** an explicit boolean flag, set only by an
  (simulated, for now) RSO action, required before a `PENDING` rotation
  touching a room with `incident_state == "open"` may reach `COMPLETED`
  (§3e).
- **The algorithm must recommend no rotation when:**
  1. The trigger condition (§3a) is not met — the ordinary case, not an
     exception.
  2. The decision point is mid-procedure, not at a boundary — the
     recommendation is deferred to the next boundary, not cancelled
     (re-evaluated there from scratch against then-current state).
  3. No eligible candidate exists (§3b) — logged as **infeasible**, not
     a crash or a silent no-op (§8).
  4. Every eligible candidate would exceed a rotation-burden or
     duty-limit bound (§3c) — logged as **infeasible**, distinct reason
     code from (3).
  5. The room (or the outgoing/incoming worker) has `incident_state ==
     "open"` without an acknowledgement flag — held, not cancelled
     (§3e, §8).
  6. Remaining shift time is shorter than `min_handoff_duration_minutes`
     — a rotation cannot be safely completed before shift end, so none
     is proposed for that boundary.

**Revision 2 refinement (does not contradict the list above; makes case
6 precise and adds case 7):** case 6's "remaining shift time shorter
than handoff duration" is now defined exactly via §3d's `T_ready`/
`B_last` test — infeasible if no boundary `B_j` with `B_j ≥ T_ready`
exists at or before shift end. **Case 7 (new):** an interrupted handoff
(§3d) that transitions `PENDING → ABORTED` before reaching `T_effective`
also results in no rotation at this boundary — distinct from case 3/4
(never attempted) because this one *was* attempted and correctly
stopped (§8b's `ABORTED` category).

---

## 5. Counterfactual dose-outcome computation method (task 5)

**The core architectural requirement, stated once, precisely:** to
compare rotation policies on *identical underlying exposure*, the
per-minute radiation exposure *rate* at a given room/procedure/minute
must be generated **independently of which worker is assigned there** —
only then can the same exposure be "replayed" under different
assignment policies and attributed to different workers, which is what a
counterfactual comparison requires.

### 5a. Two-layer generative model (new; today's `phase1_simulator` only has layer 1 tied to a fixed worker for the whole run)

1. **Exposure layer (unchanged mechanism, reorganized unit):** for each
   `AssignmentSlot` (room, procedure_class, start/end minute), generate
   the per-minute dose-rate series using the **existing, unmodified**
   room-baseline/procedure-multiplier/noise/area-model mechanism
   (`ICAIRE_Simulation_Validation_Methodology.md` §2's "what does not
   change" clause, reused exactly) — but keyed to the **slot**, not to a
   worker. This series is fixed once generated, for a given seed, and is
   never regenerated per rotation policy.
2. **Assignment layer (new):** a rotation policy `P` (one of the four
   baselines/candidate, §6) determines, independently for each minute,
   which `worker_id` occupies each slot — `assigned_worker_id(slot, t)`.
   This is the **only** thing that differs between policies run on the
   same seed.
3. **Attribution:** each worker's realized per-minute dose rate is the
   exposure-layer value of whichever slot they are assigned to at that
   minute (0 if assigned to none at that minute); cumulative dose per
   worker is the existing running-sum rule (§1) applied to that
   attributed series.

### 5b. Paired-seed comparison across policies (reuses, does not redefine, §7's existing convention)

For a given seed, generate the exposure layer **once**. Run every policy
being compared (no-rotation, fixed-interval, reference-rule, candidate —
§6) against that **same** exposure layer, varying only the assignment
layer. This is the same paired-design principle
`ICAIRE_Simulation_Validation_Methodology.md` §7 already uses for
detector/forecaster-vs-baseline comparisons (same seeds, paired
statistical test) — applied here to rotation policies instead of
detectors, not a new statistical convention invented for this document.

### 5c. What this requires that does not exist today

Per §1's finding: `phase1_simulator.scenario.WorkerSpec` currently fuses
the exposure layer and the assignment layer into one object for the
whole run. Separating them as §5a requires a new generation path (e.g.,
a `phase1_simulator.rotation_sim` module, name illustrative) that:
reuses the existing per-minute rate-generation functions
(`patterns.py`/`area_model.py`/the seeded-noise mechanism) at the slot
level instead of the worker level, and adds the assignment-layer
bookkeeping on top. **This module is specified here, not built** — per
this round's restriction, no existing simulator or forecasting code is
changed, and this new module is not written either.

---

## 6. The candidate algorithm and three baseline policies, in implementable detail (task 8)

All four operate on the same §5a two-layer input (an exposure layer plus
a starting assignment) and produce an assignment layer as output.

1. **No-rotation baseline** (`ROTATION_RECOMMENDER_DESIGN_SPEC.md` §4.1):
   `assigned_worker_id(slot, t)` = the slot's originally-scheduled worker,
   for all `t` — no decision procedure at all.
2. **Fixed-interval baseline** (§4.2): at every boundary that falls on a
   multiple of a fixed interval `N` minutes (open parameter, §10), rotate
   the currently-highest-cumulative-dose eligible worker out, replaced by
   the eligible candidate with the lowest cumulative dose (same
   eligibility filter as §3b, reused exactly, not a separately-defined
   one) — otherwise identical mechanics to §3d/§3e (handoff duration,
   incident acknowledgement apply equally to every policy, not only the
   candidate).
3. **Reference-rule baseline** (§4.3, `ROTATION_RECOMMENDER_DESIGN_SPEC.md`
   §6a reused): rotate out whenever projected cumulative dose crosses a
   declared fraction of the reference level — i.e., CGDTR's §3a trigger
   **without** CGDTR's §3c lowest-dose selection rule; replacement
   selection for this baseline is the first eligible candidate in
   roster order (deliberately simpler than CGDTR's ranking, to isolate
   what CGDTR's ranking step itself contributes).
4. **Candidate (CGDTR, §3):** trigger (§3a) + eligibility (§3b) +
   ranked selection (§3c) + handoff/incident mechanics (§3d/§3e), as
   specified above.

**Revision 1's "all four share identically" guarantee (superseded by
the extended version below, kept here for traceability):**
> All four share identically: the eligibility filter (§3b), the handoff
> state machine (§8), and the incident-acknowledgement rule (§3e) — so
> that any measured difference between policies reflects the
> *trigger-and-selection* logic being compared, not an inconsistency in
> how constraints are enforced across policies.

### 6a. Revision 2 addition — explicit ablation design (addresses Issue 4)

Revision 1's three baselines happened to already vary the candidate's
two independent design choices — the **trigger rule** (dose-threshold,
§3a, vs. fixed wall-clock interval, item 2 above) and the **replacement-
selection rule** (lowest-current-dose ranking, §3c, vs. first-eligible-
in-roster-order, item 3 above) — but did not make this a deliberate,
complete design, and left one combination unexamined. Revision 2 makes
this explicit as a 2×2 ablation:

| | Selection = lowest-dose-ranked (§3c) | Selection = first-eligible-in-roster-order (item 3) |
|---|---|---|
| **Trigger = dose-threshold (§3a)** | Candidate (CGDTR, §3) | Reference-rule baseline (item 3, unchanged) |
| **Trigger = fixed-interval (item 2)** | Fixed-interval baseline (item 2, unchanged) | **Ablation D (new in Revision 2)** |

**Ablation D — fixed-interval trigger, first-eligible-in-roster-order
selection:** rotate at the same fixed interval `N` as the fixed-interval
baseline (item 2), but replace using the first eligible candidate in
roster order (item 3's selection rule) rather than the lowest-dose-
ranked one. **This policy is not proposed as a plausible real-world
baseline** — unlike the other three, no facility would plausibly adopt
"rotate on a timer, then pick whoever's first alphabetically" — its sole
purpose is completing the 2×2 so that the trigger-rule's effect and the
selection-rule's effect can each be estimated as a **paired difference,
held on the same seeds** (§5b):
`selection-effect ≈ average of [(Candidate − Reference-rule), (Fixed-interval − Ablation D)]`;
`trigger-effect ≈ average of [(Candidate − Fixed-interval), (Reference-rule − Ablation D)]`.
Reported alongside, not instead of, the four policies' own individual
scores (§9b).

### 6b. Shared-conditions guarantee, elevated and made explicit (Revision 2; extends, not contradicts, Revision 1's version above)

All **five** policies now being compared (no-rotation, fixed-interval,
reference-rule, Ablation D, candidate) share, identically: the
eligibility filter (§3b, including the Revision 2 exclusivity
additions), the handoff timeline and state machine (§3d, §8), the
incident-acknowledgement rule (§3e), the escalation mechanism (§3h),
and — per §5b — the exposure layer and staffing roster for a given
seed. **Only the trigger-and-selection logic differs between policies
being compared.** This is checked directly by
`test_all_four_policies_share_identical_eligibility_and_handoff_checks`,
extended in Revision 2 to cover all five (§9a).

---

## 7. Dose-accounting definitions, and the non-redistribution requirement (tasks 6–7)

### 7a. Four distinct quantities — never to be collapsed into one number

1. **Individual cumulative dose** `D_i(t)`: worker `i`'s own running
   total, per the existing §1 rule. Already well-defined; not new.
2. **Maximum individual dose** `max_i D_i(T)` at shift end `T` (and, per
   `ROTATION_RECOMMENDER_DESIGN_SPEC.md` §2.4, sampled at multiple points
   across the shift, not only at `T`). This is the quantity a rotation
   policy *directly* targets — moving the highest-dose worker's further
   accumulation onto someone else.
3. **Collective dose** `Σ_i D_i(T)` — the sum across the *entire* roster
   present in the run, not just the workers who were rotated. Stated
   explicitly as a **simplified, project-internal quantity**: this is
   not the formal ICRP collective-effective-dose concept (which involves
   a defined population and reporting period) — the term is used here
   only for "total dose summed across this run's roster," and must not
   be cited as if it were the regulatory quantity.
4. **Dose distribution / workload fairness**: the variance,
   trajectory-sampled, and rotation-burden measures already specified in
   `ROTATION_RECOMMENDER_DESIGN_SPEC.md` §2.4 and §5 — a *shape*
   (how dose is spread across the roster), not a magnitude.

**These four answer different questions and must be reported as four
separate numbers in any future result, never blended into one
"improvement" figure.**

### 7b. The invariant this document is built to make visible

Under the two-layer model (§5a), the exposure layer is **fixed per
seed**, independent of policy. A room/procedure slot's total dose over
its occupied span is a property of *that slot's physics* (room baseline,
procedure multiplier, noise draw, duration) — **not** of who is assigned
to receive it. Consequently, under the simplest version of this model
(every slot-minute is attributed to exactly one worker, with no
dose-free "vacancy" and no change to total occupied time):

> **Collective dose (§7a.3) is invariant across rotation policies that
> do not change total occupied time.** Rotation changes *who* accrues
> which share (§7a.1, §7a.2, §7a.4) — it does not, by itself, change
> *how much* dose the exposure layer produces in total.

This is stated as a **modeling consequence to check for, not a claim
already demonstrated by any run** — per this round's restriction, no
simulation has been executed to confirm it numerically. It follows from
the two-layer model's own construction (§5a), and gives the evaluation a
concrete, falsifiable expectation to test against once implemented
(§9's proposed unit tests), rather than leaving "did this just move dose
around?" as a question nobody checks.

**The two legitimate mechanisms by which collective dose *could*
genuinely change**, named explicitly so they are not confused with
redistribution:
- **Handoff dead-time**, if the model is extended so a room is briefly
  unoccupied (and therefore not accruing worker dose) during a `PENDING`
  handoff — this document's §5a/§3d does **not** include that extension
  (the outgoing worker continues occupying, and accruing, through the
  handoff window); if a future design adds dead-time, it must be modeled
  as its own explicit mechanism, not an accidental side effect of
  rotation bookkeeping.
- **Avoided extension of occupied time**, if a well-timed rotation
  prevents an incident-driven delay that would otherwise have extended a
  slot's total occupied span — again not modeled by this document's
  baseline mechanics, and would need its own explicit specification if
  pursued later.

**Rechecked for Revision 2 (addresses the "Also" item asking this
invariant be rechecked):** none of Revision 2's additions introduce
dead-time or change total occupied time. `T_effective` (§3d) always
lands exactly on a scheduled boundary with zero gap — the outgoing
worker occupies through the last minute before `T_effective`, the
incoming worker from `T_effective` onward, with no unoccupied minute
between them; the `RESERVED` state (§3g) is a scheduling lock with no
exposure consequence of its own; and the escalation mechanism (§3h)
only logs and notifies — it does not change who occupies a slot or for
how long. **The invariant above therefore still holds under Revision
2's refined timing and exclusivity rules, by the same construction
argument as before** — restated, not newly demonstrated, since (per
this round's restriction, unchanged from Revision 1) no simulation has
been run to confirm it numerically for either revision.

### 7c. The required reporting discipline (satisfies task 7 directly)

Any future evaluation report comparing rotation policies **must**:
1. Report collective dose (§7a.3) as its own line, explicitly labeled,
   for every policy compared.
2. Report it alongside maximum individual dose and the fairness measures
   (§7a.2, §7a.4) — never substitute one for another.
3. **Treat any observed collective-dose difference between policies as a
   finding requiring explanation**, not as an expected benefit of
   rotation — per §7b, the default expectation is invariance; a
   measured difference should be traced to a specific mechanism (§7b's
   two legitimate ones, a modeling bug, or a genuine and newly-specified
   model extension) before being reported, rather than reported as "the
   algorithm reduced exposure."
4. Never report a reduction in maximum individual dose or an
   improvement in fairness as if it were, by itself, "a reduction in
   collective exposure" — these are different quantities (§7a), and a
   future draft must not use language that lets a reader conflate them.

---

## 8. Constraint violations, infeasible recommendations, and uncompleted handoffs (task 9)

### 8a. State machine (applies identically to all four policies, §6)

```
PROPOSED --(fails §3b eligibility, or §3c burden/duty check)--> INFEASIBLE (logged, no-op)
PROPOSED --(passes checks)--> PENDING
PENDING --(handoff duration elapses, no disqualifying event)--> COMPLETED
PENDING --(incident opens without acknowledgement, §3e)------> HELD
HELD --(acknowledgement flag set)-------------------------> PENDING (resumes countdown)
HELD --(shift ends before acknowledgement)-----------------> ABORTED (logged)
PENDING --(an eligibility condition changes mid-handoff,
           e.g. the incoming worker's incident_state opens)-> ABORTED (logged, re-evaluate at next boundary)
```

### 8a-ext. State machine extensions (new in Revision 2; extends, does not contradict, §8a above)

Revision 1's diagram above remains correct as far as it goes; Revision
2 adds the worker-exclusivity state (§3g) and the escalation state
(§3h), which interact with it as follows:

```
(worker) FREE --(selected as replacement in a batch pass, Sec 3g)--> RESERVED
RESERVED --(reserving rotation reaches COMPLETED)----------------> ASSIGNED (to the new slot)
RESERVED --(reserving rotation ABORTED or never reaches
            T_effective)-------------------------------------------> FREE, or RESTING if min_rest applies
ASSIGNED --(rotated out, reservation cycle ends)-------------------> RESTING
RESTING --(min_rest_between_assignments_minutes elapses)----------> FREE

(escalation, per worker-room pair)
NONE --(trigger fires AND infeasible/aborted, Sec 4 cases 3/4/7)----> RAISED
RAISED --(still triggered and infeasible at next boundary,
          unacknowledged)-------------------------------------------> RAISED
RAISED --(RSO-acknowledgement flag set)------------------------------> ACKNOWLEDGED
ACKNOWLEDGED --(feasible rotation COMPLETEs, or trigger stops
                holding, or shift ends)------------------------------> RESOLVED
RAISED --(shift ends, unacknowledged)---------------------------------> RESOLVED
          (flagged "unacknowledged at shift end")
```

**Interaction rule:** the rotation state machine (§8a) and the worker-
exclusivity state (§3g) are updated together, atomically, within the
same batch pass (§3g step 3) — a rotation never reaches `PENDING`
without its candidate simultaneously becoming `RESERVED` in the same
step, and never leaves `PENDING` (to `COMPLETED` or `ABORTED`) without
that worker's state being updated in the same step. They are specified
as two views of one consistent update, not two independently-timed
mechanisms that could drift out of sync.

### 8b. Distinguishing a violation from an infeasibility from an abort

- **Infeasible** (never attempted): the trigger fired but no valid
  candidate existed, or every candidate would breach a duty/burden bound
  (§4, cases 3–4). Not a defect — an expected outcome the evaluation must
  be able to observe and count, not hide.
- **Aborted** (attempted, then correctly stopped): a `PENDING` rotation
  that is correctly halted by §3e's incident-acknowledgement rule or by
  an eligibility condition changing before `COMPLETED`. Also not a
  defect — it is the constraint machinery working as specified.
- **Violation** (a defect, if it ever occurs): any rotation that reaches
  `COMPLETED` despite failing a §3b/§3d/§3e check at the moment of
  completion. Because all four policies share the same enforcement
  machinery (§6's closing paragraph), this should be **structurally
  impossible** by construction for a correct implementation — the
  violation-rate metric (§9's metrics, reusing
  `ROTATION_RECOMMENDER_DESIGN_SPEC.md` §3.5) exists specifically to
  catch an incorrect implementation that lets one through, not to score
  an inherently risky algorithm design.
- **Deferred** (not yet a terminal state): a mid-procedure trigger (§4,
  case 2) that is queued to the next boundary. Tracked separately from
  infeasible/aborted/violation so a long queue of repeatedly-deferred
  recommendations is itself visible, not silently absorbed.
- **Escalated** (new in Revision 2; a fifth category, tracked across
  boundaries per worker-room pair, not per individual rotation attempt)
  — see §3h. Distinct from the four above because it is not a property
  of one attempt, but of whether a *persisting* dose concern with no
  feasible rotation has been seen and acknowledged by a human.

Every terminal state (`INFEASIBLE`, `COMPLETED`, `HELD`→`ABORTED`,
`ABORTED`) must be logged with its reason code — none may be silently
dropped, consistent with every prior phase's "undefined/skipped is
reported, never silently treated as zero or success" discipline
(`metrics.py`'s existing `None`-not-crash convention, Phase 3A;
`test_edge_cases.py`'s zero-dose handling, same project).

---

## 9. Proposed unit tests, evaluation metrics, sensitivity analyses, and unresolved parameters (task 10)

### 9a. Proposed unit tests (named and described; none implemented)

- `test_trigger_fires_only_at_or_above_threshold` — §3a's boundary
  condition (just below vs. just at `rotation_threshold_fraction ×
  reference_level`).
- `test_no_eligible_candidate_yields_infeasible_not_crash` — §4 case 3,
  §8b.
- `test_tie_breaking_is_deterministic_by_worker_id` — §3c, run twice with
  identical tied input, confirm identical output both times.
- `test_rotation_never_takes_effect_mid_procedure` — §4 case 2; confirm a
  mid-procedure trigger is queued, not executed, and re-evaluated at the
  next boundary against then-current state (not the state at the
  original trigger time).
- `test_handoff_never_instantaneous` — §3d; confirm `PENDING` always
  persists for at least `min_handoff_duration_minutes` before
  `COMPLETED`.
- `test_open_incident_holds_rotation_until_acknowledged` — §3e, §8a's
  `HELD` transition.
- `test_rotation_burden_cap_enforced` — §3c; confirm a candidate at their
  `max_rotations_per_shift` cap is skipped in favor of the next-ranked
  eligible candidate, and that "no rotation" results if all are capped.
- `test_duty_limit_never_exceeded_by_a_completed_rotation` — confirms a
  `COMPLETED` rotation never assigns a worker already at/near
  `max_dose_per_shift_mSv` (the structural-impossibility claim in §8b,
  checked directly rather than assumed).
- `test_collective_dose_invariant_under_rotation_absent_dead_time` —
  directly tests §7b's invariant: run the no-rotation baseline and CGDTR
  on the same seeded exposure layer (§5b), with no handoff dead-time
  modeled, and confirm collective dose (§7a.3) is equal (within
  floating-point tolerance) between the two, while maximum individual
  dose and fairness measures differ. **This is the test that operationalizes
  task 7's restriction** — if it fails, either the implementation has a
  bug, or a dead-time/avoided-delay mechanism (§7b) was added without
  being explicitly specified, either of which must be resolved before
  any result is reported.
- `test_exposure_layer_identical_across_policies_same_seed` — §5a/§5b;
  confirm the slot-level exposure series itself (before assignment) is
  byte-identical regardless of which policy is run against it.
- `test_all_four_policies_share_identical_eligibility_and_handoff_checks` —
  §6's closing paragraph; confirm no policy has its own, looser
  constraint enforcement.

**New in Revision 2 (one group of tests per issue, named and described;
none implemented):**

- `test_swap_effective_time_always_lands_on_a_boundary` — §3d; for any
  `T_decide`/`min_handoff_duration_minutes` combination, confirm the
  computed `T_effective` is always a member of the slot's boundary set.
- `test_swap_never_executes_mid_procedure_without_override_flag` — §3d;
  confirm the atomic swap-application step rejects being asked to apply
  a swap at a non-boundary minute unless the emergency-override flag is
  set.
- `test_handoff_spanning_multiple_boundaries_lands_on_first_valid_one` —
  §3d; a case where `T_ready` falls between `B_k+1` and `B_k+2`, confirm
  `T_effective = B_k+2`, not `B_k+1`.
- `test_rotation_infeasible_when_no_boundary_remains_before_shift_end` —
  §3d/§4's refined case 6.
- `test_two_simultaneous_triggers_never_reserve_the_same_worker` — §3g;
  construct two rooms both ranking the same top candidate, confirm the
  deterministic batch resolution reserves them to different rooms or
  marks the second infeasible, never double-reserves.
- `test_batch_resolution_order_is_deterministic_by_room_name` — §3g step
  2; run twice on identical input, confirm identical outcome both times.
- `test_reserved_worker_excluded_from_other_candidate_lists` — §3g;
  confirm a `RESERVED` worker never appears as an eligible candidate for
  a different room's rotation until released.
- `test_candidate_forward_looking_eligibility_through_T_effective` —
  §3g step 6; a candidate whose availability window ends before
  `T_effective` must be excluded, not merely deprioritized.
- `test_trigger_distinguishes_additional_from_projected_cumulative_dose` —
  §3a; construct a case where the increment alone would (not) cross
  `doseElevated` but the projected-cumulative sum would (not), confirm
  the correct quantity drives the trigger.
- `test_stale_sensor_reading_never_used_as_trigger_input` — §3a's
  input-validity rule; confirm a `STALE`/`DISCONNECTED`/`INVALID` last
  reading causes the projected-cumulative-dose clause to evaluate as
  not-met, never substituted.
- `test_dose_values_normalized_to_mSv_before_threshold_comparison` —
  §3a; a unit-consistency check across both trigger clauses.
- `test_ablation_d_shares_identical_eligibility_handoff_and_escalation_mechanics` —
  §6b's shared-conditions guarantee, extended to five policies.
- `test_persistent_infeasible_dose_concern_escalates_and_reraises` —
  §3h; confirm `RAISED` persists and re-raises across boundaries until
  acknowledged or resolved, never silently cleared.
- `test_escalation_never_bypasses_eligibility_or_forces_a_rotation` —
  §3h; confirm no code path lets an `ACKNOWLEDGED` escalation itself
  relax §3b/§3c checks.
- `test_unacknowledged_escalation_at_shift_end_is_flagged_distinctly` —
  §3h's `RAISED → RESOLVED` ("unacknowledged at shift end") transition.
- `test_collective_dose_invariant_holds_under_revision_2_timing_and_reservation` —
  extends the Revision 1 invariant test (`test_collective_dose_invariant_under_rotation_absent_dead_time`
  above) to the new timeline/reservation mechanics (§7b's Revision 2
  recheck).

### 9b. Evaluation metrics (consolidates and extends
`ROTATION_RECOMMENDER_DESIGN_SPEC.md` §5; nothing below replaces that
section, it is restated together with the task-6/7 additions for one
place to read them)

- The five §3 scoring criteria (reused): dose reduction, fairness,
  latency, rotation count, constraint-violation rate.
- **Reported separately per task 6/7**, for every policy compared:
  individual cumulative dose (full distribution across the roster, not
  just a mean), maximum individual dose (end-of-shift and
  trajectory-sampled), collective dose, and the fairness measures
  (variance, trajectory-level, rotation-burden) — four distinct rows,
  never combined.
- **Infeasible-rate, held/aborted-rate, and deferred-rate** (§8b), each
  reported on its own, not folded into the violation rate.
- Paired comparison across all four policies on the same seeds (§5b),
  with the same statistical conventions already established
  (`ICAIRE_Simulation_Validation_Methodology.md` §7: Wilcoxon
  signed-rank, Holm–Bonferroni correction, run-level unit of
  independence per §7a).

**New in Revision 2:**
- With Ablation D added (§6a), the comparison family grows to **five**
  policies — the Holm–Bonferroni correction (above) must be applied
  across the larger family of pairwise comparisons this creates, not
  the four-policy family size Revision 1 implied; the trigger-effect and
  selection-effect paired differences (§6a) are additional comparisons
  within that same corrected family, not a separate, uncorrected
  analysis.
- **Escalation metrics** (§3h), each reported on its own, not folded
  into the violation/infeasible/aborted/deferred rates: rate of `RAISED`
  events per shift, rate of "unacknowledged at shift end" outcomes, and
  mean time from `RAISED` to `ACKNOWLEDGED` (acknowledgement latency).
- **Reservation-conflict rate** (§3g step 4): how often the batch
  resolution actually had to drop a room to infeasible because its
  candidates were already `RESERVED` elsewhere — a diagnostic metric for
  interpreting results (e.g., a large, broadly-credentialed roster should
  show this rarely binding; a short-staffed one should show it binding
  often, which could itself explain differences between policies rather
  than the trigger/selection logic being compared).

### 9c. Sensitivity analyses to run once implemented (none run now)

- `rotation_threshold_fraction` (§3a) swept across a declared range —
  does the candidate's advantage over the reference-rule baseline
  (which shares the same trigger) persist across the range, or is it an
  artifact of one chosen value?
- Fixed-interval baseline's own `N` (§6.2) swept — per
  `ROTATION_RECOMMENDER_DESIGN_SPEC.md` §5's existing requirement that
  this baseline's own parameter not be left as an unexamined constant.
- `min_handoff_duration_minutes` (registry row 9) swept — does a longer,
  more realistic handoff erode the candidate's measured advantage by
  increasing infeasible/aborted rates?
- Credential-breadth parameter (§2c step 2) swept — does the candidate's
  advantage shrink as eligible replacements become scarcer, which is the
  more realistic (short-staffed) regime?
- `max_rotations_per_shift` cap swept — does a tighter fairness-burden
  cap change which policy wins on the dose-reduction criterion?

**New in Revision 2:**
- Batch-processing tie-break order (§3g step 2: ascending room name)
  swept against an alternative fixed rule (e.g., descending outgoing-
  worker dose) — does this arbitrary tie-break materially affect
  results? If it does, that is itself a finding requiring disclosure,
  not something to be silently accepted as "arbitrary, so harmless."
- Roster size / credential-breadth interaction with the reservation-
  conflict rate (§9b) — extends the existing credential-breadth
  sensitivity item above to the new exclusivity mechanism specifically.

### 9d. New unresolved scientific parameters (not yet numbered registry rows; cross-referenced to existing rows, not silently merged into them)

None of the following have been added to
`ICAIRE_Simulation_Validation_Methodology.md` §9's numbered table in this
round — that document has not been edited here, per the instruction not
to silently change previously-approved methodology. They are listed here
so they are not lost, and would be the natural next additions to that
table in a future, explicitly-approved revision:

1. `rotation_threshold_fraction` (§3a) — related to, but more specific
   than, registry row 10's general "scoring weights/thresholds."
2. Credentialed-rooms/procedure-classes coverage-probability range (§2c
   step 2) — a new sub-parameter of registry row 8 (the eligibility
   model itself).
3. `max_dose_per_shift_mSv`, `min_rest_between_assignments_minutes`,
   `max_rotations_per_shift` illustrative ranges (§2a) — new
   sub-parameters of row 8.
4. Fixed-interval baseline's `N` (§6.2) — analogous in kind to row 9
   (handoff duration) but a distinct parameter belonging to a specific
   baseline, not the candidate.
5. Whether handoff dead-time or avoided-delay mechanisms (§7b) should
   ever be added to the model, and if so, with what parameters — a
   design question, not a value, in the same style as row 16's
   conceptual (not numeric) registry entry.

**Revision 2 note:** the five issues addressed by this revision are
structural/logical corrections (exact timing, exclusivity, input-
validity, ablation design, escalation handling), not new tunable
constants — **Revision 2 introduces no new numeric provisional
parameters** beyond the five already listed above from Revision 1. The
one Revision-2-specific question needing explicit sign-off, rather than
a value, is listed as a conceptual item in §10 below (the stale-input
fail-safe default).

### 9e. What is explicitly NOT claimed by this section

No test above has been run; no sensitivity analysis above has been
performed; no parameter above has a chosen value. §9a's tests are
proposed in enough detail to write directly against a future
implementation; nothing has been asserted about what any of them would
show. **This remains true for every Revision 2 addition**: no new test,
metric, or sensitivity analysis above has been run; the ablation design
and escalation mechanism are specified, not executed.

---

## 10. Items requiring Medical Physicist or RSO review (task 11)

Consolidating review items raised across this document, plus
restating (not replacing) the open rows already in
`SCIENTIFIC_PARAMETER_REVIEW_PACKAGE.md`:

- **Already registered and pending review** (unchanged by this
  document): registry rows 8 (eligibility/credentialing model), 9
  (handoff duration), 10 (scoring weights), 14/15/17/19/20 (all
  upstream of any dose/threshold calculation rotation would use).
- **New items this document's design surfaces, listed in §9d**:
  `rotation_threshold_fraction`'s value; credential-coverage
  realism; the three duty-limit/rest/rotation-cap values in §2a; the
  fixed-interval baseline's `N`.
- **Conceptual questions, not numeric values** (reusing row 16's
  "conceptual, not a value to approve" framing):
  1. Is the simplified "collective dose" definition in §7a.3 — a sum
     across this run's roster, explicitly not the formal ICRP
     collective-effective-dose concept — an appropriate proxy for this
     synthetic study, or does it risk being misread as the regulatory
     quantity regardless of the caveat?
  2. Is it clinically/operationally appropriate that CGDTR's trigger
     (§3f) deliberately avoids using `linearForecast` given its
     unresolved, currently-negative smoke-scale skill score — or should
     a rotation trigger be required to use the engine's existing
     forecaster regardless, once (if) that forecaster's accuracy
     question is resolved?
  3. Is the §7b invariant (collective dose unchanged by rotation absent
     an explicit dead-time/avoided-delay mechanism) itself a reasonable
     modeling assumption for how a real rotation would work, or does
     real-world rotation practice always involve enough handoff
     dead-time or procedural overhead that collective dose should be
     *expected* to change, making §7b's "default to invariant, explain
     any difference" framing miscalibrated?
  4. Is deferring (not cancelling) a mid-procedure trigger to the next
     boundary (§4 case 2) itself a safe default, or should a
     sufficiently severe trigger be allowed to interrupt a procedure
     under some circumstance this document does not specify?

### 10a. Revision 2 review items (new)

1. Is the §3a input-validity fail-safe default (treat a stale/invalid
   last sensor reading as "the projected-cumulative-dose trigger clause
   is not met," rather than falling back to an older value or a
   conservative worst-case estimate) the right default — or should a
   persistent sensor fault itself be escalated (§3h) even absent a dose
   trigger?
2. Is Ablation D (§6a) — deliberately not a realistic baseline — worth
   actually implementing and running, given the added implementation
   cost, or is the trigger/selection decomposition better obtained
   analytically from the existing three baselines plus the candidate?
3. Is "ascending room name" (§3g step 2) an acceptable arbitrary tie-
   break for simultaneous-trigger batch resolution, or should room
   processing order reflect something clinically meaningful (e.g.,
   currently-highest-risk room first)?
4. Is re-raising an unacknowledged escalation (§3h) at *every* boundary
   the right cadence, or would that create alert fatigue in a real
   deployment — a question this synthetic design does not answer, but
   relevant to whether this mechanism, as specified, is a reasonable
   basis for a future real system?
5. Is "unacknowledged at shift end" (§3h, §8a-ext) an acceptable
   terminal state, or should it instead block the shift from being
   recorded as closed until reviewed?

---

## 11. Explicit statement of what this document does and does not do

- **Does:** specify, in implementable detail, a deterministic
  non-learning candidate rotation algorithm (§3) that respects every
  hard constraint already established in
  `ROTATION_RECOMMENDER_DESIGN_SPEC.md` §2; a synthetic staffing and
  credentialing data schema (§2) and its seeded generation method; a
  counterfactual dose-simulation method that holds the underlying
  exposure identical across policies (§5); three baseline policies in
  the same implementable detail as the candidate (§6); explicit,
  separately-reported dose-accounting definitions and the
  non-redistribution reporting discipline requested this round (§7);
  constraint-violation/infeasibility/abort handling (§8); and proposed
  tests, metrics, sensitivity analyses, and a list of new unresolved
  parameters and review items (§9–§10).
- **Does not:** implement any algorithm, baseline, or simulation module
  named above; modify `phase1_simulator`, `phase2a_adapter`,
  `phase3a_forecasting`, or the frozen v1.2.3 release in any way; run
  any simulation, smoke test, or statistical campaign; report any
  dose-reduction, fairness, or collective-dose number, simulated or
  otherwise (§7c's reporting discipline has nothing to apply to yet,
  because nothing has been run); silently change any previously-approved
  content in `ICAIRE_Simulation_Validation_Methodology.md` or
  `ROTATION_RECOMMENDER_DESIGN_SPEC.md` (the latter received only the
  one non-substantive forward-pointer note described at the top of this
  document); deploy or merge anything; claim clinical validity or
  regulatory compliance anywhere.
- **Revision 2 does not change any of the above restrictions**: it
  corrects and extends the design specified in Revision 1, in the same
  documentation-only mode, with every correction's superseded Revision
  1 text kept inline for traceability (per the Revision 2 change log at
  the top of this document) rather than silently rewritten.
