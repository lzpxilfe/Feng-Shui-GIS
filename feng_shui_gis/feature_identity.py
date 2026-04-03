# -*- coding: utf-8 -*-
import hashlib


def normalized_feature_uid_value(value):
    if value is None:
        return ""
    if isinstance(value, float):
        if value == int(value):
            return f"{int(value)}"
        return f"{value:.12g}"
    return str(value).strip()


def is_derived_uid_excluded_field(name):
    lowered = str(name or "").strip().lower()
    if not lowered:
        return True
    if lowered in ("feature_uid", "cmp_feature_uid"):
        return True
    return lowered.startswith(("fs_", "cal_", "cmp_", "mt_"))


def _feature_field_names(feature, field_names=None):
    if field_names is not None:
        return list(field_names)
    try:
        return list(feature.fields().names())
    except (AttributeError, TypeError):
        return []


def feature_uid(feature, field_names=None):
    if feature is None:
        return None

    names = _feature_field_names(feature, field_names=field_names)
    lowered = {name.lower(): name for name in names}
    for key in (
        "feature_uid",
        "uid",
        "site_uid",
        "site_id",
        "point_id",
        "gid",
        "id",
        "fid",
        "fs_id",
        "cal_id",
    ):
        field_name = lowered.get(key)
        if not field_name:
            continue
        try:
            value = feature[field_name]
        except (KeyError, TypeError, ValueError):
            continue
        normalized = normalized_feature_uid_value(value)
        if normalized:
            if field_name.lower() == "feature_uid":
                return normalized
            return f"{field_name}:{normalized}"

    stable_parts = []
    for name in names:
        if is_derived_uid_excluded_field(name):
            continue
        try:
            value = feature[name]
        except (KeyError, TypeError, ValueError):
            continue
        normalized = normalized_feature_uid_value(value)
        if normalized:
            stable_parts.append(f"{name}={normalized}")

    geom_key = "no_geometry"
    try:
        has_geometry = bool(feature.hasGeometry())
    except (AttributeError, TypeError):
        has_geometry = False
    if has_geometry:
        try:
            geom_wkb = feature.geometry().asWkb()
            if geom_wkb:
                geom_key = hashlib.sha1(bytes(geom_wkb)).hexdigest()
        except (AttributeError, TypeError, ValueError):
            pass

    payload = "|".join(stable_parts)
    return hashlib.sha1(f"{geom_key}|{payload}".encode("utf-8")).hexdigest()


def feature_uid_index(layer, field_names=None):
    index = {}
    if layer is None:
        return index
    for feature in layer.getFeatures():
        try:
            feature_id = int(feature.id())
        except (TypeError, ValueError, AttributeError):
            continue
        uid = feature_uid(feature, field_names=field_names)
        if not uid:
            uid = f"fid:{feature_id}"
        index.setdefault(uid, []).append(feature_id)
    return index


def duplicate_uids_from_index(uid_index):
    duplicates = []
    for uid, feature_ids in (uid_index or {}).items():
        if len(feature_ids) > 1:
            duplicates.append(str(uid))
    return sorted(duplicates)


def duplicate_feature_uids(layer, field_names=None):
    return duplicate_uids_from_index(
        feature_uid_index(layer, field_names=field_names)
    )


def uid_match_summary(layer, feature_uids, field_names=None):
    uid_index = feature_uid_index(layer, field_names=field_names)
    present = []
    missing = []
    ambiguous = []
    seen_ids = set()
    feature_ids = []
    for feature_uid_value in feature_uids or []:
        if feature_uid_value is None:
            continue
        key = str(feature_uid_value).strip()
        if not key:
            continue
        matches = uid_index.get(key, [])
        if not matches:
            if key not in missing:
                missing.append(key)
            continue
        if len(matches) > 1:
            if key not in ambiguous:
                ambiguous.append(key)
            continue
        present.append(key)
        feature_id = matches[0]
        if feature_id in seen_ids:
            continue
        seen_ids.add(feature_id)
        feature_ids.append(feature_id)
    return {
        "present": present,
        "missing": missing,
        "ambiguous": ambiguous,
        "feature_ids": feature_ids,
    }


def feature_ids_for_uids(layer, feature_uids, field_names=None):
    return uid_match_summary(
        layer,
        feature_uids,
        field_names=field_names,
    )["feature_ids"]


def uid_lookup_summary(layer, feature_uids, field_names=None):
    summary = uid_match_summary(
        layer,
        feature_uids,
        field_names=field_names,
    )
    return summary["present"], summary["missing"], summary["ambiguous"]


def normalize_change_uids(change_rows):
    change_uids = []
    seen = set()
    for row in change_rows or []:
        if not isinstance(row, dict):
            continue
        feature_uid_value = row.get("feature_uid")
        if feature_uid_value:
            key = str(feature_uid_value).strip()
            if key and key not in seen:
                seen.add(key)
                change_uids.append(key)
            continue
    return change_uids
