# -*- coding: utf-8 -*-
"""Helpers for compare-result selection and zoom actions."""

from __future__ import annotations


def select_changed_features(
    *,
    base_layer,
    compare_layer,
    feature_uids,
    uid_match_summary,
    log_debug,
    set_active_layer,
):
    if not feature_uids:
        return 0

    expected_count = len(feature_uids)
    selected_count = 0
    for layer in (base_layer, compare_layer):
        if layer is None:
            continue
        field_names = layer.fields().names()
        match_summary = uid_match_summary(
            layer,
            feature_uids,
            field_names=field_names,
        )
        feature_ids_layer = match_summary["feature_ids"]
        if match_summary["ambiguous"]:
            log_debug(
                f"UID selection skipped ambiguous matches for layer {layer.name()}: "
                f"{', '.join(match_summary['ambiguous'][:5])}"
            )
        if match_summary["missing"]:
            log_debug(
                f"UID selection could not resolve some features for layer {layer.name()}: "
                f"{', '.join(match_summary['missing'][:5])}"
            )
        if not feature_ids_layer:
            log_debug(f"No comparable features found for layer {layer.name()}")
            return 0
        try:
            layer.removeSelection()
        except (RuntimeError, TypeError, AttributeError) as exc:
            log_debug(
                f"Failed to clear selection on layer {layer.name() if hasattr(layer, 'name') else layer}: {type(exc).__name__}: {exc}"
            )
        try:
            layer.selectByIds(feature_ids_layer)
            selected_ids = layer.selectedFeatureIds()
            if len(selected_ids) != expected_count:
                log_debug(
                    f"UID selection mismatch on layer {layer.name()}: expected {expected_count}, selected {len(selected_ids)}."
                )
                return 0
            selected_count = max(selected_count, len(selected_ids))
        except (RuntimeError, TypeError, AttributeError) as exc:
            log_debug(
                f"Failed to select changed features on layer {layer.name() if hasattr(layer, 'name') else layer}: {type(exc).__name__}: {exc}"
            )
            continue

    if compare_layer is not None:
        try:
            set_active_layer(compare_layer)
        except (RuntimeError, AttributeError, TypeError) as exc:
            log_debug(
                f"Failed to activate compare layer {compare_layer.name()}: {type(exc).__name__}: {exc}"
            )
    return selected_count


def zoom_to_selected_features(*, layer, zoom_callback, log_debug):
    if layer is None:
        return False
    try:
        selected_ids = layer.selectedFeatureIds()
    except (RuntimeError, AttributeError, TypeError) as exc:
        log_debug(
            f"Failed to read selected feature ids from layer {layer.name()}: {type(exc).__name__}: {exc}"
        )
        return False
    if not selected_ids:
        return False
    try:
        zoom_callback(layer)
        return True
    except (RuntimeError, AttributeError, TypeError) as exc:
        log_debug(
            f"Failed to zoom to selected features for layer {layer.name()}: {type(exc).__name__}: {exc}"
        )
        return False
