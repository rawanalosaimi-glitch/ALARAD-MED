"""
Phase 1 CLI entry point: generate one run per archetype (13 runs total) --
a smoke-test batch demonstrating the simulator works end-to-end, not the
statistical campaign described in
ICAIRE_Simulation_Validation_Methodology.md section 7 (>=30 independent
seeds per scenario class). That campaign is explicitly future work and is
not run by this script.

Usage (from the research-demo/validation-dev directory):
    python3 -m phase1_simulator.run_smoke_batch
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import config as cfg_mod
from . import output, scenario

DEFAULT_ARCHETYPE_SEEDS = {
    "normal": 1001,
    "gradual_increase": 1002,
    "sudden_increase": 1003,
    "transient_spike": 1004,
    "area_relocation": 1005,
    "multi_worker_mixed": 1006,
    "fault_missing": 1007,
    "fault_invalid": 1008,
    "fault_frozen": 1009,
    "fault_delayed": 1010,
    "fault_during_event": 1011,
    "multi_worker_faults": 1012,
    "concurrent_alert_and_fault": 1013,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config" / "simulation_config.json"),
    )
    parser.add_argument(
        "--out",
        default=str(Path(__file__).parent.parent / "smoke_test_output"),
    )
    args = parser.parse_args()

    config = cfg_mod.load_config(Path(args.config))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for archetype, seed in DEFAULT_ARCHETYPE_SEEDS.items():
        run = scenario.generate_run(archetype, seed, config)
        simulated = scenario.simulate_run(run, config)
        path = out_dir / f"{run.run_id}.json"
        output.write_run_output(simulated, config, path)
        n_truth = sum(len(w.truth_events) for w in run.workers)
        n_faults = sum(len(w.fault_windows) for w in run.workers)
        manifest.append({
            "run_id": run.run_id, "archetype": archetype, "seed": seed,
            "file": path.name, "shift_minutes": run.shift_minutes,
            "n_workers": len(run.workers), "n_truth_events": n_truth,
            "n_fault_events": n_faults,
        })
        print(f"  {run.run_id:38s} shift={run.shift_minutes:4d}min "
              f"workers={len(run.workers)} truth_events={n_truth} "
              f"fault_events={n_faults}")

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nWrote {len(manifest)} runs and manifest.json to {out_dir}")


if __name__ == "__main__":
    main()
