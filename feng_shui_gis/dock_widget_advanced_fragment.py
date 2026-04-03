# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .locale import language_code, tr
from .profile_catalog import available_profiles, profile_label
from .cultural_context import available_periods, period_label
from .ui_catalog import ui_text


@dataclass
class AdvancedOptionsRefs:
    advanced_options_button: QToolButton
    advanced_options_panel: QFrame
    profile_combo: QComboBox
    reload_profiles_button: QPushButton
    advanced_context_checkbox: QCheckBox
    show_experimental_context_checkbox: QCheckBox
    culture_combo: QComboBox
    period_combo: QComboBox
    context_param_combo: QComboBox
    profile_recommendation_hint: QLabel
    apply_recommended_profile_button: QPushButton
    compare_profiles_button: QPushButton
    context_evidence_button: QPushButton
    context_evidence_hint: QLabel
    context_param_hint: QLabel


def build_advanced_options_fragment(
    owner,
    *,
    on_open_context_evidence_dialog,
):
    advanced_options_button = QToolButton(owner)
    advanced_options_button.setObjectName("advancedToggle")
    advanced_options_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    advanced_options_button.setCheckable(True)
    advanced_options_button.setChecked(False)
    advanced_options_button.setArrowType(Qt.RightArrow)
    advanced_options_button.setText(
        ui_text("advanced_options_button", default="Advanced Options")
    )

    advanced_options_panel = QFrame(owner)
    advanced_options_panel.setObjectName("advancedPanel")
    advanced_layout = QVBoxLayout(advanced_options_panel)
    advanced_layout.setContentsMargins(10, 8, 10, 8)
    advanced_layout.setSpacing(8)

    advanced_form = QFormLayout()
    advanced_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    advanced_form.setFormAlignment(Qt.AlignTop)
    advanced_form.setHorizontalSpacing(16)
    advanced_form.setVerticalSpacing(8)

    lang = language_code()
    profile_combo = QComboBox(owner)
    profile_keys = list(available_profiles()) or ["general"]
    for profile_key in profile_keys:
        profile_combo.addItem(profile_label(profile_key, lang), profile_key)
    profile_row_widget = QWidget(owner)
    profile_row_layout = QHBoxLayout(profile_row_widget)
    profile_row_layout.setContentsMargins(0, 0, 0, 0)
    profile_row_layout.setSpacing(8)
    profile_row_layout.addWidget(profile_combo, 1)
    reload_profiles_button = QPushButton(
        ui_text("reload_profiles_button", default="Reload Profiles"),
        owner,
    )
    reload_profiles_button.setObjectName("helpButton")
    profile_row_layout.addWidget(reload_profiles_button)
    advanced_form.addRow(tr("model_label"), profile_row_widget)

    advanced_context_checkbox = QCheckBox(
        ui_text(
            "advanced_context_toggle_label",
            default="Enable advanced context (country/period)",
        ),
        owner,
    )
    advanced_context_checkbox.setChecked(False)
    advanced_form.addRow(
        ui_text("context_mode_label", default="Context Mode"),
        advanced_context_checkbox,
    )

    show_experimental_context_checkbox = QCheckBox(
        ui_text(
            "context_experimental_toggle_label",
            default=(
                "탐색 지역 프로필 표시 (근거 제한)"
                if language_code() == "ko"
                else "Show exploratory region profiles (limited evidence)"
            ),
        ),
        owner,
    )
    show_experimental_context_checkbox.setChecked(False)
    advanced_form.addRow(
        ui_text(
            "context_scope_label",
            default="프로필 범위" if language_code() == "ko" else "Context Profile Scope",
        ),
        show_experimental_context_checkbox,
    )

    culture_combo = QComboBox(owner)
    advanced_form.addRow(tr("culture_label"), culture_combo)

    period_combo = QComboBox(owner)
    period_keys = list(available_periods()) or ["early_modern"]
    for period_key in period_keys:
        period_combo.addItem(period_label(period_key, lang), period_key)
    if "early_modern" in period_keys:
        period_combo.setCurrentIndex(period_keys.index("early_modern"))
    advanced_form.addRow(tr("period_label"), period_combo)

    context_param_combo = QComboBox(owner)
    advanced_form.addRow(
        ui_text("context_param_label", default="Evidence Parameter"),
        context_param_combo,
    )
    advanced_layout.addLayout(advanced_form)

    profile_recommendation_hint = QLabel("", owner)
    profile_recommendation_hint.setObjectName("contextHint")
    profile_recommendation_hint.setWordWrap(True)
    advanced_layout.addWidget(profile_recommendation_hint)

    recommendation_row = QHBoxLayout()
    apply_recommended_profile_button = QPushButton(
        ui_text(
            "apply_recommended_profile_button",
            default="Use Recommended Profile",
        ),
        owner,
    )
    apply_recommended_profile_button.setObjectName("helpButton")
    apply_recommended_profile_button.setEnabled(False)
    recommendation_row.addWidget(apply_recommended_profile_button)
    compare_profiles_button = QPushButton(
        ui_text("compare_profiles_button", default="Quick Compare"),
        owner,
    )
    compare_profiles_button.setObjectName("helpButton")
    compare_profiles_button.setEnabled(False)
    recommendation_row.addWidget(compare_profiles_button)
    recommendation_row.addStretch(1)
    advanced_layout.addLayout(recommendation_row)

    evidence_row = QHBoxLayout()
    context_evidence_button = QPushButton(
        ui_text("context_evidence_button", default="View Context Evidence"),
        owner,
    )
    context_evidence_button.setObjectName("helpButton")
    context_evidence_button.clicked.connect(on_open_context_evidence_dialog)
    evidence_row.addWidget(context_evidence_button)
    evidence_row.addStretch(1)
    advanced_layout.addLayout(evidence_row)

    context_evidence_hint = QLabel("", owner)
    context_evidence_hint.setObjectName("contextHint")
    context_evidence_hint.setWordWrap(True)
    advanced_layout.addWidget(context_evidence_hint)

    context_param_hint = QLabel("", owner)
    context_param_hint.setObjectName("contextParamHint")
    context_param_hint.setWordWrap(True)
    advanced_layout.addWidget(context_param_hint)

    refs = AdvancedOptionsRefs(
        advanced_options_button=advanced_options_button,
        advanced_options_panel=advanced_options_panel,
        profile_combo=profile_combo,
        reload_profiles_button=reload_profiles_button,
        advanced_context_checkbox=advanced_context_checkbox,
        show_experimental_context_checkbox=show_experimental_context_checkbox,
        culture_combo=culture_combo,
        period_combo=period_combo,
        context_param_combo=context_param_combo,
        profile_recommendation_hint=profile_recommendation_hint,
        apply_recommended_profile_button=apply_recommended_profile_button,
        compare_profiles_button=compare_profiles_button,
        context_evidence_button=context_evidence_button,
        context_evidence_hint=context_evidence_hint,
        context_param_hint=context_param_hint,
    )
    return refs
