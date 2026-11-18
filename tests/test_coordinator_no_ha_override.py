"""Guard against shadowing private DataUpdateCoordinator methods.

4.0.4 defined a helper named ``_async_refresh`` in the coordinator. Home
Assistant calls ``DataUpdateCoordinator._async_refresh(log_failures=...,
raise_on_auth_failed=..., ...)`` during setup and polling, so the helper
replaced the framework method and setup failed with an unexpected keyword
argument. The stub test environment cannot catch this, so this test checks
the source with the standard library only.
"""

import ast
import pathlib
import unittest

COORDINATOR = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components"
    / "kia_uvo"
    / "coordinator.py"
)

# Private DataUpdateCoordinator methods that subclasses must not redefine.
# _async_update_data and _async_setup are the documented override points.
HA_PRIVATE_METHODS = {
    # From homeassistant/helpers/update_coordinator.py at tag 2026.11.2.
    "_async_config_entry_first_refresh",
    "_async_refresh",
    "_async_refresh_finished",
    "_async_unsub_refresh",
    "_async_unsub_shutdown",
    "_handle_coordinator_update",
    "_handle_refresh_interval",
    "_on_hass_stop",
    "_schedule_refresh",
    "_unschedule_refresh",
}


class CoordinatorOverrideTest(unittest.TestCase):
    def test_no_private_framework_method_is_redefined(self):
        tree = ast.parse(COORDINATOR.read_text(encoding="utf-8"))
        defined = {
            node.name
            for cls in ast.walk(tree)
            if isinstance(cls, ast.ClassDef)
            for node in cls.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertFalse(defined & HA_PRIVATE_METHODS, defined & HA_PRIVATE_METHODS)


if __name__ == "__main__":
    unittest.main()
