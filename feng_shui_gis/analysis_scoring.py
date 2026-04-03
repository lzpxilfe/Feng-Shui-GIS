# -*- coding: utf-8 -*-
"""Pure scoring helpers extracted from the analyzer core."""

from __future__ import annotations

from .reference_catalog import reference_display_text


def indicator_contributions(indicators, profile):
    rows = []
    weights = profile.get("weights", {}) if isinstance(profile, dict) else {}
    if not isinstance(weights, dict):
        return rows
    for key, weight in weights.items():
        score = indicators.get(key)
        if score is None:
            continue
        try:
            weight_value = float(weight)
            score_value = float(score)
        except (TypeError, ValueError):
            continue
        rows.append(
            {
                "key": key,
                "weight": weight_value,
                "score": score_value,
                "contrib": weight_value * score_value,
            }
        )
    rows.sort(key=lambda item: item["contrib"], reverse=True)
    return rows


def profile_weighted_score(indicators, profile):
    weights = profile.get("weights", {}) if isinstance(profile, dict) else {}
    weighted = []
    for key, weight in weights.items():
        value = indicators.get(key)
        if value is not None:
            weighted.append((weight, value))
    if not weighted:
        return None
    numerator = sum(weight * value for weight, value in weighted)
    denominator = sum(weight for weight, _ in weighted)
    return numerator / denominator if denominator else None


def profile_confidence(indicators, profile):
    weights = profile.get("weights", {}) if isinstance(profile, dict) else {}
    total = sum(weights.values()) if isinstance(weights, dict) else 0.0
    if total <= 0:
        return None
    available = 0.0
    for key, weight in weights.items():
        if indicators.get(key) is not None:
            available += weight
    return available / total


def explain_top_factors(indicators, profile):
    weighted = []
    for key, weight in (profile.get("weights", {}) if isinstance(profile, dict) else {}).items():
        score = indicators.get(key)
        if score is None:
            continue
        weighted.append((weight * score, key, score))
    if not weighted:
        return "no-data"
    weighted.sort(reverse=True)
    return ",".join(f"{key}:{score:.2f}" for _, key, score in weighted[:2])


def paper_evidence_summary(profile, language="ko", limit=3):
    records = profile.get("paper_evidence_records") if isinstance(profile, dict) else None
    if not isinstance(records, list) or not records:
        return ""

    summary_keys = []
    sources = []
    for record in records:
        if not isinstance(record, dict):
            continue
        group = str(record.get("group", "")).strip()
        name = str(record.get("name", "")).strip()
        value = record.get("value")
        level = str(record.get("evidence_level", "U")).strip().upper() or "U"
        if group and name:
            if isinstance(value, (int, float)):
                summary_keys.append(f"{group}.{name}={value:+.2f}({level})")
            else:
                summary_keys.append(f"{group}.{name}({level})")
        for source in record.get("source_doi", []):
            if source and source not in sources:
                sources.append(source)
    if not sources:
        return ""
    refs = reference_display_text(sources, language=language, limit=limit)
    if not refs:
        return ""
    selected = ", ".join(summary_keys[:3]) if summary_keys else "profile-paper-evidence"
    return f"{selected} | {refs}"
