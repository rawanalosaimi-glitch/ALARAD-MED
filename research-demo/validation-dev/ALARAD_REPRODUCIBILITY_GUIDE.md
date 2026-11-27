# ALARAD — Reproducibility Guide (Supplementary Validation Round)

Everything below runs from `research-demo/validation-dev/` on branch
`research/icaire-v123-validation`. Supplements
`ALARAD_TECHNICAL_RESEARCH_COMPLETION_REPORT.md` section 10 (the
original campaign's own reproduction instructions, unchanged and still
valid) — this guide covers only what this supplementary round added.

## Environment

Same Python environment as the rest of the project. Dependencies:
`scipy`, `numpy`, `matplotlib`, `pillow` (installed earlier this
project via `python3 -m pip install --user scipy numpy matplotlib
pillow`; no new dependency was added this round). A real, headless
Chromium instance is required (via Playwright, through
`phase2a_adapter.engine_bridge.EngineBridge`) — every experiment drives
the real, unmodified frozen engine; nothing is mocked.

## Verify the frozen release is untouched

```
find . -iname "ALARAD_Prototype_Research_Demo_v1.2.3.html" -exec sha256sum {} \;
# expected: 92e897dd0ff1738f083df829b53f7f46377e042b7019bb9776232792261182ee
```

## Run the tests (original + this round's additions)

```
python3 -m unittest discover -s phase3c_rotation_infra/tests -t .
# 111 tests (109 original + 2 regression tests added this round), 0 failures

python3 -m unittest phase3c_rotation_infra.supplementary.tests.test_supplementary_infrastructure
# 24 tests, 0 failures
```

## Run the full supplementary campaign

```
python3 -m phase3c_rotation_infra.supplementary.run_supplementary_campaign --seeds-per-case 30
```

Writes to `phase3c_supplementary_output/` (new directory; never
touches `phase3c_campaign_output/`): `config_snapshot.json`,
`experiment_a_raw.json` (300 rows), `experiment_b_raw.json` (241 rows),
`experiment_c_raw.json` (331 rows), `manifest.json` (git revision,
Python version, seed bases, per-experiment timing). Takes approximately
13 minutes on this project's reference environment (557.7s + 72.3s +
142.2s for Experiments A/B/C respectively).

To re-run a single experiment's underlying functions directly (e.g.,
for debugging one sub-case), import and call `run_experiment_a`/
`run_experiment_b`/`run_experiment_c` from the respective
`phase3c_rotation_infra.supplementary.experiment_{a,b,c}_*` module with
a live `EngineBridge`, exactly as `run_supplementary_campaign.py` does.

## Run the statistical analysis

```
python3 analyze_supplementary_campaign.py
```

Reads `phase3c_supplementary_output/experiment_a_raw.json` and the
other two experiment files; writes
`phase3c_supplementary_output/analysis_summary.json`. Reuses
`stats_common.py` unchanged (the same bootstrap/Wilcoxon/Holm-
Bonferroni helpers the main campaign's own analysis used).

## Generate the figures

```
python3 generate_supplementary_figures.py
```

Writes 7 PNGs to `figures_supplementary/` (kept separate from the
original campaign's own `figures/`).

## Seed blocks (all disjoint, this project's full history)

| Block | Seed base | Used by |
|---|---|---|
| Design set | 20260601-20260613 | earliest phases |
| Phase 3A smoke test | 3001-3008 | early forecasting smoke test |
| Phase 3A statistical campaign | 90000+ | main forecasting campaign |
| Phase 3C-B rotation campaign | 700000+ | main rotation campaign |
| Phase 3C-B sensitivity sweep | 850000+ | sensitivity analysis |
| **Supplementary Experiment A** | **910000+** | this round |
| **Supplementary Experiment B** | **920000+** | this round |
| **Supplementary Experiment C** | **930000+** | this round |

## File map (this round's new files)

```
phase3c_rotation_infra/
  simulation.py                      MODIFIED: new UNRESOLVED_AT_SHIFT_END outcome + counter
  escalation.py                      MODIFIED: re-raise-after-resolve fix
  tests/test_simulation.py           MODIFIED: +1 regression test, 1 assertion widened
  tests/test_escalation.py           MODIFIED: +1 regression test, 1 fixture corrected
  supplementary/
    __init__.py
    controlled_builders.py            WorkerSpec/AssignmentSlot/exposure/fault-injection builders
    experiment_a_selection.py         10 sub-cases, multi-candidate selection
    experiment_b_sensor_faults.py     8 sub-cases + direct-path comparison
    experiment_c_duty_limits.py       12 sub-cases, duty limits/HELD/RSO ack
    run_supplementary_campaign.py     orchestrates all three, writes phase3c_supplementary_output/
    tests/
      __init__.py
      test_supplementary_infrastructure.py   24 tests

research-demo/validation-dev/ (top level)
  analyze_supplementary_campaign.py   statistical analysis
  generate_supplementary_figures.py   figure generation
  phase3c_supplementary_output/       raw outputs (new, separate from phase3c_campaign_output/)
  figures_supplementary/              7 PNGs (new, separate from figures/)
  ALARAD_FINAL_SUPPLEMENTARY_VALIDATION_REPORT.md
  ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md
  ALARAD_FINAL_SCIENTIFIC_READINESS_REVIEW.md
  ALARAD_MANUSCRIPT_RESULTS_HANDOFF.md
  ALARAD_REPRODUCIBILITY_GUIDE.md     (this file)
```

## What this round's reproduction does NOT require

- No modification to the frozen `ALARAD_Prototype_Research_Demo_v1.2.3.html`.
- No modification to, or re-run of, `phase3c_campaign_output/` or
  `phase3a_campaign_output/` — both remain exactly as the main campaign
  left them.
- No new third-party dependency beyond what the main campaign already
  installed.
