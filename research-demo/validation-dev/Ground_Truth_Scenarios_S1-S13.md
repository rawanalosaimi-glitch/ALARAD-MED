# Ground-Truth Table — ALARAD Research-Demo v1.2.3 Simulation Scenarios (S1–S13)

**Source:** Extracted verbatim from
`research-demo/releases/html/ALARAD_Prototype_Research_Demo_v1.2.3.html`
(SHA-256 `92e897dd0ff1738f083df829b53f7f46377e042b7019bb9776232792261182ee`):
- S1–S6: `const SCEN=[...]`, lines 2875–2903
- S7–S13: `const SC=[...]`, lines 3373–3404 (inside the `SafetyLab` module)
- Fault-injection and dual-layer matching mechanics: `runWorker()`, lines 3412–3451

No values below are invented. Timing, worker assignments, and expected
outcomes are copied from the scenario object literals; narrative wording is
the engine's own `desc`/`expectText` strings, reproduced verbatim.

Out of scope for this table (not among the 13 primary scenarios, excluded
per the user's request for "all 13 simulation scenarios"): `S3A`, `S3W`,
`S3B` (sweep-only variants of S3, used only by `ref_sweep.py`) and `S3H`
(comparison-only scenario, line 3407).

Two independent kinds of ground truth exist in this engine:
- **S1–S6**: single-layer — radiation-exposure ground truth only (`truth`
  arrays matched against detected episodes via `matchEvents()` →
  precision/recall/F1).
- **S7–S13**: dual-layer — radiation-exposure ground truth (`truth`,
  matched via `revents`) **and** independent data-quality/sensor-fault
  ground truth (`faults`, matched via `dqEvents`), each with its own
  TP/FP/FN/precision/recall, computed and reported separately per worker.

---

## S1 — Normal monitoring

- **Seed:** 20260601
- **Worker:** ST-04, Cath Lab 1, personal dosimeter, flat pattern (baseline ±5% noise)
- **Event type:** None injected
- **Start/end:** N/A
- **Expected:** `{TP:0, FP:0, FN:0}`
- **Detection criterion / expected behavior:** "No abnormal event, no alert (0 TP, 0 FP, 0 FN)."

## S2 — Gradual exposure-rate increase

- **Seed:** 20260602
- **Worker:** ST-11, Fluoroscopy Suite, personal dosimeter
- **Event type:** Ramp (×1.0 → ×4.0)
- **Start/end:** Ramp from minute 15, peak ×4.0 at minute 45, holds to minute 50, then returns to baseline
- **Ground-truth window:** T+15 to T+50, labeled "Gradual increase"
- **Expected:** `{TP:1, FP:0, FN:0}`
- **Detection criterion / expected behavior:** "One labelled event (T+15 to T+50), detected with a delay of several minutes because the engine only flags once the deviation reaches its elevated threshold (1 TP)."

## S3 — Sudden abnormal exposure-rate increase

- **Seed:** 20260603
- **Worker:** ST-06, Cath Lab 3, personal dosimeter
- **Event type:** Step (×4.0)
- **Start/end:** Minute 20 to minute 30
- **Ground-truth window:** T+20 to T+30, labeled "Sudden increase"
- **Expected:** `{TP:1, FP:0, FN:0}`
- **Detection criterion / expected behavior:** "One labelled event (T+20 to T+30). The stateless engine should flag the first elevated minute (delay 0 at confirmation = 1)."

## S4 — Worker relocation and reduced exposure rate

- **Seed:** 20260604
- **Worker:** ST-02, Cath Lab 2, **area-monitor mode** (modeled via inverse-square law) with a separate MEASURED personal-dosimeter series (true exponent 1.7)
- **Event type:** Area source ×4.0 combined with worker relocation
- **Start/end:** Area monitor reads ×4.0 from minute 10; worker stands 1.0 m from source until minute 25, then moves to 2.5 m; monitor itself stays at 1.0 m reference distance
- **Ground-truth window:** T+10 to T+25, labeled "High exposure near source"
- **Expected:** `{TP:1, FP:0, FN:0}`
- **Detection criterion / expected behavior:** "One labelled event (T+10 to T+25) detected from the MODELED estimate; the alert clears after relocation. The modeled dose is expected to under-estimate the measured one after relocation." (Tests the engine's area→personal modeling, not just raw thresholding.)

## S5 — Short transient spike (false-positive test)

- **Seed:** 20260605
- **Worker:** ST-09, CT Suite, personal dosimeter
- **Event type:** Two brief spikes: ×5.0 for 1 minute, ×3.2 for 2 minutes
- **Start/end:** Spike 1 at minute 30 (1 min duration); spike 2 at minute 44 (2 min duration)
- **Ground-truth window:** None (`truth: []`) — by this lab's convention, events shorter than 3 minutes are transients, not abnormal exposure events
- **Expected:** `{TP:0, FP:2, FN:0}`
- **Detection criterion / expected behavior:** "0 labelled events. A stateless engine is expected to flag both spikes (2 FP at confirmation = 1); confirmation = 3 is expected to suppress them." (Explicitly a false-positive-suppression test, not a detection test.)

## S6 — Multiple workers, different patterns

- **Seed:** 20260606
- **Workers (3 simultaneous):**
  - ST-04, Cath Lab 1 — flat baseline with one ×4.0 spike for 1 minute at minute 40; `truth: []` (transient, not a labeled event)
  - ST-11, Fluoroscopy Suite — step ×3.5 from minute 15 to 35; ground-truth window T+15–T+35, "Sudden increase"
  - ST-13, PET/CT Suite — ramp to ×3.0 from minute 25, peak at minute 50, holds to minute 55; ground-truth window T+25–T+55, "Gradual increase"
- **Expected:** `{TP:2, FP:1, FN:0}`
- **Detection criterion / expected behavior:** "Two labelled events (ST-11, ST-13) detected and the ST-04 spike flagged as a false positive (2 TP, 1 FP, 0 FN at confirmation = 1)." Tests that multi-worker scoring is independent per worker.

---

## S7 — Sensor disconnects during normal monitoring

- **Seed:** 20260607
- **Worker:** ST-04, Cath Lab 1, flat baseline
- **Radiation event:** None (`truth: []`)
- **Data-quality fault:** `missing`, minute 25 to 40 (link lost, no samples)
- **Expected behavior:** "No radiation alert. One data-quality incident. Status UNKNOWN during the gap (never NORMAL/SAFE). Unmonitored 15 min; the observed dose is incomplete."
- **Detection criterion:** Data-quality incident only, matched against the fault window via the independent `dqEvents`/`matchEvents()` path; radiation-layer ground truth stays empty throughout.

## S8 — Sensor disconnects during an active radiation incident

- **Seed:** 20260608
- **Worker:** ST-06, Cath Lab 3
- **Radiation event:** Step ×9.0, minute 15 to 45 (sustained, projected dose above critical level); ground-truth window T+15–T+45, "Sustained high-rate event"
- **Data-quality fault:** `missing`, minute 25 to 40 (overlaps the radiation event)
- **Expected behavior:** "Radiation alert raised at the first event minute (immediate criterion). The radiation incident stays OPEN through the disconnect (never auto-closed); a separate data-quality incident is opened; the resumed alert at minute 40 joins the same radiation incident."
- **Detection criterion:** Tests that the two incident types are tracked independently and that a sensor outage never auto-closes an open radiation incident.

## S9 — Invalid reading during an increasing exposure trend

- **Seed:** 20260609
- **Worker:** ST-11, Fluoroscopy Suite
- **Radiation event:** Ramp to ×4.0 from minute 10, peak at minute 40, holds to minute 50; ground-truth window T+10–T+50, "Gradual increase"
- **Data-quality faults:** `invalid` at minute 15–17 (value `NaN` at 15, `-5` at 16); `invalid` at minute 19–20 (missing/`null` value at 19)
- **Expected behavior:** "Invalid minutes are rejected (no zero, no CRITICAL, no dose). The event is still detected once valid readings resume; the invalid values add detection delay. Flapping within 10 observed clear minutes is one data-quality incident."
- **Detection criterion:** Verifies invalid-value rejection does not corrupt dose accounting and does not spuriously fragment the data-quality incident.

## S10 — Frozen sensor reading

- **Seed:** 20260610
- **Worker:** ST-09, CT Suite
- **Radiation event:** Step ×4.0, minute 20 to 45; ground-truth window T+20–T+45, labeled "Masked event" (deliberately mislabeled as a **missed** detection, not a successful one)
- **Data-quality fault:** `frozen`, minute 15 to 50 — sensor repeats its last value exactly, starting before the event and continuing through it
- **Expected behavior:** "The event is MISSED (the frozen value looks normal) — a documented limitation. After 6 identical values the state becomes SUSPECTED_FROZEN (uncertain, not a proven fault) and a data-quality advisory is raised for RSO investigation."
- **Detection criterion:** This is the one scenario in the suite where the documented "expected" radiation-detection outcome is a **miss** by design — it demonstrates a known, disclosed gap (frozen sensors defeat the current rate-based detector) rather than a passing detection.

## S11 — Recovery after a communication interruption

- **Seed:** 20260611
- **Worker:** ST-02, Cath Lab 2
- **Radiation event:** Step ×4.0, minute 35 to 50; ground-truth window T+35–T+50, "Event after recovery"
- **Data-quality fault:** `missing`, minute 15 to 22 (resolves well before the radiation event begins)
- **Expected behavior:** "STALE → DISCONNECTED → RECOVERING → HEALTHY. The later event is detected normally. The data-quality incident stays open until the RSO resolves it, even though the condition has cleared."
- **Detection criterion:** Verifies the sensor-health state machine's exact transition sequence and that a data-quality incident requires explicit RSO resolution (not automatic closure on recovery).

## S12 — Multiple workers with independent sensor failures

- **Seed:** 20260612
- **Workers (3 simultaneous):**
  - ST-04, Cath Lab 1 — flat baseline; `missing` fault minute 20–35; no radiation event
  - ST-11, Fluoroscopy Suite — `invalid` faults at minute 10–13 (`NaN`, `NaN`, `-1`); step ×3.5 radiation event minute 30–50, ground-truth window T+30–T+50, "Sudden increase"
  - ST-13, PET/CT Suite — flat baseline; `frozen` fault minute 25–50; no radiation event
- **Expected behavior:** "Each worker is handled independently: ST-04 DQ only; ST-11 DQ then a detected radiation event; ST-13 SUSPECTED_FROZEN advisory only. Perturbing one worker never changes another."
- **Detection criterion:** Cross-worker isolation test — independence of per-worker state is the thing being validated, not any single detection outcome.

## S13 — Simultaneous radiation and data-quality alerts

- **Seed:** 20260613
- **Worker:** ST-06, Cath Lab 3
- **Radiation event:** Step ×4.0, minute 20 to 40; ground-truth window T+20–T+40, "Sudden increase"
- **Data-quality fault:** `delayed`, minute 24 to 32, lag = 3 minutes (nothing arrives for the first 3 minutes of the window, then samples arrive carrying timestamps 3 minutes old)
- **Expected behavior:** "The radiation alert (raised at minute 20) and a data-quality incident (STALE from minute 25) coexist as two separate incidents. Late samples are never shown as current."
- **Detection criterion:** Verifies the engine never presents a stale/delayed sample as a live current reading, and that simultaneous radiation and data-quality incidents remain distinct.

---

## Matching mechanics (applies to all 13 scenarios)

From `runWorker()` (lines 3412–3451):

- **Radiation layer:** labeled windows in each worker's `truth` array are
  matched against the engine's detected episodes using `matchEvents()` with
  a grace period, yielding TP / FP / FN, from which `metrics()` computes
  precision / recall / F1.
- **Data-quality layer (S7–S13 only):** labeled fault windows in each
  worker's `faults` array are matched against detected data-quality
  episodes, independently, using the same `matchEvents()` routine — a
  separate TP / FP / FN / precision / recall / F1 is computed for this
  layer, per worker.
- **Dose accounting:** `AlaradSafety.doseAccount()` partitions each
  worker's observed minutes into trusted / uncertain / unmonitored, so the
  completeness of the dose estimate itself is scored, not just whether an
  alert fired.

Fault semantics implemented in `faultAt()`/`runWorker()`:

| Fault kind | Effect on the observation stream |
|---|---|
| `missing` | Observation is `null` for the fault window (no sample at all) |
| `invalid` | Observation is a non-physical value (`NaN`, negative, or `null`) at specified minutes |
| `frozen` | Observation repeats the last true value exactly, starting one minute before the fault window |
| `delayed` | No observation for `lag` minutes, then observations arrive carrying timestamps `lag` minutes old |
