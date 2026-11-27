# Reviewer Summary — One Page

**What this is:** a research prototype (ALARAD, a radiation-safety
monitoring concept) and a simulation/testing framework built around it
(this project). Every numeric threshold either uses is currently a
placeholder — chosen to make the software runnable, with no clinical or
regulatory evidence behind it. This summary asks you, as a qualified
Medical Physicist or Radiation Safety Officer, to review those
placeholders before any scientific claim is made from them.

**What you are being asked to do:** read the full
`SCIENTIFIC_PARAMETER_REVIEW_PACKAGE.md` (no code reading required), and
for each parameter mark **Approved / Revise / Not Approved** with a
comment, in its review table. You do not need to approve everything at
once — partial review is useful.

**What "Approved" means, and does not mean:** it means *"a reasonable
choice for this synthetic simulation study."* It does **not** mean the
value is representative of real occupational radiation exposure, and
your approval of these provisional values — however thorough — does not
by itself establish external validity or regulatory compliance with
ICRP, NRRC, or any other authority. Those would need their own,
separately-scoped review.

**Start here — six items, newly surfaced, most load-bearing:**

1. **Room baseline dose rates** (35–92 µSv/h across 7 rooms) — the number
   every detection calculation is anchored to. Self-labeled by the
   software's own authors as "illustrative... not derived from real
   data."
2. **Alert thresholds** — elevated at +50% deviation or 0.15 mSv
   projected over 30 minutes; critical at +150% or 0.35 mSv. Self-labeled
   "PROTOTYPE... NOT regulatory limits."
3. **A rescaling step** this project's own adapter performs to test the
   software: it takes a simulated "procedure type" pattern and
   mathematically re-anchors it onto one of the room baselines above.
   The question for you is conceptual, not numeric: does that make
   sense, or should the simulator work in rooms from the start?
4. **An immediate-alert bypass**, on by default in the software, that
   lets a high projected dose (0.35 mSv, same figure as #2) skip the
   normal multi-minute confirmation and alert right away. Is that the
   right behavior, and is 0.35 mSv the right trigger for it?
5. **Sensor-health timing** — the rules deciding when a wearable
   sensor's link counts as "stale" (2 minutes), "disconnected" (5
   minutes), or "stuck/frozen" (6 identical readings). Are these
   realistic for a real wearable dosimeter?
6. **A forecasting-baseline smoothing parameter** (`alpha=0.5`), new in
   this round: a simple exponential-smoothing baseline built to give the
   software's own `linearForecast` function a second point of
   comparison. `alpha=0.5` is an illustrative round number, not fit to
   any data. At smoke scale (8 seeds) this baseline scored *better* than
   `linearForecast` itself — see the note below before reading that as a
   finding about either method.
7. **Four new rotation-infrastructure parameters** (rows 21–24), new
   this round: a synthetic staffing-roster model, per-worker duty
   limits (a dose-per-shift ceiling, rest time, and a rotation-count
   cap), synthetic procedure-boundary spacing, and a sensor-fault
   escalation threshold. All four are illustrative round numbers built
   only to make a not-yet-decision-making rotation-simulation
   infrastructure testable — **none is approved for any clinical or
   operational use**, and the duty-limit dose ceiling in particular
   must not be confused with item #2's radiation alert thresholds: they
   are different quantities, owned by different parts of this project,
   compared for different reasons (see the note below on the trigger
   correction).

**Fourteen more items** (procedure-class baselines, shift lengths,
event/fault timing ranges, two comparison-alarm setpoints, a noise
model, an area-monitor geometry approximation, the Chromium version gap,
scenario-dynamics realism, and four forecast-horizon/rotation items that
remain either unbuilt or only partly tested in code) are listed in full,
with exact values, in the main package.

**What is already blocked, independent of your review:** no *new*
forecasting model and no rotation algorithm have been built, and both
remain out of scope regardless of this review. The software's existing
`linearForecast` function already runs operationally for early-warning
triggering, and has now been evaluated at **smoke scale only** (8 seeds)
against ground truth: it scored *negative* skill versus simply repeating
the last reading at every horizon, while the new exponential-smoothing
baseline (#6 above) scored positively. **This is a preliminary result
from 8 specific seeds, not a statistically established finding** — it is
not yet the balanced, large-sample campaign that would be needed to say
anything general about either method's real accuracy, and that full
campaign is not part of this review either. Separately, the real
function is hard-limited to forecasting exactly 3 minutes ahead (1/2/3
minutes) — a longer horizon is not a parameter to adjust but an
unbuilt, not-yet-designed capability. No large-scale statistical
evaluation has been run or will be run before this review is further
along.

**On the trigger correction, stated once so it is not missed:** a
design document for a future rotation-recommendation trigger had
assumed the software's own alert thresholds (item #2) compare against
"dose accrued so far this shift, plus a projection" — a closer read of
the actual code found this is **not** what the software does: it
compares only a fresh, single-reading 30-minute projection, with no
memory of dose accrued earlier in the shift at all. This has been
corrected in the design document (`PHASE3B_ROTATION_ALGORITHM_DESIGN.md`,
Revision 3) before any trigger was built — **no rotation-triggering
code exists yet**, so nothing built on the wrong assumption; the
correction was caught at the design stage, which is the reason this
summary mentions it at all.

**What your review unblocks:** the project's planned statistical
evaluation campaign (many simulated seeds, compared against the real
detection software) is ready in software terms — verified, in this
project's own testing, to faithfully reproduce the real engine's
behavior — but is withheld from being treated as a *scientific* result
until the numbers above have your input. Nothing is lost by reviewing in
stages; each approved row lets that specific number be cited with
confidence in later reporting.

**One citation already exists in the software**, and both it and a
second reference remain **explicitly unverified by this project until
checked against the current official text** — nothing here should be
read as vouching for either: ICRP Publication 103's 20 mSv/year
(5-year-averaged) dose limit, used only as a dashboard reference line,
and a reference to Saudi NRRC requirements the software itself says to
check against the current official text. No other parameter has any
citation, and none has been invented for this review. If you know of
applicable manufacturer, regulatory, or published literature for any item
above, that is exactly what this review is for.
