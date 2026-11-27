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

### 3a. Trigger condition

Propose a rotation for `W` out of `R` **if and only if**:
- `W`'s cumulative dose so far ≥ `rotation_threshold_fraction ×
  reference_level` (mechanizing `ROTATION_RECOMMENDER_DESIGN_SPEC.md`
  §4.3's reference rule exactly — `rotation_threshold_fraction` is an
  open parameter, §10), **or**
- `W`'s projected dose (as defined above) crosses the engine's own
  `CONFIG.doseElevated` or `doseCritical` threshold (registry row 15,
  reused as-is, not a new threshold).

If neither holds, the algorithm's output at this decision point is **no
rotation**, by design, not by exception-handling (§4's "ordinary case").

### 3b. Eligibility filter (reuses design-spec §2.1 exactly)

From the full roster, build the candidate set of workers who are: (a)
credentialed for `R`'s room **and** current `procedure_class`, (b) not
already at or within a declared margin of their own
`max_dose_per_shift_mSv`, (c) `incident_state == "clear"`, (d) within an
`availability_window` covering the decision point, and (e) not within
`min_rest_between_assignments_minutes` of their last rotation-out.

### 3c. Selection rule (deterministic tie-breaking, stated exactly)

Rank the candidate set by **ascending current cumulative dose**; ties
broken by **ascending `worker_id`** (a fixed, arbitrary, but fully
deterministic rule — not a heuristic choice presented as meaningful).
Select the first-ranked candidate whose selection would **not** cause
their `max_rotations_per_shift` count, or the roster's own rotation-burden
fairness bound (`ROTATION_RECOMMENDER_DESIGN_SPEC.md` §2.4), to be
exceeded. If every candidate fails this check, output is **no rotation**
(§4, case 5).

### 3d. Procedure-continuity and handoff mechanics

The proposed swap is queued, not executed immediately: it becomes
`PENDING` at the decision point and `COMPLETED` only after
`min_handoff_duration_minutes` (registry row 9, still open) elapses with
no disqualifying event (§8's state machine). The outgoing worker `W`
continues to accrue dose normally during the `PENDING` window — a
handoff is not modeled as removing `W` from the room before the
replacement is actually in place, consistent with "a rotation is never
instantaneous" (`ROTATION_RECOMMENDER_DESIGN_SPEC.md` §2.3).

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

**All four share identically**: the eligibility filter (§3b), the
handoff state machine (§8), and the incident-acknowledgement rule (§3e)
— so that any measured difference between policies reflects the
*trigger-and-selection* logic being compared, not an inconsistency in
how constraints are enforced across policies.

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

### 9e. What is explicitly NOT claimed by this section

No test above has been run; no sensitivity analysis above has been
performed; no parameter above has a chosen value. §9a's tests are
proposed in enough detail to write directly against a future
implementation; nothing has been asserted about what any of them would
show.

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
