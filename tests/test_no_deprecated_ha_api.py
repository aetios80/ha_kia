"""Guard against Home Assistant APIs deprecated in 2026.11.

Home Assistant 2026.11 logs deprecation warnings for climate entities that
provide temperature_unit, current_temperature or target_temperature (removed
in 2027.11; use the native_* members) and for the TrackerEntity alias in
device_tracker.config_entry (removed in 2027.6). Standard library only.
"""

import ast
import pathlib
import unittest

PACKAGE = (
    pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "kia_uvo"
)

DEPRECATED_CLIMATE_MEMBERS = {
    "temperature_unit",
    "current_temperature",
    "target_temperature",
    "_attr_temperature_unit",
    "_attr_current_temperature",
    "_attr_target_temperature",
}


class DeprecatedApiTest(unittest.TestCase):
    def test_climate_uses_native_members(self):
        tree = ast.parse((PACKAGE / "climate.py").read_text(encoding="utf-8"))
        defined = {
            node.name
            for cls in ast.walk(tree)
            if isinstance(cls, ast.ClassDef)
            for node in cls.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        used = {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
        }
        found = (defined | used) & DEPRECATED_CLIMATE_MEMBERS
        self.assertFalse(found, found)

    def test_tracker_entity_not_imported_from_config_entry(self):
        for path in PACKAGE.rglob("*.py"):
            if "_vendor" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(
                "device_tracker.config_entry import TrackerEntity", text, path.name
            )


if __name__ == "__main__":
    unittest.main()
