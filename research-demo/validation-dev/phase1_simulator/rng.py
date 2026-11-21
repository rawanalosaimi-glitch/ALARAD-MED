"""
Deterministic seeding for the Phase 1 simulator.

A single top-level integer seed is supplied per simulation run. Every
sub-stream used while generating that run (worker attributes, pattern
timing, fault timing, measurement noise, etc.) is derived from that one
seed plus a stable text label, via a SHA-256-based derivation -- never by
incrementing or reusing the top-level seed directly, and never by drawing
further values out of one shared stream for an unrelated purpose. This
gives two guarantees:

1. Reproducibility: the same (run seed, archetype, config) always produces
   the exact same output, on any machine, for a given Python version (see
   PHASE1_README.md for why "a given Python version" is the correct scope
   of this guarantee -- Python's random.Random is specified to be stable
   for a given CPython version but is not a cross-language or
   cross-version standard).
2. Independence-by-label: two different purposes (e.g. "attrs" vs.
   "pattern" vs. "fault" for the same worker) get genuinely independent
   streams, each starting fresh from its own derived seed, rather than
   sharing or replaying one stream's position across unrelated draws.
"""

from __future__ import annotations

import hashlib
import random


def derive_seed(run_seed: int, *labels: str) -> int:
    """Deterministically derive a sub-seed from a run seed and labels."""
    h = hashlib.sha256()
    h.update(str(run_seed).encode("utf-8"))
    for label in labels:
        h.update(b"|")
        h.update(str(label).encode("utf-8"))
    # Python's random.Random accepts an arbitrarily large int seed.
    return int.from_bytes(h.digest()[:8], "big")


def make_rng(run_seed: int, *labels: str) -> random.Random:
    """A fresh, independent, deterministic RNG stream for one sub-purpose."""
    return random.Random(derive_seed(run_seed, *labels))
