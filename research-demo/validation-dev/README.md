# Research Development Working Copy — v1.2.3 Validation

**Branch:** `research/icaire-v123-validation`
**Created:** 2026-11-19
**Status:** Research development only. Not merged to `main`.

## Purpose

This directory holds new research-validation documents produced while treating
**ALARAD Research-Demo v1.2.3** as the approved technical foundation for the
ICAIRE research paper (per user approval, 2026-11-19).

It exists to satisfy two constraints at once:

1. The frozen v1.2.3 release and the live application **must not be modified**.
2. New research work (independent reruns, ground-truth extraction, gap
   analysis) needs somewhere to live that is clearly separated from the
   frozen artifacts.

Nothing in `research-demo/releases/`, `research-demo/demo/`, or any of the
existing root-level `research-demo/*.md`/`*.csv`/`*.txt` files was touched to
produce this work. Only this new `validation-dev/` subdirectory was added.

## Foundation release

- File: `research-demo/releases/html/ALARAD_Prototype_Research_Demo_v1.2.3.html`
- SHA-256: `92e897dd0ff1738f083df829b53f7f46377e042b7019bb9776232792261182ee`
- Re-verified against the file currently on disk at the time these documents
  were produced (2026-11-19) — exact match, no drift from the previously
  recorded hash.

## Contents of this directory

| File | Purpose |
|---|---|
| `Verification_Rerun_Report.md` | Independent rerun of every existing verification suite against v1.2.3, including the 85 RSO workflow tests, with exact pass/fail/skip counts and explicit environmental-vs-application failure attribution. |
| `Ground_Truth_Scenarios_S1-S13.md` | Standalone, human-readable ground-truth table for all 13 primary simulation scenarios, extracted verbatim from the v1.2.3 source. |
| `Gap_Checklist.md` | Research validation gap checklist against ICAIRE-style methodology requirements (baselines, metrics, ground truth, stress tests), building on the two prior audit reports. |

## What this work does NOT do

- It does not change any line of the frozen v1.2.3 HTML or any other frozen
  release.
- It does not implement forecasting, rotation, or any new detection
  algorithm.
- It does not claim any result that was not actually executed and observed
  in this session. Every number below is from a real command run against
  real files; environmental caveats are called out explicitly, not omitted.
