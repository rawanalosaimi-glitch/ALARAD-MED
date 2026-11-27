"""End-to-end tests for the simulation orchestrator (task 4): collective-
dose conservation across all five policies, no double counting, fair
no-rotation baseline, deterministic replay, and no unauthorized
emergency override."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from phase1_simulator import config as p1_config_mod
from phase1_simulator.scenario import ROOMS
from phase2a_adapter.engine_bridge import EngineBridge
from phase3c_rotation_infra.campaign_scenarios import build_campaign_run
from phase3c_rotation_infra.config import Phase3CConfig, load_config
from phase3c_rotation_infra.policies import ABLATION_D, ALL_POLICIES, CGDTR, FIXED_INTERVAL, NO_ROTATION, REFERENCE_RULE
from phase3c_rotation_infra.simulation import run_policy_on_run
from phase3c_rotation_infra.staffing import generate_roster

PROCEDURE_CLASSES = ["diagnostic_fluoroscopy", "interventional_cath_lab", "ct", "pet_ct"]
P1_CONFIG_PATH = Path(p1_config_mod.__file__).parent / "config" / "simulation_config.json"


def _stress_config() -> Phase3CConfig:
    """A config that makes rotations actually happen frequently, so the
    machinery (trigger -> reserve -> handoff -> complete/infeasible) is
    genuinely exercised by these tests, not just run with zero events."""
    base = load_config()
    raw = copy.deepcopy(base.raw)
    raw["cgdtr_trigger"]["rotation_threshold_fraction"] = 0.0001
    raw["cgdtr_trigger"]["reference_level_mSv_per_shift"] = 0.001
    raw["handoff"]["min_handoff_duration_minutes"] = 5
    raw["fixed_interval_baseline"]["fixed_interval_minutes"] = 30
    return Phase3CConfig(raw=raw)


def _roster_for(run, seed, p3c_cfg):
    return {
        w.worker_id: w
        for w in generate_roster(seed, run["shift_minutes"], len(run["slots_by_room"]) + 1,
                                  ROOMS, PROCEDURE_CLASSES, p3c_cfg)
    }


class TestSimulation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = EngineBridge().__enter__()
        cls.p1_cfg = p1_config_mod.load_config(P1_CONFIG_PATH)
        cls.p3c_cfg = _stress_config()
        cls.seed = 4001
        cls.archetype = "multi_worker_mixed"
        cls.campaign_run = build_campaign_run(cls.seed, cls.archetype, cls.p1_cfg, cls.p3c_cfg)

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    def _run(self, policy):
        roster = _roster_for(self.campaign_run, self.seed, self.p3c_cfg)
        return run_policy_on_run(self.bridge, self.campaign_run, roster, policy, self.p3c_cfg)

    def test_no_rotation_baseline_has_zero_events(self):
        """Fair evaluation: the no-rotation baseline must never invent a
        rotation attempt or a penalty."""
        res = self._run(NO_ROTATION)
        self.assertEqual(res.rotation_events, [])
        self.assertEqual(res.n_completed, 0)
        self.assertEqual(res.n_infeasible, 0)
        self.assertEqual(res.n_aborted, 0)
        self.assertEqual(res.n_held, 0)

    def test_at_least_one_policy_actually_rotates_under_stress_config(self):
        """Sanity check that the stress config is actually exercising
        the machinery, not silently running zero rotations."""
        res = self._run(CGDTR)
        self.assertGreater(len(res.rotation_events), 0)

    def test_collective_dose_invariant_holds_across_all_five_policies(self):
        """The central invariant (PHASE3B section 7b, task 8): fixed
        occupancy (every slot-minute attributed to exactly one worker,
        no dead time) means collective dose must be identical across
        every policy, however differently they redistribute it
        individually."""
        collective = {}
        max_individual = {}
        for policy in ALL_POLICIES:
            res = self._run(policy)
            collective[policy.name] = res.collective_dose_mSv
            max_individual[policy.name] = res.max_individual_dose_mSv

        values = list(collective.values())
        for v in values[1:]:
            self.assertAlmostEqual(v, values[0], places=9, msg=collective)

    def test_redistribution_is_not_reported_as_collective_reduction(self):
        """Task 8's explicit requirement: a policy that changes
        max-individual dose (redistribution) must not show a different
        collective dose -- checked directly, not merely asserted in
        prose."""
        no_rot = self._run(NO_ROTATION)
        cgdtr = self._run(CGDTR)
        self.assertAlmostEqual(no_rot.collective_dose_mSv, cgdtr.collective_dose_mSv, places=9)
        # individual doses are free to differ -- that IS redistribution,
        # and is explicitly allowed to differ from collective dose.

    def test_deterministic_replay_same_seed_same_policy(self):
        res1 = self._run(CGDTR)
        res2 = self._run(CGDTR)
        self.assertEqual(res1.cumulative_dose_per_worker, res2.cumulative_dose_per_worker)
        self.assertEqual(len(res1.rotation_events), len(res2.rotation_events))
        self.assertEqual(res1.n_completed, res2.n_completed)
        self.assertEqual(res1.n_infeasible, res2.n_infeasible)

    def test_exposure_layer_untouched_by_any_policy(self):
        before = copy.deepcopy(self.campaign_run["exposure_by_slot"])
        for policy in ALL_POLICIES:
            self._run(policy)
        self.assertEqual(self.campaign_run["exposure_by_slot"], before)

    def test_no_double_counting_across_policies(self):
        """dose_attribution.attribute_dose raises on any double-claimed
        minute -- run_policy_on_run calls it internally for every
        policy; reaching this point without an exception already proves
        it, this test just makes the claim explicit and permanent."""
        for policy in ALL_POLICIES:
            try:
                self._run(policy)
            except Exception as e:  # pragma: no cover - should never happen
                self.fail(f"{policy.name} raised {e!r} (likely a double-counting conflict)")

    def test_no_unauthorized_emergency_override(self):
        """The orchestrator never passes emergency_override=True to
        scheduling.resolve_attempt anywhere -- checked structurally by
        reading its own source, not just by behavioral inference."""
        import inspect

        from phase3c_rotation_infra import simulation as sim_module
        source = inspect.getsource(sim_module)
        self.assertNotIn("emergency_override=True", source)
        self.assertNotIn("emergency_override =True", source)

    def test_ablation_pair_shares_identical_trigger(self):
        """fixed_interval and ablation_d must produce identical rotation
        *timing* (same trigger) even though selection differs."""
        res_fi = self._run(FIXED_INTERVAL)
        res_ad = self._run(ABLATION_D)
        fi_times = sorted(e.t_decide for e in res_fi.rotation_events)
        ad_times = sorted(e.t_decide for e in res_ad.rotation_events)
        self.assertEqual(fi_times, ad_times)

    def test_reference_rule_shares_identical_trigger_with_cgdtr_end_to_end(self):
        res_rr = self._run(REFERENCE_RULE)
        res_cg = self._run(CGDTR)
        rr_times = sorted(e.t_decide for e in res_rr.rotation_events)
        cg_times = sorted(e.t_decide for e in res_cg.rotation_events)
        self.assertEqual(rr_times, cg_times)


class TestHeldAndEscalation(unittest.TestCase):
    """A separate scenario/seed combination known to produce a HELD
    (incident-blocked) handoff and a persistent-infeasible escalation --
    exercises the simulated-RSO-acknowledgement path and the shift-end
    unresolved-escalation path end to end, not just scheduling.py's own
    scripted unit tests."""

    @classmethod
    def setUpClass(cls):
        cls.bridge = EngineBridge().__enter__()
        p1_cfg = p1_config_mod.load_config(P1_CONFIG_PATH)
        cls.p3c_cfg = _stress_config()
        cls.seed = 5001
        cls.archetype = "multi_worker_faults"
        cls.campaign_run = build_campaign_run(cls.seed, cls.archetype, p1_cfg, cls.p3c_cfg)
        cls.roster = _roster_for(cls.campaign_run, cls.seed, cls.p3c_cfg)
        cls.result = run_policy_on_run(cls.bridge, cls.campaign_run, cls.roster, CGDTR, cls.p3c_cfg)

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    def test_held_attempt_occurred(self):
        self.assertGreater(self.result.n_held, 0)

    def test_persistent_infeasible_rotation_escalates(self):
        """Section 3h's original concept (distinct from escalation.py's
        own sensor-fault channel, per this module's documented
        simplification 5): a room with repeated infeasible triggers and
        no completed rotation is recorded in escalated_rooms -- never
        silently dropped."""
        self.assertGreater(len(self.result.escalated_rooms), 0)
        for room, count in self.result.escalated_rooms.items():
            self.assertGreaterEqual(count, 2)

    def test_audit_trail_records_every_rotation_attempt_outcome(self):
        """Every logged event has an explicit status -- INFEASIBLE,
        COMPLETED, (via HELD-then-resolved) one of those two, or
        UNRESOLVED_AT_SHIFT_END (an attempt still pending when the shift
        ends, see test_unresolved_attempt_at_shift_end_is_counted_not_dropped
        below) -- never an unset/unknown outcome."""
        self.assertGreater(len(self.result.rotation_events), 0)
        for event in self.result.rotation_events:
            self.assertIn(event.status, ("COMPLETED", "INFEASIBLE", "UNRESOLVED_AT_SHIFT_END"))

    def test_unresolved_attempt_at_shift_end_is_counted_not_dropped(self):
        """Regression test for a real bug found during the final
        supplementary validation round: `scheduling.compute_t_effective`
        legitimately allows t_effective == shift_minutes (shift end is
        itself a valid boundary, per its own docstring), but the main
        per-minute loop only iterates t in range(shift_minutes) and so
        never reaches that minute to resolve the attempt -- before the
        fix, such an attempt (and any HELD attempt whose incident never
        cleared) was silently dropped from every counter: not completed,
        not infeasible, not held, not aborted. This stress scenario's own
        high rotation rate was already latently exercising this path
        (see test_audit_trail_records_every_rotation_attempt_outcome's
        now-updated assertion); this test makes the count explicit and
        checks it is never silently absorbed elsewhere."""
        total_logged = (self.result.n_completed + self.result.n_infeasible
                         + self.result.n_unresolved_at_shift_end)
        self.assertEqual(total_logged, len(self.result.rotation_events))
        for event in self.result.rotation_events:
            if event.status == "UNRESOLVED_AT_SHIFT_END":
                self.assertIn(event.reason, (
                    "t_effective_equals_shift_minutes_never_reached_by_main_loop",
                    "held_incident_never_cleared_before_shift_end"))


if __name__ == "__main__":
    unittest.main()
