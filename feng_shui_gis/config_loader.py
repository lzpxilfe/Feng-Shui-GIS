# -*- coding: utf-8 -*-
"""Load plugin JSON configuration with schema versioning and caching."""

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
    "local_profiles.json": 1,
}


def _coerce_int(value, file_label):
    if value is None:
        return None
    if isinstance(value, bool):
        raise RuntimeError(f"{file_label}: schema_version must be an integer.")
    try:
        return int(value)
    except (TypeError, ValueError):
        raise RuntimeError(f"{file_label}: schema_version must be an integer.")


def _normalize_schema_bundle(raw: Dict[str, Any]):
    if "schema_version" not in raw:
        payload = dict(raw)
        payload[_SCHEMA_VERSION_KEY] = 0
    else:
        payload = dict(raw)
    return payload


def _migrate_schema(raw: Dict[str, Any], file_label: str, target_version: int):
    payload = _normalize_schema_bundle(raw)
    source_version = _coerce_int(payload.get(_SCHEMA_VERSION_KEY), file_label)
    if source_version == target_version:
        return payload
    if source_version is None:
        raise RuntimeError(f"{file_label}: schema_version is invalid.")

    if source_version > target_version:
        raise RuntimeError(
            f"{file_label}: config schema v{source_version} is newer than supported "
            f"v{target_version}. Please upgrade this plugin."
        )

    if source_version < 0:
        raise RuntimeError(f"{file_label}: schema_version must be >= 0.")

    # Current schema version 1 adds only explicit provenance. No semantic migration
    # exists yet, so keep payloads but bump the version number.
    payload[_SCHEMA_VERSION_KEY] = target_version
    return payload


def _config_path(filename):
    return os.path.join(os.path.dirname(__file__), "config", filename)


def load_json(filename):
    path = _config_path(filename)
    if path in _CACHE:
        return _CACHE[path]

    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing config file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON config: {path}") from exc

    _CACHE[path] = data
    return data


def load_config_json(filename, schema_version: Optional[int] = None):
    data = load_json(filename)
    if schema_version is None:
        return data
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid config top-level object: {filename}")

    expected_schema = int(schema_version)
    known_version = _SUPPORTED_SCHEMA_VERSIONS.get(filename, 1)
    if expected_schema != known_version:
        raise RuntimeError(
            f"Unsupported expected schema version for {filename}: {expected_schema} "
            f"(expected {known_version})."
        )

    return _migrate_schema(data, filename, expected_schema)


def clear_cache():
    _CACHE.clear()
