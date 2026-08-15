"""Consistency checks for the framework-owned starter forms."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrameworkFormConsistencyTests(unittest.TestCase):
    def test_control_keys_and_names_match(self):
        mismatches = []
        for path in sorted((ROOT / "Forms").glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8-sig"))
            form = document[next(iter(document))]
            for key, control in form.get("CONTROLS", {}).items():
                name = control.get("name")
                if name and name != key:
                    mismatches.append(f"{path.name}: {key} != {name}")
        self.assertEqual(mismatches, [])

    def test_any_framework_date_pickers_use_standard_width(self):
        widths = []
        for path in sorted((ROOT / "Forms").glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8-sig"))
            form = document[next(iter(document))]
            for key, control in form.get("CONTROLS", {}).items():
                if control.get("type") == "DatePickerCtrl":
                    widths.append((path.name, key, control.get("sizech", [None])[0]))
        self.assertEqual(
            [(path, key, width) for path, key, width in widths if width != 20],
            [],
        )


if __name__ == "__main__":
    unittest.main()
