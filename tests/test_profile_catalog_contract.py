import unittest
import types
import sys


if "qgis" not in sys.modules:
    qgis_module = types.ModuleType("qgis")
    pyqt_module = types.ModuleType("qgis.PyQt")
    qtcore_module = types.ModuleType("qgis.PyQt.QtCore")

    class _FakeQLocale:
        @staticmethod
        def system():
            class _SystemLocale:
                @staticmethod
                def name():
                    return "en_US"

            return _SystemLocale()

    qtcore_module.QLocale = _FakeQLocale
    qgis_module.PyQt = pyqt_module
    pyqt_module.QtCore = qtcore_module
    sys.modules["qgis"] = qgis_module
    sys.modules["qgis.PyQt"] = pyqt_module
    sys.modules["qgis.PyQt.QtCore"] = qtcore_module

from feng_shui_gis.cultural_context import available_cultures, culture_visibility_tier
from feng_shui_gis.profile_catalog import available_profiles, profile_visibility_tier


class ProfileCatalogContractTests(unittest.TestCase):
    def test_profile_visibility_filters_hide_experimental_presets_by_default_scope(self):
        stable_profiles = set(available_profiles("stable"))
        experimental_profiles = set(available_profiles("experimental"))
        all_profiles = set(available_profiles())

        self.assertIn("general", stable_profiles)
        self.assertIn("tomb", stable_profiles)
        self.assertIn("house", stable_profiles)
        self.assertIn("well", experimental_profiles)
        self.assertIn("temple", experimental_profiles)
        self.assertIn("urban_real_estate", experimental_profiles)
        self.assertIn("global_apm", experimental_profiles)
        self.assertTrue(stable_profiles.issubset(all_profiles))
        self.assertTrue(experimental_profiles.issubset(all_profiles))
        self.assertEqual(profile_visibility_tier("global_apm"), "experimental")

    def test_context_visibility_marks_global_apm_as_experimental(self):
        stable_cultures = set(available_cultures("stable"))
        experimental_cultures = set(available_cultures("experimental"))

        self.assertIn("east_asia", stable_cultures)
        self.assertIn("global_apm", experimental_cultures)
        self.assertEqual(culture_visibility_tier("global_apm"), "experimental")


if __name__ == "__main__":
    unittest.main()
