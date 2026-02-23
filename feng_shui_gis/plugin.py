# -*- coding: utf-8 -*-
import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import (
    QgsFeatureRequest,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProject,
    QgsVectorLayer,
)

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
        self._selection_hooks = {}

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
        for layer_id, slot in list(self._selection_hooks.items()):
            layer = QgsProject.instance().mapLayer(layer_id)
            if layer is None:
                continue
            try:
                layer.selectionChanged.disconnect(slot)
            except TypeError:
                pass
        self._selection_hooks.clear()

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
            self._configure_layer_click_info(output_layer)

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

    def _insert_output_layers(self, layers_top_to_bottom):
        project = QgsProject.instance()
        root = project.layerTreeRoot()
        for index, layer in enumerate(layers_top_to_bottom):
            if not layer:
                continue
            project.addMapLayer(layer, False)
            root.insertLayer(index, layer)
            self._configure_layer_click_info(layer)

    def _configure_layer_click_info(self, layer):
        if not isinstance(layer, QgsVectorLayer):
            return

        field_names = {field.name() for field in layer.fields()}
        if "reason_ko" not in field_names and "fs_reason" not in field_names:
            return

        reason_index = layer.fields().indexFromName("reason_ko")
        if reason_index >= 0:
            layer.setFieldAlias(reason_index, "설명")
        fs_reason_index = layer.fields().indexFromName("fs_reason")
        if fs_reason_index >= 0:
            layer.setFieldAlias(fs_reason_index, "입지근거")

        if "term_ko" in field_names:
            layer.setDisplayExpression("\"term_ko\"")
            layer.setMapTipTemplate(
                "<h3>[% \"term_ko\" %]</h3>"
                "<p><b>이유</b>: [% coalesce(\"reason_ko\",'설명 없음') %]</p>"
                "<p><b>score</b>: [% \"score\" %], <b>rank</b>: [% \"rank\" %]</p>"
            )
            self._bind_reason_on_selection(layer, "reason_ko")
            return

        if "ridge_class" in field_names:
            layer.setDisplayExpression("\"ridge_class\" || ' #' || \"ridge_rank\"")
            layer.setMapTipTemplate(
                "<h3>[% \"ridge_class\" %] / #% \"ridge_rank\"</h3>"
                "<p><b>이유</b>: [% coalesce(\"reason_ko\",'설명 없음') %]</p>"
                "<p><b>strength</b>: [% \"strength\" %], <b>len</b>: [% \"len\" %]</p>"
            )
            self._bind_reason_on_selection(layer, "reason_ko")
            return

        if "stream_class" in field_names:
            layer.setDisplayExpression("\"stream_class\" || ' #' || \"stream_id\"")
            layer.setMapTipTemplate(
                "<h3>[% \"stream_class\" %] / #% \"stream_id\"</h3>"
                "<p><b>이유</b>: [% coalesce(\"reason_ko\",'설명 없음') %]</p>"
                "<p><b>order</b>: [% \"order\" %], <b>flow_acc</b>: [% \"flow_acc\" %]</p>"
            )
            self._bind_reason_on_selection(layer, "reason_ko")
            return

        if "fs_reason" in field_names:
            layer.setDisplayExpression("'fs_score=' || to_string(\"fs_score\")")
            layer.setMapTipTemplate(
                "<h3>입지 점수</h3>"
                "<p><b>이유</b>: [% coalesce(\"fs_reason\",'설명 없음') %]</p>"
            )
            self._bind_reason_on_selection(layer, "fs_reason")

    def _bind_reason_on_selection(self, layer, reason_field):
        if layer is None or layer.id() in self._selection_hooks:
            return

        def _on_selection(selected, _deselected, _clear):
            if not selected:
                return
            request = QgsFeatureRequest().setFilterFids([selected[0]])
            feature = next(layer.getFeatures(request), None)
            if feature is None:
                return

            value = feature[reason_field] if reason_field in feature.fields().names() else None
            message = str(value).strip() if value not in (None, "") else "설명 없음"
            if len(message) > 260:
                message = f"{message[:257]}..."
            self.iface.messageBar().pushInfo(f"{layer.name()} 설명", message)

        layer.selectionChanged.connect(_on_selection)
        self._selection_hooks[layer.id()] = _on_selection
