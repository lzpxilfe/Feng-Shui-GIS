# -*- coding: utf-8 -*-
from collections import defaultdict
import math
import random

from qgis import processing
from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsPointXY,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingUtils,
    QgsProject,
    QgsRasterLayer,
    QgsRendererCategory,
    QgsVectorLayer,
    edit,
)

from .analysis_metrics import (
    binary_classification_metrics,
    distribution_stats,
    metrics_better,
    raw_calibration_stats,
    score_aspect,
    score_gaussian,
    score_water_distance,
    suppress_near_duplicates,
    trapezoid_auc,
    unique_float_candidates,
)
from .analysis_metadata import (
    metadata_field_name,
    metadata_grouping,
    metadata_text,
    summarize_site_metadata,
)
from .analysis_geometry import (
    build_transform,
    collect_points,
    feature_point,
    geometry_point,
    prepare_water_reference,
    transform_geometry,
    transform_point,
)
from .analysis_dem_utils import (
    azimuth_label,
    direction_mean,
    fmt_num,
    mean_scores,
    offset_point,
    sample_dem,
    sample_ring,
    stddev,
)
from .analysis_dem_metrics import (
    compute_cut_depth,
    compute_dem_water_score,
    compute_enclosure_index,
    compute_form_score,
    compute_long_score,
    compute_roughness,
    compute_sashinsa_score,
    null_dem_metrics,
    relief_statistics,
    sampling_setup,
)
from .analysis_networks import (
    compute_stream_order,
    stream_class,
    trace_downstream_path,
)
from .analysis_principles import (
    build_principle_note,
    build_principle_records,
    build_principle_summary,
)
from .analysis_reasoning import (
    compose_hyeol_reason,
    compose_term_reason,
    enclosure_hint,
    sashinsa_hint,
    score_band_label,
    tpi_class_label,
    tpi_hint,
)
from .analysis_hyeol import (
    adaptive_spacing_diagnostics as compute_adaptive_spacing_diagnostics,
    combine_hydro_scores,
    evaluate_hyeol_candidate,
    grid_points,
    recommended_hyeol_count,
)
from .analysis_scoring import (
    explain_top_factors,
    indicator_contributions,
    paper_evidence_summary,
    profile_confidence,
    profile_weighted_score,
)
from .analysis_sampling import negative_sampling_plan
from .analysis_term_generation import (
    core_hyeol_term_payload,
    generic_term_payload,
    ipsu_term_payload,
    misa_term_payload,
    myeongdang_term_payload,
    relief_from_ring_values,
)
from .analysis_terrain_rules import (
    clamp_min_order,
    clamp_quantile,
    compute_hydro_min_path_length,
    compute_hydro_spacing,
)
from .analysis_terms import (
    adjusted_term_score,
    append_term_feature,
    term_layer_fields,
    term_runtime_state,
)
from .analysis_term_links import (
    build_term_link_feature,
    distinct_points,
    group_term_features,
    link_ready_payload,
    path_mean_score,
    polyline_length,
    smooth_polyline,
    term_link_fields,
)
from .analysis_water import dem_step, nearest_water_distance
from .calibration_helpers import (
    build_calibration_report_payload,
    calibration_profile_parameters,
    split_calibration_rows,
    empty_calibration_fit,
    finalize_calibration_fit,
    normalized_weight_map,
    parameter_candidate_profiles,
    parameter_candidates,
    summarize_named_deltas,
)
from .cultural_context import build_context
from .profile_catalog import (
    analysis_rules,
    line_styles,
    point_styles,
    profile_spec,
    special_term_specs,
    term_label,
    term_label_ko,
    term_radius_scales,
    term_specs,
)
from .reference_catalog import reference_display_text
from .visualization_specs import (
    hydro_symbol_profiles,
    ridge_symbol_profiles,
    term_link_symbol_layers,
    term_point_symbol_layers,
)

RIDGE_CLASS_LABELS = {
    "major": {"ko": "대간·정맥", "en": "Daegan+Jeongmaek"},
    "minor": {"ko": "기맥·지맥", "en": "Gimaek+Jimaek"},
}

HYDRO_CLASS_LABELS_KO = {
    "main": "주수계",
    "secondary": "중간 수계",
    "branch": "지류",
    "minor": "미소 수로",
}


class FengShuiAnalyzer:
    """Compute archaeology-oriented Feng Shui scores from DEM and optional water."""

    CARDINALS = {
        "north": {"front": 180.0, "back": 0.0, "left": 90.0, "right": 270.0},
        "south": {"front": 0.0, "back": 180.0, "left": 270.0, "right": 90.0},
    }

    def __init__(self, context=None, feedback=None):
        self.context = context or QgsProcessingContext()
        self.feedback = feedback or QgsProcessingFeedback()

    @staticmethod
    def _rules():
        rules = analysis_rules()
        return rules if isinstance(rules, dict) else {}

    @classmethod
    def _rules_section(cls, section_key):
        section = cls._rules().get(section_key)
        if not isinstance(section, dict):
            raise RuntimeError(f"Missing analysis rules section '{section_key}'.")
        return section

    @staticmethod
    def _rule_float(section, key, default, min_value=None, max_value=None):
        if key not in section:
            raise RuntimeError(f"Missing numeric rule '{key}'.")
        try:
            value = float(section[key])
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"Invalid numeric rule '{key}'.") from exc
        if min_value is not None:
            value = max(float(min_value), value)
        if max_value is not None:
            value = min(float(max_value), value)
        return value

    @staticmethod
    def _rule_int(section, key, default, min_value=None, max_value=None):
        if key not in section:
            raise RuntimeError(f"Missing integer rule '{key}'.")
        try:
            value = int(section[key])
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"Invalid integer rule '{key}'.") from exc
        if min_value is not None:
            value = max(int(min_value), value)
        if max_value is not None:
            value = min(int(max_value), value)
        return value

    @staticmethod
    def _rule_threshold_value(rules_list, probe_value, value_key, default_value):
        if not isinstance(rules_list, list):
            return default_value

        candidates = []
        for item in rules_list:
            if not isinstance(item, dict):
                continue
            try:
                min_nodes = int(
                    item.get(
                        "min_nodes",
                        item.get("min_candidates", item.get("min_count", 0)),
                    )
                )
                value = item.get(value_key, default_value)
            except (TypeError, ValueError):
                continue
            candidates.append((min_nodes, value))

        candidates.sort(key=lambda pair: pair[0], reverse=True)
        for min_nodes, value in candidates:
            if probe_value >= min_nodes:
                return value
        return default_value

    def run(
        self,
        site_layer,
        dem_layer,
        water_layer=None,
        hemisphere="north",
        profile_key="general",
        culture_key="east_asia",
        period_key="early_modern",
    ):
        context = build_context(culture_key, period_key, hemisphere)
        profile = self._contextualize_profile(
            self._profile_spec(profile_key),
            context,
            profile_key,
        )
        slope = processing.run(
            "qgis:slope",
            {
                "INPUT": dem_layer,
                "BAND": 1,
                "Z_FACTOR": 1.0,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=self.context,
            feedback=self.feedback,
            is_child_algorithm=True,
        )["OUTPUT"]

        aspect = processing.run(
            "qgis:aspect",
            {
                "INPUT": dem_layer,
                "BAND": 1,
                "Z_FACTOR": 1.0,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=self.context,
            feedback=self.feedback,
            is_child_algorithm=True,
        )["OUTPUT"]

        sampled = processing.run(
            "qgis:rastersampling",
            {
                "INPUT": site_layer,
                "RASTERCOPY": slope,
                "COLUMN_PREFIX": "sl_",
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=self.context,
            feedback=self.feedback,
            is_child_algorithm=True,
        )["OUTPUT"]

        sampled = processing.run(
            "qgis:rastersampling",
            {
                "INPUT": sampled,
                "RASTERCOPY": aspect,
                "COLUMN_PREFIX": "as_",
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=self.context,
            feedback=self.feedback,
            is_child_algorithm=True,
        )["OUTPUT"]

        output_layer = self._as_vector_layer(sampled)
        self._ensure_fields(output_layer)
        self._score_points(
            site_layer=output_layer,
            dem_layer=dem_layer,
            water_layer=water_layer,
            hemisphere=hemisphere,
            profile_key=profile_key,
            context=context,
            profile=profile,
        )
        return output_layer

    def calibrate(
        self,
        site_layer,
        dem_layer,
        water_layer=None,
        hemisphere="north",
        profile_key="general",
        culture_key="korea",
        period_key="early_modern",
        negative_ratio=3,
        random_seed=42,
    ):
        positive_points = self._collect_points(site_layer, target_crs=dem_layer.crs())
        if len(positive_points) < 3:
            raise RuntimeError("Calibration requires at least 3 positive site points.")

        negative_ratio = max(1, int(negative_ratio))
        random_seed = int(random_seed)
        target_negative = len(positive_points) * negative_ratio
        negative_points = self._sample_negative_points(
            dem_layer=dem_layer,
            positive_points=positive_points,
            target_count=target_negative,
            random_seed=random_seed,
        )
        if len(negative_points) < max(3, int(target_negative * 0.4)):
            raise RuntimeError(
                "Could not generate enough negative samples for calibration."
            )

        input_layer = self._build_calibration_input_layer(
            site_layer=site_layer,
            dem_layer=dem_layer,
            positive_points=positive_points,
            negative_points=negative_points,
        )
        context = build_context(culture_key, period_key, hemisphere)
        profile = self._contextualize_profile(
            self._profile_spec(profile_key),
            context,
            profile_key,
        )
        scored_layer = self.run(
            site_layer=input_layer,
            dem_layer=dem_layer,
            water_layer=water_layer,
            hemisphere=hemisphere,
            profile_key=profile_key,
            culture_key=culture_key,
            period_key=period_key,
        )
        calibration_fit = self._fit_local_calibration_weights(
            scored_layer,
            profile,
            random_seed=random_seed,
        )
        evaluation_metrics = dict(
            calibration_fit.get("evaluation_metrics", calibration_fit.get("metrics", {}))
        )
        score_by_id = dict(
            calibration_fit.get(
                "evaluation_scores_by_id",
                calibration_fit.get("scores_by_id", {}),
            )
        )
        self._annotate_calibration_layer(
            scored_layer,
            score_by_id=score_by_id,
            best_f1_threshold=(
                evaluation_metrics["best_f1_threshold"]
                if evaluation_metrics.get("count", 0) > 0
                else None
            ),
            best_youden_threshold=(
                evaluation_metrics["best_youden_threshold"]
                if evaluation_metrics.get("count", 0) > 0
                else None
            ),
        )
        report = build_calibration_report_payload(
            context=context,
            profile=profile,
            profile_key=profile_key,
            hemisphere=hemisphere,
            site_layer_name=site_layer.name() if site_layer is not None else "",
            site_metadata_summary=self._summarize_site_metadata(site_layer),
            negative_ratio=negative_ratio,
            random_seed=random_seed,
            positive_count=len(positive_points),
            negative_count=len(negative_points),
            calibration_fit=calibration_fit,
            paper_evidence_summary=self._paper_evidence_summary(profile),
        )
        return scored_layer, report

    def extract_terms(
        self,
        dem_layer,
        water_layer=None,
        hemisphere="north",
        profile_key="general",
        culture_key="east_asia",
        period_key="early_modern",
        max_hyeol=5,
        label_language="ko",
    ):
        context = build_context(culture_key, period_key, hemisphere)
        profile = self._contextualize_profile(
            self._profile_spec(profile_key),
            context,
            profile_key,
        )
        provider = dem_layer.dataProvider()
        weights = profile.get("weights", {})
        slope_provider = None
        aspect_provider = None
        if float(weights.get("slope", 0.0)) > 0.0:
            slope_output = processing.run(
                "qgis:slope",
                {
                    "INPUT": dem_layer,
                    "BAND": 1,
                    "Z_FACTOR": 1.0,
                    "OUTPUT": "TEMPORARY_OUTPUT",
                },
                context=self.context,
                feedback=self.feedback,
                is_child_algorithm=True,
            )["OUTPUT"]
            slope_provider = self._as_raster_layer(slope_output).dataProvider()
        if float(weights.get("aspect", 0.0)) > 0.0:
            aspect_output = processing.run(
                "qgis:aspect",
                {
                    "INPUT": dem_layer,
                    "BAND": 1,
                    "Z_FACTOR": 1.0,
                    "OUTPUT": "TEMPORARY_OUTPUT",
                },
                context=self.context,
                feedback=self.feedback,
                is_child_algorithm=True,
            )["OUTPUT"]
            aspect_provider = self._as_raster_layer(aspect_output).dataProvider()
        water_index, water_geoms = self._prepare_water_reference(
            dem_layer=dem_layer,
            water_layer=water_layer,
        )
        dem_step = self._dem_step(dem_layer)
        sample_spacing = self._adaptive_spacing(dem_layer, dem_step)
        recommended_count = self._recommended_hyeol_count(dem_layer, sample_spacing)
        effective_keep = max(1, min(max_hyeol, recommended_count))
        hyeol_rules = self._rules_section("hyeol_selection")
        keep_threshold = self._rule_int(
            hyeol_rules,
            "low_keep_count_threshold",
            3,
            min_value=1,
        )
        suppress_multiplier = self._rule_float(
            hyeol_rules,
            "suppress_multiplier_high",
            10.5,
            min_value=0.1,
        )
        if effective_keep > keep_threshold:
            suppress_multiplier = self._rule_float(
                hyeol_rules,
                "suppress_multiplier_low",
                9.0,
                min_value=0.1,
            )
        suppress_distance = sample_spacing * suppress_multiplier
        candidates = self._collect_hyeol_candidates(
            provider=provider,
            dem_layer=dem_layer,
            hemisphere=hemisphere,
            dem_step=dem_step,
            spacing=sample_spacing,
            context=context,
            profile=profile,
            slope_provider=slope_provider,
            aspect_provider=aspect_provider,
            water_index=water_index,
            water_geoms=water_geoms,
        )
        selected = self._suppress_near_duplicates(
            candidates=candidates,
            min_distance=suppress_distance,
            keep=effective_keep,
        )
        return self._build_term_layer(
            dem_layer=dem_layer,
            provider=provider,
            hemisphere=hemisphere,
            dem_step=dem_step,
            selected=selected,
            context=context,
            profile_key=profile_key,
            profile=profile,
            label_language=label_language,
        )

    def _as_vector_layer(self, output_obj):
        if isinstance(output_obj, QgsVectorLayer):
            return output_obj
        resolved = QgsProcessingUtils.mapLayerFromString(output_obj, self.context)
        if not isinstance(resolved, QgsVectorLayer):
            raise RuntimeError("Could not resolve sampled output layer.")
        return resolved

    def _as_raster_layer(self, output_obj):
        if isinstance(output_obj, QgsRasterLayer):
            return output_obj
        resolved = QgsProcessingUtils.mapLayerFromString(output_obj, self.context)
        if not isinstance(resolved, QgsRasterLayer):
            raise RuntimeError("Could not resolve temporary raster output.")
        return resolved

    def _ensure_fields(self, layer):
        to_add = []
        if layer.fields().indexFromName("fs_culture") < 0:
            to_add.append(QgsField("fs_culture", QVariant.String, "string", 20))
        if layer.fields().indexFromName("fs_period") < 0:
            to_add.append(QgsField("fs_period", QVariant.String, "string", 20))
        if layer.fields().indexFromName("fs_model") < 0:
            to_add.append(QgsField("fs_model", QVariant.String, "string", 24))
        if layer.fields().indexFromName("fs_conf") < 0:
            to_add.append(QgsField("fs_conf", QVariant.Double, "double", 6, 3))
        if layer.fields().indexFromName("fs_note") < 0:
            to_add.append(QgsField("fs_note", QVariant.String, "string", 80))
        if layer.fields().indexFromName("fs_reason") < 0:
            to_add.append(QgsField("fs_reason", QVariant.String, "string", 1024))
        if layer.fields().indexFromName("fs_water_m") < 0:
            to_add.append(QgsField("fs_water_m", QVariant.Double, "double", 12, 3))
        if layer.fields().indexFromName("fs_slope") < 0:
            to_add.append(QgsField("fs_slope", QVariant.Double, "double", 6, 3))
        if layer.fields().indexFromName("fs_aspect") < 0:
            to_add.append(QgsField("fs_aspect", QVariant.Double, "double", 6, 3))
        if layer.fields().indexFromName("fs_form") < 0:
            to_add.append(QgsField("fs_form", QVariant.Double, "double", 6, 3))
        if layer.fields().indexFromName("fs_long") < 0:
            to_add.append(QgsField("fs_long", QVariant.Double, "double", 6, 3))
        if layer.fields().indexFromName("fs_demwtr") < 0:
            to_add.append(QgsField("fs_demwtr", QVariant.Double, "double", 6, 3))
        if layer.fields().indexFromName("fs_tpi") < 0:
            to_add.append(QgsField("fs_tpi", QVariant.Double, "double", 7, 4))
        if layer.fields().indexFromName("fs_conv") < 0:
            to_add.append(QgsField("fs_conv", QVariant.Double, "double", 6, 3))
        if layer.fields().indexFromName("fs_water") < 0:
            to_add.append(QgsField("fs_water", QVariant.Double, "double", 6, 3))
        if layer.fields().indexFromName("fs_score") < 0:
            to_add.append(QgsField("fs_score", QVariant.Double, "double", 7, 3))
        if layer.fields().indexFromName("fs_sashinsa") < 0:
            to_add.append(QgsField("fs_sashinsa", QVariant.Double, "double", 6, 3))
        if layer.fields().indexFromName("fs_enclosure") < 0:
            to_add.append(QgsField("fs_enclosure", QVariant.Double, "double", 6, 3))
        if layer.fields().indexFromName("fs_tpi_lg") < 0:
            to_add.append(QgsField("fs_tpi_lg", QVariant.Double, "double", 7, 4))
        if layer.fields().indexFromName("fs_roughness") < 0:
            to_add.append(QgsField("fs_roughness", QVariant.Double, "double", 6, 3))
        if layer.fields().indexFromName("fs_cut_depth") < 0:
            to_add.append(QgsField("fs_cut_depth", QVariant.Double, "double", 6, 3))

        if to_add:
            layer.dataProvider().addAttributes(to_add)
            layer.updateFields()

    def _annotate_calibration_layer(
        self,
        layer,
        score_by_id=None,
        best_f1_threshold=None,
        best_youden_threshold=None,
    ):
        if layer is None:
            return

        to_add = []
        if layer.fields().indexFromName("cal_score") < 0:
            to_add.append(QgsField("cal_score", QVariant.Double, "double", 7, 3))
        if layer.fields().indexFromName("cal_f1_th") < 0:
            to_add.append(QgsField("cal_f1_th", QVariant.Double, "double", 7, 3))
        if layer.fields().indexFromName("cal_yj_th") < 0:
            to_add.append(QgsField("cal_yj_th", QVariant.Double, "double", 7, 3))
        if layer.fields().indexFromName("cal_f1_ok") < 0:
            to_add.append(QgsField("cal_f1_ok", QVariant.Int))
        if layer.fields().indexFromName("cal_yj_ok") < 0:
            to_add.append(QgsField("cal_yj_ok", QVariant.Int))
        if to_add:
            layer.dataProvider().addAttributes(to_add)
            layer.updateFields()

        with edit(layer):
            for feature in layer.getFeatures():
                field_names = feature.fields().names()
                row_id = self._calibration_row_id(feature, field_names)
                score = None
                if isinstance(score_by_id, dict) and row_id in score_by_id:
                    score = score_by_id.get(row_id)
                if score is None and "fs_score" in field_names:
                    score = self._to_float(feature["fs_score"])
                feature["cal_score"] = score
                feature["cal_f1_th"] = best_f1_threshold
                feature["cal_yj_th"] = best_youden_threshold
                feature["cal_f1_ok"] = (
                    int(score >= best_f1_threshold)
                    if score is not None and best_f1_threshold is not None
                    else None
                )
                feature["cal_yj_ok"] = (
                    int(score >= best_youden_threshold)
                    if score is not None and best_youden_threshold is not None
                    else None
                )
                layer.updateFeature(feature)

    @staticmethod
    def _normalized_weight_map(weights):
        return normalized_weight_map(weights)

    @staticmethod
    def _calibration_row_id(feature, field_names=None):
        names = field_names or feature.fields().names()
        if "cal_id" in names:
            try:
                return int(feature["cal_id"])
            except (TypeError, ValueError):
                pass
        return int(feature.id())

    @staticmethod
    def _calibration_profile_parameters(profile):
        return calibration_profile_parameters(profile)

    def _calibration_raw_value(self, feature, key, field_names=None):
        names = list(field_names or feature.fields().names())
        if key == "slope":
            field_name = next((name for name in names if name.startswith("sl_")), None)
            if field_name:
                return self._to_float(feature[field_name])
            return None
        if key == "tpi" and "fs_tpi" in names:
            return self._to_float(feature["fs_tpi"])
        return None

    def _calibration_indicator_value(self, feature, key, profile, field_names=None):
        names = set(field_names or feature.fields().names())
        direct_fields = {
            "slope": "fs_slope",
            "aspect": "fs_aspect",
            "form": "fs_form",
            "long": "fs_long",
            "water": "fs_water",
            "conv": "fs_conv",
            "sashinsa": "fs_sashinsa",
            "enclosure": "fs_enclosure",
        }
        if key == "tpi":
            if "fs_tpi" not in names:
                return None
            raw_tpi = self._to_float(feature["fs_tpi"])
            if raw_tpi is None:
                return None
            return self._score_profile_tpi(raw_tpi, profile)

        field_name = direct_fields.get(key)
        if not field_name or field_name not in names:
            return None
        return self._to_float(feature[field_name])

    def _calibration_row_indicator(self, row, key, profile):
        raw_values = row.get("raw", {})
        if key == "slope":
            raw_slope = raw_values.get("slope")
            if raw_slope is not None:
                return self._score_profile_slope(raw_slope, profile)
        if key == "tpi":
            raw_tpi = raw_values.get("tpi")
            if raw_tpi is not None:
                return self._score_profile_tpi(raw_tpi, profile)
        return row.get("indicators", {}).get(key)

    def _calibration_rows(self, layer, profile):
        rows = []
        if layer is None or not isinstance(profile, dict):
            return rows
        weight_keys = list(profile.get("weights", {}).keys())
        for feature in layer.getFeatures():
            field_names = feature.fields().names()
            if "fs_label" not in field_names:
                continue
            label = feature["fs_label"]
            try:
                label = int(label)
            except (TypeError, ValueError):
                continue
            if label not in (0, 1):
                continue
            raw_values = {
                "slope": self._calibration_raw_value(feature, "slope", field_names),
                "tpi": self._calibration_raw_value(feature, "tpi", field_names),
            }
            indicators = {
                key: self._calibration_indicator_value(feature, key, profile, field_names)
                for key in weight_keys
            }
            if not any(value is not None for value in indicators.values()):
                continue
            rows.append(
                {
                    "row_id": self._calibration_row_id(feature, field_names),
                    "label": label,
                    "raw": raw_values,
                    "indicators": indicators,
                }
            )
        return rows

    def _evaluate_calibration_rows(self, rows, profile):
        labels = []
        scores = []
        score_by_id = {}
        if not isinstance(profile, dict):
            return self._binary_classification_metrics([], []), score_by_id
        normalized = self._normalized_weight_map(profile.get("weights", {}))
        if not rows or not normalized:
            return self._binary_classification_metrics([], []), score_by_id

        for row in rows:
            weighted = []
            for key, weight in normalized.items():
                value = self._calibration_row_indicator(row, key, profile)
                if value is None:
                    continue
                weighted.append((weight, float(value)))
            if not weighted:
                continue
            numerator = sum(weight * value for weight, value in weighted)
            denominator = sum(weight for weight, _value in weighted)
            if denominator <= 0:
                continue
            score = numerator / denominator
            labels.append(int(row["label"]))
            scores.append(float(score))
            score_by_id[row["row_id"]] = float(score)
        return self._binary_classification_metrics(labels, scores), score_by_id

    def _indicator_discrimination(self, rows, key, profile):
        labels = []
        scores = []
        positives = []
        negatives = []
        for row in rows:
            value = self._calibration_row_indicator(row, key, profile)
            if value is None:
                continue
            value = float(value)
            label = int(row["label"])
            labels.append(label)
            scores.append(value)
            if label == 1:
                positives.append(value)
            else:
                negatives.append(value)
        metrics = self._binary_classification_metrics(labels, scores)
        pos_mean = sum(positives) / len(positives) if positives else None
        neg_mean = sum(negatives) / len(negatives) if negatives else None
        roc_auc = float(metrics.get("roc_auc", 0.0))
        quality = max(0.0, min(1.0, (roc_auc - 0.5) * 2.0))
        return {
            "count": metrics.get("count", 0),
            "roc_auc": roc_auc,
            "pr_auc": float(metrics.get("pr_auc", 0.0)),
            "positive_mean": pos_mean,
            "negative_mean": neg_mean,
            "quality": quality,
        }

    @staticmethod
    def _metrics_better(candidate, baseline, tolerance=1e-6):
        return metrics_better(candidate, baseline, tolerance=tolerance)

    @staticmethod
    def _distribution_stats(values):
        return distribution_stats(values)

    @staticmethod
    def _unique_float_candidates(values, min_value=None, max_value=None):
        return unique_float_candidates(
            values,
            min_value=min_value,
            max_value=max_value,
        )

    def _raw_calibration_stats(self, rows, key):
        return raw_calibration_stats(rows, key)

    def _parameter_candidates(
        self,
        rows,
        key,
        base_target,
        base_sigma,
        sigma_floor,
    ):
        return parameter_candidates(
            rows,
            key,
            base_target,
            base_sigma,
            sigma_floor,
        )

    def _parameter_candidate_profiles(self, rows, profile):
        return parameter_candidate_profiles(rows, profile, max_candidates=24)

    def _fit_profile_weight_candidates(self, rows, profile, random_seed=42):
        base_weights = self._normalized_weight_map(profile.get("weights", {}))
        working_profile = dict(profile)
        working_profile["weights"] = dict(base_weights)
        candidate_metrics, candidate_scores_by_id = self._evaluate_calibration_rows(
            rows,
            working_profile,
        )
        if not rows or not base_weights:
            return {
                "profile": working_profile,
                "weights": base_weights,
                "weight_deltas": {},
                "weight_summary": "no-material-weight-change",
                "indicator_discrimination": {},
                "metrics": candidate_metrics,
                "scores_by_id": candidate_scores_by_id,
                "weight_applied": False,
            }

        available_keys = [
            key
            for key in base_weights.keys()
            if any(self._calibration_row_indicator(row, key, working_profile) is not None for row in rows)
        ]
        base_weights = self._normalized_weight_map(
            {key: base_weights.get(key, 0.0) for key in available_keys}
        )
        working_profile["weights"] = dict(base_weights)
        base_metrics, base_scores_by_id = self._evaluate_calibration_rows(rows, working_profile)

        indicator_discrimination = {
            key: self._indicator_discrimination(rows, key, working_profile)
            for key in available_keys
        }
        heuristic_weights = {}
        for key in available_keys:
            quality = indicator_discrimination[key]["quality"]
            heuristic_weights[key] = base_weights.get(key, 0.0) * (0.20 + quality)
        heuristic_weights = self._normalized_weight_map(heuristic_weights) or dict(base_weights)

        candidates = [dict(base_weights), dict(heuristic_weights)]
        ranked_keys = sorted(
            available_keys,
            key=lambda item: indicator_discrimination[item]["quality"],
            reverse=True,
        )
        for focus_key in ranked_keys[: min(3, len(ranked_keys))]:
            focused = {}
            for key in available_keys:
                focus_scale = 1.8 if key == focus_key else 0.55
                quality_scale = 0.35 + indicator_discrimination[key]["quality"]
                focused[key] = base_weights.get(key, 0.0) * focus_scale * quality_scale
            normalized_focused = self._normalized_weight_map(focused)
            if normalized_focused:
                candidates.append(normalized_focused)

        rng = random.Random(int(random_seed))
        trial_count = max(48, len(available_keys) * 20)
        for _ in range(trial_count):
            trial_weights = {}
            for key in available_keys:
                quality = indicator_discrimination[key]["quality"]
                jitter = 0.40 + (rng.random() * 1.80)
                trial_weights[key] = (
                    base_weights.get(key, 0.0) * jitter * (0.25 + quality)
                )
            normalized_trial = self._normalized_weight_map(trial_weights)
            if normalized_trial:
                candidates.append(normalized_trial)

        best_weights = dict(base_weights)
        best_metrics = dict(base_metrics)
        best_scores_by_id = dict(base_scores_by_id)
        for candidate in candidates:
            trial_profile = dict(working_profile)
            trial_profile["weights"] = dict(candidate)
            candidate_metrics, candidate_scores_by_id = self._evaluate_calibration_rows(
                rows,
                trial_profile,
            )
            if self._metrics_better(candidate_metrics, best_metrics):
                best_weights = dict(candidate)
                best_metrics = dict(candidate_metrics)
                best_scores_by_id = dict(candidate_scores_by_id)

        weight_applied = self._metrics_better(best_metrics, base_metrics)
        final_weights = dict(best_weights if weight_applied else base_weights)
        final_metrics = dict(best_metrics if weight_applied else base_metrics)
        final_scores_by_id = dict(best_scores_by_id if weight_applied else base_scores_by_id)

        weight_deltas = {
            key: final_weights.get(key, 0.0) - base_weights.get(key, 0.0)
            for key in available_keys
        }
        weight_summary = summarize_named_deltas(
            weight_deltas,
            threshold=0.01,
            limit=3,
            empty_label="no-material-weight-change",
        )

        return {
            "profile": dict(working_profile, weights=final_weights),
            "weights": final_weights,
            "weight_deltas": weight_deltas,
            "weight_summary": weight_summary,
            "indicator_discrimination": indicator_discrimination,
            "metrics": final_metrics,
            "scores_by_id": final_scores_by_id,
            "weight_applied": weight_applied,
        }

    def _fit_local_calibration_weights(self, layer, profile, random_seed=42):
        base_profile = dict(profile if isinstance(profile, dict) else {})
        base_profile["weights"] = dict(
            self._normalized_weight_map(base_profile.get("weights", {}))
        )
        rows = self._calibration_rows(layer, base_profile)
        fit_rows, evaluation_rows, split_plan = split_calibration_rows(
            rows=rows,
            random_seed=random_seed,
            split_ratio=0.75,
            min_fit_count=6,
            min_eval_count=3,
        )
        base_metrics, base_scores_by_id = self._evaluate_calibration_rows(
            fit_rows,
            base_profile,
        )
        validation_enabled = bool(split_plan.get("validation_enabled", False))
        if validation_enabled and evaluation_rows:
            base_evaluation_metrics, base_evaluation_scores_by_id = (
                self._evaluate_calibration_rows(
                    evaluation_rows,
                    base_profile,
                )
            )
        else:
            base_evaluation_metrics = dict(base_metrics)
            base_evaluation_scores_by_id = dict(base_scores_by_id)
        base_profile_parameters = self._calibration_profile_parameters(base_profile)
        if not fit_rows or not base_profile["weights"]:
            return empty_calibration_fit(
                base_profile=base_profile,
                base_profile_parameters=base_profile_parameters,
                base_metrics=base_metrics,
                base_scores_by_id=base_scores_by_id,
            )

        best_fit = {
            "profile": dict(base_profile),
            "weights": dict(base_profile["weights"]),
            "weight_deltas": {
                key: 0.0 for key in base_profile["weights"].keys()
            },
            "weight_summary": "no-material-weight-change",
            "indicator_discrimination": {
                key: self._indicator_discrimination(fit_rows, key, base_profile)
                for key in base_profile["weights"].keys()
                if any(
                    self._calibration_row_indicator(row, key, base_profile) is not None
                    for row in fit_rows
                )
            },
            "metrics": dict(base_metrics),
            "scores_by_id": dict(base_scores_by_id),
            "weight_applied": False,
        }
        for index, candidate_profile in enumerate(
            self._parameter_candidate_profiles(fit_rows, base_profile)
        ):
            candidate_fit = self._fit_profile_weight_candidates(
                fit_rows,
                candidate_profile,
                random_seed=random_seed + index,
            )
            if self._metrics_better(candidate_fit["metrics"], best_fit["metrics"]):
                best_fit = candidate_fit

        if validation_enabled:
            final_profile_for_evaluation = dict(best_fit.get("profile", {}))
            final_profile_for_evaluation["weights"] = dict(
                best_fit.get("weights", {})
            )
            best_fit["evaluation_metrics"], best_fit["evaluation_scores_by_id"] = (
                self._evaluate_calibration_rows(
                    evaluation_rows,
                    final_profile_for_evaluation,
                )
            )
            applied = self._metrics_better(
                best_fit["evaluation_metrics"],
                base_evaluation_metrics,
            )
            if not applied:
                best_fit["evaluation_metrics"] = dict(base_evaluation_metrics)
                best_fit["evaluation_scores_by_id"] = dict(
                    base_evaluation_scores_by_id
                )
        else:
            applied = False
        best_fit = dict(best_fit)
        best_fit["validation_plan"] = dict(split_plan or {})
        best_fit["fit_rows"] = list(fit_rows)
        best_fit["evaluation_rows"] = list(evaluation_rows)
        best_fit["validation_enabled"] = validation_enabled
        best_fit["final_profile_for_evaluation"] = dict(best_fit.get("profile", {}))
        if not validation_enabled:
            best_fit["evaluation_metrics"] = dict(base_evaluation_metrics)
            best_fit["evaluation_scores_by_id"] = dict(base_evaluation_scores_by_id)
        return finalize_calibration_fit(
            base_profile=base_profile,
            base_profile_parameters=base_profile_parameters,
            base_metrics=base_metrics,
            base_scores_by_id=base_scores_by_id,
            best_fit=best_fit,
            applied=applied,
            base_fit_scores_by_id=base_scores_by_id,
            evaluation_base_metrics=base_evaluation_metrics,
            evaluation_scores_by_id=best_fit.get("evaluation_scores_by_id", {}),
            validation_enabled=validation_enabled,
            split_plan=split_plan,
        )

    def _score_points(
        self,
        site_layer,
        dem_layer,
        water_layer,
        hemisphere,
        profile_key,
        context,
        profile=None,
    ):
        slope_field = self._find_field(site_layer, "sl_")
        aspect_field = self._find_field(site_layer, "as_")
        dem_crs = dem_layer.crs()
        site_to_dem = self._build_transform(site_layer.crs(), dem_crs)
        water_index, water_geoms = self._prepare_water_reference(
            dem_layer=dem_layer,
            water_layer=water_layer,
        )

        dem_provider = dem_layer.dataProvider()
        dem_step = self._dem_step(dem_layer)
        if profile is None:
            profile = self._contextualize_profile(
                self._profile_spec(profile_key),
                context,
                profile_key,
            )

        with edit(site_layer):
            for feature in site_layer.getFeatures():
                slope_value = self._to_float(feature[slope_field]) if slope_field else None
                aspect_value = self._to_float(feature[aspect_field]) if aspect_field else None
                feature_geom = feature.geometry() if feature.hasGeometry() else None
                site_geom_dem = self._transform_geometry(feature_geom, site_to_dem)
                site_point = self._geometry_point(site_geom_dem)

                dem_metrics = self._compute_dem_metrics(
                    provider=dem_provider,
                    site_point=site_point,
                    slope_deg=slope_value,
                    hemisphere=hemisphere,
                    dem_step=dem_step,
                    context=context,
                )

                water_distance = self._nearest_water_distance(
                    site_geom=site_geom_dem,
                    site_point=site_point,
                    water_index=water_index,
                    water_geoms=water_geoms,
                )

                distance_water_score = self._score_water_distance(
                    water_distance,
                    context=context,
                )
                water_score = self._combine_hydro_scores(
                    distance_score=distance_water_score,
                    dem_score=dem_metrics["dem_water_score"],
                )

                indicators = {
                    "slope":     self._score_profile_slope(slope_value, profile),
                    "aspect":    self._score_aspect(aspect_value, hemisphere, context=context),
                    "form":      dem_metrics["form_score"],
                    "long":      dem_metrics["long_score"],
                    "water":     water_score,
                    "conv":      dem_metrics["convergence"],
                    "tpi":       self._score_profile_tpi(dem_metrics["tpi_norm"], profile),
                    "sashinsa":  dem_metrics.get("sashinsa_score"),
                    "enclosure": dem_metrics.get("enclosure_index"),
                }

                total_score = self._profile_weighted_score(indicators, profile)
                confidence = self._profile_confidence(indicators, profile)
                principle_records = build_principle_records(
                    indicators=indicators,
                    dem_metrics=dem_metrics,
                    water_distance=water_distance,
                )
                principle_note = build_principle_note(principle_records)
                principle_summary = build_principle_summary(principle_records)
                weight_note = self._explain_top_factors(indicators, profile)
                reason_ko = self._compose_site_reason(
                    profile_key=profile_key,
                    context=context,
                    profile=profile,
                    indicators=indicators,
                    dem_metrics=dem_metrics,
                    water_distance=water_distance,
                    slope_value=slope_value,
                    aspect_value=aspect_value,
                    total_score=total_score,
                    principle_summary=principle_summary,
                    weight_note=weight_note,
                )

                feature["fs_culture"] = context["culture_key"]
                feature["fs_period"] = context["period_key"]
                feature["fs_model"] = profile_key
                feature["fs_conf"] = confidence
                feature["fs_note"] = principle_note
                feature["fs_reason"] = reason_ko
                feature["fs_water_m"] = water_distance
                feature["fs_slope"] = indicators["slope"]
                feature["fs_aspect"] = indicators["aspect"]
                feature["fs_form"] = indicators["form"]
                feature["fs_long"] = indicators["long"]
                feature["fs_demwtr"] = dem_metrics["dem_water_score"]
                feature["fs_tpi"] = dem_metrics["tpi_norm"]
                feature["fs_conv"] = dem_metrics["convergence"]
                feature["fs_water"] = indicators["water"]
                feature["fs_score"] = total_score
                feature["fs_sashinsa"]  = dem_metrics.get("sashinsa_score")
                feature["fs_enclosure"] = dem_metrics.get("enclosure_index")
                feature["fs_tpi_lg"]    = dem_metrics.get("large_tpi_norm")
                feature["fs_roughness"] = dem_metrics.get("roughness")
                feature["fs_cut_depth"] = dem_metrics.get("cut_depth")
                site_layer.updateFeature(feature)

    @classmethod
    def _profile_spec(cls, profile_key):
        return profile_spec(profile_key)

    def _prepare_water_reference(self, dem_layer, water_layer):
        project = self.context.project() if self.context is not None else None
        if project is None:
            project = QgsProject.instance()
        return prepare_water_reference(
            dem_layer=dem_layer,
            water_layer=water_layer,
            project=project,
        )

    @staticmethod
    def _contextualize_profile(profile, context, profile_key="profile"):
        paper_evidence = profile.get("paper_evidence", {})
        if not isinstance(paper_evidence, dict):
            paper_evidence = {}

        def _to_float_entry(value, context_path):
            if value is None:
                raise ValueError(f"{context_path} is required.")
            if isinstance(value, dict):
                raw_value = value.get("value", value)
                if raw_value is None:
                    raise ValueError(f"{context_path}.value is required.")
                sources = value.get("source_doi", [])
                evidence_level = str(value.get("evidence_level", "U")).strip().upper()
                note = str(value.get("note", "")).strip()
            else:
                raw_value = value
                sources = []
                evidence_level = "U"
                note = ""

            if not isinstance(sources, list):
                sources = [sources]
            normalized_sources = []
            for source in sources:
                source_text = str(source or "").strip()
                if source_text:
                    normalized_sources.append(source_text)

            try:
                return float(raw_value), {
                    "source_doi": normalized_sources,
                    "evidence_level": evidence_level if evidence_level else "U",
                    "note": note,
                }
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{context_path} must be numeric.") from exc

        adjusted = {
            "weights": dict(profile["weights"]),
            "term_bias": {},
            "slope_target": profile["slope_target"],
            "slope_sigma": profile["slope_sigma"],
            "tpi_target": profile["tpi_target"],
            "tpi_sigma": profile["tpi_sigma"],
        }
        paper_records = []

        for key, delta in context.get("weight_bias", {}).items():
            adjusted["weights"][key] = max(
                0.0, adjusted["weights"].get(key, 0.0) + float(delta)
            )

        evidence_weight_bias = paper_evidence.get("weight_bias", {})
        if not isinstance(evidence_weight_bias, dict):
            evidence_weight_bias = {}
        for key, entry in evidence_weight_bias.items():
            try:
                delta, meta = _to_float_entry(
                    entry,
                    f"profiles.{profile_key}.paper_evidence.weight_bias.{key}",
                )
            except ValueError:
                continue
            adjusted["weights"][key] = max(
                0.0, adjusted["weights"].get(key, 0.0) + delta
            )
            paper_records.append(
                {
                    "group": "weight_bias",
                    "name": key,
                    "value": delta,
                    "source_doi": meta.get("source_doi", []),
                    "evidence_level": meta.get("evidence_level", "U"),
                    "note": meta.get("note", ""),
                }
            )

        evidence_term_bias = paper_evidence.get("term_bias", {})
        if not isinstance(evidence_term_bias, dict):
            evidence_term_bias = {}
        for key, entry in evidence_term_bias.items():
            try:
                delta, meta = _to_float_entry(
                    entry,
                    f"profiles.{profile_key}.paper_evidence.term_bias.{key}",
                )
            except ValueError:
                continue
            adjusted["term_bias"][key] = delta
            paper_records.append(
                {
                    "group": "term_bias",
                    "name": key,
                    "value": delta,
                    "source_doi": meta.get("source_doi", []),
                    "evidence_level": meta.get("evidence_level", "U"),
                    "note": meta.get("note", ""),
                }
            )

        target_override = paper_evidence.get("target_overrides", {})
        if not isinstance(target_override, dict):
            target_override = {}
        for key in ("slope_target", "slope_sigma", "tpi_target", "tpi_sigma"):
            if key not in target_override and key in paper_evidence:
                target_override[key] = paper_evidence[key]
            entry = target_override.get(key)
            if entry is None:
                continue
            try:
                value, meta = _to_float_entry(
                    entry, f"profiles.{profile_key}.paper_evidence.{key}"
                )
            except ValueError:
                continue
            adjusted[key] = value
            paper_records.append(
                {
                    "group": "target",
                    "name": key,
                    "value": value,
                    "source_doi": meta.get("source_doi", []),
                    "evidence_level": meta.get("evidence_level", "U"),
                    "note": meta.get("note", ""),
                }
            )

        total = sum(adjusted["weights"].values())
        if total > 0:
            adjusted["weights"] = {
                key: value / total for key, value in adjusted["weights"].items()
            }

        if paper_records:
            adjusted["paper_evidence_records"] = paper_records
        return adjusted

    @staticmethod
    def _find_field(layer, prefix):
        for field in layer.fields():
            if field.name().startswith(prefix):
                return field.name()
        return None

    @staticmethod
    def _to_float(value):
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _metadata_text(value):
        return metadata_text(value)

    def _metadata_field_name(self, layer, candidates):
        return metadata_field_name(layer, candidates)

    def _metadata_grouping(self, layer, kind, candidates, limit=8):
        return metadata_grouping(layer, kind, candidates, limit=limit)

    def _summarize_site_metadata(self, layer):
        return summarize_site_metadata(layer)

    def _build_transform(self, source_crs, target_crs):
        project = self.context.project() if self.context is not None else None
        if project is None:
            project = QgsProject.instance()
        return build_transform(source_crs, target_crs, project)

    @staticmethod
    def _transform_point(point, transformer):
        return transform_point(point, transformer)

    @staticmethod
    def _transform_geometry(geometry, transformer):
        return transform_geometry(geometry, transformer)

    @staticmethod
    def _geometry_point(geometry):
        return geometry_point(geometry)

    @staticmethod
    def _feature_point(feature):
        return feature_point(feature)

    def _collect_points(self, layer, target_crs=None):
        project = self.context.project() if self.context is not None else None
        if project is None:
            project = QgsProject.instance()
        return collect_points(layer=layer, target_crs=target_crs, project=project)

    def _sample_negative_points(
        self,
        dem_layer,
        positive_points,
        target_count,
        random_seed=42,
    ):
        provider = dem_layer.dataProvider()
        extent = dem_layer.extent()
        dem_step = self._dem_step(dem_layer)
        calibration_rules = self._rules_section("calibration")
        local_padding_factor = self._rule_float(
            calibration_rules,
            "local_bbox_padding_factor",
            1.25,
            min_value=0.0,
        )
        local_padding_cells = self._rule_float(
            calibration_rules,
            "local_bbox_min_padding_cells",
            24.0,
            min_value=1.0,
        )
        trial_multiplier = self._rule_int(
            calibration_rules,
            "trial_multiplier",
            120,
            min_value=10,
        )
        rng = random.Random(random_seed)
        points = []
        trial_cap = max(target_count * trial_multiplier, 3000)
        sampling_plan = negative_sampling_plan(
            dem_step=dem_step,
            extent_bounds=(
                extent.xMinimum(),
                extent.xMaximum(),
                extent.yMinimum(),
                extent.yMaximum(),
            ),
            positive_xy=[(point.x(), point.y()) for point in positive_points],
            local_padding_factor=local_padding_factor,
            local_padding_cells=local_padding_cells,
        )
        min_distance_sq = sampling_plan["min_distance_sq"]
        min_negative_separation_sq = sampling_plan["min_negative_separation_sq"]
        search_windows = sampling_plan["search_windows"]

        def sample_from_window(window, max_trials):
            trial = 0
            x_min, x_max, y_min, y_max = window
            if x_max <= x_min or y_max <= y_min:
                return

            while len(points) < target_count and trial < max_trials:
                trial += 1
                x = rng.uniform(x_min, x_max)
                y = rng.uniform(y_min, y_max)
                point = QgsPointXY(x, y)
                if self._sample_dem(provider, point) is None:
                    continue

                reject = False
                for positive in positive_points:
                    dx = x - positive.x()
                    dy = y - positive.y()
                    if (dx * dx) + (dy * dy) < min_distance_sq:
                        reject = True
                        break
                if reject:
                    continue

                for negative in points[-200:]:
                    dx = x - negative.x()
                    dy = y - negative.y()
                    if (dx * dx) + (dy * dy) < min_negative_separation_sq:
                        reject = True
                        break
                if reject:
                    continue
                points.append(point)

        for window in search_windows:
            sample_from_window(window, trial_cap)
            if len(points) >= target_count:
                break
        return points

    @staticmethod
    def _build_calibration_input_layer(
        site_layer,
        dem_layer,
        positive_points,
        negative_points,
    ):
        layer = QgsVectorLayer(
            f"Point?crs={dem_layer.crs().authid()}",
            f"{site_layer.name()}_calibration_input",
            "memory",
        )
        data = layer.dataProvider()
        fields = QgsFields()
        fields.append(QgsField("cal_id", QVariant.Int))
        fields.append(QgsField("fs_label", QVariant.Int))
        fields.append(QgsField("fs_group", QVariant.String, "string", 8))
        data.addAttributes(fields)
        layer.updateFields()

        features = []
        running = 1
        for point in positive_points:
            feature = QgsFeature(layer.fields())
            feature.setGeometry(QgsGeometry.fromPointXY(point))
            feature["cal_id"] = running
            feature["fs_label"] = 1
            feature["fs_group"] = "positive"
            features.append(feature)
            running += 1
        for point in negative_points:
            feature = QgsFeature(layer.fields())
            feature.setGeometry(QgsGeometry.fromPointXY(point))
            feature["cal_id"] = running
            feature["fs_label"] = 0
            feature["fs_group"] = "negative"
            features.append(feature)
            running += 1

        if features:
            data.addFeatures(features)
        layer.updateExtents()
        return layer

    @staticmethod
    def _dem_step(dem_layer):
        return dem_step(dem_layer)

    def _nearest_water_distance(self, site_geom, site_point, water_index, water_geoms):
        return nearest_water_distance(site_geom, site_point, water_index, water_geoms)

    @staticmethod
    def _score_gaussian(value, target, sigma):
        return score_gaussian(value, target, sigma)

    @staticmethod
    def _score_aspect(aspect_deg, hemisphere, context=None):
        return score_aspect(aspect_deg, hemisphere, context=context)

    @staticmethod
    def _score_water_distance(distance_m, context=None):
        return score_water_distance(distance_m, context=context)

    def _score_profile_slope(self, slope_deg, profile):
        if slope_deg is None:
            return None
        return self._score_gaussian(
            slope_deg,
            profile["slope_target"],
            profile["slope_sigma"],
        )

    def _score_profile_tpi(self, tpi_norm, profile):
        return self._score_gaussian(
            tpi_norm,
            profile["tpi_target"],
            profile["tpi_sigma"],
        )

    def _compute_dem_metrics(
        self,
        provider,
        site_point,
        slope_deg,
        hemisphere,
        dem_step,
        context=None,
    ):
        null_metrics = null_dem_metrics()
        if site_point is None:
            return null_metrics

        center = self._sample_dem(provider, site_point)
        if center is None:
            return null_metrics

        sampling_rules = self._rules_section("sampling")
        dem_rules = self._rules_section("dem_metrics")

        sampling_state = sampling_setup(
            dem_step=dem_step,
            sampling_rules=sampling_rules,
            context=context,
        )
        micro_radius = sampling_state["micro_radius"]
        macro_radius = sampling_state["macro_radius"]
        macro_bearings = sampling_state["macro_bearings"]
        micro_bearings = sampling_state["micro_bearings"]

        macro_values = self._sample_ring(provider, site_point, macro_radius, macro_bearings)
        micro_values = self._sample_ring(provider, site_point, micro_radius, micro_bearings)

        stats = relief_statistics(
            macro_values=macro_values,
            micro_values=micro_values,
            stddev_fn=self._stddev,
        )
        relief = stats["relief"]
        mean_macro = stats["mean_macro"]
        std_macro = stats["std_macro"]
        std_micro = stats["std_micro"]

        card = self.CARDINALS.get(hemisphere, self.CARDINALS["north"])
        back_mean = self._direction_mean(provider, site_point, macro_radius, card["back"])
        front_mean = self._direction_mean(provider, site_point, macro_radius, card["front"])
        left_mean = self._direction_mean(provider, site_point, macro_radius, card["left"])
        right_mean = self._direction_mean(provider, site_point, macro_radius, card["right"])

        form_score = compute_form_score(
            center=center,
            relief=relief,
            back_mean=back_mean,
            front_mean=front_mean,
            left_mean=left_mean,
            right_mean=right_mean,
            dem_rules=dem_rules,
            score_gaussian=self._score_gaussian,
            mean_scores=self._mean_scores,
        )

        long_score, tpi_norm = compute_long_score(
            center=center,
            relief=relief,
            mean_macro=mean_macro,
            std_micro=std_micro,
            std_macro=std_macro,
            dem_rules=dem_rules,
            score_gaussian=self._score_gaussian,
            mean_scores=self._mean_scores,
        )

        dem_water_score, convergence = compute_dem_water_score(
            center=center,
            micro_values=micro_values,
            slope_deg=slope_deg,
            dem_rules=dem_rules,
            score_gaussian=self._score_gaussian,
        )

        # ── 사신사(四神砂) 포위도 ──────────────────────────────────────
        # 참고: Um 2012 IntechOpen (한국 묘지 공간회귀);
        #       ISPRS IJGI 10(11):752 2021 Nanjing (砂→surface_peaks);
        #       Buildings 15(5):800 2025 Jimei (viewshed 사신사)
        sashinsa_score = None
        try:
            sashinsa_score = compute_sashinsa_score(
                center=center,
                relief=relief,
                back_mean=back_mean,
                front_mean=front_mean,
                left_mean=left_mean,
                right_mean=right_mean,
                sashinsa_rules=self._rules_section("sashinsa"),
                score_gaussian=self._score_gaussian,
            )
        except RuntimeError:
            pass

        # ── 장풍(藏風) 포위도 지수 ────────────────────────────────────
        # 참고: Guan et al. 2024 Springer (하카마을 AHP-GIS 장풍득수);
        #       ISPRS IJGI 10(11):752 2021 (surface roughness → 龍 지표)
        enclosure_index = None
        try:
            enclosure_index = compute_enclosure_index(
                center=center,
                macro_values=macro_values,
                enclosure_rules=self._rules_section("enclosure"),
                score_gaussian=self._score_gaussian,
            )
        except RuntimeError:
            pass

        # ── 대규모 TPI (이중 스케일) ───────────────────────────────────
        # 참고: Um 2012 IntechOpen (Palgong Mountain 국지·광역 지형 위치);
        #       Lee & Kim 2021 PLOS ONE e0259651 (한반도 이중-TPI 지형 분류);
        #       Weiss 2001 ESRI (TPI 원본 방법론)
        large_tpi_norm = self._compute_large_tpi_value(
            provider=provider,
            site_point=site_point,
            center=center,
            macro_radius=macro_radius,
            relief=relief,
        )

        # ── 표면 조도 (Surface Roughness) ─────────────────────────────
        # 참고: ISPRS IJGI 10(11):752 2021 Nanjing (표면조도 → 龍 판별 인자)
        roughness = compute_roughness(std_macro, relief)

        # ── 지형 절개깊이 (Surface Cutting Depth) ────────────────────
        # 참고: ISPRS IJGI 10(11):752 2021 Nanjing (절개깊이 → 砂 판별 인자)
        cut_depth = compute_cut_depth(macro_values, center, relief)

        return {
            "form_score": form_score,
            "long_score": long_score,
            "dem_water_score": dem_water_score,
            "tpi_norm": tpi_norm,
            "convergence": convergence,
            "sashinsa_score": sashinsa_score,
            "enclosure_index": enclosure_index,
            "large_tpi_norm": large_tpi_norm,
            "roughness": roughness,
            "cut_depth": cut_depth,
        }

    @staticmethod
    def _sample_dem(provider, point):
        return sample_dem(provider, point)

    @staticmethod
    def _offset_point(point, distance, azimuth_deg):
        return offset_point(point, distance, azimuth_deg)

    def _sample_ring(self, provider, center_point, radius, azimuths):
        return sample_ring(provider, center_point, radius, azimuths)

    @staticmethod
    def _mean_scores(*values):
        return mean_scores(*values)

    @staticmethod
    def _fmt_num(value, digits=3):
        return fmt_num(value, digits=digits)

    @staticmethod
    def _azimuth_label(azimuth):
        return azimuth_label(azimuth)

    @staticmethod
    def _ridge_label(class_id, language="ko"):
        labels = RIDGE_CLASS_LABELS.get(class_id, {})
        if language == "en":
            return labels.get("en") or class_id
        return labels.get("ko") or class_id

    def _compose_term_reason(
        self,
        term_id,
        adjusted_score,
        base_score,
        elev,
        delta_rel,
        target_rel,
        fit_score,
        radius_m,
        azimuth,
        mode,
        note,
    ):
        return compose_term_reason(
            term_id=term_id,
            adjusted_score=adjusted_score,
            base_score=base_score,
            elev=elev,
            delta_rel=delta_rel,
            target_rel=target_rel,
            fit_score=fit_score,
            radius_m=radius_m,
            azimuth=azimuth,
            mode=mode,
            note=note,
        )

    @staticmethod
    def _score_band_label(value):
        return score_band_label(value)

    @staticmethod
    def _tpi_hint(tpi_norm):
        return tpi_hint(tpi_norm)

    def _compose_hyeol_reason(
        self,
        rank,
        selected_total,
        base_score,
        form_score,
        long_score,
        wet_score,
        tpi_norm,
        conv_score,
        relief,
        center_elev,
        threshold,
        water_distance=None,
        sashinsa_score=None,
        enclosure_index=None,
        large_tpi_norm=None,
    ):
        return compose_hyeol_reason(
            rank=rank,
            selected_total=selected_total,
            base_score=base_score,
            form_score=form_score,
            long_score=long_score,
            wet_score=wet_score,
            tpi_norm=tpi_norm,
            conv_score=conv_score,
            relief=relief,
            center_elev=center_elev,
            threshold=threshold,
            water_distance=water_distance,
            sashinsa_score=sashinsa_score,
            enclosure_index=enclosure_index,
            large_tpi_norm=large_tpi_norm,
        )

    @staticmethod
    def _stddev(values):
        return stddev(values)

    def _direction_mean(self, provider, center_point, radius, center_azimuth):
        return direction_mean(provider, center_point, radius, center_azimuth)

    @staticmethod
    def _combine_hydro_scores(distance_score, dem_score):
        return combine_hydro_scores(distance_score, dem_score)

    @classmethod
    def adaptive_spacing_diagnostics(cls, dem_layer, dem_step=None):
        if dem_step is None:
            dem_step = cls._dem_step(dem_layer)
        rules = cls._rules_section("adaptive_spacing")
        base_step_factor = cls._rule_float(
            rules, "base_step_factor", 10.0, min_value=0.1
        )
        min_span_divisor = cls._rule_float(
            rules, "min_span_divisor", 180.0, min_value=1.0
        )
        fallback_spacing = cls._rule_float(
            rules, "fallback_min_spacing", 1.0, min_value=0.1
        )
        max_points = cls._rule_int(rules, "max_points", 12000, min_value=50)

        extent = dem_layer.extent()
        width = max(0.0, float(extent.width()))
        height = max(0.0, float(extent.height()))
        return compute_adaptive_spacing_diagnostics(
            dem_step=dem_step,
            width=width,
            height=height,
            base_step_factor=base_step_factor,
            min_span_divisor=min_span_divisor,
            fallback_spacing=fallback_spacing,
            max_points=max_points,
        )

    def _adaptive_spacing(self, dem_layer, dem_step):
        return self.adaptive_spacing_diagnostics(dem_layer, dem_step)["spacing"]

    def _recommended_hyeol_count(self, dem_layer, spacing):
        rules = self._rules_section("hyeol_selection")
        thresholds = rules.get("recommended_count_thresholds", [])
        default_count = self._rule_int(
            rules, "default_recommended_count", 5, min_value=1
        )

        extent = dem_layer.extent()
        return recommended_hyeol_count(
            width=max(0.0, float(extent.width())),
            height=max(0.0, float(extent.height())),
            spacing=spacing,
            thresholds=thresholds,
            default_count=default_count,
        )

    @staticmethod
    def _grid_points(dem_layer, spacing):
        yield from grid_points(dem_layer.extent(), spacing)

    def _collect_hyeol_candidates(
        self,
        provider,
        dem_layer,
        hemisphere,
        dem_step,
        spacing,
        context,
        profile,
        slope_provider=None,
        aspect_provider=None,
        water_index=None,
        water_geoms=None,
    ):
        rules = self._rules_section("hyeol_candidate")
        tpi_min = float(rules["tpi_min"])
        tpi_max = float(rules["tpi_max"])
        candidates = []
        for point in self._grid_points(dem_layer, spacing):
            center = self._sample_dem(provider, point)
            if center is None:
                continue
            slope_value = (
                self._sample_dem(slope_provider, point)
                if slope_provider is not None
                else None
            )
            aspect_value = (
                self._sample_dem(aspect_provider, point)
                if aspect_provider is not None
                else None
            )

            metrics = self._compute_dem_metrics(
                provider=provider,
                site_point=point,
                slope_deg=slope_value,
                hemisphere=hemisphere,
                dem_step=dem_step,
                context=context,
            )
            tpi_norm = metrics["tpi_norm"]
            if tpi_norm is not None and (tpi_norm < tpi_min or tpi_norm > tpi_max):
                continue

            water_distance = self._nearest_water_distance(
                site_geom=QgsGeometry.fromPointXY(point),
                site_point=point,
                water_index=water_index,
                water_geoms=water_geoms,
            )
            candidate = evaluate_hyeol_candidate(
                point=point,
                center=center,
                metrics=metrics,
                water_distance=water_distance,
                slope_value=slope_value,
                aspect_value=aspect_value,
                hemisphere=hemisphere,
                context=context,
                profile=profile,
                tpi_min=tpi_min,
                tpi_max=tpi_max,
                score_profile_slope=self._score_profile_slope,
                score_aspect=self._score_aspect,
                score_profile_tpi=self._score_profile_tpi,
                score_water_distance=self._score_water_distance,
                profile_weighted_score=self._profile_weighted_score,
            )
            if candidate is None:
                continue
            candidates.append(candidate)

        candidates.sort(key=lambda item: item["score"], reverse=True)
        return candidates

    @staticmethod
    def _suppress_near_duplicates(candidates, min_distance, keep):
        return suppress_near_duplicates(candidates, min_distance, keep)

    def _build_term_layer(
        self,
        dem_layer,
        provider,
        hemisphere,
        dem_step,
        selected,
        context,
        profile_key,
        profile=None,
        label_language="ko",
    ):
        layer_name = f"{dem_layer.name()}_fengshui_terms"
        term_layer = QgsVectorLayer(
            f"Point?crs={dem_layer.crs().authid()}",
            layer_name,
            "memory",
        )
        data = term_layer.dataProvider()
        data.addAttributes(term_layer_fields())
        term_layer.updateFields()

        card = self.CARDINALS.get(hemisphere, self.CARDINALS["north"])
        scales = term_radius_scales()
        hyeol_rules = self._rules_section("hyeol_selection")
        min_score_floor = self._rule_float(
            hyeol_rules, "min_score_floor", 0.42, min_value=0.0, max_value=1.0
        )
        threshold_multiplier = self._rule_float(
            hyeol_rules,
            "context_threshold_multiplier",
            0.72,
            min_value=0.0,
            max_value=2.0,
        )
        term_state = term_runtime_state(
            context=context,
            profile=profile,
            dem_step=dem_step,
            scales=scales,
            min_score_floor=min_score_floor,
            threshold_multiplier=threshold_multiplier,
        )
        culture_id = term_state["culture_id"]
        period_id = term_state["period_id"]
        term_bias = term_state["term_bias"]
        term_target_shift = term_state["term_target_shift"]
        term_min_score = term_state["term_min_score"]
        radius_map = term_state["radius_map"]
        outer_radius = radius_map["outer"]
        term_display_language = label_language if label_language in ("ko", "en") else "ko"

        def add_term(
            term_id,
            term_name,
            parent_id,
            rank,
            point,
            score,
            elev,
            note,
            mandatory=False,
            base_score_value=None,
            delta_rel=None,
            target_rel=None,
            fit_score=None,
            radius_m=None,
            azimuth=None,
            mode=None,
            relief_m=None,
            reason_text=None,
        ):
            adjusted_score = adjusted_term_score(
                score,
                term_id=term_id,
                term_bias=term_bias,
                term_min_score=term_min_score,
                mandatory=mandatory,
            )
            if adjusted_score is None and score is not None:
                return

            reason_ko = reason_text or self._compose_term_reason(
                term_id=term_id,
                adjusted_score=adjusted_score,
                base_score=base_score_value,
                elev=elev,
                delta_rel=delta_rel,
                target_rel=target_rel,
                fit_score=fit_score,
                radius_m=radius_m,
                azimuth=azimuth,
                mode=mode,
                note=note,
            )
            append_term_feature(
                layer=term_layer,
                term_id=term_id,
                term_name=term_name,
                term_ko=term_label_ko(term_id),
                culture=culture_id,
                period=period_id,
                profile=profile_key,
                parent_id=parent_id,
                rank=rank,
                point=point,
                score=adjusted_score,
                elev=elev,
                note=note,
                base_sc=base_score_value,
                delta_rel=delta_rel,
                target_rel=target_rel,
                fit_sc=fit_score,
                radius_m=radius_m,
                azimuth=azimuth,
                mode=mode,
                relief_m=relief_m,
                reason_ko=reason_ko,
            )

        selected_total = max(1, len(selected))
        for rank, item in enumerate(selected, start=1):
            center_point = item["point"]
            center_elev = item["elev"]
            base_score = item["score"]
            metrics = item.get("metrics", {})
            form_score = metrics.get("form_score")
            long_score = metrics.get("long_score")
            wet_score = item.get("hydro_score", metrics.get("dem_water_score"))
            tpi_norm = metrics.get("tpi_norm")
            conv_score = metrics.get("convergence")
            water_distance = item.get("water_distance")

            ring_values = self._sample_ring(
                provider=provider,
                center_point=center_point,
                radius=outer_radius,
                azimuths=list(range(0, 360, 12)),
            )
            relief = relief_from_ring_values(ring_values)

            parent_id = rank
            hyeol_reason = self._compose_hyeol_reason(
                rank=rank,
                selected_total=selected_total,
                base_score=base_score,
                form_score=form_score,
                long_score=long_score,
                wet_score=wet_score,
                tpi_norm=tpi_norm,
                conv_score=conv_score,
                relief=relief,
                center_elev=center_elev,
                threshold=context["hyeol_threshold"],
                water_distance=water_distance,
                sashinsa_score=metrics.get("sashinsa_score"),
                enclosure_index=metrics.get("enclosure_index"),
                large_tpi_norm=metrics.get("large_tpi_norm"),
            )
            add_term(
                **core_hyeol_term_payload(
                    parent_id=parent_id,
                    rank=rank,
                    point=center_point,
                    base_score=base_score,
                    center_elev=center_elev,
                    relief=relief,
                    reason_text=hyeol_reason,
                    term_name=term_label("hyeol", term_display_language),
                )
            )

            special_terms = special_term_specs()
            myeongdang_spec = special_terms["myeongdang"]
            myeongdang_radius = radius_map[myeongdang_spec["radius"]]
            myeongdang_point = self._offset_point(
                center_point,
                myeongdang_radius * float(myeongdang_spec["offset_factor"]),
                card[myeongdang_spec["direction"]],
            )
            myeongdang_elev = self._sample_dem(provider, myeongdang_point)
            if myeongdang_elev is None:
                myeongdang_point = center_point
                myeongdang_elev = center_elev
            myeongdang_delta = (myeongdang_elev - center_elev) / relief
            myeongdang_target = float(myeongdang_spec["target"]) + (
                term_target_shift * float(myeongdang_spec["target_shift_scale"])
            )
            myeongdang_fit = self._score_gaussian(
                myeongdang_delta,
                myeongdang_target,
                float(myeongdang_spec["sigma"]),
            )
            add_term(
                **myeongdang_term_payload(
                    parent_id=parent_id,
                    rank=rank,
                    point=myeongdang_point,
                    elev=myeongdang_elev,
                    center_elev=center_elev,
                    base_score=base_score,
                    relief=relief,
                    target_rel=myeongdang_target,
                    fit_score=myeongdang_fit,
                    radius_m=myeongdang_radius * float(myeongdang_spec["offset_factor"]),
                    azimuth=card[myeongdang_spec["direction"]],
                    term_name=term_label("myeongdang", term_display_language),
                )
            )
            for spec in term_specs():
                term_id = spec["term_id"]
                term_name = term_label(term_id, term_display_language)
                radius = radius_map[spec["radius"]]
                azimuth = card[spec["direction"]]
                mode = spec["mode"]
                target = float(spec["target"])
                sigma = float(spec["sigma"])
                point, elev, _ = self._sector_extreme(
                    provider=provider,
                    center_point=center_point,
                    radius=radius,
                    center_azimuth=azimuth,
                    mode=mode,
                )
                if point is None:
                    continue
                delta = (elev - center_elev) / relief
                target_rel = target + term_target_shift
                fit_score = self._score_gaussian(delta, target_rel, sigma)
                add_term(
                    **generic_term_payload(
                        term_id=term_id,
                        term_name=term_name,
                        parent_id=parent_id,
                        rank=rank,
                        point=point,
                        elev=elev,
                        center_elev=center_elev,
                        base_score=base_score,
                        relief=relief,
                        target_rel=target_rel,
                        fit_score=fit_score,
                        radius_m=radius,
                        azimuth=azimuth,
                        mode=mode,
                    )
                )

            ipsu_spec = special_terms["ipsu"]
            ipsu_radius = radius_map[ipsu_spec["radius"]]
            ipsu_point, ipsu_elev, _ = self._ring_extreme(
                provider=provider,
                center_point=center_point,
                radius=ipsu_radius,
                mode=ipsu_spec["mode"],
            )
            if ipsu_point is not None:
                delta = (ipsu_elev - center_elev) / relief
                target_rel = float(ipsu_spec["target"]) + term_target_shift
                fit_score = self._score_gaussian(
                    delta,
                    target_rel,
                    float(ipsu_spec["sigma"]),
                )
                add_term(
                    **ipsu_term_payload(
                        parent_id=parent_id,
                        rank=rank,
                        point=ipsu_point,
                        elev=ipsu_elev,
                        center_elev=center_elev,
                        base_score=base_score,
                        relief=relief,
                        target_rel=target_rel,
                        fit_score=fit_score,
                        radius_m=ipsu_radius,
                        mode=ipsu_spec["mode"],
                        term_name=term_label("ipsu", term_display_language),
                    )
                )

            misa_point, misa_elev = self._sector_gentle_point(
                provider=provider,
                center_point=center_point,
                radius=radius_map[special_terms["misa"]["radius"]],
                center_azimuth=card[special_terms["misa"]["direction"]],
                reference=center_elev,
            )
            if misa_point is not None:
                misa_spec = special_terms["misa"]
                delta = (misa_elev - center_elev) / relief
                target_rel = float(misa_spec["target"]) + (
                    term_target_shift * float(misa_spec["target_shift_scale"])
                )
                fit_score = self._score_gaussian(
                    delta,
                    target_rel,
                    float(misa_spec["sigma"]),
                )
                add_term(
                    **misa_term_payload(
                        parent_id=parent_id,
                        rank=rank,
                        point=misa_point,
                        elev=misa_elev,
                        center_elev=center_elev,
                        base_score=base_score,
                        relief=relief,
                        target_rel=target_rel,
                        fit_score=fit_score,
                        radius_m=radius_map[misa_spec["radius"]],
                        azimuth=card[misa_spec["direction"]],
                        term_name=term_label("misa", term_display_language),
                    )
                )

        term_layer.updateExtents()
        return term_layer

    @staticmethod
    def _append_term_feature(
        layer,
        term_id,
        term_name,
        parent_id,
        rank,
        point,
        score,
        elev,
        note,
        base_sc=None,
        delta_rel=None,
        target_rel=None,
        fit_sc=None,
        radius_m=None,
        azimuth=None,
        mode=None,
        relief_m=None,
        term_ko=None,
        culture=None,
        period=None,
        profile=None,
        reason_ko=None,
    ):
        append_term_feature(
            layer,
            term_id=term_id,
            term_name=term_name,
            parent_id=parent_id,
            rank=rank,
            point=point,
            score=score,
            elev=elev,
            note=note,
            base_sc=base_sc,
            delta_rel=delta_rel,
            target_rel=target_rel,
            fit_sc=fit_sc,
            radius_m=radius_m,
            azimuth=azimuth,
            mode=mode,
            relief_m=relief_m,
            term_ko=term_ko,
            culture=culture,
            period=period,
            profile=profile,
            reason_ko=reason_ko,
        )

    def build_term_links(self, term_layer, label_language="ko"):
        link_layer = QgsVectorLayer(
            f"LineString?crs={term_layer.crs().authid()}",
            f"{term_layer.name()}_links",
            "memory",
        )
        data = link_layer.dataProvider()
        data.addAttributes(term_link_fields())
        link_layer.updateFields()
        link_rules = self._rules_section("term_links")
        path_plan = self._term_link_plan(link_rules)

        grouped = group_term_features(term_layer.getFeatures())

        link_features = []
        min_link_score = self._rule_float(
            link_rules, "min_link_score", 0.44, min_value=0.0, max_value=1.0
        )
        distinct_min_distance = self._rule_float(
            link_rules, "distinct_min_distance", 0.2, min_value=0.01
        )
        smooth_passes = self._rule_int(link_rules, "smooth_passes", 2, min_value=0)
        for parent_id, terms in grouped.items():
            for spec in path_plan:
                nodes = []
                points = []
                missing = False
                for node_id in spec["node_ids"]:
                    feature = terms.get(node_id)
                    if feature is None or not feature.hasGeometry():
                        missing = True
                        break
                    nodes.append(feature)
                    points.append(feature.geometry().asPoint())
                if missing:
                    continue

                payload = link_ready_payload(
                    nodes,
                    points,
                    spec=spec,
                    min_link_score=min_link_score,
                    distinct_min_distance=distinct_min_distance,
                    smooth_passes=smooth_passes,
                    to_float=self._to_float,
                )
                if payload is None:
                    continue

                line_feature = build_term_link_feature(
                    fields=link_layer.fields(),
                    smoothed_points=payload["smoothed_points"],
                    parent_id=parent_id,
                    rank_value=payload["rank_value"],
                    score=payload["score"],
                    source=payload["source"],
                    target=payload["target"],
                    spec=spec,
                    length_m=payload["length_m"],
                    azimuth=payload["azimuth"],
                    azimuth_label=self._azimuth_label,
                    term_label=term_label,
                    term_label_ko=term_label_ko,
                )
                link_features.append(line_feature)

        if link_features:
            data.addFeatures(link_features)
        link_layer.updateExtents()
        return link_layer

    @staticmethod
    def _term_link_plan(link_rules):
        default_plan = [
            {
                "node_ids": ["jusan", "dunoe", "jojongsan"],
                "style_term": "jusan",
                "link_type": "backbone",
                "label": "Backbone",
                "label_ko": "주산 축선",
            },
            {
                "node_ids": ["oecheongnyong", "josan", "oebaekho"],
                "style_term": "oecheongnyong",
                "link_type": "outer_wrap",
                "label": "Outer Wrap",
                "label_ko": "외곽 감싸기",
            },
            {
                "node_ids": ["naecheongnyong", "ansan", "naebaekho"],
                "style_term": "myeongdang",
                "link_type": "inner_wrap",
                "label": "Inner Wrap",
                "label_ko": "내곽 감싸기",
            },
            {
                "node_ids": ["jusan", "myeongdang", "ansan"],
                "style_term": "myeongdang",
                "link_type": "core_axis",
                "label": "Core Axis",
                "label_ko": "중심 축선",
            },
            {
                "node_ids": ["naesugu", "ansan", "oesugu"],
                "style_term": "naesugu",
                "link_type": "front_arc",
                "label": "Front Arc",
                "label_ko": "전면 수구 호",
            },
            {
                "node_ids": ["naesugu", "oesugu", "ipsu"],
                "style_term": "naesugu",
                "link_type": "water_flow",
                "label": "Water Flow",
                "label_ko": "수구 흐름",
            },
        ]
        if not isinstance(link_rules, dict):
            return default_plan

        raw_plan = link_rules.get("path_plan")
        if not isinstance(raw_plan, list):
            return default_plan

        normalized = []
        for item in raw_plan:
            if not isinstance(item, dict):
                continue
            node_ids = item.get("node_ids", [])
            if not isinstance(node_ids, list):
                continue
            clean_nodes = [str(node).strip() for node in node_ids if str(node).strip()]
            if len(clean_nodes) < 2:
                continue
            style_term = str(item.get("style_term", clean_nodes[0])).strip() or clean_nodes[0]
            link_type = str(item.get("link_type", "path")).strip() or "path"
            label = str(item.get("label", link_type)).strip() or link_type
            label_ko = str(item.get("label_ko", label)).strip() or label
            normalized.append(
                {
                    "node_ids": clean_nodes,
                    "style_term": style_term,
                    "link_type": link_type,
                    "label": label,
                    "label_ko": label_ko,
                }
            )
        return normalized or default_plan

    @staticmethod
    def _path_mean_score(features):
        return path_mean_score(features, FengShuiAnalyzer._to_float)

    @staticmethod
    def _polyline_length(points):
        return polyline_length(points)

    @staticmethod
    def _distinct_points(points, min_distance=0.1):
        return distinct_points(points, min_distance=min_distance)

    @staticmethod
    def _smooth_polyline(points, passes=1):
        return smooth_polyline(points, passes=passes)

    def _prepare_display_polyline(
        self,
        points,
        spacing,
        densify_step_factor,
        densify_min_step,
        smooth_passes,
        distinct_min_distance_factor,
    ):
        if len(points) < 2:
            return [QgsPointXY(point.x(), point.y()) for point in points]

        densified = self._densify_polyline(
            points,
            max_step=max(spacing * densify_step_factor, densify_min_step),
        )
        smoothed = self._smooth_polyline(densified, passes=smooth_passes)
        distinct_min_distance = max(1e-9, spacing * distinct_min_distance_factor)
        return self._distinct_points(smoothed, min_distance=distinct_min_distance)

    @staticmethod
    def _moving_average_polyline(points, passes=1):
        current = [QgsPointXY(point.x(), point.y()) for point in points]
        if len(current) < 3 or passes <= 0:
            return current

        for _ in range(passes):
            if len(current) < 3:
                break
            smoothed = [QgsPointXY(current[0].x(), current[0].y())]
            for index in range(1, len(current) - 1):
                point_prev = current[index - 1]
                point_curr = current[index]
                point_next = current[index + 1]
                smoothed.append(
                    QgsPointXY(
                        (point_prev.x() + (point_curr.x() * 2.0) + point_next.x()) / 4.0,
                        (point_prev.y() + (point_curr.y() * 2.0) + point_next.y()) / 4.0,
                    )
                )
            smoothed.append(QgsPointXY(current[-1].x(), current[-1].y()))
            current = smoothed
        return current

    def style_term_points(self, term_layer, label_language="ko"):
        style_map = point_styles()
        categories = []
        display_language = label_language if label_language in ("ko", "en") else "ko"
        for term_id, style in style_map.items():
            symbol = self._build_stacked_marker_symbol(term_point_symbol_layers(term_id, style))
            categories.append(
                QgsRendererCategory(term_id, symbol, term_label(term_id, display_language))
            )

        renderer = QgsCategorizedSymbolRenderer("term_id", categories)
        fallback = self._build_stacked_marker_symbol(
            term_point_symbol_layers("default", ("#b9b9b9", 3.0, "#5c5c5c", 0.45))
        )
        renderer.setSourceSymbol(fallback)
        term_layer.setRenderer(renderer)
        term_layer.triggerRepaint()

    def style_term_links(self, link_layer, label_language="ko"):
        style_map = line_styles()
        categories = []
        display_language = label_language if label_language in ("ko", "en") else "ko"
        for term_id, style in style_map.items():
            symbol = self._build_stacked_line_symbol(term_link_symbol_layers(term_id, style))
            categories.append(
                QgsRendererCategory(term_id, symbol, term_label(term_id, display_language))
            )

        renderer = QgsCategorizedSymbolRenderer("term_id", categories)
        default_symbol = self._build_stacked_line_symbol(
            term_link_symbol_layers("default", ("#777777", 0.9))
        )
        renderer.setSourceSymbol(default_symbol)
        link_layer.setRenderer(renderer)
        link_layer.triggerRepaint()

    def build_hydro_network(self, dem_layer):
        provider = dem_layer.dataProvider()
        dem_step = self._dem_step(dem_layer)
        spacing = self._hydro_spacing(dem_layer, dem_step)
        hydro_rules = self._rules_section("hydro_network")
        min_drop_floor = self._rule_float(
            hydro_rules, "min_drop_floor", 0.15, min_value=1e-6
        )
        min_drop_ratio = self._rule_float(
            hydro_rules, "min_drop_ratio", 0.0012, min_value=1e-9
        )
        acc_threshold_floor = self._rule_float(
            hydro_rules, "acc_threshold_floor", 8.0, min_value=0.0
        )
        secondary_keep_order_floor = self._rule_int(
            hydro_rules, "secondary_keep_order_floor", 2, min_value=1
        )
        secondary_keep_order_delta = self._rule_int(
            hydro_rules, "secondary_keep_order_delta", 1, min_value=0
        )
        secondary_keep_acc_ratio = self._rule_float(
            hydro_rules, "secondary_keep_acc_ratio", 0.82, min_value=0.0, max_value=1.0
        )

        hydro_layer = QgsVectorLayer(
            f"LineString?crs={dem_layer.crs().authid()}",
            f"{dem_layer.name()}_fengshui_hydro",
            "memory",
        )
        data = hydro_layer.dataProvider()
        fields = QgsFields()
        fields.append(QgsField("stream_id", QVariant.Int))
        fields.append(QgsField("flow_acc", QVariant.Double, "double", 12, 3))
        fields.append(QgsField("acc_thr", QVariant.Double, "double", 12, 3))
        fields.append(QgsField("keep_q", QVariant.Double, "double", 6, 3))
        fields.append(QgsField("min_len", QVariant.Double, "double", 12, 3))
        fields.append(QgsField("min_ord", QVariant.Int))
        fields.append(QgsField("node_cnt", QVariant.Int))
        fields.append(QgsField("order", QVariant.Int))
        fields.append(QgsField("stream_class", QVariant.String, "string", 16))
        fields.append(QgsField("len", QVariant.Double, "double", 12, 3))
        fields.append(QgsField("reason_ko", QVariant.String, "string", 254))
        data.addAttributes(fields)
        hydro_layer.updateFields()

        extent = dem_layer.extent()
        x_values = []
        y_values = []
        x = extent.xMinimum() + (spacing * 0.5)
        y = extent.yMinimum() + (spacing * 0.5)
        while x < extent.xMaximum():
            x_values.append(x)
            x += spacing
        while y < extent.yMaximum():
            y_values.append(y)
            y += spacing

        if len(x_values) < 2 or len(y_values) < 2:
            return hydro_layer

        nodes = {}
        for ix, x_value in enumerate(x_values):
            for iy, y_value in enumerate(y_values):
                point = QgsPointXY(x_value, y_value)
                elev = self._sample_dem(provider, point)
                if elev is None:
                    continue
                nodes[(ix, iy)] = {"point": point, "elev": elev}
        if len(nodes) < 9:
            return hydro_layer

        elevations = [node["elev"] for node in nodes.values()]
        elev_min = min(elevations)
        elev_max = max(elevations)
        elev_range = max(1e-6, elev_max - elev_min)
        min_drop = max(min_drop_floor, elev_range * min_drop_ratio)
        neighbor_offsets = [
            (-1, -1),
            (-1, 0),
            (-1, 1),
            (0, -1),
            (0, 1),
            (1, -1),
            (1, 0),
            (1, 1),
        ]

        downstream = {}
        upstream = defaultdict(list)
        for key, node in nodes.items():
            ix, iy = key
            source_elev = node["elev"]
            best_key = None
            best_elev = None
            for dx, dy in neighbor_offsets:
                near_key = (ix + dx, iy + dy)
                near_node = nodes.get(near_key)
                if near_node is None:
                    continue
                near_elev = near_node["elev"]
                if near_elev >= (source_elev - min_drop):
                    continue
                if best_elev is None or near_elev < best_elev:
                    best_key = near_key
                    best_elev = near_elev
            if best_key is None:
                continue
            downstream[key] = best_key
            upstream[best_key].append(key)

        if not downstream:
            return hydro_layer

        contrib = {key: 1.0 for key in nodes.keys()}
        keys_by_elev = sorted(nodes.keys(), key=lambda k: nodes[k]["elev"], reverse=True)
        for key in keys_by_elev:
            target = downstream.get(key)
            if target is None:
                continue
            contrib[target] = contrib.get(target, 1.0) + contrib.get(key, 1.0)

        stream_order = self._compute_stream_order(nodes, downstream, upstream)
        accumulation_values = [contrib[k] for k in downstream.keys()]
        accumulation_values.sort()
        node_count = len(nodes)
        keep_quantile = self._hydro_keep_quantile(node_count)
        min_order = self._hydro_min_order(node_count)
        min_path_length = self._hydro_min_path_length(
            dem_layer=dem_layer,
            spacing=spacing,
            node_count=node_count,
        )

        cut_index = int(len(accumulation_values) * keep_quantile)
        cut_index = max(0, min(len(accumulation_values) - 1, cut_index))
        accumulation_threshold = max(acc_threshold_floor, accumulation_values[cut_index])

        selected_downstream = {}
        for key, target in downstream.items():
            order_value = stream_order.get(key, 1)
            acc_value = contrib.get(key, 1.0)
            keep = acc_value >= accumulation_threshold
            if not keep and order_value >= min_order:
                keep = True
            if (
                not keep
                and order_value >= max(
                    secondary_keep_order_floor,
                    min_order - secondary_keep_order_delta,
                )
                and acc_value >= (accumulation_threshold * secondary_keep_acc_ratio)
            ):
                keep = True
            if keep:
                selected_downstream[key] = target

        if not selected_downstream:
            return hydro_layer

        upstream_selected = defaultdict(int)
        for source, target in selected_downstream.items():
            _ = source
            upstream_selected[target] += 1

        def node_order_value(node_key):
            return stream_order.get(node_key, 1)

        heads = [
            key
            for key in selected_downstream.keys()
            if upstream_selected.get(key, 0) != 1
        ]
        heads.sort(key=lambda k: (node_order_value(k), contrib.get(k, 1.0)), reverse=True)

        visited_edges = set()
        stream_paths = []
        for start in heads:
            path = self._trace_downstream_path(
                start=start,
                selected_downstream=selected_downstream,
                upstream_selected=upstream_selected,
                visited_edges=visited_edges,
            )
            if path and len(path) > 1:
                stream_paths.append(path)

        for start in selected_downstream.keys():
            path = self._trace_downstream_path(
                start=start,
                selected_downstream=selected_downstream,
                upstream_selected=upstream_selected,
                visited_edges=visited_edges,
            )
            if path and len(path) > 1:
                stream_paths.append(path)

        if not stream_paths:
            return hydro_layer

        render_rules = self._rules_section("hydro_rendering")
        densify_step_factor = self._rule_float(
            render_rules, "densify_step_factor", 0.72, min_value=0.05
        )
        densify_min_step = self._rule_float(
            render_rules, "densify_min_step", 1.0, min_value=1e-6
        )
        smooth_passes = self._rule_int(render_rules, "smooth_passes", 2, min_value=0)
        distinct_min_distance_factor = self._rule_float(
            render_rules, "distinct_min_distance_factor", 0.03, min_value=0.0
        )

        features = []
        stream_id = 1
        for path in stream_paths:
            raw_points = [nodes[key]["point"] for key in path if key in nodes]
            if len(raw_points) < 2:
                continue

            points = self._prepare_display_polyline(
                points=raw_points,
                spacing=spacing,
                densify_step_factor=densify_step_factor,
                densify_min_step=densify_min_step,
                smooth_passes=smooth_passes,
                distinct_min_distance_factor=distinct_min_distance_factor,
            )
            if len(points) < 2:
                continue

            length = self._polyline_length(points)
            if length <= 0:
                continue

            max_acc = max(contrib.get(key, 1.0) for key in path)
            max_order = max(stream_order.get(key, 1) for key in path)
            if length < min_path_length and max_order < min_order:
                continue
            stream_class = self._stream_class(max_order)

            feature = QgsFeature(hydro_layer.fields())
            feature.setGeometry(QgsGeometry.fromPolylineXY(points))
            feature["stream_id"] = stream_id
            feature["flow_acc"] = max_acc
            feature["acc_thr"] = accumulation_threshold
            feature["keep_q"] = keep_quantile
            feature["min_len"] = min_path_length
            feature["min_ord"] = int(min_order)
            feature["node_cnt"] = int(node_count)
            feature["order"] = int(max_order)
            feature["stream_class"] = stream_class
            feature["len"] = length
            feature["reason_ko"] = (
                f"DEM 유하방향 수로. flow_acc={max_acc:.2f}, 임계치={accumulation_threshold:.2f}, "
                f"유지백분위={keep_quantile*100:.1f}%, 차수={int(max_order)}(최소 {min_order}), "
                f"길이={length:.1f}m(최소 {min_path_length:.1f}m), "
                f"분류={HYDRO_CLASS_LABELS_KO.get(stream_class, stream_class)}."
            )
            features.append(feature)
            stream_id += 1

        if features:
            data.addFeatures(features)
        hydro_layer.updateExtents()
        return hydro_layer

    @staticmethod
    def style_hydro_network(hydro_layer):
        class_styles = hydro_symbol_profiles()
        categories = []
        for class_id, spec in class_styles.items():
            symbol = FengShuiAnalyzer._build_stacked_line_symbol(spec.get("layers", []))
            categories.append(QgsRendererCategory(class_id, symbol, class_id))

        renderer = QgsCategorizedSymbolRenderer("stream_class", categories)
        fallback = FengShuiAnalyzer._build_stacked_line_symbol(
            hydro_symbol_profiles()["minor"].get("layers", [])
        )
        renderer.setSourceSymbol(fallback)
        hydro_layer.setRenderer(renderer)
        hydro_layer.triggerRepaint()

    def build_ridge_network(self, dem_layer):
        provider = dem_layer.dataProvider()
        dem_step = self._dem_step(dem_layer)
        spacing = self._ridge_spacing(dem_layer, dem_step)
        ridge_rules = self._rules_section("ridge_network")

        ridge_layer = QgsVectorLayer(
            f"LineString?crs={dem_layer.crs().authid()}",
            f"{dem_layer.name()}_fengshui_ridges",
            "memory",
        )
        data = ridge_layer.dataProvider()
        fields = QgsFields()
        fields.append(QgsField("ridge_id", QVariant.Int))
        fields.append(QgsField("strength", QVariant.Double, "double", 7, 3))
        fields.append(QgsField("ridge_rank", QVariant.Int))
        fields.append(QgsField("ridge_class", QVariant.String, "string", 16))
        fields.append(QgsField("ridge_ko", QVariant.String, "string", 20))
        fields.append(QgsField("ridge_en", QVariant.String, "string", 28))
        fields.append(QgsField("ridge_score", QVariant.Double, "double", 7, 3))
        fields.append(QgsField("elev_a", QVariant.Double, "double", 12, 3))
        fields.append(QgsField("elev_b", QVariant.Double, "double", 12, 3))
        fields.append(QgsField("len", QVariant.Double, "double", 12, 3))
        fields.append(QgsField("reason_ko", QVariant.String, "string", 254))
        data.addAttributes(fields)
        ridge_layer.updateFields()

        extent = dem_layer.extent()
        x_values = []
        y_values = []
        x = extent.xMinimum() + (spacing * 0.5)
        y = extent.yMinimum() + (spacing * 0.5)
        while x < extent.xMaximum():
            x_values.append(x)
            x += spacing
        while y < extent.yMaximum():
            y_values.append(y)
            y += spacing

        if len(x_values) < 2 or len(y_values) < 2:
            return ridge_layer

        nodes = {}
        for ix, x_value in enumerate(x_values):
            for iy, y_value in enumerate(y_values):
                point = QgsPointXY(x_value, y_value)
                elev = self._sample_dem(provider, point)
                if elev is None:
                    continue
                nodes[(ix, iy)] = {"point": point, "elev": elev}

        if len(nodes) < 9:
            return ridge_layer

        elevations = [node["elev"] for node in nodes.values()]
        elev_min = min(elevations)
        elev_max = max(elevations)
        elev_range = max(1e-6, elev_max - elev_min)
        prominence_min_floor = self._rule_float(
            ridge_rules, "prominence_min_floor", 0.6, min_value=0.01
        )
        prominence_min_ratio = self._rule_float(
            ridge_rules, "prominence_min_ratio", 0.010, min_value=1e-6
        )
        neighbor_delta_floor = self._rule_float(
            ridge_rules, "neighbor_delta_floor", 0.05, min_value=1e-6
        )
        neighbor_delta_ratio = self._rule_float(
            ridge_rules, "neighbor_delta_ratio", 0.0022, min_value=1e-6
        )
        required_neighbor_ratio = self._rule_float(
            ridge_rules, "required_neighbor_ratio", 0.55, min_value=0.0, max_value=1.0
        )
        soft_required_ratio = self._rule_float(
            ridge_rules,
            "soft_required_neighbor_ratio",
            0.45,
            min_value=0.0,
            max_value=1.0,
        )
        soft_prominence_ratio = self._rule_float(
            ridge_rules, "soft_prominence_ratio", 0.78, min_value=0.1, max_value=2.0
        )
        max_segment_distance_factor = self._rule_float(
            ridge_rules, "max_segment_distance_factor", 2.9, min_value=0.5
        )
        max_segment_drop_floor = self._rule_float(
            ridge_rules, "max_segment_drop_floor", 2.0, min_value=0.1
        )
        max_segment_drop_ratio = self._rule_float(
            ridge_rules, "max_segment_drop_ratio", 0.14, min_value=1e-6
        )
        min_path_spacing_factor = self._rule_float(
            ridge_rules, "min_path_spacing_factor", 2.4, min_value=0.1
        )
        min_path_diag_ratio = self._rule_float(
            ridge_rules, "min_path_diag_ratio", 0.008, min_value=1e-6
        )
        prominence_min = max(prominence_min_floor, elev_range * prominence_min_ratio)
        neighbor_delta = max(neighbor_delta_floor, elev_range * neighbor_delta_ratio)

        neighborhood = [
            (-1, -1),
            (-1, 0),
            (-1, 1),
            (0, -1),
            (0, 1),
            (1, -1),
            (1, 0),
            (1, 1),
        ]
        ridge_nodes = {}
        for key, node in nodes.items():
            ix, iy = key
            elev = node["elev"]
            neighbors = []
            for dx, dy in neighborhood:
                near = nodes.get((ix + dx, iy + dy))
                if near is not None:
                    neighbors.append(near)
            if len(neighbors) < 4:
                continue

            mean_neighbor = sum(item["elev"] for item in neighbors) / len(neighbors)
            higher_count = sum(
                1 for item in neighbors if elev >= (item["elev"] + neighbor_delta)
            )
            prominence = elev - mean_neighbor
            required = max(3, int(len(neighbors) * required_neighbor_ratio))
            soft_required = max(2, int(len(neighbors) * soft_required_ratio))
            if (
                (higher_count < required or prominence < prominence_min)
                and (
                    higher_count < soft_required
                    or prominence < (prominence_min * soft_prominence_ratio)
                )
            ):
                continue

            prominence_norm = min(1.0, prominence / (prominence_min * 2.0))
            local_ratio = higher_count / len(neighbors)
            strength = (0.45 * local_ratio) + (0.55 * prominence_norm)
            ridge_nodes[key] = {"point": node["point"], "elev": elev, "strength": strength}

        if len(ridge_nodes) < 2:
            return ridge_layer

        filtered = {}
        ridge_keys = set(ridge_nodes.keys())
        for key, node in ridge_nodes.items():
            ix, iy = key
            linked = 0
            for dx, dy in neighborhood:
                if (ix + dx, iy + dy) in ridge_keys:
                    linked += 1
            if linked > 0:
                filtered[key] = node
        ridge_nodes = filtered
        if len(ridge_nodes) < 2:
            return ridge_layer

        segment_offsets = self._ridge_segment_offsets(ridge_rules)
        max_segment_distance = spacing * max_segment_distance_factor
        max_segment_drop = max(max_segment_drop_floor, elev_range * max_segment_drop_ratio)
        adjacency = self._ridge_adjacency_from_offsets(
            ridge_nodes=ridge_nodes,
            segment_offsets=segment_offsets,
            max_segment_distance=max_segment_distance,
            max_segment_drop=max_segment_drop,
        )
        adjacency = self._sparsify_ridge_adjacency(
            adjacency=adjacency,
            ridge_nodes=ridge_nodes,
            ridge_rules=ridge_rules,
            max_segment_distance=max_segment_distance,
            max_segment_drop=max_segment_drop,
        )

        if not any(adjacency.values()):
            return ridge_layer

        bridged_count = self._bridge_ridge_endpoints(
            adjacency=adjacency,
            ridge_nodes=ridge_nodes,
            spacing=spacing,
            elev_range=elev_range,
        )

        ridge_paths = self._ridge_paths_from_graph(adjacency, ridge_nodes)
        raw_paths = []
        for path in ridge_paths:
            if len(path) < 2:
                continue
            points = [ridge_nodes[key]["point"] for key in path if key in ridge_nodes]
            if len(points) < 2:
                continue

            length = 0.0
            strengths = []
            for idx in range(len(path)):
                key = path[idx]
                node = ridge_nodes.get(key)
                if node is not None:
                    strengths.append(node["strength"])
                if idx == 0:
                    continue
                prev_key = path[idx - 1]
                point_a = ridge_nodes[prev_key]["point"]
                point_b = ridge_nodes[key]["point"]
                length += math.hypot(
                    point_b.x() - point_a.x(),
                    point_b.y() - point_a.y(),
                )
            if length <= 0:
                continue

            raw_paths.append(
                {
                    "path": path,
                    "points": points,
                    "len": length,
                    "strength": sum(strengths) / len(strengths) if strengths else 0.0,
                    "elev_a": ridge_nodes[path[0]]["elev"],
                    "elev_b": ridge_nodes[path[-1]]["elev"],
                    "node_count": len(path),
                }
            )

        diag = math.hypot(extent.width(), extent.height())
        min_path_len = max(spacing * min_path_spacing_factor, diag * min_path_diag_ratio)
        raw_paths = [item for item in raw_paths if item["len"] >= min_path_len]

        if not raw_paths:
            return ridge_layer

        ranked_paths = self._rank_ridge_paths(raw_paths)
        render_rules = self._rules_section("ridge_rendering")
        densify_step_factor = self._rule_float(
            render_rules, "densify_step_factor", 0.70, min_value=0.1
        )
        densify_min_step = self._rule_float(
            render_rules, "densify_min_step", 1.0, min_value=0.1
        )
        smooth_passes = self._rule_int(render_rules, "smooth_passes", 3, min_value=0)
        moving_average_passes = self._rule_int(
            render_rules, "moving_average_passes", 2, min_value=0
        )
        distinct_min_distance_factor = self._rule_float(
            render_rules, "distinct_min_distance_factor", 0.05, min_value=0.0
        )
        features = []
        for item in ranked_paths:
            feature = QgsFeature(ridge_layer.fields())
            smoothed_points = self._prepare_display_polyline(
                points=item["points"],
                spacing=spacing,
                densify_step_factor=densify_step_factor,
                densify_min_step=densify_min_step,
                smooth_passes=smooth_passes,
                distinct_min_distance_factor=distinct_min_distance_factor,
            )
            smoothed_points = self._moving_average_polyline(
                smoothed_points,
                passes=moving_average_passes,
            )
            if len(smoothed_points) < 2:
                continue
            feature.setGeometry(QgsGeometry.fromPolylineXY(smoothed_points))
            feature["ridge_id"] = item["ridge_id"]
            feature["strength"] = item["strength"]
            feature["ridge_rank"] = item["ridge_rank"]
            feature["ridge_class"] = item["ridge_class"]
            feature["ridge_ko"] = self._ridge_label(item["ridge_class"], "ko")
            feature["ridge_en"] = self._ridge_label(item["ridge_class"], "en")
            feature["ridge_score"] = item["ridge_score"]
            feature["elev_a"] = item["elev_a"]
            feature["elev_b"] = item["elev_b"]
            feature["len"] = item["len"]
            feature["reason_ko"] = (
                f"능선 점수={item['ridge_score']:.3f} (길이+능선성 결합), "
                f"순위={item['ridge_rank']}/{item['total_count']}, "
                f"상위백분위={item['percentile']*100:.1f}%, "
                f"분류={self._ridge_label(item['ridge_class'], 'ko')}, "
                f"연결기준=거리<= {max_segment_distance:.1f}m · 고도차<= {max_segment_drop:.1f}m, "
                f"보정연결={bridged_count}개."
            )
            features.append(feature)

        if features:
            data.addFeatures(features)
        ridge_layer.updateExtents()
        return ridge_layer

    @staticmethod
    def style_ridge_network(ridge_layer):
        class_styles = ridge_symbol_profiles()
        categories = []
        for class_id, spec in class_styles.items():
            symbol = FengShuiAnalyzer._build_stacked_line_symbol(spec.get("layers", []))
            categories.append(
                QgsRendererCategory(
                    class_id,
                    symbol,
                    FengShuiAnalyzer._ridge_label(class_id, "ko"),
                )
            )

        renderer = QgsCategorizedSymbolRenderer("ridge_class", categories)
        fallback = FengShuiAnalyzer._build_stacked_line_symbol(
            ridge_symbol_profiles()["minor"].get("layers", [])
        )
        renderer.setSourceSymbol(fallback)
        ridge_layer.setRenderer(renderer)
        ridge_layer.triggerRepaint()

    @staticmethod
    def _build_stacked_line_symbol(layer_specs):
        specs = list(layer_specs or [])
        if not specs:
            specs = [{"color": "110,110,110,180", "width": 0.8}]
        first = specs[0]
        symbol = QgsLineSymbol.createSimple(
            {
                "line_color": str(first.get("color", "110,110,110,180")),
                "line_width": str(max(0.12, float(first.get("width", 0.8)))),
                "line_style": str(first.get("line_style", "solid")),
                "capstyle": str(first.get("capstyle", "round")),
                "joinstyle": str(first.get("joinstyle", "round")),
            }
        )
        for spec in specs[1:]:
            layer_symbol = QgsLineSymbol.createSimple(
                {
                    "line_color": str(spec.get("color", "110,110,110,180")),
                    "line_width": str(max(0.12, float(spec.get("width", 0.8)))),
                    "line_style": str(spec.get("line_style", "solid")),
                    "capstyle": str(spec.get("capstyle", "round")),
                    "joinstyle": str(spec.get("joinstyle", "round")),
                }
            )
            symbol.appendSymbolLayer(layer_symbol.symbolLayer(0).clone())
        return symbol

    @staticmethod
    def _build_stacked_marker_symbol(layer_specs):
        specs = list(layer_specs or [])
        if not specs:
            specs = [
                {
                    "name": "circle",
                    "color": "180,180,180,200",
                    "size": 2.5,
                    "outline_color": "80,80,80,180",
                    "outline_width": 0.3,
                }
            ]
        first = specs[0]
        symbol = QgsMarkerSymbol.createSimple(
            {
                "name": str(first.get("name", "circle")),
                "color": str(first.get("color", "180,180,180,200")),
                "size": str(max(0.4, float(first.get("size", 2.5)))),
                "outline_color": str(first.get("outline_color", "80,80,80,180")),
                "outline_width": str(max(0.0, float(first.get("outline_width", 0.3)))),
            }
        )
        for spec in specs[1:]:
            layer_symbol = QgsMarkerSymbol.createSimple(
                {
                    "name": str(spec.get("name", "circle")),
                    "color": str(spec.get("color", "180,180,180,200")),
                    "size": str(max(0.4, float(spec.get("size", 2.5)))),
                    "outline_color": str(spec.get("outline_color", "80,80,80,180")),
                    "outline_width": str(max(0.0, float(spec.get("outline_width", 0.3)))),
                }
            )
            symbol.appendSymbolLayer(layer_symbol.symbolLayer(0).clone())
        return symbol

    def _ridge_spacing(self, dem_layer, dem_step):
        rules = self._rules_section("ridge_network")
        spacing_step_factor = self._rule_float(
            rules, "spacing_step_factor", 5.8, min_value=0.1
        )
        spacing_coarse_factor = self._rule_float(
            rules, "spacing_coarse_factor", 0.92, min_value=0.01
        )
        spacing_fallback = self._rule_float(
            rules, "spacing_fallback", 1.0, min_value=0.1
        )
        max_points = self._rule_int(rules, "spacing_max_points", 12000, min_value=50)
        coarse = self._adaptive_spacing(dem_layer, dem_step)
        spacing = max(dem_step * spacing_step_factor, coarse * spacing_coarse_factor)
        if spacing <= 0:
            spacing = max(dem_step * spacing_step_factor, spacing_fallback)

        extent = dem_layer.extent()
        cols = max(1, int(extent.width() / spacing) + 1)
        rows = max(1, int(extent.height() / spacing) + 1)
        total = cols * rows
        if total > max_points:
            spacing *= math.sqrt(total / max_points)
        return spacing

    @staticmethod
    def _ridge_edge_key(key_a, key_b):
        return (key_a, key_b) if key_a <= key_b else (key_b, key_a)

    @staticmethod
    def _ridge_edge_span(key_a, key_b, ridge_nodes):
        point_a = ridge_nodes[key_a]["point"]
        point_b = ridge_nodes[key_b]["point"]
        distance = math.hypot(
            point_b.x() - point_a.x(),
            point_b.y() - point_a.y(),
        )
        mean_strength = (
            ridge_nodes[key_a]["strength"] + ridge_nodes[key_b]["strength"]
        ) * 0.5
        return distance * (0.68 + (0.32 * mean_strength))

    @staticmethod
    def _ridge_components(adjacency):
        seen = set()
        components = []
        for start in adjacency.keys():
            if start in seen or not adjacency.get(start):
                continue
            stack = [start]
            component = set()
            seen.add(start)
            while stack:
                current = stack.pop()
                component.add(current)
                for neighbor in adjacency.get(current, ()):
                    if neighbor in seen:
                        continue
                    seen.add(neighbor)
                    stack.append(neighbor)
            if len(component) > 1:
                components.append(component)
        return components

    @classmethod
    def _ridge_component_spanning_tree(cls, component_keys, adjacency, ridge_nodes):
        component_set = set(component_keys)
        tree = {key: set() for key in component_set}
        edges = []
        for key_a in component_set:
            for key_b in adjacency.get(key_a, set()):
                if key_b not in component_set:
                    continue
                edge_key = cls._ridge_edge_key(key_a, key_b)
                if edge_key[0] != key_a:
                    continue
                span = cls._ridge_edge_span(key_a, key_b, ridge_nodes)
                edges.append((span, key_a, key_b))
        if not edges:
            return tree

        parent = {key: key for key in component_set}
        rank = {key: 0 for key in component_set}

        def find(node):
            while parent[node] != node:
                parent[node] = parent[parent[node]]
                node = parent[node]
            return node

        def union(first, second):
            root_first = find(first)
            root_second = find(second)
            if root_first == root_second:
                return False
            if rank[root_first] < rank[root_second]:
                root_first, root_second = root_second, root_first
            parent[root_second] = root_first
            if rank[root_first] == rank[root_second]:
                rank[root_first] += 1
            return True

        edges.sort(key=lambda item: item[0], reverse=True)
        for _span, key_a, key_b in edges:
            if not union(key_a, key_b):
                continue
            tree[key_a].add(key_b)
            tree[key_b].add(key_a)
        return tree

    @classmethod
    def _ridge_tree_farthest(cls, start, tree_adjacency, ridge_nodes):
        best_node = start
        best_distance = 0.0
        parents = {start: None}
        stack = [(start, None, 0.0)]
        while stack:
            current, prev, distance = stack.pop()
            current_strength = ridge_nodes[current]["strength"]
            best_strength = ridge_nodes[best_node]["strength"]
            if distance > best_distance + 1e-9 or (
                abs(distance - best_distance) <= 1e-9 and current_strength > best_strength
            ):
                best_node = current
                best_distance = distance
            for neighbor in tree_adjacency.get(current, ()):
                if neighbor == prev:
                    continue
                parents[neighbor] = current
                stack.append(
                    (
                        neighbor,
                        current,
                        distance + cls._ridge_edge_span(current, neighbor, ridge_nodes),
                    )
                )
        return best_node, best_distance, parents

    @classmethod
    def _ridge_tree_diameter(cls, tree_adjacency, ridge_nodes, component_keys):
        if not component_keys:
            return []
        seed = max(component_keys, key=lambda key: ridge_nodes[key]["strength"])
        first, _first_distance, _first_parents = cls._ridge_tree_farthest(
            seed,
            tree_adjacency,
            ridge_nodes,
        )
        second, _second_distance, parents = cls._ridge_tree_farthest(
            first,
            tree_adjacency,
            ridge_nodes,
        )
        path = []
        current = second
        while current is not None:
            path.append(current)
            current = parents.get(current)
        path.reverse()
        return path

    @classmethod
    def _ridge_path_length_by_keys(cls, path, ridge_nodes):
        if len(path) < 2:
            return 0.0
        length = 0.0
        for index in range(1, len(path)):
            key_a = path[index - 1]
            key_b = path[index]
            point_a = ridge_nodes[key_a]["point"]
            point_b = ridge_nodes[key_b]["point"]
            length += math.hypot(
                point_b.x() - point_a.x(),
                point_b.y() - point_a.y(),
            )
        return length

    @staticmethod
    def _ridge_segment_offsets(ridge_rules):
        default_offsets = [(1, 0), (0, 1), (1, 1), (1, -1)]
        if not isinstance(ridge_rules, dict):
            return default_offsets
        raw_offsets = ridge_rules.get("segment_offsets")
        if not isinstance(raw_offsets, list):
            return default_offsets
        offsets = []
        for item in raw_offsets:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                continue
            try:
                dx = int(item[0])
                dy = int(item[1])
            except (TypeError, ValueError):
                continue
            if dx == 0 and dy == 0:
                continue
            if dx < 0 or (dx == 0 and dy <= 0):
                continue
            offsets.append((dx, dy))
        return offsets or default_offsets

    @staticmethod
    def _ridge_adjacency_from_offsets(
        ridge_nodes,
        segment_offsets,
        max_segment_distance,
        max_segment_drop,
    ):
        adjacency = {key: set() for key in ridge_nodes.keys()}
        for key_a in ridge_nodes.keys():
            ix, iy = key_a
            for dx, dy in segment_offsets:
                key_b = (ix + dx, iy + dy)
                if key_b not in ridge_nodes:
                    continue
                point_a = ridge_nodes[key_a]["point"]
                point_b = ridge_nodes[key_b]["point"]
                distance = math.hypot(
                    point_b.x() - point_a.x(),
                    point_b.y() - point_a.y(),
                )
                if distance > max_segment_distance:
                    continue
                elev_gap = abs(ridge_nodes[key_a]["elev"] - ridge_nodes[key_b]["elev"])
                if elev_gap > max_segment_drop:
                    continue
                adjacency[key_a].add(key_b)
                adjacency[key_b].add(key_a)
        return adjacency

    @staticmethod
    def _ridge_edge_cost(
        key_a,
        key_b,
        ridge_nodes,
        max_segment_distance,
        max_segment_drop,
    ):
        point_a = ridge_nodes[key_a]["point"]
        point_b = ridge_nodes[key_b]["point"]
        distance = math.hypot(
            point_b.x() - point_a.x(),
            point_b.y() - point_a.y(),
        )
        dist_ratio = distance / max(max_segment_distance, 1e-6)
        elev_ratio = abs(ridge_nodes[key_a]["elev"] - ridge_nodes[key_b]["elev"]) / max(
            max_segment_drop, 1e-6
        )
        strength_gap = abs(ridge_nodes[key_a]["strength"] - ridge_nodes[key_b]["strength"])
        mean_strength = (ridge_nodes[key_a]["strength"] + ridge_nodes[key_b]["strength"]) * 0.5
        return (0.50 * dist_ratio) + (0.30 * elev_ratio) + (0.20 * strength_gap) - (
            0.10 * mean_strength
        )

    def _sparsify_ridge_adjacency(
        self,
        adjacency,
        ridge_nodes,
        ridge_rules,
        max_segment_distance,
        max_segment_drop,
    ):
        max_degree = self._rule_int(ridge_rules, "max_node_degree", 2, min_value=1, max_value=8)
        orphan_extra_degree = self._rule_int(
            ridge_rules, "orphan_extra_degree", 3, min_value=1, max_value=10
        )
        orphan_extra_degree = max(max_degree + 1, orphan_extra_degree)
        orphan_strength_min = self._rule_float(
            ridge_rules, "orphan_strength_min", 0.62, min_value=0.0, max_value=1.0
        )
        edges = []
        for key_a, neighbors in adjacency.items():
            for key_b in neighbors:
                edge_key = self._ridge_edge_key(key_a, key_b)
                if edge_key[0] != key_a:
                    continue
                cost = self._ridge_edge_cost(
                    key_a=key_a,
                    key_b=key_b,
                    ridge_nodes=ridge_nodes,
                    max_segment_distance=max_segment_distance,
                    max_segment_drop=max_segment_drop,
                )
                edges.append((cost, key_a, key_b))
        if not edges:
            return adjacency

        edges.sort(key=lambda item: item[0])
        sparse = {key: set() for key in adjacency.keys()}
        degree = {key: 0 for key in adjacency.keys()}
        for _cost, key_a, key_b in edges:
            if degree[key_a] >= max_degree or degree[key_b] >= max_degree:
                continue
            sparse[key_a].add(key_b)
            sparse[key_b].add(key_a)
            degree[key_a] += 1
            degree[key_b] += 1

        for key, node in sorted(
            ridge_nodes.items(),
            key=lambda item: item[1]["strength"],
            reverse=True,
        ):
            if degree.get(key, 0) > 0:
                continue
            if node["strength"] < orphan_strength_min:
                continue
            candidates = []
            for other in adjacency.get(key, set()):
                if degree.get(other, 0) >= orphan_extra_degree:
                    continue
                cost = self._ridge_edge_cost(
                    key_a=key,
                    key_b=other,
                    ridge_nodes=ridge_nodes,
                    max_segment_distance=max_segment_distance,
                    max_segment_drop=max_segment_drop,
                )
                candidates.append((cost, other))
            if not candidates:
                continue
            candidates.sort(key=lambda item: item[0])
            best = candidates[0][1]
            sparse[key].add(best)
            sparse[best].add(key)
            degree[key] = degree.get(key, 0) + 1
            degree[best] = degree.get(best, 0) + 1

        return sparse

    @staticmethod
    def _ridge_turn_penalty(point_prev, point_curr, point_next):
        vec_a_x = point_curr.x() - point_prev.x()
        vec_a_y = point_curr.y() - point_prev.y()
        vec_b_x = point_next.x() - point_curr.x()
        vec_b_y = point_next.y() - point_curr.y()
        len_a = math.hypot(vec_a_x, vec_a_y)
        len_b = math.hypot(vec_b_x, vec_b_y)
        if len_a <= 1e-6 or len_b <= 1e-6:
            return 1.0
        dot = ((vec_a_x * vec_b_x) + (vec_a_y * vec_b_y)) / (len_a * len_b)
        dot = max(-1.0, min(1.0, dot))
        return 1.0 - dot

    @classmethod
    def _ridge_path_step_cost(cls, prev_key, current_key, next_key, ridge_nodes):
        path_rules = cls._rules_section("ridge_path")
        turn_weight = cls._rule_float(path_rules, "turn_weight", 0.66, min_value=0.0)
        length_weight = cls._rule_float(
            path_rules, "length_weight", 0.22, min_value=0.0
        )
        strength_weight = cls._rule_float(
            path_rules, "strength_weight", 0.12, min_value=0.0
        )
        weight_sum = turn_weight + length_weight + strength_weight
        if weight_sum <= 0:
            turn_weight, length_weight, strength_weight = 0.66, 0.22, 0.12
            weight_sum = 1.0
        turn_weight /= weight_sum
        length_weight /= weight_sum
        strength_weight /= weight_sum

        prev_point = ridge_nodes[prev_key]["point"]
        current_point = ridge_nodes[current_key]["point"]
        next_point = ridge_nodes[next_key]["point"]
        turn_penalty = cls._ridge_turn_penalty(prev_point, current_point, next_point)
        prev_len = math.hypot(
            current_point.x() - prev_point.x(),
            current_point.y() - prev_point.y(),
        )
        next_len = math.hypot(
            next_point.x() - current_point.x(),
            next_point.y() - current_point.y(),
        )
        length_penalty = abs(next_len - prev_len) / max(prev_len, 1e-6)
        strength_penalty = abs(
            ridge_nodes[next_key]["strength"] - ridge_nodes[current_key]["strength"]
        )
        return (turn_weight * turn_penalty) + (length_weight * length_penalty) + (
            strength_weight * strength_penalty
        )

    def _ridge_endpoint_bridge_penalty(self, key, other, adjacency, ridge_nodes):
        if key not in adjacency or other not in adjacency:
            return 1.0
        if len(adjacency[key]) != 1 or len(adjacency[other]) != 1:
            return 1.0
        prev_key = next(iter(adjacency[key]))
        prev_other = next(iter(adjacency[other]))
        point_prev = ridge_nodes[prev_key]["point"]
        point_key = ridge_nodes[key]["point"]
        point_other = ridge_nodes[other]["point"]
        point_prev_other = ridge_nodes[prev_other]["point"]
        penalty_a = self._ridge_turn_penalty(point_prev, point_key, point_other)
        penalty_b = self._ridge_turn_penalty(point_prev_other, point_other, point_key)
        return (penalty_a + penalty_b) * 0.5

    def _bridge_ridge_endpoints(self, adjacency, ridge_nodes, spacing, elev_range):
        endpoints = [key for key, neighbors in adjacency.items() if len(neighbors) == 1]
        bridge_rules = self._rules_section("ridge_bridge")
        max_endpoint_count = self._rule_int(
            bridge_rules, "max_endpoint_count", 1800, min_value=2
        )
        max_bridge_pairs = self._rule_int(
            bridge_rules, "max_bridge_pairs", 8, min_value=0
        )
        if len(endpoints) < 2:
            return 0
        if len(endpoints) > max_endpoint_count:
            return 0
        if max_bridge_pairs <= 0:
            return 0

        max_distance_factor = self._rule_float(
            bridge_rules, "max_distance_factor", 2.0, min_value=0.1
        )
        elev_tolerance_floor = self._rule_float(
            bridge_rules, "elev_tolerance_floor", 1.5, min_value=0.1
        )
        elev_tolerance_ratio = self._rule_float(
            bridge_rules, "elev_tolerance_ratio", 0.10, min_value=1e-6
        )
        distance_weight = self._rule_float(
            bridge_rules, "distance_weight", 0.50, min_value=0.0
        )
        elev_weight = self._rule_float(
            bridge_rules, "elev_weight", 0.22, min_value=0.0
        )
        strength_weight = self._rule_float(
            bridge_rules, "strength_weight", 0.10, min_value=0.0
        )
        direction_weight = self._rule_float(
            bridge_rules, "direction_weight", 0.18, min_value=0.0
        )
        max_direction_penalty = self._rule_float(
            bridge_rules, "max_direction_penalty", 0.65, min_value=0.0
        )
        max_distance = spacing * max_distance_factor
        max_distance_sq = max_distance * max_distance
        elev_tolerance = max(elev_tolerance_floor, elev_range * elev_tolerance_ratio)
        used = set()
        bridged = 0

        for key in endpoints:
            if bridged >= max_bridge_pairs:
                break
            if key in used:
                continue

            point = ridge_nodes[key]["point"]
            elev = ridge_nodes[key]["elev"]
            strength = ridge_nodes[key]["strength"]
            best = None
            best_score = None
            for other in endpoints:
                if other == key or other in used:
                    continue
                if other in adjacency[key]:
                    continue

                other_elev = ridge_nodes[other]["elev"]
                if abs(elev - other_elev) > elev_tolerance:
                    continue

                other_point = ridge_nodes[other]["point"]
                dx = point.x() - other_point.x()
                dy = point.y() - other_point.y()
                distance_sq = (dx * dx) + (dy * dy)
                if distance_sq > max_distance_sq:
                    continue
                distance_ratio = math.sqrt(distance_sq) / max_distance
                elev_ratio = abs(elev - other_elev) / elev_tolerance
                strength_ratio = abs(strength - ridge_nodes[other]["strength"])
                direction_penalty = self._ridge_endpoint_bridge_penalty(
                    key=key,
                    other=other,
                    adjacency=adjacency,
                    ridge_nodes=ridge_nodes,
                )
                if direction_penalty > max_direction_penalty:
                    continue
                score = (distance_ratio * distance_weight) + (elev_ratio * elev_weight) + (
                    strength_ratio * strength_weight
                ) + (
                    direction_penalty * direction_weight
                )
                if best is None or score < best_score:
                    best = other
                    best_score = score

            if best is None:
                continue
            adjacency[key].add(best)
            adjacency[best].add(key)
            used.add(key)
            used.add(best)
            bridged += 1

        return bridged

    def _ridge_paths_from_graph(self, adjacency, ridge_nodes):
        component_rules = self._rules_section("ridge_component")
        min_component_nodes = self._rule_int(
            component_rules, "min_component_nodes", 5, min_value=2
        )
        secondary_component_nodes = self._rule_int(
            component_rules, "secondary_component_nodes", 7, min_value=2
        )
        secondary_length_ratio = self._rule_float(
            component_rules, "secondary_length_ratio", 0.55, min_value=0.1, max_value=1.0
        )

        components = self._ridge_components(adjacency)
        components.sort(
            key=lambda component: (
                len(component),
                sum(ridge_nodes[key]["strength"] for key in component) / max(1, len(component)),
            ),
            reverse=True,
        )

        paths = []
        for component in components:
            if len(component) < min_component_nodes:
                continue
            tree = self._ridge_component_spanning_tree(component, adjacency, ridge_nodes)
            primary_path = self._ridge_tree_diameter(tree, ridge_nodes, component)
            if len(primary_path) < 2:
                continue
            paths.append(primary_path)

            interior = set(primary_path[1:-1])
            remainder = {
                key for key in component if key not in interior and len(tree.get(key, set())) > 0
            }
            if len(remainder) < secondary_component_nodes:
                continue

            remainder_tree = {
                key: {neighbor for neighbor in tree.get(key, set()) if neighbor in remainder}
                for key in remainder
            }
            remainder_components = self._ridge_components(remainder_tree)
            if not remainder_components:
                continue
            secondary_component = max(remainder_components, key=len)
            if len(secondary_component) < secondary_component_nodes:
                continue
            secondary_path = self._ridge_tree_diameter(
                remainder_tree,
                ridge_nodes,
                secondary_component,
            )
            if len(secondary_path) < 2:
                continue
            primary_length = self._ridge_path_length_by_keys(primary_path, ridge_nodes)
            secondary_length = self._ridge_path_length_by_keys(secondary_path, ridge_nodes)
            if secondary_length >= (primary_length * secondary_length_ratio):
                paths.append(secondary_path)

        return paths

    @staticmethod
    def _densify_polyline(points, max_step=1.0):
        if len(points) < 2:
            return [QgsPointXY(point.x(), point.y()) for point in points]

        step = max(0.5, float(max_step))
        densified = [QgsPointXY(points[0].x(), points[0].y())]
        for idx in range(len(points) - 1):
            point_a = points[idx]
            point_b = points[idx + 1]
            dx = point_b.x() - point_a.x()
            dy = point_b.y() - point_a.y()
            seg_len = math.hypot(dx, dy)
            if seg_len > step:
                insert_count = int(seg_len / step)
                for offset in range(1, insert_count + 1):
                    ratio = offset / (insert_count + 1)
                    densified.append(
                        QgsPointXY(
                            point_a.x() + (dx * ratio),
                            point_a.y() + (dy * ratio),
                        )
                    )
            densified.append(QgsPointXY(point_b.x(), point_b.y()))
        return densified

    @classmethod
    def _rank_ridge_paths(cls, raw_paths):
        if not raw_paths:
            return []

        rank_rules = cls._rules_section("ridge_ranking")
        length_weight = cls._rule_float(
            rank_rules, "score_length_weight", 0.62, min_value=0.0
        )
        strength_weight = cls._rule_float(
            rank_rules, "score_strength_weight", 0.38, min_value=0.0
        )
        node_weight = cls._rule_float(
            rank_rules, "score_node_weight", 0.18, min_value=0.0
        )
        weight_sum = length_weight + strength_weight + node_weight
        if weight_sum <= 0:
            length_weight = 0.62
            strength_weight = 0.38
            node_weight = 0.0
            weight_sum = 1.0
        length_weight /= weight_sum
        strength_weight /= weight_sum
        node_weight /= weight_sum

        max_len = max(item["len"] for item in raw_paths)
        max_len = max(max_len, 1e-6)
        max_nodes = max(item.get("node_count", 0) for item in raw_paths)
        max_nodes = max(max_nodes, 1)
        scored = []
        for item in raw_paths:
            length_norm = item["len"] / max_len
            node_norm = item.get("node_count", 0) / max_nodes
            score = (
                (length_weight * length_norm)
                + (strength_weight * item["strength"])
                + (node_weight * node_norm)
            )
            scored.append((score, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)

        total_candidates = len(scored)
        keep_ratio_rules = rank_rules.get("keep_ratio_rules", [])
        keep_ratio_default = cls._rule_float(
            rank_rules, "default_keep_ratio", 0.70, min_value=0.01, max_value=1.0
        )
        keep_ratio = cls._rule_threshold_value(
            keep_ratio_rules,
            total_candidates,
            "ratio",
            keep_ratio_default,
        )
        try:
            keep_ratio = float(keep_ratio)
        except (TypeError, ValueError):
            keep_ratio = keep_ratio_default
        keep_ratio = max(0.01, min(1.0, keep_ratio))
        min_keep_count = cls._rule_int(
            rank_rules, "min_keep_count", 12, min_value=1
        )
        keep_count = max(min_keep_count, int(total_candidates * keep_ratio))
        scored = scored[:keep_count]

        ranked = []
        total = len(scored)
        major_percentile_threshold = cls._rule_float(
            rank_rules, "major_percentile_threshold", 0.30, min_value=0.0, max_value=1.0
        )
        for index, (score_value, item) in enumerate(scored, start=1):
            percentile = index / total
            if percentile <= major_percentile_threshold:
                ridge_class = "major"
            else:
                ridge_class = "minor"
            ranked.append(
                {
                    "ridge_id": index,
                    "ridge_rank": index,
                    "ridge_class": ridge_class,
                    "ridge_score": score_value,
                    "percentile": percentile,
                    "total_count": total,
                    "points": item["points"],
                    "len": item["len"],
                    "strength": item["strength"],
                    "elev_a": item["elev_a"],
                    "elev_b": item["elev_b"],
                }
            )
        return ranked

    def _hydro_spacing(self, dem_layer, dem_step):
        rules = self._rules_section("hydro_network")
        spacing_step_factor = self._rule_float(
            rules, "spacing_step_factor", 3.2, min_value=0.1
        )
        spacing_coarse_factor = self._rule_float(
            rules, "spacing_coarse_factor", 0.58, min_value=0.01
        )
        spacing_fallback = self._rule_float(
            rules, "spacing_fallback", 1.0, min_value=0.1
        )
        max_points = self._rule_int(rules, "spacing_max_points", 26000, min_value=50)
        coarse = self._adaptive_spacing(dem_layer, dem_step)
        extent = dem_layer.extent()
        return compute_hydro_spacing(
            dem_step=dem_step,
            coarse_spacing=coarse,
            width=extent.width(),
            height=extent.height(),
            spacing_step_factor=spacing_step_factor,
            spacing_coarse_factor=spacing_coarse_factor,
            spacing_fallback=spacing_fallback,
            max_points=max_points,
        )

    @classmethod
    def _hydro_keep_quantile(cls, node_count):
        rules = cls._rules().get("hydro_keep_quantile_rules", [])
        default_quantile = 0.86
        value = cls._rule_threshold_value(
            rules,
            int(node_count),
            "quantile",
            default_quantile,
        )
        return clamp_quantile(value, default_quantile=default_quantile)

    @classmethod
    def _hydro_min_order(cls, node_count):
        rules = cls._rules().get("hydro_min_order_rules", [])
        value = cls._rule_threshold_value(
            rules,
            int(node_count),
            "order",
            2,
        )
        return clamp_min_order(value, default_order=2)

    @classmethod
    def _hydro_min_path_length(cls, dem_layer, spacing, node_count):
        rules = cls._rules_section("hydro_min_path_rules")
        base_spacing_factor = cls._rule_float(
            rules, "base_spacing_factor", 4.0, min_value=0.1
        )
        base_diag_ratio = cls._rule_float(
            rules, "base_diag_ratio", 0.006, min_value=1e-6
        )
        size_rules = rules.get("size_rules", [])
        extent = dem_layer.extent()
        diag = math.hypot(extent.width(), extent.height())
        length = max(spacing * base_spacing_factor, diag * base_diag_ratio)
        sized = cls._rule_threshold_value(
            size_rules,
            int(node_count),
            "spacing_factor",
            None,
        )
        return compute_hydro_min_path_length(
            width=extent.width(),
            height=extent.height(),
            spacing=spacing,
            base_spacing_factor=base_spacing_factor,
            base_diag_ratio=base_diag_ratio,
            node_spacing_factor=sized,
        )

    @staticmethod
    def _compute_stream_order(nodes, downstream, upstream):
        return compute_stream_order(nodes, downstream, upstream)

    @staticmethod
    def _trace_downstream_path(
        start,
        selected_downstream,
        upstream_selected,
        visited_edges,
    ):
        return trace_downstream_path(
            start,
            selected_downstream,
            upstream_selected,
            visited_edges,
        )

    @staticmethod
    def _stream_class(order):
        return stream_class(order)

    @staticmethod
    def _binary_classification_metrics(labels, scores):
        return binary_classification_metrics(labels, scores)

    @staticmethod
    def _trapezoid_auc(points):
        return trapezoid_auc(points)

    def _sector_extreme(
        self, provider, center_point, radius, center_azimuth, mode, span=80.0, samples=17
    ):
        best_point = None
        best_elev = None
        best_azimuth = None
        for index in range(samples):
            ratio = 0.0 if samples <= 1 else (index / (samples - 1))
            azimuth = (center_azimuth - (span / 2.0) + (ratio * span)) % 360.0
            point = self._offset_point(center_point, radius, azimuth)
            elev = self._sample_dem(provider, point)
            if elev is None:
                continue
            if best_elev is None:
                best_point, best_elev, best_azimuth = point, elev, azimuth
                continue
            if mode == "max" and elev > best_elev:
                best_point, best_elev, best_azimuth = point, elev, azimuth
            if mode == "min" and elev < best_elev:
                best_point, best_elev, best_azimuth = point, elev, azimuth
        return best_point, best_elev, best_azimuth

    def _ring_extreme(self, provider, center_point, radius, mode):
        best_point = None
        best_elev = None
        best_azimuth = None
        for azimuth in range(0, 360, 8):
            point = self._offset_point(center_point, radius, azimuth)
            elev = self._sample_dem(provider, point)
            if elev is None:
                continue
            if best_elev is None:
                best_point, best_elev, best_azimuth = point, elev, azimuth
                continue
            if mode == "max" and elev > best_elev:
                best_point, best_elev, best_azimuth = point, elev, azimuth
            if mode == "min" and elev < best_elev:
                best_point, best_elev, best_azimuth = point, elev, azimuth
        return best_point, best_elev, best_azimuth

    def _sector_gentle_point(
        self, provider, center_point, radius, center_azimuth, reference
    ):
        best_point = None
        best_elev = None
        best_delta = None
        for azimuth in range(int(center_azimuth - 45), int(center_azimuth + 46), 6):
            point = self._offset_point(center_point, radius, azimuth % 360.0)
            elev = self._sample_dem(provider, point)
            if elev is None:
                continue
            delta = abs(elev - reference)
            if best_delta is None or delta < best_delta:
                best_point, best_elev, best_delta = point, elev, delta
        return best_point, best_elev

    @staticmethod
    def _profile_weighted_score(indicators, profile):
        return profile_weighted_score(indicators, profile)

    @staticmethod
    def _profile_confidence(indicators, profile):
        return profile_confidence(indicators, profile)

    @staticmethod
    def _indicator_label_ko(key):
        labels = {
            "slope": "경사",
            "aspect": "향",
            "form": "형국",
            "long": "종심",
            "water": "수계",
            "conv": "수렴습윤",
            "tpi": "TPI",
            "sashinsa": "사신사",
            "enclosure": "장풍",
        }
        return labels.get(key, key)

    @staticmethod
    def _indicator_contributions(indicators, profile):
        return indicator_contributions(indicators, profile)

    def _compose_site_reason(
        self,
        profile_key,
        context,
        profile,
        indicators,
        dem_metrics,
        water_distance,
        slope_value,
        aspect_value,
        total_score,
        principle_summary,
        weight_note,
    ):
        contributions = self._indicator_contributions(indicators, profile)
        top_rows = contributions[:3]
        weak_rows = sorted(contributions, key=lambda item: item["score"])[:2]
        top_text = ", ".join(
            (
                f"{self._indicator_label_ko(item['key'])} "
                f"{item['score']:.2f}(w{item['weight']:.2f})"
            )
            for item in top_rows
        )
        weak_text = ", ".join(
            (
                f"{self._indicator_label_ko(item['key'])} "
                f"{item['score']:.2f}(w{item['weight']:.2f})"
            )
            for item in weak_rows
        )

        score_text = self._fmt_num(total_score, 3)
        percent_text = self._fmt_num(
            (total_score * 100.0) if total_score is not None else None,
            1,
        )
        grade = self._score_band_label(total_score)
        slope_text = "n/a" if slope_value is None else f"{slope_value:.2f}°"
        if aspect_value is None:
            aspect_text = "n/a"
        else:
            aspect_text = f"{aspect_value:.1f}°({self._azimuth_label(aspect_value)})"
        water_text = "n/a" if water_distance is None else f"{water_distance:.1f}m"
        target_text = self._fmt_num(context.get("water_distance_target"), 1)
        sigma_text = self._fmt_num(context.get("water_distance_sigma"), 1)

        tpi_class = self._tpi_class_label(
            dem_metrics.get("tpi_norm"),
            dem_metrics.get("large_tpi_norm"),
        )
        metric_text = (
            f"수렴도 {self._fmt_num(dem_metrics.get('convergence'), 3)}, "
            f"대TPI {self._fmt_num(dem_metrics.get('large_tpi_norm'), 4)}({tpi_class}), "
            f"표면조도 {self._fmt_num(dem_metrics.get('roughness'), 3)}, "
            f"절개깊이 {self._fmt_num(dem_metrics.get('cut_depth'), 3)}"
        )
        context_text = (
            f"보정층=컨텍스트 {context.get('culture_key')}/{context.get('period_key')}, "
            f"프로파일 {profile_key}"
        )
        paper_evidence_summary = self._paper_evidence_summary(profile)
        parts = [
            f"원리판독: {principle_summary}" if principle_summary else "",
            f"적합도 {score_text} ({grade}, {percent_text}/100 환산)",
            f"가중기여: {top_text}" if top_text else "가중기여: n/a",
            f"보완요인: {weak_text}" if weak_text else "보완요인: n/a",
            f"현장값: 경사 {slope_text}, 향 {aspect_text}, 수계거리 {water_text} (목표 {target_text}±{sigma_text}m)",
            f"보조지형: {metric_text}",
            context_text,
            f"프로파일 가중요약: {weight_note}" if weight_note else "",
            f"문헌검증: {paper_evidence_summary}" if paper_evidence_summary else "",
        ]
        reason = " | ".join(part for part in parts if part)
        if len(reason) > 1000:
            return f"{reason[:997]}..."
        return reason

    @classmethod
    def _paper_evidence_summary(cls, profile):
        return paper_evidence_summary(profile, language="ko", limit=3)

    @staticmethod
    def _explain_top_factors(indicators, profile):
        return explain_top_factors(indicators, profile)

    def _compute_large_tpi_value(
        self,
        provider,
        site_point,
        center,
        macro_radius,
        relief=None,
    ):
        """대규모 TPI(Topographic Position Index) - 광역 지형 위치 지수.

        참고문헌:
        • Um, J.-S. (2012). "Feng-Shui Theory and Practice Investigated by
          Spatial Regression Modeling." In Application of Geographic Information
          Systems. IntechOpen. doi:10.5772/51071
          → 팔공산 일대 한국 묘지 분포: 국지(소규모) + 광역(대규모) 이중 지형 위치 분석.
        • Lee, S. & Kim, J. (2021). "Hierarchical Landform Delineation for the
          Habitats of Biological Communities on the Korean Peninsula."
          PLOS ONE 16(10):e0259651. doi:10.1371/journal.pone.0259651
          → 이중-스케일 TPI: 소규모(능선/계곡) + 대규모(산지/평지) 조합 지형 분류.
        • Weiss, A.D. (2001). Topographic Position and Landforms Analysis.
          ESRI International User Conference, San Diego.
          → TPI 원본 방법론 및 이중 스케일 지형 분류표.

        소규모 TPI(fs_tpi): macro_radius 기준 (이미 계산됨)
        대규모 TPI(fs_tpi_lg): macro_radius × radius_multiplier 기준
        두 스케일 조합으로 풍수 혈의 계층적 지형 위치 파악 가능.
        """
        if site_point is None or center is None:
            return None
        try:
            large_rules = self._rules_section("large_tpi")
        except RuntimeError:
            return None
        multiplier = max(1.1, float(large_rules.get("radius_multiplier", 3.0)))
        n_samples  = max(8, int(large_rules.get("num_samples", 16)))
        large_radius = macro_radius * multiplier
        step = 360.0 / n_samples
        values = []
        for idx in range(n_samples):
            pt = self._offset_point(site_point, large_radius, idx * step)
            v = self._sample_dem(provider, pt)
            if v is not None:
                values.append(v)
        if not values:
            return None
        mean_large = sum(values) / len(values)
        tpi_large  = center - mean_large
        denom = relief if (relief is not None and relief > 0) else max(1.0, abs(tpi_large))
        return tpi_large / denom

    @staticmethod
    def _tpi_class_label(tpi_small, tpi_large=None):
        return tpi_class_label(tpi_small, tpi_large)

    @staticmethod
    def _sashinsa_hint(sashinsa_score):
        return sashinsa_hint(sashinsa_score)

    @staticmethod
    def _enclosure_hint(enclosure_index):
        return enclosure_hint(enclosure_index)
