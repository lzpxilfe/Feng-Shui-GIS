# -*- coding: utf-8 -*-
"""Metadata grouping helpers for analysis and calibration reporting."""

from __future__ import annotations

from collections import defaultdict


def metadata_text(value):
    if value is None:
        return ""
    return str(value).strip()


def metadata_field_name(layer, candidates):
    if layer is None:
        return None
    exact_map = {}
    field_names = []
    for field in layer.fields():
        name = field.name()
        lower_name = name.lower()
        exact_map[lower_name] = name
        field_names.append((name, lower_name))
    for candidate in candidates:
        if candidate in exact_map:
            return exact_map[candidate]
    for candidate in candidates:
        for name, lower_name in field_names:
            if candidate in lower_name:
                return name
    return None


def metadata_grouping(layer, kind, candidates, limit=8):
    field_name = metadata_field_name(layer, candidates)
    if not field_name:
        return None
    counts = defaultdict(int)
    for feature in layer.getFeatures():
        value_text = metadata_text(feature[field_name])
        counts[value_text if value_text else "(empty)"] += 1
    if not counts:
        return None
    total = sum(counts.values())
    rows = []
    for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]:
        rows.append(
            {
                "value": value,
                "count": count,
                "share": (count / total) if total > 0 else 0.0,
            }
        )
    return {
        "kind": kind,
        "field": field_name,
        "distinct_count": len(counts),
        "rows": rows,
    }


def summarize_site_metadata(layer):
    summary = {
        "layer_name": layer.name() if layer is not None else "",
        "groupings": [],
    }
    if layer is None:
        return summary
    grouping_specs = (
        (
            "site_group",
            (
                "site_group",
                "site_type",
                "siteclass",
                "site_class",
                "category",
                "class",
                "type",
                "cluster",
                "group",
            ),
        ),
        (
            "country",
            (
                "country",
                "nation",
                "state",
                "region",
                "culture",
                "tradition",
            ),
        ),
        (
            "period",
            (
                "period",
                "era",
                "phase",
                "chronology",
                "date_period",
                "age",
            ),
        ),
    )
    for kind, candidates in grouping_specs:
        grouping = metadata_grouping(layer, kind, candidates)
        if grouping is not None:
            summary["groupings"].append(grouping)
    return summary
