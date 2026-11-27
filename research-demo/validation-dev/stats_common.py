"""
Generic statistical helpers shared by the forecasting and rotation
campaign analyses (task 8 of the Phase 3C-A->campaign round):
bootstrap confidence intervals, paired Wilcoxon signed-rank tests, and
Holm-Bonferroni multiple-comparison correction -- matching
ICAIRE_Simulation_Validation_Methodology.md section 7's established
statistical design, applied here for the first time against real
campaign data rather than specified in the abstract.

Uses `scipy.stats` and `numpy` -- NEW dependencies for this project,
installed in this session (`python3 -m pip install --user scipy
numpy`), not previously part of any phase's requirements. Disclosed
here and in the final completion report, not silently added.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import stats


def bootstrap_ci(data: Sequence[float], n_boot: int = 2000, alpha: float = 0.05,
                  seed: int = 12345, statistic=np.mean) -> Tuple[float, float, float]:
    """Returns (point_estimate, ci_low, ci_high) via a simple
    nonparametric bootstrap over `data` (one value per independent run
    -- the run-level unit of independence,
    ICAIRE_Simulation_Validation_Methodology.md section 7a). Appropriate
    for n not large enough to assume normal-approximation CIs reliable,
    per the methodology's own stated rationale for bootstrapping."""
    arr = np.asarray(data, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) == 0:
        return (float("nan"), float("nan"), float("nan"))
    point = float(statistic(arr))
    if len(arr) == 1:
        return (point, point, point)
    rng = np.random.RandomState(seed)
    boots = np.empty(n_boot)
    n = len(arr)
    for i in range(n_boot):
        sample = arr[rng.randint(0, n, size=n)]
        boots[i] = statistic(sample)
    lo = float(np.percentile(boots, 100 * alpha / 2))
    hi = float(np.percentile(boots, 100 * (1 - alpha / 2)))
    return (point, lo, hi)


def wilcoxon_paired(a: Sequence[float], b: Sequence[float]) -> Dict[str, Optional[float]]:
    """Paired Wilcoxon signed-rank test (non-parametric, robust to
    non-normal metric distributions -- ICAIRE_Simulation_Validation_
    Methodology.md section 7's stated reason for preferring it over a
    paired t-test). `a` and `b` must already be paired by run (same
    seed/archetype, different policy or method) -- never independently
    sampled. Returns `statistic`/`p_value` as None (not a crash, not a
    0) when scipy itself cannot compute one (e.g., all differences are
    zero, or n < 1)."""
    a_arr = np.asarray(a, dtype=float)
    b_arr = np.asarray(b, dtype=float)
    diffs = a_arr - b_arr
    if len(diffs) == 0 or np.all(diffs == 0):
        return {"statistic": None, "p_value": None, "n_pairs": int(len(diffs)),
                "note": "undefined: no pairs or all differences are zero"}
    try:
        result = stats.wilcoxon(a_arr, b_arr)
        return {"statistic": float(result.statistic), "p_value": float(result.pvalue),
                "n_pairs": int(len(diffs)), "note": None}
    except ValueError as e:
        return {"statistic": None, "p_value": None, "n_pairs": int(len(diffs)), "note": str(e)}


def holm_bonferroni(pvalues_by_name: Dict[str, Optional[float]], alpha: float = 0.05
                     ) -> Dict[str, Dict[str, object]]:
    """Holm-Bonferroni step-down correction across a named family of
    p-values (ICAIRE_Simulation_Validation_Methodology.md section 7's
    stated reason: many comparisons run together must not overstate
    significance). `None` p-values (undefined tests) are passed through
    as not-significant, not silently dropped from the family count --
    they still count toward the family size `m`."""
    items = list(pvalues_by_name.items())
    m = len(items)
    defined = [(name, p) for name, p in items if p is not None]
    defined.sort(key=lambda kv: kv[1])
    out: Dict[str, Dict[str, object]] = {
        name: {"p_value": p, "adjusted_alpha": None, "significant": False} for name, p in items
    }
    for rank, (name, p) in enumerate(defined):
        adjusted_alpha = alpha / (m - rank)
        out[name]["adjusted_alpha"] = adjusted_alpha
        out[name]["significant"] = p < adjusted_alpha
        if p >= adjusted_alpha:
            # Holm's step-down: once one fails, every later (larger-p) one fails too.
            for later_name, later_p in defined[rank:]:
                out[later_name]["adjusted_alpha"] = alpha / (m - defined.index((later_name, later_p)))
                out[later_name]["significant"] = False
            break
    return out
