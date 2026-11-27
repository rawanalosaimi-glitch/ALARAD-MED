# ALARAD Supplementary Validation — Campaign Results

**Status: real, actually-executed results from the final supplementary
validation round, reported exactly as produced.** Data:
`phase3c_supplementary_output/{experiment_a_raw.json, experiment_b_raw.json,
experiment_c_raw.json, analysis_summary.json, manifest.json}`. This
campaign is entirely separate from, and never overwrites, the original
390-run Phase 3C-B campaign (`phase3c_campaign_output/`), which remains
unchanged and intact (verified in `ALARAD_FINAL_SCIENTIFIC_READINESS_REVIEW.md`).

---

## 1. Scope achieved

| Experiment | Sub-cases run | Seeds/case | Total rows | Wall time |
|---|---|---|---|---|
| A — multi-candidate selection | 10 | 30 | 300 | 557.7 s |
| B — sensor faults & escalation | 8 (+1 direct-path comparison) | 30 | 241 | 72.3 s |
| C — duty limits / HELD / RSO ack | 11 run + 1 reported NOT_IMPLEMENTED | 30 | 331 | 142.2 s |

0 run failures across all 872 rows. Seed bases: A=910000, B=920000,
C=930000 — disjoint from every other seed block in this project
(design set 20260601-13; Phase 3A smoke 3001-3008; Phase 3A campaign
90000+; Phase 3C-B campaign 700000+; sensitivity 850000+). 30 seeds per
case matches this project's own established minimum
(`ICAIRE_Simulation_Validation_Methodology.md` section 7/8) — reused,
not re-derived, as the precision rationale for this round.

**Architecture note (methods, not a finding):** every sub-case runs
through the real, unmodified `simulation.run_policy_on_run` orchestrator
and the real `policies.py`/`assignment.py`/`scheduling.py`/`runtime.py`/
`dose_attribution.py`/`escalation.py` functions. The only thing this
round's new code (`phase3c_rotation_infra/supplementary/`) controls
that the original campaign left to random sampling is the INPUT data:
exact worker credentials/doses/availability/duty-limit state, and exact
exposure trajectories — never trigger, selection, scheduling, or dose
logic itself.

## 2. Experiment A — multi-candidate selection

### 2a. Headline result: the selection mechanism works, and had never been tested

**100% of the 7 sub-cases designed to force a real choice (A1, A2, A4,
A5, A6, A7, A9) showed CGDTR and reference-rule selecting a DIFFERENT
worker, in every one of the 210 (case × seed) replicates (divergence
rate = 1.0 for all 7).** This directly resolves `PHASE3C_AUDIT_REPORT.md`
issues 1/2/6: `rank_candidates`'s two branches
(`SELECTION_LOWEST_DOSE` vs. `SELECTION_FIRST_IN_ORDER`) are correctly,
independently implemented and DO diverge the moment a genuine choice
exists — the original campaign's 0.4% multi-candidate rate, not a
selection-logic defect, explains why this was never observed before.

A3 (deliberately tied doses) and A10 (deliberately no candidate at all)
both show divergence rate = 0.0, exactly as designed — confirming the
deterministic tie-break and the INFEASIBLE path both behave correctly
and consistently, not just by chance on one seed.

| Case | Title | Divergence rate | n seeds |
|---|---|---|---|
| A1 | Two eligible candidates, unequal doses | 1.00 | 30 |
| A2 | Three eligible candidates, unequal doses | 1.00 | 30 |
| A3 | Equal doses -> tie-break | 0.00 | 30 |
| A4 | Lowest-dose worker unavailable | 1.00 | 30 |
| A5 | Lowest-dose worker not credentialed | 1.00 | 30 |
| A6 | Lowest-dose worker at duty-limit cap | 1.00 | 30 |
| A7 | Lowest-dose worker occupied elsewhere | 1.00 | 30 |
| A8 | Sequential rotations, evolving doses | 1.00 | 30 |
| A9 | Greedy vs. lookahead (duty-limit headroom) | 1.00 | 30 |
| A10 | No safe replacement exists | 0.00 | 30 |

Figure: `figures_supplementary/candidate_selection_divergence.png`.

### 2b. Primary endpoint result, and a real, important methodological finding about measuring it

**Pre-specified primary endpoint:** difference in maximum individual
accumulated shift dose between CGDTR and reference-rule, reported both
as a population average (all seeds) and a conditional effect
(divergent seeds only), per this round's own statistical design.

**Result for A1, A2, A4, A5, A6, A7, A9 (pooled, n=210 pairs):**
population-average mean diff = **0.0 mSv exactly** (Wilcoxon: all 210
differences are exactly zero, p undefined); the conditional effect
(restricted to the 210 divergent pairs — all of them, since divergence
rate is 1.0 in every one of these cases) is likewise **0.0 mSv
exactly**.

**This is not a null finding about CGDTR — it is a methodological
finding about how this round measured the endpoint, and it is reported
as such rather than silently reframed.** `dose_attribution.
cumulative_dose_per_worker` (verified directly: `dose_attribution.py`
lines 83-89) computes each worker's final dose **purely from occupancy
time × the shared exposure series, starting from zero** — it never
reads or adds a worker's starting `cumulative_dose_mSv`. This round's
sub-cases A1/A2/A4-A7/A9 use a **preset** starting dose on the outgoing
worker specifically to force the trigger to fire reliably and
deterministically (necessary, since without it the trigger would
depend on noisy, seed-varying exposure crossing a threshold by chance).
That preset correctly drives the LIVE trigger and selection decision
(`runtime.py` live-increments and the trigger logic live-reads the same
field) — which is exactly why the 100% divergence rate above is real
and meaningful — but the preset is **invisible** to the POST-HOC
`dose_attribution` computation used for the reported outcome metrics.
Concretely: whichever worker is selected occupies the same room for the
same remaining duration under the same exposure series, so their
POST-HOC attributed dose is identical regardless of which specific
worker-id was chosen — the preset "head start" that made them eligible
for selection in the first place never enters that calculation.

**A8 is the exception, and it is the informative case.** A8's sequential,
multi-rotation design accrues REAL dose through REAL occupancy over
time (not a preset), so by the time its later decisions are made, the
relevant dose differences ARE occupancy-based and DO show up in
`dose_attribution`'s output: **mean diff = −0.0749 mSv** (CGDTR lower),
consistent across all 30 seeds (divergence rate 1.0).

**What this round therefore actually demonstrates, precisely:**
1. The selection mechanism is implemented correctly and does select
   differently when given a real choice (proven directly from
   `rotation_events`, independent of the dose-attribution question).
2. When that different selection arises from REAL, occupancy-accrued
   dose differences (A8), it DOES propagate to a measurably different
   roster-wide dose outcome.
3. When it arises from PRESET doses used only to force deterministic
   triggering (A1/A2/A4-A7/A9), the roster-wide dose-outcome metric is
   not sensitive to it, by construction of `dose_attribution.py` — a
   genuine limitation of this round's own experimental technique for
   those specific sub-cases, not a property of CGDTR.
4. A follow-up campaign wanting to measure selection-rule dose-outcome
   effects directly should prime doses through simulated occupancy
   (as A8 does), not through a directly-set initial field, if it
   intends to report `dose_attribution`-based metrics.

Figure: `figures_supplementary/max_individual_dose_comparison.png`
(shows the 0.0 values for 6/7 cases and A9's own near-zero result
plainly, not hidden).

### 2c. Secondary endpoints

- **Fairness (roster dose-variance):** identical pattern to 2b, for the
  same reason — exactly equal between CGDTR and reference-rule in
  A1/A2/A4-A7/A9 (verified, `figures_supplementary/dose_fairness_comparison.png`).
- **Collective-dose conservation:** holds to floating-point precision
  across Experiment A: 1,500 policy-run pairs checked (300 runs × 5
  policies), max |diff| = **8.88e-16 mSv**, 0 violations — the same
  invariant the main campaign established, now re-confirmed under
  entirely different, hand-constructed, controlled conditions.
- **Successful-rotation / infeasible / held / unresolved rates:** see
  `figures_supplementary/infeasibility_breakdown.png` and section 4
  below (shared with Experiment C's coverage story).
- **Constraint-violation count:** `SimulationResult.n_violations` is
  declared in the dataclass but **never incremented anywhere in
  `simulation.py`** (confirmed by source inspection) — reported here as
  **NOT IMPLEMENTED** as a live counter, per this round's own explicit
  instruction not to invent a value for an unimplemented field.
  Constraint violations are instead verified structurally (no double
  reservation, duty-limit exclusion, credential filtering) by the
  existing and new unit tests, not by a live campaign counter.

## 3. Experiment B — sensor faults and escalation, exercised end to end

**Method note:** `escalation.py::evaluate_escalation` is still never
called by the live orchestrator (confirmed unchanged from
`PHASE3C_AUDIT_REPORT.md` issue 5) — this experiment closes that
specific audit gap by capturing the orchestrator's own real per-minute
sensor-state output (via a documented wrapper around
`advance_workers_one_minute_batch`, the exact function the live
orchestrator calls every minute) and feeding it to the real
`evaluate_escalation` as a separate, explicit analysis step. The live
decision path is untouched.

| Case | Fault kind | n runs | Raised | Resolved | States observed |
|---|---|---|---|---|---|
| B1 | Missing | 30 | 30/30 | 30/30 | HEALTHY, STALE, DISCONNECTED, RECOVERING |
| B2 | Invalid | 30 | 30/30 | 30/30 | HEALTHY, INVALID, RECOVERING |
| B3 | Frozen | 30 | 30/30 | 30/30 | HEALTHY, SUSPECTED_FROZEN |
| B4 | Delayed (orchestrator path) | 30 | **0/30** | 0/30 | HEALTHY only |
| B5 | Repeated (2 episodes) | 30 | 30/30 (both episodes) | 30/30 | STALE, DISCONNECTED |
| B6 | Recovery | 30 | 30/30 | 30/30 | INVALID |
| B7 | Elevated exposure + fault | 30 | 30/30 | 30/30 | INVALID |
| B8 | Simultaneous (2 workers) | 60 (30×2) | 60/60 | 60/60 | STALE, DISCONNECTED (per-worker, never cross-attributed) |

**B1/B2/B3/B5/B6/B7/B8: 100% detection and resolution**, across every
injected fault type this round covers, with correct per-worker
attribution (B8) and correct repeated-episode handling (B5 — see
section 5 for the real bug this sub-case found and fixed).

**B4 is a confirmed, serious, and separate finding.** A "delayed"
reading (claimed timestamp stale by 15 minutes, matching
`phase2a_adapter.dq_adapter.build_observations`'s own fault-
reconstruction convention) is **never detected at all** by the live
orchestrator path — 0 of 30 seeds raised any escalation, and the
captured sensor-state history is HEALTHY throughout. A direct-path
comparison (`B4_direct_path_comparison` row, calling
`sensor_validity.sensor_step_once`/the engine's own `sensorStep`
directly with the SAME delayed observation and its real claimed `ts`)
correctly shows INVALID then STALE then RECOVERING -- proving the
engine itself handles delayed readings correctly when given the real
timestamp. **Root cause:** `simulation.py`'s per-minute loop extracts
only `obs["value"]` from each room's observation
(`reading = None if obs is None else obs["value"]`) and discards
`obs["ts"]` entirely; `runtime.py`'s `sensor_step_batch` then rebuilds
the observation using the CURRENT loop minute as `ts`, never the
reading's own claimed timestamp. **This is a real defect in the live
orchestrator's sensor-fault handling, confirmed on 30 independent
seeds, not fixed in this round** — see section 5 for why, and
`ALARAD_FINAL_SCIENTIFIC_READINESS_REVIEW.md` for its priority.

Figure: `figures_supplementary/sensor_fault_escalation_coverage.png`.

## 4. Experiment C — duty limits, HELD, and RSO acknowledgement

| Case | Target mechanism | Clause/outcome counts (30 seeds) |
|---|---|---|
| C1 | Clause (a) alone | 30 triggers, all clause (a), 30/30 completed |
| C2 | Clause (b) alone — **first time ever fired in this project** | 60 triggers, all clause (b), 30/30 completed |
| C3 | Clause (c) alone — **first time ever fired in this project** | 30 triggers, all clause (c), 30/30 unresolved-at-shift-end (by design, see case docstring) |
| C4 | Projected-dose duty-limit exclusion — **0 occurrences in the original 390-run campaign; reliably fires here** | 90 triggers, 60 infeasible (candidate correctly excluded), 30 unresolved (a separate, zero-intended-minutes edge case at the final boundary) |
| C5 | No eligible replacement | 90 triggers, 90/90 infeasible |
| C6 | HELD state — **n_held=0 in the original campaign; fires reliably here** | 30/30 HELD, 30/30 then COMPLETED after acknowledgement |
| C7 | RSO acknowledgement received (same mechanism as C6 in this implementation) | 30/30 HELD -> COMPLETED |
| C8 | RSO acknowledgement delayed | 30/30 HELD -> COMPLETED at the correct, recomputed later boundary |
| C9 | RSO acknowledgement absent | 30/30 HELD -> UNRESOLVED_AT_SHIFT_END (this round's own fix, see section 5) |
| C10 | RSO acknowledgement rejected | **NOT IMPLEMENTED** — `scheduling.py` has no rejection state or transition; reported as such, not simulated |
| C11 | Repeated triggers while pending | 120 triggers, 120/120 correctly re-evaluated and INFEASIBLE each time (no stuck state) |
| C12 | Simultaneous cross-room trigger for the one shared candidate | 120 triggers, 30 completed / 90 infeasible — exactly one room wins the shared candidate every time, never double-booked |

**C6/C7/C8/C9 are the most important results in this experiment**: the
HELD state and the "simulated RSO acknowledgement" recompute path
(`simulation.py` lines ~164-193) had **zero occurrences across the
entire original 390-run × 5-policy campaign** (`PHASE3C_AUDIT_REPORT.md`
issue 5). Here, deliberately constructed to exercise them, they fire
and resolve correctly in **120 of 120 runs across all four sub-cases**
(30 each), including the two distinct resolution paths (clears in time
-> COMPLETED; never clears -> the newly-fixed UNRESOLVED_AT_SHIFT_END,
not silently dropped). This directly and fully closes that audit gap:
the mechanism was correctly implemented and unit-tested all along; it
had simply never been organically exercised by the main campaign's own
low trigger-success rate.

Figure: `figures_supplementary/duty_limit_state_coverage.png`.

## 5. Real defects found and fixed this round (full disclosure)

Three real defects were found; two were fixed (narrow, low-risk,
additive, zero effect on the original campaign's own stored numbers,
confirmed in each case); one was found and deliberately **not** fixed
this round, given its broader blast radius.

1. **FIXED — `simulation.py`: an attempt landing exactly at
   `t_effective == shift_minutes` (or a HELD attempt whose incident
   never clears) was silently dropped from every counter.**
   `scheduling.compute_t_effective` legitimately allows `t_effective ==
   shift_minutes` (shift end is itself a valid boundary, by its own
   docstring), but the orchestrator's main loop only iterates
   `t in range(shift_minutes)` and never reaches that minute to resolve
   it. Found via Experiment A's A8 case (and was ALREADY latent,
   unnoticed, in `test_simulation.py`'s own pre-existing stress-test
   scenario — confirmed by re-running it and observing the previously-
   silent gap surface once fixed). Fixed with a new, explicitly labeled
   `UNRESOLVED_AT_SHIFT_END` outcome category and
   `n_unresolved_at_shift_end` counter, never folded into
   `n_completed`/`n_infeasible`/`n_held`. Regression test:
   `test_simulation.py::test_unresolved_attempt_at_shift_end_is_counted_not_dropped`.
   **Effect on the original 390-run campaign: none** — verified by
   exact arithmetic (every policy's `n_completed + n_infeasible` already
   summed to exactly its own trigger-event count, leaving no room for a
   silently-dropped attempt; see `PHASE3C_AUDIT_REPORT.md` issue 3's
   independently-instrumented 1,005-trigger count for CGDTR specifically).
2. **FIXED — `escalation.py`: a worker's second, independent fault
   episode could never raise once the first episode resolved.**
   `evaluate_escalation`'s raise condition read `rec.state == NONE`
   only; once a record transitioned to `RESOLVED`, that condition could
   never be true again, so a wholly separate, later fault streak was
   silently invisible. Found via Experiment B's B5 ("repeated faults")
   sub-case. Fixed by widening the guard to `rec.state in (NONE,
   RESOLVED)`. Regression test:
   `test_escalation.py::test_second_independent_fault_episode_raises_again_after_first_resolves`.
   **Effect on the original campaign: none** — `evaluate_escalation` is
   never called by the live orchestrator at all (section 3), so this
   function contributed nothing to any of the original campaign's
   stored numbers either way.
3. **FOUND, NOT FIXED — `simulation.py`/`runtime.py`: the live
   orchestrator discards a delayed reading's claimed stale timestamp,
   always using the current minute instead (Experiment B, case B4).**
   Confirmed on 30 independent seeds (section 3). **Deliberately not
   fixed in this round**: unlike the two fixes above, this touches the
   core per-minute data-flow path (`simulation.py`'s `readings` list
   construction and `runtime.py`'s `sensor_step_batch` signature) used
   by every policy and every archetype already evaluated in the main
   campaign — a change with a much broader blast radius that deserves
   its own dedicated validation pass (including re-evaluating the
   `fault_delayed` archetype's results specifically), not a rushed fix
   appended to an already-large round. Flagged here as the top-priority
   item for the next correction round; see
   `ALARAD_FINAL_SCIENTIFIC_READINESS_REVIEW.md`.

No test was weakened, skipped, or removed to obtain a passing result.
One pre-existing test's own FIXTURE data (not its assertion's intent)
was corrected — `test_escalation.py::test_real_missing_sensor_sequence_raises_escalation`
had been unintentionally feeding a second, unrelated fault condition
(a repeated constant value, incidentally triggering frozen-sensor
detection) into what was meant to be a single-episode missing-data
test; varying the post-recovery values removes that accidental second
condition without touching the test's actual intent or assertions.
