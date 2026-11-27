# Phase 3C-A — Dose-Threshold Semantic Audit (performed before any code was written)

**Purpose, stated once:** before implementing anything, this round's
instructions required a read-only audit of the frozen v1.2.3
`doseElevated`/`doseCritical` definitions, their input units and
semantics, with an explicit instruction not to assume they are
projected-cumulative-dose thresholds, and not to implement an unverified
trigger formula. This document records exactly what was found, by
reading the frozen source directly (not by re-reading prior project
documentation), with line citations. **No code was written before this
audit was complete**, and this finding directly shaped what Phase 3C-A
does and does not implement (see §4).

The frozen release
(`research-demo/releases/html/ALARAD_Prototype_Research_Demo_v1.2.3.html`,
SHA-256 `92e897dd0ff1738f083df829b53f7f46377e042b7019bb9776232792261182ee`)
was opened only for reading throughout this audit, and remains unchanged
(re-verified after this audit and again after implementation).

---

## 1. What was found, exactly (frozen release, read directly)

**`CONFIG` (line 1501-1506):**
```js
const CONFIG = { // PROTOTYPE warning thresholds — configurable placeholders, NOT regulatory limits
  devElevated:0.5, devCritical:1.5,      // relative deviation of worker-position rate vs baseline
  doseElevated:0.15, doseCritical:0.35,  // projected task dose, mSv
  refAnnual:20,                          // visual reference level, mSv/yr
  warnFracElevated:0.5, warnFracCritical:0.9
};
```

**`evaluateExposure()` (line 1950-1991), the ONLY place `doseElevated`/
`doseCritical` are compared against anything:**
```js
function evaluateExposure({room, procMult, rate, dur, dist, refDist, shield, mode}){
  ...
  const baseline = (baselineRates[room]||60)*procMult;
  let workerRate, correction;
  if(mode==='area'){ workerRate = rate * Math.pow(refDist/dist, 2) * shield; ... }
  else { workerRate = rate; ... }
  const cumulativeDose = (workerRate * (dur/60)) / 1000;      // uSv/h x h = uSv ; /1000 = mSv
  const deviation = (workerRate - baseline) / baseline;
  let riskClass, riskLabel;
  if(deviation < CONFIG.devElevated && cumulativeDose < CONFIG.doseElevated){ riskClass='low'; ... }
  else if(deviation < CONFIG.devCritical && cumulativeDose < CONFIG.doseCritical){ riskClass='med'; ... }
  else { riskClass='high'; ... }
  ...
}
```

**Call sites that supply `dur` (every real, per-minute usage):**
- `SimLab.runWorker` (line 2947, 2951): `dur:HORIZON_MIN`, where
  `HORIZON_MIN=30` (line 2809's constant block).
- The detection adapter's own call site (line 3426): `dur:HORIZON`,
  where `HORIZON=30` (line 3368's constant block).
- `rate`/`input` at every one of these call sites is **a single
  per-minute reading** — the same value fed into `validReading` that
  minute, never a trailing average, never an accrued total.

**The UI's own label for this value (line 1985-1986, 2034), confirming
the finding below is not a misreading of obscure code:**
> "Projected task dose (assumes constant rate)" ... "Projected dose for
> a `${dur}`-minute task at this constant rate ... (current rate held
> constant; not a trend forecast)"

**For completeness, the dashboard's separate, unrelated dose concept
(line 1508-1517), confirmed NOT connected to `doseElevated`/
`doseCritical` at all:**
```js
function classifyDoseStatus(todayMsv, yearMsv, yearRef=CONFIG.refAnnual){
  const ratio = yearMsv / yearRef;
  if(ratio >= CONFIG.warnFracCritical) return 'critical';
  if(ratio >= CONFIG.warnFracElevated) return 'elevated';
  return 'normal';
}
```
This is the dashboard's Today/Year badge — a **different** accumulated-
dose idea, compared against `refAnnual`/`warnFracElevated`/
`warnFracCritical`, never against `doseElevated`/`doseCritical`. Grepped
for every use of `doseElevated`/`doseCritical` across the whole file
(lines 1366-1372, 1501-1510, 1703, 1970-1991, 2063-2076, 2999, 3019-3047,
3168-3176, 3270, 3292-3326, 3379, 3490, 3541-3588) — none of those other
call sites adds any previously-accrued dose into the comparison either;
they all read or redisplay the same single `evaluateExposure()`-computed
`cumulativeDose` value.

## 2. The verified fact, stated precisely

**`CONFIG.doseElevated`/`doseCritical` are compared against a value
named `cumulativeDose` that is, despite its name, NOT a running or
accumulated total.** It is a **fresh, memoryless, single-reading
projection**, recomputed independently at every call:

```
cumulativeDose = current_single_minute_rate (uSv/h) x (dur / 60) / 1000   [mSv]
```

with `dur` fixed at 30 minutes at every real call site. There is **no
addition of any previously-accrued dose anywhere in this computation**.
The variable name is a misnomer in the frozen engine's own source — not
something this project may "fix," since the release is frozen — but it
must not be read as implying the thresholds compare against an
accumulating total.

## 3. The mismatch this audit was specifically looking for

`PHASE3B_ROTATION_ALGORITHM_DESIGN.md` section 3a (Revision 2, written
*before* this audit) defines two quantities and asserts the engine
compares the combined one against these thresholds:

> "Projected cumulative dose `D_cum_proj(W, t)`: W's already-accrued
> cumulative dose through t (the existing, unprojected running total,
> §1) **plus** `ΔD_proj(W, t)`. This is the quantity actually compared
> against the engine's own `CONFIG.doseElevated`/`doseCritical`
> thresholds (rows 14/15) — those thresholds are themselves defined in
> the registry as projected-dose-over-a-horizon thresholds ... i.e.
> they are projected-*cumulative*, not increment-only, thresholds."

**This is incorrect, per §2 above.** The engine's actual comparison uses
*only* the single-reading projected increment (what PHASE3B calls
`ΔD_proj` alone) — there is no accrued-so-far component added anywhere.
What PHASE3B's section 3a calls "projected cumulative dose" (accrued +
increment) does not exist under that name, or under `doseElevated`/
`doseCritical`, anywhere in the frozen engine. The audit therefore
**confirms a real, verified mismatch** between the design document and
the actual source, exactly as this round anticipated might be found.

## 4. What this means for Phase 3C-A, and what remains for Phase 3C-B

- **Phase 3C-A implements no dose-trigger formula at all** — CGDTR and
  the five-policy comparison are explicitly out of scope this round
  regardless of this finding, so nothing had to be "fixed" in code; the
  finding is reported, not patched around.
- **`escalation.py` (task 5) was deliberately designed never to depend
  on `doseElevated`/`doseCritical`, `cumulativeDose`, or any dose value
  at all** — it escalates purely on sensor-fault *state* persistence
  (reusing the real engine's own `sensorStep`). This was already the
  instruction ("independently from dose-trigger logic"), and this
  audit's finding is an additional, independent reason that decoupling
  was the right call: escalation does not inherit an unverified
  assumption it never depended on.
- **`dose_attribution.py`'s own dose bookkeeping (task 2) does not use,
  or need, `CONFIG.doseElevated`/`doseCritical` at all** — it only sums
  the existing, unambiguous `Dose (mSv) = Rate (uSv/h) x Duration (h) /
  1000` increment rule (`phase1_simulator.units.dose_increment_mSv`,
  reused unchanged) over real per-minute attributed rates. "Individual
  cumulative dose" and "collective dose" in this implementation are
  genuine running sums, built independently of the engine's
  misleadingly-named `cumulativeDose` — the two must not be confused
  with each other, and this document is the place that states the
  distinction explicitly.
- **Blocker for Phase 3C-B:** before any CGDTR trigger formula is
  implemented, `PHASE3B_ROTATION_ALGORITHM_DESIGN.md` section 3a needs a
  Revision 3 correcting this finding — the trigger's
  "projected-cumulative-dose" clause as currently written compares a
  quantity the real engine does not compute. The corrected design would
  compare the engine's real `cumulativeDose` (the single-reading
  projection alone) against `doseElevated`/`doseCritical`, and separately
  decide, as an explicit design question for RSO/Medical-Physicist
  review, whether a *genuinely* accrued-plus-projected quantity should
  be introduced as a **new**, adapter-only calculation (analogous to
  Phase 3A's `forecast_cumulative_dose`, which is also explicitly new,
  adapter-only logic, never claimed as an existing engine capability) —
  not quietly assumed to be what the existing thresholds already do.
  This correction is **not made in this round**, since this round's
  instructions are implementation-only for Phase 3C-A infrastructure,
  not a further documentation revision of Phase 3B; it is reported here
  as the explicit blocker it is.

## 5. What this audit does not claim

- Does not claim the engine's `cumulativeDose` naming is a *bug* to be
  fixed — the frozen release is not modified, and no claim is made about
  whether the engine's own design is appropriate; only that its actual
  behavior has now been verified directly, not assumed.
- Does not claim this finding affects any previously-reported Phase 2A/
  2C/3A result — those phases' own dose/threshold usage was independently
  verified at the time (see `PHASE2B_INTEGRATION_AUDIT.md`,
  `PHASE2C_CORRECTIVE_IMPLEMENTATION.md`) and is not reopened here.
- Does not claim a resolution to the Phase 3C-B blocker in §4 — only that
  it is now precisely stated, with exact evidence, instead of being
  discovered mid-implementation of a trigger formula that would have
  been built on the wrong assumption.
