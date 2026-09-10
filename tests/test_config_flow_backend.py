"""Regression tests for data-backend selection in the config wizard."""

from pathlib import Path


COMPONENT_ROOT = Path(__file__).parent.parent / "custom_components" / "kia_uvo"


def test_config_flow_exposes_only_the_operational_cci_backend() -> None:
    """The initial selector must not accept unavailable official API credentials."""
    source = (COMPONENT_ROOT / "config_flow.py").read_text(encoding="utf-8")

    assert "STEP_BACKEND_DATA_SCHEMA" in source
    assert '"value": DATA_BACKEND_CCI' in source
    assert "DATA_BACKEND_OFFICIAL" in source
    assert 'reason="official_data_api_unavailable"' in source


def test_existing_entries_default_to_cci_during_migration() -> None:
    """Existing installations keep their operational CCI backend."""
    source = (COMPONENT_ROOT / "__init__.py").read_text(encoding="utf-8")

    assert "CONF_DATA_BACKEND: DATA_BACKEND_CCI" in source
    assert "if config_entry.version == 2:" in source
