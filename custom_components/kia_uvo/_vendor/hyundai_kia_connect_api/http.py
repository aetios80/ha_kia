"""HTTPS-only network boundary for Kia Connect EU."""

from collections.abc import Mapping
from urllib.parse import urlsplit

import requests


class EndpointPolicyError(requests.RequestException):
    """Raised when a request is outside the explicit EU endpoint policy."""


KIA_EU_HOSTS: Mapping[str, frozenset[int]] = {
    "prd.eu-ccapi.kia.com": frozenset({443, 8080}),
    "idpconnect-eu.kia.com": frozenset({443}),
    "cci-api-eu.kia.com": frozenset({443}),
    "oneapp.kia.com": frozenset({443}),
}
OPENSTREETMAP_HOSTS: Mapping[str, frozenset[int]] = {
    "nominatim.openstreetmap.org": frozenset({443}),
}
def validate_endpoint(
    url: str, *, allowed_hosts: Mapping[str, frozenset[int]] = KIA_EU_HOSTS
) -> None:
    """Reject non-HTTPS URLs, credentials in URLs, and unknown endpoints."""
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise EndpointPolicyError("Only absolute HTTPS endpoints are allowed")
    if parsed.username or parsed.password:
        raise EndpointPolicyError("Credentials in URLs are not allowed")
    try:
        port = parsed.port or 443
    except ValueError as exc:
        raise EndpointPolicyError("Invalid endpoint port") from exc
    allowed_ports = allowed_hosts.get(parsed.hostname.lower())
    if allowed_ports is None or port not in allowed_ports:
        raise EndpointPolicyError("Endpoint is not in the Kia Connect EU allowlist")


class ApiImplSession(requests.Session):
    """Requests session enforcing the Kia Connect EU network policy."""

    HTTP_CONNECT_TIMEOUT = 10
    HTTP_READ_TIMEOUT = 30
    allowed_hosts = KIA_EU_HOSTS

    def request(self, method: str, url: str, **kwargs):
        validate_endpoint(url, allowed_hosts=self.allowed_hosts)
        if kwargs.get("verify") is False:
            raise EndpointPolicyError("TLS certificate verification cannot be disabled")
        kwargs.setdefault("verify", True)
        kwargs.setdefault(
            "timeout", (self.HTTP_CONNECT_TIMEOUT, self.HTTP_READ_TIMEOUT)
        )
        try:
            return super().request(method, url, **kwargs)
        except requests.exceptions.Timeout as exc:
            from .exceptions import RequestTimeoutError

            raise RequestTimeoutError(str(exc)) from exc

    def send(self, request, **kwargs):
        validate_endpoint(request.url, allowed_hosts=self.allowed_hosts)
        if kwargs.get("verify") is False:
            raise EndpointPolicyError("TLS certificate verification cannot be disabled")
        kwargs.setdefault("verify", True)
        return super().send(request, **kwargs)


def http_request(method: str, url: str, **kwargs):
    """Run a one-off allowlisted request without bypassing the policy."""
    with ApiImplSession() as session:
        return session.request(method, url, **kwargs)


class OpenStreetMapSession(ApiImplSession):
    """Session available only from the explicit opt-in geocoding flow."""

    allowed_hosts = OPENSTREETMAP_HOSTS


def geocode_request(method: str, url: str, **kwargs):
    """Run an explicit opt-in OpenStreetMap geocoding request."""
    with OpenStreetMapSession() as session:
        return session.request(method, url, **kwargs)
