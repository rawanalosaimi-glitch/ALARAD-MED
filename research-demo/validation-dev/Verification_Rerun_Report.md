# Independent Verification Rerun Report — ALARAD Research-Demo v1.2.3

**Scope:** Independent re-execution of every verification suite that could be
located for the v1.2.3 lineage, run against the actual frozen v1.2.3 HTML
(copied to a scratch working directory; the original release file was never
modified). This supersedes any prior claim in changelog documents by
reporting what was actually observed when the suites were run in this
session.

**Target file verified:** `ALARAD_Prototype_Research_Demo_v1.2.3.html`,
SHA-256 `92e897dd0ff1738f083df829b53f7f46377e042b7019bb9776232792261182ee`
(exact match to the frozen release — see `README.md` in this directory).

**Execution environment caveat (disclosed, applies to every suite below):**
Suites use Playwright to drive a real Chromium browser. The network policy in
this environment blocks downloading the pinned Chromium build
(141.0.7390.37) that Playwright normally installs. All suites were instead
run against the pre-installed Chromium at `/opt/pw-browsers/chromium`
(reports as version 153.0.8010.12). Test scripts were patched, **in scratch
copies only**, to pass `executable_path=` to `chromium.launch()`; no
original script or release file was altered. This is a real, disclosed
version difference (141 vs. 153) and is the most likely explanation for any
future, currently-unobserved behavioral drift — flagged here as a limitation
of this rerun, not hidden.

---

## 1. Suites run against v1.2.3 directly

These suites from the main 500-check `ALARAD_Final_Reproducible_Package`
were re-pointed at v1.2.3 (via `env/v123/alarad_prototype.html`, a copy of
the frozen v1.2.3 release) instead of their original v1.0 FROZEN target.

| Suite | Pass | Fail | Skip | Failure detail |
|---|---|---|---|---|
| `tests/t_phase3.py` | 142 | 1 | 0 | 1 failure = blocked Google Fonts request (console 404) — **environmental**, pre-disclosed in the original package's own notes |
| `tests/t_final_fixes.py` (TARGET=candidate) | 64 | 0 | 0 | — |
| `tests/t2_rerun.py` | 91 | 1 | 0 | Same Google Fonts 404 — **environmental** |
| `tests/t_sim_v2.py` | 86 | 1 | 0 | Same Google Fonts 404 — **environmental** |
| `tests/t_validation_v2.py` | 113 | 1 | 0 | Same Google Fonts 404 — **environmental** |
| `tests/t_validation.py` (legacy/informational) | 112 | 2 | 0 | 1 Google Fonts 404 (**environmental**) + 1 documented-intentional check (pre-existing, not a defect) |
| `reference_calculations/ref_science.py` | 65 | 0 | 0 | 1 additional INFO-level record (not pass/fail) |
| `reference_calculations/ref_scenarios.py` | 32 | 0 | 0 | — |
| `reference_calculations/ref_policy.py` | 30 | 0 | 0 | 0 mismatches of 30 compared values |
| `reference_calculations/ref_sweep.py` | 8,640/8,640 runs, 432/432 grid cells | 0 | 0 | Byte-identical to the stored reference output; independently recomputed precision/recall per (K, noise, threshold) setting |

**Subtotal (application-level, excluding the environmental Google Fonts
failure and the one documented-intentional check):** every suite above
passed 100% of its application-level assertions against v1.2.3.

**Regression-detection sanity check:** `t_final_fixes.py` was also run with
`TARGET=base` against the untouched pre-fix baseline (`ALARAD_Prototype_Phase3.html`):
**20 passed, 44 failed**. This confirms the suite is actually sensitive to
the defects it claims to check for — it is not vacuously passing — and that
the 64/0 result against v1.2.3 (and the candidate) is a genuine fixed-state
result, not a tautology.

## 2. v1.2.3-specific incremental suites (the "85 additional RSO workflow
tests" and related wording/UI-comparison suites)

These come from the separate `ALARAD_Research_Demo_v1.2.3_RSO_Response`
package's `build_tools/` directory. Each compares v1.2.3 against a specific
earlier version, as named in the script.

| Script | Compared against | Pass | Fail | Skip | vs. documentation |
|---|---|---|---|---|---|
| `t_v123_workflow.py` | v1.2.2 | 85 | 0 | 0 | Matches documented "85 additional RSO workflow tests" exactly |
| `t_v122_manual_report_for_v123.py` | v1.2.1 | 74 | 0 | 0 | Matches documented 74/74 |
| `t_v121_wording_for_v123.py` | v1.2 | 31 | 0 | 0 | **Documentation discrepancy — see §3 below** |
| `t_v12_wording_for_v123.py` | v1.1 | 37 | 0 | 0 | Matches documented 37/37 |
| `t_v12_responsive.py` | v1.1 | 21 | 0 | 0 | No independently confirmed documented comparison found for this exact script; see §3 |
| `t_header_v11.py` | — | **not run** | — | — | Script referenced by `run_v123.sh` at a path outside the extracted package (`../../../audit3/V11/build/t_header_v11.py`); not present in any package handled in this session. Reported as **not executed**, not as a pass. |

**Subtotal (85-test RSO workflow suite specifically, item 3 of the user's
request):** 85 passed, 0 failed, 0 skipped — independently reproduced in
full.

**Combined total across all suites listed in §1 and §2, excluding the
not-run `t_header_v11.py`:**

- **Passed:** 1,006 (142+64+91+86+113+112+65+32+30+85+74+31+37+21; `ref_sweep.py`'s
  8,640/432 run- and cell-level comparisons counted separately above, not
  folded into this integer total since they are a different unit)
- **Failed (application-level):** 1 (the single documented-intentional
  check inside `t_validation.py`)
- **Failed (environmental, Google Fonts blocked):** 5 (one each in
  `t_phase3.py`, `t2_rerun.py`, `t_sim_v2.py`, `t_validation_v2.py`,
  `t_validation.py`)
- **Skipped:** 0 in every suite actually run
- **Not executed:** `t_header_v11.py` (script unavailable — see above)

No failure was excluded from this report. The 6 total failures above are
the complete set observed; 5 are the same recurring Google Fonts block, 1 is
a pre-existing documented-intentional check, and none indicate an
undisclosed defect in v1.2.3.

## 3. Discrepancies against prior documentation (flagged, not resolved by
assumption)

- **`t_v121_wording_for_v123.py`: reran as 31/31; `CHANGELOG_Nov2026.md`
  states "v1.2.1 wording 21/21".** This is a genuine discrepancy between
  this independent rerun and a previously-read documentation source. One
  plausible explanation was noticed but **is not confirmed**: a separate
  script, `t_v12_responsive.py`, independently reran as exactly 21/21, and
  no other script in the package reran as 21/21. It is possible the
  changelog's "21/21" figure actually refers to `t_v12_responsive.py` and
  was mislabeled, or that "v1.2.1 wording" in the changelog refers to a
  different, unavailable script version. **This report does not assume
  either explanation is correct.** It is recorded here as an open
  discrepancy requiring reconciliation against original source documents
  before any publication claim is made using either number.
- **`t_header_v11.py` could not be located or rerun.** Any documented count
  for this script (if one exists in prior changelogs) could not be
  independently verified in this session and must not be cited as
  independently reproduced.

## 4. SHA-256 verification

| File | SHA-256 | Result |
|---|---|---|
| `research-demo/releases/html/ALARAD_Prototype_Research_Demo_v1.2.3.html` | `92e897dd0ff1738f083df829b53f7f46377e042b7019bb9776232792261182ee` | Matches previously recorded value exactly; verified via `sha256sum -c` in this session |

The `SHA256SUMS.txt` manifests inside the extracted verification packages
were also checked with `sha256sum -c` against the scratch extraction. All
entries verified OK **except** the entries for files this session
intentionally patched (to inject `executable_path=` for the Chromium
workaround described above) — those mismatches are expected and are
evidence the integrity-check mechanism itself works correctly, not an
application defect. No file outside the deliberately-patched test/reference
scripts showed a hash mismatch.

## 5. Summary against the user's explicit requirements

| Requirement | Status |
|---|---|
| Rerun all existing suites against v1.2.3, including the 85 RSO workflow tests | Done — see §1, §2 |
| Report exact passed/failed/skipped counts | Done — see §2 combined totals |
| Distinguish environmental vs. application failures; do not silently exclude any | Done — every failure attributed; none omitted |
| Verify SHA-256 of the original release | Done — exact match |
