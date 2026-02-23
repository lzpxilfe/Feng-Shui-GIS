# -*- coding: utf-8 -*-
import json
import os
from datetime import datetime

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QDialog, QVBoxLayout, QTextBrowser
from qgis.core import (
    QgsFeatureRequest,
    QgsProject,
    QgsProcessingContext,
    QgsProcessingFeedback,
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
        self._reason_dialog = None
        self._reason_browser = None
        self._report_dialog = None
        self._report_browser = None

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

        if self._reason_dialog:
            self._reason_dialog.close()
            self._reason_dialog.deleteLater()
            self._reason_dialog = None
            self._reason_browser = None

        if self._report_dialog:
            self._report_dialog.close()
            self._report_dialog.deleteLater()
            self._report_dialog = None
            self._report_browser = None

    def toggle_panel(self):
        if self.dock is None:
            self.dock = FengShuiDockWidget(self.iface.mainWindow())
            self.dock.run_requested.connect(self.run_analysis)
            self.dock.terms_requested.connect(self.run_term_extraction)
            self.dock.calibration_requested.connect(self.run_calibration)
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

    def run_calibration(
        self,
        site_layer,
        dem_layer,
        water_layer,
        hemisphere,
        profile_key,
        culture_key,
        period_key,
        negative_ratio,
        random_seed,
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
            self.dock.set_status("캘리브레이션 실행 중...")
        self._warn_if_geographic(dem_layer)

        calibration_culture = "korea"
        if culture_key != "korea":
            self.iface.messageBar().pushWarning(
                tr("plugin_title"),
                "캘리브레이션은 한국 SHP 기준으로 korea 컨텍스트를 사용합니다.",
            )

        try:
            context = QgsProcessingContext()
            context.setProject(QgsProject.instance())
            feedback = QgsProcessingFeedback()
            analyzer = FengShuiAnalyzer(context=context, feedback=feedback)
            prepared_water = water_layer
            if prepared_water is None and auto_hydro:
                auto_hydro_layer = analyzer.build_hydro_network(dem_layer)
                if auto_hydro_layer and auto_hydro_layer.featureCount() > 0:
                    analyzer.style_hydro_network(auto_hydro_layer)
                    auto_hydro_layer.setName(f"{dem_layer.name()}_hydro_auto_calib")
                    QgsProject.instance().addMapLayer(auto_hydro_layer)
                    prepared_water = auto_hydro_layer

            scored_layer, report = analyzer.calibrate(
                site_layer=site_layer,
                dem_layer=dem_layer,
                water_layer=prepared_water,
                hemisphere=hemisphere,
                profile_key=profile_key,
                culture_key=calibration_culture,
                period_key=period_key,
                negative_ratio=negative_ratio,
                random_seed=random_seed,
            )
            scored_layer.setName(f"{site_layer.name()}_calibration")
            QgsProject.instance().addMapLayer(scored_layer)
            self._configure_layer_click_info(scored_layer)

            json_path, md_path = self._write_calibration_report(report)
            self._show_report_popup(report, json_path, md_path)

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
                f"캘리브레이션 완료: ROC_AUC={report.get('roc_auc', 0):.4f}, "
                f"PR_AUC={report.get('pr_auc', 0):.4f}"
            ),
        )
        if self.dock:
            self.dock.set_status("캘리브레이션 완료.")

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

        if "src_id" in field_names and "dst_id" in field_names:
            layer.setDisplayExpression(
                "\"term_ko\" || ' ' || \"src_id\" || '→' || \"dst_id\""
            )
            layer.setMapTipTemplate(
                "<h3>[% \"term_ko\" %] [% \"src_id\" %]→[% \"dst_id\" %]</h3>"
                "<p><b>이유</b>: [% coalesce(\"reason_ko\",'설명 없음') %]</p>"
                "<p><b>score</b>: [% \"score\" %], <b>len(m)</b>: [% \"len_m\" %], <b>azimuth</b>: [% \"azimuth\" %]</p>"
            )
            self._bind_reason_on_selection(layer, "reason_ko")
            return

        if "term_ko" in field_names:
            layer.setDisplayExpression("\"term_ko\"")
            if "fit_sc" in field_names:
                layer.setMapTipTemplate(
                    "<h3>[% \"term_ko\" %]</h3>"
                    "<p><b>이유</b>: [% coalesce(\"reason_ko\",'설명 없음') %]</p>"
                    "<p><b>score</b>: [% \"score\" %], <b>rank</b>: [% \"rank\" %], <b>fit</b>: [% \"fit_sc\" %]</p>"
                    "<p><b>delta</b>: [% \"delta_rel\" %], <b>target</b>: [% \"target_rel\" %], <b>radius(m)</b>: [% \"radius_m\" %]</p>"
                )
            else:
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
            if len(message) > 900:
                message = f"{message[:897]}..."
            self._show_reason_popup(f"{layer.name()} 설명", message)
            self.iface.messageBar().pushInfo(f"{layer.name()} 설명", message)

        layer.selectionChanged.connect(_on_selection)
        self._selection_hooks[layer.id()] = _on_selection

    def _show_reason_popup(self, title, message):
        if self._reason_dialog is None:
            self._reason_dialog = QDialog(self.iface.mainWindow())
            self._reason_dialog.setWindowTitle("피처 근거")
            self._reason_dialog.resize(640, 420)
            layout = QVBoxLayout(self._reason_dialog)
            self._reason_browser = QTextBrowser(self._reason_dialog)
            self._reason_browser.setOpenExternalLinks(True)
            self._reason_browser.setReadOnly(True)
            layout.addWidget(self._reason_browser)
        self._reason_dialog.setWindowTitle(title)
        safe = (
            str(message)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br/>")
        )
        self._reason_browser.setHtml(f"<h3>{title}</h3><p>{safe}</p>")
        self._reason_dialog.show()
        self._reason_dialog.raise_()
        self._reason_dialog.activateWindow()

    def _write_calibration_report(self, report):
        project_home = QgsProject.instance().homePath().strip()
        if not project_home:
            project_home = os.path.abspath(os.path.join(self.plugin_dir, ".."))
        report_dir = os.path.join(project_home, "reports")
        os.makedirs(report_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"feng_shui_calibration_{stamp}"
        json_path = os.path.join(report_dir, f"{base_name}.json")
        md_path = os.path.join(report_dir, f"{base_name}.md")

        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)

        markdown = (
            f"# Feng Shui Calibration Report ({stamp})\n\n"
            f"- Positive samples: {report.get('positive_count')}\n"
            f"- Negative samples: {report.get('negative_count')}\n"
            f"- Valid scored samples: {report.get('valid_count')}\n"
            f"- ROC AUC: {report.get('roc_auc', 0):.6f}\n"
            f"- PR AUC: {report.get('pr_auc', 0):.6f}\n"
            f"- Best F1: {report.get('best_f1', 0):.6f} @ threshold {report.get('best_f1_threshold', 0):.6f}\n"
            f"- Best Youden J: {report.get('best_youden_j', 0):.6f} @ threshold {report.get('best_youden_threshold', 0):.6f}\n\n"
            "## Context\n\n"
            f"- culture: {report.get('culture_key')}\n"
            f"- period: {report.get('period_key')}\n"
            f"- profile: {report.get('profile_key')}\n"
            f"- hemisphere: {report.get('hemisphere')}\n"
            f"- negative_ratio: {report.get('negative_ratio')}\n"
            f"- random_seed: {report.get('random_seed')}\n"
        )
        with open(md_path, "w", encoding="utf-8") as handle:
            handle.write(markdown)

        return json_path, md_path

    def _show_report_popup(self, report, json_path, md_path):
        if self._report_dialog is None:
            self._report_dialog = QDialog(self.iface.mainWindow())
            self._report_dialog.setWindowTitle("캘리브레이션 리포트")
            self._report_dialog.resize(760, 520)
            layout = QVBoxLayout(self._report_dialog)
            self._report_browser = QTextBrowser(self._report_dialog)
            self._report_browser.setOpenExternalLinks(True)
            self._report_browser.setReadOnly(True)
            layout.addWidget(self._report_browser)

        html = (
            "<h3>한국 SHP 캘리브레이션 결과</h3>"
            f"<p><b>ROC AUC</b>: {report.get('roc_auc', 0):.4f}<br/>"
            f"<b>PR AUC</b>: {report.get('pr_auc', 0):.4f}<br/>"
            f"<b>Positive</b>: {report.get('positive_count')} / "
            f"<b>Negative</b>: {report.get('negative_count')} / "
            f"<b>Valid</b>: {report.get('valid_count')}</p>"
            f"<p><b>Best F1</b>: {report.get('best_f1', 0):.4f} "
            f"(threshold={report.get('best_f1_threshold', 0):.4f})<br/>"
            f"<b>Best Youden J</b>: {report.get('best_youden_j', 0):.4f} "
            f"(threshold={report.get('best_youden_threshold', 0):.4f})</p>"
            f"<p><b>JSON</b>: {json_path}<br/><b>Markdown</b>: {md_path}</p>"
        )
        self._report_browser.setHtml(html)
        self._report_dialog.show()
        self._report_dialog.raise_()
        self._report_dialog.activateWindow()
