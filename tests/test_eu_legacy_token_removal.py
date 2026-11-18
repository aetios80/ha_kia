"""The legacy 48-char token login and refresh_token grant are gone (#1506, #1507)."""

import datetime as dt
from pathlib import Path
import sys
from types import ModuleType

COMPONENT_ROOT = Path(__file__).parent.parent / "custom_components" / "kia_uvo"


def _register_namespace(name: str, path: Path) -> None:
    package = ModuleType(name)
    package.__path__ = [str(path)]
    sys.modules.setdefault(name, package)


_register_namespace("custom_components", COMPONENT_ROOT.parent)
_register_namespace("custom_components.kia_uvo", COMPONENT_ROOT)
_register_namespace("custom_components.kia_uvo._vendor", COMPONENT_ROOT / "_vendor")

from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.KiaUvoApiEU import (  # noqa: E402
    KiaUvoApiEU,
)
from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.Token import (  # noqa: E402
    Token,
)

TOKEN_SHAPED_PASSWORD = "A" * 48


def _api(monkeypatch) -> KiaUvoApiEU:
    api = KiaUvoApiEU(1, 1, "en")
    monkeypatch.setattr(api, "_get_stamp", lambda: "stamp")
    monkeypatch.setattr(api, "_get_device_id", lambda _stamp: "device")
    monkeypatch.setattr(api, "_get_cookies", lambda: {})
    monkeypatch.setattr(api, "_set_session_language", lambda _cookies: None)
    return api


def test_grant_helper_and_constants_are_removed() -> None:
    api = KiaUvoApiEU(1, 1, "en")
    assert not hasattr(api, "_get_access_token")
    assert not hasattr(api, "CCS_SERVICE_SECRET")
    assert not hasattr(api, "BASIC_AUTHORIZATION")


def test_token_shaped_password_goes_through_the_cci_password_login(
    monkeypatch,
) -> None:
    api = _api(monkeypatch)
    seen = {}

    def _cci_login(_user, password, _device_id):
        seen["password"] = password
        return {
            "access_token": "Bearer ccs",
            "refresh_token": "cci-refresh",
            "expires_in": 3599,
            "valid_until": dt.datetime.now(dt.UTC) + dt.timedelta(hours=1),
        }

    monkeypatch.setattr(api, "_login_with_password", _cci_login)
    token = api.login("user@example.test", TOKEN_SHAPED_PASSWORD, None)

    assert seen["password"] == TOKEN_SHAPED_PASSWORD
    assert token.access_token == "Bearer ccs"


def test_token_without_cci_fields_is_migrated_by_full_login(monkeypatch) -> None:
    api = _api(monkeypatch)
    calls = []
    monkeypatch.setattr(
        api,
        "login",
        lambda user, password, pin=None: calls.append((user, password, pin)) or "new",
    )
    stale = Token(
        username="user@example.test",
        password="s3cret-test-password",
        pin="4321",
        access_token="Bearer old",
        refresh_token="legacy-refresh",
        device_id="device",
    )

    assert api.refresh_access_token(stale) == "new"
    assert calls == [("user@example.test", "s3cret-test-password", "4321")]
