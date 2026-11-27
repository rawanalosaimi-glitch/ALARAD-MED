# ALARAD — Final Supplementary Validation Report

**Scope: the "Final Supplementary Validation, Scientific Audit &
Manuscript Handoff" task, following the completed Phase 3A/3C
campaigns and the formal `PHASE3C_AUDIT_REPORT.md`.** Branch:
`research/icaire-v123-validation`. Frozen
`ALARAD_Prototype_Research_Demo_v1.2.3.html` SHA-256 verified
unchanged before and after this round:
`92e897dd0ff1738f083df829b53f7f46377e042b7019bb9776232792261182ee`.

---

## 0. Non-negotiable protections — confirmed

- Branch: `research/icaire-v123-validation` (confirmed at start and end).
- Working tree: clean before starting; every change this round is new
  files plus three narrow, documented, additive fixes (see section 4).
- Frozen file: untouched; hash re-verified identical before/after.
- `phase3c_campaign_output/` (the original 390-run campaign): never
  read or written by any file in `phase3c_rotation_infra/supplementary/`
  (checked both by source inspection and a dedicated unit test,
  `test_supplementary_infrastructure.py::TestOriginalCampaignUntouched`).
- The original CGDTR algorithm's decision logic
  (`policies.py::rank_candidates`/`evaluate_dose_threshold_trigger`) was
  **not changed at all** -- this round found it already correct; see
  section 2.
- No merge, no deploy, performed only on the research branch.

## 1. Baseline reconciliation

All audit findings quoted in the task were re-verified directly against
the actual committed data before any new work began (not re-derived
from memory):

| Finding | Re-verified value | Source |
|---|---|---|
| 390 paired runs per policy | 390 | `phase3c_campaign_output/manifest.json` |
| 1,005 CGDTR trigger events | 1,005 | `audit_diagnostics/audit_candidate_pool.py` re-run |
| 20 completed | 20 | `analysis_summary.json` |
| 985 infeasible | 985 | `analysis_summary.json` |
| 4 multi-candidate events, all tied | 4, all tied at 0.0 mSv | `audit_diagnostics/eligible_ge2_examples.json` |
| 18/390 nonzero CGDTR-vs-no-rotation pairs | 18/390 | direct re-scan of `raw_runs/*.json` |
| CGDTR == reference-rule, byte-identical | confirmed, 390/390 zero diffs | direct re-scan |
| escalation.py imported but never called | confirmed by source inspection | `simulation.py` line 61 (import), no call site |
| HELD/RSO-ack never exercised | `n_held=0` everywhere | `analysis_summary.json` + raw re-scan |

All treated as findings to verify, not assumptions — each was
independently re-derived from the actual stored JSON or source code,
not copied from the audit report's prose.

## 2. Supplementary campaign design

Three experiments, each targeting a mechanism the original campaign
could not adequately exercise, built on a new, committed package
(`phase3c_rotation_infra/supplementary/`) that reuses the real
`WorkerProfile`/`AssignmentSlot` classes and the real
`simulation.run_policy_on_run` orchestrator unchanged — the only
controlled element is the INPUT data (credentials, starting dose,
availability, duty-limit state, exposure trajectory), never the
decision logic itself. Full design, exact file references, and the
pre-registered hypothesis for every one of the 10+8+12 sub-cases:
`ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md`.

- **Experiment A** (10 sub-cases, 300 runs): forces >=2 simultaneously
  eligible, unequally-dosed candidates, something the original campaign
  achieved only 4 times in 1,005 opportunities.
- **Experiment B** (8 sub-cases + 1 direct-path comparison, 241 runs):
  exercises the real per-minute sensor-fault path end to end, closing
  the audit's "`escalation.py` imported but never called" finding by
  feeding the orchestrator's own real per-minute sensor-state output to
  the real `evaluate_escalation`, without changing the live decision
  path.
- **Experiment C** (12 sub-cases, 331 runs; 1 reported NOT IMPLEMENTED):
  deliberately drives each of the three trigger clauses, the
  previously-unexercised duty-limit and HELD/acknowledgement paths, and
  cross-room simultaneity.

Statistical design (`analyze_supplementary_campaign.py`): one
(case, seed) replicate is the unit of independence; cases are fixed,
designed conditions pooled only within the pre-declared
diverge-expected family (A1/A2/A4/A5/A6/A7/A9), never flattened across
structurally dissimilar cases; every comparison reports BOTH the
population-average effect and the conditional effect (restricted to
genuinely divergent runs), labeled separately, per this round's own
instruction; Holm-Bonferroni applied across the per-case family;
bootstrap CIs reused unchanged from `stats_common.py` (already verified
correct in the main campaign's own audit).

## 3. Execution

All three experiments ran to completion in one pass: 872 total rows, 0
run failures (`phase3c_supplementary_output/manifest.json`). Raw,
machine-readable per-run data (scenario, seed, policy, worker state,
exposure, dose history, trigger history, candidate list, selection
decision, state transitions, fault/escalation events, dose outcomes)
is stored in `experiment_{a,b,c}_raw.json`; the manifest records the
git revision, Python version, seed bases, and per-experiment timing for
reproducibility. Full counts and tables: `ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md`.

## 4. Real defects found and corrected (or deliberately deferred)

Full detail and exact file references:
`ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md` section 5. Summary:

1. **Fixed** — `simulation.py` silently dropped any rotation attempt
   whose `t_effective` landed exactly at `shift_minutes`, or any HELD
   attempt whose incident never cleared, from every counter. New
   `UNRESOLVED_AT_SHIFT_END` outcome + `n_unresolved_at_shift_end`
   counter; regression test added. Zero effect on the original
   campaign's stored numbers (proven by exact arithmetic, not assumed).
2. **Fixed** — `escalation.py`'s raise condition could never fire a
   second, independent fault episode after the first one resolved.
   Guard widened from `rec.state == NONE` to `rec.state in (NONE,
   RESOLVED)`; regression test added. Zero effect on the original
   campaign (the function is never called by the live orchestrator at
   all, before or after this fix).
3. **Found, deliberately not fixed** — the live orchestrator discards a
   delayed reading's claimed stale timestamp (always uses the current
   minute), so "delayed" sensor faults are invisible to it — confirmed
   on 30 independent seeds. Not fixed this round because it touches the
   core per-minute data-flow path used by every policy and every
   archetype already evaluated in the main campaign; flagged as the
   top-priority item for a dedicated future correction round rather
   than rushed in at the tail of this one.

Both fixes are additive, narrow, and pinned by new regression tests;
neither was applied "merely to produce more favorable results" — both
were found by, and fixed in response to, genuine scenario coverage gaps
the task asked this round to probe.

## 5. Scientific interpretation — the task's ten questions, answered explicitly

1. **Does CGDTR select lower-dose eligible replacement workers when a
   meaningful choice exists?** Yes — confirmed directly from
   `rotation_events`, independent of any dose-outcome metric: CGDTR
   selected the lowest-accumulated-dose eligible candidate in 100% of
   the 210 (case, seed) replicates across the 7 sub-cases designed to
   offer a real choice.
2. **Does this selection produce a measurable reduction in maximum
   individual dose compared with reference-rule?** Mixed, and precisely
   characterized, not glossed over: in 6 of those 7 sub-cases, no —
   because `dose_attribution.py` computes final dose purely from
   occupancy time, not from the preset starting dose used to force
   determinism, so the difference in WHO was picked does not reach the
   reported outcome metric in those designs (section 2b of the results
   doc). In the one sub-case built on REAL, occupancy-accrued dose
   (A8), yes: −0.0749 mSv (CGDTR lower), consistent across all 30 seeds.
3. **Under what staffing and exposure conditions does the benefit
   appear?** Only demonstrated where dose differences between eligible
   candidates arise from real accrued occupancy time, not from an
   artificially preset starting value — i.e., conditions resembling
   A8's sequential-rotation structure. This round did not test a
   larger-roster, naturally-occurring version of that condition at full
   campaign scale; that remains open (section 8 of the main-campaign
   audit and this report's own limitations).
4. **When does CGDTR fail to outperform simpler policies?** As already
   established by the main campaign (`PHASE3C_B_CAMPAIGN_RESULTS.md`):
   CGDTR showed no statistically detectable advantage over fixed-
   interval (p=0.098) at the achieved main-campaign sample size. This
   round adds: the selection-rule comparison specifically was not
   merely negative but uninformative in the original campaign (0.4%
   opportunity rate) — now proven correct in isolation, but still
   untested at natural campaign scale with a roster large enough to
   offer real choices organically.
5. **What is the operational cost of the additional decision logic?**
   Not separately measured this round (out of this round's declared
   scope); the main campaign already reported CGDTR's far higher
   trigger-attempt rate (1,005 vs. 133 for fixed-interval) at a much
   lower per-attempt success rate (2% vs. 16%) as the main cost signal.
6. **Does the sensor-fault pathway work end to end?** Partially: 7 of 8
   fault kinds tested (missing, invalid, frozen, repeated, recovery,
   elevated-exposure-concurrent, simultaneous-multi-worker) detect and
   resolve correctly in 100% of 270 runs. The 8th (delayed) does not —
   a confirmed, real, unfixed defect (section 4, item 3).
7. **Are all specified duty-limit checks exercised?** Now yes, for the
   first time: all three trigger clauses and the projected-dose
   exclusion check fire and behave correctly across 30/30 seeds each
   (Experiment C). The availability-window sub-check remains
   structurally unexercisable by this project's own staffing model
   (every worker gets full-shift availability by construction) — not a
   defect, a scope boundary, stated plainly.
8. **Do HELD and RSO acknowledgement transitions work correctly?**
   Yes, now demonstrated directly: 120/120 runs across the four
   dedicated sub-cases (C6-C9) correctly HELD, then either COMPLETED
   (fault cleared in time) or UNRESOLVED_AT_SHIFT_END (never cleared) —
   both resolution paths, never silently dropped.
9. **Which findings are algorithmic verification, and which constitute
   empirical simulation evidence?** Algorithmic verification (correct-
   by-construction, demonstrated on controlled inputs): selection-rule
   divergence, trigger-clause isolation, duty-limit exclusion, HELD/ack
   transitions, sensor-fault detection (7/8 kinds), collective-dose
   conservation. Empirical simulation evidence only (depends on this
   project's own synthetic exposure/staffing assumptions, not a general
   claim): none of this round's dose-outcome numbers generalize beyond
   the specific controlled scenarios that produced them — see
   limitations below and `..._LIMITATIONS...md`.
10. **Which claims remain unsupported?** Any claim that CGDTR's
    selection rule reduces real-world maximum individual dose or
    improves fairness at natural (non-forced) campaign scale — this
    round proves the mechanism is correct, not that it helps under
    realistic, non-engineered staffing conditions. Any claim that
    sensor-fault handling is fully correct end to end — the delayed-
    reading defect is a confirmed exception. Any clinical or regulatory
    claim, as throughout this entire project.

## 6. What this round does and does not change about prior conclusions

- **Unchanged:** the main campaign's own statistical findings (no
  rotation-policy superiority claim was ever supportable, and still
  isn't); the collective-dose invariant (re-confirmed independently
  here); every number in `phase3c_campaign_output/`.
- **Resolved, not merely re-asserted:** audit issues 1, 2, and 5 (the
  "escalation channel never exercised" and "HELD never exercised"
  findings) are now closed with direct, positive evidence that the
  underlying mechanisms work correctly — the original campaign's null
  results on these specific questions were due to insufficient
  opportunity, not a defect, and that distinction is now proven rather
  than argued.
- **New, previously unknown:** the two fixed defects (section 4, items
  1-2) and the one found-but-unfixed defect (item 3), none of which
  were visible before this round's targeted scenario construction.
