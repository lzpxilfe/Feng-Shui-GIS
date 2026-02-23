# -*- coding: utf-8 -*-
"""Country/period context profiles for Feng Shui archaeology workflows."""

from copy import deepcopy
from html import escape

from .config_loader import load_json

_CONFIG_FILE = "contexts.json"
_LEVEL_ORDER = {"A": 0, "B": 1, "C": 2, "U": 3}


def _config():
    return load_json(_CONFIG_FILE)


def _cultures():
    return _config().get("cultures", {})


def _periods():
    return _config().get("periods", {})


def _default_meta():
    return {"source_doi": [], "evidence_level": "U", "note": ""}


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


def _value_and_meta(node, default_value):
    if isinstance(node, dict) and "value" in node:
        return node.get("value", default_value), _meta_from_node(node)
    if node is None:
        return default_value, _default_meta()
    return node, _default_meta()


def _dict_values_and_meta(node):
    if not isinstance(node, dict):
        return {}, {}
    values = {}
    metas = {}
    for key, raw_value in node.items():
        value, meta = _value_and_meta(raw_value, 0.0)
        values[key] = value
        metas[key] = meta
    return values, metas


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
    levels = [first_meta.get("evidence_level", "U"), second_meta.get("evidence_level", "U")]
    levels = [item for item in levels if item in _LEVEL_ORDER]
    level = sorted(levels, key=lambda item: _LEVEL_ORDER[item])[0] if levels else "U"
    notes = [first_meta.get("note", "").strip(), second_meta.get("note", "").strip()]
    note = " | ".join(item for item in notes if item)
    return {"source_doi": unique_sources, "evidence_level": level, "note": note}


def _normalize_scalar_map(node):
    values, _ = _dict_values_and_meta(node)
    normalized = {}
    for key, value in values.items():
        try:
            normalized[key] = float(value)
        except (TypeError, ValueError):
            normalized[key] = 0.0
    return normalized


def _normalize_scalar_map_with_meta(node):
    values, metas = _dict_values_and_meta(node)
    normalized = {}
    for key, value in values.items():
        try:
            normalized[key] = float(value)
        except (TypeError, ValueError):
            normalized[key] = 0.0
    return normalized, metas


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

    aspect_targets = culture.get("aspect_targets", {})
    aspect_default = 180.0 if hemisphere == "north" else 0.0
    aspect_target, aspect_target_meta = _value_and_meta(
        aspect_targets.get(hemisphere),
        aspect_default,
    )
    aspect_sharpness, aspect_sharpness_meta = _value_and_meta(
        culture.get("aspect_sharpness"),
        1.0,
    )
    water_target, water_target_meta = _value_and_meta(
        culture.get("water_distance_target"),
        220.0,
    )
    water_target_shift, water_target_shift_meta = _value_and_meta(
        period.get("water_target_shift"),
        0.0,
    )
    water_sigma, water_sigma_meta = _value_and_meta(
        culture.get("water_distance_sigma"),
        350.0,
    )
    water_sigma_shift, water_sigma_shift_meta = _value_and_meta(
        period.get("water_sigma_shift"),
        0.0,
    )
    macro_multiplier, macro_multiplier_meta = _value_and_meta(
        culture.get("macro_radius_multiplier"),
        1.0,
    )
    macro_period, macro_period_meta = _value_and_meta(
        period.get("macro_radius_multiplier"),
        1.0,
    )
    micro_multiplier, micro_multiplier_meta = _value_and_meta(
        culture.get("micro_radius_multiplier"),
        1.0,
    )
    micro_period, micro_period_meta = _value_and_meta(
        period.get("micro_radius_multiplier"),
        1.0,
    )
    hyeol_threshold, hyeol_threshold_meta = _value_and_meta(
        culture.get("hyeol_threshold"),
        0.62,
    )
    hyeol_threshold_shift, hyeol_threshold_shift_meta = _value_and_meta(
        period.get("hyeol_threshold_shift"),
        0.0,
    )
    term_target_shift, term_target_shift_meta = _value_and_meta(
        culture.get("term_target_shift"),
        0.0,
    )
    term_period_shift, term_period_shift_meta = _value_and_meta(
        period.get("term_target_shift"),
        0.0,
    )

    weight_bias_culture, weight_meta_culture = _normalize_scalar_map_with_meta(
        culture.get("weight_bias", {})
    )
    weight_bias_period, weight_meta_period = _normalize_scalar_map_with_meta(
        period.get("weight_bias", {})
    )
    term_bias_culture, term_bias_meta_culture = _normalize_scalar_map_with_meta(
        culture.get("term_bias", {})
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
        "aspect_target": float(aspect_target),
        "aspect_sharpness": float(aspect_sharpness),
        "water_distance_target": float(water_target) + float(water_target_shift),
        "water_distance_sigma": max(
            120.0,
            float(water_sigma) + float(water_sigma_shift),
        ),
        "macro_radius_multiplier": float(macro_multiplier) * float(macro_period),
        "micro_radius_multiplier": float(micro_multiplier) * float(micro_period),
        "hyeol_threshold": max(
            0.50,
            min(
                0.90,
                float(hyeol_threshold) + float(hyeol_threshold_shift),
            ),
        ),
        "weight_bias": merged_weight_bias,
        "term_bias": deepcopy(term_bias_culture),
        "term_target_shift": float(term_target_shift) + float(term_period_shift),
        "evidence": {
            "parameters": {
                "aspect_target": {
                    "value": float(aspect_target),
                    **aspect_target_meta,
                },
                "aspect_sharpness": {
                    "value": float(aspect_sharpness),
                    **aspect_sharpness_meta,
                },
                "water_distance_target": {
                    "value": float(water_target) + float(water_target_shift),
                    **_merge_meta(water_target_meta, water_target_shift_meta),
                },
                "water_distance_sigma": {
                    "value": max(120.0, float(water_sigma) + float(water_sigma_shift)),
                    **_merge_meta(water_sigma_meta, water_sigma_shift_meta),
                },
                "macro_radius_multiplier": {
                    "value": float(macro_multiplier) * float(macro_period),
                    **_merge_meta(macro_multiplier_meta, macro_period_meta),
                },
                "micro_radius_multiplier": {
                    "value": float(micro_multiplier) * float(micro_period),
                    **_merge_meta(micro_multiplier_meta, micro_period_meta),
                },
                "hyeol_threshold": {
                    "value": max(
                        0.50,
                        min(0.90, float(hyeol_threshold) + float(hyeol_threshold_shift)),
                    ),
                    **_merge_meta(hyeol_threshold_meta, hyeol_threshold_shift_meta),
                },
                "term_target_shift": {
                    "value": float(term_target_shift) + float(term_period_shift),
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


def context_evidence_html(culture_key, period_key, hemisphere):
    records = context_evidence_records(culture_key, period_key, hemisphere)
    if not records:
        return "<h3>컨텍스트 근거</h3><p>근거 정보가 없습니다.</p>"

    rows = []
    for record in records:
        doi_text = "<br/>".join(
            f'<a href="{escape(source)}">{escape(source)}</a>'
            for source in record.get("source_doi", [])
        )
        if not doi_text:
            doi_text = "-"
        note = escape(record.get("note", "")) if record.get("note") else "-"
        value = record.get("value")
        if isinstance(value, float):
            value_text = f"{value:.4f}".rstrip("0").rstrip(".")
        else:
            value_text = str(value)
        rows.append(
            "<tr>"
            f"<td>{escape(record['group'])}</td>"
            f"<td>{escape(record['name'])}</td>"
            f"<td>{escape(value_text)}</td>"
            f"<td>{escape(record.get('evidence_level', 'U'))}</td>"
            f"<td>{doi_text}</td>"
            f"<td>{note}</td>"
            "</tr>"
        )

    rows_html = "".join(rows)
    return (
        "<h3>컨텍스트 파라미터 근거</h3>"
        f"<p><b>culture</b>: {escape(str(culture_key))}, "
        f"<b>period</b>: {escape(str(period_key))}, "
        f"<b>hemisphere</b>: {escape(str(hemisphere))}</p>"
        "<table border='1' cellspacing='0' cellpadding='4'>"
        "<tr><th>group</th><th>name</th><th>value</th><th>level</th><th>source_doi</th><th>note</th></tr>"
        f"{rows_html}</table>"
        "<p><small>evidence level: A=direct quantitative, B=case-study anchored, C=heuristic prior, U=unspecified.</small></p>"
    )


def _merge_dicts(first, second):
    merged = {}
    keys = set(first.keys()) | set(second.keys())
    for key in keys:
        merged[key] = first.get(key, 0.0) + second.get(key, 0.0)
    return merged
