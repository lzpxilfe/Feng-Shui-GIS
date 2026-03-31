# -*- coding: utf-8 -*-
"""Load plugin JSON configuration with schema versioning, migration, and validation."""

import json
import os
from typing import Any, Dict, Optional

_CACHE = {}
_SCHEMA_VERSION_KEY = "schema_version"

_SUPPORTED_SCHEMA_VERSIONS = {
    "analysis_rules.json": 1,
    "contexts.json": 1,
    "profiles.json": 1,
    "terms.json": 1,
    "references.json": 1,
    "ui_texts.json": 1,
    "local_profiles.json": 1,
}

_CONFIG_CONTRACTS = {
    "analysis_rules.json": {
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
        "required_fields": {
            "base_culture_key": str,
            "base_period_key": str,
            "neutral_defaults": dict,
            "cultures": dict,
            "periods": dict,
        }
    },
    "profiles.json": {
        "required_fields": {},
    },
    "terms.json": {
        "required_fields": {
            "term_labels": dict,
            "radius_scales": dict,
            "special_terms": dict,
            "term_specs": list,
        }
    },
    "references.json": {
        "required_fields": {
            "references": list,
        }
    },
    "ui_texts.json": {
        "required_fields": {
            "texts": dict,
        }
    },
    "local_profiles.json": {
        "required_fields": {},
    },
}

_SCHEMA_MIGRATIONS = {
    "analysis_rules.json": {},
    "contexts.json": {},
    "profiles.json": {},
    "terms.json": {},
    "references.json": {},
    "ui_texts.json": {},
    "local_profiles.json": {},
}


def _config_path(filename):
    return os.path.join(os.path.dirname(__file__), "config", filename)


def _fail(path, message):
    raise RuntimeError(f"{path}: {message}")


def _coerce_int(value, file_label):
    if value is None:
        raise RuntimeError(f"{file_label}: schema_version is required.")
    if isinstance(value, bool):
        raise RuntimeError(f"{file_label}: schema_version must be an integer.")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{file_label}: schema_version must be an integer.") from exc


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
            "JSON array"
            if expected_type is list
            else "JSON object"
            if expected_type is dict
            else str(expected_type)
        )
        _fail(path, f"Expected {expected_name}, got {type(value).__name__}.")


def _require_dict(value, path):
    _require_type(value, path, dict)


def _normalize_schema(payload: Dict[str, Any], file_label: str, expected_version: int):
    version = _coerce_int(payload.get(_SCHEMA_VERSION_KEY), file_label)
    if version == expected_version:
        return payload

    migrations = _SCHEMA_MIGRATIONS.get(file_label, {})
    if version not in migrations:
        if version > expected_version:
            _fail(
                file_label,
                "Schema is newer than supported "
                f"(found v{version}, expected v{expected_version}).",
            )
        raise RuntimeError(f"{file_label}: Unsupported schema version v{version}.")

    try:
        migrated = migrations[version](payload)
    except Exception as exc:
        raise RuntimeError(f"{file_label}: Failed schema migration from v{version} to v{expected_version}.") from exc
    if not isinstance(migrated, dict):
        _fail(file_label, "Schema migration returned non-object payload.")
    migrated[_SCHEMA_VERSION_KEY] = expected_version
    return migrated


def _validate_field_types(config, filename, contract):
    for field, expected_type in contract.get("required_fields", {}).items():
        if field not in config:
            _fail(filename, f"Missing required top-level field '{field}'.")
        _require_type(config[field], f"{filename}.{field}", expected_type)


def _validate_references_contract(config, filename):
    references = config.get("references", [])
    for index, item in enumerate(references):
        item_path = f"{filename}.references[{index}]"
        _require_dict(item, item_path)
        if not item.get("doi") and not item.get("id"):
            _fail(item_path, "Each reference must include at least one of 'doi' or 'id'.")
        if "short" in item:
            _require_type(item["short"], f"{item_path}.short", dict)
        if "summary" in item:
            _require_type(item["summary"], f"{item_path}.summary", dict)


def _validate_ui_text_contract(config, filename):
    optional_nodes = {
        "help_html": dict,
        "hydro_legend": list,
        "metric_help_items": dict,
        "ridge_legend": list,
        "term_meanings": dict,
    }
    for node_name, expected_type in optional_nodes.items():
        if node_name not in config:
            continue
        _require_type(config[node_name], f"{filename}.{node_name}", expected_type)


def _validate_schema(filename, path, data, expected_schema):
    if not isinstance(data, dict):
        _fail(path, f"{filename} must be a JSON object.")
    if filename not in _SUPPORTED_SCHEMA_VERSIONS:
        return data

    contract = _CONFIG_CONTRACTS.get(filename, {})
    if expected_schema is None:
        expected_schema = _SUPPORTED_SCHEMA_VERSIONS[filename]
    if not isinstance(expected_schema, int):
        _fail(path, "Requested schema version must be an integer.")

    normalized = _normalize_schema(data, filename, expected_schema)
    _validate_field_types(normalized, filename, contract)
    if filename == "references.json":
        _validate_references_contract(normalized, filename)
    if filename == "ui_texts.json":
        _validate_ui_text_contract(normalized, filename)
    return normalized


def load_json(filename):
    path = _config_path(filename)
    if path in _CACHE:
        return _CACHE[path]

    raw_data = _load_file(path)
    data = _validate_schema(filename, path, raw_data, _SUPPORTED_SCHEMA_VERSIONS.get(filename))
    _CACHE[path] = data
    return data


def load_config_json(filename, schema_version: Optional[int] = None):
    data = load_json(filename)
    if not isinstance(data, dict):
        _fail(filename, f"{filename}: Invalid config top-level object.")

    supported = _SUPPORTED_SCHEMA_VERSIONS.get(filename)
    if supported is not None:
        if schema_version is not None:
            expected = _coerce_int(schema_version, filename)
            if expected != supported:
                raise RuntimeError(
                    f"Unsupported expected schema version for {filename}: {expected} "
                    f"(expected {supported})."
                )
        data = _validate_schema(filename, filename, data, schema_version or supported)
    return data


def clear_cache():
    _CACHE.clear()
