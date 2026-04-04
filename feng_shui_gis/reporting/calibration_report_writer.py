"""Adapter layer for calibration report rendering.

The historical implementation in :mod:`feng_shui_gis.calibration_reporting` is a
collection of helper functions. Tests and runtime workflows import the
``CalibrationReportWriter`` class from a reporting namespace. This module keeps that
contract stable and adapts payloads into a consistent interpretation/analytical/audit
shape.
"""

from __future__ import annotations

from typing import Any, Dict, List


class CalibrationReportWriter:
    """Build calibration report payload / markdown / html content."""

    @staticmethod
    def _normalize_metrics(report: Dict[str, Any]) -> Dict[str, float]:
        metrics = report.get("reported_metrics") or {}
        return {
            "roc_auc": float(
                _coalesce(report.get("roc_auc"), metrics.get("roc_auc"), 0.0)
            ),
            "pr_auc": float(_coalesce(report.get("pr_auc"), metrics.get("pr_auc"), 0.0)),
            "best_f1": float(_coalesce(report.get("best_f1"), metrics.get("best_f1"), 0.0)),
            "best_f1_threshold": float(
                _coalesce(
                    report.get("best_f1_threshold"),
                    metrics.get("best_f1_threshold"),
                    0.0,
                )
            ),
            "best_youden_j": float(
                _coalesce(
                    report.get("best_youden_j"),
                    metrics.get("best_youden_j"),
                    0.0,
                )
            ),
            "best_youden_threshold": float(
                _coalesce(
                    report.get("best_youden_threshold"),
                    metrics.get("best_youden_threshold"),
                    0.0,
                )
            ),
        }

    @staticmethod
    def _normalize_payload(report: Dict[str, Any]) -> Dict[str, Any]:
        base_metrics = report.get("reported_baseline_metrics") or {}
        return {
            "timestamp": _coalesce(report.get("timestamp"), "not_available"),
            "report": report,
            "reported_metric_phase": str(report.get("reported_metric_phase", "")),
            "reported_metrics": report.get("reported_metrics") or _default_metrics(),
            "reported_baseline_metrics": report.get("reported_baseline_metrics")
            or {
                "count": 0,
                "roc_auc": float(base_metrics.get("roc_auc", 0.0)),
                "pr_auc": float(base_metrics.get("pr_auc", 0.0)),
                "best_f1": float(base_metrics.get("best_f1", 0.0)),
                "best_f1_threshold": float(base_metrics.get("best_f1_threshold", 0.0)),
                "best_youden_j": float(base_metrics.get("best_youden_j", 0.0)),
                "best_youden_threshold": float(base_metrics.get("best_youden_threshold", 0.0)),
            },
            "calibration_split": report.get("calibration_split") or {},
            "calibration_scope": str(report.get("calibration_scope", "")),
            "metric": CalibrationReportWriter._normalize_metrics(report),
            "tuned_weight_summary": str(report.get("tuned_weight_summary", "n/a")),
            "tuned_parameter_summary": str(report.get("tuned_parameter_summary", "n/a")),
        }

    @staticmethod
    def build_markdown(
        report: Dict[str, Any],
        stamp: str,
        text_lang: str,
        metric_compare_markdown: str = "",
        metadata_markdown: str = "",
        history_markdown: str = "",
        paper_evidence_summary: str = "",
        paper_evidence_references: str = "",
        trust_metadata: Dict[str, Any] | None = None,
        **_: Any,
    ) -> str:
        del text_lang  # kept for API compatibility with earlier callers.
        payload = CalibrationReportWriter._normalize_payload(report)
        phase = str(payload.get("reported_metric_phase", "")).replace("_", " ")
        if phase:
            phase = phase[:1].upper() + phase[1:]

        metric_compare = metric_compare_markdown.strip() or "No metric comparison block was provided."
        metadata_section = metadata_markdown.strip() or "No metadata section was provided."
        history_section = history_markdown.strip() or "No calibration history was provided."
        summary = [
            f"# Feng Shui Calibration Report ({stamp})",
            "",
            "## Interpretation",
            f"- phase: {phase or 'in-sample diagnostic'}",
            "- fs_score is a relative terrain suitability signal, not a probability.",
            "- local tuning and calibration are exploratory diagnostics for this profile.",
            (
                f"- {payload['calibration_scope']}"
                if payload["calibration_scope"]
                else "- Local tuning of profile weights and parameters"
            ),
        ]
        if "Local tuning of profile weights and parameters" not in summary:
            summary.append("- Local tuning of profile weights and parameters")
        if payload["reported_metric_phase"] == "held_out_evaluation":
            summary.append("- Held-out evaluation performed and separated from fit.")

        metrics = payload["metric"]
        metric_rows = [
            f"  - ROC AUC: {metrics['roc_auc']:.4f}",
            f"  - PR AUC: {metrics['pr_auc']:.4f}",
            f"  - Best F1: {metrics['best_f1']:.4f} @ {metrics['best_f1_threshold']:.3f}",
            f"  - Best Youden J: {metrics['best_youden_j']:.4f} @ {metrics['best_youden_threshold']:.3f}",
        ]
        split = payload["calibration_split"] or {}
        split_count = len(split) if isinstance(split, dict) else 0
        interpretation_lines = [
            "",
            "## Analytical",
            "### Metric comparison",
            metric_compare,
            "### Split contract",
            f"- split contract rows: {split_count}",
        ]
        interpretation_lines.extend(metric_rows)
        if payload["reported_metric_phase"] != "held_out_evaluation":
            interpretation_lines.append(
                "- Calibration split was not strictly held-out for this run."
            )

        trust_lines = [
            "",
            "### Trust metadata",
            f"- score notice: {str((trust_metadata or {}).get('score_notice', 'n/a'))}",
            f"- calibration notice: {str((trust_metadata or {}).get('calibration_notice', 'n/a'))}",
            f"- audit summary: {str((trust_metadata or {}).get('result_badges', []))}",
        ]

        analysis_lines = [
            "",
            "### Metadata",
            metadata_section,
            "### History",
            history_section,
            "",
            "### Paper evidence",
            f"- summary: {paper_evidence_summary or 'n/a'}",
            f"- references: {paper_evidence_references or 'n/a'}",
            "",
            "## Audit",
            f"- tuned weights: {payload['tuned_weight_summary']}",
            f"- tuned parameters: {payload['tuned_parameter_summary']}",
            f"- report file exports: {report.get('profile_export_path', 'n/a')}",
        ]
        return "\n".join(summary + interpretation_lines + trust_lines + analysis_lines)

    @staticmethod
    def build_popup_html(
        report: Dict[str, Any],
        text_lang: str,
        json_path: str,
        md_path: str,
        metric_compare_html: str = "",
        metadata_html: str = "",
        history_html: str = "",
        paper_evidence_summary: str = "",
        paper_evidence_references: str = "",
        trust_metadata: Dict[str, Any] | None = None,
        **_: Any,
    ) -> str:
        del text_lang
        payload = CalibrationReportWriter._normalize_payload(report)
        metrics = payload["metric"]
        split = payload["calibration_split"] or {}
        if isinstance(split, dict) and split:
            split_rows = "<br/>".join(
                [f"{key}: {value}" for key, value in split.items()]
            )
        else:
            split_rows = "No split contract details available."

        return (
            "<h3>Interpretation</h3>"
            "<p>Calibration result is a constrained diagnostic, not a predictive claim.</p>"
            f"<p>Phase: {payload['reported_metric_phase'] or 'in_sample_single_pool'}</p>"
            "<h4>Analytical</h4>"
            "<p><b>ROC AUC</b>: {:.4f}<br/>"
            "<b>PR AUC</b>: {:.4f}<br/>"
            "<b>Best F1</b>: {:.4f}<br/>"
            "<b>Best Youden J</b>: {:.4f}</p>"
            "<p><b>Local tuning</b>: {} / {}</p>"
            "<p><b>Metric comparison</b>: {}</p>"
            "<p><b>Metadata</b>: {}</p>"
            "<p><b>History</b>: {}</p>"
            "<h4>Audit</h4>"
            "<p><b>Split contract</b>: {}</p>"
            "<p><b>Report JSON</b>: {}</p>"
            "<p><b>Report Markdown</b>: {}</p>"
            "<p><b>Paper evidence</b>: {} / {}</p>"
            "</div>"
        ).format(
            metrics["roc_auc"],
            metrics["pr_auc"],
            metrics["best_f1"],
            metrics["best_youden_j"],
            payload["tuned_weight_summary"],
            payload["tuned_parameter_summary"],
            _html_escape(metric_compare_html),
            _html_escape(metadata_html),
            _html_escape(history_html),
            _html_escape(split_rows),
            _html_escape(json_path),
            _html_escape(md_path),
            _html_escape(paper_evidence_summary or "n/a"),
            _html_escape(paper_evidence_references or "n/a"),
        )

    @staticmethod
    def payload(*, report: Dict[str, Any], trust_metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        normalized = CalibrationReportWriter._normalize_payload(report)
        split = normalized["calibration_split"] or {}
        return {
            "report": dict(report),
            "interpretation": {
                "phase": normalized["reported_metric_phase"],
                "scope": normalized["calibration_scope"],
                "notice": str((trust_metadata or {}).get("calibration_notice", "")),
            },
            "analytical": {
                "metric": normalized["metric"],
                "baseline_metrics": normalized["reported_baseline_metrics"],
                "tuning": {
                    "tuned_weight_summary": normalized["tuned_weight_summary"],
                    "tuned_parameter_summary": normalized["tuned_parameter_summary"],
                },
            },
            "audit": {
                "split": split,
                "split_contract_rows": [
                    (key, value) for key, value in (split.items() if isinstance(split, dict) else [])
                ],
                "trust_metadata": trust_metadata or {},
                "result_badges": (trust_metadata or {}).get("result_badges", []),
            },
        }


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _default_metrics() -> Dict[str, float]:
    return {
        "count": 0,
        "roc_auc": 0.0,
        "pr_auc": 0.0,
        "best_f1": 0.0,
        "best_f1_threshold": 0.0,
        "best_youden_j": 0.0,
        "best_youden_threshold": 0.0,
    }


def _html_escape(text: Any) -> str:
    return str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
