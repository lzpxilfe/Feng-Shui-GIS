# -*- coding: utf-8 -*-
"""Pure math and split helpers for calibration workflows."""

import math
import random


def split_calibration_rows_once(rows, random_seed=42, validation_ratio=0.20):
    if not rows:
        return {"train": [], "validation": []}

    items = list(rows)
    try:
        ratio = float(validation_ratio)
    except (TypeError, ValueError):
        ratio = 0.20
    if not (0.0 < ratio < 1.0):
        return {"train": items, "validation": []}

    rng = random.Random(int(random_seed))
    positives = [row for row in items if int(row.get("label", 0)) == 1]
    negatives = [row for row in items if int(row.get("label", 0)) == 0]
    if not positives or not negatives:
        rng.shuffle(items)
        validation_count = max(0, int(len(items) * ratio))
        if validation_count <= 0:
            return {"train": items, "validation": []}
        return {"train": items[validation_count:], "validation": items[:validation_count]}

    rng.shuffle(positives)
    rng.shuffle(negatives)
    pos_validation = int(len(positives) * ratio)
    neg_validation = int(len(negatives) * ratio)
    pos_validation = min(max(0, pos_validation), max(0, len(positives) - 1))
    neg_validation = min(max(0, neg_validation), max(0, len(negatives) - 1))
    if pos_validation == 0 and len(positives) >= 2 and len(items) >= 4:
        pos_validation = 1
    if neg_validation == 0 and len(negatives) >= 2 and len(items) >= 4:
        neg_validation = 1
    if pos_validation + neg_validation == 0:
        return {"train": items, "validation": []}

    train_rows = []
    validation_rows = []
    train_rows.extend(positives[pos_validation:])
    validation_rows.extend(positives[:pos_validation])
    train_rows.extend(negatives[neg_validation:])
    validation_rows.extend(negatives[:neg_validation])
    rng.shuffle(train_rows)
    rng.shuffle(validation_rows)
    return {"train": train_rows, "validation": validation_rows}


def split_calibration_rows(
    rows,
    random_seed=42,
    validation_ratio=0.20,
    evaluation_ratio=0.10,
):
    split = split_calibration_rows_once(
        rows,
        random_seed=random_seed,
        validation_ratio=validation_ratio,
    )
    if not rows:
        split["evaluation"] = []
        return split

    try:
        eval_ratio = float(evaluation_ratio)
    except (TypeError, ValueError):
        eval_ratio = 0.10
    if not (0.0 < eval_ratio < 1.0):
        split["evaluation"] = []
        return split

    train_rows = split.get("train", [])
    if not train_rows:
        split["evaluation"] = []
        return split

    evaluation_split = split_calibration_rows_once(
        train_rows,
        random_seed=random_seed + 137,
        validation_ratio=eval_ratio,
    )
    split["train"] = evaluation_split["train"]
    split["evaluation"] = evaluation_split["validation"]
    return split


def metrics_better(candidate, baseline, tolerance=1e-6):
    candidate_values = (
        float(candidate.get("roc_auc", 0.0)),
        float(candidate.get("pr_auc", 0.0)),
        float(candidate.get("best_f1", 0.0)),
        float(candidate.get("best_youden_j", 0.0)),
    )
    baseline_values = (
        float(baseline.get("roc_auc", 0.0)),
        float(baseline.get("pr_auc", 0.0)),
        float(baseline.get("best_f1", 0.0)),
        float(baseline.get("best_youden_j", 0.0)),
    )
    for cand_value, base_value in zip(candidate_values, baseline_values):
        if cand_value > (base_value + tolerance):
            return True
        if cand_value < (base_value - tolerance):
            return False
    return False


def distribution_stats(values):
    if not values:
        return None, None
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return mean, math.sqrt(max(0.0, variance))


def unique_float_candidates(values, min_value=None, max_value=None):
    unique = []
    seen = set()
    for value in values:
        try:
            clean = float(value)
        except (TypeError, ValueError):
            continue
        if min_value is not None:
            clean = max(float(min_value), clean)
        if max_value is not None:
            clean = min(float(max_value), clean)
        marker = round(clean, 6)
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(clean)
    return unique
