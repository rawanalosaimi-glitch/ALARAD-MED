"""Task 1 / 7: seeded synthetic staffing module -- reproducibility and
basic structural correctness."""

from __future__ import annotations

import unittest

from phase1_simulator.scenario import ROOMS
from phase3c_rotation_infra.staffing import FREE, generate_roster

PROCEDURE_CLASSES = ["diagnostic_fluoroscopy", "interventional_cath_lab", "ct", "pet_ct"]


class TestStaffing(unittest.TestCase):
    def test_seed_reproducibility(self):
        r1 = generate_roster(42, 120, 2, ROOMS, PROCEDURE_CLASSES)
        r2 = generate_roster(42, 120, 2, ROOMS, PROCEDURE_CLASSES)
        self.assertEqual([w.worker_id for w in r1], [w.worker_id for w in r2])
        for w1, w2 in zip(r1, r2):
            self.assertEqual(w1.credentialed_rooms, w2.credentialed_rooms)
            self.assertEqual(w1.credentialed_procedure_classes, w2.credentialed_procedure_classes)
            self.assertEqual(w1.max_dose_per_shift_mSv, w2.max_dose_per_shift_mSv)
            self.assertEqual(w1.min_rest_between_assignments_minutes, w2.min_rest_between_assignments_minutes)
            self.assertEqual(w1.max_rotations_per_shift, w2.max_rotations_per_shift)

    def test_different_seed_gives_different_roster(self):
        r1 = generate_roster(1, 120, 2, ROOMS, PROCEDURE_CLASSES)
        r2 = generate_roster(2, 120, 2, ROOMS, PROCEDURE_CLASSES)
        creds1 = [sorted(w.credentialed_rooms) for w in r1]
        creds2 = [sorted(w.credentialed_rooms) for w in r2]
        self.assertNotEqual(creds1, creds2)

    def test_roster_size_is_concurrent_rooms_plus_extra(self):
        roster = generate_roster(7, 120, 3, ROOMS, PROCEDURE_CLASSES)
        # extra_workers_beyond_concurrent_rooms is 1 in the shipped config
        self.assertEqual(len(roster), 3 + 1)

    def test_every_worker_starts_free_with_zero_rotations(self):
        roster = generate_roster(7, 120, 2, ROOMS, PROCEDURE_CLASSES)
        for w in roster:
            self.assertEqual(w.state, FREE)
            self.assertEqual(w.rotations_so_far, 0)
            self.assertEqual(w.last_rotation_out_minute, None)

    def test_availability_windows_cover_full_shift_by_default(self):
        roster = generate_roster(7, 240, 2, ROOMS, PROCEDURE_CLASSES)
        for w in roster:
            self.assertTrue(w.is_within_availability(0))
            self.assertTrue(w.is_within_availability(239))
            self.assertTrue(w.is_within_availability_interval(0, 240))

    def test_credentialing_check_matches_sampled_sets(self):
        roster = generate_roster(7, 120, 2, ROOMS, PROCEDURE_CLASSES)
        w = roster[0]
        for room in ROOMS:
            for proc in PROCEDURE_CLASSES:
                expected = room in w.credentialed_rooms and proc in w.credentialed_procedure_classes
                self.assertEqual(w.is_credentialed_for(room, proc), expected)

    def test_availability_interval_check_rejects_partial_coverage(self):
        roster = generate_roster(7, 120, 2, ROOMS, PROCEDURE_CLASSES)
        w = roster[0]
        w.availability_windows = [(0, 50)]
        self.assertTrue(w.is_within_availability_interval(0, 50))
        self.assertFalse(w.is_within_availability_interval(0, 51))
        self.assertFalse(w.is_within_availability_interval(40, 60))


if __name__ == "__main__":
    unittest.main()
