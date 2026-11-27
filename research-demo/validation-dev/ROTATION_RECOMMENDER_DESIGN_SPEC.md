# Worker-Rotation Recommender — Design Specification

**Status: specification only. No algorithm has been designed in enough
detail to implement, no code has been written, and nothing here has been
run.** This document exists to be reviewed before any implementation
work starts, per this round's explicit restriction ("do not implement
the rotation algorithm yet"). It extends
`ICAIRE_Simulation_Validation_Methodology.md` §6 (Track B — specification
only) with the additional design detail requested this round: worker
eligibility, procedure continuity, handoff safety, workload fairness, and
dose-related objectives, stated together with rotation baselines,
evaluation metrics, and ground-truth assumptions, in one place a reviewer
can assess without reading `ICAIRE_Simulation_Validation_Methodology.md`
§6 first (though that section's constraints are reused here verbatim
where they already exist, not restated differently).

**No rotation-recommendation algorithm exists in the frozen v1.2.3
release** (`ICAIRE_Simulation_Validation_Methodology.md` §0 — the four
"AI Recommendation" entries are static, hand-written example text, not
engine output) **and none is implemented by this document.**

**Update (Phase 3B, companion document — non-substantive pointer only,
nothing above this note has been changed):** following provisional
review of this document, the candidate algorithm, synthetic staffing
model, counterfactual-simulation method, and expanded evaluation design
this document deferred to "future work" (§7, §8's open items) have since
been specified in
`PHASE3B_ROTATION_ALGORITHM_DESIGN.md`. That document is a companion to
this one, not a replacement — it reuses every constraint, objective, and
baseline definition here verbatim (§2–§4 above) rather than restating
them differently, and adds the detail needed for independent
implementation. This document's own content, below this note, is
otherwise unchanged from its original Phase 3A-follow-up version.

---

## 0. The central caveat this entire document is written around

**A simulated reduction in dose does not, by itself, demonstrate
real-world effectiveness.** This is stated once, prominently, because it
governs every section below, not because it is a new idea separate from
the rest of this project's "illustrative, not validated" discipline
(`ICAIRE_Simulation_Validation_Methodology.md` §9's note on what
approval does and does not mean). Specifically:

- A rotation recommender that reduces simulated cumulative dose in
  Phase 1's synthetic scenarios is, at most, evidence that the
  *algorithm correctly executes the logic it was designed to execute*
  against *this project's own illustrative noise model, event model, and
  baselines* (registry rows 1, 3, 4, 11, 12 — all unverified against
  reality).
- It is **not** evidence that real workers, following a real rotation
  recommendation, would receive less real dose — that would require real
  staffing constraints, real procedure-continuity costs, real human
  compliance with the recommendation, and real dosimetry, none of which
  this simulation models.
- Any future report of a simulated dose reduction **must** state this
  distinction explicitly, in the same place the result is reported, not
  only in a methods section a reader might skip.

---

## 1. What decision is being specified

A rotation recommender is a function that, at some point during a
simulated (eventually, real) shift, outputs one of: *no change*, or *move
worker W out of room/procedure R, replaced by worker W′, no earlier than
time T*. This document specifies the constraints such an output must
satisfy to be **valid** (§2), the objectives it should be scored against
once valid (§3), the baselines any candidate must be compared to (§4),
the metrics used for that comparison (§5), and the ground-truth
assumptions those metrics rest on (§6) — all of this independent of, and
prior to, choosing any particular algorithm (§7 explains why no
algorithm is chosen here).

---

## 2. Hard validity constraints (reused from §6b, not restated differently)

These are **unchanged** from
`ICAIRE_Simulation_Validation_Methodology.md` §6b — repeated here only so
this document is self-contained, not because they have been revised. A
candidate recommendation that violates any of these is **invalid**,
regardless of how well it would score on §3:

1. **Worker eligibility.** The proposed replacement worker must be (a)
   credentialed for the target room/procedure type, (b) not already at or
   near their own projected dose or duty-time limit, and (c) not
   currently the subject of an open, unresolved data-quality incident of
   their own. **No real or synthetic credentialing/staffing dataset
   currently exists anywhere in this project** (registry row 8) — this
   constraint cannot be *exercised* in simulation until such a model is
   built, and is not assumed available by anything in this document.
2. **Procedure continuity.** A rotation must not be recommended while the
   affected worker is mid-procedure; it may only take effect at a
   declared procedure boundary, or an explicit emergency-override flag
   itself subject to RSO review.
3. **Handoff safety.** A minimum handoff/briefing duration (registry row
   9, not yet chosen) must elapse between a recommendation and the swap
   taking effect; a rotation is never instantaneous, and none may be
   recommended during an open radiation-incident window without explicit
   RSO acknowledgement (reusing the S8 "incident stays open through
   disconnect, never silently auto-closed" precedent).
4. **Workload fairness, measured across time, not only at the end.**
   Fairness must be evaluated both at end-of-shift (dose variance across
   the roster) and as a trajectory-level measure sampled at multiple
   points across the shift, plus fairness of the rotation burden itself
   (no worker rotated disproportionately more often than peers).

## 3. Objectives a valid candidate is scored against (reused from §6c)

Also unchanged from §6c, listed here for completeness:

1. Reduction in simulated cumulative dose at end of shift vs. no
   rotation.
2. Fairness — end-of-shift dose variance, plus the trajectory-level and
   rotation-burden measures from §2.4.
3. Time-to-recommendation latency.
4. Number of rotations recommended per shift (a cost, not free).
5. Constraint-violation rate — the fraction of a candidate's outputs
   that fail any §2 constraint; reported alongside the other four, not
   as a separate pass/fail gate elsewhere.

Scoring **weights** across these five criteria are registry row 10, not
chosen here — this document specifies what is measured, not how the
measurements are combined into a single ranking.

---

## 4. Rotation baselines (what any candidate recommender must be compared to)

A candidate recommender's scores (§3) are only interpretable relative to
simple reference policies — without these, "dose went down" has no
frame of reference for how much of that reduction a smarter algorithm
actually bought. Three baselines, deliberately simple and
non-learning, mirroring the detection/forecasting evaluation's own
practice of comparing against simple references first
(`ICAIRE_Simulation_Validation_Methodology.md` §4a/§4b):

1. **No-rotation baseline.** No rotation is ever recommended. Establishes
   the dose/fairness outcome if the roster simply runs the shift as
   assigned — the floor every candidate must beat to be worth deploying
   at all.
2. **Fixed-interval baseline.** Rotate whichever eligible worker has
   accumulated the highest dose-so-far, at a fixed wall-clock interval
   (e.g. every N minutes; N is an open parameter, not chosen here,
   analogous in kind to registry rows 2/9). Represents "simple
   round-robin-by-dose" — a policy a facility could already follow
   without any AI, so this is the bar an automated recommender's added
   complexity has to justify.
3. **Reference-rule baseline (§6a, reused).** The fixed, non-learning
   policy already specified in the methodology: rotate a worker out when
   projected cumulative dose crosses a declared fraction of the reference
   level — mechanizing the logic already present as prose in v1.2.3's two
   hand-written recommendation strings (lines 1541–1542). This is the
   closest baseline to "what the existing illustrative UI text already
   implies," and the most direct test of whether a more complex candidate
   earns its complexity over just automating that existing text.

None of these three baselines is a learned model; none requires training
data; all three can be specified in full now, independent of whatever
candidate algorithm is eventually proposed (§7).

---

## 5. Evaluation metrics

Beyond the five scoring criteria already fixed in §3, a campaign
evaluating any candidate recommender against the §4 baselines needs:

- **Paired comparison across the three §4 baselines and any candidate**,
  on the *same* simulated seeds — reusing
  `ICAIRE_Simulation_Validation_Methodology.md` §7's existing paired-design
  and multiple-comparison-correction rules (Wilcoxon signed-rank,
  Holm–Bonferroni across the family of comparisons), rather than
  inventing a separate statistical convention for rotation specifically.
- **Run-level unit of independence** (§7a, reused): one shift/seed is one
  observation; per-worker or per-rotation-event numbers within a run are
  correlated by construction and must be aggregated to one value per run
  before any cross-seed statistic is computed — pooling raw per-event
  records directly would be the same pseudo-replication error already
  flagged for detection/forecasting.
- **Constraint-violation rate reported as its own number**, never folded
  silently into the dose-reduction figure — a recommender that achieves
  dose reduction partly by proposing invalid (§2-violating) rotations
  that would be rejected in practice is not actually achieving that
  reduction.
- **Sensitivity to the fixed-interval baseline's own parameter** (§4.2's
  `N`) should be reported, not just a single chosen `N` — otherwise the
  baseline's own strength is itself an unexamined constant, the same
  category of gap flagged for the exponential-smoothing baseline's
  `alpha` (registry row 20).

---

## 6. Ground-truth assumptions — stated explicitly, not left implicit

There is no "ground truth" for worker rotation in the sense detection and
forecasting have one (a known true event, a known true future value).
Rotation has no analogous observable fact to check a recommendation
against — only a simulated *counterfactual* (what dose would have
accrued under a different rotation choice), which is a property of the
simulator's own model, not an observation of reality. Stated precisely,
so this is not later mistaken for a validation claim:

1. **The only "ground truth" available is simulated counterfactual dose**
   — computed by re-running (or analytically recomputing) the same
   seeded scenario under a different rotation schedule, using Phase 1's
   own illustrative noise and event models (registry rows 1, 3, 4, 11,
   12). This measures *internal consistency of the simulation*, not
   agreement with any real-world outcome.
2. **"Correct" rotation timing is not independently defined anywhere in
   this project.** Unlike a detection true/false positive (defined
   against the simulator's own injected `truth` arrays) or a forecast
   error (defined against the simulator's own known future value), there
   is no equivalent authored "this rotation would have been correct"
   label for any scenario. Any metric computed in §5 is therefore a
   comparison of *outcomes* (dose, fairness, violation rate) across
   policies, never a comparison of a candidate's output against a
   labeled correct answer.
3. **Real compliance is not modeled at all.** Every simulated outcome in
   §4–§5 assumes a recommendation is followed exactly, at exactly the
   handoff timing specified — no model exists for whether a real RSO or
   roster would actually follow a given recommendation, delay it,
   override it, or ignore it. This is a separate, unaddressed gap from
   the §2 handoff-safety *constraint* (which governs what a valid
   recommendation may say), not a statement about whether it would be
   obeyed.
4. **Eligibility is assumed exercisable only once a staffing/credentialing
   model exists** (registry row 8) — until then, §2.1's eligibility
   constraint can be specified but not evaluated against any concrete
   roster; any smoke test run before that model exists would necessarily
   use a placeholder eligibility model of its own, which would itself
   need registering as a new provisional parameter, not silently assumed.
5. **Consistent with §0 above:** nothing in this section should be read
   as proposing that simulated counterfactual dose *can* stand in for
   real-world effectiveness once enough seeds are run — more seeds would
   make the simulated-counterfactual comparison more statistically
   reliable *as a statement about the simulation*, not more valid as a
   statement about reality. Closing that second gap would require real
   dosimetry data and a real-world trial design, neither of which is in
   scope for this project.

---

## 7. Why no candidate algorithm is proposed here

Per this round's explicit restriction, no rotation algorithm is designed
in implementable detail in this document. What has been specified
instead — validity constraints (§2), objectives (§3), baselines (§4),
metrics (§5), and ground-truth assumptions (§6) — is deliberately
algorithm-independent: any future candidate (a hand-tuned rule beyond
§4.3's reference rule, a scored multi-criteria ranking over §3's five
objectives, or a learned model) would be specified, baselined, and
evaluated through the same structure above. Choosing among those
families, and fixing registry row 10's scoring weights, is future work
this document does not do.

---

## 8. Relationship to existing documents

- Reuses, rather than restates differently: §6b/§6c of
  `ICAIRE_Simulation_Validation_Methodology.md` (§2–§3 above), §7/§7a's
  statistical design (§5 above).
- Registry rows this document depends on, all still open: row 8 (worker
  eligibility/credentialing model — does not exist), row 9 (handoff
  duration — not chosen), row 10 (scoring weights — not chosen), and now
  also row 20 (exponential-smoothing `alpha`, cited in §5 only by analogy
  to the fixed-interval baseline's own unexamined-constant risk).
- `UNRESOLVED_SCIENTIFIC_DECISIONS.md` items 1–2 (rescaling coherence,
  immediate-alert bypass) are upstream of rotation in the sense that any
  future rotation evaluation would run on top of whichever detection/dose
  pipeline those items eventually resolve into — not themselves rotation
  questions, but noted so this document is not read as independent of
  them.

---

## 9. What this document does and does not do

- **Does:** specify validity constraints, scoring objectives, comparison
  baselines, evaluation metrics, and ground-truth assumptions for a
  future worker-rotation recommender, in enough detail for expert review,
  without implementing anything; state explicitly, in §0 and §6, that a
  simulated dose reduction is not evidence of real-world effectiveness.
- **Does not:** implement any rotation algorithm (not even the §4
  baselines, as runnable code); run any simulation; choose registry rows
  8/9/10's open parameter values; claim any dose-reduction result,
  simulated or otherwise; claim clinical validity or regulatory
  compliance anywhere.
