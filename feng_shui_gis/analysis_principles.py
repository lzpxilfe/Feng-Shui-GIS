# -*- coding: utf-8 -*-
"""Principle-first site interpretation helpers."""

from __future__ import annotations

from .analysis_text import (
    enclosure_hint,
    fmt_num,
    sashinsa_hint,
    score_band_label,
    tpi_hint,
)


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean_available(*values):
    valid = [_to_float(value) for value in values]
    valid = [value for value in valid if value is not None]
    if not valid:
        return None
    return sum(valid) / len(valid)


def _truncate(text, limit):
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def build_principle_records(*, indicators, dem_metrics, water_distance=None):
    indicators = indicators if isinstance(indicators, dict) else {}
    dem_metrics = dem_metrics if isinstance(dem_metrics, dict) else {}

    form_score = _to_float(dem_metrics.get("form_score"))
    long_score = _to_float(dem_metrics.get("long_score"))
    tpi_score = _to_float(indicators.get("tpi"))
    tpi_norm = _to_float(dem_metrics.get("tpi_norm"))
    sashinsa_score = _to_float(dem_metrics.get("sashinsa_score"))
    enclosure_score = _to_float(dem_metrics.get("enclosure_index"))
    water_score = _to_float(indicators.get("water"))
    dem_water_score = _to_float(dem_metrics.get("dem_water_score"))
    water_distance_value = _to_float(water_distance)

    records = [
        {
            "key": "form",
            "label": "배산/형국",
            "score": form_score,
            "band": score_band_label(form_score),
            "detail": (
                f"형국 {fmt_num(form_score, 3)}" if form_score is not None else "형국 정보 없음"
            ),
        },
        {
            "key": "hyeol",
            "label": "혈 조건",
            "score": _mean_available(long_score, tpi_score),
            "band": score_band_label(_mean_available(long_score, tpi_score)),
            "detail": ", ".join(
                part
                for part in (
                    f"종심 {fmt_num(long_score, 3)}" if long_score is not None else "",
                    (
                        f"TPI {fmt_num(tpi_norm, 4)}({tpi_hint(tpi_norm)})"
                        if tpi_norm is not None
                        else ""
                    ),
                )
                if part
            )
            or "혈 조건 정보 없음",
        },
        {
            "key": "sashinsa",
            "label": "사신사",
            "score": sashinsa_score,
            "band": score_band_label(sashinsa_score),
            "detail": (
                f"사신사 {fmt_num(sashinsa_score, 3)}({sashinsa_hint(sashinsa_score)})"
                if sashinsa_score is not None
                else "사신사 정보 없음"
            ),
        },
        {
            "key": "enclosure",
            "label": "장풍/감쌈",
            "score": enclosure_score,
            "band": score_band_label(enclosure_score),
            "detail": (
                f"장풍 {fmt_num(enclosure_score, 3)}({enclosure_hint(enclosure_score)})"
                if enclosure_score is not None
                else "장풍 정보 없음"
            ),
        },
        {
            "key": "water",
            "label": "득수/수계 관계",
            "score": water_score,
            "band": score_band_label(water_score),
            "detail": ", ".join(
                part
                for part in (
                    f"통합수계 {fmt_num(water_score, 3)}" if water_score is not None else "",
                    (
                        f"미시수렴 {fmt_num(dem_water_score, 3)}"
                        if dem_water_score is not None
                        else ""
                    ),
                    (
                        f"수계거리 {fmt_num(water_distance_value, 1)}m"
                        if water_distance_value is not None
                        else ""
                    ),
                )
                if part
            )
            or "수계 정보 없음",
        },
    ]
    return records


def build_principle_summary(records, limit=None):
    if not isinstance(records, list):
        return "원리 판독 정보 부족"
    parts = []
    for record in records:
        if not isinstance(record, dict):
            continue
        label = str(record.get("label", "")).strip()
        band = str(record.get("band", "")).strip()
        detail = str(record.get("detail", "")).strip()
        if not label:
            continue
        if detail:
            parts.append(f"{label} {band}({detail})")
        elif band:
            parts.append(f"{label} {band}")
        else:
            parts.append(label)
        if limit is not None and len(parts) >= max(1, int(limit)):
            break
    return "; ".join(parts) if parts else "원리 판독 정보 부족"


def build_principle_note(records, *, strong_limit=2, low_threshold=0.5):
    if not isinstance(records, list):
        return "원리 판독 정보 부족"
    valid = [
        record
        for record in records
        if isinstance(record, dict) and _to_float(record.get("score")) is not None
    ]
    if not valid:
        return "원리 판독 정보 부족"

    ranked = sorted(valid, key=lambda item: float(item["score"]), reverse=True)
    best_score = float(ranked[0]["score"])
    if best_score < float(low_threshold):
        weakest = min(valid, key=lambda item: float(item["score"]))
        return _truncate(
            f"핵심 원리 전반 낮음; {weakest['label']} 보완 필요",
            80,
        )

    strong = ranked[: max(1, int(strong_limit))]
    note = ", ".join(f"{item['label']} {item['band']}" for item in strong)

    weakest = min(valid, key=lambda item: float(item["score"]))
    if weakest not in strong and float(weakest["score"]) < 0.55:
        note = f"{note}; {weakest['label']} 보완 필요"
    return _truncate(note, 80)
