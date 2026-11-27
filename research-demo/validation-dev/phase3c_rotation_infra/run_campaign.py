"""
The rotation campaign runner (task 7): for each of the 13 established
scenario classes (phase1_simulator.scenario.ARCHETYPES, reused
unchanged) and each of N independent seeds, builds ONE exposure layer
(campaign_scenarios.build_campaign_run) and runs all five policies
against it, paired on that identical exposure/staffing input
(PHASE3B_ROTATION_ALGORITHM_DESIGN.md section 5b's paired-seed design).

Seeds are a fresh block, disjoint from Phase 1's own design-set seeds
(20260601-20260613) and from Phase 3A's smoke-test/campaign seed blocks
-- ICAIRE_Simulation_Validation_Methodology.md section 8's three-way
seed-separation discipline, extended to the rotation campaign.

Stores, per run: the policy's SimulationResult (converted to a plain
dict), the exact config snapshot, and the seed -- written incrementally
to disk so a partial campaign (stopped by a runtime limit) still leaves
every completed run's raw output on disk, never silently discarded.

Usage (from research-demo/validation-dev/):
    python3 -m phase3c_rotation_infra.run_campaign --seeds-per-class N [--archetypes ...] [--out-dir ...]
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

from phase1_simulator import config as p1_config_mod
from phase1_simulator.scenario import ARCHETYPES, ROOMS
from phase2a_adapter.engine_bridge import EngineBridge

from .campaign_scenarios import build_campaign_run
from .config import load_config
from .policies import ALL_POLICIES
from .simulation import run_policy_on_run
from .staffing import generate_roster

P1_CONFIG_PATH = Path(p1_config_mod.__file__).parent / "config" / "simulation_config.json"
PROCEDURE_CLASSES = ["diagnostic_fluoroscopy", "interventional_cath_lab", "ct", "pet_ct"]

# Fresh seed block: disjoint from Phase 1's design set (20260601-13),
# Phase 3A's smoke-test seeds (3001-3008), and Phase 3A's own
# statistical-campaign block (90000+) -- see run_phase3a_statistical_campaign.py.
SEED_BASE = 700000


def _result_to_jsonable(res) -> dict:
    d = asdict(res)
    return d


def run_campaign(seeds_per_class: int, archetypes: Optional[List[str]] = None,
                  out_dir: Optional[Path] = None, seed_base: int = SEED_BASE) -> dict:
    archetypes = archetypes or ARCHETYPES
    p1_cfg = p1_config_mod.load_config(P1_CONFIG_PATH)
    p3c_cfg = load_config()
    out_dir = out_dir or (Path(__file__).parent.parent / "phase3c_campaign_output")
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw_runs"
    raw_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "config_snapshot.json").write_text(
        json.dumps(p3c_cfg.raw, indent=2), encoding="utf-8")

    manifest = {"archetypes": archetypes, "seeds_per_class": seeds_per_class,
                "seed_base": seed_base, "completed_runs": [], "failed_runs": [],
                "started_at": time.time()}

    with EngineBridge() as bridge:
        for a_idx, archetype in enumerate(archetypes):
            for i in range(seeds_per_class):
                seed = seed_base + a_idx * 1000 + i
                t0 = time.time()
                try:
                    run = build_campaign_run(seed, archetype, p1_cfg, p3c_cfg)
                    n_rooms = len(run["slots_by_room"])
                    per_policy = {}
                    for policy in ALL_POLICIES:
                        roster = {
                            w.worker_id: w for w in generate_roster(
                                seed, run["shift_minutes"], n_rooms + 1, ROOMS,
                                PROCEDURE_CLASSES, p3c_cfg)
                        }
                        res = run_policy_on_run(bridge, run, roster, policy, p3c_cfg)
                        per_policy[policy.name] = _result_to_jsonable(res)

                    record = {"seed": seed, "archetype": archetype,
                              "shift_minutes": run["shift_minutes"], "n_rooms": n_rooms,
                              "elapsed_s": time.time() - t0, "policies": per_policy}
                    out_path = raw_dir / f"{archetype}_{seed}.json"
                    out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
                    manifest["completed_runs"].append({"archetype": archetype, "seed": seed,
                                                        "file": out_path.name,
                                                        "elapsed_s": record["elapsed_s"]})
                    print(f"  {archetype:28s} seed={seed} rooms={n_rooms} "
                          f"shift_min={run['shift_minutes']} elapsed={record['elapsed_s']:.1f}s")
                except Exception as e:
                    manifest["failed_runs"].append({"archetype": archetype, "seed": seed,
                                                      "error": repr(e)})
                    print(f"  FAILED {archetype} seed={seed}: {e!r}")
                # Write the manifest after every run, not just at the end --
                # a partial campaign (stopped by a runtime limit) must never
                # look like it produced nothing.
                manifest["elapsed_total_s"] = time.time() - manifest["started_at"]
                (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds-per-class", type=int, default=30)
    parser.add_argument("--archetypes", nargs="*", default=None)
    parser.add_argument("--out-dir", type=str, default=None)
    args = parser.parse_args()
    out_dir = Path(args.out_dir) if args.out_dir else None
    manifest = run_campaign(args.seeds_per_class, archetypes=args.archetypes, out_dir=out_dir)
    print(f"\nCompleted: {len(manifest['completed_runs'])}  Failed: {len(manifest['failed_runs'])}")


if __name__ == "__main__":
    main()
