# -*- coding: utf-8 -*-
import math


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
    for candidate_value, baseline_value in zip(candidate_values, baseline_values):
        if candidate_value > (baseline_value + tolerance):
            return True
        if candidate_value < (baseline_value - tolerance):
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


def raw_calibration_stats(rows, key):
    positives = []
    negatives = []
    for row in rows:
        raw_value = row.get("raw", {}).get(key)
        if raw_value is None:
            continue
        value = float(raw_value)
        if int(row["label"]) == 1:
            positives.append(value)
        else:
            negatives.append(value)
    positive_mean, positive_stddev = distribution_stats(positives)
    negative_mean, negative_stddev = distribution_stats(negatives)
    return {
        "positive_count": len(positives),
        "negative_count": len(negatives),
        "positive_mean": positive_mean,
        "positive_stddev": positive_stddev,
        "negative_mean": negative_mean,
        "negative_stddev": negative_stddev,
    }


def score_gaussian(value, target, sigma):
    if value is None:
        return None
    sigma = max(float(sigma), 1e-9)
    return math.exp(-((float(value) - float(target)) / sigma) ** 2)


def score_aspect(aspect_deg, hemisphere, context=None):
    if aspect_deg is None:
        return None
    if context:
        target = float(context["aspect_target"])
        sharpness = max(0.5, float(context["aspect_sharpness"]))
    else:
        target = 180.0 if hemisphere == "north" else 0.0
        sharpness = 1.0
    diff = abs((float(aspect_deg) - target + 180.0) % 360.0 - 180.0)
    base_score = (math.cos(math.radians(diff)) + 1.0) / 2.0
    return max(0.0, min(1.0, base_score**sharpness))


def score_water_distance(distance_m, context=None):
    if distance_m is None:
        return None
    if not context:
        raise RuntimeError("Water-distance scoring requires a validated context.")
    target = float(context["water_distance_target"])
    sigma = float(context["water_distance_sigma"])
    score = math.exp(-((float(distance_m) - target) / sigma) ** 2)
    if float(distance_m) < 30.0:
        return max(0.1, score * 0.5)
    return score


def suppress_near_duplicates(candidates, min_distance, keep):
    selected = []
    min_sq = float(min_distance) * float(min_distance)
    for item in candidates:
        point = item["point"]
        too_close = False
        for selected_item in selected:
            dx = point.x() - selected_item["point"].x()
            dy = point.y() - selected_item["point"].y()
            if (dx * dx) + (dy * dy) < min_sq:
                too_close = True
                break
        if too_close:
            continue
        selected.append(item)
        if len(selected) >= int(keep):
            break
    return selected


def trapezoid_auc(points):
    if len(points) < 2:
        return 0.0
    ordered = sorted(points, key=lambda item: item[0])
    area = 0.0
    for index in range(1, len(ordered)):
        x0, y0 = ordered[index - 1]
        x1, y1 = ordered[index]
        dx = x1 - x0
        if dx <= 0:
            continue
        area += dx * ((y0 + y1) * 0.5)
    return max(0.0, min(1.0, area))


def binary_classification_metrics(labels, scores):
    if not labels or not scores or len(labels) != len(scores):
        return {
            "count": 0,
            "roc_auc": 0.0,
            "pr_auc": 0.0,
            "best_f1": 0.0,
            "best_f1_threshold": 0.0,
            "best_youden_j": 0.0,
            "best_youden_threshold": 0.0,
        }

    pairs = sorted(zip(scores, labels), key=lambda item: item[0], reverse=True)
    positive_count = sum(1 for _, label in pairs if label == 1)
    negative_count = sum(1 for _, label in pairs if label == 0)
    if positive_count == 0 or negative_count == 0:
        return {
            "count": len(pairs),
            "roc_auc": 0.0,
            "pr_auc": 0.0,
            "best_f1": 0.0,
            "best_f1_threshold": 0.0,
            "best_youden_j": 0.0,
            "best_youden_threshold": 0.0,
        }

    tp = 0
    fp = 0
    roc_points = [(0.0, 0.0)]
    pr_points = [(0.0, 1.0)]
    best_f1 = (0.0, pairs[0][0])
    best_youden = (-999.0, pairs[0][0])

    index = 0
    while index < len(pairs):
        score = pairs[index][0]
        group_tp = 0
        group_fp = 0
        while index < len(pairs) and pairs[index][0] == score:
            if pairs[index][1] == 1:
                group_tp += 1
            else:
                group_fp += 1
            index += 1

        tp += group_tp
        fp += group_fp
        tpr = tp / positive_count
        fpr = fp / negative_count
        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tpr
        roc_points.append((fpr, tpr))
        pr_points.append((recall, precision))

        f1 = (
            (2.0 * precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        if f1 > best_f1[0]:
            best_f1 = (f1, score)
        youden = tpr - fpr
        if youden > best_youden[0]:
            best_youden = (youden, score)

    return {
        "count": len(pairs),
        "roc_auc": trapezoid_auc(roc_points),
        "pr_auc": trapezoid_auc(pr_points),
        "best_f1": best_f1[0],
        "best_f1_threshold": best_f1[1],
        "best_youden_j": best_youden[0],
        "best_youden_threshold": best_youden[1],
    }
