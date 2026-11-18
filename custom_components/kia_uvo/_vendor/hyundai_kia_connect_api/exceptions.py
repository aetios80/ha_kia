"""exceptions.py"""

# pylint:disable=unnecessary-pass


class HyundaiKiaException(Exception):
    """
    Generic hyundaiKiaException exception.
    """


class PINMissingError(HyundaiKiaException):
    """
    Raised upon receipt of an authentication error.
    """


class AuthenticationError(HyundaiKiaException):
    """
    Raised upon receipt of an authentication error.
    """


class AuthenticationBlockedError(AuthenticationError):
    """
    The identity provider blocked the authorization request (WAF).
    """


class AuthenticationCertificateError(AuthenticationError):
    """
    The identity provider RSA certificate could not be retrieved.
    """


class AuthenticationServiceError(AuthenticationError):
    """
    The identity provider answered with a server-side error (HTTP 5xx).
    """


class AuthenticationSigninError(AuthenticationError):
    """
    The identity provider rejected the sign-in response.
    """


class AuthenticationInvalidCredentialsError(AuthenticationSigninError):
    """
    The identity provider explicitly reported invalid credentials.
    """


class AuthenticationRedirectError(AuthenticationError):
    """
    The sign-in flow redirected back to the login page (or elsewhere
    unexpected) without issuing an authorization code. The redirect alone
    cannot tell a rejected User-Agent apart from rejected credentials.
    """


class AuthenticationTokenExchangeError(AuthenticationError):
    """
    A CCI/CCS token exchange or refresh was unsuccessful.
    """


class AuthenticationCciTokenExchangeError(AuthenticationTokenExchangeError):
    """
    The CCI authorization-code exchange was unsuccessful.
    """


class AuthenticationCcsTokenExchangeError(AuthenticationTokenExchangeError):
    """
    The CCS token exchange was unsuccessful.
    """


class AuthenticationOTPRequired(AuthenticationError):
    """
    Raised when OTP is required for authentication.
    """


class APIError(HyundaiKiaException):
    """
    Generic API error
    """


class DeviceIDError(APIError):
    """
    Raised upon receipt of an Invalid Device ID error.
    """


class RateLimitingError(APIError):
    """
    Raised when we get rate limited by the server
    """


class NoDataFound(APIError):
    """
    Raised when the API doesn't have data for that car.
    Disabling the car is the solution.
    """


class ServiceTemporaryUnavailable(APIError):
    """
    Raised when Service Temporary Unavailable
    """


class DuplicateRequestError(APIError):
    """
    Raised when (supposedly) a previous request is already queued server-side
    and the server temporarily rejects requests.
    """


class SafetyAcknowledgmentError(APIError):
    """
    Raised when a safety-critical command requires explicit user acknowledgment
    before it can be executed (e.g. SVM/Find My Car capture).
    """


class UnsupportedControlError(APIError):
    """
    Raised when the vehicle does not support the requested control action.
    API returns resCode 4005 for unsupported actions (e.g. stop_climate on HEV).
    """


class RequestTimeoutError(APIError):
    """
    Raised when (supposedly) the server fails to establish a connection with the car.
    """


class InvalidAPIResponseError(APIError):
    """
    Raised upon receipt of an invalid API response.
    """


class ConsentRequiredError(AuthenticationError):
    """
    Raised when the OAuth signin succeeds but the user must accept
    a consent/authorization page before tokens can be issued.
    This typically means the user needs to log in via a browser once
    to accept terms, then use the refresh token going forward.
    """
