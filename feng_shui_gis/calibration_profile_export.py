# -*- coding: utf-8 -*-
"""Calibration profile export helpers."""

from __future__ import annotations

import json
import os

from .config_loader import clear_cache
from .profile_catalog import (
    load_local_profiles_payload,
    profile_label,
    write_local_profiles_registry,
)


def export_calibrated_profile(report, *, stamp, report_dir, plugin_dir):
    export_info = {
        "profile_export_status": "skipped-no-change",
        "exported_profile_key": "",
        "profile_export_path": "",
        "local_profile_registry_path": "",
    }
    tuned_weights = report.get("tuned_weights") or {}
    tuned_parameters = report.get("tuned_profile_parameters") or {}
    if not report.get("calibration_applied") or not tuned_weights or not tuned_parameters:
        return export_info

    base_profile_key = str(report.get("profile_key") or "profile").strip() or "profile"
    culture_key = str(report.get("culture_key") or "context").strip() or "context"
    period_key = str(report.get("period_key") or "period").strip() or "period"
    exported_profile_key = (
        f"{base_profile_key}_{culture_key}_{period_key}_cal_{stamp}".lower()
    )
    base_label_ko = profile_label(base_profile_key, "ko")
    base_label_en = profile_label(base_profile_key, "en")
    profile_spec = {
        "label": {
            "ko": f"{base_label_ko} 보정 {culture_key}/{period_key}",
            "en": f"{base_label_en} Calibrated {culture_key}/{period_key}",
        },
        "weights": dict(tuned_weights),
        "slope_target": float(tuned_parameters.get("slope_target", 0.0)),
        "slope_sigma": float(tuned_parameters.get("slope_sigma", 1.0)),
        "tpi_target": float(tuned_parameters.get("tpi_target", 0.0)),
        "tpi_sigma": float(tuned_parameters.get("tpi_sigma", 0.1)),
        "derived_from": {
            "profile_key": base_profile_key,
            "culture_key": culture_key,
            "period_key": period_key,
            "hemisphere": report.get("hemisphere"),
            "negative_ratio": report.get("negative_ratio"),
            "random_seed": report.get("random_seed"),
            "base_roc_auc": report.get("base_roc_auc"),
            "roc_auc": report.get("roc_auc"),
            "base_pr_auc": report.get("base_pr_auc"),
            "pr_auc": report.get("pr_auc"),
            "tuned_weight_summary": report.get("tuned_weight_summary"),
            "tuned_parameter_summary": report.get("tuned_parameter_summary"),
        },
    }

    snapshot_path = os.path.join(report_dir, f"feng_shui_profile_{stamp}.json")
    with open(snapshot_path, "w", encoding="utf-8") as handle:
        json.dump(
            {exported_profile_key: profile_spec},
            handle,
            ensure_ascii=False,
            indent=2,
        )

    local_profile_path = os.path.join(plugin_dir, "config", "local_profiles.json")
    try:
        local_payload = load_local_profiles_payload(base_dir=plugin_dir)
    except RuntimeError as exc:
        raise RuntimeError("Local profile registry contract load failed") from exc

    local_profiles = dict(local_payload.get("profiles") or {})
    if not isinstance(local_profiles, dict):
        raise RuntimeError("Local profile registry payload missing 'profiles' dictionary.")
    local_profiles[exported_profile_key] = profile_spec
    try:
        write_local_profiles_registry(local_profiles, base_dir=plugin_dir)
    except RuntimeError as exc:
        raise RuntimeError("Local profile registry contract write failed") from exc

    clear_cache()
    export_info.update(
        {
            "profile_export_status": "saved",
            "exported_profile_key": exported_profile_key,
            "profile_export_path": snapshot_path,
            "local_profile_registry_path": local_profile_path,
        }
    )
    return export_info
