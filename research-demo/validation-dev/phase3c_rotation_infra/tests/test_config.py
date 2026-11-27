"""Task 6/7: the centralized provisional-config loader enforces both a
recognized 'status' and a synthetic-source 'source' field."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from phase3c_rotation_infra.config import ConfigValidationError, load_config


class TestConfig(unittest.TestCase):
    def test_shipped_config_loads_successfully(self):
        cfg = load_config()
        self.assertIn("roster_generation", cfg.raw)
        self.assertIn("escalation", cfg.raw)

    def test_every_numeric_block_has_recognized_status_and_synthetic_source(self):
        cfg = load_config()
        for name, block in cfg.raw.items():
            if name in ("_disclaimer", "schema_version", "methodology_reference"):
                continue
            has_numeric = any(
                not isinstance(v, dict) and k not in ("status", "description", "registry_row", "source")
                for k, v in block.items()
            )
            if has_numeric:
                self.assertEqual(block["status"], "PROVISIONAL", msg=name)
                self.assertIn("synthetic", block["source"].lower(), msg=name)

    def _write(self, data: dict) -> Path:
        tmp = Path(tempfile.mkstemp(suffix=".json")[1])
        tmp.write_text(json.dumps(data), encoding="utf-8")
        return tmp

    def test_missing_disclaimer_rejected(self):
        bad = self._write({"_disclaimer": "no mention here", "roster_generation": {"x": 1, "status": "PROVISIONAL", "source": "synthetic"}})
        with self.assertRaises(ConfigValidationError):
            load_config(bad)

    def test_numeric_block_missing_status_rejected(self):
        bad = self._write({"_disclaimer": "PROVISIONAL", "roster_generation": {"x": 1, "source": "synthetic"}})
        with self.assertRaises(ConfigValidationError):
            load_config(bad)

    def test_numeric_block_missing_synthetic_source_rejected(self):
        bad = self._write({"_disclaimer": "PROVISIONAL", "roster_generation": {"x": 1, "status": "PROVISIONAL", "source": "clinical guidance"}})
        with self.assertRaises(ConfigValidationError):
            load_config(bad)


if __name__ == "__main__":
    unittest.main()
