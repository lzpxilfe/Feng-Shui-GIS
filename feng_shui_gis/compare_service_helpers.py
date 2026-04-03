# -*- coding: utf-8 -*-
"""Helpers for compare-service post-processing."""

from __future__ import annotations

from qgis.core import QgsProject


def prepare_compare_results(
    *,
    plugin,
    base_layer,
    compare_layer,
    compare_profile_key,
    label_language,
):
    base_stats = plugin._score_stats(base_layer)
    compare_stats = plugin._score_stats(compare_layer)
    delta_stats = plugin._pairwise_score_delta(base_layer, compare_layer)
    top_changes = plugin._top_score_changes(base_layer, compare_layer)
    top_changes = plugin._sanitize_top_change_rows(top_changes)

    is_contract_ok, contract_message = plugin._validate_compare_feature_contract(
        base_layer,
        compare_layer,
        top_changes,
    )
    if not is_contract_ok:
        raise RuntimeError(contract_message)

    selected_change_count = plugin._select_top_changed_features(
        base_layer,
        compare_layer,
        top_changes,
    )
    if top_changes and selected_change_count == 0:
        raise RuntimeError("top_changed feature UIDs could not be fully selected")

    zoom_applied = plugin._zoom_to_selected_features(compare_layer)
    change_layer = plugin._export_top_changed_features_layer(
        compare_layer,
        top_changes,
        compare_profile_key,
        label_language,
    )
    if top_changes and change_layer is None:
        raise RuntimeError("selected changed features were not exported")

    if change_layer is not None:
        plugin._style_compare_change_layer(change_layer, label_language)
        QgsProject.instance().addMapLayer(change_layer)
        plugin._configure_layer_click_info(change_layer, label_language)

    return {
        "base_stats": base_stats,
        "compare_stats": compare_stats,
        "delta_stats": delta_stats,
        "top_changes": top_changes,
        "selected_change_count": selected_change_count,
        "zoom_applied": zoom_applied,
        "change_layer": change_layer,
        "change_layer_name": change_layer.name() if change_layer is not None else "",
    }
