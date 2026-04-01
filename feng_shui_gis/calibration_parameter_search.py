# -*- coding: utf-8 -*-
"""Pure helpers for calibration parameter candidate generation."""

from .calibration_math import distribution_stats, unique_float_candidates


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


def parameter_candidate_profiles(profile, slope_candidates, tpi_candidates, max_candidates=24):
    base_profile = dict(profile)
    base_profile["weights"] = dict(base_profile.get("weights", {}))
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
                    if len(candidates) >= max(1, int(max_candidates)):
                        return candidates
    return candidates or [base_profile]
