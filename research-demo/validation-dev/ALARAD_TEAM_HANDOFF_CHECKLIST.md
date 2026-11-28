# ALARAD — Team Handoff Checklist

**Branch for all referenced files: `research/icaire-v123-validation`.**
Commit hash and final verification status: see
`ALARAD_FINAL_STATISTICAL_AUDIT.md`'s closing note and this session's
final report to the user. Nothing below has been merged or deployed.

---

## Rawan — technical methodology, results, statistics, and figures

**Needs, in this order:**

1. `ALARAD_FINAL_STATISTICAL_AUDIT.md` — the independent re-verification
   of every run count and statistic; read this first, as it corrects
   two precise statements in the documents below it.
2. `ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md` — full results for all 29
   scenarios, with the corrected run-count table and the quantitative
   sensitivity-check table (section 2b).
3. `ALARAD_FINAL_SUPPLEMENTARY_VALIDATION_REPORT.md` — design rationale,
   execution summary, and the ten scientific-interpretation questions
   answered explicitly.
4. `PHASE3C_AUDIT_REPORT.md` and `PHASE3C_B_CAMPAIGN_RESULTS.md` — the
   primary 390-run campaign's own audit and results, which this round's
   work follows up on directly.
5. `ALARAD_REPRODUCIBILITY_GUIDE.md` — exact commands, seed blocks, and
   file map to re-run or extend any part of this round.
6. Raw data and figures, for any further analysis: `phase3c_supplementary_output/`
   (870 independent replicates + 2 non-replicate records, see the audit
   for the breakdown) and `figures_supplementary/` (7 PNGs).

**Outstanding technical item for Rawan specifically:** the delayed-
sensor-reading defect (`ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md`
section 5, item 3) is confirmed but deliberately unfixed. If a future
round is scoped to fix it, it requires changing `simulation.py`'s
per-minute `readings` construction and `runtime.py`'s `sensor_step_batch`
signature to carry a reading's claimed timestamp through to the
sensor-state step — a change with a broad blast radius across every
policy and archetype already evaluated in the primary campaign, so it
should be done as its own dedicated round with its own re-validation,
not folded into unrelated work.

## Rahaf — manuscript writing and integration

**Needs, in this order:**

1. `ALARAD_MANUSCRIPT_FINAL_HANDOFF.md` — **the authoritative source for
   manuscript text.** Contains final, verified Methods, Results,
   Statistical Analysis, Discussion, and Limitations paragraphs ready
   for direct inclusion, plus the exact table/figure index and an
   explicit list of claims that must not be made.
2. `RESEARCH_HANDOFF_FOR_MANUSCRIPT.md` — the primary campaign's own
   handoff (covers the rotation-policy comparison, forecasting
   evaluation, and ablation decomposition this supplementary round
   builds on; its own section 4 flags exactly what this round resolves).
3. `figures_supplementary/*.png` and `figures/*.png` — all figures
   referenced by file name in both handoff documents; use them exactly
   as named, do not regenerate or re-derive new figures from the raw
   JSON without re-running the provided scripts.
4. The "Claims the authors must NOT make" section at the end of
   `ALARAD_MANUSCRIPT_FINAL_HANDOFF.md` — treat this as a hard
   constraint on drafting, not a suggestion; several of these claims
   are easy to state by accident when summarizing the 100%-divergence
   finding or the six zero-difference scenarios.

**If something in the primary campaign's own handoff
(`RESEARCH_HANDOFF_FOR_MANUSCRIPT.md`) and this round's handoff
(`ALARAD_MANUSCRIPT_FINAL_HANDOFF.md`) appear to conflict**, the latter
is authoritative for the supplementary-round material; the former
remains authoritative for the primary campaign's own rotation-policy
and forecasting results, which this round did not alter.

## Manar — governance, RSO oversight, human accountability, and limitations

**Needs, in this order:**

1. `ALARAD_FINAL_SCIENTIFIC_READINESS_REVIEW.md` — the formal PASS/
   WARNING/FAIL/NOT-TESTED checklist and the final verdict: **READY
   WITH DISCLOSED LIMITATIONS**, not an unconditional pass.
2. `ALARAD_MANUSCRIPT_FINAL_HANDOFF.md`'s Limitations section and
   "Claims the authors must NOT make" section — the exact language
   this project can and cannot stand behind; useful for reviewing any
   drafted manuscript text against before it goes out.
3. `PHASE3C_B_ASSUMPTIONS_LIMITATIONS_AND_THREATS_TO_VALIDITY.md` and
   `SCIENTIFIC_PARAMETER_REVIEW_PACKAGE.md` — the full, standing list
   of provisional parameters that have never received expert (Medical
   Physicist/RSO) review; this round introduced no new parameters
   needing review, but changed nothing about this outstanding list
   either.
4. `ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md` section 5 — the three
   real implementation defects found this round (two fixed, one
   deliberately not), for governance visibility into what engineering
   judgment calls were made and why.

**Remaining scientific decisions requiring expert input (unchanged in
kind from prior rounds, restated here for completeness, not newly
introduced by this round):**

- Whether the dose-threshold trigger's illustrative parameters
  (`rotation_threshold_fraction`, `reference_level_mSv_per_shift`) are
  clinically or operationally appropriate — still unreviewed.
- Whether the duty-limit profile ranges (`max_dose_per_shift_mSv`,
  rest/rotation limits) reflect real staffing policy — still
  unreviewed.
- Whether a larger-roster, higher-credential-coverage follow-up
  campaign to test the selection rule's population-level dose benefit
  under natural conditions is worth commissioning — a research
  planning decision, not a technical one, and the one new question
  this round's findings raise most directly.
- Whether and when to schedule the dedicated round to fix the
  delayed-sensor-reading defect, given it requires its own
  re-validation of the `fault_delayed` archetype's prior results.

## Final status (for all three)

- Branch: `research/icaire-v123-validation`.
- Frozen `ALARAD_Prototype_Research_Demo_v1.2.3.html`: unchanged,
  SHA-256 `92e897dd0ff1738f083df829b53f7f46377e042b7019bb9776232792261182ee`.
- All regression tests passing (see `ALARAD_FINAL_STATISTICAL_AUDIT.md`'s
  companion verification run for the exact count).
- Nothing has been merged to `main` or deployed.
