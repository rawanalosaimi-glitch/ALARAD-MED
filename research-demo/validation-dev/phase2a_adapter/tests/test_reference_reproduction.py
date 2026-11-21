"""
Task 8 / Phase 2C items 1, 4, 5: confirms the adapter's own call sequence
reproduces the frozen engine's OWN built-in output on reference
scenarios -- now extended (Phase 2C) to cover all 13 scenarios across
both layers, the area-mode pathway (S4), and the immediate-alert bypass
specifically (S8 at K=3/K=5), per PHASE2B_INTEGRATION_AUDIT.md sections
3, 4, and 7. Nothing here claims coverage of a scenario without an
exact-match assertion against that scenario's own engine-computed
output -- per the Phase 2C restriction not to claim coverage otherwise.
"""

from __future__ import annotations

import unittest

from phase2a_adapter.dq_adapter import DQ_FLAGGED_STATES, run_sensor_state_machine
from phase2a_adapter.engine_bridge import EngineBridge

RADIATION_PERSONAL_SCENARIOS = ["S1", "S2", "S3", "S5", "S6"]
DQ_SCENARIOS = ["S7", "S8", "S9", "S10", "S11", "S12", "S13"]
# Scenarios in DQ_SCENARIOS that also carry a radiation ground truth,
# per Ground_Truth_Scenarios_S1-S13.md.
DQ_SCENARIOS_WITH_RADIATION_EVENTS = {"S8", "S9", "S12", "S13"}
# The one fault kind (delayed, S13 only) whose claimed sample timestamp
# cannot be recovered from SafetyLab's own exposed row fields alone;
# reconstructed here from the documented lag value already extracted and
# verified in Ground_Truth_Scenarios_S1-S13.md ("delayed, minute 24 to
# 32, lag=3 minutes"), not guessed.
KNOWN_DELAYED_LAG = {"S13": {"start": 24, "end": 32, "lag": 3}}


class TestRadiationLayerReproduction(unittest.TestCase):
    """Reproduces SimLab's own S1, S2, S3, S5, S6 (personal-mode) and S4
    (area-mode) using only this adapter's own call sequence, fed the
    exact per-minute data the engine itself generated."""

    @classmethod
    def setUpClass(cls):
        cls.bridge = EngineBridge().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    def _engine_reference(self, scenario_id: str, K: int = 1):
        return self.bridge.evaluate(
            """(args) => {
                const r = SimLab.run(args.id, args.K, 0);
                return r.workers.map(w => ({
                    room: w.room, mode: w.mode,
                    truth: w.events.map(e => ({start: e.start, end: e.end})),
                    TP: w.TP, FP: w.FP, FN: w.FN,
                    rows: w.rows.map(x => ({valid: x.valid, engineRate: x.valid ? x.engineRate : null, dist: x.dist})),
                }));
            }""",
            {"id": scenario_id, "K": K},
        )

    def _reproduce_personal(self, worker, K: int = 1):
        rates = [r["engineRate"] for r in worker["rows"]]
        flagged = self.bridge.evaluate(
            """(args) => args.rates.map(r => {
                if (r === null || !SimLab.pure.validReading(r)) return false;
                const ev = evaluateExposure({room: args.room, procMult: 1.0, rate: r, dur: 30, dist: 1, refDist: 1, shield: 1, mode: 'personal'});
                return ev.riskClass !== 'low';
            })""",
            {"rates": rates, "room": worker["room"]},
        )
        return self._score(flagged, worker["truth"], K)

    def _reproduce_area(self, worker, K: int = 1):
        # S4's own refDist/shield are both 1.0 (Ground_Truth_Scenarios_S1-S13.md).
        ref_dist, shield = 1.0, 1.0
        derived_raw = []
        for row in worker["rows"]:
            if not row["valid"]:
                derived_raw.append(None)
                continue
            dist = row["dist"]
            derived_raw.append(row["engineRate"] / ((ref_dist / dist) ** 2) / shield)
        flagged = self.bridge.evaluate(
            """(args) => {
                const { rows, derivedRaw, room } = args;
                return rows.map((row, t) => {
                    if (!row.valid) return false;
                    const ev = evaluateExposure({room, procMult: 1.0, rate: derivedRaw[t], dur: 30, dist: row.dist, refDist: 1.0, shield: 1.0, mode: 'area'});
                    return ev.riskClass !== 'low';
                });
            }""",
            {"rows": worker["rows"], "derivedRaw": derived_raw, "room": worker["room"]},
        )
        return self._score(flagged, worker["truth"], K)

    def _score(self, flagged, truth, K):
        be = self.bridge.evaluate(
            "(args) => SimLab.pure.buildEpisodes(args.flagged, args.K, null)",
            {"flagged": flagged, "K": K},
        )
        mt = self.bridge.evaluate(
            "(args) => SimLab.pure.matchEvents(args.events, args.episodes, 2)",
            {"events": truth, "episodes": be["episodes"]},
        )
        TP = sum(1 for m in mt["matches"] if m is not None)
        FN = len(truth) - TP
        FP = len(mt["fp"])
        return {"TP": TP, "FP": FP, "FN": FN}

    def test_personal_mode_reference_scenarios_reproduce_exactly(self):
        for scenario_id in RADIATION_PERSONAL_SCENARIOS:
            workers = self._engine_reference(scenario_id)
            for w in workers:
                reproduced = self._reproduce_personal(w)
                self.assertEqual(reproduced["TP"], w["TP"], msg=f"{scenario_id} TP mismatch")
                self.assertEqual(reproduced["FP"], w["FP"], msg=f"{scenario_id} FP mismatch")
                self.assertEqual(reproduced["FN"], w["FN"], msg=f"{scenario_id} FN mismatch")

    def test_s4_area_mode_reference_scenario_reproduces_exactly(self):
        """Phase 2C item 4: area-mode is now implemented and reproduction-
        tested, not skipped as it was in Phase 2A."""
        workers = self._engine_reference("S4")
        self.assertEqual(workers[0]["mode"], "area")
        reproduced = self._reproduce_area(workers[0])
        self.assertEqual(reproduced["TP"], workers[0]["TP"])
        self.assertEqual(reproduced["FP"], workers[0]["FP"])
        self.assertEqual(reproduced["FN"], workers[0]["FN"])


class TestImmediateAlertReproduction(unittest.TestCase):
    """Phase 2C item 1: specifically regression-tests the immediate-alert
    dose bypass, including at the K values (3, 5) where
    PHASE2B_INTEGRATION_AUDIT.md section 4 found it changes detection
    timing for S8."""

    @classmethod
    def setUpClass(cls):
        cls.bridge = EngineBridge().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    def _engine_s8_reference(self, K: int):
        return self.bridge.evaluate(
            """(K) => {
                SafetyLab.setK(K);
                SafetyLab.run('S8', K);
                const res = SafetyLab.results()['S8'];
                const w = res.workers[0];
                return {
                    TP: w.TP, FP: w.FP, FN: w.FN,
                    episodes: w.episodes, truth: w.revents.map(e => ({start: e.start, end: e.end})),
                    rows: w.rows.map(x => ({t: x.t, recv: x.recv, rate: x.rate})),
                };
            }""",
            K,
        )

    def _reproduce_s8_with_immediate_alert(self, ref, K: int):
        rates = [r["rate"] for r in ref["rows"]]
        result = self.bridge.evaluate(
            """(args) => {
                const { rates, K, truth } = args;
                const pol = { mode: 'dose', doseMsv: AlaradSafety.policy().doseMsv };
                const flagged = [], imm = [];
                for (const r of rates) {
                    if (r === null || !SimLab.pure.validReading(r)) { flagged.push(false); imm.push(false); continue; }
                    const ev = evaluateExposure({room: 'Cath Lab 3', procMult: 1.0, rate: r, dur: 30, dist: 1, refDist: 1, shield: 1, mode: 'personal'});
                    flagged.push(ev.riskClass !== 'low');
                    imm.push(AlaradSafety.immediateAlert({cumulativeDose: ev.cumulativeDose}, pol));
                }
                const be = SimLab.pure.buildEpisodes(flagged, K, imm);
                const mt = SimLab.pure.matchEvents(truth, be.episodes, 2);
                const TP = mt.matches.filter(m => m !== null).length;
                const FN = truth.length - TP;
                const FP = mt.fp.length;
                return { TP, FP, FN, episodes: be.episodes };
            }""",
            {"rates": rates, "K": K, "truth": ref["truth"]},
        )
        return result

    def test_s8_immediate_alert_fires_and_matches_engine_at_k3_and_k5(self):
        for K in (3, 5):
            ref = self._engine_s8_reference(K)
            reproduced = self._reproduce_s8_with_immediate_alert(ref, K)
            self.assertEqual(reproduced["TP"], ref["TP"], msg=f"K={K} TP")
            self.assertEqual(reproduced["FP"], ref["FP"], msg=f"K={K} FP")
            self.assertEqual(reproduced["FN"], ref["FN"], msg=f"K={K} FN")
            # The specific finding this regresses against: the engine's
            # own two episodes at K=3/K=5 both have immediate=True, and
            # detect at each run's own start minute (15, then 40 after
            # the sensor disconnect/resume), not K-1 minutes later.
            # Compared episode-by-episode, not just by TP/FP/FN, since
            # that is a strictly stronger claim.
            self.assertTrue(any(e["immediate"] for e in ref["episodes"]), msg=f"K={K}: fixture assumption failed")
            reproduced_episodes = sorted(
                [{"runStart": e["runStart"], "det": e["det"], "immediate": e["immediate"]}
                 for e in reproduced["episodes"]], key=lambda e: e["runStart"])
            ref_episodes = sorted(
                [{"runStart": e["runStart"], "det": e["det"], "immediate": e["immediate"]}
                 for e in ref["episodes"]], key=lambda e: e["runStart"])
            self.assertEqual(reproduced_episodes, ref_episodes, msg=f"K={K}: episode list mismatch")

    def test_s8_without_immediate_alert_detects_later_at_k3_and_k5(self):
        """Confirms the bypass is actually doing something: with imm
        forced off, detection at K=3/K=5 should be later than minute 15."""
        for K in (3, 5):
            ref = self._engine_s8_reference(K)
            rates = [r["rate"] for r in ref["rows"]]
            result = self.bridge.evaluate(
                """(args) => {
                    const { rates, K, truth } = args;
                    const flagged = rates.map(r => {
                        if (r === null || !SimLab.pure.validReading(r)) return false;
                        const ev = evaluateExposure({room: 'Cath Lab 3', procMult: 1.0, rate: r, dur: 30, dist: 1, refDist: 1, shield: 1, mode: 'personal'});
                        return ev.riskClass !== 'low';
                    });
                    const be = SimLab.pure.buildEpisodes(flagged, K, null);
                    return be.episodes;
                }""",
                {"rates": rates, "K": K, "truth": ref["truth"]},
            )
            self.assertGreater(result[0]["det"], 15, msg=f"K={K}: without the bypass, detection should be later than minute 15")


class TestDataQualityLayerReproduction(unittest.TestCase):
    """Phase 2C item 5: reproduces SafetyLab's own sensor-state sequence,
    dTP/dFP/dFN, and (where applicable) the radiation-layer TP/FP/FN, for
    every one of S7-S13 -- not just S7 as in Phase 2A."""

    @classmethod
    def setUpClass(cls):
        cls.bridge = EngineBridge().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    def _engine_reference(self, scenario_id: str):
        return self.bridge.evaluate(
            """(id) => {
                SafetyLab.run(id, 1);
                const res = SafetyLab.results()[id];
                const w = res.workers[0];
                return {
                    room: w.room,
                    states: w.rows.map(x => x.state),
                    rows: w.rows.map(x => ({t: x.t, recv: x.recv, rate: x.rate})),
                    dTP: w.dTP, dFP: w.dFP, dFN: w.dFN,
                    revents: w.revents.map(e => ({start: e.start, end: e.end})),
                    TP: w.TP, FP: w.FP, FN: w.FN,
                };
            }""",
            scenario_id,
        )

    def _build_observations(self, scenario_id: str, rows):
        lag_info = KNOWN_DELAYED_LAG.get(scenario_id)
        obs = []
        for row in rows:
            t, recv = row["t"], row["recv"]
            if recv == "":
                obs.append(None)
                continue
            value = float("nan") if recv in ("NaN", "null") else float(recv)
            ts = t
            if lag_info and lag_info["start"] + lag_info["lag"] <= t < lag_info["end"]:
                ts = t - lag_info["lag"]
            obs.append({"ts": ts, "value": value})
        return obs

    def test_all_dq_reference_scenarios_reproduce_exactly(self):
        for scenario_id in DQ_SCENARIOS:
            ref = self._engine_reference(scenario_id)
            observations = self._build_observations(scenario_id, ref["rows"])
            steps = run_sensor_state_machine(self.bridge, observations)
            reproduced_states = [s["state"] for s in steps]
            self.assertEqual(reproduced_states, ref["states"], msg=f"{scenario_id} state sequence")

            flagged = [s in DQ_FLAGGED_STATES for s in reproduced_states]
            be = self.bridge.evaluate(
                "(flagged) => SimLab.pure.buildEpisodes(flagged, 1, null)", flagged)
            # SafetyLab's own dqEvents ground truth is used directly --
            # not re-derived from recv/fault fields -- since it is itself
            # the engine's own, real ground truth for this scenario.
            dq_events_raw = self.bridge.evaluate(
                """(id) => SafetyLab.results()[id].workers[0].dqEvents.map(e => ({start: e.start, end: e.end}))""",
                scenario_id,
            )
            mt = self.bridge.evaluate(
                "(args) => SimLab.pure.matchEvents(args.events, args.episodes, 2)",
                {"events": dq_events_raw, "episodes": be["episodes"]},
            )
            TP = sum(1 for m in mt["matches"] if m is not None)
            FN = len(dq_events_raw) - TP
            FP = len(mt["fp"])
            self.assertEqual(TP, ref["dTP"], msg=f"{scenario_id} dTP")
            self.assertEqual(FP, ref["dFP"], msg=f"{scenario_id} dFP")
            self.assertEqual(FN, ref["dFN"], msg=f"{scenario_id} dFN")

    def test_radiation_layer_on_dq_scenarios_reproduces_exactly(self):
        """Scenarios S8, S9, S12, S13 also carry a radiation ground truth
        -- this confirms the SAME candidate call sequence used for S1-S6
        reproduces the engine's own TP/FP/FN on these too, independent of
        the DQ-layer check above."""
        for scenario_id in sorted(DQ_SCENARIOS_WITH_RADIATION_EVENTS):
            ref = self._engine_reference(scenario_id)
            rates = [r["rate"] for r in ref["rows"]]
            flagged = self.bridge.evaluate(
                """(args) => args.rates.map(r => {
                    if (r === null || !SimLab.pure.validReading(r)) return false;
                    const ev = evaluateExposure({room: args.room, procMult: 1.0, rate: r, dur: 30, dist: 1, refDist: 1, shield: 1, mode: 'personal'});
                    return ev.riskClass !== 'low';
                })""",
                {"rates": rates, "room": ref["room"]},
            )
            be = self.bridge.evaluate(
                "(flagged) => SimLab.pure.buildEpisodes(flagged, 1, null)", flagged)
            mt = self.bridge.evaluate(
                "(args) => SimLab.pure.matchEvents(args.events, args.episodes, 2)",
                {"events": ref["revents"], "episodes": be["episodes"]},
            )
            TP = sum(1 for m in mt["matches"] if m is not None)
            FN = len(ref["revents"]) - TP
            FP = len(mt["fp"])
            self.assertEqual(TP, ref["TP"], msg=f"{scenario_id} radiation TP")
            self.assertEqual(FP, ref["FP"], msg=f"{scenario_id} radiation FP")
            self.assertEqual(FN, ref["FN"], msg=f"{scenario_id} radiation FN")


if __name__ == "__main__":
    unittest.main()
