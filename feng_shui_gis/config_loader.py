# -*- coding: utf-8 -*-
"""Load plugin JSON configuration with schema validation and caching."""

import json
import os

_CACHE = {}


_CONFIG_SCHEMAS = {
    "analysis_rules.json": {
        "required_schema_version": "1.0.0",
        "required_fields": {
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
            "enclosure": dict,
            "large_tpi": dict,
            "sashinsa": dict,
        },
    },
    "contexts.json": {
        "required_schema_version": "1.0.0",
        "required_fields": {
            "base_culture_key": str,
            "base_period_key": str,
            "neutral_defaults": dict,
            "cultures": dict,
            "periods": dict,
        },
    },
    "profiles.json": {
        "required_schema_version": "1.0.0",
        "required_fields": {
        },
    },
    "terms.json": {
        "required_schema_version": "1.0.0",
        "required_fields": {
            "term_labels": dict,
            "radius_scales": dict,
            "special_terms": dict,
            "term_specs": list,
        },
    },
    "references.json": {
        "required_schema_version": "1.0.0",
        "required_fields": {
            "references": list,
        },
    },
    "ridge_classes.json": {
        "required_schema_version": "1.0.0",
        "required_fields": {
            "computed_classes": list,
            "named_system": dict,
        },
    },
    "ui_texts.json": {
        "required_schema_version": "1.0.0",
        "required_fields": {
            "texts": dict,
        },
    },
}

_SCHEMA_MIGRATIONS = {
    "analysis_rules.json": {},
    "contexts.json": {},
    "profiles.json": {},
    "terms.json": {},
    "references.json": {},
    "ridge_classes.json": {},
    "ui_texts.json": {},
}


def _config_path(filename):
    return os.path.join(os.path.dirname(__file__), "config", filename)


def _fail(path, message):
    raise RuntimeError(f"{path}: {message}")


def _load_file(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing config file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON config: {path}") from exc


def _require_type(value, path, expected_type):
    if not isinstance(value, expected_type):
        expected_name = (
            "list" if expected_type is list else "JSON object" if expected_type is dict else str(expected_type)
        )
        _fail(path, f"Expected {expected_name}, got {type(value).__name__}.")


def _require_schema_version(config, path, contract):
    raw_version = config.get("schema_version")
    if raw_version is None:
        _fail(path, "Missing required schema_version.")
    version = str(raw_version).strip()
    if not version:
        _fail(path, "schema_version cannot be empty.")
    expected = contract["required_schema_version"]
    if version != expected:
        migrations = _SCHEMA_MIGRATIONS.get(os.path.basename(path), {})
        if version in migrations:
            return version
        _fail(path, f"Unsupported schema_version '{version}'. Expected '{expected}'.")
    return version


def _validate_required_fields(config, filename, path, contract):
    for field_name, expected_type in contract["required_fields"].items():
        if field_name not in config:
            _fail(path, f"Missing required top-level field '{field_name}'.")
        _require_type(config[field_name], f"{filename}:{field_name}", expected_type)


def _validate_references_contract(config, filename, path):
    references = config.get("references", [])
    for index, item in enumerate(references):
        item_path = f"{filename}:references[{index}]"
        _require_type(item, item_path, dict)
        if not item.get("doi") and not item.get("id"):
            _fail(item_path, "Each reference must have 'doi' or 'id'.")
        if "short" in item and not isinstance(item["short"], dict):
            _require_type(item["short"], f"{item_path}.short", dict)
        if "summary" in item and not isinstance(item["summary"], dict):
            _require_type(item["summary"], f"{item_path}.summary", dict)


def _validate_ui_text_contract(config, filename, path):
    texts = config.get("texts", {})
    _require_type(texts, f"{filename}.texts", dict)
    optional_nodes = ("help_html", "hydro_legend", "metric_help_items", "ridge_legend", "term_meanings")
    for node in optional_nodes:
        value = config.get(node)
        if value is None:
            continue
        if node in {"help_html", "term_meanings", "metric_help_items"} and not isinstance(value, dict):
            _require_type(value, f"{filename}.{node}", dict)
        if node in {"hydro_legend", "ridge_legend"} and not isinstance(value, list):
            _require_type(value, f"{filename}.{node}", list)


def _validate_config_contract(filename, path, config):
    if not isinstance(config, dict):
        _fail(path, f"{filename} must be a JSON object.")
    if filename not in _CONFIG_SCHEMAS:
        return config
    contract = _CONFIG_SCHEMAS[filename]
    _require_schema_version(config, path, contract)
    _validate_required_fields(config, filename, path, contract)
    if filename == "references.json":
        _validate_references_contract(config, filename, path)
    if filename == "ui_texts.json":
        _validate_ui_text_contract(config, filename, path)
    return config


def load_json(filename):
    path = _config_path(filename)
    if path in _CACHE:
        return _CACHE[path]

    data = _load_file(path)
    data = _validate_config_contract(filename, path, data)
    _CACHE[path] = data
    return data


def clear_cache():
    _CACHE.clear()
