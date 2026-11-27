# ICAIRE Simulation-Based Validation Methodology — ALARAD v1.2.3

**Status: design document only.** Nothing described here has been
implemented or executed. No code has been written, no new seeds have been
run, and no new forecasting model or rotation algorithm has been built.
(The frozen engine's own `linearForecast` already exists, independently
of this document, and is used operationally for early-warning triggering
— see §0 below; its predictive accuracy has not been scientifically
evaluated, and that is a separate fact from whether a new forecaster has
been built.) This document exists to be reviewed and approved before any
of that work starts, per instruction.

**Revision 2.** Adds: explicit unit/time-integration/personal-vs-area
definitions (§1); a conventional fixed-threshold detection baseline,
separated from the moving-average baseline whose "conventional practice"
label is now explicitly unevidenced (§4a); false-alarms-per-worker-shift,
event-level detection delay, and degenerate-scenario handling (§5);
operational constraints for worker rotation — procedure continuity,
eligibility, handoff safety, fairness (§6, expanded from Revision 1's
single bullet list); a consolidated parameter registry (§9); explicit
handling of correlated observations within a simulated shift for
uncertainty/CI purposes (§7a). Revision 1's content is otherwise preserved,
renumbered as noted inline.

**Revision 3 (Phase 2C item 6).** Adds Parameter Registry rows 14–18
(§9), registering the frozen engine's own `baselineRates` and `CONFIG`
thresholds, its default immediate-alert policy, the physical coherence of
rescaling Phase 1's procedure-class framing onto the engine's room-based
framing, and the realism of scenario dynamics (S10/S11) not yet
reproducible against the engine — all found during
`PHASE2B_INTEGRATION_AUDIT.md` and `PHASE2C_CORRECTIVE_IMPLEMENTATION.md`,
none previously tracked as scientific assumptions despite being load-
bearing for Phase 2A/2C's adapter. No other section is changed in this
revision; everything else from Revision 2 is preserved as-is.

**Revision 4 (documentation-only correction).** Adds Parameter Registry
row 19, registering `AlaradSafety.SENSOR_P` (the frozen engine's own
sensor-health state-machine timing thresholds) — identified as a gap of
exactly the same kind as rows 14/15 while preparing
`SCIENTIFIC_PARAMETER_REVIEW_PACKAGE.md`, and not previously registered.
Tightens the Status note above and this document's framing elsewhere so
"no forecasting has been built" cannot be misread as "no forecasting
code exists at all" — `linearForecast` exists in the frozen engine
(unchanged fact, already stated correctly in §0 below since Revision 1);
what remains true is that its predictive accuracy is unevaluated and no
new forecaster has been built for this research framework. Adds an
explicit note, immediately before §9's table, that a reviewer's approval
of a provisional value for this synthetic simulation study is not
evidence that the value is representative of real occupational radiation
exposure, and that expert approval alone does not establish external
validity or regulatory compliance — both already implicit in this
document's repeated "illustrative, not validated" language, now stated
as one explicit, unmissable rule rather than left to be inferred. No
parameter value, implementation code, or other section's substantive
content is changed in this revision.

**Revision 5 (documentation-only; Phase 3A follow-up).** Corrects §5's
dose-forecasting row and Parameter Registry row 7: the frozen
`linearForecast` function was empirically confirmed (Phase 3A,
`PHASE3A_LIMITATIONS.md` §1) to always return exactly 3 future samples
regardless of input length, so the previous "two horizons (next-minute
and a longer horizon, e.g. 15 minutes)" language was not describing an
open placeholder but misdescribing the function's hard limit. §5 now
describes the evaluation actually performed — 1-, 2-, and 3-minute-ahead
MAE/RMSE/MAPE, the only horizons the real function produces — and states
explicitly that any longer horizon (15 minutes included) is a distinct,
not-yet-built capability, not a parameter value waiting to be filled into
the existing function. Row 7 is reframed accordingly, from "what 15-minute
value to pick" to "whether and how any longer horizon could ever be
reached given this limit." Adds Parameter Registry row 20, registering
the Phase 3A exponential-smoothing baseline's `alpha=0.5` as a
provisional, non-data-driven illustrative choice requiring a future
sensitivity analysis before its comparison results can be treated as
more than illustrative. No code was written or run to produce this
revision; every finding cited was already established and verified in
Phase 3A's own deliverables (`PHASE3A_LIMITATIONS.md`,
`PHASE3A_SMOKE_TEST_REPORT.md`), re-checked again while writing this
revision.

**Revision 6 (documentation-only; Phase 3C-A follow-up).** Registers
Parameter Registry rows 21–24, the new synthetic provisional parameters
introduced by Phase 3C-A's rotation-simulation infrastructure (staffing
roster generation, duty limits, procedure-boundary spacing, and the
sensor-fault escalation threshold — none of them read, derive from, or
affect anything in the frozen v1.2.3 release). Updates row 9's status
to record that an illustrative value (10 minutes) now exists in code
for testing purposes, while leaving the row open and unapproved, exactly
as every other illustrative value in this registry is treated. No row's
prior content is deleted; row 9's update is additive, marked inline. See
`PHASE3C_A_DOSE_THRESHOLD_SEMANTIC_AUDIT.md` and
`PHASE3B_ROTATION_ALGORITHM_DESIGN.md` (Revision 3) for the related,
separate finding that `PHASE3B_ROTATION_ALGORITHM_DESIGN.md` section
3a's dose-trigger formula had misdescribed how the frozen engine's own
`CONFIG.doseElevated`/`doseCritical` (row 15) are actually computed —
that correction is made in `PHASE3B_ROTATION_ALGORITHM_DESIGN.md`
itself, not in this methodology document, because row 15's own text
here was already accurate (it describes the thresholds and the 30-
minute horizon generically, without asserting the incorrect accrued-
plus-projected semantics); nothing in row 15 required correction. No
code was written or run to produce this revision.

**Branch:** `research/icaire-v123-validation` (this file). No other branch
was touched. The frozen `research-demo/releases/html/ALARAD_Prototype_Research_Demo_v1.2.3.html`
(SHA-256 `92e897dd0ff1738f083df829b53f7f46377e042b7019bb9776232792261182ee`)
was not opened for writing at any point while producing this revision.

**Grounding:** every claim below about what v1.2.3 currently does or does
not do is taken from the three documents already in this directory
(`Verification_Rerun_Report.md`, `Ground_Truth_Scenarios_S1-S13.md`,
`Gap_Checklist.md`) and from source lines re-checked directly in the frozen
HTML (cited by line number below). Nothing here claims a capability of
v1.2.3 that wasn't actually found there, and nothing here asserts a
baseline "represents conventional practice" without flagging that claim as
unevidenced and registered for expert review.

---

## 0. What v1.2.3 already has, and what this methodology adds

This matters because several requested items (forecasting-baseline
comparison, rotation-recommendation evaluation) can be misread as "evaluate
the existing feature." They are not that. Re-checking the frozen source:

| Capability | Exists in v1.2.3? | Evidence |
|---|---|---|
| Rule-based, stateless-per-minute anomaly detection with a confirmation window | **Yes** | `matchEvents()`/`metrics()`, independently verified in `Verification_Rerun_Report.md` |
| A linear-regression forecast (`linearForecast`, last-4-readings OLS extrapolation) | **Yes**, but only as an internal *early-warning* signal inside the Simulation Lab/anomaly-detection tool, not as a dose forecast that is itself evaluated against ground truth | Line 1172: "**Prediction** = linear extrapolation of the last 4 readings... projecting a deviation at or above the elevated threshold within 3 minutes" |
| Worker-rotation *recommendation generation* (an algorithm that decides who should rotate, based on dose/risk) | **No.** The four "AI Recommendation" entries are static, hand-written example text | Line 1706: "a static, hand-written illustrative example entry for this prototype — it was not generated by the live detection engine or by any forecast"; lines 1541–1542 are literal hand-authored strings |
| A device-handoff "rotation" feature | **Yes, but it is a manual UI action, not a recommender** — `rotateDevice()` just re-binds a device ID to a different worker when a human clicks a button; it does not decide *who* should rotate or *when* | Lines 861–880, 1604–1612 |

**Consequence for this methodology — preserved through every section below,
not only here:**
- **Track A — evaluate what exists:** anomaly detection, the internal
  linear forecast (evaluated as a forecaster for the first time), and the
  dose-accounting unit conventions (§1), all against the existing
  engine/matching framework, extended to a statistically adequate sample.
  This needs no new algorithm.
- **Track B — define, for later implementation, how a not-yet-built
  rotation recommender would be evaluated.** A specification, not a
  result. No rotation algorithm is implemented here. (Dose forecasting was
  Track B in Revision 1's framing in one place and Track A in another;
  this revision fixes that: forecasting is Track A throughout, because
  `linearForecast` already exists — only rotation recommendation is
  genuinely unimplemented, so only rotation is Track B.)

Every new section added in this revision is tagged **(Track A)** or
**(Track B)** in its heading so the distinction stays visible throughout,
not only in this section.

---

## 1. Definitions: dose-rate units, cumulative dose, time integration, personal vs. area monitoring (Track A — documents the existing engine as built)

These definitions are not proposed; they are extracted from the existing
v1.2.3 engine exactly as it already computes and labels these quantities
(line 1170, one long in-page note), so that every later section's metrics
are stated in units that match what the engine actually does, rather than
generic placeholders.

- **Dose rate:** microsieverts per hour, **µSv/h**. This is the unit every
  simulated reading (personal or area) is generated and reported in.
- **Cumulative dose:** millisieverts, **mSv**. Accumulated by the engine's
  own stated rule: *"Incremental dose per step: Dose (mSv) = Dose Rate
  (µSv/h) × Duration (h) / 1000, with each reading held constant over its
  minute; accumulated dose is the running sum."* (line 1170). The
  dashboard's existing "Dose Summary" card reports this same mSv unit at
  four accumulation horizons: Today, This Week, This Month, This Year —
  these horizons are reused as-is for any reporting under this
  methodology; no new accumulation horizon is introduced.
- **Time integration:** 1-minute steps. In the existing 60-minute
  Simulation Lab window this is *"Time step = 1 minute, 60 steps per
  scenario"* (line 1170), with each step's reading held constant over that
  minute before being summed. The widened shift lengths proposed in §2
  (4h/8h/12h) reuse this exact per-minute step-and-sum rule over more
  steps — the integration rule itself does not change, only the number of
  steps integrated.
- **Projection horizon (distinct from a forecast):** the engine's existing
  "projected task dose" is *"the current rate held constant for 30 minutes
  — not a trend forecast"* (line 1170). This is explicitly **not** the
  same thing as the `linearForecast` extrapolation evaluated in §4b — the
  two must not be conflated in reporting. "Projected task dose" is a
  constant-rate projection used for dashboard risk display; `linearForecast`
  is a trend-based extrapolation used for early-warning detection. Both
  exist in v1.2.3 today; this methodology evaluates the latter as a
  forecaster (§4b, §5) and treats the former only as a display convention,
  out of scope for forecast-accuracy scoring.
- **Personal vs. area monitoring — MEASURED vs. MODELED:**
  - **Personal dosimeter mode:** the reading is a **direct, measured**
    value from the worker's own device. *"Measured personal-dosimeter
    readings are used as is"* (line 1170).
  - **Area-monitor mode:** the reading comes from a fixed monitor, not the
    worker's own device, and is converted by the engine into a **modeled**
    worker-position estimate: *"reading × (reference distance ÷ worker
    distance)² × shielding; distance and shielding are applied only to
    area readings"* (line 1170) — i.e., an inverse-square-law point-source
    approximation. *"Measured and modeled values are stored and plotted
    separately"* (line 1170) and must remain labeled as such (`badge.measured`
    vs. `badge.modeled` in the existing UI) in any evaluation output this
    methodology produces — a modeled estimate must never be reported or
    scored as if it were a direct measurement.
  - **Explicit limitation, already self-disclosed by the engine:**
    *"Inverse-square scaling is only a limited point-source approximation;
    scatter in real rooms does not follow it"* (line 1170). Carried forward
    into §10's limitations and §9's parameter registry (row 12) rather than
    restated as new.
  - **Invalid-reading rule (reused, not new):** *"Readings that are
    missing, negative, not finite or above 1,000,000 µSv/h are rejected
    before the engine and add no dose"* (line 1170) — this is the existing
    rule already exercised by the `invalid` fault kind in S9/S12
    (`Ground_Truth_Scenarios_S1-S13.md`), restated here as a unit-level
    validity bound rather than re-derived.

---

## 2. Radiation exposure simulation — workers, rooms, procedures, shifts (Track A)

*(Renumbered from Revision 1 §1; content unchanged except cross-references.)*

**Reuse, not replace.** The existing scenario generator (`SCEN`/`SC` arrays,
`Ground_Truth_Scenarios_S1-S13.md` §§S1–S13) already parameterizes: a worker
id, a room, a `procMult` (procedure-dependent rate multiplier, currently
fixed at `1.0` in all 13 hand-authored scenarios), a measurement mode
(`personal` or `area`, per §1's MEASURED/MODELED distinction), a pattern
(`flat`/`ramp`/`step`/`spikes`), and a seed. The proposed simulation design
keeps this exact object shape and exact seeded-RNG mechanism, and widens
three dimensions that are currently fixed constants in the hand-authored
set:

| Dimension | Current v1.2.3 (hand-authored S1–S13) | Proposed for the evaluation sample |
|---|---|---|
| Procedure multiplier (`procMult`) | Fixed at `1.0` in every scenario | Drawn per-run from a small, explicitly justified set of procedure classes (e.g., diagnostic fluoroscopy, interventional cath lab, CT, PET/CT), each with its own multiplier range — **range values require RSO/medical-physicist sign-off before use; none are proposed here as final** (Parameter Registry §9, row 1) |
| Shift / window length | Fixed at 60 minutes (one hour, matching the Simulation Lab's fixed 60-step loop; see §1's time-integration rule) | Drawn from a small discrete set (e.g., 1 h / 4 h / 8 h / 12 h) to test whether detection/forecast performance degrades on longer, lower-event-density windows (Parameter Registry §9, row 2) |
| Room/worker count per run | 1–3 workers per scenario, fixed assignment | A multi-worker roster per run (reusing the existing per-worker independence already validated in S6/S12), with room assignment randomized but seeded |

**What does not change:** the underlying per-minute rate-generation
mechanism (`seededSeries`-style noise around a baseline, inverse-square
modeling for area-mode workers per §1, the four pattern types) is reused
exactly as implemented and verified — this proposal is about *sampling
that mechanism more broadly and more times*, not about replacing it with a
different simulator. Replacing the underlying physics/noise model is out
of scope; this is a validation-methodology document, not a re-engineering
proposal.

---

## 3. Ground-truth injection — radiation anomalies and sensor failures (Track A)

*(Renumbered from Revision 1 §2; content unchanged except cross-references.)*

**Reuse, not replace.** The existing `truth` (radiation events) and
`faults` (sensor failures: `missing`/`invalid`/`frozen`/`delayed`, per §1's
invalid-reading rule) arrays, and the dual-layer `matchEvents()` scoring
already verified for S1–S13, are the ground-truth mechanism. The proposal
is to generate these programmatically per seed instead of hand-authoring 13
fixed cases:

- **Event taxonomy** (reused as-is): `ramp`, `step`, `spikes` — each with a
  start time, magnitude multiplier, and duration drawn from a declared
  range (not yet chosen — Parameter Registry §9, row 3).
- **Fault taxonomy** (reused as-is): the four existing fault kinds, with
  timing/duration/magnitude likewise drawn from a declared range rather
  than the 13 fixed windows currently hand-picked (e.g., S7's fixed 25–40,
  S10's fixed 15–50) (Parameter Registry §9, row 4).
- **Formal ground-truth record schema**, generated alongside each
  simulated run (not stored only in hand-written scenario objects):
  `{run_id, seed, worker_id, truth_events:[{start,end,label}], fault_events:[{kind,start,end,params}]}`.
  This is a data-shape proposal only; it is the same information the
  existing engine already produces per scenario, made systematic instead of
  one-off.
- **What does not change:** the matching algorithm (`matchEvents()`, grace
  period, TP/FP/FN/precision/recall/F1 via `metrics()`) is reused exactly as
  verified — no new scoring logic is proposed.

---

## 4. Comparison against conventional threshold alerts and forecasting baselines

### 4a. Detection baselines (Track A — existing detector, new comparators)

| Baseline | Description | Status |
|---|---|---|
| **Baseline 0 — "always normal"** | Never alerts. A sanity floor: establishes the base rate of true events per scenario class, and gives every other method's recall a non-trivial denominator to beat. | To be implemented as a trivial comparator, not an "algorithm" |
| **Baseline 1 — ALARAD's own detector, confirmation window ablated to K=1** | Reuses ALARAD's own tuned threshold constants; only the confirmation-window requirement is removed. Already produced as one row of the existing `ref_sweep.py` grid (confirmation window = 1). This is an **internal ablation**, not an independent reference — it does not represent "conventional practice," it represents ALARAD minus one of its own features. | **Reuse directly** — no new code, just re-select this slice of the existing sweep output |
| **Baseline 2 (new in Revision 2) — conventional fixed-threshold alarm** | An **independently-specified** reference, deliberately *not* derived from ALARAD's own tuned threshold constants: an instantaneous per-reading comparison against a fixed multiple of baseline, no averaging window, no confirmation requirement — representing the simplest physical radiation/dosimeter alarm design (the kind built into many commercial area and personal alarm devices). The specific fixed-multiple value used must come from a citable source (a manufacturer specification, or published regulatory alarm-setpoint guidance) — **no value is chosen here**; see Parameter Registry §9, row 5. | New reference implementation; threshold value pending evidence, not pending engineering |
| **Baseline 3 (was "Baseline 2" in Revision 1) — moving-average threshold reference** | A second, more adaptive reference implementation (fixed-window moving average crossing a fixed multiple of baseline). **Revision 1 described this as representing "what a non-ALARAD, off-the-shelf threshold alarm would do" — that characterization is withdrawn in this revision.** It is now described only as *an additional engineered reference point*; whether it is representative of any established conventional practice is an open question requiring a citation (Parameter Registry §9, row 6), and until that evidence exists it must not be labeled "conventional" in any paper draft. | New; conventional-practice label explicitly not asserted |
| **Candidate — ALARAD's confirmation-window detector at its documented operating point** | The existing engine, as verified. | Already implemented; no change |

This gives four points of comparison, not three: a floor (Baseline 0), a
literal ablation of ALARAD's own confirmation-window feature (Baseline 1),
an independently-specified fixed-threshold reference that is the closest
candidate this document has for "conventional practice" — pending the
evidence in Parameter Registry row 5 (Baseline 2), and a second adaptive
reference whose conventional-practice status is explicitly unresolved
(Baseline 3), rather than only comparing ALARAD against itself, and rather
than asserting any reference "is conventional" without a source.

### 4b. Forecasting baselines (Track A — the existing internal forecast, evaluated as a forecaster for the first time)

| Baseline | Description |
|---|---|
| **Persistence (naive)** | Forecast = last observed value. Standard minimum baseline for any time-series forecast claim. |
| **ALARAD's existing `linearForecast`** | OLS on the last 4 readings, as already implemented (and distinct from the "projected task dose" constant-rate projection defined in §1) — evaluated here as a forecaster in its own right (predicted value vs. the simulator's known true future value), which the current engine does not do; today it is only used as an early-warning trigger, not scored for forecast accuracy. |
| **Simple exponential smoothing** | A second, slightly less naive reference baseline, for a three-point comparison analogous to §4a. No "conventional practice" label is claimed for this baseline either, consistent with the correction made to Baseline 3 above. |

**Leakage note (previewed here, detailed in §8):** because this is
simulation, the true future value is always known — that must not leak into
the forecast input. Each forecaster sees only data strictly before its
prediction horizon; the true value is used only afterward, for scoring.

---

## 5. Evaluation protocol per capability (Track A for detection/forecasting; Track B for rotation — see §6)

| Capability | Track | Metrics | Ground truth source |
|---|---|---|---|
| Anomaly detection | A | Precision, recall, F1, **event-level** detection delay (see §5a), **false alarms per worker-shift** (see §5a) | `truth` arrays, existing `matchEvents()` |
| Data-quality/sensor-fault detection | A | Same metric set, independently, per §2 of `Ground_Truth_Scenarios_S1-S13.md` | `faults` arrays, existing dual-layer matching |
| Dose forecasting | A | MAE, RMSE, MAPE at the 1-, 2-, and 3-minute-ahead horizons the frozen `linearForecast` actually produces — it hardcodes exactly three future samples regardless of input length, verified empirically for input lengths 3/4/7/10 (`PHASE3A_LIMITATIONS.md` §1; Parameter Registry §9 row 7, revised in Revision 5) — compared across the three §4b baselines, reported in the mSv/µSv-h units defined in §1. **A longer horizon (e.g. 15 minutes) is a separate, not-yet-built capability, not a parameter of this evaluation**: reaching it would need either a recursive/cascading use of the 3-step output as new input (not something the frozen engine does anywhere, and whose compounding uncertainty is uncharacterized) or a different forecasting function entirely — both out of scope until a future phase decides to build one | The simulator's own known true future series (simulation-only; not available with real sensors, a limitation noted in §10) |
| Rotation recommendation | B — specification only | The criteria and constraints in §6 | Not applicable yet — no run has been performed |

### 5a. Metric definitions requiring explicit convention (new in Revision 2)

- **False alarms per worker-shift:** total false-positive count across a
  set of runs, divided by the total number of worker-shifts included in
  that set (one worker's participation in one run = one worker-shift).
  Reported per scenario class and pooled overall. This normalizes for
  exposure: a run with more workers or a longer shift (§2's widened shift
  lengths) naturally has more opportunities to false-alarm, so a raw FP
  count alone would make longer/larger runs look disproportionately worse
  without this normalization.
- **Event-level detection delay:** for each true event that is matched to a
  detection (a true positive), delay = (minute of first flag within the
  grace window) − (true event's start minute). This is computed **per
  matched event**, not per run and not per minute. Reported as a
  distribution (median and interquartile range) per scenario class, not
  only a mean — detection delay is not expected to be symmetric or
  normally distributed (e.g., S10's frozen-sensor case has no delay value
  at all because the event is missed by design, per
  `Ground_Truth_Scenarios_S1-S13.md`). An undetected event (a false
  negative) contributes no delay value to this distribution — it is
  excluded from the delay statistic and counted separately in recall, so
  that missed events cannot be mistaken for "detected instantly" or
  silently dropped from reporting.
- **Handling scenarios with no true events or no alerts (degenerate
  cases):** several existing scenarios have zero true radiation events
  (S1, S5, and the "no radiation event" workers inside S7/S12), and a
  method under test may, correctly or incorrectly, issue zero alerts on
  any given run.
  - If a run has zero true events and zero false positives: **recall is
    undefined (0/0)**, not 0 or 1 — it must be reported as undefined and
    **excluded** from the aggregate recall mean/median for that scenario
    class, not coerced to a number. The run still correctly contributes a
    **0** to the false-alarm-per-worker-shift numerator, so its
    "successfully stayed quiet" result is not lost.
  - If a run has zero true events and the method issues ≥1 false alarm:
    **precision is 0** (defined, TP+FP > 0) and recall remains undefined
    (excluded as above); the false alarm(s) are counted in the
    false-alarm-per-worker-shift metric.
  - If a run has ≥1 true event and the method issues zero alerts: all
    true events become false negatives; **precision is undefined (0/0)**
    and excluded from the aggregate precision statistic; **recall is 0**
    (defined).
  - This convention (exclude undefined ratios from their respective
    aggregate statistic rather than coercing to 0, while still routing
    every run's false-positive count into the false-alarm-per-worker-shift
    metric) prevents zero-event scenarios from silently dropping out of
    the report while also preventing undefined values from artificially
    inflating or deflating precision/recall means.

---

## 6. Worker-rotation evaluation protocol (Track B — specification only; no algorithm implemented)

*(Expanded in Revision 2 from Revision 1's single §3c bullet list; "no
algorithm exists or is proposed for implementation" still applies
throughout this section.)*

No rotation-recommendation algorithm exists in v1.2.3 (§0) and none is
implemented here. This section specifies the protocol a future recommender
would have to pass, including hard operational constraints a candidate must
satisfy before it is even scored — defined now, pre-registered, so the bar
cannot be quietly lowered later to fit whatever gets built.

### 6a. Reference rule

Not an "AI," a fixed policy standing in for "what the static illustrative
recommendations in v1.2.3 would amount to if made automatic": rotate a
worker out when projected cumulative dose (§1's mSv accumulation rule)
crosses a declared fraction of the reference level — the same logic already
present as prose in the two existing hand-written recommendation strings
(lines 1541–1542), made mechanical.

### 6b. Operational constraints (new in Revision 2) — hard eligibility filters

A candidate recommendation that violates any of these is **invalid**,
regardless of how well it scores on §6c below:

1. **Procedure continuity:** a rotation must not be recommended while the
   affected worker is mid-procedure. A recommendation may only take effect
   at a declared procedure boundary (end of procedure, or an explicit
   emergency-override flag, itself subject to RSO review) — never
   mid-procedure.
2. **Worker eligibility:** the proposed replacement worker must be (a)
   credentialed for the target room/procedure type, (b) not already at or
   near their own projected dose or duty-time limit, and (c) not currently
   the subject of an open, unresolved data-quality incident of their own
   (reusing the existing S7–S13 incident-state concept). **No real or
   synthetic credentialing/staffing dataset currently exists anywhere in
   this project** — this constraint cannot be exercised in simulation until
   such a model is added, which is itself an open item (Parameter Registry
   §9, row 8), not assumed available.
3. **Handoff safety:** a minimum handoff/briefing duration must elapse
   between a recommendation and the swap taking effect — a rotation is
   never instantaneous. No rotation may be recommended during an open
   radiation incident window without explicit RSO acknowledgement, reusing
   the existing S8 precedent that an incident "stays open through
   disconnect" and is never silently auto-closed — a rotation recommendation
   must not be allowed to silently interfere with or close an open
   incident either. The exact handoff duration is an open parameter
   (Parameter Registry §9, row 9), not chosen here.
4. **Workload fairness, measured across time, not only at the end:**
   fairness is evaluated both (a) at end-of-shift, via variance of
   cumulative dose across the roster (Revision 1's original criterion,
   retained as §6c.2 below), and (b) as a trajectory-level measure
   sampled at multiple points across the shift (e.g., a Gini coefficient or
   a max–min ratio of cumulative dose, not only the final snapshot) —
   because a recommender could equalize end-of-shift dose while still
   leaving one worker exposed far longer mid-shift, which an end-only
   snapshot would not catch. Fairness of the **rotation burden itself** is
   also required: no single worker should be recommended for rotation
   disproportionately more often than peers across the evaluation sample.

### 6c. Scoring criteria (applied only to candidates that already satisfy §6b)

1. Reduction in cumulative dose at end of shift vs. no rotation.
2. Fairness — end-of-shift dose variance (Revision 1's original criterion)
   **and** the trajectory-level and rotation-burden fairness measures from
   §6b.4.
3. Time-to-recommendation latency.
4. Number of rotations recommended per shift (a cost; more rotations is not
   free).
5. **(New) Constraint-violation rate:** the fraction of a candidate
   recommender's outputs that fail any §6b constraint. A recommender that
   scores well on criteria 1–4 while frequently violating §6b constraints
   is not a valid candidate — this rate must be reported alongside the
   other four, not treated as a separate pass/fail gate reported
   elsewhere.

These criteria and constraints are a specification to be reviewed
(Parameter Registry §9, row 10), not a result — nothing in this section has
been implemented, scored, or tested against any recommender, because no
recommender exists.

---

## 7. Scientific metrics, statistical analysis, and seed count

*(Renumbered from Revision 1 §5; content retained, with §7a added for
correlated observations per request.)*

**Minimum 30 independent seeds per scenario class**, not 30 seeds total.
There are 13 scenario archetypes (S1–S13); treating each as its own class
(since they test materially different mechanisms — ramp vs. step vs.
multi-worker vs. each of the four fault kinds) gives a minimum evaluation
sample of **13 × 30 = 390 independent runs**, each with its own fresh seed,
none of which may be one of the 13 original hand-authored seeds (20260601
through 20260613) — those 13 are reserved as the **design set** (§8) and
must never be counted in the statistical sample.

- **Per-class summary statistics:** mean and median precision/recall/F1 (and
  forecast MAE/RMSE/MAPE), with 95% confidence intervals computed by
  bootstrap resampling (appropriate given n=30 per class — not large enough
  for normal-approximation CIs to be assumed reliable without checking),
  computed at the **run level** per §7a below, never pooled across
  correlated sub-observations.
- **Paired comparison across methods:** for each scenario class, the
  candidate detector/forecaster and each baseline are run on the *same* 30
  seeds (paired design), so a paired test (e.g., Wilcoxon signed-rank,
  non-parametric and robust to the non-normal distributions these metrics
  typically have) is used rather than an unpaired test.
- **Multiple-comparison correction:** with 13 scenario classes × up to 4
  baselines per capability (§4a now has four, §4b has three), a
  Holm–Bonferroni correction is applied across the family of comparisons
  being reported together, so the paper does not overstate significance
  from running many tests.
- **Effect sizes, not just p-values:** report the absolute precision/
  recall/F1/MAE differences alongside any significance test — a
  statistically significant but practically tiny difference should not be
  reported as if it were operationally meaningful.

### 7a. Correlated observations within a simulated shift (new in Revision 2)

The unit of statistical independence in this methodology is **the run**
(one simulated shift, one seed) — never the individual minute, and never
the individual matched event within a run.

- **Why:** every reading within one run is generated from the same seeded
  noise realization and the same room/procedure/roster assignment. For the
  multi-worker rosters widened in §2, multiple workers and multiple events
  inside a single run are therefore correlated by construction, not
  independent draws — they share the run's seed and context.
- **Consequence for aggregation:** per-run metrics must be computed
  **first** — one precision/recall/F1/MAE value (or, for a multi-worker
  run, one within-run aggregate across that run's workers) per run — and
  only those per-run values are treated as the i.i.d. sample across the
  ≥30 seeds per class for the bootstrap CIs and paired tests above. Pooling
  raw per-minute or per-event records across runs and bootstrapping those
  directly would be pseudo-replication: it treats correlated observations
  as independent and produces confidence intervals that are too narrow,
  overstating precision of the estimate.
- **Cluster bootstrap:** any resampling below the per-run level (e.g., for
  a secondary or exploratory analysis) must resample whole runs as the
  cluster unit, never individual minutes or events within a run — standard
  cluster/block-bootstrap practice, applied here because "cluster" =
  "simulated shift."
- **Interaction with widened shift length (§2):** a longer simulated shift
  (4h/8h/12h) produces many more per-minute observations per run than the
  original 60-minute design, but this does **not** increase the number of
  independent observations — it only adds more correlated detail inside
  the same single run. The sample size that determines statistical power
  remains the **seed count per class** (≥30), not the number of minutes
  simulated. Any paper draft using this methodology must state this
  explicitly, to avoid implying a larger effective sample size than
  actually exists.

---

## 8. Leakage-free evaluation and sensitivity testing

*(Renumbered from Revision 1 §6; content retained, with one added
cross-reference to §7a's run-level unit of independence.)*

**Three-way seed separation** (the core anti-leakage control, applied at
the run level, consistent with §7a):

1. **Design set** — the 13 original hand-authored scenarios and seeds
   (20260601–20260613). These informed the existing engine's thresholds and
   behavior during its original development and are documented in
   `Ground_Truth_Scenarios_S1-S13.md`. They may continue to be used for
   illustration, regression testing, and the software-verification suites
   already covered in `Verification_Rerun_Report.md` — but **must never be
   reused as the statistical evaluation sample**, because the engine's
   existing behavior is already known to pass them; doing so would be
   circular.
2. **Tuning set** — a separate block of freshly seeded runs (count to be
   fixed before implementation, e.g. 10 seeds per class), used only if any
   baseline implementation needs a parameter choice (e.g., the moving-average
   window length for Baseline 3, or the fixed threshold for Baseline 2, in
   §4a). Any such choice is frozen after tuning and never revisited after
   seeing evaluation-set results.
3. **Evaluation set** — the ≥390 freshly seeded runs from §7, used only
   once, only for the final reported metrics. No parameter in any detector,
   forecaster, or baseline may be changed after evaluation-set results are
   seen; doing so and re-running would itself be a leakage violation.

**Forecast-specific leakage control** (per §4b): at every scored time step,
a forecaster receives only observations with timestamps strictly earlier
than the prediction target; the simulator's true generating parameters
(e.g., the exact ramp slope used to create the data) are never exposed to
any forecaster, only to the scorer, after the fact.

**Sensitivity testing:** extend the existing `ref_sweep.py` methodology
(already verified to independently reproduce 8,640 runs / 432 grid cells
across confirmation window K, noise level, and alert threshold) to the new
evaluation set, so performance is reported as a stability surface across
detector settings, not a single cherry-pickable operating point. Any claim
of "ALARAD detects X% of events" must be accompanied by how that figure
moves across the sweep grid, exactly as the existing sweep already does for
the design set.

**Reproducibility controls carried over from the verification stage:**
fixed, published seed lists (committed to the repository, not regenerated
ad hoc); explicit disclosure of the Chromium/browser-engine version used
for any suite that drives a real browser (per the version caveat already
recorded in `Verification_Rerun_Report.md`); SHA-256 of whatever file is
actually evaluated, recorded alongside every reported number.

---

## 9. Parameter registry — every unresolved scientific assumption in this document (new in Revision 2)

Every open parameter referenced above, in one place, so none can be quietly
fixed later without the review this table calls for.

**What a reviewer's sign-off on a row means, and does not mean (Revision
4):** an "Approved" mark against a row means *"this value is a
reasonable, internally-consistent choice for the purposes of this
synthetic simulation study."* It does **not** mean, and must never be
cited as meaning, that the value is representative of real occupational
radiation exposure, that it has been validated against real dosimeter or
survey data, or that it establishes regulatory compliance with ICRP,
NRRC, or any other authority. Expert approval of a provisional parameter
for a synthetic study and evidence of that parameter's real-world
representativeness are two different claims; resolving a row in this
table only ever settles the first.

| # | Parameter | Used in | Current status | Proposed evidence source | Expert approval required? |
|---|---|---|---|---|---|
| 1 | Procedure-class taxonomy and multiplier ranges | §2 | Open — illustrative class names only, no ranges chosen | RSO / medical-physicist consultation; facility procedure logs, if available | **Yes** |
| 2 | Shift-length set (1h/4h/8h/12h) | §2 | Open — illustrative set only | Facility staffing/shift-policy documentation | **Yes** (facility policy) |
| 3 | Event (ramp/step/spike) magnitude & duration sampling ranges | §3 | Open | Domain input; published incident-magnitude data if any exists | **Yes** |
| 4 | Fault (missing/invalid/frozen/delayed) timing/duration sampling ranges | §3 | Open | Domain input; wearable-sensor failure-rate literature if any exists | **Yes** |
| 5 | Conventional fixed-threshold alarm setpoint (Baseline 2) | §4a | Open — no value chosen | Manufacturer alarm specification, or published regulatory alarm-setpoint guidance | **Yes** |
| 6 | Characterization of the moving-average baseline (Baseline 3) as "conventional practice" | §4a | Explicitly **not asserted** pending evidence | A citation to an industry standard or published description of commercial dosimetry alarm logic | **Yes — required before this label may be used in any paper draft** |
| 7 | Forecast horizon beyond the 3 samples `linearForecast` actually produces (previously an unexamined placeholder "15 minutes") | §5 | **Revised in Revision 5**: the 3-sample limit is now empirically confirmed, not an open placeholder value (`PHASE3A_LIMITATIONS.md` §1, `test_forecast_contract.py::test_linear_forecast_always_returns_exactly_three_future_points`). What remains genuinely open is whether a longer horizon should ever be built at all, and if so *how* — recursively feeding the existing 3-step output back in, or a different model — not merely *what number of minutes* | Clinical/operational input on what horizon would be actionable for an RSO, **and** a methodological decision on the technique by which any longer horizon would be reached, before this row can be resolved | **Yes** |
| 8 | Worker eligibility / credentialing data model | §6b.2 | Does not exist, synthetic or real | Facility staffing/credentialing policy, or a synthetic model built with RSO input | **Yes** |
| 9 | Minimum handoff/briefing duration | §6b.3 | Open. **Revised in Revision 6**: Phase 3C-A now uses an illustrative value of **10 minutes** (`phase3c_rotation_infra/config/phase3c_config.json`, block `handoff`) purely to exercise the timeline/scheduling machinery in tests — the row remains open and unapproved; no sensitivity sweep has been run on this value | Facility handoff-safety policy, or published radiation-safety workflow guidance | **Yes** |
| 10 | Rotation-recommendation scoring weights/thresholds across §6c criteria | §6c | Open | ICAIRE methodology reviewers + RSO | **Yes** |
| 11 | Synthetic noise model realism (±5% baseline noise, as implemented in v1.2.3) | §1 / existing engine | Inherited from v1.2.3, unverified against real dosimeter noise | A real wearable-dosimeter noise-characterization study (not currently available) | **Yes, if ever claimed representative of real sensors** |
| 12 | Inverse-square point-source approximation acceptability for area monitoring | §1 / existing engine | Inherited from v1.2.3, self-disclosed in-engine as limited | Health-physics literature on area-monitor geometry corrections | **Yes, if used beyond illustrative purposes** |
| 13 | Chromium 141-vs-153 browser-version gap in verification reruns | `Verification_Rerun_Report.md`; carried forward here | Disclosed, unresolved | Either obtain the pinned 141 build under a different network policy, or formally accept 153 as the reference environment | **Yes** (methodological sign-off, not domain expertise) |
| 14 | The frozen engine's own `baselineRates` (35-92 µSv/h by room) | §1 / existing engine; `phase2a_adapter/config/engine_provisional_parameters.json` | Inherited from v1.2.3, self-disclosed in-engine as "CONFIGURABLE, ILLUSTRATIVE placeholder values (not derived from real data)" (frozen release line 1497); now load-bearing for Phase 2A/2C's `rescale_to_engine_baseline` | Real per-room dose-rate survey data, or RSO sign-off that the illustrative values are an acceptable stand-in | **Yes** |
| 15 | The frozen engine's own `CONFIG` thresholds (`devElevated/devCritical/doseElevated/doseCritical`, 30-minute horizon) | §1 / existing engine; `phase2a_adapter/config/engine_provisional_parameters.json` | Inherited from v1.2.3, self-disclosed in-engine as "PROTOTYPE warning thresholds — configurable placeholders, NOT regulatory limits" (frozen release line 1501) | Medical-physicist/RSO review of whether these thresholds, or the 30-minute projection horizon, are clinically appropriate | **Yes** |
| 16 | Physical/conceptual coherence of mapping Phase 1's procedure-class framing onto the engine's room-based framing via `rescale_to_engine_baseline` | §2 (exposure simulation); `detection_adapter.rescale_to_engine_baseline`; `PHASE2B_INTEGRATION_AUDIT.md` §1-2 | Not a numeric question: does a Phase-1-generated pattern, re-anchored onto a specific room's illustrative baseline, represent a coherent simulated worker? Unresolved | Domain input on whether procedure-class and room-based framings are interchangeable for this purpose, or should be unified (see `PHASE2C_CORRECTIVE_IMPLEMENTATION.md` §7 for the retained-rescaling decision) | **Yes** |
| 17 | Clinical basis for the immediate-alert dose bypass (`AlaradSafety.immediateAlert`, default policy `{mode:'dose', doseMsv:null}`) | §4 (not previously described in this methodology at all); `PHASE2B_INTEGRATION_AUDIT.md` §4; now implemented in `detection_adapter.classify_series` (Phase 2C item 1) | The bypass encodes a real safety-workflow judgment (an immediately dangerous projected dose should alert faster than standard confirmation); whether `doseCritical=0.35` mSv over 30 minutes is the clinically right trigger is unreviewed | RSO/medical-physicist review of the bypass's trigger value and whether bypassing confirmation is itself an appropriate design | **Yes** |
| 18 | Realism of scenario dynamics not yet reproducible against the engine (S10's masked-event timing, S11's recovery-to-next-event spacing) if/when a Phase 1 generator for them is built | `PHASE2B_INTEGRATION_AUDIT.md` §7; `PHASE2C_CORRECTIVE_IMPLEMENTATION.md` coverage matrix | Not yet applicable — no Phase 1 generator for these dynamics exists; registered now so the question is not forgotten once one is built | Domain input on realistic frozen-sensor masking durations and recovery-to-next-event spacing, before any such generator is built | **Yes, before that future generator's parameters are fixed** |
| 19 | The frozen engine's own sensor-health state-machine timing (`AlaradSafety.SENSOR_P`: a sensor is marked STALE after 2 missed minutes, DISCONNECTED after 5, SUSPECTED_FROZEN after 6 identical consecutive readings at 0.1 µSv/h resolution, with 2 consecutive changed/consistent samples required to exit RECOVERING or SUSPECTED_FROZEN) | §1 / existing engine, frozen release line 1316 (`SENSOR_P={staleAfter:2, disconnectedAfter:5, frozenN:6, frozenExitN:2, recoverN:2, resolution:0.1}`); identified while preparing `SCIENTIFIC_PARAMETER_REVIEW_PACKAGE.md` as a gap of exactly the same kind as rows 14/15, not previously registered | Inherited from v1.2.3, the engine's own code comment describes these as "simulation assumptions (documented in the UI); expected cadence = 1 sample per minute" — illustrative, not evidence-supported, and now load-bearing for every data-quality-layer result this project has reported (Phase 2A/2C's `dq_adapter.py`) | Real wearable-sensor communication-reliability data (typical dropout/reconnection timing), or RSO sign-off that these timings are an acceptable stand-in | **Yes** |
| 20 | Exponential-smoothing forecasting baseline's smoothing parameter (`alpha=0.5`, `phase3a_forecasting/config/phase3a_config.json`, block `baseline_exponential_smoothing`) | §4b baseline 2 (forecasting); `phase3a_forecasting/baselines.py::build_exponential_smoothing_forecasts` | New in Phase 3A; marked `PROVISIONAL` in its own config file at the point of implementation. Selection method: an **illustrative round-number choice (0.5)**, not fit, not cross-validated, and not derived from any domain or clinical source — chosen only so the baseline would run end-to-end for the smoke test | A sensitivity analysis sweeping `alpha` across a reasonable range (e.g. 0.1-0.9) against the full statistical campaign's data (not the 8-seed smoke batch), and/or domain input on a clinically-motivated smoothing timescale for dose-rate trends | **Yes, before this baseline's smoke-test comparison (`PHASE3A_SMOKE_TEST_REPORT.md` §3) can be treated as more than illustrative** |
| 21 | Phase 3C-A synthetic staffing roster-generation parameters: `extra_workers_beyond_concurrent_rooms=1`, `credential_coverage_probability_range=[0.4, 0.7]` (`phase3c_rotation_infra/config/phase3c_config.json`, block `roster_generation`) | §6b.2 (worker eligibility; same kind of gap as row 8); `phase3c_rotation_infra/staffing.py::generate_roster` | New in Phase 3C-A, marked `PROVISIONAL` with an explicit `source` field in its own config file. Selection method: illustrative round numbers chosen only so a roster is large enough, and credentialing sparse enough, for the exclusivity/infeasibility code paths to be exercisable in tests — not fit to any real staffing data | Facility staffing/credentialing data (same evidence source already named for row 8, which this row's parameters are a sub-case of), or RSO/staffing-policy sign-off that these illustrative ranges are an acceptable stand-in for testing purposes | **Yes** |
| 22 | Phase 3C-A synthetic per-worker duty-limit parameters: `max_dose_per_shift_mSv_range=[1.0, 3.0]`, `min_rest_between_assignments_minutes_range=[10, 20]`, `max_rotations_per_shift_range=[1, 3]` (`phase3c_rotation_infra/config/phase3c_config.json`, block `duty_limits`) | §6b.1/§6b.4 (eligibility and fairness constraints; sub-case of row 8); `phase3c_rotation_infra/staffing.py::generate_roster`; now also the **threshold owner** for the revised CGDTR trigger's duty-limit clause (`PHASE3B_ROTATION_ALGORITHM_DESIGN.md` Revision 3, section 3a clause (c)) | New in Phase 3C-A, marked `PROVISIONAL` with an explicit `source` field. Selection method: illustrative round numbers, not fit to any real staffing/scheduling policy or clinical dose-management practice. **`max_dose_per_shift_mSv` is a staffing/scheduling limit, explicitly distinct from the engine's own radiation alert thresholds (row 15) — the two must never be conflated**, per the Revision 3 trigger correction's explicit threshold-ownership distinction | Facility shift-scheduling/duty-limit policy, or RSO sign-off on illustrative ranges for a synthetic study, before this row's values drive any trigger decision beyond infrastructure testing | **Yes — and this row's resolution is now a prerequisite for the revised CGDTR trigger's clause (c), not only for the staffing model generally** |
| 23 | Phase 3C-A synthetic procedure-boundary spacing: `boundary_spacing_minutes_range=[15, 30]` (`phase3c_rotation_infra/config/phase3c_config.json`, block `procedure_boundaries`) | §6b.2 (procedure continuity); `phase3c_rotation_infra/exposure_layer.py::generate_room_boundaries` | New in Phase 3C-A, marked `PROVISIONAL` with an explicit `source` field. Selection method: an illustrative round-number range, not derived from any real procedure-duration data — used only to build a testable slot schedule for the counterfactual-simulation infrastructure | Real procedure-duration/scheduling data by room or procedure type, or RSO/operations sign-off that this range is an acceptable illustrative stand-in | **Yes, before any procedure-boundary timing is read as representative of real clinical workflow** |
| 24 | Phase 3C-A sensor-fault escalation threshold: `escalate_after_consecutive_fault_minutes=10` (`phase3c_rotation_infra/config/phase3c_config.json`, block `escalation`) | New capability, not previously described anywhere in this methodology; `phase3c_rotation_infra/escalation.py::evaluate_escalation` | New in Phase 3C-A, marked `PROVISIONAL` with an explicit `source` field stating this governs only the simulated, in-framework escalation log and is never connected to a real notification system. Selection method: an illustrative round number, not derived from any real alerting/paging policy | RSO/facility-operations input on what sensor-fault persistence duration should actually trigger human notification, before this value is used for anything beyond infrastructure testing | **Yes** |

No row in this table has been resolved by this document. Resolving a row
means obtaining and citing the evidence source listed, or obtaining the
named expert's sign-off — not substituting an engineering guess.

---

## 10. Scientific assumptions, limitations, and required expert review

*(Renumbered from Revision 1 §7. The former numbered "required expert
review" list is replaced by a pointer to §9, which now consolidates it with
the proposed evidence source for each item, removing the duplication.)*

### Assumptions carried over from the existing engine (not newly introduced, but newly load-bearing once evaluated statistically)

- Inverse-square-law point-source approximation for area-monitor modeling,
  per §1's MEASURED/MODELED distinction — **the engine's own in-page text
  already discloses this is "only a limited point-source approximation;
  scatter in real rooms does not follow it"** (line 1170). Any
  forecast/detection result involving area-mode workers inherits this
  limitation (Parameter Registry row 12).
- The detector and forecaster are both deterministic and rule-based (OLS
  linear regression, fixed thresholds) — confirmed in `Gap_Checklist.md` §1.
  No trained model, so no train/test split in the ML sense is needed for
  the *detector itself* — the seed separation in §8 is about evaluation
  sampling, not about preventing model overfitting.
- Synthetic noise (±5% on flat baselines, as implemented) stands in for
  real dosimeter measurement noise. Its realism relative to actual
  wearable dosimeter noise characteristics is unverified (`Gap_Checklist.md`
  §5; Parameter Registry row 11).

### Limitations (restated from `Gap_Checklist.md`, directly relevant to this methodology)

- All ground truth, under both the existing 13 scenarios and the proposed
  ≥390-run evaluation sample, remains **synthetic and author-specified**,
  not derived from real wearable-sensor data or real hospital shift logs.
  This methodology improves the *statistical adequacy* of synthetic
  evaluation; it does not, by itself, close the "no real data" gap.
- No independent domain-expert (RSO/medical physicist) has reviewed or
  signed off on any of the open numeric ranges or policy parameters this
  document leaves open — see Parameter Registry §9 in full for the
  complete list and each item's proposed evidence source.
- The rotation-recommendation evaluation protocol (§6) has no
  implementation to test yet; its constraints and criteria are a
  pre-registration, not a validated methodology — they should themselves
  be reviewed before being treated as fixed (Parameter Registry row 10).
- Reproducibility is currently qualified by the disclosed Chromium
  141-vs-153 version gap (`Verification_Rerun_Report.md` §2; Parameter
  Registry row 13); any new evaluation run under this methodology should
  either close that gap or carry the same disclosure forward.

### Required expert review

Every specific item requiring expert input is now tracked in §9's Parameter
Registry, including its proposed evidence source — that table is the
authoritative list, kept in one place rather than duplicated here. In
summary, the review gate before implementation covers: procedure/shift
parameters (§2), event/fault sampling ranges (§3), the two baselines whose
values or characterization are unresolved (§4a rows 5–6), forecast horizons
(§5), the rotation protocol's data model, timing, and scoring weights (§6,
rows 8–10), and the two inherited-engine assumptions whose realism is
unverified (rows 11–12). **This document does not substitute for that
review for any of them.**

---

## Explicit statement of what has and has not been done

- **Done:** this design document (now Revision 2), grounded in the three
  existing validation documents and in source lines re-verified directly in
  the frozen v1.2.3 HTML, extended per the seven additional points
  requested for this revision.
- **Not done, and not claimed as done:** no new seeds generated or run, no
  statistics computed, no baseline code written, no forecasting or rotation
  algorithm implemented, no expert review obtained, no parameter in §9
  resolved, no change to the frozen release or to any other branch.
