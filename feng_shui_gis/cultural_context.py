# -*- coding: utf-8 -*-
"""Country and period context profiles for Feng Shui archaeology workflows."""

from copy import deepcopy
from html import escape

from .config_loader import load_json
from .reference_catalog import reference_display_text
from .ui_catalog import ui_text

_CONFIG_FILE = "contexts.json"
_LEVEL_ORDER = {"A": 0, "B": 1, "C": 2, "U": 3}
_NEUTRAL_CONTEXT_KEY = "__neutral__"
_CONTEXT_TIERS = {"stable", "experimental", "deprecated"}
_DEFAULT_CONTEXT_TIER = "stable"

_REQUIRED_CULTURE_FIELDS = (
    "aspect_sharpness",
    "water_distance_target",
    "water_distance_sigma",
    "macro_radius_multiplier",
    "micro_radius_multiplier",
    "hyeol_threshold",
    "term_target_shift",
)
_REQUIRED_PERIOD_FIELDS = (
    "water_target_shift",
    "water_sigma_shift",
    "macro_radius_multiplier",
    "micro_radius_multiplier",
    "hyeol_threshold_shift",
    "term_target_shift",
)


def _default_meta():
    return {"source_doi": [], "evidence_level": "U", "note": ""}


def _require_dict(value, context, allow_empty=False):
    if not isinstance(value, dict):
        raise RuntimeError(f"{context} must be a JSON object.")
    if not allow_empty and not value:
        raise RuntimeError(f"{context} must not be empty.")
    return value


def _require_text(value, context):
    text = str(value or "").strip()
    if not text:
        raise RuntimeError(f"{context} must not be empty.")
    return text


def _meta_from_node(node):
    if not isinstance(node, dict):
        return _default_meta()
    dois = node.get("source_doi", [])
    if isinstance(dois, str):
        dois = [dois] if dois else []
    if not isinstance(dois, list):
        dois = []
    dois = [str(item).strip() for item in dois if str(item).strip()]
    level = str(node.get("evidence_level", "U")).strip().upper() or "U"
    if level not in _LEVEL_ORDER:
        level = "U"
    note = str(node.get("note", "")).strip()
    return {"source_doi": dois, "evidence_level": level, "note": note}


def _numeric_value(node, context):
    raw_value = node
    if isinstance(node, dict) and "value" in node:
        raw_value = node.get("value")
    try:
        return float(raw_value), _meta_from_node(node)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{context} must be numeric.") from exc


def _merge_meta(first_meta, second_meta):
    sources = list(first_meta.get("source_doi", [])) + list(
        second_meta.get("source_doi", [])
    )
    unique_sources = []
    seen = set()
    for source in sources:
        if source not in seen:
            seen.add(source)
            unique_sources.append(source)
    levels = [
        first_meta.get("evidence_level", "U"),
        second_meta.get("evidence_level", "U"),
    ]
    levels = [item for item in levels if item in _LEVEL_ORDER]
    level = sorted(levels, key=lambda item: _LEVEL_ORDER[item])[0] if levels else "U"
    notes = [first_meta.get("note", "").strip(), second_meta.get("note", "").strip()]
    note = " | ".join(item for item in notes if item)
    return {"source_doi": unique_sources, "evidence_level": level, "note": note}


def _normalize_context_tier(value):
    tier = str(value or "").strip().lower()
    if tier not in _CONTEXT_TIERS:
        return _DEFAULT_CONTEXT_TIER
    return tier


def _normalize_scalar_map_with_meta(node, context):
    if node is None:
        return {}, {}
    node = _require_dict(node, context, allow_empty=True)
    normalized = {}
    metas = {}
    for key, raw_value in node.items():
        value, meta = _numeric_value(raw_value, f"{context}.{key}")
        normalized[key] = value
        metas[key] = meta
    return normalized, metas


def _merge_dicts(first, second):
    merged = {}
    keys = set(first.keys()) | set(second.keys())
    for key in keys:
        merged[key] = first.get(key, 0.0) + second.get(key, 0.0)
    return merged


def _config():
    config = load_json(_CONFIG_FILE)
    return _require_dict(config, _CONFIG_FILE)


def _cultures():
    return _require_dict(_config().get("cultures"), f"{_CONFIG_FILE}.cultures")


def _periods():
    return _require_dict(_config().get("periods"), f"{_CONFIG_FILE}.periods")


def _neutral_defaults():
    defaults = _require_dict(
        _config().get("neutral_defaults"),
        f"{_CONFIG_FILE}.neutral_defaults",
    )
    aspect_targets = _require_dict(
        defaults.get("aspect_targets"),
        f"{_CONFIG_FILE}.neutral_defaults.aspect_targets",
    )
    for hemisphere in ("north", "south"):
        if hemisphere not in aspect_targets:
            raise RuntimeError(
                f"Missing hemisphere '{hemisphere}' in {_CONFIG_FILE}.neutral_defaults.aspect_targets."
            )
        _numeric_value(
            aspect_targets[hemisphere],
            f"{_CONFIG_FILE}.neutral_defaults.aspect_targets.{hemisphere}",
        )
    for field_name in _REQUIRED_CULTURE_FIELDS:
        if field_name not in defaults:
            raise RuntimeError(
                f"Missing field '{field_name}' in {_CONFIG_FILE}.neutral_defaults."
            )
        _numeric_value(defaults[field_name], f"{_CONFIG_FILE}.neutral_defaults.{field_name}")
    return defaults


def neutral_context_key():
    return _NEUTRAL_CONTEXT_KEY


def base_culture_key():
    return _require_text(_config().get("base_culture_key"), f"{_CONFIG_FILE}.base_culture_key")


def base_period_key():
    return _require_text(_config().get("base_period_key"), f"{_CONFIG_FILE}.base_period_key")


def available_cultures():
    return tuple(_cultures().keys())


def available_cultures_filtered_by_tier(visibility_tier=None):
    cultures = _cultures()
    if visibility_tier is None:
        return tuple(cultures.keys())
    requested_tier = _normalize_context_tier(visibility_tier)
    result = []
    for culture_key, culture in cultures.items():
        if not isinstance(culture, dict):
            continue
        tier = _normalize_context_tier(culture.get("visibility_tier", _DEFAULT_CONTEXT_TIER))
        if tier == requested_tier:
            result.append(culture_key)
    return tuple(result)


def culture_visibility_tier(culture_key):
    culture = _cultures().get(culture_key, {})
    if not isinstance(culture, dict):
        return _DEFAULT_CONTEXT_TIER
    return _normalize_context_tier(culture.get("visibility_tier", _DEFAULT_CONTEXT_TIER))


def culture_evidence_scope(culture_key):
    culture = _cultures().get(culture_key, {})
    if not isinstance(culture, dict):
        return ""
    return str(culture.get("evidence_scope", "")).strip()


def _context_tier_labels(language):
    if language == "ko":
        return {
            "stable": "안정형",
            "experimental": "실험적",
            "deprecated": "사용중단",
        }
    return {
        "stable": "stable",
        "experimental": "exploratory",
        "deprecated": "deprecated",
    }


def available_periods():
    return tuple(_periods().keys())


def culture_label(culture_key, language):
    labels = _cultures().get(culture_key, {}).get("label", {})
    return labels.get(language) or labels.get("en") or culture_key


def period_label(period_key, language):
    labels = _periods().get(period_key, {}).get("label", {})
    return labels.get(language) or labels.get("en") or period_key


def _neutral_context(hemisphere):
    defaults = _neutral_defaults()
    aspect_targets = defaults["aspect_targets"]
    aspect_target, aspect_target_meta = _numeric_value(
        aspect_targets[hemisphere],
        f"{_CONFIG_FILE}.neutral_defaults.aspect_targets.{hemisphere}",
    )
    aspect_sharpness, aspect_sharpness_meta = _numeric_value(
        defaults["aspect_sharpness"],
        f"{_CONFIG_FILE}.neutral_defaults.aspect_sharpness",
    )
    water_target, water_target_meta = _numeric_value(
        defaults["water_distance_target"],
        f"{_CONFIG_FILE}.neutral_defaults.water_distance_target",
    )
    water_sigma, water_sigma_meta = _numeric_value(
        defaults["water_distance_sigma"],
        f"{_CONFIG_FILE}.neutral_defaults.water_distance_sigma",
    )
    macro_multiplier, macro_multiplier_meta = _numeric_value(
        defaults["macro_radius_multiplier"],
        f"{_CONFIG_FILE}.neutral_defaults.macro_radius_multiplier",
    )
    micro_multiplier, micro_multiplier_meta = _numeric_value(
        defaults["micro_radius_multiplier"],
        f"{_CONFIG_FILE}.neutral_defaults.micro_radius_multiplier",
    )
    hyeol_threshold, hyeol_threshold_meta = _numeric_value(
        defaults["hyeol_threshold"],
        f"{_CONFIG_FILE}.neutral_defaults.hyeol_threshold",
    )
    term_target_shift, term_target_shift_meta = _numeric_value(
        defaults["term_target_shift"],
        f"{_CONFIG_FILE}.neutral_defaults.term_target_shift",
    )
    if water_sigma <= 0:
        raise RuntimeError("Neutral context water_distance_sigma must be greater than 0.")
    if not 0.0 <= hyeol_threshold <= 1.0:
        raise RuntimeError("Neutral context hyeol_threshold must be between 0 and 1.")

    return {
        "culture_key": _NEUTRAL_CONTEXT_KEY,
        "period_key": _NEUTRAL_CONTEXT_KEY,
        "aspect_target": aspect_target,
        "aspect_sharpness": aspect_sharpness,
        "water_distance_target": water_target,
        "water_distance_sigma": water_sigma,
        "macro_radius_multiplier": macro_multiplier,
        "micro_radius_multiplier": micro_multiplier,
        "hyeol_threshold": hyeol_threshold,
        "weight_bias": {},
        "term_bias": {},
        "term_target_shift": term_target_shift,
        "evidence": {
            "parameters": {
                "aspect_target": {"value": aspect_target, **aspect_target_meta},
                "aspect_sharpness": {"value": aspect_sharpness, **aspect_sharpness_meta},
                "water_distance_target": {"value": water_target, **water_target_meta},
                "water_distance_sigma": {"value": water_sigma, **water_sigma_meta},
                "macro_radius_multiplier": {
                    "value": macro_multiplier,
                    **macro_multiplier_meta,
                },
                "micro_radius_multiplier": {
                    "value": micro_multiplier,
                    **micro_multiplier_meta,
                },
                "hyeol_threshold": {"value": hyeol_threshold, **hyeol_threshold_meta},
                "term_target_shift": {
                    "value": term_target_shift,
                    **term_target_shift_meta,
                },
            },
            "weight_bias": {},
            "term_bias": {},
        },
    }


def _validated_culture(culture_id):
    cultures = _cultures()
    culture = _require_dict(
        cultures.get(culture_id),
        f"{_CONFIG_FILE}.cultures.{culture_id}",
    )
    aspect_targets = _require_dict(
        culture.get("aspect_targets"),
        f"{_CONFIG_FILE}.cultures.{culture_id}.aspect_targets",
    )
    for hemisphere in ("north", "south"):
        if hemisphere not in aspect_targets:
            raise RuntimeError(
                f"Missing hemisphere '{hemisphere}' in {_CONFIG_FILE}.cultures.{culture_id}.aspect_targets."
            )
        _numeric_value(
            aspect_targets[hemisphere],
            f"{_CONFIG_FILE}.cultures.{culture_id}.aspect_targets.{hemisphere}",
        )
    for field_name in _REQUIRED_CULTURE_FIELDS:
        if field_name not in culture:
            raise RuntimeError(
                f"Missing field '{field_name}' in {_CONFIG_FILE}.cultures.{culture_id}."
            )
        _numeric_value(
            culture[field_name],
            f"{_CONFIG_FILE}.cultures.{culture_id}.{field_name}",
        )
    return culture


def _validated_period(period_id):
    periods = _periods()
    period = _require_dict(
        periods.get(period_id),
        f"{_CONFIG_FILE}.periods.{period_id}",
    )
    for field_name in _REQUIRED_PERIOD_FIELDS:
        if field_name not in period:
            raise RuntimeError(
                f"Missing field '{field_name}' in {_CONFIG_FILE}.periods.{period_id}."
            )
        _numeric_value(
            period[field_name],
            f"{_CONFIG_FILE}.periods.{period_id}.{field_name}",
        )
    return period


def build_context(culture_key, period_key, hemisphere):
    if (
        str(culture_key).strip().lower() == _NEUTRAL_CONTEXT_KEY
        or str(period_key).strip().lower() == _NEUTRAL_CONTEXT_KEY
    ):
        return _neutral_context(hemisphere)

    cultures = _cultures()
    periods = _periods()

    culture_default = base_culture_key()
    if culture_default not in cultures:
        raise RuntimeError(
            f"Configured base culture '{culture_default}' is missing from {_CONFIG_FILE}.cultures."
        )
    period_default = base_period_key()
    if period_default not in periods:
        raise RuntimeError(
            f"Configured base period '{period_default}' is missing from {_CONFIG_FILE}.periods."
        )

    culture_id = culture_key if culture_key in cultures else culture_default
    period_id = period_key if period_key in periods else period_default

    culture = _validated_culture(culture_id)
    period = _validated_period(period_id)

    aspect_targets = culture["aspect_targets"]
    aspect_target, aspect_target_meta = _numeric_value(
        aspect_targets[hemisphere],
        f"{_CONFIG_FILE}.cultures.{culture_id}.aspect_targets.{hemisphere}",
    )
    aspect_sharpness, aspect_sharpness_meta = _numeric_value(
        culture["aspect_sharpness"],
        f"{_CONFIG_FILE}.cultures.{culture_id}.aspect_sharpness",
    )
    water_target, water_target_meta = _numeric_value(
        culture["water_distance_target"],
        f"{_CONFIG_FILE}.cultures.{culture_id}.water_distance_target",
    )
    water_target_shift, water_target_shift_meta = _numeric_value(
        period["water_target_shift"],
        f"{_CONFIG_FILE}.periods.{period_id}.water_target_shift",
    )
    water_sigma, water_sigma_meta = _numeric_value(
        culture["water_distance_sigma"],
        f"{_CONFIG_FILE}.cultures.{culture_id}.water_distance_sigma",
    )
    water_sigma_shift, water_sigma_shift_meta = _numeric_value(
        period["water_sigma_shift"],
        f"{_CONFIG_FILE}.periods.{period_id}.water_sigma_shift",
    )
    macro_multiplier, macro_multiplier_meta = _numeric_value(
        culture["macro_radius_multiplier"],
        f"{_CONFIG_FILE}.cultures.{culture_id}.macro_radius_multiplier",
    )
    macro_period, macro_period_meta = _numeric_value(
        period["macro_radius_multiplier"],
        f"{_CONFIG_FILE}.periods.{period_id}.macro_radius_multiplier",
    )
    micro_multiplier, micro_multiplier_meta = _numeric_value(
        culture["micro_radius_multiplier"],
        f"{_CONFIG_FILE}.cultures.{culture_id}.micro_radius_multiplier",
    )
    micro_period, micro_period_meta = _numeric_value(
        period["micro_radius_multiplier"],
        f"{_CONFIG_FILE}.periods.{period_id}.micro_radius_multiplier",
    )
    hyeol_threshold, hyeol_threshold_meta = _numeric_value(
        culture["hyeol_threshold"],
        f"{_CONFIG_FILE}.cultures.{culture_id}.hyeol_threshold",
    )
    hyeol_threshold_shift, hyeol_threshold_shift_meta = _numeric_value(
        period["hyeol_threshold_shift"],
        f"{_CONFIG_FILE}.periods.{period_id}.hyeol_threshold_shift",
    )
    term_target_shift, term_target_shift_meta = _numeric_value(
        culture["term_target_shift"],
        f"{_CONFIG_FILE}.cultures.{culture_id}.term_target_shift",
    )
    term_period_shift, term_period_shift_meta = _numeric_value(
        period["term_target_shift"],
        f"{_CONFIG_FILE}.periods.{period_id}.term_target_shift",
    )

    water_distance_sigma = water_sigma + water_sigma_shift
    if water_distance_sigma <= 0:
        raise RuntimeError("water_distance_sigma must remain greater than 0 after shifts.")
    combined_hyeol_threshold = hyeol_threshold + hyeol_threshold_shift
    if not 0.0 <= combined_hyeol_threshold <= 1.0:
        raise RuntimeError("hyeol_threshold must remain between 0 and 1 after shifts.")

    weight_bias_culture, weight_meta_culture = _normalize_scalar_map_with_meta(
        culture.get("weight_bias", {}),
        f"{_CONFIG_FILE}.cultures.{culture_id}.weight_bias",
    )
    weight_bias_period, weight_meta_period = _normalize_scalar_map_with_meta(
        period.get("weight_bias", {}),
        f"{_CONFIG_FILE}.periods.{period_id}.weight_bias",
    )
    term_bias_culture, term_bias_meta_culture = _normalize_scalar_map_with_meta(
        culture.get("term_bias", {}),
        f"{_CONFIG_FILE}.cultures.{culture_id}.term_bias",
    )

    merged_weight_bias = _merge_dicts(weight_bias_culture, weight_bias_period)
    merged_weight_meta = {}
    for key in set(weight_meta_culture.keys()) | set(weight_meta_period.keys()):
        merged_weight_meta[key] = _merge_meta(
            weight_meta_culture.get(key, _default_meta()),
            weight_meta_period.get(key, _default_meta()),
        )

    context = {
        "culture_key": culture_id,
        "period_key": period_id,
        "aspect_target": aspect_target,
        "aspect_sharpness": aspect_sharpness,
        "water_distance_target": water_target + water_target_shift,
        "water_distance_sigma": water_distance_sigma,
        "macro_radius_multiplier": macro_multiplier * macro_period,
        "micro_radius_multiplier": micro_multiplier * micro_period,
        "hyeol_threshold": combined_hyeol_threshold,
        "weight_bias": merged_weight_bias,
        "term_bias": deepcopy(term_bias_culture),
        "term_target_shift": term_target_shift + term_period_shift,
        "evidence": {
            "parameters": {
                "aspect_target": {"value": aspect_target, **aspect_target_meta},
                "aspect_sharpness": {"value": aspect_sharpness, **aspect_sharpness_meta},
                "water_distance_target": {
                    "value": water_target + water_target_shift,
                    **_merge_meta(water_target_meta, water_target_shift_meta),
                },
                "water_distance_sigma": {
                    "value": water_distance_sigma,
                    **_merge_meta(water_sigma_meta, water_sigma_shift_meta),
                },
                "macro_radius_multiplier": {
                    "value": macro_multiplier * macro_period,
                    **_merge_meta(macro_multiplier_meta, macro_period_meta),
                },
                "micro_radius_multiplier": {
                    "value": micro_multiplier * micro_period,
                    **_merge_meta(micro_multiplier_meta, micro_period_meta),
                },
                "hyeol_threshold": {
                    "value": combined_hyeol_threshold,
                    **_merge_meta(hyeol_threshold_meta, hyeol_threshold_shift_meta),
                },
                "term_target_shift": {
                    "value": term_target_shift + term_period_shift,
                    **_merge_meta(term_target_shift_meta, term_period_shift_meta),
                },
            },
            "weight_bias": {
                key: {"value": value, **merged_weight_meta.get(key, _default_meta())}
                for key, value in merged_weight_bias.items()
            },
            "term_bias": {
                key: {"value": value, **term_bias_meta_culture.get(key, _default_meta())}
                for key, value in term_bias_culture.items()
            },
        },
    }
    return context


def context_evidence_records(culture_key, period_key, hemisphere):
    context = build_context(culture_key, period_key, hemisphere)
    records = []
    evidence = context.get("evidence", {})
    parameters = evidence.get("parameters", {})
    for name in sorted(parameters.keys()):
        entry = parameters[name]
        records.append(
            {
                "group": "parameter",
                "name": name,
                "value": entry.get("value"),
                "source_doi": entry.get("source_doi", []),
                "evidence_level": entry.get("evidence_level", "U"),
                "note": entry.get("note", ""),
            }
        )

    for name, entry in sorted(evidence.get("weight_bias", {}).items()):
        records.append(
            {
                "group": "weight_bias",
                "name": name,
                "value": entry.get("value"),
                "source_doi": entry.get("source_doi", []),
                "evidence_level": entry.get("evidence_level", "U"),
                "note": entry.get("note", ""),
            }
        )

    for name, entry in sorted(evidence.get("term_bias", {}).items()):
        records.append(
            {
                "group": "term_bias",
                "name": name,
                "value": entry.get("value"),
                "source_doi": entry.get("source_doi", []),
                "evidence_level": entry.get("evidence_level", "U"),
                "note": entry.get("note", ""),
            }
        )
    return records


def context_evidence_html(culture_key, period_key, hemisphere, language=None):
    lang = language if language in ("ko", "en") else None
    title = ui_text("context_evidence_html_title", lang, default="Context Evidence")
    records = context_evidence_records(culture_key, period_key, hemisphere)
    if not records:
        empty_text = ui_text(
            "context_evidence_html_empty",
            lang,
            default="No evidence information is available.",
        )
        return f"<h3>{escape(title)}</h3><p>{escape(empty_text)}</p>"

    rows = []
    for record in records:
        group_name = str(record.get("group", "-"))
        group_label = ui_text(
            f"context_evidence_group_{group_name}",
            lang,
            default=group_name,
        )
        reference_text = reference_display_text(
            record.get("source_doi", []),
            language=lang,
        )
        if not reference_text:
            reference_text = "-"
        note = escape(record.get("note", "")) if record.get("note") else "-"
        value = record.get("value")
        if isinstance(value, float):
            value_text = f"{value:.4f}".rstrip("0").rstrip(".")
        else:
            value_text = str(value)
        rows.append(
            "<tr>"
            f"<td>{escape(group_label)}</td>"
            f"<td>{escape(record['name'])}</td>"
            f"<td>{escape(value_text)}</td>"
            f"<td>{escape(record.get('evidence_level', 'U'))}</td>"
            f"<td>{escape(reference_text)}</td>"
            f"<td>{note}</td>"
            "</tr>"
        )

    rows_html = "".join(rows)
    meta_culture = ui_text("context_evidence_meta_culture", lang, default="culture")
    meta_period = ui_text("context_evidence_meta_period", lang, default="period")
    meta_hemisphere = ui_text(
        "context_evidence_meta_hemisphere",
        lang,
        default="hemisphere",
    )
    meta_tier = ui_text("context_evidence_meta_tier", lang, default="context tier")
    tier_labels = _context_tier_labels(lang or "en")
    tier_label = tier_labels.get(culture_visibility_tier(culture_key), "stable")
    meta_scope = ui_text("context_evidence_meta_scope", lang, default="evidence scope")
    scope_text = culture_evidence_scope(culture_key)
    if not scope_text:
        scope_text = "-"
    col_group = ui_text("context_evidence_col_group", lang, default="group")
    col_name = ui_text("context_evidence_col_name", lang, default="name")
    col_value = ui_text("context_evidence_col_value", lang, default="value")
    col_level = ui_text("context_evidence_col_level", lang, default="level")
    col_doi = ui_text(
        "context_evidence_col_reference",
        lang,
        default="reference",
    )
    col_note = ui_text("context_evidence_col_note", lang, default="note")
    level_note = ui_text(
        "context_evidence_level_note",
        lang,
        default=(
            "Evidence level: A=direct quantitative, "
            "B=case-study anchored, C=heuristic prior, U=unspecified."
        ),
    )

    return (
        f"<h3>{escape(title)}</h3>"
        f"<p><b>{escape(meta_culture)}</b>: {escape(str(culture_key))}, "
        f"<b>{escape(meta_period)}</b>: {escape(str(period_key))}, "
        f"<b>{escape(meta_hemisphere)}</b>: {escape(str(hemisphere))}, "
        f"<b>{escape(meta_tier)}</b>: {escape(str(tier_label))}, "
        f"<b>{escape(meta_scope)}</b>: {escape(scope_text)}</p>"
        "<table border='1' cellspacing='0' cellpadding='4'>"
        "<tr>"
        f"<th>{escape(col_group)}</th>"
        f"<th>{escape(col_name)}</th>"
        f"<th>{escape(col_value)}</th>"
        f"<th>{escape(col_level)}</th>"
        f"<th>{escape(col_doi)}</th>"
        f"<th>{escape(col_note)}</th>"
        "</tr>"
        f"{rows_html}</table>"
        f"<p><small>{escape(level_note)}</small></p>"
    )
