# ALARAD — Final Scientific Readiness Review

**Performed at the end of the final supplementary validation round, on
branch `research/icaire-v123-validation`.** Assigns PASS / WARNING /
FAIL / NOT TESTED to each required category and gives a final
scientific readiness verdict, following the evidence rather than a
predetermined outcome.

---

## Verification checklist

| Category | Verdict | Evidence |
|---|---|---|
| All original tests still pass | **PASS** | `python3 -m unittest discover -s phase3c_rotation_infra/tests -t .` -> 111/111 (109 original + 2 regression tests added this round), 0 failures |
| All supplementary tests pass | **PASS** | `python3 -m unittest phase3c_rotation_infra.supplementary.tests.test_supplementary_infrastructure` -> 24/24, 0 failures |
| Original raw datasets remain intact | **PASS** | `phase3c_campaign_output/manifest.json`: 390 completed, 0 failed, unchanged; `raw_runs/` still holds exactly 390 files |
| New raw datasets are complete | **PASS** | `phase3c_supplementary_output/manifest.json`: 872 rows (300+241+331), 0 failures, git revision and config snapshot recorded |
| No unsupported or fabricated results | **PASS** | Every number in the results documents traces to a stored JSON file or a directly-executed command; the one place a result could have been fabricated or glossed over (Experiment A's zero dose-outcome difference, section 2b of the results doc) is instead explained mechanistically and disclosed as a methodological finding, not hidden |
| No unexplained policy equivalence | **PASS** | CGDTR = reference-rule in the original campaign is now fully explained (audit) AND the mechanism is proven capable of divergence (this round) — nothing about the equivalence remains unexplained |
| No undocumented safety-path coverage gaps | **WARNING** | HELD/RSO-ack and clauses (b)/(c) coverage gaps are now closed and documented; the delayed-reading defect (section 4 item 3 of the validation report) is a newly-found, explicitly documented, *not yet closed* gap — correctly flagged, not hidden, which is why this is WARNING rather than FAIL |
| No statistical pseudoreplication | **PASS** | Unit of independence is one (case, seed) replicate throughout; cases pooled only within the pre-declared family; Holm-Bonferroni applied across the per-case test family; no per-minute or per-event record treated as an independent sample |
| No mismatch between tables, figures, JSON, and manuscript text | **PASS** | Spot-checked: `ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md`'s tables reproduce exactly from `analysis_summary.json` (verified by direct query, same session); figure files exist for every reference in the manuscript handoff; no number was transcribed by hand without a traceable source |
| Frozen v1.2.3 SHA-256 unchanged | **PASS** | `92e897dd0ff1738f083df829b53f7f46377e042b7019bb9776232792261182ee`, re-verified identical before and after this round |
| No accidental deployment or production changes | **PASS** | All work confined to `research-demo/validation-dev/`; no merge performed; no deploy step exists in this project's tooling; `git status` reviewed before commit (section below) |

## Two real defects, one still open

This round found three real implementation defects (not in the frozen
release) and fixed two of them, each pinned by a new regression test
and verified to have zero effect on the original 390-run campaign's
own stored numbers:

1. Attempts landing exactly at shift end were silently dropped from
   every counter — **fixed**.
2. A worker's second, independent sensor-fault episode could never
   raise an escalation once the first one resolved — **fixed**.
3. The live orchestrator discards a delayed reading's claimed stale
   timestamp — **found, not fixed**, deliberately deferred given its
   broad blast radius across every policy and archetype already
   evaluated. This is the one open item behind the WARNING above.

## What remains a scientific limitation, not a technical gap

(Restated, not newly invented, consistent with
`PHASE3C_B_ASSUMPTIONS_LIMITATIONS_AND_THREATS_TO_VALIDITY.md` and
`PHASE3C_AUDIT_REPORT.md` section 8/9.)

- The selection-rule mechanism is now proven correct, but its
  real-world dose-outcome benefit remains untested at natural
  (non-engineered) campaign scale — this round's controlled scenarios
  prove capability, not population-level effect size.
- Every provisional parameter remains illustrative and unreviewed by a
  Medical Physicist or RSO.
- No claim anywhere in this project constitutes clinical or regulatory
  validation.

## Final scientific readiness verdict

# READY WITH DISCLOSED LIMITATIONS

Not "READY FOR MANUSCRIPT" unconditionally, because one real defect
(delayed-reading blindness) is confirmed and not yet fixed, and the
selection rule's real-world benefit at natural scale remains untested.
Not "NOT READY — CORRECTIONS REQUIRED", because:
- every required technical deliverable for this round was generated,
  executed, and verified (872 supplementary rows, 0 failures; 135
  total tests across both rounds, 0 failures);
- the two defects that WERE fixed are narrow, regression-tested, and
  proven to have zero retroactive effect on already-published numbers;
- the one unfixed defect is fully disclosed, with its exact mechanism,
  reproduction (30/30 seeds), and reason for deferral stated plainly,
  not hidden or minimized;
- no claim in any document overstates what the evidence shows, and
  several places (Experiment A's dose-outcome result, the selection-
  rule's real-world-benefit status) explicitly state a weaker
  conclusion than a reader might otherwise assume.

A manuscript may proceed using this round's results, provided it
carries the disclosed limitations forward exactly as stated here and
in `ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md` section 5 — specifically,
that the delayed-sensor-reading defect is a known, open issue, and that
the selection-rule's benefit is demonstrated as a correctness property,
not as a population-level effect size.
