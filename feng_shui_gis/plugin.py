# -*- coding: utf-8 -*-
import os

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
        self.toolbar = None
        self.dock = None
        self.plugin_dir = os.path.dirname(__file__)

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, "yingyang.png")
        self.action = QAction(QIcon(icon_path), tr("plugin_title"), self.iface.mainWindow())
        self.action.triggered.connect(self.toggle_panel)
        self.iface.addToolBarIcon(self.action)
        self.toolbar = self.iface.addToolBar(tr("plugin_title"))
        self.toolbar.setObjectName("FengShuiGISToolbar")
        self.toolbar.addAction(self.action)
        self.toolbar.setVisible(True)
        self.iface.addPluginToMenu(tr("menu_title"), self.action)

    def unload(self):
        if self.action:
            self.iface.removeToolBarIcon(self.action)
            if self.toolbar:
                self.toolbar.removeAction(self.action)
            self.iface.removePluginMenu(tr("menu_title"), self.action)
            self.action.deleteLater()
            self.action = None
        if self.toolbar:
            self.toolbar.deleteLater()
            self.toolbar = None

        if self.dock:
            self.dock.close()
            self.dock.deleteLater()
            self.dock = None

    def toggle_panel(self):
        if self.dock is None:
            self.dock = FengShuiDockWidget(self.iface.mainWindow())
            self.dock.run_requested.connect(self.run_analysis)
            self.dock.terms_requested.connect(self.run_term_extraction)
        if self.dock.isVisible():
            self.dock.hide()
        else:
            self.dock.show()
            self.dock.raise_()
            self.dock.activateWindow()

    def run_analysis(
        self,
        site_layer,
        dem_layer,
        water_layer,
        hemisphere,
        profile_key,
        culture_key,
        period_key,
        auto_hydro,
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
        self._warn_if_geographic(dem_layer)

        try:
            context = QgsProcessingContext()
            context.setProject(QgsProject.instance())
            feedback = QgsProcessingFeedback()
            analyzer = FengShuiAnalyzer(context=context, feedback=feedback)
            prepared_water = water_layer
            auto_hydro_layer = None
            if prepared_water is None and auto_hydro:
                auto_hydro_layer = analyzer.build_hydro_network(dem_layer)
                if auto_hydro_layer and auto_hydro_layer.featureCount() > 0:
                    analyzer.style_hydro_network(auto_hydro_layer)
                    auto_hydro_layer.setName(f"{dem_layer.name()}_hydro_auto")
                    QgsProject.instance().addMapLayer(auto_hydro_layer)
                    prepared_water = auto_hydro_layer

            output_layer = analyzer.run(
                site_layer,
                dem_layer,
                water_layer=prepared_water,
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

    def run_term_extraction(
        self,
        dem_layer,
        water_layer,
        hemisphere,
        culture_key,
        period_key,
        auto_hydro,
        include_terms,
    ):
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
        self._warn_if_geographic(dem_layer)

        try:
            context = QgsProcessingContext()
            context.setProject(QgsProject.instance())
            feedback = QgsProcessingFeedback()
            analyzer = FengShuiAnalyzer(context=context, feedback=feedback)

            ridge_layer = analyzer.build_ridge_network(dem_layer)
            analyzer.style_ridge_network(ridge_layer)

            hydro_layer = None
            if water_layer is None and auto_hydro:
                hydro_layer = analyzer.build_hydro_network(dem_layer)
                if hydro_layer and hydro_layer.featureCount() > 0:
                    analyzer.style_hydro_network(hydro_layer)
                else:
                    hydro_layer = None

            terms_layer = None
            line_layer = None
            if include_terms:
                terms_layer = analyzer.extract_terms(
                    dem_layer,
                    hemisphere=hemisphere,
                    culture_key=culture_key,
                    period_key=period_key,
                )
                line_layer = analyzer.build_term_links(terms_layer)
                analyzer.style_term_points(terms_layer)
                analyzer.style_term_links(line_layer)

            layers_top_to_bottom = []
            if include_terms and terms_layer:
                layers_top_to_bottom.append(terms_layer)
            if include_terms and line_layer:
                layers_top_to_bottom.append(line_layer)
            if hydro_layer:
                layers_top_to_bottom.append(hydro_layer)
            layers_top_to_bottom.append(ridge_layer)
            self._insert_output_layers(layers_top_to_bottom)
        except Exception as exc:  # pylint: disable=broad-except
            self.iface.messageBar().pushCritical(
                tr("warn_failed"),
                str(exc),
            )
            if self.dock:
                self.dock.set_status(f"{tr('warn_failed')}: {exc}")
            return

        created = [f"{ridge_layer.name()} ({ridge_layer.featureCount()})"]
        if hydro_layer:
            created.insert(0, f"{hydro_layer.name()} ({hydro_layer.featureCount()})")
        if include_terms and line_layer and terms_layer:
            created.insert(0, f"{line_layer.name()} ({line_layer.featureCount()})")
            created.insert(0, f"{terms_layer.name()} ({terms_layer.featureCount()})")
        message_key = "ok_terms_finished" if include_terms else "ok_landscape_finished"
        self.iface.messageBar().pushSuccess(
            tr("plugin_title"),
            f"{tr(message_key)}: " + ", ".join(created),
        )
        if self.dock:
            self.dock.set_status(tr("status_done"))

    def _warn_if_geographic(self, layer):
        if layer and layer.crs().isGeographic():
            self.iface.messageBar().pushWarning(
                tr("plugin_title"),
                tr("warn_geographic_crs"),
            )

    @staticmethod
    def _insert_output_layers(layers_top_to_bottom):
        project = QgsProject.instance()
        root = project.layerTreeRoot()
        for index, layer in enumerate(layers_top_to_bottom):
            if not layer:
                continue
            project.addMapLayer(layer, False)
            root.insertLayer(index, layer)
