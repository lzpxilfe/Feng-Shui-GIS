# -*- coding: utf-8 -*-
"""Shared mountain-name enrichment options loaded from analysis rules."""

from .profile_catalog import analysis_rules

_DEFAULTS = {
    "enabled_default": False,
    "radius_min_m": 500,
    "radius_max_m": 20000,
    "radius_step_m": 250,
    "radius_default_m": 3500,
    "max_features_min": 5,
    "max_features_max": 500,
    "max_features_step": 5,
    "max_features_default": 40,
    "language_default": "local",
    "overpass_url": "https://overpass-api.de/api/interpreter",
    "request_timeout_sec": 18,
    "bbox_limit_deg": 3.5,
    "query_timeout_sec": 25,
    "user_agent": "FengShuiGIS-Plugin/1.0 (QGIS)",
    "source_label": "OSM/Overpass",
}


def _rules():
    rules = analysis_rules()
    if not isinstance(rules, dict):
        return {}
    section = rules.get("mountain_lookup", {})
    return section if isinstance(section, dict) else {}


def _int_option(rules, key, default, min_value=None, max_value=None):
    try:
        value = int(rules.get(key, default))
    except (TypeError, ValueError):
        value = int(default)
    if min_value is not None:
        value = max(int(min_value), value)
    if max_value is not None:
        value = min(int(max_value), value)
    return value


def _float_option(rules, key, default, min_value=None, max_value=None):
    try:
        value = float(rules.get(key, default))
    except (TypeError, ValueError):
        value = float(default)
    if min_value is not None:
        value = max(float(min_value), value)
    if max_value is not None:
        value = min(float(max_value), value)
    return value


def _str_option(rules, key, default):
    value = str(rules.get(key, default)).strip()
    return value if value else str(default)


def mountain_options():
    rules = _rules()
    opts = {}

    opts["enabled_default"] = bool(rules.get("enabled_default", _DEFAULTS["enabled_default"]))

    radius_min = _int_option(
        rules,
        "radius_min_m",
        _DEFAULTS["radius_min_m"],
        min_value=1,
    )
    radius_max = _int_option(
        rules,
        "radius_max_m",
        _DEFAULTS["radius_max_m"],
        min_value=radius_min,
    )
    radius_step = _int_option(
        rules,
        "radius_step_m",
        _DEFAULTS["radius_step_m"],
        min_value=1,
    )
    radius_default = _int_option(
        rules,
        "radius_default_m",
        _DEFAULTS["radius_default_m"],
        min_value=radius_min,
        max_value=radius_max,
    )
    opts["radius_min_m"] = radius_min
    opts["radius_max_m"] = radius_max
    opts["radius_step_m"] = radius_step
    opts["radius_default_m"] = radius_default

    max_features_min = _int_option(
        rules,
        "max_features_min",
        _DEFAULTS["max_features_min"],
        min_value=1,
    )
    max_features_max = _int_option(
        rules,
        "max_features_max",
        _DEFAULTS["max_features_max"],
        min_value=max_features_min,
    )
    max_features_step = _int_option(
        rules,
        "max_features_step",
        _DEFAULTS["max_features_step"],
        min_value=1,
    )
    max_features_default = _int_option(
        rules,
        "max_features_default",
        _DEFAULTS["max_features_default"],
        min_value=max_features_min,
        max_value=max_features_max,
    )
    opts["max_features_min"] = max_features_min
    opts["max_features_max"] = max_features_max
    opts["max_features_step"] = max_features_step
    opts["max_features_default"] = max_features_default

    language_default = _str_option(
        rules,
        "language_default",
        _DEFAULTS["language_default"],
    ).lower()
    if language_default not in ("local", "ko", "en"):
        language_default = "local"
    opts["language_default"] = language_default

    opts["overpass_url"] = _str_option(
        rules,
        "overpass_url",
        _DEFAULTS["overpass_url"],
    )
    opts["request_timeout_sec"] = _int_option(
        rules,
        "request_timeout_sec",
        _DEFAULTS["request_timeout_sec"],
        min_value=5,
    )
    opts["bbox_limit_deg"] = _float_option(
        rules,
        "bbox_limit_deg",
        _DEFAULTS["bbox_limit_deg"],
        min_value=0.1,
    )
    opts["query_timeout_sec"] = _int_option(
        rules,
        "query_timeout_sec",
        _DEFAULTS["query_timeout_sec"],
        min_value=5,
    )
    opts["user_agent"] = _str_option(
        rules,
        "user_agent",
        _DEFAULTS["user_agent"],
    )
    opts["source_label"] = _str_option(
        rules,
        "source_label",
        _DEFAULTS["source_label"],
    )

    return opts
