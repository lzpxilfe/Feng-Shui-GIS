import unittest

from feng_shui_gis.analysis_reasoning import (
    compose_hyeol_reason,
    compose_term_reason,
    enclosure_hint,
    sashinsa_hint,
    score_band_label,
    tpi_class_label,
    tpi_hint,
)


class AnalysisReasoningContractTests(unittest.TestCase):
    def test_score_band_and_hint_labels_follow_thresholds(self):
        self.assertEqual(score_band_label(None), "정보 없음")
        self.assertEqual(score_band_label(0.82), "매우 양호")
        self.assertEqual(tpi_hint(-0.2), "완만한 오목 지형에 가까움")
        self.assertEqual(tpi_class_label(0.2, 0.2), "산릉(山陵)")
        self.assertEqual(sashinsa_hint(0.6), "사신사 배치 양호")
        self.assertEqual(enclosure_hint(0.2), "장풍 미흡(개방지형)")

    def test_compose_term_reason_includes_mode_and_numeric_summary(self):
        text = compose_term_reason(
            term_id="an_san",
            adjusted_score=0.77,
            base_score=0.71,
            elev=123.4,
            delta_rel=0.024,
            target_rel=0.02,
            fit_score=0.81,
            radius_m=45.0,
            azimuth=90.0,
            mode="max",
            note="micro relief peak",
        )
        self.assertIn("후보입니다", text)
        self.assertIn("국지 최대점", text)
        self.assertIn("micro relief peak", text)

    def test_compose_hyeol_reason_includes_threshold_and_multi_factor_labels(self):
        text = compose_hyeol_reason(
            rank=1,
            selected_total=5,
            base_score=0.74,
            form_score=0.82,
            long_score=0.63,
            wet_score=0.58,
            tpi_norm=-0.03,
            conv_score=0.61,
            relief=18.2,
            center_elev=112.0,
            threshold=0.65,
            sashinsa_score=0.72,
            enclosure_index=0.68,
            large_tpi_norm=0.04,
        )
        self.assertIn("혈 후보 #1/5", text)
        self.assertIn("기준치보다 +0.090 높아 통과", text)
        self.assertIn("사신사", text)
        self.assertIn("장풍", text)


if __name__ == "__main__":
    unittest.main()
