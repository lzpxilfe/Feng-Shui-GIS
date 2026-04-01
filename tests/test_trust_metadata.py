import unittest

from feng_shui_gis.trust_metadata import build_trust_metadata


class TrustMetadataTests(unittest.TestCase):
    def test_general_principles_default(self):
        payload = build_trust_metadata(
            "en",
            advanced_context_enabled=False,
            culture_key="",
            profile_key="tomb",
        )
        self.assertEqual(payload["result_badges"], ["general_principles"])
        self.assertIn("probability", payload["score_notice"])

    def test_exploratory_context_badge(self):
        payload = build_trust_metadata(
            "en",
            advanced_context_enabled=True,
            culture_key="ryukyu",
            profile_key="tomb",
        )
        self.assertIn("exploratory_context", payload["result_badges"])

    def test_local_calibration_badge(self):
        payload = build_trust_metadata(
            "en",
            advanced_context_enabled=True,
            culture_key="korea",
            profile_key="tomb_calibrated",
            reported_metric_phase="held_out_evaluation",
        )
        self.assertIn("local_calibration_applied", payload["result_badges"])
        self.assertIn("Held-out", payload["calibration_notice"])


if __name__ == "__main__":
    unittest.main()
