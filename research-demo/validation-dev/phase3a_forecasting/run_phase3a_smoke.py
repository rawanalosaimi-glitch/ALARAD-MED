"""
Phase 3A small integration smoke test -- NOT the statistical evaluation
campaign described in ICAIRE_Simulation_Validation_Methodology.md
section 7. Runs the real linearForecast-based adapter plus both
independent baselines (persistence, exponential smoothing) against a
handful of Phase 1 archetypes, one seed each, and reports MAE/RMSE/skill
per horizon for both the dose-rate forecast and the derived cumulative-
dose forecast.

Usage (from the research-demo/validation-dev directory):
    python3 -m phase3a_forecasting.run_phase3a_smoke
"""

from __future__ import annotations

import json
from pathlib import Path

from phase1_simulator import config as p1_config_mod
from phase1_simulator import output as p1_output
from phase1_simulator import scenario as p1_scenario
from phase2a_adapter.engine_bridge import EngineBridge

from . import baselines
from .config import load_config
from .forecast_adapter import (
    build_rate_forecasts,
    forecast_cumulative_dose,
    score_against_ground_truth,
    true_cumulative_dose_over_horizon,
)
from .forecast_contract import verify_forecast_contract, verify_known_forecast_values
from .metrics import summarize

P1_CONFIG_PATH = Path(p1_config_mod.__file__).parent / "config" / "simulation_config.json"

SMOKE_ARCHETYPE_SEEDS = {
    "normal": 3001,
    "gradual_increase": 3002,
    "sudden_increase": 3003,
    "transient_spike": 3004,
    "fault_missing": 3005,
    "fault_invalid": 3006,
    "fault_frozen": 3007,
    "fault_delayed": 3008,
}


def main() -> None:
    p1_cfg = p1_config_mod.load_config(P1_CONFIG_PATH)
    p3a_cfg = load_config()
    alpha = p3a_cfg.block("baseline_exponential_smoothing")["alpha"]

    rows = []
    with EngineBridge() as bridge:
        verify_forecast_contract(bridge)
        verify_known_forecast_values(bridge)

        candidate_all, persistence_all, ses_all = [], [], []

        for archetype, seed in SMOKE_ARCHETYPE_SEEDS.items():
            run = p1_scenario.generate_run(archetype, seed, p1_cfg)
            simulated = p1_scenario.simulate_run(run, p1_cfg)
            d = p1_output.run_to_dict(simulated, p1_cfg)

            for worker in d["workers"]:
                series = worker["series"]["observed_rate_uSv_h"]
                true_series = worker["series"]["true_rate_uSv_h"]

                cand = score_against_ground_truth(build_rate_forecasts(bridge, series), series)
                pers = score_against_ground_truth(baselines.build_persistence_forecasts(bridge, series), series)
                ses = score_against_ground_truth(
                    baselines.build_exponential_smoothing_forecasts(bridge, series, alpha), series)

                candidate_all.extend(cand)
                persistence_all.extend(pers)
                ses_all.extend(ses)

                cand_dose = forecast_cumulative_dose(cand)
                dose_errors = []
                for r in cand_dose:
                    if r["skipped"]:
                        continue
                    true_dose = true_cumulative_dose_over_horizon(true_series, r["t"])
                    for f, tr in zip(r["forecast_cumulative_dose_mSv"], true_dose):
                        if tr is not None:
                            dose_errors.append(abs(f - tr))

                n_skipped = sum(1 for r in cand if r["skipped"])
                mean_dose_err = (sum(dose_errors) / len(dose_errors)) if dose_errors else None
                rows.append({
                    "archetype": archetype, "worker_id": worker["worker_id"],
                    "n_windows": len(cand), "n_skipped": n_skipped,
                    "mean_abs_cumulative_dose_forecast_error_mSv": mean_dose_err,
                })
                print(f"  {archetype:20s} {worker['worker_id']:6s} "
                      f"windows={len(cand)} skipped={n_skipped} "
                      f"mean|dose forecast error|={mean_dose_err}")

        summary = {
            "candidate_linearForecast": summarize(candidate_all, persistence_all),
            "baseline_persistence": summarize(persistence_all),
            "baseline_exponential_smoothing": summarize(ses_all, persistence_all),
        }

    out_dir = Path(__file__).parent.parent / "phase3a_smoke_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "smoke_rows.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (out_dir / "smoke_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print()
    print(json.dumps(summary, indent=2))
    print(f"\nWrote {len(rows)} per-worker rows and summary to {out_dir}")


if __name__ == "__main__":
    main()
