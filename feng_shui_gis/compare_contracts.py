# -*- coding: utf-8 -*-
"""Pure compare-contract helpers shared by plugin orchestration and tests."""


def validate_compare_feature_contract(base_layer, compare_layer, feature_uid_resolver):
    if base_layer is None or compare_layer is None:
        return {
            "ok": False,
            "message": "Missing one or more profile compare layers.",
        }

    base_uids = []
    for feature in base_layer.getFeatures():
        value = feature_uid_resolver(feature)
        if value:
            base_uids.append(str(value))

    compare_uids = []
    for feature in compare_layer.getFeatures():
        value = feature_uid_resolver(feature)
        if value:
            compare_uids.append(str(value))

    if not base_uids or not compare_uids:
        return {
            "ok": False,
            "message": "Compare result is missing feature_uid on one of the layers.",
        }

    base_unique = set(base_uids)
    compare_unique = set(compare_uids)

    if len(base_unique) != len(base_uids) or len(compare_unique) != len(compare_uids):
        return {
            "ok": False,
            "message": "Duplicate feature_uid values detected in compare outputs.",
        }

    if base_unique != compare_unique:
        missing_in_compare = sorted(base_unique - compare_unique)
        missing_in_base = sorted(compare_unique - base_unique)
        return {
            "ok": False,
            "message": (
                f"Feature UID sets differ between base/compare layers. "
                f"Missing in compare={missing_in_compare[:3]}, "
                f"extra in compare={missing_in_base[:3]}"
            ),
        }

    return {
        "ok": True,
        "message": "",
        "count": len(base_unique),
    }


def validate_compare_top_change_contract(
    base_layer,
    compare_layer,
    top_changes,
    feature_uid_resolver,
):
    if top_changes is None:
        return {
            "ok": True,
            "message": "",
            "count": 0,
            "feature_uids": [],
        }

    feature_uids = []
    seen = set()
    for row in top_changes:
        feature_uid = str(row.get("feature_uid") or "").strip()
        if not feature_uid:
            return {
                "ok": False,
                "message": "Top change row is missing feature_uid.",
                "count": len(feature_uids),
                "feature_uids": feature_uids,
            }
        if feature_uid in seen:
            continue
        seen.add(feature_uid)
        feature_uids.append(feature_uid)

    if not feature_uids:
        return {
            "ok": False,
            "message": "No valid feature_uid found in top change rows.",
            "count": 0,
            "feature_uids": [],
        }

    base_uids = []
    compare_uids = []
    for feature in base_layer.getFeatures():
        layer_uid = str(feature_uid_resolver(feature))
        if layer_uid:
            base_uids.append(layer_uid)
    for feature in compare_layer.getFeatures():
        layer_uid = str(feature_uid_resolver(feature))
        if layer_uid:
            compare_uids.append(layer_uid)

    if not base_uids or not compare_uids:
        return {
            "ok": False,
            "message": "Compare layers do not expose feature_uid for top-change validation.",
            "count": 0,
            "feature_uids": feature_uids,
        }

    base_set = set(base_uids)
    compare_set = set(compare_uids)
    requested_set = set(feature_uids)
    missing_in_base = sorted(requested_set - base_set)
    missing_in_compare = sorted(requested_set - compare_set)

    if missing_in_base or missing_in_compare:
        return {
            "ok": False,
            "message": (
                f"Top-change UID contract mismatch. "
                f"Missing in base={missing_in_base[:3]}, "
                f"missing in compare={missing_in_compare[:3]}"
            ),
            "count": len(feature_uids),
            "feature_uids": feature_uids,
        }

    return {
        "ok": True,
        "message": "",
        "count": len(feature_uids),
        "feature_uids": feature_uids,
    }


def top_score_changes(
    base_layer,
    compare_layer,
    *,
    feature_uid_resolver,
    label_resolver,
    reason_resolver,
    limit,
):
    if base_layer is None or compare_layer is None:
        return []
    base_by_uid = {}
    compare_by_uid = {}
    for feature in base_layer.getFeatures():
        feature_uid = feature_uid_resolver(feature)
        if not feature_uid:
            continue
        try:
            score = float(feature["fs_score"])
        except (KeyError, TypeError, ValueError):
            continue
        base_by_uid[feature_uid] = {
            "label": label_resolver(feature),
            "score": score,
            "reason": reason_resolver(feature),
        }
    for feature in compare_layer.getFeatures():
        feature_uid = feature_uid_resolver(feature)
        if not feature_uid:
            continue
        try:
            score = float(feature["fs_score"])
        except (KeyError, TypeError, ValueError):
            continue
        compare_by_uid[feature_uid] = {
            "label": label_resolver(feature),
            "score": score,
            "reason": reason_resolver(feature),
        }
    shared_uids = sorted(set(base_by_uid.keys()) & set(compare_by_uid.keys()))
    rows = []
    for feature_uid in shared_uids:
        base_entry = base_by_uid[feature_uid]
        compare_entry = compare_by_uid[feature_uid]
        delta = compare_entry["score"] - base_entry["score"]
        rows.append(
            {
                "feature_uid": str(feature_uid),
                "label": compare_entry.get("label")
                or base_entry.get("label")
                or f"fid:{feature_uid}",
                "base_score": base_entry["score"],
                "compare_score": compare_entry["score"],
                "delta": delta,
                "base_reason": base_entry.get("reason", ""),
                "compare_reason": compare_entry.get("reason", ""),
            }
        )
    rows.sort(
        key=lambda item: (abs(float(item.get("delta", 0.0))), float(item.get("delta", 0.0))),
        reverse=True,
    )
    return rows[: max(1, int(limit))]
