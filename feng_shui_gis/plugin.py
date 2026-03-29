# -*- coding: utf-8 -*-
import json
import os
from datetime import datetime

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QDialog, QVBoxLayout, QTextBrowser
from qgis.core import (
    QgsFeatureRequest,
    QgsField,
    QgsProject,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsWkbTypes,
    QgsVectorLayer,
    edit,
)

from .analysis import FengShuiAnalyzer
from .cultural_context import (
    base_period_key,
    context_evidence_records,
    neutral_context_key,
)
from .dock_widget import FengShuiDockWidget
from .locale import tr
from .mountain_lookup import MountainNameService
from .mountain_options import mountain_options
from .profile_catalog import analysis_rules
from .ui_catalog import ui_text


class FengShuiGisPlugin:
    _OUTPUT_SUFFIXES = {
        "en": {
            "analysis": "fengshui",
            "calibration": "calibration",
            "ridge": "fengshui_ridges",
            "hydro": "fengshui_hydro",
            "terms": "fengshui_terms",
            "term_links": "fengshui_links",
            "hydro_auto": "hydro_auto",
            "hydro_auto_calibration": "hydro_auto_calib",
        },
        "ko": {
            "analysis": "풍수_입지평가",
            "calibration": "풍수_보정",
            "ridge": "풍수_산줄기",
            "hydro": "풍수_수계",
            "terms": "풍수_용어",
            "term_links": "풍수_구조연결",
            "hydro_auto": "풍수_자동수계",
            "hydro_auto_calibration": "풍수_자동수계_보정",
        },
    }

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
        self._context_warning_cache = set()

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
        label_lang = self._label_language()
        mountain_enabled, mountain_radius_m, mountain_max_features, mountain_lang = (
            self._mountain_name_options()
        )
        self._warn_low_evidence_context(culture_key, period_key, hemisphere)
        if not self._require_projected_dem_crs(dem_layer):
            return
        self._warn_if_crs_mismatch(dem_layer, site_layer, water_layer)

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
                    auto_hydro_layer.setName(
                        self._output_layer_name(dem_layer.name(), "hydro_auto", label_lang)
                    )
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
            output_layer.setName(self._output_layer_name(site_layer.name(), "analysis", label_lang))
            mountain_updated = 0
            if mountain_enabled:
                mountain_updated = self._enrich_layers_with_mountain_names(
                    [output_layer],
                    radius_m=mountain_radius_m,
                    max_features=mountain_max_features,
                    preferred_language=mountain_lang,
                )
            QgsProject.instance().addMapLayer(output_layer)
            self._configure_layer_click_info(output_layer, label_lang)

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
        if mountain_enabled and mountain_updated > 0:
            self.iface.messageBar().pushInfo(
                tr("plugin_title"),
                self._mountain_attached_message(mountain_updated),
            )
        if self.dock:
            self.dock.set_status(tr("status_done"))

    def run_term_extraction(
        self,
        dem_layer,
        water_layer,
        hemisphere,
        profile_key,
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
        label_lang = self._label_language()
        mountain_enabled, mountain_radius_m, mountain_max_features, mountain_lang = (
            self._mountain_name_options()
        )
        self._warn_low_evidence_context(culture_key, period_key, hemisphere)
        if not self._require_projected_dem_crs(dem_layer):
            return
        self._warn_if_crs_mismatch(dem_layer, water_layer)

        try:
            context = QgsProcessingContext()
            context.setProject(QgsProject.instance())
            feedback = QgsProcessingFeedback()
            analyzer = FengShuiAnalyzer(context=context, feedback=feedback)

            ridge_layer = analyzer.build_ridge_network(dem_layer)
            ridge_layer.setName(self._output_layer_name(dem_layer.name(), "ridge", label_lang))
            analyzer.style_ridge_network(ridge_layer)

            hydro_reference_layer = water_layer
            hydro_layer = None
            if water_layer is not None and self._is_line_layer(water_layer):
                hydro_layer = self._copy_vector_layer(
                    water_layer,
                    self._output_layer_name(dem_layer.name(), "hydro", label_lang),
                )
                if hydro_layer and hydro_layer.featureCount() > 0:
                    analyzer.style_hydro_network(hydro_layer)
                else:
                    hydro_layer = None
            elif auto_hydro:
                hydro_layer = analyzer.build_hydro_network(dem_layer)
                if hydro_layer and hydro_layer.featureCount() > 0:
                    hydro_layer.setName(
                        self._output_layer_name(dem_layer.name(), "hydro", label_lang)
                    )
                    analyzer.style_hydro_network(hydro_layer)
                    if hydro_reference_layer is None:
                        hydro_reference_layer = hydro_layer
                else:
                    hydro_layer = None

            terms_layer = None
            line_layer = None
            if include_terms:
                terms_layer = analyzer.extract_terms(
                    dem_layer,
                    water_layer=hydro_reference_layer,
                    hemisphere=hemisphere,
                    profile_key=profile_key,
                    culture_key=culture_key,
                    period_key=period_key,
                )
                terms_layer.setName(self._output_layer_name(dem_layer.name(), "terms", label_lang))
                line_layer = analyzer.build_term_links(terms_layer)
                line_layer.setName(self._output_layer_name(dem_layer.name(), "term_links", label_lang))
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
            mountain_total = 0
            if mountain_enabled:
                mountain_total = self._enrich_layers_with_mountain_names(
                    layers_top_to_bottom,
                    radius_m=mountain_radius_m,
                    max_features=mountain_max_features,
                    preferred_language=mountain_lang,
                )
            self._insert_output_layers(layers_top_to_bottom, label_lang)
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
        if mountain_enabled and mountain_total > 0:
            self.iface.messageBar().pushInfo(
                tr("plugin_title"),
                self._mountain_attached_message(mountain_total),
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
            self.dock.set_status(
                ui_text("calibration_status_running", default="Calibration in progress...")
            )
        label_lang = self._label_language()
        mountain_enabled, mountain_radius_m, mountain_max_features, mountain_lang = (
            self._mountain_name_options()
        )

        calibration_rules = analysis_rules().get("calibration", {})
        calibration_culture = calibration_rules.get("default_culture", "korea")
        if not isinstance(calibration_culture, str) or not calibration_culture.strip():
            calibration_culture = "korea"
        calibration_culture = calibration_culture.strip().lower()
        calibration_period = self._resolved_calibration_period(period_key)
        self._warn_low_evidence_context(
            calibration_culture,
            calibration_period,
            hemisphere,
        )
        if not self._require_projected_dem_crs(dem_layer):
            return
        self._warn_if_crs_mismatch(dem_layer, site_layer, water_layer)
        if culture_key != calibration_culture:
            self.iface.messageBar().pushWarning(
                tr("plugin_title"),
                ui_text(
                    "calibration_warning_template",
                    default="Calibration uses SHP baseline context: {culture}.",
                ).format(culture=calibration_culture),
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
                    auto_hydro_layer.setName(
                        self._output_layer_name(
                            dem_layer.name(),
                            "hydro_auto_calibration",
                            label_lang,
                        )
                    )
                    QgsProject.instance().addMapLayer(auto_hydro_layer)
                    prepared_water = auto_hydro_layer

            scored_layer, report = analyzer.calibrate(
                site_layer=site_layer,
                dem_layer=dem_layer,
                water_layer=prepared_water,
                hemisphere=hemisphere,
                profile_key=profile_key,
                culture_key=calibration_culture,
                period_key=calibration_period,
                negative_ratio=negative_ratio,
                random_seed=random_seed,
            )
            scored_layer.setName(
                self._output_layer_name(site_layer.name(), "calibration", label_lang)
            )
            mountain_updated = 0
            if mountain_enabled:
                mountain_updated = self._enrich_layers_with_mountain_names(
                    [scored_layer],
                    radius_m=mountain_radius_m,
                    max_features=mountain_max_features,
                    preferred_language=mountain_lang,
                )
            QgsProject.instance().addMapLayer(scored_layer)
            self._configure_layer_click_info(scored_layer, label_lang)

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
            ui_text(
                "calibration_success_template",
                default="Calibration done: ROC_AUC={roc_auc:.4f}, PR_AUC={pr_auc:.4f}",
            ).format(
                roc_auc=report.get("roc_auc", 0),
                pr_auc=report.get("pr_auc", 0),
            ),
        )
        if mountain_enabled and mountain_updated > 0:
            self.iface.messageBar().pushInfo(
                tr("plugin_title"),
                self._mountain_attached_message(mountain_updated),
            )
        if self.dock:
            self.dock.set_status(
                ui_text("calibration_status_done", default="Calibration completed.")
            )

    def _warn_if_geographic(self, layer):
        if layer and layer.crs().isGeographic():
            self.iface.messageBar().pushWarning(
                tr("plugin_title"),
                tr("warn_geographic_crs"),
            )

    def _output_layer_name(self, base_name, layer_kind, label_lang="ko"):
        language = label_lang if label_lang in self._OUTPUT_SUFFIXES else "ko"
        suffix = self._OUTPUT_SUFFIXES[language].get(layer_kind, layer_kind)
        clean_base = str(base_name).strip() if base_name is not None else ""
        clean_base = clean_base or "layer"
        return f"{clean_base}_{suffix}"

    @staticmethod
    def _is_line_layer(layer):
        if layer is None:
            return False
        return QgsWkbTypes.geometryType(layer.wkbType()) == QgsWkbTypes.LineGeometry

    @staticmethod
    def _copy_vector_layer(source_layer, layer_name):
        if source_layer is None:
            return None
        copied = source_layer.materialize(QgsFeatureRequest())
        if not isinstance(copied, QgsVectorLayer):
            return None
        copied.setName(layer_name)
        return copied

    def _require_projected_dem_crs(self, layer):
        if layer is None:
            return True
        crs = layer.crs()
        if crs is None or not crs.isValid():
            return True
        if not crs.isGeographic():
            return True

        text_lang = self._label_language()
        default_message = (
            "DEM 좌표계가 경위도(도 단위)입니다. 이 플러그인의 거리·반경 계산은 투영 좌표계가 필요합니다. "
            "미터 기반 CRS로 재투영한 뒤 다시 실행하세요."
            if text_lang == "ko"
            else (
                "DEM CRS is geographic (degrees). This plugin's distance and radius "
                "calculations require a projected CRS. Reproject the DEM to a meter-based "
                "CRS and run again."
            )
        )
        message = ui_text(
            "projected_crs_required",
            text_lang,
            default=default_message,
        )
        self.iface.messageBar().pushCritical(tr("plugin_title"), message)
        if self.dock:
            self.dock.set_status(message)
        return False

    def _warn_if_crs_mismatch(self, dem_layer, *other_layers):
        if dem_layer is None:
            return
        dem_crs = dem_layer.crs()
        if dem_crs is None or not dem_crs.isValid():
            return

        mismatched = []
        for layer in other_layers:
            if layer is None:
                continue
            layer_crs = layer.crs()
            if layer_crs is None or not layer_crs.isValid():
                continue
            if layer_crs != dem_crs:
                mismatched.append(layer.name())

        if not mismatched:
            return

        text_lang = self._label_language()
        message = ui_text(
            "warn_crs_mismatch_template",
            text_lang,
            default=(
                "DEM과 다른 CRS 레이어를 DEM CRS로 변환해 계산합니다: {layers}."
            ),
        ).format(layers=", ".join(mismatched))
        self.iface.messageBar().pushWarning(tr("plugin_title"), message)

    def _label_language(self):
        if self.dock and hasattr(self.dock, "label_language"):
            code = self.dock.label_language()
            if code in ("ko", "en"):
                return code
        return "ko"

    def _mountain_name_options(self):
        options = mountain_options()
        if not self.dock:
            return (
                False,
                options["radius_default_m"],
                options["max_features_default"],
                options["language_default"],
            )
        enabled = bool(options["enabled_default"])
        radius_m = int(options["radius_default_m"])
        max_features = int(options["max_features_default"])
        preferred_language = str(options["language_default"])
        if hasattr(self.dock, "mountain_name_enrichment_enabled"):
            enabled = bool(self.dock.mountain_name_enrichment_enabled())
        if hasattr(self.dock, "mountain_name_radius_m"):
            try:
                radius_m = int(self.dock.mountain_name_radius_m())
            except (TypeError, ValueError):
                radius_m = int(options["radius_default_m"])
        if hasattr(self.dock, "mountain_name_max_features"):
            try:
                max_features = int(self.dock.mountain_name_max_features())
            except (TypeError, ValueError):
                max_features = int(options["max_features_default"])
        if hasattr(self.dock, "mountain_name_language_preference"):
            preferred_language = str(self.dock.mountain_name_language_preference())
        if preferred_language not in ("local", "ko", "en"):
            preferred_language = options["language_default"]
        radius_m = max(
            int(options["radius_min_m"]),
            min(int(options["radius_max_m"]), int(radius_m)),
        )
        max_features = max(
            int(options["max_features_min"]),
            min(int(options["max_features_max"]), int(max_features)),
        )
        return enabled, radius_m, max_features, preferred_language

    def _mountain_attached_message(self, count):
        text_lang = self._label_language()
        options = mountain_options()
        source = str(options.get("source_label", "OSM/Overpass")).strip() or "OSM/Overpass"
        template = ui_text(
            "mountain_attach_success_template",
            text_lang,
            default="Attached mountain names to {count} features ({source}).",
        )
        return template.format(count=max(0, int(count)), source=source)

    @staticmethod
    def _resolved_calibration_period(period_key):
        neutral_key = neutral_context_key()
        normalized = str(period_key or "").strip().lower()
        if not normalized or normalized == neutral_key:
            return base_period_key()
        return period_key

    @staticmethod
    def _feature_anchor_point(feature):
        if feature is None or not feature.hasGeometry():
            return None
        geom = feature.geometry()
        if geom is None or geom.isEmpty():
            return None

        if geom.type() == QgsWkbTypes.PointGeometry:
            point = geom.asPoint()
            return point if point is not None else None

        centroid = geom.centroid()
        if centroid is not None and not centroid.isEmpty():
            point = centroid.asPoint()
            if point is not None:
                return point

        surface = geom.pointOnSurface()
        if surface is not None and not surface.isEmpty():
            point = surface.asPoint()
            if point is not None:
                return point
        return None

    @staticmethod
    def _feature_priority(feature, field_names):
        def _safe_int(value):
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        def _safe_float(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        if "rank" in field_names:
            rank_value = _safe_int(feature["rank"])
            if rank_value is not None:
                return (0, rank_value, int(feature.id()))
        if "ridge_rank" in field_names:
            rank_value = _safe_int(feature["ridge_rank"])
            if rank_value is not None:
                return (1, rank_value, int(feature.id()))
        if "stream_id" in field_names:
            stream_id = _safe_int(feature["stream_id"])
            if stream_id is not None:
                return (2, stream_id, int(feature.id()))
        if "fs_score" in field_names:
            fs_score = _safe_float(feature["fs_score"])
            if fs_score is not None:
                return (3, -fs_score, int(feature.id()))
        return (9, int(feature.id()), 0)

    def _enrich_layers_with_mountain_names(
        self,
        layers,
        radius_m=None,
        max_features=None,
        preferred_language=None,
    ):
        valid_layers = []
        for layer in layers:
            if not isinstance(layer, QgsVectorLayer):
                continue
            if layer.wkbType() == QgsWkbTypes.NoGeometry:
                continue
            if layer.featureCount() <= 0:
                continue
            valid_layers.append(layer)
        if not valid_layers:
            return 0

        service = MountainNameService(project=QgsProject.instance())
        layers_by_crs = {}
        for layer in valid_layers:
            crs = layer.crs()
            crs_key = crs.authid() if crs is not None and crs.isValid() else str(id(layer))
            group = layers_by_crs.setdefault(crs_key, {"crs": crs, "layers": []})
            group["layers"].append(layer)

        total_updated = 0
        for group in layers_by_crs.values():
            group_layers = group["layers"]
            combined_extent = None
            for layer in group_layers:
                extent = layer.extent()
                if extent is None or extent.isEmpty():
                    continue
                if combined_extent is None:
                    combined_extent = layer.extent()
                else:
                    combined_extent.combineExtentWith(extent)

            group_candidates = None
            if combined_extent is not None and not combined_extent.isEmpty():
                group_candidates = service.fetch_candidates_for_extent(
                    combined_extent,
                    group["crs"],
                )
            shared_candidates = group_candidates if group_candidates else None

            for layer in group_layers:
                total_updated += self._enrich_layer_with_mountain_names(
                    layer,
                    radius_m=radius_m,
                    max_features=max_features,
                    preferred_language=preferred_language,
                    service=service,
                    candidates=shared_candidates,
                )
        return total_updated

    def _enrich_layer_with_mountain_names(
        self,
        layer,
        radius_m=None,
        max_features=None,
        preferred_language=None,
        service=None,
        candidates=None,
    ):
        if not isinstance(layer, QgsVectorLayer):
            return 0
        if layer.wkbType() == QgsWkbTypes.NoGeometry:
            return 0
        if layer.featureCount() <= 0:
            return 0

        options = mountain_options()
        if radius_m is None:
            radius_m = options["radius_default_m"]
        if max_features is None:
            max_features = options["max_features_default"]
        if preferred_language is None:
            preferred_language = options["language_default"]
        if preferred_language not in ("local", "ko", "en"):
            preferred_language = options["language_default"]
        radius_m = max(
            int(options["radius_min_m"]),
            min(int(options["radius_max_m"]), int(radius_m)),
        )
        max_features = max(
            int(options["max_features_min"]),
            min(int(options["max_features_max"]), int(max_features)),
        )

        if service is None:
            service = MountainNameService(project=QgsProject.instance())
        if candidates is None:
            candidates = service.fetch_candidates_for_extent(layer.extent(), layer.crs())
        if not candidates:
            return 0

        field_names = {field.name() for field in layer.fields()}
        to_add = []
        if "mt_name" not in field_names:
            to_add.append(QgsField("mt_name", QVariant.String, "string", 96))
        if "mt_dist_m" not in field_names:
            to_add.append(QgsField("mt_dist_m", QVariant.Double, "double", 12, 1))
        if "mt_source" not in field_names:
            to_add.append(QgsField("mt_source", QVariant.String, "string", 24))
        if "mt_lang" not in field_names:
            to_add.append(QgsField("mt_lang", QVariant.String, "string", 10))
        if to_add:
            layer.dataProvider().addAttributes(to_add)
            layer.updateFields()
            field_names = {field.name() for field in layer.fields()}

        features = [feature for feature in layer.getFeatures() if feature.hasGeometry()]
        features.sort(key=lambda feature: self._feature_priority(feature, field_names))
        selected = features[: max(1, int(max_features))]

        updated = 0
        with edit(layer):
            for feature in selected:
                point = self._feature_anchor_point(feature)
                nearest = service.nearest_name(
                    point=point,
                    source_crs=layer.crs(),
                    candidates=candidates,
                    max_distance_m=radius_m,
                    preferred_language=preferred_language,
                )
                if nearest is None:
                    continue
                feature["mt_name"] = nearest.get("name")
                feature["mt_dist_m"] = nearest.get("distance_m")
                feature["mt_source"] = nearest.get("source")
                feature["mt_lang"] = nearest.get("name_language")
                layer.updateFeature(feature)
                updated += 1
        return updated

    @staticmethod
    def _score_band_expr(field_name):
        return (
            f"CASE "
            f"WHEN \"{field_name}\" IS NULL THEN 'n/a' "
            f"WHEN \"{field_name}\" >= 0.80 THEN 'strong' "
            f"WHEN \"{field_name}\" >= 0.65 THEN 'good' "
            f"WHEN \"{field_name}\" >= 0.50 THEN 'moderate' "
            f"ELSE 'weak' END"
        )

    def _set_field_aliases(self, layer, alias_map):
        for field_name, alias in alias_map.items():
            if not alias:
                continue
            index = layer.fields().indexFromName(field_name)
            if index >= 0:
                layer.setFieldAlias(index, alias)

    @staticmethod
    def _safe_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _term_display_name(self, feature, text_lang):
        fields = {field.name() for field in feature.fields()}
        if text_lang == "en":
            for key in ("term_name", "term_en", "term_id", "term_ko"):
                if key in fields and feature[key] not in (None, ""):
                    return str(feature[key])
        for key in ("term_ko", "term_name", "term_id", "term_en"):
            if key in fields and feature[key] not in (None, ""):
                return str(feature[key])
        return "term"

    def _feature_mountain_text(self, feature, text_lang):
        fields = {field.name() for field in feature.fields()}
        if "mt_name" not in fields or feature["mt_name"] in (None, ""):
            return ""
        name = str(feature["mt_name"])
        distance_text = ""
        if "mt_dist_m" in fields:
            distance = self._safe_float(feature["mt_dist_m"])
            if distance is not None:
                if text_lang == "en":
                    distance_text = f", {distance:.0f}m"
                else:
                    distance_text = f", 약 {distance:.0f}m"
        return f"{name}{distance_text}"

    def _term_component_text(self, feature, text_lang):
        name = self._term_display_name(feature, text_lang)
        score = self._safe_float(feature["score"]) if "score" in feature.fields().names() else None
        score_text = f"{score:.3f}" if score is not None else "n/a"
        mountain = self._feature_mountain_text(feature, text_lang)
        if mountain:
            if text_lang == "en":
                return f"{name}(score={score_text}, mountain={mountain})"
            return f"{name}(점수={score_text}, 산명={mountain})"
        if text_lang == "en":
            return f"{name}(score={score_text})"
        return f"{name}(점수={score_text})"

    def _collect_term_cluster(self, layer, parent_id):
        if parent_id in (None, ""):
            return {}
        field_names = {field.name() for field in layer.fields()}
        if "term_id" not in field_names or "parent_id" not in field_names:
            return {}

        picked = {}
        for item in layer.getFeatures():
            if item["parent_id"] != parent_id:
                continue
            term_id = str(item["term_id"]).strip()
            if not term_id:
                continue
            current = picked.get(term_id)
            if current is None:
                picked[term_id] = item
                continue
            current_score = self._safe_float(current["score"]) if "score" in field_names else None
            next_score = self._safe_float(item["score"]) if "score" in field_names else None
            if next_score is None:
                continue
            if current_score is None or next_score > current_score:
                picked[term_id] = item
        return picked

    def _term_cluster_reason(self, layer, feature, text_lang):
        field_names = {field.name() for field in layer.fields()}
        if "term_id" not in field_names or "parent_id" not in field_names:
            return ""
        term_id = str(feature["term_id"]).strip() if feature["term_id"] is not None else ""
        parent_id = feature["parent_id"]
        cluster = self._collect_term_cluster(layer, parent_id)
        if len(cluster) < 2:
            return ""

        def _group(term_ids):
            parts = []
            for key in term_ids:
                node = cluster.get(key)
                if node is not None:
                    parts.append(self._term_component_text(node, text_lang))
            return parts

        core = _group(["hyeol", "myeongdang"])
        rear = _group(["jusan", "dunoe", "jojongsan"])
        left = _group(["naecheongnyong", "oecheongnyong"])
        right = _group(["naebaekho", "oebaekho"])
        front = _group(["ansan", "josan", "misa"])
        water = _group(["naesugu", "oesugu", "ipsu"])
        missing_count = max(0, 14 - len(cluster))

        if text_lang == "en":
            lines = [
                "Morphology hierarchy (same parent cluster)",
                f"- core: {', '.join(core) if core else 'insufficient'}",
                f"- rear spine: {', '.join(rear) if rear else 'insufficient'}",
                f"- left support (cheongnyong): {', '.join(left) if left else 'insufficient'}",
                f"- right support (baekho): {', '.join(right) if right else 'insufficient'}",
                f"- frontal guard: {', '.join(front) if front else 'insufficient'}",
                f"- water gates/flow: {', '.join(water) if water else 'insufficient'}",
                f"- missing components: {missing_count}",
            ]
            if term_id == "hyeol":
                lines.append(
                    "- hyeol is explained from the full hierarchy above; "
                    "support terms can be sparse if local topography is weak."
                )
            return "\n".join(lines)

        lines = [
            "형국 계층 요약(같은 parent 묶음)",
            f"- 핵심(혈/명당): {', '.join(core) if core else '정보 부족'}",
            f"- 배후 축선(주산/둔뇌/조종산): {', '.join(rear) if rear else '정보 부족'}",
            f"- 좌청룡 계열: {', '.join(left) if left else '정보 부족'}",
            f"- 우백호 계열: {', '.join(right) if right else '정보 부족'}",
            f"- 전면 방어(안산/조산/미사): {', '.join(front) if front else '정보 부족'}",
            f"- 수구/입수 계열: {', '.join(water) if water else '정보 부족'}",
            f"- 미검출 항목 수: {missing_count}",
        ]
        if term_id == "hyeol":
            lines.append(
                "- 혈은 상위/하위 형국을 종합해서 판정하므로, "
                "내청룡·외백호 같은 단일 항목보다 설명이 길게 제공됩니다."
            )
        return "\n".join(lines)

    def _warn_low_evidence_context(self, culture_key, period_key, hemisphere):
        neutral_key = neutral_context_key()
        if culture_key == neutral_key or period_key == neutral_key:
            return

        warning_key = f"{culture_key}|{period_key}|{hemisphere}"
        if warning_key in self._context_warning_cache:
            return

        records = context_evidence_records(culture_key, period_key, hemisphere)
        if not records:
            return

        counts = {"A": 0, "B": 0, "C": 0, "U": 0}
        for item in records:
            level = str(item.get("evidence_level", "U")).upper()
            if level not in counts:
                level = "U"
            counts[level] += 1

        total = max(1, sum(counts.values()))
        low_count = counts["C"] + counts["U"]
        low_ratio = low_count / total
        if low_count <= 0 or low_ratio < 0.25:
            self._context_warning_cache.add(warning_key)
            return

        text_lang = self._label_language()
        warning = ui_text(
            "context_quality_warning",
            text_lang,
            default=(
                "Context evidence includes heuristic priors (C/U): {low}/{total}. "
                "Treat this run as exploratory and validate with local calibration."
            ),
        ).format(low=low_count, total=total)
        self.iface.messageBar().pushWarning(tr("plugin_title"), warning)
        self._context_warning_cache.add(warning_key)

    def _insert_output_layers(self, layers_top_to_bottom, label_lang="ko"):
        project = QgsProject.instance()
        root = project.layerTreeRoot()
        for index, layer in enumerate(layers_top_to_bottom):
            if not layer:
                continue
            project.addMapLayer(layer, False)
            root.insertLayer(index, layer)
            self._configure_layer_click_info(layer, label_lang)

    def _configure_layer_click_info(self, layer, label_lang="ko"):
        if not isinstance(layer, QgsVectorLayer):
            return

        field_names = {field.name() for field in layer.fields()}
        if "reason_ko" not in field_names and "fs_reason" not in field_names:
            return

        text_lang = label_lang if label_lang in ("ko", "en") else "ko"
        reason_alias = ui_text("reason_alias", text_lang, default="Reason")
        fs_reason_alias = ui_text("fs_reason_alias", text_lang, default="Site Reason")
        reason_label = ui_text("reason_label", text_lang, default="Reason")
        reason_empty = ui_text("reason_empty", text_lang, default="No description")
        fs_score_title = ui_text("fs_score_title", text_lang, default="Site Score")
        link_arrow = ui_text("link_arrow", text_lang, default="->")
        maptip_score = ui_text("maptip_score_label", text_lang, default="score")
        maptip_len_m = ui_text("maptip_len_m_label", text_lang, default="len(m)")
        maptip_azimuth = ui_text("maptip_azimuth_label", text_lang, default="azimuth")
        maptip_rank = ui_text("maptip_rank_label", text_lang, default="rank")
        maptip_fit = ui_text("maptip_fit_label", text_lang, default="fit")
        maptip_delta = ui_text("maptip_delta_label", text_lang, default="delta")
        maptip_target = ui_text("maptip_target_label", text_lang, default="target")
        maptip_radius_m = ui_text("maptip_radius_m_label", text_lang, default="radius(m)")
        maptip_strength = ui_text("maptip_strength_label", text_lang, default="strength")
        maptip_len = ui_text("maptip_len_label", text_lang, default="len")
        maptip_order = ui_text("maptip_order_label", text_lang, default="order")
        maptip_flow_acc = ui_text("maptip_flow_acc_label", text_lang, default="flow_acc")
        maptip_mountain = ui_text("maptip_mountain_label", text_lang, default="mountain")
        maptip_mountain_dist = ui_text("maptip_mountain_dist_label", text_lang, default="mountain_dist(m)")
        maptip_mountain_lang = ui_text("maptip_mountain_lang_label", text_lang, default="mountain_lang")
        alias_mountain_name = ui_text("mountain_alias_name", text_lang, default="Nearby mountain")
        alias_mountain_dist = ui_text("mountain_alias_dist", text_lang, default="Mountain distance (m)")
        alias_mountain_source = ui_text("mountain_alias_source", text_lang, default="Mountain source")
        alias_mountain_lang = ui_text("mountain_alias_lang", text_lang, default="Mountain name language")
        link_alias_score = ui_text("link_alias_score", text_lang, default="Link score (0-1)")
        link_alias_len_m = ui_text("link_alias_len_m", text_lang, default="Link length (m)")
        link_alias_azimuth = ui_text("link_alias_azimuth", text_lang, default="Direction (deg)")
        link_alias_rank = ui_text("link_alias_rank", text_lang, default="Candidate rank")
        term_alias_score = ui_text("term_alias_score", text_lang, default="Term score (0-1)")
        term_alias_fit = ui_text("term_alias_fit", text_lang, default="Shape fit (0-1)")
        term_alias_delta = ui_text("term_alias_delta", text_lang, default="Relative elevation delta")
        term_alias_target = ui_text("term_alias_target", text_lang, default="Expected relative delta")
        term_alias_radius = ui_text("term_alias_radius", text_lang, default="Search radius (m)")
        term_alias_relief = ui_text("term_alias_relief", text_lang, default="Local relief (m)")
        term_alias_rank = ui_text("term_alias_rank", text_lang, default="Candidate rank")
        ridge_alias_strength = ui_text("ridge_alias_strength", text_lang, default="Ridge strength (0-1)")
        ridge_alias_score = ui_text("ridge_alias_score", text_lang, default="Ridge rank score (0-1)")
        ridge_alias_len = ui_text("ridge_alias_len", text_lang, default="Ridge length (map units)")
        hydro_alias_order = ui_text("hydro_alias_order", text_lang, default="Stream order")
        hydro_alias_flow_acc = ui_text("hydro_alias_flow_acc", text_lang, default="Flow accumulation proxy")
        hydro_alias_len = ui_text("hydro_alias_len", text_lang, default="Stream length (map units)")
        site_alias_score = ui_text("site_alias_score", text_lang, default="Site score (0-1)")
        site_alias_conf = ui_text("site_alias_conf", text_lang, default="Confidence (0-1)")
        site_alias_slope = ui_text("site_alias_slope", text_lang, default="Slope fit (0-1)")
        site_alias_aspect = ui_text("site_alias_aspect", text_lang, default="Aspect fit (0-1)")
        site_alias_form = ui_text("site_alias_form", text_lang, default="Form fit (0-1)")
        site_alias_long = ui_text("site_alias_long", text_lang, default="Fore-aft fit (0-1)")
        site_alias_water = ui_text("site_alias_water", text_lang, default="Water fit (0-1)")
        site_alias_dem_water = ui_text("site_alias_dem_water", text_lang, default="DEM wetness fit (0-1)")
        site_alias_tpi = ui_text("site_alias_tpi", text_lang, default="Topographic position index")
        site_alias_conv = ui_text("site_alias_conv", text_lang, default="Convergence (0-1)")
        maptip_confidence = ui_text("maptip_confidence_label", text_lang, default="confidence")
        maptip_components = ui_text("maptip_components_label", text_lang, default="Component fits")
        maptip_terrain = ui_text("maptip_terrain_label", text_lang, default="Terrain metrics")
        maptip_dem_water = ui_text("maptip_dem_water_label", text_lang, default="dem_water")
        maptip_distance_water = ui_text(
            "maptip_distance_water_label",
            text_lang,
            default="distance_to_water(m)",
        )
        maptip_link_note = ui_text(
            "maptip_link_note",
            text_lang,
            default="score=overall structural fit (0-1). Higher is stronger.",
        )
        maptip_term_note = ui_text(
            "maptip_term_note",
            text_lang,
            default="fit=how close delta is to target. score=overall term suitability.",
        )
        maptip_ridge_note = ui_text(
            "maptip_ridge_note",
            text_lang,
            default="strength reflects local prominence and connectivity.",
        )
        maptip_hydro_note = ui_text(
            "maptip_hydro_note",
            text_lang,
            default="order=hierarchy in drainage graph, flow_acc=upstream support.",
        )
        maptip_site_note = ui_text(
            "maptip_site_note",
            text_lang,
            default=(
                "0-1 fits: higher is better. TPI near 0 is flatter; "
                "negative is concave; positive is convex."
            ),
        )
        reason_empty_lit = reason_empty.replace("'", "''")
        score_band_expr = self._score_band_expr("score")
        fs_score_band_expr = self._score_band_expr("fs_score")
        fs_conf_band_expr = self._score_band_expr("fs_conf")
        has_mountain_name = "mt_name" in field_names
        mountain_tip = ""
        if has_mountain_name:
            mountain_tip = (
                f"<p><b>{maptip_mountain}</b>: [% coalesce(\"mt_name\", 'n/a') %], "
                f"<b>{maptip_mountain_dist}</b>: "
                "[% CASE WHEN \"mt_dist_m\" IS NULL THEN 'n/a' ELSE to_string(round(\"mt_dist_m\", 1)) END %], "
                f"<b>{maptip_mountain_lang}</b>: [% coalesce(\"mt_lang\", 'n/a') %]</p>"
            )

        self._set_field_aliases(
            layer,
            {
                "reason_ko": reason_alias,
                "fs_reason": fs_reason_alias,
                "mt_name": alias_mountain_name,
                "mt_dist_m": alias_mountain_dist,
                "mt_source": alias_mountain_source,
                "mt_lang": alias_mountain_lang,
            },
        )

        if "src_id" in field_names and "dst_id" in field_names:
            term_field = "term_ko"
            src_field = "src_ko" if "src_ko" in field_names else "src_id"
            dst_field = "dst_ko" if "dst_ko" in field_names else "dst_id"
            if label_lang == "en":
                if "term_en" in field_names:
                    term_field = "term_en"
                if "src_en" in field_names:
                    src_field = "src_en"
                if "dst_en" in field_names:
                    dst_field = "dst_en"
            self._set_field_aliases(
                layer,
                {
                    "score": link_alias_score,
                    "len_m": link_alias_len_m,
                    "azimuth": link_alias_azimuth,
                    "rank": link_alias_rank,
                },
            )
            layer.setDisplayExpression(
                f"\"{term_field}\" || ' ' || \"{src_field}\" || ' {link_arrow} ' || \"{dst_field}\""
            )
            layer.setMapTipTemplate(
                f"<h3>[% \"{term_field}\" %] [% \"{src_field}\" %] {link_arrow} [% \"{dst_field}\" %]</h3>"
                f"<p><b>{reason_label}</b>: [% coalesce(\"reason_ko\",'{reason_empty_lit}') %]</p>"
                f"<p><b>{maptip_score}</b>: [% round(\"score\", 3) %] ([% {score_band_expr} %]), "
                f"<b>{maptip_len_m}</b>: [% round(\"len_m\", 1) %], "
                f"<b>{maptip_azimuth}</b>: [% round(\"azimuth\", 1) %]</p>"
                f"{mountain_tip}"
                f"<p><small>{maptip_link_note}</small></p>"
            )
            self._bind_reason_on_selection(layer, "reason_ko")
            return

        if "term_ko" in field_names:
            term_field = "term_ko"
            if label_lang == "en" and "term_name" in field_names:
                term_field = "term_name"
            self._set_field_aliases(
                layer,
                {
                    "score": term_alias_score,
                    "fit_sc": term_alias_fit,
                    "delta_rel": term_alias_delta,
                    "target_rel": term_alias_target,
                    "radius_m": term_alias_radius,
                    "relief_m": term_alias_relief,
                    "rank": term_alias_rank,
                },
            )
            layer.setDisplayExpression(f"\"{term_field}\"")
            if "fit_sc" in field_names:
                layer.setMapTipTemplate(
                    f"<h3>[% \"{term_field}\" %]</h3>"
                    f"<p><b>{reason_label}</b>: [% coalesce(\"reason_ko\",'{reason_empty_lit}') %]</p>"
                    f"<p><b>{maptip_score}</b>: [% round(\"score\", 3) %] ([% {score_band_expr} %]), "
                    f"<b>{maptip_rank}</b>: [% \"rank\" %], "
                    f"<b>{maptip_fit}</b>: [% round(\"fit_sc\", 3) %]</p>"
                    f"<p><b>{maptip_delta}</b>: [% round(\"delta_rel\", 4) %], "
                    f"<b>{maptip_target}</b>: [% round(\"target_rel\", 4) %], "
                    f"<b>{maptip_radius_m}</b>: [% round(\"radius_m\", 1) %]</p>"
                    f"{mountain_tip}"
                    f"<p><small>{maptip_term_note}</small></p>"
                )
            else:
                layer.setMapTipTemplate(
                    f"<h3>[% \"{term_field}\" %]</h3>"
                    f"<p><b>{reason_label}</b>: [% coalesce(\"reason_ko\",'{reason_empty_lit}') %]</p>"
                    f"<p><b>{maptip_score}</b>: [% round(\"score\", 3) %] ([% {score_band_expr} %]), "
                    f"<b>{maptip_rank}</b>: [% \"rank\" %]</p>"
                    f"{mountain_tip}"
                )
            self._bind_reason_on_selection(layer, "reason_ko")
            return

        if "ridge_class" in field_names:
            ridge_label_field = "ridge_ko" if "ridge_ko" in field_names else "ridge_class"
            if label_lang == "en" and "ridge_en" in field_names:
                ridge_label_field = "ridge_en"
            self._set_field_aliases(
                layer,
                {
                    "strength": ridge_alias_strength,
                    "ridge_score": ridge_alias_score,
                    "len": ridge_alias_len,
                },
            )
            layer.setDisplayExpression(
                f"\"{ridge_label_field}\" || ' #' || \"ridge_rank\""
            )
            layer.setMapTipTemplate(
                f"<h3>[% \"{ridge_label_field}\" %] / #% \"ridge_rank\"</h3>"
                f"<p><b>{reason_label}</b>: [% coalesce(\"reason_ko\",'{reason_empty_lit}') %]</p>"
                f"<p><b>{maptip_strength}</b>: [% round(\"strength\", 3) %], "
                f"<b>ridge_score</b>: [% round(\"ridge_score\", 3) %], "
                f"<b>{maptip_len}</b>: [% round(\"len\", 1) %]</p>"
                f"{mountain_tip}"
                f"<p><small>{maptip_ridge_note}</small></p>"
            )
            self._bind_reason_on_selection(layer, "reason_ko")
            return

        if "stream_class" in field_names:
            self._set_field_aliases(
                layer,
                {
                    "order": hydro_alias_order,
                    "flow_acc": hydro_alias_flow_acc,
                    "len": hydro_alias_len,
                },
            )
            layer.setDisplayExpression("\"stream_class\" || ' #' || \"stream_id\"")
            layer.setMapTipTemplate(
                "<h3>[% \"stream_class\" %] / #% \"stream_id\"</h3>"
                f"<p><b>{reason_label}</b>: [% coalesce(\"reason_ko\",'{reason_empty_lit}') %]</p>"
                f"<p><b>{maptip_order}</b>: [% \"order\" %], "
                f"<b>{maptip_flow_acc}</b>: [% round(\"flow_acc\", 2) %], "
                f"<b>{maptip_len}</b>: [% round(\"len\", 1) %]</p>"
                f"{mountain_tip}"
                f"<p><small>{maptip_hydro_note}</small></p>"
            )
            self._bind_reason_on_selection(layer, "reason_ko")
            return

        if "fs_reason" in field_names:
            self._set_field_aliases(
                layer,
                {
                    "fs_score": site_alias_score,
                    "fs_conf": site_alias_conf,
                    "fs_slope": site_alias_slope,
                    "fs_aspect": site_alias_aspect,
                    "fs_form": site_alias_form,
                    "fs_long": site_alias_long,
                    "fs_water": site_alias_water,
                    "fs_demwtr": site_alias_dem_water,
                    "fs_tpi": site_alias_tpi,
                    "fs_conv": site_alias_conv,
                },
            )
            layer.setDisplayExpression("'fs_score=' || to_string(round(\"fs_score\", 3))")
            layer.setMapTipTemplate(
                f"<h3>{fs_score_title}</h3>"
                f"<p><b>{maptip_score}</b>: [% round(\"fs_score\", 3) %] ([% {fs_score_band_expr} %]), "
                f"<b>{maptip_confidence}</b>: [% round(\"fs_conf\", 3) %] ([% {fs_conf_band_expr} %])</p>"
                f"<p><b>{maptip_components}</b>: "
                "slope=[% round(\"fs_slope\", 3) %], "
                "aspect=[% round(\"fs_aspect\", 3) %], "
                "form=[% round(\"fs_form\", 3) %], "
                "long=[% round(\"fs_long\", 3) %], "
                "water=[% round(\"fs_water\", 3) %]</p>"
                f"<p><b>{maptip_terrain}</b>: "
                "TPI=[% round(\"fs_tpi\", 4) %], "
                "convergence=[% round(\"fs_conv\", 3) %], "
                f"{maptip_dem_water}=[% round(\"fs_demwtr\", 3) %], "
                f"{maptip_distance_water}=[% round(\"fs_water_m\", 1) %]</p>"
                f"{mountain_tip}"
                f"<p><small>{maptip_site_note}</small></p>"
                f"<p><b>{reason_label}</b>: [% coalesce(\"fs_reason\",'{reason_empty_lit}') %]</p>"
            )
            self._bind_reason_on_selection(layer, "fs_reason")

    def _bind_reason_on_selection(self, layer, reason_field):
        if layer is None or layer.id() in self._selection_hooks:
            return

        text_lang = self._label_language()
        reason_empty = ui_text("reason_empty", text_lang, default="No description")
        reason_title = ui_text("reason_alias", text_lang, default="Reason")
        mountain_prefix = ui_text("mountain_prefix_label", text_lang, default="Nearby mountain")
        mountain_lang_label = ui_text("mountain_lang_inline_label", text_lang, default="lang")

        def _on_selection(selected, _deselected, _clear):
            if not selected:
                return
            request = QgsFeatureRequest().setFilterFids([selected[0]])
            feature = next(layer.getFeatures(request), None)
            if feature is None:
                return

            value = feature[reason_field] if reason_field in feature.fields().names() else None
            message = str(value).strip() if value not in (None, "") else reason_empty
            if "mt_name" in feature.fields().names():
                mountain_name = feature["mt_name"]
                if mountain_name not in (None, ""):
                    dist_text = ""
                    if "mt_dist_m" in feature.fields().names():
                        try:
                            dist_value = float(feature["mt_dist_m"])
                            dist_text = f" ({dist_value:.1f}m)"
                        except (TypeError, ValueError):
                            dist_text = ""
                    source_text = ""
                    if "mt_source" in feature.fields().names() and feature["mt_source"] not in (None, ""):
                        source_text = f", {feature['mt_source']}"
                    lang_text = ""
                    if "mt_lang" in feature.fields().names() and feature["mt_lang"] not in (None, ""):
                        lang_text = f", {mountain_lang_label}={feature['mt_lang']}"
                    message = (
                        f"[{mountain_prefix}] {mountain_name}{dist_text}{lang_text}{source_text}\n"
                        f"{message}"
                    )
            cluster_reason = self._term_cluster_reason(layer, feature, text_lang)
            if cluster_reason:
                message = f"{message}\n\n{cluster_reason}"
            if len(message) > 1800:
                message = f"{message[:1797]}..."
            title = f"{layer.name()} {reason_title}"
            self._show_reason_popup(title, message)
            self.iface.messageBar().pushInfo(title, message)

        layer.selectionChanged.connect(_on_selection)
        self._selection_hooks[layer.id()] = _on_selection

    def _show_reason_popup(self, title, message):
        if self._reason_dialog is None:
            self._reason_dialog = QDialog(self.iface.mainWindow())
            self._reason_dialog.setWindowTitle(
                ui_text("feature_reason_title", self._label_language(), default="Feature Reason")
            )
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

        text_lang = self._label_language()
        md_title = ui_text(
            "calibration_md_title_template",
            text_lang,
            default="Feng Shui Calibration Report ({stamp})",
        ).format(stamp=stamp)
        md_positive = ui_text("calibration_md_positive_label", text_lang, default="Positive samples")
        md_negative = ui_text("calibration_md_negative_label", text_lang, default="Negative samples")
        md_valid = ui_text("calibration_md_valid_label", text_lang, default="Valid scored samples")
        md_roc_auc = ui_text("calibration_md_roc_auc_label", text_lang, default="ROC AUC")
        md_pr_auc = ui_text("calibration_md_pr_auc_label", text_lang, default="PR AUC")
        md_best_f1 = ui_text("calibration_md_best_f1_label", text_lang, default="Best F1")
        md_best_youden = ui_text(
            "calibration_md_best_youden_label",
            text_lang,
            default="Best Youden J",
        )
        md_threshold = ui_text("calibration_md_threshold_label", text_lang, default="threshold")
        md_context_title = ui_text("calibration_md_context_title", text_lang, default="Context")
        md_culture = ui_text("calibration_md_context_culture_label", text_lang, default="culture")
        md_period = ui_text("calibration_md_context_period_label", text_lang, default="period")
        md_profile = ui_text("calibration_md_context_profile_label", text_lang, default="profile")
        md_hemisphere = ui_text(
            "calibration_md_context_hemisphere_label",
            text_lang,
            default="hemisphere",
        )
        md_negative_ratio = ui_text(
            "calibration_md_context_negative_ratio_label",
            text_lang,
            default="negative_ratio",
        )
        md_random_seed = ui_text(
            "calibration_md_context_random_seed_label",
            text_lang,
            default="random_seed",
        )

        markdown = (
            f"# {md_title}\n\n"
            f"- {md_positive}: {report.get('positive_count')}\n"
            f"- {md_negative}: {report.get('negative_count')}\n"
            f"- {md_valid}: {report.get('valid_count')}\n"
            f"- {md_roc_auc}: {report.get('roc_auc', 0):.6f}\n"
            f"- {md_pr_auc}: {report.get('pr_auc', 0):.6f}\n"
            f"- {md_best_f1}: {report.get('best_f1', 0):.6f} @ {md_threshold} {report.get('best_f1_threshold', 0):.6f}\n"
            f"- {md_best_youden}: {report.get('best_youden_j', 0):.6f} @ {md_threshold} {report.get('best_youden_threshold', 0):.6f}\n\n"
            f"## {md_context_title}\n\n"
            f"- {md_culture}: {report.get('culture_key')}\n"
            f"- {md_period}: {report.get('period_key')}\n"
            f"- {md_profile}: {report.get('profile_key')}\n"
            f"- {md_hemisphere}: {report.get('hemisphere')}\n"
            f"- {md_negative_ratio}: {report.get('negative_ratio')}\n"
            f"- {md_random_seed}: {report.get('random_seed')}\n"
        )
        with open(md_path, "w", encoding="utf-8") as handle:
            handle.write(markdown)

        return json_path, md_path

    def _show_report_popup(self, report, json_path, md_path):
        text_lang = self._label_language()
        if self._report_dialog is None:
            self._report_dialog = QDialog(self.iface.mainWindow())
            self._report_dialog.setWindowTitle(
                ui_text(
                    "calibration_report_title",
                    text_lang,
                    default="Calibration Report",
                )
            )
            self._report_dialog.resize(760, 520)
            layout = QVBoxLayout(self._report_dialog)
            self._report_browser = QTextBrowser(self._report_dialog)
            self._report_browser.setOpenExternalLinks(True)
            self._report_browser.setReadOnly(True)
            layout.addWidget(self._report_browser)

        roc_auc_label = ui_text("calibration_html_roc_auc_label", text_lang, default="ROC AUC")
        pr_auc_label = ui_text("calibration_html_pr_auc_label", text_lang, default="PR AUC")
        positive_label = ui_text("calibration_html_positive_label", text_lang, default="Positive")
        negative_label = ui_text("calibration_html_negative_label", text_lang, default="Negative")
        valid_label = ui_text("calibration_html_valid_label", text_lang, default="Valid")
        best_f1_label = ui_text("calibration_html_best_f1_label", text_lang, default="Best F1")
        best_youden_label = ui_text(
            "calibration_html_best_youden_label",
            text_lang,
            default="Best Youden J",
        )
        threshold_label = ui_text(
            "calibration_html_threshold_label",
            text_lang,
            default="threshold",
        )
        json_label = ui_text("calibration_html_json_label", text_lang, default="JSON")
        markdown_label = ui_text(
            "calibration_html_markdown_label",
            text_lang,
            default="Markdown",
        )

        html = (
            f"<h3>{ui_text('calibration_report_heading', text_lang, default='Calibration Result')}</h3>"
            f"<p><b>{roc_auc_label}</b>: {report.get('roc_auc', 0):.4f}<br/>"
            f"<b>{pr_auc_label}</b>: {report.get('pr_auc', 0):.4f}<br/>"
            f"<b>{positive_label}</b>: {report.get('positive_count')} / "
            f"<b>{negative_label}</b>: {report.get('negative_count')} / "
            f"<b>{valid_label}</b>: {report.get('valid_count')}</p>"
            f"<p><b>{best_f1_label}</b>: {report.get('best_f1', 0):.4f} "
            f"({threshold_label}={report.get('best_f1_threshold', 0):.4f})<br/>"
            f"<b>{best_youden_label}</b>: {report.get('best_youden_j', 0):.4f} "
            f"({threshold_label}={report.get('best_youden_threshold', 0):.4f})</p>"
            f"<p><b>{json_label}</b>: {json_path}<br/><b>{markdown_label}</b>: {md_path}</p>"
        )
        self._report_browser.setHtml(html)
        self._report_dialog.show()
        self._report_dialog.raise_()
        self._report_dialog.activateWindow()

