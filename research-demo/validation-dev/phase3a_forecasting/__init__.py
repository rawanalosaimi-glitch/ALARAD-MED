"""
Phase 3A: Forecasting Evaluation Design and Implementation.

Evaluates the frozen ALARAD v1.2.3 engine's own existing forecasting
function, `linearForecast`, against Phase 1 synthetic data -- it does
NOT implement any new forecasting model, trained or otherwise. Two
independently-implemented comparison baselines (persistence, simple
exponential smoothing) are provided for context, scored through the
same metrics as the real function.

See PHASE3A_LIMITATIONS.md section 1 for an important, verified mismatch
between the methodology document's forecast-horizon language and what
`linearForecast` actually supports -- read before assuming any horizon
beyond 3 minutes ahead is achievable with the existing function.

No forecasting or rotation algorithm is implemented beyond evaluating
what already exists. No worker-rotation code exists in this package.
"""

__version__ = "1.0.0-phase3a"
