# ALARAD — Manuscript Final Handoff

**Supersedes `ALARAD_MANUSCRIPT_RESULTS_HANDOFF.md` for anything the
two documents disagree on; where they agree, both stand.** Written
after `ALARAD_FINAL_STATISTICAL_AUDIT.md` independently re-verified
every run count, statistic, and endpoint definition in the
supplementary validation round. All text below is ready for direct
inclusion in the manuscript, in professional academic English.

---

## Methods (final verified text)

> To test mechanisms that our primary 390-run validation campaign's
> roster and credential configuration could not adequately exercise —
> the rotation algorithm's dose-aware candidate-selection rule, the
> sensor-fault escalation pathway, and the duty-limit and
> acknowledgement state machine — we conducted a supplementary
> validation campaign of 29 purpose-built scenarios, each replicated
> across 30 independently seeded runs (870 independent simulation
> replicates in total, zero run failures), using the identical,
> unmodified rotation-decision software as the primary campaign.
> Scenarios were organized into three experiments: (A) ten scenarios,
> each presenting a specific, controlled candidate-eligibility pattern
> to the selection logic; (B) eight scenarios, each injecting one kind
> of sensor fault and verifying detection and escalation end to end;
> and (C) eleven scenarios targeting each distinct dose-threshold
> trigger clause, duty-limit sub-check, and scheduling state
> transition, plus one additional scenario that checked for, and
> confirmed the absence of, an acknowledgement-rejection state in the
> implemented scheduling logic. Two additional, non-replicated records
> were produced alongside these 870 replicates: one direct comparison
> of the sensor-fault classifier's behavior when given a reading's true
> timestamp versus the live system's own handling of it, and one
> explicit capability-check result; neither is treated as an
> independent statistical observation in any analysis below.

## Results — candidate-selection validation (final verified text)

> Across the seven scenarios constructed to present at least two
> simultaneously eligible, differently dosed replacement workers, the
> dose-aware and plain-worker-identifier selection rules selected a
> different replacement worker in 100% of 210 independent paired
> replicates. This is a deterministic property of the implemented
> ranking logic, confirmed directly from each run's own recorded
> decision trail rather than inferred statistically, and demonstrates
> that the selection mechanism functions as designed. We separately
> assessed whether this divergence in selection translated into a
> measurable difference in the reported maximum individual dose. In
> six of the seven scenarios, it did not (mean difference 0.0 mSv,
> Wilcoxon test undefined because all 210 paired differences were
> exactly zero); in the seventh, built on dose accrued through
> simulated occupancy across a sequential rotation chain rather than a
> fixed starting condition, the dose-aware rule produced a mean
> reduction of 0.0749 mSv (Wilcoxon p = 1.86 × 10⁻⁹, 95% bootstrap CI
> [−0.0750, −0.0748], n = 30).

## Results — why six of seven scenarios showed no dose-outcome difference (final verified text)

> We traced the absence of a measurable dose-outcome difference in six
> scenarios to the measurement instrument rather than to the algorithm
> under test. Our dose-attribution procedure computes each worker's
> reported dose as an integral of simulated occupancy time and
> exposure rate from the start of the simulated shift, consistent with
> its documented definition and with its established, unmodified use
> throughout the primary campaign. Six of our seven selection scenarios
> used a fixed, non-zero starting accumulated dose — assigned before
> the simulated shift begins — specifically to force deterministic
> triggering independent of exposure noise; this starting value lies,
> by the dose-attribution procedure's own definition, outside the
> window over which shift dose is integrated, and is therefore not
> reflected in the reported outcome regardless of which worker is
> subsequently selected. A confirmatory analysis — adding each
> scenario's own fixed starting dose back to the dose-attribution
> procedure's reported value for the selected worker, using only
> already-recorded data and introducing no new simulation — exactly
> reproduced the designed dose gap between candidates in all seven
> scenarios (mean differences of −0.01 to −0.03 mSv, each matching that
> scenario's own known preset gap precisely). We conclude that the
> selection mechanism is implemented correctly and is capable of
> producing a differentiated dose outcome when the relevant dose
> difference accrues within the simulated shift, but that six of our
> seven controlled scenarios were not constructed in a way that allowed
> this outcome to register in the primary dose-attribution metric —
> a limitation of this validation technique, not evidence against the
> algorithm.

## Results — sensor-fault and escalation validation (final verified text)

> Seven of eight tested sensor-fault conditions — missing readings,
> invalid readings, frozen (repeated-value) readings, two independent
> fault episodes within a single shift, isolated fault recovery, a
> fault concurrent with elevated exposure, and simultaneous,
> independent faults across two workers — were detected and correctly
> resolved by the escalation logic in 100% of 270 independent
> replicates, with escalation events correctly and exclusively
> attributed to the affected worker in every case. The eighth
> condition — a reading whose true timestamp is stale by a known
> interval — was not detected in any of 30 replicates under the live
> decision pathway; a direct comparison confirmed that the underlying
> sensor-state classifier correctly flags the same reading when given
> its true timestamp, isolating the defect to how the live pathway
> constructs its per-minute input rather than to the classifier itself.
> This is reported as a confirmed, unresolved limitation.

## Results — duty-limit and escalation-state validation (final verified text)

> All three components of the dose-based rotation trigger — the
> accumulated-shift-dose threshold, the short-horizon engine-projected
> task-dose threshold, and the longer-horizon projected-shift-total-dose
> limit — were each isolated and confirmed to fire independently and
> correctly, including a projected-dose duty-limit exclusion mechanism
> that had not fired even once across our primary 390-run campaign. A
> state in which a scheduled handoff is held pending resolution of a
> concurrent sensor fault, and its subsequent resolution — either
> completion once the fault clears or an explicit, distinctly
> categorized unresolved outcome if it does not clear before shift
> end — were likewise confirmed correct in 120 of 120 replicates across
> four dedicated scenarios, closing a gap in which this state had never
> been exercised by the primary campaign. We additionally checked for,
> and confirmed the absence of, a state corresponding to a rejected
> acknowledgement in the implemented scheduling logic; we report this
> as not implemented rather than inferring a behavior for it.

## Statistical analysis (final verified text)

> Each scenario was replicated across 30 independently seeded runs,
> consistent with the minimum replicate count already established for
> our primary campaign. The unit of statistical independence was one
> (scenario, seed) replicate; because scenarios are fixed, purpose-built
> conditions rather than a random sample from a population of
> conditions, effects are reported per scenario and pooled only within
> the pre-declared family of scenarios sharing an identical hypothesis,
> never across structurally dissimilar conditions. We applied paired
> Wilcoxon signed-rank tests with Holm-Bonferroni correction across the
> full family of comparisons and nonparametric bootstrap confidence
> intervals (2,000 resamples), identical to the methodology validated
> for our primary campaign; where all paired differences within a
> comparison were exactly zero, the test statistic and p-value are
> reported as undefined rather than substituted with a default value.
> Every comparison distinguishes a deterministic property of the
> algorithm's own decision logic (verified directly from each run's
> recorded trail, requiring no hypothesis test) from a statistical
> claim about a measured outcome (requiring, and receiving, a
> hypothesis test and confidence interval). All run counts,
> independence assumptions, and statistical outputs reported here were
> independently re-derived from raw simulation output in a subsequent
> audit, which found no computational error in any of them.

## Discussion (final verified text)

> Together, these results resolve an open question raised by our
> primary campaign's audit: whether the observed equivalence between
> the dose-aware and plain selection rules reflected a genuine absence
> of algorithmic benefit or an absence of statistical power. Our
> supplementary campaign shows the latter for the selection mechanism's
> own correctness — it reliably produces different, dose-informed
> decisions whenever a genuine choice between replacement workers is
> available — while leaving open whether this capability translates
> into a measurable population-level dose benefit under naturally
> occurring, rather than deliberately engineered, staffing conditions
> at full campaign scale. Separately, this validation effort identified
> and corrected two implementation defects with no retroactive effect
> on previously reported results, and identified, without resolving, a
> defect in how the live system handles sensor readings with a stale
> claimed timestamp. We regard this as an appropriate point to report
> interim findings rather than to overstate either the scope of what
> has been validated or the significance of what remains open.

## Limitations (final verified text)

> This work demonstrates algorithmic correctness of the candidate-
> selection, duty-limit, and escalation mechanisms under controlled
> conditions. It does not demonstrate a population-level dose-reduction
> benefit from dose-aware worker selection under natural staffing
> conditions, which remains an open question for future work at larger
> campaign scale. One confirmed defect — the handling of sensor readings
> with a stale claimed timestamp — was identified and deliberately left
> unresolved in this round, given the scope of the implementation
> change required to correct it safely; no result in this work depends
> on that pathway functioning correctly. As throughout this project, no
> provisional threshold or parameter used in these simulations has been
> reviewed by a Medical Physicist or Radiation Safety Officer, the
> synthetic exposure and staffing models are not derived from real
> clinical data, and nothing in this work constitutes, or should be
> read as, clinical or regulatory validation of any kind.

## Exact tables and figures

| Ref | Source |
|---|---|
| Table 1 (run-count reconciliation) | `ALARAD_FINAL_STATISTICAL_AUDIT.md`, task 1 table |
| Table 2 (selection divergence by scenario) | `ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md` section 2a |
| Table 3 (primary endpoint + sensitivity check) | `ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md` section 2b |
| Table 4 (sensor-fault coverage) | `ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md` section 3 |
| Table 5 (duty-limit/escalation-state coverage) | `ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md` section 4 |
| Figure 1 | `figures_supplementary/candidate_selection_divergence.png` |
| Figure 2 | `figures_supplementary/max_individual_dose_comparison.png` |
| Figure 3 | `figures_supplementary/dose_fairness_comparison.png` |
| Figure 4 | `figures_supplementary/infeasibility_breakdown.png` |
| Figure 5 | `figures_supplementary/sensor_fault_escalation_coverage.png` |
| Figure 6 | `figures_supplementary/duty_limit_state_coverage.png` |

## Claims the authors must NOT make

- Must not state or imply that CGDTR reduces real-world occupational
  dose — only algorithmic correctness and controlled-scenario behavior
  have been demonstrated.
- Must not describe the 210-replicate selection-divergence result as
  "statistically significant dose reduction" — it is a deterministic
  verification of decision logic, not a statistical finding about dose
  outcome; only A8's result is a statistical dose-outcome finding.
- Must not describe the six zero-mean-difference scenarios as showing
  "no benefit" or "no effect of selection rule" without the
  accompanying sensitivity-check explanation — doing so would
  misrepresent a measurement-instrument limitation as a negative
  algorithmic finding.
- Must not state that the sensor-fault escalation pathway is fully
  validated — the delayed-reading defect is confirmed and unresolved.
- Must not conflate `EngineProjectedTaskDose`, `WorkerAccumulatedShiftDose`,
  and `ProjectedShiftTotalDose`, or compare any of them against the
  wrong threshold.
- Must not describe any provisional parameter (dose-threshold
  fractions, reference levels, duty limits) as clinically or
  operationally validated, approved, or representative of real
  staffing policy.
- Must not imply regulatory review, clinical trial status, or
  deployment readiness of any kind.
- Must not present the 872-row figure without the 870-replicate /
  2-non-replicate distinction established in
  `ALARAD_FINAL_STATISTICAL_AUDIT.md`.
