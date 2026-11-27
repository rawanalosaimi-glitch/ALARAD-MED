"""
Loader for phase3c_config.json -- same provisional-labeling enforcement
pattern as phase1_simulator/config.py, phase2a_adapter/config.py, and
phase3a_forecasting/config.py: a block with a numeric parameter but no
recognized 'status' is rejected at load time.

Extends that pattern with one additional, explicit requirement (task 6
of this round): every such block must also carry a 'source' string that
documents its value as a synthetic research-prototype assumption, not a
clinical or regulatory standard -- a block that only says "PROVISIONAL"
without saying where the value came from is rejected too.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

RECOGNIZED_STATUSES = {"PROVISIONAL"}

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config" / "phase3c_config.json"


class ConfigValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Phase3CConfig:
    raw: Dict[str, Any]

    def block(self, name: str) -> Dict[str, Any]:
        return self.raw[name]


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Phase3CConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    disclaimer = data.get("_disclaimer", "")
    if "PROVISIONAL" not in disclaimer.upper():
        raise ConfigValidationError(
            "phase3c_config.json must carry an explicit PROVISIONAL disclaimer"
        )
    for name, block in data.items():
        if name in ("_disclaimer", "schema_version", "methodology_reference"):
            continue
        if not isinstance(block, dict):
            continue
        has_numeric_param = any(
            not isinstance(v, dict)
            and k not in ("status", "description", "registry_row", "source")
            for k, v in block.items()
        )
        if has_numeric_param:
            status = block.get("status")
            if status not in RECOGNIZED_STATUSES:
                raise ConfigValidationError(
                    f"block {name!r} has a numeric parameter but an "
                    f"unrecognized or missing status: {status!r}"
                )
            source = block.get("source")
            if not source or "synthetic" not in str(source).lower():
                raise ConfigValidationError(
                    f"block {name!r} has a numeric parameter but its "
                    f"'source' field does not document it as a synthetic "
                    f"research-prototype assumption: {source!r}"
                )
    return Phase3CConfig(raw=data)
