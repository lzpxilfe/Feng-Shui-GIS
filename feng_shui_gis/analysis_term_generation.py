# -*- coding: utf-8 -*-
"""Feature-ready payload helpers for term generation."""

from __future__ import annotations

from .analysis_dem_utils import mean_scores


def relief_from_ring_values(ring_values):
    if not ring_values:
        return 1.0
    return max(1.0, max(ring_values) - min(ring_values))


def core_hyeol_term_payload(
    *,
    parent_id,
    rank,
    point,
    base_score,
    center_elev,
    relief,
    reason_text,
    term_name,
):
    return {
        "term_id": "hyeol",
        "term_name": term_name,
        "parent_id": parent_id,
        "rank": rank,
        "point": point,
        "score": base_score,
        "elev": center_elev,
        "note": "core candidate",
        "mandatory": True,
        "base_score_value": base_score,
        "relief_m": relief,
        "reason_text": reason_text,
    }


def myeongdang_term_payload(
    *,
    parent_id,
    rank,
    point,
    elev,
    center_elev,
    base_score,
    relief,
    target_rel,
    fit_score,
    radius_m,
    azimuth,
    term_name,
):
    delta = (elev - center_elev) / relief
    return {
        "term_id": "myeongdang",
        "term_name": term_name,
        "parent_id": parent_id,
        "rank": rank,
        "point": point,
        "score": mean_scores(base_score, fit_score),
        "elev": elev,
        "note": "open core basin",
        "mandatory": True,
        "base_score_value": base_score,
        "delta_rel": delta,
        "target_rel": target_rel,
        "fit_score": fit_score,
        "radius_m": radius_m,
        "azimuth": azimuth,
        "mode": "refine",
        "relief_m": relief,
    }


def generic_term_payload(
    *,
    term_id,
    term_name,
    parent_id,
    rank,
    point,
    elev,
    center_elev,
    base_score,
    relief,
    target_rel,
    fit_score,
    radius_m,
    azimuth,
    mode,
):
    delta = (elev - center_elev) / relief
    return {
        "term_id": term_id,
        "term_name": term_name,
        "parent_id": parent_id,
        "rank": rank,
        "point": point,
        "score": mean_scores(base_score, fit_score),
        "elev": elev,
        "note": f"delta={delta:.3f}",
        "base_score_value": base_score,
        "delta_rel": delta,
        "target_rel": target_rel,
        "fit_score": fit_score,
        "radius_m": radius_m,
        "azimuth": azimuth,
        "mode": mode,
        "relief_m": relief,
    }


def ipsu_term_payload(
    *,
    parent_id,
    rank,
    point,
    elev,
    center_elev,
    base_score,
    relief,
    target_rel,
    fit_score,
    radius_m,
    mode,
    term_name,
):
    delta = (elev - center_elev) / relief
    return {
        "term_id": "ipsu",
        "term_name": term_name,
        "parent_id": parent_id,
        "rank": rank,
        "point": point,
        "score": mean_scores(base_score, fit_score),
        "elev": elev,
        "note": f"ring_min delta={delta:.3f}",
        "base_score_value": base_score,
        "delta_rel": delta,
        "target_rel": target_rel,
        "fit_score": fit_score,
        "radius_m": radius_m,
        "azimuth": None,
        "mode": mode,
        "relief_m": relief,
    }


def misa_term_payload(
    *,
    parent_id,
    rank,
    point,
    elev,
    center_elev,
    base_score,
    relief,
    target_rel,
    fit_score,
    radius_m,
    azimuth,
    term_name,
):
    delta = (elev - center_elev) / relief
    return {
        "term_id": "misa",
        "term_name": term_name,
        "parent_id": parent_id,
        "rank": rank,
        "point": point,
        "score": mean_scores(base_score, fit_score),
        "elev": elev,
        "note": f"gentle delta={delta:.3f}",
        "base_score_value": base_score,
        "delta_rel": delta,
        "target_rel": target_rel,
        "fit_score": fit_score,
        "radius_m": radius_m,
        "azimuth": azimuth,
        "mode": "gentle",
        "relief_m": relief,
    }
