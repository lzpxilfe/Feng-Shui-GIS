# -*- coding: utf-8 -*-
"""Shared trust metadata helpers for UI, reports, and support bundles."""

from __future__ import annotations

from html import escape

from .cultural_context import culture_visibility_tier
from .ui_catalog import ui_text


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


def badge_label(badge_key, text_lang):
    key_map = {
        "general_principles": "trust_badge_general_principles",
        "advanced_context": "trust_badge_advanced_context",
        "exploratory_context": "trust_badge_exploratory_context",
        "local_calibration_applied": "trust_badge_local_calibration",
    }
    default_map = {
        "general_principles": "General Principles",
        "advanced_context": "Advanced Context",
        "exploratory_context": "Exploratory Context",
        "local_calibration_applied": "Local Calibration Applied",
    }
    return ui_text(
        key_map.get(badge_key, ""),
        text_lang,
        default=default_map.get(badge_key, badge_key.replace("_", " ")),
    )


def is_calibrated_profile(profile_key):
    key = str(profile_key or "").strip()
    return "_cal_" in key or key.endswith("_calibrated")


def calibration_notice(phase, text_lang):
    phase = str(phase or "").strip() or "no_held_out_evaluation"
    defaults = {
        "held_out_evaluation": (
            "Held-out rows were kept separate from tuned-candidate selection."
        ),
        "no_held_out_evaluation": (
            "No held-out rows were available, so tuning diagnostics are shown without reportable evaluation metrics."
        ),
        "validation_reused_for_selection": (
            "Validation rows were reused for tuned-candidate selection, so interpret these metrics as selection diagnostics."
        ),
        "evaluation_reused_for_selection": (
            "Evaluation rows also influenced tuned-candidate selection, so this is not a clean held-out validation result."
        ),
        "in_sample_tuning_diagnostic": (
            "Metrics come from in-sample tuning diagnostics rather than standalone validation."
        ),
    }
    return ui_text(
        f"trust_calibration_notice_{phase}",
        text_lang,
        default=defaults.get(phase, defaults["in_sample_tuning_diagnostic"]),
    )


def compare_notice(text_lang):
    return ui_text(
        "trust_compare_notice",
        text_lang,
        default=(
            "Read compare results as gain/drop relative to the selected profile, not as better/worse or standalone validation."
        ),
    )


def score_notice(text_lang):
    return ui_text(
        "trust_boundary_score_note",
        text_lang,
        default=(
            "Do not interpret <b>fs_score</b> as the probability of site presence. "
            "Treat it as a comparative reading frame."
        ),
    )


def build_trust_metadata(
    text_lang,
    *,
    advanced_context_enabled=False,
    culture_key="",
    profile_key="",
    reported_metric_phase="",
):
    badges = []
    if advanced_context_enabled:
        if culture_key and culture_visibility_tier(culture_key) == "experimental":
            badges.append("exploratory_context")
        else:
            badges.append("advanced_context")
    else:
        badges.append("general_principles")
    if is_calibrated_profile(profile_key):
        badges.append("local_calibration_applied")
    return {
        "result_badges": badges,
        "badge_labels": [badge_label(code, text_lang) for code in badges],
        "score_notice": score_notice(text_lang),
        "compare_notice": compare_notice(text_lang),
        "calibration_notice": calibration_notice(reported_metric_phase, text_lang),
        "reported_metric_phase": str(reported_metric_phase or "").strip()
        or "no_held_out_evaluation",
        "section_titles": section_titles(text_lang),
    }


def badges_markdown(trust_metadata):
    labels = list((trust_metadata or {}).get("badge_labels") or [])
    return ", ".join(str(label) for label in labels if str(label).strip()) or "n/a"


def badges_html(trust_metadata):
    labels = list((trust_metadata or {}).get("badge_labels") or [])
    if not labels:
        return ""
    return " ".join(
        "<span style='display:inline-block;padding:3px 8px;margin:0 6px 6px 0;"
        "border-radius:10px;background:#f0e4c8;color:#5b4630;font-weight:600;'>"
        + escape(str(label))
        + "</span>"
        for label in labels
        if str(label).strip()
    )
