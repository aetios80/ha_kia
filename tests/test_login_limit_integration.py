"""Coordinator and config flow behaviour of the login limit, with HA stubs.

The coordinator and config_flow modules are loaded under private names with
minimal Home Assistant stand-ins, then sys.modules is restored: nothing here
touches a real Home Assistant installation or the network.
"""

import asyncio
import datetime as dt
import importlib.util
from pathlib import Path
import sys
import time
from types import ModuleType
from unittest.mock import MagicMock

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
    AuthenticationError,
    LoginAttemptFailedError,
)
from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.login_guard import (  # noqa: E402
    LOGIN_WINDOW_SECONDS,
    LoginGuard,
)
from custom_components.kia_uvo._vendor.hyundai_kia_connect_api.Token import (  # noqa: E402
    Token,
)
from custom_components.kia_uvo.const import CONF_LOGIN_GUARD, CONF_TOKEN  # noqa: E402

USERNAME = "user@example.test"
PASSWORD = "s3cret-test-password"
CURRENT_ENTRY: list = [None]


class _HomeAssistantError(Exception):
    pass


class _ConfigEntryAuthFailed(_HomeAssistantError):
    pass


class _UpdateFailed(Exception):
    def __init__(self, *args, retry_after=None):
        super().__init__(*args)
        self.retry_after = retry_after


class _DataUpdateCoordinator:
    def __class_getitem__(cls, _item):
        return cls

    def __init__(self, hass, logger, *, name, update_interval=None):
        self.hass = hass
        self.config_entry = CURRENT_ENTRY[0]
        self.data = {}

    def async_set_updated_data(self, data):
        self.data = data


class _ConfigFlow:
    def __init_subclass__(cls, domain=None, **kwargs):
        super().__init_subclass__(**kwargs)

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_abort(self, **kwargs):
        return {"type": "abort", **kwargs}

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}

    def async_update_reload_and_abort(self, entry, data_updates=None, **kwargs):
        self.reload_data_updates = data_updates
        return {"type": "abort", "reason": "reconfigure_successful"}

    def _get_reconfigure_entry(self):
        return self.hass.entry


def _stub_modules() -> dict:
    def mod(name, **attrs):
        module = ModuleType(name)
        module.__dict__.update(attrs)
        return module

    dt_module = mod(
        "homeassistant.util.dt",
        now=lambda: dt.datetime.now(dt.UTC),
        utcnow=lambda: dt.datetime.now(dt.UTC),
        as_local=lambda value: value,
    )
    return {
        "homeassistant": mod("homeassistant"),
        "homeassistant.config_entries": mod(
            "homeassistant.config_entries",
            ConfigEntry=object,
            ConfigFlowResult=dict,
            ConfigFlow=_ConfigFlow,
            OptionsFlowWithReload=object,
            ConfigEntryState=MagicMock(),
        ),
        "homeassistant.const": mod(
            "homeassistant.const",
            CONF_PASSWORD="password",
            CONF_PIN="pin",
            CONF_REGION="region",
            CONF_SCAN_INTERVAL="scan_interval",
            CONF_USERNAME="username",
        ),
        "homeassistant.core": mod(
            "homeassistant.core", HomeAssistant=object, callback=lambda func: func
        ),
        "homeassistant.exceptions": mod(
            "homeassistant.exceptions",
            HomeAssistantError=_HomeAssistantError,
            ConfigEntryAuthFailed=_ConfigEntryAuthFailed,
        ),
        "homeassistant.helpers": mod("homeassistant.helpers"),
        "homeassistant.helpers.update_coordinator": mod(
            "homeassistant.helpers.update_coordinator",
            DataUpdateCoordinator=_DataUpdateCoordinator,
            UpdateFailed=_UpdateFailed,
        ),
        "homeassistant.helpers.selector": mod(
            "homeassistant.helpers.selector", selector=lambda *a, **k: None
        ),
        "homeassistant.util": mod("homeassistant.util", dt=dt_module),
        "homeassistant.util.dt": dt_module,
        "voluptuous": MagicMock(),
    }


def _load(filename: str, alias: str) -> ModuleType:
    stubs = _stub_modules()
    saved = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)
    try:
        spec = importlib.util.spec_from_file_location(
            f"custom_components.kia_uvo.{alias}", COMPONENT_ROOT / filename
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, original in saved.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


class _Hass:
    def __init__(self, entry=None):
        self.entry = entry
        self.config = MagicMock(language="en")
        self.config_entries = self
        self.updates = []
        self.reloads = []

    async def async_add_executor_job(self, func, *args):
        return func(*args)

    def async_update_entry(self, entry, data=None, **_kwargs):
        entry.data = data
        self.updates.append(data)

    async def async_reload(self, entry_id):
        self.reloads.append(entry_id)


class _Entry:
    entry_id = "entry-id"

    def __init__(self, data):
        self.data = data
        self.options = {}


def _entry_data(guard_state=None) -> dict:
    data = {
        "username": USERNAME,
        "password": PASSWORD,
        "pin": "4321",
        "region": 1,
        "brand": 1,
        CONF_TOKEN: Token(
            username=USERNAME, password=PASSWORD, access_token="Bearer old"
        ).to_dict(),
    }
    if guard_state is not None:
        data[CONF_LOGIN_GUARD] = guard_state
    return data


def _coordinator(behaviour, guard_state=None):
    module = _load("coordinator.py", "coordinator_under_test")

    class _FakeVehicleManager:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.login_guard = kwargs["login_guard"]
            self.token = kwargs["token"] or Token(username=USERNAME)
            self.vehicles = {}

        def check_and_refresh_token(self):
            return behaviour(self)

    module.VehicleManager = _FakeVehicleManager
    entry = _Entry(_entry_data(guard_state))
    CURRENT_ENTRY[0] = entry
    hass = _Hass(entry)
    coordinator = module.KiaConnectEuDataUpdateCoordinator(hass, entry)
    return module, coordinator, hass, entry


def _poll(coordinator):
    return asyncio.run(coordinator._async_update_data())


def test_throttled_poll_is_update_failed_with_remaining_time_not_reauth() -> None:
    guard_state = {"last_attempt_at": time.time() - 600, "failures": 0}

    def _refresh(manager):
        manager.login_guard.begin_attempt()

    _module, coordinator, _hass, _entry = _coordinator(_refresh, guard_state)
    with pytest.raises(_UpdateFailed) as excinfo:
        _poll(coordinator)
    assert not isinstance(excinfo.value, _ConfigEntryAuthFailed)
    expected = LOGIN_WINDOW_SECONDS - 600
    assert expected - 5 <= excinfo.value.retry_after <= expected


def test_attempt_failed_poll_is_update_failed() -> None:
    def _refresh(_manager):
        raise LoginAttemptFailedError("waf", retry_after=3000)

    _module, coordinator, _hass, _entry = _coordinator(_refresh)
    with pytest.raises(_UpdateFailed) as excinfo:
        _poll(coordinator)
    assert excinfo.value.retry_after == 3000


def test_authentication_error_still_starts_reauth() -> None:
    def _refresh(_manager):
        raise AuthenticationError("invalid credentials")

    _module, coordinator, _hass, _entry = _coordinator(_refresh)
    with pytest.raises(_ConfigEntryAuthFailed):
        _poll(coordinator)


def test_state_is_persisted_also_when_the_login_fails() -> None:
    def _refresh(manager):
        manager.login_guard.begin_attempt()
        manager.login_guard.record_rejection()
        raise AuthenticationError("redirect, second rejection")

    _module, coordinator, hass, entry = _coordinator(_refresh)
    with pytest.raises(_ConfigEntryAuthFailed):
        _poll(coordinator)

    saved = entry.data[CONF_LOGIN_GUARD]
    assert set(saved) == {"last_attempt_at", "failures"}
    assert saved["failures"] == 1 and saved["last_attempt_at"] > 0
    assert len(hass.updates) == 1
    # No credentials or token material next to the counter.
    assert PASSWORD not in repr(saved) and USERNAME not in repr(saved)


def test_only_state_changes_are_written() -> None:
    _module, coordinator, hass, _entry = _coordinator(lambda _manager: False)
    # Not dirty: a refresh that does not touch the guard writes nothing.
    asyncio.run(coordinator.async_check_and_refresh_token())
    assert not any(CONF_LOGIN_GUARD in update for update in hass.updates)


def test_restart_keeps_the_window_open_for_the_next_coordinator() -> None:
    def _refresh(manager):
        manager.login_guard.begin_attempt()
        raise LoginAttemptFailedError("waf", retry_after=1)

    _module, first, _hass, entry = _coordinator(_refresh)
    with pytest.raises(_UpdateFailed):
        _poll(first)
    persisted = dict(entry.data[CONF_LOGIN_GUARD])

    def _refresh_again(manager):
        manager.login_guard.begin_attempt()

    _module2, restarted, _hass2, _entry2 = _coordinator(_refresh_again, persisted)
    with pytest.raises(_UpdateFailed) as excinfo:
        _poll(restarted)
    assert excinfo.value.retry_after > 60  # window still closed after restart


def test_manual_commands_get_a_readable_error_and_do_not_bypass_the_limit() -> None:
    def _refresh(manager):
        manager.login_guard.begin_attempt()

    _module, coordinator, _hass, entry = _coordinator(
        _refresh, {"last_attempt_at": time.time() - 60, "failures": 0}
    )
    before = dict(entry.data[CONF_LOGIN_GUARD])

    with pytest.raises(_HomeAssistantError) as excinfo:
        asyncio.run(coordinator.async_force_update_all())
    assert "limited until" in str(excinfo.value)
    assert not isinstance(excinfo.value, _ConfigEntryAuthFailed)

    with pytest.raises(_HomeAssistantError):
        asyncio.run(coordinator.async_update_all())
    assert entry.data[CONF_LOGIN_GUARD] == before


def test_reauth_and_reconfigure_reset_the_login_limit() -> None:
    module = _load("config_flow.py", "config_flow_under_test")
    exhausted = {"last_attempt_at": 1_800_000_000.0, "failures": 2}
    fresh = LoginGuard().to_dict()

    class _FakeManager:
        def __init__(self, **_kwargs):
            self.token = Token(username=USERNAME, access_token="Bearer new")

    async def _validate(_hass, _config, _manager):
        return Token(username=USERNAME)

    module.VehicleManager = _FakeManager
    module.validate_input = _validate
    user_input = {"username": USERNAME, "password": PASSWORD, "pin": "4321"}

    # Reauth: the entry data is replaced before the reload.
    entry = _Entry(_entry_data(exhausted))
    hass = _Hass(entry)
    flow = module.ConfigFlow()
    flow.hass = hass
    flow._backend_data = {"data_backend": "cci", "region": 1, "brand": 1}
    flow.reauth_entry = entry
    result = asyncio.run(flow.async_step_credentials_password(user_input))
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_LOGIN_GUARD] == fresh
    assert hass.reloads == ["entry-id"]

    # Reconfigure merges data_updates: the guard must be in them.
    entry = _Entry(_entry_data(exhausted))
    flow = module.ConfigFlow()
    flow.hass = _Hass(entry)
    flow._backend_data = {"data_backend": "cci", "region": 1, "brand": 1}
    flow._is_reconfigure = True
    asyncio.run(flow.async_step_credentials_password(user_input))
    assert flow.reload_data_updates[CONF_LOGIN_GUARD] == fresh
