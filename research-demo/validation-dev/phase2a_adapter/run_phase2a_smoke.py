"""
Phase 2A small integration smoke test -- NOT the statistical evaluation
campaign described in ICAIRE_Simulation_Validation_Methodology.md section
7 (>=30 independent seeds per scenario class, baselines, significance
testing). That campaign is explicitly out of scope for Phase 2A. This
script runs one seed per personal-mode archetype through the real engine
via this adapter (candidate detector + both new baselines, radiation and
DQ layers) and prints a small results table, to demonstrate the pipeline
works end-to-end on real Phase 1 output.

Usage (from the research-demo/validation-dev directory):
    python3 -m phase2a_adapter.run_phase2a_smoke
"""

from __future__ import annotations

import json
from pathlib import Path

from phase1_simulator import config as p1_config_mod
from phase1_simulator import output as p1_output
from phase1_simulator import scenario as p1_scenario

from . import baselines
from . import config as p2a_config_mod
from .detection_adapter import evaluate_radiation_detection
from .dq_adapter import evaluate_dq_detection
from .engine_bridge import EngineBridge
from .engine_contract import snapshot_engine_constants, verify_contract
from .metrics_extra import summarize

P1_CONFIG_PATH = Path(p1_config_mod.__file__).parent / "config" / "simulation_config.json"

# Personal-mode archetypes only (area-mode is out of scope this phase --
# PHASE2A_LIMITATIONS.md item 1). Distinct seeds from Phase 1's own smoke
# batch, to keep the two smoke tests visibly separate.
SMOKE_ARCHETYPE_SEEDS = {
    "normal": 2001,
    "gradual_increase": 2002,
    "sudden_increase": 2003,
    "transient_spike": 2004,
    "fault_missing": 2005,
    "fault_invalid": 2006,
    "fault_frozen": 2007,
    "fault_delayed": 2008,
    "fault_during_event": 2009,
    "concurrent_alert_and_fault": 2010,
}


def main() -> None:
    p1_cfg = p1_config_mod.load_config(P1_CONFIG_PATH)
    p2a_cfg = p2a_config_mod.load_config()

    rows = []
    with EngineBridge() as bridge:
        verify_contract(bridge)
        engine_baselines = snapshot_engine_constants(bridge)["baselineRates"]

        candidate_results, b0_results, b2_results, b3_results, dq_results = [], [], [], [], []

        for archetype, seed in SMOKE_ARCHETYPE_SEEDS.items():
            run = p1_scenario.generate_run(archetype, seed, p1_cfg)
            simulated = p1_scenario.simulate_run(run, p1_cfg)
            d = p1_output.run_to_dict(simulated, p1_cfg)

            for worker in d["workers"]:
                cand = evaluate_radiation_detection(bridge, worker, p1_cfg, engine_baselines, K=1)
                b0 = baselines.baseline_0_always_normal(bridge, worker)
                b2 = baselines.baseline_2_fixed_threshold(bridge, worker, p1_cfg, engine_baselines, p2a_cfg)
                b3 = baselines.baseline_3_moving_average(bridge, worker, p1_cfg, engine_baselines, p2a_cfg)
                dq = evaluate_dq_detection(bridge, worker, p1_cfg, engine_baselines)

                candidate_results.append(cand)
                b0_results.append(b0)
                b2_results.append(b2)
                b3_results.append(b3)
                dq_results.append(dq)

                rows.append({
                    "archetype": archetype, "worker_id": worker["worker_id"],
                    "n_truth_events": len(worker["truth_events"]),
                    "n_fault_events": len(worker["fault_events"]),
                    "candidate": {"TP": cand["TP"], "FP": cand["FP"], "FN": cand["FN"]},
                    "baseline_0": {"TP": b0["TP"], "FP": b0["FP"], "FN": b0["FN"]},
                    "baseline_2": {"TP": b2["TP"], "FP": b2["FP"], "FN": b2["FN"]},
                    "baseline_3": {"TP": b3["TP"], "FP": b3["FP"], "FN": b3["FN"]},
                    "dq": {"TP": dq["TP"], "FP": dq["FP"], "FN": dq["FN"]},
                })
                print(f"  {archetype:28s} {worker['worker_id']:6s} "
                      f"truth={len(worker['truth_events'])} faults={len(worker['fault_events'])}  "
                      f"candidate TP/FP/FN={cand['TP']}/{cand['FP']}/{cand['FN']}  "
                      f"b0={b0['TP']}/{b0['FP']}/{b0['FN']}  "
                      f"b2={b2['TP']}/{b2['FP']}/{b2['FN']}  "
                      f"b3={b3['TP']}/{b3['FP']}/{b3['FN']}  "
                      f"dq={dq['TP']}/{dq['FP']}/{dq['FN']}")

        summary = {
            "candidate": summarize(candidate_results),
            "baseline_0_always_normal": summarize(b0_results),
            "baseline_2_fixed_threshold": summarize(b2_results),
            "baseline_3_moving_average": summarize(b3_results),
            "data_quality_layer": summarize(dq_results),
        }

    out_dir = Path(__file__).parent.parent / "phase2a_smoke_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "smoke_rows.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (out_dir / "smoke_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print()
    print(json.dumps(summary, indent=2))
    print(f"\nWrote {len(rows)} per-worker rows and summary to {out_dir}")


if __name__ == "__main__":
    main()
