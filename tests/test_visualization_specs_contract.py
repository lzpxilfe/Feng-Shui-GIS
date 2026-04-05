import unittest

from feng_shui_gis.visualization_specs import (
    hyeol_field_symbol_layers,
    hydro_symbol_profiles,
    mix_hex,
    rgba_from_hex,
    ridge_symbol_profiles,
    support_field_symbol_layers,
    term_link_symbol_layers,
    term_point_symbol_layers,
)


class VisualizationSpecsContractTests(unittest.TestCase):
    def test_rgba_from_hex_formats_qgis_color_string(self):
        self.assertEqual(rgba_from_hex("#0f4c81", 0.5), "15,76,129,128")

    def test_mix_hex_blends_toward_target(self):
        self.assertEqual(mix_hex("#000000", "#ffffff", 0.5), "#808080")

    def test_ridge_profiles_use_layered_ribbon_specs(self):
        profiles = ridge_symbol_profiles()
        self.assertIn("major", profiles)
        self.assertEqual(len(profiles["major"]["layers"]), 3)
        self.assertGreater(profiles["major"]["layers"][0]["width"], profiles["major"]["layers"][1]["width"])
        self.assertGreater(profiles["major"]["layers"][1]["width"], profiles["major"]["layers"][2]["width"])

    def test_hydro_profiles_keep_visual_hierarchy(self):
        profiles = hydro_symbol_profiles()
        self.assertGreater(
            profiles["main"]["layers"][1]["width"],
            profiles["minor"]["layers"][1]["width"],
        )

    def test_term_point_layers_emphasize_hyeol_more_than_regular_terms(self):
        hyeol_layers = term_point_symbol_layers("hyeol", ("#d62828", 4.8, "#240202", 0.9))
        ansan_layers = term_point_symbol_layers("ansan", ("#6aa84f", 3.3, "#245016", 0.7))
        self.assertGreater(hyeol_layers[0]["size"], ansan_layers[0]["size"])
        self.assertEqual(len(hyeol_layers), 3)

    def test_term_link_layers_are_three_stage_ribbons(self):
        layers = term_link_symbol_layers("ipsu", ("#0284c7", 2.6))
        self.assertEqual(len(layers), 3)
        self.assertGreater(layers[0]["width"], layers[1]["width"])
        self.assertGreater(layers[1]["width"], layers[2]["width"])

    def test_hyeol_field_layers_use_soft_fill_stack(self):
        layers = hyeol_field_symbol_layers()
        self.assertEqual(len(layers), 3)
        self.assertGreater(layers[0]["outline_width"], layers[1]["outline_width"])
        self.assertGreater(layers[1]["outline_width"], layers[2]["outline_width"])

    def test_support_field_layers_keep_sashinsa_broader_than_jangpung(self):
        sashinsa_layers = support_field_symbol_layers("sashinsa")
        jangpung_layers = support_field_symbol_layers("jangpung")
        self.assertEqual(len(sashinsa_layers), 3)
        self.assertEqual(len(jangpung_layers), 3)
        self.assertGreater(
            sashinsa_layers[0]["outline_width"],
            jangpung_layers[0]["outline_width"],
        )


if __name__ == "__main__":
    unittest.main()
