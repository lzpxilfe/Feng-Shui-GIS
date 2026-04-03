# -*- coding: utf-8 -*-
import random

from .analysis_metrics import raw_calibration_stats, unique_float_candidates


def normalized_weight_map(weights):
    if not isinstance(weights, dict):
        return {}
    clean = {}
    total = 0.0
    for key, value in weights.items():
        try:
            weight = float(value)
        except (TypeError, ValueError):
            continue
        if weight <= 0:
            continue
        clean[key] = weight
        total += weight
    if total <= 0:
        return {}
    return {key: value / total for key, value in clean.items()}


def calibration_profile_parameters(profile):
    if not isinstance(profile, dict):
        return {}
    parameters = {}
    for key in ("slope_target", "slope_sigma", "tpi_target", "tpi_sigma"):
        try:
            parameters[key] = float(profile[key])
        except (KeyError, TypeError, ValueError):
            continue
    return parameters


def parameter_candidates(rows, key, base_target, base_sigma, sigma_floor):
    stats = raw_calibration_stats(rows, key)
    positive_mean = stats.get("positive_mean")
    positive_stddev = stats.get("positive_stddev")
    negative_mean = stats.get("negative_mean")
    targets = [base_target]
    sigmas = [base_sigma]

    if positive_mean is not None:
        targets.extend([positive_mean, (base_target + positive_mean) * 0.5])
    if positive_mean is not None and negative_mean is not None:
        targets.append(((2.0 * positive_mean) + negative_mean) / 3.0)
    if positive_stddev is not None and positive_stddev > 0:
        sigmas.extend([positive_stddev, max(positive_stddev * 1.25, sigma_floor)])

    sigmas.extend(
        [
            max(base_sigma * 0.75, sigma_floor),
            max(base_sigma * 1.25, sigma_floor),
        ]
    )
    if positive_mean is not None and negative_mean is not None:
        separation = abs(positive_mean - negative_mean)
        if separation > 0:
            sigmas.append(max(separation * 0.5, sigma_floor))

    return {
        "targets": unique_float_candidates(targets)[:4],
        "sigmas": unique_float_candidates(sigmas, min_value=sigma_floor)[:4],
        "stats": stats,
    }


def parameter_candidate_profiles(rows, profile, max_candidates=24):
    base_profile = dict(profile if isinstance(profile, dict) else {})
    base_profile["weights"] = dict(normalized_weight_map(base_profile.get("weights", {})))
    slope_candidates = parameter_candidates(
        rows,
        "slope",
        float(base_profile.get("slope_target", 0.0)),
        max(0.5, float(base_profile.get("slope_sigma", 1.0))),
        0.5,
    )
    tpi_candidates = parameter_candidates(
        rows,
        "tpi",
        float(base_profile.get("tpi_target", 0.0)),
        max(0.02, float(base_profile.get("tpi_sigma", 0.1))),
        0.02,
    )

    candidates = []
    seen = set()
    for slope_target in slope_candidates["targets"]:
        for slope_sigma in slope_candidates["sigmas"]:
            for tpi_target in tpi_candidates["targets"]:
                for tpi_sigma in tpi_candidates["sigmas"]:
                    marker = (
                        round(slope_target, 6),
                        round(slope_sigma, 6),
                        round(tpi_target, 6),
                        round(tpi_sigma, 6),
                    )
                    if marker in seen:
                        continue
                    seen.add(marker)
                    candidate = dict(base_profile)
                    candidate["weights"] = dict(base_profile["weights"])
                    candidate["slope_target"] = slope_target
                    candidate["slope_sigma"] = slope_sigma
                    candidate["tpi_target"] = tpi_target
                    candidate["tpi_sigma"] = tpi_sigma
                    candidates.append(candidate)
                    if len(candidates) >= int(max_candidates):
                        return candidates
    return candidates or [base_profile]


def summarize_named_deltas(deltas, threshold=0.01, limit=4, empty_label="no-material-change"):
    changed = sorted(
        (
            (abs(delta), key, delta)
            for key, delta in (deltas or {}).items()
            if abs(delta) >= float(threshold)
        ),
        reverse=True,
    )
    if not changed:
        return empty_label
    return ", ".join(
        f"{key}:{delta:+.3f}" for _abs_delta, key, delta in changed[: max(1, int(limit))]
    )


def calibration_scope(applied, parameter_deltas, weight_applied, tolerance=1e-6):
    parameter_applied = any(abs(delta) > float(tolerance) for delta in parameter_deltas.values())
    if applied and parameter_applied and weight_applied:
        return "local_profile_tuning+reweighting"
    if applied and parameter_applied:
        return "local_profile_tuning"
    if applied and weight_applied:
        return "local_weight_reweighting"
    return "threshold_only"


def split_calibration_rows(rows, random_seed=42, split_ratio=0.75, min_fit_count=6, min_eval_count=3):
    if not isinstance(rows, list):
        rows = []
    rows = list(rows)
    total_rows = len(rows)
    if total_rows <= 1:
        return (
            rows,
            [],
            {
                "mode": "single_pool_disabled",
                "reason": "too_few_rows_for_holdout",
                "validation_enabled": False,
                "fit_count": total_rows,
                "evaluation_count": 0,
                "seed": int(random_seed),
            },
        )
    if total_rows < min_fit_count + min_eval_count:
        return (
            list(rows),
            [],
            {
                "mode": "single_pool_disabled",
                "reason": "insufficient_rows_for_reserved_split",
                "validation_enabled": False,
                "fit_count": total_rows,
                "evaluation_count": 0,
                "seed": int(random_seed),
            },
        )

    rng = random.Random(int(random_seed))
    positives = [row for row in rows if int(row.get("label", -1)) == 1]
    negatives = [row for row in rows if int(row.get("label", -1)) == 0]
    rng.shuffle(positives)
    rng.shuffle(negatives)

    def _split_bucket(bucket):
        bucket_size = len(bucket)
        if bucket_size <= 1:
            return bucket, []
        fit_count = int(round(bucket_size * split_ratio))
        fit_count = max(1, fit_count)
        if fit_count >= bucket_size:
            fit_count = bucket_size - 1
        eval_count = bucket_size - fit_count
        if eval_count <= 0:
            fit_count = bucket_size - 1
            eval_count = 1
        return bucket[:fit_count], bucket[fit_count:]

    fit_rows = []
    evaluation_rows = []
    for bucket in (positives, negatives):
        fit_bucket, eval_bucket = _split_bucket(bucket)
        fit_rows.extend(fit_bucket)
        evaluation_rows.extend(eval_bucket)

    # fallback to global shuffle split when stratified split is too small.
    if len(fit_rows) < min_fit_count or len(evaluation_rows) < min_eval_count:
        shuffled = list(rows)
        rng.shuffle(shuffled)
        split_index = int(round(total_rows * split_ratio))
        split_index = max(1, min(total_rows - 1, split_index))
        if split_index < min_fit_count:
            split_index = min_fit_count
        max_fit = total_rows - min_eval_count
        if split_index > max_fit:
            split_index = max(1, max_fit)
        if split_index >= total_rows:
            split_index = total_rows - 1

        fit_rows = shuffled[:split_index]
        evaluation_rows = shuffled[split_index:]
        if not evaluation_rows:
            return (
                rows,
                [],
                {
                    "mode": "single_pool_disabled",
                    "reason": "post_fallback_split_could_not_produce_validation",
                    "validation_enabled": False,
                    "fit_count": len(fit_rows),
                    "evaluation_count": len(evaluation_rows),
                    "seed": int(random_seed),
                },
            )

        return (
            fit_rows,
            evaluation_rows,
            {
                "mode": "global_holdout",
                "reason": "class_counts_insufficient_for_stratified_split",
                "validation_enabled": True,
                "fit_count": len(fit_rows),
                "evaluation_count": len(evaluation_rows),
                "seed": int(random_seed),
            },
        )

    return (
        fit_rows,
        evaluation_rows,
        {
            "mode": "stratified_holdout",
            "reason": "row-level stratified split",
            "validation_enabled": True,
            "fit_count": len(fit_rows),
            "evaluation_count": len(evaluation_rows),
            "seed": int(random_seed),
        },
    )


def empty_calibration_fit(
    base_profile,
    base_profile_parameters,
    base_metrics,
    base_scores_by_id,
):
    base_profile = dict(base_profile or {})
    base_weights = dict(base_profile.get("weights", {}))
    base_metrics = dict(base_metrics or {})
    return {
        "scope": "threshold_only",
        "applied": False,
        "base_weights": dict(base_weights),
        "weights": dict(base_weights),
        "weight_deltas": {},
        "weight_summary": "no-weight-fit",
        "base_profile_parameters": dict(base_profile_parameters or {}),
        "profile_parameters": dict(base_profile_parameters or {}),
        "parameter_deltas": {},
        "parameter_summary": "no-parameter-fit",
        "indicator_discrimination": {},
        "base_metrics": dict(base_metrics),
        "metrics": dict(base_metrics),
        "fit_metrics": dict(base_metrics),
        "evaluation_metrics": dict(base_metrics),
        "fit_base_metrics": dict(base_metrics),
        "evaluation_base_metrics": dict(base_metrics),
        "scores_by_id": dict(base_scores_by_id or {}),
        "fit_scores_by_id": dict(base_scores_by_id or {}),
        "evaluation_scores_by_id": dict(base_scores_by_id or {}),
        "validation_enabled": False,
        "split_plan": {
            "mode": "in_sample_single_pool",
            "reason": "step1: fit/eval split is a planned follow-up contract",
        },
    }


def finalize_calibration_fit(
    base_profile,
    base_profile_parameters,
    base_metrics,
    base_scores_by_id,
    best_fit,
    applied,
    base_fit_scores_by_id=None,
    evaluation_base_metrics=None,
    evaluation_scores_by_id=None,
    validation_enabled=None,
    split_plan=None,
):
    base_profile = dict(base_profile or {})
    base_weights = dict(base_profile.get("weights", {}))
    best_fit = dict(best_fit or {})
    base_metrics = dict(base_metrics or {})
    base_evaluation_metrics = dict(evaluation_base_metrics or {})
    split_plan = dict(split_plan or {})
    if validation_enabled is None:
        validation_enabled = bool(split_plan.get("validation_enabled", False))

    base_fit_scores_by_id = dict(base_fit_scores_by_id or {})
    fit_scores_by_id = dict(base_fit_scores_by_id or base_scores_by_id or {})
    evaluation_scores_by_id = dict(evaluation_scores_by_id or {})
    if not base_evaluation_metrics:
        base_evaluation_metrics = dict(base_metrics)

    if applied:
        final_profile = dict(best_fit.get("profile", {}))
        final_weights = dict(best_fit.get("weights", {}))
        fit_metrics = dict(best_fit.get("metrics", {})) or dict(base_metrics)
        fit_scores_by_id = dict(best_fit.get("scores_by_id", {}))
        final_weight_deltas = dict(best_fit.get("weight_deltas", {}))
        final_weight_summary = str(
            best_fit.get("weight_summary", "no-material-weight-change")
        )
        indicator_discrimination = dict(best_fit.get("indicator_discrimination", {}))
        weight_applied = bool(best_fit.get("weight_applied"))
    else:
        final_profile = dict(base_profile)
        final_weights = dict(base_weights)
        fit_metrics = dict(base_metrics or {})
        fit_scores_by_id = dict(base_fit_scores_by_id or base_scores_by_id or {})
        final_weight_deltas = {
            key: 0.0 for key in final_weights.keys()
        }
        final_weight_summary = "no-material-weight-change"
        indicator_discrimination = dict(best_fit.get("indicator_discrimination", {}))
        weight_applied = False
    final_profile["weights"] = dict(final_weights)

    final_profile_parameters = calibration_profile_parameters(final_profile)
    parameter_deltas = {
        key: final_profile_parameters.get(key, 0.0) - base_profile_parameters.get(key, 0.0)
        for key in (base_profile_parameters or {}).keys()
    }
    parameter_summary = summarize_named_deltas(
        parameter_deltas,
        threshold=0.01,
        limit=4,
        empty_label="no-material-parameter-change",
    )
    scope = calibration_scope(
        applied,
        parameter_deltas,
        weight_applied,
        tolerance=1e-6,
    )

    if validation_enabled and evaluation_scores_by_id:
        final_scores_by_id = dict(evaluation_scores_by_id)
        final_metrics = dict(best_fit.get("evaluation_metrics", fit_metrics))
    else:
        final_scores_by_id = dict(fit_scores_by_id)
        final_metrics = dict(fit_metrics)
    if not final_metrics:
        final_metrics = dict(base_metrics)

    if not evaluation_scores_by_id:
        evaluation_scores_by_id = dict(final_scores_by_id)

    return {
        "scope": scope,
        "applied": applied,
        "base_weights": dict(base_weights),
        "weights": final_weights,
        "weight_deltas": final_weight_deltas,
        "weight_summary": final_weight_summary,
        "base_profile_parameters": dict(base_profile_parameters or {}),
        "profile_parameters": final_profile_parameters,
        "parameter_deltas": parameter_deltas,
        "parameter_summary": parameter_summary,
        "indicator_discrimination": indicator_discrimination,
        "base_metrics": dict(base_metrics),
        "metrics": dict(final_metrics),
        "fit_metrics": dict(fit_metrics),
        "evaluation_metrics": dict(
            best_fit.get("evaluation_metrics", final_metrics)
            if validation_enabled
            else dict(fit_metrics)
        ),
        "scores_by_id": dict(final_scores_by_id),
        "fit_scores_by_id": dict(fit_scores_by_id),
        "evaluation_scores_by_id": dict(
            best_fit.get("evaluation_scores_by_id", evaluation_scores_by_id)
            if validation_enabled
            else dict(evaluation_scores_by_id)
        ),
        "base_fit_metrics": dict(base_metrics),
        "fit_base_metrics": dict(base_metrics),
        "evaluation_base_metrics": dict(base_evaluation_metrics),
        "validation_enabled": bool(validation_enabled),
        "split_plan": {
            "mode": str(split_plan.get("mode", "in_sample_single_pool")),
            "reason": str(split_plan.get("reason", "fit/evaluation split plan missing")),
            "fit_count": int(split_plan.get("fit_count", 0)),
            "evaluation_count": int(split_plan.get("evaluation_count", 0)),
            "seed": int(split_plan.get("seed", 0)),
        },
    }


def build_calibration_report_payload(
    context,
    profile,
    profile_key,
    hemisphere,
    site_layer_name,
    site_metadata_summary,
    negative_ratio,
    random_seed,
    positive_count,
    negative_count,
    calibration_fit,
    paper_evidence_summary,
):
    context = dict(context or {})
    profile = dict(profile or {})
    calibration_fit = dict(calibration_fit or {})
    metrics = dict(calibration_fit.get("metrics", {}))
    base_metrics = dict(calibration_fit.get("base_metrics", {}))
    fit_metrics = dict(calibration_fit.get("fit_metrics", metrics))
    evaluation_metrics = dict(calibration_fit.get("evaluation_metrics", metrics))
    fit_base_metrics = dict(calibration_fit.get("fit_base_metrics", base_metrics))
    evaluation_base_metrics = dict(calibration_fit.get("evaluation_base_metrics", base_metrics))
    split_plan = dict(calibration_fit.get("split_plan", {}))
    return {
        "culture_key": context.get("culture_key", ""),
        "period_key": context.get("period_key", ""),
        "profile_key": profile_key,
        "hemisphere": hemisphere,
        "site_layer_name": str(site_layer_name or ""),
        "site_metadata_summary": dict(site_metadata_summary or {}),
        "calibration_split_mode": str(split_plan.get("mode", "in_sample_single_pool")),
        "calibration_validation_enabled": bool(calibration_fit.get("validation_enabled", False)),
        "calibration_split_reason": str(split_plan.get("reason", "")),
        "fit_count": fit_metrics.get("count", 0),
        "evaluation_count": evaluation_metrics.get("count", 0),
        "negative_ratio": int(negative_ratio),
        "random_seed": int(random_seed),
        "positive_count": int(positive_count),
        "negative_count": int(negative_count),
        "valid_count": evaluation_metrics.get("count", 0),
        "base_valid_count": evaluation_base_metrics.get("count", 0),
        "roc_auc": evaluation_metrics.get("roc_auc", 0.0),
        "pr_auc": evaluation_metrics.get("pr_auc", 0.0),
        "best_f1": evaluation_metrics.get("best_f1", 0.0),
        "best_f1_threshold": evaluation_metrics.get("best_f1_threshold", 0.0),
        "best_youden_j": evaluation_metrics.get("best_youden_j", 0.0),
        "best_youden_threshold": evaluation_metrics.get("best_youden_threshold", 0.0),
        "base_roc_auc": evaluation_base_metrics.get("roc_auc", 0.0),
        "base_pr_auc": evaluation_base_metrics.get("pr_auc", 0.0),
        "base_best_f1": evaluation_base_metrics.get("best_f1", 0.0),
        "base_best_f1_threshold": evaluation_base_metrics.get("best_f1_threshold", 0.0),
        "base_best_youden_j": evaluation_base_metrics.get("best_youden_j", 0.0),
        "base_best_youden_threshold": evaluation_base_metrics.get("best_youden_threshold", 0.0),
        "fit_roc_auc": fit_metrics.get("roc_auc", 0.0),
        "fit_pr_auc": fit_metrics.get("pr_auc", 0.0),
        "fit_best_f1": fit_metrics.get("best_f1", 0.0),
        "fit_best_f1_threshold": fit_metrics.get("best_f1_threshold", 0.0),
        "fit_best_youden_j": fit_metrics.get("best_youden_j", 0.0),
        "fit_best_youden_threshold": fit_metrics.get("best_youden_threshold", 0.0),
        "fit_base_roc_auc": fit_base_metrics.get("roc_auc", 0.0),
        "fit_base_pr_auc": fit_base_metrics.get("pr_auc", 0.0),
        "fit_base_best_f1": fit_base_metrics.get("best_f1", 0.0),
        "fit_base_best_f1_threshold": fit_base_metrics.get("best_f1_threshold", 0.0),
        "fit_base_best_youden_j": fit_base_metrics.get("best_youden_j", 0.0),
        "fit_base_best_youden_threshold": fit_base_metrics.get("best_youden_threshold", 0.0),
        "evaluation_roc_auc": evaluation_metrics.get("roc_auc", 0.0),
        "evaluation_pr_auc": evaluation_metrics.get("pr_auc", 0.0),
        "evaluation_best_f1": evaluation_metrics.get("best_f1", 0.0),
        "evaluation_best_f1_threshold": evaluation_metrics.get("best_f1_threshold", 0.0),
        "evaluation_best_youden_j": evaluation_metrics.get("best_youden_j", 0.0),
        "evaluation_best_youden_threshold": evaluation_metrics.get("best_youden_threshold", 0.0),
        "evaluation_base_roc_auc": evaluation_base_metrics.get("roc_auc", 0.0),
        "evaluation_base_pr_auc": evaluation_base_metrics.get("pr_auc", 0.0),
        "evaluation_base_best_f1": evaluation_base_metrics.get("best_f1", 0.0),
        "evaluation_base_best_f1_threshold": evaluation_base_metrics.get("best_f1_threshold", 0.0),
        "evaluation_base_best_youden_j": evaluation_base_metrics.get("best_youden_j", 0.0),
        "evaluation_base_best_youden_threshold": evaluation_base_metrics.get("best_youden_threshold", 0.0),
        "calibration_scope": calibration_fit.get("scope", "threshold_only"),
        "calibration_applied": bool(calibration_fit.get("applied")),
        "tuned_weights": dict(calibration_fit.get("weights", {})),
        "base_weights": dict(calibration_fit.get("base_weights", {})),
        "tuned_weight_deltas": dict(calibration_fit.get("weight_deltas", {})),
        "tuned_weight_summary": str(
            calibration_fit.get("weight_summary", "no-material-weight-change")
        ),
        "tuned_profile_parameters": dict(
            calibration_fit.get("profile_parameters", {})
        ),
        "base_profile_parameters": dict(
            calibration_fit.get("base_profile_parameters", {})
        ),
        "tuned_parameter_deltas": dict(
            calibration_fit.get("parameter_deltas", {})
        ),
        "tuned_parameter_summary": str(
            calibration_fit.get("parameter_summary", "no-material-parameter-change")
        ),
        "indicator_discrimination": dict(
            calibration_fit.get("indicator_discrimination", {})
        ),
        "evidence_parameters": context.get("evidence", {}).get("parameters", {}),
        "paper_evidence_records": profile.get("paper_evidence_records", []),
        "paper_evidence_summary": str(paper_evidence_summary or ""),
    }
