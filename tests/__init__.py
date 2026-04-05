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

    class _FakeQVariant:
        String = "string"
        Int = "int"
        Double = "double"

    class _FakeQgsField:
        def __init__(self, name, *args, **kwargs):
            self._name = str(name)

        def name(self):
            return self._name

    class _FakeQgsFields(list):
        def indexFromName(self, name):
            for index, field in enumerate(self):
                if getattr(field, "name", lambda: None)() == name:
                    return index
            return -1

    class _FakeQgsGeometry:
        def __init__(self, payload=None):
            self._payload = payload

        @staticmethod
        def fromPointXY(point):
            return _FakeQgsGeometry(("point", point))

        @staticmethod
        def fromPolylineXY(points):
            return _FakeQgsGeometry(("polyline", points))

        @staticmethod
        def fromPolygonXY(rings):
            return _FakeQgsGeometry(("polygon", rings))

        def isEmpty(self):
            return self._payload is None

    class _FakeQgsFeature(dict):
        def __init__(self, fields=None):
            super().__init__()
            self._fields = fields
            self._geometry = None

        def setGeometry(self, geometry):
            self._geometry = geometry

        def geometry(self):
            return self._geometry

    qtcore_module.QLocale = _FakeQLocale
    qtcore_module.QVariant = _FakeQVariant
    core_module.QgsPointXY = _FakeQgsPointXY
    core_module.QgsFeature = _FakeQgsFeature
    core_module.QgsField = _FakeQgsField
    core_module.QgsFields = _FakeQgsFields
    core_module.QgsGeometry = _FakeQgsGeometry
    qgis_module.PyQt = pyqt_module
    pyqt_module.QtCore = qtcore_module
    qgis_module.core = core_module
    sys.modules["qgis"] = qgis_module
    sys.modules["qgis.core"] = core_module
    sys.modules["qgis.PyQt"] = pyqt_module
    sys.modules["qgis.PyQt.QtCore"] = qtcore_module
