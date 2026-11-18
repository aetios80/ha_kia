"""Signin User-Agent, redirect classification and log hygiene (no network)."""

import base64
import logging
from pathlib import Path
import sys

import pytest
import requests


COMPONENT_ROOT = Path(__file__).parent.parent / "custom_components" / "kia_uvo"
VENDOR = COMPONENT_ROOT / "_vendor" / "hyundai_kia_connect_api"


from custom_components.kia_uvo._vendor.hyundai_kia_connect_api import (
    http as http_module,
)
from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.exceptions import (
    AuthenticationError,
    AuthenticationInvalidCredentialsError,
    AuthenticationRedirectError,
    AuthenticationServiceError,
    AuthenticationSigninError,
    RequestTimeoutError,
)
from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.KiaUvoApiEU import (
    KiaUvoApiEU,
    SIGNIN_UA_APP_SUFFIX,
    USER_AGENT_MOZILLA,
)

REGION_EUROPE = 1
BRAND_KIA = 1
USERNAME = "user@example.test"
LOGIN_PAGE = (
    "https://idpconnect-eu.kia.com/auth/api/v2/user/oauth2/authorize"
    "?response_type=code&state=SENTINEL_STATE_VALUE"
)


def _b64(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


class _Resp:
    def __init__(self, status=200, text="", url="", headers=None, payload=None):
        self.status_code = status
        self.text = text
        self.url = url
        self.headers = headers or {}
        self._payload = payload or {}

    def json(self):
        return self._payload


def _session_factory(signin: _Resp, captured: dict):
    class _FakeSession:
        def __init__(self):
            self.headers = {}

        def get(self, url, **_kwargs):
            captured.setdefault("user_agent", self.headers.get("User-Agent"))
            if url.endswith("/certs"):
                return _Resp(
                    payload={
                        "retValue": {
                            "kid": "kid",
                            "n": _b64((1 << 1023) + 1),
                            "e": _b64(65537),
                        }
                    }
                )
            return _Resp(url=url)

        def post(self, _url, **_kwargs):
            return signin

    return _FakeSession


def _login(monkeypatch, signin: _Resp, password="short-password"):
    captured: dict = {}
    api = KiaUvoApiEU(REGION_EUROPE, BRAND_KIA, "en")
    module = sys.modules[KiaUvoApiEU.__module__]
    monkeypatch.setattr(module, "ApiImplSession", _session_factory(signin, captured))
    return (
        api,
        captured,
        lambda: api._login_with_password_cci(USERNAME, password, "device-id"),
    )


def _redirect(location: str) -> _Resp:
    return _Resp(status=302, headers={"location": location})


def test_signin_user_agent_is_current_chrome_with_app_suffix(monkeypatch) -> None:
    _api, captured, run = _login(monkeypatch, _redirect(LOGIN_PAGE))
    with pytest.raises(AuthenticationRedirectError):
        run()

    user_agent = captured["user_agent"]
    assert user_agent.endswith("_CCS_APP_AOS")
    assert user_agent == USER_AGENT_MOZILLA + SIGNIN_UA_APP_SUFFIX
    for marker in ("Galaxy Nexus", "Chrome/18.", "Android 4.1", "AppleWebKit/535"):
        assert marker not in user_agent
    assert int(user_agent.split("Chrome/")[1].split(".")[0]) >= 100


def test_vendor_has_no_legacy_user_agent_copy() -> None:
    for path in VENDOR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "Galaxy Nexus" not in text, path.name
        assert "Chrome/18." not in text, path.name


def test_login_page_redirect_is_typed_and_warns_without_blaming_credentials(
    monkeypatch, caplog
) -> None:
    _api, _captured, run = _login(monkeypatch, _redirect(LOGIN_PAGE))
    with caplog.at_level(logging.WARNING):
        with pytest.raises(AuthenticationRedirectError) as excinfo:
            run()

    assert isinstance(excinfo.value, AuthenticationError)
    assert not isinstance(excinfo.value, AuthenticationInvalidCredentialsError)
    for text in (caplog.text, str(excinfo.value)):
        assert "login page" in text
        assert "User-Agent" in text
        assert "password" in text
        assert "SENTINEL_STATE_VALUE" not in text
        assert "idpconnect" not in text
    assert "outcome=login_page" in caplog.text


def test_invalid_credentials_error_description_is_a_distinct_exception(
    monkeypatch,
) -> None:
    location = (
        "https://oneapp.kia.com/redirect?error=access_denied"
        "&error_description=Invalid%20Credentials"
    )
    _api, _captured, run = _login(monkeypatch, _redirect(location))
    with pytest.raises(AuthenticationInvalidCredentialsError) as excinfo:
        run()
    assert isinstance(excinfo.value, AuthenticationSigninError)


def test_other_idp_error_is_counted_like_a_redirect_with_sanitised_code_only(
    monkeypatch, caplog
) -> None:
    location = (
        "https://oneapp.kia.com/redirect?error=server_error"
        "&error_description=SENTINEL_FREE_TEXT"
    )
    _api, _captured, run = _login(monkeypatch, _redirect(location))
    with caplog.at_level(logging.WARNING):
        with pytest.raises(AuthenticationRedirectError) as excinfo:
            run()
    assert not isinstance(excinfo.value, AuthenticationInvalidCredentialsError)
    assert "server_error" in str(excinfo.value)
    assert "SENTINEL_FREE_TEXT" not in str(excinfo.value) + caplog.text


def test_signin_server_error_is_service_error_not_credentials(monkeypatch) -> None:
    _api, _captured, run = _login(monkeypatch, _Resp(status=503, text="body"))
    with pytest.raises(AuthenticationServiceError):
        run()


def test_unexpected_redirect_does_not_leak_the_location(monkeypatch, caplog) -> None:
    location = "https://example.test/elsewhere?x=SENTINEL_CODE&y=SENTINEL_TOKEN"
    _api, _captured, run = _login(monkeypatch, _redirect(location))
    with caplog.at_level(logging.WARNING):
        with pytest.raises(AuthenticationRedirectError) as excinfo:
            run()
    combined = caplog.text + str(excinfo.value)
    assert "SENTINEL" not in combined
    assert "example.test" not in combined


def test_long_password_gets_hint_without_length_or_password(monkeypatch, caplog) -> None:
    password = "p" * 27
    _api, _captured, run_long = _login(monkeypatch, _redirect(LOGIN_PAGE), password)
    with caplog.at_level(logging.WARNING):
        with pytest.raises(AuthenticationRedirectError) as excinfo:
            run_long()
    combined = caplog.text + str(excinfo.value)
    assert "longer than 20" in combined
    assert password not in combined
    assert "27" not in combined

    _api, _captured, run_short = _login(monkeypatch, _redirect(LOGIN_PAGE), "p" * 20)
    with pytest.raises(AuthenticationRedirectError) as excinfo:
        run_short()
    assert "longer than 20" not in str(excinfo.value)


def test_timeout_message_has_host_and_path_but_no_query(monkeypatch) -> None:
    def _timeout(_self, _method, _url, **_kwargs):
        raise requests.exceptions.Timeout(
            "HTTPSConnectionPool: Read timed out. url=?code=SENTINEL_CODE"
        )

    monkeypatch.setattr(requests.Session, "request", _timeout)
    with pytest.raises(RequestTimeoutError) as excinfo:
        http_module.http_request(
            "POST", "https://cci-api-eu.kia.com/auth/v1/token?code=SENTINEL_CODE"
        )
    message = str(excinfo.value)
    assert "cci-api-eu.kia.com/auth/v1/token" in message
    assert "SENTINEL_CODE" not in message
    assert "?" not in message


def test_connection_error_message_has_no_query(monkeypatch) -> None:
    def _fail(_self, _method, _url, **_kwargs):
        raise requests.exceptions.ConnectionError("Max retries ... ?code=SENTINEL_CODE")

    monkeypatch.setattr(requests.Session, "request", _fail)
    with pytest.raises(requests.exceptions.ConnectionError) as excinfo:
        http_module.http_request(
            "POST", "https://cci-api-eu.kia.com/auth/v1/token?code=SENTINEL_CODE"
        )
    assert "SENTINEL_CODE" not in str(excinfo.value)
    assert "cci-api-eu.kia.com/auth/v1/token" in str(excinfo.value)


def test_signin_waf_block_is_a_block_not_a_credentials_answer(monkeypatch) -> None:
    from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.exceptions import (
        AuthenticationBlockedError,
    )

    for signin in (
        _Resp(status=403, text="blocked"),
        _Resp(status=429, text="slow down"),
        _redirect("https://idpconnect-eu.kia.com/error?status=400"),
    ):
        _api, _captured, run = _login(monkeypatch, signin)
        with pytest.raises(AuthenticationBlockedError) as excinfo:
            run()
        assert not isinstance(excinfo.value, AuthenticationSigninError)


def test_generic_signin_4xx_is_counted_not_an_immediate_reauth(monkeypatch) -> None:
    for status in (400, 401, 404):
        _api, _captured, run = _login(monkeypatch, _Resp(status=status, text="x"))
        with pytest.raises(AuthenticationRedirectError) as excinfo:
            run()
        assert not isinstance(excinfo.value, AuthenticationInvalidCredentialsError)
        assert not isinstance(excinfo.value, AuthenticationSigninError)


def test_unexpected_signin_status_is_counted_with_a_fixed_warning(
    monkeypatch, caplog
) -> None:
    for status in (200, 301):
        caplog.records.clear()
        _api, _captured, run = _login(
            monkeypatch,
            _Resp(status=status, text="<html>SENTINEL_PAGE</html>"),
        )
        with caplog.at_level(logging.WARNING):
            with pytest.raises(AuthenticationRedirectError) as excinfo:
                run()
        assert not isinstance(excinfo.value, AuthenticationSigninError)
        assert "outcome=unexpected_status" in caplog.text
        assert "SENTINEL_PAGE" not in caplog.text + str(excinfo.value)
