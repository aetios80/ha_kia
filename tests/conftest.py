"""Shared pytest configuration for kia_uvo tests."""

from pathlib import Path
import sys
from types import ModuleType

import pytest

pytest.register_assert_rewrite("custom_components.kia_uvo")

COMPONENT_ROOT = Path(__file__).parent.parent / "custom_components" / "kia_uvo"

# Lightweight namespace packages, so test modules can import the vendored
# library and the integration without Home Assistant's package loader.
_NAMESPACES = {
    "custom_components": COMPONENT_ROOT.parent,
    "custom_components.kia_uvo": COMPONENT_ROOT,
    "custom_components.kia_uvo._vendor": COMPONENT_ROOT / "_vendor",
}
_installed: list[str] = []


def _install_namespaces() -> None:
    for name, path in _NAMESPACES.items():
        if name in sys.modules:
            continue
        package = ModuleType(name)
        package.__path__ = [str(path)]
        sys.modules[name] = package
        _installed.append(name)


def _remove_namespaces() -> None:
    """Drop what this file installed, and everything imported below it."""
    for root in _installed:
        for name in [n for n in sys.modules if n == root or n.startswith(root + ".")]:
            del sys.modules[name]
    _installed.clear()


_install_namespaces()


def pytest_unconfigure(config) -> None:
    _remove_namespaces()
