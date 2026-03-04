# -*- coding: utf-8 -*-
"""UI text catalog loaded from JSON config."""

from .config_loader import load_json
from .locale import language_code

_UI_FILE = "ui_texts.json"


def _catalog():
    data = load_json(_UI_FILE)
    return data if isinstance(data, dict) else {}


def _coerce_text(value):
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    if value is None:
        return ""
    return str(value)


def _localized(node, language=None):
    if not isinstance(node, dict):
        return node
    lang = (language or language_code() or "ko").lower()
    return (
        node.get(lang)
        or node.get("ko")
        or node.get("en")
        or next(iter(node.values()), "")
    )


def ui_text(key, language=None, default=""):
    texts = _catalog().get("texts", {})
    value = _localized(texts.get(key), language)
    text = _coerce_text(value)
    return text if text else default


def ui_metric_help_items(language=None):
    items_node = _catalog().get("metric_help_items", {})
    selected = _localized(items_node, language)
    if not isinstance(selected, list):
        return []

    items = []
    for item in selected:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        description = str(item.get("description", "")).strip()
        if not label:
            continue
        items.append((label, description))
    return items


def ui_term_meanings(language=None):
    meanings_node = _catalog().get("term_meanings", {})
    selected = _localized(meanings_node, language)
    return selected if isinstance(selected, dict) else {}


def ui_ridge_legend(language=None):
    rows = _catalog().get("ridge_legend", [])
    if not isinstance(rows, list):
        return []
    normalized = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        label = _localized(item.get("label", {}), language)
        normalized.append(
            {
                "id": str(item.get("id", "")).strip(),
                "label": _coerce_text(label),
                "color": str(item.get("color", "#333333")),
                "width": float(item.get("width", 1.0)),
                "opacity": float(item.get("opacity", 0.5)),
            }
        )
    return normalized


def ui_hydro_legend(language=None):
    rows = _catalog().get("hydro_legend", [])
    if not isinstance(rows, list):
        return []
    normalized = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        label = _localized(item.get("label", {}), language)
        normalized.append(
            {
                "id": str(item.get("id", "")).strip(),
                "label": _coerce_text(label),
                "color": str(item.get("color", "#5f93d2")),
                "width": float(item.get("width", 1.0)),
            }
        )
    return normalized


def ui_help_html(section_key, language=None, **kwargs):
    help_node = _catalog().get("help_html", {})
    section_node = help_node.get(section_key, {})
    localized = _localized(section_node, language)
    template = _coerce_text(localized)
    if not template:
        return ""
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError):
            return template
    return template
