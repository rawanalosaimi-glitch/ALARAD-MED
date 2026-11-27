"""
Generates the publication-support figures (task 10B) from the already-
computed campaign/analysis outputs. Run only after
run_phase3a_statistical_campaign.py, run_campaign.py (phase3c), and
analyze_rotation_campaign.py have produced their JSON outputs.

Run from research-demo/validation-dev/:
    python3 generate_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT_DIR = Path("figures")
OUT_DIR.mkdir(exist_ok=True)

POLICIES = ["no_rotation", "fixed_interval", "reference_rule", "ablation_d", "cgdtr"]
POLICY_LABELS = {"no_rotation": "No rotation", "fixed_interval": "Fixed-interval",
                  "reference_rule": "Reference-rule", "ablation_d": "Ablation D", "cgdtr": "CGDTR"}


def fig_forecast_error_comparison():
    path = Path("phase3a_campaign_output/campaign_summary.json")
    if not path.exists():
        print("skip: forecast error figure (no campaign_summary.json yet)")
        return
    data = json.loads(path.read_text())["pooled"]
    horizons = ["1", "2", "3"]
    methods = {"candidate_mae_rmse": "linearForecast", "persistence_mae_rmse": "Persistence",
               "ses_mae_rmse": "Exp. smoothing"}

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, metric in zip(axes, ["mae", "rmse"]):
        for key, label in methods.items():
            values = [data[key][h][metric] for h in horizons]
            ax.plot(horizons, values, marker="o", label=label)
        ax.set_xlabel("Forecast horizon (minutes)")
        ax.set_ylabel(f"{metric.upper()} (uSv/h, rescaled to engine baseline)")
        ax.set_title(metric.upper())
        ax.legend(fontsize=8)
    fig.suptitle("Phase 3A: forecast error by horizon (pooled, balanced campaign)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "forecast_error_comparison.png", dpi=150)
    plt.close(fig)
    print("wrote forecast_error_comparison.png")


def fig_forecast_skill_by_archetype():
    path = Path("phase3a_campaign_output/campaign_summary.json")
    if not path.exists():
        return
    data = json.loads(path.read_text())["per_class"]
    archetypes = [row["archetype"] for row in data]
    skill_h1 = [row["candidate_skill_vs_persistence"].get("1") for row in data]
    skill_h3 = [row["candidate_skill_vs_persistence"].get("3") for row in data]

    fig, ax = plt.subplots(figsize=(10, 5))
    x = range(len(archetypes))
    ax.bar([i - 0.2 for i in x], skill_h1, width=0.4, label="1-min horizon")
    ax.bar([i + 0.2 for i in x], skill_h3, width=0.4, label="3-min horizon")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(list(x))
    ax.set_xticklabels(archetypes, rotation=60, ha="right", fontsize=7)
    ax.set_ylabel("linearForecast skill vs. persistence")
    ax.set_title("Phase 3A: linearForecast skill by scenario class")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "forecast_skill_by_archetype.png", dpi=150)
    plt.close(fig)
    print("wrote forecast_skill_by_archetype.png")


def fig_max_individual_dose_by_policy():
    path = Path("phase3c_campaign_output/analysis_summary.json")
    if not path.exists():
        print("skip: rotation figures (no analysis_summary.json yet)")
        return
    data = json.loads(path.read_text())["per_policy_descriptives"]
    labels, means, lo, hi = [], [], [], []
    for p in POLICIES:
        if p not in data:
            continue
        point, l, h = data[p]["max_individual_dose_mSv"]["mean_ci"]
        labels.append(POLICY_LABELS[p])
        means.append(point)
        lo.append(point - l)
        hi.append(h - point)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(labels, means, yerr=[lo, hi], capsize=4)
    ax.set_ylabel("Mean max individual dose (mSv)")
    ax.set_title("Rotation campaign: maximum individual dose by policy\n(bootstrap 95% CI)")
    plt.xticks(rotation=20, ha="right")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "max_individual_dose_by_policy.png", dpi=150)
    plt.close(fig)
    print("wrote max_individual_dose_by_policy.png")


def fig_collective_dose_invariant():
    path = Path("phase3c_campaign_output/analysis_summary.json")
    if not path.exists():
        return
    data = json.loads(path.read_text())["per_policy_descriptives"]
    labels, means = [], []
    for p in POLICIES:
        if p not in data:
            continue
        point, l, h = data[p]["collective_dose_mSv"]["mean_ci"]
        labels.append(POLICY_LABELS[p])
        means.append(point)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(labels, means, color="gray")
    ax.set_ylabel("Mean collective dose (mSv)")
    ax.set_title("Rotation campaign: collective dose by policy\n(expected: identical across policies -- fixed-occupancy invariant)")
    plt.xticks(rotation=20, ha="right")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "collective_dose_invariant.png", dpi=150)
    plt.close(fig)
    print("wrote collective_dose_invariant.png")


def fig_safety_constraint_counts():
    path = Path("phase3c_campaign_output/analysis_summary.json")
    if not path.exists():
        return
    data = json.loads(path.read_text())["per_policy_descriptives"]
    labels = [POLICY_LABELS[p] for p in POLICIES if p in data]
    completed = [data[p]["n_completed"]["total"] for p in POLICIES if p in data]
    infeasible = [data[p]["n_infeasible"]["total"] for p in POLICIES if p in data]
    aborted = [data[p]["n_aborted"]["total"] for p in POLICIES if p in data]
    held = [data[p]["n_held"]["total"] for p in POLICIES if p in data]

    fig, ax = plt.subplots(figsize=(8, 5))
    x = range(len(labels))
    bottom = [0] * len(labels)
    for series, name, color in [(completed, "Completed", "#4c72b0"), (infeasible, "Infeasible", "#dd8452"),
                                 (aborted, "Aborted", "#55a868"), (held, "Held", "#c44e52")]:
        ax.bar(x, series, bottom=bottom, label=name, color=color)
        bottom = [b + s for b, s in zip(bottom, series)]
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel("Count across campaign")
    ax.set_title("Rotation attempt outcomes by policy")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "safety_constraint_counts.png", dpi=150)
    plt.close(fig)
    print("wrote safety_constraint_counts.png")


def fig_dose_trajectory_example():
    """Reconstructs real per-minute cumulative-dose trajectories for one
    example run, by re-running the same deterministic seed/archetype
    through campaign_scenarios + dose_attribution -- the raw campaign
    JSON stores only the final per-worker totals, not the full
    per-minute series, so this regenerates them exactly rather than
    guessing."""
    raw_dir = Path("phase3c_campaign_output/raw_runs")
    if not raw_dir.exists():
        print("skip: dose trajectory figure (no raw_runs yet)")
        return
    files = sorted(raw_dir.glob("multi_worker_mixed_*.json")) or sorted(raw_dir.glob("*.json"))
    if not files:
        return
    run_meta = json.loads(files[0].read_text())
    seed, archetype = run_meta["seed"], run_meta["archetype"]

    import sys
    sys.path.insert(0, ".")
    from phase1_simulator import config as p1_config_mod
    from phase3c_rotation_infra.campaign_scenarios import build_campaign_run
    from phase3c_rotation_infra.config import load_config
    from phase3c_rotation_infra.dose_attribution import attribute_dose
    from phase1_simulator.units import MINUTE_H, dose_increment_mSv

    p1_cfg = p1_config_mod.load_config(Path(p1_config_mod.__file__).parent / "config" / "simulation_config.json")
    p3c_cfg = load_config()
    campaign_run = build_campaign_run(seed, archetype, p1_cfg, p3c_cfg)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    for ax, policy_name, title in [(axes[0], "no_rotation", "No rotation"), (axes[1], "cgdtr", "CGDTR")]:
        res = run_meta["policies"].get(policy_name)
        if res is None:
            continue
        assignment_by_room = res["assignment_by_room"]
        attributed = attribute_dose(campaign_run["slots_by_room"], campaign_run["exposure_by_slot"],
                                     assignment_by_room, campaign_run["shift_minutes"])
        for worker_id, rates in attributed.items():
            cumulative = []
            running = 0.0
            for r in rates:
                running += dose_increment_mSv(r, MINUTE_H)
                cumulative.append(running)
            ax.plot(cumulative, label=worker_id, linewidth=1.2)
        ax.set_title(title)
        ax.set_xlabel("Minute")
        ax.legend(fontsize=6, ncol=2)
    axes[0].set_ylabel("Cumulative dose (mSv)")
    fig.suptitle(f"Example dose trajectories: {archetype} seed={seed}")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "dose_trajectory_example.png", dpi=150)
    plt.close(fig)
    print("wrote dose_trajectory_example.png")


def fig_sensitivity_plots():
    path = Path("phase3c_campaign_output/sensitivity_results.json")
    if not path.exists():
        print("skip: sensitivity figure (no sensitivity_results.json yet)")
        return
    data = json.loads(path.read_text())
    n = len(data)
    fig, axes = plt.subplots(1, n, figsize=(4 * n, 4))
    if n == 1:
        axes = [axes]
    for ax, (param, rows) in zip(axes, data.items()):
        xs = [str(r["value"]) for r in rows]
        ys = [r["mean_max_individual_dose_mSv"] for r in rows]
        ax.plot(xs, ys, marker="o")
        ax.set_title(param, fontsize=8)
        ax.set_ylabel("Mean max indiv. dose (mSv)")
        ax.tick_params(axis="x", rotation=30, labelsize=7)
    fig.suptitle("Sensitivity analysis: CGDTR mean max-individual-dose vs. parameter value")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "sensitivity_plots.png", dpi=150)
    plt.close(fig)
    print("wrote sensitivity_plots.png")


if __name__ == "__main__":
    fig_forecast_error_comparison()
    fig_forecast_skill_by_archetype()
    fig_max_individual_dose_by_policy()
    fig_collective_dose_invariant()
    fig_safety_constraint_counts()
    fig_dose_trajectory_example()
    fig_sensitivity_plots()
    print(f"\nFigures written to {OUT_DIR.resolve()}")
