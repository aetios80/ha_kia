"""Pinned X-Fingerprint vectors and gate detection, standard library only.

The module under test is loaded straight from its file so that this test runs
without pytest, requests or pycryptodome. Any of these works:

    python -I tests/test_cci_fingerprint_vectors.py
    python -I -m unittest discover -s tests -p "test_cci_fingerprint_vectors.py"
    python -m pytest tests/test_cci_fingerprint_vectors.py

The pinned vector is the Kia vector of upstream tests/test_eu_cci_fingerprint.py
(hyundai_kia_connect_api v5.3.1, from PR #1352, commit 97668164): an
empty-body exchange that answered 200 live on 2026-10-14.
"""

import hashlib
import hmac
import importlib.util
from pathlib import Path
import unittest

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


class FingerprintVectorTests(unittest.TestCase):
    def test_matches_pinned_kia_vector(self) -> None:
        self.assertEqual(fp.compute_x_fingerprint(_kia_headers()), KIA_GOLDEN_FP)

    def test_header_names_are_case_insensitive(self) -> None:
        lowered = {k.lower(): v for k, v in _kia_headers().items()}
        self.assertEqual(fp.compute_x_fingerprint(lowered), KIA_GOLDEN_FP)

    def test_strips_java_ascii_whitespace_from_body(self) -> None:
        self.assertEqual(
            fp.compute_x_fingerprint(_kia_headers(), " \t\r\n"), KIA_GOLDEN_FP
        )

    def test_keeps_unicode_whitespace_in_body(self) -> None:
        self.assertNotEqual(
            fp.compute_x_fingerprint(_kia_headers(), " "), KIA_GOLDEN_FP
        )

    def test_body_is_part_of_the_signature_and_bytes_equal_str(self) -> None:
        bare = fp.compute_x_fingerprint(_kia_headers())
        signed = fp.compute_x_fingerprint(_kia_headers(), '{"a": 1}')
        self.assertNotEqual(signed, bare)
        self.assertEqual(fp.compute_x_fingerprint(_kia_headers(), b'{"a":1}'), signed)

    def test_message_shape_is_identity_os_version_timestamp_body(self) -> None:
        """Independent recomputation of the documented scheme with hmac/hashlib."""
        headers = _kia_headers()
        identity = "".join(
            headers[name]
            for name in ("client-id", "client-name", "client-version", "client-os-code")
        )
        message = identity + "14" + KIA_GOLDEN_TS
        # The key pieces are module constants: reuse them, the pinned vector
        # is the independent check on their values.
        key = identity + "".join(fp._KIA_FINGERPRINT_KEY)
        expected = hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()
        self.assertEqual(expected, KIA_GOLDEN_FP)
        self.assertEqual(expected, fp.compute_x_fingerprint(headers))

    def test_timestamp_changes_the_signature(self) -> None:
        headers = _kia_headers()
        headers["X-Timestamp"] = "1700000000124"
        self.assertNotEqual(fp.compute_x_fingerprint(headers), KIA_GOLDEN_FP)

    def test_build_fp_headers_is_the_verified_android_identity(self) -> None:
        headers = fp.build_fp_headers(device_id="dev-1", locale="it", timezone="+01:00")
        expected = {
            "client-id": "com.kia.oneapp.eu",
            "client-name": "KiaEU",
            "client-version": "1.4.0",
            "client-os-code": "android",
            "client-os-version": "14",
            "client-device-model": "SM-S918B",
            "client-notification-provider-type": "FCM",
            "locale": "IT",
            "Accept-Language": "it",
            "X-Brand": "Kia",
            "X-Region": "eu",
            "User-Agent": "okhttp/4.12.0",
            "Accept": "*/*",
        }
        for name, value in expected.items():
            self.assertEqual(headers[name], value, name)
        self.assertEqual(fp.CLIENT_VERSION, "1.4.0")
        self.assertTrue(headers["App-Request-Id"].endswith("_dev1_AOS"))

    def test_signature_of_built_headers_is_reproducible(self) -> None:
        headers = fp.build_fp_headers(device_id="dev-1", locale="en", timezone="+00:00")
        headers["X-Timestamp"] = KIA_GOLDEN_TS
        # Same identity as the pinned vector, so the same signature.
        self.assertEqual(fp.compute_x_fingerprint(headers), KIA_GOLDEN_FP)

    def test_is_gate_rejection_code_family(self) -> None:
        for code in (9035, 9036, 9037):
            self.assertTrue(fp.is_gate_rejection(400, f'{{"code":{code},"message":"x"}}'))
            self.assertTrue(fp.is_gate_rejection(403, f'{{"code":{code}}}'.encode()))

    def test_other_codes_and_statuses_are_not_gate_rejections(self) -> None:
        for status, body in (
            (400, '{"code":9013,"message":"x"}'),
            (400, '{"code":9030,"message":"x"}'),
            (500, '{"code":9035,"message":"x"}'),
            (200, '{"code":9035,"message":"x"}'),
            (502, "upstream html error"),
            (400, ""),
            (400, "[9035]"),
            (400, '{"message":"no code"}'),
            (400, '{"code":"9035"}'),
        ):
            self.assertFalse(fp.is_gate_rejection(status, body), (status, body))


if __name__ == "__main__":
    unittest.main(verbosity=2)
