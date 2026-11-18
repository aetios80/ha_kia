"""Pinned X-Fingerprint vectors and gate detection, standard library only.

The module under test is loaded straight from its file so that this test runs
without pytest, requests or pycryptodome:

    python -I tests/test_cci_fingerprint_vectors.py

The pinned vector is the Kia vector of upstream tests/test_eu_cci_fingerprint.py
(hyundai_kia_connect_api v5.3.1, from PR #1352, commit 97668164): an
empty-body exchange that answered 200 live on 2026-10-14.
"""

import hashlib
import hmac
import importlib.util
from pathlib import Path

MODULE_PATH = (
    Path(__file__).parent.parent
    / "custom_components"
    / "kia_uvo"
    / "_vendor"
    / "hyundai_kia_connect_api"
    / "cci_fingerprint.py"
)
_spec = importlib.util.spec_from_file_location("cci_fingerprint_under_test", MODULE_PATH)
fp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fp)

KIA_GOLDEN_TS = "1700000000123"
KIA_GOLDEN_FP = "0a3ceccc83823ec0d2c5d39a15dbf722c813e6da48800a0156a7a8459db63337"

_KIA_IDENTITY = {
    "client-id": "com.kia.oneapp.eu",
    "client-name": "KiaEU",
    "client-version": "1.4.0",
    "client-os-code": "android",
    "client-os-version": "14",
}


def _kia_headers() -> dict:
    headers = dict(_KIA_IDENTITY)
    headers["X-Timestamp"] = KIA_GOLDEN_TS
    return headers


def test_matches_pinned_kia_vector() -> None:
    assert fp.compute_x_fingerprint(_kia_headers()) == KIA_GOLDEN_FP


def test_header_names_are_case_insensitive() -> None:
    lowered = {k.lower(): v for k, v in _kia_headers().items()}
    assert fp.compute_x_fingerprint(lowered) == KIA_GOLDEN_FP


def test_strips_java_ascii_whitespace_from_body() -> None:
    assert fp.compute_x_fingerprint(_kia_headers(), " \t\r\n") == KIA_GOLDEN_FP


def test_keeps_unicode_whitespace_in_body() -> None:
    assert fp.compute_x_fingerprint(_kia_headers(), " ") != KIA_GOLDEN_FP


def test_body_is_part_of_the_signature_and_bytes_equal_str() -> None:
    bare = fp.compute_x_fingerprint(_kia_headers())
    signed = fp.compute_x_fingerprint(_kia_headers(), '{"a": 1}')
    assert signed != bare
    assert fp.compute_x_fingerprint(_kia_headers(), b'{"a":1}') == signed


def test_message_shape_is_identity_os_version_timestamp_body() -> None:
    """Independent recomputation of the documented scheme with hmac/hashlib."""
    headers = _kia_headers()
    identity = "".join(
        headers[name]
        for name in ("client-id", "client-name", "client-version", "client-os-code")
    )
    message = identity + "14" + KIA_GOLDEN_TS
    # The key pieces are module constants: reuse them, the pinned vector is
    # the independent check on their values.
    key = identity + "".join(fp._KIA_FINGERPRINT_KEY)
    expected = hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()
    assert expected == KIA_GOLDEN_FP == fp.compute_x_fingerprint(headers)


def test_timestamp_changes_the_signature() -> None:
    headers = _kia_headers()
    headers["X-Timestamp"] = "1700000000124"
    assert fp.compute_x_fingerprint(headers) != KIA_GOLDEN_FP


def test_build_fp_headers_is_the_verified_android_identity() -> None:
    headers = fp.build_fp_headers(device_id="dev-1", locale="it", timezone="+01:00")
    assert headers["client-id"] == "com.kia.oneapp.eu"
    assert headers["client-name"] == "KiaEU"
    assert headers["client-version"] == fp.CLIENT_VERSION == "1.4.0"
    assert headers["client-os-code"] == "android"
    assert headers["client-os-version"] == "14"
    assert headers["client-device-model"] == "SM-S918B"
    assert headers["client-notification-provider-type"] == "FCM"
    assert headers["locale"] == "IT"
    assert headers["Accept-Language"] == "it"
    assert headers["X-Brand"] == "Kia"
    assert headers["X-Region"] == "eu"
    assert headers["User-Agent"] == "okhttp/4.12.0"
    assert headers["Accept"] == "*/*"
    assert headers["App-Request-Id"].endswith("_dev1_AOS")


def test_signature_of_built_headers_is_reproducible() -> None:
    headers = fp.build_fp_headers(device_id="dev-1", locale="en", timezone="+00:00")
    headers["X-Timestamp"] = KIA_GOLDEN_TS
    # Same identity as the pinned vector, so the same signature.
    assert fp.compute_x_fingerprint(headers) == KIA_GOLDEN_FP


def test_is_gate_rejection_code_family() -> None:
    for code in (9035, 9036, 9037):
        assert fp.is_gate_rejection(400, f'{{"code":{code},"message":"x"}}')
        assert fp.is_gate_rejection(403, f'{{"code":{code}}}'.encode())


def test_other_codes_and_statuses_are_not_gate_rejections() -> None:
    assert not fp.is_gate_rejection(400, '{"code":9013,"message":"x"}')
    assert not fp.is_gate_rejection(400, '{"code":9030,"message":"x"}')
    assert not fp.is_gate_rejection(500, '{"code":9035,"message":"x"}')
    assert not fp.is_gate_rejection(200, '{"code":9035,"message":"x"}')
    assert not fp.is_gate_rejection(502, "upstream html error")
    assert not fp.is_gate_rejection(400, "")
    assert not fp.is_gate_rejection(400, "[9035]")
    assert not fp.is_gate_rejection(400, '{"message":"no code"}')
    assert not fp.is_gate_rejection(400, '{"code":"9035"}')


if __name__ == "__main__":
    names = [n for n in sorted(globals()) if n.startswith("test_")]
    for name in names:
        globals()[name]()
        print("PASS", name)
    print(f"{len(names)}/{len(names)} passed (standard library only)")
