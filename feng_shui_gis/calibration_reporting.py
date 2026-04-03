# -*- coding: utf-8 -*-
"""Helpers for calibration popup/report presentation."""

from __future__ import annotations

import json
import os
from html import escape

from .reference_catalog import reference_display_text
from .ui_catalog import ui_text


def _markdown_table(headers, rows):
    safe_headers = [str(header).replace("|", "/") for header in headers]
    lines = [
        "| " + " | ".join(safe_headers) + " |",
        "| " + " | ".join(["---"] * len(safe_headers)) + " |",
    ]
    for row in rows:
        safe_row = [str(cell).replace("|", "/") for cell in row]
        lines.append("| " + " | ".join(safe_row) + " |")
    return "\n".join(lines)


def _html_table(headers, rows):
    head_cells = "".join(f"<th>{escape(str(header))}</th>" for header in headers)
    body_rows = []
    for row in rows:
        body_rows.append(
            "<tr>" + "".join(f"<td>{escape(str(cell))}</td>" for cell in row) + "</tr>"
        )
    return (
        "<table border='1' cellspacing='0' cellpadding='4'>"
        f"<thead><tr>{head_cells}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
    )


def _metric_rows(report, text_lang):
    return [
        (
            ui_text("calibration_metric_row_roc_auc", text_lang, default="ROC AUC"),
            report.get("base_roc_auc", 0.0),
            report.get("roc_auc", 0.0),
        ),
        (
            ui_text("calibration_metric_row_pr_auc", text_lang, default="PR AUC"),
            report.get("base_pr_auc", 0.0),
            report.get("pr_auc", 0.0),
        ),
        (
            ui_text("calibration_metric_row_best_f1", text_lang, default="Best F1"),
            report.get("base_best_f1", 0.0),
            report.get("best_f1", 0.0),
        ),
        (
            ui_text(
                "calibration_metric_row_best_youden_j",
                text_lang,
                default="Best Youden J",
            ),
            report.get("base_best_youden_j", 0.0),
            report.get("best_youden_j", 0.0),
        ),
    ]


def build_calibration_metric_comparison_markdown(report, text_lang):
    headers = [
        ui_text("calibration_metric_header_metric", text_lang, default="Metric"),
        ui_text("calibration_metric_header_base", text_lang, default="Base"),
        ui_text("calibration_metric_header_tuned", text_lang, default="Tuned"),
        ui_text("calibration_metric_header_delta", text_lang, default="Delta"),
    ]
    rows = []
    for label, base_value, tuned_value in _metric_rows(report, text_lang):
        delta = float(tuned_value or 0.0) - float(base_value or 0.0)
        rows.append(
            [
                label,
                f"{float(base_value or 0.0):.4f}",
                f"{float(tuned_value or 0.0):.4f}",
                f"{delta:+.4f}",
            ]
        )
    return _markdown_table(headers, rows)


def build_calibration_metric_comparison_html(report, text_lang):
    headers = [
        ui_text("calibration_metric_header_metric", text_lang, default="Metric"),
        ui_text("calibration_metric_header_base", text_lang, default="Base"),
        ui_text("calibration_metric_header_tuned", text_lang, default="Tuned"),
        ui_text("calibration_metric_header_delta", text_lang, default="Delta"),
    ]
    rows = []
    for label, base_value, tuned_value in _metric_rows(report, text_lang):
        delta = float(tuned_value or 0.0) - float(base_value or 0.0)
        rows.append(
            [
                label,
                f"{float(base_value or 0.0):.4f}",
                f"{float(tuned_value or 0.0):.4f}",
                f"{delta:+.4f}",
            ]
        )
    return _html_table(headers, rows)


def _metadata_kind_labels(text_lang):
    return {
        "site_group": ui_text(
            "calibration_metadata_kind_site_group",
            text_lang,
            default="Site group",
        ),
        "country": ui_text(
            "calibration_metadata_kind_country",
            text_lang,
            default="Country/region",
        ),
        "period": ui_text(
            "calibration_metadata_kind_period",
            text_lang,
            default="Period",
        ),
    }


def build_calibration_metadata_markdown(report, text_lang):
    summary = report.get("site_metadata_summary") or {}
    groupings = summary.get("groupings", [])
    layer_name = summary.get("layer_name") or report.get("site_layer_name") or "n/a"
    feature_count = int(report.get("positive_count", 0) or 0)
    layer_label = ui_text("calibration_metadata_layer_label", text_lang, default="Layer")
    positive_count_label = ui_text(
        "calibration_metadata_positive_count_label",
        text_lang,
        default="Positive sample count",
    )
    lines = [f"- {layer_label}: {layer_name}\n- {positive_count_label}: {feature_count}"]
    kind_labels = _metadata_kind_labels(text_lang)
    if not groupings:
        lines.append(
            ui_text(
                "calibration_metadata_no_groupings",
                text_lang,
                default="No attribute fields were detected for site-group/country/period comparison.",
            )
        )
        return "\n\n".join(lines)
    for grouping in groupings:
        title = kind_labels.get(grouping.get("kind"), grouping.get("kind"))
        field_name = grouping.get("field", "")
        headers = [
            ui_text("calibration_metadata_value_header", text_lang, default="Value"),
            ui_text("calibration_metadata_count_header", text_lang, default="Count"),
            ui_text("calibration_metadata_share_header", text_lang, default="Share"),
        ]
        rows = []
        for row in grouping.get("rows", []):
            rows.append(
                [
                    row.get("value", ""),
                    str(row.get("count", 0)),
                    f"{float(row.get('share', 0.0)) * 100.0:.1f}%",
                ]
            )
        lines.append(f"### {title} (`{field_name}`)\n\n{_markdown_table(headers, rows)}")
    return "\n\n".join(lines)


def build_calibration_metadata_html(report, text_lang):
    summary = report.get("site_metadata_summary") or {}
    groupings = summary.get("groupings", [])
    layer_name = summary.get("layer_name") or report.get("site_layer_name") or "n/a"
    feature_count = int(report.get("positive_count", 0) or 0)
    layer_label = ui_text("calibration_metadata_layer_label", text_lang, default="Layer")
    positive_count_label = ui_text(
        "calibration_metadata_positive_count_label",
        text_lang,
        default="Positive sample count",
    )
    parts = [
        (
            f"<p><b>{escape(layer_label)}</b>: {escape(str(layer_name))}"
            f"<br/><b>{escape(positive_count_label)}</b>: {feature_count}</p>"
        )
    ]
    kind_labels = _metadata_kind_labels(text_lang)
    if not groupings:
        parts.append(
            f"<p>{escape(ui_text('calibration_metadata_no_groupings', text_lang, default='No attribute fields were detected for site-group/country/period comparison.'))}</p>"
        )
        return "".join(parts)
    for grouping in groupings:
        title = kind_labels.get(grouping.get("kind"), grouping.get("kind"))
        field_name = grouping.get("field", "")
        headers = [
            ui_text("calibration_metadata_value_header", text_lang, default="Value"),
            ui_text("calibration_metadata_count_header", text_lang, default="Count"),
            ui_text("calibration_metadata_share_header", text_lang, default="Share"),
        ]
        rows = []
        for row in grouping.get("rows", []):
            rows.append(
                [
                    row.get("value", ""),
                    str(row.get("count", 0)),
                    f"{float(row.get('share', 0.0)) * 100.0:.1f}%",
                ]
            )
        parts.append(f"<p><b>{escape(str(title))}</b> ({escape(str(field_name))})</p>")
        parts.append(_html_table(headers, rows))
    return "".join(parts)


def collect_calibration_history(report_dir, limit=40):
    if not report_dir or not os.path.isdir(report_dir):
        return []
    records = []
    for filename in sorted(os.listdir(report_dir), reverse=True):
        if not filename.startswith("feng_shui_calibration_") or not filename.endswith(".json"):
            continue
        path = os.path.join(report_dir, filename)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                record = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(record, dict):
            continue
        record["report_file"] = filename
        record["report_path"] = path
        records.append(record)
        if len(records) >= max(1, int(limit)):
            break
    return records


def _history_context_key(record):
    return (
        str(record.get("culture_key") or ""),
        str(record.get("period_key") or ""),
        str(record.get("profile_key") or ""),
    )


def _history_summary_rows(history_records):
    grouped = {}
    for record in history_records:
        key = _history_context_key(record)
        bucket = grouped.setdefault(
            key,
            {
                "runs": 0,
                "roc_auc_total": 0.0,
                "pr_auc_total": 0.0,
                "best_roc_auc": 0.0,
                "latest_layer": "",
                "latest_file": "",
            },
        )
        bucket["runs"] += 1
        bucket["roc_auc_total"] += float(record.get("roc_auc", 0.0) or 0.0)
        bucket["pr_auc_total"] += float(record.get("pr_auc", 0.0) or 0.0)
        bucket["best_roc_auc"] = max(
            bucket["best_roc_auc"],
            float(record.get("roc_auc", 0.0) or 0.0),
        )
        latest_file = str(record.get("report_file") or "")
        if latest_file >= bucket["latest_file"]:
            bucket["latest_file"] = latest_file
            bucket["latest_layer"] = str(record.get("site_layer_name") or "")

    rows = []
    for key, bucket in sorted(
        grouped.items(),
        key=lambda item: (-item[1]["runs"], -item[1]["roc_auc_total"], item[0]),
    ):
        culture_key, period_key, profile_key = key
        runs = max(1, int(bucket["runs"]))
        rows.append(
            [
                culture_key or "-",
                period_key or "-",
                profile_key or "-",
                str(runs),
                f"{bucket['roc_auc_total'] / runs:.4f}",
                f"{bucket['pr_auc_total'] / runs:.4f}",
                f"{bucket['best_roc_auc']:.4f}",
                bucket.get("latest_layer") or "-",
            ]
        )
    return rows[:10]


def _history_recent_rows(history_records):
    rows = []
    for record in history_records[:8]:
        rows.append(
            [
                str(record.get("report_file") or "").replace(".json", ""),
                str(record.get("culture_key") or "-"),
                str(record.get("period_key") or "-"),
                str(record.get("profile_key") or "-"),
                str(record.get("site_layer_name") or "-"),
                f"{float(record.get('roc_auc', 0.0) or 0.0):.4f}",
                f"{float(record.get('pr_auc', 0.0) or 0.0):.4f}",
            ]
        )
    return rows


def _record_site_group_rows(record):
    summary = record.get("site_metadata_summary") or {}
    if not isinstance(summary, dict):
        return []
    groupings = summary.get("groupings") or []
    if not isinstance(groupings, list):
        return []
    for grouping in groupings:
        if not isinstance(grouping, dict):
            continue
        if grouping.get("kind") == "site_group":
            rows = grouping.get("rows") or []
            return rows if isinstance(rows, list) else []
    return []


def _site_group_history_rows(history_records):
    buckets = {}
    for record in history_records:
        report_file = str(record.get("report_file") or "")
        roc_auc = float(record.get("roc_auc", 0.0) or 0.0)
        pr_auc = float(record.get("pr_auc", 0.0) or 0.0)
        culture_key = str(record.get("culture_key") or "-")
        period_key = str(record.get("period_key") or "-")
        profile_key = str(record.get("profile_key") or "-")
        for row in _record_site_group_rows(record):
            value = str(row.get("value") or "(empty)")
            bucket = buckets.setdefault(
                value,
                {
                    "runs": 0,
                    "share_total": 0.0,
                    "roc_total": 0.0,
                    "pr_total": 0.0,
                    "latest_file": "",
                    "latest_context": "",
                },
            )
            bucket["runs"] += 1
            bucket["share_total"] += float(row.get("share", 0.0) or 0.0)
            bucket["roc_total"] += roc_auc
            bucket["pr_total"] += pr_auc
            if report_file >= bucket["latest_file"]:
                bucket["latest_file"] = report_file
                bucket["latest_context"] = f"{culture_key}/{period_key}/{profile_key}"

    rows = []
    for value, bucket in sorted(
        buckets.items(),
        key=lambda item: (-item[1]["runs"], -item[1]["share_total"], item[0]),
    ):
        runs = max(1, int(bucket["runs"]))
        rows.append(
            [
                value,
                str(runs),
                f"{(bucket['share_total'] / runs) * 100.0:.1f}%",
                f"{bucket['roc_total'] / runs:.4f}",
                f"{bucket['pr_total'] / runs:.4f}",
                bucket.get("latest_context") or "-",
            ]
        )
    return rows[:10]


def build_calibration_history_markdown(history_records, text_lang):
    if not history_records:
        return ui_text(
            "calibration_history_no_records",
            text_lang,
            default="No prior calibration history was found.",
        )
    summary_headers = [
        ui_text("calibration_history_summary_header_culture", text_lang, default="Culture"),
        ui_text("calibration_history_summary_header_period", text_lang, default="Period"),
        ui_text("calibration_history_summary_header_profile", text_lang, default="Profile"),
        ui_text("calibration_history_summary_header_runs", text_lang, default="Runs"),
        ui_text("calibration_history_summary_header_avg_roc", text_lang, default="Avg ROC"),
        ui_text("calibration_history_summary_header_avg_pr", text_lang, default="Avg PR"),
        ui_text("calibration_history_summary_header_best_roc", text_lang, default="Best ROC"),
        ui_text("calibration_history_summary_header_latest_layer", text_lang, default="Latest layer"),
    ]
    recent_headers = [
        ui_text("calibration_history_recent_header_run_file", text_lang, default="Run file"),
        ui_text("calibration_history_recent_header_culture", text_lang, default="Culture"),
        ui_text("calibration_history_recent_header_period", text_lang, default="Period"),
        ui_text("calibration_history_recent_header_profile", text_lang, default="Profile"),
        ui_text("calibration_history_recent_header_layer", text_lang, default="Layer"),
        ui_text("calibration_history_recent_header_roc", text_lang, default="ROC"),
        ui_text("calibration_history_recent_header_pr", text_lang, default="PR"),
    ]
    site_group_headers = [
        ui_text("calibration_history_site_group_header_name", text_lang, default="Site group"),
        ui_text("calibration_history_site_group_header_runs", text_lang, default="Runs"),
        ui_text("calibration_history_site_group_header_avg_share", text_lang, default="Avg share"),
        ui_text("calibration_history_site_group_header_avg_roc", text_lang, default="Avg ROC"),
        ui_text("calibration_history_site_group_header_avg_pr", text_lang, default="Avg PR"),
        ui_text(
            "calibration_history_site_group_header_latest_context",
            text_lang,
            default="Latest context",
        ),
    ]
    summary_title = ui_text(
        "calibration_history_summary_title",
        text_lang,
        default="Context summary",
    )
    site_group_title = ui_text(
        "calibration_history_site_group_title",
        text_lang,
        default="Site-group summary",
    )
    recent_title = ui_text(
        "calibration_history_recent_title",
        text_lang,
        default="Recent runs",
    )
    site_group_rows = _site_group_history_rows(history_records)
    site_group_block = (
        _markdown_table(site_group_headers, site_group_rows)
        if site_group_rows
        else ui_text(
            "calibration_history_no_site_groups",
            text_lang,
            default="No calibration history with site-group fields was found yet.",
        )
    )
    return (
        f"### {summary_title}\n\n"
        f"{_markdown_table(summary_headers, _history_summary_rows(history_records))}\n\n"
        f"### {site_group_title}\n\n"
        f"{site_group_block}\n\n"
        f"### {recent_title}\n\n"
        f"{_markdown_table(recent_headers, _history_recent_rows(history_records))}"
    )


def build_calibration_history_html(history_records, text_lang):
    if not history_records:
        return (
            f"<p>{escape(ui_text('calibration_history_no_records', text_lang, default='No prior calibration history was found.'))}</p>"
        )
    summary_headers = [
        ui_text("calibration_history_summary_header_culture", text_lang, default="Culture"),
        ui_text("calibration_history_summary_header_period", text_lang, default="Period"),
        ui_text("calibration_history_summary_header_profile", text_lang, default="Profile"),
        ui_text("calibration_history_summary_header_runs", text_lang, default="Runs"),
        ui_text("calibration_history_summary_header_avg_roc", text_lang, default="Avg ROC"),
        ui_text("calibration_history_summary_header_avg_pr", text_lang, default="Avg PR"),
        ui_text("calibration_history_summary_header_best_roc", text_lang, default="Best ROC"),
        ui_text("calibration_history_summary_header_latest_layer", text_lang, default="Latest layer"),
    ]
    recent_headers = [
        ui_text("calibration_history_recent_header_run_file", text_lang, default="Run file"),
        ui_text("calibration_history_recent_header_culture", text_lang, default="Culture"),
        ui_text("calibration_history_recent_header_period", text_lang, default="Period"),
        ui_text("calibration_history_recent_header_profile", text_lang, default="Profile"),
        ui_text("calibration_history_recent_header_layer", text_lang, default="Layer"),
        ui_text("calibration_history_recent_header_roc", text_lang, default="ROC"),
        ui_text("calibration_history_recent_header_pr", text_lang, default="PR"),
    ]
    site_group_headers = [
        ui_text("calibration_history_site_group_header_name", text_lang, default="Site group"),
        ui_text("calibration_history_site_group_header_runs", text_lang, default="Runs"),
        ui_text("calibration_history_site_group_header_avg_share", text_lang, default="Avg share"),
        ui_text("calibration_history_site_group_header_avg_roc", text_lang, default="Avg ROC"),
        ui_text("calibration_history_site_group_header_avg_pr", text_lang, default="Avg PR"),
        ui_text(
            "calibration_history_site_group_header_latest_context",
            text_lang,
            default="Latest context",
        ),
    ]
    summary_title = ui_text(
        "calibration_history_summary_title",
        text_lang,
        default="Context summary",
    )
    site_group_title = ui_text(
        "calibration_history_site_group_title",
        text_lang,
        default="Site-group summary",
    )
    recent_title = ui_text(
        "calibration_history_recent_title",
        text_lang,
        default="Recent runs",
    )
    site_group_rows = _site_group_history_rows(history_records)
    site_group_block = (
        _html_table(site_group_headers, site_group_rows)
        if site_group_rows
        else (
            f"<p>{escape(ui_text('calibration_history_no_site_groups', text_lang, default='No calibration history with site-group fields was found yet.'))}</p>"
        )
    )
    return (
        f"<p><b>{escape(summary_title)}</b></p>"
        f"{_html_table(summary_headers, _history_summary_rows(history_records))}"
        f"<p><b>{escape(site_group_title)}</b></p>"
        f"{site_group_block}"
        f"<p><b>{escape(recent_title)}</b></p>"
        f"{_html_table(recent_headers, _history_recent_rows(history_records))}"
    )


def _paper_evidence_sources(paper_evidence_records):
    if not isinstance(paper_evidence_records, list):
        return []
    sources = []
    seen = set()
    for record in paper_evidence_records:
        if not isinstance(record, dict):
            continue
        for source in record.get("source_doi", []):
            source_text = str(source or "").strip()
            if not source_text or source_text in seen:
                continue
            seen.add(source_text)
            sources.append(source_text)
            if len(sources) >= 12:
                break
        if len(sources) >= 12:
            break
    return sources


def build_calibration_markdown(report, stamp, text_lang, history_records):
    paper_evidence_summary = str(report.get("paper_evidence_summary", "") or "").strip()
    paper_evidence_references = reference_display_text(
        _paper_evidence_sources(report.get("paper_evidence_records")),
        language=text_lang,
        limit=10,
    ).strip()
    md_title = ui_text(
        "calibration_md_title_template",
        text_lang,
        default="Feng Shui Calibration Report ({stamp})",
    ).format(stamp=stamp)
    md_positive = ui_text("calibration_md_positive_label", text_lang, default="Positive samples")
    md_negative = ui_text("calibration_md_negative_label", text_lang, default="Negative samples")
    md_valid = ui_text("calibration_md_valid_label", text_lang, default="Valid scored samples")
    md_roc_auc = ui_text("calibration_md_roc_auc_label", text_lang, default="ROC AUC")
    md_pr_auc = ui_text("calibration_md_pr_auc_label", text_lang, default="PR AUC")
    md_best_f1 = ui_text("calibration_md_best_f1_label", text_lang, default="Best F1")
    md_best_youden = ui_text(
        "calibration_md_best_youden_label",
        text_lang,
        default="Best Youden J",
    )
    md_threshold = ui_text("calibration_md_threshold_label", text_lang, default="threshold")
    md_context_title = ui_text("calibration_md_context_title", text_lang, default="Context")
    md_culture = ui_text("calibration_md_context_culture_label", text_lang, default="culture")
    md_period = ui_text("calibration_md_context_period_label", text_lang, default="period")
    md_profile = ui_text("calibration_md_context_profile_label", text_lang, default="profile")
    md_hemisphere = ui_text(
        "calibration_md_context_hemisphere_label",
        text_lang,
        default="hemisphere",
    )
    md_negative_ratio = ui_text(
        "calibration_md_context_negative_ratio_label",
        text_lang,
        default="negative_ratio",
    )
    md_random_seed = ui_text(
        "calibration_md_context_random_seed_label",
        text_lang,
        default="random_seed",
    )
    md_scope = ui_text(
        "calibration_md_scope_label",
        text_lang,
        default="calibration_scope",
    )
    md_weight_summary = ui_text(
        "calibration_md_weight_summary_label",
        text_lang,
        default="weight_update",
    )
    md_parameter_summary = ui_text(
        "calibration_md_parameter_summary_label",
        text_lang,
        default="parameter_update",
    )
    md_base_roc_auc = ui_text(
        "calibration_md_base_roc_auc_label",
        text_lang,
        default="Base ROC AUC",
    )
    md_base_pr_auc = ui_text(
        "calibration_md_base_pr_auc_label",
        text_lang,
        default="Base PR AUC",
    )
    md_export_title = ui_text(
        "calibration_md_export_title",
        text_lang,
        default="Calibrated profile export",
    )
    md_export_key = ui_text(
        "calibration_md_export_key_label",
        text_lang,
        default="profile_key",
    )
    md_export_snapshot = ui_text(
        "calibration_md_export_snapshot_label",
        text_lang,
        default="snapshot_path",
    )
    md_export_registry = ui_text(
        "calibration_md_export_registry_label",
        text_lang,
        default="local_profile_registry",
    )
    md_export_status = ui_text(
        "calibration_md_export_status_label",
        text_lang,
        default="export_status",
    )
    md_metric_compare_title = ui_text(
        "calibration_md_metric_compare_title",
        text_lang,
        default="Metric comparison",
    )
    md_validation_label = ui_text(
        "calibration_md_validation_mode_label",
        text_lang,
        default="Validation mode",
    )
    md_validation_reason_label = ui_text(
        "calibration_md_validation_reason_label",
        text_lang,
        default="Validation reason",
    )
    md_metadata_title = ui_text(
        "calibration_md_metadata_title",
        text_lang,
        default="Site group / country / period mix",
    )
    md_history_title = ui_text(
        "calibration_md_history_title",
        text_lang,
        default="Calibration history comparison",
    )
    md_paper_title = ui_text(
        "calibration_md_paper_evidence_title",
        text_lang,
        default="Paper evidence",
    )
    md_paper_summary_label = ui_text(
        "calibration_md_paper_evidence_summary_label",
        text_lang,
        default="Paper evidence summary",
    )
    md_paper_references_label = ui_text(
        "calibration_md_paper_evidence_references_label",
        text_lang,
        default="Paper references",
    )
    md_paper_evidence_missing = ui_text(
        "calibration_md_paper_evidence_missing",
        text_lang,
        default="No profile-level paper evidence was applied.",
    )

    return (
        f"# {md_title}\n\n"
        f"- {md_positive}: {report.get('positive_count')}\n"
        f"- {md_negative}: {report.get('negative_count')}\n"
        f"- {md_valid}: {report.get('valid_count')}\n"
        f"- {md_roc_auc}: {report.get('roc_auc', 0):.6f}\n"
        f"- {md_validation_label}: {'enabled' if report.get('calibration_validation_enabled') else 'disabled'} "
        f"({report.get('calibration_split_mode', 'in_sample_single_pool')})\n"
        f"- {md_validation_reason_label}: {report.get('calibration_split_reason', '')}\n"
        f"- {md_pr_auc}: {report.get('pr_auc', 0):.6f}\n"
        f"- {md_best_f1}: {report.get('best_f1', 0):.6f} @ {md_threshold} {report.get('best_f1_threshold', 0):.6f}\n"
        f"- {md_best_youden}: {report.get('best_youden_j', 0):.6f} @ {md_threshold} {report.get('best_youden_threshold', 0):.6f}\n\n"
        f"## {md_context_title}\n\n"
        f"- {md_culture}: {report.get('culture_key')}\n"
        f"- {md_period}: {report.get('period_key')}\n"
        f"- {md_profile}: {report.get('profile_key')}\n"
        f"- {md_hemisphere}: {report.get('hemisphere')}\n"
        f"- {md_negative_ratio}: {report.get('negative_ratio')}\n"
        f"- {md_random_seed}: {report.get('random_seed')}\n"
        f"- {md_scope}: {report.get('calibration_scope', 'threshold_only')}\n"
        f"- {md_weight_summary}: {report.get('tuned_weight_summary', 'n/a')}\n"
        f"- {md_parameter_summary}: {report.get('tuned_parameter_summary', 'n/a')}\n"
        f"- {md_base_roc_auc}: {report.get('base_roc_auc', 0):.6f}\n"
        f"- {md_base_pr_auc}: {report.get('base_pr_auc', 0):.6f}\n"
        f"\n## {md_export_title}\n\n"
        f"- {md_export_status}: {report.get('profile_export_status', 'n/a')}\n"
        f"- {md_export_key}: {report.get('exported_profile_key', 'n/a')}\n"
        f"- {md_export_snapshot}: {report.get('profile_export_path', 'n/a')}\n"
        f"- {md_export_registry}: {report.get('local_profile_registry_path', 'n/a')}\n"
        f"\n## {md_metric_compare_title}\n\n"
        f"{build_calibration_metric_comparison_markdown(report, text_lang)}\n"
        f"\n## {md_metadata_title}\n\n"
        f"{build_calibration_metadata_markdown(report, text_lang)}\n"
        f"\n## {md_history_title}\n\n"
        f"{build_calibration_history_markdown(history_records, text_lang)}\n"
        f"\n## {md_paper_title}\n\n"
        f"- {md_paper_summary_label}: {paper_evidence_summary or md_paper_evidence_missing}\n"
        f"- {md_paper_references_label}: "
        f"{paper_evidence_references or md_paper_evidence_missing}\n"
    )


def write_calibration_report_files(*, report, report_dir, stamp, text_lang):
    base_name = f"feng_shui_calibration_{stamp}"
    json_path = os.path.join(report_dir, f"{base_name}.json")
    md_path = os.path.join(report_dir, f"{base_name}.md")
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    history_records = collect_calibration_history(report_dir)
    markdown = build_calibration_markdown(report, stamp, text_lang, history_records)
    with open(md_path, "w", encoding="utf-8") as handle:
        handle.write(markdown)
    return {
        "json_path": json_path,
        "md_path": md_path,
        "history_records": history_records,
    }


def build_calibration_popup_sections(*, report, report_dir, text_lang):
    history_records = collect_calibration_history(report_dir)
    return {
        "metric_compare_html": build_calibration_metric_comparison_html(report, text_lang),
        "metadata_html": build_calibration_metadata_html(report, text_lang),
        "history_html": build_calibration_history_html(history_records, text_lang),
    }


def build_calibration_popup_html(
    *,
    report,
    json_path,
    md_path,
    text_lang,
    metric_compare_html,
    metadata_html,
    history_html,
):
    roc_auc_label = ui_text("calibration_html_roc_auc_label", text_lang, default="ROC AUC")
    pr_auc_label = ui_text("calibration_html_pr_auc_label", text_lang, default="PR AUC")
    positive_label = ui_text("calibration_html_positive_label", text_lang, default="Positive")
    negative_label = ui_text("calibration_html_negative_label", text_lang, default="Negative")
    valid_label = ui_text("calibration_html_valid_label", text_lang, default="Valid")
    best_f1_label = ui_text("calibration_html_best_f1_label", text_lang, default="Best F1")
    best_youden_label = ui_text(
        "calibration_html_best_youden_label",
        text_lang,
        default="Best Youden J",
    )
    threshold_label = ui_text(
        "calibration_html_threshold_label",
        text_lang,
        default="threshold",
    )
    scope_label = ui_text(
        "calibration_html_scope_label",
        text_lang,
        default="Calibration scope",
    )
    weight_summary_label = ui_text(
        "calibration_html_weight_summary_label",
        text_lang,
        default="Weight update",
    )
    parameter_summary_label = ui_text(
        "calibration_html_parameter_summary_label",
        text_lang,
        default="Parameter update",
    )
    export_title = ui_text(
        "calibration_html_export_title",
        text_lang,
        default="Calibrated profile export",
    )
    export_status_label = ui_text(
        "calibration_html_export_status_label",
        text_lang,
        default="Export status",
    )
    export_key_label = ui_text(
        "calibration_html_export_key_label",
        text_lang,
        default="Profile key",
    )
    export_snapshot_label = ui_text(
        "calibration_html_export_snapshot_label",
        text_lang,
        default="Snapshot path",
    )
    export_registry_label = ui_text(
        "calibration_html_export_registry_label",
        text_lang,
        default="Local profile registry",
    )
    metric_compare_title = ui_text(
        "calibration_html_metric_compare_title",
        text_lang,
        default="Metric comparison",
    )
    metadata_title = ui_text(
        "calibration_html_metadata_title",
        text_lang,
        default="Site group / country / period mix",
    )
    history_title = ui_text(
        "calibration_html_history_title",
        text_lang,
        default="Calibration history comparison",
    )
    base_roc_auc_label = ui_text(
        "calibration_html_base_roc_auc_label",
        text_lang,
        default="Base ROC AUC",
    )
    base_pr_auc_label = ui_text(
        "calibration_html_base_pr_auc_label",
        text_lang,
        default="Base PR AUC",
    )
    json_label = ui_text("calibration_html_json_label", text_lang, default="JSON")
    markdown_label = ui_text(
        "calibration_html_markdown_label",
        text_lang,
        default="Markdown",
    )
    paper_title = ui_text(
        "calibration_html_paper_evidence_title",
        text_lang,
        default="Paper evidence",
    )
    paper_summary_label = ui_text(
        "calibration_html_paper_evidence_summary_label",
        text_lang,
        default="Paper evidence summary",
    )
    paper_references_label = ui_text(
        "calibration_html_paper_evidence_references_label",
        text_lang,
        default="Paper references",
    )
    paper_missing = ui_text(
        "calibration_html_paper_evidence_missing",
        text_lang,
        default="No profile-level paper evidence was applied.",
    )
    paper_summary = str(report.get("paper_evidence_summary", "") or "").strip()
    paper_references = reference_display_text(
        [
            source
            for item in (report.get("paper_evidence_records") or [])
            if isinstance(item, dict)
            for source in item.get("source_doi", [])
            if source
        ],
        language=text_lang,
        limit=10,
    ).strip()
    paper_summary_text = escape(paper_summary or paper_missing)
    paper_references_text = escape(paper_references or paper_missing)

    return (
        f"<h3>{ui_text('calibration_report_heading', text_lang, default='Calibration Result')}</h3>"
        f"<p><b>{roc_auc_label}</b>: {report.get('roc_auc', 0):.4f}<br/>"
        f"<b>{pr_auc_label}</b>: {report.get('pr_auc', 0):.4f}<br/>"
        f"<b>{positive_label}</b>: {report.get('positive_count')} / "
        f"<b>{negative_label}</b>: {report.get('negative_count')} / "
        f"<b>{valid_label}</b>: {report.get('valid_count')}</p>"
        f"<p><b>{best_f1_label}</b>: {report.get('best_f1', 0):.4f} "
        f"({threshold_label}={report.get('best_f1_threshold', 0):.4f})<br/>"
        f"<b>{best_youden_label}</b>: {report.get('best_youden_j', 0):.4f} "
        f"({threshold_label}={report.get('best_youden_threshold', 0):.4f})<br/>"
        f"<b>{scope_label}</b>: {escape(str(report.get('calibration_scope', 'threshold_only')))}<br/>"
        f"<b>{weight_summary_label}</b>: {escape(str(report.get('tuned_weight_summary', 'n/a')))}<br/>"
        f"<b>{parameter_summary_label}</b>: {escape(str(report.get('tuned_parameter_summary', 'n/a')))}<br/>"
        f"<b>{base_roc_auc_label}</b>: {report.get('base_roc_auc', 0):.4f}<br/>"
        f"<b>{base_pr_auc_label}</b>: {report.get('base_pr_auc', 0):.4f}</p>"
        f"<p><b>{export_title}</b><br/>"
        f"{export_status_label}: {escape(str(report.get('profile_export_status', 'n/a')))}<br/>"
        f"{export_key_label}: {escape(str(report.get('exported_profile_key', 'n/a')))}<br/>"
        f"{export_snapshot_label}: {escape(str(report.get('profile_export_path', 'n/a')))}<br/>"
        f"{export_registry_label}: {escape(str(report.get('local_profile_registry_path', 'n/a')))}</p>"
        f"<h4>{metric_compare_title}</h4>"
        f"{metric_compare_html}"
        f"<h4>{metadata_title}</h4>"
        f"{metadata_html}"
        f"<h4>{history_title}</h4>"
        f"{history_html}"
        f"<p><b>{paper_title}</b><br/>"
        f"{paper_summary_label}: {paper_summary_text}<br/>"
        f"{paper_references_label}: {paper_references_text}</p>"
        f"<p><b>{json_label}</b>: {json_path}<br/><b>{markdown_label}</b>: {md_path}</p>"
    )
