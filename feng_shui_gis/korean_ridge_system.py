# -*- coding: utf-8 -*-
"""Ridge class catalog, and the Korean named ridge system it is not.

The plugin grades extracted ridges by length and continuity *within the DEM
extent the user supplied*. That grade is useful, but it is a local relative
rank: widen or narrow the extent and the same ridge changes grade.

The Sangyeongpyo hierarchy — daegan, jeonggan, jeongmaek — is the opposite
kind of thing. Those are proper names fixed at national scale, with settled
courses. Labelling a locally-computed rank with them asserts an identification
the computation cannot make, so this module keeps the two apart and makes the
named system available only as a declared reference.
"""

from __future__ import annotations

from .config_loader import load_json

_RIDGE_FILE = "ridge_classes.json"


def _require_dict(value, context):
    if not isinstance(value, dict) or not value:
        raise RuntimeError(f"{context} must be a non-empty JSON object.")
    return value


def _require_list(value, context):
    if not isinstance(value, list) or not value:
        raise RuntimeError(f"{context} must be a non-empty JSON array.")
    return value


def _require_localized(value, context):
    node = _require_dict(value, context)
    for language in ("ko", "en"):
        if not str(node.get(language, "")).strip():
            raise RuntimeError(f"{context} must provide a '{language}' string.")
    return node


def _validate(catalog):
    catalog = _require_dict(catalog, _RIDGE_FILE)

    classes = _require_list(
        catalog.get("computed_classes"), f"{_RIDGE_FILE}.computed_classes"
    )
    seen = set()
    for index, entry in enumerate(classes):
        context = f"{_RIDGE_FILE}.computed_classes[{index}]"
        entry = _require_dict(entry, context)
        class_id = str(entry.get("id", "")).strip()
        if not class_id:
            raise RuntimeError(f"{context}.id must not be empty.")
        if class_id in seen:
            raise RuntimeError(f"{context}.id duplicates '{class_id}'.")
        seen.add(class_id)
        _require_localized(entry.get("label"), f"{context}.label")
        _require_localized(entry.get("definition"), f"{context}.definition")

    named = _require_dict(catalog.get("named_system"), f"{_RIDGE_FILE}.named_system")
    _require_localized(named.get("label"), f"{_RIDGE_FILE}.named_system.label")
    # The whole point of this file is that the plugin does not identify the
    # named system. Flipping that flag without implementing the match would
    # reintroduce exactly the claim this module exists to prevent.
    if named.get("identified_by_this_plugin") is not False:
        raise RuntimeError(
            f"{_RIDGE_FILE}.named_system.identified_by_this_plugin must stay false "
            "until an authoritative reference ridgeline layer is actually matched."
        )
    for field in ("why_not_identified", "what_would_be_required"):
        _require_localized(named.get(field), f"{_RIDGE_FILE}.named_system.{field}")

    ranks = _require_list(named.get("ranks"), f"{_RIDGE_FILE}.named_system.ranks")
    rank_ids = set()
    for index, rank in enumerate(ranks):
        context = f"{_RIDGE_FILE}.named_system.ranks[{index}]"
        rank = _require_dict(rank, context)
        rank_id = str(rank.get("id", "")).strip()
        if not rank_id:
            raise RuntimeError(f"{context}.id must not be empty.")
        if rank_id in rank_ids:
            raise RuntimeError(f"{context}.id duplicates '{rank_id}'.")
        rank_ids.add(rank_id)
        _require_localized(rank.get("label"), f"{context}.label")

    # A computed class id that collides with a named rank id would let the two
    # vocabularies blur back together in field values and legends.
    collisions = seen & rank_ids
    if collisions:
        raise RuntimeError(
            f"{_RIDGE_FILE}: computed class ids collide with named system ranks: "
            + ", ".join(sorted(collisions))
        )
    return catalog


def ridge_catalog():
    return _validate(load_json(_RIDGE_FILE))


def computed_ridge_classes():
    """Classes this plugin actually assigns, in legend order."""
    return list(ridge_catalog()["computed_classes"])


def computed_ridge_class_ids():
    return tuple(entry["id"] for entry in computed_ridge_classes())


def _localized(node, language):
    if not isinstance(node, dict):
        return ""
    lang = str(language or "ko").strip().lower()
    return str(node.get(lang) or node.get("en") or node.get("ko") or "")


def ridge_class_label(class_id, language="ko"):
    for entry in computed_ridge_classes():
        if entry["id"] == class_id:
            return _localized(entry.get("label"), language) or class_id
    return class_id


def ridge_class_definition(class_id, language="ko"):
    for entry in computed_ridge_classes():
        if entry["id"] == class_id:
            return _localized(entry.get("definition"), language)
    return ""


def ridge_class_is_extent_relative(class_id):
    """True when the grade only means something inside the analysed extent."""
    for entry in computed_ridge_classes():
        if entry["id"] == class_id:
            return bool(entry.get("extent_relative", False))
    return False


def named_ridge_system():
    """The Sangyeongpyo hierarchy, as declared reference only."""
    return dict(ridge_catalog()["named_system"])


def named_system_disclaimer(language="ko"):
    """Why a computed ridge grade cannot name a daegan or jeongmaek."""
    return _localized(named_ridge_system().get("why_not_identified"), language)


def named_system_requirement(language="ko"):
    """What identifying the named system would actually take."""
    return _localized(named_ridge_system().get("what_would_be_required"), language)
