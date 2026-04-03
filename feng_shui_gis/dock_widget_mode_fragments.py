# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .locale import tr
from .profile_catalog import analysis_rules
from .ui_catalog import ui_text


@dataclass
class LandscapeTabRefs:
    landscape_auto_hydro_checkbox: QCheckBox
    include_terms_checkbox: QCheckBox
    extract_terms_button: QPushButton


@dataclass
class AnalysisTabRefs:
    analysis_auto_hydro_checkbox: QCheckBox
    negative_ratio_combo: QComboBox
    calibration_seed_spin: QSpinBox
    run_button: QPushButton
    calibration_button: QPushButton


def build_landscape_tab(owner, *, on_extract_terms_requested):
    tab = QWidget(owner)
    layout = QVBoxLayout(tab)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(10)

    card = QFrame(tab)
    card.setObjectName("tabCard")
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(12, 12, 12, 12)
    card_layout.setSpacing(8)

    desc = QLabel(tr("landscape_desc"), card)
    desc.setWordWrap(True)
    card_layout.addWidget(desc)

    landscape_auto_hydro_checkbox = QCheckBox(tr("auto_hydro_label"), card)
    landscape_auto_hydro_checkbox.setChecked(True)
    card_layout.addWidget(landscape_auto_hydro_checkbox)

    include_terms_checkbox = QCheckBox(
        ui_text("include_terms_label", default="Extract term points and links"),
        card,
    )
    include_terms_checkbox.setChecked(False)
    card_layout.addWidget(include_terms_checkbox)

    extract_terms_button = QPushButton(tr("extract_landscape_button"), card)
    extract_terms_button.setObjectName("primaryAction")
    extract_terms_button.clicked.connect(on_extract_terms_requested)
    card_layout.addWidget(extract_terms_button)

    layout.addWidget(card)
    layout.addStretch(1)
    return tab, LandscapeTabRefs(
        landscape_auto_hydro_checkbox=landscape_auto_hydro_checkbox,
        include_terms_checkbox=include_terms_checkbox,
        extract_terms_button=extract_terms_button,
    )


def build_analysis_tab(owner, *, on_run_requested, on_calibration_requested):
    tab = QWidget(owner)
    layout = QVBoxLayout(tab)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(10)
    calibration_rules = analysis_rules().get("calibration", {})

    card = QFrame(tab)
    card.setObjectName("tabCard")
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(12, 12, 12, 12)
    card_layout.setSpacing(8)

    desc = QLabel(tr("analysis_desc"), card)
    desc.setWordWrap(True)
    card_layout.addWidget(desc)

    analysis_auto_hydro_checkbox = QCheckBox(
        tr("analysis_auto_hydro_label"), card
    )
    analysis_auto_hydro_checkbox.setChecked(True)
    card_layout.addWidget(analysis_auto_hydro_checkbox)

    ratio_row = QHBoxLayout()
    ratio_label = QLabel(ui_text("negative_ratio_label", default="Negative Ratio"), card)
    negative_ratio_combo = QComboBox(card)
    ratio_options = calibration_rules.get("negative_ratio_options", [1, 2, 3, 4])
    clean_options = []
    for value in ratio_options:
        try:
            clean = int(value)
        except (TypeError, ValueError):
            continue
        if clean > 0 and clean not in clean_options:
            clean_options.append(clean)
    if not clean_options:
        clean_options = [1, 2, 3, 4]
    default_ratio = calibration_rules.get("default_negative_ratio", 3)
    try:
        default_ratio = int(default_ratio)
    except (TypeError, ValueError):
        default_ratio = 3
    for value in clean_options:
        label = f"{value}x"
        if value == default_ratio:
            suffix = ui_text("negative_ratio_recommended_suffix", default="(Recommended)")
            label = f"{value}x {suffix}"
        negative_ratio_combo.addItem(label, value)
    if default_ratio in clean_options:
        negative_ratio_combo.setCurrentIndex(clean_options.index(default_ratio))
    else:
        negative_ratio_combo.setCurrentIndex(0)
    ratio_row.addWidget(ratio_label)
    ratio_row.addWidget(negative_ratio_combo, 1)
    card_layout.addLayout(ratio_row)

    seed_row = QHBoxLayout()
    seed_label = QLabel(ui_text("seed_label", default="Random Seed"), card)
    calibration_seed_spin = QSpinBox(card)
    seed_min = calibration_rules.get("seed_min", 1)
    seed_max = calibration_rules.get("seed_max", 999999)
    seed_default = calibration_rules.get("seed_default", 42)
    try:
        seed_min = int(seed_min)
    except (TypeError, ValueError):
        seed_min = 1
    try:
        seed_max = int(seed_max)
    except (TypeError, ValueError):
        seed_max = 999999
    if seed_max < seed_min:
        seed_max = seed_min
    try:
        seed_default = int(seed_default)
    except (TypeError, ValueError):
        seed_default = 42
    seed_default = max(seed_min, min(seed_max, seed_default))
    calibration_seed_spin.setRange(seed_min, seed_max)
    calibration_seed_spin.setValue(seed_default)
    seed_row.addWidget(seed_label)
    seed_row.addWidget(calibration_seed_spin, 1)
    card_layout.addLayout(seed_row)

    run_button = QPushButton(tr("run_button"), card)
    run_button.setObjectName("primaryAction")
    run_button.clicked.connect(on_run_requested)
    card_layout.addWidget(run_button)

    calibration_button = QPushButton(
        ui_text(
            "calibration_button",
            default="Korea SHP Calibration (ROC/AUC Report)",
        ),
        card,
    )
    calibration_button.setObjectName("helpButton")
    calibration_button.clicked.connect(on_calibration_requested)
    card_layout.addWidget(calibration_button)

    layout.addWidget(card)
    layout.addStretch(1)
    return tab, AnalysisTabRefs(
        analysis_auto_hydro_checkbox=analysis_auto_hydro_checkbox,
        negative_ratio_combo=negative_ratio_combo,
        calibration_seed_spin=calibration_seed_spin,
        run_button=run_button,
        calibration_button=calibration_button,
    )
