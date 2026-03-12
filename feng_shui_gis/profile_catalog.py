# -*- coding: utf-8 -*-
"""Profile, term, and rules catalogs loaded from validated JSON configs."""

from .config_loader import load_json

_PROFILE_FILE = "profiles.json"
_TERM_FILE = "terms.json"
_RULE_FILE = "analysis_rules.json"

_REQUIRED_RULE_TYPES = {
    "sampling": dict,
    "dem_metrics": dict,
    "hyeol_candidate": dict,
    "adaptive_spacing": dict,
    "hyeol_selection": dict,
    "term_links": dict,
    "ridge_network": dict,
    "ridge_bridge": dict,
    "ridge_path": dict,
    "ridge_component": dict,
    "ridge_rendering": dict,
    "ridge_ranking": dict,
    "hydro_network": dict,
    "hydro_rendering": dict,
    "hydro_keep_quantile_rules": list,
    "hydro_min_order_rules": list,
    "hydro_min_path_rules": dict,
    "mountain_lookup": dict,
    "calibration": dict,
}


def _require_dict(value, context, allow_empty=False):
    if not isinstance(value, dict):
        raise RuntimeError(f"{context} must be a JSON object.")
    if not allow_empty and not value:
        raise RuntimeError(f"{context} must not be empty.")
    return value


def _require_list(value, context, allow_empty=False):
    if not isinstance(value, list):
        raise RuntimeError(f"{context} must be a JSON array.")
    if not allow_empty and not value:
        raise RuntimeError(f"{context} must not be empty.")
    return value


def _require_number(container, key, context):
    if key not in container:
        raise RuntimeError(f"Missing numeric key '{key}' in {context}.")
    try:
        return float(container[key])
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Invalid numeric value for '{key}' in {context}.") from exc


def _require_string(container, key, context):
    value = str(container.get(key, "")).strip()
    if not value:
        raise RuntimeError(f"Missing text key '{key}' in {context}.")
    return value


def _validate_profiles(data):
    profiles = _require_dict(data, _PROFILE_FILE)
    for profile_key, spec in profiles.items():
        context = f"{_PROFILE_FILE}:{profile_key}"
        spec = _require_dict(spec, context)
        _require_dict(spec.get("label"), f"{context}.label")
        weights = _require_dict(spec.get("weights"), f"{context}.weights")
        for weight_key, value in weights.items():
            try:
                float(value)
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"Invalid weight '{weight_key}' in {context}.weights."
                ) from exc
        for field_name in ("slope_target", "slope_sigma", "tpi_target", "tpi_sigma"):
            _require_number(spec, field_name, context)
    return profiles


def _validate_term_catalog(data):
    catalog = _require_dict(data, _TERM_FILE)
    term_labels = _require_dict(catalog.get("term_labels"), f"{_TERM_FILE}.term_labels")
    for term_id, labels in term_labels.items():
        _require_dict(labels, f"{_TERM_FILE}.term_labels.{term_id}")

    radius_scales = _require_dict(
        catalog.get("radius_scales"),
        f"{_TERM_FILE}.radius_scales",
    )
    for scale_name in ("inner", "outer", "far"):
        _require_number(radius_scales, scale_name, f"{_TERM_FILE}.radius_scales")

    term_specs = _require_list(catalog.get("term_specs"), f"{_TERM_FILE}.term_specs")
    for index, spec in enumerate(term_specs):
        context = f"{_TERM_FILE}.term_specs[{index}]"
        spec = _require_dict(spec, context)
        _require_string(spec, "term_id", context)
        _require_string(spec, "radius", context)
        _require_string(spec, "direction", context)
        _require_string(spec, "mode", context)
        _require_number(spec, "target", context)
        _require_number(spec, "sigma", context)

    special_terms = _require_dict(
        catalog.get("special_terms"),
        f"{_TERM_FILE}.special_terms",
    )
    for term_id in ("myeongdang", "ipsu", "misa"):
        spec = _require_dict(
            special_terms.get(term_id),
            f"{_TERM_FILE}.special_terms.{term_id}",
        )
        _require_string(spec, "radius", f"{_TERM_FILE}.special_terms.{term_id}")
        if term_id in ("myeongdang", "misa"):
            _require_string(spec, "direction", f"{_TERM_FILE}.special_terms.{term_id}")
            if term_id == "myeongdang":
                _require_number(
                    spec,
                    "offset_factor",
                    f"{_TERM_FILE}.special_terms.{term_id}",
                )
            _require_number(
                spec,
                "target_shift_scale",
                f"{_TERM_FILE}.special_terms.{term_id}",
            )
        else:
            _require_string(spec, "mode", f"{_TERM_FILE}.special_terms.{term_id}")
        _require_number(spec, "target", f"{_TERM_FILE}.special_terms.{term_id}")
        _require_number(spec, "sigma", f"{_TERM_FILE}.special_terms.{term_id}")

    _require_dict(catalog.get("point_styles"), f"{_TERM_FILE}.point_styles", allow_empty=True)
    _require_dict(catalog.get("line_styles"), f"{_TERM_FILE}.line_styles", allow_empty=True)
    return catalog


def _validate_analysis_rules(data):
    rules = _require_dict(data, _RULE_FILE)
    for key, expected_type in _REQUIRED_RULE_TYPES.items():
        if key not in rules:
            raise RuntimeError(f"Missing required section '{key}' in {_RULE_FILE}.")
        if not isinstance(rules[key], expected_type):
            type_name = "JSON object" if expected_type is dict else "JSON array"
            raise RuntimeError(f"Section '{key}' in {_RULE_FILE} must be a {type_name}.")
    return rules


def profile_specs():
    return _validate_profiles(load_json(_PROFILE_FILE))


def available_profiles():
    return tuple(profile_specs().keys())


def profile_spec(profile_key):
    profiles = profile_specs()
    if profile_key in profiles:
        return profiles[profile_key]
    if "general" in profiles:
        return profiles["general"]
    return next(iter(profiles.values()))


def profile_label(profile_key, language):
    spec = profile_spec(profile_key)
    labels = spec.get("label", {})
    return labels.get(language) or labels.get("en") or profile_key


def term_catalog():
    return _validate_term_catalog(load_json(_TERM_FILE))


def term_labels():
    return term_catalog()["term_labels"]


def term_label(term_id, language):
    labels = term_labels().get(term_id, {})
    return labels.get(language) or labels.get("en") or term_id


def term_label_ko(term_id):
    labels = term_labels().get(term_id, {})
    return labels.get("ko") or labels.get("en") or term_id


def term_specs():
    return term_catalog()["term_specs"]


def special_term_specs():
    return term_catalog()["special_terms"]


def term_radius_scales():
    return term_catalog()["radius_scales"]


def point_styles():
    return term_catalog()["point_styles"]


def line_styles():
    return term_catalog()["line_styles"]


def analysis_rules():
    return _validate_analysis_rules(load_json(_RULE_FILE))
