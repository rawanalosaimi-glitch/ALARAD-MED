"""
Statistical analysis of the final supplementary validation campaign
(Experiments A/B/C). Reads `phase3c_supplementary_output/experiment_{a,b,c}_raw.json`
and reuses the same, already-verified `stats_common.py` helpers the main
campaign's own analysis used (bootstrap_ci, wilcoxon_paired,
holm_bonferroni) -- no new statistical machinery is introduced.

Unit of independence: one (case_id, seed) replicate -- never a
per-minute or per-event record within a run, matching this project's
own established discipline (ICAIRE_Simulation_Validation_Methodology.md
section 7a) and this round's own explicit instruction to avoid
pseudoreplication. Cases are fixed, deliberately-designed structural
conditions (not a random sample of conditions), so they are reported
per-case AND pooled across the family of cases sharing the same
hypothesis (expect_cgdtr_ref_diverge=True) -- pooling is valid here
because each (case, seed) pair is a genuinely independent simulation
replicate (disjoint seed blocks per case; no two pairs share any random
state), not a repeated measurement of the same event.

Reports BOTH the population-average effect (every (case, seed) pair,
including the ones where the two policies happened not to diverge) and
the conditional effect (restricted to pairs where they genuinely
selected differently), labeled separately, per this round's explicit
instruction.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from stats_common import bootstrap_ci, holm_bonferroni, wilcoxon_paired

POLICIES = ["no_rotation", "fixed_interval", "reference_rule", "ablation_d", "cgdtr"]
DIVERGE_EXPECTED_CASES = ["A1", "A2", "A4", "A5", "A6", "A7", "A9"]
NO_DIVERGENCE_EXPECTED_CASES = ["A3", "A10"]  # A3 structurally tied; A10 no candidate at all
INDETERMINATE_CASES = ["A8"]  # multi-trigger chain; divergence expected but not a single clean comparison


def load_experiment_a(out_dir: Path) -> List[dict]:
    return json.loads((out_dir / "experiment_a_raw.json").read_text())


def _first_completed_incoming(sim_result: dict) -> str | None:
    for e in sim_result["rotation_events"]:
        if e["status"] == "COMPLETED":
            return e["incoming"]
    return None


def experiment_a_selection_divergence(rows: List[dict]) -> Dict:
    """Primary endpoint: max-individual-dose difference (CGDTR vs.
    reference-rule), per case and pooled across the diverge-expected
    family, BOTH as a population average (all seeds) and as a
    conditional effect (only seeds where the two policies actually
    selected a different first incoming worker)."""
    by_case: Dict[str, dict] = {}
    pooled_pop_cg, pooled_pop_rr = [], []
    pooled_cond_cg, pooled_cond_rr = [], []
    divergence_counts: Dict[str, int] = {}

    cases = sorted(set(r["case_id"] for r in rows))
    for case_id in cases:
        case_rows = [r for r in rows if r["case_id"] == case_id]
        cg_doses, rr_doses = [], []
        cond_cg, cond_rr = [], []
        n_diverge = 0
        for r in case_rows:
            cg_sim = r["policies"]["cgdtr"]
            rr_sim = r["policies"]["reference_rule"]
            cg_doses.append(cg_sim["max_individual_dose_mSv"])
            rr_doses.append(rr_sim["max_individual_dose_mSv"])
            cg_first = _first_completed_incoming(cg_sim)
            rr_first = _first_completed_incoming(rr_sim)
            diverged = (cg_first is not None or rr_first is not None) and cg_first != rr_first
            if diverged:
                n_diverge += 1
                cond_cg.append(cg_sim["max_individual_dose_mSv"])
                cond_rr.append(rr_sim["max_individual_dose_mSv"])

        w = wilcoxon_paired(cg_doses, rr_doses)
        diffs = [c - r for c, r in zip(cg_doses, rr_doses)]
        by_case[case_id] = {
            "n_seeds": len(case_rows),
            "n_diverged": n_diverge,
            "divergence_rate": n_diverge / len(case_rows) if case_rows else None,
            "population_mean_diff_mSv": statistics.mean(diffs) if diffs else None,
            "population_mean_diff_ci": bootstrap_ci(diffs) if diffs else None,
            "conditional_mean_diff_mSv": (statistics.mean([c - r for c, r in zip(cond_cg, cond_rr)])
                                           if cond_cg else None),
            "wilcoxon": w,
            "expect_diverge": case_rows[0]["expect_cgdtr_ref_diverge"] if case_rows else None,
        }
        divergence_counts[case_id] = n_diverge

        if case_id in DIVERGE_EXPECTED_CASES:
            pooled_pop_cg.extend(cg_doses)
            pooled_pop_rr.extend(rr_doses)
            pooled_cond_cg.extend(cond_cg)
            pooled_cond_rr.extend(cond_rr)

    pooled_pop_diffs = [c - r for c, r in zip(pooled_pop_cg, pooled_pop_rr)]
    pooled_cond_diffs = [c - r for c, r in zip(pooled_cond_cg, pooled_cond_rr)]

    return {
        "per_case": by_case,
        "pooled_diverge_expected_family": {
            "cases": DIVERGE_EXPECTED_CASES,
            "n_pairs_population": len(pooled_pop_diffs),
            "population_average_mean_diff_mSv": statistics.mean(pooled_pop_diffs) if pooled_pop_diffs else None,
            "population_average_ci": bootstrap_ci(pooled_pop_diffs) if pooled_pop_diffs else None,
            "population_average_wilcoxon": wilcoxon_paired(pooled_pop_cg, pooled_pop_rr),
            "n_pairs_conditional_on_divergence": len(pooled_cond_diffs),
            "conditional_mean_diff_mSv": statistics.mean(pooled_cond_diffs) if pooled_cond_diffs else None,
            "conditional_ci": bootstrap_ci(pooled_cond_diffs) if pooled_cond_diffs else None,
        },
    }


def experiment_a_fairness_and_outcomes(rows: List[dict]) -> Dict:
    by_case = defaultdict(lambda: defaultdict(list))
    for r in rows:
        for policy in POLICIES:
            sim = r["policies"][policy]
            doses = list(sim["cumulative_dose_per_worker"].values())
            fairness = statistics.pvariance(doses) if len(doses) > 1 else 0.0
            by_case[r["case_id"]][policy].append({
                "fairness_variance": fairness, "collective_dose_mSv": sim["collective_dose_mSv"],
                "n_completed": sim["n_completed"], "n_infeasible": sim["n_infeasible"],
                "n_held": sim["n_held"], "n_unresolved_at_shift_end": sim["n_unresolved_at_shift_end"],
            })
    out = {}
    for case_id, policies in by_case.items():
        out[case_id] = {}
        for policy, records in policies.items():
            out[case_id][policy] = {
                "mean_fairness_variance": statistics.mean(r["fairness_variance"] for r in records),
                "mean_collective_dose_mSv": statistics.mean(r["collective_dose_mSv"] for r in records),
                "total_completed": sum(r["n_completed"] for r in records),
                "total_infeasible": sum(r["n_infeasible"] for r in records),
                "total_held": sum(r["n_held"] for r in records),
                "total_unresolved_at_shift_end": sum(r["n_unresolved_at_shift_end"] for r in records),
            }
    return out


def check_collective_dose_invariant(rows: List[dict]) -> Dict:
    max_diff = 0.0
    n_checked = 0
    violations = []
    for r in rows:
        values = {p: r["policies"][p]["collective_dose_mSv"] for p in POLICIES}
        ref = next(iter(values.values()))
        for p, v in values.items():
            diff = abs(v - ref)
            max_diff = max(max_diff, diff)
            n_checked += 1
            if diff > 1e-6:
                violations.append({"case_id": r["case_id"], "seed": r["seed"], "policy": p, "diff": diff})
    return {"n_checked": n_checked, "max_abs_diff_mSv": max_diff, "violations": violations}


def experiment_b_escalation_coverage(out_dir: Path) -> Dict:
    rows = json.loads((out_dir / "experiment_b_raw.json").read_text())
    coverage = defaultdict(lambda: {"n_runs": 0, "n_raised": 0, "n_resolved": 0, "states_seen": set()})
    for r in rows:
        if "escalation_results" not in r:
            continue
        case_id = r["case_id"]
        for worker_id, esc in r["escalation_results"].items():
            coverage[case_id]["n_runs"] += 1
            if esc["raised_at"] is not None:
                coverage[case_id]["n_raised"] += 1
            if esc["state"] == "RESOLVED":
                coverage[case_id]["n_resolved"] += 1
        for states in r.get("sensor_state_history", {}).values():
            coverage[case_id]["states_seen"].update(states)
    return {cid: {**v, "states_seen": sorted(v["states_seen"])} for cid, v in coverage.items()}


def experiment_c_coverage_matrix(out_dir: Path) -> Dict:
    rows = json.loads((out_dir / "experiment_c_raw.json").read_text())
    matrix = {}
    for case_id in sorted(set(r["case_id"] for r in rows)):
        case_rows = [r for r in rows if r["case_id"] == case_id]
        if case_rows[0].get("status") == "NOT_IMPLEMENTED":
            matrix[case_id] = {"status": "NOT_IMPLEMENTED", "detail": case_rows[0].get("detail")}
            continue
        clause_counts = defaultdict(int)
        n_completed = n_infeasible = n_held = n_unresolved = 0
        for r in case_rows:
            sim = r["simulation_result"]
            for clause, count in sim["trigger_clause_counts"].items():
                clause_counts[clause] += count
            n_completed += sim["n_completed"]
            n_infeasible += sim["n_infeasible"]
            n_held += sim["n_held"]
            n_unresolved += sim["n_unresolved_at_shift_end"]
        matrix[case_id] = {
            "n_seeds": len(case_rows), "clause_counts": dict(clause_counts),
            "n_completed": n_completed, "n_infeasible": n_infeasible,
            "n_held": n_held, "n_unresolved_at_shift_end": n_unresolved,
        }
    return matrix


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=str, default="phase3c_supplementary_output")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)

    rows_a = load_experiment_a(out_dir)
    print(f"Loaded {len(rows_a)} Experiment A rows")

    invariant = check_collective_dose_invariant(rows_a)
    print(f"Collective-dose invariant (Experiment A): checked {invariant['n_checked']} policy-run pairs, "
          f"max |diff| = {invariant['max_abs_diff_mSv']:.3e} mSv, violations = {len(invariant['violations'])}")

    selection = experiment_a_selection_divergence(rows_a)
    fairness = experiment_a_fairness_and_outcomes(rows_a)
    b_coverage = experiment_b_escalation_coverage(out_dir)
    c_matrix = experiment_c_coverage_matrix(out_dir)

    pvals = {cid: d["wilcoxon"]["p_value"] for cid, d in selection["per_case"].items()}
    corrected = holm_bonferroni(pvals)

    summary = {
        "collective_dose_invariant": invariant,
        "selection_divergence": selection,
        "holm_bonferroni_per_case": corrected,
        "fairness_and_outcomes": fairness,
        "experiment_b_escalation_coverage": b_coverage,
        "experiment_c_coverage_matrix": c_matrix,
    }
    out_path = out_dir / "analysis_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"Wrote analysis summary to {out_path}")

    pooled = selection["pooled_diverge_expected_family"]
    print("\n=== Primary endpoint: CGDTR vs. reference-rule, diverge-expected family ===")
    print(f"Population-average mean diff: {pooled['population_average_mean_diff_mSv']:.6f} mSv "
          f"(n={pooled['n_pairs_population']}, Wilcoxon p={pooled['population_average_wilcoxon']['p_value']})")
    print(f"Conditional (divergent runs only) mean diff: {pooled['conditional_mean_diff_mSv']} mSv "
          f"(n={pooled['n_pairs_conditional_on_divergence']})")


if __name__ == "__main__":
    main()
