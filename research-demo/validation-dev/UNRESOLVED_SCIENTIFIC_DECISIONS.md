# Unresolved Scientific Decisions

Distinct from `SCIENTIFIC_PARAMETER_REVIEW_PACKAGE.md`'s per-parameter
review table: these are the higher-level **decisions** this project
cannot make for itself, most of which depend on how the parameter review
comes out. Nothing below has been decided. Row numbers refer to
`ICAIRE_Simulation_Validation_Methodology.md` §9.

1. **Should the simulator keep its procedure-class framing and rescale
   onto the engine's room baselines, or should it be redesigned to
   generate directly in terms of rooms?** (Row 16.) This project
   mathematically verified the rescaling is severity-neutral for the
   ranges currently in force (`PHASE2C_CORRECTIVE_IMPLEMENTATION.md` §7),
   but verified-consistent is not the same as scientifically meaningful.
   Changing the simulator to eliminate rescaling would alter Phase 1's
   already-accepted output and needs its own explicit re-approval,
   separate from this parameter review.

2. **Should the immediate-alert dose bypass exist at all, in a research
   validation context?** (Row 17.) This is a workflow/safety-philosophy
   question, not just a threshold-value question — bypassing a
   statistical confirmation requirement because of an absolute dose
   figure is a design choice that a statistical evaluation campaign
   would need to either hold fixed or treat as its own variable.

3. **Can Baseline 3 ever be labeled "representative of conventional
   practice," and if so, on whose authority?** (Row 6.) This project has
   deliberately withheld that label pending a citation. No search for
   such a citation has been performed by this project; whether one
   exists, and whether it would actually describe this specific
   algorithm, is open.

4. **Should a Phase 1 generator be built for S10's masked-event and
   S11's recovery-then-later-event dynamics, and with what parameters?**
   (Row 18.) Not yet started. If pursued, the realistic duration/spacing
   values for those dynamics need to be decided before, not after, the
   generator's own code is written — so this decision should be made
   together with, not separately from, this parameter review.

5. **Is the fixed 30-minute dose-projection horizon appropriate across
   all procedure types, or should it vary?** (Part of row 15.) Currently
   a single constant reused everywhere a horizon is needed, inherited
   unexamined from the frozen engine's own convention.

6. **What real-world data sources, if any, exist for rows 1, 3, 4, 5,
   11, 12, 14, 15, and 19?** Every one of these is currently a placeholder
   with "no evidence" as its status. This project has not searched for
   applicable manufacturer specifications, regulatory guidance, facility
   survey data, or wearable-sensor failure-rate literature — whether any
   exists, and where, is for the reviewer's own expertise to identify
   (§6 of the review package).

7. **Resolved as a registration gap, still open as a review item: the
   frozen engine's own sensor-health state-machine thresholds**
   (`AlaradSafety.SENSOR_P`: stale after 2 missed minutes, disconnected
   after 5, suspected frozen after 6 identical consecutive readings at
   0.1 µSv/h resolution, recovery after 2 consistent samples). This item
   previously read "not yet a numbered registry row at all" — it has
   since been added as **Parameter Registry row 19**
   (`ICAIRE_Simulation_Validation_Methodology.md` Revision 4) and as a
   priority item in `SCIENTIFIC_PARAMETER_REVIEW_PACKAGE.md` §2,
   alongside rows 14/15/17 which it matches in kind. **What remains
   genuinely unresolved is the review itself** — no expert has yet
   assessed whether these five timings are realistic for a real wearable
   dosimeter's communication link.

8. **Should the Chromium browser-version gap (row 13) be closed before
   any result is reported as final, or is it acceptable to disclose and
   proceed?** This is a methodological, not clinical, decision, but it
   affects how confidently any future number can be reproduced by a
   third party.

9. **Is partial sign-off acceptable** — i.e., can the statistical
   campaign proceed once rows 14/15/17/19 (and whichever others the
   reviewer prioritizes) are resolved, while rows 7–10 (the not-yet-built
   new forecaster and rotation algorithm specifically — not
   `linearForecast`, which already exists and runs but is separately
   unevaluated) and row 18 (no generator yet) remain permanently deferred
   until those features exist? This project's own recommendation
   (`PHASE2C_CORRECTIVE_IMPLEMENTATION.md`) was that rows 14–17 are the
   most urgent (row 19 joining them as of this revision), but whether
   "most urgent" is sufficient for "ready to proceed" is a decision for
   whoever owns the project's scientific sign-off, not something this
   project can decide for itself.

10. **Who holds final sign-off authority** for this registry — a single
    reviewing Medical Physicist/RSO, a panel, or the ICAIRE programme
    itself — has not been specified anywhere in this project's documents.
    This affects how the review table in §8 of the package should
    ultimately be countersigned.

11. **Once a row is marked "Approved" for this synthetic study, what
    (if anything) would later establish that the same value is also
    representative of real occupational exposure, or relevant to
    regulatory compliance — and who decides that a further step is
    needed, versus treating synthetic-study approval as sufficient on
    its own?** This project has stated the distinction (a synthetic-study
    approval is not evidence of real-world representativeness, and is
    not a compliance determination — see the note at the top of
    `SCIENTIFIC_PARAMETER_REVIEW_PACKAGE.md`) but has not specified what
    process, if any, would close that gap, or whether ICAIRE's own
    methodology requires it to be closed before publication.

12. **Resolved as built and run at smoke scale; still open as a question
    of sufficiency: should `linearForecast`'s predictive accuracy be
    evaluated before or independently of building any new forecasting
    model?** This item previously read "nothing currently measures..." —
    an evaluation harness has since been built and run independently of
    any new model (Phase 3A, `phase3a_forecasting/`), confirming that
    scoping choice was workable. It found `linearForecast`'s skill score
    negative at every horizon against simple persistence, for 8 specific
    seeds (`PHASE3A_SMOKE_TEST_REPORT.md` §3). **What remains genuinely
    unresolved** is whether that preliminary, 8-seed result is itself a
    sufficient basis for any reporting, design, or sign-off decision, or
    whether the full ≥30-seed-per-class statistical campaign (§7 of the
    methodology) must run first before the finding can be treated as
    general — this project treats it as preliminary only and has not run
    that campaign, but whether that is the right bar is a decision for
    whoever owns scientific sign-off, not something this project decides
    for itself.

13. **Should the forecasting adapter apply the same Phase-1-to-engine
    baseline rescaling that the detection adapter already applies, before
    computing MAE/RMSE?** Found and verified numerically during this
    documentation round: `phase3a_forecasting/forecast_adapter.py` scores
    `linearForecast` directly against Phase 1's own small provisional
    baseline scale (3–8 µSv/h), never rescaling onto the frozen engine's
    own room baselines (35–92 µSv/h, row 14) the way
    `detection_adapter.rescale_to_engine_baseline` does. A direct
    numerical check this round (rescaling a test series by a factor
    k=22.5 and re-scoring) confirmed MAE/RMSE scale exactly linearly with
    that factor at every horizon, while the skill-vs-persistence score
    already reported in `PHASE3A_SMOKE_TEST_REPORT.md` §3 is unaffected —
    it is a ratio of two quantities that scale identically, so it is
    scale-invariant and numerically identical (to ~12 significant
    figures) whether or not rescaling is applied. **So the skill-score
    comparisons already reported remain valid as relative comparisons**;
    what would need rescaling first is any future reporting of *absolute*
    MAE/RMSE in units meant to represent a realistic room's dose-rate
    scale. Whether to add this rescaling to `forecast_adapter.py` before
    any absolute-unit forecast-accuracy result is reported is undecided,
    and no code change has been made for this finding — see
    `PHASE3A_LIMITATIONS.md` for the full numeric evidence.

14. **What selection method, if any, should replace the illustrative
    `alpha=0.5` for the exponential-smoothing forecasting baseline** (row
    20)? Options not yet chosen between: leave it a fixed, expert-chosen
    value; fit it to simulated or real data; or require a documented
    sensitivity sweep (e.g. 0.1–0.9) to be reported alongside any future
    campaign result, so readers can see how sensitive the baseline
    comparison is to this choice.

15. **Should a longer forecast horizon than `linearForecast`'s hardcoded
    3 samples ever be built, and if so, by what technique** — recursively
    feeding the existing 3-step output back in as new input (uncharacterized,
    not something the frozen engine does anywhere) or a different model
    entirely (row 7, revised)? Separately, and not conditional on that
    question: is a 3-minute-ahead horizon itself sufficient for an RSO's
    early-warning decisions, or is a longer horizon operationally
    necessary regardless of how it would be built?

16. **Resolved as a verified semantic finding; still open as a design
    question: should a genuinely accrued-plus-projected dose quantity
    ever be built for rotation triggering, as new, adapter-only logic —
    separate from reusing the frozen engine's existing
    `CONFIG.doseElevated`/`doseCritical`?** (Row 15; new §3a of
    `PHASE3B_ROTATION_ALGORITHM_DESIGN.md`, Revision 3.) This item
    previously did not exist because the mismatch it describes had not
    yet been found. A read-only audit
    (`PHASE3C_A_DOSE_THRESHOLD_SEMANTIC_AUDIT.md`) verified that the
    frozen engine's own thresholds compare only a fresh, memoryless,
    single-reading 30-minute projection — never an accrued-so-far total.
    The revised CGDTR trigger (Revision 3) now reuses that real quantity
    correctly (clause (b)) and adds a *separate*, newly-defined
    "projected shift total" quantity as new, adapter-only logic
    (analogous in kind to Phase 3A's `forecast_cumulative_dose`, also
    new and adapter-only) for the duty-limit clause (c), rather than
    conflating the two. **What remains genuinely open** is whether this
    new quantity should exist at all for rotation-triggering purposes,
    or whether rotation should rely only on the engine's own,
    already-registered clauses (a)/(b) and leave duty-limit management
    to a separate mechanism entirely.

17. **Is it scientifically and operationally appropriate for one
    rotation trigger to combine clauses owned by two different parts of
    this project** — the frozen engine's own radiation-safety
    thresholds (row 15, clauses (a)/(b) of the revised trigger) and this
    project's own synthetic staffing/duty-limit parameter (row 22,
    clause (c)) — **or should they be kept as two entirely separate,
    separately-reported triggers** (a radiation-safety rotation
    suggestion vs. a duty-limit/scheduling rotation requirement)? Not
    decided by `PHASE3B_ROTATION_ALGORITHM_DESIGN.md` Revision 3, which
    only made the two clauses' different ownership explicit rather than
    choosing between keeping them combined or separating them.

18. **What real-world data sources, if any, exist for rows 21–24**
    (Phase 3C-A's synthetic staffing-roster, duty-limit, procedure-
    boundary-spacing, and sensor-fault-escalation parameters)? Every one
    of these is currently an illustrative round number with "no
    evidence" as its status, in the same style as item 6 above for rows
    1/3/4/5/11/12/14/15/19 — this project has not searched for
    applicable facility staffing/scheduling policy, procedure-duration
    data, or alerting-policy precedent for any of them.
