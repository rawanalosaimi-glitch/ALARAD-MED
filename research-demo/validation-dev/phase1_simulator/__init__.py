"""
Phase 1 synthetic radiation-exposure simulator for the ICAIRE research
validation framework.

This package is standalone research-development code. It does not import,
read, or depend on the frozen ALARAD v1.2.3 release in any way -- it is an
independent reimplementation of the conventions documented in
ICAIRE_Simulation_Validation_Methodology.md (Revision 2), built to generate
reproducible synthetic exposure data and ground truth for later evaluation
phases.

Phase 1 scope only: this package generates simulated worker/room/procedure/
shift data and injects labelled ground truth (radiation anomalies and
sensor/data-quality faults). It does NOT implement any detector, forecaster,
baseline comparator, or rotation recommender, and it does NOT compute any
evaluation metric (precision/recall/F1/MAE/etc.). Those are explicitly
later-phase work per the methodology document.
"""

__version__ = "1.0.0-phase1"
