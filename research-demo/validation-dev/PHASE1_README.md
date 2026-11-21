# Phase 1 Simulator — Reproducibility Instructions

This covers `phase1_simulator/`: the standalone synthetic radiation-exposure
simulator built from `ICAIRE_Simulation_Validation_Methodology.md`
(Revision 2), per the Phase 1 implementation approval.

**Scope reminder:** this package generates simulated exposure data and
injects labelled ground truth. It does **not** implement any detector,
forecaster, baseline comparator, or rotation recommender, and computes no
evaluation metric. See `PHASE1_SMOKE_TEST_REPORT.md` for what was actually
run and observed in this session — that report is explicitly *not* a
scientific validation result.

## Requirements

- Python 3.11 (this is the version this code was written and tested
  against in this session — `python3 --version` to check yours).
- **No `pip install` of anything.** The package uses only the Python
  standard library (`random`, `hashlib`, `json`, `dataclasses`,
  `unittest`, `pathlib`, `math`, `argparse`). This is a deliberate choice
  for Phase 1: it keeps the reproducibility story to "install Python,
  nothing else," with no dependency-resolution or network access involved.

## Determinism guarantee, precisely stated

For a fixed (archetype, seed, `simulation_config.json` contents), the
simulator produces byte-identical output, because:

- All sampling uses `random.Random(seed)` instances, never the global
  `random` module.
- Every sub-stream (a worker's attributes, its pattern timing, its fault
  timing, its measurement noise) is derived from the run seed and a
  stable text label via a SHA-256-based derivation (`phase1_simulator/rng.py`),
  so adding a worker or changing roster size never perturbs any other
  sub-stream's draws.
- `random.Random`'s algorithm (Mersenne Twister) and its seeding behavior
  for integer seeds are part of the CPython language implementation and
  are stable across platforms for a given Python version. **This
  guarantee is scoped to "a given Python version"** — it is not a
  cross-language or formally version-independent standard. If this
  package is ever run under a materially different Python version and
  output differs, that should be treated the same way
  `Verification_Rerun_Report.md` treated the Chromium 141-vs-153 gap: as
  a disclosed environment difference, not a silent discrepancy.
- Verified empirically in this session: the smoke batch was generated
  twice, in two separate process invocations, to two separate output
  directories, and the resulting files were confirmed identical via
  `diff -q`. See `PHASE1_SMOKE_TEST_REPORT.md`.

## Running the unit tests

From `research-demo/validation-dev/`:

```
python3 -m unittest discover -s phase1_simulator/tests -t . -v
```

`-t .` sets the top-level directory to `research-demo/validation-dev/` so
`phase1_simulator` resolves as an importable package without installing
it. All 40 tests are expected to pass; `PHASE1_SMOKE_TEST_REPORT.md`
records the actual run.

## Running the smoke-test batch

From `research-demo/validation-dev/`:

```
python3 -m phase1_simulator.run_smoke_batch
```

This writes one JSON file per archetype (13 files) plus a `manifest.json`
to `research-demo/validation-dev/smoke_test_output/` by default. Use
`--out <dir>` to write elsewhere, and `--config <path>` to use a different
configuration file (any replacement config must still pass the
provisional-labeling check in `phase1_simulator/config.py`, or loading it
will raise `ConfigValidationError`).

## What the output means, and what it does not mean

Every generated JSON file carries an explicit `"phase"` field stating it
is Phase 1 output only, with no detector/forecaster/metric computed. Every
file also carries the exact `"config_disclaimer"` string from
`simulation_config.json`, so a reader of the output file alone (without
also reading the config) still sees the "NOT CLINICALLY VALIDATED"
disclaimer and cannot mistake simulated data for validated data.

The numeric ranges used to generate events, faults, procedure baselines,
and shift lengths are **provisional placeholders**, not evidence-based
values — see `phase1_simulator/config/simulation_config.json`'s
`provisional_parameters` block and
`ICAIRE_Simulation_Validation_Methodology.md` section 9 (the parameter
registry) for exactly which rows are still open and what would resolve
each one.

## Package layout

```
phase1_simulator/
  units.py             dose-rate/cumulative-dose/time-integration conventions
  rng.py                deterministic per-purpose seed derivation
  patterns.py           flat/ramp/step/spikes true-rate generators + noise
  faults.py             missing/invalid/frozen/delayed fault injection
  dose.py               true-dose and observed-dose (trusted/uncertain/unmonitored) accounting
  area_model.py         MEASURED vs. MODELED (inverse-square) conversion
  config.py             config loader with provisional-labeling enforcement
  config/
    simulation_config.json   the shipped provisional parameter registry (deliverable B)
  scenario.py            the 13 archetypes: roster + pattern + ground-truth generation
  output.py              JSON schema serialization
  run_smoke_batch.py      CLI: generate one run per archetype
  tests/
    test_dose_integration.py
    test_seed_reproducibility.py
    test_event_timing.py
    test_ground_truth_consistency.py
    test_output_schema.py   (also covers the provisional-labeling enforcement)
```
