import sys
import types


if "qgis" not in sys.modules:
    qgis_module = types.ModuleType("qgis")
    pyqt_module = types.ModuleType("qgis.PyQt")
    qtcore_module = types.ModuleType("qgis.PyQt.QtCore")
    core_module = types.ModuleType("qgis.core")

    class _FakeQLocale:
        @staticmethod
        def system():
            class _SystemLocale:
                @staticmethod
                def name():
                    return "en_US"

            return _SystemLocale()

    class _FakeQgsPointXY:
        def __init__(self, x=0.0, y=0.0):
            self._x = float(x)
            self._y = float(y)

        def x(self):
            return self._x

        def y(self):
            return self._y

    qtcore_module.QLocale = _FakeQLocale
    core_module.QgsPointXY = _FakeQgsPointXY
    qgis_module.PyQt = pyqt_module
    pyqt_module.QtCore = qtcore_module
    qgis_module.core = core_module
    sys.modules["qgis"] = qgis_module
    sys.modules["qgis.core"] = core_module
    sys.modules["qgis.PyQt"] = pyqt_module
    sys.modules["qgis.PyQt.QtCore"] = qtcore_module
