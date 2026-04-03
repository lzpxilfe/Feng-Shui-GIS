# -*- coding: utf-8 -*-
"""State snapshot/restore helpers for the dock widget."""

from __future__ import annotations

from .cultural_context import available_cultures


def _set_combo_data(combo, value):
    if combo is None:
        return
    index = combo.findData(value)
    if index >= 0:
        combo.setCurrentIndex(index)


def snapshot_ui_state(widget):
    return {
        "sites_layer": widget.sites_combo.currentLayer() if hasattr(widget, "sites_combo") else None,
        "dem_layer": widget.dem_combo.currentLayer() if hasattr(widget, "dem_combo") else None,
        "water_layer": widget.water_combo.currentLayer() if hasattr(widget, "water_combo") else None,
        "ui_language": widget.ui_language(),
        "label_language": widget.label_language(),
        "purpose_key": widget.purpose_combo.currentData() if hasattr(widget, "purpose_combo") else None,
        "hemisphere": widget.hemisphere_combo.currentData() if hasattr(widget, "hemisphere_combo") else None,
        "web_mountain_enabled": bool(widget.web_mountain_checkbox.isChecked()) if hasattr(widget, "web_mountain_checkbox") else False,
        "web_mountain_radius": int(widget.web_mountain_radius_spin.value()) if hasattr(widget, "web_mountain_radius_spin") else None,
        "web_mountain_limit": int(widget.web_mountain_limit_spin.value()) if hasattr(widget, "web_mountain_limit_spin") else None,
        "web_mountain_lang": widget.web_mountain_lang_combo.currentData() if hasattr(widget, "web_mountain_lang_combo") else None,
        "advanced_options_open": bool(widget.advanced_options_button.isChecked()) if hasattr(widget, "advanced_options_button") else False,
        "profile_key": widget.profile_combo.currentData() if hasattr(widget, "profile_combo") else None,
        "advanced_context_enabled": bool(widget.advanced_context_checkbox.isChecked()) if hasattr(widget, "advanced_context_checkbox") else False,
        "show_experimental_contexts": bool(widget.show_experimental_context_checkbox.isChecked()) if hasattr(widget, "show_experimental_context_checkbox") else False,
        "culture_key": widget.culture_combo.currentData() if hasattr(widget, "culture_combo") else None,
        "period_key": widget.period_combo.currentData() if hasattr(widget, "period_combo") else None,
        "mode_tab_index": widget.mode_tabs.currentIndex() if hasattr(widget, "mode_tabs") else 0,
        "landscape_auto_hydro": bool(widget.landscape_auto_hydro_checkbox.isChecked()) if hasattr(widget, "landscape_auto_hydro_checkbox") else True,
        "include_terms": bool(widget.include_terms_checkbox.isChecked()) if hasattr(widget, "include_terms_checkbox") else False,
        "analysis_auto_hydro": bool(widget.analysis_auto_hydro_checkbox.isChecked()) if hasattr(widget, "analysis_auto_hydro_checkbox") else True,
        "negative_ratio": widget.negative_ratio_combo.currentData() if hasattr(widget, "negative_ratio_combo") else None,
        "calibration_seed": int(widget.calibration_seed_spin.value()) if hasattr(widget, "calibration_seed_spin") else None,
        "status_text": widget.status_label.text() if hasattr(widget, "status_label") else "",
    }


def restore_ui_state(widget, state, *, rebuild_culture_combo):
    if not isinstance(state, dict):
        return

    widgets = [
        getattr(widget, "sites_combo", None),
        getattr(widget, "dem_combo", None),
        getattr(widget, "water_combo", None),
        getattr(widget, "ui_language_combo", None),
        getattr(widget, "label_language_combo", None),
        getattr(widget, "purpose_combo", None),
        getattr(widget, "hemisphere_combo", None),
        getattr(widget, "web_mountain_checkbox", None),
        getattr(widget, "web_mountain_radius_spin", None),
        getattr(widget, "web_mountain_limit_spin", None),
        getattr(widget, "web_mountain_lang_combo", None),
        getattr(widget, "advanced_options_button", None),
        getattr(widget, "profile_combo", None),
        getattr(widget, "advanced_context_checkbox", None),
        getattr(widget, "show_experimental_context_checkbox", None),
        getattr(widget, "culture_combo", None),
        getattr(widget, "period_combo", None),
        getattr(widget, "mode_tabs", None),
        getattr(widget, "landscape_auto_hydro_checkbox", None),
        getattr(widget, "include_terms_checkbox", None),
        getattr(widget, "analysis_auto_hydro_checkbox", None),
        getattr(widget, "negative_ratio_combo", None),
        getattr(widget, "calibration_seed_spin", None),
    ]
    for item in widgets:
        if item is not None:
            item.blockSignals(True)

    try:
        if hasattr(widget, "sites_combo"):
            widget.sites_combo.setLayer(state.get("sites_layer"))
        if hasattr(widget, "dem_combo"):
            widget.dem_combo.setLayer(state.get("dem_layer"))
        if hasattr(widget, "water_combo"):
            widget.water_combo.setLayer(state.get("water_layer"))
        _set_combo_data(getattr(widget, "ui_language_combo", None), state.get("ui_language"))
        _set_combo_data(getattr(widget, "label_language_combo", None), state.get("label_language"))
        _set_combo_data(getattr(widget, "purpose_combo", None), state.get("purpose_key"))
        _set_combo_data(getattr(widget, "hemisphere_combo", None), state.get("hemisphere"))
        if hasattr(widget, "web_mountain_checkbox"):
            widget.web_mountain_checkbox.setChecked(bool(state.get("web_mountain_enabled")))
        if hasattr(widget, "web_mountain_radius_spin") and state.get("web_mountain_radius") is not None:
            widget.web_mountain_radius_spin.setValue(int(state.get("web_mountain_radius")))
        if hasattr(widget, "web_mountain_limit_spin") and state.get("web_mountain_limit") is not None:
            widget.web_mountain_limit_spin.setValue(int(state.get("web_mountain_limit")))
        _set_combo_data(getattr(widget, "web_mountain_lang_combo", None), state.get("web_mountain_lang"))
        if hasattr(widget, "advanced_options_button"):
            widget.advanced_options_button.setChecked(bool(state.get("advanced_options_open")))
        _set_combo_data(getattr(widget, "profile_combo", None), state.get("profile_key"))
        if hasattr(widget, "advanced_context_checkbox"):
            widget.advanced_context_checkbox.setChecked(bool(state.get("advanced_context_enabled")))
        selected_culture = state.get("culture_key")
        if hasattr(widget, "show_experimental_context_checkbox"):
            if selected_culture in available_cultures("experimental"):
                widget.show_experimental_context_checkbox.setChecked(True)
            else:
                widget.show_experimental_context_checkbox.setChecked(
                    bool(state.get("show_experimental_contexts"))
                )
        if hasattr(widget, "culture_combo"):
            rebuild_culture_combo(selected_culture)
        _set_combo_data(getattr(widget, "period_combo", None), state.get("period_key"))
        if hasattr(widget, "mode_tabs"):
            tab_index = int(state.get("mode_tab_index", 0))
            if 0 <= tab_index < widget.mode_tabs.count():
                widget.mode_tabs.setCurrentIndex(tab_index)
        if hasattr(widget, "landscape_auto_hydro_checkbox"):
            widget.landscape_auto_hydro_checkbox.setChecked(bool(state.get("landscape_auto_hydro")))
        if hasattr(widget, "include_terms_checkbox"):
            widget.include_terms_checkbox.setChecked(bool(state.get("include_terms")))
        if hasattr(widget, "analysis_auto_hydro_checkbox"):
            widget.analysis_auto_hydro_checkbox.setChecked(bool(state.get("analysis_auto_hydro")))
        _set_combo_data(getattr(widget, "negative_ratio_combo", None), state.get("negative_ratio"))
        if hasattr(widget, "calibration_seed_spin") and state.get("calibration_seed") is not None:
            widget.calibration_seed_spin.setValue(int(state.get("calibration_seed")))
        if hasattr(widget, "status_label"):
            widget.status_label.setText(str(state.get("status_text", "") or ""))
    finally:
        for item in widgets:
            if item is not None:
                item.blockSignals(False)
