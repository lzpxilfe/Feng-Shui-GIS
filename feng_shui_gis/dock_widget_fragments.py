# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

from qgis.PyQt.QtWidgets import (
    QComboBox,
    QFrame,
    QLabel,
    QProgressBar,
    QVBoxLayout,
)

from .dock_widget_guide_sections import (
    build_analytical_section,
    build_audit_section,
    build_interpretation_section,
)
from .ui_catalog import ui_text


@dataclass
class WorkflowGuideCardRefs:
    progress_summary_label: QLabel
    guide_intro_widget: QLabel
    guide_steps_widget: QLabel
    workflow_progress: QProgressBar
    next_step_label: QLabel
    checklist_label: QLabel
    metric_help_combo: QComboBox
    metric_help_hint: QLabel
    quick_number_widget: QLabel
    dem_diag_widget: QLabel
    evidence_widget: QLabel
    workflow_status_label: QLabel


def build_workflow_guide_card(owner, on_metric_help_change):
    card = QFrame(owner)
    card.setObjectName("guideCard")
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(12, 10, 12, 12)
    card_layout.setSpacing(6)

    title = QLabel(ui_text("guide_title", default="Progress Guide"), card)
    title.setObjectName("guideTitle")
    card_layout.addWidget(title)

    workflow_progress = QProgressBar(card)
    workflow_progress.setObjectName("workflowProgress")
    workflow_progress.setRange(0, 100)
    workflow_progress.setValue(0)
    workflow_progress.setFormat(
        ui_text("workflow_progress_format", default="%p% ready")
    )
    interpretation_refs = build_interpretation_section(
        card,
        card_layout,
        workflow_progress,
    )
    analytical_refs = build_analytical_section(
        card,
        card_layout,
        on_metric_help_change,
    )
    audit_refs = build_audit_section(card, card_layout)

    refs = WorkflowGuideCardRefs(
        progress_summary_label=interpretation_refs.progress_summary_label,
        guide_intro_widget=interpretation_refs.guide_intro_widget,
        guide_steps_widget=interpretation_refs.guide_steps_widget,
        workflow_progress=workflow_progress,
        next_step_label=interpretation_refs.next_step_label,
        checklist_label=analytical_refs.checklist_label,
        metric_help_combo=analytical_refs.metric_help_combo,
        metric_help_hint=analytical_refs.metric_help_hint,
        quick_number_widget=analytical_refs.quick_number_widget,
        dem_diag_widget=audit_refs.dem_diag_widget,
        evidence_widget=analytical_refs.evidence_widget,
        workflow_status_label=audit_refs.workflow_status_label,
    )
    return card, refs
