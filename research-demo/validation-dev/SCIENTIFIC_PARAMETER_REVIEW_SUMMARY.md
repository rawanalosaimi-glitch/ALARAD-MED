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

**Start here — four items, newly surfaced, most load-bearing:**

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

**Fourteen more items** (procedure-class baselines, event/fault timing
ranges, two comparison-alarm setpoints, a noise model, an area-monitor
geometry approximation, and four not-yet-built forecasting/rotation
parameters) are listed in full, with exact values, in the main package.

**What is already blocked, independent of your review:** forecasting and
worker-rotation features do not exist yet and are out of scope regardless.
No large-scale statistical evaluation has been run or will be run before
this review is further along.

**What your review unblocks:** the project's planned statistical
evaluation campaign (many simulated seeds, compared against the real
detection software) is ready in software terms — verified, in this
project's own testing, to faithfully reproduce the real engine's
behavior — but is withheld from being treated as a *scientific* result
until the numbers above have your input. Nothing is lost by reviewing in
stages; each approved row lets that specific number be cited with
confidence in later reporting.

**One citation already exists in the software**, unverified by this
project: ICRP Publication 103's 20 mSv/year (5-year-averaged) dose limit,
used only as a dashboard reference line, and a reference to Saudi NRRC
requirements the software itself says to check against the current
official text. No other parameter has any citation. If you know of
applicable manufacturer, regulatory, or published literature for any item
above, that is exactly what this review is for.
