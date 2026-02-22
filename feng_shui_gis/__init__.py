# -*- coding: utf-8 -*-


def classFactory(iface):  # pylint: disable=invalid-name
    """QGIS uses this entrypoint to instantiate the plugin."""
    from .plugin import FengShuiGisPlugin

    return FengShuiGisPlugin(iface)
