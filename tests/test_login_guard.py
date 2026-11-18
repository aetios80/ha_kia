"""Login limit: one full login per 6 hours, reauth after 2 rejected logins."""

import json
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

from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.exceptions import (  # noqa: E402
    APIError,
    AuthenticationBlockedError,
    AuthenticationCciTokenExchangeError,
    AuthenticationError,
    AuthenticationInvalidCredentialsError,
    AuthenticationRedirectError,
    AuthenticationServiceError,
    ConsentRequiredError,
    LoginAttemptFailedError,
    LoginThrottledError,
    RequestTimeoutError,
)
from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.KiaUvoApiEU import (  # noqa: E402
    KiaUvoApiEU,
)
from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.login_guard import (  # noqa: E402
    LOGIN_FAILURE_LIMIT,
    LOGIN_WINDOW_SECONDS,
    LoginGuard,
)
from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.Token import (  # noqa: E402
    Token,
)

NOW = 1_800_000_000.0
HOUR = 3600.0


class _Clock:
    def __init__(self, now: float = NOW) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def _api(monkeypatch, guard, login_results):
    """KiaUvoApiEU whose CCI refresh always fails and whose login is scripted."""
    api = KiaUvoApiEU(1, 1, "en")
    api.login_guard = guard
    calls = []
    script = list(login_results)

    def _login(username, password, pin=None):
        calls.append((username, password, pin))
        item = script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def _refresh_fails(_token):
        raise RuntimeError("refresh failed")

    monkeypatch.setattr(api, "login", _login)
    monkeypatch.setattr(api, "_refresh_cci_token", _refresh_fails)
    api.login_calls = calls
    return api


def _token(cci: bool = True) -> Token:
    return Token(
        username="user@example.test",
        password="s3cret-test-password",
        pin="4321",
        access_token="Bearer old",
        refresh_token="rt",
        device_id="device",
        cci_access_token="cci" if cci else None,
    )


def test_limit_exceptions_are_not_authentication_errors() -> None:
    assert issubclass(LoginThrottledError, APIError)
    assert issubclass(LoginAttemptFailedError, APIError)
    assert not issubclass(LoginThrottledError, AuthenticationError)
    assert not issubclass(LoginAttemptFailedError, AuthenticationError)


def test_without_a_guard_the_fallback_login_is_unlimited(monkeypatch) -> None:
    api = _api(monkeypatch, None, ["t1", "t2", "t3"])
    for _ in range(3):
        api.refresh_access_token(_token())
    assert len(api.login_calls) == 3


def test_one_full_login_per_window(monkeypatch) -> None:
    clock = _Clock()
    guard = LoginGuard(clock=clock)
    api = _api(monkeypatch, guard, ["t1", "t2"])

    assert api.refresh_access_token(_token()) == "t1"
    assert guard.dirty and guard.last_attempt_at == NOW

    # Every 10 minutes, as the poll would: blocked before any login call.
    for minutes in (10, 20, 30, 350):
        clock.now = NOW + minutes * 60
        with pytest.raises(LoginThrottledError) as excinfo:
            api.refresh_access_token(_token())
        assert not isinstance(excinfo.value, AuthenticationError)
        assert excinfo.value.retry_after == pytest.approx(
            LOGIN_WINDOW_SECONDS - minutes * 60
        )
    assert len(api.login_calls) == 1

    clock.now = NOW + LOGIN_WINDOW_SECONDS
    assert api.refresh_access_token(_token()) == "t2"
    assert len(api.login_calls) == 2


def test_token_without_cci_fields_is_limited_too(monkeypatch) -> None:
    clock = _Clock()
    api = _api(monkeypatch, LoginGuard(clock=clock), ["t1"])
    api.refresh_access_token(_token(cci=False))
    with pytest.raises(LoginThrottledError):
        api.refresh_access_token(_token(cci=False))
    assert len(api.login_calls) == 1


def test_throttled_login_sends_no_request(monkeypatch) -> None:
    clock = _Clock()
    guard = LoginGuard(last_attempt_at=NOW - 60, clock=clock)
    api = KiaUvoApiEU(1, 1, "en")
    api.login_guard = guard

    def _no_network(*_args, **_kwargs):
        raise AssertionError("network used while throttled")

    module = sys.modules[KiaUvoApiEU.__module__]
    monkeypatch.setattr(module, "http_request", _no_network)
    monkeypatch.setattr(module, "ApiImplSession", _no_network)
    monkeypatch.setattr(api, "_get_stamp", _no_network)
    monkeypatch.setattr(api, "_refresh_cci_token", lambda _t: 1 / 0)
    with pytest.raises(LoginThrottledError):
        api.refresh_access_token(_token())


def test_redirect_counts_and_second_rejection_demands_reauth(monkeypatch) -> None:
    clock = _Clock()
    guard = LoginGuard(clock=clock)
    api = _api(
        monkeypatch,
        guard,
        [AuthenticationRedirectError("login page"), AuthenticationRedirectError("again")],
    )

    with pytest.raises(LoginAttemptFailedError) as first:
        api.refresh_access_token(_token())
    assert not isinstance(first.value, AuthenticationError)
    assert guard.failures == 1

    clock.now = NOW + LOGIN_WINDOW_SECONDS
    with pytest.raises(AuthenticationRedirectError):
        api.refresh_access_token(_token())
    assert guard.failures == LOGIN_FAILURE_LIMIT
    assert len(api.login_calls) == 2

    # Past the limit: reauthentication is required, nothing is attempted even
    # after the window.
    clock.now = NOW + 3 * LOGIN_WINDOW_SECONDS
    with pytest.raises(AuthenticationError):
        api.refresh_access_token(_token())
    assert len(api.login_calls) == 2


def test_invalid_credentials_demand_reauth_at_the_first_error(monkeypatch) -> None:
    guard = LoginGuard(clock=_Clock())
    api = _api(
        monkeypatch, guard, [AuthenticationInvalidCredentialsError("invalid credentials")]
    )
    with pytest.raises(AuthenticationInvalidCredentialsError):
        api.refresh_access_token(_token())
    assert len(api.login_calls) == 1


def test_consent_required_still_demands_reauth(monkeypatch) -> None:
    api = _api(monkeypatch, LoginGuard(clock=_Clock()), [ConsentRequiredError("consent")])
    with pytest.raises(ConsentRequiredError):
        api.refresh_access_token(_token())


def test_server_side_failures_neither_count_nor_demand_reauth(monkeypatch) -> None:
    for error in (
        AuthenticationServiceError("HTTP 503"),
        AuthenticationCciTokenExchangeError("HTTP 502"),
        AuthenticationBlockedError("waf"),
    ):
        clock = _Clock()
        guard = LoginGuard(clock=clock)
        api = _api(monkeypatch, guard, [error])
        with pytest.raises(LoginAttemptFailedError) as excinfo:
            api.refresh_access_token(_token())
        assert not isinstance(excinfo.value, AuthenticationError)
        assert guard.failures == 0
        # Still bound by the one-per-window limit.
        with pytest.raises(LoginThrottledError):
            api.refresh_access_token(_token())
        assert len(api.login_calls) == 1


def test_network_errors_propagate_unchanged_and_do_not_count(monkeypatch) -> None:
    guard = LoginGuard(clock=_Clock())
    api = _api(monkeypatch, guard, [RequestTimeoutError("timed out")])
    with pytest.raises(RequestTimeoutError):
        api.refresh_access_token(_token())
    assert guard.failures == 0
    assert guard.dirty  # the attempt used the window and must be persisted
    with pytest.raises(LoginThrottledError):
        api.refresh_access_token(_token())


def test_successful_login_clears_the_failure_count(monkeypatch) -> None:
    clock = _Clock()
    guard = LoginGuard(clock=clock)
    api = _api(monkeypatch, guard, [AuthenticationRedirectError("x"), "ok"])
    with pytest.raises(LoginAttemptFailedError):
        api.refresh_access_token(_token())
    assert guard.failures == 1
    clock.now += LOGIN_WINDOW_SECONDS
    assert api.refresh_access_token(_token()) == "ok"
    assert guard.failures == 0


def test_state_survives_a_restart_and_a_new_guard_resets_it(monkeypatch) -> None:
    clock = _Clock()
    guard = LoginGuard(clock=clock)
    api = _api(monkeypatch, guard, [AuthenticationRedirectError("x")])
    with pytest.raises(LoginAttemptFailedError):
        api.refresh_access_token(_token())

    stored = json.loads(json.dumps(guard.to_dict()))  # what the entry persists
    assert set(stored) == {"last_attempt_at", "failures"}

    clock.now += 600  # Home Assistant restarts ten minutes later
    restarted = LoginGuard.from_dict(stored, clock=clock)
    assert restarted.failures == 1
    with pytest.raises(LoginThrottledError):
        restarted.begin_attempt()

    # A successful reauth writes a fresh state: the window and counter reset.
    reset = LoginGuard.from_dict(LoginGuard(clock=clock).to_dict(), clock=clock)
    reset.begin_attempt()
    assert reset.failures == 0


def test_persisted_state_is_validated() -> None:
    clock = _Clock()
    for bad in (None, "x", [], 5, {"last_attempt_at": "1", "failures": "2"}):
        guard = LoginGuard.from_dict(bad, clock=clock)
        assert guard.last_attempt_at == 0.0 and guard.failures == 0

    booleans = LoginGuard.from_dict({"last_attempt_at": True, "failures": True}, clock=clock)
    assert booleans.last_attempt_at == 0.0 and booleans.failures == 0

    for not_finite in (float("nan"), float("inf"), -5):
        guard = LoginGuard.from_dict({"last_attempt_at": not_finite}, clock=clock)
        assert guard.last_attempt_at == 0.0

    clamped = LoginGuard.from_dict({"failures": 99}, clock=clock)
    assert clamped.failures == LOGIN_FAILURE_LIMIT
    assert LoginGuard.from_dict({"failures": -3}, clock=clock).failures == 0


def test_future_timestamp_is_brought_back_to_now() -> None:
    clock = _Clock()
    guard = LoginGuard.from_dict({"last_attempt_at": NOW + 10 * HOUR}, clock=clock)
    assert guard.last_attempt_at == NOW
    assert guard.dirty
    assert guard.remaining_seconds() == LOGIN_WINDOW_SECONDS


def test_unrelated_keys_are_ignored() -> None:
    guard = LoginGuard.from_dict(
        {"last_attempt_at": 0, "failures": 0, "username": "user@example.test"},
        clock=_Clock(),
    )
    assert set(guard.to_dict()) == {"last_attempt_at", "failures"}
