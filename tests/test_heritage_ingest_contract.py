"""Contract tests for heritage shapefile encoding detection.

Korea Heritage Service shapefiles are CP949 and frequently ship without the
.cpg sidecar that declares it. The failure is silent — the layer opens, the
geometry is right, and only the Korean names are wrong — so detection has to be
decided and recorded rather than left to GDAL's guess.
"""

import os
import sys
import unittest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
)

from ingest_heritage_shp import (  # noqa: E402
    CANDIDATE_ENCODINGS,
    detect_encoding,
    hangul_ratio,
)

# A DBF opens with a binary header, which is why strict decoding fails under
# every candidate and the detector has to score leniently instead.
DBF_HEADER = bytes([0x03, 0x7A, 0x09, 0x01, 0x02, 0x00, 0x00, 0x00, 0x81, 0x00])
NAMES = "건원릉 광릉 목릉 숭릉 경기도 구리시 동구릉로"


def _dbf(text, encoding):
    return DBF_HEADER + text.encode(encoding) + b"\x00\x1a"


class HangulRatioTests(unittest.TestCase):
    def test_pure_hangul_scores_high(self):
        self.assertGreater(hangul_ratio("건원릉"), 0.9)

    def test_ascii_scores_zero(self):
        self.assertEqual(hangul_ratio("Donggureung"), 0.0)

    def test_empty_text_is_safe(self):
        self.assertEqual(hangul_ratio(""), 0.0)


class DeclaredEncodingTests(unittest.TestCase):
    def test_cpg_declaring_cp949_is_honoured(self):
        encoding, _reason, confidence = detect_encoding(
            _dbf(NAMES, "cp949"), "CP949"
        )
        self.assertEqual(encoding, "cp949")
        self.assertEqual(confidence, "declared")

    def test_cpg_aliases_for_cp949_are_recognised(self):
        for declared in ("MS949", "EUC-KR", "euckr", "KSC5601", "ansi949"):
            encoding, _reason, confidence = detect_encoding(
                _dbf(NAMES, "cp949"), declared
            )
            self.assertEqual(encoding, "cp949", declared)
            self.assertEqual(confidence, "declared", declared)

    def test_cpg_declaring_utf8_is_honoured(self):
        encoding, _reason, confidence = detect_encoding(_dbf(NAMES, "utf-8"), "UTF-8")
        self.assertEqual(encoding, "utf-8")
        self.assertEqual(confidence, "declared")

    def test_unrecognised_cpg_falls_through_to_inference(self):
        encoding, _reason, confidence = detect_encoding(
            _dbf(NAMES, "cp949"), "SOMETHING-ELSE"
        )
        self.assertEqual(encoding, "cp949")
        self.assertEqual(confidence, "inferred")


class InferredEncodingTests(unittest.TestCase):
    def test_cp949_without_a_cpg_is_inferred(self):
        # The real-world case: GDAL would otherwise guess and produce mojibake.
        encoding, _reason, confidence = detect_encoding(_dbf(NAMES, "cp949"))
        self.assertEqual(encoding, "cp949")
        self.assertEqual(confidence, "inferred")

    def test_utf8_without_a_cpg_is_inferred(self):
        # Detection must not simply always answer cp949.
        encoding, _reason, confidence = detect_encoding(_dbf(NAMES, "utf-8"))
        self.assertEqual(encoding, "utf-8")
        self.assertEqual(confidence, "inferred")

    def test_reason_records_why_the_encoding_was_chosen(self):
        _encoding, reason, _confidence = detect_encoding(_dbf(NAMES, "cp949"))
        self.assertIn("hangul", reason.lower())

    def test_ascii_only_attributes_are_flagged_as_moot(self):
        encoding, reason, confidence = detect_encoding(_dbf("SEOUL GYEONGGI", "ascii"))
        self.assertEqual(confidence, "weak")
        self.assertIn("moot", reason)
        self.assertIn(encoding, CANDIDATE_ENCODINGS)


class SupersetPreferenceTests(unittest.TestCase):
    def test_euc_kr_is_not_a_separate_candidate(self):
        # CP949 is its superset and reads the same bytes, plus extended Hangul
        # that appears in some place names. Listing both only creates ties.
        self.assertNotIn("euc-kr", CANDIDATE_ENCODINGS)
        self.assertIn("cp949", CANDIDATE_ENCODINGS)

    def test_euc_kr_content_resolves_to_cp949(self):
        encoding, _reason, _confidence = detect_encoding(_dbf(NAMES, "euc-kr"))
        self.assertEqual(encoding, "cp949")


if __name__ == "__main__":
    unittest.main()
