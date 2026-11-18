"""Constants for the Kia Connect EU integration."""

from enum import StrEnum

DOMAIN: str = "kia_uvo"

CONF_BRAND: str = "brand"
CONF_FORCE_REFRESH_INTERVAL: str = "force_refresh"
CONF_NO_FORCE_REFRESH_HOUR_START: str = "no_force_refresh_hour_start"
CONF_NO_FORCE_REFRESH_HOUR_FINISH: str = "no_force_refresh_hour_finish"
CONF_ENABLE_GEOLOCATION_ENTITY: str = "enable_geolocation_entity"
CONF_USE_EMAIL_WITH_GEOCODE_API: str = "use_email_with_geocode_api"
CONF_TOKEN: str = "token"
# Login limit state (last attempt, consecutive failures). Kept apart from
# CONF_TOKEN on purpose: it holds no credential and no account data.
CONF_LOGIN_GUARD: str = "login_guard"
# After a failed full login (WAF, 5xx, timeout, exchange error) the coordinator
# retries the cheap CCI refresh after at most this many seconds; the full-login
# limit itself (one per 6 hours) is enforced by the login guard, not by this.
LOGIN_FAILED_RETRY_CAP_SECONDS: int = 1800

# A 48-character token used as "password" (removed legacy login, #1506).
LEGACY_TOKEN_PASSWORD_LENGTH: int = 48


def is_legacy_token_password(password: object) -> bool:
    """True for a stored password shaped like the removed 48-char token."""
    return (
        isinstance(password, str)
        and len(password) == LEGACY_TOKEN_PASSWORD_LENGTH
        and password.isascii()
        and all(c.isdigit() or ("A" <= c <= "Z") for c in password)
    )

CONF_DATA_BACKEND: str = "data_backend"

DATA_BACKEND_CCI: str = "cci"
DATA_BACKEND_OFFICIAL: str = "official_data_api"

REGION_EUROPE: str = "Europe"
REGIONS = {1: REGION_EUROPE}
BRAND_KIA: str = "Kia"
BRANDS = {1: BRAND_KIA}

CHARGING_CURRENTS = {1: 100, 2: 90, 3: 60}

DEFAULT_PIN: str = ""
DEFAULT_SCAN_INTERVAL: int = 30
DEFAULT_FORCE_REFRESH_INTERVAL: int = 1440
DEFAULT_NO_FORCE_REFRESH_HOUR_START: int = 22
DEFAULT_NO_FORCE_REFRESH_HOUR_FINISH: int = 7
DEFAULT_ENABLE_GEOLOCATION_ENTITY: bool = False
DEFAULT_USE_EMAIL_WITH_GEOCODE_API: bool = False

DYNAMIC_UNIT: str = "dynamic_unit"


class OffPeakChargingMode(StrEnum):
    """Off-peak charging schedule mode.

    Maps to the (charging_enabled, off_peak_charge_only_enabled) pair the API
    expects. Values are the strings exposed in services.yaml so the service
    payload converts directly: ``OffPeakChargingMode(call.data["mode"])``.
    """

    OFF = "off"
    TIME = "time"
    TARGET = "target"
