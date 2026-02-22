# -*- coding: utf-8 -*-
"""Country/period context profiles for Feng Shui archaeology workflows."""

from copy import deepcopy

from .config_loader import load_json

_CONFIG_FILE = "contexts.json"


def _config():
    return load_json(_CONFIG_FILE)


def _cultures():
    return _config().get("cultures", {})


def _periods():
    return _config().get("periods", {})


def base_culture_key():
    return _config().get("base_culture_key", "east_asia")


def base_period_key():
    return _config().get("base_period_key", "early_modern")


def available_cultures():
    return tuple(_cultures().keys())


def available_periods():
    return tuple(_periods().keys())


def culture_label(culture_key, language):
    labels = _cultures().get(culture_key, {}).get("label", {})
    return labels.get(language) or labels.get("en") or culture_key


def period_label(period_key, language):
    labels = _periods().get(period_key, {}).get("label", {})
    return labels.get(language) or labels.get("en") or period_key


def build_context(culture_key, period_key, hemisphere):
    cultures = _cultures()
    periods = _periods()

    if not cultures:
        cultures = {
            "east_asia": {
                "aspect_targets": {"north": 180.0, "south": 0.0},
                "aspect_sharpness": 1.0,
                "water_distance_target": 220.0,
                "water_distance_sigma": 350.0,
                "macro_radius_multiplier": 1.0,
                "micro_radius_multiplier": 1.0,
                "hyeol_threshold": 0.62,
                "weight_bias": {},
                "term_bias": {},
                "term_target_shift": 0.0,
            }
        }
    if not periods:
        periods = {
            "early_modern": {
                "water_target_shift": 0.0,
                "water_sigma_shift": 0.0,
                "macro_radius_multiplier": 1.0,
                "micro_radius_multiplier": 1.0,
                "hyeol_threshold_shift": 0.0,
                "weight_bias": {},
                "term_target_shift": 0.0,
            }
        }

    culture_default = base_culture_key()
    if culture_default not in cultures:
        culture_default = next(iter(cultures.keys()))
    period_default = base_period_key()
    if period_default not in periods:
        period_default = next(iter(periods.keys()))

    culture_id = culture_key if culture_key in cultures else culture_default
    period_id = period_key if period_key in periods else period_default

    culture = cultures[culture_id]
    period = periods[period_id]

    context = {
        "culture_key": culture_id,
        "period_key": period_id,
        "aspect_target": culture.get("aspect_targets", {}).get(
            hemisphere,
            180.0 if hemisphere == "north" else 0.0,
        ),
        "aspect_sharpness": culture.get("aspect_sharpness", 1.0),
        "water_distance_target": culture.get("water_distance_target", 220.0)
        + period.get("water_target_shift", 0.0),
        "water_distance_sigma": max(
            120.0,
            culture.get("water_distance_sigma", 350.0)
            + period.get("water_sigma_shift", 0.0),
        ),
        "macro_radius_multiplier": culture.get("macro_radius_multiplier", 1.0)
        * period.get("macro_radius_multiplier", 1.0),
        "micro_radius_multiplier": culture.get("micro_radius_multiplier", 1.0)
        * period.get("micro_radius_multiplier", 1.0),
        "hyeol_threshold": max(
            0.50,
            min(
                0.90,
                culture.get("hyeol_threshold", 0.62)
                + period.get("hyeol_threshold_shift", 0.0),
            ),
        ),
        "weight_bias": _merge_dicts(
            culture.get("weight_bias", {}),
            period.get("weight_bias", {}),
        ),
        "term_bias": deepcopy(culture.get("term_bias", {})),
        "term_target_shift": culture.get("term_target_shift", 0.0)
        + period.get("term_target_shift", 0.0),
    }
    return context


def _merge_dicts(first, second):
    merged = {}
    keys = set(first.keys()) | set(second.keys())
    for key in keys:
        merged[key] = first.get(key, 0.0) + second.get(key, 0.0)
    return merged
