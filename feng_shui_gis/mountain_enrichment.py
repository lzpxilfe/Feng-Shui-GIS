# -*- coding: utf-8 -*-
"""Pure helpers for mountain-name enrichment orchestration."""

from __future__ import annotations


def resolve_mountain_name_options(options, *, enabled=None, radius_m=None, max_features=None, preferred_language=None):
    options = dict(options or {})
    enabled_value = bool(options.get("enabled_default", False) if enabled is None else enabled)
    radius_value = int(options.get("radius_default_m", 5000) if radius_m is None else radius_m)
    max_features_value = int(
        options.get("max_features_default", 3) if max_features is None else max_features
    )
    language_value = str(
        options.get("language_default", "local")
        if preferred_language is None
        else preferred_language
    )

    if language_value not in ("local", "ko", "en"):
        language_value = str(options.get("language_default", "local"))
    radius_value = max(
        int(options.get("radius_min_m", radius_value)),
        min(int(options.get("radius_max_m", radius_value)), int(radius_value)),
    )
    max_features_value = max(
        int(options.get("max_features_min", max_features_value)),
        min(int(options.get("max_features_max", max_features_value)), int(max_features_value)),
    )
    return enabled_value, radius_value, max_features_value, language_value


def group_layers_by_crs(layers, *, is_valid_layer, crs_key_for_layer):
    groups = {}
    for layer in layers or []:
        if not is_valid_layer(layer):
            continue
        crs_key, crs_value = crs_key_for_layer(layer)
        group = groups.setdefault(crs_key, {"crs": crs_value, "layers": []})
        group["layers"].append(layer)
    return list(groups.values())
