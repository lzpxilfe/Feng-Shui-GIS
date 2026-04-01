import contextlib
import sys
import types
import unittest


def _install_plugin_stubs():
    if "qgis" not in sys.modules:
        qgis_module = types.ModuleType("qgis")
        pyqt_module = types.ModuleType("qgis.PyQt")
        qtcore_module = types.ModuleType("qgis.PyQt.QtCore")
        qtgui_module = types.ModuleType("qgis.PyQt.QtGui")
        qtwidgets_module = types.ModuleType("qgis.PyQt.QtWidgets")
        core_module = types.ModuleType("qgis.core")

        class _Dummy:
            def __init__(self, *args, **kwargs):
                pass

        class _DummyTask:
            def __init__(self, *args, **kwargs):
                pass

            def isActive(self):
                return False

            def isCanceled(self):
                return False

        class _DummyMessageLog:
            @staticmethod
            def logMessage(*args, **kwargs):
                return None

        class _DummyQgis:
            Critical = 2
            Warning = 1

        qtcore_module.QVariant = object
        qtgui_module.QColor = _Dummy
        qtgui_module.QIcon = _Dummy
        qtwidgets_module.QAction = _Dummy
        qtwidgets_module.QDialog = _Dummy
        qtwidgets_module.QVBoxLayout = _Dummy
        qtwidgets_module.QTextBrowser = _Dummy

        for name in (
            "QgsApplication",
            "QgsCategorizedSymbolRenderer",
            "QgsFeature",
            "QgsFeatureRequest",
            "QgsField",
            "QgsProject",
            "QgsRendererCategory",
            "QgsSymbol",
            "QgsWkbTypes",
            "QgsVectorLayer",
        ):
            setattr(core_module, name, _Dummy)
        core_module.QgsMessageLog = _DummyMessageLog
        core_module.Qgis = _DummyQgis
        core_module.QgsTask = _DummyTask
        core_module.edit = contextlib.nullcontext

        qgis_module.PyQt = pyqt_module
        qgis_module.core = core_module

        sys.modules["qgis"] = qgis_module
        sys.modules["qgis.PyQt"] = pyqt_module
        sys.modules["qgis.PyQt.QtCore"] = qtcore_module
        sys.modules["qgis.PyQt.QtGui"] = qtgui_module
        sys.modules["qgis.PyQt.QtWidgets"] = qtwidgets_module
        sys.modules["qgis.core"] = core_module

    dock_widget_module = types.ModuleType("feng_shui_gis.dock_widget")
    dock_widget_module.FengShuiDockWidget = object
    sys.modules["feng_shui_gis.dock_widget"] = dock_widget_module

    service_contracts_module = types.ModuleType("feng_shui_gis.service_contracts")
    for name in (
        "AnalysisRequest",
        "CalibrationRequest",
        "CompareRequest",
        "TermExtractionRequest",
    ):
        setattr(service_contracts_module, name, object)
    sys.modules["feng_shui_gis.service_contracts"] = service_contracts_module

    services_module = types.ModuleType("feng_shui_gis.services")
    services_module.__path__ = []
    sys.modules["feng_shui_gis.services"] = services_module

    analysis_service_module = types.ModuleType("feng_shui_gis.services.analysis_service")

    class _DummyAnalysisService:
        def __init__(self, *args, **kwargs):
            pass

    analysis_service_module.FengShuiAnalysisService = _DummyAnalysisService
    sys.modules["feng_shui_gis.services.analysis_service"] = analysis_service_module

    locale_module = types.ModuleType("feng_shui_gis.locale")
    locale_module.tr = lambda key: key
    sys.modules["feng_shui_gis.locale"] = locale_module

    mountain_lookup_module = types.ModuleType("feng_shui_gis.mountain_lookup")
    mountain_lookup_module.MountainNameService = object
    sys.modules["feng_shui_gis.mountain_lookup"] = mountain_lookup_module

    mountain_options_module = types.ModuleType("feng_shui_gis.mountain_options")
    mountain_options_module.mountain_options = lambda: {}
    sys.modules["feng_shui_gis.mountain_options"] = mountain_options_module

    profile_catalog_module = types.ModuleType("feng_shui_gis.profile_catalog")
    profile_catalog_module.analysis_rules = lambda: {}
    profile_catalog_module.local_profiles_payload = lambda: {"schema_version": 1}
    profile_catalog_module.write_local_profiles_payload = lambda payload: payload
    sys.modules["feng_shui_gis.profile_catalog"] = profile_catalog_module

    reference_catalog_module = types.ModuleType("feng_shui_gis.reference_catalog")
    reference_catalog_module.reference_display_text = lambda *args, **kwargs: ""
    sys.modules["feng_shui_gis.reference_catalog"] = reference_catalog_module

    ui_catalog_module = types.ModuleType("feng_shui_gis.ui_catalog")
    ui_catalog_module.ui_text = lambda key, *args, default=None, **kwargs: default or key
    sys.modules["feng_shui_gis.ui_catalog"] = ui_catalog_module


_install_plugin_stubs()

from feng_shui_gis.plugin import FengShuiGisPlugin  # noqa: E402


class _FakeFields:
    def __init__(self, names):
        self._names = list(names)

    def names(self):
        return list(self._names)


class _FakeFeature:
    def __init__(self, fid, attrs):
        self._fid = fid
        self._attrs = dict(attrs)

    def fields(self):
        return _FakeFields(self._attrs.keys())

    def __getitem__(self, key):
        return self._attrs[key]

    def id(self):
        return self._fid

    def hasGeometry(self):
        return False

    def geometry(self):
        return None


class _FakeLayer:
    def __init__(self, features):
        self._features = list(features)

    def getFeatures(self):
        return iter(self._features)


class CompareContractTests(unittest.TestCase):
    def test_compare_feature_contract_rejects_uid_mismatch(self):
        base_layer = _FakeLayer(
            [
                _FakeFeature(1, {"fs_uid": "a", "fs_score": 0.4}),
                _FakeFeature(2, {"fs_uid": "b", "fs_score": 0.5}),
            ]
        )
        compare_layer = _FakeLayer(
            [
                _FakeFeature(10, {"fs_uid": "a", "fs_score": 0.8}),
                _FakeFeature(20, {"fs_uid": "c", "fs_score": 0.6}),
            ]
        )

        result = FengShuiGisPlugin._validate_compare_feature_contract(
            base_layer,
            compare_layer,
        )

        self.assertFalse(result["ok"])
        self.assertIn("Feature UID sets differ", result["message"])

    def test_compare_feature_contract_rejects_duplicate_uids(self):
        base_layer = _FakeLayer(
            [
                _FakeFeature(1, {"fs_uid": "a", "fs_score": 0.4}),
                _FakeFeature(2, {"fs_uid": "a", "fs_score": 0.5}),
            ]
        )
        compare_layer = _FakeLayer([_FakeFeature(10, {"fs_uid": "a", "fs_score": 0.8})])

        result = FengShuiGisPlugin._validate_compare_feature_contract(
            base_layer,
            compare_layer,
        )

        self.assertFalse(result["ok"])
        self.assertIn("Duplicate feature_uid", result["message"])

    def test_compare_top_change_contract_fails_when_uid_missing(self):
        result = FengShuiGisPlugin._validate_compare_top_change_contract(
            _FakeLayer([_FakeFeature(1, {"fs_uid": "a", "fs_score": 0.2})]),
            _FakeLayer([_FakeFeature(2, {"fs_uid": "a", "fs_score": 0.5})]),
            [{"label": "A"}],
        )

        self.assertFalse(result["ok"])
        self.assertIn("missing feature_uid", result["message"])

    def test_compare_top_change_contract_fails_when_row_uid_not_in_layers(self):
        base_layer = _FakeLayer([_FakeFeature(1, {"fs_uid": "a", "fs_score": 0.2})])
        compare_layer = _FakeLayer([_FakeFeature(2, {"fs_uid": "a", "fs_score": 0.5})])

        result = FengShuiGisPlugin._validate_compare_top_change_contract(
            base_layer,
            compare_layer,
            [{"feature_uid": "ghost"}],
        )

        self.assertFalse(result["ok"])
        self.assertIn("Top-change UID contract mismatch", result["message"])

    def test_top_score_changes_uses_feature_uid_not_feature_id(self):
        plugin = FengShuiGisPlugin(iface=object(), analysis_service=object())
        base_layer = _FakeLayer(
            [
                _FakeFeature(
                    1,
                    {
                        "fs_uid": "shared-a",
                        "fs_score": 0.25,
                        "name": "Site A",
                        "fs_reason": "base reason",
                    },
                ),
                _FakeFeature(2, {"fs_uid": "only-base", "fs_score": 0.60}),
            ]
        )
        compare_layer = _FakeLayer(
            [
                _FakeFeature(
                    999,
                    {
                        "fs_uid": "shared-a",
                        "fs_score": 0.82,
                        "name": "Site A Calibrated",
                        "fs_reason": "compare reason",
                    },
                ),
                _FakeFeature(1000, {"fs_uid": "only-compare", "fs_score": 0.15}),
            ]
        )

        rows = plugin._top_score_changes(base_layer, compare_layer, limit=5)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["feature_uid"], "shared-a")
        self.assertEqual(rows[0]["label"], "Site A Calibrated")
        self.assertAlmostEqual(rows[0]["delta"], 0.57, places=6)

    def test_feature_uids_to_fids_preserves_requested_order(self):
        layer = _FakeLayer(
            [
                _FakeFeature(100, {"fs_uid": "b"}),
                _FakeFeature(200, {"fs_uid": "a"}),
            ]
        )

        resolved = FengShuiGisPlugin._feature_uids_to_fids(layer, ["a", "b"])

        self.assertEqual(resolved, [200, 100])


if __name__ == "__main__":
    unittest.main()

