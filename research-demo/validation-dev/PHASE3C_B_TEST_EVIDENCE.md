# Phase 3C-B — Test Evidence

**Commands actually executed, in this session, from `research-demo/validation-dev/`:**
```
python3 -m unittest discover -s phase3c_rotation_infra/tests -t . -v
python3 -m unittest discover -s phase3a_forecasting/tests -t . -v
```
**Rotation infrastructure: 109 tests, 109 passed, 0 failed, 0 skipped,
0 errors.** Re-confirmed three times across this session (after writing
`run_campaign.py`/`run_sensitivity.py`, which do not touch any tested
module; and again as part of final verification) with an identical
result each time.

**Forecasting: 47 tests, 47 passed, 0 failed, 0 skipped, 0 errors**
(33 pre-existing + 14 new in `test_metrics.py`, added this session after
the statistical campaign surfaced two real defects in this round's own
new analysis code -- see `PHASE3C_B_CAMPAIGN_RESULTS.md` section 8d for
the defects and the fix, and the `test_metrics.py` row below for what
the new tests pin; counts verified programmatically via
`unittest.TestLoader().discover(...)`, not by eye). **Combined: 156
tests, 156 passed, 0 failed.**

No test anywhere in `phase3c_rotation_infra/tests/` uses
`@unittest.skip`. Four files require a live `EngineBridge` (a real,
headless Chromium session against the frozen, unmodified
`ALARAD_Prototype_Research_Demo_v1.2.3.html`) and were run against it,
not stubbed out: `test_sensor_validity.py`, `test_runtime.py`,
`test_dose_quantities.py`, `test_policies.py`, `test_simulation.py`.

| File | Tests | Covers |
|---|---|---|
| `test_config.py` | 5 | provisional-labeling + synthetic-source enforcement |
| `test_staffing.py` | 7 | seed reproducibility, roster sizing, credentialing, availability |
| `test_exposure_layer.py` | 7 | boundary/slot reproducibility, exposure-series identity across policies, remaining-minutes helper |
| `test_sensor_validity.py` | 6 | per-minute real-engine sensor queries, step-vs-batch consistency, trusted-for-trigger classification |
| `test_dose_quantities.py` | 7 | the three section 3a quantities: dimensional consistency, correct threshold ownership (each function's signature cannot reach the wrong threshold), batch/individual equivalence |
| `test_runtime.py` | 7 | live per-minute dose accrual (assigned-only, usable-only), last-valid-rate tracking, live-vs-replay equivalence, batch/sequential equivalence |
| `test_assignment.py` | 11 | worker exclusivity, simultaneous-request batch resolution, deterministic tie-breaking, duty-limit exclusion (new, undefined-not-excluded), backward compatibility |
| `test_scheduling.py` | 15 | boundary-aligned swaps, multi-boundary handoff spanning, infeasible-near-shift-end, emergency override (never self-invoked), interrupted handoff, incident hold, post-acknowledgement recompute, audit log |
| `test_dose_attribution.py` | 4 | collective-dose conservation under fixed occupancy, no double counting (raises on conflict), no missing attribution, unassigned-minute handling |
| `test_escalation.py` | 8 | sensor-fault-persistence escalation (pure logic + real-engine integration), unacknowledged-vs-acknowledged resolution, no dose-related field anywhere |
| `test_campaign_scenarios.py` | 5 | all 13 archetypes build without error, reproducibility, multi-worker room-track count, non-negative exposure values |
| `test_policies.py` | 12 | trigger clause separation (proves clause (b)/(c) use the correct, distinct quantities and thresholds), shared-trigger guarantee (CGDTR=reference-rule, fixed-interval=Ablation D), selection ranking |
| `test_simulation.py` | 13 | collective-dose invariant across all five policies, fair no-rotation baseline, deterministic replay, exposure-layer non-mutation, no double counting, no unauthorized override, ablation-pair identical timing, HELD/escalation/audit-trail end to end |
| **Rotation subtotal** | **109** | |
| `phase3a_forecasting/tests/test_metrics.py` | 14 | MAE/RMSE and skill-vs-persistence pure-function correctness: skipped/None/NaN rows excluded (not scored as zero or propagated as NaN), zero-persistence-error and no-shared-timestamp cases return undefined (not a crash), and -- the regression tests for the two real defects this round found -- pooling rows from multiple series with colliding bare `t` values no longer silently drops/overwrites data once `series_id` is included in the pairing key |
| Pre-existing `phase3a_forecasting/tests/` (6 files: `test_baselines.py` 6, `test_dose_rate_vs_cumulative.py` 5, `test_edge_cases.py` 6, `test_forecast_adapter.py` 9, `test_forecast_contract.py` 4, `test_temporal_leakage.py` 3) | 33 | no-leakage forecast-window construction, baseline-method correctness, dose-rate-vs-cumulative edge cases, forecast contract against the real engine |
| **Combined total** | **156** | |

## Mapping to this round's mandatory test-coverage list

| Required coverage | Test(s) |
|---|---|
| Dose-rate and cumulative-dose calculations | `test_dose_quantities.py` (dimensional consistency), `test_runtime.py` (live accrual), `test_dose_attribution.py` |
| Correct threshold ownership | `test_dose_quantities.py::test_never_needs_or_calls_an_engine_bridge`, `test_policies.py::test_clause_b_fires_on_engine_threshold_not_accrued_total`, `::test_clause_c_fires_on_duty_limit_not_engine_threshold` |
| Sensor validity and missing data | `test_sensor_validity.py`, `test_runtime.py::test_missing_reading_contributes_no_dose`, `::test_last_valid_rate_tracks_only_healthy_minutes` |
| Duty-limit eligibility | `test_assignment.py::test_candidate_excluded_if_projected_to_exceed_duty_limit`, `::test_candidate_with_no_trusted_reading_not_excluded_by_duty_limit` |
| Worker exclusivity and simultaneous requests | `test_assignment.py::test_two_simultaneous_requests_with_the_same_top_candidate_never_double_reserve`, `::test_processing_order_is_deterministic_by_ascending_room_name` |
| Procedure-boundary alignment | `test_scheduling.py::test_t_effective_always_lands_on_a_boundary`, `::test_never_completes_mid_procedure_without_override` |
| Interrupted and delayed handoffs | `test_scheduling.py::test_interrupted_handoff_aborts_and_does_not_swap`, `::test_handoff_spanning_multiple_boundaries_lands_on_first_valid_one` |
| RSO acknowledgement | `test_scheduling.py::test_held_attempt_recomputes_next_boundary_after_acknowledgement_not_the_stale_one`, `test_simulation.py::TestHeldAndEscalation` |
| Escalation persistence and audit logging | `test_escalation.py` (sensor-fault channel), `test_simulation.py::test_persistent_infeasible_rotation_escalates` (dose-concern channel) |
| Shift-end unresolved events | `test_scheduling.py::test_held_attempt_aborts_if_no_boundary_remains_after_acknowledgement`, `::test_infeasible_when_no_boundary_remains_before_shift_end` |
| Deterministic replay | `test_simulation.py::test_deterministic_replay_same_seed_same_policy`, `test_campaign_scenarios.py::test_reproducible_for_same_seed_and_archetype` |
| Identical exposure layers across policies | `test_simulation.py::test_exposure_layer_untouched_by_any_policy`, `test_exposure_layer.py::test_exposure_series_same_across_different_rotation_policies` |
| No dose double counting | `test_dose_attribution.py::test_no_double_counting_conflicting_assignment_raises`, `test_simulation.py::test_no_double_counting_across_policies` |
| Collective-dose conservation under fixed occupancy | `test_dose_attribution.py::test_collective_dose_conservation_under_fixed_occupancy_...`, `test_simulation.py::test_collective_dose_invariant_holds_across_all_five_policies` |
| No unauthorized emergency override | `test_simulation.py::test_no_unauthorized_emergency_override` (structural check of the orchestrator's own source) |

## What this evidence does not claim

- Does not claim the campaign's own results (run separately, see
  `PHASE3C_B_CAMPAIGN_RESULTS.md`) are validated by these tests --
  these tests validate the *mechanism*, not any particular campaign
  outcome.
- Does not claim 100% branch/line coverage was measured (no coverage
  tool was run this round); the mapping above is a manual, honest
  cross-reference against the mandatory coverage list, not a generated
  coverage report.
