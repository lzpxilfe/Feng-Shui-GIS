# -*- coding: utf-8 -*-
"""Country/period context profiles for Feng Shui archaeology workflows."""

from copy import deepcopy

BASE_CULTURE_KEY = "east_asia"
BASE_PERIOD_KEY = "early_modern"


_CULTURES = {
    "east_asia": {
        "aspect_targets": {"north": 180.0, "south": 0.0},
        "aspect_sharpness": 1.0,
        "water_distance_target": 220.0,
        "water_distance_sigma": 350.0,
        "macro_radius_multiplier": 1.00,
        "micro_radius_multiplier": 1.00,
        "hyeol_threshold": 0.62,
        "weight_bias": {},
        "term_bias": {},
        "term_target_shift": 0.00,
    },
    "china": {
        "aspect_targets": {"north": 180.0, "south": 0.0},
        "aspect_sharpness": 1.10,
        "water_distance_target": 260.0,
        "water_distance_sigma": 420.0,
        "macro_radius_multiplier": 1.20,
        "micro_radius_multiplier": 1.05,
        "hyeol_threshold": 0.64,
        "weight_bias": {"long": 0.07, "water": 0.05, "form": 0.03, "tpi": -0.03},
        "term_bias": {
            "jusan": 0.04,
            "jojongsan": 0.06,
            "naesugu": 0.03,
            "oesugu": 0.04,
        },
        "term_target_shift": 0.03,
    },
    "korea": {
        "aspect_targets": {"north": 180.0, "south": 0.0},
        "aspect_sharpness": 1.15,
        "water_distance_target": 210.0,
        "water_distance_sigma": 330.0,
        "macro_radius_multiplier": 1.10,
        "micro_radius_multiplier": 1.00,
        "hyeol_threshold": 0.64,
        "weight_bias": {
            "form": 0.06,
            "long": 0.04,
            "water": 0.02,
            "aspect": 0.02,
            "slope": -0.03,
        },
        "term_bias": {
            "ansan": 0.05,
            "josan": 0.05,
            "naecheongnyong": 0.04,
            "naebaekho": 0.04,
            "naesugu": 0.04,
        },
        "term_target_shift": 0.01,
    },
    "japan": {
        "aspect_targets": {"north": 170.0, "south": 350.0},
        "aspect_sharpness": 0.85,
        "water_distance_target": 240.0,
        "water_distance_sigma": 360.0,
        "macro_radius_multiplier": 1.00,
        "micro_radius_multiplier": 0.95,
        "hyeol_threshold": 0.60,
        "weight_bias": {"aspect": 0.05, "form": 0.03, "water": -0.03, "long": 0.01},
        "term_bias": {
            "naecheongnyong": 0.03,
            "oecheongnyong": 0.02,
            "naebaekho": 0.03,
            "oebaekho": 0.02,
            "ansan": 0.02,
        },
        "term_target_shift": -0.01,
    },
    "ryukyu": {
        "aspect_targets": {"north": 165.0, "south": 345.0},
        "aspect_sharpness": 0.90,
        "water_distance_target": 180.0,
        "water_distance_sigma": 310.0,
        "macro_radius_multiplier": 0.90,
        "micro_radius_multiplier": 1.05,
        "hyeol_threshold": 0.59,
        "weight_bias": {"water": 0.10, "conv": 0.04, "long": -0.05, "form": 0.01},
        "term_bias": {"ipsu": 0.06, "naesugu": 0.05, "oesugu": 0.05},
        "term_target_shift": -0.03,
    },
}


_PERIODS = {
    "ancient": {
        "water_target_shift": 30.0,
        "water_sigma_shift": 20.0,
        "macro_radius_multiplier": 1.15,
        "micro_radius_multiplier": 1.00,
        "hyeol_threshold_shift": 0.02,
        "weight_bias": {"long": 0.05, "form": 0.03, "water": -0.02, "aspect": -0.02},
        "term_target_shift": 0.02,
    },
    "medieval": {
        "water_target_shift": 10.0,
        "water_sigma_shift": 10.0,
        "macro_radius_multiplier": 1.05,
        "micro_radius_multiplier": 1.00,
        "hyeol_threshold_shift": 0.01,
        "weight_bias": {"form": 0.03, "long": 0.03},
        "term_target_shift": 0.01,
    },
    "early_modern": {
        "water_target_shift": 0.0,
        "water_sigma_shift": 0.0,
        "macro_radius_multiplier": 1.00,
        "micro_radius_multiplier": 1.00,
        "hyeol_threshold_shift": 0.00,
        "weight_bias": {"aspect": 0.02, "water": 0.01},
        "term_target_shift": 0.00,
    },
    "modern": {
        "water_target_shift": -15.0,
        "water_sigma_shift": -20.0,
        "macro_radius_multiplier": 0.90,
        "micro_radius_multiplier": 1.00,
        "hyeol_threshold_shift": -0.03,
        "weight_bias": {"water": 0.03, "conv": 0.03, "long": -0.04, "form": -0.02},
        "term_target_shift": -0.02,
    },
}


def available_cultures():
    return tuple(_CULTURES.keys())


def available_periods():
    return tuple(_PERIODS.keys())


def build_context(culture_key, period_key, hemisphere):
    culture_id = culture_key if culture_key in _CULTURES else BASE_CULTURE_KEY
    period_id = period_key if period_key in _PERIODS else BASE_PERIOD_KEY

    culture = _CULTURES[culture_id]
    period = _PERIODS[period_id]

    context = {
        "culture_key": culture_id,
        "period_key": period_id,
        "aspect_target": culture["aspect_targets"].get(
            hemisphere,
            180.0 if hemisphere == "north" else 0.0,
        ),
        "aspect_sharpness": culture["aspect_sharpness"],
        "water_distance_target": culture["water_distance_target"] + period["water_target_shift"],
        "water_distance_sigma": max(
            120.0,
            culture["water_distance_sigma"] + period["water_sigma_shift"],
        ),
        "macro_radius_multiplier": (
            culture["macro_radius_multiplier"] * period["macro_radius_multiplier"]
        ),
        "micro_radius_multiplier": (
            culture["micro_radius_multiplier"] * period["micro_radius_multiplier"]
        ),
        "hyeol_threshold": max(
            0.50,
            min(0.90, culture["hyeol_threshold"] + period["hyeol_threshold_shift"]),
        ),
        "weight_bias": _merge_dicts(culture["weight_bias"], period["weight_bias"]),
        "term_bias": deepcopy(culture["term_bias"]),
        "term_target_shift": culture["term_target_shift"] + period["term_target_shift"],
    }
    return context


def _merge_dicts(first, second):
    merged = {}
    keys = set(first.keys()) | set(second.keys())
    for key in keys:
        merged[key] = first.get(key, 0.0) + second.get(key, 0.0)
    return merged
