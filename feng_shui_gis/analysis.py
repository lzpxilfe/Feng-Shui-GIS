# -*- coding: utf-8 -*-
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


class FengShuiAnalyzer:
    """Compute archaeology-oriented Feng Shui scores from DEM and optional water."""

    CARDINALS = {
        "north": {"front": 180.0, "back": 0.0, "left": 90.0, "right": 270.0},
        "south": {"front": 0.0, "back": 180.0, "left": 270.0, "right": 90.0},
    }
    TERM_KO = {
        "hyeol": "혈",
        "myeongdang": "명당",
        "jusan": "주산",
        "jojongsan": "조종산",
        "dunoe": "두뇌",
        "naecheongnyong": "내청룡",
        "oecheongnyong": "외청룡",
        "naebaekho": "내백호",
        "oebaekho": "외백호",
        "ansan": "안산",
        "josan": "조산",
        "naesugu": "내수구",
        "oesugu": "외수구",
        "ipsu": "입수",
        "misa": "미사",
    }

    PROFILE_SPECS = {
        "general": {
            "weights": {
                "slope": 0.20,
                "aspect": 0.15,
                "form": 0.25,
                "long": 0.20,
                "water": 0.20,
            },
            "slope_target": 8.0,
            "slope_sigma": 10.0,
            "tpi_target": -0.05,
            "tpi_sigma": 0.40,
        },
        "tomb": {
            "weights": {
                "long": 0.32,
                "form": 0.24,
                "water": 0.18,
                "aspect": 0.14,
                "slope": 0.08,
                "tpi": 0.04,
            },
            "slope_target": 10.0,
            "slope_sigma": 8.0,
            "tpi_target": 0.05,
            "tpi_sigma": 0.25,
        },
        "house": {
            "weights": {
                "slope": 0.20,
                "aspect": 0.24,
                "form": 0.20,
                "water": 0.18,
                "long": 0.10,
                "tpi": 0.08,
            },
            "slope_target": 5.0,
            "slope_sigma": 6.0,
            "tpi_target": -0.05,
            "tpi_sigma": 0.25,
        },
        "village": {
            "weights": {
                "slope": 0.20,
                "water": 0.22,
                "form": 0.20,
                "long": 0.14,
                "aspect": 0.08,
                "tpi": 0.16,
            },
            "slope_target": 4.0,
            "slope_sigma": 7.0,
            "tpi_target": -0.10,
            "tpi_sigma": 0.25,
        },
        "well": {
            "weights": {
                "conv": 0.38,
                "water": 0.20,
                "slope": 0.16,
                "tpi": 0.20,
                "form": 0.06,
            },
            "slope_target": 3.0,
            "slope_sigma": 5.0,
            "tpi_target": -0.22,
            "tpi_sigma": 0.22,
        },
        "temple": {
            "weights": {
                "long": 0.26,
                "form": 0.25,
                "aspect": 0.15,
                "slope": 0.10,
                "tpi": 0.16,
                "water": 0.08,
            },
            "slope_target": 9.0,
            "slope_sigma": 10.0,
            "tpi_target": 0.18,
            "tpi_sigma": 0.25,
        },
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
        max_hyeol=7,
    ):
        context = build_context(culture_key, period_key, hemisphere)
        provider = dem_layer.dataProvider()
        dem_step = self._dem_step(dem_layer)
        sample_spacing = self._adaptive_spacing(dem_layer, dem_step)
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
            min_distance=sample_spacing * 8.0,
            keep=max_hyeol,
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

                feature["fs_culture"] = context["culture_key"]
                feature["fs_period"] = context["period_key"]
                feature["fs_model"] = profile_key
                feature["fs_conf"] = confidence
                feature["fs_note"] = note
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
        return cls.PROFILE_SPECS.get(profile_key, cls.PROFILE_SPECS["general"])

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

        micro_mult = 1.0
        macro_mult = 1.0
        if context:
            micro_mult = context.get("micro_radius_multiplier", 1.0)
            macro_mult = context.get("macro_radius_multiplier", 1.0)
        micro_radius = dem_step * 2.0 * micro_mult
        macro_radius = dem_step * 12.0 * macro_mult

        macro_bearings = list(range(0, 360, 22))
        micro_bearings = list(range(0, 360, 45))

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

            back_score = self._score_gaussian(back_norm, 0.20, 0.35)
            front_score = self._score_gaussian(front_norm, 0.15, 0.35)
            side_score = self._score_gaussian(side_norm, 0.05, 0.25)
            form_score = self._mean_scores(back_score, front_score, side_score)

        long_score = None
        tpi_norm = None
        if relief is not None and relief > 0 and mean_macro is not None:
            tpi = center - mean_macro
            tpi_norm = tpi / relief
            xue_score = self._score_gaussian(tpi_norm, -0.10, 0.30)
            hierarchy_ratio = None
            if std_micro is not None and std_macro is not None and std_macro > 0:
                hierarchy_ratio = std_micro / std_macro
            hierarchy_score = self._score_gaussian(hierarchy_ratio, 0.55, 0.30)
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
                slope_factor = max(0.25, 1.0 - min(1.0, slope_deg / 35.0))

            wetness_shape = self._score_gaussian(convergence, 0.60, 0.28)
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
            if tpi_norm is not None and (tpi_norm < -0.45 or tpi_norm > 0.35):
                continue

            hyeol_shape = self._mean_scores(
                metrics["form_score"],
                metrics["long_score"],
                metrics["dem_water_score"],
            )
            tpi_score = self._score_gaussian(tpi_norm, -0.08, 0.30)
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
        fields.append(QgsField("note", QVariant.String, "string", 80))
        data.addAttributes(fields)
        term_layer.updateFields()

        card = self.CARDINALS.get(hemisphere, self.CARDINALS["north"])
        inner_radius = dem_step * 18.0 * context.get("micro_radius_multiplier", 1.0)
        outer_radius = dem_step * 38.0 * context.get("macro_radius_multiplier", 1.0)
        far_radius = dem_step * 65.0 * context.get("macro_radius_multiplier", 1.0)
        culture_id = context.get("culture_key", "east_asia")
        period_id = context.get("period_key", "early_modern")
        term_bias = context.get("term_bias", {})
        term_target_shift = context.get("term_target_shift", 0.0)

        def add_term(term_id, term_name, parent_id, rank, point, score, elev, note):
            adjusted_score = score
            if adjusted_score is not None:
                adjusted_score = max(
                    0.0,
                    min(1.0, adjusted_score + term_bias.get(term_id, 0.0)),
                )
            self._append_term_feature(
                layer=term_layer,
                term_id=term_id,
                term_name=term_name,
                term_ko=self.TERM_KO.get(term_id, term_id),
                culture=culture_id,
                period=period_id,
                parent_id=parent_id,
                rank=rank,
                point=point,
                score=adjusted_score,
                elev=elev,
                note=note,
            )

        for rank, item in enumerate(selected, start=1):
            center_point = item["point"]
            center_elev = item["elev"]
            base_score = item["score"]

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
            add_term(
                term_id="hyeol",
                term_name="Hyeol",
                parent_id=parent_id,
                rank=rank,
                point=center_point,
                score=base_score,
                elev=center_elev,
                note="core candidate",
            )
            add_term(
                term_id="myeongdang",
                term_name="Myeongdang",
                parent_id=parent_id,
                rank=rank,
                point=center_point,
                score=min(1.0, base_score * 0.98),
                elev=center_elev,
                note="open core basin",
            )

            term_specs = [
                ("jusan", "Jusan", inner_radius, card["back"], "max", 0.33, 0.33),
                ("jojongsan", "Jojongsan", far_radius, card["back"], "max", 0.42, 0.35),
                ("dunoe", "Dunoe", outer_radius, card["back"], "max", 0.36, 0.28),
                (
                    "naecheongnyong",
                    "InnerCheongnyong",
                    inner_radius,
                    card["left"],
                    "max",
                    0.25,
                    0.30,
                ),
                (
                    "oecheongnyong",
                    "OuterCheongnyong",
                    outer_radius,
                    card["left"],
                    "max",
                    0.30,
                    0.35,
                ),
                (
                    "naebaekho",
                    "InnerBaekho",
                    inner_radius,
                    card["right"],
                    "max",
                    0.25,
                    0.30,
                ),
                (
                    "oebaekho",
                    "OuterBaekho",
                    outer_radius,
                    card["right"],
                    "max",
                    0.30,
                    0.35,
                ),
                ("ansan", "Ansan", inner_radius, card["front"], "max", 0.12, 0.30),
                ("josan", "Josan", outer_radius, card["front"], "max", 0.20, 0.33),
                ("naesugu", "InnerSugu", inner_radius, card["front"], "min", -0.15, 0.30),
                ("oesugu", "OuterSugu", outer_radius, card["front"], "min", -0.25, 0.35),
            ]

            for term_id, term_name, radius, azimuth, mode, target, sigma in term_specs:
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
                score = self._mean_scores(
                    base_score,
                    self._score_gaussian(delta, target + term_target_shift, sigma),
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
                )

            ipsu_point, ipsu_elev, _ = self._ring_extreme(
                provider=provider,
                center_point=center_point,
                radius=outer_radius,
                mode="min",
            )
            if ipsu_point is not None:
                delta = (ipsu_elev - center_elev) / relief
                score = self._mean_scores(
                    base_score,
                    self._score_gaussian(delta, -0.22 + term_target_shift, 0.35),
                )
                add_term(
                    term_id="ipsu",
                    term_name="Ipsu",
                    parent_id=parent_id,
                    rank=rank,
                    point=ipsu_point,
                    score=score,
                    elev=ipsu_elev,
                    note=f"ring_min delta={delta:.3f}",
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
                score = self._mean_scores(
                    base_score,
                    self._score_gaussian(delta, -0.03 + (term_target_shift * 0.5), 0.20),
                )
                add_term(
                    term_id="misa",
                    term_name="Misa",
                    parent_id=parent_id,
                    rank=rank,
                    point=misa_point,
                    score=score,
                    elev=misa_elev,
                    note=f"gentle delta={delta:.3f}",
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
        term_ko=None,
        culture=None,
        period=None,
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
        feature["note"] = note
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
        data.addAttributes(fields)
        link_layer.updateFields()

        hyeol_map = {}
        all_features = list(term_layer.getFeatures())
        for feature in all_features:
            if feature["term_id"] == "hyeol" and feature.hasGeometry():
                hyeol_map[feature["parent_id"]] = feature.geometry().asPoint()

        link_features = []
        for feature in all_features:
            term_id = feature["term_id"]
            parent_id = feature["parent_id"]
            if term_id in ("hyeol", None):
                continue
            if parent_id not in hyeol_map:
                continue
            if not feature.hasGeometry():
                continue

            origin = hyeol_map[parent_id]
            target = feature.geometry().asPoint()
            line_feature = QgsFeature(link_layer.fields())
            line_feature.setGeometry(
                QgsGeometry.fromPolylineXY(
                    [
                        QgsPointXY(origin.x(), origin.y()),
                        QgsPointXY(target.x(), target.y()),
                    ]
                )
            )
            line_feature["term_id"] = term_id
            line_feature["term_ko"] = feature["term_ko"]
            line_feature["parent_id"] = parent_id
            line_feature["rank"] = feature["rank"]
            line_feature["score"] = feature["score"]
            line_feature["culture"] = feature["culture"]
            line_feature["period"] = feature["period"]
            link_features.append(line_feature)

        if link_features:
            data.addFeatures(link_features)
        link_layer.updateExtents()
        return link_layer

    def style_term_points(self, term_layer):
        style_map = {
            "hyeol": ("#d62828", 4.8, "#240202", 0.9),
            "myeongdang": ("#ffbf00", 4.0, "#3a2f00", 0.8),
            "jusan": ("#2a9d8f", 3.6, "#083630", 0.7),
            "jojongsan": ("#1b7f75", 3.8, "#06312c", 0.8),
            "dunoe": ("#2f8f46", 3.4, "#14381d", 0.7),
            "naecheongnyong": ("#1f6feb", 3.5, "#0a2f6e", 0.7),
            "oecheongnyong": ("#5ea3ff", 3.3, "#103a6c", 0.7),
            "naebaekho": ("#f3f3f3", 3.5, "#545454", 0.7),
            "oebaekho": ("#e1e1e1", 3.3, "#5a5a5a", 0.7),
            "ansan": ("#6aa84f", 3.3, "#245016", 0.7),
            "josan": ("#84bf65", 3.2, "#29541c", 0.7),
            "naesugu": ("#118ab2", 3.4, "#064d63", 0.7),
            "oesugu": ("#20b4d8", 3.2, "#066078", 0.7),
            "ipsu": ("#0096c7", 3.8, "#024e67", 0.8),
            "misa": ("#fb8500", 3.2, "#6a3300", 0.7),
        }

        categories = []
        for term_id, (fill_color, size, stroke_color, stroke_width) in style_map.items():
            symbol = QgsMarkerSymbol.createSimple(
                {
                    "name": "circle",
                    "color": fill_color,
                    "size": str(size),
                    "outline_color": stroke_color,
                    "outline_width": str(stroke_width),
                }
            )
            categories.append(QgsRendererCategory(term_id, symbol, term_id))

        renderer = QgsCategorizedSymbolRenderer("term_id", categories)
        fallback = QgsMarkerSymbol.createSimple(
            {
                "name": "circle",
                "color": "#cccccc",
                "size": "3.0",
                "outline_color": "#555555",
                "outline_width": "0.5",
            }
        )
        renderer.setSourceSymbol(fallback)
        term_layer.setRenderer(renderer)
        term_layer.triggerRepaint()

    def style_term_links(self, link_layer):
        line_styles = {
            "jusan": ("#0f766e", 1.8),
            "jojongsan": ("#065f46", 2.4),
            "dunoe": ("#15803d", 2.0),
            "naecheongnyong": ("#1d4ed8", 2.2),
            "oecheongnyong": ("#3b82f6", 1.8),
            "naebaekho": ("#6b7280", 2.2),
            "oebaekho": ("#9ca3af", 1.8),
            "ansan": ("#65a30d", 1.8),
            "josan": ("#84cc16", 2.0),
            "naesugu": ("#0ea5e9", 2.0),
            "oesugu": ("#22d3ee", 1.8),
            "ipsu": ("#0284c7", 2.6),
            "myeongdang": ("#f59e0b", 1.6),
            "misa": ("#f97316", 1.8),
        }

        categories = []
        for term_id, (color, width) in line_styles.items():
            symbol = QgsLineSymbol.createSimple(
                {
                    "line_color": color,
                    "line_width": str(width),
                    "line_style": "solid",
                }
            )
            categories.append(QgsRendererCategory(term_id, symbol, term_id))

        renderer = QgsCategorizedSymbolRenderer("term_id", categories)
        default_symbol = QgsLineSymbol.createSimple(
            {
                "line_color": "#777777",
                "line_width": "1.4",
                "line_style": "solid",
            }
        )
        renderer.setSourceSymbol(default_symbol)
        link_layer.setRenderer(renderer)
        link_layer.triggerRepaint()

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
