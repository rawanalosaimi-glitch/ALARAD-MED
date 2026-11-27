"""
Phase 3C-A: Rotation Simulation Infrastructure and Safety Foundations.

Implements the plumbing specified in PHASE3B_ROTATION_ALGORITHM_DESIGN.md
(Revision 2) -- synthetic staffing/credentialing, the two-layer
exposure/assignment counterfactual model, the worker-exclusivity and
rotation-scheduling state machines, dose attribution, and sensor-fault
escalation -- WITHOUT implementing any rotation-decision algorithm
(CGDTR) or the five-policy comparison. Rotation "requests" that exercise
this infrastructure in tests are supplied directly by the caller
(synthetic/programmatic), not produced by a dose-trigger rule: per this
round's read-only audit (PHASE3C_A_DOSE_THRESHOLD_SEMANTIC_AUDIT.md),
the frozen engine's actual CONFIG.doseElevated/doseCritical semantics do
not match what PHASE3B section 3a assumed, so no trigger formula is
implemented here until that is resolved.

Isolated from phase1_simulator, phase2a_adapter, and phase3a_forecasting:
this package imports reusable pieces from them (rng, units, dose
formula, the real engine's sensorStep via dq_adapter) but does not
modify any of them.
"""
