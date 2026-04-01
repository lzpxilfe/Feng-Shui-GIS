# -*- coding: utf-8 -*-
"""Pure helpers for compare report rendering."""

from html import escape

from ..trust_metadata import badges_html, badges_markdown, build_trust_metadata, section_titles
from ..ui_catalog import ui_text


class CompareReportWriter:
    @staticmethod
    def _reason_excerpt(text, limit):
        clean = str(text or "").strip().replace("\n", " ")
        if len(clean) <= max(1, int(limit)):
            return clean
        return clean[: max(1, int(limit)) - 1].rstrip() + "..."

    @staticmethod
    def interpretation_payload(
        *,
        site_layer_name,
        base_profile_key,
        compare_profile_key,
        change_layer_name,
        top_changes,
        trust_metadata,
    ):
        return {
            "claim_scope": "comparative_score_reading_only",
            "reading_note": str((trust_metadata or {}).get("compare_notice") or ""),
            "site_layer_name": site_layer_name,
            "base_profile_key": base_profile_key,
            "compare_profile_key": compare_profile_key,
            "change_layer_name": change_layer_name,
            "top_change_count": len(list(top_changes or [])),
        }

    @staticmethod
    def analytical_payload(*, base_stats, compare_stats, delta_stats, top_changes):
        return {
            "base_stats": dict(base_stats or {}),
            "compare_stats": dict(compare_stats or {}),
            "delta_stats": dict(delta_stats or {}),
            "top_changes": list(top_changes or []),
        }

    @staticmethod
    def audit_payload(
        *,
        stamp,
        site_layer_name,
        base_profile_key,
        compare_profile_key,
        change_layer_name,
        reason_excerpt_limit,
        top_changes,
    ):
        return {
            "timestamp": stamp,
            "site_layer_name": site_layer_name,
            "base_profile_key": base_profile_key,
            "compare_profile_key": compare_profile_key,
            "change_layer_name": change_layer_name,
            "reason_excerpt_limit": int(reason_excerpt_limit),
            "top_change_count": len(list(top_changes or [])),
            "top_change_feature_uids": [
                row.get("feature_uid")
                for row in list(top_changes or [])
                if row.get("feature_uid")
            ],
        }

    @classmethod
    def payload(
        cls,
        *,
        stamp,
        site_layer_name,
        base_profile_key,
        compare_profile_key,
        base_stats,
        compare_stats,
        delta_stats,
        top_changes,
        change_layer_name,
        reason_excerpt_limit=88,
        trust_metadata=None,
    ):
        top_changes = list(top_changes or [])
        trust_metadata = trust_metadata or build_trust_metadata(
            "en",
            advanced_context_enabled=False,
            culture_key="",
            profile_key=compare_profile_key,
        )
        return {
            "timestamp": stamp,
            "site_layer_name": site_layer_name,
            "base_profile_key": base_profile_key,
            "compare_profile_key": compare_profile_key,
            "base_stats": dict(base_stats or {}),
            "compare_stats": dict(compare_stats or {}),
            "delta_stats": dict(delta_stats or {}),
            "top_changes": top_changes,
            "change_layer_name": change_layer_name,
            "trust_metadata": dict(trust_metadata or {}),
            "interpretation": cls.interpretation_payload(
                site_layer_name=site_layer_name,
                base_profile_key=base_profile_key,
                compare_profile_key=compare_profile_key,
                change_layer_name=change_layer_name,
                top_changes=top_changes,
                trust_metadata=trust_metadata,
            ),
            "analytical": cls.analytical_payload(
                base_stats=base_stats,
                compare_stats=compare_stats,
                delta_stats=delta_stats,
                top_changes=top_changes,
            ),
            "audit": cls.audit_payload(
                stamp=stamp,
                site_layer_name=site_layer_name,
                base_profile_key=base_profile_key,
                compare_profile_key=compare_profile_key,
                change_layer_name=change_layer_name,
                reason_excerpt_limit=reason_excerpt_limit,
                top_changes=top_changes,
            ),
        }

    @staticmethod
    def _markdown_table(headers, rows):
        if not headers:
            return ""
        header_row = "| " + " | ".join(str(item) for item in headers) + " |"
        divider_row = "| " + " | ".join("---" for _ in headers) + " |"
        body_rows = ["| " + " | ".join(str(item) for item in row) + " |" for row in rows]
        return "\n".join([header_row, divider_row] + body_rows)

    @classmethod
    def build_markdown(
        cls,
        *,
        stamp,
        text_lang,
        site_layer_name,
        base_profile_key,
        compare_profile_key,
        base_stats,
        compare_stats,
        delta_stats,
        top_changes,
        change_layer_name,
        reason_excerpt_limit,
        trust_metadata=None,
    ):
        trust_metadata = trust_metadata or build_trust_metadata(
            text_lang,
            advanced_context_enabled=False,
            culture_key="",
            profile_key=compare_profile_key,
        )
        titles = section_titles(text_lang)
        interpretation = cls.interpretation_payload(
            site_layer_name=site_layer_name,
            base_profile_key=base_profile_key,
            compare_profile_key=compare_profile_key,
            change_layer_name=change_layer_name,
            top_changes=top_changes,
            trust_metadata=trust_metadata,
        )
        audit = cls.audit_payload(
            stamp=stamp,
            site_layer_name=site_layer_name,
            base_profile_key=base_profile_key,
            compare_profile_key=compare_profile_key,
            change_layer_name=change_layer_name,
            reason_excerpt_limit=reason_excerpt_limit,
            top_changes=top_changes,
        )

        top_change_rows = []
        for row in top_changes or []:
            reason_compare = ui_text(
                "compare_report_reason_compare_template",
                text_lang,
                default="Base: {base} / Calibrated: {calibrated}",
            ).format(
                base=cls._reason_excerpt(
                    row.get("base_reason", ""),
                    reason_excerpt_limit,
                ),
                calibrated=cls._reason_excerpt(
                    row.get("compare_reason", ""),
                    reason_excerpt_limit,
                ),
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
            top_change_table = cls._markdown_table(
                [
                    ui_text("compare_report_feature_label", text_lang, default="Feature"),
                    ui_text("compare_report_base_label", text_lang, default="Base"),
                    ui_text(
                        "compare_report_calibrated_label",
                        text_lang,
                        default="Calibrated",
                    ),
                    ui_text("compare_report_delta_label", text_lang, default="Delta"),
                    ui_text(
                        "compare_report_reason_compare_label",
                        text_lang,
                        default="Reason compare",
                    ),
                ],
                top_change_rows,
            )
        else:
            top_change_table = ui_text(
                "compare_report_no_top_changes",
                text_lang,
                default="No top-changed features were recorded.",
            )

        interpretation_note = str((trust_metadata or {}).get("compare_notice") or interpretation["reading_note"])
        top_change_count_label = ui_text(
            "compare_report_top_change_count_label",
            text_lang,
            default="Top changed features",
        )
        reading_note_label = ui_text(
            "compare_report_reading_note_label",
            text_lang,
            default="Reading note",
        )
        audit_reason_limit_label = ui_text(
            "compare_report_reason_excerpt_limit_label",
            text_lang,
            default="Reason excerpt limit",
        )
        audit_timestamp_label = ui_text(
            "compare_report_timestamp_label",
            text_lang,
            default="Timestamp",
        )
        audit_top_change_uids_label = ui_text(
            "compare_report_top_change_uids_label",
            text_lang,
            default="Top change feature_uids",
        )
        badges_label = ui_text("trust_badge_label", text_lang, default="Trust badges")
        score_notice_label = ui_text(
            "trust_score_notice_label",
            text_lang,
            default="Score notice",
        )

        top_change_uid_text = ", ".join(audit.get("top_change_feature_uids", [])) or "n/a"

        return (
            f"# {ui_text('compare_report_title_template', text_lang, default='Feng Shui Comparison Report ({stamp})').format(stamp=stamp)}\n\n"
            f"## {titles['interpretation']}\n\n"
            f"- {ui_text('compare_report_site_layer_label', text_lang, default='Site layer')}: {site_layer_name}\n"
            f"- {ui_text('compare_report_base_profile_label', text_lang, default='Base profile')}: {base_profile_key}\n"
            f"- {ui_text('compare_report_calibrated_profile_label', text_lang, default='Calibrated profile')}: {compare_profile_key}\n"
            f"- {ui_text('compare_report_change_layer_label', text_lang, default='Change layer')}: {change_layer_name or 'n/a'}\n"
            f"- {top_change_count_label}: {interpretation.get('top_change_count', 0)}\n"
            f"- {badges_label}: {badges_markdown(trust_metadata)}\n"
            f"- {score_notice_label}: {str((trust_metadata or {}).get('score_notice') or '')}\n"
            f"- {reading_note_label}: {interpretation_note}\n\n"
            f"## {titles['analytical']}\n\n"
            f"### {ui_text('compare_report_summary_title', text_lang, default='Summary statistics')}\n\n"
            f"- {ui_text('compare_report_base_mean_label', text_lang, default='Base mean')}: {float(base_stats.get('mean', 0.0) if isinstance(base_stats, dict) else 0.0):.4f}\n"
            f"- {ui_text('compare_report_calibrated_mean_label', text_lang, default='Calibrated mean')}: {float(compare_stats.get('mean', 0.0) if isinstance(compare_stats, dict) else 0.0):.4f}\n"
            f"- {ui_text('compare_report_mean_delta_label', text_lang, default='Mean score delta')}: {float(delta_stats.get('mean_delta', 0.0) if isinstance(delta_stats, dict) else 0.0):+.4f}\n"
            f"- {ui_text('compare_report_max_gain_label', text_lang, default='Max gain')}: {float(delta_stats.get('max_gain', 0.0) if isinstance(delta_stats, dict) else 0.0):+.4f}\n"
            f"- {ui_text('compare_report_max_drop_label', text_lang, default='Max drop')}: {float(delta_stats.get('max_drop', 0.0) if isinstance(delta_stats, dict) else 0.0):+.4f}\n\n"
            f"### {ui_text('compare_report_top_changes_title', text_lang, default='Top changed features')}\n\n"
            f"{top_change_table}\n\n"
            f"## {titles['audit']}\n\n"
            f"- {audit_timestamp_label}: {stamp}\n"
            f"- {audit_reason_limit_label}: {audit.get('reason_excerpt_limit', reason_excerpt_limit)}\n"
            f"- {top_change_count_label}: {audit.get('top_change_count', 0)}\n"
            f"- {audit_top_change_uids_label}: {top_change_uid_text}\n"
        )

    @classmethod
    def build_popup_html(
        cls,
        *,
        text_lang,
        base_profile_key,
        compare_profile_key,
        base_stats,
        compare_stats,
        delta_stats,
        top_changes,
        selected_change_count,
        zoom_applied,
        change_layer_name,
        json_path,
        md_path,
        base_layer_name,
        compare_layer_name,
        reason_excerpt_limit,
        trust_metadata=None,
    ):
        trust_metadata = trust_metadata or build_trust_metadata(
            text_lang,
            advanced_context_enabled=False,
            culture_key="",
            profile_key=compare_profile_key,
        )
        titles = section_titles(text_lang)
        reading_note = str((trust_metadata or {}).get("compare_notice") or "")
        top_change_count_label = ui_text(
            "compare_report_top_change_count_label",
            text_lang,
            default="Top changed features",
        )

        delta_html = ""
        if isinstance(delta_stats, dict):
            delta_label = ui_text(
                "profile_compare_delta_label",
                text_lang,
                default="Mean score delta",
            )
            gain_label = ui_text(
                "profile_compare_max_gain_label",
                text_lang,
                default="Max gain",
            )
            drop_label = ui_text(
                "profile_compare_max_drop_label",
                text_lang,
                default="Max drop",
            )
            delta_html = (
                f"<p><b>{escape(delta_label)}</b>: {delta_stats.get('mean_delta', 0.0):+.4f}<br/>"
                f"<b>{escape(gain_label)}</b>: {delta_stats.get('max_gain', 0.0):+.4f}<br/>"
                f"<b>{escape(drop_label)}</b>: {delta_stats.get('max_drop', 0.0):+.4f}</p>"
            )
        top_change_html = ""
        if top_changes:
            header_cells = (
                f"<th>{escape(ui_text('profile_compare_feature_label', text_lang, default='Feature'))}</th>"
                f"<th>{escape(ui_text('profile_compare_base_short_label', text_lang, default='Base'))}</th>"
                f"<th>{escape(ui_text('profile_compare_calibrated_short_label', text_lang, default='Calibrated'))}</th>"
                f"<th>{escape(ui_text('profile_compare_delta_short_label', text_lang, default='Delta'))}</th>"
            )
            row_html = []
            base_reason_label = ui_text(
                "profile_compare_base_reason_label",
                text_lang,
                default="Base",
            )
            compare_reason_label = ui_text(
                "profile_compare_calibrated_reason_label",
                text_lang,
                default="Calibrated",
            )
            for row in top_changes:
                base_reason_text = cls._reason_excerpt(
                    row.get("base_reason", ""),
                    reason_excerpt_limit,
                )
                compare_reason_text = cls._reason_excerpt(
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
            title = ui_text(
                "profile_compare_top_changes_title",
                text_lang,
                default="Top changed features",
            )
            top_change_html = (
                f"<h5>{escape(title)}</h5>"
                "<table border='1' cellspacing='0' cellpadding='4'>"
                f"<thead><tr>{header_cells}</tr></thead>"
                f"<tbody>{''.join(row_html)}</tbody>"
                "</table>"
            )

        selection_note = (
            (
                "<p><b>"
                + escape(
                    ui_text(
                        "profile_compare_auto_selected_template",
                        text_lang,
                        default="Auto-selected: selected {count} top changed features on the map.",
                    ).format(count=selected_change_count)
                )
                + "</b></p>"
            )
            if selected_change_count > 0
            else ""
        )
        zoom_note = (
            (
                "<p><b>"
                + escape(
                    ui_text(
                        "profile_compare_auto_zoom_note",
                        text_lang,
                        default="Auto-zoom: moved to the selected calibrated features.",
                    )
                )
                + "</b></p>"
            )
            if zoom_applied
            else ""
        )
        export_note = (
            (
                f"<p><b>{escape(ui_text('profile_compare_change_layer_label', text_lang, default='Change layer'))}</b>: "
                f"{escape(change_layer_name)}</p>"
            )
            if change_layer_name
            else ""
        )

        return (
            f"<h3>{escape(ui_text('profile_compare_heading_template', text_lang, default='{base} vs {calibrated}').format(base=base_profile_key, calibrated=compare_profile_key))}</h3>"
            f"<h4>{escape(titles['interpretation'])}</h4>"
            f"{badges_html(trust_metadata)}"
            f"<p><b>{escape(ui_text('profile_compare_base_layer_label', text_lang, default='Base layer'))}</b>: {escape(base_layer_name)}<br/>"
            f"<b>{escape(ui_text('profile_compare_calibrated_layer_label', text_lang, default='Calibrated layer'))}</b>: {escape(compare_layer_name)}<br/>"
            f"<b>{escape(top_change_count_label)}</b>: {len(list(top_changes or []))}<br/>"
            f"<b>{escape(ui_text('trust_badge_label', text_lang, default='Trust badges'))}</b>: {escape(badges_markdown(trust_metadata))}<br/>"
            f"<b>{escape(ui_text('trust_score_notice_label', text_lang, default='Score notice'))}</b>: {escape(str((trust_metadata or {}).get('score_notice') or ''))}<br/>"
            f"<b>{escape(ui_text('compare_report_reading_note_label', text_lang, default='Reading note'))}</b>: {escape(reading_note)}</p>"
            f"{selection_note}"
            f"{zoom_note}"
            f"{export_note}"
            f"<h4>{escape(titles['analytical'])}</h4>"
            f"<table border='1' cellspacing='0' cellpadding='4'>"
            f"<thead><tr>"
            f"<th>{escape(ui_text('profile_compare_profile_label', text_lang, default='Profile'))}</th>"
            f"<th>{escape(ui_text('profile_compare_count_label', text_lang, default='Count'))}</th>"
            f"<th>{escape(ui_text('profile_compare_mean_label', text_lang, default='Mean'))}</th>"
            f"<th>{escape(ui_text('profile_compare_min_label', text_lang, default='Min'))}</th>"
            f"<th>{escape(ui_text('profile_compare_max_label', text_lang, default='Max'))}</th>"
            f"</tr></thead><tbody>"
            f"<tr><td>{escape(str(base_profile_key))}</td><td>{base_stats.get('count', 0)}</td>"
            f"<td>{base_stats.get('mean', 0.0):.4f}</td><td>{base_stats.get('min', 0.0):.4f}</td>"
            f"<td>{base_stats.get('max', 0.0):.4f}</td></tr>"
            f"<tr><td>{escape(str(compare_profile_key))}</td><td>{compare_stats.get('count', 0)}</td>"
            f"<td>{compare_stats.get('mean', 0.0):.4f}</td><td>{compare_stats.get('min', 0.0):.4f}</td>"
            f"<td>{compare_stats.get('max', 0.0):.4f}</td></tr>"
            f"</tbody></table>"
            f"{delta_html}"
            f"{top_change_html}"
            f"<h4>{escape(titles['audit'])}</h4>"
            f"<p><b>{escape(ui_text('profile_compare_json_label', text_lang, default='Compare JSON'))}</b>: {escape(json_path)}<br/>"
            f"<b>{escape(ui_text('profile_compare_markdown_label', text_lang, default='Compare Markdown'))}</b>: {escape(md_path)}<br/>"
            f"<b>{escape(ui_text('compare_report_reason_excerpt_limit_label', text_lang, default='Reason excerpt limit'))}</b>: {int(reason_excerpt_limit)}</p>"
        )
