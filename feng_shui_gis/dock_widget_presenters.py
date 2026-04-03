# -*- coding: utf-8 -*-
from __future__ import annotations

from .analysis import FengShuiAnalyzer
from .dock_widget_viewmodel import dem_diagnostics_state, evidence_summary_state
from .ui_catalog import ui_text


def build_dem_diagnostics_html(*, dem_layer):
    if dem_layer is None:
        return dem_diagnostics_state()["html"]
    try:
        diagnostics = FengShuiAnalyzer.adaptive_spacing_diagnostics(dem_layer)
    except RuntimeError as exc:
        return dem_diagnostics_state(error_text=str(exc))["html"]
    return dem_diagnostics_state(
        layer_name=dem_layer.name(),
        diagnostics=diagnostics,
        crs_is_geographic=dem_layer.crs().isGeographic(),
    )["html"]


def build_evidence_summary_html(*, records, advanced_context_enabled, culture_key):
    return evidence_summary_state(
        records=records if isinstance(records, list) else [],
        advanced_context_enabled=advanced_context_enabled,
        culture_key=culture_key,
    )["html"]


def apply_workflow_presentation(refs, state):
    refs.workflow_progress.setValue(state["percent"])
    refs.progress_summary_label.setText(state["summary_text"])
    refs.next_step_label.setText(state["next_step_text"])
    refs.checklist_label.setText(state["checklist_html"])
    refs.workflow_status_label.setText(state["recent_status_text"])


def workflow_recent_status_text(text):
    return ui_text(
        "workflow_recent_status_template",
        default="Recent status: {text}",
    ).format(text=text)


def metric_help_text(description):
    if description in (None, ""):
        return ui_text(
            "metric_help_empty",
            default="No description available for the selected metric.",
        )
    return str(description)


def quick_number_html():
    return ui_text(
        "guide_quick_numbers_html",
        default=(
            "<b>Quick Number Read</b><br/>"
            "score/confidence (0-1): 0.80+ strong, 0.65-0.79 good, 0.50-0.64 moderate, below 0.50 weak.<br/>"
            "TPI: near 0 flat, negative concave, positive convex."
        ),
    )
