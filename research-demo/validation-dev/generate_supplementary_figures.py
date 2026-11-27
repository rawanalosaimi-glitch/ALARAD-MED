"""
Publication-support figures for the final supplementary validation
campaign (task 7). Run only after
phase3c_rotation_infra.supplementary.run_supplementary_campaign and
analyze_supplementary_campaign.py have produced their JSON outputs.
Writes into figures_supplementary/ -- kept separate from the original
campaign's figures/ directory.

Run from research-demo/validation-dev/:
    python3 generate_supplementary_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT_DIR = Path("figures_supplementary")
OUT_DIR.mkdir(exist_ok=True)
SUPP_DIR = Path("phase3c_supplementary_output")

DIVERGE_CASES = ["A1", "A2", "A4", "A5", "A6", "A7", "A9"]
ALL_A_CASES = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10"]


def fig_policy_comparison_table_png():
    """Max individual dose by policy, per Experiment A case (table
    rendered as a figure for consistency with the rest of the set)."""
    path = SUPP_DIR / "analysis_summary.json"
    if not path.exists():
        print("skip: policy comparison (no analysis_summary.json yet)")
        return
    data = json.loads(path.read_text())["fairness_and_outcomes"]
    cases = sorted(data.keys())
    policies = ["no_rotation", "fixed_interval", "reference_rule", "ablation_d", "cgdtr"]

    fig, ax = plt.subplots(figsize=(11, 6))
    x = range(len(cases))
    width = 0.15
    for i, policy in enumerate(policies):
        values = [data[c].get(policy, {}).get("mean_collective_dose_mSv", 0) * 0 +
                  data[c].get(policy, {}).get("total_completed", 0) for c in cases]
        # Use completed-rotation counts (more informative than dose here,
        # since doses are controlled/near-identical by design) --
        ax.bar([xi + i * width for xi in x], values, width=width, label=policy)
    ax.set_xticks([xi + 2 * width for xi in x])
    ax.set_xticklabels(cases)
    ax.set_ylabel("Total completed rotations (across 30 seeds)")
    ax.set_title("Supplementary Experiment A: completed rotations by policy and case")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "policy_comparison_completed_rotations.png", dpi=150)
    plt.close(fig)
    print("wrote policy_comparison_completed_rotations.png")


def fig_selection_divergence_table():
    path = SUPP_DIR / "analysis_summary.json"
    if not path.exists():
        print("skip: selection divergence (no analysis_summary.json yet)")
        return
    per_case = json.loads(path.read_text())["selection_divergence"]["per_case"]
    cases = [c for c in ALL_A_CASES if c in per_case]
    rates = [per_case[c]["divergence_rate"] or 0 for c in cases]

    fig, ax = plt.subplots(figsize=(9, 4.5))
    colors = ["#4c72b0" if c in DIVERGE_CASES else "#999999" for c in cases]
    ax.bar(cases, rates, color=colors)
    ax.set_ylabel("Fraction of seeds where CGDTR and\nreference-rule select a different worker")
    ax.set_title("Supplementary Experiment A: selection-divergence rate by case\n(blue = divergence expected by design; gray = not expected)")
    ax.set_ylim(0, 1.05)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "candidate_selection_divergence.png", dpi=150)
    plt.close(fig)
    print("wrote candidate_selection_divergence.png")


def fig_max_individual_dose_comparison():
    path = SUPP_DIR / "analysis_summary.json"
    if not path.exists():
        return
    per_case = json.loads(path.read_text())["selection_divergence"]["per_case"]
    cases = [c for c in DIVERGE_CASES if c in per_case]
    pop_means = [per_case[c]["population_mean_diff_mSv"] for c in cases]
    pop_ci = [per_case[c]["population_mean_diff_ci"] for c in cases]
    lo = [m - ci[1] for m, ci in zip(pop_means, pop_ci)]
    hi = [ci[2] - m for m, ci in zip(pop_means, pop_ci)]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(cases, pop_means, yerr=[lo, hi], capsize=4, color="#55a868")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("Mean (CGDTR − reference-rule)\nmax individual dose (mSv)")
    ax.set_title("Supplementary Experiment A: max-individual-dose difference\n(population average, 30 seeds/case, bootstrap 95% CI)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "max_individual_dose_comparison.png", dpi=150)
    plt.close(fig)
    print("wrote max_individual_dose_comparison.png")


def fig_fairness_comparison():
    path = SUPP_DIR / "analysis_summary.json"
    if not path.exists():
        return
    data = json.loads(path.read_text())["fairness_and_outcomes"]
    cases = [c for c in ALL_A_CASES if c in data]
    cg_fair = [data[c].get("cgdtr", {}).get("mean_fairness_variance", 0) for c in cases]
    rr_fair = [data[c].get("reference_rule", {}).get("mean_fairness_variance", 0) for c in cases]

    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = range(len(cases))
    ax.bar([xi - 0.2 for xi in x], cg_fair, width=0.4, label="CGDTR")
    ax.bar([xi + 0.2 for xi in x], rr_fair, width=0.4, label="Reference-rule")
    ax.set_xticks(list(x))
    ax.set_xticklabels(cases)
    ax.set_ylabel("Mean roster dose-variance (mSv²)")
    ax.set_title("Supplementary Experiment A: dose-distribution fairness by case")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "dose_fairness_comparison.png", dpi=150)
    plt.close(fig)
    print("wrote dose_fairness_comparison.png")


def fig_infeasibility_breakdown():
    path = SUPP_DIR / "analysis_summary.json"
    if not path.exists():
        return
    data = json.loads(path.read_text())["fairness_and_outcomes"]
    cases = [c for c in ALL_A_CASES if c in data]
    completed = [data[c].get("cgdtr", {}).get("total_completed", 0) for c in cases]
    infeasible = [data[c].get("cgdtr", {}).get("total_infeasible", 0) for c in cases]
    held = [data[c].get("cgdtr", {}).get("total_held", 0) for c in cases]
    unresolved = [data[c].get("cgdtr", {}).get("total_unresolved_at_shift_end", 0) for c in cases]

    fig, ax = plt.subplots(figsize=(9, 5))
    x = range(len(cases))
    bottom = [0] * len(cases)
    for series, name, color in [(completed, "Completed", "#4c72b0"), (infeasible, "Infeasible", "#dd8452"),
                                 (held, "Held", "#c44e52"), (unresolved, "Unresolved at shift end", "#8172b3")]:
        ax.bar(x, series, bottom=bottom, label=name, color=color)
        bottom = [b + s for b, s in zip(bottom, series)]
    ax.set_xticks(list(x))
    ax.set_xticklabels(cases)
    ax.set_ylabel("Count (CGDTR, summed over 30 seeds)")
    ax.set_title("Supplementary Experiment A: CGDTR rotation-attempt outcomes by case")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "infeasibility_breakdown.png", dpi=150)
    plt.close(fig)
    print("wrote infeasibility_breakdown.png")


def fig_sensor_fault_coverage_matrix():
    path = SUPP_DIR / "analysis_summary.json"
    if not path.exists():
        return
    data = json.loads(path.read_text())["experiment_b_escalation_coverage"]
    cases = sorted(data.keys())
    raised_rate = [data[c]["n_raised"] / data[c]["n_runs"] if data[c]["n_runs"] else 0 for c in cases]
    resolved_rate = [data[c]["n_resolved"] / data[c]["n_runs"] if data[c]["n_runs"] else 0 for c in cases]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = range(len(cases))
    ax.bar([xi - 0.2 for xi in x], raised_rate, width=0.4, label="Escalation raised")
    ax.bar([xi + 0.2 for xi in x], resolved_rate, width=0.4, label="Escalation resolved")
    ax.set_xticks(list(x))
    ax.set_xticklabels(cases)
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("Fraction of runs")
    ax.set_title("Supplementary Experiment B: sensor-fault escalation coverage")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "sensor_fault_escalation_coverage.png", dpi=150)
    plt.close(fig)
    print("wrote sensor_fault_escalation_coverage.png")


def fig_duty_limit_state_coverage_matrix():
    path = SUPP_DIR / "analysis_summary.json"
    if not path.exists():
        return
    data = json.loads(path.read_text())["experiment_c_coverage_matrix"]
    cases = sorted(c for c in data if data[c].get("status") != "NOT_IMPLEMENTED")
    completed = [data[c]["n_completed"] for c in cases]
    infeasible = [data[c]["n_infeasible"] for c in cases]
    held = [data[c]["n_held"] for c in cases]
    unresolved = [data[c]["n_unresolved_at_shift_end"] for c in cases]

    fig, ax = plt.subplots(figsize=(9, 5))
    x = range(len(cases))
    bottom = [0] * len(cases)
    for series, name, color in [(completed, "Completed", "#4c72b0"), (infeasible, "Infeasible", "#dd8452"),
                                 (held, "Held", "#c44e52"), (unresolved, "Unresolved at shift end", "#8172b3")]:
        ax.bar(x, series, bottom=bottom, label=name, color=color)
        bottom = [b + s for b, s in zip(bottom, series)]
    ax.set_xticks(list(x))
    ax.set_xticklabels(cases)
    ax.set_ylabel("Count (summed over 30 seeds)")
    ax.set_title("Supplementary Experiment C: duty-limit / state-transition coverage\n(C10 excluded: NOT IMPLEMENTED)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "duty_limit_state_coverage.png", dpi=150)
    plt.close(fig)
    print("wrote duty_limit_state_coverage.png")


if __name__ == "__main__":
    fig_policy_comparison_table_png()
    fig_selection_divergence_table()
    fig_max_individual_dose_comparison()
    fig_fairness_comparison()
    fig_infeasibility_breakdown()
    fig_sensor_fault_coverage_matrix()
    fig_duty_limit_state_coverage_matrix()
    print(f"\nFigures written to {OUT_DIR.resolve()}")
