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
   11, 12, 14, and 15?** Every one of these is currently a placeholder
   with "no evidence" as its status. This project has not searched for
   applicable manufacturer specifications, regulatory guidance, facility
   survey data, or wearable-sensor failure-rate literature — whether any
   exists, and where, is for the reviewer's own expertise to identify
   (§6 of the review package).

7. **A parameter this review surfaced that is not yet a numbered
   registry row at all: the frozen engine's own sensor-health state
   machine thresholds** (`AlaradSafety.SENSOR_P`: a sensor is marked
   "stale" after 2 missed minutes, "disconnected" after 5, and
   "suspected frozen" after 6 identical consecutive readings at 0.1
   µSv/h resolution). These are, in kind, exactly like rows 14/15 — the
   frozen engine's own illustrative constants, now load-bearing for this
   project's data-quality-layer testing — but were not identified as
   needing registration when rows 14/15/17 were added in Phase 2C. This
   project has not added it as a new registry row in this pass (that
   would be a methodology change beyond what was asked for this task);
   it is flagged here so the gap is not lost. Whether to formally
   register it is itself an open decision.

8. **Should the Chromium browser-version gap (row 13) be closed before
   any result is reported as final, or is it acceptable to disclose and
   proceed?** This is a methodological, not clinical, decision, but it
   affects how confidently any future number can be reproduced by a
   third party.

9. **Is partial sign-off acceptable** — i.e., can the statistical
   campaign proceed once rows 14/15/17 (and whichever others the
   reviewer prioritizes) are resolved, while rows 7–10 (forecasting/
   rotation, not yet built) and row 18 (no generator yet) remain
   permanently deferred until those features exist? This project's own
   recommendation (`PHASE2C_CORRECTIVE_IMPLEMENTATION.md`) was that rows
   14–17 are the most urgent, but whether "most urgent" is sufficient for
   "ready to proceed" is a decision for whoever owns the project's
   scientific sign-off, not something this project can decide for
   itself.

10. **Who holds final sign-off authority** for this registry — a single
    reviewing Medical Physicist/RSO, a panel, or the ICAIRE programme
    itself — has not been specified anywhere in this project's documents.
    This affects how the review table in §8 of the package should
    ultimately be countersigned.
