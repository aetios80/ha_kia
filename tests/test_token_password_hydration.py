"""Regression tests for token password hydration and missing-password handling."""

from unittest.mock import ANY, MagicMock

import pytest

from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.exceptions import (
    AuthenticationError,
)
from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.KiaUvoApiEU import (
    KiaUvoApiEU,
)
from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.Token import Token
from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.VehicleManager import (
    VehicleManager,
)

REGION_EUROPE = 1  # key of REGIONS for Europe
BRAND_KIA = 1  # key of BRANDS for Kia
PASSWORD = "s3cret-test-password"
PIN = "4321"
USERNAME = "user@example.test"


def _make_cci_token() -> Token:
    return Token(
        username=USERNAME,
        password=PASSWORD,
        pin=PIN,
        access_token="access",
        refresh_token="refresh",
        cci_access_token="cci-access",
        device_id="device",
    )


def test_hydrated_token_restores_password_after_round_trip() -> None:
    restored = Token.from_dict(_make_cci_token().to_dict())
    assert restored.password is None

    manager = VehicleManager(
        region=REGION_EUROPE,
        brand=BRAND_KIA,
        username=USERNAME,
        password=PASSWORD,
        pin=PIN,
        token=restored,
    )

    assert manager.token.username == USERNAME
    assert manager.token.password == PASSWORD
    assert manager.token.pin == PIN


def test_cci_refresh_failure_falls_back_to_login_with_password(monkeypatch) -> None:
    api = KiaUvoApiEU(REGION_EUROPE, BRAND_KIA, "en")
    restored = Token.from_dict(_make_cci_token().to_dict())
    restored.username = USERNAME
    restored.password = PASSWORD
    restored.pin = PIN

    def _fail(_token, *_args):
        raise RuntimeError("boom")

    login = MagicMock(return_value="new-token")
    monkeypatch.setattr(api, "_refresh_cci_token", _fail)
    monkeypatch.setattr(api, "login", login)

    assert api.refresh_access_token(restored) == "new-token"
    login.assert_called_once_with(USERNAME, PASSWORD, PIN, cycle=ANY)


def test_login_without_password_raises_authentication_error() -> None:
    api = KiaUvoApiEU(REGION_EUROPE, BRAND_KIA, "en")

    for missing in (None, ""):
        with pytest.raises(AuthenticationError) as excinfo:
            api.login(USERNAME, missing, PIN)
        assert PIN not in str(excinfo.value)


def test_to_dict_excludes_credentials() -> None:
    data = _make_cci_token().to_dict()

    assert data.keys().isdisjoint({"username", "password", "pin"})
    assert PASSWORD not in repr(data)
    assert USERNAME not in repr(data)
    assert PIN not in repr(data)


def test_token_repr_excludes_password_and_pin() -> None:
    text = repr(_make_cci_token())

    assert PASSWORD not in text
    assert PIN not in text
    assert "password" not in text
    assert "pin=" not in text


def test_refresh_warning_logs_type_and_status_only(monkeypatch, caplog) -> None:
    api = KiaUvoApiEU(REGION_EUROPE, BRAND_KIA, "en")
    token = _make_cci_token()

    class _Response:
        status_code = 401
        text = "response-body-must-not-leak"

    class _HttpError(Exception):
        response = _Response()

    def _fail(_token, *_args):
        raise _HttpError("response-body-must-not-leak")

    monkeypatch.setattr(api, "_refresh_cci_token", _fail)
    monkeypatch.setattr(api, "login", MagicMock(return_value="new-token"))

    with caplog.at_level("WARNING"):
        api.refresh_access_token(token)

    assert "_HttpError" in caplog.text
    assert "HTTP 401" in caplog.text
    assert "response-body-must-not-leak" not in caplog.text
    assert "cci-access" not in caplog.text
