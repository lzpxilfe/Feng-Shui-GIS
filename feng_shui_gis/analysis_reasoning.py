# -*- coding: utf-8 -*-
"""Narrative reasoning helpers for hyeol and term outputs."""

from __future__ import annotations

from .analysis_text import (
    azimuth_label,
    enclosure_hint,
    fmt_num,
    sashinsa_hint,
    score_band_label,
    tpi_class_label,
    tpi_hint,
)
from .profile_catalog import term_label_ko


def compose_term_reason(
    *,
    term_id,
    adjusted_score,
    base_score,
    elev,
    delta_rel,
    target_rel,
    fit_score,
    radius_m,
    azimuth,
    mode,
    note,
):
    mode_ko = {
        "max": "국지 최대점",
        "min": "국지 최소점",
        "gentle": "완경사점",
        "refine": "전면 보정점",
    }.get(mode, "추정점")
    mode_hint = {
        "max": "주변보다 상대적으로 높은 위치를 찾았습니다",
        "min": "주변보다 상대적으로 낮은 위치를 찾았습니다",
        "gentle": "경사가 완만한 위치를 찾았습니다",
        "refine": "중심 혈 전면에서 위치를 미세 보정했습니다",
    }.get(mode, "지형 패턴에 맞는 후보를 찾았습니다")
    return (
        f"{term_label_ko(term_id)} 후보입니다. 쉽게 보면 {mode_hint}. "
        f"요약: 점수 {fmt_num(adjusted_score, 3)}, 적합도 {fmt_num(fit_score, 3)}, "
        f"고도 {fmt_num(elev, 2)}m. "
        f"[세부] 기저점수={fmt_num(base_score, 3)}, "
        f"상대고도={fmt_num(delta_rel, 4)}(목표 {fmt_num(target_rel, 4)}), "
        f"반경={fmt_num(radius_m, 1)}m, "
        f"방위={fmt_num(azimuth, 1)}°({azimuth_label(azimuth)}), "
        f"추출방식={mode_ko}, 근거={note}."
    )
def compose_hyeol_reason(
    *,
    rank,
    selected_total,
    base_score,
    form_score,
    long_score,
    wet_score,
    tpi_norm,
    conv_score,
    relief,
    center_elev,
    threshold,
    water_distance=None,
    sashinsa_score=None,
    enclosure_index=None,
    large_tpi_norm=None,
):
    gap_text = "판정 불가"
    if base_score is not None:
        gap = base_score - threshold
        if gap >= 0:
            gap_text = f"기준치보다 +{gap:.3f} 높아 통과"
        else:
            gap_text = f"기준치보다 {gap:.3f} 낮음"

    tpi_class = tpi_class_label(tpi_norm, large_tpi_norm)
    return (
        f"혈 후보 #{rank}/{selected_total}. 한 줄 해석: {gap_text}입니다. "
        f"형국 {fmt_num(form_score, 3)}({score_band_label(form_score)}), "
        f"종심 {fmt_num(long_score, 3)}({score_band_label(long_score)}), "
        f"수렴습윤 {fmt_num(wet_score, 3)}({score_band_label(wet_score)}), "
        f"수렴도 {fmt_num(conv_score, 3)}({score_band_label(conv_score)}), "
        f"TPI {fmt_num(tpi_norm, 4)}({tpi_hint(tpi_norm)}), "
        f"사신사 {fmt_num(sashinsa_score, 3)}({sashinsa_hint(sashinsa_score)}), "
        f"장풍 {fmt_num(enclosure_index, 3)}({enclosure_hint(enclosure_index)}), "
        f"대TPI {fmt_num(large_tpi_norm, 4)}({tpi_class}), "
        f"주변 기복 {fmt_num(relief, 1)}m, 중심 고도 {fmt_num(center_elev, 2)}m. "
        f"[세부수치] 점수={fmt_num(base_score, 3)}, 기준치>={threshold:.3f}."
    )
