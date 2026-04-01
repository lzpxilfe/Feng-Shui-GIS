# -*- coding: utf-8 -*-
import hashlib
import json
from datetime import datetime, timezone

from qgis.core import (
    QgsApplication,
    QgsFeatureRequest,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProject,
    QgsVectorLayer,
)
from qgis.core import QgsWkbTypes

from ..analysis import FengShuiAnalyzer
from ..service_contracts import (
    AnalysisRequest,
    AnalysisOutput,
    CalibrationRequest,
    CalibrationOutput,
    CompareRequest,
    CompareOutput,
    TermExtractionOutput,
    TermExtractionRequest,
)
from ..errors import FengShuiError, FengShuiErrorCode


class FengShuiAnalysisService:
    def __init__(self, analyzer_factory=FengShuiAnalyzer):
        self._analyzer_factory = analyzer_factory

    @staticmethod
    def _build_context():
        context = QgsProcessingContext()
        context.setProject(QgsProject.instance())
        feedback = QgsProcessingFeedback()
        return context, feedback

    @staticmethod
    def _is_line_layer(layer):
        if layer is None:
            return False
        return QgsWkbTypes.geometryType(layer.wkbType()) == QgsWkbTypes.LineGeometry

    @staticmethod
    def _copy_vector_layer(source_layer):
        if source_layer is None:
            return None
        copied = source_layer.materialize(QgsFeatureRequest())
        if not isinstance(copied, QgsVectorLayer):
            return None
        return copied

    @staticmethod
    def _utc_now():
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00",
            "Z",
        )

    @staticmethod
    def _digest(value):
        text = json.dumps(value, sort_keys=True, ensure_ascii=False)
        return hashlib.sha1(text.encode("utf-8")).hexdigest()

    def _layer_contract(self, layer):
        if layer is None:
            return None
        fields = []
        try:
            for field in layer.fields():
                fields.append(
                    {
                        "name": field.name(),
                        "type": field.typeName(),
                        "len": int(field.length()),
                    }
                )
        except Exception:
            fields = []

        try:
            source = str(layer.source())
        except Exception:
            source = ""
        try:
            crs = str(layer.crs().authid())
        except Exception:
            crs = ""
        try:
            provider = str(layer.dataProvider().name())
        except Exception:
            provider = ""
        try:
            feature_count = int(layer.featureCount())
        except Exception:
            feature_count = 0
        try:
            wkb_type = int(layer.wkbType())
        except Exception:
            wkb_type = None

        contract = {
            "name": str(layer.name()),
            "source": source,
            "crs": crs,
            "provider": provider,
            "wkb_type": wkb_type,
            "feature_count": feature_count,
            "fields": fields,
        }
        contract["fingerprint"] = self._digest(contract)
        return contract

    @staticmethod
    def _layer_identity(layer):
        if layer is None:
            return {}
        identity = {"name": str(getattr(layer, "name", lambda: "")())}
        try:
            identity["id"] = str(layer.id())
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
        self,
        service_name,
        request_payload,
        seed,
        source_layers,
        *,
        output_layers=None,
        report=None,
        split_manifest=None,
    ):
        qgis_version = ""
        try:
            qgis_version = QgsApplication.version()
        except Exception:
            pass

        request_signature = self._digest(request_payload)
        return {
            "manifest_version": "1.0.0",
            "run_id": self._digest(
                {
                    "service": service_name,
                    "request_signature": request_signature,
                    "seed": seed,
                    "time": self._utc_now(),
                }
            )[:16],
            "service_name": service_name,
            "qgis_version": qgis_version,
            "started_at_utc": self._utc_now(),
            "request_signature": request_signature,
            "seed": seed,
            "source_layers": source_layers,
            "output_layers": output_layers,
            "split_manifest": split_manifest,
            "report_signature": self._digest(report) if report is not None else None,
        }

    def _new_manifest_payload(
        self,
        site_layer=None,
        dem_layer=None,
        water_layer=None,
        request_extra=None,
    ):
        payload = {
            "site_layer": self._layer_identity(site_layer),
            "dem_layer": self._layer_identity(dem_layer),
            "water_layer": self._layer_identity(water_layer),
        }
        if request_extra:
            payload.update(request_extra)
        return payload

    def _new_source_layer_contracts(
        self,
        site_layer=None,
        dem_layer=None,
        water_layer=None,
    ):
        return {
            "site": self._layer_contract(site_layer),
            "dem": self._layer_contract(dem_layer),
            "water": self._layer_contract(water_layer),
        }

    def _new_analyzer(self):
        try:
            context, feedback = self._build_context()
            return self._analyzer_factory(context=context, feedback=feedback)
        except Exception as exc:
            raise FengShuiError(
                code=FengShuiErrorCode.SERVICE_UNAVAILABLE,
                message="Failed to initialize analysis engine.",
                details=repr(exc),
                user_message="analysis_engine_init_failed",
            ) from exc

    @staticmethod
    def _require_layer(layer, layer_name, reason_code):
        if layer is None:
            raise FengShuiError(
                code=FengShuiErrorCode.INPUT_VALIDATION,
                message=f"{layer_name} is required.",
                details=f"Missing required layer for {reason_code}",
                user_message=f"missing_{layer_name}",
            )
        return layer

    @staticmethod
    def _ensure_output(layer, operation_name):
        if layer is None:
            raise FengShuiError(
                code=FengShuiErrorCode.OUTPUT_GENERATION_FAILURE,
                message=f"{operation_name} did not return a result layer.",
                user_message=f"{operation_name}_output_missing",
            )
        return layer

    @staticmethod
    def _wrap_analysis_error(operation_name, error_code, exc):
        raise FengShuiError(
            code=error_code,
            message=f"{operation_name} failed.",
            details=repr(exc),
            user_message=f"{operation_name.lower().replace(' ', '_')}_failed",
        ) from exc

    def run_analysis(self, request: AnalysisRequest) -> AnalysisOutput:
        self._require_layer(request.site_layer, "site_layer", "analysis")
        self._require_layer(request.dem_layer, "dem_layer", "analysis")
        try:
            request_payload = self._new_manifest_payload(
                site_layer=request.site_layer,
                dem_layer=request.dem_layer,
                water_layer=request.water_layer,
                request_extra={
                    "operation": "run_analysis",
                    "hemisphere": request.hemisphere,
                    "profile_key": request.profile_key,
                    "culture_key": request.culture_key,
                    "period_key": request.period_key,
                    "auto_hydro": bool(request.auto_hydro),
                },
            )
            manifest = self._build_manifest(
                service_name="run_analysis",
                request_payload=request_payload,
                seed=None,
                source_layers=self._new_source_layer_contracts(
                    site_layer=request.site_layer,
                    dem_layer=request.dem_layer,
                    water_layer=request.water_layer,
                ),
            )

            analyzer = self._new_analyzer()
            prepared_water = request.water_layer
            auto_hydro_layer = None
            if prepared_water is None and request.auto_hydro:
                auto_hydro_layer = analyzer.build_hydro_network(request.dem_layer)
                if auto_hydro_layer and auto_hydro_layer.featureCount() > 0:
                    analyzer.style_hydro_network(auto_hydro_layer)
                    prepared_water = auto_hydro_layer
            analysis_layer = analyzer.run(
                request.site_layer,
                request.dem_layer,
                water_layer=prepared_water,
                hemisphere=request.hemisphere,
                profile_key=request.profile_key,
                culture_key=request.culture_key,
                period_key=request.period_key,
            )
            self._ensure_output(analysis_layer, "analysis")
            manifest["output_layers"] = {
                "analysis_layer": self._layer_contract(analysis_layer),
                "auto_hydro_layer": self._layer_contract(auto_hydro_layer),
                "used_water_layer": self._layer_contract(prepared_water),
            }
            return AnalysisOutput(
                analysis_layer=analysis_layer,
                auto_hydro_layer=auto_hydro_layer,
                used_water_layer=prepared_water,
                run_manifest=manifest,
            )
        except FengShuiError:
            raise
        except Exception as exc:
            self._wrap_analysis_error(
                "Analysis",
                FengShuiErrorCode.ANALYSIS_FAILURE,
                exc,
            )

    def run_term_extraction(self, request: TermExtractionRequest) -> TermExtractionOutput:
        self._require_layer(request.dem_layer, "dem_layer", "term_extraction")
        try:
            request_payload = self._new_manifest_payload(
                dem_layer=request.dem_layer,
                water_layer=request.water_layer,
                request_extra={
                    "operation": "run_term_extraction",
                    "hemisphere": request.hemisphere,
                    "profile_key": request.profile_key,
                    "culture_key": request.culture_key,
                    "period_key": request.period_key,
                    "auto_hydro": bool(request.auto_hydro),
                    "include_terms": bool(request.include_terms),
                },
            )
            manifest = self._build_manifest(
                service_name="run_term_extraction",
                request_payload=request_payload,
                seed=None,
                source_layers=self._new_source_layer_contracts(
                    dem_layer=request.dem_layer,
                    water_layer=request.water_layer,
                ),
            )
            analyzer = self._new_analyzer()
            hydro_reference_layer = request.water_layer
            auto_hydro_layer = None
            hydro_layer = None

            ridge_layer = analyzer.build_ridge_network(request.dem_layer)
            analyzer.style_ridge_network(ridge_layer)

            if hydro_reference_layer is not None and self._is_line_layer(
                hydro_reference_layer
            ):
                hydro_layer = self._copy_vector_layer(hydro_reference_layer)
                if hydro_layer and hydro_layer.featureCount() > 0:
                    analyzer.style_hydro_network(hydro_layer)
            elif request.auto_hydro:
                auto_hydro_layer = analyzer.build_hydro_network(request.dem_layer)
                if auto_hydro_layer and auto_hydro_layer.featureCount() > 0:
                    analyzer.style_hydro_network(auto_hydro_layer)
                    hydro_reference_layer = auto_hydro_layer
                    hydro_layer = auto_hydro_layer

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
                )
                self._ensure_output(terms_layer, "term_extraction")
                analyzer.style_term_points(terms_layer)
                line_layer = analyzer.build_term_links(terms_layer)
                analyzer.style_term_links(line_layer)

            manifest["output_layers"] = {
                "ridge_layer": self._layer_contract(ridge_layer),
                "hydro_layer": self._layer_contract(hydro_layer),
                "terms_layer": self._layer_contract(terms_layer),
                "term_links_layer": self._layer_contract(line_layer),
            }
            return TermExtractionOutput(
                ridge_layer=ridge_layer,
                hydro_layer=hydro_layer,
                terms_layer=terms_layer,
                term_links_layer=line_layer,
                used_water_layer=hydro_reference_layer,
                run_manifest=manifest,
            )
        except FengShuiError:
            raise
        except Exception as exc:
            self._wrap_analysis_error(
                "Term extraction",
                FengShuiErrorCode.TERM_EXTRACTION_FAILURE,
                exc,
            )

    def run_profile_compare(
        self,
        request: CompareRequest,
    ) -> CompareOutput:
        self._require_layer(request.site_layer, "site_layer", "profile_compare")
        self._require_layer(request.dem_layer, "dem_layer", "profile_compare")
        try:
            request_payload = self._new_manifest_payload(
                site_layer=request.site_layer,
                dem_layer=request.dem_layer,
                water_layer=request.water_layer,
                request_extra={
                    "operation": "run_profile_compare",
                    "hemisphere": request.hemisphere,
                    "base_profile_key": request.base_profile_key,
                    "compare_profile_key": request.compare_profile_key,
                    "culture_key": request.culture_key,
                    "period_key": request.period_key,
                    "auto_hydro": bool(request.auto_hydro),
                },
            )
            manifest = self._build_manifest(
                service_name="run_profile_compare",
                request_payload=request_payload,
                seed=None,
                source_layers=self._new_source_layer_contracts(
                    site_layer=request.site_layer,
                    dem_layer=request.dem_layer,
                    water_layer=request.water_layer,
                ),
            )
            analyzer = self._new_analyzer()
            prepared_water = request.water_layer
            auto_hydro_layer = None
            if prepared_water is None and request.auto_hydro:
                auto_hydro_layer = analyzer.build_hydro_network(request.dem_layer)
                if auto_hydro_layer and auto_hydro_layer.featureCount() > 0:
                    analyzer.style_hydro_network(auto_hydro_layer)
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
            self._ensure_output(base_layer, "base_profile_compare")
            self._ensure_output(compare_layer, "compare_profile")
            manifest["output_layers"] = {
                "base_layer": self._layer_contract(base_layer),
                "compare_layer": self._layer_contract(compare_layer),
                "auto_hydro_layer": self._layer_contract(auto_hydro_layer),
                "used_water_layer": self._layer_contract(prepared_water),
            }
            return CompareOutput(
                base_layer=base_layer,
                compare_layer=compare_layer,
                auto_hydro_layer=auto_hydro_layer,
                used_water_layer=prepared_water,
                run_manifest=manifest,
            )
        except FengShuiError:
            raise
        except Exception as exc:
            self._wrap_analysis_error(
                "Profile comparison",
                FengShuiErrorCode.COMPARISON_FAILURE,
                exc,
            )

    def run_calibration(self, request: CalibrationRequest) -> CalibrationOutput:
        self._require_layer(request.site_layer, "site_layer", "calibration")
        self._require_layer(request.dem_layer, "dem_layer", "calibration")
        try:
            request_payload = self._new_manifest_payload(
                site_layer=request.site_layer,
                dem_layer=request.dem_layer,
                water_layer=request.water_layer,
                request_extra={
                    "operation": "run_calibration",
                    "hemisphere": request.hemisphere,
                    "profile_key": request.profile_key,
                    "culture_key": request.culture_key,
                    "period_key": request.period_key,
                    "negative_ratio": int(request.negative_ratio),
                    "random_seed": int(request.random_seed),
                    "auto_hydro": bool(request.auto_hydro),
                },
            )
            manifest = self._build_manifest(
                service_name="run_calibration",
                request_payload=request_payload,
                seed=request.random_seed,
                source_layers=self._new_source_layer_contracts(
                    site_layer=request.site_layer,
                    dem_layer=request.dem_layer,
                    water_layer=request.water_layer,
                ),
            )
            analyzer = self._new_analyzer()
            prepared_water = request.water_layer
            auto_hydro_layer = None
            if prepared_water is None and request.auto_hydro:
                auto_hydro_layer = analyzer.build_hydro_network(request.dem_layer)
                if auto_hydro_layer and auto_hydro_layer.featureCount() > 0:
                    analyzer.style_hydro_network(auto_hydro_layer)
                    prepared_water = auto_hydro_layer

            calibrated_layer, report = analyzer.calibrate(
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
            self._ensure_output(calibrated_layer, "calibration")
            if not isinstance(report, dict):
                raise FengShuiError(
                    code=FengShuiErrorCode.CALIBRATION_FAILURE,
                    message="Calibration returned invalid report payload.",
                    user_message="calibration_invalid_report",
                )
            manifest["split_manifest"] = report.get("calibration_split")
            manifest["output_layers"] = {
                "calibrated_layer": self._layer_contract(calibrated_layer),
                "auto_hydro_layer": self._layer_contract(auto_hydro_layer),
                "used_water_layer": self._layer_contract(prepared_water),
            }
            manifest["report_signature"] = self._digest(report)
            return CalibrationOutput(
                calibrated_layer=calibrated_layer,
                report=report,
                auto_hydro_layer=auto_hydro_layer,
                used_water_layer=prepared_water,
                run_manifest=manifest,
            )
        except FengShuiError:
            raise
        except Exception as exc:
            self._wrap_analysis_error(
                "Calibration",
                FengShuiErrorCode.CALIBRATION_FAILURE,
                exc,
            )
