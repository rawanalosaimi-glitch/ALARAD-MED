# Phase 2B Integration Audit Report

**Status: read-only audit.** No line of `phase1_simulator/`, `phase2a_adapter/`,
or the frozen v1.2.3 release was modified while producing this report.
Every empirical claim below was checked by actually running code against
the live, unmodified frozen engine in this session (commands reproduced
inline); nothing is inferred from source-reading alone where a live check
was feasible, and nothing is presented as a scientific result — several
findings below are *about* the limits of what Phase 1/2A's software tests
can tell us, which is exactly the distinction task 8's restriction
("do not assume physical validity from passing software tests") asks to
be kept explicit.

**Frozen release re-verified unchanged:** SHA-256
`92e897dd0ff1738f083df829b53f7f46377e042b7019bb9776232792261182ee`.

---

## 1. Audit of the Phase 1-to-engine dose-rate rescaling

**Code:** `phase2a_adapter/detection_adapter.py:75` (`rescale_to_engine_baseline`),
reused by `dq_adapter.py:36` (`build_observations`) and by
`baselines.py:82,115`.

### 1.1 The exact transformation

For a worker, let `B1` = Phase 1's own baseline (`phase1_baseline_rate()`,
`detection_adapter.py:65`: `procedure_classes[procedure_class]["baseline_rate_uSv_h"] * proc_mult`,
reading Phase 1's own shipped config) and `B2` = the frozen engine's own
baseline for the same room/procMult (`baselineRates[room] * proc_mult`,
read live from the engine via `engine_contract.snapshot_engine_constants`).
For every valid reading `r` in Phase 1's observed series:

```
r' = r * (B2 / B1)
```

None/NaN/Infinity pass through unchanged (fault semantics are a property
of validity, not magnitude).

### 1.2 Physical interpretation

If Phase 1 generated `r` as "`x` times Phase 1's own baseline" (e.g. a
step event at `x=4.0`), then `r' = x * B1 * (B2/B1) = x * B2` — i.e. `r'`
is *exactly* "`x` times the **engine's** baseline" instead. The
transformation is a pure re-anchoring of the multiplicative pattern onto
a different absolute baseline; it does not alter `x`, the pattern shape,
noise structure, or timing in any way.

### 1.3 Does it change event severity (risk classification)?

Checked directly against the engine's own classification rule
(`evaluateExposure`, frozen release lines 1950-1972):

```
deviation = (workerRate - baseline) / baseline
if (deviation < devElevated && cumulativeDose < doseElevated) -> low
else if (deviation < devCritical && cumulativeDose < doseCritical) -> med
else -> high
```

`deviation` is computed from `workerRate` and the engine's **own**
`baseline` (`baselineRates[room]*procMult`) — both of which equal `B2` or
a multiple of it after rescaling. Substituting `r' = x*B2`:
`deviation = (x*B2 - B2)/B2 = x - 1`, **independent of `B2`**. The same
substitution with the *unscaled* reading against Phase 1's own baseline
gives the identical `x - 1`. **The deviation-based term of the
classification is therefore mathematically invariant under this
rescaling** — rescaling cannot, by itself, change which side of
`devElevated`/`devCritical` a reading falls on.

The **dose-based term is not scale-invariant**: `cumulativeDose = workerRate * (dur/60) / 1000`
is an absolute quantity in mSv, and classification requires **both**
conditions (an `&&`, frozen release line 1970) to stay `'low'` — so an
absolute dose spike can in principle push a reading out of `'low'`
independently of `deviation`. This was checked numerically, not assumed:
with `dur = 30` min (the fixed horizon both the engine's own `SimLab`
and this adapter use — frozen release's `HORIZON_MIN=30`,
`detection_adapter.py:47`), `doseElevated = 0.15` mSv, `doseCritical = 0.35` mSv,
and the engine's own `baselineRates` (35-92 µSv/h, frozen release line
1498), the dose-based threshold requires `workerRate >= 300 µSv/h`
(elevated) or `>= 700 µSv/h` (critical). For the *largest* engine
baseline (92, Cath Lab 3), that is `x >= 3.26` (elevated) or `x >= 7.6`
(critical) — both **larger** than the deviation thresholds at that same
baseline (`x >= 1.5` elevated, `x >= 2.5` critical). **Conclusion,
checked across the full engine baseline range and Phase 1's generated
event-magnitude range (2.0-6.0x): for the constants actually in force,
the deviation-based criterion always binds at or before the dose-based
criterion, so rescaling has no observed effect on classification
outcomes in this adapter's current use.** This is a property of these
specific constants, not a structural guarantee of the rescaling itself —
see §6.2 for why this matters.

### 1.4 Does it change cumulative dose, and baseline comparisons?

Yes, directly and unavoidably: the per-minute `cumulativeDose` the
engine computes internally (used only for the dose-AND-condition above,
and currently **not** returned by `evaluate_radiation_detection` — see
§6.1) is computed from the **rescaled** `workerRate`, i.e. on the
engine's `B2` scale, not Phase 1's `B1` scale. **This is a different
absolute number than Phase 1's own `true_dose_mSv`/`observed_dose_mSv`**
(computed by `phase1_simulator/dose.py` from the *unscaled* series). The
two are not currently compared anywhere in Phase 2A's code, so no silent
inconsistency has yet occurred in practice — but if a future phase
surfaces or compares dose quantities from both sources, they must be
labeled by which baseline scale produced them; they are not
interchangeable.

**"Baseline comparisons" are, by design, exactly what changes**: the
whole purpose of rescaling is to re-anchor Phase 1's pattern onto a
different baseline for classification purposes. Any reported number in
µSv/h or mSv that passed through `rescale_to_engine_baseline` is on the
**engine's** scale and must never be combined with an unscaled Phase 1
number without that being explicit.

---

## 2. Can the simulator generate observations directly on the engine's scale?

**Yes — this is a cleaner fix than rescaling, and is proposed (not
implemented) below.**

Phase 1's `_make_worker()` (`phase1_simulator/scenario.py`) currently
computes `baseline = proc_cfg["baseline_rate_uSv_h"] * proc_mult` from
Phase 1's **own**, independently-chosen `procedure_classes` table
(`phase1_simulator/config/simulation_config.json`: 3.0-8.0 µSv/h). The
frozen engine computes baseline the same way — `baseline = baselineRates[room] * procMult`
(frozen release, `runWorker`, line 2936) — from **its own** table
(35-92 µSv/h, by room rather than procedure class).

**Proposal:** redefine Phase 1's `procedure_classes` config so that each
entry's baseline is derived from the engine's own `baselineRates[room]`
for a room consistent with that procedure class, dropping Phase 1's
independently-invented `baseline_rate_uSv_h` numbers entirely, and
keeping only `proc_mult_range` as Phase 1's own free parameter — exactly
mirroring the engine's own `baseline = baselineRates[room] * procMult`
formula. This would make Phase 1's raw generated values numerically
identical in scale to what the engine expects, **eliminating the need
for `rescale_to_engine_baseline` entirely** for the radiation layer (and,
by the same logic, for the DQ layer's quantization-sensitive
`sensorStep`).

**What this does *not* resolve:** both `baselineRates` (frozen release
line 1497, commented *"CONFIGURABLE, ILLUSTRATIVE placeholder values (not
derived from real data)"*) and Phase 1's own baselines are equally
unvalidated placeholders. Adopting the engine's numbers removes the
*scale mismatch*, not the *lack of evidence* behind either set of
numbers — both still need the same RSO/medical-physicist review (§8).

**Not implemented now**, per the restriction to audit, not change, the
simulator/adapter. See §10 for where this sits in the corrective plan.

---

## 3. S4 area-mode schema gap: investigation and proposed integration path

**Confirmed gap, exact location:** `phase1_simulator/output.py`'s
`run_to_dict()` serializes, for every worker, `mode`, `proc_mult`,
`series.{true_rate_uSv_h,observed_rate_uSv_h}` — but never the
`WorkerSpec.area_params` dict (`reference_distance_m`, `distance_before_m`,
`distance_after_m`, `move_at`, `shielding`, `true_exponent`) that
`phase1_simulator/scenario.py`'s `"area_relocation"` branch (lines ~190-205)
already computes and holds internally. The data exists; it is discarded
before serialization.

**A second, previously undocumented gap, found during this audit:** Phase 1's
`simulate_run()` (`scenario.py`) computes, for area-mode workers, the
**raw area-monitor reading** (`area_reading_series`) and then immediately
converts it in-process to a MODELED worker-position estimate
(`modeled_observed`, using Phase 1's own fixed `model_exponent=2.0`)
*before* writing to `observed_series`. Only the **already-converted**
series is serialized. The frozen engine's own `evaluateExposure(mode:'area')`
performs its **own** inverse-square conversion internally
(`workerRate = rate * (refDist/dist)^2 * shield`, line 1961) — feeding it
an *already-converted* value would double-apply the geometry conversion.

**Proposed integration path (not implemented):**
1. Extend `phase1_simulator/output.py` to serialize, for area-mode
   workers only: `area_params` (as already held in `WorkerSpec`) and a
   new `series.area_monitor_raw_rate_uSv_h` — the **pre-conversion** raw
   monitor reading (currently a local variable, `area_reading_series`,
   in `scenario.simulate_run`), alongside the existing already-converted
   series (kept for backward compatibility with any existing consumer).
   Purely additive; no existing field changes shape.
2. In `detection_adapter.py`, add an area-mode path that: rescales the
   **raw** monitor series (not the converted one) to the engine's
   baseline exactly as the personal-mode path does; computes `dist(t)`
   from `area_params`; calls `evaluateExposure(... mode:'area', dist, refDist, shield)`
   per minute, letting the **engine** perform its own fixed-exponent-2
   conversion.
3. This reproduces, faithfully, exactly the comparison S4 was designed to
   test: Phase 1's ground truth uses `true_exponent` (currently 1.7,
   `scenario.py`'s `"area_relocation"` branch) for the *true* physical
   series, while the engine's own classification uses its fixed
   exponent-2 model — so the engine's detection of S4-like Phase 1 runs
   would measure the real, documented MEASURED-vs-MODELED discrepancy,
   not an adapter-invented one.

**Not implemented now** — this is a scoped, two-file, additive change
proposal for the corrective plan (§10), not executed in this audit.

---

## 4. Investigation: the immediate-alert dose bypass

**Code:** `AlaradSafety.immediateAlert`/`immediateThreshold`/`setPolicy`
(frozen release lines 1371-1374); consumed by `SimLab.runWorker`'s
`imm` computation (line 2964) and `SimLab.defaultOpts` (line 2932).

**What it does:** `AlaradSafety`'s global policy state defaults to
`IMM = {mode:'dose', doseMsv:null}` — **enabled by default**, confirmed
live: `AlaradSafety.policy()` returns `{mode:'dose', doseMsv:null}` on a
freshly loaded page. `SimLab.defaultOpts()` defaults `opt.immediate` to
`AlaradSafety.policy().mode` — i.e. **`SimLab.run()`'s own default
behavior already uses the dose-based bypass**, unless something
explicitly turns it off. When a worker's per-minute projected dose
(`cumulativeDose`, computed with the same `dur=30` horizon) reaches
`immediateThreshold()` (default: `CONFIG.doseCritical = 0.35` mSv, i.e.
`workerRate >= 700 µSv/h`), `buildEpisodes` is allowed to raise the alert
at that minute even if the K-minute confirmation window has not yet
elapsed.

**This adapter always calls `buildEpisodes(flagged, K, null)`** — the
`imm` argument is hardcoded `null` in every call site in
`detection_adapter.py`, `baselines.py`, and `dq_adapter.py`. The
confirmation-window-only path is used unconditionally, regardless of
`AlaradSafety`'s actual policy state, which this adapter never reads.

**Concretely checked whether this matters** (it was not assumed to be
inert): for every reference scenario this adapter's reproduction tests
actually used — S1-S3, S5, S6 at K=1 — the engine's own computed
`episode.immediate` field is `false` throughout, **at every K tested
(1, 3, 5, 10)**. The reason: none of these scenarios' injected
multipliers are large enough, at any of the engine's own room baselines,
to reach the 700 µSv/h immediate-dose threshold. **So for the specific
scenarios this adapter's "reproduces exactly" claim already covers, the
`imm=null` simplification happens to make no difference** — but this was
discovered empirically, not guaranteed by the adapter's design.

**S8 is the counter-example, checked directly:** S8's own documented
design (`Ground_Truth_Scenarios_S1-S13.md`) is a sustained ×9 event
*"projected task dose above the critical level"* — specifically built to
trigger this bypass. Live check against `SafetyLab.run('S8', K)`:

| K | engine's own `episode.immediate` |
|---|---|
| 1 | `false` (confirmation already trivially met at K=1) |
| 3 | **`true`** |
| 5 | **`true`** |

At K=3 and K=5, the real engine detects S8's event *immediately* at
minute 15 (bypassing confirmation) specifically because of this feature.
An adapter call with `imm=null` at K=3 or K=5 against an S8-like input
would report a detection roughly `K-1` minutes **later** than the real
engine actually would — a genuine, now-evidenced discrepancy between
this adapter's current behavior and the real engine's default behavior,
for any scenario severe enough to cross the dose threshold.

**How it should be represented in the evaluation protocol (recommendation,
not yet implemented):** the methodology document should treat the
immediate-dose bypass as a **named, togglable mode** of the candidate
detector — "candidate (confirmation-only)" vs. "candidate (confirmation +
immediate-dose bypass, policy = engine default)" — evaluated and reported
as two distinct configurations wherever K > 1 is used, rather than a
single, implicitly confirmation-only "the detector." This adapter should
gain an `imm` pass-through parameter (plumbing `AlaradSafety.immediateAlert`
per minute, using each minute's own `cumulativeDose` from `evaluateExposure`'s
return value) so both configurations can be evaluated faithfully. See §10.

---

## 5. Audit: do the candidate and baseline detectors receive identical observations, temporal information, and scoring rules?

Checked by direct code comparison, not assumed:

| Aspect | Candidate (`detection_adapter.py`) | Baseline 0 | Baseline 1 (`baselines.py:70`) | Baseline 2 (`baselines.py:82`) | Baseline 3 (`baselines.py:115`) |
|---|---|---|---|---|---|
| Source series | `worker["series"]["observed_rate_uSv_h"]`, decoded | n/a (never flags) | Same call as candidate (literal passthrough) | Same field, same `decode_observed_value` | Same field, same `decode_observed_value` |
| Rescaling | `rescale_to_engine_baseline` | n/a | Same (via candidate) | Same function, called independently | Same function, called independently |
| **Validity gate** | `!SimLab.pure.validReading(r)` — the engine's own complete rule (rejects None, NaN, negative, and values > 1e6) | n/a | Same (via candidate) | **`v is None or v != v` only** (`baselines.py:101`) — does **not** check negative values or the 1e6 ceiling | **Same narrower check** (`baselines.py`, moving-average loop) |
| Ground truth | `worker["truth_events"]` | Same | Same | Same | Same |
| Matching (`matchEvents`) | Real engine call, `grace` default 2 | Real engine call, `grace` default 2 | Same | Same | Same |
| Scoring (`metrics`) | Real engine call | Real engine call | Same | Same | Same |
| Confirmation window K | Caller-supplied (free parameter) | Hardcoded 1 | Caller-supplied (should equal candidate's) | **Hardcoded 1** (by definition — methodology §4a: "no confirmation window") | **Hardcoded 1** (by definition) |

**Finding 1 (discrepancy, not yet consequential in practice):** Baselines
2 and 3 implement their **own**, narrower validity check (`v is None or v != v`)
rather than reusing `SimLab.pure.validReading` as the candidate path
does. In the current archetype set, Phase 1's `invalid` fault always uses
`NaN` as its sentinel (`phase1_simulator/faults.py`'s default
`invalid_value = float("nan")`), so this narrower check happens to
produce the same result as the engine's full rule *for every fault
Phase 1 currently generates*. It would **not** necessarily agree if a
future scenario injected a negative or out-of-range (but non-NaN) value
as its "invalid" sentinel. **Recommendation:** baselines 2/3 should call
`SimLab.pure.validReading` directly, exactly as the candidate does,
rather than maintaining a second, independently-written validity rule.

**Finding 2 (a usage-discipline gap, not a code bug):** the candidate's
confirmation window `K` is a free parameter with no enforced relationship
to Baseline 1's `K`; nothing in the API prevents a caller from comparing
a K=1 candidate against... a K=1 Baseline 1 (trivially the same thing) or
a K=5 candidate against Baseline 1 still called at a different K. In this
session's own smoke run, both were called at K=1 consistently, but this
is caller discipline, not an enforced invariant. **Recommendation:**
`metrics_extra.summarize` or a new comparison-runner helper should accept
a single `K` and pass it to every method that takes one, rather than each
call site choosing independently.

**Finding 3 (confirmed non-issue):** `grace` defaults to `2` identically
across every method and was not found overridden inconsistently anywhere
in `run_phase2a_smoke.py` or the test suite.

**No baseline exists for the data-quality layer at all** — `baselines.py`
covers only the radiation-detection comparators. This is a coverage gap
(§7), not a divergence, since Phase 2A's tasks only asked for radiation
baselines — but it means no apples-to-apples DQ comparison currently
exists.

---

## 6. Discrepancies between the implemented adapter and the approved methodology

1. **Dose-unit bifurcation not anticipated by methodology §1.** The
   methodology's "Definitions" section describes a single, consistent
   µSv/h / mSv convention. The as-built adapter's rescaling (§1 above)
   introduces a second, engine-scale dose convention for internal
   classification purposes, not reconciled with Phase 1's own dose
   definitions anywhere in the methodology text. **Recommendation:** a
   methodology revision should explicitly document which "baseline scale"
   any reported dose or deviation number is expressed on.
2. **The engine's own `baselineRates`/`CONFIG` are not Parameter Registry
   items.** The methodology's §9 registry (13 rows) covers Phase 1's own
   provisional parameters and a few engine-adjacent items (noise realism,
   inverse-square acceptability), but never registers the engine's own
   `baselineRates` (35-92 µSv/h by room) or `CONFIG` thresholds
   (`devElevated/devCritical/doseElevated/doseCritical`, `dur=30`) as
   themselves-provisional, evidence-pending values — even though Phase 2A's
   rescaling now depends on them directly. **Recommendation:** add two new
   registry rows (see §8).
3. **Baseline 2/3 descriptions (§4a) are silent on input-scale
   reconciliation.** The methodology specifies *what* the two new
   baselines compare against ("a fixed multiple of the engine's own
   baseline") but never anticipated that Phase-1-generated input would
   need rescaling to reach that baseline at all — this problem only
   surfaced once real integration was attempted. Not a contradiction, but
   an implementation detail the methodology text does not cover.
4. **The immediate-alert dose bypass (§4 above) is entirely absent from
   the methodology document.** §4a/§5 describe "confirmation window K" as
   if it were the complete detection-timing mechanism; the real engine's
   actual behavior (confirmation window **and** a dose-based bypass,
   active by default) is a materially different, more complex mechanism.
   Phase 2A's "reproduces the frozen detector's output" claim
   (`Verification`/smoke reports) is correct **only for the scenarios and
   K values actually tested**, where the bypass happens not to matter —
   it is not yet a general claim about the full detector, and the
   methodology should be revised to scope this precisely rather than
   leave it implicit.
5. **§5a's degenerate-scenario and false-alarm-rate conventions were
   checked and found consistently implemented** — `metrics_extra.py`'s
   handling of undefined precision/recall and its false-alarms-per-
   worker-shift definition match the methodology text as written. Noted
   here so the audit records a verified-consistent item, not only gaps.
6. **Forecasting (Track A) and rotation (Track B) remain unimplemented**,
   consistent with both the methodology and every prior phase's explicit
   restriction — confirmed as "no discrepancy," not overlooked.

---

## 7. Traceability matrix — detection pathways and scenario classes

Status key: **Covered** (exact-match reproduction test exists and
passes) / **Partial** (exercised by an adapter-level test using a Phase
1-generated analog, but not reproduction-verified against the engine's
own hand-authored scenario) / **Missing** (no path exists at all).

| Scenario (engine's own) | Pathway | Mode | Status | Evidence / gap |
|---|---|---|---|---|
| S1 Normal monitoring | Radiation | personal | **Covered** | `test_reference_reproduction.py::test_all_six_radiation_reference_scenarios_reproduce_exactly` |
| S2 Gradual increase | Radiation | personal | **Covered** | same |
| S3 Sudden increase | Radiation | personal | **Covered** | same |
| S4 Relocation | Radiation | **area** | **Missing** | `NotImplementedError` by design; see §3 |
| S5 Transient spike (FP test) | Radiation | personal | **Covered** | same |
| S6 Multi-worker mixed | Radiation | personal | **Covered** | same (all 3 workers) |
| S7 Sensor disconnect (no event) | Data quality | personal | **Covered** | `test_s7_sensor_state_sequence_and_dq_metrics_reproduce_exactly` — full state-sequence + dTP/dFP/dFN exact match |
| S8 Disconnect during active incident | DQ + radiation, concurrent | personal | **Partial** | Phase 1's `fault_during_event`/`concurrent_alert_and_fault` archetypes are structural analogs, adapter-tested (`test_dual_layer.py`), but not diffed against the engine's own S8; **also the one scenario this audit found the immediate-alert bypass actually changes (§4)**, not yet accounted for |
| S9 Invalid during increasing trend | DQ + radiation | personal | **Partial** | same reasoning as S8; no Phase 1 archetype combines "ramp event + invalid-at-onset" exactly as S9 does |
| S10 Frozen masks event (documented miss) | DQ + radiation | personal | **Missing** | Phase 1's `fault_frozen` archetype injects **no** radiation event at all (checked in `scenario.py`'s `fault_frozen` branch — no `_add_step`/`_add_ramp` call); the specific "frozen sensor masks a real event" dynamic S10 is designed to test does not exist in Phase 1 yet |
| S11 Recovery, then a later event | DQ then radiation (sequential) | personal | **Missing** | no Phase 1 archetype combines "fault fully resolves, then a *separate, later* event"; existing analogs only overlap fault and event in time |
| S12 Multi-worker independent failures | DQ | personal | **Covered-equivalent** | Phase 1's `multi_worker_faults` directly mirrors S12's structure; per-worker isolation explicitly tested (`test_dual_layer.py`), though not diffed against the engine's own S12 output |
| S13 Simultaneous radiation + DQ (delayed) | DQ + radiation, concurrent | personal | **Partial** | Phase 1's `concurrent_alert_and_fault` is a structural analog (delayed fault + step event), adapter-tested, not reproduction-verified against S13 itself |
| Baseline 0/1/2/3 comparators | Radiation only | — | **Partial** | implemented and tested for radiation; **no DQ-layer baseline exists** (§5, Finding under "no baseline... for DQ") |
| Immediate-alert bypass | Radiation (timing) | — | **Missing** | never invoked (§4); real engine uses it by default |
| Forecasting evaluation | — | — | **Missing (by design)** | Track A, scheduled for a later phase per explicit restriction |
| Rotation evaluation | — | — | **Missing (by design)** | Track B, no algorithm exists, per explicit restriction |

---

## 8. Parameters requiring medical physicist / RSO review before results are scientifically interpretable

Builds on `ICAIRE_Simulation_Validation_Methodology.md` §9's existing 13
rows (still all open) and adds items this audit newly surfaced:

| # | Parameter | Newly found by | Why expert review is required |
|---|---|---|---|
| 14 (new) | The frozen engine's own `baselineRates` (35-92 µSv/h by room) | §2, §6.2 | Self-disclosed by the engine's own source comment as "ILLUSTRATIVE... not derived from real data," yet now load-bearing for every Phase 2A classification decision via rescaling |
| 15 (new) | The frozen engine's own `CONFIG` thresholds (`devElevated/devCritical/doseElevated/doseCritical`, `dur=30`) | §1.3, §6.2 | Source comment: "PROTOTYPE warning thresholds — configurable placeholders, NOT regulatory limits"; this audit's finding that deviation always binds before dose (§1.3) is a property of *these specific numbers* — any revision to them could change that, with consequences for whether rescaling stays severity-neutral |
| 16 (new) | Physical/conceptual validity of mapping Phase 1's **procedure-class** framing onto the engine's **room-based** framing via rescaling | §1, §2 | Not just a numeric question: does "a diagnostic-fluoroscopy pattern, rescaled onto Cath Lab 1's illustrative baseline" represent a coherent simulated worker? This is a domain-interpretation question, not resolvable by code |
| 17 (new) | Whether/how the immediate-alert dose bypass should be represented as a *clinical* assumption (not just a software toggle) | §4 | The bypass encodes a real safety-workflow judgment ("an immediately dangerous dose should alert faster than the standard confirmation window") — whether `doseCritical=0.35 mSv` over a 30-minute horizon is the clinically right trigger is an RSO/medical-physicist question |
| 18 (new) | Realism of the missing S10/S11 scenario dynamics once built (masked-event duration, recovery-to-next-event spacing) | §7 | Before Phase 1 is extended to cover these (§10), the timing/duration ranges chosen need the same domain grounding as rows 3/4 already flagged |

Rows 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13 from the existing registry
remain open and are not restated in full here; nothing in this audit
resolved any of them.

---

## 9. Prioritized recommendations

1. **(High)** Implement the §4 immediate-alert pass-through before any
   S8/S9/S13-class scenario is evaluated or reported — this is the one
   finding in this audit with a demonstrated, nonzero effect on detection
   timing at K>1 for a real reference scenario.
2. **(High)** Fix baselines 2/3's validity check to reuse
   `SimLab.pure.validReading` (§5, Finding 1) — currently latent, but a
   single-line, low-risk fix that removes a real (if not yet
   consequential) inconsistency between candidate and baselines.
3. **(Medium)** Implement §2's proposal (Phase 1 generates directly on
   the engine's baseline scale) — removes the need for
   `rescale_to_engine_baseline` entirely for future work, simplifying
   everything downstream, including the DQ layer's quantization
   sensitivity that caused the bug found in Phase 2A.
4. **(Medium)** Implement §3's S4 schema extension and area-mode adapter
   path — closes the one fully-Missing radiation pathway for existing
   scenarios.
5. **(Medium)** Add registry rows 14-18 (§8) to the methodology document
   in its next revision.
6. **(Low, but should precede any paper claim)** Build Phase 1 archetypes
   for S10's masked-event and S11's recovery-then-later-event dynamics
   (§7), and a DQ-layer baseline comparator (§5).
7. **(Low)** Enforce a single shared `K` across candidate/Baseline 1 in
   whatever runs a side-by-side comparison, rather than relying on caller
   discipline (§5, Finding 2).

---

## 10. Proposed corrective implementation plan (for approval, not executed)

A plausible ordering for a future "Phase 2B.1" corrective pass, informed
by the priorities above — **none of this is implemented by this audit**:

1. `baselines.py`: swap the ad hoc `v is None or v != v` check for
   `SimLab.pure.validReading` in both baseline 2 and 3 (smallest, lowest-risk fix).
2. `detection_adapter.py`/`dq_adapter.py`/`baselines.py`: add an `imm`
   parameter threading `AlaradSafety.immediateAlert` per minute (using
   each minute's own `cumulativeDose`, already computed by
   `evaluateExposure` but currently discarded by `classify_series`) into
   `buildEpisodes`, defaulting to the engine's own live policy rather
   than hardcoded `null`; re-run `test_reference_reproduction.py` against
   S8 specifically to confirm the gap in §4 closes.
3. `phase1_simulator/config/simulation_config.json` +
   `phase1_simulator/scenario.py`: redefine `procedure_classes` to derive
   baseline from the engine's own `baselineRates[room]` rather than an
   independently-chosen number (§2) — **this changes Phase 1's
   already-accepted output**, so it should go back to the user for
   explicit re-approval of Phase 1, not be bundled silently into a Phase
   2B change.
4. `phase1_simulator/output.py` + `detection_adapter.py`: the S4 area-mode
   schema extension and adapter path (§3).
5. New Phase 1 archetypes for S10/S11 dynamics, and a DQ-layer baseline
   module (§7) — scoped as their own follow-up, not required before the
   above four.
6. Methodology document revision adding registry rows 14-18 (§8).

---

## Explicit statement of what has and has not been done

- **Done:** every empirical claim above was checked by running real code
  against the live, unmodified frozen engine in this session (commands
  available in this session's history); the traceability matrix and
  registry additions reflect what was actually found, not estimated.
- **Not done:** no change to `phase1_simulator/`, `phase2a_adapter/`, or
  the frozen release; no statistical campaign; no forecasting or rotation
  work; nothing deployed or merged. The corrective plan in §10 is a
  proposal awaiting approval, not a completed action.
