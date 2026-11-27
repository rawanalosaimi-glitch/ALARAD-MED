# Scientific Parameter Review Package — ALARAD / ICAIRE Research Validation

**Status: a review request, not a decision.** Nothing in this package has
been approved, revised, or rejected by a qualified Medical Physicist or
Radiation Safety Officer (RSO). No parameter value has been changed. The
frozen ALARAD v1.2.3 release was not modified (SHA-256
`92e897dd0ff1738f083df829b53f7f46377e042b7019bb9776232792261182ee`,
re-verified unchanged while preparing this package). No new forecasting
model and no rotation algorithm has been implemented (the frozen engine's
own `linearForecast` already exists and is used operationally for
early-warning triggering — see row 7 in §3 — but its predictive accuracy
has not been scientifically evaluated; that is a separate, correct fact
from "no forecasting exists"). No statistical campaign has been run. This
document does not claim expert approval anywhere, and nothing in it
should be read as implying any parameter is clinically validated.

**What approving a row in this package does, and does not, establish —
read this before reviewing anything below:**
- Marking a row **Approved** means *"this value is a reasonable,
  internally-consistent choice for the purposes of this synthetic
  simulation study."* It does **not** mean the value is representative
  of real occupational radiation exposure, and must never be cited as
  evidence that it is. Those are two different claims; this package and
  its review table only ever ask about the first.
- Expert approval of these provisional values, however thorough, does
  **not** by itself establish external validity (that the simulation
  behaves like the real world) or regulatory compliance with ICRP, NRRC,
  or any other authority. A reviewer's sign-off is a statement about
  reasonableness for a synthetic study, not a validation study and not a
  compliance determination — both would require their own, separate,
  explicitly-scoped review.

**Purpose:** collect, in one place, every scientific assumption this
research project currently depends on, so a qualified reviewer can
evaluate each one **without needing to read or run any code**, and record
their decision in the review table (§8).

---

## 1. How to use this document

- You do not need to inspect `phase1_simulator/`, `phase2a_adapter/`, or
  the frozen HTML file. Every value you need is quoted in §2–§3 below,
  with its unit and where it came from.
- For each parameter, answer the **Review Question** as best you can from
  your own expertise, then record **Approved / Revise / Not Approved**,
  a comment, and the date in the table in §8.
- "Illustrative" (§4) means the number was chosen only to make the
  software runnable, with no evidence behind it — your review is the
  first scientific input any of these numbers will have received.
- If you want the full technical trail behind any parameter, each entry
  below names the source document (`PHASE2B_INTEGRATION_AUDIT.md`,
  `PHASE2C_CORRECTIVE_IMPLEMENTATION.md`,
  `ICAIRE_Simulation_Validation_Methodology.md`) — reading those is
  optional, not required, to complete this review.
- A one-page distillation of this package is in
  `SCIENTIFIC_PARAMETER_REVIEW_SUMMARY.md`, and a plain list of the
  decisions still pending (beyond this parameter review) is in
  `UNRESOLVED_SCIENTIFIC_DECISIONS.md`.

---

## 2. Priority parameters — rows 14–17, 19, 20, and 21–24

These ten were only discovered to need review during this project's own
internal integration/documentation work (`PHASE2B_INTEGRATION_AUDIT.md`
for rows 14–17; this review package's own preparation for row 19; Phase
3A's own implementation for row 20; Phase 3C-A's own implementation for
rows 21–24): the
research software was already depending on them before anyone had
flagged them as scientific assumptions. They are prioritized here because
resolving them first is the most direct path to being able to interpret
any future result scientifically.

### Row 14 — The frozen engine's own room baseline dose rates

- **Exact current values (µSv/h):** Cath Lab 1 = 90, Cath Lab 2 = 85,
  Cath Lab 3 = 92, Fluoroscopy Suite = 70, Nuclear Medicine = 35,
  PET/CT Suite = 45, CT Suite = 55.
- **Source:** the frozen ALARAD v1.2.3 software's own internal table
  (`baselineRates`), with its own source-code comment reading, verbatim:
  *"µSv/h expected dose rate at the worker by room, before procedure
  multiplier — CONFIGURABLE, ILLUSTRATIVE placeholder values (not derived
  from real data)."*
- **Scientific assumption encoded:** that these seven numbers are
  reasonable order-of-magnitude stand-ins for typical worker dose rates
  in each named room type, for the purpose of generating and classifying
  simulated exposure events.
- **Role in the simulation/detection engine:** this is the **anchor**
  every other radiation-detection number is computed relative to — a
  worker's "4× baseline" event means 4× *this* number for their room.
  Changing it rescales every deviation and dose calculation downstream.
- **Illustrative, not evidence-supported.** No real dose-rate survey data
  was used.
- **Review question:** *Are these seven values reasonable illustrative
  placeholders for a radiation-safety research prototype, or should they
  be replaced with facility survey data (and if so, do you have or know
  of such data)?*

### Row 15 — The frozen engine's own alert-threshold configuration

- **Exact current values:** elevated deviation ≥ **+50%** above room
  baseline; critical deviation ≥ **+150%**; elevated projected dose ≥
  **0.15 mSv**; critical projected dose ≥ **0.35 mSv**; both dose figures
  are projected over a fixed **30-minute** horizon (current rate held
  constant). A reading is classified "elevated" or "critical" if **either**
  its relative deviation **or** its projected dose crosses the
  corresponding line (whichever comes first).
- **Source:** the frozen software's own `CONFIG` object, with its own
  comment reading, verbatim: *"PROTOTYPE warning thresholds —
  configurable placeholders, NOT regulatory limits."*
- **Scientific assumption encoded:** that +50%/+150% deviation and
  0.15/0.35 mSv-over-30-minutes are reasonable lines between normal,
  elevated, and critical exposure for the purpose of this research.
- **Role:** this is the single rule that classifies every simulated
  minute as safe/elevated/critical, which in turn drives every detection
  TP/FP/FN this project reports.
- **Illustrative, not evidence-supported.**
- **Review questions:** *(a) Are +50%/+150% deviation-from-baseline
  reasonable elevated/critical thresholds? (b) Are 0.15/0.35 mSv
  reasonable elevated/critical projected-dose thresholds for a 30-minute
  horizon? (c) Is a fixed 30-minute horizon appropriate, or should it
  vary by procedure type?*

### Row 16 — Physical coherence of rescaling onto the engine's baseline

- **What this is:** this research project's own simulator (Phase 1)
  generates synthetic exposure patterns using its own, separately-chosen
  illustrative baselines, organized by **procedure type** (e.g.
  "diagnostic fluoroscopy" = 4.0 µSv/h; see §3, row 1). To test the real
  detection software (row 14/15's engine), this project's adapter
  mathematically re-anchors each simulated pattern onto the engine's own
  **room-based** baseline (row 14) — preserving the *percentage above
  baseline* exactly, while changing the absolute number it's a percentage
  of.
- **Exact transformation:** for a simulated reading `r`, the adapter
  computes `r' = r × (engine_baseline / simulator_baseline)`. This has
  been checked mathematically and numerically (not merely asserted) to
  leave the deviation-based classification outcome unchanged; see
  `PHASE2B_INTEGRATION_AUDIT.md` §1 and
  `PHASE2C_CORRECTIVE_IMPLEMENTATION.md` §7 for the exact numbers.
- **Scientific assumption encoded:** that a pattern designed around "this
  is a diagnostic fluoroscopy procedure" and a pattern designed around
  "this happens in Cath Lab 1" can be treated as the same kind of thing
  for detection-testing purposes, merely by rescaling.
- **Role:** this determines whether every detection result this project
  has produced so far (Phase 2A/2C) is testing something scientifically
  meaningful, or just testing that two numbers can be multiplied
  together consistently.
- **This is a conceptual question, not a value to approve or reject** —
  see the Review Question below.
- **Review question:** *Does it make scientific sense to simulate a
  "procedure type" pattern and then evaluate it against a specific
  "room" baseline by rescaling, or should the simulator instead generate
  patterns directly in terms of rooms (eliminating the need to rescale at
  all — a change this project has NOT made, pending this review)?*

### Row 17 — Clinical basis for the immediate-alert dose bypass

- **Exact current value:** the engine's default policy
  (`AlaradSafety.policy()` = `{mode: "dose", doseMsv: null}`) allows an
  alert to be raised **immediately**, bypassing the normal multi-minute
  confirmation requirement, whenever a worker's projected dose reaches
  **0.35 mSv** (the same critical-dose figure from row 15) — this is
  **on by default**, not an opt-in feature.
- **Source:** the frozen software's own `AlaradSafety.immediateAlert`
  function and its default policy object, confirmed live against the
  running software in this session.
- **Scientific assumption encoded:** that a sufficiently dangerous
  projected dose should alert faster than the standard confirmation
  window, and that 0.35 mSv over 30 minutes is the right line for "fast
  enough to matter."
- **Role:** this specifically affects **detection timing**, not whether
  an event is detected at all. This project's own testing found a real
  case (a sustained high-rate exposure scenario) where this bypass
  changes the detected alert time by several minutes compared to waiting
  for normal confirmation.
- **Illustrative, not evidence-supported** — this is the same 0.35 mSv
  figure from row 15, used for a second purpose that was not previously
  identified as needing separate review.
- **Review questions:** *(a) Should a sufficiently high projected dose be
  allowed to bypass the normal confirmation window at all? (b) If yes, is
  0.35 mSv over 30 minutes the right trigger value, or should the bypass
  use a different threshold than the ordinary "critical" classification?*

### Row 19 — The frozen engine's own sensor-health state-machine timing

- **Exact current values:** a sensor is marked **STALE** after **2**
  consecutive missed minutes, **DISCONNECTED** after **5**; a reading is
  marked **SUSPECTED_FROZEN** after **6** consecutive identical readings
  (compared at **0.1 µSv/h** resolution); recovering from DISCONNECTED or
  exiting SUSPECTED_FROZEN each require **2** consecutive
  changed/consistent samples.
- **Source:** the frozen software's own `AlaradSafety.SENSOR_P` object
  (`{staleAfter:2, disconnectedAfter:5, frozenN:6, frozenExitN:2,
  recoverN:2, resolution:0.1}`), with its own source-code comment reading,
  verbatim: *"Parameters are simulation assumptions (documented in the
  UI); expected cadence = 1 sample per minute."* Identified as needing
  review only while preparing this package — it is, in kind, exactly like
  rows 14/15 (the engine's own illustrative constant) but had not
  previously been registered.
- **Scientific assumption encoded:** that these five timing/counting
  thresholds are reasonable stand-ins for how quickly a real wearable
  dosimeter's communication link would be judged stale, disconnected, or
  stuck, and how quickly it should be judged recovered.
- **Role:** this is the complete rule set behind every sensor-fault
  (data-quality) detection result this project has reported — whether a
  missing, frozen, or delayed reading is correctly flagged, and how fast.
- **Illustrative, not evidence-supported.** No real wearable-sensor
  communication-reliability data was used.
- **Review question:** *Are 2 minutes (stale), 5 minutes
  (disconnected), 6 identical readings (suspected frozen), and 2
  consecutive samples (recovery) reasonable timings for a real wearable
  radiation dosimeter's communication link, or do you know of device
  specifications or field data that should replace them?*

### Row 20 — Exponential-smoothing forecasting baseline's smoothing parameter

- **Exact current value:** `alpha = 0.5`
  (`phase3a_forecasting/config/phase3a_config.json`, block
  `baseline_exponential_smoothing`).
- **Source:** new code written for Phase 3A
  (`phase3a_forecasting/baselines.py::build_exponential_smoothing_forecasts`),
  not the frozen engine — this is this project's own baseline, used only
  to give the frozen `linearForecast` function a second point of
  comparison besides simple persistence (row 7's "already exists but
  unevaluated" `linearForecast`).
- **Selection method, stated exactly:** `alpha=0.5` was chosen as an
  **illustrative round number**, so the baseline would run end-to-end for
  the Phase 3A smoke test. It was **not** fit to any data, **not**
  cross-validated, and is **not** derived from any clinical or domain
  source. The config file marks it `PROVISIONAL` for exactly this reason.
- **Scientific assumption encoded:** that equal-weighting half the most
  recent reading and half the prior smoothed estimate is a reasonable
  general-purpose smoothing timescale for dose-rate trends — untested.
- **Role:** this value directly produced the "+0.32 to +0.33" positive
  skill scores reported for the exponential-smoothing baseline in
  `PHASE3A_SMOKE_TEST_REPORT.md` §3, which currently read as more
  favorable than the real `linearForecast`'s negative skill scores at the
  same smoke scale. Changing `alpha` would change those numbers; how much,
  and in which direction, has not been tested.
- **Illustrative, not evidence-supported, and not yet subjected to even a
  sensitivity sweep** (see §7's note on this).
- **Review question:** *Is `alpha=0.5` a defensible default smoothing
  parameter for this kind of baseline, or should a sensitivity analysis
  (sweeping a range such as 0.1–0.9) be required before this baseline's
  comparison numbers are used for anything beyond illustration?*

### Row 21 — Phase 3C-A synthetic staffing roster-generation parameters

- **Exact current values:** `extra_workers_beyond_concurrent_rooms = 1`;
  `credential_coverage_probability_range = [0.4, 0.7]`
  (`phase3c_rotation_infra/config/phase3c_config.json`, block
  `roster_generation`).
- **Units/purpose:** a count (extra spare workers beyond the number of
  concurrently-occupied rooms) and a dimensionless probability range
  (the chance a given synthetic worker is credentialed for a given
  room/procedure class), both used only to generate a synthetic shift
  roster — `phase3c_rotation_infra/staffing.py::generate_roster`.
- **Source:** new code written for Phase 3C-A, not the frozen engine.
  Marked `PROVISIONAL` with an explicit `source` field in its own config
  file, reading: *"Synthetic assumption for this research prototype,
  chosen only so eligible replacements exist sometimes (not always, not
  never) during testing; not derived from real staffing data."*
- **Selection method, stated exactly:** illustrative round numbers,
  **not** fit to any real staffing/credentialing data, chosen only so
  the worker-exclusivity and infeasibility code paths
  (`phase3c_rotation_infra/assignment.py`) are exercisable in tests.
- **Scientific assumption encoded:** that roughly 40–70% random
  credential coverage per room/procedure, with one spare worker beyond
  concurrent room count, is a reasonable illustrative stand-in for a
  real staffing/credentialing pattern.
- **Role:** this is the complete generative model behind the Phase 3C-A
  infrastructure's worker roster — no real or previously-synthesized
  staffing dataset existed anywhere in this project before this.
- **Illustrative, not evidence-supported. Unapproved for any clinical
  or operational use.**
- **Sensitivity requirement:** a sweep of the coverage-probability range
  and the extra-worker count, to check how sensitive any future
  rotation-evaluation result is to this roster-generation choice, has
  not been run.
- **Review question:** *Are these illustrative roster-size and
  credential-coverage assumptions a reasonable stand-in for testing
  purposes, or do you have facility staffing/credentialing data that
  should replace them before any rotation-evaluation result is
  reported?*

### Row 22 — Phase 3C-A synthetic per-worker duty-limit parameters

- **Exact current values:** `max_dose_per_shift_mSv_range = [1.0, 3.0]`;
  `min_rest_between_assignments_minutes_range = [10, 20]`;
  `max_rotations_per_shift_range = [1, 3]`
  (`phase3c_rotation_infra/config/phase3c_config.json`, block
  `duty_limits`).
- **Units/purpose:** mSv (a per-worker, per-shift dose ceiling for
  scheduling purposes), minutes (minimum rest between assignments), and
  a count (rotation-burden cap) — `phase3c_rotation_infra/staffing.py`.
- **Source:** new code written for Phase 3C-A, not the frozen engine.
  Marked `PROVISIONAL` with an explicit `source` field in its own config
  file, reading: *"Synthetic assumption for this research prototype;
  not derived from real staffing policy, clinical guidance, or
  regulatory dose limits."*
- **Selection method, stated exactly:** illustrative round numbers, not
  fit to any real staffing/scheduling policy or clinical dose-management
  practice.
- **Scientific assumption encoded:** that these ranges are reasonable
  illustrative stand-ins for real per-worker shift duty limits.
- **Role, and an explicit distinction that matters for this round's
  trigger correction:** `max_dose_per_shift_mSv` is **this project's own
  staffing/scheduling limit** — it is now also the threshold owner for
  the revised CGDTR trigger's duty-limit clause
  (`PHASE3B_ROTATION_ALGORITHM_DESIGN.md`, Revision 3, section 3a
  clause (c)). **It must never be confused with the frozen engine's own
  radiation alert thresholds (row 15, `CONFIG.doseElevated`/
  `doseCritical`)** — the two are different quantities with different
  owners (this project's synthetic staffing config vs. the frozen
  engine's own, separately-registered configuration), compared for
  different reasons (duty-limit/scheduling concern vs. radiation-safety
  classification).
- **Illustrative, not evidence-supported. Unapproved for any clinical
  or operational use.**
- **Sensitivity requirement:** none of these three ranges has been
  swept; `max_dose_per_shift_mSv` in particular now gates a trigger
  clause, so its sensitivity matters beyond roster generation alone.
- **Review question:** *Are these illustrative duty-limit ranges
  reasonable for testing purposes, and — separately — is it appropriate
  for a staffing/scheduling limit like this to drive part of a
  rotation-recommendation trigger at all, alongside the frozen engine's
  own radiation-safety thresholds?*

### Row 23 — Phase 3C-A synthetic procedure-boundary spacing

- **Exact current value:** `boundary_spacing_minutes_range = [15, 30]`
  (`phase3c_rotation_infra/config/phase3c_config.json`, block
  `procedure_boundaries`).
- **Units/purpose:** minutes — the spacing used to synthetically
  generate a room-track's procedure-boundary schedule for testing
  (`phase3c_rotation_infra/exposure_layer.py::generate_room_boundaries`).
- **Source:** new code written for Phase 3C-A, not the frozen engine.
  Marked `PROVISIONAL` with an explicit `source` field, reading:
  *"Synthetic assumption for this research prototype; not derived from
  real procedure-duration data."*
- **Selection method, stated exactly:** an illustrative round-number
  range, used only to build a testable slot schedule.
- **Scientific assumption encoded:** that procedures of roughly 15–30
  minutes each are a reasonable illustrative stand-in for how often a
  real procedure boundary (a legitimate point for a rotation to take
  effect) occurs.
- **Role:** this directly determines how often `T_effective`
  (`PHASE3B_ROTATION_ALGORITHM_DESIGN.md` section 3d) can land, and
  therefore how quickly a handoff can actually complete.
- **Illustrative, not evidence-supported. Unapproved for any clinical
  or operational use.**
- **Sensitivity requirement:** not yet swept against handoff-duration
  (row 9) or infeasibility/abort rates.
- **Review question:** *Is a 15–30 minute illustrative procedure-
  boundary spacing a reasonable stand-in for testing purposes, or do you
  have real procedure-duration data by room/procedure type that should
  replace it?*

### Row 24 — Phase 3C-A sensor-fault escalation threshold

- **Exact current value:** `escalate_after_consecutive_fault_minutes =
  10` (`phase3c_rotation_infra/config/phase3c_config.json`, block
  `escalation`).
- **Units/purpose:** minutes — the number of consecutive sensor-fault-
  flagged minutes (reusing the real engine's own `sensorStep` states via
  `phase2a_adapter.dq_adapter`, never reimplemented) before this
  project's own escalation log raises a simulated concern
  (`phase3c_rotation_infra/escalation.py::evaluate_escalation`).
- **Source:** new code written for Phase 3C-A, not the frozen engine.
  Marked `PROVISIONAL` with an explicit `source` field, reading:
  *"Synthetic assumption for this research prototype; not derived from
  real alerting/paging policy. This threshold governs only the
  simulated, in-framework escalation log in this module — it is never
  connected to a real notification system."*
- **Selection method, stated exactly:** an illustrative round number,
  not derived from any real alerting/paging policy.
- **Scientific assumption encoded:** that 10 consecutive minutes of a
  flagged sensor state is a reasonable point at which a real system
  should notify a human — untested.
- **Role:** this is independent of, and never interacts with, any dose
  value or dose-trigger clause (`PHASE3B_ROTATION_ALGORITHM_DESIGN.md`
  Revision 3, section 3a's explicit decoupling) — it governs only the
  sensor-fault escalation channel.
- **Illustrative, not evidence-supported. Unapproved for any clinical
  or operational use, and explicitly not connected to any real
  notification system.**
- **Sensitivity requirement:** not yet swept.
- **Review question:** *Is 10 consecutive flagged minutes a reasonable
  illustrative point to simulate an escalation for testing purposes, or
  do you have real alerting-policy input that should replace it?*

---

## 3. Remaining registry parameters — rows 1–13, 18

Documented more briefly, since these were already written up in
`ICAIRE_Simulation_Validation_Methodology.md` §9 across earlier revisions
— restated here so this package is self-contained.

| Row | Parameter | Current value(s) / unit | Source | Illustrative or evidence-supported | Review question |
|---|---|---|---|---|---|
| 1 | Procedure-class baselines & multiplier ranges | `diagnostic_fluoroscopy`=4.0 µSv/h ×[0.8–1.3]; `interventional_cath_lab`=8.0 µSv/h ×[1.0–1.8]; `ct`=3.0 µSv/h ×[0.6–1.0]; `pet_ct`=5.0 µSv/h ×[0.8–1.2] | This project's own Phase 1 config | Illustrative | Are these four procedure classes, baselines, and multiplier ranges reasonable, or should they be replaced/extended? |
| 2 | Shift-length set | 60, 240, 480, 720 minutes (1/4/8/12 h) | This project's own Phase 1 config | Illustrative | Is this a reasonable set of shift lengths to simulate; are any missing or irrelevant? |
| 3 | Event magnitude & duration ranges | Ramp peak ×[2.0–5.0] over 10–20 min; step ×[2.0–6.0] over 5–15 min; spike ×[2.0–6.0] over 1–2 min | This project's own Phase 1 config | Illustrative | Are these magnitude/duration ranges representative of real abnormal-exposure events, over- or under-stated? |
| 4 | Fault duration ranges (sensor faults) | Missing: 5–20 min; invalid: 1–4 min; frozen: 10–30 min; delayed: 3–9 min | This project's own Phase 1 config | Illustrative | Are these sensor-fault duration ranges realistic for the kind of wearable dosimeter this is meant to simulate? |
| 5 | Baseline-2 fixed-threshold setpoint | 2.0× room baseline, instantaneous, no window | This project's own Phase 2A config | Illustrative, explicitly not sourced from a manufacturer spec | Is 2.0× a reasonable "simple commercial alarm" setpoint to compare against, or do you know of a manufacturer/regulatory figure that should be used instead? |
| 6 | Baseline-3 moving-average characterization | 5-minute window, 2.0× threshold | This project's own Phase 2A config | Illustrative; **explicitly not labeled "conventional practice"** pending a citation | Is a 5-minute moving average at 2.0× a reasonable second reference point? Do you know of a citation that would justify calling this "conventional practice"? |
| 7 | Forecast horizon beyond the 3 samples `linearForecast` actually produces | Previously an unexamined placeholder "15 minutes"; **now empirically confirmed that the real function hardcodes exactly 3 future samples regardless of input length** (verified for input lengths 3/4/7/10; `PHASE3A_LIMITATIONS.md` §1) | Methodology document, revised following Phase 3A | Not a value to pick — a question of whether/how any longer horizon could ever be reached | Should a longer horizon ever be built, and if so, by what technique (recursively feeding the existing 3-step output back in — uncharacterized, and not something the frozen engine does — or a different model)? **Note:** Phase 3A has already evaluated the three horizons `linearForecast` actually produces (1/2/3 minutes ahead) against ground truth — see `PHASE3A_SMOKE_TEST_REPORT.md`. This row is only about any *longer* horizon, which remains both unbuilt and, on current evidence, not achievable by calling the existing function differently. |
| 8 | Worker eligibility/credentialing model | Does not exist | Methodology document only | N/A — nothing built yet | What data would a real eligibility check need (credentials, current dose, open incidents)? |
| 9 | Minimum handoff/briefing duration | **Revised following Phase 3C-A**: an illustrative value of 10 minutes now exists in code (`phase3c_rotation_infra/config/phase3c_config.json`, block `handoff`) purely to test the timeline/scheduling machinery — still unapproved; no rotation recommender (CGDTR) exists yet | `PHASE3B_ROTATION_ALGORITHM_DESIGN.md` section 3d; `phase3c_rotation_infra/scheduling.py` | Illustrative, unapproved | What is a realistic minimum handoff time before a rotation takes effect? |
| 10 | Rotation scoring weights | Not chosen; **no rotation recommender exists** | Methodology document only | N/A | Once built, how should dose reduction, fairness, latency, and rotation count be weighted against each other? |
| 11 | Measurement noise realism | ±5% uniform noise on flat baseline readings | Inherited from the frozen engine, reused by Phase 1 | Illustrative, unverified against real dosimeter noise | Is ±5% a reasonable noise magnitude for a wearable dosimeter, or should it be a different distribution/magnitude? |
| 12 | Inverse-square area-monitor model | Fixed exponent = 2.0 (engine), separately a true exponent = 1.7 is used in one test scenario to deliberately create a measured-vs-modeled gap | Inherited from the frozen engine, self-disclosed in-engine as a limited approximation | Illustrative | Is the fixed exponent-2 inverse-square model acceptable for this prototype's area-monitor logic, given its self-disclosed limitation? |
| 13 | Chromium browser-version gap | Pinned 141.0.7390.37 vs. actually used 153.0.8010.12 | This project's own test infrastructure | N/A — a reproducibility/methodology matter, not a clinical one | (No domain expertise needed; included for completeness only.) |
| 18 | Realism of not-yet-buildable scenario dynamics (masked-event timing, recovery-to-next-event spacing) | Not yet applicable — no generator exists | `PHASE2B_INTEGRATION_AUDIT.md` §7 | N/A until built | Once a generator for these dynamics is proposed, what durations/spacings would be realistic? |

**Note on forecasting (row 7), stated precisely so it is not
misread:** the frozen v1.2.3 engine already contains a forecasting
function, `linearForecast` — an ordinary-least-squares extrapolation of
the last 4 readings, used today inside the detection logic as an
early-warning trigger (projecting whether a deviation will cross the
elevated threshold within the next few minutes). This is a real,
existing capability, not a placeholder. What is true, and is what row 7
is actually about, is narrower: **`linearForecast`'s predictive accuracy
has never been scientifically evaluated against ground truth** (how
close its predictions actually come to what happens), and **no new
forecasting model, and no evaluation harness comparing any forecaster's
predictions against ground truth, has been built** for this research
framework. "No forecasting has been implemented" and "no forecasting
code exists" are not the same statement, and only the first is true.

**Update following Phase 3A:** an evaluation harness comparing
`linearForecast` against ground truth (and against two independent
baselines — simple persistence, and exponential smoothing, row 20) has
since been built and run at smoke scale (8 seeds). It found
`linearForecast`'s skill score **negative** at every horizon it
evaluated, while exponential smoothing scored positively — see
`PHASE3A_SMOKE_TEST_REPORT.md` §3 and `PHASE3A_LIMITATIONS.md` §4. This
is a real, verified result for those 8 specific seeds, explicitly **not**
a statistically established finding (8 seeds, heavily weighted toward
flat/near-flat scenarios, is not the balanced ≥30-seed-per-class campaign
§7 of the methodology calls for). It still does not evaluate any horizon
beyond the 3 samples the real function produces.

---

## 4. Illustrative vs. evidence-supported — summary classification

| Status | Rows |
|---|---|
| **Illustrative placeholder (no evidence at all)** | 1, 2, 3, 4, 5, 6, 14, 15, 17, 19, 20, 21, 22, 23, 24 |
| **Inherited from the frozen engine, explicitly unverified against reality** | 11 |
| **Inherited from the frozen engine, self-disclosed as a limited approximation** | 12 |
| **Not yet applicable (feature does not exist yet)** | 8, 10, 18 |
| **Illustrative value now exists for infrastructure testing only; feature (CGDTR) still does not exist** | 9 |
| **Conceptual/methodological, not a numeric value** | 16 |
| **Reproducibility/engineering, not a scientific value** | 13 |

**No row in this registry currently qualifies as evidence-supported.**
That is the central fact this review package exists to start changing.

---

## 5. Which engine function each parameter affects

| Row | Alert thresholds | Dose accumulation | Event severity classification | Forecasting | Rotation |
|---|---|---|---|---|---|
| 1 | — | ✓ | ✓ | — | — |
| 2 | — | ✓ | — | — | — |
| 3 | ✓ | ✓ | ✓ | — | — |
| 4 | ✓ (data-quality) | — | — | — | — |
| 5 | ✓ | — | — | — | — |
| 6 | ✓ | — | — | — | — |
| 7 | — | — | — | ✓ (not yet built) | — |
| 8 | — | — | — | — | ✓ (not yet built) |
| 9 | — | — | — | — | ✓ (not yet built) |
| 10 | — | — | — | — | ✓ (not yet built) |
| 11 | ✓ | ✓ | ✓ | — | — |
| 12 | — | ✓ | ✓ | — | — |
| 13 | — | — | — | — | — |
| 14 | ✓ | ✓ | ✓ | — | — |
| 15 | ✓ | ✓ | ✓ | — | — |
| 16 | ✓ | — | ✓ | — | — |
| 17 | ✓ (timing only) | — | — | — | — |
| 18 | ✓ (future) | — | ✓ (future) | — | — |
| 19 | ✓ (data-quality) | — | — | — | — |
| 20 | — | — | — | ✓ (baseline comparator) | — |
| 21 | — | — | — | — | ✓ (staffing/eligibility infra) |
| 22 | — | ✓ (duty-limit, not radiation threshold) | — | — | ✓ (staffing/eligibility infra; also the revised trigger's clause (c)) |
| 23 | — | — | — | — | ✓ (scheduling infra) |
| 24 | ✓ (sensor-fault escalation only, independent of dose) | — | — | — | — |

---

## 6. Authoritative references — what is already present, and what is not

Per instruction, **no citation is invented or claimed as compliance
here.** The only authoritative reference this project has found anywhere
in its own materials is one the frozen engine's own interface text
already cites, verbatim, in several places:

> *"ICRP Publication 103 recommends an effective-dose limit of 20 mSv per
> year, averaged over defined 5-year periods, with no single year above
> 50 mSv."*

> *"In Saudi Arabia the applicable limit and averaging period are set by
> NRRC requirements (e.g. NRRC-R-01-SR02) — consult the current official
> text."*

Both are quoted directly from the frozen software's own help text; **this
project has not independently verified either citation** against the
current official ICRP or NRRC text, and the software's own text says the
same (*"consult the current official text"*). The engine uses the 20
mSv/year figure only as a visual dashboard reference level (`CONFIG.refAnnual`),
explicitly not as a 5-year-averaged compliance calculation. **These two
citations remain explicitly unverified by this project until checked
against the current official ICRP and NRRC texts — nothing below should
be read as this project vouching for either one**, and no further
citation has been added or invented anywhere in this package.

**No other parameter in this registry (rows 1–24) has any citation
behind it at all.** Where a Review Question above asks whether a
manufacturer specification, regulatory alarm-setpoint guidance, or
published noise/failure-rate/communication-reliability data exists, that
is a genuine open question for the reviewer's own expertise — this
project does not have, and has not searched for, such sources.

---

## 7. What can be tested now vs. what remains scientifically blocked

**Can proceed as preliminary software testing, before any expert
approval** (these establish that the code does what it is written to do,
not that the numbers are realistic):
- Re-running the existing unit/regression/reproduction test suites
  (Phase 1: 40 tests; Phase 2A/2C adapter: 31 tests) — these check
  internal consistency and faithful reproduction of the frozen engine's
  own behavior, using whatever placeholder values are currently set.
- Additional smoke-scale integration runs (a handful of seeds), to catch
  software defects, exactly as done in every phase so far.
- Code-level sensitivity checks (e.g., "does changing this number change
  that outcome," as already done for rows 1/14/15/17's interaction in
  `PHASE2C_CORRECTIVE_IMPLEMENTATION.md` §7) — these describe the
  software's behavior, not the world.

**Must remain blocked until this review (or an equivalent one) is
complete:**
- The ≥30-seed-per-class statistical evaluation campaign
  (`ICAIRE_Simulation_Validation_Methodology.md` §7) — running it now
  would produce precision/recall/F1 numbers whose absolute scale and
  event-severity framing rest entirely on unreviewed placeholders.
- Any claim, in a paper draft or elsewhere, that this project's detection
  results reflect real-world radiation-safety performance.
- Any characterization of Baseline 3 as "conventional practice" (row 6).
- Any claim that `linearForecast` is accurate or validated beyond the
  8-seed smoke result already reported (see the forecasting note in §3)
  — and separately, any *new* forecasting model or rotation algorithm
  (rows 8–10), which remain out of scope for implementation regardless of
  this review.
- Any claim that the Phase 3A smoke test's negative skill score for
  `linearForecast`, or the positive skill score for the exponential-
  smoothing baseline (row 20), generalizes beyond those 8 seeds — neither
  has been through the statistical campaign.
- Any statement that rows 14/15/17/19's thresholds are clinically
  appropriate, in either direction.
- Any use of the exponential-smoothing baseline's (row 20) comparison
  numbers as more than illustrative, before a sensitivity analysis on
  `alpha` is performed.
- Any claim that Phase 3C-A's synthetic staffing/duty-limit/boundary-
  spacing/escalation parameters (rows 21–24) represent real staffing,
  scheduling, or alerting policy — all four are illustrative,
  **unapproved for any clinical or operational use**, and introduced
  only to make the rotation-simulation infrastructure testable.
- Any implementation of CGDTR's trigger clause (c) (the duty-limit
  check, `PHASE3B_ROTATION_ALGORITHM_DESIGN.md` Revision 3) using row
  22's illustrative `max_dose_per_shift_mSv` range as if it reflected a
  real or approved staffing policy.
- Any claim that a reviewer's approval of a provisional value, however
  thorough, by itself establishes external validity or regulatory
  compliance (see the note at the top of this document) — those would
  need their own, separately-scoped review.

---

## 8. Review table

*For the reviewer: mark one of Approved / Revise / Not Approved per row,
with a comment, and today's date. Leave blank if deferring.*

| # | Parameter | Current value | Approved / Revise / Not Approved | Reviewer comments | Date |
|---|---|---|---|---|---|
| 14 | Engine room baseline dose rates | 35–92 µSv/h by room | | | |
| 15 | Engine alert thresholds + horizon | +50%/+150% dev; 0.15/0.35 mSv; 30 min | | | |
| 16 | Procedure-to-room rescaling coherence | (conceptual — see §2) | | | |
| 17 | Immediate-alert dose bypass | 0.35 mSv, on by default | | | |
| 19 | Sensor-health state-machine timing | stale 2 min; disconnected 5 min; frozen 6 readings; recover 2 samples | | | |
| 20 | Exponential-smoothing baseline alpha | 0.5, illustrative round number | | | |
| 21 | Staffing roster-generation parameters | 1 extra worker; 0.4–0.7 credential coverage | | | |
| 22 | Per-worker duty-limit parameters | 1.0–3.0 mSv/shift; 10–20 min rest; 1–3 rotation cap | | | |
| 23 | Procedure-boundary spacing | 15–30 min, illustrative | | | |
| 24 | Sensor-fault escalation threshold | 10 consecutive flagged minutes | | | |
| 1 | Procedure-class baselines/multipliers | 3.0–8.0 µSv/h, various ×ranges | | | |
| 2 | Shift-length set | 60/240/480/720 min | | | |
| 3 | Event magnitude/duration ranges | ×2.0–6.0, 1–20 min | | | |
| 4 | Fault duration ranges | 1–30 min by kind | | | |
| 5 | Baseline-2 fixed-threshold setpoint | 2.0× baseline | | | |
| 6 | Baseline-3 moving-average + label | 5 min window, 2.0×, not "conventional" | | | |
| 7 | Forecast horizon beyond 3 samples | 3-sample limit confirmed; any longer horizon unbuilt | | | |
| 8 | Worker eligibility model | does not exist | | | |
| 9 | Handoff/briefing duration | 10 min illustrative value in code; not approved; CGDTR unbuilt | | | |
| 10 | Rotation scoring weights | not chosen, unbuilt | | | |
| 11 | Measurement noise realism | ±5% uniform | | | |
| 12 | Inverse-square area model | exponent 2.0 (engine), 1.7 (one test case) | | | |
| 13 | Chromium version gap | 141 pinned vs. 153 used | | | |
| 18 | S10/S11 dynamics realism | not yet applicable | | | |

---

## 9. Explicit statement of what this package does and does not do

- **Does:** collect every registered scientific parameter (24, as of
  this revision), in plain language, with exact values, sources, and
  review questions, so a qualified reviewer can act without reading
  code; distinguish what the frozen engine already contains
  (`linearForecast`, now evaluated at smoke scale against two baselines,
  including the row-20 exponential-smoothing baseline) from what has not
  been built (a new forecaster, CGDTR or any rotation algorithm, any
  horizon beyond `linearForecast`'s own 3-sample limit); distinguish the
  frozen engine's own radiation-safety thresholds (row 15) from this
  project's own, separately-owned synthetic staffing/duty-limit/
  scheduling/escalation parameters (rows 21–24), which **must never be
  presented as approved, clinical, or regulatory values**; and state
  plainly that approving a value for this synthetic study is not the
  same claim as evidence of real-world representativeness, and that
  expert approval alone does not establish external validity or
  regulatory compliance.
- **Does not:** change any parameter value; modify the frozen release;
  implement forecasting or rotation; run the statistical campaign; claim
  any expert has approved anything; invent or add any citation beyond
  the two already present in the frozen engine's own text (§6, both
  still unverified); deploy anything. All of those remain exactly as
  they were before this package was written.
