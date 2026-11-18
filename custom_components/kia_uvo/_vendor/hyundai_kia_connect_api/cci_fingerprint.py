"""X-Fingerprint signing for the Kia EU CCI auth endpoints.

Provenance (MIT, see NOTICE): port, Kia brand only, of
Hyundai-Kia-Connect/hyundai_kia_connect_api file hyundai_kia_connect_api/
cci_fingerprint.py as of tag v5.3.1 (commit 750e4e2). The signing scheme and
the Kia constants originate from upstream PR #1352 (commit 97668164, merged
2026-10-14) and were moved into this module by the refactor PR #1358; the
gate-rejection handling follows PR #1481.

Upstream documents that the OneApp app signs POSTs to cci-api-eu.../auth/*
with X-Fingerprint = HMAC-SHA256 over the client identity plus app-embedded
secret constants, recovered from the Android OneApp 1.4.0 build and verified
live on 2026-10-14. A wrong signature answers 9036, a missing X-Fingerprint
answers 9035, a timestamp out of window answers 9037.

This module is stdlib only on purpose: the signing vectors can be verified
without any third-party package.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import uuid

# Kia EU signing constants (secret, piece, suffix), concatenated into the HMAC
# key in this order. They rotate with app releases.
_KIA_FINGERPRINT_KEY: tuple[str, str, str] = (
    "yb4Z1n2nlKe",
    "ukNilE7QEdb",
    "KB34nStPVa",
)

# Android OneApp build identity the gate validates the fingerprint against.
# The legacy (unsigned) CCI header set keeps its own, different identity.
CLIENT_PACKAGE_ID = "com.kia.oneapp.eu"
CLIENT_NAME = "KiaEU"
BRAND_LABEL = "Kia"
CLIENT_VERSION = "1.4.0"
CLIENT_OS_CODE = "android"
CLIENT_OS_VERSION = "14"
CLIENT_DEVICE_MODEL = "SM-S918B"
CLIENT_NOTIFICATION_PROVIDER = "FCM"
USER_AGENT = "okhttp/4.12.0"
APP_REGION = "eu"

_IDENTITY_HEADERS = ("client-id", "client-name", "client-version", "client-os-code")

# Fingerprint-gate rejection family: 9035 = header missing, 9036 = bad
# signature, 9037 = timestamp out of window. 9013 (invalid code) and 9030
# (token expired) are business errors, not gate rejections.
GATE_REJECTION_CODES = frozenset({9035, 9036, 9037})


def compute_x_fingerprint(headers: dict[str, str], body: str | bytes = "") -> str:
    """HMAC-SHA256 over the client identity per the OneApp signing scheme.

    Key: identity (client-id + client-name + client-version + client-os-code)
         + secret + piece + suffix.
    Message: identity + client-os-version + X-Timestamp
         (+ request body with Java-ASCII whitespace removed).
    """
    lower = {k.lower(): v for k, v in headers.items()}
    identity = "".join(lower.get(name, "") for name in _IDENTITY_HEADERS)
    if isinstance(body, bytes):
        body = body.decode("utf-8")
    message = (
        identity
        + lower.get("client-os-version", "")
        + lower.get("x-timestamp", "")
        + re.sub(r"\s+", "", body or "", flags=re.ASCII)
    )
    key = identity + "".join(_KIA_FINGERPRINT_KEY)
    return hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()


def is_gate_rejection(status_code: int, body: str | bytes) -> bool:
    """True when an auth response carries a fingerprint-gate rejection code.

    The gate answers with an HTTP 4xx and a JSON body whose "code" is one of
    GATE_REJECTION_CODES. Anything else (5xx, a 4xx without a code, an
    unparsable body, business errors such as 9013/9030) is not a gate
    rejection and must not trigger the legacy fallback.
    """
    if not isinstance(status_code, int) or not 400 <= status_code < 500:
        return False
    try:
        return json.loads(body).get("code") in GATE_REJECTION_CODES
    except (ValueError, AttributeError, TypeError):
        return False


def build_fp_headers(
    device_id: str,
    locale: str,
    timezone: str,
    package_id: str = CLIENT_PACKAGE_ID,
    client_name: str = CLIENT_NAME,
    brand_label: str = BRAND_LABEL,
) -> dict[str, str]:
    """Header set for the fingerprint-gated CCI endpoints (Kia identity)."""
    return {
        "client-id": package_id,
        "client-name": client_name,
        "client-version": CLIENT_VERSION,
        "client-os-code": CLIENT_OS_CODE,
        "client-os-version": CLIENT_OS_VERSION,
        "client-device-id": device_id or "",
        "client-device-model": CLIENT_DEVICE_MODEL,
        "client-notification-provider-type": CLIENT_NOTIFICATION_PROVIDER,
        "locale": locale.upper(),
        "timezone": timezone,
        "App-Request-Id": f"{uuid.uuid4().hex[:24].upper()}_"
        f"{(device_id or '').replace('-', '')}_AOS",
        "X-Brand": brand_label,
        "X-Region": APP_REGION,
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": locale.lower(),
    }
