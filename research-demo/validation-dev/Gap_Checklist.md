# Research Validation Gap Checklist — ALARAD v1.2.3 vs. ICAIRE Methodology Requirements

**Purpose:** Identify what a governance-framework paper with simulation-based
validation needs, and state plainly which of those needs v1.2.3 already
satisfies, which it partially satisfies, and which are open gaps — based only
on code read and suites actually executed in this session (see
`Verification_Rerun_Report.md` and `Ground_Truth_Scenarios_S1-S13.md`), plus
the prior audit work (`ALARAD_ICAIRE_Technical_Audit.md`,
`ALARAD_November_Foundation_Assessment.md`). No item below claims a result
that was not observed.

Status key: **Present** (implemented and independently verified) /
**Partial** (implemented but limited in scope or rigor) / **Missing** (not
implemented; would need new work, explicitly out of scope for this stage per
the user's instructions).

---

## 1. Algorithmic transparency / "AI" characterization

| Requirement | Status | Evidence |
|---|---|---|
| Document that detection/forecasting is deterministic, not trained ML | **Present** | `riskEngine.js`'s `linearForecast` is ordinary least-squares on a fixed window; classification is fixed-threshold; no model weights, no training data, no trained parameters exist anywhere in either codebase |
| Disclose this characterization to paper reviewers explicitly (not implied) | **Partial** | Established in internal audit reports; not yet written into any paper-facing document |

## 2. Ground truth for validation

| Requirement | Status | Evidence |
|---|---|---|
| Labeled ground truth for every simulated scenario | **Present** | `Ground_Truth_Scenarios_S1-S13.md`, extracted verbatim from source |
| Ground truth independently reviewed/validated by a domain expert (RSO) outside the engineering team | **Missing** | No evidence of independent clinical/RSO sign-off on the `truth`/`faults` window definitions found in any artifact handled this session |
| Ground truth derived from real sensor data (not only synthetic/seeded) | **Missing** | All 13 scenarios use seeded RNG synthetic time series (`seed:` fields); no real wearable-dosimeter dataset was found in either codebase |
| Dual-layer ground truth (radiation events AND sensor/data-quality faults) kept and scored independently | **Present** | S7–S13 maintain separate `truth`/`faults` arrays and separate TP/FP/FN scoring paths (`runWorker()`) |

## 3. Detection performance evaluation

| Requirement | Status | Evidence |
|---|---|---|
| TP/FP/FN computed per scenario against ground truth | **Present** | `matchEvents()` + `metrics()`, independently rerun this session with exact reproduction |
| Precision/recall/F1 reported | **Present** | Same mechanism; `ref_sweep.py` additionally sweeps across detector settings |
| Sensitivity/robustness sweep across detector parameters (confirmation window, noise, threshold) | **Present** | `ref_sweep.py`: 8,640 runs / 432 grid cells, independently reproduced byte-identical this session |
| Statistical significance testing (confidence intervals, hypothesis tests) on reported precision/recall | **Missing** | No CI/test-statistic computation found anywhere in the reviewed code; sweep results are point estimates per grid cell only |
| Comparison against an external/independent baseline detector (e.g., a published or off-the-shelf anomaly detector) | **Missing** | All comparisons found are version-to-version (v1.2.2 vs. v1.2.3, etc.), not algorithm-vs-algorithm |
| Cross-validation or held-out scenario set (vs. tuning and evaluating on the same 13 scenarios) | **Missing** | The 13 scenarios double as both the design target and the evaluation set; no held-out scenario set was found |

## 4. Software-verification vs. scientific-validation distinction

| Requirement | Status | Evidence |
|---|---|---|
| Keep "the code does what it was coded to do" (software verification) distinct from "the method is scientifically sound" (scientific validation) | **Partial** | The 500+85 suites verified in this session are software-verification (regression/UI/wording/manual-report checks) and reference-calculation cross-checks (independent arithmetic reproduction) — genuinely rigorous for that purpose, but they are not a scientific-validation study (no external data, no significance testing, no comparison to literature) |
| State this distinction explicitly in the paper | **Missing** | Not yet written into any paper-facing document; this checklist is the first place it is stated for this purpose |

## 5. Data-quality / sensor-fault realism

| Requirement | Status | Evidence |
|---|---|---|
| Model multiple distinct fault classes (missing, invalid, frozen, delayed) | **Present** | `faultAt()`/`runWorker()`, four fault kinds implemented and exercised across S7–S13 |
| Sensor-health state machine with defined states and transitions | **Present** | `AlaradSafety.sensorStep`: HEALTHY→STALE→DISCONNECTED→RECOVERING, plus INVALID/SUSPECTED_FROZEN, exercised in S7, S10, S11 |
| Fault timing/magnitude parameters drawn from real wearable-sensor failure statistics (vs. hand-chosen demonstration values) | **Missing** | All fault windows (e.g., S7's 25–40, S10's 15–50) are fixed scenario-author choices; no citation to real device failure-rate data was found |
| A documented, disclosed known-limitation case (not hidden as a false "pass") | **Present** | S10 explicitly documents the frozen-sensor detection miss as a known limitation, not papered over |

## 6. Dose accounting

| Requirement | Status | Evidence |
|---|---|---|
| Dose estimate aware of data completeness (trusted vs. uncertain vs. unmonitored minutes) | **Present** | `AlaradSafety.doseAccount()`, exercised across S7–S13 |
| Validation of dose accounting against an independent physical model (e.g., inverse-square law cross-check) | **Partial** | S4 tests area-vs-personal modeling with a deliberately different true exponent (1.7) vs. the model's assumption, which is a genuine robustness test, but it is one hand-constructed scenario, not a systematic physical-model validation study |

## 7. Reproducibility

| Requirement | Status | Evidence |
|---|---|---|
| Independent party can rerun verification suites and get matching results | **Present** | Done in this session; see `Verification_Rerun_Report.md` for exact counts, including the one genuine unresolved documentation discrepancy (flagged, not hidden) |
| SHA-256 / integrity verification of the exact artifact being validated | **Present** | Verified this session, exact match |
| Reproducibility independent of a specific browser engine version | **Partial** | This session's rerun used Chromium 153.0.8010.12 instead of the originally pinned 141.0.7390.37 (network policy blocked the pinned download) — results matched, but this is a real, disclosed version gap that should be closed before any paper claims browser-version-independence |

## 8. Stress / edge-case coverage

| Requirement | Status | Evidence |
|---|---|---|
| Multi-worker independence testing (one worker's fault must not affect another's scoring) | **Present** | S6 (radiation layer), S12 (data-quality layer) both explicitly test this |
| False-positive suppression under short transient noise | **Present** | S5, explicit false-positive test with documented expected FP count |
| Concurrent radiation + data-quality incident handling | **Present** | S8, S13 |
| Load/scale stress testing (many simultaneous workers/facilities, high-frequency sampling) | **Missing** | All scenarios use at most 3 simultaneous workers over a 1-hour window; no scale/performance stress test was found in either package |
| Adversarial/edge-case input fuzzing beyond the four defined fault kinds | **Missing** | No fuzzing harness found; fault injection is limited to the four hand-specified kinds and their hand-chosen timing |

---

## Net assessment

v1.2.3 carries a genuinely substantial, independently-reproducible
**software-verification** suite (500 original checks + 85 RSO workflow
checks, reconfirmed in this session with one disclosed environmental
caveat and one disclosed unresolved documentation discrepancy) plus a real,
non-trivial **detection-evaluation framework** (TP/FP/FN/precision/recall,
dual-layer radiation + data-quality, with an 8,640-run sensitivity sweep).

That is a solid foundation, but it is evaluation **against synthetic,
author-authored ground truth, on the same 13 scenarios used to design the
system** — it is not yet a scientific-validation study in the sense ICAIRE
methodology would typically require (external/real data, held-out
evaluation sets, statistical significance, baseline comparison, independent
expert sign-off on ground truth). Closing those gaps is the next-stage
work this checklist exists to scope — none of it has been started, per the
user's explicit instruction not to implement new algorithms yet.
