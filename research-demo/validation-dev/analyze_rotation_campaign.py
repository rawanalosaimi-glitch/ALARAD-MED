"""
Statistical analysis of the rotation campaign (task 8). Reads
phase3c_campaign_output/raw_runs/*.json (written incrementally by
phase3c_rotation_infra.run_campaign), computes per-policy descriptive
statistics, paired Wilcoxon signed-rank comparisons (paired by seed +
archetype, the run-level unit of independence,
ICAIRE_Simulation_Validation_Methodology.md section 7a) with
Holm-Bonferroni correction across the comparison family, bootstrap
confidence intervals, the 2x2 ablation decomposition (trigger-effect vs
selection-effect), and an explicit check of the collective-dose
invariant across every run and policy.

Run from research-demo/validation-dev/:
    python3 analyze_rotation_campaign.py [--campaign-dir phase3c_campaign_output]
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


def load_runs(campaign_dir: Path) -> List[dict]:
    raw_dir = campaign_dir / "raw_runs"
    runs = []
    for f in sorted(raw_dir.glob("*.json")):
        runs.append(json.loads(f.read_text(encoding="utf-8")))
    return runs


def check_collective_dose_invariant(runs: List[dict]) -> Dict:
    max_abs_diff = 0.0
    n_checked = 0
    violations = []
    for run in runs:
        values = {p: run["policies"][p]["collective_dose_mSv"] for p in POLICIES if p in run["policies"]}
        if not values:
            continue
        ref = next(iter(values.values()))
        for p, v in values.items():
            diff = abs(v - ref)
            max_abs_diff = max(max_abs_diff, diff)
            n_checked += 1
            if diff > 1e-6:
                violations.append({"seed": run["seed"], "archetype": run["archetype"],
                                    "policy": p, "diff": diff})
    return {"n_checked": n_checked, "max_abs_diff_mSv": max_abs_diff, "violations": violations}


def per_policy_descriptives(runs: List[dict]) -> Dict[str, Dict]:
    out = {}
    for p in POLICIES:
        max_doses = [r["policies"][p]["max_individual_dose_mSv"] for r in runs if p in r["policies"]]
        collective = [r["policies"][p]["collective_dose_mSv"] for r in runs if p in r["policies"]]
        n_completed = [r["policies"][p]["n_completed"] for r in runs if p in r["policies"]]
        n_infeasible = [r["policies"][p]["n_infeasible"] for r in runs if p in r["policies"]]
        n_aborted = [r["policies"][p]["n_aborted"] for r in runs if p in r["policies"]]
        n_held = [r["policies"][p]["n_held"] for r in runs if p in r["policies"]]
        escalated = [len(r["policies"][p].get("escalated_rooms") or {}) for r in runs if p in r["policies"]]

        out[p] = {
            "n_runs": len(max_doses),
            "max_individual_dose_mSv": {"mean_ci": bootstrap_ci(max_doses)},
            "collective_dose_mSv": {"mean_ci": bootstrap_ci(collective)},
            "n_completed": {"mean": statistics.mean(n_completed) if n_completed else None,
                             "total": sum(n_completed)},
            "n_infeasible": {"mean": statistics.mean(n_infeasible) if n_infeasible else None,
                              "total": sum(n_infeasible)},
            "n_aborted": {"total": sum(n_aborted)},
            "n_held": {"total": sum(n_held)},
            "n_runs_with_escalation": sum(1 for e in escalated if e > 0),
        }
    return out


def fairness_variance(run: dict, policy: str) -> float:
    doses = list(run["policies"][policy]["cumulative_dose_per_worker"].values())
    if len(doses) < 2:
        return 0.0
    return statistics.pvariance(doses)


def paired_comparisons(runs: List[dict]) -> Dict[str, Dict]:
    """Paired Wilcoxon on max-individual-dose and on fairness (dose
    variance across the roster) for every policy vs. no_rotation, plus
    CGDTR vs. each of the other three comparison policies."""
    comparisons = {
        "cgdtr_vs_no_rotation": ("cgdtr", "no_rotation"),
        "fixed_interval_vs_no_rotation": ("fixed_interval", "no_rotation"),
        "reference_rule_vs_no_rotation": ("reference_rule", "no_rotation"),
        "ablation_d_vs_no_rotation": ("ablation_d", "no_rotation"),
        "cgdtr_vs_fixed_interval": ("cgdtr", "fixed_interval"),
        "cgdtr_vs_reference_rule": ("cgdtr", "reference_rule"),
        "cgdtr_vs_ablation_d": ("cgdtr", "ablation_d"),
    }
    results = {}
    pvals_max_dose = {}
    pvals_fairness = {}
    for name, (p1, p2) in comparisons.items():
        a = [r["policies"][p1]["max_individual_dose_mSv"] for r in runs if p1 in r["policies"] and p2 in r["policies"]]
        b = [r["policies"][p2]["max_individual_dose_mSv"] for r in runs if p1 in r["policies"] and p2 in r["policies"]]
        fa = [fairness_variance(r, p1) for r in runs if p1 in r["policies"] and p2 in r["policies"]]
        fb = [fairness_variance(r, p2) for r in runs if p1 in r["policies"] and p2 in r["policies"]]
        w_dose = wilcoxon_paired(a, b)
        w_fair = wilcoxon_paired(fa, fb)
        results[name] = {"max_individual_dose": w_dose, "fairness_variance": w_fair,
                          "mean_diff_max_dose": (statistics.mean(a) - statistics.mean(b)) if a else None}
        pvals_max_dose[name] = w_dose["p_value"]
        pvals_fairness[name + "_fairness"] = w_fair["p_value"]

    corrected = holm_bonferroni({**pvals_max_dose, **pvals_fairness})
    return {"raw": results, "holm_bonferroni_corrected": corrected}


def ablation_decomposition(runs: List[dict]) -> Dict:
    """2x2 (PHASE3B_ROTATION_ALGORITHM_DESIGN.md section 6a): isolates
    the trigger-rule effect from the selection-rule effect on
    max-individual-dose, as paired differences averaged across the two
    relevant pairs each."""
    usable = [r for r in runs if all(p in r["policies"] for p in POLICIES)]
    if not usable:
        return {"n_runs": 0}

    def md(p):
        return [r["policies"][p]["max_individual_dose_mSv"] for r in usable]

    cgdtr, ref, fi, ad = md("cgdtr"), md("reference_rule"), md("fixed_interval"), md("ablation_d")
    selection_effect_1 = [c - r for c, r in zip(cgdtr, ref)]
    selection_effect_2 = [f - a for f, a in zip(fi, ad)]
    trigger_effect_1 = [c - f for c, f in zip(cgdtr, fi)]
    trigger_effect_2 = [r - a for r, a in zip(ref, ad)]
    all_selection = selection_effect_1 + selection_effect_2
    all_trigger = trigger_effect_1 + trigger_effect_2
    return {
        "n_runs": len(usable),
        "selection_effect_mSv": {"mean_ci": bootstrap_ci(all_selection)},
        "trigger_effect_mSv": {"mean_ci": bootstrap_ci(all_trigger)},
    }


def per_archetype_table(runs: List[dict]) -> Dict:
    by_archetype = defaultdict(list)
    for r in runs:
        by_archetype[r["archetype"]].append(r)
    out = {}
    for archetype, rs in by_archetype.items():
        out[archetype] = {"n_runs": len(rs), "policies": per_policy_descriptives(rs)}
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-dir", type=str, default="phase3c_campaign_output")
    args = parser.parse_args()
    campaign_dir = Path(args.campaign_dir)

    runs = load_runs(campaign_dir)
    print(f"Loaded {len(runs)} raw runs from {campaign_dir}")

    invariant = check_collective_dose_invariant(runs)
    print(f"Collective-dose invariant: checked {invariant['n_checked']} policy-run pairs, "
          f"max |diff| = {invariant['max_abs_diff_mSv']:.3e} mSv, "
          f"violations (> 1e-6 mSv) = {len(invariant['violations'])}")

    descriptives = per_policy_descriptives(runs)
    comparisons = paired_comparisons(runs)
    ablation = ablation_decomposition(runs)
    per_archetype = per_archetype_table(runs)

    summary = {
        "n_runs": len(runs),
        "collective_dose_invariant_check": invariant,
        "per_policy_descriptives": descriptives,
        "paired_comparisons": comparisons,
        "ablation_decomposition": ablation,
        "per_archetype": per_archetype,
    }
    out_path = campaign_dir / "analysis_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"Wrote analysis summary to {out_path}")


if __name__ == "__main__":
    main()
