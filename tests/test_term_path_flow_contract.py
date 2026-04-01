import unittest

from qgis.core import QgsPointXY

from feng_shui_gis.analysis_term_generation import generic_term_payload
from feng_shui_gis.analysis_term_links import link_ready_payload


class TermPathFlowContractTests(unittest.TestCase):
    def test_term_payloads_feed_link_ready_payload_consistently(self):
        terms = [
            generic_term_payload(
                term_id="jusan",
                term_name="Jusan",
                parent_id=1,
                rank=1,
                point=QgsPointXY(0, 0),
                elev=18.0,
                center_elev=15.0,
                base_score=0.8,
                relief=6.0,
                target_rel=0.3,
                fit_score=0.7,
                radius_m=30.0,
                azimuth=0.0,
                mode="max",
            ),
            generic_term_payload(
                term_id="dunoe",
                term_name="Dunoe",
                parent_id=1,
                rank=1,
                point=QgsPointXY(10, 5),
                elev=17.0,
                center_elev=15.0,
                base_score=0.78,
                relief=6.0,
                target_rel=0.2,
                fit_score=0.72,
                radius_m=28.0,
                azimuth=30.0,
                mode="max",
            ),
            generic_term_payload(
                term_id="jojongsan",
                term_name="Jojongsan",
                parent_id=1,
                rank=1,
                point=QgsPointXY(20, 12),
                elev=16.5,
                center_elev=15.0,
                base_score=0.81,
                relief=6.0,
                target_rel=0.15,
                fit_score=0.75,
                radius_m=26.0,
                azimuth=45.0,
                mode="max",
            ),
        ]
        nodes = [{"score": term["score"], "rank": term["rank"]} for term in terms]
        payload = link_ready_payload(
            nodes,
            [term["point"] for term in terms],
            spec={"link_type": "backbone"},
            min_link_score=0.6,
            distinct_min_distance=0.1,
            smooth_passes=1,
            to_float=float,
        )
        self.assertIsNotNone(payload)
        self.assertEqual(payload["rank_value"], 1)
        self.assertGreater(payload["length_m"], 0.0)
        self.assertGreaterEqual(payload["score"], 0.6)


if __name__ == "__main__":
    unittest.main()
