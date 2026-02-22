# -*- coding: utf-8 -*-
"""Profile and term catalogs loaded from JSON configs."""

from .config_loader import load_json

_PROFILE_FILE = "profiles.json"
_TERM_FILE = "terms.json"
_RULE_FILE = "analysis_rules.json"


def profile_specs():
    return load_json(_PROFILE_FILE)


def available_profiles():
    return tuple(profile_specs().keys())


def profile_spec(profile_key):
    profiles = profile_specs()
    if not profiles:
        return {
            "weights": {"slope": 0.4, "aspect": 0.3, "water": 0.3},
            "slope_target": 8.0,
            "slope_sigma": 10.0,
            "tpi_target": 0.0,
            "tpi_sigma": 0.4,
            "label": {"en": "Default"},
        }
    if profile_key in profiles:
        return profiles[profile_key]
    return profiles.get("general", next(iter(profiles.values())))


def profile_label(profile_key, language):
    spec = profile_specs().get(profile_key, {})
    labels = spec.get("label", {})
    return labels.get(language) or labels.get("en") or profile_key


def term_catalog():
    return load_json(_TERM_FILE)


def term_labels():
    return term_catalog().get("term_labels", {})


def term_label(term_id, language):
    labels = term_labels().get(term_id, {})
    return labels.get(language) or labels.get("en") or term_id


def term_label_ko(term_id):
    labels = term_labels().get(term_id, {})
    return labels.get("ko") or labels.get("en") or term_id


def term_specs():
    return term_catalog().get("term_specs", [])


def term_radius_scales():
    return term_catalog().get(
        "radius_scales", {"inner": 18.0, "outer": 38.0, "far": 65.0}
    )


def point_styles():
    return term_catalog().get("point_styles", {})


def line_styles():
    return term_catalog().get("line_styles", {})


def analysis_rules():
    return load_json(_RULE_FILE)
