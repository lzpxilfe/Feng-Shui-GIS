# -*- coding: utf-8 -*-
from collections import defaultdict, deque
import math

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
    term_label,
    term_label_ko,
    term_radius_scales,
    term_specs,
)

RIDGE_CLASS_LABELS_KO = {
    "daegan": "대간",
    "jeongmaek": "정맥",
    "gimaek": "기맥",
    "jimaek": "지맥",
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

    def extract_terms(
        self,
        dem_layer,
        hemisphere="north",
        culture_key="east_asia",
        period_key="early_modern",
        max_hyeol=5,
    ):
        context = build_context(culture_key, period_key, hemisphere)
        provider = dem_layer.dataProvider()
        dem_step = self._dem_step(dem_layer)
        sample_spacing = self._adaptive_spacing(dem_layer, dem_step)
        recommended_count = self._recommended_hyeol_count(dem_layer, sample_spacing)
        effective_keep = max(1, min(max_hyeol, recommended_count))
        suppress_distance = sample_spacing * (10.5 if effective_keep <= 3 else 9.0)
        candidates = self._collect_hyeol_candidates(
            provider=provider,
            dem_layer=dem_layer,
            hemisphere=hemisphere,
            dem_step=dem_step,
            spacing=sample_spacing,
            context=context,
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
        )

    def _as_vector_layer(self, output_obj):
        if isinstance(output_obj, QgsVectorLayer):
            return output_obj
        resolved = QgsProcessingUtils.mapLayerFromString(output_obj, self.context)
        if not isinstance(resolved, QgsVectorLayer):
            raise RuntimeError("Could not resolve sampled output layer.")
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
            to_add.append(QgsField("fs_reason", QVariant.String, "string", 254))
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
            to_add.append(QgsField("fs_score", QVariant.Double, "double", 7, 2))

        if to_add:
            layer.dataProvider().addAttributes(to_add)
            layer.updateFields()

    def _score_points(
        self, site_layer, dem_layer, water_layer, hemisphere, profile_key, context
    ):
        slope_field = self._find_field(site_layer, "sl_")
        aspect_field = self._find_field(site_layer, "as_")

        water_index = None
        water_geoms = None
        if water_layer is not None:
            water_features = [f for f in water_layer.getFeatures() if f.hasGeometry()]
            if water_features:
                water_index = QgsSpatialIndex(water_features)
                water_geoms = {f.id(): f.geometry() for f in water_features}

        dem_provider = dem_layer.dataProvider()
        dem_step = self._dem_step(dem_layer)
        profile = self._profile_spec(profile_key)
        profile = self._contextualize_profile(profile, context)

        with edit(site_layer):
            for feature in site_layer.getFeatures():
                slope_value = self._to_float(feature[slope_field]) if slope_field else None
                aspect_value = self._to_float(feature[aspect_field]) if aspect_field else None
                site_point = self._feature_point(feature)

                dem_metrics = self._compute_dem_metrics(
                    provider=dem_provider,
                    site_point=site_point,
                    slope_deg=slope_value,
                    hemisphere=hemisphere,
                    dem_step=dem_step,
                    context=context,
                )

                water_distance = self._nearest_water_distance(
                    feature=feature,
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
                    "conv": dem_metrics["dem_water_score"],
                    "tpi": self._score_profile_tpi(dem_metrics["tpi_norm"], profile),
                }

                total_score = self._profile_weighted_score(indicators, profile)
                confidence = self._profile_confidence(indicators, profile)
                note = self._explain_top_factors(indicators, profile)
                score_text = "n/a" if total_score is None else f"{total_score:.2f}"
                slope_text = "n/a" if slope_value is None else f"{slope_value:.2f}"
                aspect_text = "n/a" if aspect_value is None else f"{aspect_value:.1f}"
                water_text = "n/a" if water_distance is None else f"{water_distance:.1f}"
                reason_ko = (
                    f"모델={profile_key}, 문화권={context['culture_key']}, 시대={context['period_key']}, "
                    f"총점={score_text}, 경사={slope_text}, 향={aspect_text}, "
                    f"수계거리={water_text}, 상위요인={note}"
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

    @staticmethod
    def _feature_point(feature):
        if not feature.hasGeometry():
            return None

        geom = feature.geometry()
        if geom.isEmpty():
            return None

        centroid = geom.centroid()
        if centroid.isEmpty():
            return None

        point = centroid.asPoint()
        return QgsPointXY(point.x(), point.y())

    @staticmethod
    def _dem_step(dem_layer):
        x_res = abs(dem_layer.rasterUnitsPerPixelX())
        y_res = abs(dem_layer.rasterUnitsPerPixelY())
        step = max(x_res, y_res)
        return step if step > 0 else 1.0

    def _nearest_water_distance(self, feature, site_point, water_index, water_geoms):
        if site_point is None or water_index is None or not water_geoms:
            return None

        candidate_ids = water_index.nearestNeighbor(site_point, 12)
        if not candidate_ids:
            return None

        geom = feature.geometry()
        best = None
        for fid in candidate_ids:
            water_geom = water_geoms.get(fid)
            if water_geom is None:
                continue
            distance = geom.distance(water_geom)
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
            target = context.get(
                "aspect_target",
                180.0 if hemisphere == "north" else 0.0,
            )
            sharpness = max(0.5, context.get("aspect_sharpness", 1.0))
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
        target = 220.0
        sigma = 350.0
        if context:
            target = context.get("water_distance_target", target)
            sigma = context.get("water_distance_sigma", sigma)
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

        rules = analysis_rules()
        sampling_rules = rules.get("sampling", {})
        dem_rules = rules.get("dem_metrics", {})

        micro_mult = 1.0
        macro_mult = 1.0
        if context:
            micro_mult = context.get("micro_radius_multiplier", 1.0)
            macro_mult = context.get("macro_radius_multiplier", 1.0)
        micro_radius = dem_step * float(sampling_rules.get("micro_radius_factor", 2.0)) * micro_mult
        macro_radius = dem_step * float(sampling_rules.get("macro_radius_factor", 12.0)) * macro_mult

        macro_bearing_step = int(sampling_rules.get("macro_bearing_step", 22))
        micro_bearing_step = int(sampling_rules.get("micro_bearing_step", 45))
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

            back_spec = dem_rules.get("form_back", {"target": 0.20, "sigma": 0.35})
            front_spec = dem_rules.get("form_front", {"target": 0.15, "sigma": 0.35})
            side_spec = dem_rules.get("form_side", {"target": 0.05, "sigma": 0.25})
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
            xue_spec = dem_rules.get("xue", {"target": -0.10, "sigma": 0.30})
            xue_score = self._score_gaussian(
                tpi_norm, float(xue_spec["target"]), float(xue_spec["sigma"])
            )
            hierarchy_ratio = None
            if std_micro is not None and std_macro is not None and std_macro > 0:
                hierarchy_ratio = std_micro / std_macro
            hierarchy_spec = dem_rules.get(
                "hierarchy", {"target": 0.55, "sigma": 0.30}
            )
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
                slope_denominator = float(dem_rules.get("slope_denominator", 35.0))
                slope_factor = max(0.25, 1.0 - min(1.0, slope_deg / slope_denominator))

            wetness_spec = dem_rules.get("wetness", {"target": 0.60, "sigma": 0.28})
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
        return (
            f"{term_label_ko(term_id)} 추정. 최종점수={self._fmt_num(adjusted_score, 3)}, "
            f"기저점수={self._fmt_num(base_score, 3)}, 고도={self._fmt_num(elev, 2)}m, "
            f"상대고도={self._fmt_num(delta_rel, 4)}(목표 {self._fmt_num(target_rel, 4)}), "
            f"적합도={self._fmt_num(fit_score, 3)}, 반경={self._fmt_num(radius_m, 1)}m, "
            f"방위={self._fmt_num(azimuth, 1)}°({self._azimuth_label(azimuth)}), "
            f"추출방식={mode_ko}, 근거={note}."
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

    @staticmethod
    def _adaptive_spacing(dem_layer, dem_step):
        extent = dem_layer.extent()
        min_span = min(extent.width(), extent.height())
        spacing = max(dem_step * 10.0, min_span / 180.0)
        if spacing <= 0:
            return max(dem_step * 10.0, 1.0)

        cols = max(1, int(extent.width() / spacing) + 1)
        rows = max(1, int(extent.height() / spacing) + 1)
        total = cols * rows
        max_points = 12000
        if total > max_points:
            spacing *= math.sqrt(total / max_points)
        return spacing

    @staticmethod
    def _recommended_hyeol_count(dem_layer, spacing):
        extent = dem_layer.extent()
        approx_cols = max(1, int(extent.width() / max(spacing, 1e-6)))
        approx_rows = max(1, int(extent.height() / max(spacing, 1e-6)))
        approx_nodes = approx_cols * approx_rows
        if approx_nodes >= 22000:
            return 2
        if approx_nodes >= 12000:
            return 3
        if approx_nodes >= 5000:
            return 4
        return 5

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
        self, provider, dem_layer, hemisphere, dem_step, spacing, context
    ):
        rules = analysis_rules().get("hyeol_candidate", {})
        tpi_min = float(rules.get("tpi_min", -0.45))
        tpi_max = float(rules.get("tpi_max", 0.35))
        tpi_target = float(rules.get("tpi_target", -0.08))
        tpi_sigma = float(rules.get("tpi_sigma", 0.30))
        candidates = []
        for point in self._grid_points(dem_layer, spacing):
            center = self._sample_dem(provider, point)
            if center is None:
                continue

            metrics = self._compute_dem_metrics(
                provider=provider,
                site_point=point,
                slope_deg=None,
                hemisphere=hemisphere,
                dem_step=dem_step,
                context=context,
            )
            tpi_norm = metrics["tpi_norm"]
            if tpi_norm is not None and (tpi_norm < tpi_min or tpi_norm > tpi_max):
                continue

            hyeol_shape = self._mean_scores(
                metrics["form_score"],
                metrics["long_score"],
                metrics["dem_water_score"],
            )
            tpi_score = self._score_gaussian(tpi_norm, tpi_target, tpi_sigma)
            hyeol_score = self._mean_scores(hyeol_shape, tpi_score)
            if hyeol_score is None or hyeol_score < context["hyeol_threshold"]:
                continue

            candidates.append(
                {
                    "point": point,
                    "score": hyeol_score,
                    "elev": center,
                    "metrics": metrics,
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
        self, dem_layer, provider, hemisphere, dem_step, selected, context
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
            * float(scales.get("inner", 18.0))
            * context.get("micro_radius_multiplier", 1.0)
        )
        outer_radius = (
            dem_step
            * float(scales.get("outer", 38.0))
            * context.get("macro_radius_multiplier", 1.0)
        )
        far_radius = (
            dem_step
            * float(scales.get("far", 65.0))
            * context.get("macro_radius_multiplier", 1.0)
        )
        culture_id = context.get("culture_key", "east_asia")
        period_id = context.get("period_key", "early_modern")
        term_bias = context.get("term_bias", {})
        term_target_shift = context.get("term_target_shift", 0.0)
        term_min_score = max(0.42, context.get("hyeol_threshold", 0.62) * 0.72)

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
            wet_score = metrics.get("dem_water_score")
            tpi_norm = metrics.get("tpi_norm")
            conv_score = metrics.get("convergence")

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
            hyeol_reason = (
                f"혈 후보 #{rank}/{selected_total}. 점수={self._fmt_num(base_score, 3)}, "
                f"형국={self._fmt_num(form_score, 3)}, 종심={self._fmt_num(long_score, 3)}, "
                f"수렴습윤={self._fmt_num(wet_score, 3)}, TPI={self._fmt_num(tpi_norm, 4)}, "
                f"수렴도={self._fmt_num(conv_score, 3)}, 기복={self._fmt_num(relief, 1)}m, "
                f"고도={self._fmt_num(center_elev, 2)}m, 기준치>={context['hyeol_threshold']:.3f} 충족."
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

            myeongdang_point = self._offset_point(
                center_point, inner_radius * 0.35, card["front"]
            )
            myeongdang_elev = self._sample_dem(provider, myeongdang_point)
            if myeongdang_elev is None:
                myeongdang_point = center_point
                myeongdang_elev = center_elev
            myeongdang_delta = (myeongdang_elev - center_elev) / relief
            myeongdang_target = -0.03 + (term_target_shift * 0.4)
            myeongdang_fit = self._score_gaussian(myeongdang_delta, myeongdang_target, 0.24)
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
                radius_m=inner_radius * 0.35,
                azimuth=card["front"],
                mode="refine",
                relief_m=relief,
            )

            radius_map = {"inner": inner_radius, "outer": outer_radius, "far": far_radius}
            for spec in term_specs():
                term_id = spec["term_id"]
                term_name = term_label(term_id, "en")
                radius = radius_map.get(spec.get("radius", "inner"), inner_radius)
                azimuth = card.get(spec.get("direction", "front"), card["front"])
                mode = spec.get("mode", "max")
                target = float(spec.get("target", 0.0))
                sigma = float(spec.get("sigma", 0.3))
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

            ipsu_point, ipsu_elev, _ = self._ring_extreme(
                provider=provider,
                center_point=center_point,
                radius=outer_radius,
                mode="min",
            )
            if ipsu_point is not None:
                delta = (ipsu_elev - center_elev) / relief
                target_rel = -0.22 + term_target_shift
                fit_score = self._score_gaussian(delta, target_rel, 0.35)
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
                    radius_m=outer_radius,
                    azimuth=None,
                    mode="min",
                    relief_m=relief,
                )

            misa_point, misa_elev = self._sector_gentle_point(
                provider=provider,
                center_point=center_point,
                radius=inner_radius,
                center_azimuth=card["front"],
                reference=center_elev,
            )
            if misa_point is not None:
                delta = (misa_elev - center_elev) / relief
                target_rel = -0.03 + (term_target_shift * 0.5)
                fit_score = self._score_gaussian(delta, target_rel, 0.20)
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
                    radius_m=inner_radius,
                    azimuth=card["front"],
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
        reason_ko=None,
    ):
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromPointXY(point))
        feature["term_id"] = term_id
        feature["term_ko"] = term_ko if term_ko else term_id
        feature["term_name"] = term_name
        feature["culture"] = culture if culture else ""
        feature["period"] = period if period else ""
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
        fields.append(QgsField("parent_id", QVariant.Int))
        fields.append(QgsField("rank", QVariant.Int))
        fields.append(QgsField("score", QVariant.Double, "double", 7, 3))
        fields.append(QgsField("culture", QVariant.String, "string", 20))
        fields.append(QgsField("period", QVariant.String, "string", 20))
        fields.append(QgsField("src_id", QVariant.String, "string", 28))
        fields.append(QgsField("dst_id", QVariant.String, "string", 28))
        fields.append(QgsField("len_m", QVariant.Double, "double", 12, 3))
        fields.append(QgsField("azimuth", QVariant.Double, "double", 7, 2))
        fields.append(QgsField("curved", QVariant.Int))
        fields.append(QgsField("reason_ko", QVariant.String, "string", 1024))
        data.addAttributes(fields)
        link_layer.updateFields()

        # Keep structural links but remove center-radial spokes from hyeol/myeongdang.
        link_plan = [
            ("jusan", "dunoe", "jusan"),
            ("dunoe", "jojongsan", "dunoe"),
            ("naecheongnyong", "oecheongnyong", "naecheongnyong"),
            ("naebaekho", "oebaekho", "naebaekho"),
            ("ansan", "josan", "ansan"),
            ("myeongdang", "misa", "myeongdang"),
            ("naesugu", "oesugu", "naesugu"),
            ("naesugu", "ipsu", "naesugu"),
        ]

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
        seen_edges = set()
        min_link_score = 0.48
        for parent_id, terms in grouped.items():
            hyeol_feature = terms.get("hyeol")
            hyeol_point = None
            if hyeol_feature is not None and hyeol_feature.hasGeometry():
                hyeol_point = hyeol_feature.geometry().asPoint()
            for source_id, target_id, style_term in link_plan:
                source = terms.get(source_id)
                target = terms.get(target_id)
                if source is None or target is None:
                    continue

                pair_key = tuple(sorted((source_id, target_id)))
                edge_key = (parent_id, pair_key, style_term)
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)

                origin = source.geometry().asPoint()
                destination = target.geometry().asPoint()
                if origin.x() == destination.x() and origin.y() == destination.y():
                    continue

                use_bend = True
                path_points = self._link_path_points(
                    origin=origin,
                    destination=destination,
                    center=hyeol_point,
                    use_bend=use_bend,
                )
                score = self._mean_scores(
                    self._to_float(source["score"]),
                    self._to_float(target["score"]),
                )
                if score is not None and score < min_link_score:
                    continue
                dx = destination.x() - origin.x()
                dy = destination.y() - origin.y()
                length_m = math.hypot(dx, dy)
                if length_m <= 0:
                    continue
                azimuth = (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0
                rank_value = (
                    source["rank"] if source["rank"] is not None else target["rank"]
                )

                line_feature = QgsFeature(link_layer.fields())
                line_feature.setGeometry(
                    QgsGeometry.fromPolylineXY(path_points)
                )
                line_feature["term_id"] = style_term
                line_feature["term_ko"] = term_label_ko(style_term)
                line_feature["parent_id"] = parent_id
                line_feature["rank"] = rank_value
                line_feature["score"] = score
                line_feature["culture"] = source["culture"] or target["culture"]
                line_feature["period"] = source["period"] or target["period"]
                line_feature["src_id"] = source_id
                line_feature["dst_id"] = target_id
                line_feature["len_m"] = length_m
                line_feature["azimuth"] = azimuth
                line_feature["curved"] = 1 if use_bend else 0
                score_text = "n/a" if score is None else f"{score:.3f}"
                bend_text = "곡선 보정" if use_bend else "직결"
                line_feature["reason_ko"] = (
                    f"구조 연결 {term_label_ko(source_id)}→{term_label_ko(target_id)}. "
                    f"표현={term_label_ko(style_term)}, 형태={bend_text}, 평균점수={score_text}, "
                    f"거리={length_m:.1f}m, 방위={azimuth:.1f}°({self._azimuth_label(azimuth)}), "
                    "중심 방사 연결 제외."
                )
                link_features.append(line_feature)

        if link_features:
            data.addFeatures(link_features)
        link_layer.updateExtents()
        return link_layer

    @staticmethod
    def _link_path_points(origin, destination, center=None, use_bend=False):
        origin_xy = QgsPointXY(origin.x(), origin.y())
        dest_xy = QgsPointXY(destination.x(), destination.y())
        if not use_bend or center is None:
            return [origin_xy, dest_xy]

        mid_x = (origin.x() + destination.x()) / 2.0
        mid_y = (origin.y() + destination.y()) / 2.0
        ctrl_x = mid_x + ((center.x() - mid_x) * 0.35)
        ctrl_y = mid_y + ((center.y() - mid_y) * 0.35)
        control_xy = QgsPointXY(ctrl_x, ctrl_y)
        return [origin_xy, control_xy, dest_xy]

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
                    "line_width": str(max(0.55, float(width) * 0.56)),
                    "line_style": "solid",
                    "capstyle": "round",
                    "joinstyle": "round",
                }
            )
            symbol.setOpacity(0.38)
            categories.append(QgsRendererCategory(term_id, symbol, term_id))

        renderer = QgsCategorizedSymbolRenderer("term_id", categories)
        default_symbol = QgsLineSymbol.createSimple(
            {
                "line_color": "#777777",
                "line_width": "0.65",
                "line_style": "solid",
                "capstyle": "round",
                "joinstyle": "round",
            }
        )
        default_symbol.setOpacity(0.26)
        renderer.setSourceSymbol(default_symbol)
        link_layer.setRenderer(renderer)
        link_layer.triggerRepaint()

    def build_hydro_network(self, dem_layer):
        provider = dem_layer.dataProvider()
        dem_step = self._dem_step(dem_layer)
        spacing = self._hydro_spacing(dem_layer, dem_step)

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
        min_drop = max(0.15, elev_range * 0.0012)
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
        accumulation_threshold = max(8.0, accumulation_values[cut_index])

        selected_downstream = {}
        for key, target in downstream.items():
            order_value = stream_order.get(key, 1)
            acc_value = contrib.get(key, 1.0)
            keep = acc_value >= accumulation_threshold
            if not keep and order_value >= min_order:
                keep = True
            if (
                not keep
                and order_value >= max(2, min_order - 1)
                and acc_value >= (accumulation_threshold * 0.82)
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

        features = []
        stream_id = 1
        for path in stream_paths:
            points = [nodes[key]["point"] for key in path if key in nodes]
            if len(points) < 2:
                continue

            length = 0.0
            for idx in range(1, len(path)):
                key_a = path[idx - 1]
                key_b = path[idx]
                point_a = nodes[key_a]["point"]
                point_b = nodes[key_b]["point"]
                length += math.hypot(
                    point_b.x() - point_a.x(),
                    point_b.y() - point_a.y(),
                )
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
            "main": ("#0b3d91", 1.6, 0.48),
            "secondary": ("#1456b8", 1.2, 0.40),
            "branch": ("#2b7bd8", 0.9, 0.32),
            "minor": ("#63a5ff", 0.7, 0.24),
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
        fallback.setOpacity(0.20)
        renderer.setSourceSymbol(fallback)
        hydro_layer.setRenderer(renderer)
        hydro_layer.triggerRepaint()

    def build_ridge_network(self, dem_layer):
        provider = dem_layer.dataProvider()
        dem_step = self._dem_step(dem_layer)
        spacing = self._ridge_spacing(dem_layer, dem_step)

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
        prominence_min = max(0.6, elev_range * 0.010)
        neighbor_delta = max(0.05, elev_range * 0.0022)

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
            required = max(3, int(len(neighbors) * 0.55))
            soft_required = max(2, int(len(neighbors) * 0.45))
            if (
                (higher_count < required or prominence < prominence_min)
                and (higher_count < soft_required or prominence < (prominence_min * 0.78))
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

        segment_offsets = [
            (1, 0),
            (0, 1),
            (1, 1),
            (1, -1),
            (2, 0),
            (0, 2),
            (2, 1),
            (1, 2),
            (2, -1),
            (1, -2),
            (2, 2),
            (2, -2),
        ]
        max_segment_distance = spacing * 2.9
        max_segment_drop = max(2.0, elev_range * 0.14)
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
                if abs(ridge_nodes[key_a]["elev"] - ridge_nodes[key_b]["elev"]) > (
                    max_segment_drop
                ):
                    continue
                adjacency[key_a].add(key_b)
                adjacency[key_b].add(key_a)

        if not any(adjacency.values()):
            return ridge_layer

        bridged_count = self._bridge_ridge_endpoints(
            adjacency=adjacency,
            ridge_nodes=ridge_nodes,
            spacing=spacing,
            elev_range=elev_range,
        )

        ridge_paths = self._ridge_paths_from_graph(adjacency)
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
                }
            )

        if not raw_paths:
            return ridge_layer

        ranked_paths = self._rank_ridge_paths(raw_paths)
        features = []
        for item in ranked_paths:
            feature = QgsFeature(ridge_layer.fields())
            feature.setGeometry(QgsGeometry.fromPolylineXY(item["points"]))
            feature["ridge_id"] = item["ridge_id"]
            feature["strength"] = item["strength"]
            feature["ridge_rank"] = item["ridge_rank"]
            feature["ridge_class"] = item["ridge_class"]
            feature["ridge_score"] = item["ridge_score"]
            feature["elev_a"] = item["elev_a"]
            feature["elev_b"] = item["elev_b"]
            feature["len"] = item["len"]
            feature["reason_ko"] = (
                f"능선 점수={item['ridge_score']:.3f} (길이+능선성 결합), "
                f"순위={item['ridge_rank']}/{item['total_count']}, "
                f"상위백분위={item['percentile']*100:.1f}%, "
                f"분류={RIDGE_CLASS_LABELS_KO.get(item['ridge_class'], item['ridge_class'])}, "
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
            "daegan": ("#000000", 3.8, 0.55),
            "jeongmaek": ("#171717", 3.0, 0.45),
            "gimaek": ("#292929", 2.2, 0.36),
            "jimaek": ("#404040", 1.5, 0.28),
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

        renderer = QgsCategorizedSymbolRenderer("ridge_class", categories)
        fallback = QgsLineSymbol.createSimple(
            {
                "line_color": "#3d3d3d",
                "line_width": "1.3",
                "line_style": "solid",
            }
        )
        fallback.setOpacity(0.24)
        renderer.setSourceSymbol(fallback)
        ridge_layer.setRenderer(renderer)
        ridge_layer.triggerRepaint()

    def _ridge_spacing(self, dem_layer, dem_step):
        coarse = self._adaptive_spacing(dem_layer, dem_step)
        spacing = max(dem_step * 4.0, coarse * 0.70)
        if spacing <= 0:
            spacing = max(dem_step * 4.0, 1.0)

        extent = dem_layer.extent()
        cols = max(1, int(extent.width() / spacing) + 1)
        rows = max(1, int(extent.height() / spacing) + 1)
        total = cols * rows
        max_points = 22000
        if total > max_points:
            spacing *= math.sqrt(total / max_points)
        return spacing

    @staticmethod
    def _ridge_edge_key(key_a, key_b):
        return (key_a, key_b) if key_a <= key_b else (key_b, key_a)

    def _bridge_ridge_endpoints(self, adjacency, ridge_nodes, spacing, elev_range):
        endpoints = [key for key, neighbors in adjacency.items() if len(neighbors) == 1]
        if len(endpoints) < 2:
            return 0
        if len(endpoints) > 1800:
            return 0

        max_distance = spacing * 3.6
        max_distance_sq = max_distance * max_distance
        elev_tolerance = max(2.0, elev_range * 0.16)
        used = set()
        bridged = 0

        for key in endpoints:
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
                score = (distance_ratio * 0.55) + (elev_ratio * 0.25) + (
                    strength_ratio * 0.20
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

    def _ridge_paths_from_graph(self, adjacency):
        visited_edges = set()
        paths = []

        def trace_path(start, neighbor):
            edge = self._ridge_edge_key(start, neighbor)
            if edge in visited_edges:
                return None
            visited_edges.add(edge)

            path = [start, neighbor]
            prev = start
            current = neighbor
            while True:
                candidates = sorted(
                    n for n in adjacency[current] if n != prev
                )
                if len(candidates) != 1:
                    break
                nxt = candidates[0]
                next_edge = self._ridge_edge_key(current, nxt)
                if next_edge in visited_edges:
                    break
                visited_edges.add(next_edge)
                path.append(nxt)
                prev, current = current, nxt
            return path

        branch_nodes = sorted(
            key for key, neighbors in adjacency.items() if len(neighbors) != 2 and neighbors
        )
        for start in branch_nodes:
            for neighbor in sorted(adjacency[start]):
                path = trace_path(start, neighbor)
                if path and len(path) > 1:
                    paths.append(path)

        for key in sorted(adjacency.keys()):
            for neighbor in sorted(adjacency[key]):
                path = trace_path(key, neighbor)
                if path and len(path) > 1:
                    paths.append(path)

        return paths

    @staticmethod
    def _rank_ridge_paths(raw_paths):
        if not raw_paths:
            return []

        max_len = max(item["len"] for item in raw_paths)
        max_len = max(max_len, 1e-6)
        scored = []
        for item in raw_paths:
            length_norm = item["len"] / max_len
            score = (0.62 * length_norm) + (0.38 * item["strength"])
            scored.append((score, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)

        ranked = []
        total = len(scored)
        for index, (score_value, item) in enumerate(scored, start=1):
            percentile = index / total
            if percentile <= 0.05:
                ridge_class = "daegan"
            elif percentile <= 0.22:
                ridge_class = "jeongmaek"
            elif percentile <= 0.52:
                ridge_class = "gimaek"
            else:
                ridge_class = "jimaek"
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
        coarse = self._adaptive_spacing(dem_layer, dem_step)
        spacing = max(dem_step * 3.2, coarse * 0.58)
        if spacing <= 0:
            spacing = max(dem_step * 3.2, 1.0)

        extent = dem_layer.extent()
        cols = max(1, int(extent.width() / spacing) + 1)
        rows = max(1, int(extent.height() / spacing) + 1)
        total = cols * rows
        max_points = 26000
        if total > max_points:
            spacing *= math.sqrt(total / max_points)
        return spacing

    @staticmethod
    def _hydro_keep_quantile(node_count):
        if node_count >= 20000:
            return 0.95
        if node_count >= 12000:
            return 0.93
        if node_count >= 7000:
            return 0.91
        if node_count >= 3000:
            return 0.89
        return 0.86

    @staticmethod
    def _hydro_min_order(node_count):
        if node_count >= 18000:
            return 4
        if node_count >= 4000:
            return 3
        return 2

    @staticmethod
    def _hydro_min_path_length(dem_layer, spacing, node_count):
        extent = dem_layer.extent()
        diag = math.hypot(extent.width(), extent.height())
        length = max(spacing * 4.0, diag * 0.006)
        if node_count >= 18000:
            length = max(length, spacing * 10.0)
        elif node_count >= 9000:
            length = max(length, spacing * 7.0)
        elif node_count >= 4000:
            length = max(length, spacing * 5.5)
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
        return (numerator / denominator) * 100.0

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
