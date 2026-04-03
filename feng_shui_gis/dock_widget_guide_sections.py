# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout

from .ui_catalog import ui_metric_help_items, ui_text


@dataclass
class GuideInterpretationRefs:
    progress_summary_label: QLabel
    guide_intro_widget: QLabel
    guide_steps_widget: QLabel
    workflow_progress_label: QLabel
    next_step_label: QLabel


@dataclass
class GuideAnalyticalRefs:
    checklist_label: QLabel
    metric_help_combo: QComboBox
    metric_help_hint: QLabel
    quick_number_widget: QLabel
    evidence_widget: QLabel


@dataclass
class GuideAuditRefs:
    dem_diag_widget: QLabel
    workflow_status_label: QLabel


def build_interpretation_section(owner, card_layout, workflow_progress):
    progress_summary_label = QLabel("", owner)
    progress_summary_label.setObjectName("guideSummary")
    progress_summary_label.setWordWrap(True)
    card_layout.addWidget(progress_summary_label)

    guide_intro_widget = QLabel("", owner)
    guide_intro_widget.setObjectName("guideWidget")
    guide_intro_widget.setWordWrap(True)
    guide_intro_widget.setTextFormat(Qt.RichText)
    card_layout.addWidget(guide_intro_widget)

    guide_steps_widget = QLabel("", owner)
    guide_steps_widget.setObjectName("guideWidget")
    guide_steps_widget.setWordWrap(True)
    guide_steps_widget.setTextFormat(Qt.RichText)
    card_layout.addWidget(guide_steps_widget)

    card_layout.addWidget(workflow_progress)

    next_step_label = QLabel("", owner)
    next_step_label.setObjectName("guideNext")
    next_step_label.setWordWrap(True)
    card_layout.addWidget(next_step_label)

    return GuideInterpretationRefs(
        progress_summary_label=progress_summary_label,
        guide_intro_widget=guide_intro_widget,
        guide_steps_widget=guide_steps_widget,
        workflow_progress_label=workflow_progress,
        next_step_label=next_step_label,
    )


def build_analytical_section(owner, card_layout, on_metric_help_change):
    checklist_label = QLabel("", owner)
    checklist_label.setObjectName("guideChecklist")
    checklist_label.setWordWrap(True)
    checklist_label.setTextFormat(Qt.RichText)
    card_layout.addWidget(checklist_label)

    metric_row = QHBoxLayout()
    metric_label = QLabel(ui_text("guide_metric_label", default="Metric Help"), owner)
    metric_help_combo = QComboBox(owner)
    for label, description in ui_metric_help_items():
        metric_help_combo.addItem(label, description)
    metric_help_combo.currentIndexChanged.connect(on_metric_help_change)
    metric_row.addWidget(metric_label)
    metric_row.addWidget(metric_help_combo, 1)
    card_layout.addLayout(metric_row)

    metric_help_hint = QLabel("", owner)
    metric_help_hint.setObjectName("metricHint")
    metric_help_hint.setWordWrap(True)
    card_layout.addWidget(metric_help_hint)

    quick_number_widget = QLabel("", owner)
    quick_number_widget.setObjectName("guideWidget")
    quick_number_widget.setWordWrap(True)
    quick_number_widget.setTextFormat(Qt.RichText)
    card_layout.addWidget(quick_number_widget)

    evidence_widget = QLabel("", owner)
    evidence_widget.setObjectName("guideWidget")
    evidence_widget.setWordWrap(True)
    evidence_widget.setTextFormat(Qt.RichText)
    card_layout.addWidget(evidence_widget)

    return GuideAnalyticalRefs(
        checklist_label=checklist_label,
        metric_help_combo=metric_help_combo,
        metric_help_hint=metric_help_hint,
        quick_number_widget=quick_number_widget,
        evidence_widget=evidence_widget,
    )


def build_audit_section(owner, card_layout):
    dem_diag_widget = QLabel("", owner)
    dem_diag_widget.setObjectName("guideWidget")
    dem_diag_widget.setWordWrap(True)
    dem_diag_widget.setTextFormat(Qt.RichText)
    card_layout.addWidget(dem_diag_widget)

    workflow_status_label = QLabel("", owner)
    workflow_status_label.setObjectName("guideStatus")
    workflow_status_label.setWordWrap(True)
    card_layout.addWidget(workflow_status_label)

    return GuideAuditRefs(
        dem_diag_widget=dem_diag_widget,
        workflow_status_label=workflow_status_label,
    )
