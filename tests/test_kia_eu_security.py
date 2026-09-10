"""Security regression tests for the self-contained Kia Connect EU API."""

import ast
import json
import logging
from pathlib import Path
import sys
from types import ModuleType

import pytest
import requests


COMPONENT_ROOT = Path(__file__).parent.parent / "custom_components" / "kia_uvo"


def _register_namespace(name: str, path: Path) -> None:
    package = ModuleType(name)
    package.__path__ = [str(path)]
    sys.modules.setdefault(name, package)


_register_namespace("custom_components", COMPONENT_ROOT.parent)
_register_namespace("custom_components.kia_uvo", COMPONENT_ROOT)
_register_namespace("custom_components.kia_uvo._vendor", COMPONENT_ROOT / "_vendor")

from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.Token import Token
from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.KiaUvoApiEU import (
    CCI_UPSTREAM_BASELINE,
)
from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.http import (
    ApiImplSession,
    EndpointPolicyError,
    KIA_EU_HOSTS,
    OpenStreetMapSession,
    validate_endpoint,
)
from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.logging_utils import (
    SafeDebugLogger,
    debug_event,
)
from custom_components.kia_uvo.redact import strip_token_credentials


def test_persisted_token_excludes_duplicated_credentials() -> None:
    token = Token(username="user@example.test", password="password", pin="1234")

    assert token.to_dict().keys().isdisjoint({"username", "password", "pin"})


def test_legacy_token_credentials_are_removed() -> None:
    token = {
        "username": "user@example.test",
        "password": "password",
        "pin": "1234",
        "access_token": "renewable-token",
    }

    assert strip_token_credentials(token) == {"access_token": "renewable-token"}
    assert strip_token_credentials(None) is None


def test_cci_tokens_persist_without_credentials() -> None:
    token = Token(
        username="user@example.test",
        password="password",
        pin="1234",
        cci_access_token="cci-access",
        refresh_token="cci-refresh",
        exchangeable_token="exchangeable",
        non_ccs_token="non-ccs",
    )

    persisted = token.to_dict()

    assert CCI_UPSTREAM_BASELINE == "v4.29.1"
    assert persisted["cci_access_token"] == "cci-access"
    assert persisted["refresh_token"] == "cci-refresh"
    assert persisted.keys().isdisjoint({"username", "password", "pin"})


def test_credentials_schema_uses_password_selectors() -> None:
    source = (COMPONENT_ROOT / "config_flow.py").read_text(encoding="utf-8")

    assert 'vol.Required(CONF_PASSWORD): selector({"text": {"type": "password"}})' in source
    assert 'vol.Optional(CONF_PIN, default=DEFAULT_PIN): selector(' in source
    assert '"text": {"type": "password"}' in source


@pytest.mark.parametrize(
    "host,ports",
    KIA_EU_HOSTS.items(),
)
def test_kia_eu_allowlist_accepts_official_hosts(host: str, ports: frozenset[int]) -> None:
    for port in ports:
        suffix = "" if port == 443 else f":{port}"
        validate_endpoint(f"https://{host}{suffix}/api")


@pytest.mark.parametrize(
    "url",
    (
        "http://prd.eu-ccapi.kia.com/api",
        "https://example.invalid/api",
        "https://prd.eu-ccapi.kia.com:444/api",
        "https://user:password@prd.eu-ccapi.kia.com/api",
    ),
)
def test_kia_eu_allowlist_rejects_invalid_endpoints(url: str) -> None:
    with pytest.raises(EndpointPolicyError):
        validate_endpoint(url)


def test_session_rejects_disabled_tls_verification() -> None:
    with pytest.raises(EndpointPolicyError):
        ApiImplSession().get("https://prd.eu-ccapi.kia.com/api", verify=False)


def test_session_rejects_redirect_to_untrusted_host() -> None:
    request = requests.Request("GET", "https://example.invalid/api").prepare()
    with pytest.raises(EndpointPolicyError):
        ApiImplSession().send(request)


def test_geocoding_session_accepts_only_openstreetmap() -> None:
    with pytest.raises(EndpointPolicyError):
        OpenStreetMapSession().get("https://prd.eu-ccapi.kia.com/api")


def test_safe_debug_logging_drops_sensitive_values(caplog: pytest.LogCaptureFixture) -> None:
    logger = SafeDebugLogger(logging.getLogger("tests.kia_eu_security"))
    secret = "password=secret pin=1234 token=renewable VIN=KNA location=50.0,19.0"

    with caplog.at_level(logging.DEBUG):
        logger.debug("vendor response: %s", secret)
        debug_event(logger, "token_refresh", status=200)

    logged = caplog.text
    assert "token_refresh" in logged
    assert secret not in logged
    assert "secret" not in logged
    assert "KNA" not in logged


def test_vendor_source_prohibits_insecure_network_patterns() -> None:
    vendor_root = (
        Path(__file__).parent.parent
        / "custom_components"
        / "kia_uvo"
        / "_vendor"
        / "hyundai_kia_connect_api"
    )
    violations: list[str] = []

    for source_path in vendor_root.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if (
                        keyword.arg == "verify"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is False
                    ):
                        violations.append(f"{source_path}:{node.lineno}: verify=False")
                if (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "requests"
                    and node.func.attr in {"get", "post", "request"}
                ):
                    violations.append(f"{source_path}:{node.lineno}: direct requests call")
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value.startswith("http://")
            ):
                violations.append(f"{source_path}:{node.lineno}: non-HTTPS URL")

    assert not violations, "\n".join(violations)


def test_cci_auth_uses_the_secure_request_boundary() -> None:
    source = (
        COMPONENT_ROOT
        / "_vendor"
        / "hyundai_kia_connect_api"
        / "KiaUvoApiEU.py"
    ).read_text(encoding="utf-8")

    assert source.count("http_request(") >= 3
    assert "requests.post(" not in source


def test_hacs_manifest_has_no_external_api_dependency() -> None:
    manifest = json.loads((COMPONENT_ROOT / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["name"] == "Kia Connect EU"
    assert not any("hyundai_kia_connect_api" in item for item in manifest["requirements"])
    assert "pycryptodome>=3.23.0" in manifest["requirements"]


def test_cci_backend_is_operational_and_official_backend_stays_disabled() -> None:
    init_source = (COMPONENT_ROOT / "__init__.py").read_text(encoding="utf-8")
    flow_source = (COMPONENT_ROOT / "config_flow.py").read_text(encoding="utf-8")

    assert "KiaConnectEuDataUpdateCoordinator(hass, config_entry)" in init_source
    assert "strip_token_credentials(token_data)" in init_source
    assert 'reason="official_data_api_unavailable"' in flow_source
