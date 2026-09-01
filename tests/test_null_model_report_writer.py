"""Contract tests for the background-comparison report.

The report exists so a comparison can be cited and reproduced. That fails the
moment the numbers can be read apart from the background policy that gives
them meaning, so these tests hold the two together.
"""

import json
import os
import random
import tempfile
import unittest

from feng_shui_gis.null_model import background_comparison, background_policy
from feng_shui_gis.reporting import (
    NullModelReportWriter,
    write_null_model_report_files,
)

STAMP = "20260902-1200"


def _sample(mean, sigma, count, seed):
    rng = random.Random(seed)
    return [rng.gauss(mean, sigma) for _ in range(count)]


def _comparison(observed_mean=0.70, background_mean=0.45, iterations=500):
    policy = background_policy(count=600, exclude_within_m=300.0)
    return background_comparison(
        _sample(observed_mean, 0.10, 30, seed=1),
        _sample(background_mean, 0.12, 600, seed=2),
        background_policy=policy["description"],
        iterations=iterations,
    )


def _sample_record(drawn=600, requested=600, complete=True):
    return {
        "scores": [0.0] * drawn,
        "requested": requested,
        "complete": complete,
        "attempts": 12000,
        "attempt_cap": 24000,
        "rejected": {"nodata_or_slope": 8000, "near_observed": 120},
    }


def _payload(**overrides):
    kwargs = {
        "stamp": STAMP,
        "site_layer_name": "eupchi",
        "dem_layer_name": "dem5m",
        "comparison": _comparison(),
        "sample": _sample_record(),
        "profile_key": "village_kr",
        "culture_key": "korea",
        "period_key": "early_modern",
        "scoring_note": "slope/aspect from DEM on both sides",
    }
    kwargs.update(overrides)
    return NullModelReportWriter.payload(**kwargs)


def _markdown(**overrides):
    kwargs = {
        "stamp": STAMP,
        "site_layer_name": "eupchi",
        "dem_layer_name": "dem5m",
        "comparison": _comparison(),
        "sample": _sample_record(),
        "profile_key": "village_kr",
        "culture_key": "korea",
        "period_key": "early_modern",
        "scoring_note": "slope/aspect from DEM on both sides",
    }
    kwargs.update(overrides)
    return NullModelReportWriter.build_markdown(**kwargs)


class PayloadStructureTests(unittest.TestCase):
    def test_payload_uses_the_shared_report_sections(self):
        payload = _payload()
        for section in ("timestamp", "interpretation", "analytical", "audit"):
            self.assertIn(section, payload)

    def test_background_policy_sits_with_the_interpretation(self):
        # Reading the numbers without the policy is the failure this guards.
        interpretation = _payload()["interpretation"]
        self.assertIn("slope <= 25 deg", interpretation["background_policy"])
        self.assertIn("seed=", interpretation["background_policy"])

    def test_claim_limits_travel_with_the_result(self):
        interpretation = _payload()["interpretation"]
        self.assertTrue(interpretation["establishes"])
        self.assertIn("feng shui", interpretation["does_not_establish"])
        self.assertIn("unsurveyed", interpretation["does_not_establish"])

    def test_context_and_profile_are_recorded(self):
        interpretation = _payload()["interpretation"]
        self.assertEqual(interpretation["profile"], "village_kr")
        self.assertEqual(interpretation["culture"], "korea")
        self.assertEqual(interpretation["period"], "early_modern")
        self.assertEqual(interpretation["dem_layer"], "dem5m")

    def test_statistics_are_carried_in_full(self):
        analytical = _payload()["analytical"]
        for key in (
            "n_observed",
            "n_background",
            "observed_mean",
            "background_mean",
            "mean_percentile",
            "cliffs_delta",
            "effect_magnitude",
            "p_value",
        ):
            self.assertIn(key, analytical)

    def test_seed_and_iterations_are_auditable(self):
        audit = _payload()["audit"]
        self.assertEqual(audit["iterations"], 500)
        self.assertEqual(audit["seed"], 42)


class SamplingRecordTests(unittest.TestCase):
    def test_complete_sample_records_no_shortfall(self):
        sampling = _payload()["analytical"]["sampling"]
        self.assertTrue(sampling["complete"])
        self.assertEqual(sampling["shortfall"], 0)

    def test_shortfall_is_computed_and_flagged(self):
        payload = _payload(
            sample=_sample_record(drawn=120, requested=800, complete=False)
        )
        sampling = payload["analytical"]["sampling"]
        self.assertEqual(sampling["shortfall"], 680)
        self.assertFalse(payload["audit"]["background_sample_complete"])

    def test_rejection_counts_are_preserved(self):
        sampling = _payload()["analytical"]["sampling"]
        self.assertEqual(sampling["rejected"]["nodata_or_slope"], 8000)
        self.assertEqual(sampling["rejected"]["near_observed"], 120)

    def test_missing_sample_record_does_not_break_the_payload(self):
        payload = _payload(sample=None)
        self.assertEqual(payload["analytical"]["sampling"]["drawn"], 0)


class EffectReportabilityTests(unittest.TestCase):
    def test_a_real_effect_is_marked_reportable(self):
        self.assertTrue(_payload()["audit"]["effect_reportable"])

    def test_negligible_effect_is_not_marked_reportable(self):
        # A small p-value on a negligible delta is sample size, not a finding.
        payload = _payload(
            comparison=_comparison(observed_mean=0.452, background_mean=0.45)
        )
        self.assertEqual(payload["analytical"]["effect_magnitude"], "negligible")
        self.assertFalse(payload["audit"]["effect_reportable"])


class UnusableComparisonTests(unittest.TestCase):
    def test_unusable_result_reports_the_reason_not_statistics(self):
        comparison = background_comparison(
            [0.7], [0.4, 0.5], background_policy="too few"
        )
        payload = _payload(comparison=comparison)
        self.assertFalse(payload["interpretation"]["usable"])
        self.assertEqual(payload["analytical"]["reason"], "insufficient_samples")
        self.assertNotIn("cliffs_delta", payload["analytical"])

    def test_unusable_markdown_says_so_plainly(self):
        comparison = background_comparison(
            [0.7], [0.4, 0.5], background_policy="too few"
        )
        text = _markdown(comparison=comparison)
        self.assertIn("not usable", text)
        self.assertNotIn("Cliff's delta", text)


class MarkdownTests(unittest.TestCase):
    def test_caveats_appear_before_the_numbers(self):
        text = _markdown()
        self.assertLess(
            text.index("What this does not establish"),
            text.index("## Analytical"),
            "claim limits must not be buried under the result",
        )

    def test_policy_is_printed_with_the_result(self):
        text = _markdown()
        self.assertIn("background policy:", text)
        self.assertIn("slope <= 25 deg", text)

    def test_shortfall_raises_a_visible_warning(self):
        text = _markdown(
            sample=_sample_record(drawn=120, requested=800, complete=False)
        )
        self.assertIn("WARNING", text)
        self.assertIn("not the background requested", text)

    def test_negligible_effect_carries_an_inline_note(self):
        text = _markdown(
            comparison=_comparison(observed_mean=0.452, background_mean=0.45)
        )
        self.assertIn("negligible", text)
        self.assertIn("reflects sample size", text)

    def test_markdown_reports_effect_size_alongside_the_p_value(self):
        text = _markdown()
        self.assertIn("Cliff's delta", text)
        self.assertIn("permutation p", text)


if __name__ == "__main__":
    unittest.main()

class ReportFileTests(unittest.TestCase):
    def test_writes_a_json_and_markdown_pair(self):
        with tempfile.TemporaryDirectory() as report_dir:
            paths = write_null_model_report_files(
                report_dir=report_dir,
                stamp=STAMP,
                site_layer_name="eupchi",
                comparison=_comparison(),
                sample=_sample_record(),
                profile_key="village_kr",
            )
            self.assertTrue(os.path.exists(paths["json_path"]))
            self.assertTrue(os.path.exists(paths["md_path"]))
            self.assertIn(STAMP, os.path.basename(paths["json_path"]))

    def test_written_json_keeps_the_policy_with_the_numbers(self):
        with tempfile.TemporaryDirectory() as report_dir:
            paths = write_null_model_report_files(
                report_dir=report_dir,
                stamp=STAMP,
                site_layer_name="eupchi",
                comparison=_comparison(),
                sample=_sample_record(),
            )
            with open(paths["json_path"], encoding="utf-8") as handle:
                data = json.load(handle)
        self.assertIn("slope <= 25 deg", data["interpretation"]["background_policy"])
        self.assertIn("cliffs_delta", data["analytical"])

    def test_written_markdown_matches_the_builder(self):
        common = {
            "stamp": STAMP,
            "site_layer_name": "eupchi",
            "comparison": _comparison(),
            "sample": _sample_record(),
        }
        with tempfile.TemporaryDirectory() as report_dir:
            paths = write_null_model_report_files(report_dir=report_dir, **common)
            with open(paths["md_path"], encoding="utf-8") as handle:
                written = handle.read()
        self.assertEqual(written, NullModelReportWriter.build_markdown(**common))

