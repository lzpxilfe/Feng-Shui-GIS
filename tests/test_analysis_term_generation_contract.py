import unittest

from qgis.core import QgsPointXY

from feng_shui_gis.analysis_term_generation import (
    core_hyeol_term_payload,
    generic_term_payload,
    ipsu_term_payload,
    misa_term_payload,
    myeongdang_term_payload,
    relief_from_ring_values,
)


class AnalysisTermGenerationContractTests(unittest.TestCase):
    def test_relief_from_ring_values_uses_nonzero_floor(self):
        self.assertEqual(relief_from_ring_values([]), 1.0)
        self.assertEqual(relief_from_ring_values([10.0, 10.2, 10.4]), 1.0)
        self.assertEqual(relief_from_ring_values([10.0, 14.0]), 4.0)

    def test_core_hyeol_term_payload_marks_mandatory_core_candidate(self):
        payload = core_hyeol_term_payload(
            parent_id=1,
            rank=1,
            point=QgsPointXY(0, 0),
            base_score=0.72,
            center_elev=15.0,
            relief=3.5,
            reason_text="core reason",
            term_name="Hyeol",
        )
        self.assertEqual(payload["term_id"], "hyeol")
        self.assertTrue(payload["mandatory"])
        self.assertEqual(payload["reason_text"], "core reason")

    def test_special_and_generic_term_payloads_build_feature_ready_dicts(self):
        point = QgsPointXY(1, 2)
        myeongdang = myeongdang_term_payload(
            parent_id=1,
            rank=1,
            point=point,
            elev=18.0,
            center_elev=15.0,
            base_score=0.8,
            relief=6.0,
            target_rel=0.3,
            fit_score=0.6,
            radius_m=24.0,
            azimuth=180.0,
            term_name="Myeongdang",
        )
        generic = generic_term_payload(
            term_id="ansan",
            term_name="Ansan",
            parent_id=1,
            rank=1,
            point=point,
            elev=16.2,
            center_elev=15.0,
            base_score=0.8,
            relief=4.0,
            target_rel=0.2,
            fit_score=0.7,
            radius_m=32.0,
            azimuth=90.0,
            mode="max",
        )
        ipsu = ipsu_term_payload(
            parent_id=1,
            rank=1,
            point=point,
            elev=14.0,
            center_elev=15.0,
            base_score=0.8,
            relief=2.0,
            target_rel=-0.3,
            fit_score=0.5,
            radius_m=40.0,
            mode="min",
            term_name="Ipsu",
        )
        misa = misa_term_payload(
            parent_id=1,
            rank=1,
            point=point,
            elev=15.4,
            center_elev=15.0,
            base_score=0.8,
            relief=2.0,
            target_rel=0.1,
            fit_score=0.9,
            radius_m=18.0,
            azimuth=210.0,
            term_name="Misa",
        )
        self.assertEqual(myeongdang["mode"], "refine")
        self.assertTrue(myeongdang["mandatory"])
        self.assertEqual(generic["note"], "delta=0.300")
        self.assertEqual(ipsu["mode"], "min")
        self.assertEqual(misa["note"], "gentle delta=0.200")


if __name__ == "__main__":
    unittest.main()
