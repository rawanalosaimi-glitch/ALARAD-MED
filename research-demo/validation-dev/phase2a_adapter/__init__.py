"""
Phase 2A: Detection Evaluation Integration.

This package does NOT reimplement or approximate the frozen ALARAD v1.2.3
detection engine. It loads the frozen, unmodified release in a real
browser (via Playwright) and calls the engine's own, already-exposed
functions (`evaluateExposure`, `SimLab.pure.buildEpisodes`,
`SimLab.pure.matchEvents`, `SimLab.pure.metrics`, `AlaradSafety.sensorStep`)
directly. The frozen file is opened read-only and never written to.

Scope: radiation-anomaly detection evaluation (personal-mode workers only
-- see PHASE2A_LIMITATIONS.md for why area-mode is out of scope this
phase), sensor/data-quality fault detection evaluation (both modes), two
new comparison baselines (fixed-threshold, moving-average), and the
additional metrics (false alarms per worker-shift, event-level detection
delay) the methodology calls for. No forecasting or rotation algorithm is
implemented here.
"""

__version__ = "1.0.0-phase2a"
