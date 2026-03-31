# -*- coding: utf-8 -*-
from qgis.core import (
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
            return AnalysisOutput(
                analysis_layer=analysis_layer,
                auto_hydro_layer=auto_hydro_layer,
                used_water_layer=prepared_water,
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

            return TermExtractionOutput(
                ridge_layer=ridge_layer,
                hydro_layer=hydro_layer,
                terms_layer=terms_layer,
                term_links_layer=line_layer,
                used_water_layer=hydro_reference_layer,
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
            return CompareOutput(
                base_layer=base_layer,
                compare_layer=compare_layer,
                auto_hydro_layer=auto_hydro_layer,
                used_water_layer=prepared_water,
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
            return CalibrationOutput(
                calibrated_layer=calibrated_layer,
                report=report,
                auto_hydro_layer=auto_hydro_layer,
                used_water_layer=prepared_water,
            )
        except FengShuiError:
            raise
        except Exception as exc:
            self._wrap_analysis_error(
                "Calibration",
                FengShuiErrorCode.CALIBRATION_FAILURE,
                exc,
            )
