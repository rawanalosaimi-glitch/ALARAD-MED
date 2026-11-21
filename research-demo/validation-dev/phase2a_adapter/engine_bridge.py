"""
Read-only Playwright bridge to the frozen ALARAD v1.2.3 release.

This module never writes to the frozen HTML file. It launches a headless
browser, loads the file via a file:// URL, and evaluates JavaScript
expressions against the live page -- calling the engine's own, real,
unmodified functions. No detection, scoring, or classification logic is
reimplemented here, or anywhere in phase2a_adapter's "adapter" layer; this
bridge only transports calls and their results between Python and the
real engine running in the browser.

Before every session, the frozen file's SHA-256 is re-verified against
the value already recorded in Verification_Rerun_Report.md, so a result
can never silently come from an unexpected copy of the release.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Optional

from playwright.sync_api import sync_playwright

FROZEN_RELEASE_PATH = (
    Path(__file__).resolve().parents[2]
    / "releases" / "html" / "ALARAD_Prototype_Research_Demo_v1.2.3.html"
)

# Recorded in Verification_Rerun_Report.md and re-verified independently
# multiple times across sessions; see that document for provenance.
FROZEN_RELEASE_SHA256 = (
    "92e897dd0ff1738f083df829b53f7f46377e042b7019bb9776232792261182ee"
)

# Pre-installed Chromium used throughout this project because the pinned
# Playwright build cannot be downloaded under this environment's network
# policy -- see Verification_Rerun_Report.md's disclosed version caveat
# (141.0.7390.37 pinned vs. 153.0.8010.12 actually used). The same
# disclosed caveat applies here.
CHROMIUM_EXECUTABLE_PATH = "/opt/pw-browsers/chromium"


class EngineBridgeError(RuntimeError):
    pass


def verify_frozen_release_hash(path: Path) -> str:
    actual = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if actual != FROZEN_RELEASE_SHA256:
        raise EngineBridgeError(
            f"Frozen release hash mismatch at {path}: expected "
            f"{FROZEN_RELEASE_SHA256}, got {actual}. Refusing to evaluate "
            f"against an unverified file."
        )
    return actual


class EngineBridge:
    """A reusable, read-only browser session against the frozen engine.

    Use as a context manager:
        with EngineBridge() as bridge:
            result = bridge.evaluate(
                "(a) => evaluateExposure(a)",
                {"room": "Cath Lab 1", "procMult": 1.0, "rate": 400,
                 "dur": 30, "dist": 1, "refDist": 1, "shield": 1,
                 "mode": "personal"},
            )
    """

    def __init__(self, release_path: Path = FROZEN_RELEASE_PATH, verify_hash: bool = True):
        self.release_path = Path(release_path)
        if verify_hash:
            verify_frozen_release_hash(self.release_path)
        self._pw = None
        self._browser = None
        self._page = None

    def __enter__(self) -> "EngineBridge":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            executable_path=CHROMIUM_EXECUTABLE_PATH, headless=True)
        self._page = self._browser.new_page()
        url = "file://" + os.path.abspath(str(self.release_path))
        self._page.goto(url)
        self._page.wait_for_timeout(300)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._pw is not None:
            self._pw.stop()

    def evaluate(self, expression: str, arg: Optional[Any] = None):
        """Evaluate a JS expression/function in the live, unmodified page."""
        if arg is None:
            return self._page.evaluate(expression)
        return self._page.evaluate(expression, arg)

    def type_of(self, name: str) -> str:
        return self._page.evaluate(f"typeof {name}")
