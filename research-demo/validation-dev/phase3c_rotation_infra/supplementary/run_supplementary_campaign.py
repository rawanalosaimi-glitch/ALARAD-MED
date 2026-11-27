"""
Final supplementary validation round -- runs Experiments A, B, and C
end to end and writes raw, machine-readable results plus a manifest to
a NEW output directory (`phase3c_supplementary_output/`), never the
original campaign's own `phase3c_campaign_output/`.

Usage (from research-demo/validation-dev/):
    python3 -m phase3c_rotation_infra.supplementary.run_supplementary_campaign [--seeds-per-case N]
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import time
from pathlib import Path

from phase2a_adapter.engine_bridge import EngineBridge

from ..config import load_config
from .experiment_a_selection import EXPERIMENT_A_SEED_BASE, run_experiment_a
from .experiment_b_sensor_faults import EXPERIMENT_B_SEED_BASE, run_experiment_b
from .experiment_c_duty_limits import EXPERIMENT_C_SEED_BASE, run_experiment_c

OUT_DIR = Path(__file__).resolve().parents[2] / "phase3c_supplementary_output"


def _git_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[3], text=True,
        ).strip()
    except Exception as e:
        return f"unavailable ({e})"


def run_all(seeds_per_case: int = 30, out_dir: Path = OUT_DIR) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = load_config()

    manifest = {
        "started_at": time.time(),
        "seeds_per_case": seeds_per_case,
        "seed_bases": {"A": EXPERIMENT_A_SEED_BASE, "B": EXPERIMENT_B_SEED_BASE, "C": EXPERIMENT_C_SEED_BASE},
        "git_revision": _git_revision(),
        "python_version": platform.python_version(),
        "config_snapshot_file": "config_snapshot.json",
        "experiments": {},
    }
    (out_dir / "config_snapshot.json").write_text(json.dumps(cfg.raw, indent=2), encoding="utf-8")

    with EngineBridge() as bridge:
        t0 = time.time()
        print("=== Experiment A: multi-candidate selection ===")
        rows_a = run_experiment_a(bridge, cfg, seeds_per_case=seeds_per_case)
        (out_dir / "experiment_a_raw.json").write_text(json.dumps(rows_a, indent=2), encoding="utf-8")
        manifest["experiments"]["A"] = {"n_rows": len(rows_a), "elapsed_s": time.time() - t0,
                                          "file": "experiment_a_raw.json"}
        print(f"  wrote {len(rows_a)} rows to experiment_a_raw.json ({time.time() - t0:.1f}s)")

        t0 = time.time()
        print("=== Experiment B: sensor faults and escalation ===")
        rows_b = run_experiment_b(bridge, cfg, seeds_per_case=seeds_per_case)
        (out_dir / "experiment_b_raw.json").write_text(json.dumps(rows_b, indent=2), encoding="utf-8")
        manifest["experiments"]["B"] = {"n_rows": len(rows_b), "elapsed_s": time.time() - t0,
                                          "file": "experiment_b_raw.json"}
        print(f"  wrote {len(rows_b)} rows to experiment_b_raw.json ({time.time() - t0:.1f}s)")

        t0 = time.time()
        print("=== Experiment C: duty limits, HELD, RSO acknowledgement ===")
        rows_c = run_experiment_c(bridge, cfg, seeds_per_case=seeds_per_case)
        (out_dir / "experiment_c_raw.json").write_text(json.dumps(rows_c, indent=2), encoding="utf-8")
        manifest["experiments"]["C"] = {"n_rows": len(rows_c), "elapsed_s": time.time() - t0,
                                          "file": "experiment_c_raw.json"}
        print(f"  wrote {len(rows_c)} rows to experiment_c_raw.json ({time.time() - t0:.1f}s)")

    manifest["finished_at"] = time.time()
    manifest["total_elapsed_s"] = manifest["finished_at"] - manifest["started_at"]
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nDone. Manifest written to {out_dir / 'manifest.json'}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds-per-case", type=int, default=30)
    args = parser.parse_args()
    run_all(seeds_per_case=args.seeds_per_case)


if __name__ == "__main__":
    main()
