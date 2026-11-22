# Scientific Parameter Review Package — ALARAD / ICAIRE Research Validation

**Status: a review request, not a decision.** Nothing in this package has
been approved, revised, or rejected by a qualified Medical Physicist or
Radiation Safety Officer (RSO). No parameter value has been changed. The
frozen ALARAD v1.2.3 release was not modified (SHA-256
`92e897dd0ff1738f083df829b53f7f46377e042b7019bb9776232792261182ee`,
re-verified unchanged while preparing this package). No forecasting or
rotation algorithm exists to review yet. No statistical campaign has been
run. This document does not claim expert approval anywhere, and nothing
in it should be read as implying any parameter is clinically validated.

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

## 2. Priority parameters — rows 14–17

These four were only discovered to need review during this project's own
internal integration audit (`PHASE2B_INTEGRATION_AUDIT.md`): the research
software was already depending on them before anyone had flagged them as
scientific assumptions. They are prioritized here because resolving them
first is the most direct path to being able to interpret any future
result scientifically.

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
| 7 | Forecast horizon | Placeholder "15 minutes"; **no forecaster is implemented** | Methodology document only | Placeholder, not yet acted on | What forecast horizon would actually be actionable for an RSO, once forecasting is built? |
| 8 | Worker eligibility/credentialing model | Does not exist | Methodology document only | N/A — nothing built yet | What data would a real eligibility check need (credentials, current dose, open incidents)? |
| 9 | Minimum handoff/briefing duration | Not chosen; **no rotation recommender exists** | Methodology document only | N/A | What is a realistic minimum handoff time before a rotation takes effect? |
| 10 | Rotation scoring weights | Not chosen; **no rotation recommender exists** | Methodology document only | N/A | Once built, how should dose reduction, fairness, latency, and rotation count be weighted against each other? |
| 11 | Measurement noise realism | ±5% uniform noise on flat baseline readings | Inherited from the frozen engine, reused by Phase 1 | Illustrative, unverified against real dosimeter noise | Is ±5% a reasonable noise magnitude for a wearable dosimeter, or should it be a different distribution/magnitude? |
| 12 | Inverse-square area-monitor model | Fixed exponent = 2.0 (engine), separately a true exponent = 1.7 is used in one test scenario to deliberately create a measured-vs-modeled gap | Inherited from the frozen engine, self-disclosed in-engine as a limited approximation | Illustrative | Is the fixed exponent-2 inverse-square model acceptable for this prototype's area-monitor logic, given its self-disclosed limitation? |
| 13 | Chromium browser-version gap | Pinned 141.0.7390.37 vs. actually used 153.0.8010.12 | This project's own test infrastructure | N/A — a reproducibility/methodology matter, not a clinical one | (No domain expertise needed; included for completeness only.) |
| 18 | Realism of not-yet-buildable scenario dynamics (masked-event timing, recovery-to-next-event spacing) | Not yet applicable — no generator exists | `PHASE2B_INTEGRATION_AUDIT.md` §7 | N/A until built | Once a generator for these dynamics is proposed, what durations/spacings would be realistic? |

---

## 4. Illustrative vs. evidence-supported — summary classification

| Status | Rows |
|---|---|
| **Illustrative placeholder (no evidence at all)** | 1, 2, 3, 4, 5, 6, 14, 15, 17 |
| **Inherited from the frozen engine, explicitly unverified against reality** | 11 |
| **Inherited from the frozen engine, self-disclosed as a limited approximation** | 12 |
| **Not yet applicable (feature does not exist yet)** | 7, 8, 9, 10, 18 |
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
explicitly not as a 5-year-averaged compliance calculation.

**No other parameter in this registry (rows 1–18) has any citation
behind it at all.** Where a Review Question above asks whether a
manufacturer specification, regulatory alarm-setpoint guidance, or
published noise/failure-rate data exists, that is a genuine open question
for the reviewer's own expertise — this project does not have, and has
not searched for, such sources.

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
- Any forecasting or rotation implementation (rows 7–10) — not just
  blocked by this review, but explicitly out of scope for this phase
  regardless.
- Any statement that rows 14/15/17's thresholds are clinically
  appropriate, in either direction.

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
| 1 | Procedure-class baselines/multipliers | 3.0–8.0 µSv/h, various ×ranges | | | |
| 2 | Shift-length set | 60/240/480/720 min | | | |
| 3 | Event magnitude/duration ranges | ×2.0–6.0, 1–20 min | | | |
| 4 | Fault duration ranges | 1–30 min by kind | | | |
| 5 | Baseline-2 fixed-threshold setpoint | 2.0× baseline | | | |
| 6 | Baseline-3 moving-average + label | 5 min window, 2.0×, not "conventional" | | | |
| 7 | Forecast horizon (placeholder) | "15 minutes", unbuilt | | | |
| 8 | Worker eligibility model | does not exist | | | |
| 9 | Handoff/briefing duration | not chosen, unbuilt | | | |
| 10 | Rotation scoring weights | not chosen, unbuilt | | | |
| 11 | Measurement noise realism | ±5% uniform | | | |
| 12 | Inverse-square area model | exponent 2.0 (engine), 1.7 (one test case) | | | |
| 13 | Chromium version gap | 141 pinned vs. 153 used | | | |
| 18 | S10/S11 dynamics realism | not yet applicable | | | |

---

## 9. Explicit statement of what this package does and does not do

- **Does:** collect every registered scientific parameter, in plain
  language, with exact values, sources, and review questions, so a
  qualified reviewer can act without reading code.
- **Does not:** change any parameter value; modify the frozen release;
  implement forecasting or rotation; run the statistical campaign; claim
  any expert has approved anything; deploy anything. All of those remain
  exactly as they were before this package was written.
