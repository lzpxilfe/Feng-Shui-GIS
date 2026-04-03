# -*- coding: utf-8 -*-
"""Application service layer for plugin workflows.

This module owns orchestration-heavy QGIS work and returns payload dicts consumed
by plugin UI adapters.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
)

from .analysis import FengShuiAnalyzer
from .compare_service_helpers import prepare_compare_results
from .service_contracts import (
    AnalysisRequest,
    CalibrationRequest,
    CompareRequest,
    RunManifest,
    TermExtractionRequest,
)


class _ServiceTaskFeedback(QgsProcessingFeedback):
    """Adapter to forward task progress to QGIS processing feedback."""

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


def _layer_identity(layer: Optional[Any]) -> Dict[str, Any]:
    if layer is None:
        return {}
    identity = {
        "name": getattr(layer, "name", lambda: None)(),
    }
    try:
        identity["id"] = layer.id()
    except Exception:
        pass
    try:
        identity["source"] = str(layer.source())
    except Exception:
        pass
    try:
        identity["crs"] = str(layer.crs().authid())
    except Exception:
        pass
    return identity


def _build_manifest(
    service_name: str,
    request_payload: Optional[Dict[str, Any]],
    seed: Optional[int],
    source_layers: Optional[Dict[str, Any]],
) -> RunManifest:
    try:
        qgis_version = QgsApplication.version()
    except Exception:
        qgis_version = None
    return RunManifest.for_service(
        service_name=service_name,
        config_payload=request_payload,
        seed=seed,
        qgis_version=qgis_version,
        source_layers=source_layers,
    )


def run_analysis_service(*, task, plugin, request: AnalysisRequest) -> Dict[str, Any]:
    if task.isCanceled():
        return {
            "ok": False,
            "error_code": "E_TASK_CANCELLED",
            "error_context": "analysis canceled",
        }

    mountain_options = request.mountain_options or {}
    manifest_payload = {
        "site_layer": _layer_identity(request.site_layer),
        "dem_layer": _layer_identity(request.dem_layer),
        "water_layer": _layer_identity(request.water_layer),
        "hemisphere": request.hemisphere,
        "profile_key": request.profile_key,
        "culture_key": request.culture_key,
        "period_key": request.period_key,
        "auto_hydro": request.auto_hydro,
        "label_language": request.label_language,
    }
    try:
        manifest = _build_manifest(
            "run_analysis_service",
            request_payload=manifest_payload,
            seed=request.random_seed,
            source_layers=manifest_payload,
        )

        context = QgsProcessingContext()
        context.setProject(QgsProject.instance())
        feedback = _ServiceTaskFeedback(task)
        analyzer = FengShuiAnalyzer(context=context, feedback=feedback)

        prepared_water = request.water_layer
        if prepared_water is None and request.auto_hydro:
            auto_hydro_layer = analyzer.build_hydro_network(request.dem_layer)
            if auto_hydro_layer is not None and auto_hydro_layer.featureCount() > 0:
                analyzer.style_hydro_network(auto_hydro_layer)
                auto_hydro_layer.setName(
                    plugin._output_layer_name(
                        request.dem_layer.name(),
                        "hydro_auto",
                        request.label_language,
                    )
                )
                QgsProject.instance().addMapLayer(auto_hydro_layer)
                prepared_water = auto_hydro_layer

        output_layer = analyzer.run(
            request.site_layer,
            request.dem_layer,
            water_layer=prepared_water,
            hemisphere=request.hemisphere,
            profile_key=request.profile_key,
            culture_key=request.culture_key,
            period_key=request.period_key,
        )
        if output_layer is None:
            raise RuntimeError("No analysis output layer was produced.")

        plugin._ensure_feature_uid_field(output_layer)
        output_layer.setName(
            plugin._output_layer_name(
                request.site_layer.name(),
                "analysis",
                request.label_language,
            )
        )

        mountain_updated = 0
        if mountain_options.get("enabled", False):
            mountain_updated = plugin._enrich_layers_with_mountain_names(
                [output_layer],
                radius_m=mountain_options.get("radius_m", 5000),
                max_features=mountain_options.get("max_features", 3),
                preferred_language=mountain_options.get("preferred_language", "local"),
            )

        QgsProject.instance().addMapLayer(output_layer)
        plugin._configure_layer_click_info(output_layer, request.label_language)

        return {
            "ok": True,
            "manifest": manifest.as_dict(),
            "output_layer_name": output_layer.name(),
            "mountain_updated": mountain_updated,
        }
    except (RuntimeError, ValueError, KeyError, TypeError, OSError) as exc:
        return {
            "ok": False,
            "error_code": "E_ANALYSIS_RUNTIME",
            "error_context": "Analysis failed",
            "error": exc,
        }
    except (
        RuntimeError,
        ValueError,
        KeyError,
        TypeError,
        OSError,
        QgsProcessingException,
    ) as exc:
        return {
            "ok": False,
            "error_code": "E_ANALYSIS_UNEXPECTED",
            "error_context": "Unexpected analysis failure",
            "error": exc,
        }


def run_term_extraction_service(
    *,
    task,
    plugin,
    request: TermExtractionRequest,
) -> Dict[str, Any]:
    if task.isCanceled():
        return {
            "ok": False,
            "error_code": "E_TASK_CANCELLED",
            "error_context": "landscape extraction canceled",
        }

    mountain_options = getattr(request, "mountain_options", {}) or {}
    manifest_payload = {
        "dem_layer": _layer_identity(request.dem_layer),
        "water_layer": _layer_identity(request.water_layer),
        "hemisphere": request.hemisphere,
        "profile_key": request.profile_key,
        "culture_key": request.culture_key,
        "period_key": request.period_key,
        "auto_hydro": request.auto_hydro,
        "include_terms": request.include_terms,
        "label_language": request.label_language,
    }
    try:
        manifest = _build_manifest(
            "run_term_extraction_service",
            request_payload=manifest_payload,
            seed=None,
            source_layers={
                "dem_layer": _layer_identity(request.dem_layer),
                "water_layer": _layer_identity(request.water_layer),
            },
        )

        context = QgsProcessingContext()
        context.setProject(QgsProject.instance())
        feedback = _ServiceTaskFeedback(task)
        analyzer = FengShuiAnalyzer(context=context, feedback=feedback)

        ridge_layer = analyzer.build_ridge_network(request.dem_layer)
        if ridge_layer is None:
            return {
                "ok": False,
                "error_code": "E_LANDSCAPE_RUNTIME",
                "error_context": "Landscape extraction failed: ridge network was not created",
                "error": RuntimeError("Ridge layer creation failed."),
            }
        ridge_layer.setName(
            plugin._output_layer_name(
                request.dem_layer.name(),
                "ridge",
                request.label_language,
            )
        )
        analyzer.style_ridge_network(ridge_layer)

        hydro_reference_layer = request.water_layer
        hydro_layer = None
        if request.water_layer is not None and plugin._is_line_layer(request.water_layer):
            hydro_layer = plugin._copy_vector_layer(
                request.water_layer,
                plugin._output_layer_name(
                    request.dem_layer.name(),
                    "hydro",
                    request.label_language,
                ),
            )
            if hydro_layer is not None and hydro_layer.featureCount() > 0:
                analyzer.style_hydro_network(hydro_layer)
            else:
                hydro_layer = None
        elif request.auto_hydro:
            hydro_layer = analyzer.build_hydro_network(request.dem_layer)
            if hydro_layer is not None and hydro_layer.featureCount() > 0:
                hydro_layer.setName(
                    plugin._output_layer_name(
                        request.dem_layer.name(),
                        "hydro",
                        request.label_language,
                    )
                )
                analyzer.style_hydro_network(hydro_layer)
                if hydro_reference_layer is None:
                    hydro_reference_layer = hydro_layer
            else:
                hydro_layer = None

        terms_layer = None
        line_layer = None
        if request.include_terms:
            terms_layer = analyzer.extract_terms(
                request.dem_layer,
                water_layer=hydro_reference_layer,
                hemisphere=request.hemisphere,
                profile_key=request.profile_key,
                culture_key=request.culture_key,
                period_key=request.period_key,
                label_language=request.label_language,
            )
            if terms_layer is not None:
                terms_layer.setName(
                    plugin._output_layer_name(
                        request.dem_layer.name(),
                        "terms",
                        request.label_language,
                    )
                )
                line_layer = analyzer.build_term_links(
                    terms_layer,
                    label_language=request.label_language,
                )
                if line_layer is not None:
                    line_layer.setName(
                        plugin._output_layer_name(
                            request.dem_layer.name(),
                            "term_links",
                            request.label_language,
                        )
                    )
                analyzer.style_term_points(
                    terms_layer,
                    label_language=request.label_language,
                )
                if line_layer is not None:
                    analyzer.style_term_links(
                        line_layer,
                        label_language=request.label_language,
                    )

        layers_top_to_bottom = []
        if request.include_terms and terms_layer:
            layers_top_to_bottom.append(terms_layer)
        if request.include_terms and line_layer:
            layers_top_to_bottom.append(line_layer)
        if hydro_layer:
            layers_top_to_bottom.append(hydro_layer)
        layers_top_to_bottom.append(ridge_layer)

        mountain_updated = 0
        if mountain_options.get("enabled", False):
            mountain_updated = plugin._enrich_layers_with_mountain_names(
                layers_top_to_bottom,
                radius_m=mountain_options.get("radius_m", 5000),
                max_features=mountain_options.get("max_features", 3),
                preferred_language=mountain_options.get(
                    "preferred_language",
                    "local",
                ),
            )

        plugin._insert_output_layers(layers_top_to_bottom, request.label_language)

        created = [f"{ridge_layer.name()} ({ridge_layer.featureCount()})"]
        if hydro_layer:
            created.insert(0, f"{hydro_layer.name()} ({hydro_layer.featureCount()})")
        if request.include_terms and line_layer and terms_layer:
            created.insert(0, f"{line_layer.name()} ({line_layer.featureCount()})")
            created.insert(0, f"{terms_layer.name()} ({terms_layer.featureCount()})")

        return {
            "ok": True,
            "manifest": manifest.as_dict(),
            "created_layers": created,
            "mountain_updated": mountain_updated,
        }
    except (RuntimeError, ValueError, KeyError, TypeError, OSError) as exc:
        return {
            "ok": False,
            "error_code": "E_LANDSCAPE_RUNTIME",
            "error_context": "Landscape extraction failed",
            "error": exc,
        }
    except (
        RuntimeError,
        ValueError,
        KeyError,
        TypeError,
        OSError,
        QgsProcessingException,
    ) as exc:
        return {
            "ok": False,
            "error_code": "E_LANDSCAPE_UNEXPECTED",
            "error_context": "Unexpected landscape extraction failure",
            "error": exc,
        }


def run_profile_compare_service(
    *,
    task,
    plugin,
    request: CompareRequest,
    mountain_options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if task.isCanceled():
        return {
            "ok": False,
            "error_code": "E_TASK_CANCELLED",
            "error_context": "comparison canceled",
        }

    mountain_options = mountain_options or {}
    manifest_payload = {
        "site_layer": _layer_identity(request.site_layer),
        "dem_layer": _layer_identity(request.dem_layer),
        "water_layer": _layer_identity(request.water_layer),
        "hemisphere": request.hemisphere,
        "base_profile_key": request.base_profile_key,
        "compare_profile_key": request.compare_profile_key,
        "culture_key": request.culture_key,
        "period_key": request.period_key,
        "auto_hydro": request.auto_hydro,
        "label_language": request.label_language,
    }
    try:
        manifest = _build_manifest(
            "run_profile_compare_service",
            request_payload=manifest_payload,
            seed=None,
            source_layers={
                "site_layer": _layer_identity(request.site_layer),
                "dem_layer": _layer_identity(request.dem_layer),
            },
        )

        context = QgsProcessingContext()
        context.setProject(QgsProject.instance())
        feedback = _ServiceTaskFeedback(task)
        analyzer = FengShuiAnalyzer(context=context, feedback=feedback)

        prepared_water = request.water_layer
        if prepared_water is None and request.auto_hydro:
            auto_hydro_layer = analyzer.build_hydro_network(request.dem_layer)
            if auto_hydro_layer and auto_hydro_layer.featureCount() > 0:
                analyzer.style_hydro_network(auto_hydro_layer)
                auto_hydro_layer.setName(
                    plugin._output_layer_name(
                        request.dem_layer.name(),
                        "hydro_auto",
                        request.label_language,
                    )
                )
                QgsProject.instance().addMapLayer(auto_hydro_layer)
                prepared_water = auto_hydro_layer

        base_layer = analyzer.run(
            request.site_layer,
            request.dem_layer,
            water_layer=prepared_water,
            hemisphere=request.hemisphere,
            profile_key=request.base_profile_key,
            culture_key=request.culture_key,
            period_key=request.period_key,
        )
        compare_layer = analyzer.run(
            request.site_layer,
            request.dem_layer,
            water_layer=prepared_water,
            hemisphere=request.hemisphere,
            profile_key=request.compare_profile_key,
            culture_key=request.culture_key,
            period_key=request.period_key,
        )
        if base_layer is None or compare_layer is None:
            return {
                "ok": False,
                "error_code": "E_COMPARE_RUNTIME",
                "error_context": "Profile comparison failed",
                "error": RuntimeError("Profile comparison produced no layer(s)."),
            }

        plugin._ensure_feature_uid_field(base_layer)
        plugin._ensure_feature_uid_field(compare_layer)
        base_layer.setName(
            f"{plugin._output_layer_name(request.site_layer.name(), 'analysis', request.label_language)}_{request.base_profile_key}"
        )
        compare_layer.setName(
            f"{plugin._output_layer_name(request.site_layer.name(), 'analysis', request.label_language)}_{request.compare_profile_key}"
        )

        if mountain_options.get("enabled", False):
            plugin._enrich_layers_with_mountain_names(
                [base_layer, compare_layer],
                radius_m=mountain_options.get("radius_m", 5000),
                max_features=mountain_options.get("max_features", 3),
                preferred_language=mountain_options.get(
                    "preferred_language",
                    "local",
                ),
            )

        QgsProject.instance().addMapLayer(base_layer)
        QgsProject.instance().addMapLayer(compare_layer)
        plugin._configure_layer_click_info(base_layer, request.label_language)
        plugin._configure_layer_click_info(compare_layer, request.label_language)

        try:
            compare_results = prepare_compare_results(
                plugin=plugin,
                base_layer=base_layer,
                compare_layer=compare_layer,
                compare_profile_key=request.compare_profile_key,
                label_language=request.label_language,
            )
        except RuntimeError as exc:
            message = str(exc)
            error_context = (
                "Compare selection failed for top changed features"
                if "fully selected" in message
                else "Compare change-layer export failed"
                if "not exported" in message
                else "Compare contract check failed"
            )
            return {
                "ok": False,
                "error_code": "E_DATA_MISMATCH",
                "error_context": error_context,
                "error": exc,
            }

        base_stats = compare_results["base_stats"]
        compare_stats = compare_results["compare_stats"]
        delta_stats = compare_results["delta_stats"]
        top_changes = compare_results["top_changes"]
        selected_change_count = compare_results["selected_change_count"]
        zoom_applied = compare_results["zoom_applied"]
        change_layer_name = compare_results["change_layer_name"]

        try:
            json_path, md_path = plugin._write_profile_compare_report(
                site_layer_name=request.site_layer.name(),
                base_profile_key=request.base_profile_key,
                compare_profile_key=request.compare_profile_key,
                base_stats=base_stats,
                compare_stats=compare_stats,
                delta_stats=delta_stats,
                top_changes=top_changes,
                change_layer_name=change_layer_name,
            )
        except (OSError, ValueError, TypeError) as exc:
            return {
                "ok": False,
                "error_code": "E_REPORT_WRITE",
                "error_context": "Comparison report write failed",
                "error": exc,
            }

        return {
            "ok": True,
            "manifest": manifest.as_dict(),
            "base_stats": base_stats,
            "compare_stats": compare_stats,
            "delta_stats": delta_stats,
            "top_changes": top_changes,
            "selected_change_count": selected_change_count,
            "zoom_applied": zoom_applied,
            "change_layer_name": change_layer_name,
            "json_path": json_path,
            "md_path": md_path,
            "base_layer_name": base_layer.name(),
            "compare_layer_name": compare_layer.name(),
        }
    except (RuntimeError, ValueError, KeyError, TypeError, OSError) as exc:
        return {
            "ok": False,
            "error_code": "E_COMPARE_RUNTIME",
            "error_context": "Profile comparison failed",
            "error": exc,
        }
    except (
        RuntimeError,
        ValueError,
        KeyError,
        TypeError,
        OSError,
        QgsProcessingException,
    ) as exc:
        return {
            "ok": False,
            "error_code": "E_COMPARE_UNEXPECTED",
            "error_context": "Unexpected profile comparison failure",
            "error": exc,
        }


def run_calibration_service(
    *,
    task,
    plugin,
    request: CalibrationRequest,
    mountain_options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if task.isCanceled():
        return {
            "ok": False,
            "error_code": "E_TASK_CANCELLED",
            "error_context": "calibration canceled",
        }

    mountain_options = mountain_options or request.mountain_options or {}
    manifest_payload = {
        "site_layer": _layer_identity(request.site_layer),
        "dem_layer": _layer_identity(request.dem_layer),
        "water_layer": _layer_identity(request.water_layer),
        "hemisphere": request.hemisphere,
        "profile_key": request.profile_key,
        "culture_key": request.culture_key,
        "period_key": request.period_key,
        "negative_ratio": request.negative_ratio,
        "random_seed": request.random_seed,
        "auto_hydro": request.auto_hydro,
        "label_language": request.label_language,
    }
    try:
        manifest = _build_manifest(
            "run_calibration_service",
            request_payload=manifest_payload,
            seed=request.random_seed,
            source_layers={
                "site_layer": _layer_identity(request.site_layer),
                "dem_layer": _layer_identity(request.dem_layer),
            },
        )

        context = QgsProcessingContext()
        context.setProject(QgsProject.instance())
        feedback = _ServiceTaskFeedback(task)
        analyzer = FengShuiAnalyzer(context=context, feedback=feedback)

        prepared_water = request.water_layer
        if prepared_water is None and request.auto_hydro:
            auto_hydro_layer = analyzer.build_hydro_network(request.dem_layer)
            if auto_hydro_layer is not None and auto_hydro_layer.featureCount() > 0:
                analyzer.style_hydro_network(auto_hydro_layer)
                auto_hydro_layer.setName(
                    plugin._output_layer_name(
                        request.dem_layer.name(),
                        "hydro_auto_calibration",
                        request.label_language,
                    )
                )
                QgsProject.instance().addMapLayer(auto_hydro_layer)
                prepared_water = auto_hydro_layer

        scored_layer, report = analyzer.calibrate(
            site_layer=request.site_layer,
            dem_layer=request.dem_layer,
            water_layer=prepared_water,
            hemisphere=request.hemisphere,
            profile_key=request.profile_key,
            culture_key=request.culture_key,
            period_key=request.period_key,
            negative_ratio=request.negative_ratio,
            random_seed=request.random_seed,
        )
        if scored_layer is None or not isinstance(report, dict):
            return {
                "ok": False,
                "error_code": "E_CALIBRATION_RUNTIME",
                "error_context": "Calibration failed",
                "error": RuntimeError("Calibration did not return scored layer or report."),
            }

        plugin._ensure_feature_uid_field(scored_layer)
        scored_layer.setName(
            plugin._output_layer_name(
                request.site_layer.name(),
                "calibration",
                request.label_language,
            )
        )

        mountain_updated = 0
        if mountain_options.get("enabled", False):
            mountain_updated = plugin._enrich_layers_with_mountain_names(
                [scored_layer],
                radius_m=mountain_options.get("radius_m", 5000),
                max_features=mountain_options.get("max_features", 3),
                preferred_language=mountain_options.get(
                    "preferred_language",
                    "local",
                ),
            )

        QgsProject.instance().addMapLayer(scored_layer)
        plugin._configure_layer_click_info(scored_layer, request.label_language)

        is_contract_ok, contract_message = plugin._validate_calibration_feature_contract(
            scored_layer,
            report,
        )
        if not is_contract_ok:
            return {
                "ok": False,
                "error_code": "E_DATA_MISMATCH",
                "error_context": "Calibration contract check failed",
                "error": RuntimeError(contract_message),
            }

        try:
            json_path, md_path = plugin._write_calibration_report(report)
        except (OSError, ValueError, TypeError) as exc:
            return {
                "ok": False,
                "error_code": "E_REPORT_WRITE",
                "error_context": "Calibration report write failed",
                "error": exc,
            }

        return {
            "ok": True,
            "manifest": manifest.as_dict(),
            "report": report,
            "json_path": json_path,
            "md_path": md_path,
            "mountain_updated": mountain_updated,
        }
    except (RuntimeError, ValueError, KeyError, TypeError, OSError) as exc:
        return {
            "ok": False,
            "error_code": "E_CALIBRATION_RUNTIME",
            "error_context": "Calibration failed",
            "error": exc,
        }
    except (
        RuntimeError,
        ValueError,
        KeyError,
        TypeError,
        OSError,
        QgsProcessingException,
    ) as exc:
        return {
            "ok": False,
            "error_code": "E_CALIBRATION_UNEXPECTED",
            "error_context": "Unexpected calibration failure",
            "error": exc,
        }
