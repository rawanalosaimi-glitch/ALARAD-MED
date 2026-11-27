"""
Phase 3A balanced statistical campaign -- resolves
PHASE3A_FORECASTING_READINESS_CHECKLIST.md section 2's open items:
balanced coverage across all 13 archetypes (not the smoke test's 8,
heavily weighted toward flat/near-flat scenarios), fresh seeds (never
the 8-seed smoke batch's 3001-3008, never the design-set seeds
20260601-13), and the exposure-scale fix
(UNRESOLVED_SCIENTIFIC_DECISIONS.md item 13): series are rescaled onto
the frozen engine's own room baselines (`detection_adapter.
rescale_to_engine_baseline`, reused exactly as the detection adapter
already does, not re-derived) before `linearForecast` is evaluated, so
absolute MAE/RMSE are now on a scale representing a realistic room,
not Phase 1's own small provisional baseline.

Still evaluates only the three horizons the real `linearForecast`
actually produces (1/2/3 minutes) -- no 15-minute capability is
invented or assumed.

Usage (from research-demo/validation-dev/):
    python3 -m phase3a_forecasting.run_phase3a_statistical_campaign [--seeds-per-class N]
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from phase1_simulator import config as p1_config_mod
from phase1_simulator import output as p1_output
from phase1_simulator import scenario as p1_scenario
from phase1_simulator.scenario import ARCHETYPES
from phase2a_adapter.detection_adapter import decode_observed_value, phase1_baseline_rate, rescale_to_engine_baseline
from phase2a_adapter.engine_bridge import EngineBridge
from phase2a_adapter.engine_contract import snapshot_engine_constants

from . import baselines
from .config import load_config
from .forecast_adapter import build_rate_forecasts, score_against_ground_truth
from .forecast_contract import verify_forecast_contract, verify_known_forecast_values
from .metrics import mae_rmse_by_horizon, skill_vs_persistence

P1_CONFIG_PATH = Path(p1_config_mod.__file__).parent / "config" / "simulation_config.json"

# Fresh seeds: never the design set (20260601-20260613) and never the
# Phase 3A smoke test's own seeds (3001-3008) -- a disjoint block, per
# ICAIRE_Simulation_Validation_Methodology.md section 8's three-way
# seed-separation discipline.
SEED_BASE = 90000


def run_campaign(seeds_per_class: int, archetypes=ARCHETYPES, seed_base: int = SEED_BASE) -> dict:
    p1_cfg = p1_config_mod.load_config(P1_CONFIG_PATH)
    p3a_cfg = load_config()
    alpha = p3a_cfg.block("baseline_exponential_smoothing")["alpha"]

    per_class_rows = []
    pooled = {"candidate": [], "persistence": [], "ses": []}

    with EngineBridge() as bridge:
        verify_forecast_contract(bridge)
        verify_known_forecast_values(bridge)
        engine_constants = snapshot_engine_constants(bridge)
        engine_baselines = engine_constants["baselineRates"]

        for archetype in archetypes:
            class_candidate, class_persistence, class_ses = [], [], []
            n_windows_total = 0
            n_skipped_total = 0

            for i in range(seeds_per_class):
                seed = seed_base + archetypes.index(archetype) * 1000 + i
                run = p1_scenario.generate_run(archetype, seed, p1_cfg)
                simulated = p1_scenario.simulate_run(run, p1_cfg)
                d = p1_output.run_to_dict(simulated, p1_cfg)

                for worker in d["workers"]:
                    raw_series = [decode_observed_value(v) for v in worker["series"]["observed_rate_uSv_h"]]
                    p1_baseline = phase1_baseline_rate(worker, p1_cfg)
                    engine_baseline = engine_baselines[worker["room"]] * worker["proc_mult"]
                    series = rescale_to_engine_baseline(raw_series, p1_baseline, engine_baseline)

                    # Unique per (archetype, seed, worker) so skill_vs_persistence's
                    # pairing-by-(series_id, t) never collides across different
                    # series when these rows are pooled below (see metrics.py).
                    series_id = f"{archetype}:{seed}:{worker['worker_id']}"

                    cand = score_against_ground_truth(build_rate_forecasts(bridge, series), series)
                    pers = score_against_ground_truth(baselines.build_persistence_forecasts(bridge, series), series)
                    ses = score_against_ground_truth(
                        baselines.build_exponential_smoothing_forecasts(bridge, series, alpha), series)
                    for row_list in (cand, pers, ses):
                        for row in row_list:
                            row["series_id"] = series_id

                    class_candidate.extend(cand)
                    class_persistence.extend(pers)
                    class_ses.extend(ses)
                    pooled["candidate"].extend(cand)
                    pooled["persistence"].extend(pers)
                    pooled["ses"].extend(ses)

                    n_windows_total += len(cand)
                    n_skipped_total += sum(1 for r in cand if r["skipped"])

            per_class_rows.append({
                "archetype": archetype,
                "n_seeds": seeds_per_class,
                "n_windows": n_windows_total,
                "n_skipped": n_skipped_total,
                "candidate_mae_rmse": mae_rmse_by_horizon(class_candidate),
                "persistence_mae_rmse": mae_rmse_by_horizon(class_persistence),
                "ses_mae_rmse": mae_rmse_by_horizon(class_ses),
                "candidate_skill_vs_persistence": skill_vs_persistence(class_candidate, class_persistence),
                "ses_skill_vs_persistence": skill_vs_persistence(class_ses, class_persistence),
            })
            print(f"  {archetype:28s} seeds={seeds_per_class} windows={n_windows_total} "
                  f"skipped={n_skipped_total}")

    summary = {
        "per_class": per_class_rows,
        "pooled": {
            "n_windows": len(pooled["candidate"]),
            "candidate_mae_rmse": mae_rmse_by_horizon(pooled["candidate"]),
            "persistence_mae_rmse": mae_rmse_by_horizon(pooled["persistence"]),
            "ses_mae_rmse": mae_rmse_by_horizon(pooled["ses"]),
            "candidate_skill_vs_persistence": skill_vs_persistence(pooled["candidate"], pooled["persistence"]),
            "ses_skill_vs_persistence": skill_vs_persistence(pooled["ses"], pooled["persistence"]),
        },
        "config": {
            "seeds_per_class": seeds_per_class,
            "archetypes": list(archetypes),
            "seed_base": seed_base,
            "rescaled_to_engine_baseline": True,
            "alpha": alpha,
        },
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds-per-class", type=int, default=30)
    parser.add_argument("--archetypes", nargs="*", default=None)
    args = parser.parse_args()
    archetypes = args.archetypes or ARCHETYPES

    summary = run_campaign(args.seeds_per_class, archetypes=archetypes)

    out_dir = Path(__file__).parent.parent / "phase3a_campaign_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "campaign_summary.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nWrote campaign summary to {out_path}")
    print(json.dumps(summary["pooled"], indent=2))


if __name__ == "__main__":
    main()
