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

12. **Should `linearForecast`'s predictive accuracy be evaluated before
    or independently of building any new forecasting model?** Nothing
    currently measures how good its existing early-warning predictions
    actually are against ground truth. That evaluation does not require
    building a new model first, and could be scoped as its own,
    smaller piece of work — whether it should be is undecided.
