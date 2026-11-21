"""
Loader for phase2a_config.json, mirroring phase1_simulator/config.py's
provisional-labeling enforcement: a baseline threshold that is missing
its 'status' field, or that claims a status outside the recognized
provisional vocabulary, is rejected at load time rather than silently
treated as validated.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

PROVISIONAL_STATUSES = {"PROVISIONAL"}

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config" / "phase2a_config.json"


class ConfigValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Phase2AConfig:
    raw: Dict[str, Any]

    def baseline(self, name: str) -> Dict[str, Any]:
        return self.raw["baselines"][name]


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Phase2AConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    disclaimer = data.get("_disclaimer", "")
    if "PROVISIONAL" not in disclaimer.upper():
        raise ConfigValidationError(
            "phase2a_config.json must carry an explicit PROVISIONAL disclaimer"
        )
    for name, block in data.get("baselines", {}).items():
        has_numeric_param = any(
            not isinstance(v, (dict,)) and k not in ("status", "description", "registry_row")
            for k, v in block.items()
        )
        if has_numeric_param:
            status = block.get("status")
            if status not in PROVISIONAL_STATUSES:
                raise ConfigValidationError(
                    f"baseline {name!r} has a numeric parameter but an "
                    f"unrecognized or missing status: {status!r}"
                )
    return Phase2AConfig(raw=data)
