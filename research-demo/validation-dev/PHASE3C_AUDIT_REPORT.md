# Phase 3C Rotation Campaign — Final Scientific and Implementation Audit

**Scope:** a post-hoc audit of the already-completed Phase 3C-B rotation
campaign (`PHASE3C_B_CAMPAIGN_RESULTS.md`, `PHASE3C_B_TEST_EVIDENCE.md`,
`ALARAD_TECHNICAL_RESEARCH_COMPLETION_REPORT.md`), performed before
manuscript sign-off. Branch: `research/icaire-v123-validation`. The
frozen `ALARAD_Prototype_Research_Demo_v1.2.3.html` was not opened for
editing at any point in this audit; its SHA-256
(`92e897dd0ff1738f083df829b53f7f46377e042b7019bb9776232792261182ee`)
was re-verified unchanged before and after. **No algorithm file was
modified and the campaign was not re-run.** Where a defect was found in
*documentation* (not in the algorithm or the campaign's own numbers),
it was corrected directly in the affected `.md` file, per this audit's
own instructions to propose and make scientifically justified
corrections rather than silently leave a known-wrong claim standing;
every such correction is logged in section 7 below and is visible as a
"Correction (post-hoc audit)" block at its exact location in
`PHASE3C_B_CAMPAIGN_RESULTS.md`.

**Method:** direct inspection of `phase3c_rotation_infra/policies.py`,
`assignment.py`, `simulation.py`, `staffing.py`, `escalation.py`,
`stats_common.py`, and `analyze_rotation_campaign.py`; direct querying
of `phase3c_campaign_output/analysis_summary.json` and
`phase3c_campaign_output/raw_runs/*.json` (all 390 files); and, where
the committed outputs could not answer a question on their own (issues
1-3 below), two new **read-only diagnostic scripts** that deterministically
replay the exact same seeds, archetypes, and roster-generation calls as
the real campaign, wrapping (never editing) `assignment.batch_resolve`
to additionally record what it already computes internally, with
unchanged inputs, outputs, and side effects. Both are committed at
`phase3c_rotation_infra/audit_diagnostics/` for reproducibility, along
with their raw output (`eligible_ge2_examples.json`,
`infeasibility_breakdown.json`).

---

## Issue 1 — Why CGDTR and reference-rule produce identical outcomes across all 390 paired runs

**Verdict: WARNING** (correct implementation; the campaign's own
experimental conditions never gave the two selection rules a chance to
disagree — an under-powered design for this specific question, not a
code defect).

`rank_candidates` (`policies.py:143-159`) implements two genuinely
different orderings — `SELECTION_LOWEST_DOSE` sorts by
`(worker_accumulated_shift_dose_mSv(w), worker_id)`;
`SELECTION_FIRST_IN_ORDER` sorts by `worker_id` alone — and these are
proven to diverge given a mixed-dose, multi-candidate input
(`phase3c_rotation_infra/tests/test_policies.py`'s dedicated ranking
tests). `assignment.batch_resolve` (`assignment.py:72-98`) correctly
walks `candidate_order` and falls through to the next-ranked candidate
if an earlier one is ineligible — it is **not** a bug where only the
top-ranked candidate is ever tried.

Direct instrumented replay of the real campaign's 1,005 CGDTR trigger
events (`phase3c_rotation_infra/audit_diagnostics/audit_candidate_pool.py`)
found:

| Eligible candidates at decision time | Count | % |
|---|---|---|
| 0 | 985 | 98.0% |
| 1 | 16 | 1.6% |
| 2+ (the only condition where ranking could matter) | **4** | **0.4%** |

In **all 4** of those 4 events, the eligible candidates' own
`cumulative_dose_mSv` were tied at exactly 0.0 — neither had accrued
any dose yet this shift — so `SELECTION_LOWEST_DOSE`'s sort collapsed
to its own ascending-`worker_id` tie-break, which is the same rule
`SELECTION_FIRST_IN_ORDER` uses as its primary key. The two rules were
therefore not merely rarely tested; the rare tests that did occur were
structurally incapable of producing a different winner, given how the
tie-break is defined. Root cause: this round's illustrative roster size
(`staffing.py::generate_roster`, `n_workers = n_concurrent_rooms + 2`
once `run_campaign.py`'s own `n_rooms + 1` argument and
`extra_workers_beyond_concurrent_rooms=1` are combined — a smaller
spare margin than the campaign's own documentation previously implied)
combined with `credential_coverage_probability_range=[0.4, 0.7]` and
the compound room-AND-procedure-class credentialing check
(`WorkerProfile.is_credentialed_for`) leaves, in 98% of trigger events,
no one else credentialed and simultaneously free at all.

**File references:** `phase3c_rotation_infra/policies.py:143-159`,
`assignment.py:48-103`, `staffing.py:77-114`,
`run_campaign.py:84-87` (the `n_rooms + 1` call site),
`phase3c_rotation_infra/audit_diagnostics/audit_candidate_pool.py`
(new, this audit), `.../eligible_ge2_examples.json` (new, this audit).

## Issue 2 — Why the selection ablation effect is exactly zero; whether the selection mechanism is meaningfully tested

**Verdict: WARNING** (mechanism verified correct in isolation by unit
test; never meaningfully exercised at campaign scale; the campaign
provides no evidence, for or against, any real selection-rule effect).

Direct consequence of Issue 1. The ablation decomposition in
`analyze_rotation_campaign.py::ablation_decomposition` is computed
correctly from the campaign's own data (`selection_effect_mSv` = mean
of `(cgdtr − reference_rule)` and `(fixed_interval − ablation_d)` paired
differences); both pairs are identically zero in every one of the 390
runs for the reason given in Issue 1, so a mean of exactly 0.0 with a
[0.0, 0.0] bootstrap CI is the mathematically correct output of a
correctly-implemented function fed all-zero input — not a computation
bug. The selection mechanism itself is proven to work via
`test_policies.py` (unit level, synthetic multi-candidate scenarios)
but is "meaningfully tested" in the sense of being exercised against
real, organically-arising multi-candidate campaign conditions **0 times
out of 1,005 opportunities**. No claim about CGDTR's selection rule
being better, worse, or equivalent to a plain worker-ID rule can be
supported by this campaign in its current configuration; see Issue 6.

**File references:** `analyze_rotation_campaign.py:123-146`,
`PHASE3C_B_CAMPAIGN_RESULTS.md` section 6 (now corrected, see section 7
below), `phase3c_rotation_infra/tests/test_policies.py`.

## Issue 3 — CGDTR's 20 completed / 985 infeasible breakdown

**Verdict: WARNING** (the committed campaign log cannot answer this
breakdown on its own; reconstructed by read-only replay; dominant cause
is credential scarcity, not duty limits or scheduling).

`assignment.batch_resolve` records only one generic reason string on
failure, `"no_eligible_candidate_free_through_interval"`
(`assignment.py:94-97`), for every one of the 985 CGDTR INFEASIBLE
events (confirmed by a direct scan of all 390 `raw_runs/*.json` files —
100% of CGDTR's infeasible reasons are this single string). This is a
genuine reporting-granularity limitation of the implementation: by
design, it does not distinguish *why* no candidate survived. Replaying
the same 1,005 trigger events with a read-only classifier
(`audit_diagnostics/audit_infeasibility_reasons.py`) that applies
`batch_resolve`'s own filter chain per-candidate, in the same order,
gives:

| Root cause | Count | % of 1,005 triggers |
|---|---|---|
| No credentialed candidate at all | 845 | 84.1% |
| Credentialed candidate(s) existed, all occupying another room | 133 | 13.2% |
| All credentialed candidates blocked by `max_rotations_per_shift` duty limit | 7 | 0.7% |
| Had ≥1 eligible candidate → completed | 20 | 2.0% |

The `max_rotations_per_shift` duty limit **did fire for real** on live
campaign data (7 times, concentrated entirely in `transient_spike`),
confirming that sub-check works as specified outside of unit tests. Two
other eligibility sub-checks never fired in the real campaign at all:
the projected-dose duty-limit check
(`projected_shift_total_dose_mSv >= max_dose_per_shift_mSv`,
`assignment.py:88-91`, the Phase 3C-A gap-3 closure) and the
availability-window check (`assignment.py:86`) — the latter is
structurally unexercisable in this campaign by construction, since
`staffing.py::generate_roster` always grants every worker a single
full-shift availability window (line 111:
`availability_windows=[(0, shift_minutes)]`). Both remain validated
only by `test_assignment.py`'s dedicated unit tests, never by this
campaign's own data.

**File references:** `assignment.py:48-103`,
`staffing.py:77-114` (line 111 specifically),
`phase3c_rotation_infra/audit_diagnostics/audit_infeasibility_reasons.py`
(new, this audit), `.../infeasibility_breakdown.json` (new, this audit).

## Issue 4 — Paired statistical tests, Holm-Bonferroni, confidence intervals, zero-difference treatment, and the 2.85% figure

**Verdict: WARNING** (every computation checked is statistically
correct; one real disclosure gap found and now corrected — the
effective/nonzero pair count was not previously shown alongside the
headline mean difference).

- **Holm-Bonferroni** (`stats_common.py::holm_bonferroni`): hand-
  recomputed the full step-down over the actual 14-member family
  (`analysis_summary.json::paired_comparisons.holm_bonferroni_corrected`)
  and confirmed the stored `adjusted_alpha`/`significant` values match
  the correct sorted step-down procedure exactly, including the
  `p=None` (undefined, all-zero-difference) entries correctly counting
  toward the family size `m=14` rather than being silently dropped.
  **PASS.**
- **Bootstrap CIs** (`stats_common.py::bootstrap_ci`): standard
  nonparametric percentile bootstrap (`n_boot=2000`, fixed `seed=12345`
  for reproducibility), with correct `n=0`/`n=1` edge-case handling.
  **PASS.**
- **Zero-difference treatment and the effective sample size** (the
  core of this issue): `scipy.stats.wilcoxon`'s default
  `zero_method='wilcox'` (confirmed: scipy 1.17.1, this environment)
  drops zero-difference pairs before computing the test statistic —
  standard, accepted practice, **not a defect**. But
  `stats_common.py::wilcoxon_paired`'s returned `n_pairs` field reports
  the *raw* pair count (390) rather than the number of pairs the test
  actually used. Direct recomputation against the real data
  (`cg - nr` across all 390 raw runs) found: for CGDTR-vs-no-rotation,
  only **18 of 390 pairs (4.6%) are nonzero**, and all 18 favor CGDTR —
  which is exactly why the Wilcoxon statistic is 0 and p is small
  (1.96e-4) despite the tiny effective n. The reported headline mean
  difference (−0.001104 mSv, a **2.85%** relative reduction against
  no-rotation's full-campaign mean of 0.03877 mSv) is arithmetically
  correct **and is the right number for a population-average framing**,
  but it was not previously shown next to the fact that 95.4% of runs
  contributed an exact zero to it. The conditional effect, computed
  only over the 18 affected runs, is −0.0239 mSv (≈29.7% relative to
  those 18 runs' own no-rotation mean of 0.0806 mSv) — over 20x larger
  in absolute terms than the population-average figure. **This gap is
  now disclosed directly in `PHASE3C_B_CAMPAIGN_RESULTS.md` section 5**
  (new table + explanatory paragraph, added by this audit). Verdict for
  the underlying math: correct. Verdict for the original disclosure:
  incomplete, now fixed.

**File references:** `stats_common.py:24-98`,
`analyze_rotation_campaign.py:91-121`,
`phase3c_campaign_output/analysis_summary.json::paired_comparisons`,
`PHASE3C_B_CAMPAIGN_RESULTS.md` section 5 (corrected by this audit).

## Issue 5 — Collective dose conservation, duty limits, sensor-fault handling, and RSO escalation

**Verdict: mixed — PASS / PARTIAL PASS / WARNING / FAIL**, broken out below
because this issue bundles four materially different mechanisms:

- **Collective dose conservation: PASS.** Verified to floating-point
  precision across the entire campaign: 1,950 policy-run pairs checked
  (390 runs × 5 policies), max |diff| = 2.22e-16 mSv, 0 violations
  (`analysis_summary.json::collective_dose_invariant_check`,
  independently re-confirmed by a direct re-scan during this audit).
  The strongest-evidenced claim in the whole campaign.
- **Duty limits: PARTIAL PASS.** The `max_rotations_per_shift`
  sub-check fired for real on live data (Issue 3, 7 times). The
  projected-dose sub-check and the availability-window sub-check never
  fired in the real campaign (Issue 3) — both remain validated only in
  isolation by `test_assignment.py`.
- **Sensor-fault handling (dose-accrual gating): PASS**, for the part
  that *is* continuously exercised — dose only accrues when
  `ASSIGNED` and the reading is `usable` (`runtime.py`), confirmed
  operating throughout the campaign by the nonzero skipped-window
  counts in every `fault_*` archetype.
- **Sensor-fault handling (HELD / simulated RSO acknowledgement):
  WARNING.** `simulation.py`'s HELD-attempt branch
  (lines ~164-193) and the "simulated RSO acknowledgement" recompute
  path were triggered **zero times** across all 1,950 policy-run
  evaluations (`n_held=0` everywhere in `analysis_summary.json`,
  independently confirmed by a direct re-scan of all 390×5 raw-run
  records this audit performed). This path is unit-tested via a
  scripted, engineered scenario
  (`test_simulation.py::TestHeldAndEscalation`) but the live campaign
  itself contributes zero evidence that it behaves correctly under
  organically-arising conditions.
- **RSO escalation / sensor-fault-persistence channel: FAIL on the
  documentation claim; WARNING on the underlying architecture.**
  `escalation.py::evaluate_escalation` — the actual sensor-fault-
  persistence state machine, unit-tested by `test_escalation.py`'s 8
  tests including a real-engine-integration test — is imported by
  `simulation.py` (line 61) but is **never called anywhere in the live
  orchestrator** (confirmed directly by inspecting every line of
  `simulation.py`; no call site exists). The original
  `PHASE3C_B_CAMPAIGN_RESULTS.md` (section 4) incorrectly stated that
  the campaign's "escalated_rooms" counts (e.g. 72 for CGDTR) came from
  "the sensor-fault-persistence channel (`escalation.py`)." **That
  claim was false** — the actual counter is `simulation.py`'s own,
  separate, simpler "≥2 consecutive INFEASIBLE rotation attempts"
  per-room counter (the module's own documented simplification #5,
  with no connection to sensor faults). The real sensor-fault-
  persistence channel was never exercised by any run in the campaign.
  **This has been corrected directly in `PHASE3C_B_CAMPAIGN_RESULTS.md`
  section 4** (see section 7 below). The underlying architecture (two
  separate escalation-shaped mechanisms, one wired into the live
  orchestrator and one not) is itself a disclosed, intentional scope
  decision per `simulation.py`'s own module docstring point 5 — the
  defect was specifically in how the campaign *results document*
  described the live orchestrator's output, not in the orchestrator's
  design.

**File references:** `phase3c_rotation_infra/escalation.py` (entire
file, never called from `simulation.py`), `simulation.py:61` (the
unused import), `simulation.py:160-193` (the HELD branch, `n_held=0`
confirmed), `dose_attribution.py`, `runtime.py`,
`test_escalation.py`, `test_simulation.py::TestHeldAndEscalation`,
`PHASE3C_B_CAMPAIGN_RESULTS.md` sections 3-4 (corrected by this audit).

## Issue 6 — Does the experiment support CGDTR superiority, or only improvement relative to no rotation?

**Verdict: WARNING against any superiority claim; PASS for the
narrower, already-stated claim.**

The only claim this campaign, as configured, can support:
**rotation of any of the four tested kinds (fixed-interval,
reference-rule, Ablation D, CGDTR) significantly reduces maximum
individual dose and improves roster-dose fairness relative to no
rotation** (p < 0.0005 for every rotation-vs-no-rotation comparison,
Holm-Bonferroni corrected — though see Issue 4's caveat that this is
driven by a minority, 4.6-6.4%, of runs per comparison).

**No claim of CGDTR superiority over the other rotation policies is
supportable**, for two independent reasons now fully quantified by this
audit:

1. CGDTR vs. reference-rule (the selection-rule test) is not merely a
   null result — it is an *uninformative* one. Issue 1/2 show the
   selection rule was given a chance to matter in only 4 of 1,005
   trigger events, and even those 4 were tie-broken identically by
   construction. The campaign cannot distinguish "no selection-rule
   effect exists" from "this campaign never tested for one."
2. CGDTR vs. fixed-interval (the trigger-rule test, which *did* have a
   real chance to differ — 25/390 nonzero pairs, split 14/11) found no
   statistically significant difference (p=0.098, not significant after
   Holm-Bonferroni correction). This is a genuine, informative null
   result, not an artifact of missing data — the trigger rule was
   actually exercised and still showed no detectable advantage.

This matches what `PHASE3C_B_CAMPAIGN_RESULTS.md` and
`RESEARCH_HANDOFF_FOR_MANUSCRIPT.md` already stated before this audit
(no superiority claim was ever made in either document); this audit's
contribution is pinning down *why* the selection-rule result is
specifically uninformative rather than merely negative, which changes
how a manuscript should phrase it (see section 8).

**File references:** `PHASE3C_B_CAMPAIGN_RESULTS.md` sections 5-6,
`RESEARCH_HANDOFF_FOR_MANUSCRIPT.md` section 4.

---

## 7. Corrections made to existing documentation by this audit

All three are documentation corrections only — no algorithm file was
touched and the campaign was not re-run. Each is marked in place in
`PHASE3C_B_CAMPAIGN_RESULTS.md` as a **"Correction (post-hoc audit)"**
block so the edit history is traceable:

1. **Section 3**: "all held attempts resolved before shift end" →
   corrected to state plainly that zero HELD attempts occurred at all
   (`n_held=0` everywhere), with the Issue 5 explanation.
2. **Section 3-4**: added the Issue 1/2/3 quantified findings (candidate-
   pool/eligibility histograms, the tied-dose tie-break finding, and the
   infeasibility root-cause table) that were not computable from the
   previously-committed campaign outputs alone.
3. **Section 4**: corrected the false attribution of the
   "escalated_rooms" counter to `escalation.py`'s sensor-fault-
   persistence channel; relabeled the table column; stated plainly that
   the real sensor-fault-persistence channel was never exercised by the
   campaign.
4. **Section 5**: added the zero/nonzero effective-pair-count disclosure
   and the population-average-vs-conditional-effect-size distinction for
   the 2.85% figure.

No correction required changing any number already reported for the
collective-dose invariant, the Holm-Bonferroni results table, the
bootstrap CIs, the sensitivity sweep, or any forecasting result — all
of those were independently re-verified and found correct as originally
reported.

## 8. Recommended manuscript wording adjustment (not yet applied to `RESEARCH_HANDOFF_FOR_MANUSCRIPT.md`; proposed here for review)

Where that document currently says CGDTR "was statistically
indistinguishable from reference-rule," a manuscript should instead say
the comparison was *uninformative, not merely null* — e.g.: "the
campaign's illustrative roster and credential-coverage parameters left
the dose-aware selection rule with a genuine choice between two or more
eligible candidates in only 4 of 1,005 trigger events (0.4%), so this
campaign cannot distinguish a true absence of a selection-rule effect
from an absence of statistical power to detect one." This is a wording
refinement, not a numeric correction, and is left to the manuscript
team's own judgment on phrasing rather than applied unilaterally here.

## 9. Final manuscript-readiness decision

**CONDITIONAL PASS**, now that the corrections in section 7 are in
place. Specifically:

- **Ready to support**: "all four tested rotation policies reduce
  maximum individual dose and improve fairness relative to no rotation
  at this sample size" and "no rotation policy tested, including
  CGDTR, shows a statistically detectable advantage over the simplest
  tested alternative (fixed-interval)" — both exactly as already framed
  in `PHASE3C_B_CAMPAIGN_RESULTS.md` and
  `RESEARCH_HANDOFF_FOR_MANUSCRIPT.md`, and both independently
  re-verified correct by this audit.
- **Not ready, and not fixable without a new campaign** (explicitly out
  of this audit's scope per its own instructions): any claim about the
  selection rule specifically (Issue 1/2/6) — the current illustrative
  roster/credential parameters make that comparison structurally
  uninformative, not just negative. A future campaign intending to test
  the selection rule would need a roster/credential configuration that
  produces multiple simultaneously-eligible, differently-dosed
  candidates with non-trivial frequency; that is a new experimental
  design decision, not a bug fix, and is explicitly flagged here rather
  than silently attempted.
- **Documentation now accurate**: the escalation-channel misattribution
  (a false claim) and the zero/nonzero disclosure gap (an incomplete
  but not false claim) are both corrected as of this audit.
- **No change was made, or is recommended, to any algorithm, any
  configuration value, or the campaign's own stored results.** The
  frozen v1.2.3 release remains untouched
  (SHA-256 `92e897dd0ff1738f083df829b53f7f46377e042b7019bb9776232792261182ee`,
  re-verified at the end of this audit). Nothing in this branch has been
  merged or deployed.
