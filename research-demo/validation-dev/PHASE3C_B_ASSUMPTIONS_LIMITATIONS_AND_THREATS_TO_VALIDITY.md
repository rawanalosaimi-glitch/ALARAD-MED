# Phase 3C-B — Assumptions, Limitations, and Threats to Validity

Consolidates, in one place, every assumption and limitation that bears
on how the rotation-campaign and forecasting-campaign results in
`PHASE3C_B_CAMPAIGN_RESULTS.md` may be read. Nothing here is new
information not already stated somewhere in this project's documents;
this document exists so a manuscript-writing team does not have to
assemble it from a dozen files.

---

## 1. What is, and is not, validated by this round's work

**Is validated (by actually running the code, per `PHASE3C_B_TEST_EVIDENCE.md`):**
- The infrastructure (staffing, exposure/assignment two-layer model,
  worker exclusivity, scheduling, dose attribution, sensor-fault
  escalation) behaves as specified, including under contention
  (simultaneous rotation requests), faults (missing/invalid/frozen/
  delayed sensor data), and edge cases (shift end, zero eligible
  candidates).
- The collective-dose conservation invariant holds, to floating-point
  precision, across every policy and every run in the campaign (not
  merely a unit-test claim -- checked across the full campaign in
  `analyze_rotation_campaign.py`).
- CGDTR's trigger clauses use the correct, separately-owned quantities
  and thresholds (`EngineProjectedTaskDose` vs. `WorkerAccumulatedShiftDose`
  vs. `ProjectedShiftTotalDose`) -- the exact mismatch found in the
  prior round's audit does not recur.

**Is NOT validated by this round's work:**
- That CGDTR, or any rotation policy, reduces *real* occupational dose.
  Every number in the campaign is a property of this project's own
  synthetic exposure model, noise model, and staffing model -- a
  simulated outcome, not a real-world measurement.
- That the provisional parameters (rotation threshold, reference level,
  duty limits, handoff duration, escalation threshold, credential
  coverage, roster size) are clinically or operationally appropriate.
  All remain illustrative and unapproved (see
  `SCIENTIFIC_PARAMETER_REVIEW_PACKAGE.md`).
- That `linearForecast` is, or is not, a good predictor in any general
  sense beyond the specific balanced campaign reported here -- see
  `PHASE3C_B_CAMPAIGN_RESULTS.md` for the actual, exact finding, which
  this document does not pre-judge.

---

## 2. Threats to validity

### 2a. Internal validity (does the simulation do what it claims to do)

- **Mitigated by test evidence**: every mechanism (exclusivity,
  scheduling, dose attribution, trigger math) is covered by unit and
  integration tests that check the mechanism directly, not just its
  aggregate output (`PHASE3C_B_TEST_EVIDENCE.md`).
- **Residual risk**: the live orchestrator (`simulation.py`) is new,
  substantial code written and tested in one round. Its documented
  simplifications (section 4 of `PHASE3C_B_ARCHITECTURE_AND_METHODS.md`)
  are deliberate scope choices, not hidden bugs, but a reader should
  treat the orchestrator's specific behavior (e.g., incident state
  defined via sensor-fault state, simulated RSO acknowledgement as
  "incident cleared") as part of what is being evaluated, not as a
  transparent stand-in for a more detailed future model.

### 2b. Construct validity (do the measured quantities mean what they are reported to mean)

- **Collective dose** (section 7a.3 of `PHASE3B_ROTATION_ALGORITHM_DESIGN.md`)
  is an explicitly simplified, project-internal sum -- not the formal
  ICRP collective-effective-dose concept. Reported as such throughout.
- **"Scenario class"** in this campaign reuses Phase 1's own 13
  archetypes, each originally designed to test *detection*, repurposed
  here to drive room-track exposure for *rotation*. The archetypes'
  event/fault timing was not re-designed with rotation decision-making
  in mind -- a scenario class that stresses detection is not guaranteed
  to be the scenario class that would most stress a rotation policy.

### 2c. External validity (do the results generalize beyond this simulation)

- **Does not generalize to real staffing, real dosimetry, or real RSO
  behavior** -- see `ROTATION_RECOMMENDER_DESIGN_SPEC.md` section 0's
  central caveat, restated here: a simulated reduction in dose does not
  by itself demonstrate real-world effectiveness.
- **Does not generalize beyond the illustrative parameter values used**
  -- the sensitivity analysis (`PHASE3C_B_CAMPAIGN_RESULTS.md` section on
  sensitivity) reports how much the result moves when key parameters
  change, which is itself evidence that the specific reported numbers
  are not independent of those illustrative choices.

### 2d. Statistical validity

- **Run-level independence**: every statistic in
  `analyze_rotation_campaign.py` treats one (seed, archetype) run as
  the unit of independence, never a per-minute or per-event record
  within a run -- `ICAIRE_Simulation_Validation_Methodology.md` section
  7a's pseudo-replication warning, applied here as it was for detection
  and forecasting.
- **Multiple comparisons**: Holm-Bonferroni correction is applied
  across the full family of paired comparisons run together (both the
  dose and fairness comparisons across all policy pairs), not per
  comparison in isolation.
- **Residual risk**: 30 seeds per archetype (where the full campaign
  completed at that scale) is the methodology's own stated minimum,
  not a large sample by general statistical standards -- bootstrap CIs
  and non-parametric tests are used specifically because n is not large
  enough to assume normal-approximation reliability, but a null or weak
  result at this scale should not be read as strong evidence of no
  effect, only as "no effect detected at this scale."

---

## 3. Known simplifications carried over from earlier rounds (not reopened here)

- Personal-mode dosimetry only; area-mode (modeled) workers are out of
  scope for the rotation campaign, same as Phase 2A/3C-A's own scoping
  decision.
- The procedure-vs-room baseline framing question (registry row 16)
  is carried forward, not resolved, by reusing Phase 1's procedure-class
  baseline for each room-track's exposure.
- The Chromium 141-vs-153 version gap (registry row 13) applies to
  every EngineBridge call this round made, exactly as it has for every
  prior phase.

---

## 4. What would need to change before any clinical or regulatory claim could be made

(Restated, not newly invented, from `ROTATION_RECOMMENDER_DESIGN_SPEC.md`
section 0 and `SCIENTIFIC_PARAMETER_REVIEW_PACKAGE.md`'s own framing.)

1. Every provisional parameter in `SCIENTIFIC_PARAMETER_REVIEW_PACKAGE.md`
   (rows 1-24, plus the new trigger parameters in
   `PHASE3C_B_ARCHITECTURE_AND_METHODS.md` section 5) would need expert
   (Medical Physicist/RSO) review and resolution.
2. The exposure, noise, and staffing models would need validation
   against real dosimetry and real staffing/credentialing data, not
   just internal consistency.
3. A real compliance/acknowledgement model would need to replace this
   round's "simulated RSO acknowledgement = incident clears" proxy.
4. None of this round's work performs, or claims to perform, any part
   of that validation.
