"""Signed CCI exchanges, gate-only legacy fallback and log hygiene (no network).

http_request is replaced at the KiaUvoApiEU module boundary; nothing here
opens a socket.
"""

import json
import logging
from pathlib import Path
import sys
from types import ModuleType

import pytest


COMPONENT_ROOT = Path(__file__).parent.parent / "custom_components" / "kia_uvo"


def _register_namespace(name: str, path: Path) -> None:
    package = ModuleType(name)
    package.__path__ = [str(path)]
    sys.modules.setdefault(name, package)


_register_namespace("custom_components", COMPONENT_ROOT.parent)
_register_namespace("custom_components.kia_uvo", COMPONENT_ROOT)
_register_namespace("custom_components.kia_uvo._vendor", COMPONENT_ROOT / "_vendor")

from custom_components.kia_uvo._vendor.hyundai_kia_connect_api import (  # noqa: E402
    cci_fingerprint as fp,
)
from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.exceptions import (  # noqa: E402
    AuthenticationCcsTokenExchangeError,
    AuthenticationCciTokenExchangeError,
    AuthenticationTokenExchangeError,
    RequestTimeoutError,
)
from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.KiaUvoApiEU import (  # noqa: E402
    KiaUvoApiEU,
)
from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.Token import (  # noqa: E402
    Token,
)

GATE_BODY = '{"code":9035,"message":"gate"}'
SENTINEL_CODE = "SENTINEL_AUTH_CODE"
SENTINEL_DEVICE = "SENTINEL-DEVICE-ID"


class _Resp:
    def __init__(self, status: int, text: str = "", headers=None):
        self.status_code = status
        self.text = text
        self.headers = headers or {}

    def json(self):
        return json.loads(self.text)


class _Http:
    """Records calls and plays a scripted sequence of responses or errors."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls = []

    def __call__(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _api(monkeypatch, *script):
    api = KiaUvoApiEU(1, 1, "en")
    http = _Http(*script)
    monkeypatch.setattr(sys.modules[KiaUvoApiEU.__module__], "http_request", http)
    return api, http


def _assert_valid_signature(kwargs: dict, body: str = "") -> None:
    headers = kwargs["headers"]
    assert headers["X-Fingerprint"] == fp.compute_x_fingerprint(headers, body)
    assert headers["X-Timestamp"].isdigit()


def test_auth_code_exchange_is_signed_android_identity(monkeypatch) -> None:
    api, http = _api(monkeypatch, _Resp(200, '{"accessToken":"cci"}'))
    result = api._exchange_auth_code_for_cci_tokens(SENTINEL_DEVICE, SENTINEL_CODE)

    assert result == {"accessToken": "cci"}
    assert len(http.calls) == 1
    _method, url, kwargs = http.calls[0]
    assert url == "https://cci-api-eu.kia.com/auth/v1/token"
    assert kwargs["params"] == {"code": SENTINEL_CODE}
    _assert_valid_signature(kwargs)
    headers = kwargs["headers"]
    assert headers["client-os-code"] == "android"
    assert headers["client-version"] == fp.CLIENT_VERSION
    assert headers["client-name"] == "KiaEU"
    assert headers["User-Agent"] == "okhttp/4.12.0"


def test_gate_rejection_falls_back_to_legacy_once(monkeypatch) -> None:
    api, http = _api(
        monkeypatch, _Resp(400, GATE_BODY), _Resp(200, '{"accessToken":"legacy"}')
    )
    assert api._exchange_auth_code_for_cci_tokens("dev", "code")["accessToken"] == (
        "legacy"
    )
    assert [c[1] for c in http.calls] == [
        "https://cci-api-eu.kia.com/auth/v1/token",
        "https://cci-api-eu.kia.com/domain/api/v1/auth/token",
    ]
    legacy_headers = http.calls[1][2]["headers"]
    assert "X-Fingerprint" not in legacy_headers
    assert legacy_headers["client-os-code"] == "ios"


def test_signed_and_legacy_identities_stay_distinct(monkeypatch) -> None:
    api = KiaUvoApiEU(1, 1, "en")
    signed = api._cci_fp_headers("dev")
    legacy = api._get_cci_headers("dev")
    assert signed["client-os-code"] == "android"
    assert legacy["client-os-code"] == "ios"
    assert signed["client-version"] == fp.CLIENT_VERSION
    assert signed["X-Fingerprint"] == fp.compute_x_fingerprint(signed)


def test_no_fallback_for_non_gate_failures(monkeypatch) -> None:
    cases = (
        _Resp(400, '{"code":9013,"message":"invalid code"}'),
        _Resp(400, '{"code":9030,"message":"token expired"}'),
        _Resp(500, GATE_BODY),
        _Resp(502, "<html>bad gateway</html>"),
        _Resp(400, "not json"),
        _Resp(400, '{"message":"no code"}'),
    )
    for response in cases:
        api, http = _api(monkeypatch, response)
        with pytest.raises(AuthenticationCciTokenExchangeError):
            api._exchange_auth_code_for_cci_tokens("dev", "code")
        assert len(http.calls) == 1, response.text


def test_no_fallback_on_timeout(monkeypatch) -> None:
    api, http = _api(monkeypatch, RequestTimeoutError("timed out"))
    with pytest.raises(RequestTimeoutError):
        api._exchange_auth_code_for_cci_tokens("dev", "code")
    assert len(http.calls) == 1


def test_legacy_failure_after_gate_rejection_stops(monkeypatch) -> None:
    api, http = _api(monkeypatch, _Resp(400, GATE_BODY), _Resp(400, GATE_BODY))
    with pytest.raises(AuthenticationCciTokenExchangeError):
        api._exchange_auth_code_for_cci_tokens("dev", "code")
    assert len(http.calls) == 2


def test_at_most_one_legacy_fallback_per_cycle(monkeypatch) -> None:
    api, http = _api(
        monkeypatch,
        _Resp(400, GATE_BODY),
        _Resp(200, '{"accessToken":"legacy"}'),
        _Resp(400, GATE_BODY),
    )
    api._exchange_auth_code_for_cci_tokens("dev", "code")
    with pytest.raises(AuthenticationCcsTokenExchangeError):
        api._exchange_ccs_token("dev", "Bearer cci", "non-ccs", "exchangeable")
    # 2 calls for the code exchange, only the signed attempt for the CCS one.
    assert len(http.calls) == 3
    assert http.calls[2][1].endswith("/auth/v1/token-exchange")


def test_ccs_exchange_is_signed_with_token_headers(monkeypatch) -> None:
    api, http = _api(
        monkeypatch, _Resp(200, '{"accessToken":"ccs","expiresTime":3600}')
    )
    token, _valid_until = api._exchange_ccs_token(
        "dev", "Bearer cci", "non-ccs", "exchangeable"
    )
    assert token == "ccs"
    _method, url, kwargs = http.calls[0]
    assert url == "https://cci-api-eu.kia.com/auth/v1/token-exchange"
    assert kwargs["params"] == {"serviceType": "CCS"}
    _assert_valid_signature(kwargs)
    headers = kwargs["headers"]
    assert headers["authorization"] == "Bearer cci"
    assert headers["Authentication"] == "non-ccs"
    assert headers["exchangeable-token"] == "exchangeable"
    assert headers["non-ccs-token"] == "non-ccs"


def test_ccs_exchange_falls_back_only_on_gate(monkeypatch) -> None:
    api, http = _api(
        monkeypatch,
        _Resp(400, GATE_BODY),
        _Resp(200, '{"accessToken":"ccs-legacy","expiresTime":86400}'),
    )
    token, _ = api._exchange_ccs_token("dev", "Bearer cci", "non-ccs", "")
    assert token == "ccs-legacy"
    assert http.calls[1][1].endswith("/domain/api/v1/auth/token-exchange")
    assert "X-Fingerprint" not in http.calls[1][2]["headers"]

    api, http = _api(monkeypatch, _Resp(500, "boom"))
    with pytest.raises(AuthenticationCcsTokenExchangeError):
        api._exchange_ccs_token("dev", "Bearer cci", "non-ccs", "")
    assert len(http.calls) == 1


def _token() -> Token:
    return Token(
        username="u",
        password="p",
        access_token="Bearer ccs",
        refresh_token="cci-rt",
        device_id="dev-1",
        cci_access_token="Bearer cci-at",
        exchangeable_token="ex-at",
        exchangeable_refresh_token="ex-rt",
        non_ccs_token="non-ccs",
        non_ccs_refresh_token="non-ccs-rt",
        id_token="id-t",
    )


REFRESH_OK = json.dumps(
    {
        "accessToken": "cci-new",
        "refreshToken": "rt-new",
        "nonCcsToken": "nc-new",
        "exchangeableAccessToken": "ex-new",
        "exchangeableRefreshToken": "exr-new",
        "nonCcsRefreshToken": "ncr-new",
        "idToken": "id-new",
    }
)


def test_refresh_is_signed_over_the_exact_seven_field_body(monkeypatch) -> None:
    api, http = _api(monkeypatch, _Resp(200, REFRESH_OK))
    monkeypatch.setattr(api, "_exchange_ccs_token", lambda *a: ("ccs", None))
    api._refresh_cci_token(_token())

    _method, url, kwargs = http.calls[0]
    assert url == "https://cci-api-eu.kia.com/auth/v2/token-refresh"
    assert "json" not in kwargs
    payload = kwargs["data"]
    assert isinstance(payload, str)
    assert list(json.loads(payload)) == [
        "accessToken",
        "refreshToken",
        "exchangeableAccessToken",
        "exchangeableRefreshToken",
        "nonCcsToken",
        "nonCcsRefreshToken",
        "idToken",
    ]
    assert json.loads(payload)["accessToken"] == "cci-at"
    _assert_valid_signature(kwargs, payload)
    assert kwargs["headers"]["Content-Type"] == "application/json"
    assert kwargs["headers"]["client-os-code"] == "android"


def test_refresh_falls_back_to_legacy_only_on_gate(monkeypatch) -> None:
    api, http = _api(monkeypatch, _Resp(400, GATE_BODY), _Resp(200, REFRESH_OK))
    monkeypatch.setattr(api, "_exchange_ccs_token", lambda *a: ("ccs", None))
    api._refresh_cci_token(_token())
    assert http.calls[1][1] == "https://cci-api-eu.kia.com/domain/api/v2/auth/token-refresh"
    assert set(http.calls[1][2]["json"]) >= {"idToken", "nonCcsRefreshToken"}
    assert http.calls[1][2]["headers"]["client-os-code"] == "ios"

    api, http = _api(monkeypatch, _Resp(401, '{"code":9030}'))
    with pytest.raises(AuthenticationTokenExchangeError):
        api._refresh_cci_token(_token())
    assert len(http.calls) == 1


def test_logs_and_errors_carry_no_secrets(monkeypatch, caplog) -> None:
    api, http = _api(
        monkeypatch,
        _Resp(400, GATE_BODY),
        _Resp(400, '{"code":9013,"echo":"SENTINEL_BODY_TEXT"}'),
    )
    with caplog.at_level(logging.WARNING):
        with pytest.raises(AuthenticationCciTokenExchangeError) as excinfo:
            api._exchange_auth_code_for_cci_tokens(SENTINEL_DEVICE, SENTINEL_CODE)

    first_headers = http.calls[0][2]["headers"]
    combined = caplog.text + str(excinfo.value)
    for secret in (
        SENTINEL_CODE,
        SENTINEL_DEVICE,
        "SENTINEL_BODY_TEXT",
        first_headers["X-Fingerprint"],
        first_headers["App-Request-Id"],
        first_headers["X-Timestamp"],
    ):
        assert secret not in combined
    assert "endpoint=auth_code_exchange" in caplog.text


def test_ccs_valid_until_is_pulled_in_by_the_rotation_margin(monkeypatch) -> None:
    import datetime as dt

    from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.const import (
        CCI_TOKEN_REFRESH_MARGIN_SECONDS,
        CCI_TOKEN_ROTATION_FLOOR_SECONDS,
    )

    assert CCI_TOKEN_REFRESH_MARGIN_SECONDS == 360
    assert CCI_TOKEN_ROTATION_FLOOR_SECONDS == 300

    api, _http = _api(
        monkeypatch, _Resp(200, '{"accessToken":"ccs","expiresTime":3600}')
    )
    before = dt.datetime.now(dt.UTC)
    _token_value, valid_until = api._exchange_ccs_token("d", "c", "n", "e")
    after = dt.datetime.now(dt.UTC)
    offset = dt.timedelta(seconds=3600 - CCI_TOKEN_REFRESH_MARGIN_SECONDS)
    assert before + offset <= valid_until <= after + offset

    api, _http = _api(
        monkeypatch, _Resp(200, '{"accessToken":"ccs","expiresTime":200}')
    )
    before = dt.datetime.now(dt.UTC)
    _token_value, valid_until = api._exchange_ccs_token("d", "c", "n", "e")
    assert valid_until >= before + dt.timedelta(seconds=CCI_TOKEN_ROTATION_FLOOR_SECONDS)


def test_failed_exchange_logs_endpoint_status_and_int_code_only(
    monkeypatch, caplog
) -> None:
    cases = (
        (400, '{"code":9036,"message":"SENTINEL_MESSAGE"}', "status=400 code=9036"),
        (400, '{"code":9013,"message":"SENTINEL_MESSAGE"}', "status=400 code=9013"),
        (502, "<html>SENTINEL_MESSAGE</html>", "status=502 code=none"),
        (400, '{"code":"9036"}', "status=400 code=none"),
    )
    for status, body, expected in cases:
        caplog.records.clear()
        api, _http = _api(monkeypatch, _Resp(status, body))
        with caplog.at_level(logging.WARNING):
            # A gate code is retried once on the legacy route: give it a
            # second response so the final failure is what gets logged.
            if '"code":9036' in body and '"9036"' not in body:
                api, _http = _api(monkeypatch, _Resp(status, body), _Resp(status, body))
            with pytest.raises(AuthenticationCciTokenExchangeError):
                api._exchange_auth_code_for_cci_tokens("SENTINEL-DEVICE", "SENTINEL_CODE")
        text = caplog.text
        assert "exchange_failed endpoint=auth_code_exchange" in text
        assert expected in text
        for secret in ("SENTINEL_MESSAGE", "SENTINEL-DEVICE", "SENTINEL_CODE"):
            assert secret not in text


def test_failed_ccs_exchange_and_refresh_log_their_endpoint(monkeypatch, caplog) -> None:
    api, _http = _api(monkeypatch, _Resp(500, "boom"))
    with caplog.at_level(logging.WARNING):
        with pytest.raises(AuthenticationCcsTokenExchangeError):
            api._exchange_ccs_token("d", "c", "n", "e")
    assert "exchange_failed endpoint=ccs_token_exchange status=500 code=none" in caplog.text

    caplog.records.clear()
    api, _http = _api(monkeypatch, _Resp(401, '{"code":9030}'))
    with caplog.at_level(logging.WARNING):
        with pytest.raises(AuthenticationTokenExchangeError):
            api._refresh_cci_token(_token())
    assert "exchange_failed endpoint=token_refresh status=401 code=9030" in caplog.text
