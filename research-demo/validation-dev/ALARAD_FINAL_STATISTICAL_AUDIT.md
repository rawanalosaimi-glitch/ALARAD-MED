# ALARAD — Final Statistical Audit

**An independent-style re-verification of the supplementary validation
round's run counts, statistics, and endpoint definitions, performed on
branch `research/icaire-v123-validation` by directly re-deriving every
number below from the raw JSON files and source code — not by copying
values from `analysis_summary.json` or any prior document.** No
algorithm was changed and no simulation was re-run to obtain this
audit's numbers; every recomputation below used data already stored in
`phase3c_supplementary_output/`. Frozen `ALARAD_Prototype_Research_Demo_v1.2.3.html`
SHA-256 re-verified unchanged:
`92e897dd0ff1738f083df829b53f7f46377e042b7019bb9776232792261182ee`.

---

## Task 1 — Run-count reconciliation (872 vs. 900)

**Direct answer: 900 was never the correct planned count. The correct
planned-and-executed count of independent simulation replicates is
870. The remaining 2 of the reported 872 rows are deliberate,
single, non-replicate records, not simulation runs, exclusions, or
failures.**

The methodology's shorthand "10 + 8 + 12 scenarios with 30 seeds each"
describes the number of named *scenario definitions*, not the number
of scenario-seed combinations that were ever intended to run a
simulated seed loop. One of the 12 Experiment C scenario definitions
(C10, "RSO acknowledgement rejected") was designed, from the moment it
was written, to check whether the implemented state machine supports a
rejection transition at all — it does not — and to report that finding
as a single capability-check record, never to run any seeds. The
correct planned scenario count with an actual seed loop is therefore
**29, not 30** (10 + 8 + 11), giving **870** planned-and-executed
scenario-seed combinations, not 900.

### Full scenario-by-scenario reconciliation

| Scenario | Planned seeds | Executed | Excluded/skipped | Additional rows | Rows in raw file | Notes |
|---|---|---|---|---|---|---|
| A1–A10 (10 scenarios) | 30 each (300 total) | 300 | 0 | 0 | 300 | Full execution, no exceptions |
| B1, B2, B3, B5, B6, B7, B8 (7 scenarios) | 30 each (210 total) | 210 | 0 | 0 | 210 | Full execution |
| B4 | 30 | 30 | 0 | **1** (`B4_direct_path_comparison`) | 31 | The extra row reuses seed 920000 (B1's own first seed) to run the SAME delayed observation directly through `sensor_validity.sensor_step_once`, bypassing the orchestrator, as an illustrative comparison — not a new independent replicate |
| C1–C9, C11, C12 (11 scenarios) | 30 each (330 total) | 330 | 0 | 0 | 330 | Full execution |
| C10 | **0** (by design — this scenario was never given a seed loop) | 0 | — | **1** (status record) | 1 | Not a simulation run; checks `scheduling.py`'s own source for a rejection state/transition and finds none |
| **Total** | **870** | **870** | **0** | **2** | **872** | |

**Answers to the seven specific sub-questions:**

1. **Planned unique scenario-seed combinations: 870** (29 scenarios ×
   30 seeds). Not 900 — C10 was never planned to have a seed loop.
2. **Executed: 870 of 870 (100%), 0 failures.** Directly confirmed:
   `len(set((case_id, seed) for row in experiment_a_raw.json)) == 300`;
   the equivalent count for B's 8 seeded scenarios is 240 and for C's
   11 seeded scenarios is 330; 300+240+330 = 870.
3. **Excluded, skipped, or NOT_IMPLEMENTED: 0 scenario-seed
   combinations were excluded or skipped.** C10 is reported
   NOT_IMPLEMENTED as a single capability-check record because no
   seed loop was ever started for it — this is a documented scope
   decision made before execution, not an exclusion of planned work.
4. **Why Experiment B has 241, not 240, rows:** 240 genuine
   independent replicates (8 scenarios × 30 seeds) plus 1 additional,
   non-independent, illustrative row (`B4_direct_path_comparison`)
   appended once, after the seed loop, reusing an already-used seed.
5. **Why Experiment C has 331, not 360, rows:** 360 would require all
   12 scenario slots to run 30 seeds; only 11 do (330 total). C10 ran
   zero seeds by design and instead emits exactly 1 status record —
   330 + 1 = 331.
6. **Do any rows represent diagnostic checks, aggregate records,
   duplicated seeds, or non-independent observations?** Yes, exactly
   2 of 872: `B4_direct_path_comparison` (a diagnostic comparison,
   re-using seed 920000, which already appears as B1's first
   replicate — this is a duplicated seed used deliberately for a
   different, non-statistical purpose, not a second independent draw)
   and `C10` (a capability-check record with no seed at all). Every
   other row (870 of 872) is confirmed to carry a unique
   `(case_id, seed)` pair with no duplication anywhere in any of the
   three raw files (directly checked: `len(set(...)) == len(rows)` for
   every experiment's seeded scenarios).
7. **Does 872 represent simulation runs, output records, or a
   mixture?** **A mixture**: 870 output records each corresponding to
   one genuine, independent simulation run, plus 2 output records that
   are not simulation runs at all (one is a direct non-orchestrator
   engine-API comparison; one is a static source-code capability
   check). Prior documents' "872 total rows, 0 run failures" statement
   was true as far as it went but did not make this distinction
   explicit — corrected in `ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md`
   section 1 and `ALARAD_FINAL_SUPPLEMENTARY_VALIDATION_REPORT.md`
   section 3, both updated alongside this audit.

No output record was relabeled as an independent replicate without
first verifying its `(case_id, seed)` uniqueness directly against the
raw files; the 2 non-replicate rows are excluded from every
statistical calculation below and in the corrected documents.

## Task 2 — Independent statistical re-verification

Every item below was recomputed directly from
`phase3c_supplementary_output/experiment_a_raw.json` in this session,
using fresh code, not by reading `analysis_summary.json`'s stored
values.

| Item | Verification method | Result |
|---|---|---|
| Pairing keys / independence unit | Confirmed one `(case_id, seed)` row carries both `policies.cgdtr` and `policies.reference_rule` nested under it — a true paired design, not two independently sampled groups | **Correct** |
| Unique scenario-seed counts | `len(set((r['case_id'], r['seed']) for r in rows_a)) == 300 == len(rows_a)` | **Confirmed, no duplicates** |
| Primary endpoint (max individual dose, CGDTR − reference-rule) | Recomputed per case from `cgdtr['max_individual_dose_mSv'] − reference_rule['max_individual_dose_mSv']` for all 300 rows | **Matches `analysis_summary.json` exactly**: 0.0 for A1/A2/A3/A4/A5/A6/A7/A9/A10, −0.074940 for A8 |
| Population-average and conditional effects | Recomputed the 210-pair pooled family (A1/A2/A4/A5/A6/A7/A9) independently: mean = 0.0, 0 of 210 nonzero | **Matches**; conditional effect is undefined (no divergent pairs show a nonzero difference) rather than equal to the population average by coincidence — both are 0.0 for the same underlying reason (section Task 3) |
| 95% bootstrap CIs | Recomputed A8's CI with `stats_common.bootstrap_ci`: (−0.074940, −0.075048, −0.074826) | **Matches** |
| Bootstrap resampling unit | Confirmed `bootstrap_ci` resamples at the level of the list passed to it — one element per independent `(case, seed)` replicate's own paired difference, never a per-minute or sub-run value | **Correct unit of resampling** |
| Wilcoxon signed-rank tests | Recomputed directly with `scipy.stats.wilcoxon(cg, rr)` for A8: statistic=0.0, p=1.8626e-09 — identical to `stats_common.wilcoxon_paired`'s wrapped result | **Matches, both the wrapper and raw scipy agree** |
| Zero differences and ties | For the 9 all-zero cases, `wilcoxon_paired` correctly returns `p_value=None` with an explicit `"undefined: no pairs or all differences are zero"` note, never a fabricated p-value or a silent 0/1 | **Correct, verified by re-running `wilcoxon_paired` directly on each case's own 30 pairs** |
| Holm-Bonferroni family | Re-inspected `analysis_summary.json`'s stored `holm_bonferroni_per_case`: family size = 10 (all Experiment A cases, including the 9 undefined ones, which correctly still count toward `m`); only A8 carries a real p-value and is correctly flagged significant at `alpha/m = 0.005` | **Correct construction and correction** |
| Cross-scenario pooling | Confirmed the pooled 210-pair family only combines the 7 scenarios sharing the identical pre-declared hypothesis (`expect_cgdtr_ref_diverge=True`); A3, A8, A10 are never folded into that pool. Seed ranges for every scenario are disjoint by construction (`EXPERIMENT_A_SEED_BASE + case_index*1000 + i`), so no two scenarios' replicates share a seed, and no hidden dependence across scenarios was found | **No improper pooling; no cross-scenario seed reuse found** |
| Effect sizes and units | All reported in mSv, consistent with every other document in this project; no unit conversion errors found | **Correct** |
| Figure/table consistency | Spot-checked `figures_supplementary/max_individual_dose_comparison.png`'s generating code (`generate_supplementary_figures.py::fig_max_individual_dose_comparison`) against `analysis_summary.json`'s stored per-case means — consistent | **Consistent** |

**On the specific items flagged for special attention:**

- **The 210 controlled selection-divergence replicates**: confirmed
  correct and independent (7 scenarios × 30 seeds, disjoint seeds, one
  paired difference per replicate).
- **A8's mean difference of −0.0749 mSv**: independently reproduced to
  6 decimal places (−0.074940), with all 30 individual differences
  negative (consistent direction) and a Wilcoxon p-value of 1.86×10⁻⁹ —
  this is genuine statistical evidence of a dose difference under A8's
  specific controlled condition, not an artifact.
- **Repeated seeds across different scenarios**: none found. Every
  scenario within an experiment uses a disjoint seed offset by
  construction; the one deliberate seed reuse (`B4_direct_path_comparison`
  reusing seed 920000) is a single, explicitly labeled, non-statistical
  illustration, already excluded from every statistical calculation —
  no stratified or hierarchical resampling correction is needed because
  no genuine dependence across independent replicates exists.

**Distinguishing statistical evidence from deterministic verification
(explicitly, per task 2's own instruction):** the claim "CGDTR selects
a different worker than reference-rule when a real choice exists" is a
**deterministic verification of algorithm behavior** — it is checked
directly against `rotation_events`, is true in 210 of 210 replicates
with no exceptions, and requires no hypothesis test (there is no
sampling variability in whether a deterministic function produces
output X or Y given fixed inputs). The claim "this produces a
measurably different roster-wide dose outcome" is a **statistical
claim about a measured quantity**, and it is supported by genuine
statistical evidence only for A8 (Wilcoxon p=1.86×10⁻⁹); for the other
6 scenarios, the measured quantity is 0.0 with p undefined, and no
statistical test can or should be invented where the underlying
difference is identically zero by the mechanism explained in task 3
below.

## Task 3 — Dose-attribution endpoint audit

**The methodology's own, authoritative, and already-correctly-implemented
definition is option (1): incremental dose accrued during the
simulated shift, measured from shift start.** This is traced directly
to `PHASE3B_ROTATION_ALGORITHM_DESIGN.md` line 286's definition table:
*"`WorkerAccumulatedShiftDose(W, t)`... Σ of Dose(mSv)... over every
minute from shift start through `t`... already implemented, correctly,
as `phase3c_rotation_infra.dose_attribution.cumulative_dose_per_worker`."*
This is an explicit statement, in the project's own design
documentation, that the existing implementation is correct for its
intended purpose. **No bug or ambiguity exists in `dose_attribution.py`
or in the methodology's own definition.** Option (2) ("total including
initial dose") is not a competing intended definition anywhere in this
project's design documents; option (3) ("both, separately labeled") is
therefore also not the methodology's own prescription — it is, however,
exactly the right diagnostic tool for auditing *this round's own
experimental technique*, which is what the sensitivity check below
does.

**Why the discrepancy appeared at all:** the original 390-run campaign
never presets a nonzero starting dose for any worker — every worker's
`cumulative_dose_mSv` begins at `0.0`, so "from shift start" and "total
including initial dose" are identical there, and no discrepancy could
ever have appeared in the main campaign. This round's supplementary
Experiment A deliberately presets a nonzero starting dose on 6 of its
10 scenarios (A1, A2, A4, A5, A6, A7, A9) specifically to force the
dose-threshold trigger to fire deterministically, independent of
seed-to-seed exposure noise — a technique never used by, or
anticipated in the design of, the main campaign or `dose_attribution.py`.

**Sensitivity analysis (performed, as instructed, using only existing
raw data and the scenarios' own already-fixed initial conditions — no
re-simulation, no change to any historical result or to the primary
endpoint's own definition):** for each of the 7 diverge-expected
scenarios, we computed "preset starting dose of the selected worker +
`dose_attribution`'s own reported shift-accrual for that same worker,"
and the resulting CGDTR-minus-reference-rule difference exactly
reproduces that scenario's own known, designed preset-dose gap in
every one of the 7 cases (−0.02, −0.03, −0.01, −0.01, −0.01, −0.01,
−0.02 mSv respectively — see
`ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md` section 2b's table for the
full per-case correspondence to each scenario's own preset values).

**Direct answer to "do the six zero-effect scenarios genuinely
demonstrate no outcome difference, or is the metric insensitive to the
controlled initial-dose conditions?": the metric is insensitive to
those conditions, not the algorithm, and this round's own primary
endpoint is correctly defined and correctly computed throughout — it
simply does not, and by design should not, include dose attributed to
before the simulated shift began, which is exactly where this round's
own trigger-forcing technique placed its controlling variable for
those 6 scenarios.** No historical number is changed by this finding;
it reframes the *interpretation* of an already-correct set of zero
values, exactly as `ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md` section
2b already stated qualitatively before this audit, now confirmed
quantitatively and exactly for all 7 scenarios.

**Reassessment of A8:** A8's result requires no reinterpretation and no
sensitivity check — its own relevant dose differences accrue through
genuine, simulated occupancy time entirely within the shift (the
standard, intended mechanism), so its primary-endpoint value
(−0.0749 mSv) already is the correct, methodology-consistent measure of
the selection rule's effect under A8's specific sequential-rotation
condition. A8 remains the one scenario in this round that provides
direct statistical evidence of a dose-outcome difference from
selection-rule divergence; the other 6 provide direct evidence only of
selection-rule divergence itself (a deterministic, not statistical,
finding), not of its roster-wide dose consequence.

## Corrections made as a result of this audit

1. `ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md` section 1: replaced the
   undifferentiated "872 total rows" framing with the full
   scenario-by-scenario reconciliation table above.
2. `ALARAD_FINAL_SUPPLEMENTARY_VALIDATION_REPORT.md` section 3:
   corrected the same statement with a pointer to this audit.
3. `ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md` section 2b: added the
   exact, per-case quantitative sensitivity-check table (section Task
   3 above), strengthening what was previously stated only
   qualitatively.
4. No number in `analysis_summary.json`, any figure, or any raw data
   file was changed — every correction is to prose describing already-
   correct numbers, or an added analysis computed from already-stored
   data.

## Remaining limitations (unchanged by this audit)

- The selection rule's population-level dose benefit at natural
  (non-engineered) campaign scale remains untested — this audit
  strengthens, but does not remove, that limitation.
- The delayed-sensor-reading defect found in the supplementary round
  remains unresolved (deliberately deferred; see
  `ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md` section 5, item 3).
- No provisional parameter has received expert (Medical
  Physicist/RSO) review.
