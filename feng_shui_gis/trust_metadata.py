"""Central trust/badge contract for user-facing interpretation text."""

from __future__ import annotations

from typing import Any, Dict, List


def build_trust_metadata(
    label_language: str,
    *,
    advanced_context_enabled: bool,
    culture_key: str,
    profile_key: str,
    reported_metric_phase: str | None = None,
    calibration_split: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    del label_language
    badges = ["general_principles"]
    if advanced_context_enabled:
        badges.append("advanced_context")
    if culture_key:
        badges.append("exploratory_context")
    if "cal" in str(profile_key or "").lower() or "cal_" in str(profile_key or "").lower():
        badges.append("local_calibration_applied")
    if (reported_metric_phase or "").lower() in ("held_out_evaluation", "held_out"):
        if "local_calibration_applied" not in badges:
            badges.append("local_calibration_applied")

    result_badges = list(dict.fromkeys(badges))
    return {
        "result_badges": result_badges,
        "score_notice": "fs_score is a heuristic terrain score, not a probability.",
        "compare_notice": "Compare results are gain/drop relative to the selected profile.",
        "calibration_notice": (
            "Held-out evaluation" if (reported_metric_phase or "").lower() == "held_out_evaluation"
            else "No held-out calibration split was reported."
        ),
        "advanced_context_enabled": bool(advanced_context_enabled),
        "culture_key": culture_key,
        "profile_key": profile_key,
        "reported_metric_phase": reported_metric_phase or "",
        "calibration_split": calibration_split or {},
    }
