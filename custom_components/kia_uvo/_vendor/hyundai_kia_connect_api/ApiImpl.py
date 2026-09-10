"""ApiImpl.py"""

# pylint:disable=unnecessary-pass,missing-class-docstring,invalid-name,missing-function-docstring,wildcard-import,unused-wildcard-import,unused-argument,logging-fstring-interpolation
import datetime as dt
import logging
from dataclasses import dataclass

from requests.exceptions import JSONDecodeError

from .const import (
    CHARGE_PORT_ACTION,
    DOMAIN,
    GEO_LOCATION_PROVIDERS,
    GOOGLE,
    OPENSTREETMAP,
    ORDER_STATUS,
    OTP_NOTIFY_TYPE,
    VALET_MODE_ACTION,
    VEHICLE_LOCK_ACTION,
    WINDOW_STATE,
)
from .http import geocode_request
from .logging_utils import SafeDebugLogger
from .svm import SVMDetails
from .Token import Token
from .utils import get_child_value, to_int_enum
from .Vehicle import Vehicle

_LOGGER = SafeDebugLogger(logging.getLogger(__name__))


@dataclass
class ClimateRequestOptions:
    set_temp: float = None
    duration: int = None
    defrost: bool = None
    climate: bool = None
    heating: int = None
    front_left_seat: int = None
    front_right_seat: int = None
    rear_left_seat: int = None
    rear_right_seat: int = None
    steering_wheel: int = None


@dataclass
class WindowRequestOptions:
    back_left: WINDOW_STATE = None
    back_right: WINDOW_STATE = None
    front_left: WINDOW_STATE = None
    front_right: WINDOW_STATE = None

    def __post_init__(self):
        """Convert string/int values to WINDOW_STATE enums."""
        self.back_left = to_int_enum(WINDOW_STATE, self.back_left)
        self.back_right = to_int_enum(WINDOW_STATE, self.back_right)
        self.front_left = to_int_enum(WINDOW_STATE, self.front_left)
        self.front_right = to_int_enum(WINDOW_STATE, self.front_right)


@dataclass
class OTPRequest:
    request_id: str | None
    otp_key: str | None
    has_email: bool | None
    has_sms: bool | None
    email: str | None
    sms: str | None


@dataclass
class ScheduleChargingClimateRequestOptions:
    @dataclass
    class DepartureOptions:
        enabled: bool = None
        days: list[int] = None  # Sun=0, Mon=1, ..., Sat=6
        time: dt.time = None

    first_departure: DepartureOptions = None
    second_departure: DepartureOptions = None
    charging_enabled: bool = None
    off_peak_start_time: dt.time = None
    off_peak_end_time: dt.time = None
    off_peak_charge_only_enabled: bool = None
    climate_enabled: bool = None
    temperature: float = None
    temperature_unit: int = None
    defrost: bool = None



class ApiImpl:
    data_timezone = dt.UTC
    temperature_range = None
    previous_latitude: float = None
    previous_longitude: float = None
    supports_window_control: bool = False
    supports_valet_mode: bool = False
    supports_svm: bool = False

    def __init__(self) -> None:
        """Initialize."""

    def login(
        self,
        username: str,
        password: str,
        pin: str | None = None,
    ) -> Token | OTPRequest:
        """Login into cloud endpoints and return Token or OTP Details if OTP is triggered"""
        raise NotImplementedError("login is not implemented for this region")

    def send_otp(self, otp_request: OTPRequest, notify_type: OTP_NOTIFY_TYPE) -> None:
        """Sends OTP to the user via selected destination and via"""
        raise NotImplementedError("send_otp is not implemented for this region")

    def verify_otp_and_complete_login(
        self,
        username: str,
        password: str,
        otp_code: str,
        otp_request: OTPRequest,
        pin: str | None = None,
    ) -> Token:
        """Confirms OTP code sent to the user"""
        raise NotImplementedError(
            "verify_otp_and_complete_login is not implemented for this region"
        )

    def get_vehicles(self, token: Token) -> list[Vehicle]:
        """Return all Vehicle instances for a given Token"""
        raise NotImplementedError("get_vehicles is not implemented for this region")

    def refresh_vehicles(self, token: Token, vehicles: list[Vehicle]) -> None:
        """Refresh the vehicle data provided in get_vehicles.
        Required for Kia USA as key is session specific"""
        return

    def update_vehicle_with_cached_state(self, token: Token, vehicle: Vehicle) -> None:
        """Get cached vehicle data and update Vehicle instance with it"""
        raise NotImplementedError(
            "update_vehicle_with_cached_state is not implemented for this region"
        )

    def test_token(self, token: Token) -> bool:
        """Test if token is valid
        Use any dummy request to test if token is still valid"""
        return True

    def check_action_status(
        self,
        token: Token,
        vehicle: Vehicle,
        action_id: str,
        synchronous: bool = False,
        timeout: int = 0,
    ) -> ORDER_STATUS:
        pass

    def force_refresh_vehicle_state(self, token: Token, vehicle: Vehicle) -> None:
        """Triggers the system to contact the car and get fresh data"""
        raise NotImplementedError(
            "force_refresh_vehicle_state is not implemented for this region"
        )

    def update_geocoded_location(
        self,
        token: Token,
        vehicle: Vehicle,
        use_email: bool,
        provider: int = 1,
        API_KEY: str | None = None,
    ) -> None:
        if vehicle.location_latitude and vehicle.location_longitude:
            if (
                vehicle.geocode
                and vehicle.location_latitude == self.previous_latitude
                and vehicle.location_longitude == self.previous_longitude
            ):  # previous coordinates are the same, so keep last valid vehicle.geocode
                _LOGGER.debug(f"{DOMAIN} - Keeping last geocode location")
            elif GEO_LOCATION_PROVIDERS[provider] == OPENSTREETMAP:
                email_parameter = ""
                if use_email is True:
                    email_parameter = "&email=" + token.username

                url = (
                    "https://nominatim.openstreetmap.org/reverse?lat="
                    + str(vehicle.location_latitude)
                    + "&lon="
                    + str(vehicle.location_longitude)
                    + "&format=json&addressdetails=1&zoom=18"
                    + email_parameter
                )
                headers = {"user-agent": "curl/7.81.0"}
                response = geocode_request("GET", url, headers=headers, timeout=(5, 15))
                try:
                    response = response.json()
                except JSONDecodeError:
                    _LOGGER.warning(f"{DOMAIN} - failed geocode openstreetmap")
                    vehicle.geocode = None
                else:
                    vehicle.geocode = (
                        get_child_value(response, "display_name"),
                        get_child_value(response, "address"),
                    )
                    self.previous_latitude = vehicle.location_latitude
                    self.previous_longitude = vehicle.location_longitude
                    _LOGGER.debug(f"{DOMAIN} - geocode openstreetmap")
            elif GEO_LOCATION_PROVIDERS[provider] == GOOGLE:
                _LOGGER.warning(f"{DOMAIN} - Google geocoding is not supported in Kia EU")
                vehicle.geocode = None

    def lock_action(
        self, token: Token, vehicle: Vehicle, action: VEHICLE_LOCK_ACTION
    ) -> str:
        """Lock or unlocks a vehicle.  Returns the tracking ID"""
        raise NotImplementedError("lock_action is not implemented for this region")

    def start_climate(
        self, token: Token, vehicle: Vehicle, options: ClimateRequestOptions
    ) -> str:
        """Starts climate or remote start.  Returns the tracking ID"""
        raise NotImplementedError("start_climate is not implemented for this region")

    def stop_climate(self, token: Token, vehicle: Vehicle) -> str:
        """Stops climate or remote start.  Returns the tracking ID"""
        raise NotImplementedError("stop_climate is not implemented for this region")

    def start_charge(self, token: Token, vehicle: Vehicle) -> str:
        """Starts charge. Returns the tracking ID"""
        raise NotImplementedError("start_charge is not implemented for this region")

    def stop_charge(self, token: Token, vehicle: Vehicle) -> str:
        """Stops charge. Returns the tracking ID"""
        raise NotImplementedError("stop_charge is not implemented for this region")

    def set_charge_limits(
        self, token: Token, vehicle: Vehicle, ac: int, dc: int
    ) -> str:
        """Sets charge limits. Returns the tracking ID"""
        raise NotImplementedError(
            "set_charge_limits is not implemented for this region"
        )

    def set_charging_current(self, token: Token, vehicle: Vehicle, level: int) -> str:
        """
        feature only available for some regions.
        Sets charge current level (1=100%, 2=90%, 3=60%). Returns the tracking ID
        """
        raise NotImplementedError(
            "set_charging_current is not implemented for this region"
        )

    def set_windows_state(
        self, token: Token, vehicle: Vehicle, options: WindowRequestOptions
    ) -> str:
        """Opens or closes a particular window. Returns the tracking ID"""
        raise NotImplementedError(
            "set_windows_state is not implemented for this region"
        )

    def charge_port_action(
        self, token: Token, vehicle: Vehicle, action: CHARGE_PORT_ACTION
    ) -> str:
        """Opens or closes the charging port of the car. Returns the tracking ID"""
        raise NotImplementedError(
            "charge_port_action is not implemented for this region"
        )

    def update_month_trip_info(
        self, token: Token, vehicle: Vehicle, yyyymm_string: str
    ) -> None:
        """
        feature only available for some regions.
        Updates the vehicle.month_trip_info for the specified month.

        Default this information is None:

        month_trip_info: MonthTripInfo = None
        """
        raise NotImplementedError(
            "update_month_trip_info is not implemented for this region"
        )

    def update_day_trip_info(
        self, token: Token, vehicle: Vehicle, yyyymmdd_string: str
    ) -> None:
        """
        feature only available for some regions.
        Updates the vehicle.day_trip_info information for the specified day.

        Default this information is None:

        day_trip_info: DayTripInfo = None
        """
        raise NotImplementedError(
            "update_day_trip_info is not implemented for this region"
        )

    def schedule_charging_and_climate(
        self,
        token: Token,
        vehicle: Vehicle,
        options: ScheduleChargingClimateRequestOptions,
    ) -> str:
        """
        feature only available for some regions.
        Schedule charging and climate control. Returns the tracking ID
        """
        raise NotImplementedError(
            "schedule_charging_and_climate is not implemented for this region"
        )

    def start_hazard_lights(self, token: Token, vehicle: Vehicle) -> str:
        """Turns on the hazard lights for 30 seconds"""
        raise NotImplementedError(
            "start_hazard_lights is not implemented for this region"
        )

    def start_hazard_lights_and_horn(self, token: Token, vehicle: Vehicle) -> str:
        """Turns on the hazard lights and horn for 30 seconds"""
        raise NotImplementedError(
            "start_hazard_lights_and_horn is not implemented for this region"
        )

    def valet_mode_action(
        self, token: Token, vehicle: Vehicle, action: VALET_MODE_ACTION
    ) -> str:
        """
        feature only available for some regions.
        Activate or Deactivate valet mode. Returns the tracking ID
        """
        raise NotImplementedError(
            "valet_mode_action is not implemented for this region"
        )

    def set_vehicle_to_load_discharge_limit(
        self, token: Token, vehicle: Vehicle, limit: int
    ) -> str:
        """
        feature only available for some regions.
        Set the vehicle to load limit. Returns the tracking ID
        """
        raise NotImplementedError(
            "set_vehicle_to_load_discharge_limit is not implemented for this region"
        )

    def refresh_access_token(self, token: Token) -> Token | OTPRequest:
        """Refresh the token using the refresh token"""
        # By default, just call login again, ideally use the refresh token flow
        # Pass the pin explicitly as a keyword to avoid positional
        # argument mis-binding in subclasses that accept different
        # login() signatures (some accept a `token` positional arg).
        return self.login(
            username=token.username, password=token.password, pin=token.pin
        )

    def get_svm_details(self, token: Token, vehicle: Vehicle) -> SVMDetails:
        """Return the latest SVM composite image and metadata."""
        raise NotImplementedError("get_svm_details is not implemented for this region")

    def request_svm_capture(
        self,
        token: Token,
        vehicle: Vehicle,
        acknowledged_warning: bool = False,
    ) -> SVMDetails:
        """Trigger a fresh SVM capture and return the resulting image."""
        raise NotImplementedError(
            "request_svm_capture is not implemented for this region"
        )
