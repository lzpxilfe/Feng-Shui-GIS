# -*- coding: utf-8 -*-
from collections import defaultdict, deque
import math
import random

from qgis import processing
from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsCoordinateTransform,
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
    QgsSpatialIndex,
    QgsVectorLayer,
    edit,
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
        scored_layer = self.run(
            site_layer=input_layer,
            dem_layer=dem_layer,
            water_layer=water_layer,
            hemisphere=hemisphere,
            profile_key=profile_key,
            culture_key=culture_key,
            period_key=period_key,
        )

        labels = []
        scores = []
        for feature in scored_layer.getFeatures():
            label = feature["fs_label"] if "fs_label" in feature.fields().names() else None
            score = self._to_float(feature["fs_score"]) if "fs_score" in feature.fields().names() else None
            if label is None or score is None:
                continue
            labels.append(int(label))
            scores.append(float(score))

        metrics = self._binary_classification_metrics(labels, scores)
        context = build_context(culture_key, period_key, hemisphere)
        report = {
            "culture_key": culture_key,
            "period_key": period_key,
            "profile_key": profile_key,
            "hemisphere": hemisphere,
            "negative_ratio": negative_ratio,
            "random_seed": random_seed,
            "positive_count": len(positive_points),
            "negative_count": len(negative_points),
            "valid_count": metrics["count"],
            "roc_auc": metrics["roc_auc"],
            "pr_auc": metrics["pr_auc"],
            "best_f1": metrics["best_f1"],
            "best_f1_threshold": metrics["best_f1_threshold"],
            "best_youden_j": metrics["best_youden_j"],
            "best_youden_threshold": metrics["best_youden_threshold"],
            "evidence_parameters": context.get("evidence", {}).get("parameters", {}),
        }
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
    ):
        context = build_context(culture_key, period_key, hemisphere)
        profile = self._contextualize_profile(
            self._profile_spec(profile_key),
            context,
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

        if to_add:
            layer.dataProvider().addAttributes(to_add)
            layer.updateFields()

    def _score_points(
        self, site_layer, dem_layer, water_layer, hemisphere, profile_key, context
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
        profile = self._profile_spec(profile_key)
        profile = self._contextualize_profile(profile, context)

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
                    "slope": self._score_profile_slope(slope_value, profile),
                    "aspect": self._score_aspect(aspect_value, hemisphere, context=context),
                    "form": dem_metrics["form_score"],
                    "long": dem_metrics["long_score"],
                    "water": water_score,
                    "conv": dem_metrics["convergence"],
                    "tpi": self._score_profile_tpi(dem_metrics["tpi_norm"], profile),
                }

                total_score = self._profile_weighted_score(indicators, profile)
                confidence = self._profile_confidence(indicators, profile)
                note = self._explain_top_factors(indicators, profile)
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
                    note=note,
                )

                feature["fs_culture"] = context["culture_key"]
                feature["fs_period"] = context["period_key"]
                feature["fs_model"] = profile_key
                feature["fs_conf"] = confidence
                feature["fs_note"] = note
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
                site_layer.updateFeature(feature)

    @classmethod
    def _profile_spec(cls, profile_key):
        return profile_spec(profile_key)

    def _prepare_water_reference(self, dem_layer, water_layer):
        if dem_layer is None or water_layer is None:
            return None, None

        dem_crs = dem_layer.crs()
        water_to_dem = self._build_transform(water_layer.crs(), dem_crs)
        indexed_features = []
        transformed_geoms = {}
        for src_feature in water_layer.getFeatures():
            if not src_feature.hasGeometry():
                continue
            transformed = self._transform_geometry(
                src_feature.geometry(),
                water_to_dem,
            )
            if transformed is None or transformed.isEmpty():
                continue
            feature_id = int(src_feature.id())
            indexed = QgsFeature()
            indexed.setId(feature_id)
            indexed.setGeometry(transformed)
            indexed_features.append(indexed)
            transformed_geoms[feature_id] = transformed
        if not indexed_features:
            return None, None
        spatial_index = QgsSpatialIndex()
        for indexed_feature in indexed_features:
            spatial_index.addFeature(indexed_feature)
        return spatial_index, transformed_geoms

    @staticmethod
    def _contextualize_profile(profile, context):
        adjusted = {
            "weights": dict(profile["weights"]),
            "slope_target": profile["slope_target"],
            "slope_sigma": profile["slope_sigma"],
            "tpi_target": profile["tpi_target"],
            "tpi_sigma": profile["tpi_sigma"],
        }
        for key, delta in context.get("weight_bias", {}).items():
            adjusted["weights"][key] = max(0.0, adjusted["weights"].get(key, 0.0) + delta)

        total = sum(adjusted["weights"].values())
        if total > 0:
            adjusted["weights"] = {
                key: value / total for key, value in adjusted["weights"].items()
            }
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

    def _build_transform(self, source_crs, target_crs):
        if source_crs is None or target_crs is None:
            raise RuntimeError("Missing CRS required for coordinate transform.")
        if not source_crs.isValid() or not target_crs.isValid():
            raise RuntimeError("Invalid CRS encountered while preparing coordinate transform.")
        if source_crs == target_crs:
            return None

        project = self.context.project() if self.context is not None else None
        if project is None:
            project = QgsProject.instance()
        try:
            return QgsCoordinateTransform(source_crs, target_crs, project)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to build coordinate transform: {source_crs.authid()} -> {target_crs.authid()}"
            ) from exc

    @staticmethod
    def _transform_point(point, transformer):
        if point is None:
            return None
        if transformer is None:
            return QgsPointXY(point.x(), point.y())
        try:
            transformed = transformer.transform(QgsPointXY(point.x(), point.y()))
            return QgsPointXY(transformed.x(), transformed.y())
        except Exception as exc:
            raise RuntimeError("Failed to transform point geometry.") from exc

    @staticmethod
    def _transform_geometry(geometry, transformer):
        if geometry is None or geometry.isEmpty():
            return None
        cloned = QgsGeometry(geometry)
        if transformer is None:
            return cloned
        try:
            cloned.transform(transformer)
            return cloned
        except Exception as exc:
            raise RuntimeError("Failed to transform feature geometry.") from exc

    @staticmethod
    def _geometry_point(geometry):
        if geometry is None or geometry.isEmpty():
            return None

        centroid = geometry.centroid()
        if centroid is None or centroid.isEmpty():
            return None

        point = centroid.asPoint()
        if point is None:
            return None
        return QgsPointXY(point.x(), point.y())

    @staticmethod
    def _feature_point(feature):
        if feature is None or not feature.hasGeometry():
            return None
        return FengShuiAnalyzer._geometry_point(feature.geometry())

    def _collect_points(self, layer, target_crs=None):
        points = []
        transformer = None
        if target_crs is not None and layer is not None and hasattr(layer, "crs"):
            transformer = self._build_transform(layer.crs(), target_crs)
        for feature in layer.getFeatures():
            point = self._feature_point(feature)
            point = self._transform_point(point, transformer)
            if point is not None:
                points.append(point)
        return points

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
        min_distance = max(
            dem_step * 20.0,
            min(extent.width(), extent.height()) / 240.0,
        )
        min_distance_sq = min_distance * min_distance
        min_negative_separation_sq = (min_distance * 0.40) ** 2
        rng = random.Random(random_seed)
        points = []
        trial_cap = max(target_count * 120, 3000)
        trial = 0

        while len(points) < target_count and trial < trial_cap:
            trial += 1
            x = rng.uniform(extent.xMinimum(), extent.xMaximum())
            y = rng.uniform(extent.yMinimum(), extent.yMaximum())
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
        x_res = abs(dem_layer.rasterUnitsPerPixelX())
        y_res = abs(dem_layer.rasterUnitsPerPixelY())
        step = max(x_res, y_res)
        return step if step > 0 else 1.0

    def _nearest_water_distance(self, site_geom, site_point, water_index, water_geoms):
        if (
            site_geom is None
            or site_geom.isEmpty()
            or site_point is None
            or water_index is None
            or not water_geoms
        ):
            return None

        candidate_ids = water_index.nearestNeighbor(site_point, 12)
        if not candidate_ids:
            return None

        best = None
        for fid in candidate_ids:
            water_geom = water_geoms.get(fid)
            if water_geom is None:
                continue
            distance = site_geom.distance(water_geom)
            if best is None or distance < best:
                best = distance
        return best

    @staticmethod
    def _score_gaussian(value, target, sigma):
        if value is None:
            return None
        sigma = max(sigma, 1e-9)
        return math.exp(-((value - target) / sigma) ** 2)

    @staticmethod
    def _score_aspect(aspect_deg, hemisphere, context=None):
        if aspect_deg is None:
            return None
        if context:
            target = float(context["aspect_target"])
            sharpness = max(0.5, float(context["aspect_sharpness"]))
        else:
            target = 180.0 if hemisphere == "north" else 0.0
            sharpness = 1.0
        diff = abs((aspect_deg - target + 180.0) % 360.0 - 180.0)
        base_score = (math.cos(math.radians(diff)) + 1.0) / 2.0
        return max(0.0, min(1.0, base_score**sharpness))

    @staticmethod
    def _score_water_distance(distance_m, context=None):
        if distance_m is None:
            return None
        if not context:
            raise RuntimeError("Water-distance scoring requires a validated context.")
        target = float(context["water_distance_target"])
        sigma = float(context["water_distance_sigma"])
        score = math.exp(-((distance_m - target) / sigma) ** 2)
        if distance_m < 30.0:
            return max(0.1, score * 0.5)
        return score

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
        null_metrics = {
            "form_score": None,
            "long_score": None,
            "dem_water_score": None,
            "tpi_norm": None,
            "convergence": None,
        }
        if site_point is None:
            return null_metrics

        center = self._sample_dem(provider, site_point)
        if center is None:
            return null_metrics

        sampling_rules = self._rules_section("sampling")
        dem_rules = self._rules_section("dem_metrics")

        micro_mult = 1.0
        macro_mult = 1.0
        if context:
            micro_mult = float(context["micro_radius_multiplier"])
            macro_mult = float(context["macro_radius_multiplier"])
        micro_radius = dem_step * float(sampling_rules["micro_radius_factor"]) * micro_mult
        macro_radius = dem_step * float(sampling_rules["macro_radius_factor"]) * macro_mult

        macro_bearing_step = int(sampling_rules["macro_bearing_step"])
        micro_bearing_step = int(sampling_rules["micro_bearing_step"])
        macro_bearings = list(range(0, 360, max(1, macro_bearing_step)))
        micro_bearings = list(range(0, 360, max(1, micro_bearing_step)))

        macro_values = self._sample_ring(provider, site_point, macro_radius, macro_bearings)
        micro_values = self._sample_ring(provider, site_point, micro_radius, micro_bearings)

        relief = None
        mean_macro = None
        std_macro = None
        std_micro = None
        if macro_values:
            relief = max(macro_values) - min(macro_values)
            mean_macro = sum(macro_values) / len(macro_values)
            std_macro = self._stddev(macro_values)
        if micro_values:
            std_micro = self._stddev(micro_values)

        card = self.CARDINALS.get(hemisphere, self.CARDINALS["north"])
        back_mean = self._direction_mean(provider, site_point, macro_radius, card["back"])
        front_mean = self._direction_mean(provider, site_point, macro_radius, card["front"])
        left_mean = self._direction_mean(provider, site_point, macro_radius, card["left"])
        right_mean = self._direction_mean(provider, site_point, macro_radius, card["right"])

        form_score = None
        if (
            relief is not None
            and relief > 0
            and back_mean is not None
            and front_mean is not None
            and left_mean is not None
            and right_mean is not None
        ):
            back_norm = (back_mean - center) / relief
            front_norm = (center - front_mean) / relief
            side_norm = (left_mean - right_mean) / relief

            back_spec = dem_rules["form_back"]
            front_spec = dem_rules["form_front"]
            side_spec = dem_rules["form_side"]
            back_score = self._score_gaussian(
                back_norm, float(back_spec["target"]), float(back_spec["sigma"])
            )
            front_score = self._score_gaussian(
                front_norm, float(front_spec["target"]), float(front_spec["sigma"])
            )
            side_score = self._score_gaussian(
                side_norm, float(side_spec["target"]), float(side_spec["sigma"])
            )
            form_score = self._mean_scores(back_score, front_score, side_score)

        long_score = None
        tpi_norm = None
        if relief is not None and relief > 0 and mean_macro is not None:
            tpi = center - mean_macro
            tpi_norm = tpi / relief
            xue_spec = dem_rules["xue"]
            xue_score = self._score_gaussian(
                tpi_norm, float(xue_spec["target"]), float(xue_spec["sigma"])
            )
            hierarchy_ratio = None
            if std_micro is not None and std_macro is not None and std_macro > 0:
                hierarchy_ratio = std_micro / std_macro
            hierarchy_spec = dem_rules["hierarchy"]
            hierarchy_score = self._score_gaussian(
                hierarchy_ratio,
                float(hierarchy_spec["target"]),
                float(hierarchy_spec["sigma"]),
            )
            long_score = self._mean_scores(xue_score, hierarchy_score)

        dem_water_score = None
        convergence = None
        if micro_values:
            higher = sum(max(value - center, 0.0) for value in micro_values)
            lower = sum(max(center - value, 0.0) for value in micro_values)
            convergence = higher / (higher + lower + 1e-6)

            if slope_deg is None:
                slope_factor = 0.75
            else:
                slope_denominator = float(dem_rules["slope_denominator"])
                slope_factor = max(0.25, 1.0 - min(1.0, slope_deg / slope_denominator))

            wetness_spec = dem_rules["wetness"]
            wetness_shape = self._score_gaussian(
                convergence,
                float(wetness_spec["target"]),
                float(wetness_spec["sigma"]),
            )
            dem_water_score = max(
                0.0, min(1.0, wetness_shape * (0.6 + 0.4 * slope_factor))
            )

        return {
            "form_score": form_score,
            "long_score": long_score,
            "dem_water_score": dem_water_score,
            "tpi_norm": tpi_norm,
            "convergence": convergence,
        }

    @staticmethod
    def _sample_dem(provider, point):
        value, ok = provider.sample(point, 1)
        if not ok:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _offset_point(point, distance, azimuth_deg):
        rad = math.radians(azimuth_deg)
        return QgsPointXY(
            point.x() + (distance * math.sin(rad)),
            point.y() + (distance * math.cos(rad)),
        )

    def _sample_ring(self, provider, center_point, radius, azimuths):
        values = []
        for azimuth in azimuths:
            sample_point = self._offset_point(center_point, radius, azimuth)
            sample_value = self._sample_dem(provider, sample_point)
            if sample_value is not None:
                values.append(sample_value)
        return values

    @staticmethod
    def _mean_scores(*values):
        valid = [v for v in values if v is not None]
        if not valid:
            return None
        return sum(valid) / len(valid)

    @staticmethod
    def _fmt_num(value, digits=3):
        if value is None:
            return "n/a"
        return f"{float(value):.{digits}f}"

    @staticmethod
    def _azimuth_label(azimuth):
        if azimuth is None:
            return "ring"
        directions = [
            "북",
            "북동",
            "동",
            "남동",
            "남",
            "남서",
            "서",
            "북서",
        ]
        idx = int(((azimuth % 360.0) + 22.5) // 45.0) % 8
        return directions[idx]

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
        mode_ko = {
            "max": "국지 최대점",
            "min": "국지 최소점",
            "gentle": "완경사점",
            "refine": "전면 보정점",
        }.get(mode, "추정점")
        mode_hint = {
            "max": "주변보다 상대적으로 높은 위치를 찾았습니다",
            "min": "주변보다 상대적으로 낮은 위치를 찾았습니다",
            "gentle": "경사가 완만한 위치를 찾았습니다",
            "refine": "중심 혈 전면에서 위치를 미세 보정했습니다",
        }.get(mode, "지형 패턴에 맞는 후보를 찾았습니다")
        return (
            f"{term_label_ko(term_id)} 후보입니다. 쉽게 보면 {mode_hint}. "
            f"요약: 점수 {self._fmt_num(adjusted_score, 3)}, 적합도 {self._fmt_num(fit_score, 3)}, "
            f"고도 {self._fmt_num(elev, 2)}m. "
            f"[세부] 기저점수={self._fmt_num(base_score, 3)}, "
            f"상대고도={self._fmt_num(delta_rel, 4)}(목표 {self._fmt_num(target_rel, 4)}), "
            f"반경={self._fmt_num(radius_m, 1)}m, "
            f"방위={self._fmt_num(azimuth, 1)}°({self._azimuth_label(azimuth)}), "
            f"추출방식={mode_ko}, 근거={note}."
        )

    @staticmethod
    def _score_band_label(value):
        if value is None:
            return "정보 없음"
        if value >= 0.8:
            return "매우 양호"
        if value >= 0.65:
            return "양호"
        if value >= 0.5:
            return "보통"
        return "낮음"

    @staticmethod
    def _tpi_hint(tpi_norm):
        if tpi_norm is None:
            return "지형 곡률 정보 없음"
        if tpi_norm <= -0.08:
            return "완만한 오목 지형에 가까움"
        if tpi_norm < 0.08:
            return "평탄에 가까운 중립 지형"
        return "완만한 볼록 지형에 가까움"

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
    ):
        gap_text = "판정 불가"
        if base_score is not None:
            gap = base_score - threshold
            if gap >= 0:
                gap_text = f"기준치보다 +{gap:.3f} 높아 통과"
            else:
                gap_text = f"기준치보다 {gap:.3f} 낮음"

        return (
            f"혈 후보 #{rank}/{selected_total}. 한 줄 해석: {gap_text}입니다. "
            f"형국 {self._fmt_num(form_score, 3)}({self._score_band_label(form_score)}), "
            f"종심 {self._fmt_num(long_score, 3)}({self._score_band_label(long_score)}), "
            f"수렴습윤 {self._fmt_num(wet_score, 3)}({self._score_band_label(wet_score)}), "
            f"수렴도 {self._fmt_num(conv_score, 3)}({self._score_band_label(conv_score)}), "
            f"TPI {self._fmt_num(tpi_norm, 4)}({self._tpi_hint(tpi_norm)}), "
            f"주변 기복 {self._fmt_num(relief, 1)}m, 중심 고도 {self._fmt_num(center_elev, 2)}m. "
            f"[세부수치] 점수={self._fmt_num(base_score, 3)}, 기준치>={threshold:.3f}."
        )

    @staticmethod
    def _stddev(values):
        if not values:
            return None
        if len(values) == 1:
            return 0.0
        mean_value = sum(values) / len(values)
        variance = sum((value - mean_value) ** 2 for value in values) / len(values)
        return math.sqrt(variance)

    def _direction_mean(self, provider, center_point, radius, center_azimuth):
        offsets = (-30.0, -15.0, 0.0, 15.0, 30.0)
        values = []
        for offset in offsets:
            azimuth = (center_azimuth + offset) % 360.0
            sample_point = self._offset_point(center_point, radius, azimuth)
            sample_value = self._sample_dem(provider, sample_point)
            if sample_value is not None:
                values.append(sample_value)
        if not values:
            return None
        return sum(values) / len(values)

    @staticmethod
    def _combine_hydro_scores(distance_score, dem_score):
        if distance_score is not None and dem_score is not None:
            return (0.7 * distance_score) + (0.3 * dem_score)
        if distance_score is not None:
            return distance_score
        return dem_score

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
        min_span = min(extent.width(), extent.height())
        spacing = max(dem_step * base_step_factor, min_span / min_span_divisor)
        if spacing <= 0:
            spacing = max(dem_step * base_step_factor, fallback_spacing)

        cols = max(1, int(width / spacing) + 1)
        rows = max(1, int(height / spacing) + 1)
        total = cols * rows
        if total > max_points:
            spacing *= math.sqrt(total / max_points)
            cols = max(1, int(width / spacing) + 1)
            rows = max(1, int(height / spacing) + 1)
            total = cols * rows
        return {
            "dem_step": dem_step,
            "width": width,
            "height": height,
            "spacing": spacing,
            "approx_nodes": total,
            "max_points": max_points,
        }

    def _adaptive_spacing(self, dem_layer, dem_step):
        return self.adaptive_spacing_diagnostics(dem_layer, dem_step)["spacing"]

    def _recommended_hyeol_count(self, dem_layer, spacing):
        rules = self._rules_section("hyeol_selection")
        thresholds = rules.get("recommended_count_thresholds", [])
        default_count = self._rule_int(
            rules, "default_recommended_count", 5, min_value=1
        )

        extent = dem_layer.extent()
        approx_cols = max(1, int(extent.width() / max(spacing, 1e-6)))
        approx_rows = max(1, int(extent.height() / max(spacing, 1e-6)))
        approx_nodes = approx_cols * approx_rows
        count = self._rule_threshold_value(
            thresholds,
            approx_nodes,
            "count",
            default_count,
        )
        try:
            return max(1, int(count))
        except (TypeError, ValueError):
            return default_count

    @staticmethod
    def _grid_points(dem_layer, spacing):
        extent = dem_layer.extent()
        x_start = extent.xMinimum() + (spacing * 0.5)
        y_start = extent.yMinimum() + (spacing * 0.5)
        x = x_start
        while x < extent.xMaximum():
            y = y_start
            while y < extent.yMaximum():
                yield QgsPointXY(x, y)
                y += spacing
            x += spacing

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
            water_distance_score = self._score_water_distance(
                water_distance,
                context=context,
            )
            water_score = self._combine_hydro_scores(
                distance_score=water_distance_score,
                dem_score=metrics["dem_water_score"],
            )

            hyeol_indicators = {
                "slope": self._score_profile_slope(slope_value, profile),
                "aspect": self._score_aspect(aspect_value, hemisphere, context=context),
                "form": metrics["form_score"],
                "long": metrics["long_score"],
                "water": water_score,
                "conv": metrics["convergence"],
                "tpi": self._score_profile_tpi(tpi_norm, profile),
            }
            hyeol_score = self._profile_weighted_score(hyeol_indicators, profile)
            if hyeol_score is None or hyeol_score < context["hyeol_threshold"]:
                continue

            candidates.append(
                {
                    "point": point,
                    "score": hyeol_score,
                    "elev": center,
                    "metrics": metrics,
                    "water_distance": water_distance,
                    "hydro_score": water_score,
                }
            )

        candidates.sort(key=lambda item: item["score"], reverse=True)
        return candidates

    @staticmethod
    def _suppress_near_duplicates(candidates, min_distance, keep):
        selected = []
        min_sq = min_distance * min_distance
        for item in candidates:
            point = item["point"]
            too_close = False
            for selected_item in selected:
                dx = point.x() - selected_item["point"].x()
                dy = point.y() - selected_item["point"].y()
                if (dx * dx) + (dy * dy) < min_sq:
                    too_close = True
                    break
            if too_close:
                continue
            selected.append(item)
            if len(selected) >= keep:
                break
        return selected

    def _build_term_layer(
        self, dem_layer, provider, hemisphere, dem_step, selected, context, profile_key
    ):
        layer_name = f"{dem_layer.name()}_fengshui_terms"
        term_layer = QgsVectorLayer(
            f"Point?crs={dem_layer.crs().authid()}",
            layer_name,
            "memory",
        )
        data = term_layer.dataProvider()
        fields = QgsFields()
        fields.append(QgsField("term_id", QVariant.String, "string", 28))
        fields.append(QgsField("term_ko", QVariant.String, "string", 28))
        fields.append(QgsField("term_name", QVariant.String, "string", 28))
        fields.append(QgsField("culture", QVariant.String, "string", 20))
        fields.append(QgsField("period", QVariant.String, "string", 20))
        fields.append(QgsField("profile", QVariant.String, "string", 20))
        fields.append(QgsField("parent_id", QVariant.Int))
        fields.append(QgsField("rank", QVariant.Int))
        fields.append(QgsField("score", QVariant.Double, "double", 7, 3))
        fields.append(QgsField("elev", QVariant.Double, "double", 12, 3))
        fields.append(QgsField("base_sc", QVariant.Double, "double", 7, 3))
        fields.append(QgsField("delta_rel", QVariant.Double, "double", 8, 4))
        fields.append(QgsField("target_rel", QVariant.Double, "double", 8, 4))
        fields.append(QgsField("fit_sc", QVariant.Double, "double", 7, 3))
        fields.append(QgsField("radius_m", QVariant.Double, "double", 12, 3))
        fields.append(QgsField("azimuth", QVariant.Double, "double", 7, 2))
        fields.append(QgsField("mode", QVariant.String, "string", 8))
        fields.append(QgsField("relief_m", QVariant.Double, "double", 12, 3))
        fields.append(QgsField("note", QVariant.String, "string", 80))
        fields.append(QgsField("reason_ko", QVariant.String, "string", 1024))
        data.addAttributes(fields)
        term_layer.updateFields()

        card = self.CARDINALS.get(hemisphere, self.CARDINALS["north"])
        scales = term_radius_scales()
        inner_radius = (
            dem_step
            * float(scales["inner"])
            * float(context["micro_radius_multiplier"])
        )
        outer_radius = (
            dem_step
            * float(scales["outer"])
            * float(context["macro_radius_multiplier"])
        )
        far_radius = (
            dem_step
            * float(scales["far"])
            * float(context["macro_radius_multiplier"])
        )
        culture_id = context["culture_key"]
        period_id = context["period_key"]
        term_bias = context.get("term_bias", {})
        term_target_shift = float(context["term_target_shift"])
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
        term_min_score = max(
            min_score_floor,
            float(context["hyeol_threshold"]) * threshold_multiplier,
        )

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
            adjusted_score = score
            if adjusted_score is not None:
                adjusted_score = max(
                    0.0,
                    min(1.0, adjusted_score + term_bias.get(term_id, 0.0)),
                )
            if (
                not mandatory
                and adjusted_score is not None
                and adjusted_score < term_min_score
            ):
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
            self._append_term_feature(
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
            relief = 1.0
            if ring_values:
                relief = max(1.0, max(ring_values) - min(ring_values))

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
            )
            add_term(
                term_id="hyeol",
                term_name=term_label("hyeol", "en"),
                parent_id=parent_id,
                rank=rank,
                point=center_point,
                score=base_score,
                elev=center_elev,
                note="core candidate",
                mandatory=True,
                base_score_value=base_score,
                relief_m=relief,
                reason_text=hyeol_reason,
            )

            radius_map = {"inner": inner_radius, "outer": outer_radius, "far": far_radius}
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
            myeongdang_score = self._mean_scores(base_score, myeongdang_fit)
            add_term(
                term_id="myeongdang",
                term_name=term_label("myeongdang", "en"),
                parent_id=parent_id,
                rank=rank,
                point=myeongdang_point,
                score=myeongdang_score,
                elev=myeongdang_elev,
                note="open core basin",
                mandatory=True,
                base_score_value=base_score,
                delta_rel=myeongdang_delta,
                target_rel=myeongdang_target,
                fit_score=myeongdang_fit,
                radius_m=myeongdang_radius * float(myeongdang_spec["offset_factor"]),
                azimuth=card[myeongdang_spec["direction"]],
                mode="refine",
                relief_m=relief,
            )
            for spec in term_specs():
                term_id = spec["term_id"]
                term_name = term_label(term_id, "en")
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
                score = self._mean_scores(
                    base_score,
                    fit_score,
                )
                add_term(
                    term_id=term_id,
                    term_name=term_name,
                    parent_id=parent_id,
                    rank=rank,
                    point=point,
                    score=score,
                    elev=elev,
                    note=f"delta={delta:.3f}",
                    base_score_value=base_score,
                    delta_rel=delta,
                    target_rel=target_rel,
                    fit_score=fit_score,
                    radius_m=radius,
                    azimuth=azimuth,
                    mode=mode,
                    relief_m=relief,
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
                score = self._mean_scores(
                    base_score,
                    fit_score,
                )
                add_term(
                    term_id="ipsu",
                    term_name=term_label("ipsu", "en"),
                    parent_id=parent_id,
                    rank=rank,
                    point=ipsu_point,
                    score=score,
                    elev=ipsu_elev,
                    note=f"ring_min delta={delta:.3f}",
                    base_score_value=base_score,
                    delta_rel=delta,
                    target_rel=target_rel,
                    fit_score=fit_score,
                    radius_m=ipsu_radius,
                    azimuth=None,
                    mode=ipsu_spec["mode"],
                    relief_m=relief,
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
                score = self._mean_scores(
                    base_score,
                    fit_score,
                )
                add_term(
                    term_id="misa",
                    term_name=term_label("misa", "en"),
                    parent_id=parent_id,
                    rank=rank,
                    point=misa_point,
                    score=score,
                    elev=misa_elev,
                    note=f"gentle delta={delta:.3f}",
                    base_score_value=base_score,
                    delta_rel=delta,
                    target_rel=target_rel,
                    fit_score=fit_score,
                    radius_m=radius_map[misa_spec["radius"]],
                    azimuth=card[misa_spec["direction"]],
                    mode="gentle",
                    relief_m=relief,
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
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromPointXY(point))
        feature["term_id"] = term_id
        feature["term_ko"] = term_ko if term_ko else term_id
        feature["term_name"] = term_name
        feature["culture"] = culture if culture else ""
        feature["period"] = period if period else ""
        feature["profile"] = profile if profile else ""
        feature["parent_id"] = parent_id
        feature["rank"] = rank
        feature["score"] = score
        feature["elev"] = elev
        feature["base_sc"] = base_sc
        feature["delta_rel"] = delta_rel
        feature["target_rel"] = target_rel
        feature["fit_sc"] = fit_sc
        feature["radius_m"] = radius_m
        feature["azimuth"] = azimuth
        feature["mode"] = mode if mode else ""
        feature["relief_m"] = relief_m
        feature["note"] = note
        feature["reason_ko"] = reason_ko if reason_ko else ""
        layer.dataProvider().addFeature(feature)

    def build_term_links(self, term_layer):
        link_layer = QgsVectorLayer(
            f"LineString?crs={term_layer.crs().authid()}",
            f"{term_layer.name()}_links",
            "memory",
        )
        data = link_layer.dataProvider()
        fields = QgsFields()
        fields.append(QgsField("term_id", QVariant.String, "string", 28))
        fields.append(QgsField("term_ko", QVariant.String, "string", 28))
        fields.append(QgsField("term_en", QVariant.String, "string", 28))
        fields.append(QgsField("parent_id", QVariant.Int))
        fields.append(QgsField("rank", QVariant.Int))
        fields.append(QgsField("score", QVariant.Double, "double", 7, 3))
        fields.append(QgsField("culture", QVariant.String, "string", 20))
        fields.append(QgsField("period", QVariant.String, "string", 20))
        fields.append(QgsField("profile", QVariant.String, "string", 20))
        fields.append(QgsField("src_id", QVariant.String, "string", 28))
        fields.append(QgsField("src_ko", QVariant.String, "string", 28))
        fields.append(QgsField("src_en", QVariant.String, "string", 28))
        fields.append(QgsField("dst_id", QVariant.String, "string", 28))
        fields.append(QgsField("dst_ko", QVariant.String, "string", 28))
        fields.append(QgsField("dst_en", QVariant.String, "string", 28))
        fields.append(QgsField("link_type", QVariant.String, "string", 20))
        fields.append(QgsField("len_m", QVariant.Double, "double", 12, 3))
        fields.append(QgsField("azimuth", QVariant.Double, "double", 7, 2))
        fields.append(QgsField("curved", QVariant.Int))
        fields.append(QgsField("reason_ko", QVariant.String, "string", 1024))
        data.addAttributes(fields)
        link_layer.updateFields()
        link_rules = self._rules_section("term_links")
        path_plan = self._term_link_plan(link_rules)

        grouped = defaultdict(dict)
        for feature in term_layer.getFeatures():
            term_id = feature["term_id"]
            parent_id = feature["parent_id"]
            if not term_id or parent_id is None:
                continue
            if not feature.hasGeometry():
                continue
            grouped[parent_id][term_id] = feature

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

                distinct_points = self._distinct_points(
                    points, min_distance=distinct_min_distance
                )
                if len(distinct_points) < 2:
                    continue

                smoothed_points = self._smooth_polyline(
                    distinct_points, passes=smooth_passes
                )
                if len(smoothed_points) < 2:
                    continue

                source = nodes[0]
                target = nodes[-1]
                source_id = source["term_id"]
                target_id = target["term_id"]
                style_term = spec["style_term"]

                score = self._path_mean_score(nodes)
                if (
                    score is not None
                    and score < min_link_score
                    and spec["link_type"] != "backbone"
                ):
                    continue

                origin = smoothed_points[0]
                destination = smoothed_points[-1]
                dx = destination.x() - origin.x()
                dy = destination.y() - origin.y()
                length_m = self._polyline_length(smoothed_points)
                if length_m <= 0:
                    continue
                azimuth = (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0
                rank_value = (
                    source["rank"] if source["rank"] is not None else target["rank"]
                )

                line_feature = QgsFeature(link_layer.fields())
                line_feature.setGeometry(QgsGeometry.fromPolylineXY(smoothed_points))
                line_feature["term_id"] = style_term
                line_feature["term_ko"] = term_label_ko(style_term)
                line_feature["term_en"] = term_label(style_term, "en")
                line_feature["parent_id"] = parent_id
                line_feature["rank"] = rank_value
                line_feature["score"] = score
                line_feature["culture"] = source["culture"] or target["culture"]
                line_feature["period"] = source["period"] or target["period"]
                line_feature["profile"] = source["profile"] or target["profile"]
                line_feature["src_id"] = source_id
                line_feature["src_ko"] = term_label_ko(source_id)
                line_feature["src_en"] = term_label(source_id, "en")
                line_feature["dst_id"] = target_id
                line_feature["dst_ko"] = term_label_ko(target_id)
                line_feature["dst_en"] = term_label(target_id, "en")
                line_feature["link_type"] = spec["link_type"]
                line_feature["len_m"] = length_m
                line_feature["azimuth"] = azimuth
                line_feature["curved"] = 1
                score_text = "n/a" if score is None else f"{score:.3f}"
                line_feature["reason_ko"] = (
                    f"{spec['label']} 경로 {term_label_ko(source_id)}→{term_label_ko(target_id)}. "
                    f"표현={term_label_ko(style_term)}, 형태=완만 곡선, 평균점수={score_text}, "
                    f"거리={length_m:.1f}m, 방위={azimuth:.1f}°({self._azimuth_label(azimuth)}), "
                    "명당 중심 방사 연결 대신 감싸는 구조를 우선 적용."
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
            },
            {
                "node_ids": ["oecheongnyong", "josan", "oebaekho"],
                "style_term": "oecheongnyong",
                "link_type": "outer_wrap",
                "label": "Outer Wrap",
            },
            {
                "node_ids": ["naecheongnyong", "ansan", "naebaekho"],
                "style_term": "myeongdang",
                "link_type": "inner_wrap",
                "label": "Inner Wrap",
            },
            {
                "node_ids": ["jusan", "myeongdang", "ansan"],
                "style_term": "myeongdang",
                "link_type": "core_axis",
                "label": "Core Axis",
            },
            {
                "node_ids": ["naesugu", "ansan", "oesugu"],
                "style_term": "naesugu",
                "link_type": "front_arc",
                "label": "Front Arc",
            },
            {
                "node_ids": ["naesugu", "oesugu", "ipsu"],
                "style_term": "naesugu",
                "link_type": "water_flow",
                "label": "Water Flow",
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
            normalized.append(
                {
                    "node_ids": clean_nodes,
                    "style_term": style_term,
                    "link_type": link_type,
                    "label": label,
                }
            )
        return normalized or default_plan

    @staticmethod
    def _path_mean_score(features):
        values = []
        for feature in features:
            value = FengShuiAnalyzer._to_float(feature["score"])
            if value is not None:
                values.append(value)
        if not values:
            return None
        return sum(values) / len(values)

    @staticmethod
    def _polyline_length(points):
        length = 0.0
        for idx in range(1, len(points)):
            prev = points[idx - 1]
            curr = points[idx]
            length += math.hypot(curr.x() - prev.x(), curr.y() - prev.y())
        return length

    @staticmethod
    def _distinct_points(points, min_distance=0.1):
        if not points:
            return []
        clean = [QgsPointXY(points[0].x(), points[0].y())]
        min_sq = max(1e-6, float(min_distance) * float(min_distance))
        for point in points[1:]:
            prev = clean[-1]
            dx = point.x() - prev.x()
            dy = point.y() - prev.y()
            if (dx * dx) + (dy * dy) < min_sq:
                continue
            clean.append(QgsPointXY(point.x(), point.y()))
        if len(clean) == 1 and len(points) > 1:
            tail = points[-1]
            clean.append(QgsPointXY(tail.x(), tail.y()))
        return clean

    @staticmethod
    def _smooth_polyline(points, passes=1):
        if len(points) < 3 or passes <= 0:
            return [QgsPointXY(point.x(), point.y()) for point in points]

        current = [QgsPointXY(point.x(), point.y()) for point in points]
        for _ in range(passes):
            if len(current) < 3:
                break
            smoothed = [QgsPointXY(current[0].x(), current[0].y())]
            for idx in range(len(current) - 1):
                point_a = current[idx]
                point_b = current[idx + 1]
                qx = (0.75 * point_a.x()) + (0.25 * point_b.x())
                qy = (0.75 * point_a.y()) + (0.25 * point_b.y())
                rx = (0.25 * point_a.x()) + (0.75 * point_b.x())
                ry = (0.25 * point_a.y()) + (0.75 * point_b.y())
                smoothed.append(QgsPointXY(qx, qy))
                smoothed.append(QgsPointXY(rx, ry))
            smoothed.append(QgsPointXY(current[-1].x(), current[-1].y()))
            current = smoothed
        return current

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

    def style_term_points(self, term_layer):
        style_map = point_styles()
        categories = []
        for term_id, style in style_map.items():
            fill_color, size, stroke_color, stroke_width = style
            if term_id == "hyeol":
                size_scale = 0.92
                opacity = 0.95
            elif term_id == "myeongdang":
                size_scale = 0.86
                opacity = 0.88
            else:
                size_scale = 0.70
                opacity = 0.68
            symbol = QgsMarkerSymbol.createSimple(
                {
                    "name": "circle",
                    "color": fill_color,
                    "size": str(max(1.8, float(size) * size_scale)),
                    "outline_color": stroke_color,
                    "outline_width": str(max(0.35, float(stroke_width) * 0.75)),
                }
            )
            symbol.setOpacity(opacity)
            categories.append(QgsRendererCategory(term_id, symbol, term_id))

        renderer = QgsCategorizedSymbolRenderer("term_id", categories)
        fallback = QgsMarkerSymbol.createSimple(
            {
                "name": "circle",
                "color": "#cccccc",
                "size": "2.1",
                "outline_color": "#555555",
                "outline_width": "0.35",
            }
        )
        fallback.setOpacity(0.60)
        renderer.setSourceSymbol(fallback)
        term_layer.setRenderer(renderer)
        term_layer.triggerRepaint()

    def style_term_links(self, link_layer):
        style_map = line_styles()
        categories = []
        for term_id, style in style_map.items():
            color, width = style
            symbol = QgsLineSymbol.createSimple(
                {
                    "line_color": color,
                    "line_width": str(max(0.38, float(width) * 0.42)),
                    "line_style": "solid",
                    "capstyle": "round",
                    "joinstyle": "round",
                }
            )
            symbol.setOpacity(0.32)
            categories.append(QgsRendererCategory(term_id, symbol, term_id))

        renderer = QgsCategorizedSymbolRenderer("term_id", categories)
        default_symbol = QgsLineSymbol.createSimple(
            {
                "line_color": "#777777",
                "line_width": "0.50",
                "line_style": "solid",
                "capstyle": "round",
                "joinstyle": "round",
            }
        )
        default_symbol.setOpacity(0.20)
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
        class_styles = {
            "main": ("#0b3d91", 1.7, 0.62),
            "secondary": ("#1456b8", 1.35, 0.54),
            "branch": ("#2b7bd8", 1.0, 0.44),
            "minor": ("#63a5ff", 0.8, 0.34),
        }
        categories = []
        for class_id, (color, width, opacity) in class_styles.items():
            symbol = QgsLineSymbol.createSimple(
                {
                    "line_color": color,
                    "line_width": str(width),
                    "line_style": "solid",
                    "capstyle": "round",
                    "joinstyle": "round",
                }
            )
            symbol.setOpacity(opacity)
            categories.append(QgsRendererCategory(class_id, symbol, class_id))

        renderer = QgsCategorizedSymbolRenderer("stream_class", categories)
        fallback = QgsLineSymbol.createSimple(
            {
                "line_color": "#5f93d2",
                "line_width": "0.6",
                "line_style": "solid",
            }
        )
        fallback.setOpacity(0.26)
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
        class_styles = {
            "major": ("#22302e", 1.55, 0.78),
            "minor": ("#54615f", 0.65, 0.24),
        }
        categories = []
        for class_id, (color, width, opacity) in class_styles.items():
            symbol = QgsLineSymbol.createSimple(
                {
                    "line_color": color,
                    "line_width": str(width),
                    "line_style": "solid",
                    "capstyle": "round",
                    "joinstyle": "round",
                }
            )
            symbol.setOpacity(opacity)
            categories.append(
                QgsRendererCategory(
                    class_id,
                    symbol,
                    FengShuiAnalyzer._ridge_label(class_id, "ko"),
                )
            )

        renderer = QgsCategorizedSymbolRenderer("ridge_class", categories)
        fallback = QgsLineSymbol.createSimple(
            {
                "line_color": "#3d3d3d",
                "line_width": "0.70",
                "line_style": "solid",
            }
        )
        fallback.setOpacity(0.25)
        renderer.setSourceSymbol(fallback)
        ridge_layer.setRenderer(renderer)
        ridge_layer.triggerRepaint()

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
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return default_quantile

    @classmethod
    def _hydro_min_order(cls, node_count):
        rules = cls._rules().get("hydro_min_order_rules", [])
        value = cls._rule_threshold_value(
            rules,
            int(node_count),
            "order",
            2,
        )
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return 2

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
        if sized is not None:
            try:
                length = max(length, spacing * max(0.1, float(sized)))
            except (TypeError, ValueError):
                pass
        return length

    @staticmethod
    def _compute_stream_order(nodes, downstream, upstream):
        pending = {key: len(upstream.get(key, [])) for key in nodes.keys()}
        seeds = [key for key, cnt in pending.items() if cnt == 0]
        seeds.sort(key=lambda k: nodes[k]["elev"], reverse=True)
        queue = deque(seeds)
        order = {}
        collected = defaultdict(list)

        while queue:
            key = queue.popleft()
            incoming = collected.get(key, [])
            if not incoming:
                order[key] = 1
            else:
                max_value = max(incoming)
                if incoming.count(max_value) >= 2:
                    order[key] = max_value + 1
                else:
                    order[key] = max_value

            target = downstream.get(key)
            if target is None:
                continue
            collected[target].append(order[key])
            pending[target] -= 1
            if pending[target] == 0:
                queue.append(target)

        return order

    @staticmethod
    def _trace_downstream_path(
        start,
        selected_downstream,
        upstream_selected,
        visited_edges,
    ):
        if start not in selected_downstream:
            return None

        path = [start]
        current = start
        while current in selected_downstream:
            target = selected_downstream[current]
            edge_key = (current, target)
            if edge_key in visited_edges:
                break
            visited_edges.add(edge_key)
            path.append(target)
            if upstream_selected.get(target, 0) != 1:
                break
            current = target

        if len(path) < 2:
            return None
        return path

    @staticmethod
    def _stream_class(order):
        if order >= 6:
            return "main"
        if order >= 5:
            return "secondary"
        if order >= 4:
            return "branch"
        return "minor"

    @staticmethod
    def _binary_classification_metrics(labels, scores):
        if not labels or not scores or len(labels) != len(scores):
            return {
                "count": 0,
                "roc_auc": 0.0,
                "pr_auc": 0.0,
                "best_f1": 0.0,
                "best_f1_threshold": 0.0,
                "best_youden_j": 0.0,
                "best_youden_threshold": 0.0,
            }

        pairs = sorted(zip(scores, labels), key=lambda item: item[0], reverse=True)
        positive_count = sum(1 for _, label in pairs if label == 1)
        negative_count = sum(1 for _, label in pairs if label == 0)
        if positive_count == 0 or negative_count == 0:
            return {
                "count": len(pairs),
                "roc_auc": 0.0,
                "pr_auc": 0.0,
                "best_f1": 0.0,
                "best_f1_threshold": 0.0,
                "best_youden_j": 0.0,
                "best_youden_threshold": 0.0,
            }

        tp = 0
        fp = 0
        roc_points = [(0.0, 0.0)]
        pr_points = [(0.0, 1.0)]
        best_f1 = (0.0, pairs[0][0])
        best_youden = (-999.0, pairs[0][0])

        index = 0
        while index < len(pairs):
            score = pairs[index][0]
            group_tp = 0
            group_fp = 0
            while index < len(pairs) and pairs[index][0] == score:
                if pairs[index][1] == 1:
                    group_tp += 1
                else:
                    group_fp += 1
                index += 1

            tp += group_tp
            fp += group_fp
            tpr = tp / positive_count
            fpr = fp / negative_count
            precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
            recall = tpr
            roc_points.append((fpr, tpr))
            pr_points.append((recall, precision))

            f1 = (
                (2.0 * precision * recall) / (precision + recall)
                if (precision + recall) > 0
                else 0.0
            )
            if f1 > best_f1[0]:
                best_f1 = (f1, score)
            youden = tpr - fpr
            if youden > best_youden[0]:
                best_youden = (youden, score)

        roc_auc = FengShuiAnalyzer._trapezoid_auc(roc_points)
        pr_auc = FengShuiAnalyzer._trapezoid_auc(pr_points)
        return {
            "count": len(pairs),
            "roc_auc": roc_auc,
            "pr_auc": pr_auc,
            "best_f1": best_f1[0],
            "best_f1_threshold": best_f1[1],
            "best_youden_j": best_youden[0],
            "best_youden_threshold": best_youden[1],
        }

    @staticmethod
    def _trapezoid_auc(points):
        if len(points) < 2:
            return 0.0
        ordered = sorted(points, key=lambda item: item[0])
        area = 0.0
        for index in range(1, len(ordered)):
            x0, y0 = ordered[index - 1]
            x1, y1 = ordered[index]
            dx = x1 - x0
            if dx <= 0:
                continue
            area += dx * ((y0 + y1) * 0.5)
        return max(0.0, min(1.0, area))

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
        weights = profile["weights"]
        weighted = []
        for key, weight in weights.items():
            value = indicators.get(key)
            if value is not None:
                weighted.append((weight, value))
        if not weighted:
            return None
        numerator = sum(weight * value for weight, value in weighted)
        denominator = sum(weight for weight, _ in weighted)
        return numerator / denominator

    @staticmethod
    def _profile_confidence(indicators, profile):
        weights = profile["weights"]
        total = sum(weights.values())
        if total <= 0:
            return None
        available = 0.0
        for key, weight in weights.items():
            if indicators.get(key) is not None:
                available += weight
        return available / total

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
        }
        return labels.get(key, key)

    @staticmethod
    def _indicator_contributions(indicators, profile):
        rows = []
        weights = profile.get("weights", {})
        if not isinstance(weights, dict):
            return rows
        for key, weight in weights.items():
            score = indicators.get(key)
            if score is None:
                continue
            try:
                weight_value = float(weight)
                score_value = float(score)
            except (TypeError, ValueError):
                continue
            rows.append(
                {
                    "key": key,
                    "weight": weight_value,
                    "score": score_value,
                    "contrib": weight_value * score_value,
                }
            )
        rows.sort(key=lambda item: item["contrib"], reverse=True)
        return rows

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
        note,
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

        metric_text = (
            f"형국 {self._fmt_num(dem_metrics.get('form_score'), 3)}, "
            f"종심 {self._fmt_num(dem_metrics.get('long_score'), 3)}, "
            f"수렴습윤 {self._fmt_num(dem_metrics.get('dem_water_score'), 3)}, "
            f"수렴도 {self._fmt_num(dem_metrics.get('convergence'), 3)}, "
            f"TPI {self._fmt_num(dem_metrics.get('tpi_norm'), 4)}"
            f"({self._tpi_hint(dem_metrics.get('tpi_norm'))})"
        )
        context_text = (
            f"컨텍스트={context.get('culture_key')}/{context.get('period_key')}, "
            f"모델={profile_key}"
        )
        parts = [
            f"적합도 {score_text} ({grade}, {percent_text}/100 환산)",
            f"상위기여: {top_text}" if top_text else "상위기여: n/a",
            f"보완요인: {weak_text}" if weak_text else "보완요인: n/a",
            f"현장값: 경사 {slope_text}, 향 {aspect_text}, 수계거리 {water_text} (목표 {target_text}±{sigma_text}m)",
            f"세부지표: {metric_text}",
            context_text,
            f"가중요약: {note}" if note else "",
        ]
        reason = " | ".join(part for part in parts if part)
        if len(reason) > 1000:
            return f"{reason[:997]}..."
        return reason

    @staticmethod
    def _explain_top_factors(indicators, profile):
        weighted = []
        for key, weight in profile["weights"].items():
            score = indicators.get(key)
            if score is None:
                continue
            weighted.append((weight * score, key, score))
        if not weighted:
            return "no-data"
        weighted.sort(reverse=True)
        top = weighted[:2]
        return ",".join(f"{key}:{score:.2f}" for _, key, score in top)
