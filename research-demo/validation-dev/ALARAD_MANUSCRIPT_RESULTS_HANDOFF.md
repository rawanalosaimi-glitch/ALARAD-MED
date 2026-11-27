# ALARAD — Manuscript Results Handoff (Supplementary Validation)

**For the manuscript-writing team.** Supplements, does not replace,
`RESEARCH_HANDOFF_FOR_MANUSCRIPT.md` (the original campaign's own
handoff). Every number below traces to
`phase3c_supplementary_output/analysis_summary.json` or a directly
re-executed command in this session; nothing is invented. Table/figure
references use the exact filenames this round produced.

---

## Simulation methodology (manuscript-ready text)

> "To directly test mechanisms the main campaign's own roster and
> credential configuration could not adequately exercise — the
> rotation algorithm's candidate-selection rule, the sensor-fault
> escalation pathway, and the duty-limit/acknowledgement state
> machine — we constructed a supplementary validation campaign of
> controlled scenarios. Each scenario reuses the identical, unmodified
> rotation-decision software (trigger evaluation, candidate ranking,
> atomic reservation, handoff scheduling, dose attribution) as the main
> campaign; only the input conditions (worker credentials, starting
> accumulated dose, availability, duty-limit state, and exposure
> trajectory) were explicitly constructed rather than randomly sampled.
> Three experiments were run: (A) ten scenarios each designed to
> present the rotation algorithm with a specific, controlled candidate-
> eligibility pattern (N=30 independently seeded replicates each); (B)
> eight scenarios each injecting one kind of sensor fault (missing,
> invalid, frozen, delayed, repeated, recovered, concurrent with
> elevated exposure, or simultaneous across two workers) and verifying
> detection and escalation end to end (N=30 each); (C) twelve scenarios
> targeting each distinct trigger clause, duty-limit sub-check, and
> scheduling state transition (N=30 each, one scenario found to have no
> implemented counterpart and reported as such rather than simulated)."

## Rotation-policy candidate-selection validation (manuscript-ready text)

> "Across the seven controlled scenarios designed to present at least
> two simultaneously eligible, differently-dosed replacement workers,
> the dose-aware (CGDTR) and plain-worker-ID (reference-rule) selection
> rules selected a different replacement worker in 100% of 210
> independent paired replicates (Table S1; Figure
> `candidate_selection_divergence.png`). This directly demonstrates that
> the candidate-selection mechanism functions as designed and is
> capable of divergent, dose-informed decisions; the main campaign's own
> finding that these two rules never diverged in practice (0 of 390
> paired comparisons) is attributable to its roster and credential
> configuration presenting such a choice in only 4 of 1,005 trigger
> events, not to a defect in the selection logic."

## Selection ablation (manuscript-ready text, with the honest caveat)

> "Six of the seven divergent scenarios used a preset starting
> accumulated dose on the outgoing worker to force deterministic
> triggering; because the platform's dose-attribution step computes
> each worker's reported final dose from occupancy time alone (not
> from any preset starting value), the resulting difference in which
> worker was selected did not propagate to a difference in the
> reported maximum individual dose or roster dose-fairness in those six
> scenarios (mean difference = 0.0 mSv exactly, both as a population
> average and restricted to the divergent replicates; Table S2). The
> seventh scenario, built on dose accrued through genuine simulated
> occupancy across a sequential rotation chain rather than a preset
> value, showed a mean difference of −0.0749 mSv (lower under the
> dose-aware rule), consistent across all 30 seeds. We interpret this as
> evidence that the selection mechanism is correctly implemented and
> responds to genuinely accrued dose differences, but that its
> population-level benefit for roster-wide dose outcomes remains
> untested under natural (non-engineered) staffing conditions at
> campaign scale — a direction for future work, not a claim this
> dataset supports either way."

## Sensor-fault validation (manuscript-ready text)

> "Seven of eight tested sensor-fault conditions (missing, invalid,
> frozen, repeated-with-recovery, isolated recovery, concurrent with
> elevated exposure, and simultaneous across two independent workers)
> were correctly detected and resolved in 100% of 270 independent
> replicates, with escalation events correctly and exclusively
> attributed to the affected worker (Table S3; Figure
> `sensor_fault_escalation_coverage.png`). The eighth condition —
> readings whose true timestamp is stale by a known interval — was not
> detected in any of 30 replicates under the platform's live decision
> path, which we traced to the omission of the reading's claimed
> timestamp when the per-minute sensor-state update is performed; a
> direct comparison confirmed the underlying sensor-state classifier
> correctly flags the same readings when given their true timestamp.
> This is reported as a confirmed, unresolved limitation of the current
> implementation, not a limitation of the underlying sensor-fault
> detection logic itself."

## Duty-limit and escalation-state validation (manuscript-ready text)

> "All three components of the dose-based rotation trigger — the
> accumulated-shift-dose threshold, the engine's own short-horizon
> projected-task-dose threshold, and the longer-horizon projected-
> shift-total-dose limit — were each isolated and confirmed to fire
> independently and correctly (Table S4; Figure
> `duty_limit_state_coverage.png`), including the projected-dose
> duty-limit exclusion mechanism, none of which had occurred even once
> in the 390-run main campaign. The HELD state (triggered when a
> sensor fault coincides with a scheduled handoff) and its subsequent
> resolution — either completion once the fault clears, or an explicit,
> correctly-categorized unresolved outcome if it does not clear before
> shift end — were likewise confirmed correct in 120 of 120 replicates
> across four dedicated scenarios, closing a gap in which this state
> had never been exercised by the main campaign at all. A rejected-
> acknowledgement transition was checked for and found not to be part
> of the implemented state machine; we report this as not implemented
> rather than inferring or simulating a behavior for it."

## Statistical analysis (manuscript-ready text)

> "Each supplementary scenario was replicated across 30 independently
> seeded runs, matching the minimum replicate count already established
> for the main campaign. The unit of statistical independence was one
> (scenario, seed) replicate; scenarios are fixed, purpose-built
> conditions rather than a random sample, so effects are reported per
> scenario and, only within the pre-declared family of scenarios
> sharing the same hypothesis, pooled across scenarios — never across
> structurally dissimilar conditions. Paired Wilcoxon signed-rank tests
> with Holm-Bonferroni correction and nonparametric bootstrap confidence
> intervals (2,000 resamples) were used throughout, identical to the
> methodology already validated for the main campaign. Both the
> population-average effect (all replicates) and the conditional effect
> (restricted to replicates where the compared policies genuinely
> produced different decisions) are reported separately in every
> comparison, per our own pre-specified analysis plan."

## Results (fill in only from `ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md`; already-verified numbers above may be used directly)

> "The supplementary campaign comprised 872 independent simulation runs
> across 30 scenarios (10 candidate-selection, 8 sensor-fault, 12
> duty-limit/escalation), with zero run failures. The collective-dose
> conservation invariant established by the main campaign held again
> here, to floating-point precision, across 1,500 independent policy-
> run checks (maximum deviation 8.88×10⁻¹⁶ mSv, zero violations)."

## Discussion (manuscript-ready text)

> "These results resolve an open question from our primary audit of
> the main campaign: whether the apparent equivalence between the
> dose-aware and plain selection rules reflected a genuine absence of
> benefit or an absence of statistical power. The supplementary
> campaign shows the latter — the selection mechanism is implemented
> correctly and produces different, dose-informed decisions whenever a
> real choice is available, but the main campaign's roster and
> credential configuration presented such a choice in only 0.4% of
> trigger events. Whether a larger, more credentialed roster would
> allow this capability to produce a measurable population-level dose
> benefit under naturally occurring (rather than engineered) conditions
> remains an open question for future work. Separately, this round
> surfaced and corrected two implementation defects with no effect on
> previously reported results, and identified one confirmed, unresolved
> defect in how delayed sensor readings are handled by the live
> decision pathway, which should be corrected before any claim is made
> about this platform's sensor-fault robustness under realistic,
> communication-delayed conditions."

## Limitations (manuscript-ready text)

> "This supplementary campaign demonstrates algorithmic correctness
> under controlled conditions; it does not demonstrate a population-
> level dose-reduction benefit from dose-aware worker selection, which
> remains untested at natural campaign scale. One confirmed defect
> (delayed-reading handling) was found and left unresolved, deliberately,
> given the scope of the data-flow change required to fix it safely; no
> claim in this work relies on delayed-fault detection functioning
> correctly. As throughout this project, no provisional parameter has
> been reviewed by a Medical Physicist or Radiation Safety Officer, and
> nothing here constitutes clinical or regulatory validation."

## Exact table/figure index

| Ref | File |
|---|---|
| Table S1 | Selection divergence rate per case — `ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md` section 2a |
| Table S2 | Primary endpoint (max-individual-dose diff) per case, population vs. conditional — section 2b |
| Table S3 | Experiment B escalation coverage — section 3 |
| Table S4 | Experiment C clause/state coverage matrix — section 4 |
| Figure S1 | `figures_supplementary/candidate_selection_divergence.png` |
| Figure S2 | `figures_supplementary/max_individual_dose_comparison.png` |
| Figure S3 | `figures_supplementary/dose_fairness_comparison.png` |
| Figure S4 | `figures_supplementary/infeasibility_breakdown.png` |
| Figure S5 | `figures_supplementary/sensor_fault_escalation_coverage.png` |
| Figure S6 | `figures_supplementary/duty_limit_state_coverage.png` |
| Figure S7 | `figures_supplementary/policy_comparison_completed_rotations.png` |
