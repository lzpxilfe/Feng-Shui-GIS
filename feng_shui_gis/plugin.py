# -*- coding: utf-8 -*-
import json
import os
from html import escape
from datetime import datetime

from qgis.PyQt.QtCore import QTimer, QVariant
from qgis.PyQt.QtGui import QColor, QIcon
from qgis.PyQt.QtWidgets import QAction, QDialog, QVBoxLayout, QTextBrowser
from qgis.core import (
    QgsApplication,
    QgsCategorizedSymbolRenderer,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsMessageLog,
    Qgis,
    QgsProject,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingException,
    QgsRendererCategory,
    QgsTask,
    QgsSymbol,
    QgsWkbTypes,
    QgsVectorLayer,
    edit,
)

from .analysis import FengShuiAnalyzer
from .calibration_profile_export import export_calibrated_profile
from .calibration_reporting import (
    build_calibration_popup_html,
    build_calibration_popup_sections,
    write_calibration_report_files,
)
from .china_geodesy import datum_advisory, recommended_projected_crs
from .compare_layer_export import (
    export_top_changed_features_layer,
    style_compare_change_layer,
)
from .compare_layer_actions import (
    select_changed_features,
    zoom_to_selected_features,
)
from .compare_reporting import build_compare_popup_html, write_compare_report
from .cultural_context import (
    base_period_key,
    context_evidence_records,
    neutral_context_key,
)
from .dock_widget import FengShuiDockWidget
from .feature_identity import (
    duplicate_feature_uids,
    duplicate_uids_from_index,
    feature_ids_for_uids,
    feature_uid,
    feature_uid_index,
    is_derived_uid_excluded_field,
    normalize_change_uids,
    normalized_feature_uid_value,
    uid_lookup_summary,
    uid_match_summary,
)
from .feature_reason_presenter import (
    build_feature_reason_message,
    build_feature_reason_limitations,
    build_feature_reason_overview,
    build_reason_popup_html,
    build_term_cluster_reason,
)
from .locale import tr
from .layer_info_presenter import (
    compare_layer_info_config,
    link_layer_info_config,
    mountain_tip_html,
    ridge_layer_info_config,
    site_layer_info_config,
    stream_layer_info_config,
    term_layer_info_config,
)
from .mountain_enrichment import resolve_mountain_name_options
from .mountain_lookup import MountainNameService
from .mountain_layer_enrichment import (
    enrich_layer_with_mountain_names,
    enrich_layers_with_mountain_names,
    feature_anchor_point,
    feature_priority,
)
from .mountain_options import mountain_options
from .application_services import (
    run_analysis_service,
    run_calibration_service,
    run_profile_compare_service,
    run_term_extraction_service,
)
from .service_contracts import (
    AnalysisRequest,
    CalibrationRequest,
    CompareRequest,
    TermExtractionRequest,
)
from .profile_catalog import analysis_rules, normalize_label_language
from .ui_catalog import ui_text


class _AnalysisTaskFeedback(QgsProcessingFeedback):
    def __init__(self, task):
        super().__init__()
        self._task = task

    def setProgress(self, value):
        try:
            value = float(value)
            self._task.setProgress(max(0, min(100, int(value))))
        except (TypeError, ValueError):
            pass
        return super().setProgress(value)


class _PluginRunTask(QgsTask):
    def __init__(self, description, worker, payload_handler):
        super().__init__(description, QgsTask.CanCancel)
        self._worker = worker
        self._payload_handler = payload_handler
        self._payload = None
        self._worker_error = None

    def run(self):
        if self.isCanceled():
            return True
        try:
            self._payload = self._worker(self)
        except Exception as exc:  # pragma: no cover
            self._worker_error = exc
            return False
        return True

    def finished(self, result):
        payload = {"ok": True}
        if self.isCanceled():
            payload = {"ok": False, "error_code": "E_TASK_CANCELLED", "error_context": "Task cancelled"}
        elif not result or self._worker_error is not None:
            if self._worker_error is None:
                payload = {
                    "ok": False,
                    "error_code": "E_TASK_FAILED",
                    "error_context": "Task failed without explicit error context",
                }
            else:
                payload = {
                    "ok": False,
                    "error_code": "E_TASK_EXCEPTION",
                    "error_context": "Background task raised an exception",
                    "error": self._worker_error,
                }
        elif isinstance(self._payload, dict):
            payload = self._payload

        if not isinstance(payload, dict):
            payload = {"ok": False, "error_code": "E_TASK_FAILED", "error_context": "Unexpected task payload"}
        self._payload_handler(payload)


class FengShuiGisPlugin:
    _LOG_TAG = "Feng Shui GIS"
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
            "hyeol_fields": "fengshui_hyeol_field",
            "support_fields": "fengshui_support_fields",
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
            "hyeol_fields": "풍수_혈장",
            "support_fields": "풍수_감쌈장",
            "term_links": "풍수_구조연결",
            "hydro_auto": "풍수_자동수계",
            "hydro_auto_calibration": "풍수_자동수계_보정",
        },
    }
    _ERROR_CATALOG = {
        "E_ANALYSIS_RUNTIME": {
            "user_ko": "입지 분석 실행 중 오류가 발생해 중단했습니다. 입력 레이어/파라미터를 확인해 주세요.",
            "user_en": "Analysis failed. Please check input layers and parameters, then rerun.",
            "debug": "Analysis pipeline runtime failure.",
        },
        "E_ANALYSIS_UNEXPECTED": {
            "user_ko": "예상치 못한 분석 오류가 발생해 작업을 중단했습니다.",
            "user_en": "Unexpected analysis error. The operation was stopped.",
            "debug": "Unexpected analysis failure.",
        },
        "E_LANDSCAPE_RUNTIME": {
            "user_ko": "지형 추출 실행 중 오류가 발생해 중단했습니다.",
            "user_en": "Landscape extraction failed. The operation was stopped.",
            "debug": "Landscape extraction runtime failure.",
        },
        "E_LANDSCAPE_UNEXPECTED": {
            "user_ko": "예상치 못한 지형 추출 오류가 발생해 중단했습니다.",
            "user_en": "Unexpected landscape extraction error. The operation was stopped.",
            "debug": "Unexpected landscape extraction failure.",
        },
        "E_COMPARE_RUNTIME": {
            "user_ko": "프로파일 비교 중 오류가 발생해 중단했습니다.",
            "user_en": "Profile comparison failed. The operation was stopped.",
            "debug": "Profile compare runtime failure.",
        },
        "E_COMPARE_UNEXPECTED": {
            "user_ko": "예상치 못한 비교 오류가 발생해 중단했습니다.",
            "user_en": "Unexpected profile comparison error. The operation was stopped.",
            "debug": "Unexpected profile comparison failure.",
        },
        "E_CALIBRATION_RUNTIME": {
            "user_ko": "보정 실행 중 오류가 발생해 중단했습니다.",
            "user_en": "Calibration failed. The operation was stopped.",
            "debug": "Calibration runtime failure.",
        },
        "E_CALIBRATION_UNEXPECTED": {
            "user_ko": "예상치 못한 보정 오류가 발생해 중단했습니다.",
            "user_en": "Unexpected calibration error. The operation was stopped.",
            "debug": "Unexpected calibration failure.",
        },
        "E_DATA_MISMATCH": {
            "user_ko": "데이터 정합성 검사에 실패해 리포트를 생성하지 않았습니다.",
            "user_en": "Data contract check failed. Report generation was skipped.",
            "debug": "Contract validation failed.",
        },
        "E_REPORT_WRITE": {
            "user_ko": "리포트 생성 중 실패해 중단했습니다.",
            "user_en": "Report export failed. The operation was stopped.",
            "debug": "Report write failed.",
        },
        "E_MOUNTAIN_TIMEOUT": {
            "user_ko": "산명 조회 시간이 초과되어 이번 실행 구간은 건너뜁니다.",
            "user_en": "Mountain lookup timed out, and this run skipped this step.",
            "debug": "Mountain lookup timed out.",
        },
        "E_MOUNTAIN_NETWORK": {
            "user_ko": "산명 조회 네트워크가 불안정해 이번 실행 구간은 건너뜁니다.",
            "user_en": "Mountain lookup network issue occurred, and this run skipped this step.",
            "debug": "Mountain lookup network failure.",
        },
        "E_MOUNTAIN_BAD_DATA": {
            "user_ko": "산명 조회 응답 형식이 비정상이라 이번 실행 구간은 건너뜁니다.",
            "user_en": "Mountain lookup returned unexpected payload, and this run skipped this step.",
            "debug": "Mountain lookup payload decode/parse failure.",
        },
        "E_MOUNTAIN_NO_DATA": {
            "user_ko": "요청 범위에서 산명 후보가 없어 산명 보강을 생략했습니다.",
            "user_en": "No mountain candidates were found for the query area; skipping name enrichment.",
            "debug": "Mountain lookup no data for extent.",
        },
        "E_MOUNTAIN_CACHE_NO_DATA": {
            "user_ko": "산명 캐시에서 해당 구간 데이터를 찾지 못해 산명 보강을 생략했습니다.",
            "user_en": "No cached mountain data for the query area; skipping name enrichment.",
            "debug": "Mountain lookup cache miss for extent.",
        },
        "E_MOUNTAIN_BBOX_UNSUPPORTED": {
            "user_ko": "현재 지도 영역으로 산명 조회를 실행할 수 없어 산명 보강을 건너뜁니다.",
            "user_en": "Cannot run mountain lookup for the current area, so name enrichment was skipped.",
            "debug": "Mountain lookup skipped due unsupported bbox.",
        },
        "E_MOUNTAIN_UNKNOWN": {
            "user_ko": "산명 조회 중 알 수 없는 오류가 발생해 건너뜁니다.",
            "user_en": "Unknown mountain lookup error occurred; skipping this step.",
            "debug": "Mountain lookup unknown failure.",
        },
    }
    _ERROR_HANDLING_PRIORITY = {
        "E_ANALYSIS_RUNTIME": 70,
        "E_ANALYSIS_UNEXPECTED": 90,
        "E_LANDSCAPE_RUNTIME": 60,
        "E_LANDSCAPE_UNEXPECTED": 90,
        "E_COMPARE_RUNTIME": 65,
        "E_COMPARE_UNEXPECTED": 90,
        "E_CALIBRATION_RUNTIME": 65,
        "E_CALIBRATION_UNEXPECTED": 90,
        "E_DATA_MISMATCH": 85,
        "E_REPORT_WRITE": 75,
        "E_MOUNTAIN_TIMEOUT": 45,
        "E_MOUNTAIN_NETWORK": 45,
        "E_MOUNTAIN_BAD_DATA": 55,
        "E_MOUNTAIN_NO_DATA": 10,
        "E_MOUNTAIN_CACHE_NO_DATA": 8,
        "E_MOUNTAIN_BBOX_UNSUPPORTED": 5,
        "E_MOUNTAIN_UNKNOWN": 40,
    }
    _MOUNTAIN_STATUS_TO_ERROR_CODE = {
        MountainNameService.STATUS_TIMEOUT_ERROR: "E_MOUNTAIN_TIMEOUT",
        MountainNameService.STATUS_NETWORK_ERROR: "E_MOUNTAIN_NETWORK",
        MountainNameService.STATUS_BAD_PAYLOAD: "E_MOUNTAIN_BAD_DATA",
        MountainNameService.STATUS_NO_DATA: "E_MOUNTAIN_NO_DATA",
        MountainNameService.STATUS_CACHE_HIT_NO_DATA: "E_MOUNTAIN_CACHE_NO_DATA",
        MountainNameService.STATUS_BBOX_UNSUPPORTED: "E_MOUNTAIN_BBOX_UNSUPPORTED",
        MountainNameService.STATUS_UNKNOWN: "E_MOUNTAIN_UNKNOWN",
        MountainNameService.STATUS_OK: None,
        MountainNameService.STATUS_CACHE_HIT: None,
    }

    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.toolbar = None
        self.dock = None
        self.plugin_dir = os.path.dirname(__file__)
        self._selection_hooks = {}
        self._background_tasks = {}
        self._reason_dialog = None
        self._reason_browser = None
        self._report_dialog = None
        self._report_browser = None
        self._compare_dialog = None
        self._compare_browser = None
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
            except (RuntimeError, TypeError) as exc:
                self._log_debug(
                    f"selectionChanged disconnect skipped for layer {layer_id}: {type(exc).__name__}: {exc}"
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
        for task in list(self._background_tasks.values()):
            if task is not None and task.isActive():
                task.cancel()
        self._background_tasks.clear()
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
        if self.dock.isVisible():
            self.dock.hide()
        else:
            self.dock.show()
            self.dock.raise_()
            self.dock.activateWindow()

    @staticmethod
    def _error_label(lang, text_ko, text_en):
        if lang == "en":
            return text_en or text_ko
        return text_ko or text_en

    def _error_user_message(self, code, context, exc):
        lang = self._label_language()
        entry = self._ERROR_CATALOG.get(code, {})
        user = self._error_label(
            lang,
            entry.get("user_ko") or str(context),
            entry.get("user_en") or str(context),
        )
        if not user:
            user = str(context)
        if exc is None:
            return user
        detail = f"{type(exc).__name__}: {exc}"
        return f"{user} ({detail})"

    @classmethod
    def _error_priority(cls, code):
        return cls._ERROR_HANDLING_PRIORITY.get(code, 0)

    @staticmethod
    def _post_to_main_thread(callback):
        if callback is None:
            return
        try:
            QTimer.singleShot(0, callback)
            return
        except Exception:
            pass
        try:
            callback()
        except Exception:
            pass

    def _push_messagebar(self, level, title, message):
        text = str(message) if message is not None else ""

        def _emit():
            if self.iface is None:
                return
            bar = self.iface.messageBar()
            if bar is None:
                return
            if level == "critical":
                bar.pushCritical(title, text)
            elif level == "warning":
                bar.pushWarning(title, text)
            elif level == "info":
                bar.pushInfo(title, text)
            elif level == "success":
                bar.pushSuccess(title, text)
            else:
                bar.pushInfo(title, text)

        self._post_to_main_thread(_emit)

    def _set_status(self, text):
        if not self.dock or text is None:
            return
        self._post_to_main_thread(lambda: self.dock.set_status(text))

    def _log_and_notify_error(self, code, context, exc, include_exception=True):
        lang = self._label_language()
        entry = self._ERROR_CATALOG.get(
            code,
            {
                "debug": str(context),
                "user_ko": str(context),
                "user_en": str(context),
            },
        )
        debug_text = self._error_label(lang, entry.get("user_ko"), entry.get("user_en"))
        if include_exception and exc is not None:
            details = (
                f"{debug_text} | code={code} | priority={self._error_priority(code)}"
                f" | {type(exc).__name__}: {exc}"
            )
        else:
            details = f"{debug_text} | code={code} | priority={self._error_priority(code)}"
        self._log_debug(details, Qgis.Warning)
        user_message = self._error_user_message(code, context, exc if include_exception else None)
        self._push_messagebar("critical", tr("warn_failed"), user_message)
        self._set_status(self._error_user_message(code, context, None))

    def _log_and_notify_warning(self, code, context, detail=None):
        lang = self._label_language()
        entry = self._ERROR_CATALOG.get(
            code,
            {
                "user_ko": str(context),
                "user_en": str(context),
                "debug": str(context),
            },
        )
        message = self._error_label(
            lang,
            entry.get("user_ko") or str(context),
            entry.get("user_en") or str(context),
        )
        if context:
            message = f"{message} ({context})"
        if detail:
            message = f"{message} | {detail}"
        self._log_debug(
            f"{entry.get('debug', message)} | code={code} | priority={self._error_priority(code)}",
            Qgis.Warning,
        )
        self._push_messagebar("warning", tr("plugin_title"), message)
        self._set_status(message)

    def _warn_mountain_lookup_status(self, service):
        status_code = getattr(service, "last_query_error_code", None)
        if not status_code:
            return False
        error_code = self._MOUNTAIN_STATUS_TO_ERROR_CODE.get(status_code)
        if not error_code:
            return False
        self._log_and_notify_warning(
            error_code,
            context=str(getattr(service, "source_label", "OSM/Overpass").strip())
            or "OSM/Overpass",
            detail=getattr(service, "last_query_error", None),
        )
        return True

    @classmethod
    def _log_debug(cls, message, level=Qgis.Info):
        QgsMessageLog.logMessage(str(message), cls._LOG_TAG, level)

    def _report_dir(self):
        project_home = QgsProject.instance().homePath().strip()
        if not project_home:
            project_home = os.path.abspath(os.path.join(self.plugin_dir, ".."))
        report_dir = os.path.join(project_home, "reports")
        os.makedirs(report_dir, exist_ok=True)
        return report_dir

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
    def _normalized_feature_uid_value(value):
        return normalized_feature_uid_value(value)

    @staticmethod
    def _is_derived_uid_excluded_field(name):
        return is_derived_uid_excluded_field(name)

    @classmethod
    def _feature_uid(cls, feature, field_names=None):
        return feature_uid(feature, field_names=field_names)

    def _ensure_feature_uid_field(self, layer):
        if layer is None:
            return 0
        try:
            source_field_names = list(layer.fields().names())
        except (AttributeError, TypeError):
            return 0

        if "feature_uid" not in source_field_names:
            layer.dataProvider().addAttributes(
                [QgsField("feature_uid", QVariant.String, "string", 128)]
            )
            layer.updateFields()

        if "feature_uid" in source_field_names:
            source_field_names = [name for name in source_field_names if name != "feature_uid"]

        updated = 0
        with edit(layer):
            for feature in layer.getFeatures():
                expected_uid = self._feature_uid(feature, field_names=source_field_names)
                if not expected_uid:
                    continue
                try:
                    current_uid = str(feature["feature_uid"] or "").strip()
                except (KeyError, TypeError, ValueError):
                    current_uid = ""
                if current_uid == expected_uid:
                    continue
                feature["feature_uid"] = expected_uid
                layer.updateFeature(feature)
                updated += 1
        return updated

    @classmethod
    def _feature_uid_index(cls, layer, field_names=None):
        return feature_uid_index(layer, field_names=field_names)

    @staticmethod
    def _duplicate_uids_from_index(uid_index):
        return duplicate_uids_from_index(uid_index)

    @classmethod
    def _duplicate_feature_uids(cls, layer, field_names=None):
        return duplicate_feature_uids(layer, field_names=field_names)

    @classmethod
    def _uid_match_summary(cls, layer, feature_uids, field_names=None):
        return uid_match_summary(
            layer,
            feature_uids,
            field_names=field_names,
        )

    @classmethod
    def _feature_ids_for_uids(cls, layer, feature_uids, field_names=None):
        return feature_ids_for_uids(layer, feature_uids, field_names=field_names)

    @classmethod
    def _uid_lookup_summary(cls, layer, feature_uids, field_names=None):
        return uid_lookup_summary(layer, feature_uids, field_names=field_names)

    @staticmethod
    def _normalize_change_uids(change_rows):
        return normalize_change_uids(change_rows)

    @staticmethod
    def _sanitize_top_change_rows(top_changes):
        sanitized = []
        seen = set()
        for row in top_changes or []:
            if not isinstance(row, dict):
                continue
            feature_uid = row.get("feature_uid")
            if not feature_uid:
                continue
            key = str(feature_uid).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            row["feature_uid"] = key
            sanitized.append(row)
        return sanitized

    @staticmethod
    def _to_non_negative_int(value):
        try:
            ivalue = int(value)
        except (TypeError, ValueError):
            return None
        if ivalue < 0:
            return None
        return ivalue

    @classmethod
    def _validate_compare_feature_contract(cls, base_layer, compare_layer, top_changes):
        layer_names = {
            layer.name() if hasattr(layer, "name") else str(layer)
            for layer in (base_layer, compare_layer)
            if layer is not None
        }
        if base_layer is None or compare_layer is None:
            return (
                False,
                "Comparison layers are not available for report contract check.",
            )

        change_uids = cls._normalize_change_uids(top_changes)
        if not top_changes and base_layer.featureCount() > 0 and compare_layer.featureCount() > 0:
            return (
                False,
                f"Comparison has no matched features by UID between {', '.join(sorted(layer_names))}.",
            )
        if top_changes and not change_uids:
            return (
                False,
                "Top change rows do not include feature_uid values required for deterministic feature matching.",
            )

        base_field_names = base_layer.fields().names()
        compare_field_names = compare_layer.fields().names()
        if "feature_uid" not in base_field_names:
            return False, "Base layer is missing feature_uid required for compare matching."
        if "feature_uid" not in compare_field_names:
            return False, "Compare layer is missing feature_uid required for compare matching."
        base_duplicates = cls._duplicate_feature_uids(
            base_layer,
            field_names=base_field_names,
        )
        if base_duplicates:
            sample = ", ".join(base_duplicates[:5])
            return (
                False,
                f"Base layer has duplicated feature_uid values, so compare matching was stopped. Example: {sample}",
            )

        compare_duplicates = cls._duplicate_feature_uids(
            compare_layer,
            field_names=compare_field_names,
        )
        if compare_duplicates:
            sample = ", ".join(compare_duplicates[:5])
            return (
                False,
                f"Compare layer has duplicated feature_uid values, so compare matching was stopped. Example: {sample}",
            )

        _, base_missing, base_ambiguous = cls._uid_lookup_summary(
            base_layer,
            change_uids,
            field_names=base_field_names,
        )
        _, compare_missing, compare_ambiguous = cls._uid_lookup_summary(
            compare_layer,
            change_uids,
            field_names=compare_field_names,
        )
        ambiguous_union = sorted(set(base_ambiguous) | set(compare_ambiguous))
        if ambiguous_union:
            sample = ", ".join(ambiguous_union[:5])
            return (
                False,
                f"Could not resolve {len(ambiguous_union)} change-row identifiers to one feature per layer. Example: {sample}",
            )
        missing_union = sorted(set(base_missing) | set(compare_missing))
        if missing_union:
            sample = ", ".join(missing_union[:5])
            return (
                False,
                f"Could not match {len(missing_union)} change-row identifiers in both layers. Example: {sample}",
            )
        return True, ""

    @classmethod
    def _validate_calibration_feature_contract(cls, scored_layer, report):
        if scored_layer is None:
            return False, "Calibration result layer is not available for report contract check."

        if not isinstance(report, dict):
            return False, "Calibration report payload is invalid for contract check."

        required_field_names = ("feature_uid", "cal_id", "fs_label")
        field_names = set(scored_layer.fields().names())
        missing_fields = [name for name in required_field_names if name not in field_names]
        if missing_fields:
            return (
                False,
                f"Calibration layer is missing required fields: {', '.join(missing_fields)}.",
            )

        report_positive_count = cls._to_non_negative_int(report.get("positive_count"))
        report_negative_count = cls._to_non_negative_int(report.get("negative_count"))
        report_valid_count = cls._to_non_negative_int(report.get("valid_count"))
        if report_positive_count is None:
            return (
                False,
                "Calibration report is missing a valid non-negative positive_count.",
            )
        if report_negative_count is None:
            return (
                False,
                "Calibration report is missing a valid non-negative negative_count.",
            )
        if report_valid_count is None:
            return (
                False,
                "Calibration report is missing a valid non-negative valid_count.",
            )

        layer_positive_count = 0
        layer_negative_count = 0
        cal_id_values = set()
        for feature in scored_layer.getFeatures():
            cal_id = feature["cal_id"]
            cal_id_value = cls._to_non_negative_int(cal_id)
            if cal_id_value is None:
                return (
                    False,
                    f"Calibration layer has invalid cal_id value: {cal_id!r}.",
                )
            if cal_id_value in cal_id_values:
                return (
                    False,
                    f"Calibration layer has duplicated cal_id: {cal_id!r}.",
                )
            cal_id_values.add(cal_id_value)

            fs_label = feature["fs_label"]
            if fs_label not in (0, 1):
                if fs_label in (None, ""):
                    continue
                fs_label = cls._to_non_negative_int(fs_label)
                if fs_label not in (0, 1):
                    return False, f"Calibration layer has invalid fs_label value: {feature['fs_label']!r}."
            if fs_label == 1:
                layer_positive_count += 1
            elif fs_label == 0:
                layer_negative_count += 1

        layer_feature_count = scored_layer.featureCount()
        if report_positive_count + report_negative_count == 0:
            return (
                False,
                "Calibration report has zero-positive/negative counts.",
            )

        if report_positive_count + report_negative_count != layer_positive_count + layer_negative_count:
            return (
                False,
                "Calibration positive/negative sample count does not match scored-layer label count.",
            )

        if layer_positive_count + layer_negative_count != layer_feature_count:
            return (
                False,
                "Calibration scored layer has non-calibration rows or missing labels.",
            )

        if report_valid_count > layer_positive_count + layer_negative_count:
            return (
                False,
                "Calibration report valid_count exceeds number of scored calibration rows.",
            )

        if report.get("calibration_applied") and not report.get("tuned_weights"):
            return False, "Calibration report indicates applied optimization but tuned_weights is empty."

        return True, ""

    @classmethod
    def _pairwise_score_delta(cls, base_layer, compare_layer):
        if base_layer is None or compare_layer is None:
            return None
        base_scores_by_uid = {}
        compare_scores_by_uid = {}

        for feature in base_layer.getFeatures():
            try:
                score = float(feature["fs_score"])
            except (KeyError, TypeError, ValueError):
                continue
            uid = cls._feature_uid(feature, field_names=feature.fields().names())
            if not uid:
                continue
            base_scores_by_uid[uid] = score
        for feature in compare_layer.getFeatures():
            try:
                score = float(feature["fs_score"])
            except (KeyError, TypeError, ValueError):
                continue
            uid = cls._feature_uid(feature, field_names=feature.fields().names())
            if not uid:
                continue
            compare_scores_by_uid[uid] = score

        shared_uids = sorted(set(base_scores_by_uid.keys()) & set(compare_scores_by_uid.keys()))
        if not shared_uids:
            return None
        deltas = [
            compare_scores_by_uid[uid] - base_scores_by_uid[uid]
            for uid in shared_uids
        ]
        return {
            "count": len(deltas),
            "mean_delta": sum(deltas) / len(deltas),
            "max_gain": max(deltas),
            "max_drop": min(deltas),
        }

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
        return f"uid:{FengShuiGisPlugin._feature_uid(feature, feature.fields().names())}"

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
        if base_layer is None or compare_layer is None:
            return []
        if limit is None:
            limit = self._COMPARE_TOP_CHANGE_LIMIT
        base_by_uid = {}
        compare_by_uid = {}
        for feature in base_layer.getFeatures():
            try:
                score = float(feature["fs_score"])
            except (KeyError, TypeError, ValueError):
                continue
            uid = self._feature_uid(feature, feature.fields().names())
            if not uid:
                continue
            base_by_uid[uid] = {
                "label": self._feature_display_name(feature),
                "score": score,
                "reason": self._feature_reason_text(feature),
            }
        for feature in compare_layer.getFeatures():
            try:
                score = float(feature["fs_score"])
            except (KeyError, TypeError, ValueError):
                continue
            uid = self._feature_uid(feature, feature.fields().names())
            if not uid:
                continue
            compare_by_uid[uid] = {
                "label": self._feature_display_name(feature),
                "score": score,
                "reason": self._feature_reason_text(feature),
            }
        shared_uids = sorted(set(base_by_uid.keys()) & set(compare_by_uid.keys()))
        rows = []
        for feature_uid in shared_uids:
            base_entry = base_by_uid[feature_uid]
            compare_entry = compare_by_uid[feature_uid]
            delta = compare_entry["score"] - base_entry["score"]
            rows.append(
                {
                    "feature_uid": feature_uid,
                    "label": compare_entry.get("label")
                    or base_entry.get("label")
                    or f"uid:{feature_uid}",
                    "base_score": base_entry["score"],
                    "compare_score": compare_entry["score"],
                    "delta": delta,
                    "base_reason": base_entry.get("reason", ""),
                    "compare_reason": compare_entry.get("reason", ""),
                }
            )
        rows.sort(
            key=lambda item: (abs(float(item.get("delta", 0.0))), float(item.get("delta", 0.0))),
            reverse=True,
        )
        return rows[: max(1, int(limit))]

    @staticmethod
    def _feature_ids_from_change_rows(change_rows):
        return FengShuiGisPlugin._normalize_change_uids(change_rows)

    def _select_top_changed_features(self, base_layer, compare_layer, change_rows):
        feature_uids = self._feature_ids_from_change_rows(change_rows)
        if not feature_uids:
            return 0
        return select_changed_features(
            base_layer=base_layer,
            compare_layer=compare_layer,
            feature_uids=feature_uids,
            uid_match_summary=self._uid_match_summary,
            log_debug=self._log_debug,
            set_active_layer=self.iface.setActiveLayer,
        )

    def _zoom_to_selected_features(self, layer):
        return zoom_to_selected_features(
            layer=layer,
            zoom_callback=self.iface.mapCanvas().zoomToSelected,
            log_debug=self._log_debug,
        )

    def _export_top_changed_features_layer(
        self,
        compare_layer,
        top_changes,
        compare_profile_key,
        label_lang,
    ):
        return export_top_changed_features_layer(
            compare_layer=compare_layer,
            top_changes=top_changes,
            compare_profile_key=compare_profile_key,
            label_lang=label_lang,
            output_layer_name=self._output_layer_name(
                compare_layer.name(),
                "compare_changes",
                label_lang,
            ),
            compare_delta_epsilon=self._COMPARE_DELTA_EPSILON,
            reason_excerpt_limit=self._COMPARE_REASON_EXCERPT,
        )

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
        _payload, json_path, md_path = write_compare_report(
            report_dir=self._report_dir(),
            label_language=self._label_language(),
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
        return json_path, md_path

    def _style_compare_change_layer(self, layer, label_lang):
        style_compare_change_layer(layer, self._COMPARE_TREND_STYLES, label_lang)

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
        html = build_compare_popup_html(
            label_language=text_lang,
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

    def _warn_if_geographic(self, layer):
        if layer and layer.crs().isGeographic():
            self._push_messagebar(
                "warning",
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

    @staticmethod
    def _layer_center_wgs84(layer):
        """Centre of a layer's extent as (lon, lat), or None if unobtainable."""
        if layer is None:
            return None
        crs = layer.crs()
        if crs is None or not crs.isValid():
            return None
        extent = layer.extent()
        if extent is None or extent.isEmpty():
            return None
        center = extent.center()
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        if crs == wgs84:
            return center.x(), center.y()
        try:
            transform = QgsCoordinateTransform(crs, wgs84, QgsProject.instance())
            projected = transform.transform(center)
        except Exception:  # noqa: BLE001 - a failed transform is not fatal here
            return None
        return projected.x(), projected.y()

    def _dem_cell_size_meters(self, layer):
        """DEM cell size in metres, or None when it cannot be established."""
        if layer is None:
            return None
        crs = layer.crs()
        if crs is None or not crs.isValid() or crs.isGeographic():
            return None
        try:
            return abs(float(layer.rasterUnitsPerPixelX()))
        except Exception:  # noqa: BLE001
            return None

    def _chinese_datum_advisory(self, dem_layer):
        center = self._layer_center_wgs84(dem_layer)
        if center is None:
            return None
        return datum_advisory(
            center_lon=center[0],
            center_lat=center[1],
            dem_cell_size_m=self._dem_cell_size_meters(dem_layer),
        )

    def _warn_if_chinese_datum_hazard(self, dem_layer):
        """Flag the GCJ-02 / BD-09 trap for analyses inside China.

        The datum cannot be read off the data - a layer digitised from a
        Chinese basemap declares EPSG:4326 exactly like a WGS84 one - so this
        reports how far a mix-up would move the analysis and leaves the call
        to the user.
        """
        advisory = self._chinese_datum_advisory(dem_layer)
        if advisory is None:
            return

        text_lang = self._label_language()
        message = ui_text(
            "warn_chinese_datum_template",
            text_lang,
            default=(
                "Analysis extent is inside China. If any input was digitised from "
                "a Chinese basemap (Amap/Baidu/Tencent), it is in GCJ-02 or BD-09, "
                "not WGS84, and would be offset by about {gcj:.0f} m (BD-09 "
                "{bd:.0f} m). Verify the source datum before reading the result."
            ),
        ).format(
            gcj=advisory["gcj02_offset_m"],
            bd=advisory["bd09_offset_m"],
        )
        cells = advisory.get("cells_shifted")
        if cells:
            message += " " + ui_text(
                "warn_chinese_datum_cells",
                text_lang,
                default="That is about {cells:.0f} DEM cells.",
            ).format(cells=cells)
        severity = "warning" if advisory["severity"] != "info" else "info"
        self._push_messagebar(severity, tr("plugin_title"), message)

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
        # A generic "use a projected CRS" is not actionable in China, where the
        # right answer is a specific Gauss-Kruger belt.
        center = self._layer_center_wgs84(layer)
        if center is not None:
            suggestion = recommended_projected_crs(center[0], center[1])
            if suggestion:
                message += " " + ui_text(
                    "projected_crs_suggestion",
                    text_lang,
                    default="Suggested for this extent: {label} ({authid}).",
                ).format(
                    label=suggestion["label"],
                    authid=suggestion.get("authid") or suggestion.get("proj4", ""),
                )
        self._push_messagebar("critical", tr("plugin_title"), message)
        self._set_status(message)
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
        self._push_messagebar("warning", tr("plugin_title"), message)

    def _label_language(self):
        if self.dock and hasattr(self.dock, "label_language"):
            return normalize_label_language(self.dock.label_language())
        return "ko"

    def _mountain_name_options(self):
        options = mountain_options()
        if not self.dock:
            return resolve_mountain_name_options(options, enabled=False)
        enabled = (
            bool(self.dock.mountain_name_enrichment_enabled())
            if hasattr(self.dock, "mountain_name_enrichment_enabled")
            else None
        )
        radius_m = None
        max_features = None
        preferred_language = None
        if hasattr(self.dock, "mountain_name_radius_m"):
            try:
                radius_m = int(self.dock.mountain_name_radius_m())
            except (TypeError, ValueError):
                radius_m = None
        if hasattr(self.dock, "mountain_name_max_features"):
            try:
                max_features = int(self.dock.mountain_name_max_features())
            except (TypeError, ValueError):
                max_features = None
        if hasattr(self.dock, "mountain_name_language_preference"):
            preferred_language = str(self.dock.mountain_name_language_preference())
        return resolve_mountain_name_options(
            options,
            enabled=enabled,
            radius_m=radius_m,
            max_features=max_features,
            preferred_language=preferred_language,
        )

    @staticmethod
    def _mountain_options_payload(
        mountain_enabled,
        mountain_radius_m,
        mountain_max_features,
        mountain_lang,
    ):
        return {
            "enabled": mountain_enabled,
            "radius_m": mountain_radius_m,
            "max_features": mountain_max_features,
            "preferred_language": mountain_lang,
        }

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
        return feature_anchor_point(feature)

    @staticmethod
    def _feature_priority(feature, field_names):
        return feature_priority(feature, field_names)

    def _enrich_layers_with_mountain_names(
        self,
        layers,
        radius_m=None,
        max_features=None,
        preferred_language=None,
    ):
        return enrich_layers_with_mountain_names(
            layers,
            radius_m=radius_m,
            max_features=max_features,
            preferred_language=preferred_language,
            project=QgsProject.instance(),
            warn_lookup_status=self._warn_mountain_lookup_status,
        )

    def _enrich_layer_with_mountain_names(
        self,
        layer,
        radius_m=None,
        max_features=None,
        preferred_language=None,
        service=None,
        candidates=None,
    ):
        return enrich_layer_with_mountain_names(
            layer,
            radius_m=radius_m,
            max_features=max_features,
            preferred_language=preferred_language,
            service=service,
            candidates=candidates,
            project=QgsProject.instance(),
        )

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

    def _term_cluster_reason(self, layer, feature, text_lang):
        return build_term_cluster_reason(layer, feature, text_lang)

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
        self._push_messagebar("warning", tr("plugin_title"), warning)
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

        # ui_text falls back to English for keys without a translation, which
        # is a better default for a Chinese label run than silently using Korean.
        text_lang = normalize_label_language(label_lang)
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
        maptip_ridge_score = ui_text("maptip_ridge_score_label", text_lang, default="ridge_score")
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
        compare_change_feature_alias = ui_text(
            "compare_change_feature_alias",
            text_lang,
            default="Feature",
        )
        compare_change_base_alias = ui_text(
            "compare_change_base_alias",
            text_lang,
            default="Base",
        )
        compare_change_calibrated_alias = ui_text(
            "compare_change_calibrated_alias",
            text_lang,
            default="Calibrated",
        )
        compare_change_delta_alias = ui_text(
            "compare_change_delta_alias",
            text_lang,
            default="Delta",
        )
        compare_change_trend_alias = ui_text(
            "compare_change_trend_alias",
            text_lang,
            default="Trend",
        )
        compare_change_reason_b_alias = ui_text(
            "compare_change_reason_b_alias",
            text_lang,
            default="Base reason",
        )
        compare_change_reason_c_alias = ui_text(
            "compare_change_reason_c_alias",
            text_lang,
            default="Calibrated reason",
        )
        compare_change_model_alias = ui_text(
            "compare_change_model_alias",
            text_lang,
            default="Model",
        )
        maptip_confidence = ui_text("maptip_confidence_label", text_lang, default="confidence")
        maptip_components = ui_text("maptip_components_label", text_lang, default="Component fits")
        maptip_terrain = ui_text("maptip_terrain_label", text_lang, default="Terrain metrics")
        maptip_dem_water = ui_text("maptip_dem_water_label", text_lang, default="dem_water")
        maptip_distance_water = ui_text(
            "maptip_distance_water_label",
            text_lang,
            default="distance_to_water(m)",
        )
        maptip_base_fs_score = ui_text(
            "maptip_base_fs_score_label",
            text_lang,
            default="base_fs_score",
        )
        maptip_best_f1_th = ui_text(
            "maptip_best_f1_th_label",
            text_lang,
            default="best_f1_th",
        )
        maptip_best_youden_th = ui_text(
            "maptip_best_youden_th_label",
            text_lang,
            default="best_youden_th",
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
        fs_conf_band_expr = self._score_band_expr("fs_conf")
        mountain_tip = mountain_tip_html(
            field_names,
            maptip_mountain=maptip_mountain,
            maptip_mountain_dist=maptip_mountain_dist,
            maptip_mountain_lang=maptip_mountain_lang,
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

        config = None
        if "src_id" in field_names and "dst_id" in field_names:
            config = link_layer_info_config(
                field_names,
                label_lang=label_lang,
                link_arrow=link_arrow,
                reason_label=reason_label,
                reason_empty_lit=reason_empty_lit,
                mountain_tip=mountain_tip,
                link_alias_score=link_alias_score,
                link_alias_len_m=link_alias_len_m,
                link_alias_azimuth=link_alias_azimuth,
                link_alias_rank=link_alias_rank,
                maptip_score=maptip_score,
                maptip_len_m=maptip_len_m,
                maptip_azimuth=maptip_azimuth,
                maptip_link_note=maptip_link_note,
                score_band_expr=score_band_expr,
            )
        elif "term_ko" in field_names:
            config = term_layer_info_config(
                field_names,
                label_lang=label_lang,
                reason_label=reason_label,
                reason_empty_lit=reason_empty_lit,
                mountain_tip=mountain_tip,
                term_alias_score=term_alias_score,
                term_alias_fit=term_alias_fit,
                term_alias_delta=term_alias_delta,
                term_alias_target=term_alias_target,
                term_alias_radius=term_alias_radius,
                term_alias_relief=term_alias_relief,
                term_alias_rank=term_alias_rank,
                maptip_score=maptip_score,
                maptip_rank=maptip_rank,
                maptip_fit=maptip_fit,
                maptip_delta=maptip_delta,
                maptip_target=maptip_target,
                maptip_radius_m=maptip_radius_m,
                maptip_term_note=maptip_term_note,
                score_band_expr=score_band_expr,
            )
        elif "ridge_class" in field_names:
            config = ridge_layer_info_config(
                field_names,
                label_lang=label_lang,
                reason_label=reason_label,
                reason_empty_lit=reason_empty_lit,
                mountain_tip=mountain_tip,
                ridge_alias_strength=ridge_alias_strength,
                ridge_alias_score=ridge_alias_score,
                ridge_alias_len=ridge_alias_len,
                maptip_strength=maptip_strength,
                maptip_ridge_score=maptip_ridge_score,
                maptip_len=maptip_len,
                maptip_ridge_note=maptip_ridge_note,
            )
        elif "stream_class" in field_names:
            config = stream_layer_info_config(
                field_names,
                reason_label=reason_label,
                reason_empty_lit=reason_empty_lit,
                mountain_tip=mountain_tip,
                hydro_alias_order=hydro_alias_order,
                hydro_alias_flow_acc=hydro_alias_flow_acc,
                hydro_alias_len=hydro_alias_len,
                maptip_order=maptip_order,
                maptip_flow_acc=maptip_flow_acc,
                maptip_len=maptip_len,
                maptip_hydro_note=maptip_hydro_note,
            )
        elif {
            "cmp_label",
            "cmp_base",
            "cmp_score",
            "cmp_delta",
            "cmp_trend",
            "cmp_reason_b",
            "cmp_reason_c",
            "cmp_model",
        } <= field_names:
            compare_change_gain_label = ui_text("compare_trend_gain", text_lang, default="Gain")
            compare_change_drop_label = ui_text(
                "compare_trend_drop",
                text_lang,
                default="Drop",
            )
            compare_change_neutral_label = ui_text(
                "compare_trend_neutral",
                text_lang,
                default="Near neutral",
            )
            config = compare_layer_info_config(
                field_names,
                reason_empty_lit=reason_empty_lit,
                mountain_tip=mountain_tip,
                compare_change_feature_alias=compare_change_feature_alias,
                compare_change_base_alias=compare_change_base_alias,
                compare_change_calibrated_alias=compare_change_calibrated_alias,
                compare_change_delta_alias=compare_change_delta_alias,
                compare_change_trend_alias=compare_change_trend_alias,
                compare_change_reason_b_alias=compare_change_reason_b_alias,
                compare_change_reason_c_alias=compare_change_reason_c_alias,
                compare_change_model_alias=compare_change_model_alias,
                compare_change_gain_label=compare_change_gain_label,
                compare_change_drop_label=compare_change_drop_label,
                compare_change_neutral_label=compare_change_neutral_label,
            )
        elif "fs_reason" in field_names:
            score_field = "cal_score" if "cal_score" in field_names else "fs_score"
            site_score_band_expr = self._score_band_expr(score_field)
            cal_score_title = ui_text(
                "cal_score_title",
                text_lang,
                default="Calibrated Score",
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
            config = site_layer_info_config(
                field_names,
                reason_label=reason_label,
                reason_empty_lit=reason_empty_lit,
                mountain_tip=mountain_tip,
                fs_score_title=fs_score_title,
                cal_score_title=cal_score_title,
                site_alias_score=site_alias_score,
                site_alias_conf=site_alias_conf,
                site_alias_slope=site_alias_slope,
                site_alias_aspect=site_alias_aspect,
                site_alias_form=site_alias_form,
                site_alias_long=site_alias_long,
                site_alias_water=site_alias_water,
                site_alias_dem_water=site_alias_dem_water,
                site_alias_tpi=site_alias_tpi,
                site_alias_conv=site_alias_conv,
                cal_score_alias=cal_score_alias,
                cal_f1_alias=cal_f1_alias,
                cal_youden_alias=cal_youden_alias,
                maptip_score=maptip_score,
                maptip_confidence=maptip_confidence,
                maptip_components=maptip_components,
                maptip_terrain=maptip_terrain,
                maptip_dem_water=maptip_dem_water,
                maptip_distance_water=maptip_distance_water,
                maptip_site_note=maptip_site_note,
                maptip_base_fs_score=maptip_base_fs_score,
                maptip_best_f1_th=maptip_best_f1_th,
                maptip_best_youden_th=maptip_best_youden_th,
                site_score_band_expr=site_score_band_expr,
                fs_conf_band_expr=fs_conf_band_expr,
            )
        if config:
            self._set_field_aliases(layer, config["aliases"])
            layer.setDisplayExpression(config["display_expression"])
            layer.setMapTipTemplate(config["map_tip_template"])
            reason_field = config.get("reason_field")
            if reason_field:
                self._bind_reason_on_selection(layer, reason_field)

    def _bind_reason_on_selection(self, layer, reason_field):
        if layer is None or layer.id() in self._selection_hooks:
            return

        text_lang = self._label_language()
        reason_empty = ui_text("reason_empty", text_lang, default="No description")
        reason_title = ui_text("reason_alias", text_lang, default="Reason")
        reason_overview_title = ui_text(
            "reason_overview_title",
            text_lang,
            default="Top reasons",
        )
        reason_detail_title = ui_text(
            "reason_detail_title",
            text_lang,
            default="Detailed explanation",
        )
        reason_limitations_title = ui_text(
            "reason_limitations_title",
            text_lang,
            default="What this result cannot say",
        )
        reason_cluster_title = ui_text(
            "reason_cluster_title",
            text_lang,
            default="Cluster context",
        )
        mountain_prefix = ui_text("mountain_prefix_label", text_lang, default="Nearby mountain")
        mountain_lang_label = ui_text("mountain_lang_inline_label", text_lang, default="lang")

        def _on_selection(selected, _deselected, _clear):
            if not selected:
                return
            request = QgsFeatureRequest().setFilterFids([selected[0]])
            feature = next(layer.getFeatures(request), None)
            if feature is None:
                return

            message = build_feature_reason_message(
                feature,
                reason_field,
                reason_empty=reason_empty,
                mountain_prefix=mountain_prefix,
                mountain_lang_label=mountain_lang_label,
            )
            cluster_reason = self._term_cluster_reason(layer, feature, text_lang)
            overview_items = build_feature_reason_overview(feature, text_lang)
            limitations_items = build_feature_reason_limitations(feature, text_lang)
            popup_message = message
            if len(popup_message) > 1800:
                popup_message = f"{popup_message[:1797]}..."
            title = f"{layer.name()} {reason_title}"
            self._show_reason_popup(
                title,
                overview_items=overview_items,
                detail_message=popup_message,
                cluster_reason=cluster_reason,
                limitations_items=limitations_items,
                overview_title=reason_overview_title,
                detail_title=reason_detail_title,
                cluster_title=reason_cluster_title,
                limitations_title=reason_limitations_title,
            )
            brief = " | ".join(overview_items[:2]) if overview_items else message
        if len(brief) > 240:
            brief = f"{brief[:237]}..."
        self._push_messagebar("info", title, brief)

        layer.selectionChanged.connect(_on_selection)
        self._selection_hooks[layer.id()] = _on_selection

    def _show_reason_popup(
        self,
        title,
        *,
        overview_items,
        detail_message,
        cluster_reason,
        limitations_items,
        overview_title,
        detail_title,
        cluster_title,
        limitations_title,
    ):
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
        self._reason_browser.setHtml(
            build_reason_popup_html(
                title,
                overview_title=overview_title,
                overview_items=overview_items,
                detail_title=detail_title,
                message=detail_message,
                cluster_title=cluster_title,
                cluster_reason=cluster_reason,
                limitations_title=limitations_title,
                limitations_items=limitations_items,
            )
        )
        self._reason_dialog.show()
        self._reason_dialog.raise_()
        self._reason_dialog.activateWindow()

    def _write_calibration_report(self, report):
        report_dir = self._report_dir()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report.update(self._export_calibrated_profile(report, stamp, report_dir))
        paths = write_calibration_report_files(
            report=report,
            report_dir=report_dir,
            stamp=stamp,
            text_lang=self._label_language(),
        )
        return paths["json_path"], paths["md_path"]

    def _export_calibrated_profile(self, report, stamp, report_dir):
        return export_calibrated_profile(
            report,
            stamp=stamp,
            report_dir=report_dir,
            plugin_dir=self.plugin_dir,
        )

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
        sections = build_calibration_popup_sections(
            report=report,
            report_dir=os.path.dirname(json_path),
            text_lang=text_lang,
        )
        html = build_calibration_popup_html(
            report=report,
            json_path=json_path,
            md_path=md_path,
            text_lang=text_lang,
            metric_compare_html=sections["metric_compare_html"],
            metadata_html=sections["metadata_html"],
            history_html=sections["history_html"],
        )
        self._report_browser.setHtml(html)
        self._report_dialog.show()
        self._report_dialog.raise_()
        self._report_dialog.activateWindow()

    def _run_background_task(self, task_key, task_label, worker, on_payload):
        existing = self._background_tasks.get(task_key)
        if existing is not None and existing.isActive():
            busy_text = (
                "Another operation is already running. "
                "Wait until it finishes, then retry."
                if self._label_language() == "en"
                else "다른 작업이 진행 중입니다. 완료 후 다시 실행해 주세요."
            )
            self._push_messagebar("warning", tr("plugin_title"), busy_text)
            self._set_status(busy_text)
            return False

        if self.dock and hasattr(self.dock, "workflow_progress"):
            try:
                self.dock.workflow_progress.setValue(0)
            except (TypeError, AttributeError, RuntimeError):
                pass

        def _handle_payload(payload):
            self._background_tasks.pop(task_key, None)
            if self.dock and hasattr(self.dock, "workflow_progress"):
                try:
                    if payload.get("ok"):
                        self.dock.workflow_progress.setValue(100)
                    else:
                        self.dock.workflow_progress.setValue(0)
                except (TypeError, AttributeError, RuntimeError):
                    pass
            on_payload(payload)

        task = _PluginRunTask(task_label, worker, _handle_payload)
        self._background_tasks[task_key] = task
        QgsApplication.taskManager().addTask(task)
        return True

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
            self._push_messagebar("warning", tr("plugin_title"), tr("warn_missing_layers"))
            self._set_status(tr("warn_missing_layers"))
            return

        self._set_status(tr("status_running"))
        label_lang = self._label_language()
        mountain_enabled, mountain_radius_m, mountain_max_features, mountain_lang = (
            self._mountain_name_options()
        )
        self._warn_low_evidence_context(culture_key, period_key, hemisphere)
        if not self._require_projected_dem_crs(dem_layer):
            return
        self._warn_if_crs_mismatch(dem_layer, site_layer, water_layer)
        self._warn_if_chinese_datum_hazard(dem_layer)

        def _worker(task):
            return self._run_analysis_worker(
                task=task,
                site_layer=site_layer,
                dem_layer=dem_layer,
                water_layer=water_layer,
                hemisphere=hemisphere,
                profile_key=profile_key,
                culture_key=culture_key,
                period_key=period_key,
                auto_hydro=auto_hydro,
                label_lang=label_lang,
                mountain_enabled=mountain_enabled,
                mountain_radius_m=mountain_radius_m,
                mountain_max_features=mountain_max_features,
                mountain_lang=mountain_lang,
            )

        def _done(payload):
            if not payload.get("ok"):
                if payload.get("error_code") == "E_TASK_CANCELLED":
                    self._set_status(
                        "analysis"
                        if self._label_language() == "en"
                        else "분석이 취소되었습니다."
                    )
                    return
                self._log_and_notify_error(
                    payload.get("error_code") or "E_ANALYSIS_UNEXPECTED",
                    payload.get("error_context", "Analysis failed"),
                    payload.get("error"),
                )
                return

            output_layer_name = payload.get("output_layer_name", "")
            mountain_updated = int(payload.get("mountain_updated") or 0)
            self._push_messagebar("success", tr("plugin_title"), f"{tr('ok_finished')}: {output_layer_name}")
            if mountain_updated > 0:
                self._push_messagebar(
                    "info",
                    tr("plugin_title"),
                    self._mountain_attached_message(mountain_updated),
                )
            self._set_status(tr("status_done"))

        self._run_background_task("analysis", "analysis", _worker, _done)

    def _run_analysis_worker(
        self,
        task,
        site_layer,
        dem_layer,
        water_layer,
        hemisphere,
        profile_key,
        culture_key,
        period_key,
        auto_hydro,
        label_lang,
        mountain_enabled,
        mountain_radius_m,
        mountain_max_features,
        mountain_lang,
    ):
        request = AnalysisRequest(
            site_layer=site_layer,
            dem_layer=dem_layer,
            water_layer=water_layer,
            hemisphere=hemisphere,
            profile_key=profile_key,
            culture_key=culture_key,
            period_key=period_key,
            auto_hydro=auto_hydro,
            label_language=label_lang,
            mountain_options=self._mountain_options_payload(
                mountain_enabled,
                mountain_radius_m,
                mountain_max_features,
                mountain_lang,
            ),
        )
        return run_analysis_service(
            task=task,
            plugin=self,
            request=request,
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
            self._push_messagebar("warning", tr("plugin_title"), tr("warn_dem_required"))
            self._set_status(tr("warn_dem_required"))
            return

        self._set_status(tr("status_terms_running"))
        label_lang = self._label_language()
        mountain_enabled, mountain_radius_m, mountain_max_features, mountain_lang = (
            self._mountain_name_options()
        )
        self._warn_low_evidence_context(culture_key, period_key, hemisphere)
        if not self._require_projected_dem_crs(dem_layer):
            return
        self._warn_if_crs_mismatch(dem_layer, water_layer)
        self._warn_if_chinese_datum_hazard(dem_layer)

        def _worker(task):
            return self._run_term_extraction_worker(
                task=task,
                dem_layer=dem_layer,
                water_layer=water_layer,
                hemisphere=hemisphere,
                profile_key=profile_key,
                culture_key=culture_key,
                period_key=period_key,
                auto_hydro=auto_hydro,
                include_terms=include_terms,
                label_lang=label_lang,
                mountain_enabled=mountain_enabled,
                mountain_radius_m=mountain_radius_m,
                mountain_max_features=mountain_max_features,
                mountain_lang=mountain_lang,
            )

        def _done(payload):
            if not payload.get("ok"):
                if payload.get("error_code") == "E_TASK_CANCELLED":
                    self._set_status(
                        "done"
                        if self._label_language() == "en"
                        else "취소되었습니다."
                    )
                    return
                self._log_and_notify_error(
                    payload.get("error_code") or "E_LANDSCAPE_UNEXPECTED",
                    payload.get("error_context", "Landscape extraction failed"),
                    payload.get("error"),
                )
                return
            created = payload.get("created_layers", [])
            mountain_updated = int(payload.get("mountain_updated") or 0)
            message_key = "ok_terms_finished" if include_terms else "ok_landscape_finished"
            self._push_messagebar(
                "success",
                tr("plugin_title"),
                f"{tr(message_key)}: " + ", ".join(created),
            )
            if mountain_updated > 0:
                self._push_messagebar(
                    "info",
                    tr("plugin_title"),
                    self._mountain_attached_message(mountain_updated),
                )
            self._set_status(tr("status_done"))

        self._run_background_task("term_extraction", "term_extraction", _worker, _done)

    def _run_term_extraction_worker(
        self,
        task,
        dem_layer,
        water_layer,
        hemisphere,
        profile_key,
        culture_key,
        period_key,
        auto_hydro,
        include_terms,
        label_lang,
        mountain_enabled,
        mountain_radius_m,
        mountain_max_features,
        mountain_lang,
    ):
        request = TermExtractionRequest(
            dem_layer=dem_layer,
            water_layer=water_layer,
            hemisphere=hemisphere,
            profile_key=profile_key,
            culture_key=culture_key,
            period_key=period_key,
            auto_hydro=auto_hydro,
            include_terms=include_terms,
            label_language=label_lang,
            mountain_options=self._mountain_options_payload(
                mountain_enabled,
                mountain_radius_m,
                mountain_max_features,
                mountain_lang,
            ),
        )
        return run_term_extraction_service(task=task, plugin=self, request=request)

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
            self._push_messagebar("warning", tr("plugin_title"), tr("warn_missing_layers"))
            self._set_status(tr("warn_missing_layers"))
            return

        self._set_status(
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
        self._warn_if_chinese_datum_hazard(dem_layer)

        def _worker(task):
            return self._run_profile_compare_worker(
                task=task,
                site_layer=site_layer,
                dem_layer=dem_layer,
                water_layer=water_layer,
                hemisphere=hemisphere,
                base_profile_key=base_profile_key,
                compare_profile_key=compare_profile_key,
                culture_key=culture_key,
                period_key=period_key,
                auto_hydro=auto_hydro,
                label_lang=label_lang,
                mountain_enabled=mountain_enabled,
                mountain_radius_m=mountain_radius_m,
                mountain_max_features=mountain_max_features,
                mountain_lang=mountain_lang,
            )

        def _done(payload):
            if not payload.get("ok"):
                if payload.get("error_code") == "E_TASK_CANCELLED":
                    self._set_status(
                        "compare canceled"
                        if self._label_language() == "en"
                        else "비교가 취소되었습니다."
                    )
                    return
                self._log_and_notify_error(
                    payload.get("error_code") or "E_COMPARE_UNEXPECTED",
                    payload.get("error_context", "Profile comparison failed"),
                    payload.get("error"),
                )
                return
            self._show_profile_compare_popup(
                base_profile_key=base_profile_key,
                compare_profile_key=compare_profile_key,
                base_stats=payload.get("base_stats", {}),
                compare_stats=payload.get("compare_stats", {}),
                delta_stats=payload.get("delta_stats", {}),
                top_changes=payload.get("top_changes", []),
                selected_change_count=payload.get("selected_change_count", 0),
                zoom_applied=payload.get("zoom_applied", False),
                change_layer_name=payload.get("change_layer_name", ""),
                json_path=payload.get("json_path"),
                md_path=payload.get("md_path"),
                base_layer_name=payload.get("base_layer_name", ""),
                compare_layer_name=payload.get("compare_layer_name", ""),
            )
            success_message = ui_text(
                "profile_compare_status_done",
                label_lang,
                default="Created base/calibrated comparison layers.",
            )
            self._set_status(success_message)
            self._push_messagebar("success", tr("plugin_title"), success_message)

        self._run_background_task("profile_compare", "profile_compare", _worker, _done)

    def _run_profile_compare_worker(
        self,
        task,
        site_layer,
        dem_layer,
        water_layer,
        hemisphere,
        base_profile_key,
        compare_profile_key,
        culture_key,
        period_key,
        auto_hydro,
        label_lang,
        mountain_enabled,
        mountain_radius_m,
        mountain_max_features,
        mountain_lang,
    ):
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
            label_language=label_lang,
        )
        mountain_options = self._mountain_options_payload(
            mountain_enabled,
            mountain_radius_m,
            mountain_max_features,
            mountain_lang,
        )
        return run_profile_compare_service(
            task=task,
            plugin=self,
            request=request,
            mountain_options=mountain_options,
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
            self._push_messagebar("warning", tr("plugin_title"), tr("warn_missing_layers"))
            self._set_status(tr("warn_missing_layers"))
            return

        self._set_status(ui_text("calibration_status_running", default="Calibration in progress..."))
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
        self._warn_if_chinese_datum_hazard(dem_layer)

        def _worker(task):
            return self._run_calibration_worker(
                task=task,
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
                label_lang=label_lang,
                mountain_enabled=mountain_enabled,
                mountain_radius_m=mountain_radius_m,
                mountain_max_features=mountain_max_features,
                mountain_lang=mountain_lang,
            )

        def _done(payload):
            if not payload.get("ok"):
                if payload.get("error_code") == "E_TASK_CANCELLED":
                    self._set_status(
                        "calibration canceled"
                        if self._label_language() == "en"
                        else "보정이 취소되었습니다."
                    )
                    return
                self._log_and_notify_error(
                    payload.get("error_code") or "E_CALIBRATION_UNEXPECTED",
                    payload.get("error_context", "Calibration failed"),
                    payload.get("error"),
                )
                return
            report = payload.get("report", {})
            self._push_messagebar(
                "success",
                tr("plugin_title"),
                ui_text(
                    "calibration_success_template",
                    default="Calibration done: ROC_AUC={roc_auc:.4f}, PR_AUC={pr_auc:.4f}",
                ).format(roc_auc=report.get("roc_auc", 0), pr_auc=report.get("pr_auc", 0)),
            )
            mountain_updated = int(payload.get("mountain_updated") or 0)
            if mountain_updated > 0:
                self._push_messagebar(
                    "info",
                    tr("plugin_title"),
                    self._mountain_attached_message(mountain_updated),
                )
            self._set_status(ui_text("calibration_status_done", default="Calibration completed."))
            self._show_report_popup(report, payload.get("json_path"), payload.get("md_path"))

        self._run_background_task("calibration", "calibration", _worker, _done)

    def _run_calibration_worker(
        self,
        task,
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
        label_lang,
        mountain_enabled,
        mountain_radius_m,
        mountain_max_features,
        mountain_lang,
    ):
        request = CalibrationRequest(
            site_layer=site_layer,
            dem_layer=dem_layer,
            water_layer=water_layer,
            hemisphere=hemisphere,
            profile_key=profile_key,
            culture_key=culture_key,
            period_key=period_key,
            negative_ratio=negative_ratio,
            random_seed=random_seed,
            auto_hydro=auto_hydro,
            label_language=label_lang,
            mountain_options={
                "enabled": mountain_enabled,
                "radius_m": mountain_radius_m,
                "max_features": mountain_max_features,
                "preferred_language": mountain_lang,
            },
        )
        return run_calibration_service(
            task=task,
            plugin=self,
            request=request,
        )

