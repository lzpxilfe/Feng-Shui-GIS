# -*- coding: utf-8 -*-
"""Citation-first reference helpers for evidence and help UI."""

from html import escape

from .config_loader import load_json
from .locale import language_code

_REFERENCE_FILE = "references.json"


def _catalog():
    data = load_json(_REFERENCE_FILE)
    items = data.get("references", [])
    return items if isinstance(items, list) else []


def _localized(node, language=None):
    if not isinstance(node, dict):
        return ""
    lang = (language or language_code() or "en").lower()
    return (
        node.get(lang)
        or node.get("en")
        or node.get("ko")
        or next(iter(node.values()), "")
    )


def normalize_reference_id(value):
    text = str(value or "").strip()
    if not text:
        return ""
    lower = text.lower()
    prefixes = (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi:",
    )
    for prefix in prefixes:
        if lower.startswith(prefix):
            text = text[len(prefix) :]
            break
    return text.strip()


def _entry_keys(item):
    if not isinstance(item, dict):
        return []
    keys = []
    ref_id = str(item.get("id", "")).strip()
    if ref_id:
        keys.append(ref_id)
    doi = normalize_reference_id(item.get("doi"))
    if doi and doi not in keys:
        keys.append(doi)
    return keys


def _entries_by_key():
    lookup = {}
    for item in _catalog():
        for key in _entry_keys(item):
            lookup[key] = item
    return lookup


def reference_entry(value):
    key = normalize_reference_id(value)
    entry = _entries_by_key().get(key, {})
    return {
        "id": str(entry.get("id", "")).strip(),
        "doi": normalize_reference_id(entry.get("doi")),
        "short": entry.get("short", {}),
        "summary": entry.get("summary", {}),
        "show_in_help": bool(entry.get("show_in_help", False)),
    }


def reference_label(value, language=None):
    entry = reference_entry(value)
    label = _localized(entry.get("short", {}), language)
    return label or entry.get("doi") or str(value or "").strip()


def reference_summary(value, language=None):
    entry = reference_entry(value)
    return _localized(entry.get("summary", {}), language)


def reference_labels(values, language=None, limit=None):
    if isinstance(values, (str, bytes)):
        values = [values]
    labels = []
    seen = set()
    for value in values or []:
        label = reference_label(value, language=language)
        if not label or label in seen:
            continue
        seen.add(label)
        labels.append(label)
        if limit is not None and len(labels) >= int(limit):
            break
    return labels


def reference_display_text(values, language=None, limit=None):
    labels = reference_labels(values, language=language, limit=limit)
    return "; ".join(labels)


def references_help_html(language=None):
    lang = (language or language_code() or "ko").lower()
    title = "연구 참고" if lang == "ko" else "References"
    note = (
        "국가/시대 파라미터는 여전히 지역별 보정이 필요합니다."
        if lang == "ko"
        else "Country and period parameters still need local calibration."
    )

    rows = [f"<h3>{escape(title)}</h3>"]
    for item in _catalog():
        if not isinstance(item, dict) or not item.get("show_in_help", False):
            continue
        doi = normalize_reference_id(item.get("doi"))
        ref_id = str(item.get("id", "")).strip()
        short = _localized(item.get("short", {}), lang) or doi or ref_id
        summary = _localized(item.get("summary", {}), lang)
        parts = [f"<b>{escape(short)}</b>"]
        if summary:
            parts.append(escape(summary))
        if doi or ref_id:
            parts.append(f"<code>{escape(doi or ref_id)}</code>")
        rows.append(f"<p>- {' | '.join(parts)}</p>")
    rows.append(f"<p><small>{escape(note)}</small></p>")
    return "".join(rows)
