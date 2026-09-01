"""Shared QGIS stub for the test suite.

The plugin imports ``qgis`` at module scope, but the QGIS runtime is not
installed in CI or in a plain local checkout.  This package installs one
stub for the whole suite.

It has to be the *only* stub installer that wins.  Several test modules
carry their own ``_install_qgis_stubs()`` helper guarded by
``if "qgis" in sys.modules: return``; because this package's ``__init__``
runs first, those helpers always return early.  So whatever they would
have registered must be covered here, or the module fails to import.  The
``__getattr__`` fallback below keeps that from turning into whack-a-mole:
any QGIS name we have not modelled explicitly resolves to an inert dummy.

Fakes with real behaviour (geometry, fields, features) are spelled out
because tests assert on what they return; everything else is a marker.
"""

import contextlib
import sys
import types
from importlib.machinery import ModuleSpec


def _make_module(name, is_package=False):
    """Build a stub module that ``importlib.util.find_spec`` accepts.

    Without a real ``__spec__`` a ``find_spec("qgis")`` lookup raises
    ``ValueError: qgis.__spec__ is None`` instead of reporting the module,
    and without ``__path__`` a dotted import of ``qgis.PyQt.QtWidgets``
    fails with "not a package".
    """
    module = types.ModuleType(name)
    module.__spec__ = ModuleSpec(name, loader=None, is_package=is_package)
    if is_package:
        module.__path__ = []
        module.__spec__.submodule_search_locations = module.__path__
    return module


if "qgis" not in sys.modules:

    class _Dummy:
        def __init__(self, *args, **kwargs):
            pass

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

    class _FakeQgsTask:
        def __init__(self, *args, **kwargs):
            pass

        def isActive(self):
            return False

        def isCanceled(self):
            return False

    class _FakeQgsMessageLog:
        @staticmethod
        def logMessage(*args, **kwargs):
            return None

    class _FakeQgis:
        Critical = 2
        Warning = 1
        Info = 0

    def _dummy_factory(module_name):
        """Mint an inert class on demand for un-modelled QGIS names."""

        def __getattr__(name):
            if name.startswith("__"):
                raise AttributeError(name)
            generated = type(name, (_Dummy,), {})
            setattr(sys.modules[module_name], name, generated)
            return generated

        return __getattr__

    qgis_module = _make_module("qgis", is_package=True)
    pyqt_module = _make_module("qgis.PyQt", is_package=True)
    qtcore_module = _make_module("qgis.PyQt.QtCore")
    qtgui_module = _make_module("qgis.PyQt.QtGui")
    qtwidgets_module = _make_module("qgis.PyQt.QtWidgets")
    core_module = _make_module("qgis.core")
    gui_module = _make_module("qgis.gui")
    processing_module = _make_module("qgis.processing")

    qtcore_module.QLocale = _FakeQLocale
    qtcore_module.QVariant = _FakeQVariant

    core_module.QgsPointXY = _FakeQgsPointXY
    core_module.QgsFeature = _FakeQgsFeature
    core_module.QgsField = _FakeQgsField
    core_module.QgsFields = _FakeQgsFields
    core_module.QgsGeometry = _FakeQgsGeometry
    core_module.QgsTask = _FakeQgsTask
    core_module.QgsMessageLog = _FakeQgsMessageLog
    core_module.Qgis = _FakeQgis
    core_module.edit = contextlib.nullcontext

    processing_module.run = lambda *args, **kwargs: {"OUTPUT": None}

    qgis_module.PyQt = pyqt_module
    qgis_module.core = core_module
    qgis_module.gui = gui_module
    qgis_module.processing = processing_module
    pyqt_module.QtCore = qtcore_module
    pyqt_module.QtGui = qtgui_module
    pyqt_module.QtWidgets = qtwidgets_module

    sys.modules["qgis"] = qgis_module
    sys.modules["qgis.core"] = core_module
    sys.modules["qgis.gui"] = gui_module
    sys.modules["qgis.processing"] = processing_module
    sys.modules["qgis.PyQt"] = pyqt_module
    sys.modules["qgis.PyQt.QtCore"] = qtcore_module
    sys.modules["qgis.PyQt.QtGui"] = qtgui_module
    sys.modules["qgis.PyQt.QtWidgets"] = qtwidgets_module

    for _name in (
        "qgis.core",
        "qgis.gui",
        "qgis.processing",
        "qgis.PyQt.QtCore",
        "qgis.PyQt.QtGui",
        "qgis.PyQt.QtWidgets",
    ):
        sys.modules[_name].__getattr__ = _dummy_factory(_name)
