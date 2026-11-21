"""
Configuration loading for the Phase 1 simulator.

Every numeric range in the shipped config/simulation_config.json is
explicitly marked with a "status" of PROVISIONAL (or an equivalent
inherited-but-unverified status) and cross-references a row in
ICAIRE_Simulation_Validation_Methodology.md section 9's parameter
registry. This loader actively refuses to load a configuration that is
missing the top-level provisional disclaimer, or that contains a
provisional_parameters leaf without a recognized status -- a parameter
cannot silently become "validated" just by being loaded.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

# Any status in this set, or any status string starting with
# "REUSED_FROM_V1.2.3", is accepted as a recognized, honest label. A
# provisional_parameters leaf with no "status" key at all, or an
# unrecognized one, fails loading.
PROVISIONAL_STATUSES = {
    "PROVISIONAL",
    "INHERITED_FROM_V1.2.3_UNVERIFIED",
    "INHERITED_FROM_V1.2.3_SELF_DISCLOSED_LIMITATION",
}


class ConfigValidationError(ValueError):
    pass


@dataclass(frozen=True)
class SimulationConfig:
    raw: Dict[str, Any]
    path: Path

    @property
    def schema_version(self) -> str:
        return self.raw["schema_version"]

    @property
    def provisional_parameters(self) -> Dict[str, Any]:
        return self.raw["provisional_parameters"]

    def procedure_classes(self) -> Dict[str, Any]:
        return self.provisional_parameters["procedure_classes"]

    def shift_lengths_minutes(self):
        return self.provisional_parameters["shift_lengths_minutes"]["values"]

    def every_provisional_item_is_labeled(self) -> bool:
        """Used both at load time and by tests: every leaf parameter block
        under provisional_parameters must carry a recognized 'status'.

        A dict is treated as a "leaf parameter block" (and therefore
        required to declare its own 'status') if it has any value that is
        not itself a dict, other than 'status' -- e.g. a numeric range, a
        list, a scalar. A dict whose values are *all* further dicts (e.g.
        procedure_classes grouping several named procedure entries) is
        treated as a pure grouping node and is not itself required to
        carry a 'status': recursion continues into its dict-valued
        children instead. This distinction matters because a leaf with no
        dict children (e.g. {"value": 1.0}) must not be allowed to pass
        this check merely because recursing into its one scalar child
        trivially returns True.
        """

        def walk(node) -> bool:
            if not isinstance(node, dict):
                return True
            non_status_items = [(k, v) for k, v in node.items() if k != "status"]
            has_scalar_value = any(not isinstance(v, dict) for _, v in non_status_items)
            if has_scalar_value:
                status = node.get("status")
                if status is None:
                    return False
                status = str(status)
                if status not in PROVISIONAL_STATUSES and not status.startswith(
                    "REUSED_FROM_V1.2.3"
                ):
                    return False
                return True
            if not non_status_items:
                return True
            return all(walk(v) for _, v in non_status_items if isinstance(v, dict))

        return all(walk(v) for v in self.provisional_parameters.values())


def load_config(path: Path) -> SimulationConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    disclaimer = data.get("_disclaimer", "")
    if "PROVISIONAL" not in disclaimer.upper():
        raise ConfigValidationError(
            "simulation_config.json must carry an explicit PROVISIONAL "
            "disclaimer in its top-level '_disclaimer' field"
        )
    if "provisional_parameters" not in data:
        raise ConfigValidationError(
            "simulation_config.json must have a 'provisional_parameters' block"
        )
    cfg = SimulationConfig(raw=data, path=Path(path))
    if not cfg.every_provisional_item_is_labeled():
        raise ConfigValidationError(
            "every provisional_parameters leaf must carry a recognized "
            "'status' field (see config.py PROVISIONAL_STATUSES) -- "
            "an unlabeled numeric parameter would silently look validated"
        )
    return cfg
