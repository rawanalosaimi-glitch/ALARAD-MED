"""
Task 8: confirms the adapter's own call sequence reproduces the frozen
engine's OWN built-in output on reference scenarios, rather than merely
asserting individual functions are callable. For each scenario tested,
the exact per-minute rates (or raw observations) the engine itself
generated are extracted, fed independently through this adapter's own
call sequence, and the result is diffed against the engine's own
SimLab.run() / SafetyLab.run() output. A mismatch here would mean this
adapter does NOT faithfully reproduce the real detector, and per the
Phase 2A restrictions, that must be reported, not papered over -- these
tests are the mechanism for catching that.
"""

from __future__ import annotations

import unittest

from phase2a_adapter.dq_adapter import DQ_FLAGGED_STATES, run_sensor_state_machine
from phase2a_adapter.engine_bridge import EngineBridge

RADIATION_REFERENCE_SCENARIOS = ["S1", "S2", "S3", "S4", "S5", "S6"]


class TestRadiationLayerReproduction(unittest.TestCase):
    """Reproduces SimLab's own S1-S6 (the engine's built-in reference
    scenarios) using only this adapter's own evaluateExposure ->
    buildEpisodes -> matchEvents -> metrics call sequence, fed the exact
    noiseless rates the engine itself generated for that scenario."""

    @classmethod
    def setUpClass(cls):
        cls.bridge = EngineBridge().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    def _engine_reference(self, scenario_id: str):
        return self.bridge.evaluate(
            """(id) => {
                const r = SimLab.run(id, 1, 0);
                return r.workers.map(w => ({
                    room: w.room, mode: w.mode,
                    truth: w.events.map(e => ({start: e.start, end: e.end})),
                    TP: w.TP, FP: w.FP, FN: w.FN,
                    rates: w.rows.map(x => x.valid ? x.engineRate : null),
                    procMult: 1.0,
                }));
            }""",
            scenario_id,
        )

    def _reproduce_with_adapter_calls(self, worker):
        if worker["mode"] != "personal":
            return None  # area-mode is out of scope (see PHASE2A_LIMITATIONS.md)
        flagged = self.bridge.evaluate(
            """(args) => args.rates.map(r => {
                if (r === null || !SimLab.pure.validReading(r)) return false;
                const ev = evaluateExposure({room: args.room, procMult: args.procMult, rate: r, dur: 30, dist: 1, refDist: 1, shield: 1, mode: 'personal'});
                return ev.riskClass !== 'low';
            })""",
            worker,
        )
        be = self.bridge.evaluate(
            "(flagged) => SimLab.pure.buildEpisodes(flagged, 1, null)", flagged)
        mt = self.bridge.evaluate(
            "(args) => SimLab.pure.matchEvents(args.events, args.episodes, 2)",
            {"events": worker["truth"], "episodes": be["episodes"]},
        )
        TP = sum(1 for m in mt["matches"] if m is not None)
        FN = len(worker["truth"]) - TP
        FP = len(mt["fp"])
        return {"TP": TP, "FP": FP, "FN": FN}

    def test_all_six_radiation_reference_scenarios_reproduce_exactly(self):
        for scenario_id in RADIATION_REFERENCE_SCENARIOS:
            workers = self._engine_reference(scenario_id)
            for w in workers:
                reproduced = self._reproduce_with_adapter_calls(w)
                if reproduced is None:
                    continue  # area-mode worker (S4) -- documented limitation
                self.assertEqual(
                    reproduced["TP"], w["TP"],
                    msg=f"{scenario_id} TP mismatch: {reproduced} vs engine {w}")
                self.assertEqual(reproduced["FP"], w["FP"], msg=f"{scenario_id} FP mismatch")
                self.assertEqual(reproduced["FN"], w["FN"], msg=f"{scenario_id} FN mismatch")

    def test_s4_area_mode_is_explicitly_not_reproduced(self):
        # Documents, via a passing test, that S4 (the one area-mode
        # reference scenario) is knowingly skipped by the reproduction
        # check above -- not silently ignored.
        workers = self._engine_reference("S4")
        self.assertEqual(workers[0]["mode"], "area")
        self.assertIsNone(self._reproduce_with_adapter_calls(workers[0]))


class TestDataQualityLayerReproduction(unittest.TestCase):
    """Reproduces SafetyLab's own S7 sensor-state sequence and dTP/dFP/dFN
    using only this adapter's own sensorStep -> buildEpisodes ->
    matchEvents -> metrics call sequence, fed the exact raw observations
    (including the missing-fault gaps) SafetyLab itself generated."""

    @classmethod
    def setUpClass(cls):
        cls.bridge = EngineBridge().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.bridge.__exit__(None, None, None)

    def test_s7_sensor_state_sequence_and_dq_metrics_reproduce_exactly(self):
        ref = self.bridge.evaluate(
            """() => {
                SafetyLab.run('S7', 1);
                const res = SafetyLab.results()['S7'];
                const w = res.workers[0];
                return {
                    states: w.rows.map(x => x.state),
                    rows: w.rows.map(x => ({t: x.t, recv: x.recv})),
                    dqEvents: w.dqEvents, dTP: w.dTP, dFP: w.dFP, dFN: w.dFN,
                };
            }"""
        )
        observations = []
        for row in ref["rows"]:
            if row["recv"] == "":
                observations.append(None)
            else:
                observations.append({"ts": row["t"], "value": float(row["recv"])})

        steps = run_sensor_state_machine(self.bridge, observations)
        reproduced_states = [s["state"] for s in steps]
        self.assertEqual(reproduced_states, ref["states"])

        flagged = [s in DQ_FLAGGED_STATES for s in reproduced_states]
        be = self.bridge.evaluate(
            "(flagged) => SimLab.pure.buildEpisodes(flagged, 1, null)", flagged)
        # S7's own fault window is recoverable from where 'recv' is empty.
        fault_minutes = [row["t"] for row in ref["rows"] if row["recv"] == ""]
        fault_window = [{"start": min(fault_minutes), "end": max(fault_minutes) + 1}] if fault_minutes else []
        mt = self.bridge.evaluate(
            "(args) => SimLab.pure.matchEvents(args.events, args.episodes, 2)",
            {"events": fault_window, "episodes": be["episodes"]},
        )
        TP = sum(1 for m in mt["matches"] if m is not None)
        FN = len(fault_window) - TP
        FP = len(mt["fp"])
        self.assertEqual(TP, ref["dTP"])
        self.assertEqual(FP, ref["dFP"])
        self.assertEqual(FN, ref["dFN"])


if __name__ == "__main__":
    unittest.main()
