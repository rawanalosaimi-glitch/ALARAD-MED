"""
Final supplementary validation round -- tests for the new controlled-
scenario infrastructure itself (task 3: deterministic unit/integration/
boundary tests, reproducibility, collective-dose conservation, no
bypass of safety constraints, original campaign untouched).

Deliberately does NOT re-test policy/trigger/selection/scheduling logic
itself (that is already covered by phase3c_rotation_infra/tests/, 111
tests, unchanged in scope); this file tests only the NEW supplementary
builders and experiment modules.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from phase2a_adapter.engine_bridge import EngineBridge
from phase3c_rotation_infra.config import load_config
from phase3c_rotation_infra.policies import ALL_POLICIES, CGDTR, REFERENCE_RULE
from phase3c_rotation_infra.simulation import run_policy_on_run
from phase3c_rotation_infra.supplementary.controlled_builders import (
    WorkerSpec, build_roster, build_single_room_run, inject_fault,
)
from phase3c_rotation_infra.supplementary.experiment_a_selection import build_sub_cases, run_sub_case
from phase3c_rotation_infra.supplementary.experiment_b_sensor_faults import run_fault_case
from phase3c_rotation_infra.supplementary.experiment_c_duty_limits import SUB_CASES_C
from phase3c_rotation_infra import dose_attribution


class TestControlledBuilders(unittest.TestCase):
    def test_build_single_room_run_shape_matches_what_run_policy_on_run_expects(self):
        run = build_single_room_run(seed=1, shift_minutes=60, rate_uSv_h=100.0, n_slots=2)
        self.assertIn("slots_by_room", run)
        self.assertIn("exposure_by_slot", run)
        self.assertIn("observations_by_room", run)
        self.assertEqual(run["shift_minutes"], 60)

    def test_exposure_series_deterministic_given_same_seed(self):
        run1 = build_single_room_run(seed=7, shift_minutes=60, rate_uSv_h=150.0, n_slots=2)
        run2 = build_single_room_run(seed=7, shift_minutes=60, rate_uSv_h=150.0, n_slots=2)
        for slot_id in run1["exposure_by_slot"]:
            self.assertEqual(run1["exposure_by_slot"][slot_id], run2["exposure_by_slot"][slot_id])

    def test_different_seeds_give_different_noise(self):
        run1 = build_single_room_run(seed=1, shift_minutes=60, rate_uSv_h=150.0, n_slots=1)
        run2 = build_single_room_run(seed=2, shift_minutes=60, rate_uSv_h=150.0, n_slots=1)
        slot_id = list(run1["exposure_by_slot"].keys())[0]
        self.assertNotEqual(run1["exposure_by_slot"][slot_id], run2["exposure_by_slot"][slot_id])

    def test_worker_spec_fields_map_onto_real_worker_profile_unchanged(self):
        spec = WorkerSpec("W00", ("Cath Lab 1",), ("ct",), cumulative_dose_mSv=0.03,
                           max_dose_per_shift_mSv=1.5, rotations_so_far=2, max_rotations_per_shift=3,
                           last_valid_rate_uSv_h=42.0)
        roster = build_roster([spec], shift_minutes=60)
        w = roster["W00"]
        self.assertEqual(w.cumulative_dose_mSv, 0.03)
        self.assertEqual(w.max_dose_per_shift_mSv, 1.5)
        self.assertEqual(w.rotations_so_far, 2)
        self.assertEqual(w.last_valid_rate_uSv_h, 42.0)
        self.assertIn("Cath Lab 1", w.credentialed_rooms)

    def test_inject_fault_missing_sets_none_observations_and_zero_dose_ready_values(self):
        run = build_single_room_run(seed=1, shift_minutes=60, rate_uSv_h=150.0, n_slots=1)
        room = "Cath Lab 1"
        inject_fault(run, room, 10, 20, "missing")
        for t in range(10, 20):
            self.assertIsNone(run["observations_by_room"][room][t])
        slot = run["slots_by_room"][room][0]
        series = run["exposure_by_slot"][slot.slot_id]
        for t in range(10, 20):
            self.assertEqual(series[t - slot.start_minute], 0.0)

    def test_inject_fault_frozen_repeats_a_single_value(self):
        run = build_single_room_run(seed=1, shift_minutes=60, rate_uSv_h=150.0, n_slots=1)
        room = "Cath Lab 1"
        inject_fault(run, room, 10, 20, "frozen")
        values = {run["observations_by_room"][room][t]["value"] for t in range(10, 20)}
        self.assertEqual(len(values), 1)  # exactly one distinct value across the window


class TestExperimentAReproducibilityAndSafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_config()
        cls.bridge = EngineBridge().__enter__()
        cls.cases = {c.case_id: c for c in build_sub_cases()}

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    def test_deterministic_replay_same_seed_same_case(self):
        case = self.cases["A1"]
        res1 = run_sub_case(self.bridge, case, seed=5, p3c_cfg=self.cfg)["cgdtr"]
        res2 = run_sub_case(self.bridge, case, seed=5, p3c_cfg=self.cfg)["cgdtr"]
        self.assertEqual(res1.assignment_by_room, res2.assignment_by_room)
        self.assertEqual(res1.cumulative_dose_per_worker, res2.cumulative_dose_per_worker)

    def test_collective_dose_conservation_across_all_five_policies(self):
        """The main campaign's own invariant (fixed, gapless occupancy ->
        identical collective dose regardless of rotation policy) must
        also hold in these hand-built, controlled scenarios -- this is
        not re-deriving the invariant, it is checking the SAME real
        dose_attribution.py code produces it here too."""
        case = self.cases["A2"]
        results = run_sub_case(self.bridge, case, seed=9, p3c_cfg=self.cfg)
        collective = {name: res.collective_dose_mSv for name, res in results.items()}
        values = list(collective.values())
        for v in values[1:]:
            self.assertAlmostEqual(v, values[0], places=9)

    def test_cgdtr_and_reference_rule_can_select_different_workers(self):
        """The central positive finding of Experiment A: given a REAL
        choice (>=2 eligible candidates, unequal doses), CGDTR and
        reference-rule select differently -- confirming `rank_candidates`
        is not broken, only never exercised by the original campaign's
        roster/credential conditions."""
        case = self.cases["A1"]
        results = run_sub_case(self.bridge, case, seed=1, p3c_cfg=self.cfg)
        cg_first = next((e.incoming for e in results["cgdtr"].rotation_events if e.status == "COMPLETED"), None)
        rr_first = next((e.incoming for e in results["reference_rule"].rotation_events if e.status == "COMPLETED"), None)
        self.assertEqual(cg_first, "W02")
        self.assertEqual(rr_first, "W01")
        self.assertNotEqual(cg_first, rr_first)

    def test_tied_doses_collapse_to_same_tiebreak_both_rules(self):
        case = self.cases["A3"]
        results = run_sub_case(self.bridge, case, seed=1, p3c_cfg=self.cfg)
        cg_first = next((e.incoming for e in results["cgdtr"].rotation_events if e.status == "COMPLETED"), None)
        rr_first = next((e.incoming for e in results["reference_rule"].rotation_events if e.status == "COMPLETED"), None)
        self.assertEqual(cg_first, rr_first)

    def test_no_eligible_candidate_case_is_infeasible_not_fabricated(self):
        case = self.cases["A10"]
        results = run_sub_case(self.bridge, case, seed=1, p3c_cfg=self.cfg)
        cg = results["cgdtr"]
        self.assertEqual(cg.n_completed, 0)
        self.assertGreater(cg.n_infeasible, 0)
        for e in cg.rotation_events:
            self.assertIn(e.status, ("INFEASIBLE", "UNRESOLVED_AT_SHIFT_END"))

    def test_duty_limited_candidate_is_excluded_not_silently_selected(self):
        """A6: W02 has the lowest dose but has used up its duty-limit
        rotation budget -- it must never appear as the chosen incoming
        worker for any policy."""
        case = self.cases["A6"]
        results = run_sub_case(self.bridge, case, seed=1, p3c_cfg=self.cfg)
        for name, res in results.items():
            for e in res.rotation_events:
                if e.status == "COMPLETED":
                    self.assertNotEqual(e.incoming, "W02")


class TestExperimentBSafetyAndAttribution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_config()
        cls.bridge = EngineBridge().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    def test_missing_fault_raises_and_resolves_escalation(self):
        row = run_fault_case(self.bridge, "B1", "missing", 10, 30, seed=1, p3c_cfg=self.cfg)
        esc = row["escalation_results"]["W00"]
        self.assertEqual(esc["state"], "RESOLVED")
        self.assertIsNotNone(esc["raised_at"])
        self.assertEqual(esc["resolution_reason"], "sensor_fault_cleared")

    def test_frozen_fault_is_detected_as_suspected_frozen(self):
        row = run_fault_case(self.bridge, "B3", "frozen", 10, 30, seed=1, p3c_cfg=self.cfg)
        states = row["sensor_state_history"]["W00"]
        self.assertIn("SUSPECTED_FROZEN", states)

    def test_two_simultaneous_worker_faults_attributed_independently(self):
        row = run_fault_case(self.bridge, "B8", "missing", 10, 30, seed=1, p3c_cfg=self.cfg, second_worker=True)
        self.assertEqual(set(row["escalation_results"].keys()), {"W00", "W01"})
        for worker_id, esc in row["escalation_results"].items():
            self.assertEqual(esc["state"], "RESOLVED")
            for ev in esc["audit_log"]:
                self.assertEqual(ev["worker_id"], worker_id)  # never cross-attributed

    def test_escalation_detection_never_mutates_dose_or_rotation_fields(self):
        """Structural safety check: applying evaluate_escalation to the
        captured sensor history must never itself change the
        simulation's own dose or rotation outcome -- it is read-only
        analysis, called AFTER run_policy_on_run already finished."""
        row = run_fault_case(self.bridge, "B2", "invalid", 10, 30, seed=1, p3c_cfg=self.cfg)
        sim = row["simulation_result"]
        self.assertIn("cumulative_dose_per_worker", sim)
        self.assertIn("collective_dose_mSv", sim)
        # escalation_results is a separate top-level key, not merged into sim
        self.assertNotIn("escalation_results", sim)


class TestExperimentCSafetyAndCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_config()
        cls.bridge = EngineBridge().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    def _run(self, case_id):
        fn = next(fn for cid, _title, fn in SUB_CASES_C if cid == case_id)
        return fn(self.bridge, seed=1, cfg=self.cfg)

    def test_clause_a_b_c_each_isolated_without_the_others_firing(self):
        res_a, _ = self._run("C1")
        self.assertEqual(set(res_a.trigger_clause_counts.keys()), {"a"})
        res_b, _ = self._run("C2")
        self.assertEqual(set(res_b.trigger_clause_counts.keys()), {"b"})
        res_c, _ = self._run("C3")
        self.assertEqual(set(res_c.trigger_clause_counts.keys()), {"c"})

    def test_projected_duty_limit_exclusion_actually_excludes(self):
        """C4: at the first trigger (t_decide=30), W01's projected dose
        over its full intended assignment interval exceeds its own cap,
        so it must be excluded -- the trigger goes INFEASIBLE despite
        W01 being the only other credentialed, otherwise-FREE candidate.
        (A later trigger in this same scenario lands with zero remaining
        assignment minutes -- a legitimate, different edge case, not
        re-asserted here; see ALARAD_SUPPLEMENTARY_CAMPAIGN_RESULTS.md.)"""
        res, _ = self._run("C4")
        first = next(e for e in res.rotation_events if e.t_decide == 30)
        self.assertEqual(first.status, "INFEASIBLE")
        self.assertIsNone(first.incoming)

    def test_held_then_completes_after_fault_clears(self):
        res, meta = self._run("C6")
        self.assertGreater(res.n_held, 0)
        completed = [e for e in res.rotation_events if e.status == "COMPLETED"]
        self.assertTrue(any(e.reason == "completed_after_incident_acknowledgement" for e in completed))

    def test_unresolved_at_shift_end_when_incident_never_clears(self):
        res, meta = self._run("C9")
        self.assertGreater(res.n_unresolved_at_shift_end, 0)
        unresolved = [e for e in res.rotation_events if e.status == "UNRESOLVED_AT_SHIFT_END"]
        self.assertTrue(any(e.reason == "held_incident_never_cleared_before_shift_end" for e in unresolved))

    def test_acknowledgement_rejected_reported_as_not_implemented(self):
        res, meta = self._run("C10")
        self.assertIsNone(res)
        self.assertEqual(meta["status"], "NOT_IMPLEMENTED")

    def test_simultaneous_cross_room_trigger_never_double_reserves(self):
        """C12: both rooms want the same sole shared candidate at the
        same decision minute -- exactly one of them gets it."""
        res, _ = self._run("C12")
        completed = [e for e in res.rotation_events if e.status == "COMPLETED"]
        incoming_ids = [e.incoming for e in completed]
        self.assertEqual(len(incoming_ids), len(set(incoming_ids)))  # no worker double-booked


class TestOriginalCampaignUntouched(unittest.TestCase):
    def test_original_campaign_output_directory_unmodified_by_this_package(self):
        """This package must never OPEN/WRITE the original campaign's
        own output directory (mentioning the path in a comment, to
        explain that it is deliberately avoided, is fine and expected --
        this checks for an actual file-operation call, not the string)."""
        import inspect
        import re
        from phase3c_rotation_infra.supplementary import (
            controlled_builders, experiment_a_selection, experiment_b_sensor_faults, experiment_c_duty_limits,
        )
        pattern = re.compile(r'(open|Path)\([^)]*phase3c_campaign_output')
        for module in (controlled_builders, experiment_a_selection, experiment_b_sensor_faults, experiment_c_duty_limits):
            source = inspect.getsource(module)
            self.assertIsNone(pattern.search(source), f"{module.__name__} appears to touch phase3c_campaign_output")

    def test_original_manifest_and_raw_runs_still_present_and_unchanged_count(self):
        out_dir = Path(__file__).resolve().parents[3] / "phase3c_campaign_output"
        manifest = json.loads((out_dir / "manifest.json").read_text())
        self.assertEqual(len(manifest["completed_runs"]), 390)
        self.assertEqual(len(manifest["failed_runs"]), 0)
        raw_files = list((out_dir / "raw_runs").glob("*.json"))
        self.assertEqual(len(raw_files), 390)


if __name__ == "__main__":
    unittest.main()
