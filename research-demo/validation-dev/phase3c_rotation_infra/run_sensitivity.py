"""
Sensitivity analysis for the rotation campaign's provisional parameters
(task 9). Uses a SEPARATE seed block from both the main campaign
(run_campaign.py, seed base 700000) and the forecasting campaign
(seed base 90000), and a small seed count per sweep point, deliberately
NOT the same runs used for the main campaign's performance claims
(avoiding "tuning on the test set"). Sweeps: rotation_threshold_fraction,
fixed_interval_minutes, min_handoff_duration_minutes, credential
coverage, max_rotations_per_shift. For each sweep point, reports mean
max-individual-dose, mean collective dose (should stay invariant),
n_completed/n_infeasible, over a handful of seeds across 3 archetypes
chosen to span "normal," "multi-worker," and "faulty" conditions.

Usage: python3 -m phase3c_rotation_infra.run_sensitivity
"""

from __future__ import annotations

import copy
import json
import statistics
from pathlib import Path
from typing import Dict, List

from phase1_simulator import config as p1_config_mod
from phase1_simulator.scenario import ROOMS
from phase2a_adapter.engine_bridge import EngineBridge

from .campaign_scenarios import build_campaign_run
from .config import Phase3CConfig, load_config
from .policies import CGDTR, NO_ROTATION
from .simulation import run_policy_on_run
from .staffing import generate_roster

P1_CONFIG_PATH = Path(p1_config_mod.__file__).parent / "config" / "simulation_config.json"
PROCEDURE_CLASSES = ["diagnostic_fluoroscopy", "interventional_cath_lab", "ct", "pet_ct"]
SENSITIVITY_SEED_BASE = 850000
SEEDS_PER_POINT = 5
ARCHETYPES_FOR_SENSITIVITY = ["normal", "multi_worker_mixed", "fault_missing"]


def _run_point(bridge, p3c_cfg: Phase3CConfig, p1_cfg, seed_offset: int) -> Dict:
    max_doses, collective_doses, n_completed, n_infeasible = [], [], [], []
    for a_idx, archetype in enumerate(ARCHETYPES_FOR_SENSITIVITY):
        for i in range(SEEDS_PER_POINT):
            seed = SENSITIVITY_SEED_BASE + seed_offset * 100 + a_idx * 20 + i
            run = build_campaign_run(seed, archetype, p1_cfg, p3c_cfg)
            roster = {
                w.worker_id: w for w in generate_roster(
                    seed, run["shift_minutes"], len(run["slots_by_room"]) + 1, ROOMS,
                    PROCEDURE_CLASSES, p3c_cfg)
            }
            res = run_policy_on_run(bridge, run, roster, CGDTR, p3c_cfg)
            max_doses.append(res.max_individual_dose_mSv)
            collective_doses.append(res.collective_dose_mSv)
            n_completed.append(res.n_completed)
            n_infeasible.append(res.n_infeasible)
    return {
        "n_runs": len(max_doses),
        "mean_max_individual_dose_mSv": statistics.mean(max_doses),
        "mean_collective_dose_mSv": statistics.mean(collective_doses),
        "collective_dose_stdev": statistics.pstdev(collective_doses) if len(collective_doses) > 1 else 0.0,
        "mean_n_completed": statistics.mean(n_completed),
        "mean_n_infeasible": statistics.mean(n_infeasible),
    }


def sweep_param(bridge, p1_cfg, block: str, key: str, values: List, seed_offset_base: int) -> List[Dict]:
    rows = []
    for i, v in enumerate(values):
        base = load_config()
        raw = copy.deepcopy(base.raw)
        raw[block][key] = v
        cfg = Phase3CConfig(raw=raw)
        point = _run_point(bridge, cfg, p1_cfg, seed_offset_base + i)
        point.update({"parameter": f"{block}.{key}", "value": v})
        rows.append(point)
        print(f"  {block}.{key}={v!r}: {point}")
    return rows


def main() -> None:
    p1_cfg = p1_config_mod.load_config(P1_CONFIG_PATH)
    results: Dict[str, List[Dict]] = {}
    with EngineBridge() as bridge:
        print("Sweep: rotation_threshold_fraction")
        results["rotation_threshold_fraction"] = sweep_param(
            bridge, p1_cfg, "cgdtr_trigger", "rotation_threshold_fraction",
            [0.1, 0.3, 0.5, 0.7, 0.9], seed_offset_base=0)

        print("Sweep: fixed_interval_minutes")
        results["fixed_interval_minutes"] = sweep_param(
            bridge, p1_cfg, "fixed_interval_baseline", "fixed_interval_minutes",
            [20, 40, 60, 80, 100], seed_offset_base=10)

        print("Sweep: min_handoff_duration_minutes")
        results["min_handoff_duration_minutes"] = sweep_param(
            bridge, p1_cfg, "handoff", "min_handoff_duration_minutes",
            [5, 10, 15, 20, 30], seed_offset_base=20)

        print("Sweep: max_rotations_per_shift_range")
        results["max_rotations_per_shift_range"] = sweep_param(
            bridge, p1_cfg, "duty_limits", "max_rotations_per_shift_range",
            [[1, 1], [1, 2], [1, 3], [2, 4]], seed_offset_base=30)

        print("Sweep: credential_coverage_probability_range")
        results["credential_coverage_probability_range"] = sweep_param(
            bridge, p1_cfg, "roster_generation", "credential_coverage_probability_range",
            [[0.2, 0.3], [0.4, 0.7], [0.8, 0.95]], seed_offset_base=40)

    out_dir = Path(__file__).parent.parent / "phase3c_campaign_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "sensitivity_results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote sensitivity results to {out_path}")


if __name__ == "__main__":
    main()
