import unittest

from feng_shui_gis.analysis_principles import (
    build_principle_note,
    build_principle_records,
    build_principle_summary,
)


class AnalysisPrinciplesContractTests(unittest.TestCase):
    def test_build_principle_records_maps_current_metrics_to_core_principles(self):
        records = build_principle_records(
            indicators={"water": 0.61, "tpi": 0.66},
            dem_metrics={
                "form_score": 0.74,
                "long_score": 0.68,
                "tpi_norm": -0.03,
                "sashinsa_score": 0.71,
                "enclosure_index": 0.59,
                "dem_water_score": 0.53,
            },
            water_distance=72.0,
        )
        self.assertEqual([record["key"] for record in records], ["form", "hyeol", "sashinsa", "enclosure", "water"])
        self.assertEqual(records[0]["label"], "배산/형국")
        self.assertIn("TPI -0.0300", records[1]["detail"])
        self.assertIn("수계거리 72.0m", records[-1]["detail"])

    def test_build_principle_summary_prioritizes_principle_language(self):
        summary = build_principle_summary(
            build_principle_records(
                indicators={"water": 0.61, "tpi": 0.66},
                dem_metrics={
                    "form_score": 0.74,
                    "long_score": 0.68,
                    "tpi_norm": -0.03,
                    "sashinsa_score": 0.71,
                    "enclosure_index": 0.59,
                    "dem_water_score": 0.53,
                },
                water_distance=72.0,
            )
        )
        self.assertIn("배산/형국 양호", summary)
        self.assertIn("혈 조건 양호", summary)
        self.assertIn("득수/수계 관계 보통", summary)

    def test_build_principle_note_surfaces_strengths_and_cautions(self):
        note = build_principle_note(
            build_principle_records(
                indicators={"water": 0.32, "tpi": 0.62},
                dem_metrics={
                    "form_score": 0.78,
                    "long_score": 0.71,
                    "tpi_norm": -0.02,
                    "sashinsa_score": 0.69,
                    "enclosure_index": 0.28,
                    "dem_water_score": 0.41,
                },
                water_distance=110.0,
            )
        )
        self.assertIn("배산/형국", note)
        self.assertIn("보완 필요", note)
        self.assertLessEqual(len(note), 80)


if __name__ == "__main__":
    unittest.main()
