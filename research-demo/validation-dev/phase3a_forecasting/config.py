"""
Loader for phase3a_config.json, same provisional-labeling enforcement
pattern as phase1_simulator/config.py and phase2a_adapter/config.py: a
parameter block with a numeric value but no recognized 'status' is
rejected at load time.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

RECOGNIZED_STATUSES = {"PROVISIONAL"}

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config" / "phase3a_config.json"


class ConfigValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Phase3AConfig:
    raw: Dict[str, Any]

    def block(self, name: str) -> Dict[str, Any]:
        return self.raw[name]


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Phase3AConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    disclaimer = data.get("_disclaimer", "")
    if "PROVISIONAL" not in disclaimer.upper():
        raise ConfigValidationError(
            "phase3a_config.json must carry an explicit PROVISIONAL disclaimer"
        )
    for name, block in data.items():
        if name == "_disclaimer" or not isinstance(block, dict):
            continue
        has_numeric_param = any(
            not isinstance(v, dict) and k not in ("status", "description", "registry_row", "source_comment")
            for k, v in block.items()
        )
        if has_numeric_param:
            status = block.get("status")
            if status not in RECOGNIZED_STATUSES and not str(status).startswith(
                "REUSED_FROM_V1.2.3"
            ):
                raise ConfigValidationError(
                    f"block {name!r} has a numeric parameter but an "
                    f"unrecognized or missing status: {status!r}"
                )
    return Phase3AConfig(raw=data)
