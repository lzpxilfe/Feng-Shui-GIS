# -*- coding: utf-8 -*-
"""Helpers for compare-report payloads, markdown, and popup HTML."""

from __future__ import annotations

import json
import os
from datetime import datetime
from html import escape
from typing import Any, Dict, Iterable, List, Tuple

from .ui_catalog import ui_text


def _reason_excerpt(text: Any, limit: int) -> str:
    clean = str(text or "").strip().replace("\n", " ")
    limit = max(1, int(limit))
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"


def _markdown_table(headers: Iterable[Any], rows: Iterable[Iterable[Any]]) -> str:
    safe_headers = [str(header).replace("|", "/") for header in headers]
    lines = [
        "| " + " | ".join(safe_headers) + " |",
        "| " + " | ".join(["---"] * len(safe_headers)) + " |",
    ]
    for row in rows:
        safe_row = [str(cell).replace("|", "/") for cell in row]
        lines.append("| " + " | ".join(safe_row) + " |")
    return "\n".join(lines)


def build_compare_report_payload(
    *,
    stamp: str,
    site_layer_name: str,
    base_profile_key: str,
    compare_profile_key: str,
    base_stats: Dict[str, Any],
    compare_stats: Dict[str, Any],
    delta_stats: Dict[str, Any],
    top_changes: List[Dict[str, Any]],
    change_layer_name: str,
) -> Dict[str, Any]:
    return {
        "timestamp": stamp,
        "site_layer_name": site_layer_name,
        "base_profile_key": base_profile_key,
        "compare_profile_key": compare_profile_key,
        "base_stats": dict(base_stats or {}),
        "compare_stats": dict(compare_stats or {}),
        "delta_stats": dict(delta_stats or {}),
        "top_changes": list(top_changes or []),
        "change_layer_name": change_layer_name,
    }


def write_compare_report(
    *,
    report_dir: str,
    label_language: str,
    site_layer_name: str,
    base_profile_key: str,
    compare_profile_key: str,
    base_stats: Dict[str, Any],
    compare_stats: Dict[str, Any],
    delta_stats: Dict[str, Any],
    top_changes: List[Dict[str, Any]],
    change_layer_name: str,
    reason_excerpt_limit: int = 44,
) -> Tuple[Dict[str, Any], str, str]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"feng_shui_compare_{stamp}"
    json_path = os.path.join(report_dir, f"{base_name}.json")
    md_path = os.path.join(report_dir, f"{base_name}.md")
    payload = build_compare_report_payload(
        stamp=stamp,
        site_layer_name=site_layer_name,
        base_profile_key=base_profile_key,
        compare_profile_key=compare_profile_key,
        base_stats=base_stats,
        compare_stats=compare_stats,
        delta_stats=delta_stats,
        top_changes=top_changes,
        change_layer_name=change_layer_name,
    )

    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    top_change_rows = []
    for row in top_changes or []:
        if not isinstance(row, dict):
            continue
        reason_compare = ui_text(
            "compare_report_reason_compare_template",
            label_language,
            default="Base: {base} / Calibrated: {calibrated}",
        ).format(
            base=_reason_excerpt(row.get("base_reason", ""), reason_excerpt_limit),
            calibrated=_reason_excerpt(row.get("compare_reason", ""), reason_excerpt_limit),
        )
        top_change_rows.append(
            [
                row.get("label", ""),
                f"{float(row.get('base_score', 0.0)):.4f}",
                f"{float(row.get('compare_score', 0.0)):.4f}",
                f"{float(row.get('delta', 0.0)):+.4f}",
                reason_compare,
            ]
        )

    if top_change_rows:
        top_change_table = _markdown_table(
            [
                ui_text("compare_report_feature_label", label_language, default="Feature"),
                ui_text("compare_report_base_label", label_language, default="Base"),
                ui_text("compare_report_calibrated_label", label_language, default="Calibrated"),
                ui_text("compare_report_delta_label", label_language, default="Delta"),
                ui_text(
                    "compare_report_reason_compare_label",
                    label_language,
                    default="Reason compare",
                ),
            ],
            top_change_rows,
        )
    else:
        top_change_table = ui_text(
            "compare_report_no_top_changes",
            label_language,
            default="No top-changed features were recorded.",
        )

    report_title = ui_text(
        "compare_report_title_template",
        label_language,
        default="Feng Shui Comparison Report ({stamp})",
    ).format(base=base_profile_key, calibrated=compare_profile_key, stamp=stamp)

    markdown = (
        f"# {report_title}\n\n"
        f"- {ui_text('compare_report_site_layer_label', label_language, default='Site layer')}: {site_layer_name}\n"
        f"- {ui_text('compare_report_base_profile_label', label_language, default='Base profile')}: {base_profile_key}\n"
        f"- {ui_text('compare_report_calibrated_profile_label', label_language, default='Calibrated profile')}: {compare_profile_key}\n"
        f"- {ui_text('compare_report_change_layer_label', label_language, default='Change layer')}: {change_layer_name or 'n/a'}\n\n"
        f"## {ui_text('compare_report_summary_title', label_language, default='Summary statistics')}\n\n"
        f"- {ui_text('compare_report_base_mean_label', label_language, default='Base mean')}: {float(base_stats.get('mean', 0.0) if isinstance(base_stats, dict) else 0.0):.4f}\n"
        f"- {ui_text('compare_report_calibrated_mean_label', label_language, default='Calibrated mean')}: {float(compare_stats.get('mean', 0.0) if isinstance(compare_stats, dict) else 0.0):.4f}\n"
        f"- {ui_text('compare_report_mean_delta_label', label_language, default='Mean score delta')}: {float(delta_stats.get('mean_delta', 0.0) if isinstance(delta_stats, dict) else 0.0):+.4f}\n"
        f"- {ui_text('compare_report_max_gain_label', label_language, default='Max gain')}: {float(delta_stats.get('max_gain', 0.0) if isinstance(delta_stats, dict) else 0.0):+.4f}\n"
        f"- {ui_text('compare_report_max_drop_label', label_language, default='Max drop')}: {float(delta_stats.get('max_drop', 0.0) if isinstance(delta_stats, dict) else 0.0):+.4f}\n\n"
        f"## {ui_text('compare_report_top_changes_title', label_language, default='Top changed features')}\n\n"
        f"{top_change_table}\n"
    )
    with open(md_path, "w", encoding="utf-8") as handle:
        handle.write(markdown)
    return payload, json_path, md_path


def build_compare_popup_html(
    *,
    label_language: str,
    base_profile_key: str,
    compare_profile_key: str,
    base_stats: Dict[str, Any],
    compare_stats: Dict[str, Any],
    delta_stats: Dict[str, Any],
    top_changes: List[Dict[str, Any]],
    selected_change_count: int,
    zoom_applied: bool,
    change_layer_name: str,
    json_path: str,
    md_path: str,
    base_layer_name: str,
    compare_layer_name: str,
    reason_excerpt_limit: int = 88,
) -> str:
    delta_html = ""
    if isinstance(delta_stats, dict):
        delta_html = (
            f"<p><b>{escape(ui_text('profile_compare_delta_label', label_language, default='Mean score delta'))}</b>: {delta_stats.get('mean_delta', 0.0):+.4f}<br/>"
            f"<b>{escape(ui_text('profile_compare_max_gain_label', label_language, default='Max gain'))}</b>: {delta_stats.get('max_gain', 0.0):+.4f}<br/>"
            f"<b>{escape(ui_text('profile_compare_max_drop_label', label_language, default='Max drop'))}</b>: {delta_stats.get('max_drop', 0.0):+.4f}</p>"
        )

    top_change_html = ""
    if top_changes:
        header_cells = (
            f"<th>{escape(ui_text('profile_compare_feature_label', label_language, default='Feature'))}</th>"
            f"<th>{escape(ui_text('profile_compare_base_short_label', label_language, default='Base'))}</th>"
            f"<th>{escape(ui_text('profile_compare_calibrated_short_label', label_language, default='Calibrated'))}</th>"
            f"<th>{escape(ui_text('profile_compare_delta_short_label', label_language, default='Delta'))}</th>"
        )
        row_html = []
        base_reason_label = ui_text(
            "profile_compare_base_reason_label",
            label_language,
            default="Base",
        )
        compare_reason_label = ui_text(
            "profile_compare_calibrated_reason_label",
            label_language,
            default="Calibrated",
        )
        for row in top_changes:
            base_reason_text = _reason_excerpt(row.get("base_reason", ""), reason_excerpt_limit)
            compare_reason_text = _reason_excerpt(
                row.get("compare_reason", ""),
                reason_excerpt_limit,
            )
            reason_html = (
                f"<div style='font-size:11px;color:#5f5646;'>"
                f"{escape(base_reason_label)}: {escape(base_reason_text or '-')}<br/>"
                f"{escape(compare_reason_label)}: {escape(compare_reason_text or '-')}"
                f"</div>"
            )
            row_html.append(
                "<tr>"
                f"<td>{escape(str(row.get('label', '')))}{reason_html}</td>"
                f"<td>{float(row.get('base_score', 0.0)):.4f}</td>"
                f"<td>{float(row.get('compare_score', 0.0)):.4f}</td>"
                f"<td>{float(row.get('delta', 0.0)):+.4f}</td>"
                "</tr>"
            )
        selection_note = (
            "<p><b>"
            + escape(
                ui_text(
                    "profile_compare_auto_selected_template",
                    label_language,
                    default="Auto-selected: selected {count} top changed features on the map.",
                ).format(count=selected_change_count)
            )
            + "</b></p>"
            if selected_change_count > 0
            else ""
        )
        zoom_note = (
            "<p><b>"
            + escape(
                ui_text(
                    "profile_compare_auto_zoom_note",
                    label_language,
                    default="Auto-zoom: moved to the selected calibrated features.",
                )
            )
            + "</b></p>"
            if zoom_applied
            else ""
        )
        export_note = (
            f"<p><b>{escape(ui_text('profile_compare_change_layer_label', label_language, default='Change layer'))}</b>: {escape(change_layer_name)}</p>"
            if change_layer_name
            else ""
        )
        report_note = (
            f"<p><b>{escape(ui_text('profile_compare_json_label', label_language, default='Compare JSON'))}</b>: {escape(json_path or '')}<br/>"
            f"<b>{escape(ui_text('profile_compare_markdown_label', label_language, default='Compare Markdown'))}</b>: {escape(md_path or '')}</p>"
        )
        top_change_html = (
            f"<h4>{escape(ui_text('profile_compare_top_changes_title', label_language, default='Top changed features'))}</h4>"
            f"{selection_note}{zoom_note}{export_note}{report_note}"
            "<table border='1' cellspacing='0' cellpadding='4'>"
            f"<thead><tr>{header_cells}</tr></thead>"
            f"<tbody>{''.join(row_html)}</tbody></table>"
        )

    return (
        f"<h3>{escape(ui_text('profile_compare_heading_template', label_language, default='{base} vs {calibrated}').format(base=base_profile_key, calibrated=compare_profile_key))}</h3>"
        f"<p><b>{escape(ui_text('profile_compare_base_layer_label', label_language, default='Base layer'))}</b>: {escape(base_layer_name)}<br/>"
        f"<b>{escape(ui_text('profile_compare_calibrated_layer_label', label_language, default='Calibrated layer'))}</b>: {escape(compare_layer_name)}</p>"
        "<table border='1' cellspacing='0' cellpadding='4'>"
        f"<thead><tr><th>{escape(ui_text('profile_compare_profile_label', label_language, default='Profile'))}</th>"
        f"<th>{escape(ui_text('profile_compare_count_label', label_language, default='Count'))}</th>"
        f"<th>{escape(ui_text('profile_compare_mean_label', label_language, default='Mean'))}</th>"
        f"<th>{escape(ui_text('profile_compare_min_label', label_language, default='Min'))}</th>"
        f"<th>{escape(ui_text('profile_compare_max_label', label_language, default='Max'))}</th></tr></thead>"
        f"<tbody><tr><td>{escape(str(base_profile_key))}</td><td>{base_stats.get('count', 0)}</td>"
        f"<td>{base_stats.get('mean', 0.0):.4f}</td><td>{base_stats.get('min', 0.0):.4f}</td>"
        f"<td>{base_stats.get('max', 0.0):.4f}</td></tr>"
        f"<tr><td>{escape(str(compare_profile_key))}</td><td>{compare_stats.get('count', 0)}</td>"
        f"<td>{compare_stats.get('mean', 0.0):.4f}</td><td>{compare_stats.get('min', 0.0):.4f}</td>"
        f"<td>{compare_stats.get('max', 0.0):.4f}</td></tr></tbody></table>"
        f"{delta_html}{top_change_html}"
    )
