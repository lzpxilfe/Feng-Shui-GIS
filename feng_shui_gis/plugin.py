# -*- coding: utf-8 -*-
import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsProcessingContext, QgsProcessingFeedback, QgsProject

from .analysis import FengShuiAnalyzer
from .dock_widget import FengShuiDockWidget
from .locale import tr


class FengShuiGisPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dock = None
        self.plugin_dir = os.path.dirname(__file__)

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, "yingyang.png")
        self.action = QAction(QIcon(icon_path), tr("plugin_title"), self.iface.mainWindow())
        self.action.triggered.connect(self.toggle_panel)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(tr("menu_title"), self.action)

    def unload(self):
        if self.action:
            self.iface.removeToolBarIcon(self.action)
            self.iface.removePluginMenu(tr("menu_title"), self.action)
            self.action.deleteLater()
            self.action = None

        if self.dock:
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None

    def toggle_panel(self):
        if self.dock is None:
            self.dock = FengShuiDockWidget(self.iface.mainWindow())
            self.dock.run_requested.connect(self.run_analysis)
            self.dock.terms_requested.connect(self.run_term_extraction)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.dock.setVisible(not self.dock.isVisible())

    def run_analysis(
        self,
        site_layer,
        dem_layer,
        water_layer,
        hemisphere,
        profile_key,
        culture_key,
        period_key,
    ):
        if not site_layer or not dem_layer:
            self.iface.messageBar().pushWarning(
                tr("plugin_title"),
                tr("warn_missing_layers"),
            )
            if self.dock:
                self.dock.set_status(tr("warn_missing_layers"))
            return

        if self.dock:
            self.dock.set_status(tr("status_running"))

        try:
            context = QgsProcessingContext()
            context.setProject(QgsProject.instance())
            feedback = QgsProcessingFeedback()
            analyzer = FengShuiAnalyzer(context=context, feedback=feedback)
            output_layer = analyzer.run(
                site_layer,
                dem_layer,
                water_layer=water_layer,
                hemisphere=hemisphere,
                profile_key=profile_key,
                culture_key=culture_key,
                period_key=period_key,
            )
            output_layer.setName(f"{site_layer.name()}_fengshui")
            QgsProject.instance().addMapLayer(output_layer)

        except Exception as exc:  # pylint: disable=broad-except
            self.iface.messageBar().pushCritical(
                tr("warn_failed"),
                str(exc),
            )
            if self.dock:
                self.dock.set_status(f"{tr('warn_failed')}: {exc}")
            return

        self.iface.messageBar().pushSuccess(
            tr("plugin_title"),
            f"{tr('ok_finished')}: {output_layer.name()}",
        )
        if self.dock:
            self.dock.set_status(tr("status_done"))

    def run_term_extraction(self, dem_layer, hemisphere, culture_key, period_key):
        if not dem_layer:
            self.iface.messageBar().pushWarning(
                tr("plugin_title"),
                tr("warn_dem_required"),
            )
            if self.dock:
                self.dock.set_status(tr("warn_dem_required"))
            return

        if self.dock:
            self.dock.set_status(tr("status_terms_running"))

        try:
            context = QgsProcessingContext()
            context.setProject(QgsProject.instance())
            feedback = QgsProcessingFeedback()
            analyzer = FengShuiAnalyzer(context=context, feedback=feedback)
            terms_layer = analyzer.extract_terms(
                dem_layer,
                hemisphere=hemisphere,
                culture_key=culture_key,
                period_key=period_key,
            )
            line_layer = analyzer.build_term_links(terms_layer)
            analyzer.style_term_points(terms_layer)
            analyzer.style_term_links(line_layer)
            QgsProject.instance().addMapLayer(terms_layer)
            QgsProject.instance().addMapLayer(line_layer)
        except Exception as exc:  # pylint: disable=broad-except
            self.iface.messageBar().pushCritical(
                tr("warn_failed"),
                str(exc),
            )
            if self.dock:
                self.dock.set_status(f"{tr('warn_failed')}: {exc}")
            return

        self.iface.messageBar().pushSuccess(
            tr("plugin_title"),
            (
                f"{tr('ok_terms_finished')}: {terms_layer.name()} "
                f"({terms_layer.featureCount()}), {line_layer.name()} ({line_layer.featureCount()})"
            ),
        )
        if self.dock:
            self.dock.set_status(tr("status_done"))
