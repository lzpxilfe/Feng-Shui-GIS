# -*- coding: utf-8 -*-
"""Payload assembly helpers for calibration fitting results."""


def calibration_split_manifest(
    *,
    total_count,
    train_count,
    validation_count,
    evaluation_count,
    used_validation,
    used_evaluation,
    train_role,
    validation_role,
    evaluation_role,
    selection_phase,
    reported_metric_phase,
):
    return {
        "total_count": int(total_count),
        "train_count": int(train_count),
        "validation_count": int(validation_count),
        "evaluation_count": int(evaluation_count),
        "deterministic_split": True,
        "used_validation": bool(used_validation),
        "used_evaluation": bool(used_evaluation),
        "train_role": str(train_role),
        "validation_role": str(validation_role),
        "evaluation_role": str(evaluation_role),
        "selection_phase": str(selection_phase),
        "reported_metric_phase": str(reported_metric_phase),
        "selection_reused_for_reporting": False,
        "selection_count": int(validation_count),
        "report_count": int(evaluation_count),
    }


def training_diagnostics(baseline_metrics, candidate_metrics):
    return {
        "baseline_metrics": baseline_metrics,
        "candidate_metrics": candidate_metrics,
    }


def selection_diagnostics(selection_phase, baseline_metrics, candidate_metrics):
    return {
        "phase": str(selection_phase),
        "baseline_metrics": baseline_metrics,
        "candidate_metrics": candidate_metrics,
        "reused_for_reporting": False,
    }


def parameter_change_summary(base_parameters, final_parameters, *, threshold=0.01, max_items=4):
    deltas = {
        key: float(final_parameters.get(key, 0.0)) - float(base_parameters.get(key, 0.0))
        for key in base_parameters.keys()
    }
    changed = sorted(
        (
            (abs(delta), key, delta)
            for key, delta in deltas.items()
            if abs(delta) >= float(threshold)
        ),
        reverse=True,
    )
    if changed:
        summary = ", ".join(
            f"{key}:{delta:+.3f}"
            for _abs_delta, key, delta in changed[: max(1, int(max_items))]
        )
    else:
        summary = "no-material-parameter-change"
    applied = any(abs(delta) > 1e-6 for delta in deltas.values())
    return deltas, summary, applied


def calibration_scope(applied, parameter_applied, weight_applied):
    if applied and parameter_applied and weight_applied:
        return "local_profile_tuning+reweighting"
    if applied and parameter_applied:
        return "local_profile_tuning"
    if applied and weight_applied:
        return "local_weight_reweighting"
    return "threshold_only"


def calibration_fallback_payload(
    *,
    scope,
    applied,
    base_weights,
    weights,
    weight_deltas,
    weight_summary,
    base_profile_parameters,
    profile_parameters,
    parameter_deltas,
    parameter_summary,
    indicator_discrimination,
    base_metrics,
    metrics,
    scores_by_id,
    annotation_metrics,
    reported_baseline_metrics,
    reported_metrics,
    reported_scores_by_id,
    reported_metric_phase,
    reported_metric_notice,
    calibration_split,
    base_train_metrics,
    base_validation_metrics,
    training_baseline_metrics,
    training_candidate_metrics,
    selection_phase,
    selection_baseline_metrics,
    selection_candidate_metrics,
):
    return {
        "scope": scope,
        "applied": applied,
        "base_weights": base_weights,
        "weights": weights,
        "weight_deltas": weight_deltas,
        "weight_summary": weight_summary,
        "base_profile_parameters": base_profile_parameters,
        "profile_parameters": profile_parameters,
        "parameter_deltas": parameter_deltas,
        "parameter_summary": parameter_summary,
        "indicator_discrimination": indicator_discrimination,
        "base_metrics": base_metrics,
        "metrics": metrics,
        "scores_by_id": scores_by_id,
        "annotation_metrics": annotation_metrics,
        "reported_baseline_metrics": reported_baseline_metrics,
        "reported_metrics": reported_metrics,
        "reported_scores_by_id": reported_scores_by_id,
        "reported_metric_phase": reported_metric_phase,
        "reported_metric_notice": reported_metric_notice,
        "calibration_split": calibration_split,
        "base_train_metrics": base_train_metrics,
        "base_validation_metrics": base_validation_metrics,
        "training_diagnostics": training_diagnostics(
            training_baseline_metrics,
            training_candidate_metrics,
        ),
        "selection_diagnostics": selection_diagnostics(
            selection_phase,
            selection_baseline_metrics,
            selection_candidate_metrics,
        ),
    }


def calibration_fit_payload(
    *,
    scope,
    applied,
    base_weights,
    weights,
    weight_deltas,
    weight_summary,
    base_profile_parameters,
    profile_parameters,
    parameter_deltas,
    parameter_summary,
    indicator_discrimination,
    base_metrics,
    metrics,
    scores_by_id,
    annotation_metrics,
    reported_baseline_metrics,
    reported_metrics,
    reported_scores_by_id,
    reported_metric_phase,
    reported_metric_notice,
    calibration_split,
    base_train_metrics,
    base_validation_metrics,
    base_train_scores_by_id,
    base_validation_scores_by_id,
    training_baseline_metrics,
    training_candidate_metrics,
    selection_phase,
    selection_baseline_metrics,
    selection_candidate_metrics,
):
    payload = calibration_fallback_payload(
        scope=scope,
        applied=applied,
        base_weights=base_weights,
        weights=weights,
        weight_deltas=weight_deltas,
        weight_summary=weight_summary,
        base_profile_parameters=base_profile_parameters,
        profile_parameters=profile_parameters,
        parameter_deltas=parameter_deltas,
        parameter_summary=parameter_summary,
        indicator_discrimination=indicator_discrimination,
        base_metrics=base_metrics,
        metrics=metrics,
        scores_by_id=scores_by_id,
        annotation_metrics=annotation_metrics,
        reported_baseline_metrics=reported_baseline_metrics,
        reported_metrics=reported_metrics,
        reported_scores_by_id=reported_scores_by_id,
        reported_metric_phase=reported_metric_phase,
        reported_metric_notice=reported_metric_notice,
        calibration_split=calibration_split,
        base_train_metrics=base_train_metrics,
        base_validation_metrics=base_validation_metrics,
        training_baseline_metrics=training_baseline_metrics,
        training_candidate_metrics=training_candidate_metrics,
        selection_phase=selection_phase,
        selection_baseline_metrics=selection_baseline_metrics,
        selection_candidate_metrics=selection_candidate_metrics,
    )
    payload["base_train_scores_by_id"] = base_train_scores_by_id
    payload["base_validation_scores_by_id"] = base_validation_scores_by_id
    return payload
