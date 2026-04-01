# -*- coding: utf-8 -*-
"""Pure helpers for calibration report rendering."""

from html import escape

from ..ui_catalog import ui_text


class CalibrationReportWriter:
    @staticmethod
    def metric_bundle(report, bundle_key, fallback_prefix=""):
        bundle = report.get(bundle_key) or {}
        if isinstance(bundle, dict) and bundle:
            return bundle
        return {
            "count": int(
                report.get(f"{fallback_prefix}valid_count", report.get("valid_count", 0))
                or 0
            ),
            "roc_auc": float(report.get(f"{fallback_prefix}roc_auc", 0.0) or 0.0),
            "pr_auc": float(report.get(f"{fallback_prefix}pr_auc", 0.0) or 0.0),
            "best_f1": float(report.get(f"{fallback_prefix}best_f1", 0.0) or 0.0),
            "best_f1_threshold": float(
                report.get(f"{fallback_prefix}best_f1_threshold", 0.0) or 0.0
            ),
            "best_youden_j": float(
                report.get(f"{fallback_prefix}best_youden_j", 0.0) or 0.0
            ),
            "best_youden_threshold": float(
                report.get(f"{fallback_prefix}best_youden_threshold", 0.0) or 0.0
            ),
        }

    @classmethod
    def reported_metrics(cls, report):
        return cls.metric_bundle(report, "reported_metrics")

    @classmethod
    def reported_baseline_metrics(cls, report):
        return cls.metric_bundle(
            report,
            "reported_baseline_metrics",
            fallback_prefix="base_",
        )

    @staticmethod
    def goal_text(text_lang):
        return ui_text(
            "calibration_goal_local_tuning",
            text_lang,
            default=(
                "Local tuning of profile weights and parameters for exploratory calibration; "
                "not a standalone validation claim."
            ),
        )

    @staticmethod
    def section_titles(text_lang):
        return {
            "interpretation": ui_text(
                "report_section_interpretation_title",
                text_lang,
                default="Interpretation",
            ),
            "analytical": ui_text(
                "report_section_analytical_title",
                text_lang,
                default="Analytical",
            ),
            "audit": ui_text(
                "report_section_audit_title",
                text_lang,
                default="Audit",
            ),
        }

    @staticmethod
    def phase_parts(report, text_lang):
        phase = str(
            report.get("reported_metric_phase")
            or (report.get("calibration_split") or {}).get("reported_metric_phase")
            or "no_held_out_evaluation"
        ).strip()
        phase_key_map = {
            "held_out_evaluation": "calibration_phase_held_out_evaluation",
            "no_held_out_evaluation": "calibration_phase_no_holdout_evaluation",
            "validation_reused_for_selection": "calibration_phase_validation_reused",
            "evaluation_reused_for_selection": "calibration_phase_evaluation_reused",
            "in_sample_tuning_diagnostic": "calibration_phase_in_sample_diagnostic",
        }
        phase_default_map = {
            "held_out_evaluation": "Held-out evaluation",
            "no_held_out_evaluation": "No held-out evaluation available",
            "validation_reused_for_selection": "Validation reused for model selection",
            "evaluation_reused_for_selection": "Evaluation rows reused for model selection",
            "in_sample_tuning_diagnostic": "In-sample tuning diagnostic",
        }
        notice_default_map = {
            "held_out_evaluation": (
                "Reported metrics are from held-out rows that were not used to choose the tuned candidate."
            ),
            "no_held_out_evaluation": (
                "No held-out evaluation rows were available, so this run exposes tuning diagnostics but no reportable evaluation metrics."
            ),
            "validation_reused_for_selection": (
                "Reported metrics reuse the same validation rows used to choose the tuned candidate."
            ),
            "evaluation_reused_for_selection": (
                "Reported metrics reuse evaluation rows that also influenced tuned-candidate selection."
            ),
            "in_sample_tuning_diagnostic": (
                "Reported metrics are in-sample diagnostics and should not be interpreted as held-out performance."
            ),
        }
        phase_key = phase_key_map.get(phase, "")
        phase_label = ui_text(
            phase_key,
            text_lang,
            default=phase_default_map.get(phase, phase.replace("_", " ")),
        )
        phase_notice = str(report.get("reported_metric_notice") or "").strip() or ui_text(
            f"{phase_key_map.get(phase, 'calibration_phase_in_sample_diagnostic')}_note",
            text_lang,
            default=notice_default_map.get(
                phase,
                notice_default_map["in_sample_tuning_diagnostic"],
            ),
        )
        return phase, phase_label, phase_notice

    @staticmethod
    def _split_audit_lines(report, text_lang):
        split = report.get("calibration_split") or {}
        if not isinstance(split, dict) or not split:
            return []
        split_fields = (
            ("deterministic_split", "calibration_md_split_deterministic_label", "deterministic_split"),
            ("fit_count", "calibration_md_split_fit_count_label", "fit_count"),
            ("selection_count", "calibration_md_split_selection_count_label", "selection_count"),
            ("report_count", "calibration_md_split_report_count_label", "report_count"),
            ("fit_role", "calibration_md_split_fit_role_label", "fit_role"),
            ("selection_role", "calibration_md_split_selection_role_label", "selection_role"),
            ("report_role", "calibration_md_split_report_role_label", "report_role"),
        )
        lines = []
        for key, label_key, default_label in split_fields:
            value = split.get(key)
            if value in (None, ""):
                continue
            lines.append(
                "- {label}: {value}".format(
                    label=ui_text(label_key, text_lang, default=default_label),
                    value=value,
                )
            )
        return lines

    @staticmethod
    def _manifest_audit_lines(report, text_lang):
        manifest = report.get("run_manifest") or {}
        if not isinstance(manifest, dict):
            manifest = {}
        lines = []
        audit_fields = (
            (
                manifest.get("request_signature"),
                "calibration_md_request_signature_label",
                "request_signature",
            ),
            (
                report.get("report_signature") or manifest.get("report_signature"),
                "calibration_md_report_signature_label",
                "report_signature",
            ),
            (
                manifest.get("seed"),
                "calibration_md_manifest_seed_label",
                "manifest_seed",
            ),
            (
                manifest.get("qgis_version"),
                "calibration_md_qgis_version_label",
                "qgis_version",
            ),
        )
        for value, label_key, default_label in audit_fields:
            if value in (None, ""):
                continue
            lines.append(
                "- {label}: {value}".format(
                    label=ui_text(label_key, text_lang, default=default_label),
                    value=value,
                )
            )
        return lines

    @classmethod
    def build_markdown(
        cls,
        *,
        report,
        stamp,
        text_lang,
        metric_compare_markdown,
        metadata_markdown,
        history_markdown,
        paper_evidence_summary,
        paper_evidence_references,
    ):
        reported_metrics = cls.reported_metrics(report)
        reported_baseline_metrics = cls.reported_baseline_metrics(report)
        goal_text = cls.goal_text(text_lang)
        _phase_code, phase_label, phase_notice = cls.phase_parts(report, text_lang)
        section_titles = cls.section_titles(text_lang)

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
        md_goal = ui_text("calibration_md_goal_label", text_lang, default="goal")
        md_report_phase = ui_text(
            "calibration_md_report_phase_label",
            text_lang,
            default="reported_metric_phase",
        )
        md_report_note = ui_text(
            "calibration_md_report_note_label",
            text_lang,
            default="reported_metric_note",
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

        interpretation_lines = [
            f"- {md_goal}: {goal_text}",
            f"- {md_report_phase}: {phase_label}",
            f"- {md_report_note}: {phase_notice}",
            f"- {md_scope}: {report.get('calibration_scope', 'threshold_only')}",
        ]
        analytical_lines = [
            f"- {md_positive}: {report.get('positive_count')}",
            f"- {md_negative}: {report.get('negative_count')}",
            f"- {md_valid}: {reported_metrics.get('count', 0)}",
            f"- {md_roc_auc}: {reported_metrics.get('roc_auc', 0):.6f}",
            f"- {md_pr_auc}: {reported_metrics.get('pr_auc', 0):.6f}",
            (
                f"- {md_best_f1}: {reported_metrics.get('best_f1', 0):.6f} @ "
                f"{md_threshold} {reported_metrics.get('best_f1_threshold', 0):.6f}"
            ),
            (
                f"- {md_best_youden}: {reported_metrics.get('best_youden_j', 0):.6f} @ "
                f"{md_threshold} {reported_metrics.get('best_youden_threshold', 0):.6f}"
            ),
            f"- {md_base_roc_auc}: {reported_baseline_metrics.get('roc_auc', 0):.6f}",
            f"- {md_base_pr_auc}: {reported_baseline_metrics.get('pr_auc', 0):.6f}",
            f"- {md_weight_summary}: {report.get('tuned_weight_summary', 'n/a')}",
            f"- {md_parameter_summary}: {report.get('tuned_parameter_summary', 'n/a')}",
        ]
        audit_lines = [
            f"- {md_culture}: {report.get('culture_key')}",
            f"- {md_period}: {report.get('period_key')}",
            f"- {md_profile}: {report.get('profile_key')}",
            f"- {md_hemisphere}: {report.get('hemisphere')}",
            f"- {md_negative_ratio}: {report.get('negative_ratio')}",
            f"- {md_random_seed}: {report.get('random_seed')}",
            f"- {md_export_status}: {report.get('profile_export_status', 'n/a')}",
            f"- {md_export_key}: {report.get('exported_profile_key', 'n/a')}",
            f"- {md_export_snapshot}: {report.get('profile_export_path', 'n/a')}",
            f"- {md_export_registry}: {report.get('local_profile_registry_path', 'n/a')}",
        ]
        audit_lines.extend(cls._split_audit_lines(report, text_lang))
        audit_lines.extend(cls._manifest_audit_lines(report, text_lang))
        audit_lines.append(
            f"- {md_paper_summary_label}: {paper_evidence_summary or md_paper_evidence_missing}"
        )
        audit_lines.append(
            f"- {md_paper_references_label}: "
            f"{paper_evidence_references or md_paper_evidence_missing}"
        )

        return (
            f"# {md_title}\n\n"
            f"## {section_titles['interpretation']}\n\n"
            f"{chr(10).join(interpretation_lines)}\n\n"
            f"## {section_titles['analytical']}\n\n"
            f"{chr(10).join(analytical_lines)}\n\n"
            f"### {md_metric_compare_title}\n\n"
            f"{metric_compare_markdown}\n\n"
            f"### {md_metadata_title}\n\n"
            f"{metadata_markdown}\n\n"
            f"### {md_history_title}\n\n"
            f"{history_markdown}\n\n"
            f"## {section_titles['audit']}\n\n"
            f"{chr(10).join(audit_lines)}\n\n"
            f"### {md_paper_title}\n\n"
            f"- {md_paper_summary_label}: {paper_evidence_summary or md_paper_evidence_missing}\n"
            f"- {md_paper_references_label}: "
            f"{paper_evidence_references or md_paper_evidence_missing}\n"
        )

    @classmethod
    def build_popup_html(
        cls,
        *,
        report,
        text_lang,
        json_path,
        md_path,
        metric_compare_html,
        metadata_html,
        history_html,
        paper_evidence_summary,
        paper_evidence_references,
    ):
        reported_metrics = cls.reported_metrics(report)
        reported_baseline_metrics = cls.reported_baseline_metrics(report)
        goal_text = cls.goal_text(text_lang)
        _phase_code, phase_text, phase_notice = cls.phase_parts(report, text_lang)
        section_titles = cls.section_titles(text_lang)

        heading = ui_text(
            "calibration_report_heading",
            text_lang,
            default="Calibration Result",
        )
        roc_auc_label = ui_text("calibration_html_roc_auc_label", text_lang, default="ROC AUC")
        pr_auc_label = ui_text("calibration_html_pr_auc_label", text_lang, default="PR AUC")
        positive_label = ui_text(
            "calibration_html_positive_label",
            text_lang,
            default="Positive samples",
        )
        negative_label = ui_text(
            "calibration_html_negative_label",
            text_lang,
            default="Negative samples",
        )
        valid_label = ui_text(
            "calibration_html_valid_label",
            text_lang,
            default="Valid scored samples",
        )
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
        goal_label = ui_text("calibration_html_goal_label", text_lang, default="Goal")
        report_phase_label = ui_text(
            "calibration_html_report_phase_label",
            text_lang,
            default="Reported metric phase",
        )
        report_note_label = ui_text(
            "calibration_html_report_note_label",
            text_lang,
            default="Reported metric note",
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
        context_title = ui_text(
            "calibration_html_context_title",
            text_lang,
            default="Context",
        )
        culture_label = ui_text(
            "calibration_html_context_culture_label",
            text_lang,
            default="culture",
        )
        period_label = ui_text(
            "calibration_html_context_period_label",
            text_lang,
            default="period",
        )
        profile_label = ui_text(
            "calibration_html_context_profile_label",
            text_lang,
            default="profile",
        )
        hemisphere_label = ui_text(
            "calibration_html_context_hemisphere_label",
            text_lang,
            default="hemisphere",
        )
        negative_ratio_label = ui_text(
            "calibration_html_context_negative_ratio_label",
            text_lang,
            default="negative_ratio",
        )
        random_seed_label = ui_text(
            "calibration_html_context_random_seed_label",
            text_lang,
            default="random_seed",
        )
        export_title = ui_text(
            "calibration_html_export_title",
            text_lang,
            default="Calibrated profile export",
        )
        export_key_label = ui_text(
            "calibration_html_export_key_label",
            text_lang,
            default="profile_key",
        )
        export_snapshot_label = ui_text(
            "calibration_html_export_snapshot_label",
            text_lang,
            default="snapshot_path",
        )
        export_registry_label = ui_text(
            "calibration_html_export_registry_label",
            text_lang,
            default="local_profile_registry",
        )
        export_status_label = ui_text(
            "calibration_html_export_status_label",
            text_lang,
            default="export_status",
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
        split_title = ui_text(
            "calibration_html_split_title",
            text_lang,
            default="Split contract",
        )
        audit_title = ui_text(
            "calibration_html_audit_meta_title",
            text_lang,
            default="Audit metadata",
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

        split_lines = []
        for line in cls._split_audit_lines(report, text_lang):
            if ": " not in line:
                continue
            label, value = line[2:].split(": ", 1)
            split_lines.append(f"{escape(label)}: {escape(value)}")
        split_html = (
            f"<p><b>{escape(split_title)}</b><br/>{'<br/>'.join(split_lines)}</p>"
            if split_lines
            else ""
        )

        audit_lines = []
        for line in cls._manifest_audit_lines(report, text_lang):
            if ": " not in line:
                continue
            label, value = line[2:].split(": ", 1)
            audit_lines.append(f"{escape(label)}: {escape(value)}")
        audit_meta_html = (
            f"<p><b>{escape(audit_title)}</b><br/>{'<br/>'.join(audit_lines)}</p>"
            if audit_lines
            else ""
        )

        paper_summary_text = escape(paper_evidence_summary or paper_missing)
        paper_references_text = escape(paper_evidence_references or paper_missing)

        return (
            f"<h3>{escape(heading)}</h3>"
            f"<h4>{escape(section_titles['interpretation'])}</h4>"
            f"<p><b>{escape(goal_label)}</b>: {escape(goal_text)}<br/>"
            f"<b>{escape(report_phase_label)}</b>: {escape(phase_text)}<br/>"
            f"<b>{escape(report_note_label)}</b>: {escape(phase_notice)}<br/>"
            f"<b>{escape(scope_label)}</b>: {escape(str(report.get('calibration_scope', 'threshold_only')))}</p>"
            f"<h4>{escape(section_titles['analytical'])}</h4>"
            f"<p><b>{escape(roc_auc_label)}</b>: {reported_metrics.get('roc_auc', 0):.4f}<br/>"
            f"<b>{escape(pr_auc_label)}</b>: {reported_metrics.get('pr_auc', 0):.4f}<br/>"
            f"<b>{escape(positive_label)}</b>: {report.get('positive_count')} / "
            f"<b>{escape(negative_label)}</b>: {report.get('negative_count')} / "
            f"<b>{escape(valid_label)}</b>: {reported_metrics.get('count', 0)}<br/>"
            f"<b>{escape(best_f1_label)}</b>: {reported_metrics.get('best_f1', 0):.4f} "
            f"({escape(threshold_label)}={reported_metrics.get('best_f1_threshold', 0):.4f})<br/>"
            f"<b>{escape(best_youden_label)}</b>: {reported_metrics.get('best_youden_j', 0):.4f} "
            f"({escape(threshold_label)}={reported_metrics.get('best_youden_threshold', 0):.4f})<br/>"
            f"<b>{escape(base_roc_auc_label)}</b>: {reported_baseline_metrics.get('roc_auc', 0):.4f}<br/>"
            f"<b>{escape(base_pr_auc_label)}</b>: {reported_baseline_metrics.get('pr_auc', 0):.4f}<br/>"
            f"<b>{escape(weight_summary_label)}</b>: {escape(str(report.get('tuned_weight_summary', 'n/a')))}<br/>"
            f"<b>{escape(parameter_summary_label)}</b>: {escape(str(report.get('tuned_parameter_summary', 'n/a')))}</p>"
            f"<h5>{escape(metric_compare_title)}</h5>"
            f"{metric_compare_html}"
            f"<h5>{escape(metadata_title)}</h5>"
            f"{metadata_html}"
            f"<h5>{escape(history_title)}</h5>"
            f"{history_html}"
            f"<h4>{escape(section_titles['audit'])}</h4>"
            f"<p><b>{escape(context_title)}</b><br/>"
            f"{escape(culture_label)}: {escape(str(report.get('culture_key')))}<br/>"
            f"{escape(period_label)}: {escape(str(report.get('period_key')))}<br/>"
            f"{escape(profile_label)}: {escape(str(report.get('profile_key')))}<br/>"
            f"{escape(hemisphere_label)}: {escape(str(report.get('hemisphere')))}<br/>"
            f"{escape(negative_ratio_label)}: {escape(str(report.get('negative_ratio')))}<br/>"
            f"{escape(random_seed_label)}: {escape(str(report.get('random_seed')))}</p>"
            f"{split_html}"
            f"{audit_meta_html}"
            f"<p><b>{escape(export_title)}</b><br/>"
            f"{escape(export_status_label)}: {escape(str(report.get('profile_export_status', 'n/a')))}<br/>"
            f"{escape(export_key_label)}: {escape(str(report.get('exported_profile_key', 'n/a')))}<br/>"
            f"{escape(export_snapshot_label)}: {escape(str(report.get('profile_export_path', 'n/a')))}<br/>"
            f"{escape(export_registry_label)}: {escape(str(report.get('local_profile_registry_path', 'n/a')))}</p>"
            f"<p><b>{escape(paper_title)}</b><br/>"
            f"{escape(paper_summary_label)}: {paper_summary_text}<br/>"
            f"{escape(paper_references_label)}: {paper_references_text}</p>"
            f"<p><b>{escape(json_label)}</b>: {escape(json_path)}<br/>"
            f"<b>{escape(markdown_label)}</b>: {escape(md_path)}</p>"
        )
