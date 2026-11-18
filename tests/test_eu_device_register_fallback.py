"""Full login survives a failing legacy device register (upstream #1342)."""

import datetime as dt
import logging
import uuid

import pytest

from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.exceptions import (
    AuthenticationError,
    DeviceIDError,
)
from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.KiaUvoApiEU import (
    KiaUvoApiEU,
)

USERNAME = "user@example.test"
PASSWORD = "s3cret-test-password"


def _api(monkeypatch, register_error: Exception) -> KiaUvoApiEU:
    api = KiaUvoApiEU(1, 1, "en")
    seen = {}

    def _register(_stamp):
        raise register_error

    def _login_with_password(_user, _password, device_id, *_cycle):
        seen["device_id"] = device_id
        return {
            "access_token": "Bearer ccs",
            "refresh_token": "cci-refresh",
            "expires_in": 3599,
            "valid_until": dt.datetime.now(dt.UTC) + dt.timedelta(hours=1),
        }

    monkeypatch.setattr(api, "_get_stamp", lambda: "stamp")
    monkeypatch.setattr(api, "_get_device_id", _register)
    monkeypatch.setattr(api, "_get_cookies", lambda: {})
    monkeypatch.setattr(api, "_set_session_language", lambda _cookies: None)
    monkeypatch.setattr(api, "_login_with_password", _login_with_password)
    api.seen = seen
    return api


def test_register_failure_falls_back_to_random_persisted_device_id(
    monkeypatch, caplog
) -> None:
    api = _api(monkeypatch, DeviceIDError("register rejected"))
    with caplog.at_level(logging.WARNING):
        token = api.login(USERNAME, PASSWORD, None)

    assert uuid.UUID(token.device_id).version == 4
    assert api.seen["device_id"] == token.device_id
    assert "DeviceIDError" in caplog.text
    assert token.device_id not in caplog.text
    assert "register rejected" not in caplog.text


def test_register_response_without_resmsg_falls_back(monkeypatch) -> None:
    api = _api(monkeypatch, KeyError("resMsg"))
    token = api.login(USERNAME, PASSWORD, None)
    assert uuid.UUID(token.device_id).version == 4


def test_register_authentication_error_falls_back(monkeypatch) -> None:
    api = _api(monkeypatch, AuthenticationError("nope"))
    assert uuid.UUID(api.login(USERNAME, PASSWORD, None).device_id).version == 4


def test_missing_password_still_fails_before_register(monkeypatch) -> None:
    api = _api(monkeypatch, DeviceIDError("x"))
    called = []
    monkeypatch.setattr(api, "_get_device_id", lambda _s: called.append(1))
    with pytest.raises(AuthenticationError):
        api.login(USERNAME, "", None)
    assert not called
