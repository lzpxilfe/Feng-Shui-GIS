# -*- coding: utf-8 -*-
"""Load plugin JSON configuration with light validation and caching."""

import json
import os

_CACHE = {}


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


def clear_cache():
    _CACHE.clear()
