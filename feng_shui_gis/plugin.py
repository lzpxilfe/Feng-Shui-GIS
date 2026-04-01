# -*- coding: utf-8 -*-
import hashlib
import json
import os
import traceback
from html import escape
from datetime import datetime
from time import perf_counter

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor, QIcon
from qgis.PyQt.QtWidgets import QAction, QDialog, QVBoxLayout, QTextBrowser
from qgis.core import (
    QgsApplication,
    QgsCategorizedSymbolRenderer,
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsProject,
    QgsMessageLog,
    Qgis,
    QgsRendererCategory,
    QgsTask,
    QgsSymbol,
    QgsWkbTypes,
    QgsVectorLayer,
    edit,
)

from .cultural_context import (
    base_period_key,
    context_evidence_records,
    neutral_context_key,
)
from .compare_contracts import (
    top_score_changes as compare_top_score_changes,
    validate_compare_feature_contract,
    validate_compare_top_change_contract,
)
from .dock_widget import FengShuiDockWidget
from .service_contracts import (
    AnalysisRequest,
    CalibrationRequest,
    CompareRequest,
    TermExtractionRequest,
)
from .services.analysis_service import FengShuiAnalysisService
from .locale import tr
from .mountain_lookup import MountainNameService
from .mountain_options import mountain_options
from .errors import FengShuiError, FengShuiErrorCode
from .profile_catalog import (
    analysis_rules,
    local_profiles_payload,
    write_local_profiles_payload,
)
from .reference_catalog import reference_display_text
from .reporting.benchmark_manifest_writer import BenchmarkManifestWriter
from .reporting.calibration_report_writer import CalibrationReportWriter
from .reporting.compare_report_writer import CompareReportWriter
from .ui_catalog import ui_text


class _BackgroundTask(QgsTask):
    def __init__(self, description, callback):
        super().__init__(description)
        self._callback = callback
        self._result = None
        self._exception = None
        self._traceback = ""
        self._runtime_seconds = 0.0
        self._started_at = None
        self._finished_at = None

    def run(self):
        if self.isCanceled():
            return False
        self._started_at = perf_counter()
        try:
            self._result = self._callback()
            return True
        except Exception as exc:  # pylint: disable=broad-except
            self._exception = exc
            self._traceback = traceback.format_exc()
            return False
        finally:
            self._finished_at = perf_counter()
            if self._started_at is not None:
                self._runtime_seconds = max(
                    0.0,
                    self._finished_at - self._started_at,
                )


class FengShuiGisPlugin:
    _LOG_TAG = "Feng-Shui GIS"
    _COMPARE_DELTA_EPSILON = 0.01
    _COMPARE_TOP_CHANGE_LIMIT = 8
    _COMPARE_REASON_EXCERPT = 96
    _COMPARE_REPORT_REASON_EXCERPT = 44
    _COMPARE_TREND_STYLES = (
        ("gain", "#1f7a4f", "compare_trend_gain", "Gain"),
        ("drop", "#b14a3b", "compare_trend_drop", "Drop"),
        ("neutral", "#b8933f", "compare_trend_neutral", "Near neutral"),
    )
    _OUTPUT_SUFFIXES = {
        "en": {
            "analysis": "fengshui",
            "calibration": "calibration",
            "compare_changes": "compare_changes",
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
            "compare_changes": "풍수_변화지점",
            "ridge": "풍수_산줄기",
            "hydro": "풍수_수계",
            "terms": "풍수_용어",
            "term_links": "풍수_구조연결",
            "hydro_auto": "풍수_자동수계",
            "hydro_auto_calibration": "풍수_자동수계_보정",
        },
    }

    def __init__(self, iface, analysis_service=None):
        self.iface = iface
        self.action = None
        self.toolbar = None
        self.dock = None
        self.plugin_dir = os.path.dirname(__file__)
        self._analysis_service = (
            analysis_service if analysis_service is not None else FengShuiAnalysisService()
        )
        self._selection_hooks = {}
        self._reason_dialog = None
        self._reason_browser = None
        self._report_dialog = None
        self._report_browser = None
        self._compare_dialog = None
        self._compare_browser = None
        self._context_warning_cache = set()
        self._analysis_task = None

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
        if self._analysis_task and self._analysis_task.isActive():
            self._analysis_task.cancel()
            self._analysis_task = None
        for layer_id, slot in list(self._selection_hooks.items()):
            layer = QgsProject.instance().mapLayer(layer_id)
            if layer is None:
                continue
            try:
                layer.selectionChanged.disconnect(slot)
            except (RuntimeError, TypeError) as exc:
                QgsMessageLog.logMessage(
                    f"selectionChanged disconnect skipped for layer {layer_id}: {type(exc).__name__}: {exc}",
                    self._LOG_TAG,
                    level=Qgis.Warning,
                )
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

        if self._compare_dialog:
            self._compare_dialog.close()
            self._compare_dialog.deleteLater()
            self._compare_dialog = None
            self._compare_browser = None

    def toggle_panel(self):
        if self.dock is None:
            self.dock = FengShuiDockWidget(self.iface.mainWindow())
            self.dock.run_requested.connect(self.run_analysis)
            self.dock.compare_requested.connect(self.run_profile_compare)
            self.dock.terms_requested.connect(self.run_term_extraction)
            self.dock.calibration_requested.connect(self.run_calibration)
            self.dock.cancel_requested.connect(self.cancel_running_tasks)
        if self.dock.isVisible():
            self.dock.hide()
        else:
            self.dock.show()
            self.dock.raise_()
            self.dock.activateWindow()

    @staticmethod
    def _debug_error_message(context, exc):
        return f"{context}: {type(exc).__name__}: {exc}"

    def _resolve_user_message(self, message):
        if not message:
            return message
        language = self._label_language()
        translated = ui_text(message, language, default=message)
        return translated or message

    @staticmethod
    def _contract_error(code, message, details, user_message):
        return FengShuiError(
            code=code,
            message=message,
            details=str(details),
            user_message=user_message,
        )

    def _publish_error(self, context, exc, *, failure_code=None):
        if isinstance(exc, FengShuiError):
            code = exc.code
            user_message = self._resolve_user_message(
                exc.user_message or exc.message
            )
            details = exc.details or self._debug_error_message(context, exc)
        else:
            code = failure_code or FengShuiErrorCode.UNEXPECTED
            user_message = self._resolve_user_message(str(exc))
            details = self._debug_error_message(context, exc)

        log_message = f"{code.value} | {details}"
        QgsMessageLog.logMessage(log_message, "Feng-Shui GIS", level=Qgis.Critical)

        ui_message = f"{context}: {user_message}" if user_message else context
        self.iface.messageBar().pushCritical(tr("warn_failed"), ui_message)
        if self.dock:
            self.dock.set_status(ui_message)

    def _run_with_error_handler(self, context, callback, failure_code=None):
        try:
            return callback()
        except Exception as exc:  # pylint: disable=broad-except
            self._publish_error(context, exc, failure_code=failure_code)
            return None

    def _run_background_task(
        self,
        description,
        callback,
        on_success,
        *,
        failure_code=None,
        failure_context=None,
    ):
        if self._analysis_task is not None and self._analysis_task.isActive():
            message = ui_text(
                "analysis_task_running",
                self._label_language(),
                default="A task is already running. Please wait or cancel it before starting another.",
            )
            self.iface.messageBar().pushWarning(tr("plugin_title"), message)
            if self.dock:
                self.dock.set_status(message)
            return False

        task = _BackgroundTask(description, callback)

        def _on_completed():
            if self._analysis_task is task:
                self._analysis_task = None
            if task._exception is not None:
                self._publish_error(
                    failure_context or description,
                    task._exception,
                    failure_code=failure_code,
                )
                if self.dock:
                    self.dock.set_running_state(False, task_key=str(id(task)))
                return
            try:
                on_success(task._result, task)
            except Exception as exc:  # pylint: disable=broad-except
                self._publish_error(
                    failure_context or description,
                    exc,
                    failure_code=failure_code,
                )
            finally:
                if self.dock:
                    self.dock.set_running_state(False, task_key=str(id(task)))

        def _on_terminated():
            if self._analysis_task is task:
                self._analysis_task = None
            if task._exception is None and task.isCanceled():
                message = ui_text(
                    "analysis_task_cancelled",
                    self._label_language(),
                    default="Operation was canceled.",
                )
                self.iface.messageBar().pushWarning(
                    tr("plugin_title"),
                    message,
                )
                if self.dock:
                    self.dock.set_status(message)
                    self.dock.set_running_state(False, task_key=str(id(task)))
                return
            if task._exception is not None:
                self._publish_error(
                    failure_context or description,
                    task._exception,
                    failure_code=failure_code,
                )
                if self.dock:
                    self.dock.set_running_state(False, task_key=str(id(task)))
                return
            if self.dock:
                self.dock.set_running_state(False, task_key=str(id(task)))

        self._analysis_task = task
        task.taskCompleted.connect(_on_completed)
        task.taskTerminated.connect(_on_terminated)
        QgsApplication.taskManager().addTask(task)
        if self.dock:
            self.dock.set_running_state(
                True,
                task_key=str(id(task)),
                task_label=str(description),
            )
        return True

    def cancel_running_tasks(self):
        if self._analysis_task is None or not self._analysis_task.isActive():
            if self._analysis_task is not None:
                self._analysis_task = None
            message = ui_text(
                "analysis_no_task_to_cancel",
                self._label_language(),
                default="No running workflow to cancel.",
            )
            if self.dock:
                self.dock.set_status(message)
            self.iface.messageBar().pushInfo(tr("plugin_title"), message)
            if self.dock:
                self.dock.set_running_state(False)
            return

        self._analysis_task.cancel()
        message = ui_text(
            "analysis_task_cancel_requested",
            self._label_language(),
            default="Cancel request sent. Waiting for workflow to stop.",
        )
        self.iface.messageBar().pushInfo(tr("plugin_title"), message)
        if self.dock:
            self.dock.set_status(message)

    def _report_dir(self):
        project_home = QgsProject.instance().homePath().strip()
        if not project_home:
            project_home = os.path.abspath(os.path.join(self.plugin_dir, ".."))
        report_dir = os.path.join(project_home, "reports")
        os.makedirs(report_dir, exist_ok=True)
        return report_dir

    @staticmethod
    def _write_json_payload(path, payload):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        return path

    def _write_run_manifest_snapshot(self, service_name, run_manifest):
        if not isinstance(run_manifest, dict) or not run_manifest:
            return ""
        report_dir = self._report_dir()
        run_id = str(run_manifest.get("run_id") or "").strip()
        if not run_id:
            run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(
            report_dir,
            f"feng_shui_run_{service_name}_{run_id}.json",
        )
        self._write_json_payload(path, run_manifest)
        return path

    def _write_benchmark_manifest(
        self,
        *,
        service_name,
        run_manifest,
        runtime_seconds,
        run_manifest_path="",
        report_json_path="",
        report_md_path="",
        notes="",
    ):
        if not isinstance(run_manifest, dict) or not run_manifest:
            return ""
        run_id = str(run_manifest.get("run_id") or "").strip()
        if not run_id:
            run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        payload = BenchmarkManifestWriter.build_manifest(
            dataset_id=run_id,
            service_name=service_name,
            qgis_version=run_manifest.get("qgis_version"),
            runtime_seconds=runtime_seconds,
            run_manifest=run_manifest,
            run_manifest_path=run_manifest_path,
            report_json_path=report_json_path,
            report_md_path=report_md_path,
            notes=notes,
        )
        path = os.path.join(
            self._report_dir(),
            f"feng_shui_benchmark_{service_name}_{run_id}.json",
        )
        BenchmarkManifestWriter.write_json(path, payload)
        QgsMessageLog.logMessage(
            f"Saved benchmark manifest: {path}",
            self._LOG_TAG,
            level=Qgis.Info,
        )
        return path

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

        request = AnalysisRequest(
            site_layer=site_layer,
            dem_layer=dem_layer,
            water_layer=water_layer,
            hemisphere=hemisphere,
            profile_key=profile_key,
            culture_key=culture_key,
            period_key=period_key,
            auto_hydro=auto_hydro,
        )

        def _execute():
            return self._analysis_service.run_analysis(request)

        def _on_success(result, task):
            output_layer = result.analysis_layer
            auto_hydro_layer = result.auto_hydro_layer
            if auto_hydro_layer is not None:
                auto_hydro_layer.setName(
                    self._output_layer_name(dem_layer.name(), "hydro_auto", label_lang)
                )
                QgsProject.instance().addMapLayer(auto_hydro_layer)
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
            run_manifest_path = self._write_run_manifest_snapshot(
                "analysis",
                result.run_manifest,
            )
            self._write_benchmark_manifest(
                service_name="analysis",
                run_manifest=result.run_manifest,
                runtime_seconds=getattr(task, "_runtime_seconds", 0.0),
                run_manifest_path=run_manifest_path,
                notes="Auto-saved from QGIS UI analysis run.",
            )
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

        self._run_background_task(
            "Run feng shui analysis",
            _execute,
            _on_success,
            failure_code=FengShuiErrorCode.ANALYSIS_FAILURE,
            failure_context="Analysis failed",
        )

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

        def _execute():
            request = TermExtractionRequest(
                dem_layer=dem_layer,
                water_layer=water_layer,
                hemisphere=hemisphere,
                profile_key=profile_key,
                culture_key=culture_key,
                period_key=period_key,
                auto_hydro=auto_hydro,
                include_terms=include_terms,
            )
            return self._analysis_service.run_term_extraction(request)

        def _on_success(result, task):
            if not result:
                return
            ridge_layer = result.ridge_layer
            hydro_layer = result.hydro_layer
            terms_layer = result.terms_layer
            line_layer = result.term_links_layer

            ridge_layer.setName(
                self._output_layer_name(dem_layer.name(), "ridge", label_lang)
            )
            if hydro_layer is not None:
                hydro_layer.setName(
                    self._output_layer_name(dem_layer.name(), "hydro", label_lang)
                )
            if terms_layer is not None:
                terms_layer.setName(
                    self._output_layer_name(dem_layer.name(), "terms", label_lang)
                )
            if line_layer is not None:
                line_layer.setName(
                    self._output_layer_name(dem_layer.name(), "term_links", label_lang)
                )

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

            created = [f"{ridge_layer.name()} ({ridge_layer.featureCount()})"]
            if hydro_layer:
                created.insert(0, f"{hydro_layer.name()} ({hydro_layer.featureCount()})")
            if include_terms and line_layer and terms_layer:
                created.insert(0, f"{line_layer.name()} ({line_layer.featureCount()})")
                created.insert(0, f"{terms_layer.name()} ({terms_layer.featureCount()})")
            message_key = (
                "ok_terms_finished" if include_terms else "ok_landscape_finished"
            )
            self.iface.messageBar().pushSuccess(
                tr("plugin_title"),
                f"{tr(message_key)}: " + ", ".join(created),
            )
            if mountain_enabled and mountain_total > 0:
                self.iface.messageBar().pushInfo(
                    tr("plugin_title"),
                    self._mountain_attached_message(mountain_total),
                )
            run_manifest_path = self._write_run_manifest_snapshot(
                "term_extraction",
                result.run_manifest,
            )
            self._write_benchmark_manifest(
                service_name="term_extraction",
                run_manifest=result.run_manifest,
                runtime_seconds=getattr(task, "_runtime_seconds", 0.0),
                run_manifest_path=run_manifest_path,
                notes="Auto-saved from QGIS UI term extraction run.",
            )
            if self.dock:
                self.dock.set_status(tr("status_done"))

        self._run_background_task(
            "Run feng shui term extraction",
            _execute,
            _on_success,
            failure_code=FengShuiErrorCode.TERM_EXTRACTION_FAILURE,
            failure_context="Term extraction failed",
        )

    @staticmethod
    def _score_stats(layer):
        if layer is None:
            return {"count": 0, "mean": 0.0, "min": 0.0, "max": 0.0}
        scores = []
        for feature in layer.getFeatures():
            try:
                value = float(feature["fs_score"])
            except (KeyError, TypeError, ValueError):
                continue
            scores.append(value)
        if not scores:
            return {"count": 0, "mean": 0.0, "min": 0.0, "max": 0.0}
        return {
            "count": len(scores),
            "mean": sum(scores) / len(scores),
            "min": min(scores),
            "max": max(scores),
        }

    @staticmethod
    def _pairwise_score_delta(base_layer, compare_layer):
        if base_layer is None or compare_layer is None:
            return None
        base_scores = {}
        compare_scores = {}
        for feature in base_layer.getFeatures():
            feature_uid = FengShuiGisPlugin._feature_uid(feature)
            try:
                base_scores[feature_uid] = float(feature["fs_score"])
            except (KeyError, TypeError, ValueError):
                continue
        for feature in compare_layer.getFeatures():
            feature_uid = FengShuiGisPlugin._feature_uid(feature)
            try:
                compare_scores[feature_uid] = float(feature["fs_score"])
            except (KeyError, TypeError, ValueError):
                continue
        shared_uids = set(base_scores.keys()) & set(compare_scores.keys())
        if not shared_uids:
            return None
        deltas = [
            compare_scores[feature_uid] - base_scores[feature_uid]
            for feature_uid in shared_uids
        ]
        if not deltas:
            return None
        return {
            "count": len(deltas),
            "mean_delta": sum(deltas) / len(deltas),
            "max_gain": max(deltas),
            "max_drop": min(deltas),
        }

    @staticmethod
    def _validate_compare_feature_contract(base_layer, compare_layer):
        return validate_compare_feature_contract(
            base_layer,
            compare_layer,
            FengShuiGisPlugin._feature_uid,
        )

    @staticmethod
    def _validate_compare_top_change_contract(base_layer, compare_layer, top_changes):
        return validate_compare_top_change_contract(
            base_layer,
            compare_layer,
            top_changes,
            FengShuiGisPlugin._feature_uid,
        )

    @staticmethod
    def _validate_calibration_feature_contract(calibrated_layer, report=None):
        if calibrated_layer is None:
            return {
                "ok": False,
                "message": "Calibrated layer is missing.",
                "count": 0,
            }

        feature_uids = []
        for feature in calibrated_layer.getFeatures():
            feature_uid = str(FengShuiGisPlugin._feature_uid(feature))
            if feature_uid:
                feature_uids.append(feature_uid)

        if not feature_uids:
            return {
                "ok": False,
                "message": "Calibrated layer does not expose feature_uid.",
                "count": 0,
            }

        unique_count = len(set(feature_uids))
        if unique_count != len(feature_uids):
            return {
                "ok": False,
                "message": "Duplicate feature_uid values detected in calibrated layer.",
                "count": unique_count,
            }

        return {
            "ok": True,
            "message": "",
            "count": unique_count,
        }

    @staticmethod
    def _normalize_signature_value(value):
        if value is None:
            return ""
        if isinstance(value, float):
            return f"{value:.12g}"
        if isinstance(value, (list, tuple, dict)):
            return json.dumps(value, sort_keys=True, ensure_ascii=False)
        return str(value)

    @classmethod
    def _signature_from_inputs(cls, geometry, attributes, sequence=None):
        payload = {
            "sequence": int(sequence) if sequence is not None else None,
            "geometry": "",
            "attributes": {},
        }
        if geometry is not None:
            try:
                wkb_bytes = geometry.asWkb()
            except Exception:
                wkb_bytes = None
            if wkb_bytes:
                payload["geometry"] = wkb_bytes.hex()
        if attributes:
            for key in sorted(attributes):
                payload["attributes"][str(key)] = cls._normalize_signature_value(
                    attributes[key]
                )
        return hashlib.sha1(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _feature_uid(feature):
        if feature is None:
            return ""
        field_names = feature.fields().names()
        lowered = {name.lower(): name for name in field_names}
        for candidate in ("fs_uid", "feature_uid", "cal_uid", "cal_id"):
            if candidate in lowered:
                try:
                    value = feature[lowered[candidate]]
                except (KeyError, TypeError, ValueError):
                    continue
                text = str(value or "").strip()
                if text:
                    return text

        attributes = {}
        excluded = {"fid", "id", "objectid", "globalid", "uuid"}
        for name in field_names:
            lowered_name = str(name).lower()
            if lowered_name.startswith("fs_"):
                continue
            if lowered_name in excluded:
                continue
            try:
                attributes[name] = feature[name]
            except (TypeError, ValueError, KeyError):
                continue

        geometry = feature.geometry() if feature.hasGeometry() else None
        signature = FengShuiGisPlugin._signature_from_inputs(geometry, attributes)
        if signature:
            return f"geom:{signature}"
        return f"fid:{int(feature.id())}"

    @staticmethod
    def _feature_display_name(feature):
        if feature is None:
            return ""
        field_candidates = (
            "name",
            "site_name",
            "site",
            "title",
            "label",
            "site_id",
            "id",
        )
        field_names = feature.fields().names()
        lowered = {name.lower(): name for name in field_names}
        for candidate in field_candidates:
            if candidate in lowered:
                try:
                    value = feature[lowered[candidate]]
                except (KeyError, TypeError, ValueError):
                    continue
                text = str(value or "").strip()
                if text:
                    return text
        uid = FengShuiGisPlugin._feature_uid(feature)
        if uid:
            return uid
        return f"fid:{int(feature.id())}"

    @staticmethod
    def _feature_reason_text(feature):
        if feature is None:
            return ""
        field_candidates = ("fs_reason", "reason", "fs_note")
        field_names = feature.fields().names()
        lowered = {name.lower(): name for name in field_names}
        for candidate in field_candidates:
            if candidate in lowered:
                try:
                    value = feature[lowered[candidate]]
                except (KeyError, TypeError, ValueError):
                    continue
                text = str(value or "").strip()
                if text:
                    return text
        return ""

    @staticmethod
    def _reason_excerpt(text, limit=None):
        if limit is None:
            limit = FengShuiGisPlugin._COMPARE_REASON_EXCERPT
        clean = str(text or "").strip().replace("\n", " ")
        if len(clean) <= max(1, int(limit)):
            return clean
        return clean[: max(1, int(limit)) - 1].rstrip() + "…"

    @classmethod
    def _compare_trend(cls, delta_value):
        if float(delta_value) > cls._COMPARE_DELTA_EPSILON:
            return "gain"
        if float(delta_value) < (-cls._COMPARE_DELTA_EPSILON):
            return "drop"
        return "neutral"

    def _top_score_changes(self, base_layer, compare_layer, limit=None):
        if limit is None:
            limit = self._COMPARE_TOP_CHANGE_LIMIT
        return compare_top_score_changes(
            base_layer,
            compare_layer,
            feature_uid_resolver=self._feature_uid,
            label_resolver=self._feature_display_name,
            reason_resolver=self._feature_reason_text,
            limit=limit,
        )

    @staticmethod
    def _feature_uids_from_change_rows(change_rows):
        feature_uids = []
        for row in change_rows or []:
            feature_uid = row.get("feature_uid")
            if not feature_uid:
                continue
            feature_uids.append(str(feature_uid))
        return feature_uids

    @staticmethod
    def _feature_uids_to_fids(layer, feature_uids):
        if layer is None:
            return []
        target_uids = {str(item) for item in feature_uids}
        resolved = {}
        for feature in layer.getFeatures():
            uid = str(FengShuiGisPlugin._feature_uid(feature))
            if uid in target_uids:
                resolved[uid] = int(feature.id())
        selected = []
        for uid in feature_uids:
            fid = resolved.get(str(uid))
            if fid is not None:
                selected.append(fid)
        return selected

    def _select_top_changed_features(self, base_layer, compare_layer, change_rows):
        feature_uids = self._feature_uids_from_change_rows(change_rows)
        feature_ids = self._feature_uids_to_fids(compare_layer, feature_uids)
        if not feature_ids:
            return 0
        selected_count = 0
        for layer in (base_layer, compare_layer):
            if layer is None:
                continue
            try:
                layer.removeSelection()
            except (RuntimeError, TypeError, AttributeError) as exc:
                QgsMessageLog.logMessage(
                    f"Failed to clear selection on layer {getattr(layer, 'name', lambda: layer)()}: {type(exc).__name__}: {exc}",
                    self._LOG_TAG,
                    level=Qgis.Warning,
                )
            try:
                layer.selectByIds(feature_ids)
                selected_count = max(selected_count, len(layer.selectedFeatureIds()))
            except (RuntimeError, TypeError, AttributeError) as exc:
                QgsMessageLog.logMessage(
                    f"Failed to select changed features on layer {getattr(layer, 'name', lambda: layer)()}: {type(exc).__name__}: {exc}",
                    self._LOG_TAG,
                    level=Qgis.Warning,
                )
                continue
        if compare_layer is not None:
            try:
                self.iface.setActiveLayer(compare_layer)
            except (RuntimeError, AttributeError, TypeError) as exc:
                QgsMessageLog.logMessage(
                    f"Failed to activate compare layer {compare_layer.name()}: {type(exc).__name__}: {exc}",
                    self._LOG_TAG,
                    level=Qgis.Warning,
                )
        return selected_count

    def _zoom_to_selected_features(self, layer):
        if layer is None:
            return False
        try:
            selected_ids = layer.selectedFeatureIds()
        except (RuntimeError, AttributeError, TypeError) as exc:
            QgsMessageLog.logMessage(
                f"Failed to read selected feature ids from layer {layer.name()}: {type(exc).__name__}: {exc}",
                self._LOG_TAG,
                level=Qgis.Warning,
            )
            return False
        if not selected_ids:
            return False
        try:
            self.iface.mapCanvas().zoomToSelected(layer)
            return True
        except (RuntimeError, AttributeError, TypeError) as exc:
            QgsMessageLog.logMessage(
                f"Zoom-to-selected failed for layer {layer.name()}: {type(exc).__name__}: {exc}",
                self._LOG_TAG,
                level=Qgis.Warning,
            )
            return False

    def _export_top_changed_features_layer(
        self,
        compare_layer,
        top_changes,
        compare_profile_key,
        label_lang,
    ):
        if compare_layer is None or not top_changes:
            return None
        feature_map = {}
        for row in top_changes:
            feature_uid = row.get("feature_uid")
            if not feature_uid:
                continue
            feature_map[str(feature_uid)] = row
        if not feature_map:
            return None

        geometry_name = QgsWkbTypes.displayString(compare_layer.wkbType()) or "Point"
        crs_authid = compare_layer.crs().authid() or "EPSG:4326"
        layer_name = self._output_layer_name(
            compare_layer.name(),
            "compare_changes",
            label_lang,
        )
        export_layer = QgsVectorLayer(
            f"{geometry_name}?crs={crs_authid}",
            layer_name,
            "memory",
        )
        if not export_layer.isValid():
            return None

        provider = export_layer.dataProvider()
        provider.addAttributes(list(compare_layer.fields()))
        provider.addAttributes(
            [
                QgsField("cmp_label", QVariant.String, "string", 120),
                QgsField("cmp_uid", QVariant.String, "string", 80),
                QgsField("cmp_base", QVariant.Double, "double", 7, 4),
                QgsField("cmp_score", QVariant.Double, "double", 7, 4),
                QgsField("cmp_delta", QVariant.Double, "double", 7, 4),
                QgsField("cmp_trend", QVariant.String, "string", 16),
                QgsField("cmp_reason_b", QVariant.String, "string", 1024),
                QgsField("cmp_reason_c", QVariant.String, "string", 1024),
                QgsField("cmp_model", QVariant.String, "string", 80),
            ]
        )
        export_layer.updateFields()

        new_features = []
        output_fields = export_layer.fields()
        original_field_names = compare_layer.fields().names()
        for source_feature in compare_layer.getFeatures():
            feature_uid = str(self._feature_uid(source_feature))
            row = feature_map.get(feature_uid)
            if row is None:
                continue
            new_feature = QgsFeature(output_fields)
            new_feature.setGeometry(source_feature.geometry())
            for field_name in original_field_names:
                try:
                    new_feature[field_name] = source_feature[field_name]
                except (KeyError, TypeError, ValueError):
                    continue
            new_feature["cmp_label"] = str(row.get("label", ""))
            new_feature["cmp_uid"] = str(row.get("feature_uid", ""))
            new_feature["cmp_base"] = float(row.get("base_score", 0.0))
            new_feature["cmp_score"] = float(row.get("compare_score", 0.0))
            new_feature["cmp_delta"] = float(row.get("delta", 0.0))
            delta_value = float(row.get("delta", 0.0))
            trend = self._compare_trend(delta_value)
            new_feature["cmp_trend"] = trend
            base_reason = str(row.get("base_reason", "") or "")
            compare_reason = str(row.get("compare_reason", "") or "")
            new_feature["cmp_reason_b"] = base_reason
            new_feature["cmp_reason_c"] = compare_reason
            if "fs_reason" in original_field_names:
                if label_lang == "ko":
                    reason_summary = (
                        f"[기준] {self._reason_excerpt(base_reason)} | "
                        f"[보정] {self._reason_excerpt(compare_reason)}"
                    )
                else:
                    reason_summary = (
                        f"[Base] {self._reason_excerpt(base_reason)} | "
                        f"[Calibrated] {self._reason_excerpt(compare_reason)}"
                    )
                new_feature["fs_reason"] = reason_summary
            new_feature["cmp_model"] = str(compare_profile_key)
            new_features.append(new_feature)

        if not new_features:
            return None
        provider.addFeatures(new_features)
        export_layer.updateExtents()
        return export_layer

    def _write_profile_compare_report(
        self,
        site_layer_name,
        base_profile_key,
        compare_profile_key,
        base_stats,
        compare_stats,
        delta_stats,
        top_changes,
        change_layer_name,
    ):
        report_dir = self._report_dir()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"feng_shui_compare_{stamp}"
        json_path = os.path.join(report_dir, f"{base_name}.json")
        md_path = os.path.join(report_dir, f"{base_name}.md")
        text_lang = self._label_language()

        payload = CompareReportWriter.payload(
            stamp=stamp,
            site_layer_name=site_layer_name,
            base_profile_key=base_profile_key,
            compare_profile_key=compare_profile_key,
            base_stats=base_stats,
            compare_stats=compare_stats,
            delta_stats=delta_stats,
            top_changes=top_changes,
            change_layer_name=change_layer_name,
            reason_excerpt_limit=self._COMPARE_REPORT_REASON_EXCERPT,
        )
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

        markdown = CompareReportWriter.build_markdown(
            stamp=stamp,
            text_lang=text_lang,
            site_layer_name=site_layer_name,
            base_profile_key=base_profile_key,
            compare_profile_key=compare_profile_key,
            base_stats=base_stats,
            compare_stats=compare_stats,
            delta_stats=delta_stats,
            top_changes=top_changes,
            change_layer_name=change_layer_name,
            reason_excerpt_limit=self._COMPARE_REPORT_REASON_EXCERPT,
        )
        with open(md_path, "w", encoding="utf-8") as handle:
            handle.write(markdown)
        return json_path, md_path

    def _style_compare_change_layer(self, layer, label_lang):
        if layer is None or not isinstance(layer, QgsVectorLayer):
            return
        categories = []
        for value, color_hex, label_key, default_label in self._COMPARE_TREND_STYLES:
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            if symbol is None:
                continue
            symbol.setColor(QColor(color_hex))
            symbol.setOpacity(0.88)
            try:
                symbol.setWidth(0.9)
            except (AttributeError, TypeError, RuntimeError) as exc:
                QgsMessageLog.logMessage(
                    f"Failed to set compare style width on layer {layer.name()}: {type(exc).__name__}: {exc}",
                    self._LOG_TAG,
                    level=Qgis.Warning,
                )
            try:
                symbol.setSize(4.6)
            except (AttributeError, TypeError, RuntimeError) as exc:
                QgsMessageLog.logMessage(
                    f"Failed to set compare style size on layer {layer.name()}: {type(exc).__name__}: {exc}",
                    self._LOG_TAG,
                    level=Qgis.Warning,
                )
            categories.append(
                QgsRendererCategory(
                    value,
                    symbol,
                    ui_text(label_key, label_lang, default=default_label),
                )
            )
        if not categories:
            return
        layer.setRenderer(QgsCategorizedSymbolRenderer("cmp_trend", categories))
        layer.triggerRepaint()

    def _show_profile_compare_popup(
        self,
        base_profile_key,
        compare_profile_key,
        base_stats,
        compare_stats,
        delta_stats,
        top_changes,
        selected_change_count,
        zoom_applied,
        change_layer_name,
        json_path,
        md_path,
        base_layer_name,
        compare_layer_name,
    ):
        text_lang = self._label_language()
        if self._compare_dialog is None:
            self._compare_dialog = QDialog(self.iface.mainWindow())
            self._compare_dialog.resize(760, 420)
            layout = QVBoxLayout(self._compare_dialog)
            self._compare_browser = QTextBrowser(self._compare_dialog)
            self._compare_browser.setOpenExternalLinks(True)
            self._compare_browser.setReadOnly(True)
            layout.addWidget(self._compare_browser)
        self._compare_dialog.setWindowTitle(
            ui_text(
                "profile_compare_dialog_title",
                text_lang,
                default="Base vs calibrated quick comparison",
            )
        )
        html = CompareReportWriter.build_popup_html(
            text_lang=text_lang,
            base_profile_key=base_profile_key,
            compare_profile_key=compare_profile_key,
            base_stats=base_stats,
            compare_stats=compare_stats,
            delta_stats=delta_stats,
            top_changes=top_changes,
            selected_change_count=selected_change_count,
            zoom_applied=zoom_applied,
            change_layer_name=change_layer_name,
            json_path=json_path,
            md_path=md_path,
            base_layer_name=base_layer_name,
            compare_layer_name=compare_layer_name,
            reason_excerpt_limit=88,
        )
        self._compare_browser.setHtml(html)
        self._compare_dialog.show()
        self._compare_dialog.raise_()
        self._compare_dialog.activateWindow()

    def run_profile_compare(
        self,
        site_layer,
        dem_layer,
        water_layer,
        hemisphere,
        base_profile_key,
        compare_profile_key,
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
            self.dock.set_status(
                ui_text(
                    "profile_compare_status_running",
                    self._label_language(),
                    default="Comparing base and calibrated profiles...",
                )
            )
        label_lang = self._label_language()
        mountain_enabled, mountain_radius_m, mountain_max_features, mountain_lang = (
            self._mountain_name_options()
        )
        self._warn_low_evidence_context(culture_key, period_key, hemisphere)
        if not self._require_projected_dem_crs(dem_layer):
            return
        self._warn_if_crs_mismatch(dem_layer, site_layer, water_layer)

        def _execute():
            request = CompareRequest(
                site_layer=site_layer,
                dem_layer=dem_layer,
                water_layer=water_layer,
                hemisphere=hemisphere,
                base_profile_key=base_profile_key,
                compare_profile_key=compare_profile_key,
                culture_key=culture_key,
                period_key=period_key,
                auto_hydro=auto_hydro,
            )
            return self._analysis_service.run_profile_compare(request)

        def _on_success(result, task):
            base_layer = result.base_layer
            compare_layer = result.compare_layer
            auto_hydro_layer = result.auto_hydro_layer
            contract = self._validate_compare_feature_contract(
                base_layer,
                compare_layer,
            )
            if not contract.get("ok"):
                raise self._contract_error(
                    FengShuiErrorCode.COMPARISON_UID_MISMATCH,
                    "Compare profile layers failed feature UID contract validation.",
                    contract.get("message"),
                    "compare_feature_contract_failed",
                )
            top_changes = self._top_score_changes(base_layer, compare_layer)
            change_contract = self._validate_compare_top_change_contract(
                base_layer,
                compare_layer,
                top_changes,
            )
            if not change_contract.get("ok"):
                raise self._contract_error(
                    FengShuiErrorCode.COMPARISON_TOP_CHANGE_MISMATCH,
                    "Compare top-change rows failed UID contract validation.",
                    change_contract.get("message"),
                    "compare_top_change_contract_failed",
                )
            if auto_hydro_layer is not None:
                auto_hydro_layer.setName(
                    self._output_layer_name(dem_layer.name(), "hydro_auto", label_lang)
                )
                QgsProject.instance().addMapLayer(auto_hydro_layer)

            base_layer.setName(
                f"{self._output_layer_name(site_layer.name(), 'analysis', label_lang)}_{base_profile_key}"
            )
            compare_layer.setName(
                f"{self._output_layer_name(site_layer.name(), 'analysis', label_lang)}_{compare_profile_key}"
            )
            if mountain_enabled:
                self._enrich_layers_with_mountain_names(
                    [base_layer, compare_layer],
                    radius_m=mountain_radius_m,
                    max_features=mountain_max_features,
                    preferred_language=mountain_lang,
                )
            QgsProject.instance().addMapLayer(base_layer)
            QgsProject.instance().addMapLayer(compare_layer)
            self._configure_layer_click_info(base_layer, label_lang)
            self._configure_layer_click_info(compare_layer, label_lang)

            base_stats = self._score_stats(base_layer)
            compare_stats = self._score_stats(compare_layer)
            delta_stats = self._pairwise_score_delta(base_layer, compare_layer)
            selected_change_count = self._select_top_changed_features(
                base_layer,
                compare_layer,
                top_changes,
            )
            if selected_change_count < change_contract.get("count", 0):
                raise self._contract_error(
                    FengShuiErrorCode.COMPARISON_TOP_CHANGE_EXPORT_MISMATCH,
                    "Top-change UID selection contract failed.",
                    "Failed to select all top-change features by UID; selection and analysis layers are out of sync.",
                    "compare_top_change_selection_failed",
                )
            zoom_applied = self._zoom_to_selected_features(compare_layer)
            change_layer = self._export_top_changed_features_layer(
                compare_layer,
                top_changes,
                compare_profile_key,
                label_lang,
            )
            if change_layer is not None and change_layer.featureCount() < change_contract.get(
                "count", 0
            ):
                raise self._contract_error(
                    FengShuiErrorCode.COMPARISON_TOP_CHANGE_EXPORT_MISMATCH,
                    "Top-change UID export contract failed.",
                    "Top-change export dropped features by UID; comparison mapping is not stable.",
                    "compare_top_change_export_failed",
                )
            if change_layer is not None:
                if change_layer.featureCount() == 0:
                    raise self._contract_error(
                        FengShuiErrorCode.COMPARISON_TOP_CHANGE_EXPORT_MISMATCH,
                        "Top-change UID export contract failed.",
                        "No top-change features were exported for comparison output.",
                        "compare_top_change_export_failed",
                    )
            elif top_changes:
                raise self._contract_error(
                    FengShuiErrorCode.COMPARISON_TOP_CHANGE_EXPORT_MISMATCH,
                    "Top-change UID export contract failed.",
                    "Failed to export top-change features despite detected UID set.",
                    "compare_top_change_export_failed",
                )
            if change_layer is not None:
                self._style_compare_change_layer(change_layer, label_lang)
                QgsProject.instance().addMapLayer(change_layer)
                self._configure_layer_click_info(change_layer, label_lang)
            json_path, md_path = self._write_profile_compare_report(
                site_layer_name=site_layer.name(),
                base_profile_key=base_profile_key,
                compare_profile_key=compare_profile_key,
                base_stats=base_stats,
                compare_stats=compare_stats,
                delta_stats=delta_stats,
                top_changes=top_changes,
                change_layer_name=change_layer.name() if change_layer is not None else "",
            )
            run_manifest_path = self._write_run_manifest_snapshot(
                "compare",
                result.run_manifest,
            )
            self._write_benchmark_manifest(
                service_name="compare",
                run_manifest=result.run_manifest,
                runtime_seconds=getattr(task, "_runtime_seconds", 0.0),
                run_manifest_path=run_manifest_path,
                report_json_path=json_path,
                report_md_path=md_path,
                notes="Auto-saved from QGIS UI profile comparison run.",
            )
            self._show_profile_compare_popup(
                base_profile_key=base_profile_key,
                compare_profile_key=compare_profile_key,
                base_stats=base_stats,
                compare_stats=compare_stats,
                delta_stats=delta_stats,
                top_changes=top_changes,
                selected_change_count=selected_change_count,
                zoom_applied=zoom_applied,
                change_layer_name=change_layer.name() if change_layer is not None else "",
                json_path=json_path,
                md_path=md_path,
                base_layer_name=base_layer.name(),
                compare_layer_name=compare_layer.name(),
            )

            success_message = ui_text(
                "profile_compare_status_done",
                self._label_language(),
                default="Created base/calibrated comparison layers.",
            )
            self.iface.messageBar().pushSuccess(
                tr("plugin_title"),
                success_message,
            )
            if self.dock:
                self.dock.set_status(success_message)

        self._run_background_task(
            "Run feng shui profile comparison",
            _execute,
            _on_success,
            failure_code=FengShuiErrorCode.COMPARISON_FAILURE,
            failure_context="Profile comparison failed",
        )

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

        calibration_culture, calibration_period = self._resolved_calibration_context(
            culture_key,
            period_key,
        )
        self._warn_low_evidence_context(
            calibration_culture,
            calibration_period,
            hemisphere,
        )
        if not self._require_projected_dem_crs(dem_layer):
            return
        self._warn_if_crs_mismatch(dem_layer, site_layer, water_layer)

        def _execute():
            request = CalibrationRequest(
                site_layer=site_layer,
                dem_layer=dem_layer,
                water_layer=water_layer,
                hemisphere=hemisphere,
                profile_key=profile_key,
                culture_key=calibration_culture,
                period_key=calibration_period,
                negative_ratio=negative_ratio,
                random_seed=random_seed,
                auto_hydro=auto_hydro,
            )
            return self._analysis_service.run_calibration(request)

        def _on_success(result, task):
            scored_layer = result.calibrated_layer
            report = result.report
            auto_hydro_layer = result.auto_hydro_layer
            reported_metrics = self._calibration_report_metrics(report)
            calibration_contract = self._validate_calibration_feature_contract(scored_layer, report)
            if not calibration_contract.get("ok"):
                raise self._contract_error(
                    FengShuiErrorCode.CALIBRATION_UID_MISMATCH,
                    "Calibrated output failed UID contract validation.",
                    calibration_contract.get("message"),
                    "calibration_feature_contract_failed",
                )
            if auto_hydro_layer is not None:
                auto_hydro_layer.setName(
                    self._output_layer_name(
                        dem_layer.name(),
                        "hydro_auto_calibration",
                        label_lang,
                    )
                )
                QgsProject.instance().addMapLayer(auto_hydro_layer)
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
            run_manifest_path = self._write_run_manifest_snapshot(
                "calibration",
                result.run_manifest,
            )
            self._write_benchmark_manifest(
                service_name="calibration",
                run_manifest=result.run_manifest,
                runtime_seconds=getattr(task, "_runtime_seconds", 0.0),
                run_manifest_path=run_manifest_path,
                report_json_path=json_path,
                report_md_path=md_path,
                notes="Auto-saved from QGIS UI calibration run.",
            )
            self._show_report_popup(report, json_path, md_path)

            if int(reported_metrics.get("count", 0) or 0) > 0:
                success_message = ui_text(
                    "calibration_success_template",
                    default="Calibration done: ROC_AUC={roc_auc:.4f}, PR_AUC={pr_auc:.4f}",
                ).format(
                    roc_auc=reported_metrics.get("roc_auc", 0),
                    pr_auc=reported_metrics.get("pr_auc", 0),
                )
            else:
                success_message = ui_text(
                    "calibration_success_no_holdout_template",
                    self._label_language(),
                    default="Calibration done: tuning diagnostics prepared, but no held-out evaluation rows were available.",
                )
            self.iface.messageBar().pushSuccess(
                tr("plugin_title"),
                success_message,
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

        self._run_background_task(
            "Run feng shui calibration",
            _execute,
            _on_success,
            failure_code=FengShuiErrorCode.CALIBRATION_FAILURE,
            failure_context="Calibration failed",
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
            "DEM CRS is geographic (degrees). This plugin's distance and radius "
            "calculations require a projected CRS. Reproject the DEM to a meter-based "
            "CRS and run again."
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
    def _resolved_calibration_context(culture_key, period_key):
        neutral_key = neutral_context_key()
        culture_value = str(culture_key or "").strip()
        period_value = str(period_key or "").strip()
        if culture_value.lower() == neutral_key or period_value.lower() == neutral_key:
            return neutral_key, neutral_key

        if not culture_value:
            calibration_rules = analysis_rules().get("calibration", {})
            culture_value = str(
                calibration_rules.get("default_culture", "korea")
            ).strip() or "korea"
        if not period_value:
            period_value = base_period_key()
        return culture_value.lower(), period_value.lower()

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
        lookup_warning_emitted = False
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
                if (
                    not group_candidates
                    and getattr(service, "last_query_error", None)
                    and not lookup_warning_emitted
                ):
                    self.iface.messageBar().pushWarning(
                        tr("plugin_title"),
                        str(service.last_query_error),
                    )
                    lookup_warning_emitted = True
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
                "Context evidence includes heuristic priors (C/U): "
                "{low}/{total}. Consider exploratory usage + local calibration."
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
            score_field = "cal_score" if "cal_score" in field_names else "fs_score"
            site_score_band_expr = self._score_band_expr(score_field)
            score_title = (
                ui_text("cal_score_title", text_lang, default="Calibrated Score")
                if score_field == "cal_score"
                else fs_score_title
            )
            cal_score_alias = ui_text(
                "cal_score_alias",
                text_lang,
                default="Calibrated score (0-1)",
            )
            cal_f1_alias = ui_text(
                "cal_f1_alias",
                text_lang,
                default="Best F1 threshold",
            )
            cal_youden_alias = ui_text(
                "cal_youden_alias",
                text_lang,
                default="Best Youden threshold",
            )
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
                    "cal_score": cal_score_alias,
                    "cal_f1_th": cal_f1_alias,
                    "cal_yj_th": cal_youden_alias,
                },
            )
            layer.setDisplayExpression(
                f"'{score_field}=' || to_string(round(\"{score_field}\", 3))"
            )
            threshold_tip = ""
            if "cal_score" in field_names:
                threshold_tip = (
                    "<p><b>base_fs_score</b>: [% round(\"fs_score\", 3) %]"
                    + (
                        ", <b>best_f1_th</b>: [% round(\"cal_f1_th\", 3) %]"
                        if "cal_f1_th" in field_names
                        else ""
                    )
                    + (
                        ", <b>best_youden_th</b>: [% round(\"cal_yj_th\", 3) %]"
                        if "cal_yj_th" in field_names
                        else ""
                    )
                    + "</p>"
                )
            layer.setMapTipTemplate(
                f"<h3>{score_title}</h3>"
                f"<p><b>{maptip_score}</b>: [% round(\"{score_field}\", 3) %] ([% {site_score_band_expr} %]), "
                f"<b>{maptip_confidence}</b>: [% round(\"fs_conf\", 3) %] ([% {fs_conf_band_expr} %])</p>"
                f"{threshold_tip}"
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
        report_dir = self._report_dir()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"feng_shui_calibration_{stamp}"
        json_path = os.path.join(report_dir, f"{base_name}.json")
        md_path = os.path.join(report_dir, f"{base_name}.md")
        report.update(self._export_calibrated_profile(report, stamp, report_dir))

        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        history_records = self._collect_calibration_history(report_dir)

        text_lang = self._label_language()
        paper_evidence_summary = str(report.get("paper_evidence_summary", "") or "").strip()
        paper_evidence_references = reference_display_text(
            self._paper_evidence_sources(report.get("paper_evidence_records")),
            language=text_lang,
            limit=10,
        ).strip()
        markdown = CalibrationReportWriter.build_markdown(
            report=report,
            stamp=stamp,
            text_lang=text_lang,
            metric_compare_markdown=self._calibration_metric_comparison_markdown(
                report,
                text_lang,
            ),
            metadata_markdown=self._calibration_metadata_markdown(report, text_lang),
            history_markdown=self._calibration_history_markdown(
                history_records,
                text_lang,
            ),
            paper_evidence_summary=paper_evidence_summary,
            paper_evidence_references=paper_evidence_references,
        )
        with open(md_path, "w", encoding="utf-8") as handle:
            handle.write(markdown)

        return json_path, md_path

    @staticmethod
    def _paper_evidence_sources(paper_evidence_records):
        if not isinstance(paper_evidence_records, list):
            return []
        sources = []
        seen = set()
        for record in paper_evidence_records:
            if not isinstance(record, dict):
                continue
            for source in record.get("source_doi", []):
                source_text = str(source or "").strip()
                if not source_text or source_text in seen:
                    continue
                seen.add(source_text)
                sources.append(source_text)
                if len(sources) >= 12:
                    break
            if len(sources) >= 12:
                break
        return sources

    def _export_calibrated_profile(self, report, stamp, report_dir):
        export_info = {
            "profile_export_status": "skipped-no-change",
            "exported_profile_key": "",
            "profile_export_path": "",
            "local_profile_registry_path": "",
        }
        reported_baseline_metrics = self._calibration_report_baseline_metrics(report)
        reported_metrics = self._calibration_report_metrics(report)
        tuned_weights = report.get("tuned_weights") or {}
        tuned_parameters = report.get("tuned_profile_parameters") or {}
        if not report.get("calibration_applied") or not tuned_weights or not tuned_parameters:
            return export_info

        from .config_loader import clear_cache
        from .profile_catalog import profile_label

        base_profile_key = str(report.get("profile_key") or "profile").strip() or "profile"
        culture_key = str(report.get("culture_key") or "context").strip() or "context"
        period_key = str(report.get("period_key") or "period").strip() or "period"
        exported_profile_key = (
            f"{base_profile_key}_{culture_key}_{period_key}_cal_{stamp}".lower()
        )
        base_label_ko = profile_label(base_profile_key, "ko")
        base_label_en = profile_label(base_profile_key, "en")
        profile_spec = {
            "label": {
                "ko": f"{base_label_ko} 보정 {culture_key}/{period_key}",
                "en": f"{base_label_en} Calibrated {culture_key}/{period_key}",
            },
            "weights": dict(tuned_weights),
            "slope_target": float(tuned_parameters.get("slope_target", 0.0)),
            "slope_sigma": float(tuned_parameters.get("slope_sigma", 1.0)),
            "tpi_target": float(tuned_parameters.get("tpi_target", 0.0)),
            "tpi_sigma": float(tuned_parameters.get("tpi_sigma", 0.1)),
            "derived_from": {
                "profile_key": base_profile_key,
                "culture_key": culture_key,
                "period_key": period_key,
                "hemisphere": report.get("hemisphere"),
                "negative_ratio": report.get("negative_ratio"),
                "random_seed": report.get("random_seed"),
                "reported_metric_phase": report.get("reported_metric_phase"),
                "reported_metric_notice": report.get("reported_metric_notice"),
                "base_roc_auc": reported_baseline_metrics.get("roc_auc"),
                "roc_auc": reported_metrics.get("roc_auc"),
                "base_pr_auc": reported_baseline_metrics.get("pr_auc"),
                "pr_auc": reported_metrics.get("pr_auc"),
                "tuned_weight_summary": report.get("tuned_weight_summary"),
                "tuned_parameter_summary": report.get("tuned_parameter_summary"),
            },
        }

        snapshot_path = os.path.join(report_dir, f"feng_shui_profile_{stamp}.json")
        with open(snapshot_path, "w", encoding="utf-8") as handle:
            json.dump(
                {exported_profile_key: profile_spec},
                handle,
                ensure_ascii=False,
                indent=2,
            )

        try:
            local_profiles = local_profiles_payload()
        except RuntimeError as exc:
            raise RuntimeError(
                "Local profile registry contract load failed"
            ) from exc
        if not isinstance(local_profiles, dict):
            raise RuntimeError(
                "Local profile registry payload is invalid; expected JSON object."
            )
        local_profiles[exported_profile_key] = profile_spec
        try:
            write_local_profiles_payload(local_profiles)
        except RuntimeError as exc:
            raise RuntimeError(
                "Local profile registry contract write failed"
            ) from exc
        clear_cache()

        export_info.update(
            {
                "profile_export_status": "saved",
                "exported_profile_key": exported_profile_key,
                "profile_export_path": snapshot_path,
                "local_profile_registry_path": os.path.join(
                    self.plugin_dir,
                    "config",
                    "local_profiles.json",
                ),
            }
        )
        return export_info

    @staticmethod
    def _markdown_table(headers, rows):
        safe_headers = [str(header).replace("|", "/") for header in headers]
        lines = [
            "| " + " | ".join(safe_headers) + " |",
            "| " + " | ".join(["---"] * len(safe_headers)) + " |",
        ]
        for row in rows:
            safe_row = [str(cell).replace("|", "/") for cell in row]
            lines.append("| " + " | ".join(safe_row) + " |")
        return "\n".join(lines)

    @staticmethod
    def _html_table(headers, rows):
        head_cells = "".join(f"<th>{escape(str(header))}</th>" for header in headers)
        body_rows = []
        for row in rows:
            body_rows.append(
                "<tr>" + "".join(f"<td>{escape(str(cell))}</td>" for cell in row) + "</tr>"
            )
        return (
            "<table border='1' cellspacing='0' cellpadding='4'>"
            f"<thead><tr>{head_cells}</tr></thead>"
            f"<tbody>{''.join(body_rows)}</tbody>"
            "</table>"
        )

    @staticmethod
    def _calibration_report_metric_bundle(report, bundle_key, fallback_prefix=""):
        return CalibrationReportWriter.metric_bundle(
            report,
            bundle_key,
            fallback_prefix=fallback_prefix,
        )

    def _calibration_report_metrics(self, report):
        return self._calibration_report_metric_bundle(report, "reported_metrics")

    def _calibration_report_baseline_metrics(self, report):
        return self._calibration_report_metric_bundle(
            report,
            "reported_baseline_metrics",
            fallback_prefix="base_",
        )

    def _calibration_goal_text(self, text_lang):
        return CalibrationReportWriter.goal_text(text_lang)

    def _calibration_report_phase_parts(self, report, text_lang):
        return CalibrationReportWriter.phase_parts(report, text_lang)

    def _calibration_metric_rows(self, report):
        baseline_metrics = self._calibration_report_baseline_metrics(report)
        reported_metrics = self._calibration_report_metrics(report)
        return [
            ("ROC AUC", baseline_metrics.get("roc_auc", 0.0), reported_metrics.get("roc_auc", 0.0)),
            ("PR AUC", baseline_metrics.get("pr_auc", 0.0), reported_metrics.get("pr_auc", 0.0)),
            ("Best F1", baseline_metrics.get("best_f1", 0.0), reported_metrics.get("best_f1", 0.0)),
            (
                "Best Youden J",
                baseline_metrics.get("best_youden_j", 0.0),
                reported_metrics.get("best_youden_j", 0.0),
            ),
        ]

    def _calibration_metric_comparison_markdown(self, report, text_lang):
        headers = [
            ui_text("calibration_metric_header_metric", text_lang, default="Metric"),
            ui_text("calibration_metric_header_base", text_lang, default="Baseline"),
            ui_text("calibration_metric_header_tuned", text_lang, default="Reported"),
            ui_text("calibration_metric_header_delta", text_lang, default="Delta"),
        ]
        rows = []
        for label, base_value, tuned_value in self._calibration_metric_rows(report):
            delta = float(tuned_value or 0.0) - float(base_value or 0.0)
            rows.append(
                [
                    label,
                    f"{float(base_value or 0.0):.4f}",
                    f"{float(tuned_value or 0.0):.4f}",
                    f"{delta:+.4f}",
                ]
            )
        return self._markdown_table(headers, rows)

    def _calibration_metric_comparison_html(self, report, text_lang):
        headers = [
            ui_text("calibration_metric_header_metric", text_lang, default="Metric"),
            ui_text("calibration_metric_header_base", text_lang, default="Baseline"),
            ui_text("calibration_metric_header_tuned", text_lang, default="Reported"),
            ui_text("calibration_metric_header_delta", text_lang, default="Delta"),
        ]
        rows = []
        for label, base_value, tuned_value in self._calibration_metric_rows(report):
            delta = float(tuned_value or 0.0) - float(base_value or 0.0)
            rows.append(
                [
                    label,
                    f"{float(base_value or 0.0):.4f}",
                    f"{float(tuned_value or 0.0):.4f}",
                    f"{delta:+.4f}",
                ]
            )
        return self._html_table(headers, rows)

    def _calibration_metadata_markdown(self, report, text_lang):
        summary = report.get("site_metadata_summary") or {}
        groupings = summary.get("groupings", [])
        layer_name = summary.get("layer_name") or report.get("site_layer_name") or "n/a"
        feature_count = int(report.get("positive_count", 0) or 0)
        layer_label = ui_text("calibration_metadata_layer_label", text_lang, default="Layer")
        positive_count_label = ui_text(
            "calibration_metadata_positive_count_label",
            text_lang,
            default="Positive sample count",
        )
        lines = [f"- {layer_label}: {layer_name}\n- {positive_count_label}: {feature_count}"]
        kind_labels = {
            "site_group": ui_text(
                "calibration_metadata_kind_site_group",
                text_lang,
                default="Site group",
            ),
            "country": ui_text(
                "calibration_metadata_kind_country",
                text_lang,
                default="Country/region",
            ),
            "period": ui_text(
                "calibration_metadata_kind_period",
                text_lang,
                default="Period",
            ),
        }
        if not groupings:
            lines.append(
                ui_text(
                    "calibration_metadata_no_groupings",
                    text_lang,
                    default="No attribute fields were detected for site-group/country/period comparison.",
                )
            )
            return "\n\n".join(lines)
        for grouping in groupings:
            title = kind_labels.get(grouping.get("kind"), grouping.get("kind"))
            field_name = grouping.get("field", "")
            headers = [
                ui_text("calibration_metadata_value_header", text_lang, default="Value"),
                ui_text("calibration_metadata_count_header", text_lang, default="Count"),
                ui_text("calibration_metadata_share_header", text_lang, default="Share"),
            ]
            rows = []
            for row in grouping.get("rows", []):
                rows.append(
                    [
                        row.get("value", ""),
                        str(row.get("count", 0)),
                        f"{float(row.get('share', 0.0)) * 100.0:.1f}%",
                    ]
                )
            lines.append(f"### {title} (`{field_name}`)\n\n{self._markdown_table(headers, rows)}")
        return "\n\n".join(lines)

    def _calibration_metadata_html(self, report, text_lang):
        summary = report.get("site_metadata_summary") or {}
        groupings = summary.get("groupings", [])
        layer_name = summary.get("layer_name") or report.get("site_layer_name") or "n/a"
        feature_count = int(report.get("positive_count", 0) or 0)
        layer_label = ui_text("calibration_metadata_layer_label", text_lang, default="Layer")
        positive_count_label = ui_text(
            "calibration_metadata_positive_count_label",
            text_lang,
            default="Positive sample count",
        )
        parts = [
            (
                f"<p><b>{escape(layer_label)}</b>: {escape(str(layer_name))}"
                f"<br/><b>{escape(positive_count_label)}</b>: {feature_count}</p>"
            )
        ]
        kind_labels = {
            "site_group": ui_text(
                "calibration_metadata_kind_site_group",
                text_lang,
                default="Site group",
            ),
            "country": ui_text(
                "calibration_metadata_kind_country",
                text_lang,
                default="Country/region",
            ),
            "period": ui_text(
                "calibration_metadata_kind_period",
                text_lang,
                default="Period",
            ),
        }
        if not groupings:
            parts.append(
                f"<p>{escape(ui_text('calibration_metadata_no_groupings', text_lang, default='No attribute fields were detected for site-group/country/period comparison.'))}</p>"
            )
            return "".join(parts)
        for grouping in groupings:
            title = kind_labels.get(grouping.get("kind"), grouping.get("kind"))
            field_name = grouping.get("field", "")
            headers = [
                ui_text("calibration_metadata_value_header", text_lang, default="Value"),
                ui_text("calibration_metadata_count_header", text_lang, default="Count"),
                ui_text("calibration_metadata_share_header", text_lang, default="Share"),
            ]
            rows = []
            for row in grouping.get("rows", []):
                rows.append(
                    [
                        row.get("value", ""),
                        str(row.get("count", 0)),
                        f"{float(row.get('share', 0.0)) * 100.0:.1f}%",
                    ]
                )
            parts.append(f"<p><b>{escape(str(title))}</b> ({escape(str(field_name))})</p>")
            parts.append(self._html_table(headers, rows))
        return "".join(parts)

    def _collect_calibration_history(self, report_dir, limit=40):
        if not report_dir or not os.path.isdir(report_dir):
            return []
        records = []
        for filename in sorted(os.listdir(report_dir), reverse=True):
            if not filename.startswith("feng_shui_calibration_") or not filename.endswith(".json"):
                continue
            path = os.path.join(report_dir, filename)
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    record = json.load(handle)
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(record, dict):
                continue
            record["report_file"] = filename
            record["report_path"] = path
            records.append(record)
            if len(records) >= max(1, int(limit)):
                break
        return records

    @staticmethod
    def _history_context_key(record):
        return (
            str(record.get("culture_key") or ""),
            str(record.get("period_key") or ""),
            str(record.get("profile_key") or ""),
        )

    def _calibration_history_summary_rows(self, history_records):
        grouped = {}
        for record in history_records:
            key = self._history_context_key(record)
            bucket = grouped.setdefault(
                key,
                {
                    "runs": 0,
                    "roc_auc_total": 0.0,
                    "pr_auc_total": 0.0,
                    "best_roc_auc": 0.0,
                    "latest_layer": "",
                    "latest_file": "",
                },
            )
            bucket["runs"] += 1
            bucket["roc_auc_total"] += float(record.get("roc_auc", 0.0) or 0.0)
            bucket["pr_auc_total"] += float(record.get("pr_auc", 0.0) or 0.0)
            bucket["best_roc_auc"] = max(
                bucket["best_roc_auc"],
                float(record.get("roc_auc", 0.0) or 0.0),
            )
            latest_file = str(record.get("report_file") or "")
            if latest_file >= bucket["latest_file"]:
                bucket["latest_file"] = latest_file
                bucket["latest_layer"] = str(record.get("site_layer_name") or "")

        rows = []
        for key, bucket in sorted(
            grouped.items(),
            key=lambda item: (
                -item[1]["runs"],
                -item[1]["roc_auc_total"],
                item[0],
            ),
        ):
            culture_key, period_key, profile_key = key
            runs = max(1, int(bucket["runs"]))
            rows.append(
                [
                    culture_key or "-",
                    period_key or "-",
                    profile_key or "-",
                    str(runs),
                    f"{bucket['roc_auc_total'] / runs:.4f}",
                    f"{bucket['pr_auc_total'] / runs:.4f}",
                    f"{bucket['best_roc_auc']:.4f}",
                    bucket.get("latest_layer") or "-",
                ]
            )
        return rows[:10]

    @staticmethod
    def _calibration_history_recent_rows(history_records):
        rows = []
        for record in history_records[:8]:
            rows.append(
                [
                    str(record.get("report_file") or "").replace(".json", ""),
                    str(record.get("culture_key") or "-"),
                    str(record.get("period_key") or "-"),
                    str(record.get("profile_key") or "-"),
                    str(record.get("site_layer_name") or "-"),
                    f"{float(record.get('roc_auc', 0.0) or 0.0):.4f}",
                    f"{float(record.get('pr_auc', 0.0) or 0.0):.4f}",
                ]
            )
        return rows

    @staticmethod
    def _record_site_group_rows(record):
        summary = record.get("site_metadata_summary") or {}
        if not isinstance(summary, dict):
            return []
        groupings = summary.get("groupings") or []
        if not isinstance(groupings, list):
            return []
        for grouping in groupings:
            if not isinstance(grouping, dict):
                continue
            if grouping.get("kind") == "site_group":
                rows = grouping.get("rows") or []
                return rows if isinstance(rows, list) else []
        return []

    def _calibration_site_group_history_rows(self, history_records):
        buckets = {}
        for record in history_records:
            report_file = str(record.get("report_file") or "")
            roc_auc = float(record.get("roc_auc", 0.0) or 0.0)
            pr_auc = float(record.get("pr_auc", 0.0) or 0.0)
            culture_key = str(record.get("culture_key") or "-")
            period_key = str(record.get("period_key") or "-")
            profile_key = str(record.get("profile_key") or "-")
            for row in self._record_site_group_rows(record):
                value = str(row.get("value") or "(empty)")
                bucket = buckets.setdefault(
                    value,
                    {
                        "runs": 0,
                        "share_total": 0.0,
                        "roc_total": 0.0,
                        "pr_total": 0.0,
                        "latest_file": "",
                        "latest_context": "",
                    },
                )
                bucket["runs"] += 1
                bucket["share_total"] += float(row.get("share", 0.0) or 0.0)
                bucket["roc_total"] += roc_auc
                bucket["pr_total"] += pr_auc
                if report_file >= bucket["latest_file"]:
                    bucket["latest_file"] = report_file
                    bucket["latest_context"] = f"{culture_key}/{period_key}/{profile_key}"

        rows = []
        for value, bucket in sorted(
            buckets.items(),
            key=lambda item: (-item[1]["runs"], -item[1]["share_total"], item[0]),
        ):
            runs = max(1, int(bucket["runs"]))
            rows.append(
                [
                    value,
                    str(runs),
                    f"{(bucket['share_total'] / runs) * 100.0:.1f}%",
                    f"{bucket['roc_total'] / runs:.4f}",
                    f"{bucket['pr_total'] / runs:.4f}",
                    bucket.get("latest_context") or "-",
                ]
            )
        return rows[:10]

    def _calibration_history_markdown(self, history_records, text_lang):
        if not history_records:
            return ui_text(
                "calibration_history_no_records",
                text_lang,
                default="No prior calibration history was found.",
            )
        summary_headers = [
            ui_text("calibration_history_summary_header_culture", text_lang, default="Culture"),
            ui_text("calibration_history_summary_header_period", text_lang, default="Period"),
            ui_text("calibration_history_summary_header_profile", text_lang, default="Profile"),
            ui_text("calibration_history_summary_header_runs", text_lang, default="Runs"),
            ui_text("calibration_history_summary_header_avg_roc", text_lang, default="Avg ROC"),
            ui_text("calibration_history_summary_header_avg_pr", text_lang, default="Avg PR"),
            ui_text("calibration_history_summary_header_best_roc", text_lang, default="Best ROC"),
            ui_text("calibration_history_summary_header_latest_layer", text_lang, default="Latest layer"),
        ]
        recent_headers = [
            ui_text("calibration_history_recent_header_run_file", text_lang, default="Run file"),
            ui_text("calibration_history_recent_header_culture", text_lang, default="Culture"),
            ui_text("calibration_history_recent_header_period", text_lang, default="Period"),
            ui_text("calibration_history_recent_header_profile", text_lang, default="Profile"),
            ui_text("calibration_history_recent_header_layer", text_lang, default="Layer"),
            ui_text("calibration_history_recent_header_roc", text_lang, default="ROC"),
            ui_text("calibration_history_recent_header_pr", text_lang, default="PR"),
        ]
        site_group_headers = [
            ui_text("calibration_history_site_group_header_name", text_lang, default="Site group"),
            ui_text("calibration_history_site_group_header_runs", text_lang, default="Runs"),
            ui_text("calibration_history_site_group_header_avg_share", text_lang, default="Avg share"),
            ui_text("calibration_history_site_group_header_avg_roc", text_lang, default="Avg ROC"),
            ui_text("calibration_history_site_group_header_avg_pr", text_lang, default="Avg PR"),
            ui_text(
                "calibration_history_site_group_header_latest_context",
                text_lang,
                default="Latest context",
            ),
        ]
        summary_title = ui_text(
            "calibration_history_summary_title",
            text_lang,
            default="Context summary",
        )
        site_group_title = ui_text(
            "calibration_history_site_group_title",
            text_lang,
            default="Site-group summary",
        )
        recent_title = ui_text(
            "calibration_history_recent_title",
            text_lang,
            default="Recent runs",
        )
        site_group_rows = self._calibration_site_group_history_rows(history_records)
        site_group_block = (
            self._markdown_table(site_group_headers, site_group_rows)
            if site_group_rows
            else ui_text(
                "calibration_history_no_site_groups",
                text_lang,
                default="No calibration history with site-group fields was found yet.",
            )
        )
        return (
            f"### {summary_title}\n\n"
            f"{self._markdown_table(summary_headers, self._calibration_history_summary_rows(history_records))}\n\n"
            f"### {site_group_title}\n\n"
            f"{site_group_block}\n\n"
            f"### {recent_title}\n\n"
            f"{self._markdown_table(recent_headers, self._calibration_history_recent_rows(history_records))}"
        )

    def _calibration_history_html(self, history_records, text_lang):
        if not history_records:
            return (
                f"<p>{escape(ui_text('calibration_history_no_records', text_lang, default='No prior calibration history was found.'))}</p>"
            )
        summary_headers = [
            ui_text("calibration_history_summary_header_culture", text_lang, default="Culture"),
            ui_text("calibration_history_summary_header_period", text_lang, default="Period"),
            ui_text("calibration_history_summary_header_profile", text_lang, default="Profile"),
            ui_text("calibration_history_summary_header_runs", text_lang, default="Runs"),
            ui_text("calibration_history_summary_header_avg_roc", text_lang, default="Avg ROC"),
            ui_text("calibration_history_summary_header_avg_pr", text_lang, default="Avg PR"),
            ui_text("calibration_history_summary_header_best_roc", text_lang, default="Best ROC"),
            ui_text("calibration_history_summary_header_latest_layer", text_lang, default="Latest layer"),
        ]
        recent_headers = [
            ui_text("calibration_history_recent_header_run_file", text_lang, default="Run file"),
            ui_text("calibration_history_recent_header_culture", text_lang, default="Culture"),
            ui_text("calibration_history_recent_header_period", text_lang, default="Period"),
            ui_text("calibration_history_recent_header_profile", text_lang, default="Profile"),
            ui_text("calibration_history_recent_header_layer", text_lang, default="Layer"),
            ui_text("calibration_history_recent_header_roc", text_lang, default="ROC"),
            ui_text("calibration_history_recent_header_pr", text_lang, default="PR"),
        ]
        site_group_headers = [
            ui_text("calibration_history_site_group_header_name", text_lang, default="Site group"),
            ui_text("calibration_history_site_group_header_runs", text_lang, default="Runs"),
            ui_text("calibration_history_site_group_header_avg_share", text_lang, default="Avg share"),
            ui_text("calibration_history_site_group_header_avg_roc", text_lang, default="Avg ROC"),
            ui_text("calibration_history_site_group_header_avg_pr", text_lang, default="Avg PR"),
            ui_text(
                "calibration_history_site_group_header_latest_context",
                text_lang,
                default="Latest context",
            ),
        ]
        summary_title = ui_text(
            "calibration_history_summary_title",
            text_lang,
            default="Context summary",
        )
        site_group_title = ui_text(
            "calibration_history_site_group_title",
            text_lang,
            default="Site-group summary",
        )
        recent_title = ui_text(
            "calibration_history_recent_title",
            text_lang,
            default="Recent runs",
        )
        site_group_rows = self._calibration_site_group_history_rows(history_records)
        site_group_block = (
            self._html_table(site_group_headers, site_group_rows)
            if site_group_rows
            else (
                f"<p>{escape(ui_text('calibration_history_no_site_groups', text_lang, default='No calibration history with site-group fields was found yet.'))}</p>"
            )
        )
        return (
            f"<p><b>{escape(summary_title)}</b></p>"
            f"{self._html_table(summary_headers, self._calibration_history_summary_rows(history_records))}"
            f"<p><b>{escape(site_group_title)}</b></p>"
            f"{site_group_block}"
            f"<p><b>{escape(recent_title)}</b></p>"
            f"{self._html_table(recent_headers, self._calibration_history_recent_rows(history_records))}"
        )

    def _show_report_popup(self, report, json_path, md_path):
        text_lang = self._label_language()
        if self._report_dialog is None:
            self._report_dialog = QDialog(self.iface.mainWindow())
            self._report_dialog.resize(760, 520)
            layout = QVBoxLayout(self._report_dialog)
            self._report_browser = QTextBrowser(self._report_dialog)
            self._report_browser.setOpenExternalLinks(True)
            self._report_browser.setReadOnly(True)
            layout.addWidget(self._report_browser)
        self._report_dialog.setWindowTitle(
            ui_text(
                "calibration_report_title",
                text_lang,
                default="Calibration Report",
            )
        )
        paper_summary = str(report.get("paper_evidence_summary", "") or "").strip()
        paper_references = reference_display_text(
            self._paper_evidence_sources(report.get("paper_evidence_records")),
            language=text_lang,
            limit=10,
        ).strip()

        html = CalibrationReportWriter.build_popup_html(
            report=report,
            text_lang=text_lang,
            json_path=json_path,
            md_path=md_path,
            metric_compare_html=self._calibration_metric_comparison_html(report, text_lang),
            metadata_html=self._calibration_metadata_html(report, text_lang),
            history_html=self._calibration_history_html(
                self._collect_calibration_history(os.path.dirname(json_path)),
                text_lang,
            ),
            paper_evidence_summary=paper_summary,
            paper_evidence_references=paper_references,
        )
        self._report_browser.setHtml(html)
        self._report_dialog.show()
        self._report_dialog.raise_()
        self._report_dialog.activateWindow()
