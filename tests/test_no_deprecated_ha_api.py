"""Guard against Home Assistant APIs deprecated in 2026.11.

Home Assistant 2026.11 logs deprecation warnings for climate entities that
provide temperature_unit, current_temperature, target_temperature,
target_temperature_high or target_temperature_low (removed in 2027.11; use
the native_* members) and for the TrackerEntity alias in
device_tracker.config_entry (removed in 2027.6). Standard library only.
"""

import ast
import pathlib
import unittest

PACKAGE = (
    pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "kia_uvo"
)

_DEPRECATED_CLIMATE_PROPERTIES = {
    "temperature_unit",
    "current_temperature",
    "target_temperature",
    "target_temperature_high",
    "target_temperature_low",
}
DEPRECATED_CLIMATE_MEMBERS = _DEPRECATED_CLIMATE_PROPERTIES | {
    f"_attr_{name}" for name in _DEPRECATED_CLIMATE_PROPERTIES
}


def _class_member_names(tree: ast.AST) -> set[str]:
    """Names defined in class bodies: methods, assignments, annotations."""
    names: set[str] = set()
    for cls in ast.walk(tree):
        if not isinstance(cls, ast.ClassDef):
            continue
        for node in cls.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                names.update(t.id for t in node.targets if isinstance(t, ast.Name))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names.add(node.target.id)
    return names


def _self_attribute_names(tree: ast.AST) -> set[str]:
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    }


def _platform_files():
    return [p for p in PACKAGE.rglob("*.py") if "_vendor" not in p.parts]


class DeprecatedApiTest(unittest.TestCase):
    def test_climate_uses_native_members(self):
        tree = ast.parse((PACKAGE / "climate.py").read_text(encoding="utf-8"))
        found = (
            _class_member_names(tree) | _self_attribute_names(tree)
        ) & DEPRECATED_CLIMATE_MEMBERS
        self.assertFalse(found, found)

    def test_tracker_entity_not_imported_from_config_entry(self):
        for path in _platform_files():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and (node.module or "").endswith(
                    "device_tracker.config_entry"
                ):
                    imported = {alias.name for alias in node.names}
                    self.assertNotIn("TrackerEntity", imported, path.name)

    def test_detects_class_level_assignments(self):
        """Self-check: the scanner sees Assign and AnnAssign in class bodies."""
        tree = ast.parse(
            "class A:\n"
            "    _attr_temperature_unit = 'C'\n"
            "    _attr_target_temperature: float = 20.0\n"
        )
        self.assertEqual(
            _class_member_names(tree) & DEPRECATED_CLIMATE_MEMBERS,
            {"_attr_temperature_unit", "_attr_target_temperature"},
        )

    def test_detects_multiline_import(self):
        """Self-check: a parenthesised multi-name import is caught."""
        tree = ast.parse(
            "from homeassistant.components.device_tracker.config_entry import (\n"
            "    SourceType,\n"
            "    TrackerEntity,\n"
            ")\n"
        )
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom))
        self.assertIn("TrackerEntity", {a.name for a in node.names})


if __name__ == "__main__":
    unittest.main()
