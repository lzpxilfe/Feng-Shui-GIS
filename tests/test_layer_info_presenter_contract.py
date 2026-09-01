import unittest

from feng_shui_gis.layer_info_presenter import (
    compare_layer_info_config,
    mountain_tip_html,
    site_layer_info_config,
)


class LayerInfoPresenterContractTests(unittest.TestCase):
    def test_mountain_tip_html_only_appears_when_mountain_fields_exist(self):
        self.assertEqual(
            mountain_tip_html(
                {"score"},
                maptip_mountain="Mountain",
                maptip_mountain_dist="Distance",
                maptip_mountain_lang="Language",
            ),
            "",
        )
        html = mountain_tip_html(
            {"mt_name"},
            maptip_mountain="Mountain",
            maptip_mountain_dist="Distance",
            maptip_mountain_lang="Language",
        )
        self.assertIn("mt_name", html)
        self.assertIn("Distance", html)

    def test_compare_layer_info_config_builds_gain_drop_maptip(self):
        config = compare_layer_info_config(
            {
                "cmp_label",
                "cmp_base",
                "cmp_score",
                "cmp_delta",
                "cmp_trend",
                "cmp_reason_b",
                "cmp_reason_c",
                "cmp_model",
            },
            reason_empty_lit="No description",
            mountain_tip="",
            compare_change_feature_alias="Feature",
            compare_change_base_alias="Base",
            compare_change_calibrated_alias="Calibrated",
            compare_change_delta_alias="Delta",
            compare_change_trend_alias="Trend",
            compare_change_reason_b_alias="Base reason",
            compare_change_reason_c_alias="Current reason",
            compare_change_model_alias="Model",
            compare_change_gain_label="Gain",
            compare_change_drop_label="Drop",
            compare_change_neutral_label="Near neutral",
        )
        self.assertEqual(config["display_expression"], "\"cmp_label\"")
        self.assertEqual(config["reason_field"], "fs_reason")
        self.assertIn("Gain", config["map_tip_template"])
        self.assertIn("cmp_reason_c", config["map_tip_template"])

    def test_site_layer_info_config_includes_threshold_tip_when_calibrated(self):
        config = site_layer_info_config(
            {"fs_reason", "cal_score", "cal_f1_th", "cal_yj_th"},
            reason_label="Reason",
            reason_empty_lit="No description",
            mountain_tip="",
            fs_score_title="Score",
            cal_score_title="Calibrated Score",
            site_alias_score="Score",
            site_alias_conf="Confidence",
            site_alias_slope="Slope",
            site_alias_aspect="Aspect",
            site_alias_form="Form",
            site_alias_long="Long",
            site_alias_water="Water",
            site_alias_dem_water="DEM Water",
            site_alias_tpi="TPI",
            site_alias_conv="Convergence",
            cal_score_alias="Calibrated Score",
            cal_f1_alias="F1 Threshold",
            cal_youden_alias="Youden Threshold",
            maptip_score="Score",
            maptip_coverage="Indicator coverage",
            maptip_components="Components",
            maptip_terrain="Terrain",
            maptip_dem_water="DEM Water",
            maptip_distance_water="Water distance",
            maptip_site_note="Site note",
            maptip_base_fs_score="Base score",
            maptip_best_f1_th="Best F1",
            maptip_best_youden_th="Best Youden",
            site_score_band_expr="'Moderate'",
            site_alias_missing="Not computed",
            maptip_missing="Not computed",
        )
        self.assertIn("cal_score", config["display_expression"])
        self.assertIn("Best F1", config["map_tip_template"])
        self.assertIn("Best Youden", config["map_tip_template"])


if __name__ == "__main__":
    unittest.main()
